"""Skill analysis endpoints — /api/skill-breakdown, /api/cooldown-analysis."""
import api._paths  # noqa: F401

from fastapi import APIRouter, HTTPException
from typing import Any, Dict, List

from api.routers.user_data import _dict_to_user_data
from api.routers.dps import _make_serializable
from streamlit_app.utils.dps_calculator import (
    aggregate_stats,
    get_combat_mode_enum,
    calculate_effective_defense_pen_with_sources,
    calculate_effective_attack_speed_with_sources,
)
from core.constants import BASE_MIN_DMG, BASE_MAX_DMG
from core.damage import calculate_final_damage_mult
from game.skills import DPSCalculator, create_character_at_level
from game.job_classes import JobClass, get_main_stat_name, get_secondary_stat_name
from game.cubes import CombatMode, COMBAT_SCENARIO_PARAMS
from game.artifacts import calculate_book_of_ancient_bonus

router = APIRouter(tags=["skills"])


def _build_character(stats: Dict[str, Any], job_class: JobClass,
                     combat_mode_str: str, cd_override: float = -1.0):
    """Build a CharacterState from aggregated stats. Mirrors calculate_dps() in dps_calculator.py."""
    main_stat_type = get_main_stat_name(job_class)

    total_defense_pen, _ = calculate_effective_defense_pen_with_sources(stats.get('def_pen_sources', []))
    total_attack_speed, _ = calculate_effective_attack_speed_with_sources(stats.get('attack_speed_sources', []))
    fd_mult = calculate_final_damage_mult(stats.get('final_damage_sources', []))
    fd_correction = stats.get('final_damage_correction', 1.0)
    if fd_correction != 1.0:
        fd_mult *= fd_correction

    main_stat_flat = stats.get(f'{main_stat_type}_flat', 0)
    main_stat_pct = stats.get(f'{main_stat_type}_pct', 0)
    attack_flat = max(stats.get('attack_flat', 0), 10000)
    base_atk = attack_flat * (1 + stats.get('attack_pct', 0) / 100) + stats.get('total_attack_adjustment', 0)

    book_stars = stats.get('book_of_ancient_stars', 0)
    crit_rate = stats['crit_rate']
    _, cd_from_book = calculate_book_of_ancient_bonus(book_stars, crit_rate / 100)
    total_crit_damage = stats['crit_damage'] + (cd_from_book * 100)

    combat_mode_enum = get_combat_mode_enum(combat_mode_str)
    scenario = COMBAT_SCENARIO_PARAMS.get(combat_mode_enum, COMBAT_SCENARIO_PARAMS[CombatMode.STAGE])
    mob_fraction = scenario.mob_time_fraction

    level = stats.get('level', 140)
    all_skills = int(stats.get('all_skills_bonus', 0))
    char = create_character_at_level(level, all_skills, job_class=job_class)

    char.attack = base_atk
    char.main_stat_flat = main_stat_flat
    char.main_stat_pct = main_stat_pct
    char.main_stat_conversion = stats.get('main_stat_conversion', 0)

    secondary_type = get_secondary_stat_name(job_class)
    char.secondary_stat_flat = stats.get(f'{secondary_type}_flat', 0)
    char.secondary_stat_pct = stats.get(f'{secondary_type}_pct', 0)

    char.damage_pct = stats['damage_pct'] + stats['normal_damage'] * mob_fraction + stats['boss_damage'] * (1 - mob_fraction)
    char.boss_damage = stats['boss_damage']
    char.normal_damage = 0

    char.crit_rate = crit_rate
    char.crit_damage = total_crit_damage
    char.min_dmg_mult = stats['min_dmg_mult']
    char.max_dmg_mult = stats['max_dmg_mult']
    char.skill_damage = stats.get('skill_damage', 0)
    char.basic_attack_damage = stats.get('basic_attack_damage', 0)
    char.final_damage_pct = (fd_mult - 1) * 100
    char.def_pen_pct = total_defense_pen * 100
    char.attack_speed_pct = total_attack_speed
    char.ba_target_bonus = int(stats.get('ba_target_bonus', 0))
    char.skill_1st_bonus = int(stats.get('skill_1st_bonus', 0))
    char.skill_2nd_bonus = int(stats.get('skill_2nd_bonus', 0))
    char.skill_3rd_bonus = int(stats.get('skill_3rd_bonus', 0))
    char.skill_4th_bonus = int(stats.get('skill_4th_bonus', 0))
    char.skill_cd_reduction = cd_override if cd_override >= 0 else stats.get('skill_cd_reduction', 0)

    return char, scenario


