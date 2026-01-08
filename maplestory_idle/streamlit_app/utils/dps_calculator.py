"""
Shared DPS calculation functions for Streamlit pages.

This module provides the core stat aggregation and DPS calculation functions
used by both the Equipment page and the Upgrade Optimizer page.

All special potentials are properly handled:
- All Skills → Final Damage (via skill rotation model)
- BA Targets → Final Damage (based on BA% of DPS)
- Skill CD → Final Damage (DPS comparison)
- Buff Duration → Final Damage (MB uptime)
- Crit Rate/Damage → Direct stats (with Book of Ancient CR→CD conversion)
- Defense Pen → Multiplicative list
- Final Damage → Multiplicative list
"""
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add parent directory to path for imports (maplestory_idle root)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import core damage calculation functions
from core.damage import (
    calculate_damage,
    calculate_defense_pen,
    calculate_final_damage_mult,
    calculate_total_dex,
    calculate_attack_speed,
)
from equipment import get_amplify_multiplier
from artifacts import (
    calculate_book_of_ancient_bonus,
    calculate_hex_multiplier,
    ARTIFACTS,
)
from companions import COMPANIONS
from weapons import calculate_weapon_atk_str
from weapon_mastery import calculate_mastery_stages_from_weapons, calculate_mastery_stats
from skills import (
    calculate_all_skills_value, create_character_at_level, DPSCalculator,
    BOWMASTER_SKILLS, JobSkillBonus, create_character_with_job_bonuses,
    calculate_job_skill_value, Job,
)
from cubes import BA_TARGETS_MODE_MULTIPLIER, CombatMode
from utils.data_manager import EQUIPMENT_SLOTS


# Constants
HEX_MULTIPLIER = 1.24
BASE_MIN_DMG = 60.0
BASE_MAX_DMG = 100.0
BASE_CRIT_DMG = 30.0

# Defense Penetration Priority Order
# Lower number = applied first (gets full value)
DEF_PEN_PRIORITY = {
    'guild_skill': 1,
    'shoulder_pot': 2,  # Shoulder potentials (average for multiple lines)
    'hero_power': 3,
    # All other sources default to priority 100 and are sorted by value (highest first)
}


# =============================================================================
# Defense Penetration Calculation with Source Tracking
# =============================================================================
def calculate_effective_defense_pen_with_sources(sources: List[tuple]) -> tuple:
    """
    Calculate total Defense Penetration with effective gain per source.

    Sources are applied in priority order:
    1. Guild skill
    2. Shoulder potentials (averaged if multiple lines)
    3. Hero power
    4. All others sorted by value (highest first)

    Each source shows its EFFECTIVE gain after previous sources are applied.

    Args:
        sources: List of (source_name, value, priority) tuples
                 value is decimal (e.g., 0.20 for 20%)

    Returns:
        Tuple of (total_def_pen, source_breakdown)
        source_breakdown is list of (source_name, raw_value, effective_gain) tuples
    """
    if not sources:
        return 0.0, []

    # Separate shoulder pot sources for averaging
    shoulder_sources = [(name, val, pri) for name, val, pri in sources if 'shoulder_pot' in name.lower()]
    other_sources = [(name, val, pri) for name, val, pri in sources if 'shoulder_pot' not in name.lower()]

    # Average shoulder pot sources if multiple exist
    processed_sources = []
    if shoulder_sources:
        # Keep individual lines but mark them with same priority
        for name, val, pri in shoulder_sources:
            processed_sources.append((name, val, pri))

    processed_sources.extend(other_sources)

    # Sort by priority first, then by value (highest first) for same priority
    def sort_key(src):
        name, val, pri = src
        # For priority 100 (default), sort by value descending
        return (pri, -val)

    sorted_sources = sorted(processed_sources, key=sort_key)

    # Calculate effective gains
    remaining = 1.0
    source_breakdown = []

    for name, raw_value, priority in sorted_sources:
        # Effective gain = how much this source actually reduces remaining defense
        effective_gain = remaining * raw_value
        remaining *= (1 - raw_value)
        source_breakdown.append((name, raw_value, effective_gain))

    total_def_pen = 1 - remaining
    return min(total_def_pen, 1.0), source_breakdown


# =============================================================================
# Attack Speed Calculation with Source Tracking
# =============================================================================
ATK_SPD_CAP = 150.0  # Maximum attack speed %


def calculate_effective_attack_speed_with_sources(sources: List[tuple]) -> tuple:
    """
    Calculate total Attack Speed with effective gain per source.

    Attack speed uses diminishing returns formula:
        For each source: gain = (cap - current) * (source / cap)

    Sources are sorted by value (highest first) to show effective gains.

    Args:
        sources: List of (source_name, value) tuples
                 value is percentage (e.g., 15 for 15%)

    Returns:
        Tuple of (total_atk_spd, source_breakdown)
        source_breakdown is list of (source_name, raw_value, effective_gain) tuples
    """
    if not sources:
        return 0.0, []

    # Sort by value (highest first)
    sorted_sources = sorted(sources, key=lambda x: -x[1])

    # Calculate effective gains with diminishing returns
    current_atk_spd = 0.0
    source_breakdown = []

    for name, raw_value in sorted_sources:
        if raw_value > 0:
            # Effective gain = remaining gap to cap * (source / cap)
            effective_gain = (ATK_SPD_CAP - current_atk_spd) * (raw_value / ATK_SPD_CAP)
            current_atk_spd += effective_gain
            source_breakdown.append((name, raw_value, effective_gain))

    return min(current_atk_spd, ATK_SPD_CAP), source_breakdown


