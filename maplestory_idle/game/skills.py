"""
MapleStory Idle - Skill System and DPS Calculator

This module models:
- Bowmaster skills with level scaling
- Mastery system with unlock levels and bonuses
- Character level progression
- DPS rotation simulation with cooldowns
- Attack speed effects on cast times
- Passive/proc damage contributions
- True value calculation for +All Skills
"""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING
import functools
import json
import math
import os

from game.job_classes import JobClass

if TYPE_CHECKING:
    # Forward reference for build_companion_summon_skill_data; the runtime
    # import is local inside the function to avoid a circular import with
    # game.companions.
    from game.companions import JobAdvancement


# =============================================================================
# DATAMINE: Skill Level Factor Table (multiplicative scaling)
# =============================================================================

def _load_skill_level_factors() -> dict:
    """Load SkillLevelFactorTable.json into {level: [factor0..factor23]} dict.

    Skills scale multiplicatively: damage = base_damage * factor[level][index] / 1000
    At level 1, all factors = 1000 (i.e., 100% of base damage).
    """
    path = os.path.join(os.path.dirname(__file__), "..", "data_mine", "TextAsset", "SkillLevelFactorTable.json")
    with open(path) as f:
        data = json.load(f)
    return {int(entry["Level"]): [int(x) for x in entry["Factor"]] for entry in data}

SKILL_LEVEL_FACTORS: dict = _load_skill_level_factors()


class SkillGrowth(IntEnum):
    """Factor table column indices for skill_bonuses scaling.

    Each value is a column in SkillLevelFactorTable.json.
    Formula: value = int(base * factor_table[skill_level][index] / 1000 * 10) / 10

    The INC_X name describes how much the factor grows per skill level, which is
    equivalent to the stat gaining base × X/1000 per skill level.
    Example: INC3 on a 15% base stat → +0.045% per level → 22.0% at skill level 156.
    """
    FLAT  = 11  # Grows slowly (~+1/level at higher levels) — nimble_feet, beginner buffs
    INC3  = 22  # +3/level  — standard passive stat (most skills)
    INC4  = 21  # +4/level  — into_darkness, sharp_eyes, agile mastery skills
    INC5  = 12  # +5/level  — I/L mage skills, some 2nd-job actives
    INC10 = 13  # +10/level — soul_arrow dex, NL haste
    INC20 = 15  # +20/level
    INC25 = 16  # +25/level — NL maple_hero (approx)
    INC30 = 17  # +30/level — NL maple_hero (approx)
    INC40 = 19  # +40/level
    INC50 = 23  # +50/level L1-L120, then +10/level L121+ — validated vs maple_hero at L158


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class SkillType(Enum):
    BASIC_ATTACK = "basic_attack"      # Arrow Stream - uses Basic Attack Damage %
    ACTIVE = "active"                   # Hurricane, Covering Fire - uses Skill Damage %
    SUMMON = "summon"                   # Phoenix, Arrow Platter - independent attackers
    PASSIVE_PROC = "passive_proc"       # Final Attack, Flash Mirage - proc on attacks
    PASSIVE_BUFF = "passive_buff"       # Mortal Blow, Concentration - conditional buffs
    BUFF = "buff"                       # Sharp Eyes - active buff
    PASSIVE_STAT = "passive_stat"       # Skills that give flat stat bonuses
    SKILL_ENHANCER = "skill_enhancer"   # Skills that enhance other skills (e.g., Enchanted Quiver)


class DamageType(Enum):
    BASIC = "basic"      # Scales with Basic Attack Damage %
    SKILL = "skill"      # Scales with Skill Damage %


class Job(Enum):
    BASIC = 0    # Basic skills (unaffected by +All Skills)
    FIRST = 1    # Level 10-29
    SECOND = 2   # Level 30-59
    THIRD = 3    # Level 60-99 (skill points 60-99)
    FOURTH = 4   # Level 100+ (skill points 100+)


# Job advancement levels
JOB_LEVEL_RANGES = {
    Job.BASIC: (1, 9),    # Basic skills don't scale with level
    Job.FIRST: (10, 29),  # 20 levels × 3 = 60 skill points
    Job.SECOND: (30, 59),
    Job.THIRD: (60, 99),
    Job.FOURTH: (100, 999),
}


def get_job_for_level(level: int) -> Job:
    """Get the job advancement for a given character level."""
    if level < 30:
        return Job.FIRST
    elif level < 60:
        return Job.SECOND
    elif level < 100:
        return Job.THIRD
    else:
        return Job.FOURTH


def get_skill_points_for_job(level: int, job: Job) -> int:
    """
    Calculate total skill points available for a job at given level.
    You get 3 skill points per level in that job's range.
    """
    level = min(level, 140)  # Character level caps at 140 for skill point gain [See 431.3]
    min_level, max_level = JOB_LEVEL_RANGES[job]
    current_job = get_job_for_level(level)

    if current_job.value < job.value:
        # Haven't reached this job yet
        return 0
    elif current_job.value > job.value:
        # Completed this job, max points
        levels_in_job = max_level - min_level + 1
        return levels_in_job * 3
    else:
        # Currently in this job
        levels_completed = level - min_level
        return levels_completed * 3


def calculate_effective_cooldown(
    base_cooldown: float,
    percent_reduction: float = 0,
    flat_reduction: float = 0,
) -> float:
    """
    Calculate effective cooldown with Skill CD Reduction mechanic.

    The mechanic works as follows:
    1. Apply percentage reduction first (capped at 100%)
    2. Split flat reduction into sources of 2s each (remainder as a final source)
    3. Apply each source sequentially:
       - If the source would push cooldown below 7s, that source loses 0.5s effectiveness
    4. Minimum cooldown is 4 seconds

    Example: Meso Explosion (11s base), 6s flat reduction = 3 sources of 2s:
      11 -> 9 (full) -> 7 (full) -> 5.5 (below 7: 2s - 0.5 = 1.5s effective)

    Args:
        base_cooldown: Original skill cooldown in seconds
        percent_reduction: Percentage reduction (0-100)
        flat_reduction: Flat seconds reduction (e.g., 6.0 from hat potential)

    Returns:
        Final cooldown in seconds (minimum 4.0)
    """
    # Step 1: Apply percentage reduction (capped at 100%)
    pct = min(percent_reduction, 100) / 100
    cd = base_cooldown * (1 - pct)

    if flat_reduction <= 0:
        return max(cd, 4.0)

    # Step 2: Split flat reduction into sources of 2s each + remainder
    full_sources = int(flat_reduction // 2)
    remainder = flat_reduction % 2
    sources = [2.0] * full_sources
    if remainder > 0:
        sources.append(remainder)

    # Step 3: Apply each source with per-source diminishing returns
    for source in sources:
        if cd - source < 7:
            # This source would push below 7: loses 0.5s effectiveness
            cd -= (source - 0.5)
        else:
            cd -= source
        if cd <= 4.0:
            return 4.0

    return max(cd, 4.0)


# =============================================================================
# SKILL DEFINITIONS
# =============================================================================

@dataclass
class SkillData:
    """Definition of a skill with its scaling."""
    name: str
    skill_type: SkillType
    damage_type: DamageType
    job: Job
    unlock_level: int               # Character level required to unlock

    # Base values at Level 1 (from wiki)
    base_damage_pct: float = 0      # Damage % per hit at level 1
    base_hits: int = 1              # Number of hits
    base_targets: int = 1           # Max targets

    # Per-level scaling
    damage_per_level: float = 0     # Fallback additive scaling (used when level_factor_index < 0)
    level_factor_index: int = -1    # Index into SKILL_LEVEL_FACTORS for multiplicative scaling (-1 = use damage_per_level)

    # Cooldown (0 = no cooldown, can spam)
    cooldown: float = 0             # Seconds
    duration: float = 0             # For summons/buffs: how long they last

    # Special mechanics
    proc_chance: float = 1.0        # For procs: activation chance
    attack_interval: float = 0      # For summons: time between attacks
    scales_with_attack_speed: bool = True  # Does AS affect this skill?
    max_as_interval_reduction: float = 0.0  # Flat cap (seconds): interval -= cap * (as_mult-1); 0 = use multiplicative mode
    cast_time: float = 1.0          # Base cast time in seconds (from datamine frames / 30 FPS)

    # For skills that grant bonuses to other skills (e.g., Maple Hero), or stat bonuses
    # Dict mapping stat_or_skill_name -> (base_value, factor_index)
    # Formula: int(base * factor_table[level][factor_index] / 1000 * 10) / 10
    skill_bonuses: Optional[Dict[str, Tuple[float, int]]] = None

    # For skills that grant target bonuses to other skills (e.g., Flash Mirage II)
    # Dict mapping skill_name -> (base_targets, per_level)
    # Formula: floor(base + per_level * level)
    skill_target_bonuses: Optional[Dict[str, Tuple[float, float]]] = None

    # Scenario when this skill's bonuses apply
    # "all" = always applies (default)
    # "boss" = only applies in single-target/boss scenarios
    # "mob" = only applies in multi-target/mob scenarios
    scenario: str = "all"

    # Innate normal monster damage bonus (part of the skill, not a mastery)
    # e.g., Arrow Platter: "deals 200% additional Normal Monster Damage"
    innate_normal_monster_damage: float = 0

    # Stat conversion: converts a percentage of one stat into another
    # e.g., Shield Mastery: LUK = 10% of Defense
    # Format: (source_stat, target_stat, (base_rate_pct, per_level_rate_pct))
    # source_stat: "defense" -> total defense (flat * (1 + pct/100))
    # target_stat: "main_stat_flat" -> job's main stat
    stat_conversion: Optional[Tuple[str, str, Tuple[float, float]]] = None

    # Stack-based skills (e.g., Meso Explosion)
    # Stacks accumulate as decimal (targets * proc_chance per atk), int() only at consumption
    max_stacks: int = 0                           # Max stack count (0 = not stack-based)
    stack_source: Optional[str] = None            # Chain generation off another skill's stacks
    single_target_stack_bonus: float = 0          # Per-stack final dmg bonus in boss (e.g., 0.05 = +5%)

    # Skill proc chance modification (e.g., Meso Mastery -> Meso Explosion)
    # Maps target_skill_name -> (base_modifier_pct_points, per_level_modifier)
    proc_chance_modifier: Optional[Dict[str, Tuple[float, float]]] = None

    # Finishing blow: extra damage line every N uses (e.g., Assassinate)
    finishing_blow_pct: float = 0          # Extra damage % of the finishing blow
    finishing_blow_interval: int = 0       # Every N uses (0 = disabled)
    finishing_blow_factor_index: int = -1  # Factor index for finishing blow scaling (if different from main)
    finishing_blow_unlock_level: int = 0   # Mastery level to unlock FB (0 = always active)
    finishing_blow_boss_only: bool = False  # If True, FB only contributes to boss DPS

    # DoT component (e.g., Sudden Raid continuous damage)
    dot_damage_pct: float = 0             # Damage % per DoT tick
    dot_duration: float = 0               # Total DoT duration in seconds
    dot_interval: float = 1.0             # Time between ticks (default 1s)

    # Buff downtime after proc trigger (e.g., Shadow Shifter loses attack buff for 4s)
    buff_downtime: float = 0              # Seconds of buff downtime per trigger cycle

    # Sharp Eyes-style: adds X% of own crit_damage as bonus crit_damage while active
    self_crit_damage_pct: float = 0.0


# =============================================================================
# MASTERY DEFINITIONS
# =============================================================================

@dataclass
class MasteryNode:
    """A single mastery upgrade."""
    name: str
    unlock_level: int               # Character level required
    unlock_rd: int = 0              # Required RD (optional cost)

    # Effect type and value
    effect_type: str = ""           # What this mastery affects
    effect_target: str = ""         # Which skill it affects (or "all")
    effect_value: float = 0         # The bonus value

    # Description for display
    description: str = ""

    # Optional: For mastery effects that scale with another skill's level
    # Formula: effect_value * (1 + scale_per_level * skill_level)
    scale_with_skill: str = ""      # Skill name whose level scales this effect
    scale_per_level: float = 0.0    # Scaling factor per skill level


# =============================================================================
# MASTERY CATEGORIES
# =============================================================================
#
# Masteries are divided into two types:
# 1. GLOBAL STATS (effect_target="global") - Apply to character stats directly
#    Examples: +30 DEX, +5% Crit Rate, +15% Skill Damage
#
# 2. SKILL-SPECIFIC (effect_target=skill_name) - Only affect that one skill
#    Examples: Arrow Blow damage +15%, Phoenix targets +2
#
# Note: Some masteries like "Archer Mastery - Speed +5%p" boost a passive skill's
# contribution. We treat these as global stats that stack additively.
# =============================================================================

# Bowmaster Mastery Tree (from your data)
BOWMASTER_MASTERIES: List[MasteryNode] = [
    # =========================================================================
    # 1st Job Masteries (unlocked during levels 1-29)
    # =========================================================================

    # Skill-specific: Arrow Blow
    MasteryNode("Arrow Blow - Damage", 10, 0, "skill_damage_pct", "arrow_blow", 15, "Arrow Blow damage +15%"),
    MasteryNode("Arrow Blow - Target", 14, 0, "skill_targets", "arrow_blow", 1, "Arrow Blow max targets +1"),
    MasteryNode("Arrow Blow - Damage 2", 18, 0, "skill_damage_pct", "arrow_blow", 20, "Arrow Blow damage +20%"),
    MasteryNode("Arrow Blow - Target 2", 22, 0, "skill_targets", "arrow_blow", 1, "Arrow Blow max targets +1"),
    MasteryNode("Arrow Blow - Damage 3", 26, 0, "skill_damage_pct", "arrow_blow", 20, "Arrow Blow damage +20%"),

    # Global stats
    MasteryNode("Main Stat Enhancement", 12, 0, "main_stat_flat", "global", 30, "Main Stat +30"),
    MasteryNode("Critical Rate Enhancement", 16, 0, "crit_rate", "global", 5, "Critical Rate +5%"),
    MasteryNode("Archer Mastery - Speed", 20, 0, "attack_speed", "global", 5, "Attack Speed +5%"),
    MasteryNode("Critical Shot - Critical", 24, 0, "crit_rate", "global", 5, "Critical Rate +5%"),
    MasteryNode("Basic Attack Damage Enhancement", 28, 0, "basic_attack_damage", "global", 15, "Basic Attack Damage +15%"),

    # =========================================================================
    # 2nd Job Masteries (unlocked during levels 30-59)
    # =========================================================================

    # Skill-specific: Wind Arrow
    MasteryNode("Wind Arrow - Damage", 30, 0, "skill_damage_pct", "wind_arrow", 15, "Wind Arrow damage +15%"),
    MasteryNode("Wind Arrow - Target", 34, 0, "skill_targets", "wind_arrow", 1, "Wind Arrow max targets +1"),
    MasteryNode("Wind Arrow - Damage 2", 38, 0, "skill_damage_pct", "wind_arrow", 20, "Wind Arrow damage +20%"),
    MasteryNode("Wind Arrow - Boss Damage", 42, 0, "skill_boss_damage", "wind_arrow", 15, "Wind Arrow Boss Damage +15%"),
    MasteryNode("Wind Arrow - Damage 3", 46, 0, "skill_damage_pct", "wind_arrow", 20, "Wind Arrow damage +20%"),
    MasteryNode("Wind Arrow - Strike", 50, 0, "skill_hits", "wind_arrow", 1, "Wind Arrow hits +1"),

    # Skill-specific: Covering Fire
    MasteryNode("Covering Fire - Damage", 36, 0, "skill_damage_pct", "covering_fire", 50, "Covering Fire damage +50%"),
    MasteryNode("Covering Fire - Stun", 44, 0, "skill_effect", "covering_fire", 1, "Stuns target for 1 sec"),

    # Skill-specific: Quiver Cartridge
    MasteryNode("Quiver Cartridge - Damage", 40, 0, "skill_damage_pct", "quiver_cartridge", 50, "Quiver Cartridge damage +50%"),

    # Skill-specific: Final Attack
    MasteryNode("Final Attack - Damage", 48, 0, "skill_damage_pct", "final_attack", 50, "Final Attack damage +50%"),

    # Global stats
    MasteryNode("Accuracy Enhancement", 32, 0, "accuracy", "global", 5, "Accuracy +5"),
    MasteryNode("Max Damage Multiplier Enhancement", 52, 0, "max_dmg_mult", "global", 10, "Max Damage Multiplier +10%"),

    # =========================================================================
    # 3rd Job Masteries (unlocked during levels 60-99)
    # =========================================================================

    # Skill-specific: Wind Arrow II
    MasteryNode("Wind Arrow II - Damage", 60, 0, "skill_damage_pct", "wind_arrow_2", 10, "Wind Arrow II damage +10%"),
    MasteryNode("Wind Arrow II - Damage 2", 64, 0, "skill_damage_pct", "wind_arrow_2", 11, "Wind Arrow II damage +11%"),
    MasteryNode("Wind Arrow II - Boss Damage", 68, 0, "skill_boss_damage", "wind_arrow_2", 10, "Wind Arrow II Boss Damage +10%"),
    MasteryNode("Wind Arrow II - Damage 3", 72, 0, "skill_damage_pct", "wind_arrow_2", 12, "Wind Arrow II damage +12%"),
    MasteryNode("Wind Arrow II - Damage 4", 80, 4500, "skill_damage_pct", "wind_arrow_2", 13, "Wind Arrow II damage +13%"),
    MasteryNode("Wind Arrow II - Boss Damage 2", 84, 5000, "skill_boss_damage", "wind_arrow_2", 10, "Wind Arrow II Boss Damage +10%"),
    MasteryNode("Wind Arrow II - Damage 5", 88, 5500, "skill_damage_pct", "wind_arrow_2", 14, "Wind Arrow II damage +14%"),
    MasteryNode("Wind Arrow II - Damage 6", 92, 6000, "skill_damage_pct", "wind_arrow_2", 15, "Wind Arrow II damage +15%"),
    MasteryNode("Wind Arrow II - Strike", 96, 6500, "skill_hits", "wind_arrow_2", 1, "Wind Arrow II hits +1"),

    # Skill-specific: Flash Mirage
    MasteryNode("Flash Mirage - Damage", 66, 0, "skill_damage_pct", "flash_mirage", 50, "Flash Mirage damage +50%"),

    # Skill-specific: Arrow Platter
    MasteryNode("Arrow Platter - Damage", 70, 0, "skill_damage_pct", "arrow_platter", 50, "Arrow Platter damage +50%"),
    MasteryNode("Arrow Platter - Target", 98, 9750, "skill_targets", "arrow_platter", 2, "Arrow Platter max targets +2"),

    # Skill-specific: Phoenix
    MasteryNode("Phoenix - Target", 78, 0, "skill_targets", "phoenix", 3, "Phoenix max targets +3"),  # Patch: +2 → +3
    MasteryNode("Phoenix - Strike Interval", 82, 6750, "skill_attack_interval_pct", "phoenix", -30, "Phoenix strike interval -30%"),
    MasteryNode("Phoenix - Normal Monster Damage", 94, 9000, "skill_normal_monster_damage", "phoenix", 100, "Phoenix Normal Monster Damage +100%"),

    # Skill-specific: Mortal Blow
    MasteryNode("Mortal Blow - Persistence", 90, 8250, "skill_duration", "mortal_blow", 5, "Mortal Blow duration +5 sec"),

    # Global stats
    MasteryNode("Basic Attack Target Enhancement", 62, 0, "basic_attack_targets", "global", 1, "Basic Attack Target +1"),
    MasteryNode("Skill Damage Enhancement", 86, 7500, "skill_damage", "global", 15, "Skill Damage +15%"),

    # =========================================================================
    # 4th Job Masteries (unlocked at level 100+)
    # =========================================================================

    # Skill-specific: Arrow Stream
    MasteryNode("Arrow Stream - Damage", 102, 7000, "skill_damage_pct", "arrow_stream", 10, "Arrow Stream damage +10%"),
    MasteryNode("Arrow Stream - Damage 2", 106, 7500, "skill_damage_pct", "arrow_stream", 11, "Arrow Stream damage +11%"),
    MasteryNode("Arrow Stream - Boss Damage", 111, 8000, "skill_boss_damage", "arrow_stream", 10, "Arrow Stream Boss Damage +10%"),
    MasteryNode("Arrow Stream - Damage 3", 116, 8500, "skill_damage_pct", "arrow_stream", 12, "Arrow Stream damage +12%"),
    MasteryNode("Arrow Stream - Damage 4", 120, 9000, "skill_damage_pct", "arrow_stream", 13, "Arrow Stream damage +13%"),
    MasteryNode("Arrow Stream - Boss Damage 2", 124, 9500, "skill_boss_damage", "arrow_stream", 10, "Arrow Stream Boss Damage +10%"),
    MasteryNode("Arrow Stream - Damage 5", 128, 10000, "skill_damage_pct", "arrow_stream", 14, "Arrow Stream damage +14%"),
    MasteryNode("Arrow Stream - Damage 6", 132, 10500, "skill_damage_pct", "arrow_stream", 15, "Arrow Stream damage +15%"),
    MasteryNode("Arrow Stream - Strike", 136, 11000, "skill_hits", "arrow_stream", 1, "Arrow Stream hits +1"),

    # Skill-specific: Hurricane
    MasteryNode("Hurricane - Damage", 108, 11250, "skill_damage_pct", "hurricane", 50, "Hurricane damage +50%"),
    MasteryNode("Hurricane - Extend", 134, 15750, "skill_hits", "hurricane", 15, "Hurricane shots increased to 35"),

    # Skill-specific: Phoenix
    MasteryNode("Phoenix - Reuse", 104, 10500, "skill_cooldown_reduction", "phoenix", 0.5, "Phoenix cooldown -50%"),

    # Skill-specific: Final Attack
    MasteryNode("Advanced Final Attack - Enhance", 113, 12000, "skill_final_damage", "final_attack", 50, "Final Attack Final Damage +50%"),

    # Skill-specific: Flash Mirage
    MasteryNode("Flash Mirage II - Reuse", 122, 13500, "skill_cooldown_reduction", "flash_mirage", 0.4, "Flash Mirage cooldown -40%"),
    # Split the combined mastery into two separate effects so each is applied correctly
    MasteryNode("Flash Mirage II - Enhance", 138, 16500, "skill_final_damage", "flash_mirage", 50, "Flash Mirage II Final Damage +50%"),
    MasteryNode("Flash Mirage II - Target", 138, 0, "skill_targets", "flash_mirage", 3, "Flash Mirage targets +3"),

    # Skill-specific: Sharp Eyes
    MasteryNode("Sharp Eyes - Persistence", 126, 14250, "skill_duration", "sharp_eyes", 0.5, "Sharp Eyes duration +50%"),

    # Skill-specific: Illusion Step
    MasteryNode("Illusion Step - Enhance", 118, 12750, "skill_effect", "illusion_step", 2, "Attack increase effect doubled"),

    # Skill-specific: Enchanted Quiver
    # Drain mastery adds 1050% * (1 + 0.004 * EQ_level) additional damage to Quiver Cartridge
    MasteryNode(
        "Enchanted Quiver - Drain", 130, 15000,
        "skill_additional_damage", "quiver_cartridge", 1050,
        "Quiver Cartridge deals 1050% additional damage (scales +0.4%/EQ level)",
        scale_with_skill="enchanted_quiver", scale_per_level=0.004
    ),
]


def get_unlocked_masteries(
    level: int,
    masteries: Optional[List[MasteryNode]] = None,
) -> List[MasteryNode]:
    """Get all masteries unlocked at the given level."""
    if masteries is None:
        masteries = BOWMASTER_MASTERIES
    return [m for m in masteries if m.unlock_level <= level]


def get_mastery_bonuses(
    level: int,
    masteries: Optional[List[MasteryNode]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Calculate total mastery bonuses at a given level.

    Args:
        level: Character level
        masteries: List of mastery nodes (defaults to BOWMASTER_MASTERIES for backwards compat)

    Returns dict like:
    {
        "global": {"crit_rate": 10, "main_stat_flat": 30, "attack_speed": 5, ...},
        "arrow_stream": {"skill_damage_pct": 75, "skill_boss_damage": 20, ...},
        ...
    }

    "global" = stats that apply to your character directly
    skill_name = bonuses that only apply to that specific skill
    """
    bonuses: Dict[str, Dict[str, float]] = {"global": {}}

    for mastery in get_unlocked_masteries(level, masteries):
        target = mastery.effect_target
        effect = mastery.effect_type

        if target not in bonuses:
            bonuses[target] = {}

        if effect not in bonuses[target]:
            bonuses[target][effect] = 0

        bonuses[target][effect] += mastery.effect_value

    return bonuses


def get_global_mastery_stats(level: int) -> Dict[str, float]:
    """
    Get just the global character stats from masteries.

    Returns dict like:
    {
        "main_stat_flat": 30,
        "crit_rate": 10,
        "attack_speed": 5,
        "basic_attack_damage": 15,
        "max_dmg_mult": 10,
        "skill_damage": 15,
        ...
    }
    """
    bonuses = get_mastery_bonuses(level)
    return bonuses.get("global", {})


def get_level_breakpoints(
    job_class: 'JobClass',
    min_level: int = 10,
    max_level: int = 200,
) -> List[int]:
    """
    Get levels where skills or masteries unlock, causing potential rotation changes.

    These "breakpoints" are the levels where DPS calculation might change significantly.
    Between breakpoints, damage scales linearly with level (via passive stat gains),
    so we can interpolate without running full simulation.

    Args:
        job_class: The job class to check
        min_level: Minimum level to consider
        max_level: Maximum level to consider

    Returns:
        Sorted list of breakpoint levels within [min_level, max_level]
    """
    breakpoints = set()

    # Add boundary levels
    breakpoints.add(min_level)
    breakpoints.add(max_level)

    # Get masteries and skills for this job
    masteries = get_masteries_for_job(job_class)
    skills = get_skills_for_job(job_class)

    # Add mastery unlock levels
    for mastery in masteries:
        if min_level <= mastery.unlock_level <= max_level:
            breakpoints.add(mastery.unlock_level)

    # Add skill unlock levels
    for skill in skills.values():
        if min_level <= skill.unlock_level <= max_level:
            breakpoints.add(skill.unlock_level)

    return sorted(breakpoints)


# =============================================================================
# BOWMASTER SKILL DATABASE
# =============================================================================

BOWMASTER_SKILLS: Dict[str, SkillData] = {
    # ==========================================================================
    # 1st Job Skills
    # ==========================================================================
    "arrow_blow": SkillData(
        name="Arrow Blow",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FIRST,
        unlock_level=10,
        base_damage_pct=26.0,
        base_hits=2,
        base_targets=3,
        damage_per_level=0,  # Replaced by Wind Arrow
    ),

    "critical_shot": SkillData(
        name="Critical Shot",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=15,
        skill_bonuses={
            "crit_rate": (5.0, SkillGrowth.INC3),  # (6.5 - 5) / 103
        },
    ),

    "archer_mastery": SkillData(
        name="Archer Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=10,
        skill_bonuses={
            "attack_speed": (5.0, SkillGrowth.INC3),
        },
    ),

    "nimble_feet": SkillData(
        name="Nimble Feet",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.BASIC,  # Basic skill - unaffected by +All Skills
        unlock_level=1,
        cooldown=60.0,
        duration=15.0,
        skill_bonuses={
            "attack_speed": (15.0, SkillGrowth.FLAT),  # +15% attack speed while active
        },
    ),

    # ==========================================================================
    # 2nd Job Skills
    # ==========================================================================
    "wind_arrow": SkillData(
        name="Wind Arrow",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.SECOND,
        unlock_level=30,
        base_damage_pct=40.0,
        base_hits=3,
        base_targets=5,
        damage_per_level=0,  # Replaced by Wind Arrow II
    ),

    "covering_fire": SkillData(
        name="Covering Fire",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=35,
        base_damage_pct=250.0,
        base_hits=3,
        base_targets=1,
        damage_per_level=1.26,  # (437.5 - 250) / 149
        level_factor_index=12,  # Datamine: SkillIndex 72020
        cooldown=19.0,
    ),

    "quiver_cartridge": SkillData(
        name="Quiver Cartridge",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=40,
        base_damage_pct=22.0,
        base_hits=1,
        base_targets=1,
        damage_per_level=0.089,  # (35.2 - 22) / 149
        cooldown=999999,              # Permanent summon — always active
        duration=999999,
        attack_interval=1.0,
        cast_time=0,                     # No player action needed (always deployed)
        scales_with_attack_speed=True,
        max_as_interval_reduction=0.4,   # Patch: interval reduces by up to 0.4s (was ÷2× AS)
    ),

    "bow_acceleration": SkillData(
        name="Bow Acceleration",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=33,
        skill_bonuses={
            "attack_speed": (5.0, SkillGrowth.INC3),  # (7.2 - 5) / 149
        },
    ),

    "bow_mastery": SkillData(
        name="Bow Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=43,
        skill_bonuses={
            "min_dmg_mult": (15.0, SkillGrowth.INC3),  # (21.7 - 15) / 149
        },
    ),

    "soul_arrow": SkillData(
        name="Soul Arrow: Bow",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=45,
        skill_bonuses={
            "dex_flat": (50.0, SkillGrowth.INC10),  # Scales up to 300 with AS (was 150)
        },
    ),

    "final_attack": SkillData(
        name="Final Attack: Bow",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=50,
        base_damage_pct=35.0,
        base_hits=1,
        base_targets=1,
        damage_per_level=0.14,  # (56 - 35) / 149
        level_factor_index=21,  # Datamine: SkillIndex 72030
        proc_chance=0.25,
    ),

    "physical_training": SkillData(
        name="Physical Training",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=38,
        skill_bonuses={
            "basic_attack_damage": (10.0, SkillGrowth.INC3),  # (14.5 - 10) / 149
        },
    ),

    # ==========================================================================
    # 3rd Job Skills
    # ==========================================================================
    "wind_arrow_2": SkillData(
        name="Wind Arrow II",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.THIRD,
        unlock_level=60,
        base_damage_pct=80.0,
        base_hits=5,
        base_targets=6,
        damage_per_level=0,  # Replaced by Arrow Stream at 4th job
    ),

    "flash_mirage": SkillData(
        name="Flash Mirage",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=60,
        base_damage_pct=550.0,
        base_hits=1,
        base_targets=1,
        damage_per_level=2.21,  # (972.4 - 550) / 191
        level_factor_index=21,  # Datamine: SkillIndex 73020
        cooldown=5.0,
        proc_chance=0.20,
        scales_with_attack_speed=True,
    ),

    "phoenix": SkillData(
        name="Phoenix",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=69,
        base_damage_pct=600.0,
        base_hits=1,
        base_targets=5,  # Patch: max targets 3 → 5
        damage_per_level=3.02,  # (1176 - 600) / 191
        level_factor_index=12,  # Datamine: SkillIndex 73031
        cooldown=60.0,
        duration=20.0,
        attack_interval=3.0,
        cast_time=0.67,                  # 20 frames @ 30 FPS (datamine: Phoenix summon)
        scales_with_attack_speed=False,
    ),

    "arrow_platter": SkillData(
        name="Arrow Platter",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=63,
        base_damage_pct=50.0,
        base_hits=1,
        base_targets=1,
        damage_per_level=0.25,  # (98 - 50) / 191
        level_factor_index=12,  # Datamine: SkillIndex 73041
        cooldown=40.0,
        duration=60.0,
        attack_interval=0.3,
        cast_time=0.67,                  # 20 frames @ 30 FPS (datamine: ArrowPlatter summon)
        scales_with_attack_speed=False,
        innate_normal_monster_damage=200.0,  # "deals 200% additional Normal Monster Damage"
    ),

    "extreme_archery": SkillData(
        name="Extreme Archery: Bow",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=75,
        skill_bonuses={
            "final_damage": (15.0, SkillGrowth.INC3),  # (23.6 - 15) / 191
        },
    ),

    "mortal_blow": SkillData(
        name="Mortal Blow",
        skill_type=SkillType.PASSIVE_BUFF,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=72,
        # Buff with uptime - handled specially in calculate_hit_damage()
        skill_bonuses={
            "final_damage": (10.0, SkillGrowth.INC3),  # (15.7 - 10) / 191
        },
    ),

    "concentration": SkillData(
        name="Concentration",
        skill_type=SkillType.PASSIVE_BUFF,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=66,
        # Stacking buff (7 stacks max) - handled specially in calculate_hit_damage()
        skill_bonuses={
            "crit_damage": (3.0, SkillGrowth.INC3),  # Per stack, (4.7 - 3) / 191
        },
    ),

    "marksmanship": SkillData(
        name="Marksmanship",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=74,
        skill_bonuses={
            "attack_pct": (20.0, SkillGrowth.INC3),  # (31.5 - 20) / 191
        },
        scenario="boss",  # Only active in single-target (boss) scenarios
    ),

    # ==========================================================================
    # 4th Job Skills
    # ==========================================================================
    "arrow_stream": SkillData(
        name="Arrow Stream",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FOURTH,
        unlock_level=100,
        base_damage_pct=290.0,
        base_hits=5,
        base_targets=6,
        damage_per_level=1.19,  # (342.2 - 290) / 44
        level_factor_index=21,  # Datamine: SkillIndex 74010
    ),

    "hurricane": SkillData(
        name="Hurricane",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=103,
        base_damage_pct=800.0,
        base_hits=20,
        base_targets=7,  # Patch: AoE up to 7 enemies (was single-target)
        damage_per_level=4.09,  # (980 - 800) / 44
        level_factor_index=12,  # Datamine: SkillIndex 74020
        cooldown=40.0,
        attack_interval=0.248,  # Base seconds per arrow (~4 arrows/sec at 0% AS)
        # Tested: 20 arrows in 2.5s at 98.2% AS → base interval = 2.5 * 1.982 / 20 = 0.248
        scales_with_attack_speed=True,
    ),

    "sharp_eyes": SkillData(
        name="Sharp Eyes",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=115,
        cooldown=35.0,
        duration=18.0,  # Patch: 15s → 18s
        # Patch: crit_rate removed; self gets +40% crit damage + 20% of own crit damage
        # Allies get 20% of your crit damage (self included as allied player)
        skill_bonuses={
            "crit_damage": (40.0, SkillGrowth.INC4),
        },
        self_crit_damage_pct=20.0,  # +20% of own crit_damage while active
    ),

    "enchanted_quiver": SkillData(
        name="Enchanted Quiver",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=107,
        # Grants final damage to Quiver Cartridge
        # Formula: int((base + per_level * level) * 10) / 10
        # Level 0: 500%, Level 44: 588%
        skill_bonuses={
            "quiver_cartridge": (500.0, SkillGrowth.INC4),  # final_damage
        },
    ),

    "flash_mirage_2": SkillData(
        name="Flash Mirage II",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=110,
        # Grants final damage and targets to Flash Mirage
        # Formula: int((base + per_level * level) * 10) / 10
        # Level 0: 400%, Level 44: 466%
        skill_bonuses={
            "flash_mirage": (400.0, SkillGrowth.INC4),  # final_damage
        },
        skill_target_bonuses={
            "flash_mirage": (4, 0),  # +4 targets (flat, doesn't scale)
        },
    ),

    "illusion_step": SkillData(
        name="Illusion Step",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=117,
        duration=15.0,   # Attack phase duration
        cooldown=24.0,   # Patch: full cycle 15s attack + 9s evasion (was 20s = 15+5)
        # Attack phase: +X% Attack | Evasion phase: +20 Evasion, -X% damage taken
        skill_bonuses={
            "attack_pct": (14.0, SkillGrowth.INC5),  # Patch: 10% → 14%
        },
    ),

    "advanced_final_attack": SkillData(
        name="Advanced Final Attack",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=105,
        # Grants final damage to Final Attack: Bow
        # Formula: int((base + per_level * level) * 10) / 10
        # Level 0: 500%, Level 44: 588%
        skill_bonuses={
            "final_attack": (500.0, SkillGrowth.INC4),  # final_damage
        },
    ),

    "bow_expert": SkillData(
        name="Bow Expert",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=120,
        # Formula: int((base + per_level * level) * 10) / 10
        skill_bonuses={
            "skill_damage": (15.0, SkillGrowth.INC3),  # (17 - 15) / 44
        },
    ),

    "armor_break": SkillData(
        name="Armor Break",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=125,
        # Formula: int((base + per_level * level) * 10) / 10
        # Grants both defense penetration and final damage (same value)
        skill_bonuses={
            "defense_pen": (10.0, SkillGrowth.INC3),  # (11.3 - 10) / 44
            "final_damage": (10.0, SkillGrowth.INC3),
        },
    ),

    "maple_hero": SkillData(
        name="Maple Hero",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=100,
        # Grants FD to Arrow Platter, Phoenix, Covering Fire
        # Formula: int(base + per_level * level)
        # Level 0: AP 25%, Phoenix 30%, CF 100%
        # Level 20: AP 50%, Phoenix 60%, CF 200%
        # Level 44: AP 80%, Phoenix 96%, CF 320%
        skill_bonuses={
            "arrow_platter": (25, SkillGrowth.INC50),   # (base, per_level) -> final_damage
            "phoenix": (30, SkillGrowth.INC50),
            "covering_fire": (100, SkillGrowth.INC50),
        },
    ),
}


# =============================================================================
# ICE/LIGHTNING MAGE SKILLS
# =============================================================================

ICE_LIGHTNING_SKILLS: Dict[str, SkillData] = {
    # =========================================================================
    # Shared Beginner Skills (same as Bowmaster)
    # =========================================================================
    "nimble_feet": SkillData(
        name="Nimble Feet",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.BASIC,  # Basic skill - unaffected by +All Skills
        unlock_level=1,
        cooldown=60.0,
        duration=15.0,
        skill_bonuses={
            "attack_speed": (15.0, SkillGrowth.FLAT),  # +15% attack speed while active (no scaling)
        },
    ),

    # =========================================================================
    # 1st Job Skills (Level 10-29)
    # =========================================================================
    "energy_bolt": SkillData(
        name="Energy Bolt",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FIRST,
        unlock_level=10,
        base_damage_pct=26.0,
        base_hits=2,
        base_targets=3,
        damage_per_level=0.13,
    ),

    "magic_guard": SkillData(
        name="Magic Guard",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=15,  # Wiki: unlocks at level 15
        cooldown=60.0,
        duration=15.0,
        skill_bonuses={
            "attack_pct": (12.0, SkillGrowth.FLAT),   # +12% Attack, does NOT scale (wiki)
            # Also +12% Defense but we don't model defense
        },
    ),

    # =========================================================================
    # 2nd Job Skills (Level 30-59)
    # =========================================================================
    "cold_beam": SkillData(
        name="Cold Beam",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.SECOND,
        unlock_level=30,
        base_damage_pct=40.0,
        base_hits=3,
        base_targets=5,
        damage_per_level=0.2,
    ),

    "magic_acceleration": SkillData(
        name="Magic Acceleration",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=33,  # Wiki: unlocks at level 33
        skill_bonuses={
            "attack_speed": (5.0, SkillGrowth.INC5),  # +5% AS at base
        },
    ),

    "thunder_bolt": SkillData(
        name="Thunder Bolt",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=38,  # Wiki: unlocks at level 38
        base_damage_pct=180.0,
        base_hits=3,
        base_targets=6,
        damage_per_level=0.9,
        cooldown=15.0,
    ),

    "meditation": SkillData(
        name="Meditation",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=40,  # Wiki: unlocks at level 40
        cooldown=60.0,
        duration=15.0,
        skill_bonuses={
            "attack_pct": (20.0, SkillGrowth.INC5),  # +20% attack to allies
        },
    ),

    "spell_mastery": SkillData(
        name="Spell Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=43,  # Wiki: unlocks at level 43
        skill_bonuses={
            "min_dmg_mult": (15.0, SkillGrowth.INC5),  # +15% min damage
        },
    ),

    "high_wisdom": SkillData(
        name="High Wisdom",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=50,  # Wiki: unlocks at level 50
        skill_bonuses={
            "crit_rate": (8.0, SkillGrowth.INC5),  # +8% crit rate
        },
    ),

    # =========================================================================
    # 3rd Job Skills (Level 60-99)
    # =========================================================================
    "ice_strike": SkillData(
        name="Ice Strike",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.THIRD,
        unlock_level=60,
        base_damage_pct=80.0,
        base_hits=5,
        base_targets=6,
        damage_per_level=0.4,
    ),

    "glacier_wall": SkillData(
        name="Glacier Wall",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=63,  # Wiki: unlocks at level 63
        base_damage_pct=290.0,
        base_hits=3,
        base_targets=8,
        damage_per_level=1.45,
        cooldown=20.0,
    ),

    "thunder_sphere": SkillData(
        name="Thunder Sphere",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=69,  # Wiki: unlocks at level 69
        base_damage_pct=100.0,
        base_hits=3,
        base_targets=6,
        damage_per_level=0.5,
        cooldown=40.0,
        duration=10.0,  # Wiki: 10 sec duration
        attack_interval=2.0,
        scales_with_attack_speed=False,
        innate_normal_monster_damage=150.0,  # +150% damage to normal monsters
    ),

    "magic_critical": SkillData(
        name="Magic Critical",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=74,  # Wiki: unlocks at level 74
        skill_bonuses={
            "crit_rate": (8.0, SkillGrowth.INC5),    # +8% crit rate
            "crit_damage": (12.0, SkillGrowth.INC5),  # +12% crit damage
        },
    ),

    "element_amplification": SkillData(
        name="Element Amplification",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=75,  # Wiki: unlocks at level 75
        skill_bonuses={
            "final_damage": (15.0, SkillGrowth.INC5),  # +15% final damage (at 50%+ MP)
        },
    ),

    # =========================================================================
    # 4th Job Skills (Level 100+)
    # =========================================================================
    "chain_lightning": SkillData(
        name="Chain Lightning",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FOURTH,
        unlock_level=100,
        base_damage_pct=290.0,
        base_hits=5,
        base_targets=6,
        damage_per_level=1.45,
    ),

    "maple_hero_mage": SkillData(
        name="Maple Hero",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=100,
        # Wiki: Grants FD to Thunder Sphere +20%, Glacier Wall +30%, Thunder Bolt +100%
        skill_bonuses={
            "thunder_sphere": (20, SkillGrowth.INC50),   # +20% FD base, +1% per level
            "glacier_wall": (30, SkillGrowth.INC50),     # +30% FD base, +1.5% per level
            "thunder_bolt": (100, SkillGrowth.INC50),    # +100% FD base, +5% per level
        },
    ),

    "freezing_breath": SkillData(
        name="Freezing Breath",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=103,  # Wiki: unlocks at level 103
        base_damage_pct=800.0,
        base_hits=1,
        base_targets=10,
        damage_per_level=4.0,
        cooldown=30.0,
        duration=5.0,  # Wiki: 5 sec duration, activates every 0.5s
        attack_interval=0.5,
        scales_with_attack_speed=False,
    ),

    "blizzard": SkillData(
        name="Blizzard",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=105,  # Wiki: unlocks at level 105
        base_damage_pct=600.0,
        base_hits=3,
        base_targets=5,
        damage_per_level=3.0,
        cooldown=25.0,
    ),

    "frozen_orb": SkillData(
        name="Frozen Orb",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=107,  # Wiki: unlocks at level 107
        base_damage_pct=900.0,
        base_hits=1,
        base_targets=10,
        damage_per_level=4.5,
        cooldown=30.0,
        duration=5.0,  # Wiki: 5 sec duration, activates every 0.5s
        attack_interval=0.5,
        scales_with_attack_speed=False,
    ),

    "infinity": SkillData(
        name="Infinity",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=110,  # Wiki: unlocks at level 110
        cooldown=90.0,
        duration=15.0,  # Wiki: 15 sec duration
        skill_bonuses={
            # +15% FD base, +1% per second up to 10 stacks = +25% max
            "final_damage": (15.0, SkillGrowth.INC5),
        },
    ),

    "elquines": SkillData(
        name="Elquines",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=115,  # Wiki: unlocks at level 115
        base_damage_pct=3500.0,
        base_hits=1,
        base_targets=3,
        damage_per_level=17.5,
        cooldown=60.0,
        duration=30.0,
        attack_interval=4.0,
        scales_with_attack_speed=False,
    ),

    "arcane_aim": SkillData(
        name="Arcane Aim",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=120,  # Wiki: unlocks at level 120
        proc_chance=0.25,  # 25% chance to trigger
        duration=10.0,  # Wiki: 10 sec duration for stacks
        # Stacking FD buff (+3% per stack, up to 5 stacks = +15%)
        skill_bonuses={
            "final_damage": (3.0, SkillGrowth.FLAT),  # +3% per stack
        },
    ),
}


# =============================================================================
# ICE/LIGHTNING MAGE MASTERIES
# =============================================================================

ICE_LIGHTNING_MASTERIES: List[MasteryNode] = [
    # ==========================================================================
    # 1st Job Masteries (Level 12-28)
    # ==========================================================================
    MasteryNode(
        name="Energy Bolt - Damage I",
        unlock_level=12,
        effect_type="skill_damage_pct",
        effect_target="energy_bolt",
        effect_value=15.0,
        description="Energy Bolt Damage +15%",
    ),
    MasteryNode(
        name="Energy Bolt - Damage II",
        unlock_level=16,
        effect_type="skill_damage_pct",
        effect_target="energy_bolt",
        effect_value=20.0,
        description="Energy Bolt Damage +20%",
    ),
    MasteryNode(
        name="Energy Bolt - Damage III",
        unlock_level=20,
        effect_type="skill_damage_pct",
        effect_target="energy_bolt",
        effect_value=20.0,
        description="Energy Bolt Damage +20%",
    ),
    MasteryNode(
        name="Energy Bolt - Targets I",
        unlock_level=24,
        effect_type="skill_targets",
        effect_target="energy_bolt",
        effect_value=1.0,
        description="Energy Bolt Target +1",
    ),
    MasteryNode(
        name="Energy Bolt - Targets II",
        unlock_level=28,
        effect_type="skill_targets",
        effect_target="energy_bolt",
        effect_value=1.0,
        description="Energy Bolt Target +1",
    ),

    # ==========================================================================
    # 2nd Job Masteries (Level 32-58)
    # ==========================================================================
    MasteryNode(
        name="Cold Beam - Damage I",
        unlock_level=32,
        effect_type="skill_damage_pct",
        effect_target="cold_beam",
        effect_value=15.0,
        description="Cold Beam Damage +15%",
    ),
    MasteryNode(
        name="Cold Beam - Targets I",
        unlock_level=36,
        effect_type="skill_targets",
        effect_target="cold_beam",
        effect_value=1.0,
        description="Cold Beam Target +1",
    ),
    MasteryNode(
        name="Cold Beam - Boss Damage I",
        unlock_level=40,
        effect_type="skill_boss_damage",
        effect_target="cold_beam",
        effect_value=20.0,
        description="Cold Beam Boss Damage +20%",
    ),
    MasteryNode(
        name="Thunder Bolt - Damage I",
        unlock_level=44,
        effect_type="skill_damage_pct",
        effect_target="thunder_bolt",
        effect_value=30.0,
        description="Thunder Bolt Damage +30%",
    ),
    MasteryNode(
        name="Cold Beam - Damage II",
        unlock_level=48,
        effect_type="skill_damage_pct",
        effect_target="cold_beam",
        effect_value=20.0,
        description="Cold Beam Damage +20%",
    ),
    MasteryNode(
        name="Cold Beam - Strikes I",
        unlock_level=52,
        effect_type="skill_hits",
        effect_target="cold_beam",
        effect_value=1.0,
        description="Cold Beam Strikes +1",
    ),
    MasteryNode(
        name="Thunder Bolt - Cooldown I",
        unlock_level=56,
        effect_type="skill_cooldown_reduction",
        effect_target="thunder_bolt",
        effect_value=2.0,
        description="Thunder Bolt Cooldown -2s",
    ),
    MasteryNode(
        name="Main Stat I",
        unlock_level=58,
        effect_type="main_stat",
        effect_target="global",
        effect_value=30.0,
        description="INT +30",
    ),

    # ==========================================================================
    # 3rd Job Masteries (Level 62-98)
    # ==========================================================================
    MasteryNode(
        name="Ice Strike - Damage I",
        unlock_level=62,
        effect_type="skill_damage_pct",
        effect_target="ice_strike",
        effect_value=15.0,
        description="Ice Strike Damage +15%",
    ),
    MasteryNode(
        name="Ice Strike - Boss Damage I",
        unlock_level=66,
        effect_type="skill_boss_damage",
        effect_target="ice_strike",
        effect_value=20.0,
        description="Ice Strike Boss Damage +20%",
    ),
    MasteryNode(
        name="Thunder Sphere - Damage I",
        unlock_level=70,
        effect_type="skill_damage_pct",
        effect_target="thunder_sphere",
        effect_value=30.0,
        description="Thunder Sphere Damage +30%",
    ),
    MasteryNode(
        name="Ice Strike - Damage II",
        unlock_level=74,
        effect_type="skill_damage_pct",
        effect_target="ice_strike",
        effect_value=20.0,
        description="Ice Strike Damage +20%",
    ),
    MasteryNode(
        name="Glacier Wall - Damage I",
        unlock_level=78,
        effect_type="skill_damage_pct",
        effect_target="glacier_wall",
        effect_value=30.0,
        description="Glacier Wall Damage +30%",
    ),
    MasteryNode(
        name="Crit Rate I",
        unlock_level=82,
        effect_type="crit_rate",
        effect_target="global",
        effect_value=5.0,
        description="Critical Rate +5%",
    ),
    MasteryNode(
        name="Ice Strike - Strikes I",
        unlock_level=86,
        effect_type="skill_hits",
        effect_target="ice_strike",
        effect_value=1.0,
        description="Ice Strike Strikes +1",
    ),
    MasteryNode(
        name="Glacier Wall - Cooldown I",
        unlock_level=90,
        effect_type="skill_cooldown_reduction",
        effect_target="glacier_wall",
        effect_value=2.0,
        description="Glacier Wall Cooldown -2s",
    ),
    MasteryNode(
        name="Thunder Sphere - Normal Monster Damage",
        unlock_level=94,
        effect_type="skill_normal_monster_damage",
        effect_target="thunder_sphere",
        effect_value=150.0,
        description="Thunder Sphere Normal Monster Damage +150%",
    ),
    MasteryNode(
        name="Accuracy I",
        unlock_level=98,
        effect_type="accuracy",
        effect_target="global",
        effect_value=5.0,
        description="Accuracy +5",
    ),

    # ==========================================================================
    # 4th Job Masteries (Level 102-138)
    # ==========================================================================
    MasteryNode(
        name="Chain Lightning - Damage I",
        unlock_level=102,
        effect_type="skill_damage_pct",
        effect_target="chain_lightning",
        effect_value=15.0,
        description="Chain Lightning Damage +15%",
    ),
    MasteryNode(
        name="Chain Lightning - Boss Damage I",
        unlock_level=106,
        effect_type="skill_boss_damage",
        effect_target="chain_lightning",
        effect_value=20.0,
        description="Chain Lightning Boss Damage +20%",
    ),
    MasteryNode(
        name="Freezing Breath - Damage I",
        unlock_level=110,
        effect_type="skill_damage_pct",
        effect_target="freezing_breath",
        effect_value=30.0,
        description="Freezing Breath Damage +30%",
    ),
    MasteryNode(
        name="Chain Lightning - Damage II",
        unlock_level=114,
        effect_type="skill_damage_pct",
        effect_target="chain_lightning",
        effect_value=20.0,
        description="Chain Lightning Damage +20%",
    ),
    MasteryNode(
        name="Frozen Orb - Damage I",
        unlock_level=118,
        effect_type="skill_damage_pct",
        effect_target="frozen_orb",
        effect_value=30.0,
        description="Frozen Orb Damage +30%",
    ),
    MasteryNode(
        name="Max Damage Mult I",
        unlock_level=122,
        effect_type="max_dmg_mult",
        effect_target="global",
        effect_value=10.0,
        description="Maximum Damage Multiplier +10%",
    ),
    MasteryNode(
        name="Chain Lightning - Strikes I",
        unlock_level=126,
        effect_type="skill_hits",
        effect_target="chain_lightning",
        effect_value=1.0,
        description="Chain Lightning Strikes +1",
    ),
    MasteryNode(
        name="Elquines - Damage I",
        unlock_level=130,
        effect_type="skill_damage_pct",
        effect_target="elquines",
        effect_value=30.0,
        description="Elquines Damage +30%",
    ),
    MasteryNode(
        name="Skill Damage I",
        unlock_level=134,
        effect_type="skill_damage",
        effect_target="global",
        effect_value=15.0,
        description="Skill Damage +15%",
    ),
    MasteryNode(
        name="Basic Attack Damage I",
        unlock_level=136,
        effect_type="basic_attack_damage",
        effect_target="global",
        effect_value=15.0,
        description="Basic Attack Damage +15%",
    ),
    MasteryNode(
        name="Basic Attack Target I",
        unlock_level=138,
        effect_type="basic_attack_targets",
        effect_target="global",
        effect_value=1.0,
        description="Basic Attack Target +1",
    ),

    # ==========================================================================
    # Passive Skill Masteries (from passive skills, not level-gated)
    # These are applied via skill bonuses, modeled here for reference
    # ==========================================================================
    # Magic Acceleration: +5% Attack Speed (passive skill, always active from level 30)
    # Spell Mastery: +15% Min Damage (passive skill, always active from level 30)
    # High Wisdom: +8% Crit Rate (passive skill, always active from level 30)
    # Magic Critical: +8% CR, +12% CD (passive skill, always active from level 60)
    # Element Amplification: +15% Final Damage (passive skill, always active from level 60)
    # Arcane Aim: +3% FD per stack, 5 stacks max = +15% FD (passive proc)
    # Frozen Break: +3% FD per stack, 5 stacks max = +15% FD (passive proc)
]


# =============================================================================
# FIRE/POISON ARCH MAGE SKILLS
# =============================================================================
# Skill IDs (datamine): 51010-54100 (CreatureIndex=5)
# 1st: 51010-51040, 2nd: 52010-52080, 3rd: 53010-53080, 4th: 54010-54100

FIRE_POISON_SKILLS: Dict[str, SkillData] = {
    # =========================================================================
    # Shared Beginner Skills
    # =========================================================================
    "nimble_feet": SkillData(
        name="Nimble Feet",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.BASIC,
        unlock_level=1,
        cooldown=60.0,
        duration=15.0,
        skill_bonuses={
            "attack_speed": (15.0, SkillGrowth.FLAT),
        },
    ),

    # =========================================================================
    # 1st Job Skills (Level 10-29)
    # =========================================================================
    # 51010 EnergyBolt action — basic ranged attack
    "energy_bolt": SkillData(
        name="Energy Bolt",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FIRST,
        unlock_level=10,
        base_damage_pct=26.0,
        base_hits=2,
        base_targets=3,
        damage_per_level=0.13,
    ),

    # 51030 MagicGuard action — +12% Attack/Def for 15s, 30s CD
    "magic_guard": SkillData(
        name="Magic Guard",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=15,
        cooldown=30.0,
        duration=15.0,
        skill_bonuses={
            "attack_pct": (12.0, SkillGrowth.FLAT),
        },
    ),

    # =========================================================================
    # 2nd Job Skills (Level 30-59)
    # =========================================================================
    # 52010 FlameOrb action (Fire) — 5 hits × 3 targets × 40%
    "flame_orb": SkillData(
        name="Flame Orb",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.SECOND,
        unlock_level=30,
        base_damage_pct=40.0,
        base_hits=5,
        base_targets=3,
        damage_per_level=0.2,
    ),

    # 52050 — +5% Attack Speed passive
    "spell_mastery": SkillData(
        name="Spell Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=33,
        skill_bonuses={
            "attack_speed": (5.0, SkillGrowth.INC5),
        },
    ),

    # 52060 (Fire OnAttack, 50% trigger, 2.5s ICD) → 52061 fires 130% × 1 hit
    # Wiki name: "Ignite"
    "ignite": SkillData(
        name="Ignite",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=35,
        base_damage_pct=130.0,
        base_hits=1,
        base_targets=1,
        damage_per_level=0.65,
        proc_chance=0.5,
        cooldown=2.5,
    ),

    # 52030 PoisonBreath action (Poison) — 160% × 6 hits, 18s CD
    "poison_breath": SkillData(
        name="Poison Breath",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=38,
        base_damage_pct=160.0,
        base_hits=6,
        base_targets=3,
        damage_per_level=0.8,
        cooldown=18.0,
    ),

    # 52040 Meditation action — +20% Attack for 15s, 30s CD (ally-target)
    "meditation": SkillData(
        name="Meditation",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=40,
        cooldown=30.0,
        duration=15.0,
        skill_bonuses={
            "attack_pct": (20.0, SkillGrowth.INC5),
        },
    ),

    # 52070 — +15% Min Damage passive
    "magic_boost": SkillData(
        name="Magic Boost",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=43,
        skill_bonuses={
            "min_dmg_mult": (15.0, SkillGrowth.INC5),
        },
    ),

    # 52020 (Poison OnHit, 50% trigger) → DoT 8% × 20 ticks, applies ArchMagePoison state
    # Modeled as PASSIVE_PROC contributing total DoT contribution
    # 8% × 20 ticks = 160% total over 20s window
    "poison_dot": SkillData(
        name="Poison Brace",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=50,
        base_damage_pct=8.0,
        base_hits=20,
        base_targets=1,
        damage_per_level=0.04,
        proc_chance=0.5,
    ),

    # =========================================================================
    # 3rd Job Skills (Level 60-99)
    # =========================================================================
    # 53010 Explosion action (Fire) — 3rd-job basic, 80% × 6 hits × 5 targets
    "explosion": SkillData(
        name="Explosion",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.THIRD,
        unlock_level=60,
        base_damage_pct=80.0,
        base_hits=6,
        base_targets=5,
        damage_per_level=0.4,
    ),

    # 53020 PoisonMist action (Poison) — 160% × 10 hits, 35s CD (+ DoT 70% per tick)
    "poison_mist": SkillData(
        name="Poison Mist",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=63,
        base_damage_pct=160.0,
        base_hits=10,
        base_targets=3,
        damage_per_level=0.8,
        cooldown=35.0,
    ),

    # 53030 PoisonRegion (Poison, 27s CD, 15s buff) → 53032 chains 120% × 2 hits
    # on Fire attacks against poisoned targets (2s ICD per target).
    # Modeled as SUMMON: 15s up, 2s interval, 120% × 2 hits per tick.
    # Wiki name: "Creeping Toxin"
    "creeping_toxin": SkillData(
        name="Creeping Toxin",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=69,
        base_damage_pct=120.0,
        base_hits=2,
        base_targets=5,
        damage_per_level=0.6,
        cooldown=27.0,
        duration=15.0,
        attack_interval=2.0,
        scales_with_attack_speed=False,
    ),

    # 53070 — +8% Crit Rate, +12% Crit Damage passive (Magic Critical)
    "magic_critical": SkillData(
        name="Magic Critical",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=74,
        skill_bonuses={
            "crit_rate": (8.0, SkillGrowth.INC5),
            "crit_damage": (12.0, SkillGrowth.INC5),
        },
    ),

    # 53080 — +15% Final Damage passive (Element Amplification, at >=50% MP)
    "element_amplification": SkillData(
        name="Element Amplification",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=75,
        skill_bonuses={
            "final_damage": (15.0, SkillGrowth.INC5),
        },
    ),

    # =========================================================================
    # 4th Job Skills (Level 100+)
    # =========================================================================
    # 54010 FlameSweep action (Fire) — 4th-job basic, 290% × 6 hits × 5 targets
    "flame_sweep": SkillData(
        name="Flame Sweep",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FOURTH,
        unlock_level=100,
        base_damage_pct=290.0,
        base_hits=6,
        base_targets=5,
        damage_per_level=1.45,
    ),

    # 54100 — Skill enhancer: Maple Hero (F/P)
    # 53032 (Creeping Toxin proc): +10% FD, 53020 (Poison Mist): +10% FD,
    # 52030 (Poison Breath): +80% FD, 52061 (Ignite): +50% FD
    "maple_hero_fp": SkillData(
        name="Maple Hero",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=100,
        skill_bonuses={
            "creeping_toxin": (10, SkillGrowth.INC50),
            "poison_mist": (10, SkillGrowth.INC50),
            "poison_breath": (80, SkillGrowth.INC50),
            "ignite": (50, SkillGrowth.INC50),
        },
    ),

    # 54020/54021/54022 — Mist Eruption
    # Triggers on enemy death within 53020 (Poison Mist) projectile area.
    # Modeled as a mob-scenario active: 3000% × 1 hit, gated to Poison Mist's CD.
    "mist_eruption": SkillData(
        name="Mist Eruption",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=103,
        base_damage_pct=3000.0,
        base_hits=1,
        base_targets=5,
        damage_per_level=15.0,
        cooldown=35.0,
        scenario="mob",
    ),

    # 54030 Meteor action (Fire) — 600% × 5 hits, 33s CD, 1500mm radius
    # Wiki name: "Meteor Shower"
    "meteor_shower": SkillData(
        name="Meteor Shower",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=105,
        base_damage_pct=600.0,
        base_hits=5,
        base_targets=5,
        damage_per_level=3.0,
        cooldown=33.0,
    ),

    # 54040/54041 FlameHaze action (Fire) — 1200% × 3 hits + Burn DoT
    # Boss: +150% DoT × 30s = +4500% total; Non-boss: +150% DoT × 10s = +1500%
    # Use non-boss values (default scenario); boss damage bonus handled separately
    # Wiki name: "Flame Haze"
    "flame_haze": SkillData(
        name="Flame Haze",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=107,
        base_damage_pct=1200.0,
        base_hits=3,
        base_targets=5,
        damage_per_level=6.0,
        cooldown=25.0,
        dot_damage_pct=150.0,
        dot_duration=10.0,
        dot_interval=1.0,
    ),

    # 54050 Infinity action — +15% FD base + ModStatOnTick (+1% per sec, max +10%)
    # 30s CD, 15s duration (FP is shorter CD than IL's 90s)
    "infinity": SkillData(
        name="Infinity",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=110,
        cooldown=30.0,
        duration=15.0,
        skill_bonuses={
            "final_damage": (15.0, SkillGrowth.INC5),
        },
    ),

    # 54060/54061 Efreet action (Fire summon) — 80s CD, 3500% × 1 hit
    # Estimate duration=30s, interval=4s (matches IL Elquines pattern)
    "ifrit": SkillData(
        name="Ifrit",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=115,
        base_damage_pct=3500.0,
        base_hits=1,
        base_targets=3,
        damage_per_level=17.5,
        cooldown=80.0,
        duration=30.0,
        attack_interval=4.0,
        scales_with_attack_speed=False,
    ),

    # 54080 — +3% FD per stack proc (Arcane Aim), 25% trigger, 10s duration
    "arcane_aim": SkillData(
        name="Arcane Aim",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=120,
        proc_chance=0.25,
        duration=10.0,
        skill_bonuses={
            "final_damage": (3.0, SkillGrowth.FLAT),
        },
    ),

    # 54090 — +60% Fire Damage per ArchMagePoison stack
    # Approximation: assume 3 stacks held in typical fight → +180% Fire damage
    # ~75% of FP damage is Fire-tagged, so effective FD bonus ≈ +135%
    # Use conservative +90% baseline; treat as passive_stat final_damage
    # (Note: 53050 "Burning Magic" is the 3rd-job version with +3% per stack;
    #  this 4th-job passive stacks multiplicatively for Fire-tagged skills.)
    "ignite_mastery": SkillData(
        name="Ignite Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=125,
        skill_bonuses={
            "final_damage": (90.0, SkillGrowth.INC5),
        },
    ),
}


# =============================================================================
# FIRE/POISON ARCH MAGE MASTERIES
# =============================================================================
# Sourced from idle.maplestorywiki.net/w/Arch_Mage_(Fire_Poison) and cross-checked
# against the datamine (HeroSkillMasteryTable + SkillTable IDs 50010-50295).
# Skills appear in the wiki interleaved by level — listed here in level order.

FIRE_POISON_MASTERIES: List[MasteryNode] = [
    # ==========================================================================
    # 1st Job (Levels 12-28)
    # ==========================================================================
    MasteryNode("Energy Bolt - Damage I", 12, 0, "skill_damage_pct", "energy_bolt", 15.0, "Energy Bolt Damage +15%"),
    MasteryNode("Main Stat Enhancement", 14, 0, "main_stat_flat", "global", 30.0, "Main Stat +30"),
    MasteryNode("Energy Bolt - Target I", 15, 0, "skill_targets", "energy_bolt", 1.0, "Energy Bolt +1 target"),
    MasteryNode("Critical Rate Enhancement", 17, 0, "crit_rate", "global", 5.0, "Critical Rate +5%"),
    MasteryNode("Energy Bolt - Damage II", 19, 0, "skill_damage_pct", "energy_bolt", 20.0, "Energy Bolt Damage +20%"),
    MasteryNode("Magic Guard - Reuse", 21, 0, "skill_cooldown_reduction", "magic_guard", 9.0, "Magic Guard Cooldown -30% (-9s of 30s base)"),
    MasteryNode("Energy Bolt - Target II", 22, 0, "skill_targets", "energy_bolt", 1.0, "Energy Bolt +1 target"),
    # Lvl 24 Teleport - Reuse (movement only, skipped)
    MasteryNode("Energy Bolt - Damage III", 26, 0, "skill_damage_pct", "energy_bolt", 20.0, "Energy Bolt Damage +20%"),
    MasteryNode("Basic Attack Damage Enhancement", 28, 0, "basic_attack_damage", "global", 15.0, "Basic Attack Damage +15%"),

    # ==========================================================================
    # 2nd Job (Levels 32-58)
    # ==========================================================================
    MasteryNode("Flame Orb - Damage I", 32, 0, "skill_damage_pct", "flame_orb", 15.0, "Flame Orb Damage +15%"),
    MasteryNode("Accuracy Enhancement", 34, 0, "accuracy", "global", 5.0, "Accuracy +5"),
    MasteryNode("Flame Orb - Target I", 37, 0, "skill_targets", "flame_orb", 1.0, "Flame Orb +1 target"),
    MasteryNode("Poison Breath - Damage I", 39, 0, "skill_damage_pct", "poison_breath", 50.0, "Poison Breath Damage +50%"),
    MasteryNode("Flame Orb - Damage II", 42, 0, "skill_damage_pct", "flame_orb", 20.0, "Flame Orb Damage +20%"),
    MasteryNode("Meditation - Persistence", 44, 0, "skill_duration", "meditation", 4.5, "Meditation Duration +30% (+4.5s of 15s base)"),
    MasteryNode("Flame Orb - Boss Damage I", 47, 0, "skill_boss_damage", "flame_orb", 15.0, "Flame Orb Boss Damage +15%"),
    # Lvl 49 MP Eater - MP Boost: +7% AS at >=50% MP (conditional; approximated as +7% global AS since MP is usually full in idle play)
    MasteryNode("MP Eater - MP Boost", 49, 0, "attack_speed", "global", 7.0, "Attack Speed +7% (at >50% MP)"),
    MasteryNode("Flame Orb - Damage III", 52, 0, "skill_damage_pct", "flame_orb", 20.0, "Flame Orb Damage +20%"),
    MasteryNode("Ignite - Damage I", 54, 0, "skill_damage_pct", "ignite", 100.0, "Ignite Damage +100%"),
    MasteryNode("Flame Orb - Strike I", 56, 0, "skill_hits", "flame_orb", 1.0, "Flame Orb +1 hit"),
    MasteryNode("Max Damage Multiplier Enhancement", 58, 0, "max_dmg_mult", "global", 10.0, "Max Damage Multiplier +10%"),

    # ==========================================================================
    # 3rd Job (Levels 62-98)
    # ==========================================================================
    MasteryNode("Explosion - Damage I", 62, 0, "skill_damage_pct", "explosion", 10.0, "Explosion Damage +10%"),
    MasteryNode("Basic Attack Target Enhancement", 64, 0, "basic_attack_targets", "global", 1.0, "Basic Attack Target +1"),
    MasteryNode("Explosion - Damage II", 66, 0, "skill_damage_pct", "explosion", 11.0, "Explosion Damage +11%"),
    MasteryNode("Poison Mist - Damage I", 68, 0, "skill_damage_pct", "poison_mist", 50.0, "Poison Mist Damage +50%"),
    MasteryNode("Explosion - Boss Damage I", 71, 0, "skill_boss_damage", "explosion", 10.0, "Explosion Boss Damage +10%"),
    # Lvl 73 Creeping Toxin - Poison: mechanic enabler (auto-applies 3 poison stacks to nearby targets), skipped — Burning Magic per-stack scaling assumes full stacks
    MasteryNode("Explosion - Damage III", 76, 0, "skill_damage_pct", "explosion", 12.0, "Explosion Damage +12%"),
    MasteryNode("Creeping Toxin - Damage I", 78, 0, "skill_damage_pct", "creeping_toxin", 50.0, "Creeping Toxin Damage +50%"),
    MasteryNode("Explosion - Damage IV", 80, 0, "skill_damage_pct", "explosion", 13.0, "Explosion Damage +13%"),
    # Lvl 82 Elemental Reset - Chance: doubles Weakness-debuff trigger rate (not modeled — def-pen averaging)
    MasteryNode("Explosion - Boss Damage II", 84, 0, "skill_boss_damage", "explosion", 10.0, "Explosion Boss Damage +10%"),
    MasteryNode("Skill Damage Enhancement", 86, 0, "skill_damage", "global", 15.0, "Skill Damage +15%"),
    MasteryNode("Explosion - Damage V", 88, 0, "skill_damage_pct", "explosion", 14.0, "Explosion Damage +14%"),
    MasteryNode("Poison Mist - Reuse", 90, 0, "skill_cooldown_reduction", "poison_mist", 10.5, "Poison Mist Cooldown -30% (-10.5s of 35s base)"),
    MasteryNode("Explosion - Damage VI", 92, 0, "skill_damage_pct", "explosion", 15.0, "Explosion Damage +15%"),
    MasteryNode("Creeping Toxin - Normal Monster Damage", 94, 0, "skill_normal_monster_damage", "creeping_toxin", 100.0, "Creeping Toxin Normal Monster Damage +100%p"),
    MasteryNode("Explosion - Strike I", 96, 0, "skill_hits", "explosion", 1.0, "Explosion +1 hit"),
    # Lvl 98 Burning Magic - Damage: +2%p per Poison stack — bakes into ignite_mastery's baked-in average (skipped as separate node)

    # ==========================================================================
    # 4th Job (Levels 102-138)
    # ==========================================================================
    MasteryNode("Flame Sweep - Damage I", 102, 0, "skill_damage_pct", "flame_sweep", 10.0, "Flame Sweep Damage +10%"),
    MasteryNode("Poison Mist - Strike Interval", 104, 0, "skill_attack_interval_pct", "poison_mist", -50.0, "Poison Mist Strike Interval -50%"),
    MasteryNode("Flame Sweep - Damage II", 106, 0, "skill_damage_pct", "flame_sweep", 11.0, "Flame Sweep Damage +11%"),
    # Lvl 108 Mist Eruption - Explosion: +1 max explosion count, 2s CD (mechanic, not modeled)
    MasteryNode("Flame Sweep - Boss Damage I", 111, 0, "skill_boss_damage", "flame_sweep", 10.0, "Flame Sweep Boss Damage +10%"),
    # Lvl 113 Meteor Shower - Final Attack: 20% proc, 750% (procs from Meteor in slot; complex conditional, approximated as +10% damage)
    MasteryNode("Meteor Shower - Final Attack", 113, 0, "skill_damage_pct", "meteor_shower", 10.0, "Meteor Shower +10% via Final Attack proc"),
    MasteryNode("Flame Sweep - Damage III", 116, 0, "skill_damage_pct", "flame_sweep", 12.0, "Flame Sweep Damage +12%"),
    # Lvl 118 Flame Haze - Poisonous Fog: creates Poison Mist on cast (mechanic, not modeled)
    MasteryNode("Flame Sweep - Damage IV", 120, 0, "skill_damage_pct", "flame_sweep", 13.0, "Flame Sweep Damage +13%"),
    MasteryNode("Mist Eruption - Damage I", 122, 0, "skill_damage_pct", "mist_eruption", 100.0, "Mist Eruption Damage +100%"),
    MasteryNode("Flame Sweep - Boss Damage II", 124, 0, "skill_boss_damage", "flame_sweep", 10.0, "Flame Sweep Boss Damage +10%"),
    # Lvl 126 Flame Haze - Burn: Ifrit duration +5s, max targets +1 (modeled via Ifrit's existing values)
    MasteryNode("Ifrit - Targets I", 126, 0, "skill_targets", "ifrit", 1.0, "Ifrit +1 target (Flame Haze - Burn)"),
    MasteryNode("Flame Sweep - Damage V", 128, 0, "skill_damage_pct", "flame_sweep", 14.0, "Flame Sweep Damage +14%"),
    MasteryNode("Meteor Shower - Damage I", 130, 0, "skill_damage_pct", "meteor_shower", 20.0, "Meteor Shower Damage +20%"),
    MasteryNode("Flame Sweep - Damage VI", 132, 0, "skill_damage_pct", "flame_sweep", 15.0, "Flame Sweep Damage +15%"),
    # Lvl 134 Meteor Shower - Damage ([Flame Haze in Slot]): conditional proc (skipped)
    MasteryNode("Flame Sweep - Strike I", 136, 0, "skill_hits", "flame_sweep", 1.0, "Flame Sweep +1 hit"),
    # Lvl 138 Ifrit - Persistence & Target: +10% per Burn stack on target (conditional, skipped)
]


# =============================================================================
# HERO (WARRIOR) SKILLS
# =============================================================================
# Skill IDs (datamine, CreatureIndex=1): 11010-14100
# Names sourced from idle.maplestorywiki.net mastery list and cross-checked
# against datamine action names (RagingBlow, EnhanceRagingBlow, Incising,
# MagicCrash).

HERO_SKILLS: Dict[str, SkillData] = {
    # =========================================================================
    # Shared Beginner Skills
    # =========================================================================
    "nimble_feet": SkillData(
        name="Nimble Feet",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.BASIC,
        unlock_level=1,
        cooldown=60.0,
        duration=15.0,
        skill_bonuses={
            "attack_speed": (15.0, SkillGrowth.FLAT),
        },
    ),

    # =========================================================================
    # 1st Job Skills (Level 10-29)
    # =========================================================================
    # 11010 — basic melee attack, 26% × 3 hits × 2 targets, 600ms tick
    "slash_blast": SkillData(
        name="Slash Blast",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FIRST,
        unlock_level=10,
        base_damage_pct=26.0,
        base_hits=3,
        base_targets=2,
        damage_per_level=0.13,
    ),

    # 11030 — +15% Defence (skipped, defensive) and +30 STR passive
    "iron_body": SkillData(
        name="Iron Body",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=10,
        skill_bonuses={
            "main_stat_flat": (30.0, SkillGrowth.INC3),
        },
    ),

    # =========================================================================
    # 2nd Job Skills (Level 30-59)
    # =========================================================================
    # 12010 — Brandish basic, 40% × 5 hits × 3 targets
    "brandish": SkillData(
        name="Brandish",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.SECOND,
        unlock_level=30,
        base_damage_pct=40.0,
        base_hits=5,
        base_targets=3,
        damage_per_level=0.2,
    ),

    # 12020 — Flash Slash active, 16s CD: 250% × 7 hits + 350% × 7 hits
    # Modeled as combined 600% per hit × 7 hits for simplicity
    "flash_slash": SkillData(
        name="Flash Slash",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=35,
        base_damage_pct=600.0,
        base_hits=7,
        base_targets=1,
        damage_per_level=3.0,
        cooldown=16.0,
    ),

    # 12030 — Combo Attack: OnAttack +4% Attack per stack (ComboAttack state)
    # Approx avg 3 stacks held = +12% Attack passive
    "combo_attack": SkillData(
        name="Combo Attack",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=45,
        skill_bonuses={
            "attack_pct": (12.0, SkillGrowth.INC5),
        },
    ),

    # 12040 — Spirit Blade active buff, 45s CD: +10% Attack for 20s
    "spirit_blade": SkillData(
        name="Spirit Blade",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=40,
        cooldown=45.0,
        duration=20.0,
        skill_bonuses={
            "attack_pct": (10.0, SkillGrowth.INC5),
        },
    ),

    # 12050 — +15% Min Damage Ratio passive
    "weapon_mastery": SkillData(
        name="Weapon Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=43,
        skill_bonuses={
            "min_dmg_mult": (15.0, SkillGrowth.INC5),
        },
    ),

    # 12060 — +5% Attack Speed passive
    "weapon_booster": SkillData(
        name="Weapon Booster",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=33,
        skill_bonuses={
            "attack_speed": (5.0, SkillGrowth.INC5),
        },
    ),

    # 12070 — Final Attack: OnAttack DoT proc, 35% damage per tick
    "final_attack_hero": SkillData(
        name="Final Attack",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=50,
        base_damage_pct=35.0,
        base_hits=1,
        base_targets=1,
        damage_per_level=0.175,
        proc_chance=0.5,
    ),

    # 12080 — +10% BaseAttackPower passive (Physical Training)
    "physical_training": SkillData(
        name="Physical Training",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=38,
        skill_bonuses={
            "attack_pct": (10.0, SkillGrowth.INC5),
        },
    ),

    # =========================================================================
    # 3rd Job Skills (Level 60-99)
    # =========================================================================
    # 13010 — Intrepid Slash basic, 80% × 6 hits × 5 targets
    "intrepid_slash": SkillData(
        name="Intrepid Slash",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.THIRD,
        unlock_level=60,
        base_damage_pct=80.0,
        base_hits=6,
        base_targets=5,
        damage_per_level=0.4,
    ),

    # 13020 — Beam Blade active, 16s CD: 250% × 8 hits × 4 targets
    "beam_blade": SkillData(
        name="Beam Blade",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=69,
        base_damage_pct=250.0,
        base_hits=8,
        base_targets=4,
        damage_per_level=1.25,
        cooldown=16.0,
    ),

    # 13030 — Rush active, 22s CD: 600% × 12 hits × 1 target, +Stun
    "rush": SkillData(
        name="Rush",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=63,
        base_damage_pct=600.0,
        base_hits=12,
        base_targets=1,
        damage_per_level=3.0,
        cooldown=22.0,
    ),

    # 13050 — Combo Synergy: boosts Combo Attack effectiveness
    # Approximated as additional +5% Attack to represent the upgrade
    "combo_synergy": SkillData(
        name="Combo Synergy",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=75,
        skill_bonuses={
            "attack_pct": (5.0, SkillGrowth.INC5),
        },
    ),

    # 13060 — Self Recovery: +5% Final Damage at >=50% HP (approximated as permanent passive)
    "self_recovery": SkillData(
        name="Self Recovery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=60,
        skill_bonuses={
            "final_damage": (5.0, SkillGrowth.INC5),
        },
    ),

    # 13070 — Combat Mastery: +8% Crit Rate, +12% AttackPowerInCc (only CR modeled)
    "combat_mastery": SkillData(
        name="Combat Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=74,
        skill_bonuses={
            "crit_rate": (8.0, SkillGrowth.INC5),
        },
    ),

    # =========================================================================
    # 4th Job Skills (Level 100+)
    # =========================================================================
    # 14010 — RagingBlow action, 290% × 6 hits × 5 targets
    "raging_blow": SkillData(
        name="Raging Blow",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FOURTH,
        unlock_level=100,
        base_damage_pct=290.0,
        base_hits=6,
        base_targets=5,
        damage_per_level=1.45,
    ),

    # 14100 — Maple Hero (Warrior): +FD to key actives
    # 13020 (Beam Blade) +20%, 13030 (Rush) +30%, 12020 (Flash Slash) +80%
    "maple_hero_warrior": SkillData(
        name="Maple Hero",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=100,
        skill_bonuses={
            "beam_blade": (20, SkillGrowth.INC50),
            "rush": (30, SkillGrowth.INC50),
            "flash_slash": (80, SkillGrowth.INC50),
        },
    ),

    # 14020 — Enhanced Raging Blow / "Puncture" (EnhanceRagingBlow action)
    # 19s CD: 550% × 9 hits × 6 targets
    "enhanced_raging_blow": SkillData(
        name="Enhanced Raging Blow",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=103,
        base_damage_pct=550.0,
        base_hits=9,
        base_targets=6,
        damage_per_level=2.75,
        cooldown=19.0,
    ),

    # 14030 — Incising active, 19s CD: 900% × 5 hits × 3 targets + 150% × 10s Burn DoT
    "incising": SkillData(
        name="Incising",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=107,
        base_damage_pct=900.0,
        base_hits=5,
        base_targets=3,
        damage_per_level=4.5,
        cooldown=19.0,
        dot_damage_pct=150.0,
        dot_duration=10.0,
        dot_interval=1.0,
    ),

    # 14040 — MagicCrash active, 28s CD: 4800% × 5 hits × 1 target + Weakness debuff
    "magic_crash": SkillData(
        name="Magic Crash",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=117,
        base_damage_pct=4800.0,
        base_hits=5,
        base_targets=1,
        damage_per_level=24.0,
        cooldown=28.0,
    ),

    # 14050 — Enrage passive: OnTimer auto-procs +12% FD/+15% CD for 5s
    # Approximated as a permanent passive (always-on uptime)
    "enrage": SkillData(
        name="Enrage",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=115,
        skill_bonuses={
            "final_damage": (12.0, SkillGrowth.INC5),
            "crit_damage": (15.0, SkillGrowth.INC5),
        },
    ),

    # 14070 — Combat Mastery (4th): +5% Toughness, +15% FD passive
    "combat_mastery_4th": SkillData(
        name="Combat Mastery (Advanced)",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=110,
        skill_bonuses={
            "final_damage": (15.0, SkillGrowth.INC5),
        },
    ),

    # 14080 — Advanced Final Attack: +500% FD to Final Attack DoT (12070)
    "advanced_final_attack": SkillData(
        name="Advanced Final Attack",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=105,
        skill_bonuses={
            "final_attack_hero": (500, SkillGrowth.INC50),
        },
    ),

    # 14090 — Hyper Body: +15% Skill Power, +20% Max Damage Ratio
    "hyper_body": SkillData(
        name="Hyper Body",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=120,
        skill_bonuses={
            "skill_damage": (15.0, SkillGrowth.INC5),
            "max_dmg_mult": (20.0, SkillGrowth.INC5),
        },
    ),
}


# =============================================================================
# HERO (WARRIOR) MASTERIES
# =============================================================================
# Sourced from datamine (HeroSkillMasteryTable + SkillTable IDs 10010-10295).
# Main spine = basic-attack chain (11010 → 12010 → 13010 → 14010).
# Branch nodes (sub-tier 100X) cover global stats and per-skill upgrades.

HERO_MASTERIES: List[MasteryNode] = [
    # ==========================================================================
    # 1st Job (Levels 12-28)
    # ==========================================================================
    MasteryNode("Slash Blast - Damage I", 12, 0, "skill_damage_pct", "slash_blast", 15.0, "Slash Blast Damage +15%"),
    MasteryNode("Main Stat Enhancement", 14, 0, "main_stat_flat", "global", 30.0, "Main Stat +30"),
    MasteryNode("Slash Blast - Target I", 15, 0, "skill_targets", "slash_blast", 1.0, "Slash Blast +1 target"),
    MasteryNode("Critical Rate Enhancement", 17, 0, "crit_rate", "global", 5.0, "Critical Rate +5%"),
    MasteryNode("Slash Blast - Damage II", 19, 0, "skill_damage_pct", "slash_blast", 20.0, "Slash Blast Damage +20%"),
    # Lvl 21 Iron Body - Defense +10%p: defensive, skipped
    MasteryNode("Slash Blast - Target II", 22, 0, "skill_targets", "slash_blast", 1.0, "Slash Blast +1 target"),
    # Lvl 24 Warrior Mastery - Speed +5%p: movement, skipped
    MasteryNode("Slash Blast - Damage III", 26, 0, "skill_damage_pct", "slash_blast", 20.0, "Slash Blast Damage +20%"),
    MasteryNode("Basic Attack Damage Enhancement", 28, 0, "basic_attack_damage", "global", 15.0, "Basic Attack Damage +15%"),

    # ==========================================================================
    # 2nd Job (Levels 32-58)
    # ==========================================================================
    MasteryNode("Brandish - Damage I", 32, 0, "skill_damage_pct", "brandish", 15.0, "Brandish Damage +15%"),
    MasteryNode("Accuracy Enhancement", 34, 0, "accuracy", "global", 5.0, "Accuracy +5"),
    MasteryNode("Brandish - Target I", 37, 0, "skill_targets", "brandish", 1.0, "Brandish +1 target"),
    MasteryNode("Flash Slash - Damage I", 39, 0, "skill_damage_pct", "flash_slash", 50.0, "Flash Slash Damage +50%"),
    MasteryNode("Brandish - Damage II", 42, 0, "skill_damage_pct", "brandish", 20.0, "Brandish Damage +20%"),
    MasteryNode("Spirit Blade - Reuse", 44, 0, "skill_cooldown_reduction", "spirit_blade", 13.5, "Spirit Blade Cooldown -30% (-13.5s of 45s base)"),
    MasteryNode("Brandish - Boss Damage I", 47, 0, "skill_boss_damage", "brandish", 15.0, "Brandish Boss Damage +15%"),
    # Lvl 49 Combo Attack +1.5%p per stack: bundled into combo_attack baseline
    MasteryNode("Brandish - Damage III", 52, 0, "skill_damage_pct", "brandish", 20.0, "Brandish Damage +20%"),
    MasteryNode("Final Attack - Damage I", 54, 0, "skill_damage_pct", "final_attack_hero", 50.0, "Final Attack Damage +50%"),
    MasteryNode("Brandish - Strike I", 56, 0, "skill_hits", "brandish", 1.0, "Brandish +1 hit"),
    MasteryNode("Max Damage Multiplier Enhancement", 58, 0, "max_dmg_mult", "global", 10.0, "Max Damage Multiplier +10%"),

    # ==========================================================================
    # 3rd Job (Levels 62-98)
    # ==========================================================================
    MasteryNode("Intrepid Slash - Damage I", 62, 0, "skill_damage_pct", "intrepid_slash", 10.0, "Intrepid Slash Damage +10%"),
    MasteryNode("Basic Attack Target Enhancement", 64, 0, "basic_attack_targets", "global", 1.0, "Basic Attack Target +1"),
    MasteryNode("Intrepid Slash - Damage II", 66, 0, "skill_damage_pct", "intrepid_slash", 11.0, "Intrepid Slash Damage +11%"),
    MasteryNode("Rush - Damage I", 68, 0, "skill_damage_pct", "rush", 80.0, "Rush Damage +80%"),
    MasteryNode("Intrepid Slash - Boss Damage I", 71, 0, "skill_boss_damage", "intrepid_slash", 10.0, "Intrepid Slash Boss Damage +10%"),
    MasteryNode("Beam Blade - Damage I", 73, 0, "skill_damage_pct", "beam_blade", 50.0, "Beam Blade Damage +50%"),
    MasteryNode("Intrepid Slash - Damage III", 76, 0, "skill_damage_pct", "intrepid_slash", 12.0, "Intrepid Slash Damage +12%"),
    # Lvl 78 Scaring Sword - Weaken +8%p damage taken: enemy debuff during 15s/30s = ~50% uptime
    # Approximated as +4% skill_damage globally to represent average uptime contribution
    MasteryNode("Scaring Sword - Weaken", 78, 0, "skill_damage", "global", 4.0, "Scaring Sword +8%p damage taken (50% uptime ~ +4% skill dmg)"),
    MasteryNode("Intrepid Slash - Damage IV", 80, 0, "skill_damage_pct", "intrepid_slash", 13.0, "Intrepid Slash Damage +13%"),
    MasteryNode("Combo Synergy - Final Damage", 82, 0, "final_damage", "global", 1.0, "Combo Synergy +1%p Final Damage"),
    MasteryNode("Intrepid Slash - Boss Damage II", 84, 0, "skill_boss_damage", "intrepid_slash", 10.0, "Intrepid Slash Boss Damage +10%"),
    MasteryNode("Skill Damage Enhancement", 86, 0, "skill_damage", "global", 15.0, "Skill Damage +15%"),
    MasteryNode("Intrepid Slash - Damage V", 88, 0, "skill_damage_pct", "intrepid_slash", 14.0, "Intrepid Slash Damage +14%"),
    MasteryNode("Rush - Reuse", 90, 0, "skill_cooldown_reduction", "rush", 6.6, "Rush Cooldown -30% (-6.6s of 22s base)"),
    MasteryNode("Intrepid Slash - Damage VI", 92, 0, "skill_damage_pct", "intrepid_slash", 15.0, "Intrepid Slash Damage +15%"),
    MasteryNode("Beam Blade - Strike I", 94, 0, "skill_hits", "beam_blade", 1.0, "Beam Blade +1 hit"),
    MasteryNode("Intrepid Slash - Strike I", 96, 0, "skill_hits", "intrepid_slash", 1.0, "Intrepid Slash +1 hit"),
    MasteryNode("Self Recovery - Attack", 98, 0, "final_damage", "global", 5.0, "Self Recovery +5% Final Damage at >=50% HP"),

    # ==========================================================================
    # 4th Job (Levels 102-138)
    # ==========================================================================
    MasteryNode("Raging Blow - Damage I", 102, 0, "skill_damage_pct", "raging_blow", 10.0, "Raging Blow Damage +10%"),
    MasteryNode("Beam Blade - Reuse", 104, 0, "skill_cooldown_reduction", "beam_blade", 4.8, "Beam Blade Cooldown -30% (-4.8s of 16s base)"),
    MasteryNode("Raging Blow - Damage II", 106, 0, "skill_damage_pct", "raging_blow", 11.0, "Raging Blow Damage +11%"),
    # Lvl 108 "Puncture - Damage": datamine targets Incising (14030).
    # "Puncture" = the Burn DoT + Weakness sub-effect of Incising. Wiki description appears mislabeled.
    MasteryNode("Puncture - Damage", 108, 0, "skill_damage_pct", "incising", 50.0, "Incising Damage +50% (wiki: 'Puncture')"),
    MasteryNode("Raging Blow - Boss Damage I", 111, 0, "skill_boss_damage", "raging_blow", 10.0, "Raging Blow Boss Damage +10%"),
    MasteryNode("Advanced Final Attack - Enhance", 113, 0, "skill_damage_pct", "final_attack_hero", 50.0, "Advanced Final Attack FD boost +50%"),
    MasteryNode("Raging Blow - Damage III", 116, 0, "skill_damage_pct", "raging_blow", 12.0, "Raging Blow Damage +12%"),
    # Lvl 118 Advanced Combo - Max Stacks +1: bundled into combo_attack baseline
    MasteryNode("Raging Blow - Damage IV", 120, 0, "skill_damage_pct", "raging_blow", 13.0, "Raging Blow Damage +13%"),
    # Lvl 122 "Enhanced Raging Blow - Damage": datamine targets ERB (14020).
    MasteryNode("Enhanced Raging Blow - Damage", 122, 0, "skill_damage_pct", "enhanced_raging_blow", 50.0, "Enhanced Raging Blow Damage +50%"),
    MasteryNode("Raging Blow - Boss Damage II", 124, 0, "skill_boss_damage", "raging_blow", 10.0, "Raging Blow Boss Damage +10%"),
    # Lvl 126 Magic Crash - Weaken: +10% damage taken during state (28s CD, 15s state = ~54% uptime ~+5.4% skill dmg)
    MasteryNode("Magic Crash - Weaken", 126, 0, "skill_damage", "global", 5.0, "Magic Crash +10% damage taken (54% uptime ~ +5% skill dmg)"),
    MasteryNode("Raging Blow - Damage V", 128, 0, "skill_damage_pct", "raging_blow", 14.0, "Raging Blow Damage +14%"),
    # Lvl 130 Advanced Combo - Defense Penetration: +1% per combo stack
    # Approximated assuming 5 avg stacks held = +5% def_pen → +5% boss damage (conservative)
    MasteryNode("Advanced Combo - Def Pen", 130, 0, "skill_boss_damage", "raging_blow", 5.0, "Advanced Combo +1% Def Pen per stack (~+5% boss dmg)"),
    MasteryNode("Raging Blow - Damage VI", 132, 0, "skill_damage_pct", "raging_blow", 15.0, "Raging Blow Damage +15%"),
    # Lvl 134 "Puncture - Weaken": datamine strengthens Incising's Weakness debuff (100 -> 500).
    # Modeled as a Boss Damage boost on Incising representing the def-pen amplification.
    MasteryNode("Puncture - Weaken", 134, 0, "skill_boss_damage", "incising", 40.0, "Incising Weakness debuff strengthened (~+40% boss dmg)"),
    MasteryNode("Raging Blow - Strike I", 136, 0, "skill_hits", "raging_blow", 1.0, "Raging Blow +1 hit"),
    # Lvl 138 ERB FD scales per excess combo stack via #EnhanceRagingBlow_Mastery formula.
    # ERB requires >=5 combo stacks to cast; avg ~7-8 stacks = 2-3 excess.
    # Approximated as +50% FD to enhanced_raging_blow.
    MasteryNode("Enhanced Raging Blow - FD per Stack", 138, 0, "skill_damage_pct", "enhanced_raging_blow", 50.0, "ERB FD scales per excess combo stack (~+50% avg)"),
]


# =============================================================================
# NIGHT LORD SKILLS
# =============================================================================

NIGHT_LORD_SKILLS: Dict[str, SkillData] = {
    # =========================================================================
    # Shared Beginner Skills
    # =========================================================================
    "nimble_feet": SkillData(
        name="Nimble Feet",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.BASIC,
        unlock_level=1,
        cooldown=60.0,
        duration=15.0,
        skill_bonuses={
            "attack_speed": (15.0, SkillGrowth.FLAT),
        },
    ),

    # =========================================================================
    # 1st Job Skills
    # =========================================================================
    "lucky_seven": SkillData(
        name="Lucky Seven",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FIRST,
        unlock_level=10,
        base_damage_pct=26.0,
        base_hits=2,
        base_targets=3,
        damage_per_level=0,  # Replaced by Shuriken Burst at 2nd job
    ),

    "haste": SkillData(
        name="Haste",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=15,
        skill_bonuses={
            "movement_speed": (10.0, SkillGrowth.INC10),  # 10% base, Lv91 → 19%
        },
    ),

    "dark_sight": SkillData(
        name="Dark Sight",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=20,
        cooldown=25.0,
        duration=8.0,
        skill_bonuses={
            "crit_rate": (5.0, SkillGrowth.INC5),    # Lv91 → 8.1%
            "attack_pct": (10.0, SkillGrowth.INC4),  # Lv91 → 13.6%
        },
    ),

    "thief_mastery": SkillData(
        name="Thief Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=10,
        skill_bonuses={
            "attack_speed": (5.0, SkillGrowth.INC3),  # Similar to Archer Mastery
        },
    ),

    # =========================================================================
    # 2nd Job Skills
    # =========================================================================
    "shuriken_burst": SkillData(
        name="Shuriken Burst",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.SECOND,
        unlock_level=30,
        base_damage_pct=40.0,
        base_hits=3,
        base_targets=5,
        damage_per_level=0,  # Replaced by Shuriken Challenge at 3rd job
    ),

    "gust_charm": SkillData(
        name="Gust Charm",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=35,
        base_damage_pct=400.0,
        base_hits=1,
        base_targets=6,
        damage_per_level=2.0,  # Lv127 → 654%
        cooldown=24.0,
    ),

    "agile_claws": SkillData(
        name="Agile Claws",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=33,
        skill_bonuses={
            "attack_speed": (4.0, SkillGrowth.INC5),  # 4% base, Lv127 → 6.9%
        },
    ),

    "physical_training": SkillData(
        name="Physical Training",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=38,
        skill_bonuses={
            "basic_attack_damage": (10.0, SkillGrowth.INC3),  # 10% base, Lv127 → 13.8%
        },
    ),

    "claw_mastery": SkillData(
        name="Claw Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=40,
        skill_bonuses={
            "min_dmg_mult": (15.0, SkillGrowth.INC3),  # 15% base, Lv127 → 20.7%
        },
    ),

    "mark_of_assassin": SkillData(
        name="Mark of Assassin",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=45,
        base_damage_pct=300.0,
        base_hits=1,
        base_targets=5,
        damage_per_level=1.20,  # Lv127 → 452.4%
        level_factor_index=21,  # Datamine: SkillIndex 93031
        proc_chance=1.0,  # 100% when hitting marked targets
        attack_interval=5.0,  # Marks every 5 seconds
    ),

    "critical_throw": SkillData(
        name="Critical Throw",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=48,
        skill_bonuses={
            "crit_rate": (5.0, SkillGrowth.INC3),     # 5% base, Lv127 → 8.2%
            "crit_damage": (10.0, SkillGrowth.INC3),  # 10% base, Lv127 → 13.8%
        },
    ),

    "shadow_surge": SkillData(
        name="Shadow Surge",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=50,
        cooldown=6.0,
        duration=0,  # Instant dash
    ),

    # =========================================================================
    # 3rd Job Skills
    # =========================================================================
    "shuriken_challenge": SkillData(
        name="Shuriken Challenge",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.THIRD,
        unlock_level=60,
        base_damage_pct=80.0,
        base_hits=5,
        base_targets=6,
        damage_per_level=0,  # Replaced by Showdown at 4th job
    ),

    "triple_throw": SkillData(
        name="Triple Throw",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=60,
        base_damage_pct=360.0,
        base_hits=3,
        base_targets=1,
        damage_per_level=1.80,  # Lv186 → 694.8%
        level_factor_index=12,  # Datamine: SkillIndex 93020
        cooldown=13.0,
    ),

    "shadow_partner": SkillData(
        name="Shadow Partner",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=60,
        base_damage_pct=84.0,  # Deals X% additional damage (buffed from 70%)
        base_hits=1,
        base_targets=1,
        damage_per_level=0.186,
        level_factor_index=21,  # INC4: 151.8% at L202 (verified)
        proc_chance=0.25,  # 25% chance
    ),

    "dark_flare": SkillData(
        name="Dark Flare",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=65,
        base_damage_pct=400.0,           # Datamine: 4000/10 (was 500% from wiki)
        base_hits=2,
        base_targets=5,
        damage_per_level=1.46,  # Lv186 → 772%
        level_factor_index=12,  # Datamine: SkillIndex 93041
        cooldown=45.0,
        duration=20.0,
        attack_interval=5.0,
        scales_with_attack_speed=False,
    ),

    "enveloping_darkness": SkillData(
        name="Enveloping Darkness",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=66,
        skill_bonuses={
            "boss_damage": (15.0, SkillGrowth.INC5),  # 15% base, Lv186 → 28%
        },
        scenario="boss",
    ),

    "venom": SkillData(
        name="Venom",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=70,
        base_damage_pct=50.0,
        base_hits=1,
        base_targets=1,
        damage_per_level=0.153,  # Lv186 → 78.4%
        proc_chance=0.30,  # 30% chance to poison
        duration=10.0,  # Poison lasts 10 seconds
        attack_interval=1.0,  # DoT ticks every 1 second
    ),

    "alchemic_adrenaline": SkillData(
        name="Alchemic Adrenaline",
        skill_type=SkillType.PASSIVE_BUFF,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=72,
        duration=10.0,  # Buff lasts 10 seconds
        skill_bonuses={
            "final_damage": (10.0, SkillGrowth.INC3),    # 10% base, Lv186 → 15.5%
            "attack_speed": (8.0, SkillGrowth.INC3),     # 8% base, Lv186 → 12.4%
        },
    ),

    "expert_throwing_star_handling": SkillData(
        name="Expert Throwing Star Handling",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=75,
        skill_bonuses={
            "attack_pct": (20.0, SkillGrowth.INC3),  # 20% base, Lv186 → 28%
        },
    ),

    # =========================================================================
    # 4th Job Skills
    # =========================================================================
    "showdown": SkillData(
        name="Showdown",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FOURTH,
        unlock_level=100,
        base_damage_pct=290.0,
        base_hits=5,
        base_targets=6,
        damage_per_level=1.16,  # Lv56 → 354.9%
        level_factor_index=21,  # Datamine: SkillIndex 94010
    ),

    "quad_star": SkillData(
        name="Quad Star",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=100,
        base_damage_pct=1150.0,
        base_hits=4,
        base_targets=1,
        damage_per_level=5.75,  # Lv56 → 1472%
        level_factor_index=12,  # Datamine: SkillIndex 94020
        cooldown=13.0,
        cast_time=0.70,                  # 21 frames @ 30 FPS (datamine: QuadrupleThrow)
    ),

    "sudden_raid": SkillData(
        name="Sudden Raid",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=103,
        base_damage_pct=1400.0,          # Datamine: 14000/10 (was 800% from wiki)
        base_hits=3,                     # Datamine: Values[2]=3 (was 8 from wiki)
        base_targets=8,                  # Datamine: MaxHitCount=8 (was 6 from wiki)
        damage_per_level=4.09,
        level_factor_index=12,           # Datamine: SkillIndex 94030
        cooldown=19.0,
        cast_time=1.30,                  # 39 frames @ 30 FPS (datamine: SuddenRaid)
        dot_damage_pct=360.0,            # Datamine: 3600/10 - same as Shadower (was missing)
        dot_duration=5.0,                # 5 seconds
        dot_interval=1.0,                # Once per second
    ),

    "shadow_shifter": SkillData(
        name="Shadow Shifter",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=115,
        cooldown=35.0,
        duration=15.0,
        skill_bonuses={
            "crit_rate": (8.0, SkillGrowth.INC4),     # 8% + 0.032%/level
            "crit_damage": (40.0, SkillGrowth.INC4),  # 40% + 0.161%/level
        },
    ),

    "toxic_venom": SkillData(
        name="Toxic Venom",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=105,
        skill_bonuses={
            "venom": (500.0, SkillGrowth.INC4),  # final_damage to Venom
        },
    ),

    "night_lords_mark": SkillData(
        name="Night Lord's Mark",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=110,
        skill_bonuses={
            "mark_of_assassin": (400.0, SkillGrowth.INC4),  # final_damage to Mark of Assassin
        },
    ),

    "claw_expert": SkillData(
        name="Claw Expert",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=120,
        skill_bonuses={
            "skill_damage": (15.0, SkillGrowth.INC3),  # Similar to Bow Expert
        },
    ),

    "dark_harmony": SkillData(
        name="Dark Harmony",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=125,
        skill_bonuses={
            "defense_pen": (10.0, SkillGrowth.INC3),
            "final_damage": (10.0, SkillGrowth.INC3),
        },
    ),

    "maple_hero": SkillData(
        name="Maple Hero",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=100,
        # Grants FD to Dark Flare, Venom, Shadow Partner, Gust Charm
        # Values from Lv56 screenshot: DF 57%, Venom 190%, SP 190%, GC 494%
        skill_bonuses={
            "dark_flare": (25, SkillGrowth.INC25),        # base 25%, at Lv56 → 57%
            "venom": (75, SkillGrowth.INC30),             # base 75%, at Lv56 → 190%
            "shadow_partner": (75, SkillGrowth.INC30),    # base 75%, at Lv56 → 190%
            "gust_charm": (200, SkillGrowth.INC25),       # base 200%, at Lv56 → 494%
        },
    ),

    "frailty_curse": SkillData(
        name="Frailty Curse",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=112,
        cooldown=60.0,
        duration=30.0,
        # Reduces enemies' critical resistance in range
        # Enhanced by mastery at level 113
    ),
}


# =============================================================================
# NIGHT LORD MASTERIES
# =============================================================================
# From wiki: https://idle.maplestorywiki.net/w/Night_Lord/Mastery

NIGHT_LORD_MASTERIES: List[MasteryNode] = [
    # =========================================================================
    # 1st Job Masteries (Levels 12-28)
    # =========================================================================
    MasteryNode("Lucky Seven - Damage", 12, 0, "skill_damage_pct", "lucky_seven", 15, "Lucky Seven damage +15%"),
    MasteryNode("Main Stat Enhancement", 14, 0, "main_stat_flat", "global", 30, "Main Stat +30"),
    MasteryNode("Lucky Seven - Target", 15, 0, "skill_targets", "lucky_seven", 1, "Lucky Seven max targets +1"),
    MasteryNode("Critical Rate Enhancement", 17, 0, "crit_rate", "global", 5, "Critical Rate +5%"),
    MasteryNode("Lucky Seven - Damage 2", 19, 0, "skill_damage_pct", "lucky_seven", 20, "Lucky Seven damage +20%"),
    MasteryNode("Haste - Speed", 21, 0, "movement_speed", "global", 5, "Haste Speed +5%p"),
    MasteryNode("Lucky Seven - Target 2", 22, 0, "skill_targets", "lucky_seven", 1, "Lucky Seven max targets +1"),
    MasteryNode("Dark Sight - Persistence", 24, 0, "skill_duration", "dark_sight", 0.5, "Dark Sight buff duration +50%"),
    MasteryNode("Lucky Seven - Damage 3", 26, 0, "skill_damage_pct", "lucky_seven", 20, "Lucky Seven damage +20%"),
    MasteryNode("Basic Attack Damage Enhancement", 28, 0, "basic_attack_damage", "global", 15, "Basic Attack Damage +15%"),

    # =========================================================================
    # 2nd Job Masteries (Levels 32-58)
    # =========================================================================
    MasteryNode("Shuriken Burst - Damage", 32, 0, "skill_damage_pct", "shuriken_burst", 15, "Shuriken Burst damage +15%"),
    MasteryNode("Accuracy Enhancement", 34, 0, "accuracy", "global", 5, "Accuracy +5"),
    MasteryNode("Shuriken Burst - Target", 37, 0, "skill_targets", "shuriken_burst", 1, "Shuriken Burst max targets +1"),
    MasteryNode("Gust Charm - Stun", 39, 0, "skill_effect", "gust_charm", 0.5, "Gust Charm stun duration +50%"),
    MasteryNode("Shuriken Burst - Damage 2", 42, 0, "skill_damage_pct", "shuriken_burst", 20, "Shuriken Burst damage +20%"),
    MasteryNode("Mark of Assassin - Damage", 44, 0, "skill_damage_pct", "mark_of_assassin", 50, "Mark of Assassin damage +50%"),
    MasteryNode("Shuriken Burst - Boss Damage", 47, 0, "skill_boss_damage", "shuriken_burst", 15, "Shuriken Burst Boss Damage +15%"),
    MasteryNode("Critical Throw - Critical", 49, 0, "crit_rate", "global", 8, "Critical Rate +8%p"),
    MasteryNode("Shuriken Burst - Damage 3", 52, 0, "skill_damage_pct", "shuriken_burst", 20, "Shuriken Burst damage +20%"),
    MasteryNode("Shadow Surge - Accelerate", 54, 0, "skill_effect", "shadow_surge", 50, "After Shadow Surge, Speed +50% for 3 sec"),
    MasteryNode("Shuriken Burst - Strike", 56, 0, "skill_hits", "shuriken_burst", 1, "Shuriken Burst hits +1"),
    MasteryNode("Max Damage Multiplier Enhancement", 58, 0, "max_dmg_mult", "global", 10, "Max Damage Multiplier +10%"),

    # =========================================================================
    # 3rd Job Masteries (Levels 62-98)
    # =========================================================================
    MasteryNode("Shuriken Challenge - Damage", 62, 0, "skill_damage_pct", "shuriken_challenge", 10, "Shuriken Challenge damage +10%"),
    MasteryNode("Basic Attack Target Enhancement", 64, 0, "basic_attack_targets", "global", 1, "Basic Attack Target +1"),
    MasteryNode("Shuriken Challenge - Damage 2", 66, 0, "skill_damage_pct", "shuriken_challenge", 11, "Shuriken Challenge damage +11%"),
    MasteryNode("Shadow Partner - Damage", 68, 0, "skill_damage_pct", "shadow_partner", 100, "Shadow Partner damage +100%"),
    MasteryNode("Shuriken Challenge - Boss Damage", 71, 0, "skill_boss_damage", "shuriken_challenge", 10, "Shuriken Challenge Boss Damage +10%"),
    MasteryNode("Triple Throw - Damage", 73, 0, "skill_damage_pct", "triple_throw", 100, "Triple Throw damage +100%"),
    MasteryNode("Shuriken Challenge - Damage 3", 76, 0, "skill_damage_pct", "shuriken_challenge", 12, "Shuriken Challenge damage +12%"),
    MasteryNode("Dark Flare - Strike", 78, 0, "skill_hits", "dark_flare", 1, "Dark Flare hits +1"),
    MasteryNode("Shuriken Challenge - Damage 4", 80, 0, "skill_damage_pct", "shuriken_challenge", 13, "Shuriken Challenge damage +13%"),
    MasteryNode("Venom - Weaken", 82, 0, "skill_effect", "venom", 12, "Venom target damage taken +12%"),
    MasteryNode("Shuriken Challenge - Boss Damage 2", 84, 0, "skill_boss_damage", "shuriken_challenge", 10, "Shuriken Challenge Boss Damage +10%"),
    MasteryNode("Skill Damage Enhancement", 86, 0, "skill_damage", "global", 15, "Skill Damage +15%"),
    MasteryNode("Shuriken Challenge - Damage 5", 88, 0, "skill_damage_pct", "shuriken_challenge", 14, "Shuriken Challenge damage +14%"),
    MasteryNode("Alchemic Adrenaline - Persistence", 90, 0, "skill_duration", "alchemic_adrenaline", 5, "Alchemic Adrenaline duration +5 sec"),
    MasteryNode("Shuriken Challenge - Damage 6", 92, 0, "skill_damage_pct", "shuriken_challenge", 15, "Shuriken Challenge damage +15%"),
    MasteryNode("Dark Flare - Reuse", 94, 0, "skill_cooldown_reduction", "dark_flare", 0.3, "Dark Flare cooldown -30%"),
    MasteryNode("Shuriken Challenge - Strike", 96, 0, "skill_hits", "shuriken_challenge", 1, "Shuriken Challenge hits +1"),
    MasteryNode("Venom - Chance", 98, 0, "skill_proc_chance", "venom", 10, "Venom activation chance +10%p"),

    # =========================================================================
    # 4th Job Masteries (Levels 102-138)
    # =========================================================================
    MasteryNode("Showdown - Damage", 102, 0, "skill_damage_pct", "showdown", 10, "Showdown damage +10%"),
    MasteryNode("Dark Flare - Strike Interval", 104, 0, "skill_attack_interval_pct", "dark_flare", -40, "Dark Flare strike interval -40%"),
    MasteryNode("Showdown - Damage 2", 106, 0, "skill_damage_pct", "showdown", 11, "Showdown damage +11%"),
    MasteryNode("Quad Star - Reuse", 108, 0, "skill_cooldown_reduction", "quad_star", 0.3, "Quad Star cooldown -30%"),
    MasteryNode("Showdown - Boss Damage", 111, 0, "skill_boss_damage", "showdown", 10, "Showdown Boss Damage +10%"),
    MasteryNode("Frailty Curse - Critical", 113, 0, "skill_effect", "frailty_curse", 10, "Frailty Curse decreases target Crit Resistance -10%"),
    MasteryNode("Showdown - Damage 3", 116, 0, "skill_damage_pct", "showdown", 12, "Showdown damage +12%"),
    MasteryNode("Shadow Shifter - Evasion", 118, 0, "skill_effect", "shadow_shifter", 100, "Shadow Shifter Attack boost +100%, Evasion +20 for 3 sec"),
    MasteryNode("Showdown - Damage 4", 120, 0, "skill_damage_pct", "showdown", 13, "Showdown damage +13%"),
    MasteryNode("Night Lord's Mark - Activation Interval", 122, 0, "skill_attack_interval", "mark_of_assassin", -1, "Mark of Assassin interval and duration -1 sec"),
    MasteryNode("Showdown - Boss Damage 2", 124, 0, "skill_boss_damage", "showdown", 10, "Showdown Boss Damage +10%"),
    MasteryNode("Sudden Raid - Damage", 126, 0, "skill_damage_pct", "sudden_raid", 50, "Sudden Raid damage +50%"),
    MasteryNode("Showdown - Damage 5", 128, 0, "skill_damage_pct", "showdown", 14, "Showdown damage +14%"),
    MasteryNode("Toxic Venom - Damage", 130, 0, "skill_damage_pct", "venom", 100, "Toxic Venom damage +100%"),
    MasteryNode("Showdown - Damage 6", 132, 0, "skill_damage_pct", "showdown", 15, "Showdown damage +15%"),
    MasteryNode("Quad Star - Damage", 134, 0, "skill_damage_pct", "quad_star", 50, "Quad Star damage +50%"),
    MasteryNode("Showdown - Strike", 136, 0, "skill_hits", "showdown", 1, "Showdown hits +1"),
    MasteryNode("Night Lord's Mark - Weaken", 138, 0, "skill_effect", "mark_of_assassin", 15, "Targets hit by Mark of Assassin take +15% damage for 4 sec"),
]


# =============================================================================
# MARKSMAN SKILLS
# =============================================================================

MARKSMAN_SKILLS: Dict[str, SkillData] = {
    # =========================================================================
    # Shared Beginner Skills
    # =========================================================================
    "nimble_feet": SkillData(
        name="Nimble Feet",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.BASIC,
        unlock_level=1,
        cooldown=60.0,
        duration=15.0,
        skill_bonuses={
            "attack_speed": (15.0, SkillGrowth.FLAT),
        },
    ),

    # =========================================================================
    # 1st Job Skills
    # =========================================================================
    "arrow_blow": SkillData(
        name="Arrow Blow",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FIRST,
        unlock_level=10,
        base_damage_pct=26.0,
        base_hits=2,
        base_targets=3,
        damage_per_level=0,  # Replaced by Piercing Arrow
    ),

    "critical_shot": SkillData(
        name="Critical Shot",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=15,
        skill_bonuses={
            "crit_rate": (5.0, SkillGrowth.INC3),
        },
    ),

    "archer_mastery": SkillData(
        name="Archer Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=10,
        skill_bonuses={
            "attack_speed": (5.0, SkillGrowth.INC3),
        },
    ),

    # =========================================================================
    # 2nd Job Skills
    # =========================================================================
    "piercing_arrow": SkillData(
        name="Piercing Arrow",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.SECOND,
        unlock_level=30,
        base_damage_pct=40.0,
        base_hits=3,
        base_targets=5,
        damage_per_level=0,  # Replaced by Piercing Arrow II
    ),

    "covering_fire": SkillData(
        name="Covering Fire",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=35,
        base_damage_pct=250.0,
        base_hits=3,
        base_targets=1,
        damage_per_level=1.26,
        level_factor_index=12,  # Datamine: SkillIndex 82020
        cooldown=19.0,
    ),

    "crossbow_acceleration": SkillData(
        name="Agile Crossbows",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=33,
        skill_bonuses={
            "attack_speed": (5.0, SkillGrowth.INC3),
        },
    ),

    "crossbow_mastery": SkillData(
        name="Crossbow Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=43,
        skill_bonuses={
            "min_dmg_mult": (15.0, SkillGrowth.INC3),
        },
    ),

    "soul_arrow": SkillData(
        name="Soul Arrow: Crossbow",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=45,
        skill_bonuses={
            "dex_flat": (50.0, SkillGrowth.INC10),
        },
    ),

    "final_attack": SkillData(
        name="Final Attack: Crossbow",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=50,
        base_damage_pct=35.0,
        base_hits=1,
        base_targets=1,
        damage_per_level=0.14,
        level_factor_index=21,  # Datamine: SkillIndex 82060
        proc_chance=0.25,
    ),

    "physical_training": SkillData(
        name="Physical Training",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=38,
        skill_bonuses={
            "basic_attack_damage": (10.0, SkillGrowth.INC3),
        },
    ),

    # =========================================================================
    # 3rd Job Skills
    # =========================================================================
    "piercing_arrow_2": SkillData(
        name="Piercing Arrow II",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.THIRD,
        unlock_level=60,
        base_damage_pct=80.0,
        base_hits=5,
        base_targets=6,
        damage_per_level=0,  # Replaced by Empowered Piercing Arrow at 4th job
    ),

    "bolt_burst": SkillData(
        name="Bolt Burst",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=66,
        base_damage_pct=380.0,
        base_hits=3,
        base_targets=10,
        damage_per_level=1.93,
        level_factor_index=12,  # Datamine: SkillIndex 83030
        cooldown=21.0,
    ),

    "frostprey": SkillData(
        name="Frostprey",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=69,
        base_damage_pct=600.0,
        base_hits=1,
        base_targets=3,
        damage_per_level=3.02,
        level_factor_index=12,  # Datamine: SkillIndex 83021
        cooldown=60.0,
        duration=20.0,
        attack_interval=3.0,
        cast_time=0.67,
        scales_with_attack_speed=False,
    ),

    "blink_bolt": SkillData(
        name="Blink Bolt",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=60,
        skill_bonuses={
            "attack_pct": (25.0, SkillGrowth.FLAT),  # Auto-cast buff, effectively 100% uptime
        },
    ),

    "extreme_archery": SkillData(
        name="Extreme Archery: Crossbow",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=75,
        skill_bonuses={
            "final_damage": (15.0, SkillGrowth.INC3),
        },
    ),

    "mortal_blow": SkillData(
        name="Mortal Blow",
        skill_type=SkillType.PASSIVE_BUFF,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=72,
        skill_bonuses={
            "final_damage": (10.0, SkillGrowth.INC3),
        },
    ),

    "concentration": SkillData(
        name="Concentration",
        skill_type=SkillType.PASSIVE_BUFF,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=63,
        skill_bonuses={
            "crit_damage": (3.0, SkillGrowth.INC3),
        },
    ),

    "marksmanship": SkillData(
        name="Marksmanship",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=74,
        skill_bonuses={
            "attack_pct": (20.0, SkillGrowth.INC3),
        },
        scenario="boss",  # Only active in single-target (boss) scenarios
    ),

    # =========================================================================
    # 4th Job Skills
    # =========================================================================
    "empowered_piercing_arrow": SkillData(
        name="Empowered Piercing Arrow",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FOURTH,
        unlock_level=100,
        base_damage_pct=290.0,
        base_hits=5,
        base_targets=6,
        damage_per_level=1.19,
        level_factor_index=21,  # Datamine: SkillIndex 84010
    ),

    "snipe": SkillData(
        name="Snipe",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=103,
        base_damage_pct=3800.0,
        base_hits=1,
        base_targets=1,
        damage_per_level=15.6,
        level_factor_index=12,           # Datamine: SkillIndex 84020
        cooldown=12.0,
        cast_time=1.0,                   # 30 frames @ 30 FPS
        # Empowered Snipe (L134 mastery 80285): mark target, 5700% follow-up every cast
        # Boss: fires every cast (mark → execute → re-mark). Mob: 0% (targets die before 2nd hit)
        finishing_blow_pct=5700.0,
        finishing_blow_interval=1,
        finishing_blow_factor_index=12,   # Datamine: SkillIndex 84022
        finishing_blow_unlock_level=134,
        finishing_blow_boss_only=True,
    ),

    "arrow_illusion": SkillData(
        name="Arrow Illusion",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=110,
        base_damage_pct=2400.0,
        base_hits=1,
        base_targets=10,
        damage_per_level=9.84,
        level_factor_index=12,           # Datamine: SkillIndex 84041
        cooldown=45.0,
        duration=25.0,
        attack_interval=3.0,
        cast_time=1.1,                   # 33 frames @ 30 FPS
        scales_with_attack_speed=False,
    ),

    "sharp_eyes": SkillData(
        name="Sharp Eyes",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=115,
        cooldown=35.0,
        duration=18.0,  # Patch: 15s → 18s
        skill_bonuses={
            "crit_damage": (40.0, SkillGrowth.INC4),  # Patch: crit_rate removed; self gets +40% + 20% of own CD
        },
        self_crit_damage_pct=20.0,
    ),

    "bolt_surplus": SkillData(
        name="Bolt Surplus",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=107,
        base_damage_pct=650.0,
        base_hits=2,
        base_targets=3,
        damage_per_level=2.67,
        level_factor_index=21,           # Datamine: SkillIndex 84050
        proc_chance=0.15,
    ),

    "advanced_final_attack": SkillData(
        name="Advanced Final Attack",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=105,
        skill_bonuses={
            "final_attack": (500.0, SkillGrowth.INC4),  # +500% FD to Final Attack: Crossbow
        },
    ),

    "maple_hero_mm": SkillData(
        name="Maple Hero",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=100,
        # Grants FD to Bolt Burst, Frostprey, Covering Fire (Datamine: 84100, factor 23)
        # Formula: int((base + per_level * level) * 10) / 10
        # Factor 23 = base * (1 + 0.05*level), so per_level = base/20
        skill_bonuses={
            "bolt_burst": (25.0, SkillGrowth.INC50),       # 25% base FD, +1.25% per level
            "frostprey": (30.0, SkillGrowth.INC50),         # 30% base FD, +1.5% per level
            "covering_fire": (100.0, SkillGrowth.INC50),    # 100% base FD, +5.0% per level
        },
    ),

    "illusion_step": SkillData(
        name="Illusion Step",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=117,
        duration=15.0,
        cooldown=24.0,  # Patch: 15s attack + 9s evasion (was 20s = 15+5)
        skill_bonuses={
            "attack_pct": (14.0, SkillGrowth.INC5),  # Patch: 10% → 14%
        },
    ),

    "crossbow_expert": SkillData(
        name="Crossbow Expert",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=120,
        skill_bonuses={
            "skill_damage": (15.0, SkillGrowth.INC3),
            "max_dmg_mult": (20.0, SkillGrowth.INC3),
        },
    ),

    "last_man_standing": SkillData(
        name="Last Man Standing",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=125,
        skill_bonuses={
            "final_damage": (15.0, SkillGrowth.INC3),
        },
    ),
}

# =============================================================================
# MARKSMAN MASTERIES
# =============================================================================

MARKSMAN_MASTERIES: List[MasteryNode] = [
    # =========================================================================
    # 1st Job Masteries (unlocked during levels 1-29)
    # =========================================================================

    # Skill-specific: Arrow Blow
    MasteryNode("Arrow Blow - Damage", 12, 0, "skill_damage_pct", "arrow_blow", 15, "Arrow Blow damage +15%"),
    MasteryNode("Arrow Blow - Target", 15, 0, "skill_targets", "arrow_blow", 1, "Arrow Blow max targets +1"),
    MasteryNode("Arrow Blow - Damage 2", 19, 0, "skill_damage_pct", "arrow_blow", 20, "Arrow Blow damage +20%"),
    MasteryNode("Arrow Blow - Target 2", 22, 0, "skill_targets", "arrow_blow", 1, "Arrow Blow max targets +1"),
    MasteryNode("Arrow Blow - Damage 3", 26, 0, "skill_damage_pct", "arrow_blow", 20, "Arrow Blow damage +20%"),

    # Global stats
    MasteryNode("Main Stat Enhancement", 14, 0, "main_stat_flat", "global", 30, "Main Stat +30"),
    MasteryNode("Critical Rate Enhancement", 17, 0, "crit_rate", "global", 5, "Critical Rate +5%"),
    MasteryNode("Archer Mastery - Speed", 21, 0, "attack_speed", "global", 5, "Attack Speed +5%"),
    MasteryNode("Critical Shot - Critical", 24, 0, "crit_rate", "global", 5, "Critical Rate +5%"),
    MasteryNode("Basic Attack Damage Enhancement", 28, 0, "basic_attack_damage", "global", 15, "Basic Attack Damage +15%"),

    # =========================================================================
    # 2nd Job Masteries (unlocked during levels 30-59)
    # =========================================================================

    # Skill-specific: Piercing Arrow
    MasteryNode("Piercing Arrow - Damage", 32, 0, "skill_damage_pct", "piercing_arrow", 15, "Piercing Arrow damage +15%"),
    MasteryNode("Piercing Arrow - Target", 37, 0, "skill_targets", "piercing_arrow", 1, "Piercing Arrow max targets +1"),
    MasteryNode("Piercing Arrow - Damage 2", 42, 0, "skill_damage_pct", "piercing_arrow", 20, "Piercing Arrow damage +20%"),
    MasteryNode("Piercing Arrow - Boss Damage", 47, 0, "skill_boss_damage", "piercing_arrow", 15, "Piercing Arrow Boss Damage +15%"),
    MasteryNode("Piercing Arrow - Damage 3", 52, 0, "skill_damage_pct", "piercing_arrow", 20, "Piercing Arrow damage +20%"),
    MasteryNode("Piercing Arrow - Strike", 56, 0, "skill_hits", "piercing_arrow", 1, "Piercing Arrow hits +1"),

    # Skill-specific: Covering Fire, Final Attack
    MasteryNode("Covering Fire - Damage", 39, 0, "skill_damage_pct", "covering_fire", 50, "Covering Fire damage +50%"),
    MasteryNode("Covering Fire - Stun", 49, 0, "skill_effect", "covering_fire", 1, "Stuns target for 1 sec"),
    MasteryNode("Final Attack - Damage", 54, 0, "skill_damage_pct", "final_attack", 50, "Final Attack damage +50%"),

    # Global stats
    MasteryNode("Accuracy Enhancement", 34, 0, "accuracy", "global", 5, "Accuracy +5"),
    MasteryNode("Max Damage Multiplier Enhancement", 58, 0, "max_dmg_mult", "global", 10, "Max Damage Multiplier +10%"),

    # =========================================================================
    # 3rd Job Masteries (unlocked during levels 60-99)
    # =========================================================================

    # Skill-specific: Piercing Arrow II
    MasteryNode("Piercing Arrow II - Damage", 62, 0, "skill_damage_pct", "piercing_arrow_2", 10, "Piercing Arrow II damage +10%"),
    MasteryNode("Piercing Arrow II - Damage 2", 66, 0, "skill_damage_pct", "piercing_arrow_2", 11, "Piercing Arrow II damage +11%"),
    MasteryNode("Piercing Arrow II - Boss Damage", 71, 0, "skill_boss_damage", "piercing_arrow_2", 10, "Piercing Arrow II Boss Damage +10%"),
    MasteryNode("Piercing Arrow II - Damage 3", 76, 0, "skill_damage_pct", "piercing_arrow_2", 12, "Piercing Arrow II damage +12%"),
    MasteryNode("Piercing Arrow II - Damage 4", 80, 4500, "skill_damage_pct", "piercing_arrow_2", 13, "Piercing Arrow II damage +13%"),
    MasteryNode("Piercing Arrow II - Boss Damage 2", 84, 5000, "skill_boss_damage", "piercing_arrow_2", 10, "Piercing Arrow II Boss Damage +10%"),
    MasteryNode("Piercing Arrow II - Damage 5", 88, 5500, "skill_damage_pct", "piercing_arrow_2", 14, "Piercing Arrow II damage +14%"),
    MasteryNode("Piercing Arrow II - Damage 6", 92, 6000, "skill_damage_pct", "piercing_arrow_2", 15, "Piercing Arrow II damage +15%"),
    MasteryNode("Piercing Arrow II - Strike", 96, 6500, "skill_hits", "piercing_arrow_2", 1, "Piercing Arrow II hits +1"),

    # Skill-specific: Bolt Burst, Frostprey
    MasteryNode("Bolt Burst - Damage", 68, 0, "skill_damage_pct", "bolt_burst", 50, "Bolt Burst damage +50%"),
    MasteryNode("Frostprey - Target", 78, 0, "skill_targets", "frostprey", 2, "Frostprey max targets +2"),
    MasteryNode("Frostprey - Damage", 82, 6750, "skill_damage_pct", "frostprey", 50, "Frostprey damage +50%"),

    # Skill-specific: Mortal Blow
    MasteryNode("Mortal Blow - Persistence", 90, 8250, "skill_duration", "mortal_blow", 5, "Mortal Blow duration +5 sec"),

    # Global stats
    MasteryNode("Basic Attack Target Enhancement", 64, 0, "basic_attack_targets", "global", 1, "Basic Attack Target +1"),
    MasteryNode("Skill Damage Enhancement", 86, 7500, "skill_damage", "global", 15, "Skill Damage +15%"),

    # =========================================================================
    # 4th Job Masteries (unlocked at level 100+)
    # =========================================================================

    # Skill-specific: Empowered Piercing Arrow
    MasteryNode("EPA - Damage", 102, 7000, "skill_damage_pct", "empowered_piercing_arrow", 10, "Empowered Piercing Arrow damage +10%"),
    MasteryNode("EPA - Damage 2", 106, 7500, "skill_damage_pct", "empowered_piercing_arrow", 11, "Empowered Piercing Arrow damage +11%"),
    MasteryNode("EPA - Boss Damage", 111, 8000, "skill_boss_damage", "empowered_piercing_arrow", 10, "Empowered Piercing Arrow Boss Damage +10%"),
    MasteryNode("EPA - Damage 3", 116, 8500, "skill_damage_pct", "empowered_piercing_arrow", 12, "Empowered Piercing Arrow damage +12%"),
    MasteryNode("EPA - Damage 4", 120, 9000, "skill_damage_pct", "empowered_piercing_arrow", 13, "Empowered Piercing Arrow damage +13%"),
    MasteryNode("EPA - Boss Damage 2", 124, 9500, "skill_boss_damage", "empowered_piercing_arrow", 10, "Empowered Piercing Arrow Boss Damage +10%"),
    MasteryNode("EPA - Damage 5", 128, 10000, "skill_damage_pct", "empowered_piercing_arrow", 14, "Empowered Piercing Arrow damage +14%"),
    MasteryNode("EPA - Damage 6", 132, 10500, "skill_damage_pct", "empowered_piercing_arrow", 15, "Empowered Piercing Arrow damage +15%"),
    MasteryNode("EPA - Strike", 136, 16000, "skill_hits", "empowered_piercing_arrow", 1, "Empowered Piercing Arrow hits +1"),

    # Skill-specific: Snipe, Bolt Surplus, Arrow Illusion
    MasteryNode("Snipe - Damage", 108, 11250, "skill_damage_pct", "snipe", 50, "Snipe damage +50%"),
    MasteryNode("Bolt Surplus - Damage", 122, 13500, "skill_damage_pct", "bolt_surplus", 50, "Bolt Surplus damage +50%"),
    MasteryNode("Arrow Illusion - Damage", 130, 15000, "skill_damage_pct", "arrow_illusion", 50, "Arrow Illusion damage +50%"),

    # Skill-specific: Frostprey cooldown
    MasteryNode("Frostprey - Reuse", 104, 10500, "skill_cooldown_reduction", "frostprey", 0.5, "Frostprey cooldown -50%"),

    # Skill-specific: Advanced Final Attack enhance
    MasteryNode("Advanced Final Attack - Enhance", 113, 12000, "skill_final_damage", "final_attack", 50, "Final Attack Final Damage +50%"),

    # Skill-specific: Sharp Eyes persistence
    MasteryNode("Sharp Eyes - Persistence", 126, 14250, "skill_duration", "sharp_eyes", 0.5, "Sharp Eyes duration +50%"),

    # Skill-specific: Illusion Step enhance
    MasteryNode("Illusion Step - Enhance", 118, 12750, "skill_effect", "illusion_step", 2, "Attack increase effect doubled"),

    # Skill-specific: Snipe - Empowered (L134)
    # Datamine 80285: ChangeSkill 84020→84021, UsePassiveSkill 84022 (5700% follow-up)
    # DPS effect handled by SkillData finishing_blow_unlock_level=134 + boss_only=True
    MasteryNode("Snipe - Empowered", 134, 15750, "skill_effect", "snipe", 1, "Marks targets; every Snipe on a marked boss deals +5700% follow-up"),

    # Skill-specific: Bolt Surplus - Strike & Target (L138)
    # Datamine 80295: Enables second hit operation on Bolt Surplus (5 additional hits, larger AoE)
    MasteryNode("Bolt Surplus - Strike & Target", 138, 16500, "skill_hits", "bolt_surplus", 5, "Bolt Surplus gains second strike (+5 hits)"),
]


# =============================================================================
# DARK KNIGHT SKILLS
# =============================================================================

DARK_KNIGHT_SKILLS: Dict[str, SkillData] = {
    # =========================================================================
    # 1st Job Skills (Warrior basics)
    # =========================================================================

    "slash_blast": SkillData(
        name="Slash Blast",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FIRST,
        unlock_level=10,
        base_damage_pct=26.0,
        base_hits=3,
        base_targets=2,                  # Datamine 31010 Values[2]=2 targets
        damage_per_level=0.11,
        level_factor_index=21,
    ),

    "iron_body": SkillData(
        name="Iron Body",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=10,
        skill_bonuses={
            "str_flat": (3.0, SkillGrowth.INC5),  # STR +30 raw / 10 = 3.0 base
        },
    ),

    # =========================================================================
    # 2nd Job Skills
    # =========================================================================

    "spear_sweep": SkillData(
        name="Spear Sweep",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.SECOND,
        unlock_level=30,
        base_damage_pct=40.0,
        base_hits=5,
        base_targets=3,                  # Datamine 32010 Values[2]=3 targets
        damage_per_level=0.16,
        level_factor_index=21,
    ),

    "evil_eye": SkillData(
        name="Evil Eye",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=35,
        base_damage_pct=70.0,           # Beholder attack: 700/10 = 70% per hit
        base_hits=6,
        base_targets=1,
        damage_per_level=0.29,
        level_factor_index=12,          # Datamine: SkillIndex 32021
        cooldown=999999,                # Permanent summon — always active
        duration=999999,
        attack_interval=3.0,            # Beholder attacks every 3 seconds
        cast_time=0,                    # No player action needed (auto-deploys)
        scales_with_attack_speed=False,
    ),

    "hyper_body": SkillData(
        name="Hyper Body",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=45,
        cooldown=30.0,
        duration=15.0,
        cast_time=0.67,                 # 20 frames @ 30 FPS
        skill_bonuses={
            "attack_pct": (12.0, SkillGrowth.INC3),  # Attack +120 raw / 10 = 12.0%, factor 21
        },
    ),

    "weapon_mastery": SkillData(
        name="Weapon Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=43,
        skill_bonuses={
            "min_dmg_mult": (15.0, SkillGrowth.INC3),  # MinDamageRatio +150 raw / 10 = 15.0%
        },
    ),

    "weapon_acceleration": SkillData(
        name="Weapon Acceleration",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=33,
        skill_bonuses={
            "attack_speed": (5.0, SkillGrowth.INC3),  # AttackSpeed +50 raw / 10 = 5.0%
        },
    ),

    "final_attack": SkillData(
        name="Final Attack",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=50,
        base_damage_pct=35.0,           # 350 raw / 10 = 35%
        base_hits=1,
        base_targets=1,
        damage_per_level=0.14,
        level_factor_index=21,          # Datamine: SkillIndex 32080
        proc_chance=0.25,               # TriggerRatio: 250 / 1000
    ),

    # =========================================================================
    # 3rd Job Skills
    # =========================================================================

    "la_mancha_spear": SkillData(
        name="La Mancha Spear",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.THIRD,
        unlock_level=60,
        base_damage_pct=80.0,           # 800 raw / 10 = 80%
        base_hits=6,
        base_targets=5,                  # Datamine 33010 Values[2]=5 targets
        damage_per_level=0.33,
        level_factor_index=21,
    ),

    "rush": SkillData(
        name="Rush",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=63,
        base_damage_pct=600.0,          # 6000 raw / 10 = 600%
        base_hits=12,                   # Datamine 33020 MaxHitCount=12
        base_targets=1,                 # Datamine 33020 Values[2]=1 (single target)
        damage_per_level=2.46,
        level_factor_index=12,          # Datamine: SkillIndex 33020
        cooldown=22.0,
        cast_time=1.0,                  # 30 frames @ 30 FPS
    ),

    "cross_over_chains": SkillData(
        name="Cross Over Chains",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=66,
        cooldown=30.0,
        duration=15.0,
        cast_time=0.8,                  # 24 frames @ 30 FPS
        skill_bonuses={
            "attack_pct": (15.0, SkillGrowth.INC3),  # Attack +150 raw / 10 = 15.0%, factor 21
        },
    ),

    "hex_of_evil_eye": SkillData(
        name="Hex of the Evil Eye",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=69,
        skill_bonuses={
            "attack_pct": (15.0, SkillGrowth.INC3),  # Attack +150 raw / 10 = 15.0%, factor 22
        },
    ),

    "lord_of_darkness": SkillData(
        name="Lord of Darkness",
        skill_type=SkillType.PASSIVE_BUFF,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=72,
        # 30% proc on attack, 2s ICD, 5s duration
        # Grants Crit Rate +8% and Crit Power +30%
        skill_bonuses={
            "crit_rate": (8.0, SkillGrowth.INC3),    # CriticalChance +80 raw / 10 = 8.0%
            "crit_damage": (30.0, SkillGrowth.INC3),  # CriticalPower +300 raw / 10 = 30.0%
        },
    ),

    "evil_eye_shock_enhance": SkillData(
        name="Evil Eye Shock Enhancement",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=75,
        # FinalDamage +1000 (raw) to Evil Eye attack (32021)
        # = +100% FD at base, factor 22
        skill_bonuses={
            "evil_eye": (100.0, SkillGrowth.INC3),
        },
    ),

    # =========================================================================
    # 4th Job Skills
    # =========================================================================

    "dark_impale": SkillData(
        name="Dark Impale",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FOURTH,
        unlock_level=100,
        base_damage_pct=290.0,          # 2900 raw / 10 = 290%
        base_hits=6,                    # Datamine 34010 MaxHitCount=6
        base_targets=5,                 # Datamine 34010 Values[2]=5 targets
        damage_per_level=1.19,
        level_factor_index=21,          # Datamine: SkillIndex 34010
    ),

    "gungnirs_descent": SkillData(
        name="Gungnir's Descent",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=103,
        base_damage_pct=1800.0,         # 18000 raw / 10 = 1800%
        base_hits=2,
        base_targets=2,                 # Datamine 34020 Values[2]=2 (small AoE around target)
        damage_per_level=7.38,
        level_factor_index=12,          # Datamine: SkillIndex 34020
        cooldown=13.0,
        cast_time=1.0,                  # 30 frames @ 30 FPS
    ),

    "dark_resonance": SkillData(
        name="Dark Resonance",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=115,
        cooldown=35.0,
        duration=20.0,
        cast_time=1.0,                  # 30 frames @ 30 FPS
        skill_bonuses={
            "attack_pct": (25.0, SkillGrowth.INC3),  # Attack +250 raw / 10 = 25.0%, factor 21
        },
    ),

    "magic_crash": SkillData(
        name="Magic Crash",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=117,
        base_damage_pct=4800.0,         # 48000 raw / 10 = 4800%
        base_hits=5,                    # Datamine 34040 MaxHitCount=5
        base_targets=1,                 # Datamine 34040 Values[2]=1 (single target nuke)
        damage_per_level=19.67,
        level_factor_index=12,          # Datamine: SkillIndex 34040
        cooldown=28.0,
        cast_time=1.4,                  # 42 frames @ 30 FPS
    ),

    "final_pact": SkillData(
        name="Final Pact",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=107,
        skill_bonuses={
            "final_damage": (10.0, SkillGrowth.INC3),  # FinalDamage +100 raw / 10 = 10.0%, factor 22
        },
    ),

    "revenge_of_evil_eye": SkillData(
        name="Revenge of the Evil Eye",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=110,
        base_damage_pct=650.0,          # 6500 raw / 10 = 650%
        base_hits=2,
        base_targets=1,
        damage_per_level=2.67,
        level_factor_index=12,          # Datamine: SkillIndex 34062
        proc_chance=1.0,                # 100% trigger on attack
        cooldown=5.0,                   # 5s ICD (BeholderRevenge_Off state)
    ),

    "power_stance": SkillData(
        name="Power Stance",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=125,
        skill_bonuses={
            "final_damage": (15.0, SkillGrowth.INC3),  # FinalDamage +150 raw / 10 = 15.0%, factor 22
        },
    ),

    "advanced_final_attack": SkillData(
        name="Advanced Final Attack",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=105,
        skill_bonuses={
            "final_attack": (500.0, SkillGrowth.INC4),  # FinalDamage +5000 raw to FA, factor 21
        },
    ),

    "barricade_mastery": SkillData(
        name="Barricade Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=120,
        skill_bonuses={
            "skill_damage": (15.0, SkillGrowth.INC3),    # SkillPower +150 raw / 10 = 15.0%
            "max_dmg_mult": (20.0, SkillGrowth.INC3),    # MaxDamageRatio +200 raw / 10 = 20.0%
        },
    ),

    "maple_hero_dk": SkillData(
        name="Maple Hero",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=100,
        # FD boosts to sub-skills (factor 23)
        skill_bonuses={
            "evil_eye": (40.0, SkillGrowth.INC40),    # FD +400 raw to Evil Eye of Dominant attack
            "rush": (30.0, SkillGrowth.INC50),        # FD +300 raw to Rush
        },
    ),
}

# =============================================================================
# DARK KNIGHT MASTERIES
# =============================================================================

DARK_KNIGHT_MASTERIES: List[MasteryNode] = [
    # =========================================================================
    # 1st Job Masteries (unlocked during levels 10-28)
    # =========================================================================

    # Skill-specific: Slash Blast
    MasteryNode("Slash Blast - Damage", 12, 200, "skill_damage_pct", "slash_blast", 15, "Slash Blast damage +15%"),
    MasteryNode("Slash Blast - Target", 15, 400, "skill_targets", "slash_blast", 1, "Slash Blast max targets +1"),
    MasteryNode("Slash Blast - Damage 2", 19, 600, "skill_damage_pct", "slash_blast", 20, "Slash Blast damage +20%"),
    MasteryNode("Slash Blast - Target 2", 22, 800, "skill_targets", "slash_blast", 1, "Slash Blast max targets +1"),
    MasteryNode("Slash Blast - Damage 3", 26, 1000, "skill_damage_pct", "slash_blast", 20, "Slash Blast damage +20%"),

    # Global stats
    MasteryNode("Main Stat Enhancement", 10, 0, "main_stat_flat", "global", 30, "Main Stat +30"),
    MasteryNode("Critical Rate Enhancement", 16, 0, "crit_rate", "global", 5, "Critical Rate +5%"),
    MasteryNode("Weapon Acceleration - Speed", 20, 0, "attack_speed", "global", 5, "Attack Speed +5%"),
    MasteryNode("Critical Rate Enhancement 2", 24, 0, "crit_rate", "global", 5, "Critical Rate +5%"),
    MasteryNode("Basic Attack Damage Enhancement", 28, 0, "basic_attack_damage", "global", 15, "Basic Attack Damage +15%"),

    # =========================================================================
    # 2nd Job Masteries (unlocked during levels 30-56)
    # =========================================================================

    # Skill-specific: Spear Sweep
    MasteryNode("Spear Sweep - Damage", 32, 1100, "skill_damage_pct", "spear_sweep", 15, "Spear Sweep damage +15%"),
    MasteryNode("Spear Sweep - Target", 37, 1200, "skill_targets", "spear_sweep", 1, "Spear Sweep max targets +1"),
    MasteryNode("Spear Sweep - Damage 2", 42, 1400, "skill_damage_pct", "spear_sweep", 20, "Spear Sweep damage +20%"),
    MasteryNode("Spear Sweep - Boss Damage", 47, 1600, "skill_boss_damage", "spear_sweep", 15, "Spear Sweep Boss Damage +15%"),
    MasteryNode("Spear Sweep - Damage 3", 52, 1800, "skill_damage_pct", "spear_sweep", 20, "Spear Sweep damage +20%"),
    MasteryNode("Spear Sweep - Strike", 56, 2000, "skill_hits", "spear_sweep", 1, "Spear Sweep hits +1"),

    # Skill-specific: Final Attack
    MasteryNode("Final Attack - Damage", 48, 0, "skill_damage_pct", "final_attack", 50, "Final Attack damage +50%"),

    # Global stats
    MasteryNode("Accuracy Enhancement", 32, 0, "accuracy", "global", 5, "Accuracy +5"),
    MasteryNode("Max Damage Multiplier Enhancement", 52, 0, "max_dmg_mult", "global", 10, "Max Damage Multiplier +10%"),

    # =========================================================================
    # 3rd Job Masteries (unlocked during levels 60-96)
    # =========================================================================

    # Skill-specific: La Mancha Spear
    MasteryNode("La Mancha Spear - Damage", 62, 2500, "skill_damage_pct", "la_mancha_spear", 10, "La Mancha Spear damage +10%"),
    MasteryNode("La Mancha Spear - Damage 2", 66, 3000, "skill_damage_pct", "la_mancha_spear", 11, "La Mancha Spear damage +11%"),
    MasteryNode("La Mancha Spear - Boss Damage", 71, 3500, "skill_boss_damage", "la_mancha_spear", 10, "La Mancha Spear Boss Damage +10%"),
    MasteryNode("La Mancha Spear - Damage 3", 76, 4000, "skill_damage_pct", "la_mancha_spear", 12, "La Mancha Spear damage +12%"),
    MasteryNode("La Mancha Spear - Damage 4", 80, 4500, "skill_damage_pct", "la_mancha_spear", 13, "La Mancha Spear damage +13%"),
    MasteryNode("La Mancha Spear - Boss Damage 2", 84, 5000, "skill_boss_damage", "la_mancha_spear", 10, "La Mancha Spear Boss Damage +10%"),
    MasteryNode("La Mancha Spear - Damage 5", 88, 5500, "skill_damage_pct", "la_mancha_spear", 14, "La Mancha Spear damage +14%"),
    MasteryNode("La Mancha Spear - Damage 6", 92, 6000, "skill_damage_pct", "la_mancha_spear", 15, "La Mancha Spear damage +15%"),
    MasteryNode("La Mancha Spear - Strike", 96, 6500, "skill_hits", "la_mancha_spear", 1, "La Mancha Spear hits +1"),

    # Global stats
    MasteryNode("Basic Attack Target Enhancement", 62, 0, "basic_attack_targets", "global", 1, "Basic Attack Target +1"),
    MasteryNode("Skill Damage Enhancement", 86, 7500, "skill_damage", "global", 15, "Skill Damage +15%"),

    # =========================================================================
    # 4th Job Masteries (unlocked during levels 100-138)
    # =========================================================================

    # Skill-specific: Dark Impale (main path)
    MasteryNode("Dark Impale - Damage", 102, 7000, "skill_damage_pct", "dark_impale", 10, "Dark Impale damage +10%"),
    MasteryNode("Dark Impale - Damage 2", 106, 7500, "skill_damage_pct", "dark_impale", 11, "Dark Impale damage +11%"),
    MasteryNode("Dark Impale - Boss Damage", 111, 8000, "skill_boss_damage", "dark_impale", 10, "Dark Impale Boss Damage +10%"),
    MasteryNode("Dark Impale - Damage 3", 116, 8500, "skill_damage_pct", "dark_impale", 12, "Dark Impale damage +12%"),
    MasteryNode("Dark Impale - Damage 4", 120, 9000, "skill_damage_pct", "dark_impale", 13, "Dark Impale damage +13%"),
    MasteryNode("Dark Impale - Boss Damage 2", 124, 9500, "skill_boss_damage", "dark_impale", 10, "Dark Impale Boss Damage +10%"),
    MasteryNode("Dark Impale - Damage 5", 128, 10000, "skill_damage_pct", "dark_impale", 14, "Dark Impale damage +14%"),
    MasteryNode("Dark Impale - Damage 6", 132, 10500, "skill_damage_pct", "dark_impale", 15, "Dark Impale damage +15%"),

    # -------------------------------------------------------------------------
    # Secondary path masteries (from datamine 30105-30295)
    # -------------------------------------------------------------------------

    # Final Attack FD boost
    MasteryNode("Final Attack - Damage 2", 54, 2700, "skill_final_damage", "final_attack", 50, "Final Attack Final Damage +50%"),

    # Global: Max Damage Multiplier
    MasteryNode("Max Damage Multiplier Enhancement 2", 58, 3000, "max_dmg_mult", "global", 10, "Max Damage Multiplier +10%"),

    # Basic Attack hit count
    MasteryNode("Basic Attack Hit Count Enhancement", 64, 3750, "basic_attack_hits", "global", 1, "Basic Attack Hits +1"),

    # Rush FD boost
    MasteryNode("Rush - Damage", 68, 4500, "skill_final_damage", "rush", 80, "Rush Final Damage +80%"),

    # Cross Over Chains buff enhancement
    MasteryNode("Cross Over Chains - Attack", 73, 5250, "skill_effect", "cross_over_chains", 100, "Cross Over Chains Attack buff +100%"),

    # Evil Eye FD boost
    MasteryNode("Evil Eye of Dominant - Damage", 78, 6000, "skill_final_damage", "evil_eye", 50, "Evil Eye Final Damage +50%"),

    # Hex accuracy
    MasteryNode("Hex of Evil Eye - Accuracy", 82, 6750, "accuracy", "global", 5, "Accuracy +5"),

    # Global: Skill Power
    MasteryNode("Skill Power Enhancement", 86, 7500, "skill_damage", "global", 15, "Skill Damage +15%"),

    # Rush CD reduction
    MasteryNode("Rush - Reuse", 90, 8250, "skill_cooldown_reduction", "rush", 0.3, "Rush cooldown -30%"),

    # Evil Eye targets
    MasteryNode("Evil Eye of Dominant - Target", 94, 9000, "skill_targets", "evil_eye", 3, "Evil Eye max targets +3"),

    # Hex attack buff enhancement
    MasteryNode("Hex of Evil Eye - Attack", 98, 9750, "skill_effect", "hex_of_evil_eye", 50, "Hex of Evil Eye Attack buff +50%"),

    # Evil Eye CD reduction
    MasteryNode("Evil Eye - Reuse", 104, 10500, "skill_cooldown_reduction", "evil_eye", 0.3, "Evil Eye cooldown -30%"),

    # Gungnir's Descent FD boost
    MasteryNode("Gungnir's Descent - Damage", 108, 11250, "skill_final_damage", "gungnirs_descent", 50, "Gungnir's Descent Final Damage +50%"),

    # Advanced Final Attack enhance
    MasteryNode("Advanced Final Attack - Enhance", 113, 12000, "skill_final_damage", "final_attack", 50, "Final Attack Final Damage +50%"),

    # Revenge of Evil Eye FD boost
    MasteryNode("Revenge of Evil Eye - Damage", 122, 13500, "skill_final_damage", "revenge_of_evil_eye", 50, "Revenge of Evil Eye Final Damage +50%"),

    # Dark Resonance persistence
    MasteryNode("Dark Resonance - Persistence", 130, 15000, "skill_duration", "dark_resonance", 0.4, "Dark Resonance duration +40%"),

    # Gungnir's Descent Strike — converts 1800%×2 to 900%×6
    MasteryNode("Gungnir's Descent - Strike (Hits)", 134, 15750, "skill_hits", "gungnirs_descent", 4, "Gungnir's Descent hits +4 (total 6)"),
    MasteryNode("Gungnir's Descent - Strike (Adjust)", 134, 0, "skill_damage_pct", "gungnirs_descent", -50, "Gungnir's Descent per-hit damage adjusted for 6-hit pattern"),
]


# =============================================================================
# SHADOWER SKILLS
# =============================================================================

SHADOWER_SKILLS: Dict[str, SkillData] = {
    # =========================================================================
    # Shared Beginner Skills
    # =========================================================================
    "nimble_feet": SkillData(
        name="Nimble Feet",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.BASIC,
        unlock_level=1,
        cooldown=60.0,
        duration=15.0,
        skill_bonuses={
            "attack_speed": (15.0, SkillGrowth.FLAT),
        },
    ),

    # =========================================================================
    # 1st Job Skills
    # =========================================================================
    "double_stab": SkillData(
        name="Double Stab",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FIRST,
        unlock_level=10,
        base_damage_pct=26.0,
        base_hits=2,
        base_targets=3,
        damage_per_level=0,  # Replaced by Savage Blow at 2nd job
    ),

    "haste": SkillData(
        name="Haste",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=10,
        skill_bonuses={
            "movement_speed": (15.0, SkillGrowth.INC3),
        },
    ),

    "dark_sight": SkillData(
        name="Dark Sight",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=15,
        cooldown=25.0,
        duration=8.0,
        skill_bonuses={
            "crit_rate": (6.0, SkillGrowth.INC4),
            "attack_pct": (10.0, SkillGrowth.INC4),
        },
    ),

    # =========================================================================
    # 2nd Job Skills
    # =========================================================================
    "savage_blow": SkillData(
        name="Savage Blow",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.SECOND,
        unlock_level=30,
        base_damage_pct=40.0,
        base_hits=3,
        base_targets=5,
        damage_per_level=0,  # Replaced by Midnight Carnival at 3rd job
    ),

    "steal": SkillData(
        name="Steal",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=35,
        base_damage_pct=0,
        base_hits=0,
        base_targets=1,
        proc_chance=0.10,  # 10% chance
        duration=5.0,  # Buff lasts 5 sec
        # Decreases target attack by 10%, increases own attack by 5% (stacks x3)
        skill_bonuses={
            "attack_pct": (5.0, SkillGrowth.INC3),  # 5% base per stack, scales with level
        },
    ),

    "agile_daggers": SkillData(
        name="Agile Daggers",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=33,
        skill_bonuses={
            "attack_speed": (5.0, SkillGrowth.INC3),
        },
    ),

    "physical_training": SkillData(
        name="Physical Training",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=38,
        skill_bonuses={
            "basic_attack_damage": (10.0, SkillGrowth.INC3),
        },
    ),

    "dagger_mastery": SkillData(
        name="Dagger Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=43,
        skill_bonuses={
            "min_dmg_mult": (15.0, SkillGrowth.INC3),
        },
    ),

    "channel_karma": SkillData(
        name="Channel Karma",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=40,
        skill_bonuses={
            "attack_pct": (8.0, SkillGrowth.INC3),
        },
    ),

    "critical_edge": SkillData(
        name="Critical Edge",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=50,
        skill_bonuses={
            "crit_rate": (6.0, SkillGrowth.INC3),
            "crit_damage": (10.0, SkillGrowth.INC3),
        },
    ),

    "shield_mastery": SkillData(
        name="Shield Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=45,
        stat_conversion=("defense", "main_stat_flat", (10.0, 0.030)),
    ),

    # =========================================================================
    # 3rd Job Skills
    # =========================================================================
    "midnight_carnival": SkillData(
        name="Midnight Carnival",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.THIRD,
        unlock_level=60,
        base_damage_pct=80.0,
        base_hits=5,
        base_targets=6,
        damage_per_level=0,  # Replaced by Cruel Stab at 4th job
    ),

    "phase_dash": SkillData(
        name="Phase Dash",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=63,
        base_damage_pct=450.0,
        base_hits=2,
        base_targets=7,
        damage_per_level=2.0,
        level_factor_index=12,           # Datamine: SkillIndex 103020
        cooldown=23.0,                   # Datamine: 23000ms (was 20s from wiki)
    ),

    "meso_explosion": SkillData(
        name="Meso Explosion",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=66,
        base_damage_pct=270.0,
        base_hits=3,
        base_targets=10,  # max targets = max stacks
        damage_per_level=1.0,
        level_factor_index=12,           # Datamine: SkillIndex 103030
        proc_chance=0.50,  # 50% base generation chance per target hit
        cooldown=11.0,  # Explosion cooldown
        max_stacks=10,  # Max meso stacks
        scales_with_attack_speed=False,
    ),

    "dark_flare": SkillData(
        name="Dark Flare",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=69,
        base_damage_pct=400.0,
        base_hits=2,
        base_targets=5,
        damage_per_level=1.46,
        level_factor_index=12,           # Datamine: SkillIndex 103041
        cooldown=45.0,
        duration=20.0,
        attack_interval=5.0,
        scales_with_attack_speed=False,
    ),

    "shadow_partner": SkillData(
        name="Shadow Partner",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=60,
        base_damage_pct=84.0,  # Buffed from 60%
        base_hits=1,
        base_targets=1,
        damage_per_level=0.186,
        level_factor_index=21,  # INC4: 151.8% at L202 (verified)
        proc_chance=0.25,  # 25% chance
    ),

    "venom": SkillData(
        name="Venom",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=72,
        base_damage_pct=45.0,
        base_hits=1,
        base_targets=1,
        damage_per_level=0.153,
        level_factor_index=21,  # INC4: 81.3% at L202 (verified)
        proc_chance=0.30,  # 30% chance to poison
        duration=10.0,  # Poison lasts 10 seconds
        attack_interval=1.0,  # DoT ticks every 1 second
    ),

    "into_darkness": SkillData(
        name="Into Darkness",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=74,
        cooldown=30.0,
        duration=13.0,
        skill_bonuses={
            "final_damage": (20.0, SkillGrowth.INC4),
        },
    ),

    "meso_mastery": SkillData(
        name="Meso Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=75,
        proc_chance_modifier={"meso_explosion": (25.0, 0.0)},  # +25%p to meso generation
        skill_bonuses={
            "attack_pct": (25.0, SkillGrowth.INC3),  # +25% attack when meso generated (near 100% uptime)
        },
    ),

    # =========================================================================
    # 4th Job Skills
    # =========================================================================
    "cruel_stab": SkillData(
        name="Cruel Stab",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FOURTH,
        unlock_level=100,
        base_damage_pct=290.0,
        base_hits=5,
        base_targets=6,
        damage_per_level=1.16,
        level_factor_index=21,           # Datamine: SkillIndex 104010
    ),

    "assassinate": SkillData(
        name="Assassinate",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=103,
        base_damage_pct=1400.0,
        base_hits=2,
        base_targets=1,
        damage_per_level=5.75,
        level_factor_index=21,           # Datamine: SkillIndex 104020
        cooldown=13.0,
        cast_time=0.73,                  # 22 frames @ 30 FPS (datamine: Assassination)
        finishing_blow_pct=3000.0,       # +3000% line every 3rd use
        finishing_blow_interval=3,
        finishing_blow_factor_index=12,  # Datamine: SkillIndex 104021
    ),

    "sudden_raid": SkillData(
        name="Sudden Raid",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=105,
        base_damage_pct=1400.0,
        base_hits=3,
        base_targets=8,
        damage_per_level=4.09,
        level_factor_index=12,           # Datamine: SkillIndex 104030
        cooldown=19.0,
        cast_time=1.30,                  # 39 frames @ 30 FPS (datamine: SuddenRaid)
        dot_damage_pct=360.0,            # 360% per tick
        dot_duration=5.0,                # 5 seconds
        dot_interval=1.0,                # Once per second
    ),

    "blood_money": SkillData(
        name="Blood Money",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=107,
        base_damage_pct=2800.0,
        base_hits=1,
        base_targets=5,  # max targets = max stacks
        level_factor_index=12,

        proc_chance=0.50,  # 50% of meso stacks become blood money
        cooldown=11.0,  # Triggers alongside meso explosion
        max_stacks=5,  # Max blood money stacks
        stack_source="meso_explosion",  # Chains off meso generation
        single_target_stack_bonus=0.05,  # +5% final dmg per stack in boss phase
        scales_with_attack_speed=False,
    ),

    "smokescreen": SkillData(
        name="Smokescreen",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=110,
        cooldown=45.0,                   # Datamine: 45000ms (was 60s from wiki)
        duration=20.0,
        cast_time=0.83,                  # 25 frames @ 30 FPS (datamine: SmokeShell)
        skill_bonuses={
            "final_damage": (13.0, SkillGrowth.INC3),  # Verified: 19.3% @ L164, 18.2% @ L134
            "def_pen": (7.0, SkillGrowth.INC3),         # Verified: 10.4% @ L164, 9.8% @ L134
        },
    ),

    "shadow_shifter": SkillData(
        name="Shadow Shifter",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=115,
        base_damage_pct=2500.0,          # Counterattack damage
        base_hits=1,
        base_targets=1,
        level_factor_index=21,           # INC4: 4080% at L158 (verified)
        cooldown=12.0,                   # 12s ICD
        scales_with_attack_speed=False,
        skill_bonuses={
            "final_damage": (10.0, SkillGrowth.INC3),  # +10% FD (was attack%; changed in patch)
        },
        buff_downtime=3.0,               # Buff suppressed for 3s after trigger (was 4s)
    ),

    "toxic_venom": SkillData(
        name="Toxic Venom",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=117,
        base_damage_pct=600.0,
        base_hits=1,
        base_targets=1,
        damage_per_level=2.0,
        level_factor_index=21,  # INC4: 979.2% at L158 (verified)
        proc_chance=0.20,  # 20% chance on venom-afflicted targets
    ),

    "dagger_expert": SkillData(
        name="Dagger Expert",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=120,
        skill_bonuses={
            "skill_damage": (15.0, SkillGrowth.INC3),
            "max_dmg_mult": (20.0, SkillGrowth.INC3),
        },
    ),

    "shadower_instinct": SkillData(
        name="Shadower Instinct",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=125,
        skill_bonuses={
            "final_damage": (20.0, SkillGrowth.INC3),
        },
    ),

    "maple_hero": SkillData(
        name="Maple Hero",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=100,
        # Increases Final Damage: Dark Flare 15%, Venom 50%, Shadow Partner 50%, Phase Dash 40%
        skill_bonuses={
            "dark_flare": (15, SkillGrowth.INC50),
            "venom": (50, SkillGrowth.INC50),
            "shadow_partner": (50, SkillGrowth.INC50),
            "phase_dash": (40, SkillGrowth.INC50),
        },
    ),
}


# =============================================================================
# SHADOWER MASTERIES
# =============================================================================
# From wiki: https://idle.maplestorywiki.net/w/Shadower/Mastery

SHADOWER_MASTERIES: List[MasteryNode] = [
    # =========================================================================
    # 1st Job Masteries (Levels 12-28)
    # =========================================================================
    MasteryNode("Double Stab - Damage", 12, 0, "skill_damage_pct", "double_stab", 15, "Double Stab damage +15%"),
    MasteryNode("Main Stat Enhancement", 14, 0, "main_stat_flat", "global", 30, "Main Stat +30"),
    MasteryNode("Double Stab - Target", 15, 0, "skill_targets", "double_stab", 1, "Double Stab max targets +1"),
    MasteryNode("Critical Rate Enhancement", 17, 0, "crit_rate", "global", 5, "Critical Rate +5%"),
    MasteryNode("Double Stab - Damage 2", 19, 0, "skill_damage_pct", "double_stab", 20, "Double Stab damage +20%"),
    MasteryNode("Haste - Speed", 21, 0, "movement_speed", "global", 5, "Haste Speed +5%p"),
    MasteryNode("Double Stab - Target 2", 22, 0, "skill_targets", "double_stab", 1, "Double Stab max targets +1"),
    MasteryNode("Dark Sight - Persistence", 24, 0, "skill_duration", "dark_sight", 0.5, "Dark Sight buff duration +50%"),
    MasteryNode("Double Stab - Damage 3", 26, 0, "skill_damage_pct", "double_stab", 20, "Double Stab damage +20%"),
    MasteryNode("Basic Attack Damage Enhancement", 28, 0, "basic_attack_damage", "global", 15, "Basic Attack Damage +15%"),

    # =========================================================================
    # 2nd Job Masteries (Levels 32-58)
    # =========================================================================
    MasteryNode("Savage Blow - Damage", 32, 0, "skill_damage_pct", "savage_blow", 15, "Savage Blow damage +15%"),
    MasteryNode("Accuracy Enhancement", 34, 0, "accuracy", "global", 5, "Accuracy +5"),
    MasteryNode("Savage Blow - Target", 37, 0, "skill_targets", "savage_blow", 1, "Savage Blow max targets +1"),
    MasteryNode("Steal - Chance", 39, 0, "skill_proc_chance", "steal", 5, "Steal activation chance +5%p"),
    MasteryNode("Savage Blow - Damage 2", 42, 0, "skill_damage_pct", "savage_blow", 20, "Savage Blow damage +20%"),
    MasteryNode("Agile Daggers - Speed", 44, 0, "attack_speed", "global", 7, "Agile Daggers Attack Speed +7%p"),
    MasteryNode("Savage Blow - Boss Damage", 47, 0, "skill_boss_damage", "savage_blow", 15, "Savage Blow Boss Damage +15%"),
    MasteryNode("Dagger Mastery - Critical", 49, 0, "crit_rate", "global", 8, "Dagger Mastery Critical Rate +8%p"),
    MasteryNode("Savage Blow - Damage 3", 52, 0, "skill_damage_pct", "savage_blow", 20, "Savage Blow damage +20%"),
    MasteryNode("Steal - Weaken", 54, 0, "skill_effect", "steal", 50, "Steal target Attack reduction +50%"),
    MasteryNode("Savage Blow - Strike", 56, 0, "skill_hits", "savage_blow", 1, "Savage Blow hits +1"),
    MasteryNode("Max Damage Multiplier Enhancement", 58, 0, "max_dmg_mult", "global", 10, "Max Damage Multiplier +10%"),

    # =========================================================================
    # 3rd Job Masteries (Levels 62-98)
    # =========================================================================
    MasteryNode("Midnight Carnival - Damage", 62, 0, "skill_damage_pct", "midnight_carnival", 10, "Midnight Carnival damage +10%"),
    MasteryNode("Basic Attack Target Enhancement", 64, 0, "basic_attack_targets", "global", 1, "Basic Attack Target +1"),
    MasteryNode("Midnight Carnival - Damage 2", 66, 0, "skill_damage_pct", "midnight_carnival", 11, "Midnight Carnival damage +11%"),
    MasteryNode("Shadow Partner - Damage", 68, 0, "skill_damage_pct", "shadow_partner", 100, "Shadow Partner damage +100%"),
    MasteryNode("Midnight Carnival - Boss Damage", 71, 0, "skill_boss_damage", "midnight_carnival", 10, "Midnight Carnival Boss Damage +10%"),
    MasteryNode("Phase Dash - Damage", 73, 0, "skill_damage_pct", "phase_dash", 80, "Phase Dash damage +80%"),
    MasteryNode("Midnight Carnival - Damage 3", 76, 0, "skill_damage_pct", "midnight_carnival", 12, "Midnight Carnival damage +12%"),
    MasteryNode("Dark Flare - Strike", 78, 0, "skill_hits", "dark_flare", 1, "Dark Flare hits +1"),
    MasteryNode("Midnight Carnival - Damage 4", 80, 0, "skill_damage_pct", "midnight_carnival", 13, "Midnight Carnival damage +13%"),
    MasteryNode("Venom - Weaken", 82, 0, "skill_effect", "venom", 12, "Venom target damage taken +12%"),
    MasteryNode("Midnight Carnival - Boss Damage 2", 84, 0, "skill_boss_damage", "midnight_carnival", 10, "Midnight Carnival Boss Damage +10%"),
    MasteryNode("Skill Damage Enhancement", 86, 0, "skill_damage", "global", 15, "Skill Damage +15%"),
    MasteryNode("Midnight Carnival - Damage 5", 88, 0, "skill_damage_pct", "midnight_carnival", 14, "Midnight Carnival damage +14%"),
    MasteryNode("Meso Explosion - Damage", 90, 0, "skill_damage_pct", "meso_explosion", 100, "Meso Explosion damage +100%"),
    MasteryNode("Midnight Carnival - Damage 6", 92, 0, "skill_damage_pct", "midnight_carnival", 15, "Midnight Carnival damage +15%"),
    MasteryNode("Dark Flare - Reuse", 94, 0, "skill_cooldown_reduction", "dark_flare", 0.3, "Dark Flare cooldown -30%"),
    MasteryNode("Midnight Carnival - Strike", 96, 0, "skill_hits", "midnight_carnival", 1, "Midnight Carnival hits +1"),
    MasteryNode("Venom - Chance", 98, 0, "skill_proc_chance", "venom", 10, "Venom activation chance +10%p"),

    # =========================================================================
    # 4th Job Masteries (Levels 102-138)
    # =========================================================================
    MasteryNode("Cruel Stab - Damage", 102, 0, "skill_damage_pct", "cruel_stab", 10, "Cruel Stab damage +10%"),
    MasteryNode("Dark Flare - Strike Interval", 104, 0, "skill_attack_interval_pct", "dark_flare", -40, "Dark Flare strike interval -40%"),
    MasteryNode("Cruel Stab - Damage 2", 106, 0, "skill_damage_pct", "cruel_stab", 11, "Cruel Stab damage +11%"),
    MasteryNode("Assassinate - Murderous Intent", 108, 0, "skill_finishing_blow_pct", "assassinate", 100, "After Blood Money, doubles Assassinate finishing blow"),
    MasteryNode("Cruel Stab - Boss Damage", 111, 0, "skill_boss_damage", "cruel_stab", 10, "Cruel Stab Boss Damage +10%"),
    MasteryNode("Smokescreen - Critical", 113, 0, "skill_effect", "smokescreen", 30, "Smokescreen: Crit Resist -10%, allied Crit Damage +30%"),
    MasteryNode("Cruel Stab - Damage 3", 116, 0, "skill_damage_pct", "cruel_stab", 12, "Cruel Stab damage +12%"),
    MasteryNode("Shadow Shifter - Final Damage", 118, 0, "skill_final_damage", "shadow_shifter", 10, "Shadow Shifter Final Damage +10%p"),
    MasteryNode("Cruel Stab - Damage 4", 120, 0, "skill_damage_pct", "cruel_stab", 13, "Cruel Stab damage +13%"),
    MasteryNode("Blood Money - Target", 122, 0, "skill_damage_pct", "blood_money", 100, "Blood Money damage +100%"),
    MasteryNode("Cruel Stab - Boss Damage 2", 124, 0, "skill_boss_damage", "cruel_stab", 10, "Cruel Stab Boss Damage +10%"),
    MasteryNode("Sudden Raid - Damage", 126, 0, "skill_damage_pct", "sudden_raid", 50, "Sudden Raid damage +50%"),
    MasteryNode("Cruel Stab - Damage 5", 128, 0, "skill_damage_pct", "cruel_stab", 14, "Cruel Stab damage +14%"),
    MasteryNode("Toxic Venom - Damage", 130, 0, "skill_damage_pct", "toxic_venom", 100, "Toxic Venom damage +100%"),
    MasteryNode("Cruel Stab - Damage 6", 132, 0, "skill_damage_pct", "cruel_stab", 15, "Cruel Stab damage +15%"),
    MasteryNode("Assassinate - Damage", 134, 0, "skill_damage_pct", "assassinate", 50, "Assassinate damage +50%"),
    MasteryNode("Cruel Stab - Strike", 136, 0, "skill_hits", "cruel_stab", 1, "Cruel Stab hits +1"),
    MasteryNode("Blood Money - Damage", 138, 0, "skill_effect", "blood_money", 100, "Doubles Blood Money stack count"),
]


# =============================================================================
# BUCCANEER SKILLS
# =============================================================================

BUCCANEER_SKILLS: Dict[str, SkillData] = {
    # =========================================================================
    # Shared Beginner Skills
    # =========================================================================
    "nimble_feet": SkillData(
        name="Nimble Feet",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.BASIC,
        unlock_level=1,
        cooldown=60.0,
        duration=15.0,
        skill_bonuses={"attack_speed": (15.0, SkillGrowth.FLAT)},
    ),
    "quick_motion": SkillData(
        name="Quick Motion",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.BASIC,
        unlock_level=1,
        skill_bonuses={"attack_speed": (6.0, SkillGrowth.INC3)},
    ),

    # =========================================================================
    # 1st Job Skills
    # =========================================================================
    "somersault_kick": SkillData(
        name="Somersault Kick",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FIRST,
        unlock_level=10,
        base_damage_pct=26.0,
        base_hits=2,
        base_targets=3,
    ),
    "shadow_heart": SkillData(
        name="Shadow Heart",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=10,
        skill_bonuses={"crit_rate": (5.0, SkillGrowth.INC3)},
    ),

    # =========================================================================
    # 2nd Job Skills
    # =========================================================================
    "shotgun_punch": SkillData(
        name="Shotgun Punch",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.SECOND,
        unlock_level=30,
        base_damage_pct=40.0,
        base_hits=3,
        base_targets=5,
    ),
    "sea_serpent_burst": SkillData(
        name="Sea Serpent Burst",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=35,
        base_damage_pct=130.0,
        base_hits=2,
        base_targets=5,
        proc_chance=0.40,   # 40% chance on Basic Attack
    ),
    "agile_knuckles": SkillData(
        name="Agile Knuckles",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=30,
        skill_bonuses={"attack_speed": (5.0, SkillGrowth.INC3)},
    ),
    "dark_clarity": SkillData(
        name="Dark Clarity",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=40,
        skill_bonuses={"attack_pct": (12.0, SkillGrowth.INC3)},
    ),
    "knuckle_mastery": SkillData(
        name="Knuckle Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=35,
        skill_bonuses={"min_dmg_mult": (15.0, SkillGrowth.INC3)},
    ),
    "physical_training": SkillData(
        name="Physical Training",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=45,
        skill_bonuses={"basic_attack_damage": (10.0, SkillGrowth.INC3)},
    ),

    # =========================================================================
    # 3rd Job Skills
    # =========================================================================
    "turning_kick": SkillData(
        name="Turning Kick",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.THIRD,
        unlock_level=60,
        base_damage_pct=80.0,
        base_hits=5,
        base_targets=6,
    ),
    "corkscrew_blow": SkillData(
        name="Corkscrew Blow",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=65,
        base_damage_pct=340.0,
        base_hits=2,
        base_targets=7,
        cooldown=25.0,
        level_factor_index=21,  # INC4
    ),
    "serpent_scale": SkillData(
        name="Serpent Scale",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=70,
        cooldown=11.0,   # ~90% uptime: 10s assault / (10s + ~1s stack build) cycle
        duration=10.0,
        skill_bonuses={"final_damage": (25.0, SkillGrowth.INC4)},
    ),

    # =========================================================================
    # 4th Job Skills
    # =========================================================================
    "hook_bomber": SkillData(
        name="Hook Bomber",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FOURTH,
        unlock_level=100,
        base_damage_pct=290.0,
        base_hits=5,
        base_targets=6,
    ),
    "groggy_mastery": SkillData(
        name="Groggy Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=100,
        skill_bonuses={"damage_pct": (25.0, SkillGrowth.INC3)},
    ),
    "roll_of_the_dice": SkillData(
        name="Roll of the Dice",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=105,
        # +20% base attack + avg ~1.8% from dice roll (2.5% × 5/7 uptime)
        skill_bonuses={"attack_pct": (22.0, SkillGrowth.INC3)},
    ),
    "octopunch": SkillData(
        name="Octopunch",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=105,
        base_damage_pct=900.0,
        base_hits=3,
        base_targets=4,
        cooldown=20.0,
        level_factor_index=21,  # INC4
    ),
    "nautilus_strike": SkillData(
        name="Nautilus Strike",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=110,
        base_damage_pct=1950.0,
        base_hits=5,
        base_targets=15,
        cooldown=60.0,
        level_factor_index=21,  # INC4
    ),
    "crossbones": SkillData(
        name="Crossbones",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=115,
        cooldown=30.0,
        duration=12.0,
        skill_bonuses={
            "final_damage": (10.0, SkillGrowth.INC3),
            "def_pen": (5.0, SkillGrowth.INC3),
        },
    ),
    "speed_infusion": SkillData(
        name="Speed Infusion",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=115,
        cooldown=45.0,
        duration=15.0,
        skill_bonuses={
            "attack_speed": (20.0, SkillGrowth.INC3),
            "final_damage": (20.0, SkillGrowth.INC3),
        },
    ),
    "time_leap": SkillData(
        name="Time Leap",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=120,
        cooldown=120.0,
        duration=40.0,
        # CD reduction on active skills modelled as +30% FD for simplicity
        skill_bonuses={"final_damage": (30.0, SkillGrowth.INC4)},
    ),
    "sea_serpents_rage": SkillData(
        name="Sea Serpent's Rage",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=120,
        base_damage_pct=1700.0,
        base_hits=2,
        base_targets=8,
        cooldown=20.0,   # Fires every Octopunch cycle
        level_factor_index=21,  # INC4
    ),
    "raging_serpent_assault": SkillData(
        name="Raging Serpent Assault",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=125,
        base_damage_pct=1300.0,
        base_hits=2,
        base_targets=9,
        # 5 attacks per 5s burst, triggered every ~25s (Octopunch CD) → avg: 5/25 = fire every 5s
        attack_interval=5.0,
        level_factor_index=21,  # INC4
    ),
    "maple_hero_bucc": SkillData(
        name="Maple Hero",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=130,
        skill_bonuses={
            "sea_serpent_burst": (60.0, SkillGrowth.INC25),
            "corkscrew_blow":    (40.0, SkillGrowth.INC20),
        },
    ),
}


BUCCANEER_MASTERIES: List[MasteryNode] = [
    # =========================================================================
    # 1st Job Masteries (Levels 28-30)
    # =========================================================================
    MasteryNode("Basic Attack Damage Enhancement", 28, 0, "basic_attack_damage", "global", 15, "Basic Attack Damage +15%"),

    # =========================================================================
    # 2nd Job Masteries (Levels 32-58)
    # =========================================================================
    MasteryNode("Shotgun Punch - Damage", 32, 0, "skill_damage_pct", "shotgun_punch", 15, "Shotgun Punch damage +15%"),
    MasteryNode("Shotgun Punch - Target", 36, 0, "skill_targets", "shotgun_punch", 1, "Shotgun Punch max targets +1"),
    MasteryNode("Knuckle Mastery - Critical", 38, 0, "crit_rate", "global", 8, "Knuckle Mastery Critical Rate +8%p"),
    MasteryNode("Shotgun Punch - Damage 2", 42, 0, "skill_damage_pct", "shotgun_punch", 20, "Shotgun Punch damage +20%"),
    MasteryNode("Agile Knuckles - Speed", 46, 0, "attack_speed", "global", 7, "Agile Knuckles Attack Speed +7%p"),
    MasteryNode("Shotgun Punch - Boss Damage", 49, 0, "skill_boss_damage", "shotgun_punch", 15, "Shotgun Punch Boss Damage +15%"),
    MasteryNode("Shotgun Punch - Damage 3", 56, 0, "skill_damage_pct", "shotgun_punch", 20, "Shotgun Punch damage +20%"),
    MasteryNode("Max Damage Multiplier Enhancement", 58, 0, "max_dmg_mult", "global", 10, "Max Damage Multiplier +10%"),

    # =========================================================================
    # 3rd Job Masteries (Levels 62-98)
    # =========================================================================
    MasteryNode("Turning Kick - Damage", 62, 0, "skill_damage_pct", "turning_kick", 10, "Turning Kick damage +10%"),
    MasteryNode("Basic Attack Target Enhancement", 64, 0, "basic_attack_targets", "global", 1, "Basic Attack Target +1"),
    MasteryNode("Turning Kick - Damage 2", 66, 0, "skill_damage_pct", "turning_kick", 11, "Turning Kick damage +11%"),
    MasteryNode("Corkscrew Blow - Damage", 70, 0, "skill_damage_pct", "corkscrew_blow", 40, "Corkscrew Blow damage +40%"),
    MasteryNode("Turning Kick - Boss Damage", 71, 0, "skill_boss_damage", "turning_kick", 10, "Turning Kick Boss Damage +10%"),
    MasteryNode("Sea Serpent Burst - Damage", 76, 0, "skill_damage_pct", "sea_serpent_burst", 300, "Greater Sea Serpent I: Sea Serpent Burst damage changes to 430%"),
    MasteryNode("Sea Serpent Burst - Target", 78, 0, "skill_targets", "sea_serpent_burst", 2, "Greater Sea Serpent I: Sea Serpent Burst max targets +2"),
    MasteryNode("Corkscrew Blow - Boss Damage", 80, 0, "skill_boss_damage", "corkscrew_blow", 15, "Corkscrew Blow Boss Damage +15%"),
    MasteryNode("Skill Damage Enhancement", 86, 0, "skill_damage", "global", 15, "Skill Damage +15%"),
    MasteryNode("Corkscrew Blow - Strike", 88, 0, "skill_hits", "corkscrew_blow", 1, "Corkscrew Blow hits +1"),
    MasteryNode("Turning Kick - Strike", 96, 0, "skill_hits", "turning_kick", 1, "Turning Kick hits +1"),

    # =========================================================================
    # 4th Job Masteries (Levels 102-138)
    # =========================================================================
    MasteryNode("Hook Bomber - Damage", 102, 0, "skill_damage_pct", "hook_bomber", 10, "Hook Bomber damage +10%"),
    MasteryNode("Sea Serpent Burst - Final Damage", 104, 0, "skill_final_damage", "sea_serpent_burst", 100, "Greater Sea Serpent II: Sea Serpent Burst Final Damage +100%"),
    MasteryNode("Hook Bomber - Damage 2", 106, 0, "skill_damage_pct", "hook_bomber", 11, "Hook Bomber damage +11%"),
    MasteryNode("Sea Serpent Burst - Hits", 108, 0, "skill_hits", "sea_serpent_burst", 1, "Serpent Assault: Sea Serpent Burst hits +1"),
    MasteryNode("Hook Bomber - Boss Damage", 111, 0, "skill_boss_damage", "hook_bomber", 10, "Hook Bomber Boss Damage +10%"),
    MasteryNode("Sea Serpent Burst - Targets 2", 113, 0, "skill_targets", "sea_serpent_burst", 5, "Serpent Assault: Sea Serpent Burst max targets +5"),
    MasteryNode("Hook Bomber - Damage 3", 116, 0, "skill_damage_pct", "hook_bomber", 12, "Hook Bomber damage +12%"),
    MasteryNode("Hook Bomber - Damage 4", 120, 0, "skill_damage_pct", "hook_bomber", 13, "Hook Bomber damage +13%"),
    MasteryNode("Sea Serpent Burst - Damage 2", 124, 0, "skill_damage_pct", "sea_serpent_burst", 50, "Serpent Assault damage boost"),
    MasteryNode("Octopunch - Damage", 126, 0, "skill_damage_pct", "octopunch", 50, "Octopunch damage +50%"),
    MasteryNode("Hook Bomber - Damage 5", 128, 0, "skill_damage_pct", "hook_bomber", 14, "Hook Bomber damage +14%"),
    MasteryNode("Nautilus Strike - Damage", 130, 0, "skill_damage_pct", "nautilus_strike", 50, "Nautilus Strike damage +50%"),
    MasteryNode("Hook Bomber - Damage 6", 132, 0, "skill_damage_pct", "hook_bomber", 15, "Hook Bomber damage +15%"),
    MasteryNode("Octopunch - Boss Damage", 134, 0, "skill_boss_damage", "octopunch", 30, "Octopunch Boss Damage +30%"),
    MasteryNode("Hook Bomber - Strike", 136, 0, "skill_hits", "hook_bomber", 1, "Hook Bomber hits +1"),
    MasteryNode("Sea Serpents Rage - Damage", 138, 0, "skill_damage_pct", "sea_serpents_rage", 50, "Sea Serpent's Rage damage +50%"),
]


# =============================================================================
# CORSAIR SKILLS
# =============================================================================

CORSAIR_SKILLS: Dict[str, SkillData] = {
    # =========================================================================
    # Shared Beginner Skills
    # =========================================================================
    "nimble_feet": SkillData(
        name="Nimble Feet",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.BASIC,
        unlock_level=1,
        cooldown=60.0,
        duration=15.0,
        skill_bonuses={"attack_speed": (15.0, SkillGrowth.FLAT)},
    ),
    "quick_motion": SkillData(
        name="Quick Motion",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.BASIC,
        unlock_level=1,
        skill_bonuses={"attack_speed": (6.0, SkillGrowth.INC3)},
    ),

    # =========================================================================
    # 1st Job Skills
    # =========================================================================
    "double_shot": SkillData(
        name="Double Shot",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FIRST,
        unlock_level=10,
        base_damage_pct=26.0,
        base_hits=2,
        base_targets=3,
    ),
    "shadow_heart": SkillData(
        name="Shadow Heart",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=10,
        skill_bonuses={"crit_rate": (5.0, SkillGrowth.INC3)},
    ),

    # =========================================================================
    # 2nd Job Skills
    # =========================================================================
    "rapid_blast": SkillData(
        name="Rapid Blast",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.SECOND,
        unlock_level=30,
        base_damage_pct=40.0,
        base_hits=3,
        base_targets=5,
    ),
    "swift_fire": SkillData(
        name="Swift Fire",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=35,
        base_damage_pct=180.0,
        base_hits=3,
        base_targets=1,
        cooldown=15.0,
        level_factor_index=22,  # INC3
    ),
    "scurvy_summons": SkillData(
        name="Scurvy Summons",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=35,
        base_damage_pct=95.0,
        base_hits=2,
        base_targets=1,
        # 20s duration / 30s CD = ~67% uptime → effective interval = 3s / 0.67 = 4.5s
        attack_interval=4.5,
        level_factor_index=22,  # INC3
    ),
    "agile_guns": SkillData(
        name="Agile Guns",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=30,
        skill_bonuses={"attack_speed": (5.0, SkillGrowth.INC3)},
    ),
    "gun_mastery": SkillData(
        name="Gun Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=35,
        skill_bonuses={"min_dmg_mult": (15.0, SkillGrowth.INC3)},
    ),
    "physical_training": SkillData(
        name="Physical Training",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=45,
        skill_bonuses={"basic_attack_damage": (10.0, SkillGrowth.INC3)},
    ),
    "infinity_blast": SkillData(
        name="Infinity Blast",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=40,
        skill_bonuses={"attack_pct": (10.0, SkillGrowth.INC3)},
    ),

    # =========================================================================
    # 3rd Job Skills
    # =========================================================================
    "blunderbuster": SkillData(
        name="Blunderbuster",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.THIRD,
        unlock_level=60,
        base_damage_pct=80.0,
        base_hits=5,
        base_targets=6,
    ),
    "blackboot_bill": SkillData(
        name="Blackboot Bill",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=65,
        base_damage_pct=170.0,
        base_hits=4,
        base_targets=6,
        cooldown=20.0,
        level_factor_index=22,  # INC3
    ),
    "siege_bomber": SkillData(
        name="Siege Bomber",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=70,
        base_damage_pct=290.0,
        base_hits=1,
        base_targets=4,
        # 30s duration / 40s CD = 75% uptime → effective interval = 2.5s / 0.75 = 3.33s
        attack_interval=3.33,
        level_factor_index=22,  # INC3
    ),
    "all_aboard": SkillData(
        name="All Aboard",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=74,
        base_damage_pct=190.0,
        base_hits=3,
        base_targets=3,
        # Sharpshooter Crew fires every 4s, same 67% uptime as Scurvy Summons → 4.0s / 0.67 = 6.0s
        attack_interval=6.0,
        level_factor_index=22,  # INC3
    ),

    # =========================================================================
    # 4th Job Skills
    # =========================================================================
    "eight_legs_easton": SkillData(
        name="Eight-Legs Easton",
        skill_type=SkillType.BASIC_ATTACK,
        damage_type=DamageType.BASIC,
        job=Job.FOURTH,
        unlock_level=100,
        base_damage_pct=290.0,
        base_hits=5,
        base_targets=6,
    ),
    "fullmetal_jacket": SkillData(
        name="Fullmetal Jacket",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=100,
        skill_bonuses={"crit_damage": (10.0, SkillGrowth.INC3)},
    ),
    "roll_of_the_dice": SkillData(
        name="Roll of the Dice",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=105,
        skill_bonuses={"attack_pct": (22.0, SkillGrowth.INC3)},
    ),
    "cross_cut_blast": SkillData(
        name="Cross Cut Blast",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=100,
        skill_bonuses={"final_damage": (10.0, SkillGrowth.INC3)},
    ),
    "brain_scrambler": SkillData(
        name="Brain Scrambler",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=105,
        base_damage_pct=2900.0,
        base_hits=2,
        base_targets=1,
        cooldown=20.0,
        level_factor_index=21,  # INC4
    ),
    "nautilus_strike": SkillData(
        name="Nautilus Strike",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=110,
        base_damage_pct=1950.0,
        base_hits=5,
        base_targets=15,
        cooldown=60.0,
        level_factor_index=21,  # INC4
    ),
    "rapid_fire": SkillData(
        name="Rapid Fire",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=110,
        base_damage_pct=1350.0,
        base_hits=7,
        base_targets=1,
        cooldown=20.0,
        level_factor_index=21,  # INC4
    ),
    "broadside": SkillData(
        name="Broadside",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=115,
        base_damage_pct=3300.0,
        base_hits=2,
        base_targets=5,
        # 30s duration / 60s CD = 50% uptime → effective interval = 2.0s / 0.5 = 4.0s
        attack_interval=4.0,
        level_factor_index=21,  # INC4
    ),
    "jolly_roger": SkillData(
        name="Jolly Roger",
        skill_type=SkillType.BUFF,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=115,
        cooldown=30.0,
        duration=18.0,
        skill_bonuses={"final_damage": (18.0, SkillGrowth.INC4)},
    ),
    "quickdraw": SkillData(
        name="Quickdraw",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=120,
        skill_bonuses={"basic_attack_damage": (25.0, SkillGrowth.INC3)},
    ),
    "majestic_presence": SkillData(
        name="Majestic Presence",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=120,
        base_damage_pct=1800.0,
        base_hits=1,
        base_targets=1,
        proc_chance=0.25,
        level_factor_index=21,  # INC4
    ),
    "ahoy_mateys": SkillData(
        name="Ahoy Mateys",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=125,
        skill_bonuses={
            "scurvy_summons": (250.0, SkillGrowth.INC25),
            "all_aboard":     (100.0, SkillGrowth.INC25),
        },
    ),
    "maple_hero_corsair": SkillData(
        name="Maple Hero",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=130,
        skill_bonuses={
            "siege_bomber":    (20.0, SkillGrowth.INC20),
            "blackboot_bill":  (40.0, SkillGrowth.INC20),
            "swift_fire":      (80.0, SkillGrowth.INC25),
        },
    ),
}


CORSAIR_MASTERIES: List[MasteryNode] = [
    # =========================================================================
    # 1st Job Masteries (Levels 28-30)
    # =========================================================================
    MasteryNode("Basic Attack Damage Enhancement", 28, 0, "basic_attack_damage", "global", 15, "Basic Attack Damage +15%"),

    # =========================================================================
    # 2nd Job Masteries (Levels 32-58)
    # =========================================================================
    MasteryNode("Rapid Blast - Damage", 32, 0, "skill_damage_pct", "rapid_blast", 15, "Rapid Blast damage +15%"),
    MasteryNode("Rapid Blast - Target", 36, 0, "skill_targets", "rapid_blast", 1, "Rapid Blast max targets +1"),
    MasteryNode("Gun Mastery - Critical", 38, 0, "crit_rate", "global", 8, "Gun Mastery Critical Rate +8%p"),
    MasteryNode("Scurvy Summons - Damage", 40, 0, "skill_damage_pct", "scurvy_summons", 30, "Scurvy Summons damage +30%"),
    MasteryNode("Rapid Blast - Damage 2", 44, 0, "skill_damage_pct", "rapid_blast", 20, "Rapid Blast damage +20%"),
    MasteryNode("Agile Guns - Speed", 46, 0, "attack_speed", "global", 7, "Agile Guns Attack Speed +7%p"),
    MasteryNode("Rapid Blast - Boss Damage", 49, 0, "skill_boss_damage", "rapid_blast", 15, "Rapid Blast Boss Damage +15%"),
    MasteryNode("Rapid Blast - Damage 3", 56, 0, "skill_damage_pct", "rapid_blast", 20, "Rapid Blast damage +20%"),
    MasteryNode("Max Damage Multiplier Enhancement", 58, 0, "max_dmg_mult", "global", 10, "Max Damage Multiplier +10%"),

    # =========================================================================
    # 3rd Job Masteries (Levels 62-98)
    # =========================================================================
    MasteryNode("Blunderbuster - Damage", 62, 0, "skill_damage_pct", "blunderbuster", 10, "Blunderbuster damage +10%"),
    MasteryNode("Basic Attack Target Enhancement", 64, 0, "basic_attack_targets", "global", 1, "Basic Attack Target +1"),
    MasteryNode("Blunderbuster - Damage 2", 66, 0, "skill_damage_pct", "blunderbuster", 11, "Blunderbuster damage +11%"),
    MasteryNode("Blackboot Bill - Damage", 70, 0, "skill_damage_pct", "blackboot_bill", 40, "Blackboot Bill damage +40%"),
    MasteryNode("Blunderbuster - Boss Damage", 71, 0, "skill_boss_damage", "blunderbuster", 10, "Blunderbuster Boss Damage +10%"),
    MasteryNode("Siege Bomber - Damage", 76, 0, "skill_damage_pct", "siege_bomber", 50, "Siege Bomber damage +50%"),
    MasteryNode("Blackboot Bill - Boss Damage", 80, 0, "skill_boss_damage", "blackboot_bill", 15, "Blackboot Bill Boss Damage +15%"),
    MasteryNode("Skill Damage Enhancement", 86, 0, "skill_damage", "global", 15, "Skill Damage +15%"),
    MasteryNode("Blunderbuster - Strike", 96, 0, "skill_hits", "blunderbuster", 1, "Blunderbuster hits +1"),

    # =========================================================================
    # 4th Job Masteries (Levels 102-138)
    # =========================================================================
    MasteryNode("Eight-Legs Easton - Damage", 102, 0, "skill_damage_pct", "eight_legs_easton", 10, "Eight-Legs Easton damage +10%"),
    MasteryNode("Scurvy Summons - Damage 2", 104, 0, "skill_damage_pct", "scurvy_summons", 50, "Scurvy Summons damage +50%"),
    MasteryNode("Brain Scrambler - Damage", 106, 0, "skill_damage_pct", "brain_scrambler", 20, "Brain Scrambler damage +20%"),
    MasteryNode("Rapid Fire - Damage", 108, 0, "skill_damage_pct", "rapid_fire", 20, "Rapid Fire damage +20%"),
    MasteryNode("Eight-Legs Easton - Boss Damage", 111, 0, "skill_boss_damage", "eight_legs_easton", 10, "Eight-Legs Easton Boss Damage +10%"),
    MasteryNode("Brain Scrambler - Damage 2", 113, 0, "skill_damage_pct", "brain_scrambler", 20, "Brain Scrambler damage +20%"),
    MasteryNode("Eight-Legs Easton - Damage 2", 116, 0, "skill_damage_pct", "eight_legs_easton", 11, "Eight-Legs Easton damage +11%"),
    MasteryNode("Majestic Presence - Damage", 118, 0, "skill_damage_pct", "majestic_presence", 50, "Majestic Presence damage +50%"),
    MasteryNode("Brain Scrambler - Damage 3", 120, 0, "skill_damage_pct", "brain_scrambler", 20, "Brain Scrambler damage +20%"),
    MasteryNode("Broadside - Damage", 122, 0, "skill_damage_pct", "broadside", 30, "Broadside damage +30%"),
    MasteryNode("Brain Scrambler - Damage 4", 124, 0, "skill_damage_pct", "brain_scrambler", 20, "Brain Scrambler damage +20%"),
    MasteryNode("Rapid Fire - Damage 2", 126, 0, "skill_damage_pct", "rapid_fire", 30, "Rapid Fire damage +30%"),
    MasteryNode("Eight-Legs Easton - Damage 3", 128, 0, "skill_damage_pct", "eight_legs_easton", 12, "Eight-Legs Easton damage +12%"),
    MasteryNode("Nautilus Strike - Damage", 130, 0, "skill_damage_pct", "nautilus_strike", 50, "Nautilus Strike damage +50%"),
    MasteryNode("Brain Scrambler - Damage 5", 132, 0, "skill_damage_pct", "brain_scrambler", 20, "Brain Scrambler damage +20%"),
    MasteryNode("Rapid Fire - Boss Damage", 134, 0, "skill_boss_damage", "rapid_fire", 30, "Rapid Fire Boss Damage +30%"),
    MasteryNode("Brain Scrambler - Strike", 136, 0, "skill_hits", "brain_scrambler", 1, "Brain Scrambler hits +1"),
    MasteryNode("Majestic Presence - Damage 2", 138, 0, "skill_damage_pct", "majestic_presence", 50, "Majestic Presence damage +50%"),
]


# =============================================================================
# JOB CLASS SKILL/MASTERY REGISTRY
# =============================================================================

# Registry maps job class to its skills and masteries
# This allows DPSCalculator to work with any job class
SKILLS_BY_JOB: Dict[JobClass, Dict[str, 'SkillData']] = {
    JobClass.BOWMASTER: BOWMASTER_SKILLS,
    JobClass.ARCHMAGE_FIRE_POISON: FIRE_POISON_SKILLS,
    JobClass.ARCHMAGE_ICE_LIGHTNING: ICE_LIGHTNING_SKILLS,
    JobClass.HERO: HERO_SKILLS,
    JobClass.NIGHT_LORD: NIGHT_LORD_SKILLS,
    JobClass.SHADOWER: SHADOWER_SKILLS,
    JobClass.MARKSMAN: MARKSMAN_SKILLS,
    JobClass.DARK_KNIGHT: DARK_KNIGHT_SKILLS,
    JobClass.BUCCANEER: BUCCANEER_SKILLS,
    JobClass.CORSAIR: CORSAIR_SKILLS,
}

MASTERIES_BY_JOB: Dict[JobClass, List['MasteryNode']] = {
    JobClass.BOWMASTER: BOWMASTER_MASTERIES,
    JobClass.ARCHMAGE_FIRE_POISON: FIRE_POISON_MASTERIES,
    JobClass.ARCHMAGE_ICE_LIGHTNING: ICE_LIGHTNING_MASTERIES,
    JobClass.HERO: HERO_MASTERIES,
    JobClass.NIGHT_LORD: NIGHT_LORD_MASTERIES,
    JobClass.SHADOWER: SHADOWER_MASTERIES,
    JobClass.MARKSMAN: MARKSMAN_MASTERIES,
    JobClass.DARK_KNIGHT: DARK_KNIGHT_MASTERIES,
    JobClass.BUCCANEER: BUCCANEER_MASTERIES,
    JobClass.CORSAIR: CORSAIR_MASTERIES,
}


def get_skills_for_job(job_class: JobClass) -> Dict[str, 'SkillData']:
    """Get skills dictionary for a job class."""
    return SKILLS_BY_JOB.get(job_class, BOWMASTER_SKILLS)


def get_masteries_for_job(job_class: JobClass) -> List['MasteryNode']:
    """Get masteries list for a job class."""
    return MASTERIES_BY_JOB.get(job_class, BOWMASTER_MASTERIES)


# =============================================================================
# CHARACTER STATE
# =============================================================================

@dataclass
class CharacterState:
    """Complete state of a character for any job class."""
    level: int = 100

    # Job class determines which skills/masteries to use
    job_class: JobClass = JobClass.BOWMASTER

    # Skill levels (base level, before +All Skills)
    skill_levels: Dict[str, int] = field(default_factory=dict)

    # +All Skills bonus from potentials
    all_skills_bonus: int = 0

    # Equipment stats
    attack: float = 1000
    main_stat_flat: float = 0  # Flat DEX/main stat (1% per point) - equipment only, NOT multiplied by main_stat_pct
    main_stat_pct: float = 0   # DEX%/main stat %
    main_stat_conversion: float = 0  # Stat-converted main stat (e.g. Shield Mastery: DEF->LUK); added AFTER %main_stat multiplication
    secondary_stat_flat: float = 0  # Flat STR/secondary stat (0.25% per point)
    secondary_stat_pct: float = 0   # STR%/secondary stat %
    damage_pct: float = 0
    boss_damage: float = 0           # Global boss damage % (applied during boss phase)
    normal_damage: float = 0         # Global normal monster damage % (applied during mob phase)
    crit_rate: float = 50.0
    crit_damage: float = 150.0
    min_dmg_mult: float = 0
    max_dmg_mult: float = 0
    skill_damage: float = 0
    basic_attack_damage: float = 0
    final_damage_pct: float = 0
    def_pen_pct: float = 0
    attack_speed_pct: float = 0

    # Equipment potentials
    ba_target_bonus: int = 0  # +BA Targets from potentials (e.g., +3 from Mystic pot)

    # Job-specific skill level bonuses from equipment sub stats
    skill_1st_bonus: int = 0  # +1st Job Skill levels
    skill_2nd_bonus: int = 0  # +2nd Job Skill levels
    skill_3rd_bonus: int = 0  # +3rd Job Skill levels
    skill_4th_bonus: int = 0  # +4th Job Skill levels

    # Skill cooldown reduction from hat special potential (flat seconds)
    skill_cd_reduction: float = 0.0

    # Buff Duration % — multiplies all BUFF skill durations (e.g. from items/masteries)
    buff_duration_pct: float = 0.0

    # Hexagon Necklace star count (0-5). Used by the realistic-DPS simulator to
    # step hex stacks live over the fight (see DPSCalculator._hex_stacks_at and
    # the per-tick hex multiplier inside _simulate_fight). 0 = not equipped.
    hex_necklace_stars: int = 0

    # Companion-gated FD (Horn Flute artifact), combined as a multiplicative
    # decimal (e.g. 0.20 = +20% FD). Realistic-DPS only:
    #   - Applied to player damage events while a companion summon is active
    #     (gated by `active_summons` in `_simulate_fight`).
    #   - Baked into the companion's frozen snapshot at cast time so the
    #     companion benefits for its full window — but only once (the
    #     simulator does NOT re-multiply companion damage).
    # Legacy DPS path averages this in via fight uptime instead.
    companion_active_fd_decimal: float = 0.0

    # Unique stats (HeroUniqueStatOption levels, 0 = not invested)
    # Formula: bonus = (Value + AddedValue * level) / 10  (from datamine)
    unique_attack_speed_level: int = 0       # 0-20: +3.0% base, +0.2%/level (max 7.0%)
    unique_crit_chance_level: int = 0        # 0-10: +5.0% base, +0.5%/level (max 10.0%)
    unique_min_damage_level: int = 0         # 0-20: +5.0% base, +0.3%/level (max 11.0%)
    unique_max_damage_level: int = 0         # 0-20: +5.0% base, +0.3%/level (max 11.0%)
    unique_crit_power_level: int = 0         # 0-30: +5.0% base, +0.5%/level (max 20.0%)
    unique_normal_damage_level: int = 0      # 0-30: +5.0% base, +0.5%/level (max 20.0%)
    unique_boss_damage_level: int = 0        # 0-30: +5.0% base, +0.5%/level (max 20.0%)
    unique_skill_power_level: int = 0        # 0-30: +10.0% base, +0.5%/level (max 25.0%)
    unique_attack_power_level: int = 0       # 0-50: +10.0% base, +0.5%/level (max 35.0%)
    unique_main_stat_level: int = 0          # 0-160: +30.0 base, +0.5/level (max 110.0)

    # For stat matching mode: which BUFF skills are manually enabled (full stat value)
    # e.g., {"nimble_feet", "sharp_eyes"} means both buffs are active for stat display
    enabled_buffs: Set[str] = field(default_factory=set)

    # Skill names that are forcibly treated as unlocked by `is_skill_unlocked`,
    # regardless of unlock_level. Used by features that inject synthetic skills
    # (e.g., the companion summon mechanic — see register_companion_summon).
    _extra_unlocked_skills: Set[str] = field(default_factory=set)

    @functools.cached_property
    def skills(self) -> Dict[str, 'SkillData']:
        return get_skills_for_job(self.job_class)

    @functools.cached_property
    def masteries(self) -> List['MasteryNode']:
        return get_masteries_for_job(self.job_class)

    @functools.cached_property
    def _unlocked_skills(self) -> frozenset:
        return frozenset(name for name, s in self.skills.items()
                         if self.level >= s.unlock_level)

    def get_unique_stat_bonuses(self) -> Dict[str, float]:
        """Compute stat bonuses from unique stat levels.

        Returns dict of stat_name -> bonus_value (percentage or flat).
        Formula per stat: (base_value + added_value * level) / 10
        Returns 0 for any stat at level 0 (not invested).
        """
        bonuses = {}

        # (field_name, stat_key, base_value, added_value)
        # Values from HeroUniqueStatOptionTable.json (raw ints, divided by 10)
        UNIQUE_STAT_CONFIG = [
            ('unique_attack_speed_level', 'attack_speed', 30, 2),       # 3.0% + 0.2%/lv
            ('unique_crit_chance_level', 'crit_rate', 50, 5),           # 5.0% + 0.5%/lv
            ('unique_min_damage_level', 'min_dmg_mult', 50, 3),         # 5.0% + 0.3%/lv
            ('unique_max_damage_level', 'max_dmg_mult', 50, 3),         # 5.0% + 0.3%/lv
            ('unique_crit_power_level', 'crit_damage', 50, 5),          # 5.0% + 0.5%/lv
            ('unique_normal_damage_level', 'normal_damage', 50, 5),     # 5.0% + 0.5%/lv
            ('unique_boss_damage_level', 'boss_damage', 50, 5),         # 5.0% + 0.5%/lv
            ('unique_skill_power_level', 'skill_damage', 100, 5),       # 10.0% + 0.5%/lv
            ('unique_attack_power_level', 'attack_pct', 100, 5),        # 10.0% + 0.5%/lv
            ('unique_main_stat_level', 'main_stat_flat', 300, 5),       # 30.0 + 0.5/lv
        ]

        for field, stat_key, base_val, added_val in UNIQUE_STAT_CONFIG:
            level = getattr(self, field, 0)
            if level > 0:
                bonuses[stat_key] = (base_val + added_val * level) / 10
            else:
                bonuses[stat_key] = 0

        return bonuses

    def get_effective_skill_cooldown(self, base_cd: float, percent_reduction: float = 0) -> float:
        """
        Get effective cooldown for a skill, applying hat's skill CD reduction.

        Args:
            base_cd: Base cooldown in seconds
            percent_reduction: Percentage reduction from masteries (0-100)

        Returns:
            Effective cooldown after all reductions
        """
        return calculate_effective_cooldown(
            base_cd,
            percent_reduction,
            self.skill_cd_reduction
        )

    def get_effective_skill_level(self, skill_name: str) -> int:
        """
        Get effective skill level including:
        - Base level (1)
        - Job-specific skill points from leveling (3 per level in that job)
        - +All Skills bonus from gear
        - Job-specific skill bonuses from equipment (e.g., +5 1st Job Skill)

        Example at level 103 with +44 All Skills and +5 1st Job:
        - 1st Job skill: 1 + 87 + 44 + 5 = 137
        - 2nd Job skill: 1 + 90 + 44 + 0 = 135
        - 3rd Job skill: 1 + 120 + 44 + 0 = 165
        - 4th Job skill: 1 + 9 + 44 + 0 = 54
        """
        base = self.skill_levels.get(skill_name, 1)

        # Get job-specific skill point bonus from leveling
        job_skill_points = 0
        job_equipment_bonus = 0
        if skill_name in self.skills:
            skill_job = self.skills[skill_name].job
            job_skill_points = get_skill_points_for_job(self.level, skill_job)

            # Add job-specific equipment bonus
            if skill_job == Job.FIRST:
                job_equipment_bonus = self.skill_1st_bonus
            elif skill_job == Job.SECOND:
                job_equipment_bonus = self.skill_2nd_bonus
            elif skill_job == Job.THIRD:
                job_equipment_bonus = self.skill_3rd_bonus
            elif skill_job == Job.FOURTH:
                job_equipment_bonus = self.skill_4th_bonus

        return base + job_skill_points + self.all_skills_bonus + job_equipment_bonus

    def get_current_job(self) -> Job:
        """Get current job advancement."""
        return get_job_for_level(self.level)

    def is_skill_unlocked(self, skill_name: str) -> bool:
        if skill_name in self._extra_unlocked_skills:
            return True
        return skill_name in self._unlocked_skills

    def get_active_basic_attack(self) -> str:
        """Get the highest tier basic attack available for this job class."""
        # Find all unlocked basic attacks, pick the one with highest unlock level
        best_ba = None
        best_unlock_level = -1

        for skill_name, skill in self.skills.items():
            if skill.skill_type == SkillType.BASIC_ATTACK:
                if self.level >= skill.unlock_level:
                    if skill.unlock_level > best_unlock_level:
                        best_ba = skill_name
                        best_unlock_level = skill.unlock_level

        return best_ba if best_ba else ""


def create_character_at_level(
    level: int,
    all_skills_bonus: int = 0,
    job_class: JobClass = JobClass.BOWMASTER,
) -> CharacterState:
    """
    Create a character state at the given level with default skill distribution.

    Args:
        level: Character level
        all_skills_bonus: +All Skills bonus from equipment
        job_class: The job class for this character

    Assumes:
    - 3 skill points per level into current job skills
    - Skills are leveled somewhat evenly
    """
    char = CharacterState(level=level, all_skills_bonus=all_skills_bonus, job_class=job_class)

    # Set skill levels based on available skill points
    # This is a simplified model - in practice players optimize differently

    for skill_name, skill_data in char.skills.items():
        if level >= skill_data.unlock_level:
            # Skill is unlocked, calculate approximate level
            # Simplified: assume base level 1 for now, since +All Skills is the focus
            char.skill_levels[skill_name] = 1

    return char


def create_default_character(
    level: int,
    job_class: JobClass = JobClass.BOWMASTER,
    all_skills_bonus: int = 0,
    skill_1st_bonus: int = 0,
    skill_2nd_bonus: int = 0,
    skill_3rd_bonus: int = 0,
    skill_4th_bonus: int = 0,
) -> CharacterState:
    """
    Create a default character for skill analysis with standardized stats.

    This provides a consistent baseline for comparing skill damage contributions
    across different levels and job classes, independent of user-specific stats.

    Args:
        level: Character level
        job_class: The job class for this character
        all_skills_bonus: +All Skills bonus from equipment
        skill_1st_bonus: +1st Job Skill bonus from equipment
        skill_2nd_bonus: +2nd Job Skill bonus from equipment
        skill_3rd_bonus: +3rd Job Skill bonus from equipment
        skill_4th_bonus: +4th Job Skill bonus from equipment

    Returns:
        CharacterState with standardized stats for analysis
    """
    char = create_character_at_level(level, all_skills_bonus, job_class)

    # Apply job-specific skill bonuses
    char.skill_1st_bonus = skill_1st_bonus
    char.skill_2nd_bonus = skill_2nd_bonus
    char.skill_3rd_bonus = skill_3rd_bonus
    char.skill_4th_bonus = skill_4th_bonus

    # Standardized stats (not from user data) for consistent comparison
    char.attack = 50000  # Baseline attack
    char.main_stat_flat = 30000
    char.main_stat_pct = 100
    char.damage_pct = 150
    char.boss_damage = 100
    char.normal_damage = 50
    char.crit_rate = 80
    char.crit_damage = 150
    char.final_damage_pct = 50
    char.def_pen_pct = 30

    return char


def build_companion_summon_skill_data(
    advancement: 'JobAdvancement',
    level: int,
    *,
    name: str = "Companion Summon",
    primary_attack_override: Optional[Dict] = None,
) -> Optional['SkillData']:
    """
    Build a synthetic SkillData (SkillType.SUMMON) representing the equipped
    main companion's attack while summoned. Returns None if the companion's
    tier has no active attack (Basic / Grade1) or level is invalid.

    Per-grade attack stats and per-level scaling come from
    game.companions.get_companion_summon_attack (which in turn sources its
    numbers from data_mine/TextAsset/SupporterTable.json,
    SupporterLevelStatFactorTable.json, and SkillTable.json).

    `primary_attack_override` (from `CompanionDefinition.
    summon_primary_attack_override`) overrides specific fields on the
    tier's primary attack — used by Bishop 4th (5 hits, 6 targets).
    """
    from game.companions import get_companion_summon_attack
    attack = get_companion_summon_attack(advancement, level,
                                         primary_attack_override=primary_attack_override)
    if attack is None:
        return None
    return SkillData(
        name=name,
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.BASIC,            # not a job skill — Job.BASIC = unaffected by +All Skills
        unlock_level=1,           # always considered unlocked at L1+
        base_damage_pct=attack["damage_pct"],
        base_hits=attack["hits"],
        base_targets=attack["targets"],
        damage_per_level=0.0,     # level scaling already baked into base_damage_pct
        level_factor_index=-1,
        cooldown=attack["cooldown_s"],
        duration=attack["duration_s"],
        attack_interval=attack["attack_interval_s"],
        scales_with_attack_speed=False,  # companion has fixed tick from datamine
        cast_time=0.5,                   # animation only, doesn't matter much
    )


# =============================================================================
# DPS CALCULATOR (Updated with Masteries)
# =============================================================================

@dataclass
class DPSResult:
    """Result of DPS calculation."""
    total_dps: float

    # Breakdown by source
    basic_attack_dps: float
    active_skill_dps: float
    summon_dps: float
    proc_dps: float

    # Details
    rotation_length: float
    skills_used: List[str]

    # Stat totals (for debugging)
    total_skill_damage_pct: float = 0
    total_basic_attack_dmg_pct: float = 0
    total_final_damage_pct: float = 0

    # Phase breakdown (only from realistic DPS)
    mob_phase_dps: float = 0
    boss_phase_dps: float = 0

    # Fight simulation log (optional, only from realistic DPS)
    fight_log: List['FightLogEntry'] = None


@dataclass
class SkillActionValue:
    """Precalculated action values for a skill in both combat phases.

    Used by realistic DPS simulation to avoid recalculating damage each tick.
    """
    skill_name: str
    damage_per_use_mob: float    # Total damage when used in mob phase
    damage_per_use_boss: float   # Total damage when used in boss phase
    cast_time: float             # Time to execute this action
    cooldown: float              # Cooldown after use (0 for basic attack)
    dps_value_mob: float         # damage_per_use_mob / cast_time
    dps_value_boss: float        # damage_per_use_boss / cast_time


# Planning horizon for scheduler scoring. At each decision point the scheduler
# scores candidate plans (damage, buff, summon, buff_then_summon) by their
# total damage produced over this many seconds, with greedy BA filling any
# remaining time. Capped at remaining_fight_time at each tick.
#
# 90s comfortably covers most cooldowns (longest 4th-job CD is ~80s for Ifrit)
# and summon windows (typical 30s), giving the scorer enough horizon to
# fairly weigh long-windup plans like Mist Eruption against burst options.
LOOKAHEAD_HORIZON_S: float = 90.0


@dataclass
class FightLogEntry:
    """A single action in the fight simulation log."""
    time: float                  # Time when action started
    skill_name: str              # Name of skill used
    phase: str                   # 'mob' or 'boss'
    damage: float                # Damage dealt by this action
    cast_time: float             # Duration of this action
    reason: str = ""             # Why this skill was chosen (e.g., "highest DPS value")


@dataclass
class CachedRotationResult:
    """Cached simulation result enabling fast recalculation for Tier 1/2 stats.

    This stores the results of a full fight simulation in a way that allows
    fast recalculation when only linear multiplier stats change.

    Tier 1 (Universal): main_stat, damage%, crit, FD%, def_pen
        -> Just multiply total_dps by ratio of new/old universal multiplier

    Tier 2 (Phase-weighted): boss_damage%, normal_damage%
        -> Use skill_mob_dps and skill_boss_dps to recalculate phase weighting

    Tier 3 (Rotation-affecting): attack_speed, skill_levels, cooldowns
        -> Must run full simulation again
    """
    total_dps: float

    # Per-skill breakdown (needed for Tier 2 phase recalc)
    skill_mob_dps: Dict[str, float]   # DPS from each skill during mob phase
    skill_boss_dps: Dict[str, float]  # DPS from each skill during boss phase

    # Baseline multipliers used (needed for Tier 1 ratio calculation)
    baseline_universal_mult: float    # Combined main_stat × dmg × crit × FD × def_pen
    baseline_normal_mult: float       # 1 + normal_damage_pct / 100
    baseline_boss_mult: float         # 1 + boss_damage_pct / 100

    # Context for cache key / invalidation
    rotation_key: Tuple               # (level, all_skills, skill_bonuses, attack_speed, ...)


# Stat categorization for optimization
TIER_1_UNIVERSAL_STATS = frozenset({
    'main_stat_flat', 'main_stat_pct', 'damage_pct',
    'crit_rate', 'crit_damage', 'final_damage_pct', 'def_pen_pct'
})

TIER_2_PHASE_STATS = frozenset({
    'boss_damage', 'normal_damage'
})

TIER_3_ROTATION_STATS = frozenset({
    'attack_speed_pct', 'all_skills_bonus', 'skill_1st_bonus', 'skill_2nd_bonus',
    'skill_3rd_bonus', 'skill_4th_bonus', 'cooldown_reduction'
})


@dataclass(frozen=True)
class PlayerStatSnapshot:
    """
    Frozen snapshot of the player's offensive stat block at a single instant.

    Used by the burst-window scheduler to capture the player's "best version of
    themselves" at the moment a companion is summoned, so that the companion's
    30-second attack window deals damage as if the player's stats at cast time
    persisted for the full window, regardless of how the player's own buff
    state evolves afterward.

    Values are TOTALS (`char.X + get_total_stat_bonus("X")`) — no further
    summation in `calculate_hit_damage` when this is passed via stat_override.

    See plan: C:/Users/ianpr/.claude/plans/sorted-nibbling-meteor.md (Phase 1).
    """
    # Core attack
    attack: float

    # Main stat (totals: flat + pct, already scaled, plus conversion)
    main_stat_flat_total: float           # char.main_stat_flat + global("main_stat_flat")
    main_stat_pct_total: float            # char.main_stat_pct + global_bonus("main_stat_pct")
    main_stat_conversion: float
    secondary_stat_flat: float
    secondary_stat_pct: float

    # Damage % bucket
    damage_pct_total: float               # char.damage_pct + total_bonus("damage_pct")

    # Phase-specific damage
    boss_damage: float
    normal_damage: float

    # Damage-type bonuses
    basic_attack_damage_total: float      # char.basic_attack_damage + total_bonus("basic_attack_damage")
    skill_damage_total: float             # char.skill_damage + total_bonus("skill_damage")

    # Final damage (the global one; per-skill enhancer FD is computed live since
    # it depends on skill_name, not on player state)
    final_damage_pct: float

    # Crit (totaled: includes passive bonuses from get_total_stat_bonus)
    crit_rate_total: float
    crit_damage: float

    # Defense penetration (used to derive _def_pen_mult)
    def_pen_pct: float

    # Attack speed (for cast-time-dependent helpers like Venom uptime)
    attack_speed_pct: float

    # Buff-duration % stat (extends snapshot's buff durations consistently)
    buff_duration_pct: float = 0.0

    # Currently active player buffs (Sharp Eyes, Smokescreen, etc.) — frozen at
    # snapshot time so the companion's hits get the buff stat boost for its
    # entire window even after the player's buffs decay.
    active_buffs: frozenset = field(default_factory=frozenset)

    # "Optimal pre-stack" assumptions for mechanics whose live stepping we
    # intentionally don't model in the simulator (per Phase 4 simplification):
    # - mortal_blow_forced: when True, treat MB as active (full FD bonus, no
    #   uptime averaging). None = use the calculate_hit_damage default.
    # - concentration_forced_stacks: when set, override the implicit 7-stack
    #   assumption with this explicit value.
    mortal_blow_forced: Optional[bool] = None
    concentration_forced_stacks: Optional[int] = None

    # External multiplier baked in at snapshot time (NOT recomputed during the
    # 30s window, even as hex stacks would evolve on the player).
    hex_multiplier: float = 1.0

    @classmethod
    def from_calculator(
        cls,
        calc: 'DPSCalculator',
        active_buffs: Optional[Set[str]] = None,
        hex_multiplier: float = 1.0,
        *,
        mortal_blow_forced: Optional[bool] = None,
        concentration_forced_stacks: Optional[int] = None,
    ) -> 'PlayerStatSnapshot':
        """
        Build a snapshot from a live `DPSCalculator`'s current state.

        Pre-totals all stats with their passive bonuses so the consumer can
        read them directly without re-summing. `active_buffs` is captured as a
        frozenset so the snapshot is hashable and immutable.
        """
        char = calc.char
        # Pre-total every stat that calculate_hit_damage normally sums on the fly.
        main_flat_total = char.main_stat_flat + calc.get_global_stat("main_stat_flat")
        main_pct_total = char.main_stat_pct + calc.get_total_stat_bonus("main_stat_pct")
        damage_pct_total = char.damage_pct + calc.get_total_stat_bonus("damage_pct")
        ba_dmg_total = char.basic_attack_damage + calc.get_total_stat_bonus("basic_attack_damage")
        skill_dmg_total = char.skill_damage + calc.get_total_stat_bonus("skill_damage")
        crit_rate_total = char.crit_rate + calc.get_total_stat_bonus("crit_rate")

        return cls(
            attack=char.attack,
            main_stat_flat_total=main_flat_total,
            main_stat_pct_total=main_pct_total,
            main_stat_conversion=char.main_stat_conversion,
            secondary_stat_flat=char.secondary_stat_flat,
            secondary_stat_pct=char.secondary_stat_pct,
            damage_pct_total=damage_pct_total,
            boss_damage=char.boss_damage,
            normal_damage=char.normal_damage,
            basic_attack_damage_total=ba_dmg_total,
            skill_damage_total=skill_dmg_total,
            final_damage_pct=char.final_damage_pct,
            crit_rate_total=crit_rate_total,
            crit_damage=char.crit_damage,
            def_pen_pct=char.def_pen_pct,
            attack_speed_pct=char.attack_speed_pct,
            buff_duration_pct=char.buff_duration_pct,
            active_buffs=frozenset(active_buffs or ()),
            mortal_blow_forced=mortal_blow_forced,
            concentration_forced_stacks=concentration_forced_stacks,
            hex_multiplier=hex_multiplier,
        )


class DPSCalculator:
    """
    Calculates DPS for any job class given character state.

    Now includes:
    - Mastery bonuses
    - Level-appropriate skills
    - Proper skill unlocking
    - Multi-class support via job_class registry
    """

    def __init__(self, char: CharacterState, enemy_def: float = 0.752):
        self.char = char
        self.enemy_def = enemy_def  # Enemy defense value (default: stage ~0.752)
        # Cache skills and masteries for this character's job class.
        # NOTE: shallow-copy the skill dict so per-calculator mutations (e.g.,
        # register_companion_summon injecting a synthetic SUMMON) don't leak
        # into the module-level skill table.
        self._skills = dict(char.skills)
        self._masteries = char.masteries
        self.mastery_bonuses = get_mastery_bonuses(char.level, self._masteries)

        # Pre-compute def_pen_mult — constant for this char+enemy combination
        def_pen_decimal = min(char.def_pen_pct / 100, 1.0)
        self._def_pen_mult = 1 / (1 + enemy_def * (1 - def_pen_decimal))

        # Pre-partition skills by type to avoid filtering full skill dict in hot loops
        self._active_skills = {k: v for k, v in self._skills.items() if v.skill_type == SkillType.ACTIVE}
        self._summon_skills = {k: v for k, v in self._skills.items() if v.skill_type == SkillType.SUMMON}
        self._proc_skills = {k: v for k, v in self._skills.items() if v.skill_type == SkillType.PASSIVE_PROC}
        self._enhancer_skills = {k: v for k, v in self._skills.items() if v.skill_type == SkillType.SKILL_ENHANCER}
        self._buff_skills = {k: v for k, v in self._skills.items() if v.skill_type == SkillType.BUFF}
        self._stat_skills = {k: v for k, v in self._skills.items() if v.skill_type == SkillType.PASSIVE_STAT}

        # Instance-level caches for frequently-called methods
        # These values are stable for a given character state
        self._skill_damage_cache: Dict[str, float] = {}
        self._skill_hits_cache: Dict[str, int] = {}
        self._skill_targets_cache: Dict[str, int] = {}

        # Companion-summon stat snapshot — set when the burst-window scheduler
        # decides to cast the companion summon, and read by the companion's
        # per-hit damage path so that the 30-second summon window uses the
        # player's stat block as frozen at cast time. None when no companion
        # is currently summoned. See Phase 2 of the burst-window scheduler.
        self._companion_snapshot: Optional[PlayerStatSnapshot] = None

        # Bishop-style companion kit. Populated by `calculate_dps` after
        # `register_companion_summon`; defaults here so non-Bishop paths
        # don't need defensive getattr().
        self._companion_self_buff_fd_decimal: float = 0.0
        self._companion_player_bonuses: Dict[str, float] = {}
        self._companion_secondary_skills: List[Any] = []
        self._companion_proc_skill: Optional[Any] = None

    def get_skill(self, skill_name: str) -> Optional[SkillData]:
        """Get skill data by name for this character's job class."""
        return self._skills.get(skill_name)

    def register_companion_summon(
        self,
        skill_data: 'SkillData',
        skill_name: str = "companion_main_summon",
    ) -> None:
        """
        Inject a synthetic SUMMON skill into the calculator so the existing
        4 summon DPS paths (_calc_summons_dps_phased, calculate_total_dps,
        calculate_mortal_blow_uptime, get_skill_damage_breakdown) treat it
        like Phoenix / Arrow Platter — same uptime math, same per-hit damage
        path, same propagation of player stats via calculate_hit_damage.

        Marks the skill as unlocked on the character regardless of its
        unlock_level (the companion's "summon" isn't a job skill the player
        has to learn).
        """
        if skill_data.skill_type != SkillType.SUMMON:
            raise ValueError(
                f"register_companion_summon expects SkillType.SUMMON, got {skill_data.skill_type}"
            )
        self._skills[skill_name] = skill_data
        self._summon_skills[skill_name] = skill_data
        self.char._extra_unlocked_skills.add(skill_name)
        # Track companion-summon skill_name(s) so the burst-window scheduler
        # (realistic-DPS path) can find them and treat them as discrete
        # castable actions rather than as a passive uptime-averaged summon.
        if not hasattr(self, '_companion_summon_keys') or self._companion_summon_keys is None:
            self._companion_summon_keys: Set[str] = set()
        self._companion_summon_keys.add(skill_name)

    def _hex_stacks_at(self, t: float) -> int:
        """
        Hexagon Necklace stack count active at simulator time `t`.
        Matches the schedule baked into `artifacts.calculate_hex_average_multiplier`:
        0 stacks 0-20s, 1 stack 20-40s, 2 stacks 40-60s, 3 stacks 60s+.
        """
        if t < 20.0:
            return 0
        if t < 40.0:
            return 1
        if t < 60.0:
            return 2
        return 3

    def _hex_multiplier_at(self, t: float) -> float:
        """
        Live hex multiplier at simulator time `t`. Returns 1.0 if no necklace
        is equipped. Memoizes the per-stack lookup since it's hit on every
        damage event.
        """
        stars = getattr(self.char, 'hex_necklace_stars', 0) or 0
        if stars <= 0:
            return 1.0
        stacks = self._hex_stacks_at(t)
        if stacks <= 0:
            return 1.0
        cache = getattr(self, '_hex_mult_cache', None)
        if cache is None:
            cache = {}
            self._hex_mult_cache = cache
        key = (stars, stacks)
        if key not in cache:
            from game.artifacts import calculate_hex_multiplier
            cache[key] = calculate_hex_multiplier(stars, stacks)
        return cache[key]

    def _get_available_summon_actions(
        self,
        t: float,
        summon_cooldowns: Dict[str, float],
    ) -> Dict[str, 'SkillData']:
        """
        Return registered companion summons that are castable at simulator
        time `t`. A summon is castable iff:
            (a) `t >= SUMMON_LOCKOUT_S` (5-second start-of-fight lockout), AND
            (b) its own cooldown timer is `<= 0`.
        Used by the burst-window scheduler in `_simulate_fight`.

        See plan: C:/Users/ianpr/.claude/plans/sorted-nibbling-meteor.md (Phase 2).
        """
        from game.companions import SUMMON_LOCKOUT_S
        if t < SUMMON_LOCKOUT_S:
            return {}
        keys = getattr(self, '_companion_summon_keys', None) or set()
        return {
            key: self._summon_skills[key]
            for key in keys
            if key in self._summon_skills
            and summon_cooldowns.get(key, 0.0) <= 0.0
        }

    # Phase 4 "optimal pre-stack" defaults applied to every companion-summon
    # snapshot. The player's own continuous damage still uses the averaged
    # uptime / hardcoded 7-stack assumption; only the companion's frozen
    # 30s window benefits from the enriched values.
    _COMPANION_CONCENTRATION_FORCED_STACKS = 7

    def _build_companion_snapshot(
        self,
        active_buffs: Optional[Set[str]] = None,
        hex_multiplier: float = 1.0,
    ) -> 'PlayerStatSnapshot':
        """
        Construct a companion-summon snapshot with the Phase 4 "optimal
        pre-stack" enrichment: Mortal Blow forced active, Concentration at
        max stacks. All three sites that snapshot for a companion
        (scheduler cast, summon-scoring lookahead, delay-dominance check)
        route through here so the enrichment stays consistent.

        Horn Flute (`char.companion_active_fd_decimal`) is baked into the
        snapshot's final_damage_pct exactly once here. The simulator does
        NOT re-multiply companion damage by this FD — that would
        double-count, since the companion's per-hit damage already reads
        the boosted final_damage_pct via stat_override.
        """
        snapshot = PlayerStatSnapshot.from_calculator(
            self,
            active_buffs=active_buffs,
            hex_multiplier=hex_multiplier,
            mortal_blow_forced=True,
            concentration_forced_stacks=self._COMPANION_CONCENTRATION_FORCED_STACKS,
        )
        # Compose two FD sources multiplicatively into the snapshot's
        # final_damage_pct: Horn Flute (player+companion gate) and the
        # companion's own self-buff (3rd/4th job OnStart skill, baked once
        # at spawn). Both are stored as decimals (0.20 = +20%).
        horn_fd = getattr(self.char, 'companion_active_fd_decimal', 0.0)
        self_buff_fd = getattr(self, '_companion_self_buff_fd_decimal', 0.0)
        extra_fd_mult = (1.0 + horn_fd) * (1.0 + self_buff_fd)
        if extra_fd_mult > 1.0:
            from dataclasses import replace as _dc_replace
            base_fd_mult = 1.0 + snapshot.final_damage_pct / 100.0
            boosted_fd_pct = (base_fd_mult * extra_fd_mult - 1.0) * 100.0
            snapshot = _dc_replace(snapshot, final_damage_pct=boosted_fd_pct)
        return snapshot

    def _compose_companion_player_buff_mult(self) -> float:
        """
        Compose the player-damage multiplier from `_companion_player_bonuses`.
        Returns 1.0 when no bonuses are configured (every non-Bishop main).

        Per-stat composition rules (see plan: Bishop 4th, Phase 3):
        - attack_pct, final_damage: decimals, simple `× (1 + value)`.
        - max_dmg_mult: adjusts the damage-range avg.
        - crit_damage: percentage points, weighted by the char's effective
          crit rate (capped at 100%).
        - attack_speed: NOT in here — accelerates attack cadence, not a
          damage multiplier. Handled separately in `_simulate_fight` by
          recomputing `current_attack_speed_mult` + `skill_values` when
          the companion is summoned/despawns.

        Applied at player-damage events in `_simulate_fight` ONLY when a
        companion is currently summoned. Companion damage uses the snapshot
        and does NOT pick these up — that's the point of the asymmetry.
        """
        bonuses = self._companion_player_bonuses
        if not bonuses:
            return 1.0
        from core.constants import BASE_MIN_DMG, BASE_MAX_DMG
        mult = 1.0
        # attack_pct (decimal)
        atk_pct = bonuses.get('attack_pct', 0.0)
        if atk_pct:
            mult *= (1.0 + atk_pct)
        # final_damage (decimal)
        fd = bonuses.get('final_damage', 0.0)
        if fd:
            mult *= (1.0 + fd)
        # max_dmg_mult (percentage points added to BASE_MAX_DMG)
        max_dmg_bonus = bonuses.get('max_dmg_mult', 0.0)
        if max_dmg_bonus:
            base_min = BASE_MIN_DMG + getattr(self.char, 'min_dmg_mult', 0.0)
            base_max = BASE_MAX_DMG + getattr(self.char, 'max_dmg_mult', 0.0)
            base_avg = (base_min + base_max) / 2.0
            new_avg = (base_min + base_max + max_dmg_bonus) / 2.0
            if base_avg > 0:
                mult *= (new_avg / base_avg)
        # crit_damage (percentage points, weighted by effective crit rate)
        cd_bonus = bonuses.get('crit_damage', 0.0)
        if cd_bonus:
            eff_crit_rate = min(
                self.char.crit_rate + self.get_total_stat_bonus('crit_rate'),
                100.0,
            )
            # value/100 is the decimal addition to the crit multiplier;
            # weighted by effective crit rate (also as a fraction).
            mult *= (1.0 + (eff_crit_rate / 100.0) * (cd_bonus / 100.0))
        return mult

    def _avg_hex_between(self, t0: float, t1: float) -> float:
        """
        Average hex multiplier over [t0, t1], accounting for the 20s-interval
        stack bumps. Returns 1.0 if no necklace is equipped. Used by the
        delay-summon plan scoring to credit BA damage during the delay /
        post-summon at the live hex stack count, not a flat 1.0x.
        """
        if getattr(self.char, 'hex_necklace_stars', 0) <= 0:
            return 1.0
        if t1 <= t0:
            return self._hex_multiplier_at(t0)
        breakpoints = sorted({t0, 20.0, 40.0, 60.0, t1})
        breakpoints = [b for b in breakpoints if t0 <= b <= t1]
        if not breakpoints or breakpoints[0] != t0:
            breakpoints.insert(0, t0)
        if breakpoints[-1] != t1:
            breakpoints.append(t1)
        total = 0.0
        for i in range(len(breakpoints) - 1):
            seg0, seg1 = breakpoints[i], breakpoints[i + 1]
            if seg1 > seg0:
                # Sample at segment midpoint — hex is constant within a segment
                # because the breakpoints include every stack-change boundary.
                total += (seg1 - seg0) * self._hex_multiplier_at((seg0 + seg1) / 2.0)
        return total / (t1 - t0)

    def _enumerate_hex_delay_candidates(
        self,
        current_t: float,
        fight_duration: float,
        summon_duration: float,
    ) -> List[float]:
        """
        Return candidate `delay_duration` values that land the next summon
        cast precisely at an upcoming hex stack threshold (t=20, 40, 60).
        Skips thresholds that don't leave enough fight time for the summon
        to pay back its delay.
        """
        if getattr(self.char, 'hex_necklace_stars', 0) <= 0:
            return []
        # Each summon window after the delayed cast must give the companion
        # at least ~10s to attack — otherwise the delay never pays back.
        min_post_window = min(10.0, summon_duration)
        candidates: List[float] = []
        for threshold_t in (20.0, 40.0, 60.0):
            if threshold_t <= current_t:
                continue
            if (fight_duration - threshold_t) < min_post_window:
                break
            candidates.append(threshold_t - current_t)
        return candidates

    def _delay_dominates_summon_now(
        self,
        summon_name: str,
        summon_skill: 'SkillData',
        delay_duration: float,
        current_t: float,
        fight_duration: float,
        best_player_dps: float,
        current_active_buffs: Set[str],
        current_attack_speed_mult: float,
        num_enemies: int,
        is_boss: bool,
        mob_time_fraction: float,
    ) -> bool:
        """
        Return True iff "wait `delay_duration`s then cast summon" outperforms
        "cast summon now" over the longer of the two plans' windows. Used by
        the scheduler to suppress summon-now when an imminent hex bump makes
        delaying strictly better (e.g., the user's "save summon for hex 2"
        rotation on chapter bosses).

        Comparison method: total damage over a common horizon ending at the
        later plan's last segment. Both plans get the same horizon. Whichever
        total wins is the better plan over that window. Greedy "summon-now"
        scoring (damage / plan_window) can't see this trade-off because the
        plans have different natural windows.

        See plan: C:/Users/ianpr/.claude/plans/sorted-nibbling-meteor.md (Phase 3).
        """
        if delay_duration <= 0:
            return False
        if getattr(self.char, 'hex_necklace_stars', 0) <= 0:
            return False

        cast_now_window = min(summon_skill.duration, fight_duration - current_t)
        if cast_now_window <= 0:
            return False
        cast_at = current_t + delay_duration
        cast_delayed_window = min(summon_skill.duration, fight_duration - cast_at)
        if cast_delayed_window <= 0:
            return False

        cur_hex = self._hex_multiplier_at(current_t)
        future_hex = self._hex_multiplier_at(cast_at)
        if future_hex <= cur_hex:
            return False

        horizon_end = current_t + max(cast_now_window, delay_duration + cast_delayed_window)
        horizon_end = min(horizon_end, fight_duration)

        # Companion per-second damage at each hex level. Build fresh
        # snapshots so the snapshot's stored hex_multiplier is wired to the
        # right level; `calculate_hit_damage` reads stats from the snapshot
        # but does not itself apply hex, so we multiply at the end.
        def _companion_dps_per_sec(snap_hex_mult: float) -> float:
            snap = self._build_companion_snapshot(
                active_buffs=current_active_buffs, hex_multiplier=snap_hex_mult,
            )
            damage_pct = self.get_skill_damage_pct(summon_name)
            attacks_per_sec = 1.0 / summon_skill.attack_interval
            hits = self.get_skill_hits(summon_name)
            dmg_boss = self.calculate_hit_damage(
                damage_pct, summon_skill.damage_type, summon_name,
                is_boss_phase=True, attack_speed_mult=current_attack_speed_mult,
                active_buffs=current_active_buffs, num_enemies=1, stat_override=snap,
            )
            if is_boss:
                return dmg_boss * hits * 1 * attacks_per_sec * snap_hex_mult
            dmg_mob = self.calculate_hit_damage(
                damage_pct, summon_skill.damage_type, summon_name,
                is_boss_phase=False, attack_speed_mult=current_attack_speed_mult,
                active_buffs=current_active_buffs, num_enemies=num_enemies,
                stat_override=snap,
            )
            targets_mob = min(self.get_skill_targets(summon_name), num_enemies)
            mob_part = dmg_mob * hits * targets_mob * attacks_per_sec * snap_hex_mult * mob_time_fraction
            boss_part = dmg_boss * hits * 1 * attacks_per_sec * snap_hex_mult * (1 - mob_time_fraction)
            return mob_part + boss_part

        comp_now_dps_sec = _companion_dps_per_sec(cur_hex)
        comp_future_dps_sec = _companion_dps_per_sec(future_hex)

        # summon-now totals. The player keeps attacking DURING the summon
        # window, so we include BA damage across the whole horizon at the
        # live hex multiplier — the hex bump that lands mid-summon-window
        # multiplies the player's own damage even though the snapshot
        # freezes the companion's hex.
        now_companion = comp_now_dps_sec * cast_now_window
        now_summon_end = current_t + cast_now_window
        now_ba_during_summon = (
            best_player_dps * cast_now_window
            * self._avg_hex_between(current_t, now_summon_end)
        )
        now_post_seconds = max(0.0, horizon_end - now_summon_end)
        now_post_ba = (
            best_player_dps * now_post_seconds
            * self._avg_hex_between(now_summon_end, horizon_end)
        ) if now_post_seconds > 0 else 0.0
        now_total = now_companion + now_ba_during_summon + now_post_ba

        # delay-then-summon totals — same BA-everywhere treatment so the
        # comparison is apples-to-apples.
        delay_pre_ba = (
            best_player_dps * delay_duration
            * self._avg_hex_between(current_t, cast_at)
        )
        delay_companion = comp_future_dps_sec * cast_delayed_window
        delay_summon_end = cast_at + cast_delayed_window
        delay_ba_during_summon = (
            best_player_dps * cast_delayed_window
            * self._avg_hex_between(cast_at, delay_summon_end)
        )
        delay_post_seconds = max(0.0, horizon_end - delay_summon_end)
        delay_post_ba = (
            best_player_dps * delay_post_seconds
            * self._avg_hex_between(delay_summon_end, horizon_end)
        ) if delay_post_seconds > 0 else 0.0
        delay_total = delay_pre_ba + delay_companion + delay_ba_during_summon + delay_post_ba

        return delay_total > now_total

    def get_mastery_bonus(self, skill_name: str, effect_type: str) -> float:
        """Get total mastery bonus for a skill and effect type."""
        total = 0

        # Check skill-specific bonuses
        if skill_name in self.mastery_bonuses:
            total += self.mastery_bonuses[skill_name].get(effect_type, 0)

        # Note: Global bonuses are applied separately via get_global_stat()
        # This method is for skill-specific mastery bonuses only

        return total

    def get_scaled_mastery_bonus(self, skill_name: str, effect_type: str) -> float:
        """
        Get mastery bonus that scales with another skill's level.

        Some masteries (like Enchanted Quiver - Drain) have effects that scale
        with a skill's level. This method computes the full scaled value.

        Formula: base_value * (1 + scale_per_level * skill_level)
        """
        total = 0.0

        for mastery in get_unlocked_masteries(self.char.level, self._masteries):
            if mastery.effect_target != skill_name:
                continue
            if mastery.effect_type != effect_type:
                continue
            if not mastery.scale_with_skill:
                # Non-scaled mastery - already handled by get_mastery_bonus
                continue

            # Get the skill level for scaling
            skill_level = self.char.get_effective_skill_level(mastery.scale_with_skill)
            scaled_value = mastery.effect_value * (1 + mastery.scale_per_level * skill_level)
            total += scaled_value

        return total

    def get_global_stat(self, stat_type: str) -> float:
        """Get global stat bonus from masteries (applies to character, not specific skills)."""
        if "global" in self.mastery_bonuses:
            return self.mastery_bonuses["global"].get(stat_type, 0)
        return 0

    def get_skill_bonus(self, skill_name: str, bonus_type: str) -> float:
        """
        Get bonus granted to a skill from other skills (e.g., Flash Mirage II -> Flash Mirage).

        Args:
            skill_name: The skill receiving the bonus (e.g., "flash_mirage")
            bonus_type: "final_damage" or "targets"

        Returns:
            Total bonus value (floor applied)

        Formula: floor(base + per_level * level)
        """
        total = 0.0

        for source_skill_name, source_skill in self._skills.items():
            if not self.char.is_skill_unlocked(source_skill_name):
                continue

            if bonus_type == "final_damage" and source_skill.skill_bonuses:
                if skill_name in source_skill.skill_bonuses:
                    level = self.char.get_effective_skill_level(source_skill_name)
                    base, factor_index = source_skill.skill_bonuses[skill_name]
                    total += int(self.calc_skill_damage_with_factor(base, factor_index, level))

            elif bonus_type == "targets" and source_skill.skill_target_bonuses:
                if skill_name in source_skill.skill_target_bonuses:
                    level = self.char.get_effective_skill_level(source_skill_name)
                    base, per_level = source_skill.skill_target_bonuses[skill_name]
                    total += int(base + per_level * level)

        return total

    @staticmethod
    def calc_skill_value(base: float, per_level: float, level: int) -> float:
        """
        Calculate skill value using standard formula: int((base + per_level * level) * 10) / 10

        Truncates to 1 decimal place (e.g., 15.87 -> 15.8).
        """
        return int((base + per_level * level) * 10) / 10

    def get_skill_bonus_value(self, skill_name: str, stat_name: str) -> float:
        """
        Get a specific stat bonus value from a skill's skill_bonuses dict.

        Args:
            skill_name: Name of the skill (e.g., "extreme_archery")
            stat_name: Name of the stat (e.g., "final_damage")

        Returns:
            Calculated value using formula: int(base * factor[level][index] / 1000 * 10) / 10
            Returns 0 if skill not unlocked or stat not in skill_bonuses
        """
        if not self.char.is_skill_unlocked(skill_name):
            return 0.0

        skill = self._skills.get(skill_name)
        if not skill or not skill.skill_bonuses or stat_name not in skill.skill_bonuses:
            return 0.0

        level = self.char.get_effective_skill_level(skill_name)
        base, factor_index = skill.skill_bonuses[stat_name]
        return self.calc_skill_damage_with_factor(base, factor_index, level)

    def calculate_attack_speed_mult(
        self,
        active_buffs: Optional[Set[str]] = None,
        companion_summon_active: bool = False,
    ) -> float:
        """
        Calculate attack speed multiplier including passive skills and active buffs.

        This consolidates attack speed calculation in one place for use by:
        - DPS simulation (with dynamically tracked buffs)
        - Stat display (with user-enabled buffs)

        Args:
            active_buffs: Set of currently active buff names. If None, uses char.enabled_buffs.
            companion_summon_active: When True, add the companion's
                attack_speed bonus from `_companion_player_bonuses`
                (e.g. Bishop's skill 8: +20% AS at full HP). Only used
                by the realistic-DPS simulator; the legacy stat display
                doesn't know about companion summon state.

        Returns:
            Attack speed multiplier capped at 2.5 (150% bonus)
        """
        # char.attack_speed_pct already includes passive skills, mastery,
        # companions, maple rank, etc. (aggregated with diminishing returns
        # by aggregate_stats). Only add buff bonuses here.
        attack_speed_pct = self.char.attack_speed_pct

        # Add active buff bonuses (BUFF type) - not included in aggregate_stats
        buff_bonuses = self.get_buff_stat_bonuses(active_buffs)
        for as_value in buff_bonuses.get("attack_speed", []):
            attack_speed_pct += as_value

        if companion_summon_active:
            attack_speed_pct += self._companion_player_bonuses.get('attack_speed', 0.0)

        return min(1 + attack_speed_pct / 100, 2.5)

    def get_all_skill_stat_bonuses(self, is_boss_phase: Optional[bool] = None) -> Dict[str, List[float]]:
        """
        Collect all stat bonuses from PASSIVE_STAT skills for a given phase.

        This handles skills that only apply in certain scenarios:
        - Marksmanship (scenario="boss"): Only active during single-target/boss fights
        - Future mob-only skills would use scenario="mob"

        This is different from mastery bonuses like "skill_boss_damage" which are
        damage multipliers applied during calculate_hit_damage(), not stat bonuses.

        Args:
            is_boss_phase: True = boss phase (include "all" + "boss" scenario skills)
                          False = mob phase (include "all" + "mob" scenario skills)
                          None = permanent stats only ("all" scenario skills for char sheet)

        Returns:
            Dict mapping stat_type -> list of individual values from each skill
            e.g., {"attack_speed": [6.5, 7.2], "final_damage": [23.6, 11.3], ...}

            Caller is responsible for combining these appropriately:
            - Additive stats (crit_rate, dex_flat, etc.): sum the list
            - Multiplicative stats (final_damage): product of (1 + v/100)
            - Special stats (attack_speed, defense_pen): use their formulas
        """
        bonuses: Dict[str, List[float]] = {}

        for skill_name, skill in self._stat_skills.items():
            if not skill.skill_bonuses:
                continue

            # Filter by scenario:
            # - "all" scenario skills always apply (permanent bonuses)
            # - "boss" scenario skills only apply when is_boss_phase=True
            # - "mob" scenario skills only apply when is_boss_phase=False
            # - When is_boss_phase=None, only include "all" scenario (for char sheet)
            if skill.scenario != "all":
                if is_boss_phase is None:
                    continue  # Exclude situational skills from char sheet
                if skill.scenario == "boss" and is_boss_phase is False:
                    continue
                if skill.scenario == "mob" and is_boss_phase is True:
                    continue

            if not self.char.is_skill_unlocked(skill_name):
                continue

            level = self.char.get_effective_skill_level(skill_name)

            # Add each stat bonus from this skill
            for stat_type, (base, factor_index) in skill.skill_bonuses.items():
                value = self.calc_skill_damage_with_factor(base, factor_index, level)
                if stat_type not in bonuses:
                    bonuses[stat_type] = []
                bonuses[stat_type].append(value)

        return bonuses

    def get_stat_conversions(self) -> List[Tuple[str, str, float]]:
        """
        Get active stat conversions from skills with stat_conversion defined.

        Returns list of (source_stat, target_stat, rate_pct) for unlocked skills.
        e.g., [("defense", "main_stat_flat", 12.5)] means convert 12.5% of defense to main stat.
        """
        conversions = []
        for skill_name, skill in self._skills.items():
            if skill.stat_conversion is None:
                continue
            if not self.char.is_skill_unlocked(skill_name):
                continue
            source, target, (base, per_level) = skill.stat_conversion
            level = self.char.get_effective_skill_level(skill_name)
            rate = self.calc_skill_value(base, per_level, level)
            conversions.append((source, target, rate))
        return conversions

    def get_effective_proc_chance(self, skill_name: str) -> float:
        """Get proc chance including mastery bonuses and skill-based modifiers.

        Combines:
        - Base proc_chance from skill definition
        - Mastery node bonuses (skill_proc_chance effect type)
        - Skill-based modifiers (proc_chance_modifier field on other skills)
        """
        skill = self._skills[skill_name]
        chance = skill.proc_chance

        # Add mastery node bonuses (e.g., "Venom - Chance" mastery)
        mastery_bonus = self.get_mastery_bonus(skill_name, "skill_proc_chance")
        chance += mastery_bonus / 100  # Mastery values are in %p, convert to fraction

        # Add skill-based proc chance modifiers (e.g., Meso Mastery -> meso_explosion)
        for other_name, other_skill in self._skills.items():
            if other_skill.proc_chance_modifier and skill_name in other_skill.proc_chance_modifier:
                if self.char.is_skill_unlocked(other_name):
                    level = self.char.get_effective_skill_level(other_name)
                    base, per_level = other_skill.proc_chance_modifier[skill_name]
                    chance += self.calc_skill_value(base, per_level, level) / 100

        return min(chance, 1.0)

    def get_finishing_blow_avg_damage(
        self,
        skill_name: str,
        is_boss_phase=None,
        active_buffs=None,
        num_enemies: int = 1,
    ) -> float:
        """Get average extra damage per use from finishing blow mechanic.

        Skills like Assassinate have an extra damage line every N uses.
        Returns the averaged extra damage (total_fb_damage / interval).
        """
        skill = self._skills[skill_name]
        if skill.finishing_blow_interval <= 0:
            return 0.0
        # Check mastery-gated unlock level (e.g., Snipe Empowered at L134)
        if skill.finishing_blow_unlock_level > 0 and self.char.level < skill.finishing_blow_unlock_level:
            return 0.0

        # Get finishing blow damage% with level scaling and mastery bonus
        level = self.char.get_effective_skill_level(skill_name)
        if skill.finishing_blow_factor_index >= 0:
            fb_pct = self.calc_skill_damage_with_factor(
                skill.finishing_blow_pct, skill.finishing_blow_factor_index, level
            )
        else:
            fb_pct = skill.finishing_blow_pct
        mastery_bonus = self.get_mastery_bonus(skill_name, "skill_finishing_blow_pct")
        if mastery_bonus > 0:
            fb_pct *= (1 + mastery_bonus / 100)

        # Calculate hit damage for the finishing blow line
        fb_hit_damage = self.calculate_hit_damage(
            fb_pct, skill.damage_type, skill_name,
            is_boss_phase=is_boss_phase,
            active_buffs=active_buffs,
            num_enemies=num_enemies,
        )

        # Average over N uses: finishing blow fires once every N uses
        return fb_hit_damage / skill.finishing_blow_interval

    def calculate_steal_attack_bonus(self, attack_speed_mult: float, num_enemies: int) -> float:
        """Calculate expected attack% bonus from Steal's uptime-based stacking.

        Each enemy hit has proc_chance to apply a debuff lasting duration seconds.
        Max 1 debuff per enemy, max 3 stacks total. Each stack = +5% attack.

        Boss (1 enemy): P(1 stack) = 1 - (1-p)^(aps*dur)
        Mob (N enemies): Expected stacks = min(3, N) * P(per-enemy active)
        """
        if not self.char.is_skill_unlocked("steal"):
            return 0.0

        steal_skill = self._skills.get("steal")
        if not steal_skill or not steal_skill.duration:
            return 0.0

        proc_chance = self.get_effective_proc_chance("steal")
        duration = self.get_effective_buff_duration("steal")

        ba_name = self.char.get_active_basic_attack()
        ba_skill = self._skills.get(ba_name) if ba_name else None
        ba_cast_time = ba_skill.cast_time if ba_skill else 1.0
        cast_time = self.get_cast_time(ba_cast_time, True, attack_speed_mult)
        attacks_per_second = 1 / cast_time
        attacks_in_window = attacks_per_second * duration

        # P(at least 1 proc on a given enemy within duration)
        p_active = 1 - (1 - proc_chance) ** attacks_in_window

        # Expected active stacks (each enemy independent, capped at 3)
        possible_stacks = min(3, num_enemies)
        expected_stacks = possible_stacks * p_active

        per_stack_bonus = self.get_skill_bonus_value("steal", "attack_pct")
        return per_stack_bonus * expected_stacks

    def get_buff_stat_bonuses(self, active_buffs: Optional[Set[str]] = None) -> Dict[str, List[float]]:
        """
        Get stat bonuses from BUFF skills that are currently active.

        BUFF skills like Nimble Feet and Sharp Eyes grant temporary stat bonuses.
        This method returns the full stat values (not uptime-weighted) since we
        track actual buff activation either via:
        - enabled_buffs (for stat matching mode - user toggles buffs on/off)
        - active_buffs parameter (for DPS simulation - dynamic tracking)

        Args:
            active_buffs: Set of buff names currently active (for simulation).
                         If None, uses self.char.enabled_buffs (for stat matching).
                         Empty set means no buffs active.

        Returns:
            Dict mapping stat_name -> list of values from active buffs.
            e.g., {"attack_speed": [15.0], "crit_rate": [10.2], "crit_damage": [52.8]}
        """
        buffs_to_check = active_buffs if active_buffs is not None else self.char.enabled_buffs
        bonuses: Dict[str, List[float]] = {}

        for skill_name, skill in self._buff_skills.items():
            if skill_name not in buffs_to_check:
                continue
            if not self.char.is_skill_unlocked(skill_name):
                continue
            if not skill.skill_bonuses:
                continue

            level = self.char.get_effective_skill_level(skill_name)

            for stat_name, (base, factor_index) in skill.skill_bonuses.items():
                value = self.calc_skill_damage_with_factor(base, factor_index, level)
                if stat_name not in bonuses:
                    bonuses[stat_name] = []
                bonuses[stat_name].append(value)

        return bonuses

    def apply_passive_skill_stats(self, is_boss_phase: Optional[bool] = None) -> Dict[str, List[Tuple[str, float]]]:
        """
        Apply passive skill stat bonuses AND global mastery stats to character.
        Returns special stat sources for proper formula calculation.

        Collects stats from:
        1. PASSIVE_STAT type skills (labeled "Passive Skills" in sources)
        2. Global mastery bonuses (labeled "Masteries" in sources)

        Simple additive stats are applied directly to character fields.
        Special stats (attack_speed, defense_pen, final_damage) are returned as
        source lists to be combined using proper formulas.

        Args:
            is_boss_phase: True = boss phase (include "all" + "boss" scenario skills)
                          False = mob phase (include "all" + "mob" scenario skills)
                          None = permanent stats only (for character sheet display)

        Returns:
            Dict with special stat source lists:
            {
                "attack_speed_sources": [("source_name", value), ...],
                "def_pen_sources": [("source_name", value), ...],
                "final_damage_sources": [("source_name", value), ...],
            }
        """
        # Collect passive skill bonuses
        skill_bonuses = self.get_all_skill_stat_bonuses(is_boss_phase)

        # Collect global mastery bonuses
        mastery_stats = get_global_mastery_stats(self.char.level)

        # Track sources for special stats
        special_sources: Dict[str, List[Tuple[str, float]]] = {
            "attack_speed_sources": [],
            "def_pen_sources": [],
            "final_damage_sources": [],
        }

        # Additive stats mapping: stat_name -> char_field
        additive_mappings = {
            "crit_rate": "crit_rate",
            "crit_damage": "crit_damage",
            "dex_flat": "main_stat_flat",
            "main_stat_flat": "main_stat_flat",
            "dex_pct": "main_stat_pct",
            "attack_pct": "attack",
            "basic_attack_damage": "basic_attack_damage",
            "skill_damage": "skill_damage",
            "damage_pct": "damage_pct",
            "min_dmg_mult": "min_dmg_mult",
            "max_dmg_mult": "max_dmg_mult",
        }

        # Apply passive skill bonuses (additive stats)
        for stat_name, char_field in additive_mappings.items():
            if stat_name in skill_bonuses:
                total = sum(skill_bonuses[stat_name])
                current = getattr(self.char, char_field, 0)
                setattr(self.char, char_field, current + total)

        # Apply global mastery bonuses (additive stats)
        for stat_name, char_field in additive_mappings.items():
            if stat_name in mastery_stats:
                value = mastery_stats[stat_name]
                current = getattr(self.char, char_field, 0)
                setattr(self.char, char_field, current + value)

        # Special stats from passive skills - return as source lists
        if "attack_speed" in skill_bonuses:
            for value in skill_bonuses["attack_speed"]:
                special_sources["attack_speed_sources"].append(("Passive Skills", value))

        if "defense_pen" in skill_bonuses:
            for value in skill_bonuses["defense_pen"]:
                special_sources["def_pen_sources"].append(("Passive Skills", value / 100))

        if "final_damage" in skill_bonuses:
            for value in skill_bonuses["final_damage"]:
                special_sources["final_damage_sources"].append(("Passive Skills", value / 100))

        # Special stats from global masteries - return as source lists
        if "attack_speed" in mastery_stats:
            special_sources["attack_speed_sources"].append(("Masteries", mastery_stats["attack_speed"]))

        if "defense_pen" in mastery_stats:
            special_sources["def_pen_sources"].append(("Masteries", mastery_stats["defense_pen"] / 100))

        if "final_damage" in mastery_stats:
            special_sources["final_damage_sources"].append(("Masteries", mastery_stats["final_damage"] / 100))

        return special_sources

    def get_cast_time(self, base_time: float, scales_with_as: bool, attack_speed_mult: float) -> float:
        """Calculate actual cast time with linear attack speed scaling.

        Cast time is inversely proportional to attack speed:
        cast_time = base_time / attack_speed_mult

        Args:
            base_time: Base cast time in seconds (typically 1.0)
            scales_with_as: Whether this skill is affected by attack speed
            attack_speed_mult: Attack speed multiplier (1.0 = base, 2.5 = max)
        """
        if not scales_with_as:
            return base_time

        # Simple linear scaling: faster attack speed = shorter cast time
        return base_time / attack_speed_mult

    def get_effective_buff_duration(self, skill_name: str) -> float:
        """
        Return a buff skill's duration after applying mastery 'skill_duration'
        bonus and the character-wide buff_duration_pct stat.

        Use for any buff/proc whose duration represents an uptime window.
        Do NOT use for summons (Phoenix, Arrow Platter, Dark Flare, etc.) —
        summon durations are not buffs and intentionally not extended.
        """
        skill = self._skills.get(skill_name)
        if skill is None or skill.duration <= 0:
            return 0.0
        duration = skill.duration
        mastery_bonus = self.get_mastery_bonus(skill_name, "skill_duration")
        if mastery_bonus > 0:
            duration *= (1 + mastery_bonus)
        if self.char.buff_duration_pct > 0:
            duration *= (1 + self.char.buff_duration_pct / 100)
        return duration

    def calculate_mortal_blow_uptime(self, attack_speed_mult: float) -> float:
        """
        Calculate Mortal Blow uptime based on hit rate.

        Mortal Blow activates after 50 hits, lasts 5 sec (+ 5 sec with mastery = 10 sec).
        Hit sources that COUNT:
        - Arrow Stream/basic attacks (5 hits per attack)
        - Hurricane (20 hits base, 35 with mastery)
        - Phoenix (1 hit per attack)
        - Final Attack procs (1 hit)
        - Flash Mirage procs (1 hit)
        - Covering Fire (3 hits)

        Hit sources that DON'T count:
        - Arrow Platter
        - Quiver Cartridge

        Args:
            attack_speed_mult: Attack speed multiplier (1.0 = base, 2.5 = max)
        """
        if not self.char.is_skill_unlocked("mortal_blow"):
            return 0.0

        # Get cast time based on attack speed (using BA's animation time)
        basic_skill_name = self.char.get_active_basic_attack()
        ba_skill = self._skills.get(basic_skill_name) if basic_skill_name else None
        ba_cast_time = ba_skill.cast_time if ba_skill else 1.0
        cast_time = self.get_cast_time(ba_cast_time, True, attack_speed_mult)

        # Calculate hits per second from each source dynamically
        hits_per_second = 0.0

        # Basic attack
        if basic_skill_name and self.char.is_skill_unlocked(basic_skill_name):
            basic_hits = self.get_skill_hits(basic_skill_name)
            attacks_per_second = 1 / cast_time
            hits_per_second += basic_hits * attacks_per_second

        # Active skills (contribute hits based on cooldown)
        for skill_name, skill in self._active_skills.items():
            if not self.char.is_skill_unlocked(skill_name):
                continue
            skill_hits = self.get_skill_hits(skill_name)
            skill_cd = self.char.get_effective_skill_cooldown(skill.cooldown, 0)
            if skill_cd > 0:
                hits_per_second += skill_hits / skill_cd

        # Summons (contribute hits based on interval and uptime)
        # Skip companion summons — those are managed by the burst-window
        # scheduler and their contribution to MB is handled via the snapshot's
        # mortal_blow_forced flag, not by averaging into player MB uptime.
        companion_keys_mb = getattr(self, '_companion_summon_keys', None) or set()
        for skill_name, skill in self._summon_skills.items():
            if skill_name in companion_keys_mb:
                continue
            if not self.char.is_skill_unlocked(skill_name):
                continue
            if skill.duration <= 0 or skill.attack_interval <= 0:
                continue
            interval = skill.attack_interval
            flat_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval")
            if flat_reduction != 0:
                interval = max(1.0, interval + flat_reduction)
            pct_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval_pct")
            if pct_reduction != 0:
                interval = max(1.0, interval * (1 + pct_reduction / 100))
            # Calculate uptime
            if skill.cooldown > 0:
                mastery_pct_reduction = self.get_mastery_bonus(skill_name, "skill_cooldown_reduction") * 100
                skill_cd = self.char.get_effective_skill_cooldown(skill.cooldown, mastery_pct_reduction)
                uptime = min(skill.duration / skill_cd, 1.0)
            else:
                uptime = 1.0
            hits_per_second += (1 / interval) * uptime

        # Procs (contribute hits based on proc chance and possibly ICD)
        for skill_name, skill in self._proc_skills.items():
            if not self.char.is_skill_unlocked(skill_name):
                continue
            proc_chance = skill.proc_chance
            attacks_per_second = 1 / cast_time
            if skill.cooldown > 0:
                # Has ICD - max procs limited
                mastery_pct_reduction = self.get_mastery_bonus(skill_name, "skill_cooldown_reduction")
                icd = skill.cooldown * (1 - mastery_pct_reduction)
                hits_per_second += min(proc_chance * attacks_per_second, 1 / icd)
            else:
                hits_per_second += proc_chance * attacks_per_second

        # Calculate build time to reach 50 hits
        hits_to_activate = 50
        build_time = hits_to_activate / hits_per_second if hits_per_second > 0 else 999

        # Duration: 5 sec base + mastery bonus (flat seconds), then buff duration %
        duration = 5.0
        duration += self.get_mastery_bonus("mortal_blow", "skill_duration")
        duration *= (1 + self.char.buff_duration_pct / 100)

        # Uptime = duration / (duration + build_time)
        uptime = duration / (duration + build_time)

        return uptime

    def calc_skill_damage_with_factor(self, base_damage_pct: float, factor_index: int, level: int) -> float:
        """Calculate skill damage using multiplicative factor table.

        Formula: int(base * factor[level][index] / 1000 * 10) / 10
        This matches the in-game formula exactly (verified: Assassinate at L6 = 1433.6%).
        """
        level = max(1, level)
        if level in SKILL_LEVEL_FACTORS:
            factor = SKILL_LEVEL_FACTORS[level][factor_index]
        else:
            # Table ends at L300; extrapolate linearly using the last delta.
            # Better than hard-capping since INC3/4/etc. are linear throughout.
            max_lv = max(SKILL_LEVEL_FACTORS)
            delta = SKILL_LEVEL_FACTORS[max_lv][factor_index] - SKILL_LEVEL_FACTORS[max_lv - 1][factor_index]
            factor = SKILL_LEVEL_FACTORS[max_lv][factor_index] + delta * (level - max_lv)
        return int(base_damage_pct * factor / 1000 * 10) / 10

    def get_skill_damage_pct(self, skill_name: str) -> float:
        """Get total damage % for a skill including level scaling and masteries."""
        # Check cache first
        if skill_name in self._skill_damage_cache:
            return self._skill_damage_cache[skill_name]

        if skill_name not in self._skills:
            return 0

        skill = self._skills[skill_name]
        level = self.char.get_effective_skill_level(skill_name)

        # Base + level scaling (multiplicative if factor index available, else additive fallback)
        if skill.level_factor_index >= 0:
            damage = self.calc_skill_damage_with_factor(skill.base_damage_pct, skill.level_factor_index, level)
        else:
            damage = self.calc_skill_value(skill.base_damage_pct, skill.damage_per_level, level)

        # Add mastery damage bonus (additive to base)
        mastery_bonus = self.get_mastery_bonus(skill_name, "skill_damage_pct")
        # Mastery bonuses are often percentage increases on top
        damage *= (1 + mastery_bonus / 100)

        # Cache the result
        self._skill_damage_cache[skill_name] = damage
        return damage

    def get_skill_hits(self, skill_name: str) -> int:
        """Get total hits for a skill including masteries."""
        # Check cache first
        if skill_name in self._skill_hits_cache:
            return self._skill_hits_cache[skill_name]

        if skill_name not in self._skills:
            return 1

        skill = self._skills[skill_name]
        hits = skill.base_hits

        # Add mastery hit bonuses
        hits += int(self.get_mastery_bonus(skill_name, "skill_hits"))

        # Hurricane special case
        if skill_name == "hurricane" and self.char.level >= 134:
            hits = 35  # Hurricane - Extend mastery

        # Cache the result
        self._skill_hits_cache[skill_name] = hits
        return hits

    def get_skill_targets(self, skill_name: str) -> int:
        """Get total targets for a skill including masteries and equipment bonuses."""
        # Check cache first
        if skill_name in self._skill_targets_cache:
            return self._skill_targets_cache[skill_name]

        if skill_name not in self._skills:
            return 1

        skill = self._skills[skill_name]
        targets = skill.base_targets

        # Add mastery target bonuses (skill-specific)
        targets += int(self.get_mastery_bonus(skill_name, "skill_targets"))

        # Add target bonuses from other skills (e.g., Flash Mirage II -> Flash Mirage)
        targets += int(self.get_skill_bonus(skill_name, "targets"))

        # For basic attacks, also add global BA target bonuses
        if skill.skill_type == SkillType.BASIC_ATTACK:
            # Global mastery bonus (+1 at level 62)
            targets += int(self.get_global_stat("basic_attack_targets"))
            # Bonus from equipment potentials (stored on character state)
            targets += getattr(self.char, 'ba_target_bonus', 0)

        # Cache the result
        self._skill_targets_cache[skill_name] = targets
        return targets

    def get_effective_targets(
        self,
        skill_name: str,
        num_enemies: int,
        mob_time_fraction: float,
    ) -> float:
        """
        Calculate effective targets for a skill in the given combat scenario.

        During mob waves: hit min(skill_targets, num_enemies) enemies
        During boss: hit 1 enemy (bosses are always single target)

        Returns weighted average based on mob_time_fraction:
            effective = (mob_targets × mob_fraction) + (boss_targets × (1 - mob_fraction))

        Args:
            skill_name: Name of the skill
            num_enemies: Number of enemies during mob waves (12 for stages)
            mob_time_fraction: Fraction of fight spent on mobs (0.0-1.0)

        Returns:
            Effective target count for DPS calculation
        """
        targets = self.get_skill_targets(skill_name)

        # During mob waves: capped by num_enemies
        # During boss: always 1 target
        mob_targets = min(targets, num_enemies)
        boss_targets = 1

        return (mob_targets * mob_time_fraction) + (boss_targets * (1 - mob_time_fraction))

    def get_total_stat_bonus(self, stat_type: str) -> float:
        """
        Get total bonus for a stat type from passive skills and global masteries.

        Passive skills: Scale with +All Skills
        Global masteries: Fixed bonuses, don't scale with +All Skills
        """
        total = 0.0

        # From passive stat skills (these SCALE with +All Skills)
        for skill_name, skill in self._stat_skills.items():
            if skill.skill_bonuses:
                if stat_type in skill.skill_bonuses:
                    if self.char.is_skill_unlocked(skill_name):
                        level = self.char.get_effective_skill_level(skill_name)
                        base, factor_index = skill.skill_bonuses[stat_type]
                        total += self.calc_skill_damage_with_factor(base, factor_index, level)

        # From global masteries (FIXED, don't scale with +All Skills)
        total += self.get_global_stat(stat_type)

        return total

    def calculate_hit_damage(
        self,
        skill_damage_pct: float,
        damage_type: DamageType,
        skill_name: str = "",
        is_boss_phase: Optional[bool] = None,
        attack_speed_mult: Optional[float] = None,
        active_buffs: Optional[Set[str]] = None,
        num_enemies: int = 1,
        stat_override: Optional[PlayerStatSnapshot] = None,
    ) -> float:
        """Calculate damage for a single hit.

        Args:
            skill_damage_pct: Skill damage percentage
            damage_type: BASIC or SKILL
            skill_name: Name of skill for mastery lookups
            is_boss_phase: If True, apply boss damage multipliers.
                          If False, apply normal monster damage multipliers.
                          If None (default), use old behavior (boss_mult applied to all).
            attack_speed_mult: Attack speed multiplier for mortal blow uptime calculation.
                              If None, defaults to 1.0 (no attack speed bonus).
            active_buffs: Set of currently active buff skill names (for crit bonuses etc).
                         If None, no buff bonuses are applied.
            num_enemies: Number of enemies (for Steal uptime calculation).
                        Boss phase callers should pass 1.
            stat_override: Optional snapshot of the player's offensive stats at a
                          specific point in time. When provided, all numerical stat
                          reads (attack, main stat, damage%, boss/normal damage,
                          basic/skill damage, final damage, crit, def pen) are taken
                          from the snapshot instead of self.char + live bonuses.
                          Buff/Mortal-Blow/Smokescreen logic still uses the
                          `active_buffs` argument and live calc state — extended
                          consumption of the snapshot's optional fields happens in
                          Phase 2 of the burst-window scheduler work.
                          When None (default), behavior is unchanged from before.
        """
        if attack_speed_mult is None:
            attack_speed_mult = 1.0

        # --- Resolve "effective" stat values ----------------------------------
        # When stat_override is provided, read pre-totaled values from the
        # snapshot (no further summation). When None, fall back to the live
        # char + passive-bonus aggregation that existed before this change.
        if stat_override is not None:
            eff_attack = stat_override.attack
            eff_main_stat_flat = stat_override.main_stat_flat_total
            eff_main_stat_pct = stat_override.main_stat_pct_total
            eff_main_stat_conv = stat_override.main_stat_conversion
            eff_secondary_flat = stat_override.secondary_stat_flat
            eff_secondary_pct = stat_override.secondary_stat_pct
            eff_damage_pct = stat_override.damage_pct_total
            eff_boss_damage = stat_override.boss_damage
            eff_normal_damage = stat_override.normal_damage
            eff_basic_attack_damage = stat_override.basic_attack_damage_total
            eff_skill_damage = stat_override.skill_damage_total
            eff_final_damage_pct = stat_override.final_damage_pct
            eff_crit_rate = stat_override.crit_rate_total
            eff_crit_damage = stat_override.crit_damage
            eff_def_pen_pct = stat_override.def_pen_pct
            # Recompute def_pen multiplier since the cached one is built from char.
            _eff_def_pen_dec = min(eff_def_pen_pct / 100, 1.0)
            eff_def_pen_mult = 1 / (1 + self.enemy_def * (1 - _eff_def_pen_dec))
        else:
            eff_attack = self.char.attack
            eff_main_stat_flat = self.char.main_stat_flat + self.get_global_stat("main_stat_flat")
            eff_main_stat_pct = self.char.main_stat_pct + self.get_total_stat_bonus("main_stat_pct")
            eff_main_stat_conv = self.char.main_stat_conversion
            eff_secondary_flat = self.char.secondary_stat_flat
            eff_secondary_pct = self.char.secondary_stat_pct
            eff_damage_pct = self.char.damage_pct + self.get_total_stat_bonus("damage_pct")
            eff_boss_damage = self.char.boss_damage
            eff_normal_damage = self.char.normal_damage
            eff_basic_attack_damage = self.char.basic_attack_damage + self.get_total_stat_bonus("basic_attack_damage")
            eff_skill_damage = self.char.skill_damage + self.get_total_stat_bonus("skill_damage")
            eff_final_damage_pct = self.char.final_damage_pct
            eff_crit_rate = self.char.crit_rate
            eff_crit_damage = self.char.crit_damage
            eff_def_pen_pct = self.char.def_pen_pct
            eff_def_pen_mult = self._def_pen_mult

        base = eff_attack * (skill_damage_pct / 100)

        # Main stat (1% per point) and secondary stat (0.25% per point)
        # stat_dmg_pct = main_stat * 0.01 + secondary_stat * 0.0025
        # multiplier = 1 + (stat_dmg_pct / 100)
        total_main_stat = eff_main_stat_flat * (1 + eff_main_stat_pct / 100)
        total_main_stat += eff_main_stat_conv  # skill-converted stat (e.g. Shield Mastery), not multiplied by %
        total_secondary_stat = eff_secondary_flat * (1 + eff_secondary_pct / 100)
        main_stat_mult = 1 + (total_main_stat / 10000) + (total_secondary_stat / 40000)

        # Damage %
        damage_mult = 1 + eff_damage_pct / 100

        # Phase-specific damage multiplier (for realistic DPS calculation)
        if is_boss_phase is True:
            # Boss phase: apply global boss damage + skill-specific boss damage masteries
            phase_dmg = eff_boss_damage
            phase_dmg += self.get_mastery_bonus(skill_name, "skill_boss_damage")
            phase_mult = 1 + phase_dmg / 100
        elif is_boss_phase is False:
            # Mob phase: apply global normal damage + skill-specific normal monster damage masteries
            phase_dmg = eff_normal_damage
            phase_dmg += self.get_mastery_bonus(skill_name, "skill_normal_monster_damage")
            # Add innate normal monster damage from skill definition (e.g., Arrow Platter +200%)
            if skill_name and skill_name in self._skills:
                phase_dmg += self._skills[skill_name].innate_normal_monster_damage
            phase_mult = 1 + phase_dmg / 100
        else:
            # Legacy behavior (is_boss_phase=None): apply boss_mult to everything
            # This preserves backward compatibility for existing calculate_total_dps()
            boss_dmg = eff_boss_damage
            boss_dmg += self.get_mastery_bonus(skill_name, "skill_boss_damage")
            phase_mult = 1 + boss_dmg / 100

        # Skill/Basic Attack damage type
        # Note: get_total_stat_bonus already includes global mastery bonuses
        if damage_type == DamageType.BASIC:
            type_bonus = eff_basic_attack_damage
        else:
            type_bonus = eff_skill_damage

        type_mult = 1 + type_bonus / 100

        # Final damage (multiplicative)
        # Note: Global FD from extreme_archery and armor_break should be in char.final_damage_pct
        # via apply_passive_skill_stats() - they are NOT calculated here to avoid double-counting
        final_mult = 1 + eff_final_damage_pct / 100

        # Mortal Blow - FD with uptime calculation (kept inline due to variable uptime).
        # When a stat_override snapshot was passed with mortal_blow_forced=True
        # (the companion-summon path: assume optimal pre-stack), credit the
        # full FD bonus rather than averaging by player MB uptime.
        mb_fd = self.get_skill_bonus_value("mortal_blow", "final_damage")
        if mb_fd > 0:
            if stat_override is not None and stat_override.mortal_blow_forced:
                mb_uptime = 1.0
            else:
                mb_uptime = self.calculate_mortal_blow_uptime(attack_speed_mult)
            final_mult *= (1 + (mb_fd * mb_uptime) / 100)

        # Shadow Shifter - FD buff with downtime after counterattack trigger
        # PASSIVE_PROC so not auto-applied; handled here like Mortal Blow
        ss_fd = self.get_skill_bonus_value("shadow_shifter", "final_damage")
        if ss_fd > 0:
            ss_skill = self._skills["shadow_shifter"]
            # Mastery "Shadow Shifter - Final Damage" adds 10%p FD
            ss_mastery_fd = self.get_mastery_bonus("shadow_shifter", "skill_final_damage")
            total_ss_fd = ss_fd + ss_mastery_fd
            # Uptime = (cooldown - downtime) / cooldown
            ss_uptime = (ss_skill.cooldown - ss_skill.buff_downtime) / ss_skill.cooldown
            final_mult *= (1 + total_ss_fd * ss_uptime / 100)

        # Venom Weaken: target takes +X% more damage while Venom DoT is active.
        # Same multiplicative mechanic as Coin/Peach artifacts — diminishing returns applies.
        venom_weaken = self.get_mastery_bonus("venom", "skill_effect")
        if venom_weaken > 0 and self.char.is_skill_unlocked("venom"):
            venom_skill = self._skills.get("venom")
            if venom_skill:
                eff_as = attack_speed_mult if attack_speed_mult is not None else self.calculate_attack_speed_mult()
                ba_name = self.char.get_active_basic_attack()
                ba_skill = self._skills.get(ba_name) if ba_name else None
                ba_cast_time = ba_skill.cast_time if ba_skill else 1.0
                cast_time = self.get_cast_time(ba_cast_time, True, eff_as)
                attacks_in_window = (1.0 / cast_time) * venom_skill.duration
                venom_uptime = 1.0 - (1.0 - venom_skill.proc_chance) ** attacks_in_window
                final_mult *= (1 + venom_weaken / 100 * venom_uptime)

        # Steal - uptime-based attack buff (PASSIVE_PROC, not auto-applied)
        steal_attack = self.calculate_steal_attack_bonus(attack_speed_mult, num_enemies)
        if steal_attack > 0:
            final_mult *= (1 + steal_attack / 100)

        # Skill-specific final damage from SKILL_ENHANCER skills (Maple Hero, AFA, EQ, etc.)
        # Each enhancer grants FD to specific target skills; all FD from enhancers is additive
        enhancer_fd = 0.0
        for enhancer_name, enhancer_skill in self._enhancer_skills.items():
            if not self.char.is_skill_unlocked(enhancer_name):
                continue
            if not enhancer_skill.skill_bonuses or skill_name not in enhancer_skill.skill_bonuses:
                continue
            enhancer_fd += self.get_skill_bonus_value(enhancer_name, skill_name)
        # Add mastery bonus for skill-specific final damage (e.g., Final Attack mastery)
        enhancer_fd += self.get_mastery_bonus(skill_name, "skill_final_damage")
        if enhancer_fd > 0:
            final_mult *= (1 + enhancer_fd / 100)

        # Crit calculation
        # Note: when stat_override is active, eff_crit_rate / eff_crit_damage
        # already include any passive crit bonuses baked into the snapshot, so
        # we skip the live get_total_stat_bonus("crit_rate") addition.
        crit_rate_bonus = (
            0.0 if stat_override is not None
            else self.get_total_stat_bonus("crit_rate")
        )
        crit_dmg_bonus = 0.0

        # Add bonuses from active buffs (e.g., Sharp Eyes, Dark Resonance)
        buff_attack_pct = 0.0
        buff_final_damage = 0.0
        if active_buffs:
            buff_bonuses = self.get_buff_stat_bonuses(active_buffs)
            for cr_value in buff_bonuses.get("crit_rate", []):
                crit_rate_bonus += cr_value
            for cd_value in buff_bonuses.get("crit_damage", []):
                crit_dmg_bonus += cd_value
            for ap_value in buff_bonuses.get("attack_pct", []):
                buff_attack_pct += ap_value
            for fd_value in buff_bonuses.get("final_damage", []):
                buff_final_damage += fd_value

        crit_rate = min((eff_crit_rate + crit_rate_bonus) / 100, 1.0)

        # Concentration (crit damage stacks) - PASSIVE_BUFF so not in char stats.
        # Snapshot path can override the implicit 7-stack assumption: the
        # companion-summon path forces max stacks ("optimal pre-stack" — see
        # plan Phase 4) regardless of what the player can actually maintain.
        conc_per_stack = self.get_skill_bonus_value("concentration", "crit_damage")
        if stat_override is not None and stat_override.concentration_forced_stacks is not None:
            conc_stacks = stat_override.concentration_forced_stacks
        else:
            conc_stacks = 7
        crit_dmg_bonus += conc_per_stack * conc_stacks

        # Smokescreen mastery: +crit damage while Smokescreen is active
        sm_crit = self.get_mastery_bonus("smokescreen", "skill_effect")
        if sm_crit > 0 and self.char.is_skill_unlocked("smokescreen"):
            if active_buffs is not None and "smokescreen" in active_buffs:
                # During simulation: buff is explicitly active
                crit_dmg_bonus += sm_crit
            elif active_buffs is None:
                # Outside simulation: weight by buff uptime
                from libs.cooldown_calc import calculate_buff_uptime
                sm_skill = self._skills["smokescreen"]
                sm_cd = self.char.get_effective_skill_cooldown(sm_skill.cooldown, 0)
                sm_dur = self.get_effective_buff_duration("smokescreen")
                sm_uptime = calculate_buff_uptime(
                    cooldown=sm_cd, buff_duration=sm_dur, fight_duration=60.0)
                crit_dmg_bonus += sm_crit * sm_uptime

        # Sharp Eyes: +20% of own crit_damage (self is an allied player)
        se_skill = self._skills.get("sharp_eyes")
        if se_skill and se_skill.self_crit_damage_pct > 0 and self.char.is_skill_unlocked("sharp_eyes"):
            se_pct = se_skill.self_crit_damage_pct / 100
            if active_buffs is not None:
                if "sharp_eyes" in active_buffs:
                    crit_dmg_bonus += se_pct * eff_crit_damage
            else:
                from libs.cooldown_calc import calculate_buff_uptime
                se_cd = self.char.get_effective_skill_cooldown(se_skill.cooldown, 0)
                se_dur = self.get_effective_buff_duration("sharp_eyes")
                se_uptime = calculate_buff_uptime(se_cd, se_dur, 60.0)
                crit_dmg_bonus += se_pct * eff_crit_damage * se_uptime

        crit_damage = eff_crit_damage + crit_dmg_bonus
        crit_mult = 1 + crit_rate * (crit_damage / 100)

        def_pen_mult = eff_def_pen_mult
        # Apply def_pen from active buffs (Smokescreen)
        if active_buffs:
            buff_def_pen = sum(buff_bonuses.get("def_pen", []))
            if buff_def_pen > 0:
                total_def_pen = min((eff_def_pen_pct + buff_def_pen) / 100, 1.0)
                def_pen_mult = 1 / (1 + self.enemy_def * (1 - total_def_pen))

        # Apply buff attack % (Hyper Body, Cross Over Chains, Dark Resonance, Dark Sight)
        if buff_attack_pct > 0:
            base *= (1 + buff_attack_pct / 100)
        # Apply buff final damage (Into Darkness, Smokescreen)
        if buff_final_damage > 0:
            final_mult *= (1 + buff_final_damage / 100)

        damage = base * main_stat_mult * damage_mult * phase_mult * type_mult
        damage *= final_mult * crit_mult * def_pen_mult

        # Quiver Cartridge: Add Enchanted Quiver - Drain additional damage
        # This is a separate damage instance that does NOT get Enchanted Quiver FD
        # but does get all other multipliers (stats, crit, defense pen, etc.)
        if skill_name == "quiver_cartridge":
            drain_dmg_pct = self.get_scaled_mastery_bonus("quiver_cartridge", "skill_additional_damage")
            if drain_dmg_pct > 0:
                # Calculate drain damage with same multipliers but without EQ FD
                drain_base = self.char.attack * (drain_dmg_pct / 100)
                drain_damage = drain_base * main_stat_mult * damage_mult * phase_mult * type_mult
                # Apply final_mult WITHOUT the EQ FD portion
                # EQ FD is already in final_mult, so we need to remove it
                eq_fd = self.get_skill_bonus_value("enchanted_quiver", "quiver_cartridge")
                if eq_fd > 0:
                    drain_final_mult = final_mult / (1 + eq_fd / 100)
                else:
                    drain_final_mult = final_mult
                drain_damage *= drain_final_mult * crit_mult * def_pen_mult
                damage += drain_damage

        return damage

    def _precalculate_skill_values(
        self,
        num_enemies: int,
        attack_speed_mult: float,
        active_buffs: Optional[Set[str]] = None,
    ) -> Dict[str, SkillActionValue]:
        """Precalculate damage values for all player action skills in both phases.

        This enables efficient simulation by calculating damage once per skill
        rather than once per action tick.

        Args:
            num_enemies: Number of enemies during mob phase (for target calculation)
            attack_speed_mult: Attack speed multiplier (1.0 = base, 2.5 = max)
            active_buffs: Set of currently active buff skill names (for crit bonuses etc)

        Returns:
            Dictionary mapping skill name to SkillActionValue with mob/boss damage
        """
        values = {}

        # Basic Attack (current tier based on level)
        ba_name = self.char.get_active_basic_attack()
        if ba_name and self.char.is_skill_unlocked(ba_name):
            ba_skill = self._skills[ba_name]
            hits = self.get_skill_hits(ba_name)
            targets_mob = min(self.get_skill_targets(ba_name), num_enemies)
            cast_time = self.get_cast_time(ba_skill.cast_time, ba_skill.scales_with_attack_speed, attack_speed_mult)

            dmg_mob = self.calculate_hit_damage(
                self.get_skill_damage_pct(ba_name),
                ba_skill.damage_type,
                ba_name,
                is_boss_phase=False,
                active_buffs=active_buffs,
                num_enemies=num_enemies,
            )
            dmg_boss = self.calculate_hit_damage(
                self.get_skill_damage_pct(ba_name),
                ba_skill.damage_type,
                ba_name,
                is_boss_phase=True,
                active_buffs=active_buffs,
                num_enemies=1,
            )

            damage_mob = dmg_mob * hits * targets_mob
            damage_boss = dmg_boss * hits * 1  # Single target during boss phase

            values[ba_name] = SkillActionValue(
                skill_name=ba_name,
                damage_per_use_mob=damage_mob,
                damage_per_use_boss=damage_boss,
                cast_time=cast_time,
                cooldown=0,  # No cooldown for basic attack
                dps_value_mob=damage_mob / cast_time,
                dps_value_boss=damage_boss / cast_time,
            )

        # Active skills
        for skill_name, skill in self._active_skills.items():
            if not self.char.is_skill_unlocked(skill_name):
                continue
            hits = self.get_skill_hits(skill_name)
            targets_mob = min(self.get_skill_targets(skill_name), num_enemies)

            # Calculate cast time
            if skill.attack_interval > 0:
                # Hurricane: fires arrows over time, attack speed affects firing rate
                base_cast_time = hits * skill.attack_interval
                if skill.scales_with_attack_speed:
                    skill_cast_time = base_cast_time / attack_speed_mult
                else:
                    skill_cast_time = base_cast_time
            else:
                skill_cast_time = self.get_cast_time(skill.cast_time, skill.scales_with_attack_speed, attack_speed_mult)

            dmg_mob = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=False,
                active_buffs=active_buffs,
                num_enemies=num_enemies,
            )
            dmg_boss = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=True,
                active_buffs=active_buffs,
                num_enemies=1,
            )

            # Get effective cooldown with hat reduction
            effective_cd = self.char.get_effective_skill_cooldown(skill.cooldown, 0)

            damage_mob = dmg_mob * hits * targets_mob
            damage_boss = dmg_boss * hits * 1  # Single target during boss

            # Finishing blow: extra damage line every N uses (e.g., Assassinate)
            if skill.finishing_blow_interval > 0:
                fb_boss = self.get_finishing_blow_avg_damage(
                    skill_name, is_boss_phase=True, active_buffs=active_buffs, num_enemies=1)
                damage_boss += fb_boss * 1
                if not skill.finishing_blow_boss_only:
                    fb_mob = self.get_finishing_blow_avg_damage(
                        skill_name, is_boss_phase=False, active_buffs=active_buffs, num_enemies=num_enemies)
                    damage_mob += fb_mob * targets_mob

            # DoT component: extra damage ticks after cast (e.g., Sudden Raid)
            if skill.dot_damage_pct > 0 and skill.dot_duration > 0:
                dot_ticks = int(skill.dot_duration / skill.dot_interval)
                dot_dmg_mob = self.calculate_hit_damage(
                    skill.dot_damage_pct, skill.damage_type, skill_name,
                    is_boss_phase=False, active_buffs=active_buffs, num_enemies=num_enemies)
                dot_dmg_boss = self.calculate_hit_damage(
                    skill.dot_damage_pct, skill.damage_type, skill_name,
                    is_boss_phase=True, active_buffs=active_buffs, num_enemies=1)
                damage_mob += dot_dmg_mob * dot_ticks * targets_mob
                damage_boss += dot_dmg_boss * dot_ticks * 1

            values[skill_name] = SkillActionValue(
                skill_name=skill_name,
                damage_per_use_mob=damage_mob,
                damage_per_use_boss=damage_boss,
                cast_time=skill_cast_time,
                cooldown=effective_cd,
                dps_value_mob=damage_mob / skill_cast_time,
                dps_value_boss=damage_boss / skill_cast_time,
            )

        # Summons are NOT player actions — all summon damage is handled by
        # _calc_summons_dps_phased as background DPS. Adding them here would
        # double-count their damage. Cast time opportunity cost is negligible
        # (<1% of fight time) so we skip summons entirely from the action pool.
        #
        # Note: BUFF skills (Nimble Feet, Sharp Eyes) are handled via get_buff_stat_bonuses()
        # Their stat bonuses are weighted by uptime and included in attack_speed_mult, crit_rate, etc.
        # They don't need SkillActionValue entries since their benefit is baked into the stats.

        return values

    def _get_available_buffs(self) -> Dict[str, SkillData]:
        """Get all unlocked BUFF skills that can be cast."""
        return {
            k: v for k, v in self._buff_skills.items()
            if self.char.is_skill_unlocked(k) and v.skill_bonuses and v.duration > 0
        }

    def _calculate_buff_dps_value(
        self,
        buff_name: str,
        buff_skill: SkillData,
        remaining_fight_time: float,
        current_active_buffs: Set[str],
        current_attack_speed_mult: float,
        num_enemies: int,
        is_boss: bool,
        skill_values_getter: Optional[Callable[[float, Set[str]], Dict[str, 'SkillActionValue']]] = None,
    ) -> float:
        """
        Score for casting a buff now, averaged as DPS over the lookahead horizon.

        Returns: total damage produced over min(LOOKAHEAD_HORIZON_S, remaining_fight)
        seconds if we follow this plan, divided by that horizon. All plans use the
        same horizon so they are directly comparable.

        Plan timeline:
        - cast_time seconds with NO damage (player is casting)
        - buff_active_time seconds at boosted BA DPS (buff is up)
        - rest of horizon at baseline BA DPS (buff has expired)
        """
        horizon = min(LOOKAHEAD_HORIZON_S, remaining_fight_time)
        if horizon <= 0:
            return 0.0

        cast_time = self.get_cast_time(buff_skill.cast_time, False, current_attack_speed_mult)
        if cast_time >= horizon:
            return 0.0

        ba_name = self.char.get_active_basic_attack()
        if not ba_name:
            return 0.0

        # Baseline BA DPS at the current (pre-buff) state — used for the
        # tail of the horizon after the buff expires.
        if skill_values_getter is not None:
            cur_sv = skill_values_getter(current_attack_speed_mult, current_active_buffs)
        else:
            cur_sv = self._precalculate_skill_values(num_enemies, current_attack_speed_mult, current_active_buffs)
        if ba_name not in cur_sv:
            return 0.0
        baseline_ba_dps = cur_sv[ba_name].dps_value_boss if is_boss else cur_sv[ba_name].dps_value_mob

        # Boosted BA DPS while the buff is active.
        new_buffs = current_active_buffs | {buff_name}
        new_attack_speed_mult = self.calculate_attack_speed_mult(new_buffs)
        if skill_values_getter is not None:
            new_sv = skill_values_getter(new_attack_speed_mult, new_buffs)
        else:
            new_sv = self._precalculate_skill_values(num_enemies, new_attack_speed_mult, new_buffs)
        boosted_ba_dps = new_sv[ba_name].dps_value_boss if is_boss else new_sv[ba_name].dps_value_mob

        # Buff active for min(duration, post-cast portion of horizon).
        effective_duration = self.get_effective_buff_duration(buff_name)
        buff_active_time = min(effective_duration, horizon - cast_time)
        post_buff_time = max(0.0, horizon - cast_time - buff_active_time)

        # Total damage = (boosted while buff up) + (baseline after buff expires).
        # Cast time itself contributes 0 damage (player is casting, not attacking).
        total_damage = boosted_ba_dps * buff_active_time + baseline_ba_dps * post_buff_time
        return total_damage / horizon

    def _calculate_summon_dps_value(
        self,
        summon_name: str,
        summon_skill: SkillData,
        remaining_fight_time: float,
        current_active_buffs: Set[str],
        current_attack_speed_mult: float,
        num_enemies: int,
        is_boss: bool,
        mob_time_fraction: float,
        skill_values_getter: Optional[Callable[[float, Set[str]], Dict[str, 'SkillActionValue']]] = None,
        hex_multiplier: float = 1.0,
    ) -> float:
        """
        Score for casting the summon now, averaged as DPS over the lookahead horizon.

        Uses the same horizon as `_calculate_buff_dps_value` so plans are comparable.

        Plan timeline:
        - cast_time seconds with NO player damage (player is casting)
        - summon_window seconds with companion damage + player BA in parallel
        - rest of horizon at baseline BA DPS (companion has expired)
        """
        if summon_skill.duration <= 0 or summon_skill.attack_interval <= 0:
            return 0.0

        horizon = min(LOOKAHEAD_HORIZON_S, remaining_fight_time)
        if horizon <= 0:
            return 0.0

        cast_time = self.get_cast_time(
            summon_skill.cast_time, summon_skill.scales_with_attack_speed, current_attack_speed_mult,
        )
        if cast_time >= horizon:
            return 0.0

        # Summon active for min(duration, post-cast portion of horizon).
        summon_window = min(summon_skill.duration, horizon - cast_time)
        post_summon_time = max(0.0, horizon - cast_time - summon_window)

        # Build a stat snapshot of the player as they are right now. The
        # companion will use this snapshot for its 30s of attacks regardless
        # of how the player's buff state evolves afterward.
        snapshot = self._build_companion_snapshot(
            active_buffs=current_active_buffs, hex_multiplier=hex_multiplier,
        )

        attacks_per_sec = 1.0 / summon_skill.attack_interval

        # Per-hit damage in each phase, computed against the snapshot
        damage_pct = self.get_skill_damage_pct(summon_name)
        dmg_mob = self.calculate_hit_damage(
            damage_pct,
            summon_skill.damage_type,
            summon_name,
            is_boss_phase=False,
            attack_speed_mult=current_attack_speed_mult,
            active_buffs=current_active_buffs,
            num_enemies=num_enemies,
            stat_override=snapshot,
        )
        dmg_boss = self.calculate_hit_damage(
            damage_pct,
            summon_skill.damage_type,
            summon_name,
            is_boss_phase=True,
            attack_speed_mult=current_attack_speed_mult,
            active_buffs=current_active_buffs,
            num_enemies=1,
            stat_override=snapshot,
        )
        hits = self.get_skill_hits(summon_name)
        targets_mob = min(self.get_skill_targets(summon_name), num_enemies)

        # Companion damage during its active window, phase-split.
        if is_boss:
            companion_damage = dmg_boss * hits * 1 * attacks_per_sec * summon_window
        else:
            mob_damage = dmg_mob * hits * targets_mob * attacks_per_sec * summon_window * mob_time_fraction
            boss_damage = dmg_boss * hits * 1 * attacks_per_sec * summon_window * (1 - mob_time_fraction)
            companion_damage = mob_damage + boss_damage

        # The simulator's main loop applies the snapshot's hex multiplier to
        # companion damage at execution time. Mirror that here so the
        # scoring function predicts what the run will actually produce.
        companion_damage *= hex_multiplier

        # Player's BA DPS at the current (pre-summon) state — used for both
        # the in-summon parallel attacks AND the post-summon tail of the horizon.
        ba_dps = 0.0
        if skill_values_getter is not None:
            sv = skill_values_getter(current_attack_speed_mult, current_active_buffs)
            ba_name = self.char.get_active_basic_attack()
            if ba_name and ba_name in sv:
                action = sv[ba_name]
                ba_dps = action.dps_value_boss if is_boss else action.dps_value_mob

        # BA damage during the summon window + during the post-summon tail.
        # Cast time itself contributes 0 damage (player is casting).
        ba_damage = ba_dps * (summon_window + post_summon_time)

        total_damage = companion_damage + ba_damage
        return total_damage / horizon

    def _score_buff_then_summon_plan(
        self,
        summon_name: str,
        summon_skill: SkillData,
        buff_name: str,
        buff_skill: SkillData,
        remaining_fight_time: float,
        current_active_buffs: Set[str],
        current_attack_speed_mult: float,
        num_enemies: int,
        is_boss: bool,
        mob_time_fraction: float,
        skill_values_getter: Callable[[float, Set[str]], Dict[str, 'SkillActionValue']],
        current_t: float = 0.0,
    ) -> float:
        """
        Score the 2-action plan "cast `buff_name` first, then cast `summon_name`"
        as DPS averaged over the lookahead horizon. Same horizon/units as
        `_calculate_buff_dps_value` / `_calculate_summon_dps_value` so the
        scheduler picks the best 1- or 2-action plan at each tick.

        Plan timeline:
        - buff_cast_time : 0 damage (player casting buff)
        - summon_cast_time : 0 damage (player casting summon)
        - summon_window : companion damage (with buff baked into snapshot) + boosted BA in parallel
        - tail : baseline boosted-BA if buff still alive, else baseline pre-buff BA
        """
        horizon = min(LOOKAHEAD_HORIZON_S, remaining_fight_time)
        if horizon <= 0:
            return -1.0

        buff_cast_time = self.get_cast_time(buff_skill.cast_time, False, current_attack_speed_mult)
        if buff_cast_time >= horizon:
            return -1.0

        # State AFTER casting the buff: it's active. Re-evaluate attack speed
        # and the BA reference DPS using the new buff set.
        future_buffs = current_active_buffs | {buff_name}
        future_as = self.calculate_attack_speed_mult(future_buffs)

        # Summon cast happens at t + buff_cast_time, with the buff active.
        summon_cast_time = self.get_cast_time(
            summon_skill.cast_time, summon_skill.scales_with_attack_speed, future_as,
        )
        if buff_cast_time + summon_cast_time >= horizon:
            return -1.0

        # Window where companion is up, capped by the horizon's tail.
        summon_window = min(summon_skill.duration, horizon - buff_cast_time - summon_cast_time)
        if summon_window <= 0:
            return -1.0

        # Build the companion snapshot using the post-buff player state.
        # Hex is read at the moment the summon would actually land.
        landing_t = current_t + buff_cast_time + summon_cast_time
        hex_at_landing = self._hex_multiplier_at(landing_t)
        snapshot = self._build_companion_snapshot(
            active_buffs=future_buffs, hex_multiplier=hex_at_landing,
        )

        damage_pct = self.get_skill_damage_pct(summon_name)
        dmg_mob = self.calculate_hit_damage(
            damage_pct, summon_skill.damage_type, summon_name,
            is_boss_phase=False, attack_speed_mult=future_as,
            active_buffs=future_buffs, num_enemies=num_enemies,
            stat_override=snapshot,
        )
        dmg_boss = self.calculate_hit_damage(
            damage_pct, summon_skill.damage_type, summon_name,
            is_boss_phase=True, attack_speed_mult=future_as,
            active_buffs=future_buffs, num_enemies=1,
            stat_override=snapshot,
        )
        hits = self.get_skill_hits(summon_name)
        targets_mob = min(self.get_skill_targets(summon_name), num_enemies)
        attacks_per_sec = 1.0 / summon_skill.attack_interval

        if is_boss:
            companion_damage = dmg_boss * hits * 1 * attacks_per_sec * summon_window
        else:
            mob_damage = dmg_mob * hits * targets_mob * attacks_per_sec * summon_window * mob_time_fraction
            boss_damage = dmg_boss * hits * 1 * attacks_per_sec * summon_window * (1 - mob_time_fraction)
            companion_damage = mob_damage + boss_damage
        companion_damage *= hex_at_landing

        # Player BA contribution. The buff is active for min(buff_duration,
        # post-cast horizon); within that we use boosted_ba_dps, after we use
        # baseline_ba_dps. The buff lasts buff_duration starting at t+buff_cast_time.
        ba_name = self.char.get_active_basic_attack()
        boosted_ba_dps = 0.0
        baseline_ba_dps = 0.0
        if ba_name:
            cur_sv = skill_values_getter(current_attack_speed_mult, current_active_buffs)
            new_sv = skill_values_getter(future_as, future_buffs)
            if ba_name in new_sv:
                boosted_ba_dps = new_sv[ba_name].dps_value_boss if is_boss else new_sv[ba_name].dps_value_mob
            if ba_name in cur_sv:
                baseline_ba_dps = cur_sv[ba_name].dps_value_boss if is_boss else cur_sv[ba_name].dps_value_mob

        # BA contributes during the post-buff-cast tail of the horizon.
        effective_buff_dur = self.get_effective_buff_duration(buff_name)
        ba_total_window = horizon - buff_cast_time  # tail after buff is cast
        boosted_window = min(effective_buff_dur, ba_total_window)
        unboosted_window = max(0.0, ba_total_window - boosted_window)
        ba_damage = boosted_ba_dps * boosted_window + baseline_ba_dps * unboosted_window

        total_damage = companion_damage + ba_damage
        return total_damage / horizon

    def _simulate_fight(
        self,
        fight_duration: float,
        num_enemies: int,
        mob_time_fraction: float,
        attack_speed_mult: float,
        log_actions: bool = False,
    ) -> Tuple[float, float, float, float, float, List[FightLogEntry]]:
        """Simulate fight by picking best action at each decision point.

        At each action window, picks the skill with highest DPS value for
        the current phase (mob or boss). Dynamically tracks buff activation
        and expiration, recalculating attack speed when buffs change.

        Args:
            fight_duration: Total fight duration in seconds
            num_enemies: Number of enemies during mob phase
            mob_time_fraction: Fraction of fight spent on mobs (0.0-1.0)
                              Mob phase comes first, then boss phase.
            attack_speed_mult: Base attack speed multiplier (without buffs)
            log_actions: If True, build a detailed log of each action taken

        Returns:
            Tuple of (total_damage, basic_damage, active_damage, mob_damage, boss_damage, fight_log)
        """
        mob_duration = fight_duration * mob_time_fraction
        fight_log: List[FightLogEntry] = [] if log_actions else None

        # Get available BUFF skills
        available_buffs = self._get_available_buffs()

        # Track buff state: remaining duration and cooldowns
        buff_timers: Dict[str, float] = {}      # buff_name -> remaining_duration
        buff_cooldowns: Dict[str, float] = {}   # buff_name -> cooldown_remaining
        for buff_name in available_buffs:
            buff_cooldowns[buff_name] = 0.0  # All buffs start off cooldown

        # Track companion-summon state. summon_cooldowns gates re-casting (gated
        # additionally by the 5-second start-of-fight lockout inside
        # _get_available_summon_actions). active_summons[name] = seconds the
        # summon has left to attack. When a summon expires its entry is
        # removed and self._companion_snapshot is cleared.
        companion_keys = getattr(self, '_companion_summon_keys', None) or set()
        summon_cooldowns: Dict[str, float] = {name: 0.0 for name in companion_keys}
        active_summons: Dict[str, float] = {}
        self._companion_snapshot = None  # Cleared at sim start in case of reuse
        # Bishop-style secondary skill cooldowns. Reset to 0 (fires
        # immediately) each time a companion is summoned; reset to the
        # skill's cooldown_s when fired. Tracked across resummons.
        secondary_cooldowns: Dict[str, float] = {
            sk.name: 0.0 for sk in self._companion_secondary_skills
        }
        # Bishop proc skill ICD timer (seconds remaining until next allowed proc).
        proc_icd_remaining: float = 0.0

        # Current active buffs (empty set = no buffs)
        current_active_buffs: Set[str] = set()
        current_attack_speed_mult = self.calculate_attack_speed_mult(current_active_buffs)

        # Cache for precalculated skill values, keyed by (attack_speed_mult, frozenset(active_buffs))
        # This avoids redundant recalculation when evaluating buff options
        precalc_cache: Dict[Tuple[float, frozenset], Dict[str, SkillActionValue]] = {}

        def get_cached_skill_values(as_mult: float, buffs: Set[str]) -> Dict[str, SkillActionValue]:
            """Get skill values from cache or calculate if not present."""
            cache_key = (round(as_mult, 4), frozenset(buffs))
            if cache_key not in precalc_cache:
                precalc_cache[cache_key] = self._precalculate_skill_values(num_enemies, as_mult, buffs)
            return precalc_cache[cache_key]

        # Precalculate skill values with current attack speed and buffs
        skill_values = get_cached_skill_values(current_attack_speed_mult, current_active_buffs)

        if not skill_values:
            return 0.0, 0.0, 0.0, 0.0, 0.0, fight_log

        t = 0.0
        total_damage = 0.0
        basic_damage = 0.0
        active_damage = 0.0
        mob_damage = 0.0
        boss_damage = 0.0
        cooldowns = {name: 0.0 for name in skill_values}

        while t < fight_duration:
            is_boss = t >= mob_duration
            phase = "boss" if is_boss else "mob"
            remaining_fight_time = fight_duration - t

            # Check for expired buffs and update state
            buffs_changed = False
            for buff_name in list(buff_timers.keys()):
                if buff_timers[buff_name] <= 0:
                    del buff_timers[buff_name]
                    current_active_buffs.discard(buff_name)
                    buffs_changed = True

            # Recalculate if buffs changed. Preserve the companion AS bonus
            # (Bishop skill 8) if a companion is currently summoned —
            # otherwise a player buff expiring mid-summon would falsely drop
            # AS back to the no-companion baseline.
            if buffs_changed:
                current_attack_speed_mult = self.calculate_attack_speed_mult(
                    current_active_buffs,
                    companion_summon_active=bool(active_summons),
                )
                skill_values = get_cached_skill_values(current_attack_speed_mult, current_active_buffs)

            # Find best available damage action. Score each candidate by its
            # horizon-averaged DPS so the comparison is on the same scale as
            # the buff/summon scorers below (total damage over the next 90s
            # divided by 90, with greedy BA filling any gaps).
            best_action = None
            best_dps_value = -1.0      # Raw per-cast DPS rate, kept for logging
            best_horizon_score = -1.0  # Horizon-averaged DPS (used for plan choice)
            available_options = []

            _scoring_horizon = min(LOOKAHEAD_HORIZON_S, remaining_fight_time)
            # Baseline BA DPS used as the "filler rate" between casts of a
            # cooldown-bearing skill — same value the buff/summon scorers use.
            _ba_name = self.char.get_active_basic_attack()
            _baseline_ba_dps = 0.0
            if _ba_name and _ba_name in skill_values:
                _baseline_ba_dps = (
                    skill_values[_ba_name].dps_value_boss if is_boss
                    else skill_values[_ba_name].dps_value_mob
                )

            for name, sv in skill_values.items():
                if cooldowns[name] > 0:
                    continue  # On cooldown

                dps_value = sv.dps_value_boss if is_boss else sv.dps_value_mob
                damage_per_use = sv.damage_per_use_boss if is_boss else sv.damage_per_use_mob
                available_options.append((name, dps_value))

                # Horizon-averaged DPS: amortize future re-casts inside the
                # horizon by floor((horizon - cast_time) / cooldown). Filler
                # at baseline_ba_dps for time between casts.
                # NOTE: use a non-shadowing local name — `total_damage` is the
                # function-level accumulator and must NOT be reassigned here.
                if _scoring_horizon <= 0 or sv.cast_time <= 0:
                    horizon_score = dps_value
                elif sv.cooldown <= 0:
                    # No cooldown = basic-attack-class skill. Its per-cast DPS
                    # IS the horizon-averaged DPS (sustained spam).
                    horizon_score = dps_value
                else:
                    _tail = max(0.0, _scoring_horizon - sv.cast_time)
                    _extra_casts = int(_tail / sv.cooldown) if sv.cooldown > 0 else 0
                    _total_casts = 1 + _extra_casts
                    _skill_time = _total_casts * sv.cast_time
                    _filler_time = max(0.0, _scoring_horizon - _skill_time)
                    _horizon_dmg = _total_casts * damage_per_use + _baseline_ba_dps * _filler_time
                    horizon_score = _horizon_dmg / _scoring_horizon

                if horizon_score > best_horizon_score:
                    best_horizon_score = horizon_score
                    best_dps_value = dps_value
                    best_action = sv

            # Check if casting a buff is better than the best damage action
            best_buff_name = None
            best_buff_value = -1.0
            for buff_name, buff_skill in available_buffs.items():
                # Skip if buff is on cooldown or already active
                if buff_cooldowns.get(buff_name, 0) > 0:
                    continue
                if buff_name in current_active_buffs:
                    continue

                buff_value = self._calculate_buff_dps_value(
                    buff_name, buff_skill, remaining_fight_time,
                    current_active_buffs, current_attack_speed_mult,
                    num_enemies, is_boss,
                    skill_values_getter=get_cached_skill_values
                )
                if buff_value > best_buff_value:
                    best_buff_value = buff_value
                    best_buff_name = buff_name

            # Check if casting the companion summon is better than buff or
            # damage action. Gated by the 5-second start-of-fight lockout and
            # by the summon's own cooldown — both checked inside
            # _get_available_summon_actions.
            best_summon_name = None
            best_summon_value = -1.0
            for summon_name, summon_skill in self._get_available_summon_actions(t, summon_cooldowns).items():
                if summon_name in active_summons:
                    continue  # Already summoned; can't re-cast while active
                summon_value = self._calculate_summon_dps_value(
                    summon_name, summon_skill, remaining_fight_time,
                    current_active_buffs, current_attack_speed_mult,
                    num_enemies, is_boss, mob_time_fraction,
                    skill_values_getter=get_cached_skill_values,
                    hex_multiplier=self._hex_multiplier_at(t),
                )
                if summon_value > best_summon_value:
                    best_summon_value = summon_value
                    best_summon_name = summon_name

            # Phase 3.E: "delay summon for hex stack" check. If a hex
            # threshold (t=20/40/60) lands soon enough that summoning AT the
            # threshold beats summoning now over the longer horizon, suppress
            # the summon plan this tick. The scheduler will fall through to
            # damage/buff plans and re-evaluate at the next tick — when the
            # threshold finally arrives, summon-now becomes the optimal plan
            # again (because current_t == threshold and cur_hex == future_hex).
            if best_summon_name is not None and best_summon_value > 0:
                summon_skill_for_delay = self._summon_skills[best_summon_name]
                delay_candidates = self._enumerate_hex_delay_candidates(
                    t, fight_duration, summon_skill_for_delay.duration,
                )
                for delay_dur in delay_candidates:
                    if self._delay_dominates_summon_now(
                        best_summon_name, summon_skill_for_delay,
                        delay_dur, t, fight_duration,
                        best_dps_value if best_dps_value > 0 else 0.0,
                        current_active_buffs, current_attack_speed_mult,
                        num_enemies, is_boss, mob_time_fraction,
                    ):
                        best_summon_value = -1.0
                        best_summon_name = None
                        break

            # 2-step lookahead: score the "cast buff B, then cast summon"
            # plan for every castable buff. If any beats the 1-step plans,
            # the scheduler casts the BUFF now (not the summon) so the
            # summon's snapshot will include this buff when cast next.
            best_buff_then_summon_score = -1.0
            best_buff_for_summon = None
            if best_summon_name is not None:
                summon_skill_for_la = self._summon_skills[best_summon_name]
                for buff_name_la, buff_skill_la in available_buffs.items():
                    if buff_cooldowns.get(buff_name_la, 0) > 0:
                        continue
                    if buff_name_la in current_active_buffs:
                        continue
                    plan_score = self._score_buff_then_summon_plan(
                        best_summon_name, summon_skill_for_la,
                        buff_name_la, buff_skill_la,
                        remaining_fight_time,
                        current_active_buffs, current_attack_speed_mult,
                        num_enemies, is_boss, mob_time_fraction,
                        skill_values_getter=get_cached_skill_values,
                        current_t=t,
                    )
                    if plan_score > best_buff_then_summon_score:
                        best_buff_then_summon_score = plan_score
                        best_buff_for_summon = buff_name_la

            # Pick the highest-scoring plan and take its FIRST action.
            # All scorers return "damage over the 90s lookahead horizon / 90s"
            # so the values are directly comparable. "buff_then_summon" first
            # action is the BUFF (not the summon).
            plan_scores = {
                'damage':           best_horizon_score,
                'buff':             best_buff_value,
                'summon':           best_summon_value,
                'buff_then_summon': best_buff_then_summon_score,
            }
            chosen_plan = max(plan_scores, key=lambda k: plan_scores[k])

            cast_summon = chosen_plan == 'summon'
            cast_buff = chosen_plan in ('buff', 'buff_then_summon')
            # If buff_then_summon won, redirect the buff cast to the one we
            # specifically chose for the lookahead.
            if chosen_plan == 'buff_then_summon':
                best_buff_name = best_buff_for_summon

            if cast_summon and best_summon_name is not None:
                # Cast the companion summon. Snapshot the player's stats at
                # this instant; the companion uses that frozen snapshot for
                # the entire 30s window even as our own buffs decay.
                summon_skill = self._summon_skills[best_summon_name]
                cast_time = self.get_cast_time(
                    summon_skill.cast_time, summon_skill.scales_with_attack_speed,
                    current_attack_speed_mult,
                )
                if cast_time > remaining_fight_time:
                    time_used = remaining_fight_time
                else:
                    time_used = cast_time
                    # Snapshot includes the live hex multiplier at cast time —
                    # the companion gets this stack count for its full 30s window
                    # even as the player's own hex stacks continue to evolve.
                    # Phase 4 enrichment (MB / Concentration) is bundled in
                    # via `_build_companion_snapshot`.
                    self._companion_snapshot = self._build_companion_snapshot(
                        active_buffs=current_active_buffs,
                        hex_multiplier=self._hex_multiplier_at(t),
                    )
                    active_summons[best_summon_name] = summon_skill.duration
                    summon_cooldowns[best_summon_name] = summon_skill.cooldown
                    # Reset Bishop-style secondary skill / proc cooldowns so
                    # each fresh summon starts with the secondary ready to
                    # cast and the proc ready to trigger.
                    for sk in self._companion_secondary_skills:
                        secondary_cooldowns[sk.name] = 0.0
                    proc_icd_remaining = 0.0
                    # Companion-provided attack_speed (Bishop skill 8) actually
                    # accelerates the player's attack cadence — recompute the
                    # AS multiplier and refresh the skill_values cache to pick
                    # up the boosted attacks-per-second. Reverts at despawn.
                    if self._companion_player_bonuses.get('attack_speed', 0.0) > 0:
                        current_attack_speed_mult = self.calculate_attack_speed_mult(
                            current_active_buffs, companion_summon_active=True,
                        )
                        skill_values = get_cached_skill_values(
                            current_attack_speed_mult, current_active_buffs,
                        )

                if log_actions:
                    fight_log.append(FightLogEntry(
                        time=t,
                        skill_name=best_summon_name,
                        phase=phase,
                        damage=0,  # Summon damage is accumulated below per-step
                        cast_time=time_used,
                        reason=f"Summon value: {best_summon_value:,.0f}/s (vs buff {best_buff_value:,.0f}/s, BA {best_dps_value:,.0f}/s)",
                    ))

            elif cast_buff and best_buff_name is not None:
                # Cast the buff
                buff_skill = available_buffs[best_buff_name]
                cast_time = self.get_cast_time(buff_skill.cast_time, False, current_attack_speed_mult)

                # Handle partial execution at fight end
                if cast_time > remaining_fight_time:
                    time_used = remaining_fight_time
                else:
                    time_used = cast_time
                    # Activate buff
                    buff_timers[best_buff_name] = self.get_effective_buff_duration(best_buff_name)
                    current_active_buffs.add(best_buff_name)

                    # Get effective cooldown (check for mastery reductions)
                    mastery_cd_reduction = self.get_mastery_bonus(best_buff_name, "skill_cooldown_reduction") * 100
                    buff_cooldowns[best_buff_name] = self.char.get_effective_skill_cooldown(
                        buff_skill.cooldown, mastery_cd_reduction
                    )

                    # Recalculate attack speed and damage with new buff.
                    # Preserve the companion AS bonus if a companion is up.
                    current_attack_speed_mult = self.calculate_attack_speed_mult(
                        current_active_buffs,
                        companion_summon_active=bool(active_summons),
                    )
                    skill_values = get_cached_skill_values(current_attack_speed_mult, current_active_buffs)

                # Log the buff cast
                if log_actions:
                    fight_log.append(FightLogEntry(
                        time=t,
                        skill_name=best_buff_name,
                        phase=phase,
                        damage=0,  # Buffs don't deal damage
                        cast_time=time_used,
                        reason=f"Buff value: {best_buff_value:,.0f}/s (vs BA: {best_dps_value:,.0f}/s)",
                    ))

            elif best_action is not None:
                # Execute damage action
                damage = best_action.damage_per_use_boss if is_boss else best_action.damage_per_use_mob

                # Handle partial execution at fight end
                if best_action.cast_time > remaining_fight_time:
                    fraction = remaining_fight_time / best_action.cast_time
                    damage *= fraction
                    time_used = remaining_fight_time
                else:
                    time_used = best_action.cast_time

                # Apply the live hex-stack multiplier at this point in the fight.
                # The realistic-DPS path used to post-multiply by a single
                # time-averaged hex multiplier; we step it here instead.
                damage *= self._hex_multiplier_at(t)

                # Horn Flute: companion-gated FD applies to player damage only
                # while a companion summon is currently up. The companion
                # itself gets this FD via its frozen snapshot at cast time —
                # we deliberately do NOT re-apply it to companion damage in
                # the per-tick accumulation below.
                if active_summons and self.char.companion_active_fd_decimal > 0:
                    damage *= (1.0 + self.char.companion_active_fd_decimal)

                # Bishop-style player buffs (skill 2/3/5/6/8): applies to
                # player damage only while companion is summoned. Companion
                # damage does NOT pick this up — same player/companion
                # asymmetry as Horn Flute, but composed across multiple
                # stats. See `_compose_companion_player_buff_mult` for the
                # per-stat rules.
                if active_summons and self._companion_player_bonuses:
                    damage *= self._compose_companion_player_buff_mult()

                # Log the action if requested
                if log_actions:
                    if len(available_options) > 1:
                        sorted_options = sorted(available_options, key=lambda x: -x[1])
                        reason = f"DPS: {best_dps_value:,.0f}/s"
                        if len(sorted_options) > 1:
                            runner_up = sorted_options[1]
                            reason += f" (vs {runner_up[0]}: {runner_up[1]:,.0f}/s)"
                    else:
                        reason = "only option available"

                    # Add buff status to reason
                    if current_active_buffs:
                        reason += f" [Buffs: {', '.join(current_active_buffs)}]"

                    fight_log.append(FightLogEntry(
                        time=t,
                        skill_name=best_action.skill_name,
                        phase=phase,
                        damage=damage,
                        cast_time=time_used,
                        reason=reason,
                    ))

                total_damage += damage

                # Track by type
                if best_action.cooldown == 0:
                    basic_damage += damage
                else:
                    active_damage += damage

                # Track by phase
                if is_boss:
                    boss_damage += damage
                else:
                    mob_damage += damage

                # Set cooldown for this skill
                if best_action.cooldown > 0:
                    cooldowns[best_action.skill_name] = best_action.cooldown

            else:
                # No action available - advance time by minimum remaining cooldown
                all_cooldowns = (
                    list(cooldowns.values())
                    + list(buff_cooldowns.values())
                    + list(summon_cooldowns.values())
                )
                positive_cds = [cd for cd in all_cooldowns if cd > 0]
                if not positive_cds:
                    break  # Safety: avoid infinite loop
                min_cd = min(positive_cds)
                time_used = min_cd

            # Accumulate companion damage for active summons over `time_used`.
            # Each active summon does (time_used / interval) attacks; each attack
            # deals damage_per_hit × hits × targets, where damage_per_hit comes
            # from the frozen player snapshot taken at cast time.
            if active_summons and self._companion_snapshot is not None:
                for summon_name, _remaining in active_summons.items():
                    summon_skill = self._summon_skills.get(summon_name)
                    if summon_skill is None or summon_skill.attack_interval <= 0:
                        continue
                    # Active time within this step is min(time_used, remaining)
                    active_dt = min(time_used, _remaining)
                    if active_dt <= 0:
                        continue
                    attacks = active_dt / summon_skill.attack_interval
                    damage_pct = self.get_skill_damage_pct(summon_name)
                    hits = self.get_skill_hits(summon_name)
                    targets = (
                        1 if is_boss
                        else min(self.get_skill_targets(summon_name), num_enemies)
                    )
                    per_hit = self.calculate_hit_damage(
                        damage_pct,
                        summon_skill.damage_type,
                        summon_name,
                        is_boss_phase=is_boss,
                        attack_speed_mult=current_attack_speed_mult,
                        active_buffs=current_active_buffs,
                        num_enemies=num_enemies,
                        stat_override=self._companion_snapshot,
                    )
                    companion_dmg = per_hit * hits * targets * attacks
                    # Apply the hex multiplier the snapshot captured at the
                    # moment summon was cast — the companion stays at that
                    # multiplier for its entire 30s window even as the
                    # player's own hex stacks evolve afterwards.
                    companion_dmg *= self._companion_snapshot.hex_multiplier
                    total_damage += companion_dmg
                    if is_boss:
                        boss_damage += companion_dmg
                    else:
                        mob_damage += companion_dmg

                    # Bishop secondary skills (e.g. skill 4: 650% × 6 × 10 / 11s CD).
                    # Each tracks its own cooldown; fires at most once per tick.
                    # Uses the same snapshot as the primary attack — companion
                    # self-buff FD + Horn Flute are baked in exactly once.
                    for sk in self._companion_secondary_skills:
                        cd_remaining = secondary_cooldowns.get(sk.name, 0.0)
                        if cd_remaining > 0:
                            secondary_cooldowns[sk.name] = max(0.0, cd_remaining - active_dt)
                            continue
                        sec_targets = 1 if is_boss else min(sk.targets, num_enemies)
                        sec_per_hit = self.calculate_hit_damage(
                            sk.damage_pct,
                            summon_skill.damage_type,
                            summon_name,
                            is_boss_phase=is_boss,
                            attack_speed_mult=current_attack_speed_mult,
                            active_buffs=current_active_buffs,
                            num_enemies=num_enemies,
                            stat_override=self._companion_snapshot,
                        )
                        sec_dmg = sec_per_hit * sk.hits * sec_targets
                        sec_dmg *= self._companion_snapshot.hex_multiplier
                        total_damage += sec_dmg
                        if is_boss:
                            boss_damage += sec_dmg
                        else:
                            mob_damage += sec_dmg
                        secondary_cooldowns[sk.name] = sk.cooldown_s

                    # Bishop proc skill (e.g. skill 7: 20% per attack, 3s ICD,
                    # 2600% × 7 targets). Expected-value model: per tick,
                    # contribute `expected_procs × per-proc damage`, capped by
                    # ICD so we never exceed `active_dt / icd_s` procs.
                    proc = self._companion_proc_skill
                    if proc is not None:
                        proc_icd_remaining = max(0.0, proc_icd_remaining - active_dt)
                        # Procs we'd see in this tick if uncapped:
                        proc_attempts = attacks * proc.proc_chance
                        # ICD cap: at most `active_dt / icd_s` procs may fire
                        # (e.g., 1s tick with 3s ICD → 0.33 cap).
                        proc_cap = active_dt / proc.icd_s if proc.icd_s > 0 else proc_attempts
                        expected_procs = min(proc_attempts, proc_cap)
                        if expected_procs > 0:
                            proc_targets = 1 if is_boss else min(proc.targets, num_enemies)
                            proc_per_hit = self.calculate_hit_damage(
                                proc.damage_pct,
                                summon_skill.damage_type,
                                summon_name,
                                is_boss_phase=is_boss,
                                attack_speed_mult=current_attack_speed_mult,
                                active_buffs=current_active_buffs,
                                num_enemies=num_enemies,
                                stat_override=self._companion_snapshot,
                            )
                            proc_dmg = proc_per_hit * proc.hits * proc_targets * expected_procs
                            proc_dmg *= self._companion_snapshot.hex_multiplier
                            total_damage += proc_dmg
                            if is_boss:
                                boss_damage += proc_dmg
                            else:
                                mob_damage += proc_dmg

            # Advance time and decrement all cooldowns / timers
            for name in cooldowns:
                cooldowns[name] = max(0, cooldowns[name] - time_used)
            for name in buff_cooldowns:
                buff_cooldowns[name] = max(0, buff_cooldowns[name] - time_used)
            for name in buff_timers:
                buff_timers[name] = max(0, buff_timers[name] - time_used)
            # Summon cooldowns decrement; active summons decrement and expire.
            had_active_summon = bool(active_summons)
            for name in list(summon_cooldowns.keys()):
                summon_cooldowns[name] = max(0, summon_cooldowns[name] - time_used)
            for name in list(active_summons.keys()):
                active_summons[name] -= time_used
                if active_summons[name] <= 0:
                    del active_summons[name]
            # If no companion is active, clear the snapshot so the next summon
            # cast captures fresh stats. Also reset attack speed to baseline
            # (Bishop skill 8's +20% AS only applied while the companion was up).
            if not active_summons:
                self._companion_snapshot = None
                if had_active_summon and self._companion_player_bonuses.get('attack_speed', 0.0) > 0:
                    current_attack_speed_mult = self.calculate_attack_speed_mult(
                        current_active_buffs, companion_summon_active=False,
                    )
                    skill_values = get_cached_skill_values(
                        current_attack_speed_mult, current_active_buffs,
                    )
            t += time_used

        return total_damage, basic_damage, active_damage, mob_damage, boss_damage, fight_log

    def _calc_summons_dps_phased(
        self,
        fight_duration: float,
        num_enemies: int,
        mob_time_fraction: float,
        attack_speed_mult: float,
    ) -> Tuple[float, float, float]:
        """Calculate summon DPS with proper phase weighting.

        Summons attack independently of player actions. Their damage is
        weighted by phase duration with appropriate multipliers.

        Args:
            fight_duration: Total fight duration in seconds
            num_enemies: Number of enemies during mob phase
            mob_time_fraction: Fraction of fight spent on mobs
            attack_speed_mult: Attack speed multiplier (1.0 = base, 2.5 = max)

        Returns:
            Tuple of (total_dps, mob_dps, boss_dps)
        """
        from libs.cooldown_calc import calculate_buff_uptime

        total_summon_dps = 0.0
        total_mob_dps = 0.0
        total_boss_dps = 0.0

        # Companion summons are scheduled as discrete actions by the burst-window
        # scheduler (Phase 2 of the snapshot work) — accumulating their damage
        # here would double-count. Skip them; the scheduler accumulates their
        # damage into player_active_dmg / phase-specific buckets directly.
        companion_keys = getattr(self, '_companion_summon_keys', None) or set()

        for skill_name, skill in self._summon_skills.items():
            if skill_name in companion_keys:
                continue
            if not self.char.is_skill_unlocked(skill_name):
                continue
            if skill.duration <= 0 or skill.attack_interval <= 0:
                continue

            # Calculate damage for each phase
            dmg_mob = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=False,
                num_enemies=num_enemies,
            )
            dmg_boss = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=True,
                num_enemies=1,
            )

            # Calculate uptime
            if skill.cooldown > 0:
                cd = skill.cooldown
                mastery_pct_reduction = self.get_mastery_bonus(skill_name, "skill_cooldown_reduction") * 100
                cd = self.char.get_effective_skill_cooldown(cd, mastery_pct_reduction)
                uptime = calculate_buff_uptime(
                    cooldown=cd,
                    buff_duration=skill.duration,
                    fight_duration=fight_duration,
                )
            else:
                uptime = 1.0

            # Attack interval - apply mastery reduction and attack speed scaling
            interval = skill.attack_interval
            # Apply mastery interval reduction (negative values reduce interval)
            flat_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval")
            if flat_reduction != 0:
                interval = max(1.0, interval + flat_reduction)
            pct_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval_pct")
            if pct_reduction != 0:
                interval = max(1.0, interval * (1 + pct_reduction / 100))
            # Some summons scale with attack speed (e.g., quiver_cartridge)
            if skill.scales_with_attack_speed:
                as_mult = min(attack_speed_mult, 2.0)
                if skill.max_as_interval_reduction > 0:
                    interval = interval - min(skill.max_as_interval_reduction,
                                              skill.max_as_interval_reduction * (as_mult - 1.0))
                else:
                    interval = interval / as_mult

            attacks_per_second = 1 / interval

            # Calculate hits and targets for each phase
            hits = self.get_skill_hits(skill_name)
            targets_mob = min(self.get_skill_targets(skill_name), num_enemies)
            targets_boss = 1

            # Weight by phase duration
            mob_dps = dmg_mob * hits * targets_mob * attacks_per_second * uptime * mob_time_fraction
            boss_dps = dmg_boss * hits * targets_boss * attacks_per_second * uptime * (1 - mob_time_fraction)

            total_summon_dps += mob_dps + boss_dps
            total_mob_dps += mob_dps
            total_boss_dps += boss_dps

        return total_summon_dps, total_mob_dps, total_boss_dps

    def _calc_procs_dps_phased(
        self,
        fight_duration: float,
        num_enemies: int,
        mob_time_fraction: float,
        attack_speed_mult: float,
    ) -> Tuple[float, float, float]:
        """Calculate proc DPS with proper phase weighting.

        Procs trigger on player attacks. Their damage is weighted by
        phase duration with appropriate multipliers.

        Args:
            fight_duration: Total fight duration in seconds
            num_enemies: Number of enemies during mob phase
            mob_time_fraction: Fraction of fight spent on mobs
            attack_speed_mult: Attack speed multiplier (1.0 = base, 2.5 = max)

        Returns:
            Tuple of (total_dps, mob_dps, boss_dps)
        """
        total_proc_dps = 0.0
        total_mob_dps = 0.0
        total_boss_dps = 0.0

        # Get basic attack for cast time and targets
        basic_skill_name = self.char.get_active_basic_attack()
        ba_skill = self._skills.get(basic_skill_name) if basic_skill_name else None
        ba_cast_time = ba_skill.cast_time if ba_skill else 1.0
        cast_time = self.get_cast_time(ba_cast_time, True, attack_speed_mult)
        attacks_per_second = 1 / cast_time
        basic_attack_targets = self.get_skill_targets(basic_skill_name) if basic_skill_name else 1

        for skill_name, skill in self._proc_skills.items():
            if not self.char.is_skill_unlocked(skill_name):
                continue

            # Calculate damage for each phase
            dmg_mob = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=False,
                num_enemies=num_enemies,
            )
            dmg_boss = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=True,
                num_enemies=1,
            )

            if skill.max_stacks > 0:
                # Stack-based proc (Meso Explosion, Blood Money)
                hits = self.get_skill_hits(skill_name)
                mastery_cd_pct = self.get_mastery_bonus(skill_name, "skill_cooldown_reduction") * 100
                effective_cd = self.char.get_effective_skill_cooldown(skill.cooldown, mastery_cd_pct)
                gen_chance = self.get_effective_proc_chance(skill_name)

                # Mastery can increase max stacks (e.g., Blood Money - Damage doubles stacks)
                effective_max_stacks = skill.max_stacks
                stack_mastery = self.get_mastery_bonus(skill_name, "skill_effect")
                if stack_mastery > 0:
                    effective_max_stacks = int(skill.max_stacks * (1 + stack_mastery / 100))

                ba_targets_mob = min(basic_attack_targets, num_enemies)
                ba_targets_boss = 1

                if skill.stack_source:
                    source_chance = self.get_effective_proc_chance(skill.stack_source)
                    stacks_per_atk_mob = ba_targets_mob * source_chance * gen_chance
                    stacks_per_atk_boss = ba_targets_boss * source_chance * gen_chance
                else:
                    stacks_per_atk_mob = ba_targets_mob * gen_chance
                    stacks_per_atk_boss = ba_targets_boss * gen_chance

                attacks_in_cd = attacks_per_second * effective_cd
                accumulated_mob = stacks_per_atk_mob * attacks_in_cd
                accumulated_boss = stacks_per_atk_boss * attacks_in_cd
                mob_stacks = min(effective_max_stacks, int(accumulated_mob))
                boss_stacks = min(effective_max_stacks, int(accumulated_boss))

                mob_targets = min(mob_stacks, num_enemies)
                boss_targets = min(boss_stacks, 1)

                mob_dps = dmg_mob * hits * mob_targets / effective_cd
                boss_dps = dmg_boss * hits * boss_targets / effective_cd

                if skill.single_target_stack_bonus > 0 and boss_targets == 1:
                    boss_dps *= (1 + skill.single_target_stack_bonus * boss_stacks)

                mob_dps *= mob_time_fraction
                boss_dps *= (1 - mob_time_fraction)

            elif skill.attack_interval > 0:
                # Marking-style procs (like Mark of Assassin)
                interval = skill.attack_interval
                flat_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval")
                if flat_reduction != 0:
                    interval = max(1.0, interval + flat_reduction)
                pct_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval_pct")
                if pct_reduction != 0:
                    interval = max(1.0, interval * (1 + pct_reduction / 100))

                marks_per_interval_mob = min(skill.base_targets, num_enemies)
                procs_per_second_mob = marks_per_interval_mob / interval
                procs_per_second_boss = 1 / interval

                mob_dps = dmg_mob * 1 * procs_per_second_mob * mob_time_fraction
                boss_dps = dmg_boss * 1 * procs_per_second_boss * (1 - mob_time_fraction)
            else:
                # Standard proc calculation
                targets_mob = min(self.get_skill_targets(skill_name), num_enemies)
                targets_boss = 1

                proc_chance = skill.proc_chance
                if skill.scales_with_attack_speed:
                    proc_chance = min(proc_chance * attack_speed_mult, proc_chance * 2)

                if skill.cooldown > 0:
                    mastery_pct_reduction = self.get_mastery_bonus(skill_name, "skill_cooldown_reduction") * 100
                    effective_cd = self.char.get_effective_skill_cooldown(skill.cooldown, mastery_pct_reduction)
                    procs_per_second = min(1 / cast_time * proc_chance, 1 / effective_cd)
                else:
                    procs_per_second = 1 / cast_time * proc_chance

                mob_dps = dmg_mob * targets_mob * procs_per_second * mob_time_fraction
                boss_dps = dmg_boss * targets_boss * procs_per_second * (1 - mob_time_fraction)

            total_proc_dps += mob_dps + boss_dps
            total_mob_dps += mob_dps
            total_boss_dps += boss_dps

        return total_proc_dps, total_mob_dps, total_boss_dps

    def calculate_total_dps(
        self,
        fight_duration: float = 60.0,
        num_enemies: int = 1,
        mob_time_fraction: float = 1.0,
    ) -> DPSResult:
        """Calculate total DPS with current character state.

        Uses unified cooldown_calc module for accurate trigger/uptime calculations
        that account for partial triggers at fight end.

        Args:
            fight_duration: Fight duration in seconds (default 60s rotation)
            num_enemies: Number of enemies during mob waves (1 for pure boss fights)
                         Multi-target skills hit min(skill_targets, num_enemies) enemies.
            mob_time_fraction: Fraction of fight time spent on mob waves (0.0-1.0)
                         Remaining time (1 - mob_time_fraction) is spent on boss (single target).
                         Default 1.0 = all mob waves (pure multi-target).
                         Example: 0.6 = 60% mobs, 40% boss (typical chapter stage).
        """
        from libs.cooldown_calc import calculate_triggers, calculate_buff_uptime

        # Collect all skill stat bonuses; attack speed already in char.attack_speed_pct
        skill_bonuses = self.get_all_skill_stat_bonuses()
        attack_speed_mult = self.calculate_attack_speed_mult()

        rotation_length = fight_duration

        basic_dps = 0
        active_dps = 0
        summon_dps = 0
        proc_dps = 0
        skills_used = []

        # Basic attack (current tier)
        basic_skill_name = self.char.get_active_basic_attack()
        ba_skill_data = self._skills.get(basic_skill_name) if basic_skill_name else None
        ba_cast_time = ba_skill_data.cast_time if ba_skill_data else 1.0
        cast_time = self.get_cast_time(ba_cast_time, True, attack_speed_mult)

        if basic_skill_name and self.char.is_skill_unlocked(basic_skill_name):
            basic_skill = self._skills[basic_skill_name]
            damage = self.calculate_hit_damage(
                self.get_skill_damage_pct(basic_skill_name),
                basic_skill.damage_type,
                basic_skill_name,
            )
            hits = self.get_skill_hits(basic_skill_name)
            effective_targets = self.get_effective_targets(basic_skill_name, num_enemies, mob_time_fraction)
            attacks_per_second = 1 / cast_time

            basic_dps = damage * hits * effective_targets * attacks_per_second
            skills_used.append(basic_skill_name)

        # Active skills - find all ACTIVE type skills dynamically
        active_skill_time_used = 0
        for skill_name, skill in self._active_skills.items():
            if not self.char.is_skill_unlocked(skill_name):
                continue
            hits = self.get_skill_hits(skill_name)
            effective_targets = self.get_effective_targets(skill_name, num_enemies, mob_time_fraction)

            # Calculate cast time
            if skill.attack_interval > 0:
                # Hurricane: fires arrows over time, attack speed affects firing rate
                # Base cast time = hits × interval (e.g., 20 × 0.248 = ~5 seconds)
                # At 98.2% AS: 5.0 / 1.982 = 2.5 seconds (verified from testing)
                base_cast_time = hits * skill.attack_interval
                if skill.scales_with_attack_speed:
                    skill_cast_time = base_cast_time / attack_speed_mult
                else:
                    skill_cast_time = base_cast_time
            else:
                # Cast time from datamine animation frames (default 1.0s)
                skill_cast_time = self.get_cast_time(skill.cast_time, skill.scales_with_attack_speed, attack_speed_mult)

            if skill.cooldown > 0:
                # Apply skill CD reduction from hat potential
                effective_cd = self.char.get_effective_skill_cooldown(skill.cooldown, 0)

                # Use unified trigger calculation (accounts for partial triggers)
                triggers = calculate_triggers(
                    cooldown=effective_cd,
                    duration=skill_cast_time,
                    fight_duration=rotation_length,
                )

                damage = self.calculate_hit_damage(
                    self.get_skill_damage_pct(skill_name),
                    skill.damage_type,
                    skill_name,
                )

                # Base damage per use
                damage_per_use = damage * hits * effective_targets

                # Finishing blow: extra damage line every N uses
                if skill.finishing_blow_interval > 0:
                    fb_damage = self.get_finishing_blow_avg_damage(skill_name)
                    if fb_damage > 0:
                        if skill.finishing_blow_boss_only:
                            # Boss-only FB: single target, weighted by boss time fraction
                            boss_fraction = 1 - mob_time_fraction
                            damage_per_use += fb_damage * 1 * boss_fraction
                        else:
                            damage_per_use += fb_damage * effective_targets

                # DoT component: extra damage ticks after cast
                if skill.dot_damage_pct > 0 and skill.dot_duration > 0:
                    dot_ticks = int(skill.dot_duration / skill.dot_interval)
                    dot_damage = self.calculate_hit_damage(
                        skill.dot_damage_pct, skill.damage_type, skill_name)
                    damage_per_use += dot_damage * dot_ticks * effective_targets

                # Handle infinite fight duration (steady state DPS)
                if math.isinf(rotation_length):
                    # Steady state: DPS = damage_per_use / cooldown
                    active_dps += damage_per_use / effective_cd
                    # Time ratio for basic attack: skill_cast_time / cooldown
                    active_skill_time_used += skill_cast_time / effective_cd
                else:
                    time_per_rotation = skill_cast_time * triggers
                    active_skill_time_used += time_per_rotation
                    active_dps += damage_per_use * triggers / rotation_length
                skills_used.append(skill_name)

        # Adjust basic DPS for time spent on actives
        if math.isinf(rotation_length):
            # At infinite duration, use fraction of time spent on actives
            basic_time_ratio = max(0, 1.0 - active_skill_time_used)
        else:
            basic_time_ratio = max(0, rotation_length - active_skill_time_used) / rotation_length
        basic_dps *= basic_time_ratio

        # Summons
        for skill_name, skill in self._summon_skills.items():
            if not self.char.is_skill_unlocked(skill_name):
                continue
            damage = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
            )

            if skill.duration > 0 and skill.attack_interval > 0:
                # Calculate uptime using unified module
                if skill.cooldown > 0:
                    # Cooldown reduction from mastery
                    cd = skill.cooldown
                    mastery_pct_reduction = self.get_mastery_bonus(skill_name, "skill_cooldown_reduction") * 100
                    # Apply skill CD reduction from hat potential
                    cd = self.char.get_effective_skill_cooldown(cd, mastery_pct_reduction)

                    # Use unified uptime calculation (accounts for partial triggers)
                    uptime = calculate_buff_uptime(
                        cooldown=cd,
                        buff_duration=skill.duration,
                        fight_duration=rotation_length,
                    )
                else:
                    uptime = 1.0

                # Attack interval (apply mastery reduction and AS scaling)
                interval = skill.attack_interval
                flat_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval")
                if flat_reduction != 0:
                    interval = max(1.0, interval + flat_reduction)
                pct_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval_pct")
                if pct_reduction != 0:
                    interval = max(1.0, interval * (1 + pct_reduction / 100))  # Flat second reduction
                if skill.scales_with_attack_speed:
                    as_mult = min(attack_speed_mult, 2.0)
                    if skill.max_as_interval_reduction > 0:
                        interval = interval - min(skill.max_as_interval_reduction,
                                                  skill.max_as_interval_reduction * (as_mult - 1.0))
                    else:
                        interval = interval / as_mult

                attacks_per_second = 1 / interval
                hits = self.get_skill_hits(skill_name)
                effective_targets = self.get_effective_targets(skill_name, num_enemies, mob_time_fraction)
                summon_dps += damage * hits * effective_targets * attacks_per_second * uptime
                skills_used.append(skill_name)

        # Procs
        basic_attack_targets = self.get_skill_targets(basic_skill_name) if basic_skill_name else 1
        attacks_per_second = 1 / cast_time

        for skill_name, skill in self._proc_skills.items():
            if not self.char.is_skill_unlocked(skill_name):
                continue
            damage = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
            )

            if skill.max_stacks > 0:
                # Stack-based proc (Meso Explosion, Blood Money)
                # Stacks accumulate as decimal, int() only at consumption
                hits = self.get_skill_hits(skill_name)
                mastery_cd_pct = self.get_mastery_bonus(skill_name, "skill_cooldown_reduction") * 100
                effective_cd = self.char.get_effective_skill_cooldown(skill.cooldown, mastery_cd_pct)
                gen_chance = self.get_effective_proc_chance(skill_name)

                # Mastery can increase max stacks (e.g., Blood Money - Damage doubles stacks)
                effective_max_stacks = skill.max_stacks
                stack_mastery = self.get_mastery_bonus(skill_name, "skill_effect")
                if stack_mastery > 0:
                    effective_max_stacks = int(skill.max_stacks * (1 + stack_mastery / 100))

                ba_targets_mob = min(basic_attack_targets, num_enemies)
                ba_targets_boss = 1

                if skill.stack_source:
                    source_chance = self.get_effective_proc_chance(skill.stack_source)
                    stacks_per_atk_mob = ba_targets_mob * source_chance * gen_chance
                    stacks_per_atk_boss = ba_targets_boss * source_chance * gen_chance
                else:
                    stacks_per_atk_mob = ba_targets_mob * gen_chance
                    stacks_per_atk_boss = ba_targets_boss * gen_chance

                attacks_in_cd = attacks_per_second * effective_cd
                accumulated_mob = stacks_per_atk_mob * attacks_in_cd
                accumulated_boss = stacks_per_atk_boss * attacks_in_cd
                mob_stacks = min(effective_max_stacks, int(accumulated_mob))
                boss_stacks = min(effective_max_stacks, int(accumulated_boss))

                mob_targets = min(mob_stacks, num_enemies)
                boss_targets = min(boss_stacks, 1)

                mob_dps = damage * hits * mob_targets / effective_cd
                boss_dps = damage * hits * boss_targets / effective_cd

                if skill.single_target_stack_bonus > 0 and boss_targets == 1:
                    boss_dps *= (1 + skill.single_target_stack_bonus * boss_stacks)

                proc_dps += mob_dps * mob_time_fraction + boss_dps * (1 - mob_time_fraction)

            elif skill.attack_interval > 0:
                # Marking-style procs (like Mark of Assassin)
                interval = skill.attack_interval
                flat_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval")
                if flat_reduction != 0:
                    interval = max(1.0, interval + flat_reduction)
                pct_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval_pct")
                if pct_reduction != 0:
                    interval = max(1.0, interval * (1 + pct_reduction / 100))

                marks_per_interval_mob = min(skill.base_targets, num_enemies)
                procs_per_second_mob = marks_per_interval_mob / interval
                procs_per_second_boss = 1 / interval

                mob_dps = damage * 1 * procs_per_second_mob * mob_time_fraction
                boss_dps = damage * 1 * procs_per_second_boss * (1 - mob_time_fraction)
                proc_dps += mob_dps + boss_dps
            else:
                # Standard proc calculation
                effective_targets = self.get_effective_targets(skill_name, num_enemies, mob_time_fraction)

                proc_chance = skill.proc_chance
                if skill.scales_with_attack_speed:
                    proc_chance = min(proc_chance * attack_speed_mult, proc_chance * 2)

                if skill.cooldown > 0:
                    mastery_pct_reduction = self.get_mastery_bonus(skill_name, "skill_cooldown_reduction") * 100
                    effective_cd = self.char.get_effective_skill_cooldown(skill.cooldown, mastery_pct_reduction)
                    procs_per_second = min(1 / cast_time * proc_chance, 1 / effective_cd)
                else:
                    procs_per_second = 1 / cast_time * proc_chance

                proc_dps += damage * effective_targets * procs_per_second

            skills_used.append(skill_name)

        total_dps = basic_dps + active_dps + summon_dps + proc_dps

        return DPSResult(
            total_dps=total_dps,
            basic_attack_dps=basic_dps,
            active_skill_dps=active_dps,
            summon_dps=summon_dps,
            proc_dps=proc_dps,
            rotation_length=rotation_length,
            skills_used=skills_used,
            total_skill_damage_pct=self.get_total_stat_bonus("skill_damage"),
            total_basic_attack_dmg_pct=self.get_total_stat_bonus("basic_attack_damage"),
            total_final_damage_pct=self.char.final_damage_pct,
        )

    def calculate_realistic_dps(
        self,
        fight_duration: float = 60.0,
        num_enemies: int = 12,
        mob_time_fraction: float = 0.6,
        boss_importance: float = 0.7,
        boss_damage_multiplier: float = 1.0,
        log_actions: bool = False,
    ) -> DPSResult:
        """Calculate DPS using realistic phase-aware simulation.

        This method properly handles:
        1. Boss vs Normal damage stats applied only during their respective phases
        2. Skill scheduling: picks best action at each decision point
        3. Hurricane saved for boss phase when multi-target BA is better during mobs
        4. Proper phase-weighted summon and proc damage
        5. Boss importance weighting for optimization recommendations

        Phase order: Mob phase first, then boss phase.
        Example: 60/40 = 60% mob (36s), then 40% boss (24s) for a 60s fight.

        The boss_importance parameter allows users to tune how much boss vs mob
        damage matters for their progression. Default 70% reflects that bosses
        typically have ~70% of total stage HP.

        The boss_damage_multiplier scales boss phase DPS in the weighted calculation.
        Set to ~5 (number of mobs) to make boss damage comparable to multi-target
        mob damage for optimization purposes.

        Args:
            fight_duration: Total fight duration in seconds
            num_enemies: Number of enemies during mob phase
            mob_time_fraction: Fraction of fight spent on mobs (0.0-1.0)
            boss_importance: How much to weight boss damage (0.0-1.0)
                            Higher = boss is the bottleneck
                            Lower = mobs are the bottleneck
            boss_damage_multiplier: Multiplier for boss phase DPS (default 1.0)
            log_actions: If True, include detailed fight log in result

        Returns:
            DPSResult with breakdown by source (and fight_log if log_actions=True)
        """
        # Collect all skill stat bonuses; attack speed already in char.attack_speed_pct
        skill_bonuses = self.get_all_skill_stat_bonuses()
        attack_speed_mult = self.calculate_attack_speed_mult()

        # Handle infinite duration (chapter hunt)
        if math.isinf(fight_duration):
            # Steady state: use original method (simulation doesn't work at infinity)
            return self.calculate_total_dps(fight_duration, num_enemies, mob_time_fraction)

        # Simulate player actions - returns (total, basic, active, mob, boss, log)
        total_dmg, basic_dmg, active_dmg, player_mob_dmg, player_boss_dmg, fight_log = self._simulate_fight(
            fight_duration, num_enemies, mob_time_fraction, attack_speed_mult, log_actions=log_actions
        )

        # Calculate summon and proc DPS (run in parallel with player)
        # Returns (total, mob, boss) for each
        summon_total, summon_mob, summon_boss = self._calc_summons_dps_phased(
            fight_duration, num_enemies, mob_time_fraction, attack_speed_mult
        )
        proc_total, proc_mob, proc_boss = self._calc_procs_dps_phased(
            fight_duration, num_enemies, mob_time_fraction, attack_speed_mult
        )

        # Hex Necklace applies to non-companion summons (Phoenix, Arrow Platter)
        # and procs (Final Attack, Mark of Assassin, etc.). The player's own
        # damage gets hex applied per damage event inside `_simulate_fight`,
        # and companion summons get hex via the snapshot — so those paths
        # are already covered. _calc_summons_dps_phased / _calc_procs_dps_phased
        # do NOT apply hex internally; we apply the time-averaged multiplier
        # here so the realistic path's summon/proc DPS isn't under-counted.
        hex_stars = getattr(self.char, 'hex_necklace_stars', 0) or 0
        if hex_stars > 0:
            from game.artifacts import calculate_hex_average_multiplier
            hex_avg = calculate_hex_average_multiplier(hex_stars, fight_duration)
            summon_total *= hex_avg
            summon_mob *= hex_avg
            summon_boss *= hex_avg
            proc_total *= hex_avg
            proc_mob *= hex_avg
            proc_boss *= hex_avg

        # Convert player damage to DPS
        player_mob_dps = player_mob_dmg / fight_duration
        player_boss_dps = player_boss_dmg / fight_duration

        # Total mob and boss DPS across all sources
        total_mob_dps = player_mob_dps + summon_mob + proc_mob
        total_boss_dps = player_boss_dps + summon_boss + proc_boss

        # Apply boss damage multiplier and sum both phases
        # The multiplier scales boss DPS to make it comparable to multi-target mob DPS
        # e.g., if mobs have 5 targets, set multiplier to 5 so boss damage is weighted fairly
        # Note: boss_importance is currently disabled for testing, so we just sum both phases
        scaled_boss_dps = total_boss_dps * boss_damage_multiplier
        weighted_total_dps = total_mob_dps + scaled_boss_dps

        # For breakdown display, use unweighted values
        basic_dps = basic_dmg / fight_duration
        active_dps = active_dmg / fight_duration

        # Get skills used from precalculation (no buffs, just for listing)
        skill_values = self._precalculate_skill_values(num_enemies, attack_speed_mult, None)
        skills_used = list(skill_values.keys())

        # Add summons and procs to skills list
        for skill_name in (*self._summon_skills, *self._proc_skills):
            if self.char.is_skill_unlocked(skill_name) and skill_name not in skills_used:
                skills_used.append(skill_name)

        return DPSResult(
            total_dps=weighted_total_dps,
            basic_attack_dps=basic_dps,
            active_skill_dps=active_dps,
            summon_dps=summon_total,
            proc_dps=proc_total,
            rotation_length=fight_duration,
            skills_used=skills_used,
            total_skill_damage_pct=self.get_total_stat_bonus("skill_damage"),
            total_basic_attack_dmg_pct=self.get_total_stat_bonus("basic_attack_damage"),
            total_final_damage_pct=self.char.final_damage_pct,
            mob_phase_dps=total_mob_dps,
            boss_phase_dps=total_boss_dps,
            fight_log=fight_log,
        )

    def get_skill_damage_breakdown(
        self,
        fight_duration: float = 60.0,
        num_enemies: int = 12,
        mob_time_fraction: float = 0.6,
    ) -> Dict[str, Dict]:
        """
        Calculate per-skill damage contribution breakdown.

        This provides detailed information about how much damage each skill
        contributes to total DPS, useful for visualizing skill importance
        across different levels and mastery configurations.

        The breakdown uses the fight simulation which tracks all player actions
        (basic attacks, active skills, summon casts) in a fight log. Summons
        like Phoenix and Arrow Platter appear in the log when cast, and their
        total damage includes all attacks over their duration.

        Procs (Final Attack, Flash Mirage) are calculated separately as they
        trigger independently of player actions.

        Args:
            fight_duration: Total fight duration in seconds
            num_enemies: Number of enemies during mob phase
            mob_time_fraction: Fraction of fight spent on mobs (0.0-1.0)

        Returns:
            Dict mapping skill_name -> {
                'display_name': str,
                'total_damage': float,
                'dps': float,
                'pct_of_total': float,
                'mob_damage': float,
                'boss_damage': float,
                'skill_type': str,  # 'basic', 'active', 'summon', 'proc'
            }
        """
        # Calculate attack speed multiplier (passive/mastery already in char.attack_speed_pct)
        attack_speed_mult = self.calculate_attack_speed_mult()

        breakdown = {}
        total_damage = 0.0

        # Run fight simulation to get player action damage with detailed log
        # This includes basic attacks, active skills, AND summon casts (Phoenix, Arrow Platter)
        # The summon damage in the log is the total damage over the summon's duration
        _, basic_dmg, active_dmg, mob_dmg, boss_dmg, fight_log = self._simulate_fight(
            fight_duration, num_enemies, mob_time_fraction, attack_speed_mult, log_actions=True
        )

        # Aggregate damage by skill from fight log
        skill_damage = {}
        skill_mob_damage = {}
        skill_boss_damage = {}

        if fight_log:
            for entry in fight_log:
                name = entry.skill_name
                if name not in skill_damage:
                    skill_damage[name] = 0.0
                    skill_mob_damage[name] = 0.0
                    skill_boss_damage[name] = 0.0
                skill_damage[name] += entry.damage
                if entry.phase == 'mob':
                    skill_mob_damage[name] += entry.damage
                else:
                    skill_boss_damage[name] += entry.damage

        # Add player action skills to breakdown (skip 0-damage entries like buffs)
        for skill_name, dmg in skill_damage.items():
            if dmg <= 0:
                continue  # Skip buffs and other non-damage skills

            skill = self._skills.get(skill_name)
            if not skill:
                continue

            # Determine skill type based on skill definition
            if skill.skill_type == SkillType.BASIC_ATTACK:
                skill_type = 'basic'
            elif skill.skill_type == SkillType.ACTIVE:
                skill_type = 'active'
            elif skill.skill_type == SkillType.SUMMON:
                skill_type = 'summon'
            else:
                skill_type = 'other'

            breakdown[skill_name] = {
                'display_name': skill.name,
                'total_damage': dmg,
                'dps': dmg / fight_duration,
                'pct_of_total': 0.0,  # Calculated after total is known
                'mob_damage': skill_mob_damage.get(skill_name, 0.0),
                'boss_damage': skill_boss_damage.get(skill_name, 0.0),
                'skill_type': skill_type,
            }
            total_damage += dmg

        # Add permanent summons (not in fight simulation)
        for skill_name, skill in self._summon_skills.items():
            if not self.char.is_skill_unlocked(skill_name):
                continue
            # Skip summons already in breakdown from fight simulation
            if skill_name in breakdown:
                continue
            # Permanent summons have duration and attack_interval set
            if not (skill.duration > 0 and skill.attack_interval > 0):
                continue

            dmg_mob = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=False,
                num_enemies=num_enemies,
            )
            dmg_boss = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=True,
                num_enemies=1,
            )

            # Attack interval scales with AS (up to 2x mult, or flat reduction if specified)
            as_mult = min(attack_speed_mult, 2.0)
            if skill.scales_with_attack_speed and skill.max_as_interval_reduction > 0:
                interval = skill.attack_interval - min(skill.max_as_interval_reduction,
                                                       skill.max_as_interval_reduction * (as_mult - 1.0))
            else:
                interval = skill.attack_interval / as_mult
            attacks_per_second = 1 / interval
            hits = self.get_skill_hits(skill_name)
            targets_mob = min(self.get_skill_targets(skill_name), num_enemies)

            # Calculate phase damage (permanent uptime)
            mob_damage = dmg_mob * hits * targets_mob * attacks_per_second * fight_duration * mob_time_fraction
            boss_damage = dmg_boss * hits * 1 * attacks_per_second * fight_duration * (1 - mob_time_fraction)
            summon_dmg = mob_damage + boss_damage

            breakdown[skill_name] = {
                'display_name': skill.name,
                'total_damage': summon_dmg,
                'dps': summon_dmg / fight_duration,
                'pct_of_total': 0.0,
                'mob_damage': mob_damage,
                'boss_damage': boss_damage,
                'skill_type': 'summon',
            }
            total_damage += summon_dmg

        # Calculate proc damage (procs run in parallel with player actions) - find dynamically
        ba_name = self.char.get_active_basic_attack()
        if ba_name:
            ba_skill = self._skills.get(ba_name)
            ba_ct = ba_skill.cast_time if ba_skill else 1.0
            cast_time = self.get_cast_time(ba_ct, True, attack_speed_mult)
            attacks_per_second = 1 / cast_time
            ba_targets = self.get_skill_targets(ba_name)
        else:
            attacks_per_second = 2.0
            ba_targets = 1

        for skill_name, skill in self._proc_skills.items():
            if not self.char.is_skill_unlocked(skill_name):
                continue

            # Calculate proc's contribution
            dmg_mob = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=False,
                num_enemies=num_enemies,
            )
            dmg_boss = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=True,
                num_enemies=1,
            )

            if skill.max_stacks > 0:
                # Stack-based proc (Meso Explosion, Blood Money)
                hits = self.get_skill_hits(skill_name)
                mastery_cd_pct = self.get_mastery_bonus(skill_name, "skill_cooldown_reduction") * 100
                effective_cd = self.char.get_effective_skill_cooldown(skill.cooldown, mastery_cd_pct)
                gen_chance = self.get_effective_proc_chance(skill_name)

                # Mastery can increase max stacks (e.g., Blood Money - Damage doubles stacks)
                effective_max_stacks = skill.max_stacks
                stack_mastery = self.get_mastery_bonus(skill_name, "skill_effect")
                if stack_mastery > 0:
                    effective_max_stacks = int(skill.max_stacks * (1 + stack_mastery / 100))

                ba_targets_mob = min(ba_targets, num_enemies)
                ba_targets_boss = 1

                if skill.stack_source:
                    source_chance = self.get_effective_proc_chance(skill.stack_source)
                    stacks_per_atk_mob = ba_targets_mob * source_chance * gen_chance
                    stacks_per_atk_boss = ba_targets_boss * source_chance * gen_chance
                else:
                    stacks_per_atk_mob = ba_targets_mob * gen_chance
                    stacks_per_atk_boss = ba_targets_boss * gen_chance

                attacks_in_cd = attacks_per_second * effective_cd
                accumulated_mob = stacks_per_atk_mob * attacks_in_cd
                accumulated_boss = stacks_per_atk_boss * attacks_in_cd
                mob_stacks = min(effective_max_stacks, int(accumulated_mob))
                boss_stacks = min(effective_max_stacks, int(accumulated_boss))

                mob_targets = min(mob_stacks, num_enemies)
                boss_targets = min(boss_stacks, 1)

                # Total damage over fight duration
                triggers_mob = fight_duration * mob_time_fraction / effective_cd
                triggers_boss = fight_duration * (1 - mob_time_fraction) / effective_cd
                mob_damage = dmg_mob * hits * mob_targets * triggers_mob
                boss_damage = dmg_boss * hits * boss_targets * triggers_boss

                if skill.single_target_stack_bonus > 0 and boss_targets == 1:
                    boss_damage *= (1 + skill.single_target_stack_bonus * boss_stacks)

            elif skill.attack_interval > 0:
                # Marking-style procs (like Mark of Assassin)
                interval = skill.attack_interval
                flat_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval")
                if flat_reduction != 0:
                    interval = max(1.0, interval + flat_reduction)
                pct_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval_pct")
                if pct_reduction != 0:
                    interval = max(1.0, interval * (1 + pct_reduction / 100))

                marks_per_interval_mob = min(skill.base_targets, num_enemies)
                procs_per_second_mob = marks_per_interval_mob / interval
                procs_per_second_boss = 1 / interval

                mob_damage = dmg_mob * 1 * procs_per_second_mob * fight_duration * mob_time_fraction
                boss_damage = dmg_boss * 1 * procs_per_second_boss * fight_duration * (1 - mob_time_fraction)
            else:
                # Standard proc calculation
                targets_mob = min(self.get_skill_targets(skill_name), num_enemies)
                targets_boss = 1

                proc_chance = skill.proc_chance
                if skill.scales_with_attack_speed:
                    proc_chance = min(proc_chance * attack_speed_mult, proc_chance * 2)

                if skill.cooldown > 0:
                    mastery_cd_reduction_pct = self.get_mastery_bonus(skill_name, "skill_cooldown_reduction")
                    effective_cd = skill.cooldown * (1 - mastery_cd_reduction_pct)
                    procs_per_second = min(attacks_per_second * proc_chance, 1 / effective_cd)
                else:
                    procs_per_second = attacks_per_second * proc_chance

                mob_damage = dmg_mob * targets_mob * procs_per_second * fight_duration * mob_time_fraction
                boss_damage = dmg_boss * targets_boss * procs_per_second * fight_duration * (1 - mob_time_fraction)
            proc_dmg = mob_damage + boss_damage

            breakdown[skill_name] = {
                'display_name': skill.name,
                'total_damage': proc_dmg,
                'dps': proc_dmg / fight_duration,
                'pct_of_total': 0.0,
                'mob_damage': mob_damage,
                'boss_damage': boss_damage,
                'skill_type': 'proc',
            }
            total_damage += proc_dmg

        # Calculate percentages
        if total_damage > 0:
            for skill_name in breakdown:
                breakdown[skill_name]['pct_of_total'] = (
                    breakdown[skill_name]['total_damage'] / total_damage * 100
                )

        return breakdown

    def get_skill_damage_breakdown_with_cache(
        self,
        fight_duration: float = 60.0,
        num_enemies: int = 12,
        mob_time_fraction: float = 0.6,
    ) -> Tuple[Dict[str, Dict], CachedRotationResult]:
        """
        Calculate skill damage breakdown and return both the breakdown and a cache
        object for fast recalculation with Tier 1/2 stat changes.

        Returns:
            Tuple of (breakdown dict, CachedRotationResult)
        """
        breakdown = self.get_skill_damage_breakdown(
            fight_duration, num_enemies, mob_time_fraction
        )

        # Calculate baseline multipliers for Tier 1/2 fast recalculation
        # These are the current character's multipliers that were used in the simulation
        baseline_universal_mult = self._calculate_baseline_universal_mult()
        baseline_normal_mult = 1 + self.char.normal_damage / 100
        baseline_boss_mult = 1 + self.char.boss_damage / 100

        # Build per-skill mob/boss DPS breakdown
        skill_mob_dps = {}
        skill_boss_dps = {}
        total_dps = 0.0

        for skill_name, info in breakdown.items():
            skill_mob_dps[skill_name] = info['mob_damage'] / fight_duration
            skill_boss_dps[skill_name] = info['boss_damage'] / fight_duration
            total_dps += info['dps']

        # Create rotation key for cache invalidation
        # This captures all Tier 3 stats that affect rotation
        rotation_key = (
            self.char.level,
            self.char.all_skills_bonus,
            self.char.skill_1st_bonus,
            self.char.skill_2nd_bonus,
            self.char.skill_3rd_bonus,
            self.char.skill_4th_bonus,
            self.char.attack_speed_pct,
        )

        cached = CachedRotationResult(
            total_dps=total_dps,
            skill_mob_dps=skill_mob_dps,
            skill_boss_dps=skill_boss_dps,
            baseline_universal_mult=baseline_universal_mult,
            baseline_normal_mult=baseline_normal_mult,
            baseline_boss_mult=baseline_boss_mult,
            rotation_key=rotation_key,
        )

        return breakdown, cached

    def _calculate_baseline_universal_mult(self) -> float:
        """
        Calculate the combined universal multiplier from Tier 1 stats.

        This is the product of all multipliers that scale ALL damage identically:
        main_stat × damage% × crit_expected × FD × def_pen

        Used for fast Tier 1 recalculation: new_dps = cached_dps × (new_mult / old_mult)
        """
        # Main stat multiplier
        base_main_stat = self.char.main_stat_flat + self.get_global_stat("main_stat_flat")
        total_main_stat = base_main_stat * (1 + (self.char.main_stat_pct + self.get_total_stat_bonus("main_stat_pct")) / 100)
        total_main_stat += self.char.main_stat_conversion  # skill-converted stat, not multiplied by %
        total_secondary_stat = self.char.secondary_stat_flat * (1 + self.char.secondary_stat_pct / 100)
        main_stat_mult = 1 + (total_main_stat / 10000) + (total_secondary_stat / 40000)

        # Damage %
        damage_mult = 1 + (self.char.damage_pct + self.get_total_stat_bonus("damage_pct")) / 100

        # Crit expected value multiplier
        crit_rate_bonus = self.get_total_stat_bonus("crit_rate")
        crit_rate = min((self.char.crit_rate + crit_rate_bonus) / 100, 1.0)

        # Concentration crit damage (passive buff, ~100% uptime)
        conc_per_stack = self.get_skill_bonus_value("concentration", "crit_damage")
        crit_dmg_bonus = conc_per_stack * 7

        crit_damage = self.char.crit_damage + crit_dmg_bonus
        crit_mult = 1 + crit_rate * (crit_damage / 100)

        # Defense penetration
        def_pen = self.char.def_pen_pct
        def_pen_decimal = min(def_pen / 100, 1.0)
        def_pen_mult = 1 / (1 + self.enemy_def * (1 - def_pen_decimal))

        # Note: We don't include FD here because it varies by skill
        # The "universal" part is: main_stat × damage × crit × def_pen
        return main_stat_mult * damage_mult * crit_mult * def_pen_mult

    def recalculate_dps_tier1(
        self,
        cached: CachedRotationResult,
        new_main_stat_flat: Optional[float] = None,
        new_main_stat_pct: Optional[float] = None,
        new_damage_pct: Optional[float] = None,
        new_crit_rate: Optional[float] = None,
        new_crit_damage: Optional[float] = None,
        new_defense_pen: Optional[float] = None,
    ) -> float:
        """
        Fast Tier 1 recalculation: scale cached DPS by ratio of universal multipliers.

        This is O(1) - just a ratio calculation, no simulation needed.
        Use when ONLY Tier 1 stats change (main_stat, damage%, crit, def_pen).

        Args:
            cached: CachedRotationResult from previous simulation
            new_*: New stat values. If None, uses current character value.

        Returns:
            Estimated new total DPS
        """
        # Get values (use passed value or fall back to current character)
        main_stat_flat = new_main_stat_flat if new_main_stat_flat is not None else self.char.main_stat_flat
        main_stat_pct = new_main_stat_pct if new_main_stat_pct is not None else self.char.main_stat_pct
        damage_pct = new_damage_pct if new_damage_pct is not None else self.char.damage_pct
        crit_rate = new_crit_rate if new_crit_rate is not None else self.char.crit_rate
        crit_damage = new_crit_damage if new_crit_damage is not None else self.char.crit_damage
        defense_pen = new_defense_pen if new_defense_pen is not None else self.char.def_pen_pct

        # Calculate new universal multiplier
        base_main_stat = main_stat_flat + self.get_global_stat("main_stat_flat")
        total_main_stat = base_main_stat * (1 + (main_stat_pct + self.get_total_stat_bonus("main_stat_pct")) / 100)
        total_main_stat += self.char.main_stat_conversion  # skill-converted stat, not multiplied by %
        total_secondary_stat = self.char.secondary_stat_flat * (1 + self.char.secondary_stat_pct / 100)
        new_main_stat_mult = 1 + (total_main_stat / 10000) + (total_secondary_stat / 40000)

        new_damage_mult = 1 + (damage_pct + self.get_total_stat_bonus("damage_pct")) / 100

        crit_rate_bonus = self.get_total_stat_bonus("crit_rate")
        new_crit_rate_capped = min((crit_rate + crit_rate_bonus) / 100, 1.0)
        conc_per_stack = self.get_skill_bonus_value("concentration", "crit_damage")
        crit_dmg_bonus = conc_per_stack * 7
        new_crit_mult = 1 + new_crit_rate_capped * ((crit_damage + crit_dmg_bonus) / 100)

        def_pen_decimal = min(defense_pen / 100, 1.0)
        new_def_pen_mult = 1 / (1 + self.enemy_def * (1 - def_pen_decimal))

        new_universal_mult = new_main_stat_mult * new_damage_mult * new_crit_mult * new_def_pen_mult

        # Scale by ratio
        ratio = new_universal_mult / cached.baseline_universal_mult
        return cached.total_dps * ratio

    def recalculate_dps_tier2(
        self,
        cached: CachedRotationResult,
        new_normal_damage_pct: Optional[float] = None,
        new_boss_damage_pct: Optional[float] = None,
    ) -> float:
        """
        Tier 2 recalculation: adjust phase weighting using cached per-skill breakdown.

        This is O(n) where n = number of skills - iterates through skill breakdown
        but doesn't run simulation. Use when boss_damage% or normal_damage% changes.

        Note: This is an approximation because skill-specific boss/normal damage
        masteries are baked into the cached mob/boss damage. For exact results
        when skill levels change, use full simulation.

        Args:
            cached: CachedRotationResult from previous simulation
            new_normal_damage_pct: New normal monster damage %. If None, uses current.
            new_boss_damage_pct: New boss damage %. If None, uses current.

        Returns:
            Estimated new total DPS
        """
        new_normal = new_normal_damage_pct if new_normal_damage_pct is not None else self.char.normal_damage
        new_boss = new_boss_damage_pct if new_boss_damage_pct is not None else self.char.boss_damage

        new_normal_mult = 1 + new_normal / 100
        new_boss_mult = 1 + new_boss / 100

        total_dps = 0.0
        for skill_name in cached.skill_mob_dps:
            # Remove old phase multipliers and apply new ones
            # mob_dps was calculated with baseline_normal_mult, boss_dps with baseline_boss_mult
            if cached.baseline_normal_mult > 0:
                adjusted_mob_dps = cached.skill_mob_dps[skill_name] / cached.baseline_normal_mult * new_normal_mult
            else:
                adjusted_mob_dps = cached.skill_mob_dps[skill_name]

            if cached.baseline_boss_mult > 0:
                adjusted_boss_dps = cached.skill_boss_dps[skill_name] / cached.baseline_boss_mult * new_boss_mult
            else:
                adjusted_boss_dps = cached.skill_boss_dps[skill_name]

            total_dps += adjusted_mob_dps + adjusted_boss_dps

        return total_dps

    def get_active_passive_effects(self) -> Dict[str, List[Dict]]:
        """
        Get all active passive effects that modify other skills.

        Returns:
            Dict mapping target_skill_name -> [
                {
                    'source': str (skill providing the bonus),
                    'effect_type': str (e.g., 'final_damage', 'targets'),
                    'value': float (the bonus value),
                },
                ...
            ]
        """
        effects = {}

        # Check SKILL_ENHANCER skills (like Maple Hero)
        for skill_name, skill in self._enhancer_skills.items():
            if not self.char.is_skill_unlocked(skill_name):
                continue
            if not skill.skill_bonuses:
                continue

            level = self.char.get_effective_skill_level(skill_name)

            for target_skill, (base, factor_index) in skill.skill_bonuses.items():
                # Check if target skill exists
                if target_skill not in self._skills:
                    continue

                value = int(self.calc_skill_damage_with_factor(base, factor_index, level))

                if target_skill not in effects:
                    effects[target_skill] = []

                effects[target_skill].append({
                    'source': skill.name,
                    'effect_type': 'final_damage',
                    'value': value,
                })

        # Check mastery bonuses
        for target_skill in self._skills:
            # Skill damage % bonuses from masteries
            skill_dmg = self.get_mastery_bonus(target_skill, "skill_damage_pct")
            if skill_dmg > 0:
                if target_skill not in effects:
                    effects[target_skill] = []
                effects[target_skill].append({
                    'source': 'Mastery',
                    'effect_type': 'skill_damage',
                    'value': skill_dmg,
                })

            # Boss damage bonuses from masteries
            boss_dmg = self.get_mastery_bonus(target_skill, "skill_boss_damage")
            if boss_dmg > 0:
                if target_skill not in effects:
                    effects[target_skill] = []
                effects[target_skill].append({
                    'source': 'Mastery',
                    'effect_type': 'boss_damage',
                    'value': boss_dmg,
                })

            # Normal monster damage bonuses from masteries
            normal_dmg = self.get_mastery_bonus(target_skill, "skill_normal_monster_damage")
            if normal_dmg > 0:
                if target_skill not in effects:
                    effects[target_skill] = []
                effects[target_skill].append({
                    'source': 'Mastery',
                    'effect_type': 'normal_monster_damage',
                    'value': normal_dmg,
                })

            # Target bonuses from masteries
            targets = self.get_mastery_bonus(target_skill, "skill_targets")
            if targets > 0:
                if target_skill not in effects:
                    effects[target_skill] = []
                effects[target_skill].append({
                    'source': 'Mastery',
                    'effect_type': 'targets',
                    'value': targets,
                })

        return effects


# =============================================================================
# ALL SKILLS VALUE CALCULATOR
# =============================================================================

@dataclass
class JobSkillBonus:
    """Tracks skill level bonuses by job."""
    first_job: int = 0
    second_job: int = 0
    third_job: int = 0
    fourth_job: int = 0

    def get_bonus_for_job(self, job: Job) -> int:
        """Get the bonus for a specific job."""
        if job == Job.FIRST:
            return self.first_job
        elif job == Job.SECOND:
            return self.second_job
        elif job == Job.THIRD:
            return self.third_job
        elif job == Job.FOURTH:
            return self.fourth_job
        return 0

    def total(self) -> int:
        """Get total bonus across all jobs (for +All Skills)."""
        return self.first_job + self.second_job + self.third_job + self.fourth_job


def create_character_with_job_bonuses(
    level: int,
    job_bonuses: JobSkillBonus,
    job_class: JobClass = JobClass.BOWMASTER,
    **extra_stats,
) -> CharacterState:
    """
    Create a character with job-specific skill bonuses.

    This allows for equipment like "+5 3rd Job Skills" to be modeled.
    """
    char = CharacterState(level=level, job_class=job_class)

    # Set skill levels based on job bonuses
    for skill_name, skill_data in char.skills.items():
        if level >= skill_data.unlock_level:
            # Base level 1 + job-specific bonus
            bonus = job_bonuses.get_bonus_for_job(skill_data.job)
            char.skill_levels[skill_name] = 1 + bonus

    # Apply extra stats
    for stat, value in extra_stats.items():
        setattr(char, stat, value)

    return char


def calculate_job_skill_value(
    level: int,
    target_job: Job,
    current_job_bonuses: JobSkillBonus,
    **extra_stats,
) -> float:
    """
    Calculate the DPS value of +1 skill level for a specific job.

    Args:
        level: Character level
        target_job: Which job to add +1 skill level to (Job.FIRST, Job.SECOND, etc.)
        current_job_bonuses: Current skill bonuses by job
        **extra_stats: Additional character stats

    Returns:
        DPS increase percent from +1 to that job's skills
    """
    # Current DPS
    char_current = create_character_with_job_bonuses(level, current_job_bonuses, **extra_stats)
    calc_current = DPSCalculator(char_current)
    dps_current = calc_current.calculate_total_dps()

    # Create new bonuses with +1 to target job
    new_bonuses = JobSkillBonus(
        first_job=current_job_bonuses.first_job + (1 if target_job == Job.FIRST else 0),
        second_job=current_job_bonuses.second_job + (1 if target_job == Job.SECOND else 0),
        third_job=current_job_bonuses.third_job + (1 if target_job == Job.THIRD else 0),
        fourth_job=current_job_bonuses.fourth_job + (1 if target_job == Job.FOURTH else 0),
    )

    # DPS with +1 to target job
    char_plus1 = create_character_with_job_bonuses(level, new_bonuses, **extra_stats)
    calc_plus1 = DPSCalculator(char_plus1)
    dps_plus1 = calc_plus1.calculate_total_dps()

    if dps_current.total_dps > 0:
        return (dps_plus1.total_dps / dps_current.total_dps - 1) * 100
    return 0


def calculate_all_skills_value_by_job(
    level: int,
    current_all_skills: int = 0,
    **extra_stats,
) -> Dict[str, float]:
    """
    Calculate the DPS value of +1 All Skills, broken down by job contribution.

    Returns:
        Dict with keys: "first_job", "second_job", "third_job", "fourth_job", "total"
        Values are DPS increase percent from +1 to that job's skills
    """
    # Create current bonuses (All Skills applies equally to all jobs)
    current_bonuses = JobSkillBonus(
        first_job=current_all_skills,
        second_job=current_all_skills,
        third_job=current_all_skills,
        fourth_job=current_all_skills,
    )

    result = {}

    # Calculate value for each job
    for job, key in [(Job.FIRST, "first_job"), (Job.SECOND, "second_job"),
                     (Job.THIRD, "third_job"), (Job.FOURTH, "fourth_job")]:
        result[key] = calculate_job_skill_value(level, job, current_bonuses, **extra_stats)

    # Total is sum of all job contributions
    result["total"] = sum(result.values())

    return result


def calculate_all_skills_value(
    level: int,
    current_all_skills: int = 0,
    **extra_stats,
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate the DPS value of +1 All Skills at a given level.

    Returns:
        Tuple of (dps_increase_percent, breakdown_by_category)

    Note: For job-level breakdown, use calculate_all_skills_value_by_job()
    """
    # Create character at current level
    char_current = create_character_at_level(level, current_all_skills)
    for stat, value in extra_stats.items():
        setattr(char_current, stat, value)

    calc_current = DPSCalculator(char_current)
    dps_current = calc_current.calculate_total_dps()

    # Create character with +1 All Skills
    char_plus1 = create_character_at_level(level, current_all_skills + 1)
    for stat, value in extra_stats.items():
        setattr(char_plus1, stat, value)

    calc_plus1 = DPSCalculator(char_plus1)
    dps_plus1 = calc_plus1.calculate_total_dps()

    # Calculate increase
    if dps_current.total_dps > 0:
        dps_increase = (dps_plus1.total_dps / dps_current.total_dps - 1) * 100
    else:
        dps_increase = 0

    # Breakdown by damage category
    breakdown = {}
    if dps_current.basic_attack_dps > 0:
        breakdown["basic_attack"] = (dps_plus1.basic_attack_dps / dps_current.basic_attack_dps - 1) * 100
    if dps_current.active_skill_dps > 0:
        breakdown["active_skills"] = (dps_plus1.active_skill_dps / dps_current.active_skill_dps - 1) * 100
    if dps_current.summon_dps > 0:
        breakdown["summons"] = (dps_plus1.summon_dps / dps_current.summon_dps - 1) * 100
    if dps_current.proc_dps > 0:
        breakdown["procs"] = (dps_plus1.proc_dps / dps_current.proc_dps - 1) * 100

    return dps_increase, breakdown


# =============================================================================
# MAIN (Test)
# =============================================================================

if __name__ == "__main__":
    print("MapleStory Idle - Skill DPS Calculator (with Masteries)")
    print("=" * 60)

    # Test at your level (100) with +44 All Skills
    level = 100
    all_skills = 44

    print(f"\nCharacter Level: {level}")
    print(f"All Skills Bonus: +{all_skills}")
    print(f"Current Job: {get_job_for_level(level).name}")

    # Show unlocked masteries
    masteries = get_unlocked_masteries(level)
    print(f"\nUnlocked Masteries: {len(masteries)}")

    # Create character and calculate DPS
    char = create_character_at_level(level, all_skills)
    char.attack = 1000
    char.main_stat_pct = 50
    char.damage_pct = 30
    char.boss_damage = 20
    char.crit_rate = 70
    char.crit_damage = 200
    char.attack_speed_pct = 50

    calc = DPSCalculator(char)
    result = calc.calculate_total_dps()

    print(f"\n{'='*60}")
    print("DPS BREAKDOWN")
    print(f"{'='*60}")
    print(f"Total DPS: {result.total_dps:,.0f}")
    print(f"  Basic Attack: {result.basic_attack_dps:,.0f} ({result.basic_attack_dps/result.total_dps*100:.1f}%)")
    print(f"  Active Skills: {result.active_skill_dps:,.0f} ({result.active_skill_dps/result.total_dps*100:.1f}%)")
    print(f"  Summons: {result.summon_dps:,.0f} ({result.summon_dps/result.total_dps*100:.1f}%)")
    print(f"  Procs: {result.proc_dps:,.0f} ({result.proc_dps/result.total_dps*100:.1f}%)")
    print(f"\nSkills Used: {', '.join(result.skills_used)}")

    # Calculate value of +1 All Skills
    print(f"\n{'='*60}")
    print("VALUE OF +1 ALL SKILLS")
    print(f"{'='*60}")

    increase, breakdown = calculate_all_skills_value(
        level, all_skills,
        attack=1000, main_stat_pct=50, damage_pct=30,
        boss_damage=20, crit_rate=70, crit_damage=200,
        attack_speed_pct=50,
    )

    print(f"\nAt Level {level} with +{all_skills} existing:")
    print(f"  +1 All Skills = +{increase:.4f}% DPS")
    print(f"\n  Breakdown:")
    for category, pct in breakdown.items():
        print(f"    {category}: +{pct:.4f}%")

    # Value at different levels
    print(f"\n{'='*60}")
    print("ALL SKILLS VALUE BY CHARACTER LEVEL")
    print(f"{'='*60}")

    for test_level in [60, 80, 100, 120, 140]:
        inc, _ = calculate_all_skills_value(
            test_level, 44,
            attack=1000, main_stat_pct=50, damage_pct=30,
            boss_damage=20, crit_rate=70, crit_damage=200,
            attack_speed_pct=50,
        )
        print(f"  Level {test_level}: +1 All Skills = +{inc:.4f}% DPS")
