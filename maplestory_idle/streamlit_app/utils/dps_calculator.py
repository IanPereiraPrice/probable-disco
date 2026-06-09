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
import functools
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import streamlit as st

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
from game.equipment import get_amplify_multiplier, SLOT_THIRD_MAIN_STAT
from game.artifacts import (
    calculate_book_of_ancient_bonus,
    calculate_bottle_of_emotions_fd,
    calculate_hex_multiplier,
    calculate_hex_average_multiplier,
    ARTIFACTS,
    ArtifactTier,
    CombatScenario,
    EffectType,
    POTENTIAL_SLOT_UNLOCKS,
)
from game.companions import COMPANIONS
from game.weapons import calculate_weapon_atk_str
from game.weapon_mastery import calculate_mastery_stages_from_weapons, calculate_mastery_stats
from game.skills import (
    calculate_all_skills_value, create_character_at_level, DPSCalculator,
    BOWMASTER_SKILLS, create_character_with_job_bonuses,
)
from game.cubes import CombatMode, COMBAT_SCENARIO_PARAMS
from streamlit_app.utils.data_manager import EQUIPMENT_SLOTS
from game.job_classes import JobClass, get_job_stats, get_main_stat_name, get_secondary_stat_name
from libs.stat_names import (
    is_multiplicative_stat, MULTIPLICATIVE_STATS, GENERIC_STAT_KEYS,
    MAIN_STAT_FLAT, MAIN_STAT_PCT, DEF_PEN, FINAL_DAMAGE, ATTACK_SPEED,
    ALL_SKILLS, SKILL_CD, BUFF_DURATION,
    # Stat key constants for dict initialization
    DAMAGE_PCT, BOSS_DAMAGE, NORMAL_DAMAGE, CRIT_DAMAGE, CRIT_RATE,
    MIN_DMG_MULT, MAX_DMG_MULT, ATTACK_FLAT, ATTACK_PCT, SKILL_DAMAGE,
    ACCURACY, BA_TARGETS, BASIC_ATTACK_DAMAGE,
    SKILL_1ST, SKILL_2ND, SKILL_3RD, SKILL_4TH,
)


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
# Cached with lru_cache — inputs are standardized params, not real user stats
# =============================================================================
@functools.lru_cache(maxsize=256)
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


@functools.lru_cache(maxsize=256)
def calculate_ba_percent_of_dps(
    level: int,
    all_skills_bonus: int,
    base_attack: float,
    crit_damage: float,
    num_enemies: int = 6,
    mob_time_fraction: float = 0.6,
    ba_target_bonus: int = 0,
) -> float:
    """Calculate what percentage of total DPS comes from Basic Attack.

    Args:
        level: Character level
        all_skills_bonus: +All Skills from gear
        base_attack: Total attack stat
        crit_damage: Total crit damage %
        num_enemies: Number of enemies in mob waves (default 6 for typical stage)
        mob_time_fraction: Fraction of fight spent on mob waves (default 0.6 = 60%)
        ba_target_bonus: Bonus BA targets from potentials (e.g., +3 from Mystic pot)

    Returns:
        BA DPS as percentage of total DPS
    """
    try:
        char = create_character_at_level(level, all_skills_bonus)
        char.attack = base_attack
        char.crit_damage = crit_damage
        char.crit_rate = 70
        char.attack_speed_pct = 50
        # BA Target bonus increases the number of targets BA can hit
        # Base BA targets is 6, so +3 = 9 targets
        char.ba_target_bonus = ba_target_bonus

        calc = DPSCalculator(char)
        result = calc.calculate_total_dps(
            num_enemies=num_enemies,
            mob_time_fraction=mob_time_fraction,
        )

        if result.total_dps > 0:
            return (result.basic_attack_dps / result.total_dps) * 100
    except Exception:
        pass
    return 40.0  # Fallback


@functools.lru_cache(maxsize=256)
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


@functools.lru_cache(maxsize=256)
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
        # Use skill_bonuses format: {stat_name: (base, per_level)}
        base, per_level = mb_skill.skill_bonuses.get("final_damage", (0, 0))
        mb_fd = int((base + per_level * mb_level) * 10) / 10

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
        'chapter_hunt': CombatMode.CHAPTER_HUNT,
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