# =============================================================================
# Special Potential Helpers (using skills.py DPS calculator for accuracy)
# =============================================================================
def get_all_skills_dps_value(level: int, current_all_skills: int, base_attack: float, crit_damage: float) -> float:
    """
    Calculate the DPS value of +1 All Skills using skills.py calculator.
    Returns percentage DPS increase per +1 All Skills.
    """
    try:
        value, _ = calculate_all_skills_value(
            level=level,
            current_all_skills=current_all_skills,
            attack=base_attack,
            crit_rate=70,
            crit_damage=crit_damage,
            attack_speed_pct=50,
        )
        return value
    except Exception:
        return 0.68  # Fallback


def get_job_skill_dps_values(
    level: int,
    current_all_skills: int,
    base_attack: float,
    crit_damage: float,
) -> Dict[str, float]:
    """
    Calculate the DPS value of +1 skill level for each job tier.

    Returns dict with keys: 'first_job', 'second_job', 'third_job', 'fourth_job'
    Values are percentage DPS increase per +1 skill level to that job.
    """
    # Create current bonuses (All Skills applies equally to all jobs)
    current_bonuses = JobSkillBonus(
        first_job=current_all_skills,
        second_job=current_all_skills,
        third_job=current_all_skills,
        fourth_job=current_all_skills,
    )

    extra_stats = {
        'attack': base_attack,
        'crit_rate': 70,
        'crit_damage': crit_damage,
        'attack_speed_pct': 50,
    }

    result = {}
    for job, key in [(Job.FIRST, 'first_job'), (Job.SECOND, 'second_job'),
                     (Job.THIRD, 'third_job'), (Job.FOURTH, 'fourth_job')]:
        result[key] = calculate_job_skill_value(level, job, current_bonuses, **extra_stats)

    return result


def calculate_ba_percent_of_dps(level: int, all_skills_bonus: int, base_attack: float, crit_damage: float) -> float:
    """Calculate what percentage of total DPS comes from Basic Attack."""
    try:
        char = create_character_at_level(level, all_skills_bonus)
        char.attack = base_attack
        char.crit_damage = crit_damage
        char.crit_rate = 70
        char.attack_speed_pct = 50

        calc = DPSCalculator(char)
        result = calc.calculate_total_dps()

        if result.total_dps > 0:
            return (result.basic_attack_dps / result.total_dps) * 100
    except Exception:
        pass
    return 40.0  # Fallback


def calculate_skill_cd_dps_value(level: int, all_skills_bonus: int, cd_reduction_seconds: float) -> float:
    """
    Calculate the DPS increase from Skill CD reduction (hat special potential).

    Skill CD affects:
    - Hurricane (40s base CD) - major DPS skill
    - Covering Fire (19s base CD)
    - Phoenix (60s→30s with mastery)
    - Flash Mirage (5s→3s with mastery)

    Formula: Compare DPS with and without CD reduction
    Returns percentage DPS increase.
    """
    try:
        # Calculate DPS without CD reduction
        char_base = create_character_at_level(level, all_skills_bonus)
        char_base.attack = 50000
        char_base.crit_damage = 200
        char_base.crit_rate = 70
        char_base.attack_speed_pct = 50
        char_base.skill_cd_reduction = 0.0

        calc_base = DPSCalculator(char_base)
        result_base = calc_base.calculate_total_dps()

        # Calculate DPS with CD reduction
        char_cd = create_character_at_level(level, all_skills_bonus)
        char_cd.attack = 50000
        char_cd.crit_damage = 200
        char_cd.crit_rate = 70
        char_cd.attack_speed_pct = 50
        char_cd.skill_cd_reduction = cd_reduction_seconds

        calc_cd = DPSCalculator(char_cd)
        result_cd = calc_cd.calculate_total_dps()

        if result_base.total_dps > 0:
            return ((result_cd.total_dps / result_base.total_dps) - 1) * 100
    except Exception:
        pass
    return 0.0  # Fallback


def calculate_buff_duration_dps_value(level: int, all_skills_bonus: int, buff_duration_pct: float) -> float:
    """
    Calculate the DPS increase from Buff Duration % (belt special potential).

    Buff Duration primarily affects:
    - Mortal Blow: Increases uptime → more average Final Damage
    - Sharp Eyes: Increases uptime → more crit rate/damage buff uptime

    For Mortal Blow (main buff affected):
    - Base duration: 5s (+ 5s with mastery at 90+)
    - With buff duration: duration * (1 + buff_dur%/100)
    - Uptime = duration / (duration + build_time)
    - MB gives ~10-15% FD at max level

    Returns percentage DPS increase.
    """
    try:
        char = create_character_at_level(level, all_skills_bonus)
        char.attack = 50000
        char.crit_damage = 200
        char.crit_rate = 70
        char.attack_speed_pct = 50

        calc = DPSCalculator(char)

        if not char.is_skill_unlocked("mortal_blow"):
            return 0.0

        mb_skill = BOWMASTER_SKILLS["mortal_blow"]
        mb_level = char.get_effective_skill_level("mortal_blow")
        mb_fd = mb_skill.base_stat_value + mb_skill.stat_per_level * (mb_level - 1)

        base_uptime = calc.calculate_mortal_blow_uptime()

        base_duration = 5.0
        if level >= 90:
            base_duration += 5.0

        new_duration = base_duration * (1 + buff_duration_pct / 100)

        if base_uptime > 0 and base_uptime < 1:
            build_time = base_duration * (1 - base_uptime) / base_uptime
            new_uptime = new_duration / (new_duration + build_time)
        else:
            new_uptime = base_uptime

        base_avg_fd = mb_fd * base_uptime
        new_avg_fd = mb_fd * new_uptime

        if base_avg_fd > 0:
            dps_increase = ((1 + new_avg_fd/100) / (1 + base_avg_fd/100) - 1) * 100
            return dps_increase
    except Exception:
        pass
    return 0.0