@router.post("/skill-breakdown")
def skill_breakdown_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return per-skill DPS breakdown for the given user data.

    Body fields:
      - user_data: dict — UserData fields
      - combat_mode: str, optional
      - enemy_def: float, optional
    """
    try:
        user_data_dict = body.get("user_data", body)
        user_data = _dict_to_user_data(user_data_dict)
        combat_mode = body.get("combat_mode", user_data.combat_mode)
        enemy_def = float(body.get("enemy_def", 0.752))
        job_class = JobClass(user_data.job_class)

        stats = aggregate_stats(user_data)
        char, scenario = _build_character(stats, job_class, combat_mode)
        calc = DPSCalculator(char, enemy_def=enemy_def)

        dmg_range_mult = (BASE_MIN_DMG + stats['min_dmg_mult'] + BASE_MAX_DMG + stats['max_dmg_mult']) / 2 / 100
        hex_mult = stats.get('hex_multiplier', 1.0)

        raw = calc.get_skill_damage_breakdown(
            fight_duration=scenario.fight_duration,
            num_enemies=scenario.num_enemies,
            mob_time_fraction=scenario.mob_time_fraction,
        )

        result = {}
        for skill_name, info in raw.items():
            result[skill_name] = {
                **info,
                'dps': info['dps'] * dmg_range_mult * hex_mult,
                'total_damage': info.get('total_damage', 0) * dmg_range_mult * hex_mult,
            }

        return _make_serializable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cooldown-analysis")
def cooldown_analysis_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sweep CD reduction 0-10s in 0.5s steps and return DPS + per-skill breakdown at each step.

    Body fields:
      - user_data: dict — UserData fields
      - combat_mode: str, optional
      - enemy_def: float, optional

    Returns:
      {
        "summary": [{"cd_reduction": 0.0, "total_dps": ...}, ...],
        "breakdowns": {"0.0": [{"skill": ..., "dps": ..., "pct": ..., "skill_type": ...}, ...], ...}
      }
    """
    try:
        user_data_dict = body.get("user_data", body)
        user_data = _dict_to_user_data(user_data_dict)
        combat_mode = body.get("combat_mode", user_data.combat_mode)
        enemy_def = float(body.get("enemy_def", 0.752))
        job_class = JobClass(user_data.job_class)

        stats = aggregate_stats(user_data)
        dmg_range_mult = (BASE_MIN_DMG + stats['min_dmg_mult'] + BASE_MAX_DMG + stats['max_dmg_mult']) / 2 / 100
        hex_mult = stats.get('hex_multiplier', 1.0)

        cd_values: List[float] = [x * 0.5 for x in range(0, 21)]  # 0.0 to 10.0
        summary = []
        breakdowns: Dict[str, List[Dict]] = {}

        for cd_val in cd_values:
            char, scenario = _build_character(stats, job_class, combat_mode, cd_override=cd_val)
            calc = DPSCalculator(char, enemy_def=enemy_def)
            raw = calc.get_skill_damage_breakdown(
                fight_duration=scenario.fight_duration,
                num_enemies=scenario.num_enemies,
                mob_time_fraction=scenario.mob_time_fraction,
            )

            total_dps = sum(info['dps'] for info in raw.values()) * dmg_range_mult * hex_mult
            summary.append({"cd_reduction": cd_val, "total_dps": total_dps})

            skill_rows = []
            for skill_name, info in raw.items():
                display = 'Basic Attack' if info['skill_type'] == 'basic' else info['display_name']
                skill_rows.append({
                    "skill": display,
                    "skill_name": skill_name,
                    "dps": info['dps'] * dmg_range_mult * hex_mult,
                    "pct": info['pct_of_total'],
                    "skill_type": info['skill_type'],
                })
            breakdowns[str(cd_val)] = skill_rows

        return {"summary": summary, "breakdowns": breakdowns}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