@st.cache_data(ttl=300, show_spinner=False)
def aggregate_stats(user_data, star_overrides: Dict[str, int] = None, apply_adjustments: bool = True,
                    scenario: str = None, skip_artifact_actives: bool = False) -> Dict[str, Any]:
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
        scenario: Combat scenario for artifact effects (e.g., "world_boss", "guild", "growth", "arena", "chapter")
                  If None, uses combat_mode to infer scenario
        skip_artifact_actives: If True, skip processing equipped artifact active effects.
                              Used for artifact ranking calculations where we need to measure
                              each artifact's contribution independently.

    Returns dict with:
    - Additive stats as totals
    - Multiplicative stats as lists of sources
    """
    # Get job class for main stat mapping
    job_class = JobClass(user_data.job_class)
    main_stat_type = get_main_stat_name(job_class)  # e.g., 'dex', 'str', 'int', 'luk'
    secondary_stat_type = get_secondary_stat_name(job_class)

    # Create stat keys based on job class
    main_flat_key = f'{main_stat_type}_flat'
    main_pct_key = f'{main_stat_type}_pct'
    secondary_flat_key = f'{secondary_stat_type}_flat'
    secondary_pct_key = f'{secondary_stat_type}_pct'

    # Initialize stats dict using standardized keys from stat_names.py
    stats = {
        # Job class info for downstream consumers
        'main_stat_type': main_stat_type,  # e.g., 'dex', 'str', 'int', 'luk'
        # Main/secondary stats - dynamic based on job class
        main_flat_key: 0,
        main_pct_key: 0,
        secondary_flat_key: 0,
        secondary_pct_key: 0,
        # Damage stats
        'damage_pct': 0,
        'boss_damage': 0,
        'normal_damage': 0,
        # Critical stats
        'crit_damage': 0,
        'crit_rate': 0,
        # Damage range stats
        'min_dmg_mult': 0,
        'max_dmg_mult': 0,
        # Attack stats
        'attack_flat': 0,
        'attack_pct': 0,
        # Skill stats
        'skill_damage': 0,
        'all_skills_bonus': 0,
        'skill_cd_reduction': 0,
        'buff_duration': 0,
        # Extra seconds added to the companion summon's 30s base duration
        # (shoes special potential, Glass Slipper artifact). Read by the
        # realistic-DPS simulator; sequence-affecting.
        'companion_duration': 0,
        'skill_1st_bonus': 0,
        'skill_2nd_bonus': 0,
        'skill_3rd_bonus': 0,
        'skill_4th_bonus': 0,
        # Defense stats (for Shield Mastery: LUK = 10% of Defense)
        'defense_flat': 0,
        'defense_pct': 0,
        # Utility stats
        'accuracy': 0,
        'ba_target_bonus': 0,
        'basic_attack_damage': 0,
        'damage_amp': 0,  # From equipment scrolls
        # Character info
        'level': user_data.character_level,
        # Multiplicative stats - stored as lists for stacking calculation
        'def_pen_sources': [],       # List of (source_name, value, priority) tuples
        'final_damage_sources': [],  # List of decimal values (e.g., 0.10 for 10%)
        # Decimal values of FD sources gated on "companion is currently summoned"
        # (Horn Flute). Multiplied through, applied only when active_summons
        # is non-empty in _simulate_fight. NOT added to final_damage_sources
        # because that path treats sources as always-on.
        'companion_active_fd_sources': [],
        'attack_speed_sources': [],  # List of (source_name, value) tuples
        # Special artifact tracking
        'hex_necklace_stars': 0,     # Hexagon Necklace stars (for time-weighted calculation)
        'hex_multiplier': 1.0,       # Time-weighted Hex multiplier (displayable, varies by scenario)
    }

    star_overrides = star_overrides or {}

    # Infer scenario from combat_mode if not explicitly provided
    # Supported scenarios: "normal" (stage farming), "boss" (boss stage), "world_boss"
    if scenario is None:
        combat_mode = getattr(user_data, 'combat_mode', 'stage')
        if combat_mode == 'world_boss':
            scenario = 'world_boss'
        elif combat_mode == 'boss':
            scenario = 'boss'
        else:
            scenario = 'normal'  # Default scenario for stage mode

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

    # Note: Hero Power doesn't have crit_damage as a stat type (see hero_power.py)
    # Legacy code that read from hero_power_lines was removed - HP only has:
    # damage_pct, boss_damage, normal_damage, def_pen, attack_speed, main_stat, etc.

    effective_base_attack = max(base_attack_total, 10000)
    effective_crit_damage = max(crit_damage_base, 150)

    # Pre-calculate special potential conversion values
    all_skills_to_dps = get_all_skills_dps_value(
        user_data.character_level, user_data.all_skills, effective_base_attack, effective_crit_damage
    )

    # Get combat scenario parameters
    combat_mode_enum = get_combat_mode_enum(user_data.combat_mode)
    scenario_params = COMBAT_SCENARIO_PARAMS.get(combat_mode_enum, COMBAT_SCENARIO_PARAMS[CombatMode.STAGE])
    num_enemies = scenario_params.num_enemies
    mob_time_fraction = scenario_params.mob_time_fraction

    # NOTE: BA% calculation moved to PASS 4 (after ba_targets are collected from potentials)

    # =========================================================================
    # PASS 2: Full stat aggregation using standardized stat names
    # =========================================================================
    def _add_stat(stat_name, value, source):
        """
        Add a stat value using standardized stat names.

        Handles:
        - Multiplicative stats: append to list (def_pen, final_damage, attack_speed)
        - Additive stats: stats[stat_name] += value
        - Generic main_stat: resolve to job's actual stat (dex_flat, str_flat, etc.)
        """
        if not stat_name or value <= 0:
            return

        # Resolve generic main_stat to job-specific key
        if stat_name == 'main_stat_flat':
            stats[main_flat_key] += value
            return
        if stat_name == 'main_stat_pct':
            # Hero Power lines use 'main_stat_pct' but it's actually flat stat (e.g., +1120 DEX)
            # This is a legacy naming issue - the stat provides flat main stat, not percentage
            if 'hero_power' in source.lower():
                stats[main_flat_key] += value
            else:
                stats[main_pct_key] += value
            return

        # Handle specific flat stats (dex_flat, str_flat, int_flat, luk_flat)
        # Only contribute if they match the job's main or secondary stat type
        specific_flat_stats = {'dex_flat', 'str_flat', 'int_flat', 'luk_flat'}
        if stat_name in specific_flat_stats:
            if stat_name == main_flat_key:
                stats[main_flat_key] += value
            elif stat_name == secondary_flat_key:
                stats[secondary_flat_key] += value
            # else: stat doesn't match job's main or secondary, ignore it
            return

        # Handle specific percentage stats (dex_pct, str_pct, int_pct, luk_pct)
        # Only contribute if they match the job's main or secondary stat type
        specific_pct_stats = {'dex_pct', 'str_pct', 'int_pct', 'luk_pct'}
        if stat_name in specific_pct_stats:
            if stat_name == main_pct_key:
                stats[main_pct_key] += value
            elif stat_name == secondary_pct_key:
                stats[secondary_pct_key] += value
            # else: stat doesn't match job's main or secondary, ignore it
            return

        # Handle multiplicative stats (append to list)
        if stat_name == 'def_pen':
            # Determine priority based on source
            if 'guild' in source.lower():
                priority = DEF_PEN_PRIORITY['guild_skill']
            elif 'shoulder' in source.lower() and 'pot' in source.lower():
                priority = DEF_PEN_PRIORITY['shoulder_pot']
            elif 'hero_power' in source.lower():
                priority = DEF_PEN_PRIORITY['hero_power']
            else:
                priority = 100
            stats['def_pen_sources'].append((source, value / 100, priority))
            return
        if stat_name == 'final_damage':
            stats['final_damage_sources'].append(value / 100)
            return
        if stat_name == 'attack_speed':
            stats['attack_speed_sources'].append((source, value))
            return

        # Handle stats with DPS side effects
        if stat_name == 'all_skills':
            stats['all_skills_bonus'] += value
            return
        if stat_name == 'skill_cd':
            stats['skill_cd_reduction'] += value
            return
        if stat_name == 'buff_duration':
            stats['buff_duration'] += value
            return
        if stat_name == 'companion_duration':
            # Shoe special potential / glass slipper artifact: extends the
            # companion summon's 30s base duration by N seconds.
            stats['companion_duration'] += value
            return

        # Stat name aliases - map potential stat names to stats dict keys
        stat_aliases = {
            'damage': 'damage_pct',      # Potentials use 'damage', stats dict uses 'damage_pct'
            'defense': 'defense_pct',    # Potentials use 'defense', stats dict uses 'defense_pct'
            'ba_targets': 'ba_target_bonus',  # Old potential type name → new dict key
        }
        resolved_name = stat_aliases.get(stat_name, stat_name)

        # Simple additive stats - just add directly if key exists
        if resolved_name in stats:
            stats[resolved_name] += value

    # Equipment potentials (regular and bonus) - NOT affected by starforce
    for slot in EQUIPMENT_SLOTS:
        pots = user_data.equipment_potentials.get(slot, {})
        for prefix in ['', 'bonus_']:
            for i in range(1, 4):
                stat = pots.get(f'{prefix}line{i}_stat', '')
                value = float(pots.get(f'{prefix}line{i}_value', 0))
                _add_stat(stat, value, f'{slot}_{prefix}pot')

    # Equipment scrolls - independent from starforce
    equipment_scrolls = getattr(user_data, 'equipment_scrolls', {}) or {}
    for slot in EQUIPMENT_SLOTS:
        scroll_data = equipment_scrolls.get(slot, {})
        if scroll_data:
            # Damage Amp % - additive with other damage amp sources
            damage_amp = float(scroll_data.get('damage_amp', 0))
            if damage_amp > 0:
                if 'damage_amp' not in stats:
                    stats['damage_amp'] = 0
                stats['damage_amp'] += damage_amp
            # Flat Attack
            flat_atk = float(scroll_data.get('flat_attack', 0))
            if flat_atk > 0:
                stats['attack_flat'] += flat_atk
            # Flat Main Stat
            flat_stat = float(scroll_data.get('flat_main_stat', 0))
            if flat_stat > 0:
                stats[main_flat_key] += flat_stat

    # Equipment base stats with starforce amplification
    for slot in EQUIPMENT_SLOTS:
        item = user_data.equipment_items.get(slot, {})
        stars = star_overrides.get(slot, int(item.get('stars', 0)))
        main_mult = get_amplify_multiplier(stars, is_sub=False)
        sub_mult = get_amplify_multiplier(stars, is_sub=True)

        stats['attack_flat'] += item.get('base_attack', 0) * main_mult
        stats['attack_flat'] += item.get('sub_attack_flat', 0) * sub_mult

        # Main stat from equipment - only certain slots have main_stat as 3rd stat
        # weapon, ring, necklace, eye, face have main_stat; others have defense/accuracy/etc
        third_stat_type = SLOT_THIRD_MAIN_STAT.get(slot, 'main_stat')
        if third_stat_type == 'main_stat':
            stats[main_flat_key] += item.get('base_third_stat', 0) * main_mult
        elif third_stat_type == 'defense':
            stats['defense_flat'] += item.get('base_third_stat', 0) * main_mult

        stats['crit_damage'] += item.get('sub_crit_damage', 0) * sub_mult
        stats['crit_rate'] += item.get('sub_crit_rate', 0) * sub_mult
        stats['boss_damage'] += item.get('sub_boss_damage', 0) * sub_mult
        stats['normal_damage'] += item.get('sub_normal_damage', 0) * sub_mult
        stats['damage_pct'] += item.get('sub_damage_pct', 0) * sub_mult

        # Min/Max Damage % (Sub Amplify) - separate inputs, available on any item
        stats['min_dmg_mult'] += item.get('sub_min_dmg', 0) * sub_mult
        stats['max_dmg_mult'] += item.get('sub_max_dmg', 0) * sub_mult

        # Handle special stats based on special_stat_type field
        if item.get('is_special', False):
            special_type = item.get('special_stat_type', 'damage_pct')
            special_value = item.get('special_stat_value', 0) * sub_mult

            if special_type == 'damage_pct' and special_value > 0:
                stats['damage_pct'] += special_value
            elif special_type == 'final_damage' and special_value > 0:
                stats['final_damage_sources'].append(special_value / 100)
            elif special_type == 'all_skills' and special_value > 0:
                stats['all_skills_bonus'] += int(special_value)
            elif special_type == 'def_pen' and special_value > 0:
                stats['def_pen_sources'].append(('Equipment Special', special_value / 100, 100))
            elif special_type == 'skill_damage' and special_value > 0:
                stats['skill_damage'] += special_value
            elif special_type == 'basic_attack_dmg' and special_value > 0:
                stats['basic_attack_damage'] += special_value

        # Job-specific skill level bonuses (sub_skill_1st, sub_skill_2nd, etc.)
        # These boost specific job skills and are amplified by starforce
        # Accumulate for passing to DPSCalculator
        stats['skill_1st_bonus'] += item.get('sub_skill_1st', 0) * sub_mult
        stats['skill_2nd_bonus'] += item.get('sub_skill_2nd', 0) * sub_mult
        stats['skill_3rd_bonus'] += item.get('sub_skill_3rd', 0) * sub_mult
        stats['skill_4th_bonus'] += item.get('sub_skill_4th', 0) * sub_mult

    # Hero Power lines - use active preset's lines, not hero_power_lines directly
    # hero_power_lines may be stale if user hasn't visited Hero Power page recently
    active_preset = getattr(user_data, 'active_hero_power_preset', '1')
    hero_power_presets = getattr(user_data, 'hero_power_presets', {})

    if active_preset and active_preset in hero_power_presets:
        # Use lines from the active preset
        preset_data = hero_power_presets[active_preset]
        hp_lines = preset_data.get('lines', {})
    else:
        # Fallback to hero_power_lines if no preset system
        hp_lines = user_data.hero_power_lines

    for line_key, line in hp_lines.items():
        stat = line.get('stat', '')
        value = float(line.get('value', 0))
        _add_stat(stat, value, f'hero_power_{line_key}')

    # Hero Power passives - direct values
    passive_values = getattr(user_data, 'hero_power_passive_values', {}) or {}
    stats[main_flat_key] += passive_values.get('main_stat', 0)
    stats['damage_pct'] += passive_values.get('damage_percent', 0)
    stats['attack_flat'] += passive_values.get('attack', 0)

    # Maple Rank - use correct cumulative formula
    from game.maple_rank import get_cumulative_main_stat, MAIN_STAT_SPECIAL
    mr = user_data.maple_rank
    stage = mr.get('current_stage', 1)
    ms_level = mr.get('main_stat_level', 0)
    special = mr.get('special_main_stat', 0)
    # Regular main stat uses cumulative formula with varying per-point values
    regular_ms = get_cumulative_main_stat(stage, ms_level)
    # Special main stat has base value of 300 even at 0 points
    special_ms = MAIN_STAT_SPECIAL["base_value"] + special * MAIN_STAT_SPECIAL["per_point"]
    stats[main_flat_key] += regular_ms + special_ms

    stat_levels = mr.get('stat_levels', {})
    if isinstance(stat_levels, dict):
        # Use correct per_level values from MAPLE_RANK_STATS
        atk_spd = stat_levels.get('attack_speed', 0) * 0.35  # 7% max / 20 levels
        if atk_spd > 0:
            stats['attack_speed_sources'].append(('MapleRank', atk_spd))
        stats['crit_rate'] += stat_levels.get('crit_rate', 0) * 1.0      # 10% max / 10 levels
        stats['damage_pct'] += stat_levels.get('damage_percent', 0) * 0.7  # 35% max / 50 levels
        stats['boss_damage'] += stat_levels.get('boss_damage', 0) * 0.667  # 20% max / 30 levels
        stats['normal_damage'] += stat_levels.get('normal_damage', 0) * 0.667  # 20% max / 30 levels
        stats['crit_damage'] += stat_levels.get('crit_damage', 0) * 0.667  # 20% max / 30 levels
        stats['skill_damage'] += stat_levels.get('skill_damage', 0) * 0.833  # 25% max / 30 levels
        stats['min_dmg_mult'] += stat_levels.get('min_dmg_mult', 0) * 0.55  # 11% max / 20 levels
        stats['max_dmg_mult'] += stat_levels.get('max_dmg_mult', 0) * 0.55  # 11% max / 20 levels

    # Equipment sets
    stats[main_flat_key] += user_data.equipment_sets.get('medal', 0)
    stats[main_flat_key] += user_data.equipment_sets.get('costume', 0)

    # Unique stats (HeroUniqueStatOption levels) - pass through to calculate_dps
    unique_stats = getattr(user_data, 'unique_stats', {}) or {}
    stats['unique_attack_speed_level'] = unique_stats.get('attack_speed', 0)
    stats['unique_crit_chance_level'] = unique_stats.get('crit_chance', 0)
    stats['unique_min_damage_level'] = unique_stats.get('min_damage', 0)
    stats['unique_max_damage_level'] = unique_stats.get('max_damage', 0)
    stats['unique_crit_power_level'] = unique_stats.get('crit_power', 0)
    stats['unique_normal_damage_level'] = unique_stats.get('normal_damage', 0)
    stats['unique_boss_damage_level'] = unique_stats.get('boss_damage', 0)
    stats['unique_skill_power_level'] = unique_stats.get('skill_power', 0)
    stats['unique_attack_power_level'] = unique_stats.get('attack_power', 0)
    stats['unique_main_stat_level'] = unique_stats.get('main_stat', 0)

    # Weapons (weapons_data dict with "rarity_tier" keys)
    weapons_data = getattr(user_data, 'weapons_data', {}) or {}
    equipped_weapon_key = getattr(user_data, 'equipped_weapon_key', '') or ''

    # Auto-select best weapon if none equipped but weapons exist
    if not equipped_weapon_key and weapons_data:
        best_key = ""
        best_atk = 0.0
        for key, w_data in weapons_data.items():
            lvl = w_data.get('level', 0)
            if lvl <= 0:
                continue
            parts = key.rsplit('_', 1)
            if len(parts) == 2:
                rarity, tier = parts[0], int(parts[1])
                w_stats = calculate_weapon_atk_str(rarity, tier, lvl)
                if w_stats['on_equip_atk'] > best_atk:
                    best_atk = w_stats['on_equip_atk']
                    best_key = key
        equipped_weapon_key = best_key

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
        stats['attack_pct'] += total_weapon_atk_pct

    # Companions - using new format: equipped_companions (list) + companion_levels (dict)
    equipped_companions = getattr(user_data, 'equipped_companions', []) or []
    companion_levels = getattr(user_data, 'companion_levels', {}) or {}

    # MAIN slot (index 0) companion summon mechanic — record (advancement, level)
    # so calculate_dps can inject a synthetic SUMMON skill into the calculator.
    # See game/companions.py SUMMON MECHANIC section for the model.
    # Also record the companion's self-buff FD (3rd/4th job get +75% by default);
    # baked into the companion's snapshot at cast time so every companion
    # attack during the 30s window benefits.
    main_comp_key = equipped_companions[0] if equipped_companions else None
    if main_comp_key and main_comp_key in COMPANIONS:
        main_level = companion_levels.get(main_comp_key, 0)
        if main_level > 0:
            stats['_main_companion_summon'] = (
                COMPANIONS[main_comp_key].advancement,
                main_level,
            )
            # Level-scaled self-buff FD (+25% at each of L5/L8/L10 for 3rd/4th
            # job companions). At level 1-4 this returns 0; at max level, +75%.
            stats['_main_companion_self_buff_fd_decimal'] = (
                COMPANIONS[main_comp_key].get_self_buff_fd_decimal(main_level)
            )
            # Per-companion kit data — empty for non-Bishop today; populated
            # for Bishop 4th (player buffs, primary attack override,
            # secondary skill, proc). Routed into the calculator below.
            _main_comp = COMPANIONS[main_comp_key]
            stats['_main_companion_player_bonuses'] = dict(_main_comp.summon_active_player_bonuses)
            stats['_main_companion_primary_attack_override'] = _main_comp.summon_primary_attack_override
            stats['_main_companion_secondary_skills'] = list(_main_comp.summon_secondary_skills)
            stats['_main_companion_proc_skill'] = _main_comp.summon_proc_skill

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
            stats['attack_speed_sources'].append((f'Companion: {companion.name}', value))
        elif stat_type == 'flat_attack' and value > 0:
            stats['attack_flat'] += value
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
        elif stat_type == 'main_stat_pct' and value > 0:
            stats[main_pct_key] += value
        elif stat_type == 'crit_damage' and value > 0:
            stats['crit_damage'] += value
        elif stat_type == 'skill_damage' and value > 0:
            stats['skill_damage'] += value
        elif stat_type == 'basic_attack_damage' and value > 0:
            stats['basic_attack_damage'] += value

    # Inventory stats from ALL owned companions (any with level > 0)
    for comp_key, level in companion_levels.items():
        if level <= 0 or comp_key not in COMPANIONS:
            continue

        companion = COMPANIONS[comp_key]
        inv_stats = companion.get_inventory_stats(level)

        # Inventory stats use standardized names: attack_flat, main_stat_flat, damage_pct, max_hp
        if 'attack_flat' in inv_stats:
            stats['attack_flat'] += inv_stats['attack_flat']
        if 'main_stat_flat' in inv_stats:
            stats[main_flat_key] += inv_stats['main_stat_flat']
        if 'damage_pct' in inv_stats:
            stats['damage_pct'] += inv_stats['damage_pct']
        if 'main_stat_pct' in inv_stats:
            stats[main_pct_key] += inv_stats['main_stat_pct']
        if 'crit_damage' in inv_stats:
            stats['crit_damage'] += inv_stats['crit_damage']

    # Guild skills (all stats)
    guild_skills = getattr(user_data, 'guild_skills', {})
    if guild_skills:
        # Defense Penetration - multiplicative with priority
        guild_def_pen = guild_skills.get('def_pen', 0)
        if guild_def_pen > 0:
            stats['def_pen_sources'].append(('Guild Skill', guild_def_pen / 100, DEF_PEN_PRIORITY['guild_skill']))

        # Final Damage - multiplicative
        guild_fd = guild_skills.get('final_damage', 0)
        if guild_fd > 0:
            stats['final_damage_sources'].append(guild_fd / 100)

        # Additive stats
        stats['damage_pct'] += guild_skills.get('damage', 0)
        stats['boss_damage'] += guild_skills.get('boss_damage', 0)
        stats['crit_damage'] += guild_skills.get('crit_damage', 0)
        stats[main_pct_key] += guild_skills.get('main_stat', 0)
        stats['attack_flat'] += guild_skills.get('attack', 0)

    # Weapon Mastery stats (calculated from weapon awakening levels)
    if weapons_data:
        mastery_stages = calculate_mastery_stages_from_weapons(weapons_data)
        mastery_stats = calculate_mastery_stats(mastery_stages)
        stats['attack_flat'] += mastery_stats['attack']
        stats[main_flat_key] += mastery_stats['main_stat']
        stats['accuracy'] += mastery_stats['accuracy']
        stats['min_dmg_mult'] += mastery_stats['min_dmg_mult']
        stats['max_dmg_mult'] += mastery_stats['max_dmg_mult']

    # Artifacts - equipped active effects and inventory effects
    # Build name->key mapping for fallback
    artifact_key_by_name = {defn.name: key for key, defn in ARTIFACTS.items()}

    # Track Book of Ancient stars for CR->CD conversion
    # IMPORTANT: Only apply if Book is actually EQUIPPED (in one of the 3 slots)
    # AND we're not skipping artifact actives (used for artifact ranking baseline)
    # The Book's CR→CD conversion is an active effect, so it should be excluded
    # from baseline when calculating individual artifact DPS contributions.
    book_of_ancient_stars = 0
    artifacts_inventory = getattr(user_data, 'artifacts_inventory', {})

    # Equipped artifacts (active effects)
    # Now uses scenario-aware artifact effects
    # Skip if skip_artifact_actives is True (used for artifact ranking calculations)
    artifacts_equipped = getattr(user_data, 'artifacts_equipped', {})

    # First pass: check if Book of Ancient is equipped
    # Skip this if skip_artifact_actives is True - Book's CR→CD is an active effect
    if artifacts_equipped and not skip_artifact_actives:
        for slot_key in ['slot0', 'slot1', 'slot2', 'slot3']:
            slot_data = artifacts_equipped.get(slot_key, {})
            if not isinstance(slot_data, dict):
                continue
            artifact_key = slot_data.get('artifact', '')
            if not artifact_key:
                name = slot_data.get('name', '')
                artifact_key = artifact_key_by_name.get(name, '')
            if artifact_key == 'book_of_ancient':
                # Book is equipped - get its stars from inventory
                if artifacts_inventory and 'book_of_ancient' in artifacts_inventory:
                    book_data = artifacts_inventory.get('book_of_ancient', {})
                    if isinstance(book_data, dict):
                        book_of_ancient_stars = int(book_data.get('stars', 0))
                else:
                    book_of_ancient_stars = int(slot_data.get('stars', 0))
                break

    # Store in stats for use by calculate_dps
    stats['book_of_ancient_stars'] = book_of_ancient_stars

    # Second pass: apply active effects from equipped artifacts
    if artifacts_equipped and not skip_artifact_actives:
        for slot_key in ['slot0', 'slot1', 'slot2', 'slot3']:
            slot_data = artifacts_equipped.get(slot_key, {})
            if not isinstance(slot_data, dict):
                continue

            # Get artifact key - prefer name-based lookup for accuracy
            # (artifact field may be stale if user changed equipment)
            name = slot_data.get('name', '')
            artifact_key = ''
            if name and name != '(Empty)':
                # Name lookup is source of truth
                artifact_key = artifact_key_by_name.get(name, '')
            if not artifact_key:
                # Fallback to artifact field if name lookup failed
                artifact_key = slot_data.get('artifact', '')

            if not artifact_key or artifact_key not in ARTIFACTS:
                continue

            # Get stars from inventory (source of truth) or fall back to slot data
            if artifact_key in artifacts_inventory:
                inv_data = artifacts_inventory.get(artifact_key, {})
                stars = int(inv_data.get('stars', 0)) if isinstance(inv_data, dict) else 0
            else:
                stars = int(slot_data.get('stars', 0))

            defn = ARTIFACTS[artifact_key]

            # Check if artifact's active effect applies to current scenario
            if not defn.applies_to_scenario(scenario):
                continue  # Skip this artifact's active effect

            # Get uptime for this artifact
            fight_duration = scenario_params.fight_duration
            uptime = defn.get_effective_uptime(fight_duration)

            # All artifacts now use active_effects format
            if not defn.active_effects:
                continue

            # Special handling for Candle: dual-phase timing (FD 0-20s, Boss DMG 20-30s)
            # Standard single uptime can't represent two different time windows per effect.
            if artifact_key == 'candle':
                fd_uptime = min(20.0, fight_duration) / fight_duration if fight_duration > 0 else 0.0
                boss_uptime = (max(0.0, min(30.0, fight_duration) - 20.0) / fight_duration
                               if fight_duration > 0 else 0.0)
                for effect in defn.active_effects:
                    ev = effect.get_value(stars)
                    if effect.stat == 'final_damage':
                        if ev * fd_uptime > 0:
                            stats['final_damage_sources'].append(ev * fd_uptime)
                    elif effect.stat == 'boss_damage':
                        stats['boss_damage'] += ev * boss_uptime * 100
                continue  # Skip standard effect loop for this artifact

            for effect in defn.active_effects:
                # Companion-gated effects (Horn Flute): route raw value (no
                # uptime averaging) into a dedicated source list. The
                # realistic-DPS simulator gates them on actual summon-active
                # state; the legacy path averages them in below.
                if effect.companion_gated and effect.stat == 'final_damage':
                    raw_value = effect.get_value(stars)
                    if raw_value > 0:
                        stats['companion_active_fd_sources'].append(raw_value)
                    continue

                # Book of Ancient's DERIVED crit_damage (CR→CD conversion)
                # is owned by calculate_dps at the final crit_mult stage,
                # where the FULL aggregated crit_rate is available. Computing
                # it here in the artifact loop runs against an incomplete
                # crit_rate (baseline masteries aren't yet added at this
                # point in aggregate_stats), under-counting the CD bonus.
                # Skip; calculate_dps handles it.
                if (artifact_key == 'book_of_ancient'
                        and effect.effect_type == EffectType.DERIVED
                        and effect.stat == 'crit_damage'):
                    continue

                effect_value = effect.get_value(stars) * uptime

                if effect.effect_type == EffectType.DERIVED and effect.derived_from:
                    # Derived effects (e.g., Book of Ancient CD from CR, Athena max dmg from speed)
                    source_stat = effect.derived_from
                    if source_stat == 'crit_rate':
                        source_value = stats.get('crit_rate', 0) / 100
                        effect_value = effect.get_value(stars) * source_value * uptime
                    elif source_stat == 'attack_speed':
                        # Athena Pierce's Gloves: max_dmg = conversion_rate × attack_speed
                        total_atk_spd, _ = calculate_effective_attack_speed_with_sources(
                            stats.get('attack_speed_sources', [])
                        )
                        source_value = total_atk_spd / 100  # as decimal
                        effect_value = effect.get_value(stars) * source_value * uptime
                    elif source_stat == 'attack_speed_fd':
                        # Bottle of Emotions: FD = rate × (spd-60)/3 ticks, capped at cap
                        total_atk_spd, _ = calculate_effective_attack_speed_with_sources(
                            stats.get('attack_speed_sources', [])
                        )
                        ticks = max(0.0, total_atk_spd - 60.0) / 3.0
                        fd_cap = (0.10 + 0.02 * stars) * uptime
                        effect_value = min(fd_cap, effect.get_value(stars) * ticks * uptime)
                    else:
                        source_value = stats.get(source_stat, 0)
                        effect_value = effect.get_value(stars) * source_value * uptime

                elif effect.effect_type == EffectType.MULTIPLICATIVE:
                    # Hex Necklace: Calculate time-weighted multiplier
                    # Kept separate from final_damage for easier stat verification
                    if artifact_key == 'hexagon_necklace':
                        if stars > 0:
                            stats['hex_necklace_stars'] = stars
                            # Calculate time-weighted average multiplier based on fight duration
                            hex_mult = calculate_hex_average_multiplier(stars, fight_duration)
                            stats['hex_multiplier'] = hex_mult
                        continue

                # Handle per-target effects (Fire Flower)
                # Use weighted average: mob_stacks * mob_fraction + boss_stacks * boss_fraction
                if effect.max_stacks > 0 and effect.stat == 'final_damage':
                    mob_stacks = min(num_enemies, effect.max_stacks)
                    boss_stacks = min(1, effect.max_stacks)
                    weighted_stacks = mob_stacks * mob_time_fraction + boss_stacks * (1 - mob_time_fraction)
                    effect_value = effect_value * weighted_stacks

                # Apply the effect based on stat type
                stat = effect.stat
                if stat == 'crit_rate':
                    stats['crit_rate'] += effect_value * 100
                elif stat == 'crit_damage':
                    stats['crit_damage'] += effect_value * 100
                elif stat == 'boss_damage':
                    stats['boss_damage'] += effect_value * 100
                elif stat == 'normal_damage':
                    stats['normal_damage'] += effect_value * 100
                elif stat in ('damage', 'damage_multiplier'):
                    stats['damage_pct'] += effect_value * 100
                elif stat == 'final_damage':
                    if effect_value > 0:
                        stats['final_damage_sources'].append(effect_value)
                elif stat == 'attack_speed':
                    stats['attack_speed_sources'].append((f'{defn.name}_active', effect_value * 100))
                elif stat == 'max_damage_mult':
                    stats['max_dmg_mult'] += effect_value * 100
                elif stat == 'attack_buff':
                    # ATK % buff (Charm of Undead, Old Music Box)
                    stats['attack_pct'] += effect_value * 100
                elif stat == 'enemy_damage_taken':
                    # Enemy damage taken (Silver Pendant) - acts like FD
                    if effect_value > 0:
                        stats['final_damage_sources'].append(effect_value)
                elif stat == 'buff_duration':
                    # Buff duration: decimal → percentage points; extends buff uptime
                    stats['buff_duration'] += effect_value * 100
                elif stat == 'companion_duration':
                    # +X% to the companion summon window. Stored as percentage
                    # points so the simulator can do `base * (1 + pct/100)`.
                    # Hero-power values arrive as a decimal (0.20 = +20%) so
                    # scale × 100, matching how other percent stats convert.
                    # Sequence-affecting in the realistic simulator.
                    stats['companion_duration'] += effect_value * 100
                # Utility stats (no DPS impact) - silently skip
                elif stat in ('hp_recovery', 'hp_mp_recovery',
                              'cooldown_reduction', 'utility'):
                    pass

    # Artifact inventory effects (passive bonuses from all owned artifacts)
    # Note: artifacts_inventory already loaded above for Book of Ancient stars
    #
    # IMPORTANT: Inventory stats apply to ALL owned artifacts (passive bonus from owning)
    # but artifact POTENTIALS only apply from EQUIPPED artifacts!

    # Build set of equipped artifact keys for potential filtering
    equipped_artifact_keys = set()
    if artifacts_equipped:
        for slot_key in ['slot0', 'slot1', 'slot2', 'slot3']:
            slot_data = artifacts_equipped.get(slot_key, {})
            if not isinstance(slot_data, dict):
                continue
            # Try artifact key directly, fall back to name lookup
            artifact_key = slot_data.get('artifact', '')
            if not artifact_key:
                name = slot_data.get('name', '')
                if name and name != '(Empty)':
                    artifact_key = artifact_key_by_name.get(name, '')
            if artifact_key:
                equipped_artifact_keys.add(artifact_key)

    if artifacts_inventory:
        for art_key, art_data in artifacts_inventory.items():
            if art_key not in ARTIFACTS:
                continue
            if not isinstance(art_data, dict):
                continue

            defn = ARTIFACTS[art_key]
            stars = int(art_data.get('stars', 0))

            # Inventory stat (passive effect from owning the artifact) - applies to ALL
            inv_stat = defn.inventory_stat
            inv_value = defn.get_inventory_value(stars)

            if inv_value > 0:
                if inv_stat == 'attack_flat':
                    stats['attack_flat'] += inv_value
                elif inv_stat == 'damage':
                    stats['damage_pct'] += inv_value * 100
                elif inv_stat == 'boss_damage':
                    stats['boss_damage'] += inv_value * 100
                elif inv_stat == 'normal_damage':
                    stats['normal_damage'] += inv_value * 100
                elif inv_stat == 'crit_rate':
                    # Book of Ancient inventory: crit rate
                    stats['crit_rate'] += inv_value * 100
                elif inv_stat == 'crit_damage':
                    # Icy Soul Rock inventory: straight crit damage
                    stats['crit_damage'] += inv_value * 100
                elif inv_stat == 'max_damage_mult':
                    stats['max_dmg_mult'] += inv_value * 100
                elif inv_stat == 'def_pen':
                    # Silver Pendant inventory: defense penetration
                    stats['def_pen_sources'].append(('Artifact Inventory', inv_value, 100))
                elif inv_stat == 'basic_attack_damage':
                    # Sayram's Necklace inventory: basic attack damage
                    stats['basic_attack_damage'] += inv_value * 100
                elif inv_stat == 'skill_damage':
                    # Soul Contract inventory: skill damage
                    stats['skill_damage'] += inv_value * 100
                elif inv_stat == 'min_dmg_mult':
                    # Bottle of Emotions inventory: min damage %
                    stats['min_dmg_mult'] += inv_value * 100
                elif inv_stat == 'attack_speed':
                    # Artifact inventory: attack speed %
                    stats['attack_speed_sources'].append((f'{defn.name} (Inventory)', inv_value * 100))
                # Note: Utility stats like defense, debuff_tolerance, evasion,
                # damage_taken_decrease are not DPS stats and are skipped

            # Artifact potentials - ONLY from EQUIPPED artifacts!
            if art_key not in equipped_artifact_keys:
                continue  # Skip potentials for non-equipped artifacts

            # Determine how many slots are unlocked based on stars
            # Slot 0: unlocked at 1★, Slot 1: unlocked at 3★, Slot 2: unlocked at 5★
            slots_unlocked = POTENTIAL_SLOT_UNLOCKS.get(stars, 0)
            # For non-legendary artifacts, cap at 2 slots
            if defn.tier != ArtifactTier.LEGENDARY and slots_unlocked > 2:
                slots_unlocked = 2

            potentials = art_data.get('potentials', [])
            if isinstance(potentials, list):
                for idx, pot in enumerate(potentials):
                    # Skip slots that aren't unlocked yet
                    if idx >= slots_unlocked:
                        continue
                    if isinstance(pot, dict):
                        pot_stat = pot.get('stat', '')
                        pot_value = float(pot.get('value', 0) or 0)
                        if pot_value > 0:
                            if pot_stat == 'main_stat_pct':
                                stats[main_pct_key] += pot_value
                            elif pot_stat == 'damage_pct':
                                stats['damage_pct'] += pot_value
                            elif pot_stat == 'boss_damage':
                                stats['boss_damage'] += pot_value
                            elif pot_stat == 'normal_damage':
                                stats['normal_damage'] += pot_value
                            elif pot_stat == 'crit_rate':
                                stats['crit_rate'] += pot_value
                            elif pot_stat == 'crit_damage':
                                stats['crit_damage'] += pot_value
                            elif pot_stat == 'def_pen':
                                stats['def_pen_sources'].append(('Artifact Potential', pot_value / 100, 100))
                            elif pot_stat == 'min_dmg_mult':
                                stats['min_dmg_mult'] += pot_value
                            elif pot_stat == 'max_dmg_mult':
                                stats['max_dmg_mult'] += pot_value

    # Artifact Resonance stats (flat main stat and max HP from resonance level)
    artifacts_resonance = getattr(user_data, 'artifacts_resonance', {}) or {}
    if artifacts_resonance:
        resonance_level = int(artifacts_resonance.get('resonance_level', 0))
        if resonance_level > 0:
            from game.artifacts import calculate_resonance_main_stat, calculate_resonance_hp
            # Flat main stat from resonance
            resonance_main = calculate_resonance_main_stat(resonance_level)
            stats[main_flat_key] += resonance_main
            # Max HP from resonance (not a DPS stat but tracked for reference)
            # resonance_hp = calculate_resonance_hp(resonance_level)

    # =========================================================================
    # Skill Passive Stats (from PASSIVE_STAT type skills and mastery nodes)
    # =========================================================================
    try:
        from game.skills import DPSCalculator as SkillDPSCalculator, CharacterState, get_global_mastery_stats
        # Use correct UserData attributes
        char_level = getattr(user_data, 'character_level', 100)
        all_skills_bonus = getattr(user_data, 'all_skills', 0)

        # Calculate job-specific skill bonuses from equipment sub-stats
        # These affect skills like Bow Mastery's min_dmg_mult calculation
        skill_1st_total = int(stats.get('skill_1st_bonus', 0))
        skill_2nd_total = int(stats.get('skill_2nd_bonus', 0))
        skill_3rd_total = int(stats.get('skill_3rd_bonus', 0))
        skill_4th_total = int(stats.get('skill_4th_bonus', 0))

        char = CharacterState(
            level=char_level,
            all_skills_bonus=all_skills_bonus,
            skill_1st_bonus=skill_1st_total,
            skill_2nd_bonus=skill_2nd_total,
            skill_3rd_bonus=skill_3rd_total,
            skill_4th_bonus=skill_4th_total,
        )
        calc = SkillDPSCalculator(char)

        # Get passive skill bonuses (None = permanent stats for char sheet)
        skill_bonuses = calc.get_all_skill_stat_bonuses(is_boss_phase=None)

        # Apply passive skill stats
        if 'min_dmg_mult' in skill_bonuses:
            stats['min_dmg_mult'] += sum(skill_bonuses['min_dmg_mult'])
        if 'attack_speed' in skill_bonuses:
            for value in skill_bonuses['attack_speed']:
                stats['attack_speed_sources'].append(('Passive Skills', value))
        if 'defense_pen' in skill_bonuses:
            for value in skill_bonuses['defense_pen']:
                stats['def_pen_sources'].append(('Passive Skills', value / 100, 50))
        if 'final_damage' in skill_bonuses:
            for value in skill_bonuses['final_damage']:
                stats['final_damage_sources'].append(value / 100)
        if 'crit_rate' in skill_bonuses:
            stats['crit_rate'] += sum(skill_bonuses['crit_rate'])
        if 'dex_flat' in skill_bonuses:
            stats[main_flat_key] += sum(skill_bonuses['dex_flat'])
        if 'basic_attack_damage' in skill_bonuses:
            stats['basic_attack_damage'] += sum(skill_bonuses['basic_attack_damage'])

        # Get global mastery stats
        mastery_stats = get_global_mastery_stats(char_level)

        if 'max_dmg_mult' in mastery_stats:
            stats['max_dmg_mult'] += mastery_stats['max_dmg_mult']
        if 'crit_rate' in mastery_stats:
            stats['crit_rate'] += mastery_stats['crit_rate']
        if 'attack_speed' in mastery_stats:
            stats['attack_speed_sources'].append(('Mastery Nodes', mastery_stats['attack_speed']))
        if 'main_stat_flat' in mastery_stats:
            stats[main_flat_key] += mastery_stats['main_stat_flat']
        if 'basic_attack_damage' in mastery_stats:
            stats['basic_attack_damage'] += mastery_stats['basic_attack_damage']
        if 'skill_damage' in mastery_stats:
            stats['skill_damage'] += mastery_stats['skill_damage']

        # Apply stat conversions (e.g., Shield Mastery: LUK = 10% of Defense)
        stat_conversions = calc.get_stat_conversions()
        for source, target, rate_pct in stat_conversions:
            # Resolve source stat value
            if source == "defense":
                source_value = stats['defense_flat'] * (1 + stats['defense_pct'] / 100)
            else:
                source_value = stats.get(source, 0)

            converted = source_value * rate_pct / 100

            # Resolve target stat key.
            # Skill-converted main/secondary stats are kept SEPARATE from equipment flat stats
            # so they are NOT multiplied by %main_stat / %secondary_stat in calculate_hit_damage().
            if target == "main_stat_flat":
                stats['main_stat_conversion'] = stats.get('main_stat_conversion', 0) + converted
            elif target == "secondary_stat_flat":
                stats['secondary_stat_conversion'] = stats.get('secondary_stat_conversion', 0) + converted
            else:
                if target in stats:
                    stats[target] += converted

    except Exception as e:
        import traceback
        print(f"Error in skill passive stats: {e}")
        traceback.print_exc()

    # =========================================================================
    # PASS 3: Apply Manual Adjustments (if enabled)
    # =========================================================================
    # Manual adjustments from Character Stats page help account for
    # any remaining stat differences (e.g., buffs, titles, etc.)
    if apply_adjustments:
        manual_adj = getattr(user_data, 'manual_adjustments', {}) or {}
        if manual_adj:
            # Map adjustment keys to standardized stat keys
            # Manual adjustment uses main_flat_key/main_pct_key for job-specific main stat
            adjustment_mapping = {
                'main_stat_flat': main_flat_key,
                'main_stat_pct': main_pct_key,
                # Job-specific keys also map to main/secondary (handles legacy saves)
                main_flat_key: main_flat_key,
                main_pct_key: main_pct_key,
                secondary_flat_key: secondary_flat_key,
                secondary_pct_key: secondary_pct_key,
                'attack_flat': 'attack_flat',
                'attack_pct': 'attack_pct',
                'damage_pct': 'damage_pct',
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
            # def_pen adjustment - add as a manual source
            def_pen_adj = manual_adj.get('def_pen', 0)
            if def_pen_adj != 0:
                # Convert percentage to decimal and add as lowest priority source
                stats['def_pen_sources'].append(('Manual Adjustment', def_pen_adj / 100, 999))

            # attack_speed adjustment - add as a manual source
            atk_spd_adj = manual_adj.get('attack_speed', 0)
            if atk_spd_adj != 0:
                stats['attack_speed_sources'].append(('Manual Adjustment', atk_spd_adj))

            # final_damage adjustment - use multiplicative correction
            # FD is multiplicative, so we use a correction multiplier:
            # If calc FD mult is 4.0 (300%) but actual is 2.0 (100%), correction = 0.5
            # This correction is applied to the final FD multiplier in calculate_dps()
            fd_correction = manual_adj.get('final_damage_correction', 1.0)
            if fd_correction != 1.0:
                stats['final_damage_correction'] = fd_correction
            # Legacy: ignore old additive FD adjustments (they don't work correctly)
            # fd_adj = manual_adj.get('final_damage', 0) - intentionally not used

            # total_main_stat and total_attack adjustments need special handling
            # They are derived stats, so we track adjustment separately
            # These will be applied in calculate_dps
            stats['total_main_stat_adjustment'] = manual_adj.get('total_main_stat', 0)
            stats['total_attack_adjustment'] = manual_adj.get('total_attack', 0)

    return stats


def build_character_model_from_stats(stats: Dict[str, Any], job_class: JobClass) -> 'CharacterModel':
    """
    Convert the raw aggregate_stats() dict to a typed CharacterModel.

    Collapses multiplicative source lists to scalars:
      - final_damage_sources (List[float]) → final_damage_pct (0-100)
      - def_pen_sources (List[tuple]) → def_pen_pct (0-100)
      - attack_speed_sources (List[tuple]) → attack_speed_pct (0-100)

    The source lists are kept separately in the raw stats dict for display purposes
    (e.g., Character Stats page source breakdowns). CharacterModel holds the
    pre-combined scalars for clean calculation.
    """
    from core.models import CharacterModel

    main_stat_type = get_main_stat_name(job_class)
    secondary_stat_type = get_secondary_stat_name(job_class)
    main_flat_key = f'{main_stat_type}_flat'
    main_pct_key = f'{main_stat_type}_pct'
    secondary_flat_key = f'{secondary_stat_type}_flat'
    secondary_pct_key = f'{secondary_stat_type}_pct'

    # Collapse multiplicative source lists to 0-100 scalars
    total_def_pen, _ = calculate_effective_defense_pen_with_sources(
        stats.get('def_pen_sources', [])
    )
    total_atk_spd, _ = calculate_effective_attack_speed_with_sources(
        stats.get('attack_speed_sources', [])
    )
    fd_mult = calculate_final_damage_mult(stats.get('final_damage_sources', []))
    fd_correction = stats.get('final_damage_correction', 1.0)
    if fd_correction != 1.0:
        fd_mult *= fd_correction
    final_damage_pct = (fd_mult - 1) * 100  # e.g. 1.30x → 30.0%

    return CharacterModel(
        job_class=job_class.value,
        level=stats.get('level', 100),
        attack_flat=stats.get('attack_flat', 0.0),
        attack_pct=stats.get('attack_pct', 0.0),
        main_stat_flat=stats.get(main_flat_key, 0.0),
        main_stat_pct=stats.get(main_pct_key, 0.0),
        main_stat_conversion=stats.get('main_stat_conversion', 0.0),
        secondary_stat_flat=stats.get(secondary_flat_key, 0.0),
        secondary_stat_pct=stats.get(secondary_pct_key, 0.0),
        secondary_stat_conversion=stats.get('secondary_stat_conversion', 0.0),
        damage_pct=stats.get('damage_pct', 0.0),
        boss_damage=stats.get('boss_damage', 0.0),
        normal_damage=stats.get('normal_damage', 0.0),
        skill_damage=stats.get('skill_damage', 0.0),
        basic_attack_damage=stats.get('basic_attack_damage', 0.0),
        damage_amp=stats.get('damage_amp', 0.0),
        final_damage_pct=final_damage_pct,
        final_damage_correction=stats.get('final_damage_correction', 1.0),
        crit_rate=stats.get('crit_rate', 0.0),
        crit_damage=stats.get('crit_damage', 0.0),
        def_pen_pct=total_def_pen * 100,   # decimal → 0-100
        attack_speed_pct=total_atk_spd,
        min_dmg_mult=stats.get('min_dmg_mult', 0.0),
        max_dmg_mult=stats.get('max_dmg_mult', 0.0),
        all_skills_bonus=int(stats.get('all_skills_bonus', 0)),
        skill_1st_bonus=int(stats.get('skill_1st_bonus', 0)),
        skill_2nd_bonus=int(stats.get('skill_2nd_bonus', 0)),
        skill_3rd_bonus=int(stats.get('skill_3rd_bonus', 0)),
        skill_4th_bonus=int(stats.get('skill_4th_bonus', 0)),
        skill_cd_reduction=stats.get('skill_cd_reduction', 0.0),
        ba_target_bonus=int(stats.get('ba_target_bonus', 0)),
        buff_duration=stats.get('buff_duration', 0.0),
        hex_multiplier=stats.get('hex_multiplier', 1.0),
        hex_necklace_stars=int(stats.get('hex_necklace_stars', 0)),
        book_of_ancient_stars=int(stats.get('book_of_ancient_stars', 0)),
        accuracy=stats.get('accuracy', 0.0),
        total_main_stat_adjustment=stats.get('total_main_stat_adjustment', 0.0),
        total_attack_adjustment=stats.get('total_attack_adjustment', 0.0),
        unique_attack_speed_level=int(stats.get('unique_attack_speed_level', 0)),
        unique_crit_chance_level=int(stats.get('unique_crit_chance_level', 0)),
        unique_min_damage_level=int(stats.get('unique_min_damage_level', 0)),
        unique_max_damage_level=int(stats.get('unique_max_damage_level', 0)),
        unique_crit_power_level=int(stats.get('unique_crit_power_level', 0)),
        unique_normal_damage_level=int(stats.get('unique_normal_damage_level', 0)),
        unique_boss_damage_level=int(stats.get('unique_boss_damage_level', 0)),
        unique_skill_power_level=int(stats.get('unique_skill_power_level', 0)),
        unique_attack_power_level=int(stats.get('unique_attack_power_level', 0)),
        unique_main_stat_level=int(stats.get('unique_main_stat_level', 0)),
    )


def aggregate_to_character_model(
    user_data,
    star_overrides: Dict[str, int] = None,
    apply_adjustments: bool = True,
    scenario: str = None,
    skip_artifact_actives: bool = False,
) -> 'CharacterModel':
    """
    Aggregate all stats into a typed CharacterModel.

    Wraps aggregate_stats() + build_character_model_from_stats().
    Use this when you need a typed CharacterModel for calculations.
    Use aggregate_stats() directly when you need source breakdowns for display.
    """
    job_class = JobClass(user_data.job_class)
    stats = aggregate_stats(
        user_data,
        star_overrides=star_overrides,
        apply_adjustments=apply_adjustments,
        scenario=scenario,
        skip_artifact_actives=skip_artifact_actives,
    )
    return build_character_model_from_stats(stats, job_class)


def calculate_basic_attack_damage(stats: Dict[str, Any], enemy_def: float = 0.752,
                                   job_class: JobClass = None, vs_boss: bool = False) -> Dict[str, Any]:
    """
    Calculate single damage line for basic attack skill.

    This returns the damage of ONE hit (one damage number you see in-game).
    For Arrow Stream at level 100+: 5 hits per attack × 6 targets = 30 damage lines.
    This calculates what ONE of those 30 lines should be.

    Args:
        stats: Aggregated character stats dictionary
        enemy_def: Enemy defense value
        job_class: Character's job class
        vs_boss: If True, use boss damage; if False, use normal damage

    Returns:
        Dict with single-line damage values and formula breakdown
    """
    from game.skills import create_character_at_level, DPSCalculator, BOWMASTER_SKILLS

    # Get job class for stat key lookup
    if job_class is None:
        raise ValueError("job_class must be provided to calculate_dps — got None")
    if isinstance(job_class, str):
        job_class = JobClass(job_class)
    main_stat_type = get_main_stat_name(job_class)
    main_flat_key = f'{main_stat_type}_flat'
    main_pct_key = f'{main_stat_type}_pct'
    secondary_stat_type = get_secondary_stat_name(job_class)
    secondary_flat_key = f'{secondary_stat_type}_flat'
    secondary_pct_key = f'{secondary_stat_type}_pct'

    # Calculate multiplicative stats
    total_defense_pen, _ = calculate_effective_defense_pen_with_sources(
        stats.get('def_pen_sources', [])
    )
    fd_mult = calculate_final_damage_mult(stats.get('final_damage_sources', []))

    # Apply FD correction if set
    fd_correction = stats.get('final_damage_correction', 1.0)
    if fd_correction != 1.0:
        fd_mult *= fd_correction

    # Main stat (1% per point) and secondary stat (0.25% per point)
    main_stat_flat = stats.get(main_flat_key, 0)
    main_stat_pct = stats.get(main_pct_key, 0)
    total_main_stat = calculate_total_dex(main_stat_flat, main_stat_pct)

    secondary_stat_flat = stats.get(secondary_flat_key, 0)
    secondary_stat_pct = stats.get(secondary_pct_key, 0)
    total_secondary_stat = secondary_stat_flat * (1 + secondary_stat_pct / 100)

    # Total attack
    attack_flat = max(stats.get('attack_flat', 0), 10000)
    attack_pct = stats.get('attack_pct', 0)
    total_attack = attack_flat * (1 + attack_pct / 100)

    # Damage multipliers
    damage_pct = stats.get('damage_pct', 0)
    boss_damage = stats.get('boss_damage', 0)
    normal_damage = stats.get('normal_damage', 0)
    damage_amp = stats.get('damage_amp', 0)
    basic_attack_damage = stats.get('basic_attack_damage', 0)
    hex_mult = stats.get('hex_multiplier', 1.0)

    # Damage multipliers - these are SEPARATE multipliers, not additive
    damage_mult = 1 + (damage_pct / 100)  # Base damage %

    # Boss/Normal damage is a separate multiplier
    if vs_boss:
        target_dmg_mult = 1 + (boss_damage / 100)
    else:
        target_dmg_mult = 1 + (normal_damage / 100)

    amp_mult = 1 + (damage_amp / 100)
    ba_dmg_mult = 1 + (basic_attack_damage / 100)  # Basic Attack Damage %
    # Stat multiplier: main stat gives 1% per point, secondary gives 0.25% per point
    # stat_dmg_pct = main_stat * 0.01 + secondary_stat * 0.0025
    # multiplier = 1 + (stat_dmg_pct / 100)
    # Combined: stat_mult = 1 + (main_stat / 10000) + (secondary_stat / 40000)
    stat_mult = 1 + (total_main_stat / 10000) + (total_secondary_stat / 40000)
    def_mult = 1 / (1 + enemy_def * (1 - total_defense_pen))

    # Crit stats
    crit_rate = stats.get('crit_rate', 0)
    crit_damage = stats.get('crit_damage', 0) + BASE_CRIT_DMG
    crit_mult = 1 + (crit_damage / 100)

    # Damage range
    min_dmg = BASE_MIN_DMG + stats.get('min_dmg_mult', 0)
    max_dmg = BASE_MAX_DMG + stats.get('max_dmg_mult', 0)

    # Create character for skill calculations
    level = stats.get('level', 140)
    all_skills = int(stats.get('all_skills_bonus', 0))
    char = create_character_at_level(level, all_skills)
    char.attack = total_attack

    # Determine basic attack skill based on level
    if level >= 100:
        ba_skill_name = "arrow_stream"
    elif level >= 60:
        ba_skill_name = "wind_arrow_2"
    elif level >= 30:
        ba_skill_name = "wind_arrow"
    else:
        ba_skill_name = "double_shot"

    ba_skill = BOWMASTER_SKILLS.get(ba_skill_name)
    ba_display_name = ba_skill.name if ba_skill else ba_skill_name.replace('_', ' ').title()

    # Get skill damage % (the % shown on the skill tooltip)
    calc = DPSCalculator(char, enemy_def=enemy_def)
    skill_dmg_pct = calc.get_skill_damage_pct(ba_skill_name)
    skill_mult = skill_dmg_pct / 100

    # Get hits and targets for reference
    hits = calc.get_skill_hits(ba_skill_name)
    targets = calc.get_skill_targets(ba_skill_name)

    # Single line damage = ATK × Stat × Damage% × Boss/Normal% × Amp × FD × Defense × Skill% × BA% × Hex
    base_line = total_attack * stat_mult * damage_mult * target_dmg_mult * amp_mult * fd_mult * def_mult * skill_mult * ba_dmg_mult * hex_mult

    # Apply damage range for min/max
    line_min = base_line * (min_dmg / 100)
    line_max = base_line * (max_dmg / 100)

    # Crit versions
    crit_min = line_min * crit_mult
    crit_max = line_max * crit_mult

    return {
        'skill_name': ba_skill_name,
        'skill_display_name': ba_display_name,
        'skill_damage_pct': skill_dmg_pct,
        'hits': hits,
        'targets': targets,
        # Single line damage values
        'min': line_min,
        'max': line_max,
        'crit_min': crit_min,
        'crit_max': crit_max,
        # Formula components for breakdown
        'total_attack': total_attack,
        'total_main_stat': total_main_stat,
        'total_secondary_stat': total_secondary_stat,
        'stat_mult': stat_mult,
        'damage_mult': damage_mult,
        'target_dmg_mult': target_dmg_mult,  # Boss% or Normal% (separate multiplier)
        'damage_pct': damage_pct,
        'boss_damage': boss_damage,
        'normal_damage': normal_damage,
        'amp_mult': amp_mult,
        'damage_amp': damage_amp,
        'fd_mult': fd_mult,
        'def_mult': def_mult,
        'skill_mult': skill_mult,
        'crit_mult': crit_mult,
        'crit_damage': crit_damage,
        'min_dmg_range': min_dmg,
        'max_dmg_range': max_dmg,
        'defense_pen': total_defense_pen,
        'enemy_def': enemy_def,
        'vs_boss': vs_boss,
        # BA-specific multipliers
        'ba_dmg_mult': ba_dmg_mult,
        'basic_attack_damage': basic_attack_damage,
        'hex_mult': hex_mult,
    }


def calculate_dps(stats: Dict[str, Any], combat_mode: str = 'stage', enemy_def: float = 0.752,
                   job_class: JobClass = None, use_realistic_dps: bool = False,
                   boss_importance: float = 0.7, log_actions: bool = False,
                   boss_damage_multiplier: float = 1.0,
                   include_companion_summon: bool = True) -> Dict[str, Any]:
    """
    Calculate DPS using the full skill rotation model.

    Uses DPSCalculator from skills.py to properly account for:
    - Multi-target damage (BA targets, skill targets)
    - Skill rotations and cooldowns
    - Attack speed effects on rotation
    - Book of Ancient CR → CD conversion

    Args:
        stats: Aggregated character stats dictionary
        combat_mode: Combat scenario ('stage', 'boss', 'world_boss', 'chapter_hunt')
        enemy_def: Enemy defense value
        job_class: Character's job class
        use_realistic_dps: If True, uses phase-aware simulation that:
            - Applies boss damage only during boss phase
            - Applies normal damage only during mob phase
            - Schedules skills optimally per phase (e.g., saves Hurricane for boss)
        boss_importance: Weight for boss vs mob damage (0.0-1.0)
        log_actions: If True, include detailed fight log
        boss_damage_multiplier: Multiplier for boss phase DPS display (for comparison)

    Returns:
        Dict with 'total' DPS and component multipliers
    """
    from game.skills import CharacterState

    # Get job class for stat key lookup
    if job_class is None:
        raise ValueError("job_class must be provided to calculate_dps — got None")
    if isinstance(job_class, str):
        job_class = JobClass(job_class)
    main_stat_type = get_main_stat_name(job_class)
    main_flat_key = f'{main_stat_type}_flat'
    main_pct_key = f'{main_stat_type}_pct'

    # Calculate multiplicative stats using core functions
    total_defense_pen, def_pen_breakdown = calculate_effective_defense_pen_with_sources(
        stats.get('def_pen_sources', [])
    )
    total_attack_speed, atk_spd_breakdown = calculate_effective_attack_speed_with_sources(
        stats.get('attack_speed_sources', [])
    )
    fd_mult = calculate_final_damage_mult(stats.get('final_damage_sources', []))

    # Apply FD correction multiplier if set (for when actual FD differs from calculated)
    # e.g., if calculated FD mult is 4.0 but actual is 2.0, correction = 0.5
    fd_correction = stats.get('final_damage_correction', 1.0)
    if fd_correction != 1.0:
        fd_mult *= fd_correction

    # Companion-gated FD (Horn Flute): the artifact only applies its FD bonus
    # while a companion summon is currently up. We split paths here:
    #   - Realistic: store the raw combined decimal on the character; the
    #     simulator gates it on `active_summons` and bakes it into the
    #     companion snapshot at cast time.
    #   - Legacy:    no simulator to gate timing, so average the FD bonus by
    #     the companion's flat duty cycle (30s on / 90s cooldown ≈ 33%).
    companion_gated_fd_sources = stats.get('companion_active_fd_sources', [])
    companion_gated_fd_mult = calculate_final_damage_mult(companion_gated_fd_sources)
    companion_active_fd_decimal = companion_gated_fd_mult - 1.0  # +0.20 = +20% FD
    if not use_realistic_dps and companion_active_fd_decimal > 0:
        from game.companions import SUMMON_DURATION_S, SUMMON_COOLDOWN_S
        # Cap at 1.0 in case a companion_duration potential ever pushes the
        # window past the cooldown cycle.
        companion_uptime = min(1.0, SUMMON_DURATION_S / SUMMON_COOLDOWN_S)
        fd_mult *= (1 + companion_active_fd_decimal * companion_uptime)

    # Main stat calculation (with manual adjustment if present)
    main_stat_flat = stats.get(main_flat_key, 0)
    main_stat_pct = stats.get(main_pct_key, 0)
    total_main_stat = calculate_total_dex(main_stat_flat, main_stat_pct) + stats.get('main_stat_conversion', 0)
    total_main_stat += stats.get('total_main_stat_adjustment', 0)

    # Total attack = attack_flat * (1 + attack_pct/100) + manual adjustment
    attack_flat = max(stats.get('attack_flat', 0), 10000)
    attack_pct = stats.get('attack_pct', 0)
    base_atk = attack_flat * (1 + attack_pct / 100)
    base_atk += stats.get('total_attack_adjustment', 0)

    # Book of Ancient: Convert portion of Crit Rate to Crit Damage
    book_of_ancient_stars = stats.get('book_of_ancient_stars', 0)
    crit_rate = stats['crit_rate']
    base_crit_damage = stats['crit_damage']
    _, cd_from_book = calculate_book_of_ancient_bonus(book_of_ancient_stars, crit_rate / 100)
    total_crit_damage = base_crit_damage + (cd_from_book * 100)

    # Min/Max damage range
    final_min = BASE_MIN_DMG + stats['min_dmg_mult']
    final_max = BASE_MAX_DMG + stats['max_dmg_mult']
    avg_mult = (final_min + final_max) / 2
    dmg_range_mult = avg_mult / 100

    # Get combat scenario parameters
    combat_mode_enum = get_combat_mode_enum(combat_mode)
    scenario_params = COMBAT_SCENARIO_PARAMS.get(combat_mode_enum, COMBAT_SCENARIO_PARAMS[CombatMode.STAGE])
    num_enemies = scenario_params.num_enemies
    mob_time_fraction = scenario_params.mob_time_fraction
    fight_duration = scenario_params.fight_duration

    # Create character state from aggregated stats
    level = stats.get('level', 140)
    all_skills = int(stats.get('all_skills_bonus', 0))

    char = create_character_at_level(level, all_skills, job_class=job_class)
    char.attack = base_atk
    char.main_stat_flat = main_stat_flat
    char.main_stat_pct = main_stat_pct
    char.main_stat_conversion = stats.get('main_stat_conversion', 0)

    # Secondary stat (0.25% per point vs main stat's 1% per point)
    secondary_stat_type = get_secondary_stat_name(job_class)
    secondary_flat_key = f'{secondary_stat_type}_flat'
    secondary_pct_key = f'{secondary_stat_type}_pct'
    char.secondary_stat_flat = stats.get(secondary_flat_key, 0)
    char.secondary_stat_pct = stats.get(secondary_pct_key, 0)

    if use_realistic_dps:
        # Realistic DPS: pass raw stats, simulation handles phase weighting
        char.damage_pct = stats['damage_pct']
        char.boss_damage = stats['boss_damage']
        char.normal_damage = stats['normal_damage']
    else:
        # Legacy behavior: pre-weight boss/normal damage into damage_pct
        char.damage_pct = stats['damage_pct'] + stats['normal_damage'] * mob_time_fraction + stats['boss_damage'] * (1 - mob_time_fraction)
        char.boss_damage = stats['boss_damage']
        char.normal_damage = 0  # Not used in legacy mode

    char.crit_rate = crit_rate
    char.crit_damage = total_crit_damage
    char.min_dmg_mult = stats['min_dmg_mult']
    char.max_dmg_mult = stats['max_dmg_mult']
    char.skill_damage = stats.get('skill_damage', 0)
    char.basic_attack_damage = stats.get('basic_attack_damage', 0)
    char.final_damage_pct = (fd_mult - 1) * 100  # Convert multiplier to percentage
    char.def_pen_pct = total_defense_pen * 100  # Convert decimal to percentage (skills.py expects %)
    char.attack_speed_pct = total_attack_speed
    char.ba_target_bonus = int(stats.get('ba_target_bonus', 0))
    char.skill_cd_reduction = stats.get('skill_cd_reduction', 0)
    char.buff_duration_pct = stats.get('buff_duration', 0)
    # Hex necklace star count — the simulator steps stacks live, so the
    # realistic path needs the star count to look up per-stack multipliers.
    char.hex_necklace_stars = int(stats.get('hex_necklace_stars', 0))
    # Companion-gated FD (Horn Flute), combined as a multiplicative decimal.
    # Realistic-DPS only: applied to player damage events while a companion
    # is summoned, AND baked into the companion's snapshot once at cast time.
    # Legacy mode already folded this into fd_mult above (averaged by uptime).
    char.companion_active_fd_decimal = (
        companion_active_fd_decimal if use_realistic_dps else 0.0
    )

    # Job-specific skill level bonuses from equipment
    char.skill_1st_bonus = int(stats.get('skill_1st_bonus', 0))
    char.skill_2nd_bonus = int(stats.get('skill_2nd_bonus', 0))
    char.skill_3rd_bonus = int(stats.get('skill_3rd_bonus', 0))
    char.skill_4th_bonus = int(stats.get('skill_4th_bonus', 0))

    # Unique stats (HeroUniqueStatOption levels)
    char.unique_attack_speed_level = int(stats.get('unique_attack_speed_level', 0))
    char.unique_crit_chance_level = int(stats.get('unique_crit_chance_level', 0))
    char.unique_min_damage_level = int(stats.get('unique_min_damage_level', 0))
    char.unique_max_damage_level = int(stats.get('unique_max_damage_level', 0))
    char.unique_crit_power_level = int(stats.get('unique_crit_power_level', 0))
    char.unique_normal_damage_level = int(stats.get('unique_normal_damage_level', 0))
    char.unique_boss_damage_level = int(stats.get('unique_boss_damage_level', 0))
    char.unique_skill_power_level = int(stats.get('unique_skill_power_level', 0))
    char.unique_attack_power_level = int(stats.get('unique_attack_power_level', 0))
    char.unique_main_stat_level = int(stats.get('unique_main_stat_level', 0))

    # Apply unique stat bonuses to CharacterState
    unique_bonuses = char.get_unique_stat_bonuses()
    char.attack_speed_pct += unique_bonuses.get('attack_speed', 0)
    char.crit_rate += unique_bonuses.get('crit_rate', 0)
    char.min_dmg_mult += unique_bonuses.get('min_dmg_mult', 0)
    char.max_dmg_mult += unique_bonuses.get('max_dmg_mult', 0)
    char.crit_damage += unique_bonuses.get('crit_damage', 0)
    char.normal_damage += unique_bonuses.get('normal_damage', 0)
    char.boss_damage += unique_bonuses.get('boss_damage', 0)
    char.skill_damage += unique_bonuses.get('skill_damage', 0)
    # attack_pct is already baked into char.attack, so apply as multiplier
    atk_pct_bonus = unique_bonuses.get('attack_pct', 0)
    if atk_pct_bonus > 0:
        char.attack *= (1 + atk_pct_bonus / 100)
    # main_stat_flat is additive
    char.main_stat_flat += unique_bonuses.get('main_stat_flat', 0)

    # Calculate DPS using full skill rotation model
    calc = DPSCalculator(char, enemy_def=enemy_def)

    # Inject the main-slot companion as a synthetic SUMMON if there is one.
    # See game/companions.py SUMMON MECHANIC + game/skills.py
    # build_companion_summon_skill_data / DPSCalculator.register_companion_summon.
    main_companion_summon = stats.get('_main_companion_summon')
    if include_companion_summon and main_companion_summon is not None:
        from game.skills import build_companion_summon_skill_data
        from dataclasses import replace as _dc_replace
        advancement, comp_level = main_companion_summon
        primary_override = stats.get('_main_companion_primary_attack_override')
        companion_skill = build_companion_summon_skill_data(
            advancement, comp_level,
            primary_attack_override=primary_override,
        )
        if companion_skill is not None:
            # Apply +X% companion duration (shoes special, Glass Shoes artifact)
            # by extending the skill's duration before registering. The scheduler
            # then reads this longer window naturally; nothing downstream needs
            # to know about the stat.
            companion_duration_pct = stats.get('companion_duration', 0)
            if companion_duration_pct > 0:
                companion_skill = _dc_replace(
                    companion_skill,
                    duration=companion_skill.duration * (1 + companion_duration_pct / 100),
                )
            calc.register_companion_summon(companion_skill)
            # Companion self-buff FD (3rd/4th job auto-cast OnStart): baked
            # into the snapshot at cast time so all companion hits during
            # the 30s window benefit. Doesn't affect player damage.
            self_buff_fd = stats.get('_main_companion_self_buff_fd_decimal', 0.0)
            if self_buff_fd > 0:
                calc._companion_self_buff_fd_decimal = self_buff_fd
            # Bishop-style player buffs + secondary skill + proc. Empty/None
            # for non-Bishop companions today; the simulator only acts when
            # these are populated.
            calc._companion_player_bonuses = stats.get('_main_companion_player_bonuses', {})
            calc._companion_secondary_skills = stats.get('_main_companion_secondary_skills', [])
            calc._companion_proc_skill = stats.get('_main_companion_proc_skill', None)

    if use_realistic_dps:
        # Phase-aware simulation: proper boss/normal damage separation
        dps_result = calc.calculate_realistic_dps(
            fight_duration=fight_duration,
            num_enemies=num_enemies,
            mob_time_fraction=mob_time_fraction,
            boss_importance=boss_importance,
            boss_damage_multiplier=boss_damage_multiplier,
            log_actions=log_actions,
        )
    else:
        # Legacy calculation
        dps_result = calc.calculate_total_dps(
            fight_duration=fight_duration,
            num_enemies=num_enemies,
            mob_time_fraction=mob_time_fraction,
        )

    # Apply damage range multiplier (not handled by DPSCalculator)
    # Apply Hex Necklace multiplier. In LEGACY mode this is a time-averaged
    # post-multiplier baked at aggregation time. In REALISTIC mode the
    # simulator steps hex stacks live per damage event (see
    # DPSCalculator._hex_multiplier_at and the per-tick multiplication in
    # _simulate_fight) — EXCEPT when fight_duration is infinite (chapter
    # hunt), where calculate_realistic_dps falls back to calculate_total_dps
    # (the legacy steady-state path) which doesn't apply hex internally. In
    # that case we still need the post-multiplier.
    import math as _math
    simulator_applied_hex = use_realistic_dps and not _math.isinf(fight_duration)
    hex_mult = stats.get('hex_multiplier', 1.0) if not simulator_applied_hex else 1.0
    # Damage Amp (equipment scrolls) is its own multiplier: (1 + damage_amp/100).
    # Applied as a post-multiplier on the total DPS, separate from FD and damage_pct.
    damage_amp_mult = 1 + stats.get('damage_amp', 0.0) / 100
    final_total = dps_result.total_dps * dmg_range_mult * hex_mult * damage_amp_mult

    # Also calculate old-style result for breakdown display (single-target reference)
    secondary_stat_type = get_secondary_stat_name(job_class)
    secondary_flat_key = f'{secondary_stat_type}_flat'
    result = calculate_damage(
        base_atk=base_atk,
        dex_flat=main_stat_flat,
        dex_percent=main_stat_pct,
        dex_flat_conversion=stats.get('main_stat_conversion', 0),
        damage_percent=stats['damage_pct'],
        damage_amp=stats.get('damage_amp', 0),
        final_damage_sources=stats.get('final_damage_sources', []),
        crit_rate=crit_rate,
        crit_damage=total_crit_damage,
        defense_pen=total_defense_pen,
        enemy_def=enemy_def,
        boss_damage=stats['boss_damage'] if combat_mode in ('boss', 'world_boss') else 0,
        str_flat=stats.get(secondary_flat_key, 0),
    )

    atk_spd_mult = 1 + (total_attack_speed / 100)

    # Phase DPS (only meaningful for realistic DPS mode)
    # Apply display multiplier to boss phase for easier comparison
    mob_phase_dps = dps_result.mob_phase_dps * dmg_range_mult * hex_mult * damage_amp_mult
    boss_phase_dps = dps_result.boss_phase_dps * dmg_range_mult * hex_mult * damage_amp_mult
    boss_phase_dps_display = boss_phase_dps * boss_damage_multiplier

    return {
        'total': final_total,
        'defense_pen': total_defense_pen,
        'defense_pen_breakdown': def_pen_breakdown,
        'attack_speed': total_attack_speed,
        'attack_speed_breakdown': atk_spd_breakdown,
        'fd_mult': fd_mult,
        'hex_mult': hex_mult,
        # Multiplier breakdown for display (from single-target calc)
        'stat_mult': result.stat_mult,
        'damage_mult': result.damage_mult,
        'amp_mult': result.amp_mult,
        'crit_mult': result.crit_mult,
        'def_mult': result.def_mult,
        'range_mult': dmg_range_mult,
        'speed_mult': atk_spd_mult,
        'total_dex': result.total_dex,
        # Full DPS breakdown
        'basic_attack_dps': dps_result.basic_attack_dps * dmg_range_mult * hex_mult * damage_amp_mult,
        'active_skill_dps': dps_result.active_skill_dps * dmg_range_mult * hex_mult * damage_amp_mult,
        'summon_dps': dps_result.summon_dps * dmg_range_mult * hex_mult * damage_amp_mult,
        'proc_dps': dps_result.proc_dps * dmg_range_mult * hex_mult * damage_amp_mult,
        # Phase breakdown (realistic DPS only)
        'mob_phase_dps': mob_phase_dps,
        'boss_phase_dps': boss_phase_dps,
        'boss_phase_dps_display': boss_phase_dps_display,  # With user's display multiplier
        'boss_damage_multiplier': boss_damage_multiplier,
        # Fight simulation log (only populated when log_actions=True)
        'fight_log': dps_result.fight_log,
    }


# =============================================================================
# Fast-path DPS evaluation for the optimizer
# =============================================================================
#
# The realistic simulator is slow per candidate evaluation. Most optimizer
# candidates only change stats that multiply through the damage chain
# (attack, crit, damage %, FD, def pen, etc.) — those don't affect WHICH
# actions get cast, only the damage each action deals. For those candidates
# we can evaluate via the closed-form legacy path and scale the result by
# a one-time baseline ratio.
#
# A handful of stats DO change the action sequence (when buffs/summons fire,
# how long they stay up). Candidates touching those must re-run the sim.

# Keys are stat-dict names (what aggregate_stats populates) and the matching
# potential-name aliases (what some optimizer code paths key by). Either form
# triggers the sequence-aware re-sim.
SEQUENCE_AFFECTING_STAT_KEYS = frozenset({
    # Stats-dict keys (populated by aggregate_stats)
    'skill_cd_reduction',     # Hat special potential, hero power
    'buff_duration',          # Belt special potential, hero power, artifacts
    'companion_duration',     # Shoes special potential, Glass Shoes artifact
    # Potential-name aliases (used by some optimizer call sites)
    'skill_cd',
})


def is_sequence_affecting(stat_name: str) -> bool:
    """
    True iff a candidate touching `stat_name` requires re-running the
    realistic simulator. Everything else can use the legacy + ratio
    fast path in `FastDPSEvaluator.evaluate`.
    """
    return stat_name in SEQUENCE_AFFECTING_STAT_KEYS


class FastDPSEvaluator:
    """
    Optimizer helper that scales legacy-path candidate evaluations to
    match a realistic baseline. Reduces per-candidate cost from "run the
    full simulator" to "run the closed-form formula and multiply by a
    precomputed ratio" for candidates that don't change the action
    sequence.

    Usage:
        evaluator = FastDPSEvaluator(
            baseline_stats=current_stats,
            combat_mode=data.combat_mode,
            enemy_def=enemy_def,
            calculate_dps_fn=calculate_dps,
            extra_kwargs={'job_class': job_class, 'boss_importance': 0.7},
        )
        # For each candidate:
        candidate_dps = evaluator.evaluate(
            candidate_stats,
            changed_stat='damage_pct',   # non-sequence -> fast path
        )

    When `changed_stat` is sequence-affecting (or None / unknown), the
    evaluator runs the realistic simulator. Otherwise it runs the legacy
    path and multiplies by `baseline_realistic_dps / baseline_legacy_dps`.
    """

    def __init__(
        self,
        baseline_stats: Dict[str, Any],
        combat_mode: str,
        enemy_def: float,
        calculate_dps_fn,
        extra_kwargs: Optional[Dict[str, Any]] = None,
    ):
        self._calculate_dps = calculate_dps_fn
        self._combat_mode = combat_mode
        self._enemy_def = enemy_def
        self._extra_kwargs = dict(extra_kwargs or {})

        # Strip use_realistic_dps from extra kwargs — we control it.
        self._extra_kwargs.pop('use_realistic_dps', None)
        self._extra_kwargs.pop('log_actions', None)

        # Baseline realistic (with sim) — used as the anchor everything else
        # is scaled toward.
        self._baseline_realistic = self._calculate_dps(
            baseline_stats, combat_mode, enemy_def,
            use_realistic_dps=True, log_actions=False,
            **self._extra_kwargs,
        )
        # Baseline legacy (closed-form) — used to compute the scaling ratio.
        baseline_legacy = self._calculate_dps(
            baseline_stats, combat_mode, enemy_def,
            use_realistic_dps=False, log_actions=False,
            **self._extra_kwargs,
        )

        real_dps = self._baseline_realistic.get('total', 0.0)
        legacy_dps = baseline_legacy.get('total', 0.0)
        # Ratio of "what the realistic sim produces" to "what the legacy
        # formula produces" at the baseline. For non-sequence candidates the
        # legacy path scales identically with stat changes, so this ratio
        # transfers from baseline to candidate.
        self._ratio = (real_dps / legacy_dps) if legacy_dps > 0 else 1.0

    @property
    def baseline_realistic_dps(self) -> float:
        return self._baseline_realistic.get('total', 0.0)

    @property
    def ratio(self) -> float:
        """realistic / legacy DPS at the baseline. Public for diagnostics."""
        return self._ratio

    def evaluate(
        self,
        candidate_stats: Dict[str, Any],
        changed_stat: Optional[str] = None,
    ) -> float:
        """
        Predicted realistic-path DPS for `candidate_stats`.

        - `changed_stat`: hint about which stat differs from baseline. If
          sequence-affecting (or None/unknown), we re-run the realistic
          sim. Otherwise we run legacy and scale.
        """
        needs_sim = changed_stat is None or is_sequence_affecting(changed_stat)
        result = self._calculate_dps(
            candidate_stats, self._combat_mode, self._enemy_def,
            use_realistic_dps=needs_sim, log_actions=False,
            **self._extra_kwargs,
        )
        dps = result.get('total', 0.0)
        return dps if needs_sim else dps * self._ratio


# =============================================================================
# Stage Phase-Weighted DPS Helpers
# =============================================================================

# Stage fight: 60% mob clearing, 40% boss
STAGE_MOB_FRACTION = 0.6
STAGE_BOSS_FRACTION = 0.4


def compute_phase_dps(stats: Dict[str, Any], calc_dps_func, mode: str = 'stage') -> tuple:
    """
    Returns (mob_dps, boss_dps) for combat-mode-aware DPS scoring.

    - `'stage'`: returns true (mob_phase, boss_phase) for the 60/40 stage
       fight. In realistic mode, one stage call populates both via
       mob_phase_dps / boss_phase_dps. In legacy mode, two calls
       ('chapter_hunt' + 'boss').
    - `'boss'` / `'world_boss'`: pure boss fight — (0, boss_total).
    - `'chapter_hunt'`: pure mob — (mob_total, 0).
    - Anything else: falls back to the stage behavior.

    Critical for artifact / DPS-gain scoring: callers in pure boss mode
    should NOT get stage-weighted (60/40) numbers. Before this argument
    existed, artifact rankings used stage weights regardless of the user's
    combat mode, so boss-only builds saw skewed scores.

    calc_dps_func signature: (stats, mode_str) -> Dict[str, Any] or float
    """
    def _total(r):
        return r.get('total', r) if isinstance(r, dict) else r

    if mode in ('boss', 'world_boss'):
        return (0.0, _total(calc_dps_func(stats, mode)))
    if mode == 'chapter_hunt':
        return (_total(calc_dps_func(stats, mode)), 0.0)

    # Default = stage phase split.
    stage_result = calc_dps_func(stats, 'stage')
    if isinstance(stage_result, dict):
        mob_phase = stage_result.get('mob_phase_dps', 0)
        boss_phase = stage_result.get('boss_phase_dps', 0)
        if mob_phase > 0 and boss_phase > 0:
            return mob_phase, boss_phase  # Realistic mode: already separated

    # Legacy mode: need separate calls per phase
    return (
        _total(calc_dps_func(stats, 'chapter_hunt')),
        _total(calc_dps_func(stats, 'boss')),
    )


def stage_weighted_gain_pct(
    mob_b: float, boss_b: float, mob_t: float, boss_t: float,
    mode: str = 'stage',
) -> float:
    """
    Combat-mode-aware DPS gain percentage:
    - 'stage': mob_gain × 0.6 + boss_gain × 0.4
    - 'boss' / 'world_boss': boss_gain (mob component is 0 by construction)
    - 'chapter_hunt': mob_gain
    """
    mob_gain = (mob_t / mob_b - 1) if mob_b > 0 else 0.0
    boss_gain = (boss_t / boss_b - 1) if boss_b > 0 else 0.0
    if mode in ('boss', 'world_boss'):
        return boss_gain * 100
    if mode == 'chapter_hunt':
        return mob_gain * 100
    return (mob_gain * STAGE_MOB_FRACTION + boss_gain * STAGE_BOSS_FRACTION) * 100


def compute_stage_weighted_gain_pct(
    current_stats: Dict[str, Any],
    test_stats: Dict[str, Any],
    calc_dps_func,
    mode: str = 'stage',
) -> float:
    """
    DPS gain % evaluated against the user's combat mode. The name is kept
    for backward compatibility, but the function now respects `mode`:
    boss / world_boss → pure boss gain, chapter_hunt → pure mob gain,
    anything else → 60/40 stage weighting.
    """
    mob_b, boss_b = compute_phase_dps(current_stats, calc_dps_func, mode)
    mob_t, boss_t = compute_phase_dps(test_stats, calc_dps_func, mode)
    return stage_weighted_gain_pct(mob_b, boss_b, mob_t, boss_t, mode)