def get_combat_mode_enum(combat_mode: str) -> CombatMode:
    """Convert string combat mode to CombatMode enum."""
    mode_map = {
        'stage': CombatMode.STAGE,
        'boss': CombatMode.BOSS,
        'world_boss': CombatMode.WORLD_BOSS,
    }
    return mode_map.get(combat_mode.lower(), CombatMode.STAGE)


def calculate_crit_rate_dps_value(
    current_crit_rate: float,
    current_crit_damage: float,
    cr_to_add: float,
    book_of_ancient_stars: int = 5,
) -> float:
    """
    Calculate the DPS value of additional Crit Rate %.

    When crit rate is below 100%, each % CR provides direct DPS gain.
    When crit rate is at or above 100%, excess CR still has value through
    the Book of Ancient artifact which converts crit rate to crit damage.

    Book of Ancient conversion at ★5: 60% of CR → CD (0.30 base + 0.06*5)
    So +1% CR above 100% → +0.6% CD from Book of Ancient.
    """
    _, cd_bonus_base = calculate_book_of_ancient_bonus(book_of_ancient_stars, current_crit_rate / 100)
    _, cd_bonus_new = calculate_book_of_ancient_bonus(book_of_ancient_stars, (current_crit_rate + cr_to_add) / 100)

    cd_from_book = (cd_bonus_new - cd_bonus_base) * 100

    total_crit_dmg = 30 + current_crit_damage
    effective_cr = min(current_crit_rate, 100) / 100
    base_crit_mult = 1 + (effective_cr * total_crit_dmg / 100)

    new_crit_rate = current_crit_rate + cr_to_add
    new_crit_dmg = current_crit_damage + cd_from_book
    new_total_crit_dmg = 30 + new_crit_dmg
    new_effective_cr = min(new_crit_rate, 100) / 100
    new_crit_mult = 1 + (new_effective_cr * new_total_crit_dmg / 100)

    if base_crit_mult > 0:
        dps_gain = ((new_crit_mult / base_crit_mult) - 1) * 100
        return dps_gain
    return 0.0


