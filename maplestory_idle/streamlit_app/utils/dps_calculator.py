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
    calculate_hex_average_multiplier,
    ARTIFACTS,
    CombatScenario,
    EffectType,
)
from companions import COMPANIONS
from weapons import calculate_weapon_atk_str
from weapon_mastery import calculate_mastery_stages_from_weapons, calculate_mastery_stats
from skills import (
    calculate_all_skills_value, create_character_at_level, DPSCalculator,
    BOWMASTER_SKILLS, JobSkillBonus, create_character_with_job_bonuses,
    calculate_job_skill_value, Job,
)
from cubes import CombatMode, COMBAT_SCENARIO_PARAMS
from utils.data_manager import EQUIPMENT_SLOTS
from job_classes import JobClass, get_job_stats, get_main_stat_name, get_secondary_stat_name
from stat_names import (
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
    job_class_str = getattr(user_data, 'job_class', 'bowmaster')
    try:
        job_class = JobClass(job_class_str)
    except ValueError:
        job_class = JobClass.BOWMASTER
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
        'all_skills': 0,
        'skill_cd': 0,
        'buff_duration': 0,
        'skill_1st': 0,
        'skill_2nd': 0,
        'skill_3rd': 0,
        'skill_4th': 0,
        # Utility stats
        'accuracy': 0,
        'ba_targets': 0,
        'basic_attack_damage': 0,
        # Character info
        'character_level': user_data.character_level,
        # Multiplicative stats - stored as lists for stacking calculation
        'def_pen_sources': [],       # List of (source_name, value, priority) tuples
        'final_damage_sources': [],  # List of decimal values (e.g., 0.10 for 10%)
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

    # Get combat scenario parameters
    combat_mode_enum = get_combat_mode_enum(user_data.combat_mode)
    scenario_params = COMBAT_SCENARIO_PARAMS.get(combat_mode_enum, COMBAT_SCENARIO_PARAMS[CombatMode.STAGE])
    num_enemies = scenario_params.num_enemies
    mob_time_fraction = scenario_params.mob_time_fraction

    # NOTE: BA% calculation moved to PASS 4 (after ba_targets are collected from potentials)

    # Job-specific skill level DPS values
    job_skill_dps_values = get_job_skill_dps_values(
        user_data.character_level, user_data.all_skills, effective_base_attack, effective_crit_damage
    )

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

        # Handle stats with DPS conversion side effects
        if stat_name == 'all_skills':
            stats['all_skills'] += value
            fd_from_all_skills = value * all_skills_to_dps
            if fd_from_all_skills > 0:
                stats['final_damage_sources'].append(fd_from_all_skills / 100)
            return
        if stat_name == 'skill_cd':
            stats['skill_cd'] += value
            cd_dps_gain = calculate_skill_cd_dps_value(
                user_data.character_level, user_data.all_skills, value
            )
            if cd_dps_gain > 0:
                stats['final_damage_sources'].append(cd_dps_gain / 100)
            return
        if stat_name == 'buff_duration':
            stats['buff_duration'] += value
            buff_dps_gain = calculate_buff_duration_dps_value(
                user_data.character_level, user_data.all_skills, value
            )
            if buff_dps_gain > 0:
                stats['final_damage_sources'].append(buff_dps_gain / 100)
            return

        # Stat name aliases - map potential stat names to stats dict keys
        stat_aliases = {
            'damage': 'damage_pct',  # Potentials use 'damage', stats dict uses 'damage_pct'
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

    # Equipment base stats with starforce amplification
    for slot in EQUIPMENT_SLOTS:
        item = user_data.equipment_items.get(slot, {})
        stars = star_overrides.get(slot, int(item.get('stars', 0)))
        main_mult = get_amplify_multiplier(stars, is_sub=False)
        sub_mult = get_amplify_multiplier(stars, is_sub=True)

        stats['attack_flat'] += item.get('base_attack', 0) * main_mult
        stats['attack_flat'] += item.get('sub_attack_flat', 0) * sub_mult
        stats['crit_damage'] += item.get('sub_crit_damage', 0) * sub_mult
        stats['crit_rate'] += item.get('sub_crit_rate', 0) * sub_mult
        stats['boss_damage'] += item.get('sub_boss_damage', 0) * sub_mult
        stats['normal_damage'] += item.get('sub_normal_damage', 0) * sub_mult

        # Handle special stats based on special_stat_type field
        if item.get('is_special', False):
            special_type = item.get('special_stat_type', 'damage_pct')
            special_value = item.get('special_stat_value', 0) * sub_mult

            if special_type == 'damage_pct' and special_value > 0:
                stats['damage_pct'] += special_value
            elif special_type == 'final_damage' and special_value > 0:
                stats['final_damage_sources'].append(special_value / 100)
            elif special_type == 'all_skills' and special_value > 0:
                fd_from_as = special_value * all_skills_to_dps
                if fd_from_as > 0:
                    stats['final_damage_sources'].append(fd_from_as / 100)

        # Job-specific skill level bonuses (sub_skill_1st, sub_skill_2nd, etc.)
        # These boost specific job skills and are amplified by starforce
        # Accumulate for passing to DPSCalculator
        stats['skill_1st'] += item.get('sub_skill_1st', 0) * sub_mult
        stats['skill_2nd'] += item.get('sub_skill_2nd', 0) * sub_mult
        stats['skill_3rd'] += item.get('sub_skill_3rd', 0) * sub_mult
        stats['skill_4th'] += item.get('sub_skill_4th', 0) * sub_mult

    # Hero Power lines
    for line_key, line in user_data.hero_power_lines.items():
        stat = line.get('stat', '')
        value = float(line.get('value', 0))
        _add_stat(stat, value, f'hero_power_{line_key}')

    # Hero Power passives
    passives = user_data.hero_power_passives
    stats[main_flat_key] += passives.get('main_stat', 0) * 100
    stats['damage_pct'] += passives.get('damage', 0) * 2

    # Maple Rank
    mr = user_data.maple_rank
    stage = mr.get('current_stage', 1)
    ms_level = mr.get('main_stat_level', 0)
    special = mr.get('special_main_stat', 0)
    stats[main_flat_key] += (stage - 1) * 100 + ms_level * 10 + special

    stat_levels = mr.get('stat_levels', {})
    if isinstance(stat_levels, dict):
        atk_spd = stat_levels.get('attack_speed', 0) * 0.5
        if atk_spd > 0:
            stats['attack_speed_sources'].append(('MapleRank', atk_spd))
        stats['crit_rate'] += stat_levels.get('crit_rate', 0) * 1
        stats['damage_pct'] += stat_levels.get('damage', 0) * 2
        stats['boss_damage'] += stat_levels.get('boss_damage', 0) * 2
        stats['normal_damage'] += stat_levels.get('normal_damage', 0) * 2
        stats['crit_damage'] += stat_levels.get('crit_damage', 0) * 2
        stats['skill_damage'] += stat_levels.get('skill_damage', 0) * 2

    # Equipment sets
    stats[main_flat_key] += user_data.equipment_sets.get('medal', 0)
    stats[main_flat_key] += user_data.equipment_sets.get('costume', 0)

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
        stats['attack_pct'] += total_weapon_atk_pct

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
        for slot_key in ['slot0', 'slot1', 'slot2']:
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

            # Check if artifact's active effect applies to current scenario
            if not defn.applies_to_scenario(scenario):
                continue  # Skip this artifact's active effect

            # Get uptime for this artifact
            fight_duration = scenario_params.fight_duration
            uptime = defn.get_effective_uptime(fight_duration)

            # All artifacts now use active_effects format
            if not defn.active_effects:
                continue

            for effect in defn.active_effects:
                effect_value = effect.get_value(stars) * uptime

                if effect.effect_type == EffectType.DERIVED and effect.derived_from:
                    # Derived effects (e.g., Book of Ancient CD from CR)
                    source_stat = effect.derived_from
                    if source_stat == 'crit_rate':
                        source_value = stats.get('crit_rate', 0) / 100
                    elif source_stat == 'attack_speed':
                        # For Athena Pierce's Gloves: max_dmg from attack speed
                        # Calculate total attack speed from all sources (attack_speed_sources is a list of tuples)
                        total_atk_spd, _ = calculate_effective_attack_speed_with_sources(
                            stats.get('attack_speed_sources', [])
                        )
                        source_value = total_atk_spd / 100  # Convert from percentage to decimal
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
                # Utility stats (no DPS impact) - silently skip
                elif stat in ('buff_duration', 'hp_recovery', 'hp_mp_recovery',
                              'companion_duration', 'cooldown_reduction', 'utility'):
                    pass

    # Artifact inventory effects (passive bonuses from all owned artifacts)
    # Note: artifacts_inventory already loaded above for Book of Ancient stars
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
                # Note: Utility stats like defense, debuff_tolerance, evasion,
                # damage_taken_decrease are not DPS stats and are skipped

            # Artifact potentials
            potentials = art_data.get('potentials', [])
            if isinstance(potentials, list):
                for pot in potentials:
                    if isinstance(pot, dict):
                        pot_stat = pot.get('stat', '')
                        pot_value = float(pot.get('value', 0) or 0)
                        if pot_value > 0:
                            if pot_stat == 'main_stat':
                                stats[main_pct_key] += pot_value
                            elif pot_stat == 'damage':
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
                            elif pot_stat == 'min_max_damage':
                                stats['min_dmg_mult'] += pot_value
                                stats['max_dmg_mult'] += pot_value

    # Artifact Resonance stats (flat main stat and max HP from resonance level)
    artifacts_resonance = getattr(user_data, 'artifacts_resonance', {}) or {}
    if artifacts_resonance:
        resonance_level = int(artifacts_resonance.get('resonance_level', 0))
        if resonance_level > 0:
            from artifacts import calculate_resonance_main_stat, calculate_resonance_hp
            # Flat main stat from resonance
            resonance_main = calculate_resonance_main_stat(resonance_level)
            stats[main_flat_key] += resonance_main
            # Max HP from resonance (not a DPS stat but tracked for reference)
            # resonance_hp = calculate_resonance_hp(resonance_level)

    # =========================================================================
    # PASS 3: Apply Manual Adjustments (if enabled)
    # =========================================================================
    # Manual adjustments from Character Stats page help account for
    # stats from sources we don't track (passive skills, buffs, etc.)
    if apply_adjustments:
        manual_adj = getattr(user_data, 'manual_adjustments', {}) or {}
        if manual_adj:
            # Map adjustment keys to standardized stat keys
            # Manual adjustment uses main_flat_key/main_pct_key for job-specific main stat
            adjustment_mapping = {
                'main_stat_flat': main_flat_key,
                'main_stat_pct': main_pct_key,
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

            # final_damage adjustment - add as additional source
            fd_adj = manual_adj.get('final_damage', 0)
            if fd_adj != 0:
                stats['final_damage_sources'].append(fd_adj / 100)

            # total_main_stat and total_attack adjustments need special handling
            # They are derived stats, so we track adjustment separately
            # These will be applied in calculate_dps
            stats['total_main_stat_adjustment'] = manual_adj.get('total_main_stat', 0)
            stats['total_attack_adjustment'] = manual_adj.get('total_attack', 0)

    # =========================================================================
    # PASS 4: Convert skill_damage and basic_attack_damage to Final Damage
    # =========================================================================
    # Skill Damage % applies to all skills EXCEPT basic attacks
    # Basic Attack Damage % applies only to basic attacks (e.g., Sayram's Necklace)
    # Convert to FD weighted by the portion of DPS they affect:
    #   skill_damage FD = skill_damage * (1 - BA%)
    #   basic_attack_damage FD = basic_attack_damage * BA%

    # Calculate BA% of DPS now that ba_targets has been collected from potentials
    ba_target_bonus = int(stats.get('ba_targets', 0))
    ba_dps_pct = calculate_ba_percent_of_dps(
        user_data.character_level, user_data.all_skills, effective_base_attack, effective_crit_damage,
        num_enemies=num_enemies,
        mob_time_fraction=mob_time_fraction,
        ba_target_bonus=ba_target_bonus,
    )

    skill_damage = stats.get('skill_damage', 0)
    basic_attack_damage = stats.get('basic_attack_damage', 0)

    if skill_damage > 0 or basic_attack_damage > 0:
        ba_fraction = ba_dps_pct / 100  # Convert to decimal (e.g., 0.40 = 40%)

        if skill_damage > 0:
            # Skill damage affects (1 - BA%) of total DPS
            skill_fd_contribution = skill_damage * (1 - ba_fraction)
            if skill_fd_contribution > 0:
                stats['final_damage_sources'].append(skill_fd_contribution / 100)

        if basic_attack_damage > 0:
            # Basic attack damage affects BA% of total DPS
            ba_fd_contribution = basic_attack_damage * ba_fraction
            if ba_fd_contribution > 0:
                stats['final_damage_sources'].append(ba_fd_contribution / 100)

    return stats


def calculate_dps(stats: Dict[str, Any], combat_mode: str = 'stage', enemy_def: float = 0.752,
                   job_class: JobClass = None, use_realistic_dps: bool = False,
                   boss_importance: float = 0.7, log_actions: bool = False) -> Dict[str, Any]:
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

    Returns:
        Dict with 'total' DPS and component multipliers
    """
    from skills import CharacterState

    # Get job class for stat key lookup
    if job_class is None:
        job_class = JobClass.BOWMASTER
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

    # Main stat calculation (with manual adjustment if present)
    main_stat_flat = stats.get(main_flat_key, 0)
    main_stat_pct = stats.get(main_pct_key, 0)
    total_main_stat = calculate_total_dex(main_stat_flat, main_stat_pct)
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
    level = stats.get('character_level', 140)
    all_skills = int(stats.get('all_skills', 0))

    char = create_character_at_level(level, all_skills)
    char.attack = base_atk
    char.main_stat_flat = main_stat_flat
    char.main_stat_pct = main_stat_pct

    if use_realistic_dps:
        # Realistic DPS: pass raw stats, simulation handles phase weighting
        char.damage_pct = stats['damage_pct']
        char.boss_damage_pct = stats['boss_damage']
        char.normal_damage_pct = stats['normal_damage']
    else:
        # Legacy behavior: pre-weight boss/normal damage into damage_pct
        char.damage_pct = stats['damage_pct'] + stats['normal_damage'] * mob_time_fraction + stats['boss_damage'] * (1 - mob_time_fraction)
        char.boss_damage_pct = stats['boss_damage']
        char.normal_damage_pct = 0  # Not used in legacy mode

    char.crit_rate = crit_rate
    char.crit_damage = total_crit_damage
    char.min_dmg_mult = stats['min_dmg_mult']
    char.max_dmg_mult = stats['max_dmg_mult']
    char.skill_damage_pct = stats.get('skill_damage', 0)
    char.basic_attack_dmg_pct = stats.get('basic_attack_damage', 0)
    char.final_damage_pct = (fd_mult - 1) * 100  # Convert multiplier to percentage
    char.defense_pen = total_defense_pen * 100  # Convert decimal to percentage (skills.py expects %)
    char.attack_speed_pct = total_attack_speed
    char.ba_target_bonus = int(stats.get('ba_targets', 0))
    char.skill_cd_reduction = stats.get('skill_cd', 0)

    # Job-specific skill level bonuses from equipment
    char.skill_1st_bonus = int(stats.get('skill_1st', 0))
    char.skill_2nd_bonus = int(stats.get('skill_2nd', 0))
    char.skill_3rd_bonus = int(stats.get('skill_3rd', 0))
    char.skill_4th_bonus = int(stats.get('skill_4th', 0))

    # Calculate DPS using full skill rotation model
    calc = DPSCalculator(char, enemy_def=enemy_def)

    if use_realistic_dps:
        # Phase-aware simulation: proper boss/normal damage separation
        dps_result = calc.calculate_realistic_dps(
            fight_duration=fight_duration,
            num_enemies=num_enemies,
            mob_time_fraction=mob_time_fraction,
            boss_importance=boss_importance,
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
    # Apply Hex Necklace multiplier (calculated during aggregation, varies by scenario)
    hex_mult = stats.get('hex_multiplier', 1.0)
    final_total = dps_result.total_dps * dmg_range_mult * hex_mult

    # Also calculate old-style result for breakdown display (single-target reference)
    secondary_stat_type = get_secondary_stat_name(job_class)
    secondary_flat_key = f'{secondary_stat_type}_flat'
    result = calculate_damage(
        base_atk=base_atk,
        dex_flat=main_stat_flat,
        dex_percent=main_stat_pct,
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
        'basic_attack_dps': dps_result.basic_attack_dps * dmg_range_mult * hex_mult,
        'active_skill_dps': dps_result.active_skill_dps * dmg_range_mult * hex_mult,
        'summon_dps': dps_result.summon_dps * dmg_range_mult * hex_mult,
        'proc_dps': dps_result.proc_dps * dmg_range_mult * hex_mult,
        # Fight simulation log (only populated when log_actions=True)
        'fight_log': dps_result.fight_log,
    }