def aggregate_stats(user_data, star_overrides: Dict[str, int] = None, apply_adjustments: bool = True) -> Dict[str, Any]:
    """
    Aggregate all stats from user data for DPS calculation.

    Properly handles ALL special potentials:
    - All Skills → Final Damage (via skill rotation model)
    - BA Targets → Final Damage (based on BA% of DPS)
    - Skill CD → Final Damage (DPS comparison)
    - Buff Duration → Final Damage (MB uptime)
    - Crit Rate/Damage → Direct stats
    - Defense Pen → Multiplicative list
    - Final Damage → Multiplicative list
    - Stat per Level → Flat DEX based on character level

    Args:
        user_data: The user's data object from session state
        star_overrides: Optional dict of slot -> star level for "what-if" calculations
        apply_adjustments: Whether to apply manual adjustments from user_data.manual_adjustments
                          (default True - set to False for Character Stats page raw values)

    Returns dict with:
    - Additive stats as totals
    - Multiplicative stats as lists of sources
    """
    stats = {
        'flat_dex': 0,
        'str_flat': 0,
        'dex_percent': 0,
        'damage_percent': 0,
        'damage_amp': 0,
        'boss_damage': 0,
        'normal_damage': 0,
        'crit_damage': 0,
        'crit_rate': 0,
        'min_dmg_mult': 0,
        'max_dmg_mult': 0,
        'base_attack': 0,
        'attack_percent': 0,  # Attack % (separate from base_attack)
        'skill_damage': 0,    # Skill Damage %
        'accuracy': 0,        # Accuracy stat
        'all_skills': 0,
        'skill_cd': 0,
        'buff_duration': 0,
        'ba_targets': 0,
        # Lists for multiplicative stats
        'final_damage_sources': [],
        'defense_pen_sources': [],  # List of (source_name, value, priority) tuples
        'attack_speed_sources': [],
        # Special multipliers
        'hex_multiplier': 1.0,  # Hexagon Necklace damage multiplier (default 1.0 = no effect)
    }

    star_overrides = star_overrides or {}

    # =========================================================================
    # PASS 1: Gather base stats (needed for special potential conversions)
    # =========================================================================
    base_attack_total = 0
    crit_damage_base = 0

    for slot in EQUIPMENT_SLOTS:
        item = user_data.equipment_items.get(slot, {})
        stars = star_overrides.get(slot, int(item.get('stars', 0)))
        main_mult = get_amplify_multiplier(stars, is_sub=False)
        sub_mult = get_amplify_multiplier(stars, is_sub=True)
        base_attack_total += item.get('base_attack', 0) * main_mult
        base_attack_total += item.get('sub_attack_flat', 0) * sub_mult
        crit_damage_base += item.get('sub_crit_damage', 0) * sub_mult

    # Add crit damage from hero power
    for line_key, line in user_data.hero_power_lines.items():
        stat = line.get('stat', '')
        value = float(line.get('value', 0))
        if stat.lower() in ('crit_damage', 'cd', 'crit_dmg') and value > 0:
            crit_damage_base += value

    effective_base_attack = max(base_attack_total, 10000)
    effective_crit_damage = max(crit_damage_base, 150)

    # Pre-calculate special potential conversion values
    all_skills_to_dps = get_all_skills_dps_value(
        user_data.character_level, user_data.all_skills, effective_base_attack, effective_crit_damage
    )
    ba_dps_pct = calculate_ba_percent_of_dps(
        user_data.character_level, user_data.all_skills, effective_base_attack, effective_crit_damage
    )
    # Job-specific skill level DPS values
    job_skill_dps_values = get_job_skill_dps_values(
        user_data.character_level, user_data.all_skills, effective_base_attack, effective_crit_damage
    )
    combat_mode_enum = get_combat_mode_enum(user_data.combat_mode)
    ba_mode_mult = BA_TARGETS_MODE_MULTIPLIER.get(combat_mode_enum, 0)

    # =========================================================================
    # PASS 2: Full stat aggregation with special potential handling
    # =========================================================================
    def _add_stat(stat_type, value, source):
        """Add a stat value to the appropriate field."""
        if not stat_type or value <= 0:
            return

        stat_type_lower = stat_type.lower().replace(' ', '_')

        # Standard stats
        if stat_type_lower in ('damage', 'damage_percent', 'dmg', 'dmg%', 'damage_pct'):
            stats['damage_percent'] += value
        elif stat_type_lower in ('boss', 'boss_damage', 'boss_dmg', 'boss%'):
            stats['boss_damage'] += value
        elif stat_type_lower in ('normal', 'normal_damage', 'normal_dmg'):
            stats['normal_damage'] += value
        elif stat_type_lower in ('crit_rate', 'cr', 'crit%'):
            stats['crit_rate'] += value
        elif stat_type_lower in ('crit_damage', 'cd', 'crit_dmg'):
            stats['crit_damage'] += value
        elif stat_type_lower in ('def_pen', 'defense_pen', 'ied', 'ignore_defense'):
            # Determine priority based on source
            if 'guild' in source.lower():
                priority = DEF_PEN_PRIORITY['guild_skill']
            elif 'shoulder' in source.lower() and 'pot' in source.lower():
                priority = DEF_PEN_PRIORITY['shoulder_pot']
            elif 'hero_power' in source.lower():
                priority = DEF_PEN_PRIORITY['hero_power']
            else:
                priority = 100  # Default priority for other sources
            stats['defense_pen_sources'].append((source, value / 100, priority))
        elif stat_type_lower in ('final_damage', 'fd', 'final_dmg', 'final_atk_dmg'):
            stats['final_damage_sources'].append(value / 100)
        elif stat_type_lower in ('attack_speed', 'atk_spd', 'as'):
            stats['attack_speed_sources'].append((source, value))
        elif stat_type_lower in ('dex', 'dex%', 'dex_percent', 'main_stat_pct', 'dex_pct'):
            stats['dex_percent'] += value
        elif stat_type_lower in ('str_pct', 'int_pct', 'luk_pct'):
            pass  # Wrong class stats
        elif stat_type_lower in ('flat_dex', 'dex_flat', 'main_stat_flat'):
            stats['flat_dex'] += value
        elif stat_type_lower in ('str_flat', 'int_flat', 'luk_flat'):
            pass  # Wrong class stats
        elif stat_type_lower in ('min_dmg', 'min_damage', 'min_dmg_mult'):
            stats['min_dmg_mult'] += value
        elif stat_type_lower in ('max_dmg', 'max_damage', 'max_dmg_mult'):
            stats['max_dmg_mult'] += value
        elif stat_type_lower in ('damage_amp', 'dmg_amp'):
            stats['damage_amp'] += value

        # Special potentials
        elif stat_type_lower in ('all_skills', 'all_skill', 'allskills'):
            stats['all_skills'] += value
            fd_from_all_skills = value * all_skills_to_dps
            if fd_from_all_skills > 0:
                stats['final_damage_sources'].append(fd_from_all_skills / 100)

        elif stat_type_lower in ('ba_targets', 'ba_target', 'basic_attack_targets'):
            stats['ba_targets'] += value
            BASE_BA_TARGETS = 7
            ba_increase_pct = (value / BASE_BA_TARGETS) * 100
            dps_gain = (ba_dps_pct / 100) * ba_increase_pct * ba_mode_mult
            if dps_gain > 0:
                stats['final_damage_sources'].append(dps_gain / 100)

        elif stat_type_lower in ('skill_cd', 'skill_cooldown', 'cd_reduction'):
            stats['skill_cd'] += value
            cd_dps_gain = calculate_skill_cd_dps_value(
                user_data.character_level, user_data.all_skills, value
            )
            if cd_dps_gain > 0:
                stats['final_damage_sources'].append(cd_dps_gain / 100)

        elif stat_type_lower in ('buff_duration', 'buff_dur', 'buff%'):
            stats['buff_duration'] += value
            buff_dps_gain = calculate_buff_duration_dps_value(
                user_data.character_level, user_data.all_skills, value
            )
            if buff_dps_gain > 0:
                stats['final_damage_sources'].append(buff_dps_gain / 100)

        elif stat_type_lower in ('stat_per_level', 'main_stat_per_level'):
            flat_dex_from_level = value * user_data.character_level
            stats['flat_dex'] += flat_dex_from_level

    # Equipment potentials (regular and bonus) - NOT affected by starforce
    for slot in EQUIPMENT_SLOTS:
        pots = user_data.equipment_potentials.get(slot, {})
        for prefix in ['', 'bonus_']:
            for i in range(1, 4):
                stat = pots.get(f'{prefix}line{i}_stat', '')
                value = float(pots.get(f'{prefix}line{i}_value', 0))
                _add_stat(stat, value, f'{slot}_{prefix}pot')

    # Equipment base stats with starforce amplification
    for slot in EQUIPMENT_SLOTS:
        item = user_data.equipment_items.get(slot, {})
        stars = star_overrides.get(slot, int(item.get('stars', 0)))
        main_mult = get_amplify_multiplier(stars, is_sub=False)
        sub_mult = get_amplify_multiplier(stars, is_sub=True)

        stats['base_attack'] += item.get('base_attack', 0) * main_mult
        stats['base_attack'] += item.get('sub_attack_flat', 0) * sub_mult
        stats['crit_damage'] += item.get('sub_crit_damage', 0) * sub_mult
        stats['crit_rate'] += item.get('sub_crit_rate', 0) * sub_mult
        stats['boss_damage'] += item.get('sub_boss_damage', 0) * sub_mult
        stats['normal_damage'] += item.get('sub_normal_damage', 0) * sub_mult

        # Handle special stats based on special_stat_type field
        if item.get('is_special', False):
            special_type = item.get('special_stat_type', 'damage_pct')
            special_value = item.get('special_stat_value', 0) * sub_mult

            if special_type == 'damage_pct' and special_value > 0:
                stats['damage_percent'] += special_value
            elif special_type == 'final_damage' and special_value > 0:
                stats['final_damage_sources'].append(special_value / 100)
            elif special_type == 'all_skills' and special_value > 0:
                fd_from_as = special_value * all_skills_to_dps
                if fd_from_as > 0:
                    stats['final_damage_sources'].append(fd_from_as / 100)

        # Job-specific skill level bonuses (sub_skill_1st, sub_skill_2nd, etc.)
        # These boost specific job skills and are amplified by starforce
        skill_1st = item.get('sub_skill_1st', 0) * sub_mult
        skill_2nd = item.get('sub_skill_2nd', 0) * sub_mult
        skill_3rd = item.get('sub_skill_3rd', 0) * sub_mult
        skill_4th = item.get('sub_skill_4th', 0) * sub_mult

        # Convert each job's skill bonus to final damage using pre-calculated DPS values
        if skill_1st > 0:
            fd_from_skill = skill_1st * job_skill_dps_values['first_job']
            if fd_from_skill > 0:
                stats['final_damage_sources'].append(fd_from_skill / 100)
        if skill_2nd > 0:
            fd_from_skill = skill_2nd * job_skill_dps_values['second_job']
            if fd_from_skill > 0:
                stats['final_damage_sources'].append(fd_from_skill / 100)
        if skill_3rd > 0:
            fd_from_skill = skill_3rd * job_skill_dps_values['third_job']
            if fd_from_skill > 0:
                stats['final_damage_sources'].append(fd_from_skill / 100)
        if skill_4th > 0:
            fd_from_skill = skill_4th * job_skill_dps_values['fourth_job']
            if fd_from_skill > 0:
                stats['final_damage_sources'].append(fd_from_skill / 100)

    # Hero Power lines
    for line_key, line in user_data.hero_power_lines.items():
        stat = line.get('stat', '')
        value = float(line.get('value', 0))
        _add_stat(stat, value, f'hero_power_{line_key}')

    # Hero Power passives
    passives = user_data.hero_power_passives
    stats['flat_dex'] += passives.get('main_stat', 0) * 100
    stats['damage_percent'] += passives.get('damage', 0) * 2

    # Maple Rank
    mr = user_data.maple_rank
    stage = mr.get('current_stage', 1)
    ms_level = mr.get('main_stat_level', 0)
    special = mr.get('special_main_stat', 0)
    stats['flat_dex'] += (stage - 1) * 100 + ms_level * 10 + special

    stat_levels = mr.get('stat_levels', {})
    if isinstance(stat_levels, dict):
        atk_spd = stat_levels.get('attack_speed', 0) * 0.5
        if atk_spd > 0:
            stats['attack_speed_sources'].append(('MapleRank', atk_spd))
        stats['crit_rate'] += stat_levels.get('crit_rate', 0) * 1
        stats['damage_percent'] += stat_levels.get('damage', 0) * 2
        stats['boss_damage'] += stat_levels.get('boss_damage', 0) * 2
        stats['normal_damage'] += stat_levels.get('normal_damage', 0) * 2
        stats['crit_damage'] += stat_levels.get('crit_damage', 0) * 2

    # Equipment sets
    stats['flat_dex'] += user_data.equipment_sets.get('medal', 0)
    stats['flat_dex'] += user_data.equipment_sets.get('costume', 0)

    # Weapons (weapons_data dict with "rarity_tier" keys)
    weapons_data = getattr(user_data, 'weapons_data', {}) or {}
    equipped_weapon_key = getattr(user_data, 'equipped_weapon_key', '') or ''

    total_weapon_atk_pct = 0.0
    for key, weapon_data in weapons_data.items():
        level = weapon_data.get('level', 0)
        if level > 0:
            parts = key.rsplit('_', 1)
            if len(parts) == 2:
                rarity, tier = parts[0], int(parts[1])
                weapon_stats = calculate_weapon_atk_str(rarity, tier, level)

                # Inventory ATK% always applies (from all owned weapons)
                total_weapon_atk_pct += weapon_stats['inventory_atk']

                # On-equip ATK% only from equipped weapon
                if key == equipped_weapon_key:
                    total_weapon_atk_pct += weapon_stats['on_equip_atk']

    if total_weapon_atk_pct > 0:
        stats['attack_percent'] += total_weapon_atk_pct

    # Companions - using new format: equipped_companions (list) + companion_levels (dict)
    equipped_companions = getattr(user_data, 'equipped_companions', []) or []
    companion_levels = getattr(user_data, 'companion_levels', {}) or {}

    # On-equip stats from equipped companions
    for comp_key in equipped_companions:
        if not comp_key or comp_key not in COMPANIONS:
            continue
        level = companion_levels.get(comp_key, 0)
        if level <= 0:
            continue

        companion = COMPANIONS[comp_key]
        stat_type = companion.on_equip_type.value  # e.g., 'attack_speed', 'boss_damage'
        value = companion.get_on_equip_value(level)

        if stat_type == 'attack_speed' and value > 0:
            stats['attack_speed_sources'].append(('Companions (Equipped)', value))
        elif stat_type == 'flat_attack' and value > 0:
            stats['base_attack'] += value
        elif stat_type == 'min_dmg_mult' and value > 0:
            stats['min_dmg_mult'] += value
        elif stat_type == 'max_dmg_mult' and value > 0:
            stats['max_dmg_mult'] += value
        elif stat_type == 'boss_damage' and value > 0:
            stats['boss_damage'] += value
        elif stat_type == 'normal_damage' and value > 0:
            stats['normal_damage'] += value
        elif stat_type == 'crit_rate' and value > 0:
            stats['crit_rate'] += value

    # Inventory stats from ALL owned companions (any with level > 0)
    for comp_key, level in companion_levels.items():
        if level <= 0 or comp_key not in COMPANIONS:
            continue

        companion = COMPANIONS[comp_key]
        inv_stats = companion.get_inventory_stats(level)

        # Inventory stats: attack, main_stat, max_hp, damage
        if 'attack' in inv_stats:
            stats['base_attack'] += inv_stats['attack']
        if 'main_stat' in inv_stats:
            stats['flat_dex'] += inv_stats['main_stat']
        if 'damage' in inv_stats:
            stats['damage_percent'] += inv_stats['damage']

    # Guild skills (all stats)
    guild_skills = getattr(user_data, 'guild_skills', {})
    if guild_skills:
        # Defense Penetration - multiplicative with priority
        guild_def_pen = guild_skills.get('def_pen', 0)
        if guild_def_pen > 0:
            stats['defense_pen_sources'].append(('Guild Skill', guild_def_pen / 100, DEF_PEN_PRIORITY['guild_skill']))

        # Final Damage - multiplicative
        guild_fd = guild_skills.get('final_damage', 0)
        if guild_fd > 0:
            stats['final_damage_sources'].append(guild_fd / 100)

        # Additive stats
        stats['damage_percent'] += guild_skills.get('damage', 0)
        stats['boss_damage'] += guild_skills.get('boss_damage', 0)
        stats['crit_damage'] += guild_skills.get('crit_damage', 0)
        stats['dex_percent'] += guild_skills.get('main_stat', 0)
        stats['base_attack'] += guild_skills.get('attack', 0)

    # Weapon Mastery stats (calculated from weapon awakening levels)
    if weapons_data:
        mastery_stages = calculate_mastery_stages_from_weapons(weapons_data)
        mastery_stats = calculate_mastery_stats(mastery_stages)
        stats['base_attack'] += mastery_stats['attack']
        stats['flat_dex'] += mastery_stats['main_stat']
        stats['accuracy'] += mastery_stats['accuracy']
        stats['min_dmg_mult'] += mastery_stats['min_dmg_mult']
        stats['max_dmg_mult'] += mastery_stats['max_dmg_mult']

    # Artifacts - equipped active effects and inventory effects
    # Build name->key mapping for fallback
    artifact_key_by_name = {defn.name: key for key, defn in ARTIFACTS.items()}

    # Track Book of Ancient stars for CR->CD conversion (default 0 if not owned)
    book_of_ancient_stars = 0

    # First, get Book of Ancient stars from inventory (this is the source of truth)
    artifacts_inventory = getattr(user_data, 'artifacts_inventory', {})
    if artifacts_inventory and 'book_of_ancient' in artifacts_inventory:
        book_data = artifacts_inventory.get('book_of_ancient', {})
        if isinstance(book_data, dict):
            book_of_ancient_stars = int(book_data.get('stars', 0))

    # Store in stats for use by calculate_dps
    stats['book_of_ancient_stars'] = book_of_ancient_stars

    # Equipped artifacts (active effects)
    artifacts_equipped = getattr(user_data, 'artifacts_equipped', {})
    if artifacts_equipped:
        for slot_key in ['slot0', 'slot1', 'slot2']:
            slot_data = artifacts_equipped.get(slot_key, {})
            if not isinstance(slot_data, dict):
                continue

            # Try to get artifact key directly first (new format), fallback to name lookup
            artifact_key = slot_data.get('artifact', '')
            if not artifact_key:
                # Fallback: lookup by name
                name = slot_data.get('name', '')
                if not name or name == '(Empty)':
                    continue
                artifact_key = artifact_key_by_name.get(name, '')

            if not artifact_key or artifact_key not in ARTIFACTS:
                continue

            # Get stars from inventory (source of truth) or fall back to slot data
            if artifact_key in artifacts_inventory:
                inv_data = artifacts_inventory.get(artifact_key, {})
                stars = int(inv_data.get('stars', 0)) if isinstance(inv_data, dict) else 0
            else:
                stars = int(slot_data.get('stars', 0))

            defn = ARTIFACTS[artifact_key]

            # Handle specific active effects
            if artifact_key == 'hexagon_necklace':
                # Hex multiplier applied separately in calculate_dps
                stats['hex_multiplier'] = calculate_hex_multiplier(stars, stacks=3)

            elif artifact_key == 'book_of_ancient':
                # Crit rate from Book of Ancient (as %)
                cr_bonus = defn.get_active_value(stars)  # Returns decimal
                stats['crit_rate'] += cr_bonus * 100
                # CR->CD conversion uses book_of_ancient_stars in calculate_dps

            elif artifact_key == 'star_rock':
                # Boss damage from Star Rock
                boss_dmg = defn.get_active_value(stars)  # Returns decimal
                stats['boss_damage'] += boss_dmg * 100

            elif artifact_key == 'sayrams_necklace':
                # Normal damage from Sayram's
                normal_dmg = defn.get_active_value(stars)
                stats['normal_damage'] += normal_dmg * 100

            elif artifact_key == 'chalice':
                # Conditional Final Damage (add as FD source)
                fd = defn.get_active_value(stars)
                if fd > 0:
                    stats['final_damage_sources'].append(fd)

            elif artifact_key == 'lit_lamp':
                # World Boss Final Damage (only in world_boss mode)
                if user_data.combat_mode == 'world_boss':
                    fd = defn.get_active_value(stars)
                    if fd > 0:
                        stats['final_damage_sources'].append(fd)

            elif artifact_key == 'fire_flower':
                # Fire Flower: Final Damage per target (max 10)
                # Assume average 5 targets for stage mode, 1 for boss
                targets = 5 if user_data.combat_mode == 'stage' else 1
                fd_per_target = defn.get_active_value(stars)
                fd = fd_per_target * min(targets, 10)
                if fd > 0:
                    stats['final_damage_sources'].append(fd)

            elif artifact_key == 'icy_soul_rock':
                # Icy Soul Rock: Crit Damage at MP>=50% (doubled at 75%)
                # Assume MP is at 75%+ for full effect
                cd_bonus = defn.get_active_value(stars) * 2  # Doubled
                stats['crit_damage'] += cd_bonus * 100

    # Artifact inventory effects (passive bonuses from all owned artifacts)
    artifacts_inventory = getattr(user_data, 'artifacts_inventory', {})
    if artifacts_inventory:
        for art_key, art_data in artifacts_inventory.items():
            if art_key not in ARTIFACTS:
                continue
            if not isinstance(art_data, dict):
                continue

            defn = ARTIFACTS[art_key]
            stars = int(art_data.get('stars', 0))

            # Inventory stat (passive effect from owning the artifact)
            inv_stat = defn.inventory_stat
            inv_value = defn.get_inventory_value(stars)

            if inv_value > 0:
                if inv_stat == 'attack_flat':
                    stats['base_attack'] += inv_value
                elif inv_stat == 'damage':
                    stats['damage_percent'] += inv_value * 100
                elif inv_stat == 'boss_damage':
                    stats['boss_damage'] += inv_value * 100
                elif inv_stat == 'normal_damage':
                    stats['normal_damage'] += inv_value * 100
                elif inv_stat == 'crit_damage_conditional':
                    # Book of Ancient inventory: CD at MP>=50%, doubled at 75%
                    # Assume MP is at 75%+ for full effect
                    stats['crit_damage'] += inv_value * 100 * 2  # Doubled
                elif inv_stat == 'crit_damage':
                    # Icy Soul Rock inventory: straight crit damage
                    stats['crit_damage'] += inv_value * 100
                elif inv_stat == 'max_damage_mult':
                    stats['max_dmg_mult'] += inv_value * 100
                elif inv_stat == 'def_pen':
                    # Silver Pendant inventory: defense penetration
                    stats['defense_pen_sources'].append(('Artifact Inventory', inv_value, 100))

            # Artifact potentials
            potentials = art_data.get('potentials', [])
            if isinstance(potentials, list):
                for pot in potentials:
                    if isinstance(pot, dict):
                        pot_stat = pot.get('stat', '')
                        pot_value = float(pot.get('value', 0) or 0)
                        if pot_value > 0:
                            if pot_stat == 'main_stat':
                                stats['dex_percent'] += pot_value
                            elif pot_stat == 'damage':
                                stats['damage_percent'] += pot_value
                            elif pot_stat == 'boss_damage':
                                stats['boss_damage'] += pot_value
                            elif pot_stat == 'normal_damage':
                                stats['normal_damage'] += pot_value
                            elif pot_stat == 'crit_rate':
                                stats['crit_rate'] += pot_value
                            elif pot_stat == 'crit_damage':
                                stats['crit_damage'] += pot_value
                            elif pot_stat == 'def_pen':
                                stats['defense_pen_sources'].append(('Artifact Potential', pot_value / 100, 100))
                            elif pot_stat == 'min_max_damage':
                                stats['min_dmg_mult'] += pot_value
                                stats['max_dmg_mult'] += pot_value

    # =========================================================================
    # PASS 3: Apply Manual Adjustments (if enabled)
    # =========================================================================
    # Manual adjustments from Character Stats page help account for
    # stats from sources we don't track (passive skills, buffs, etc.)
    if apply_adjustments:
        manual_adj = getattr(user_data, 'manual_adjustments', {}) or {}
        if manual_adj:
            # Map adjustment keys to stat keys
            # Most keys match directly, but some need special handling
            adjustment_mapping = {
                'flat_dex': 'flat_dex',
                'dex_percent': 'dex_percent',
                'base_attack': 'base_attack',
                'attack_percent': 'attack_percent',
                'damage_percent': 'damage_percent',
                'boss_damage': 'boss_damage',
                'normal_damage': 'normal_damage',
                'crit_rate': 'crit_rate',
                'crit_damage': 'crit_damage',
                'min_dmg_mult': 'min_dmg_mult',
                'max_dmg_mult': 'max_dmg_mult',
                'skill_damage': 'skill_damage',
                'accuracy': 'accuracy',
            }

            for adj_key, stat_key in adjustment_mapping.items():
                adj_value = manual_adj.get(adj_key, 0)
                if adj_value != 0 and stat_key in stats:
                    stats[stat_key] += adj_value

            # Special handling for multiplicative stats:
            # defense_pen adjustment - add as a manual source
            def_pen_adj = manual_adj.get('defense_pen', 0)
            if def_pen_adj != 0:
                # Convert percentage to decimal and add as lowest priority source
                stats['defense_pen_sources'].append(('Manual Adjustment', def_pen_adj / 100, 999))

            # attack_speed adjustment - add as a manual source
            atk_spd_adj = manual_adj.get('attack_speed', 0)
            if atk_spd_adj != 0:
                stats['attack_speed_sources'].append(('Manual Adjustment', atk_spd_adj))

            # final_damage adjustment - add as additional source
            fd_adj = manual_adj.get('final_damage', 0)
            if fd_adj != 0:
                stats['final_damage_sources'].append(fd_adj / 100)

            # total_dex and total_attack adjustments need special handling
            # They are derived stats, so we track adjustment separately
            # These will be applied in calculate_dps
            stats['total_dex_adjustment'] = manual_adj.get('total_dex', 0)
            stats['total_attack_adjustment'] = manual_adj.get('total_attack', 0)

    return stats


def calculate_dps(stats: Dict[str, Any], combat_mode: str = 'stage', enemy_def: float = 0.752, book_of_ancient_stars: int = None) -> Dict[str, Any]:
    """
    Calculate DPS using core damage formulas.

    Includes Book of Ancient CR → CD conversion:
    - At ★5: 60% of crit rate converts to crit damage
    - This gives value to crit rate even above 100%

    Args:
        stats: Aggregated stats from aggregate_stats()
        combat_mode: 'stage', 'boss', or 'world_boss'
        enemy_def: Enemy defense multiplier (default 0.752)
        book_of_ancient_stars: Book of Ancient awakening level (uses stats value if None)

    Returns:
        Dict with 'total' DPS and component multipliers
    """
    # Calculate multiplicative stats using core functions
    # Defense pen now returns effective gains per source in priority order
    total_defense_pen, def_pen_breakdown = calculate_effective_defense_pen_with_sources(
        stats.get('defense_pen_sources', [])
    )
    # Attack speed returns effective gains per source (highest to lowest)
    total_attack_speed, atk_spd_breakdown = calculate_effective_attack_speed_with_sources(
        stats.get('attack_speed_sources', [])
    )
    fd_mult = calculate_final_damage_mult(stats.get('final_damage_sources', []))

    # DEX calculation (with manual adjustment if present)
    total_dex = calculate_total_dex(stats['flat_dex'], stats['dex_percent'])
    total_dex += stats.get('total_dex_adjustment', 0)

    # Total attack = base_attack * (1 + attack_percent/100) + manual adjustment
    base_attack = max(stats['base_attack'], 10000)
    attack_percent = stats.get('attack_percent', 0)
    base_atk = base_attack * (1 + attack_percent / 100)
    base_atk += stats.get('total_attack_adjustment', 0)

    # Book of Ancient: Convert portion of Crit Rate to Crit Damage
    # Use stats value if parameter not explicitly provided
    if book_of_ancient_stars is None:
        book_of_ancient_stars = stats.get('book_of_ancient_stars', 0)

    crit_rate = stats['crit_rate']
    base_crit_damage = stats['crit_damage']
    _, cd_from_book = calculate_book_of_ancient_bonus(book_of_ancient_stars, crit_rate / 100)
    total_crit_damage = base_crit_damage + (cd_from_book * 100)

    # Use core damage function
    result = calculate_damage(
        base_atk=base_atk,
        dex_flat=stats['flat_dex'],
        dex_percent=stats['dex_percent'],
        damage_percent=stats['damage_percent'],
        damage_amp=stats.get('damage_amp', 0),
        final_damage_sources=stats.get('final_damage_sources', []),
        crit_rate=crit_rate,
        crit_damage=total_crit_damage,
        defense_pen=total_defense_pen,
        enemy_def=enemy_def,
        boss_damage=stats['boss_damage'] if combat_mode in ('boss', 'world_boss') else 0,
        str_flat=stats.get('str_flat', 0),
    )

    # Handle stage mode with weighted boss/normal
    if combat_mode == 'stage':
        normal_weight = 0.60
        boss_weight = 0.40

        result_normal = calculate_damage(
            base_atk=base_atk,
            dex_flat=stats['flat_dex'],
            dex_percent=stats['dex_percent'],
            damage_percent=stats['damage_percent'] + stats['normal_damage'],
            damage_amp=stats.get('damage_amp', 0),
            final_damage_sources=stats.get('final_damage_sources', []),
            crit_rate=crit_rate,
            crit_damage=total_crit_damage,
            defense_pen=total_defense_pen,
            enemy_def=enemy_def,
            str_flat=stats.get('str_flat', 0),
        )

        result_boss = calculate_damage(
            base_atk=base_atk,
            dex_flat=stats['flat_dex'],
            dex_percent=stats['dex_percent'],
            damage_percent=stats['damage_percent'],
            damage_amp=stats.get('damage_amp', 0),
            final_damage_sources=stats.get('final_damage_sources', []),
            crit_rate=crit_rate,
            crit_damage=total_crit_damage,
            defense_pen=total_defense_pen,
            enemy_def=enemy_def,
            boss_damage=stats['boss_damage'],
            str_flat=stats.get('str_flat', 0),
        )

        weighted_total = (normal_weight * result_normal.total) + (boss_weight * result_boss.total)
        final_total = weighted_total
    else:
        final_total = result.total

    # Min/Max damage range
    final_min = BASE_MIN_DMG + stats['min_dmg_mult']
    final_max = BASE_MAX_DMG + stats['max_dmg_mult']
    avg_mult = (final_min + final_max) / 2
    dmg_range_mult = avg_mult / 100

    # Attack speed multiplier
    atk_spd_mult = 1 + (total_attack_speed / 100)

    # Apply range and speed to final
    final_total = final_total * dmg_range_mult * atk_spd_mult

    return {
        'total': final_total,
        'defense_pen': total_defense_pen,
        'defense_pen_breakdown': def_pen_breakdown,  # List of (source, raw_value, effective_gain)
        'attack_speed': total_attack_speed,
        'attack_speed_breakdown': atk_spd_breakdown,  # List of (source, raw_value, effective_gain)
        'fd_mult': fd_mult,
        # Multiplier breakdown for display
        'stat_mult': result.stat_mult,
        'damage_mult': result.damage_mult,
        'amp_mult': result.amp_mult,
        'crit_mult': result.crit_mult,
        'def_mult': result.def_mult,
        'range_mult': dmg_range_mult,
        'speed_mult': atk_spd_mult,
        'total_dex': result.total_dex,
    }
