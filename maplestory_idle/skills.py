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
from enum import Enum
from typing import Callable, Dict, List, Optional, Set, Tuple
import math

from job_classes import JobClass


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
    2. Apply flat reduction (from hat potential, etc.)
    3. If flat reduction would push cooldown below 7 seconds:
       - Loses 0.5 sec of effectiveness per second below 7
    4. Minimum cooldown is 4 seconds

    Args:
        base_cooldown: Original skill cooldown in seconds
        percent_reduction: Percentage reduction (0-100)
        flat_reduction: Flat seconds reduction (e.g., 2.0 from Mystic hat)

    Returns:
        Final cooldown in seconds (minimum 4.0)
    """
    # Step 1: Apply percentage reduction (capped at 100%)
    pct = min(percent_reduction, 100) / 100
    after_pct = base_cooldown * (1 - pct)

    # Step 2: Apply flat reduction with diminishing returns
    # If result would go below 7, we lose effectiveness
    naive_result = after_pct - flat_reduction

    if naive_result >= 7:
        # No diminishing returns needed
        final_cd = naive_result
    else:
        # Calculate how far below 7 the naive result would be
        seconds_below_7 = 7 - naive_result
        # Lose 0.5s of effectiveness per second below 7
        effectiveness_lost = seconds_below_7 * 0.5
        # Apply reduced flat reduction
        effective_flat = max(0, flat_reduction - effectiveness_lost)
        final_cd = after_pct - effective_flat

    # Step 3: Minimum 4 seconds
    return max(final_cd, 4.0)


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

    # Per-level scaling (calculated from your data)
    damage_per_level: float = 0     # Additional damage % per skill level

    # Cooldown (0 = no cooldown, can spam)
    cooldown: float = 0             # Seconds
    duration: float = 0             # For summons/buffs: how long they last

    # Special mechanics
    proc_chance: float = 1.0        # For procs: activation chance
    attack_interval: float = 0      # For summons: time between attacks
    scales_with_attack_speed: bool = True  # Does AS affect this skill?

    # For skills that grant bonuses to other skills (e.g., Maple Hero)
    # Dict mapping skill_name -> (base_value, per_level)
    # Formula: floor(base + per_level * level)
    skill_bonuses: Optional[Dict[str, Tuple[float, float]]] = None

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
    MasteryNode("Phoenix - Target", 78, 0, "skill_targets", "phoenix", 2, "Phoenix max targets +2"),
    MasteryNode("Phoenix - Strike Interval", 82, 6750, "skill_attack_interval", "phoenix", -0.3, "Phoenix strike interval -30%"),
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
            "crit_rate": (5.0, 0.0146),  # (6.5 - 5) / 103
        },
    ),

    "archer_mastery": SkillData(
        name="Archer Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=10,
        skill_bonuses={
            "attack_speed": (5.0, 0.0146),
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
            "attack_speed": (15.0, 0.0),  # +15% attack speed while active
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
        cooldown=0,
        duration=999999,
        attack_interval=1.0,
        scales_with_attack_speed=True,
    ),

    "bow_acceleration": SkillData(
        name="Bow Acceleration",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=33,
        skill_bonuses={
            "attack_speed": (5.0, 0.0148),  # (7.2 - 5) / 149
        },
    ),

    "bow_mastery": SkillData(
        name="Bow Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=43,
        skill_bonuses={
            "min_dmg_mult": (15.0, 0.045),  # (21.7 - 15) / 149
        },
    ),

    "soul_arrow": SkillData(
        name="Soul Arrow: Bow",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=45,
        skill_bonuses={
            "dex_flat": (50.0, 0.67),  # Scales up to 150 with AS
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
        proc_chance=0.25,
    ),

    "physical_training": SkillData(
        name="Physical Training",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=38,
        skill_bonuses={
            "basic_attack_damage": (10.0, 0.030),  # (14.5 - 10) / 149
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
        base_targets=3,
        damage_per_level=3.02,  # (1176 - 600) / 191
        cooldown=60.0,
        duration=20.0,
        attack_interval=3.0,
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
        cooldown=40.0,
        duration=60.0,
        attack_interval=0.3,
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
            "final_damage": (15.0, 0.045),  # (23.6 - 15) / 191
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
            "final_damage": (10.0, 0.030),  # (15.7 - 10) / 191
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
            "crit_damage": (3.0, 0.0089),  # Per stack, (4.7 - 3) / 191
        },
    ),

    "marksmanship": SkillData(
        name="Marksmanship",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=74,
        skill_bonuses={
            "attack_pct": (20.0, 0.060),  # (31.5 - 20) / 191
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
    ),

    "hurricane": SkillData(
        name="Hurricane",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=103,
        base_damage_pct=800.0,
        base_hits=20,
        base_targets=1,
        damage_per_level=4.09,  # (980 - 800) / 44
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
        duration=15.0,
        # Wiki data: L1: CR 8%, CD 40% | L200: CR 14.4%, CD 72%
        # Per level: CR +0.032%, CD +0.161%
        skill_bonuses={
            "crit_rate": (8.0, 0.032),    # 8% + 0.032%/level (14.4% at L200)
            "crit_damage": (40.0, 0.161), # 40% + 0.161%/level (72% at L200)
        },
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
            "quiver_cartridge": (500.0, 2.0),  # final_damage
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
            "flash_mirage": (400.0, 1.5),  # final_damage
        },
        skill_target_bonuses={
            "flash_mirage": (4, 0),  # +4 targets (flat, doesn't scale)
        },
    ),

    "illusion_step": SkillData(
        name="Illusion Step",
        skill_type=SkillType.PASSIVE_BUFF,  # Toggling buff with uptime
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=117,
        duration=15.0,   # Attack phase duration
        cooldown=20.0,   # Full cycle length (15s attack + 5s evasion)
        # Formula: int((base + per_level * level) * 10) / 10
        # Attack phase: +X% Attack
        # Evasion phase: +20 Evasion, -X% damage taken
        skill_bonuses={
            "attack_pct": (10.0, 0.077),  # TODO: verify scaling
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
            "final_attack": (500.0, 2.0),  # final_damage
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
            "skill_damage": (15.0, 0.045),  # (17 - 15) / 44
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
            "defense_pen": (10.0, 0.030),  # (11.3 - 10) / 44
            "final_damage": (10.0, 0.030),
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
            "arrow_platter": (25, 1.25),   # (base, per_level) -> final_damage
            "phoenix": (30, 1.5),
            "covering_fire": (100, 5.0),
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
            "attack_speed": (15.0, 0.0),  # +15% attack speed while active (no scaling)
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
            "attack_pct": (12.0, 0.0),   # +12% Attack, does NOT scale (wiki)
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
            "attack_speed": (5.0, 0.025),  # +5% AS at base
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
            "attack_pct": (20.0, 0.1),  # +20% attack to allies
        },
    ),

    "spell_mastery": SkillData(
        name="Spell Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=43,  # Wiki: unlocks at level 43
        skill_bonuses={
            "min_dmg_mult": (15.0, 0.075),  # +15% min damage
        },
    ),

    "high_wisdom": SkillData(
        name="High Wisdom",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=50,  # Wiki: unlocks at level 50
        skill_bonuses={
            "crit_rate": (8.0, 0.04),  # +8% crit rate
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
            "crit_rate": (8.0, 0.04),    # +8% crit rate
            "crit_damage": (12.0, 0.06),  # +12% crit damage
        },
    ),

    "element_amplification": SkillData(
        name="Element Amplification",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=75,  # Wiki: unlocks at level 75
        skill_bonuses={
            "final_damage": (15.0, 0.075),  # +15% final damage (at 50%+ MP)
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
            "thunder_sphere": (20, 1.0),   # +20% FD base, +1% per level
            "glacier_wall": (30, 1.5),     # +30% FD base, +1.5% per level
            "thunder_bolt": (100, 5.0),    # +100% FD base, +5% per level
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
            "final_damage": (15.0, 0.075),
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
            "final_damage": (3.0, 0.0),  # +3% per stack
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
        effect_type="skill_damage_pct",
        effect_target="global",
        effect_value=15.0,
        description="Skill Damage +15%",
    ),
    MasteryNode(
        name="Basic Attack Damage I",
        unlock_level=136,
        effect_type="basic_attack_dmg_pct",
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
            "attack_speed": (15.0, 0.0),
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
            "movement_speed": (10.0, 0.099),  # 10% base, Lv91 → 19%
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
            "crit_rate": (5.0, 0.034),    # Lv91 → 8.1%
            "attack_pct": (10.0, 0.040),  # Lv91 → 13.6%
        },
    ),

    "thief_mastery": SkillData(
        name="Thief Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=10,
        skill_bonuses={
            "attack_speed": (5.0, 0.0146),  # Similar to Archer Mastery
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
            "attack_speed": (4.0, 0.023),  # 4% base, Lv127 → 6.9%
        },
    ),

    "physical_training": SkillData(
        name="Physical Training",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=38,
        skill_bonuses={
            "basic_attack_damage": (10.0, 0.030),  # 10% base, Lv127 → 13.8%
        },
    ),

    "claw_mastery": SkillData(
        name="Claw Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=40,
        skill_bonuses={
            "min_dmg_mult": (15.0, 0.045),  # 15% base, Lv127 → 20.7%
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
            "crit_rate": (5.0, 0.025),     # 5% base, Lv127 → 8.2%
            "crit_damage": (10.0, 0.030),  # 10% base, Lv127 → 13.8%
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
        cooldown=13.0,
    ),

    "shadow_partner": SkillData(
        name="Shadow Partner",
        skill_type=SkillType.PASSIVE_PROC,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=60,
        base_damage_pct=70.0,  # Deals X% additional damage
        base_hits=1,
        base_targets=1,
        damage_per_level=0.186,  # Lv186 → 104.6%
        proc_chance=0.25,  # 25% chance
    ),

    "dark_flare": SkillData(
        name="Dark Flare",
        skill_type=SkillType.SUMMON,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=65,
        base_damage_pct=500.0,
        base_hits=2,
        base_targets=5,
        damage_per_level=1.46,  # Lv186 → 772%
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
            "boss_damage": (15.0, 0.070),  # 15% base, Lv186 → 28%
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
            "final_damage": (10.0, 0.030),    # 10% base, Lv186 → 15.5%
            "attack_speed": (8.0, 0.024),     # 8% base, Lv186 → 12.4%
        },
    ),

    "expert_throwing_star_handling": SkillData(
        name="Expert Throwing Star Handling",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=75,
        skill_bonuses={
            "attack_pct": (20.0, 0.043),  # 20% base, Lv186 → 28%
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
        cooldown=13.0,
    ),

    "sudden_raid": SkillData(
        name="Sudden Raid",
        skill_type=SkillType.ACTIVE,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=103,
        base_damage_pct=800.0,
        base_hits=8,
        base_targets=6,
        damage_per_level=4.09,  # Similar to Hurricane scaling
        cooldown=40.0,
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
            "crit_rate": (8.0, 0.032),     # 8% + 0.032%/level
            "crit_damage": (40.0, 0.161),  # 40% + 0.161%/level
        },
    ),

    "toxic_venom": SkillData(
        name="Toxic Venom",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=105,
        skill_bonuses={
            "venom": (500.0, 2.0),  # final_damage to Venom
        },
    ),

    "night_lords_mark": SkillData(
        name="Night Lord's Mark",
        skill_type=SkillType.SKILL_ENHANCER,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=110,
        skill_bonuses={
            "mark_of_assassin": (400.0, 1.5),  # final_damage to Mark of Assassin
        },
    ),

    "claw_expert": SkillData(
        name="Claw Expert",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=120,
        skill_bonuses={
            "skill_damage": (15.0, 0.045),  # Similar to Bow Expert
        },
    ),

    "dark_harmony": SkillData(
        name="Dark Harmony",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=125,
        skill_bonuses={
            "defense_pen": (10.0, 0.030),
            "final_damage": (10.0, 0.030),
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
            "dark_flare": (25, 0.57),        # base 25%, at Lv56 → 57%
            "venom": (75, 2.05),             # base 75%, at Lv56 → 190%
            "shadow_partner": (75, 2.05),    # base 75%, at Lv56 → 190%
            "gust_charm": (200, 5.25),       # base 200%, at Lv56 → 494%
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
    MasteryNode("Dark Flare - Strike Interval", 104, 0, "skill_attack_interval", "dark_flare", -0.4, "Dark Flare strike interval -40%"),
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
# JOB CLASS SKILL/MASTERY REGISTRY
# =============================================================================

# Registry maps job class to its skills and masteries
# This allows DPSCalculator to work with any job class
SKILLS_BY_JOB: Dict[JobClass, Dict[str, 'SkillData']] = {
    JobClass.BOWMASTER: BOWMASTER_SKILLS,
    JobClass.ARCHMAGE_ICE_LIGHTNING: ICE_LIGHTNING_SKILLS,
    JobClass.NIGHT_LORD: NIGHT_LORD_SKILLS,
}

MASTERIES_BY_JOB: Dict[JobClass, List['MasteryNode']] = {
    JobClass.BOWMASTER: BOWMASTER_MASTERIES,
    JobClass.ARCHMAGE_ICE_LIGHTNING: ICE_LIGHTNING_MASTERIES,
    JobClass.NIGHT_LORD: NIGHT_LORD_MASTERIES,
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
    main_stat_flat: float = 0  # Flat DEX/main stat (1% per point)
    main_stat_pct: float = 0   # DEX%/main stat %
    secondary_stat_flat: float = 0  # Flat STR/secondary stat (0.25% per point)
    secondary_stat_pct: float = 0   # STR%/secondary stat %
    damage_pct: float = 0
    boss_damage_pct: float = 0       # Global boss damage % (applied during boss phase)
    normal_damage_pct: float = 0     # Global normal monster damage % (applied during mob phase)
    crit_rate: float = 50.0
    crit_damage: float = 150.0
    min_dmg_mult: float = 0
    max_dmg_mult: float = 0
    skill_damage_pct: float = 0
    basic_attack_dmg_pct: float = 0
    final_damage_pct: float = 0
    defense_pen: float = 0
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

    # For stat matching mode: which BUFF skills are manually enabled (full stat value)
    # e.g., {"nimble_feet", "sharp_eyes"} means both buffs are active for stat display
    enabled_buffs: Set[str] = field(default_factory=set)

    @property
    def skills(self) -> Dict[str, 'SkillData']:
        """Get skills dictionary for this character's job class."""
        return get_skills_for_job(self.job_class)

    @property
    def masteries(self) -> List['MasteryNode']:
        """Get masteries list for this character's job class."""
        return get_masteries_for_job(self.job_class)

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
        """Check if a skill is unlocked at current level."""
        if skill_name not in self.skills:
            return False
        return self.level >= self.skills[skill_name].unlock_level

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
    char.boss_damage_pct = 100
    char.normal_damage_pct = 50
    char.crit_rate = 80
    char.crit_damage = 150
    char.final_damage_pct = 50
    char.defense_pen = 30

    return char


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
    'crit_rate', 'crit_damage', 'final_damage_pct', 'defense_pen'
})

TIER_2_PHASE_STATS = frozenset({
    'boss_damage_pct', 'normal_damage_pct'
})

TIER_3_ROTATION_STATS = frozenset({
    'attack_speed_pct', 'all_skills_bonus', 'skill_1st_bonus', 'skill_2nd_bonus',
    'skill_3rd_bonus', 'skill_4th_bonus', 'cooldown_reduction'
})


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
        # Cache skills and masteries for this character's job class
        self._skills = char.skills
        self._masteries = char.masteries
        self.mastery_bonuses = get_mastery_bonuses(char.level, self._masteries)

        # Instance-level caches for frequently-called methods
        # These values are stable for a given character state
        self._skill_damage_cache: Dict[str, float] = {}
        self._skill_hits_cache: Dict[str, int] = {}
        self._skill_targets_cache: Dict[str, int] = {}

    def get_skill(self, skill_name: str) -> Optional[SkillData]:
        """Get skill data by name for this character's job class."""
        return self._skills.get(skill_name)

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
                    base, per_level = source_skill.skill_bonuses[skill_name]
                    total += int(base + per_level * level)

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
            Calculated value using formula: int((base + per_level * level) * 10) / 10
            Returns 0 if skill not unlocked or stat not in skill_bonuses
        """
        if not self.char.is_skill_unlocked(skill_name):
            return 0.0

        skill = self._skills.get(skill_name)
        if not skill or not skill.skill_bonuses or stat_name not in skill.skill_bonuses:
            return 0.0

        level = self.char.get_effective_skill_level(skill_name)
        base, per_level = skill.skill_bonuses[stat_name]
        return self.calc_skill_value(base, per_level, level)

    def calculate_attack_speed_mult(self, active_buffs: Optional[Set[str]] = None) -> float:
        """
        Calculate attack speed multiplier including passive skills and active buffs.

        This consolidates attack speed calculation in one place for use by:
        - DPS simulation (with dynamically tracked buffs)
        - Stat display (with user-enabled buffs)

        Args:
            active_buffs: Set of currently active buff names. If None, uses char.enabled_buffs.

        Returns:
            Attack speed multiplier capped at 2.5 (150% bonus)
        """
        # Start with character's base attack speed %
        attack_speed_pct = self.char.attack_speed_pct

        # Add passive skill bonuses (PASSIVE_STAT type)
        skill_bonuses = self.get_all_skill_stat_bonuses()
        for as_value in skill_bonuses.get("attack_speed", []):
            attack_speed_pct += as_value

        # Add global mastery bonus
        attack_speed_pct += self.get_global_stat("attack_speed")

        # Add active buff bonuses (BUFF type)
        buff_bonuses = self.get_buff_stat_bonuses(active_buffs)
        for as_value in buff_bonuses.get("attack_speed", []):
            attack_speed_pct += as_value

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

        for skill_name, skill in self._skills.items():
            # Only process PASSIVE_STAT skills with skill_bonuses defined
            if skill.skill_type != SkillType.PASSIVE_STAT or not skill.skill_bonuses:
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
            for stat_type, (base, per_level) in skill.skill_bonuses.items():
                value = self.calc_skill_value(base, per_level, level)
                if stat_type not in bonuses:
                    bonuses[stat_type] = []
                bonuses[stat_type].append(value)

        return bonuses

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

        for skill_name, skill in self._skills.items():
            if skill.skill_type != SkillType.BUFF:
                continue
            if skill_name not in buffs_to_check:
                continue
            if not self.char.is_skill_unlocked(skill_name):
                continue
            if not skill.skill_bonuses:
                continue

            level = self.char.get_effective_skill_level(skill_name)

            for stat_name, (base, per_level) in skill.skill_bonuses.items():
                value = self.calc_skill_value(base, per_level, level)
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
            "dex_flat": "main_stat_flat",
            "main_stat_flat": "main_stat_flat",
            "dex_pct": "main_stat_pct",
            "attack_pct": "attack",
            "basic_attack_damage": "basic_attack_dmg_pct",
            "skill_damage": "skill_damage_pct",
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

        # Get cast time based on attack speed
        cast_time = self.get_cast_time(1.0, True, attack_speed_mult)

        # Calculate hits per second from each source dynamically
        hits_per_second = 0.0

        # Basic attack
        basic_skill_name = self.char.get_active_basic_attack()
        if basic_skill_name and self.char.is_skill_unlocked(basic_skill_name):
            basic_hits = self.get_skill_hits(basic_skill_name)
            attacks_per_second = 1 / cast_time
            hits_per_second += basic_hits * attacks_per_second

        # Active skills (contribute hits based on cooldown)
        for skill_name, skill in self._skills.items():
            if skill.skill_type != SkillType.ACTIVE:
                continue
            if not self.char.is_skill_unlocked(skill_name):
                continue
            skill_hits = self.get_skill_hits(skill_name)
            skill_cd = self.char.get_effective_skill_cooldown(skill.cooldown, 0)
            if skill_cd > 0:
                hits_per_second += skill_hits / skill_cd

        # Summons (contribute hits based on interval and uptime)
        for skill_name, skill in self._skills.items():
            if skill.skill_type != SkillType.SUMMON:
                continue
            if not self.char.is_skill_unlocked(skill_name):
                continue
            if skill.duration <= 0 or skill.attack_interval <= 0:
                continue
            interval = skill.attack_interval
            interval_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval")
            if interval_reduction != 0:
                interval = max(1.0, interval + interval_reduction)  # Flat second reduction
            # Calculate uptime
            if skill.cooldown > 0:
                mastery_pct_reduction = self.get_mastery_bonus(skill_name, "skill_cooldown_reduction") * 100
                skill_cd = self.char.get_effective_skill_cooldown(skill.cooldown, mastery_pct_reduction)
                uptime = min(skill.duration / skill_cd, 1.0)
            else:
                uptime = 1.0
            hits_per_second += (1 / interval) * uptime

        # Procs (contribute hits based on proc chance and possibly ICD)
        for skill_name, skill in self._skills.items():
            if skill.skill_type != SkillType.PASSIVE_PROC:
                continue
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

        # Duration: 5 sec base + mastery bonus (flat seconds)
        duration = 5.0
        duration += self.get_mastery_bonus("mortal_blow", "skill_duration")

        # Uptime = duration / (duration + build_time)
        uptime = duration / (duration + build_time)

        return uptime

    def get_skill_damage_pct(self, skill_name: str) -> float:
        """Get total damage % for a skill including level scaling and masteries."""
        # Check cache first
        if skill_name in self._skill_damage_cache:
            return self._skill_damage_cache[skill_name]

        if skill_name not in self._skills:
            return 0

        skill = self._skills[skill_name]
        level = self.char.get_effective_skill_level(skill_name)

        # Base + level scaling
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
        for skill_name, skill in self._skills.items():
            if skill.skill_type == SkillType.PASSIVE_STAT and skill.skill_bonuses:
                if stat_type in skill.skill_bonuses:
                    if self.char.is_skill_unlocked(skill_name):
                        level = self.char.get_effective_skill_level(skill_name)
                        base, per_level = skill.skill_bonuses[stat_type]
                        total += self.calc_skill_value(base, per_level, level)

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
        """
        if attack_speed_mult is None:
            attack_speed_mult = 1.0
        base = self.char.attack * (skill_damage_pct / 100)

        # Main stat (1% per point) and secondary stat (0.25% per point)
        # stat_dmg_pct = main_stat * 0.01 + secondary_stat * 0.0025
        # multiplier = 1 + (stat_dmg_pct / 100)
        base_main_stat = self.char.main_stat_flat + self.get_global_stat("main_stat_flat")
        total_main_stat = base_main_stat * (1 + (self.char.main_stat_pct + self.get_total_stat_bonus("main_stat_pct")) / 100)
        total_secondary_stat = self.char.secondary_stat_flat * (1 + self.char.secondary_stat_pct / 100)
        main_stat_mult = 1 + (total_main_stat / 10000) + (total_secondary_stat / 40000)

        # Damage %
        damage_mult = 1 + (self.char.damage_pct + self.get_total_stat_bonus("damage_pct")) / 100

        # Phase-specific damage multiplier (for realistic DPS calculation)
        if is_boss_phase is True:
            # Boss phase: apply global boss damage + skill-specific boss damage masteries
            phase_dmg = self.char.boss_damage_pct
            phase_dmg += self.get_mastery_bonus(skill_name, "skill_boss_damage")
            phase_mult = 1 + phase_dmg / 100
        elif is_boss_phase is False:
            # Mob phase: apply global normal damage + skill-specific normal monster damage masteries
            phase_dmg = self.char.normal_damage_pct
            phase_dmg += self.get_mastery_bonus(skill_name, "skill_normal_monster_damage")
            # Add innate normal monster damage from skill definition (e.g., Arrow Platter +200%)
            if skill_name and skill_name in self._skills:
                phase_dmg += self._skills[skill_name].innate_normal_monster_damage
            phase_mult = 1 + phase_dmg / 100
        else:
            # Legacy behavior (is_boss_phase=None): apply boss_mult to everything
            # This preserves backward compatibility for existing calculate_total_dps()
            boss_dmg = self.char.boss_damage_pct
            boss_dmg += self.get_mastery_bonus(skill_name, "skill_boss_damage")
            phase_mult = 1 + boss_dmg / 100

        # Skill/Basic Attack damage type
        # Note: get_total_stat_bonus already includes global mastery bonuses
        if damage_type == DamageType.BASIC:
            type_bonus = self.char.basic_attack_dmg_pct
            type_bonus += self.get_total_stat_bonus("basic_attack_damage")
        else:
            type_bonus = self.char.skill_damage_pct
            type_bonus += self.get_total_stat_bonus("skill_damage")

        type_mult = 1 + type_bonus / 100

        # Final damage (multiplicative)
        # Note: Global FD from extreme_archery and armor_break should be in char.final_damage_pct
        # via apply_passive_skill_stats() - they are NOT calculated here to avoid double-counting
        final_mult = 1 + self.char.final_damage_pct / 100

        # Mortal Blow - FD with uptime calculation (kept inline due to variable uptime)
        mb_fd = self.get_skill_bonus_value("mortal_blow", "final_damage")
        if mb_fd > 0:
            mb_uptime = self.calculate_mortal_blow_uptime(attack_speed_mult)
            final_mult *= (1 + (mb_fd * mb_uptime) / 100)

        # Skill-specific final damage from SKILL_ENHANCER skills
        # These apply FD only to specific skills, not globally
        if skill_name == "final_attack":
            afa_fd = self.get_skill_bonus_value("advanced_final_attack", "final_attack")
            afa_fd += self.get_mastery_bonus("final_attack", "skill_final_damage")
            if afa_fd > 0:
                final_mult *= (1 + afa_fd / 100)

        if skill_name == "flash_mirage":
            fm2_fd = self.get_skill_bonus_value("flash_mirage_2", "flash_mirage")
            fm2_fd += self.get_mastery_bonus("flash_mirage", "skill_final_damage")
            if fm2_fd > 0:
                final_mult *= (1 + fm2_fd / 100)

        if skill_name == "quiver_cartridge":
            # Enchanted Quiver grants FD to Quiver Cartridge
            # The Drain mastery additional damage is already added in get_skill_damage_pct
            # so the EQ FD multiplies both base QC damage AND drain damage
            eq_fd = self.get_skill_bonus_value("enchanted_quiver", "quiver_cartridge")
            if eq_fd > 0:
                final_mult *= (1 + eq_fd / 100)

        # Maple Hero (skill-specific FD for certain skills)
        # Formula: floor(base + per_level * level)
        if self.char.is_skill_unlocked("maple_hero"):
            mh_skill = self._skills["maple_hero"]
            if mh_skill.skill_bonuses and skill_name in mh_skill.skill_bonuses:
                mh_level = self.char.get_effective_skill_level("maple_hero")
                mh_base, mh_per_level = mh_skill.skill_bonuses[skill_name]
                mh_fd = int(mh_base + mh_per_level * mh_level)  # Always rounds down
                final_mult *= (1 + mh_fd / 100)

        # Crit calculation
        crit_rate_bonus = self.get_total_stat_bonus("crit_rate")
        crit_dmg_bonus = 0.0

        # Add bonuses from active buffs (e.g., Sharp Eyes)
        if active_buffs:
            buff_bonuses = self.get_buff_stat_bonuses(active_buffs)
            for cr_value in buff_bonuses.get("crit_rate", []):
                crit_rate_bonus += cr_value
            for cd_value in buff_bonuses.get("crit_damage", []):
                crit_dmg_bonus += cd_value

        crit_rate = min((self.char.crit_rate + crit_rate_bonus) / 100, 1.0)

        # Concentration (crit damage stacks) - PASSIVE_BUFF so not in char stats
        # 7 stacks, ~100% uptime (TODO: implement precise uptime calculation)
        conc_per_stack = self.get_skill_bonus_value("concentration", "crit_damage")
        crit_dmg_bonus += conc_per_stack * 7

        crit_damage = self.char.crit_damage + crit_dmg_bonus
        crit_mult = 1 + crit_rate * (crit_damage / 100)

        # Defense penetration
        # Note: armor_break defense_pen is a PASSIVE_STAT, so it should be in
        # char.defense_pen via apply_passive_skill_stats() - not added here
        def_pen = self.char.defense_pen
        # Defense multiplier: 1 / (1 + enemy_def * (1 - def_pen))
        def_pen_decimal = min(def_pen / 100, 1.0)  # Cap at 100%
        def_pen_mult = 1 / (1 + self.enemy_def * (1 - def_pen_decimal))

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
            cast_time = self.get_cast_time(1.0, ba_skill.scales_with_attack_speed, attack_speed_mult)

            dmg_mob = self.calculate_hit_damage(
                self.get_skill_damage_pct(ba_name),
                ba_skill.damage_type,
                ba_name,
                is_boss_phase=False,
                active_buffs=active_buffs,
            )
            dmg_boss = self.calculate_hit_damage(
                self.get_skill_damage_pct(ba_name),
                ba_skill.damage_type,
                ba_name,
                is_boss_phase=True,
                active_buffs=active_buffs,
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

        # Active skills - find all ACTIVE type skills dynamically
        for skill_name, skill in self._skills.items():
            if skill.skill_type != SkillType.ACTIVE:
                continue
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
                skill_cast_time = self.get_cast_time(1.0, skill.scales_with_attack_speed, attack_speed_mult)

            dmg_mob = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=False,
                active_buffs=active_buffs,
            )
            dmg_boss = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=True,
                active_buffs=active_buffs,
            )

            # Get effective cooldown with hat reduction
            effective_cd = self.char.get_effective_skill_cooldown(skill.cooldown, 0)

            damage_mob = dmg_mob * hits * targets_mob
            damage_boss = dmg_boss * hits * 1  # Single target during boss

            values[skill_name] = SkillActionValue(
                skill_name=skill_name,
                damage_per_use_mob=damage_mob,
                damage_per_use_boss=damage_boss,
                cast_time=skill_cast_time,
                cooldown=effective_cd,
                dps_value_mob=damage_mob / skill_cast_time,
                dps_value_boss=damage_boss / skill_cast_time,
            )

        # Summons - calculate total damage over duration for all SUMMON type skills
        for skill_name, skill in self._skills.items():
            if skill.skill_type != SkillType.SUMMON:
                continue
            if not self.char.is_skill_unlocked(skill_name):
                continue
            if skill.duration <= 0 or skill.attack_interval <= 0:
                continue

            # Cast time is ~1 second for summons
            cast_time = self.get_cast_time(1.0, skill.scales_with_attack_speed, attack_speed_mult)

            # Calculate damage per hit
            dmg_mob = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=False,
            )
            dmg_boss = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=True,
            )

            # Calculate attack interval (with mastery reduction if any)
            interval = skill.attack_interval
            interval_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval")
            if interval_reduction != 0:
                interval = max(1.0, interval + interval_reduction)  # Flat second reduction (min 1s)

            # Number of attacks over the summon's duration
            num_attacks = int(skill.duration / interval)
            targets_mob = min(self.get_skill_targets(skill_name), num_enemies)
            targets_boss = 1

            # Total damage over the summon's entire duration
            total_dmg_mob = dmg_mob * num_attacks * targets_mob
            total_dmg_boss = dmg_boss * num_attacks * targets_boss

            # Get effective cooldown (with mastery reduction)
            mastery_cd_reduction_pct = self.get_mastery_bonus(skill_name, "skill_cooldown_reduction") * 100
            effective_cd = self.char.get_effective_skill_cooldown(skill.cooldown, mastery_cd_reduction_pct)

            values[skill_name] = SkillActionValue(
                skill_name=skill_name,
                damage_per_use_mob=total_dmg_mob,
                damage_per_use_boss=total_dmg_boss,
                cast_time=cast_time,
                cooldown=effective_cd,
                dps_value_mob=total_dmg_mob / cast_time,
                dps_value_boss=total_dmg_boss / cast_time,
            )

        # Note: BUFF skills (Nimble Feet, Sharp Eyes) are handled via get_buff_stat_bonuses()
        # Their stat bonuses are weighted by uptime and included in attack_speed_mult, crit_rate, etc.
        # They don't need SkillActionValue entries since their benefit is baked into the stats.

        return values

    def _get_available_buffs(self) -> Dict[str, SkillData]:
        """Get all unlocked BUFF skills that can be cast."""
        buffs = {}
        for skill_name, skill in self._skills.items():
            if skill.skill_type != SkillType.BUFF:
                continue
            if not self.char.is_skill_unlocked(skill_name):
                continue
            if not skill.skill_bonuses or skill.duration <= 0:
                continue
            buffs[skill_name] = skill
        return buffs

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
        Calculate the DPS value of casting a buff now.

        Compares two scenarios over the buff duration window:
        - Option A: Attack continuously without buff
        - Option B: Cast buff then attack with buff active

        Returns an "equivalent DPS" value that can be compared with
        damage skill DPS to decide whether to cast the buff.

        Args:
            skill_values_getter: Optional cached function to get skill values.
                                If provided, uses cache. Otherwise calls _precalculate_skill_values directly.
        """
        # Time buff would be active (capped by remaining fight time)
        active_time = min(buff_skill.duration, remaining_fight_time)
        if active_time <= 0:
            return 0.0

        # Cast time for buff (buffs don't scale with attack speed)
        cast_time = self.get_cast_time(1.0, False, current_attack_speed_mult)

        # Not enough time to even cast the buff
        if cast_time >= active_time:
            return 0.0

        # Get basic attack name
        ba_name = self.char.get_active_basic_attack()
        if not ba_name:
            return 0.0

        # Calculate DPS with this buff active
        new_buffs = current_active_buffs | {buff_name}
        new_attack_speed_mult = self.calculate_attack_speed_mult(new_buffs)

        # Use cached getter if provided, otherwise call _precalculate_skill_values directly
        if skill_values_getter is not None:
            new_skill_values = skill_values_getter(new_attack_speed_mult, new_buffs)
        else:
            new_skill_values = self._precalculate_skill_values(num_enemies, new_attack_speed_mult, new_buffs)

        new_dps = new_skill_values[ba_name].dps_value_boss if is_boss else new_skill_values[ba_name].dps_value_mob

        # Option B: Cast buff (lose cast_time) then attack with buff
        attack_time_with_buff = active_time - cast_time
        damage_with_buff = new_dps * attack_time_with_buff

        # If buff is worth it, calculate equivalent DPS
        # The "equivalent DPS" is what DPS value would make Option B equal Option A
        # Buff is worth it if: new_dps * (active_time - cast_time) > current_dps * active_time
        #
        # For comparison, we return an "effective DPS" that represents the average
        # DPS over the active_time window when casting the buff:
        # effective_dps = damage_with_buff / active_time
        effective_dps = damage_with_buff / active_time

        return effective_dps

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

            # Recalculate if buffs changed
            if buffs_changed:
                current_attack_speed_mult = self.calculate_attack_speed_mult(current_active_buffs)
                skill_values = get_cached_skill_values(current_attack_speed_mult, current_active_buffs)

            # Find best available damage action
            best_action = None
            best_dps_value = -1.0
            available_options = []

            for name, sv in skill_values.items():
                if cooldowns[name] > 0:
                    continue  # On cooldown

                dps_value = sv.dps_value_boss if is_boss else sv.dps_value_mob
                available_options.append((name, dps_value))
                if dps_value > best_dps_value:
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

            # Decide: cast buff or use damage skill
            cast_buff = best_buff_name is not None and best_buff_value > best_dps_value

            if cast_buff and best_buff_name is not None:
                # Cast the buff
                buff_skill = available_buffs[best_buff_name]
                cast_time = self.get_cast_time(1.0, False, current_attack_speed_mult)

                # Handle partial execution at fight end
                if cast_time > remaining_fight_time:
                    time_used = remaining_fight_time
                else:
                    time_used = cast_time
                    # Activate buff
                    # Apply duration mastery bonus
                    buff_duration = buff_skill.duration
                    duration_bonus_pct = self.get_mastery_bonus(best_buff_name, "skill_duration")
                    if duration_bonus_pct > 0:
                        buff_duration = buff_duration * (1 + duration_bonus_pct)
                    buff_timers[best_buff_name] = buff_duration
                    current_active_buffs.add(best_buff_name)

                    # Get effective cooldown (check for mastery reductions)
                    mastery_cd_reduction = self.get_mastery_bonus(best_buff_name, "skill_cooldown_reduction") * 100
                    buff_cooldowns[best_buff_name] = self.char.get_effective_skill_cooldown(
                        buff_skill.cooldown, mastery_cd_reduction
                    )

                    # Recalculate attack speed and damage with new buff
                    current_attack_speed_mult = self.calculate_attack_speed_mult(current_active_buffs)
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
                all_cooldowns = list(cooldowns.values()) + list(buff_cooldowns.values())
                positive_cds = [cd for cd in all_cooldowns if cd > 0]
                if not positive_cds:
                    break  # Safety: avoid infinite loop
                min_cd = min(positive_cds)
                time_used = min_cd

            # Advance time and decrement all cooldowns
            for name in cooldowns:
                cooldowns[name] = max(0, cooldowns[name] - time_used)
            for name in buff_cooldowns:
                buff_cooldowns[name] = max(0, buff_cooldowns[name] - time_used)
            for name in buff_timers:
                buff_timers[name] = max(0, buff_timers[name] - time_used)
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
        from cooldown_calc import calculate_buff_uptime

        total_summon_dps = 0.0
        total_mob_dps = 0.0
        total_boss_dps = 0.0

        # Find all SUMMON type skills dynamically
        for skill_name, skill in self._skills.items():
            if skill.skill_type != SkillType.SUMMON:
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
            )
            dmg_boss = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=True,
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
            interval_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval")
            if interval_reduction != 0:
                interval = max(1.0, interval + interval_reduction)  # Flat second reduction
            # Some summons scale with attack speed (e.g., quiver_cartridge)
            if skill.scales_with_attack_speed:
                as_mult = min(attack_speed_mult, 2.0)
                interval = interval / as_mult

            attacks_per_second = 1 / interval

            # Calculate targets for each phase
            targets_mob = min(self.get_skill_targets(skill_name), num_enemies)
            targets_boss = 1

            # Weight by phase duration
            mob_dps = dmg_mob * targets_mob * attacks_per_second * uptime * mob_time_fraction
            boss_dps = dmg_boss * targets_boss * attacks_per_second * uptime * (1 - mob_time_fraction)

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
        cast_time = self.get_cast_time(1.0, True, attack_speed_mult)

        # Find all PASSIVE_PROC type skills dynamically
        for skill_name, skill in self._skills.items():
            if skill.skill_type != SkillType.PASSIVE_PROC:
                continue
            if not self.char.is_skill_unlocked(skill_name):
                continue

            # Calculate damage for each phase
            dmg_mob = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=False,
            )
            dmg_boss = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=True,
            )

            # Calculate targets for each phase
            targets_mob = min(self.get_skill_targets(skill_name), num_enemies)
            targets_boss = 1

            # Check for marking-style procs (like Mark of Assassin)
            if skill.attack_interval > 0:
                # Apply mastery interval reduction
                interval = skill.attack_interval
                interval_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval")
                if interval_reduction != 0:
                    interval = max(1.0, interval + interval_reduction)  # Flat second reduction

                # Marks don't stack - rate limited by marking interval
                # Each mark = 1 hit on 1 target when consumed
                marks_per_interval_mob = min(skill.base_targets, num_enemies)
                procs_per_second_mob = marks_per_interval_mob / interval
                procs_per_second_boss = 1 / interval  # Only 1 target for boss

                # For marking procs, each proc is 1 hit - don't multiply by targets
                mob_dps = dmg_mob * 1 * procs_per_second_mob * mob_time_fraction
                boss_dps = dmg_boss * 1 * procs_per_second_boss * (1 - mob_time_fraction)
            else:
                # Standard proc calculation
                proc_chance = skill.proc_chance
                if skill.scales_with_attack_speed:
                    proc_chance = min(proc_chance * attack_speed_mult, proc_chance * 2)

                # Account for internal cooldown
                if skill.cooldown > 0:
                    mastery_pct_reduction = self.get_mastery_bonus(skill_name, "skill_cooldown_reduction") * 100
                    effective_cd = self.char.get_effective_skill_cooldown(skill.cooldown, mastery_pct_reduction)
                    procs_per_second = min(1 / cast_time * proc_chance, 1 / effective_cd)
                else:
                    procs_per_second = 1 / cast_time * proc_chance

                # Standard procs can hit multiple targets
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
        from cooldown_calc import calculate_triggers, calculate_buff_uptime

        # Collect all skill stat bonuses and calculate attack speed
        skill_bonuses = self.get_all_skill_stat_bonuses()
        attack_speed_pct = self.char.attack_speed_pct
        for as_value in skill_bonuses.get("attack_speed", []):
            attack_speed_pct += as_value
        attack_speed_pct += self.get_global_stat("attack_speed")
        attack_speed_mult = min(1 + attack_speed_pct / 100, 2.5)

        cast_time = self.get_cast_time(1.0, True, attack_speed_mult)
        rotation_length = fight_duration

        basic_dps = 0
        active_dps = 0
        summon_dps = 0
        proc_dps = 0
        skills_used = []

        # Basic attack (current tier)
        basic_skill_name = self.char.get_active_basic_attack()
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
        for skill_name, skill in self._skills.items():
            if skill.skill_type != SkillType.ACTIVE:
                continue
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
                # Default: 1 second base cast time for instant-cast skills
                skill_cast_time = self.get_cast_time(1.0, skill.scales_with_attack_speed, attack_speed_mult)

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

                # Handle infinite fight duration (steady state DPS)
                if math.isinf(rotation_length):
                    # Steady state: DPS = damage_per_use / cooldown
                    damage_per_use = damage * hits * effective_targets
                    active_dps += damage_per_use / effective_cd
                    # Time ratio for basic attack: skill_cast_time / cooldown
                    active_skill_time_used += skill_cast_time / effective_cd
                else:
                    time_per_rotation = skill_cast_time * triggers
                    active_skill_time_used += time_per_rotation
                    total_damage = damage * hits * effective_targets * triggers
                    active_dps += total_damage / rotation_length
                skills_used.append(skill_name)

        # Adjust basic DPS for time spent on actives
        if math.isinf(rotation_length):
            # At infinite duration, use fraction of time spent on actives
            basic_time_ratio = max(0, 1.0 - active_skill_time_used)
        else:
            basic_time_ratio = max(0, rotation_length - active_skill_time_used) / rotation_length
        basic_dps *= basic_time_ratio

        # Summons - find all SUMMON type skills dynamically
        for skill_name, skill in self._skills.items():
            if skill.skill_type != SkillType.SUMMON:
                continue
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
                interval_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval")
                if interval_reduction != 0:
                    interval = max(1.0, interval + interval_reduction)  # Flat second reduction
                if skill.scales_with_attack_speed:
                    as_mult = min(attack_speed_mult, 2.0)
                    interval = interval / as_mult

                attacks_per_second = 1 / interval
                effective_targets = self.get_effective_targets(skill_name, num_enemies, mob_time_fraction)
                summon_dps += damage * effective_targets * attacks_per_second * uptime
                skills_used.append(skill_name)

        # Procs - find all PASSIVE_PROC type skills dynamically
        for skill_name, skill in self._skills.items():
            if skill.skill_type != SkillType.PASSIVE_PROC:
                continue
            if not self.char.is_skill_unlocked(skill_name):
                continue
            damage = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
            )

            # Check for marking-style procs (like Mark of Assassin)
            if skill.attack_interval > 0:
                # Apply mastery interval reduction
                interval = skill.attack_interval
                interval_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval")
                if interval_reduction != 0:
                    interval = max(1.0, interval + interval_reduction)  # Flat second reduction

                # Marks don't stack - rate limited by marking interval
                # Each mark = 1 hit on 1 target when consumed
                marks_per_interval_mob = min(skill.base_targets, num_enemies)
                procs_per_second_mob = marks_per_interval_mob / interval
                procs_per_second_boss = 1 / interval  # Only 1 target for boss

                # Weighted DPS across phases - don't multiply by targets (already in proc rate)
                mob_dps = damage * 1 * procs_per_second_mob * mob_time_fraction
                boss_dps = damage * 1 * procs_per_second_boss * (1 - mob_time_fraction)
                proc_dps += mob_dps + boss_dps
            else:
                # Standard proc calculation
                effective_targets = self.get_effective_targets(skill_name, num_enemies, mob_time_fraction)

                proc_chance = skill.proc_chance
                if skill.scales_with_attack_speed:
                    proc_chance = min(proc_chance * attack_speed_mult, proc_chance * 2)

                # Account for internal cooldown
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
        # Collect all skill stat bonuses and calculate attack speed
        skill_bonuses = self.get_all_skill_stat_bonuses()
        attack_speed_pct = self.char.attack_speed_pct
        for as_value in skill_bonuses.get("attack_speed", []):
            attack_speed_pct += as_value
        attack_speed_pct += self.get_global_stat("attack_speed")
        attack_speed_mult = min(1 + attack_speed_pct / 100, 2.5)

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

        # Add summons and procs to skills list dynamically
        for skill_name, skill in self._skills.items():
            if skill.skill_type in (SkillType.SUMMON, SkillType.PASSIVE_PROC):
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
        # Calculate attack speed multiplier
        skill_bonuses = self.get_all_skill_stat_bonuses()
        attack_speed_pct = self.char.attack_speed_pct
        for as_value in skill_bonuses.get("attack_speed", []):
            attack_speed_pct += as_value
        attack_speed_pct += self.get_global_stat("attack_speed")
        attack_speed_mult = min(1 + attack_speed_pct / 100, 2.5)

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

        # Add permanent summons (not in fight simulation) - find dynamically based on job class
        # Permanent summons have infinite duration (duration > 0) and attack_interval > 0
        for skill_name, skill in self._skills.items():
            if skill.skill_type != SkillType.SUMMON:
                continue
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
            )
            dmg_boss = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=True,
            )

            # Attack interval scales with AS up to 2x
            as_mult = min(attack_speed_mult, 2.0)
            interval = skill.attack_interval / as_mult
            attacks_per_second = 1 / interval
            targets_mob = min(self.get_skill_targets(skill_name), num_enemies)

            # Calculate phase damage (permanent uptime)
            mob_damage = dmg_mob * targets_mob * attacks_per_second * fight_duration * mob_time_fraction
            boss_damage = dmg_boss * 1 * attacks_per_second * fight_duration * (1 - mob_time_fraction)
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
        for skill_name, skill in self._skills.items():
            if skill.skill_type != SkillType.PASSIVE_PROC:
                continue
            if not self.char.is_skill_unlocked(skill_name):
                continue

            # Calculate proc's contribution
            dmg_mob = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=False,
            )
            dmg_boss = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
                is_boss_phase=True,
            )

            targets_mob = min(self.get_skill_targets(skill_name), num_enemies)
            targets_boss = 1

            # Check for marking-style procs (like Mark of Assassin)
            # attack_interval > 0 means marks are applied at fixed intervals, not per attack
            if skill.attack_interval > 0:
                # Apply mastery interval reduction
                interval = skill.attack_interval
                interval_reduction = self.get_mastery_bonus(skill_name, "skill_attack_interval")
                if interval_reduction != 0:
                    interval = max(1.0, interval + interval_reduction)  # Flat second reduction (min 1s)

                # Marks don't stack - can only consume marks as fast as they're applied
                # Each mark = 1 hit on 1 target when consumed
                # Mob phase: mark up to (base_targets) enemies per interval
                marks_per_interval_mob = min(skill.base_targets, num_enemies)
                procs_per_second_mob = marks_per_interval_mob / interval

                # Boss phase: only 1 target, so only 1 mark per interval
                procs_per_second_boss = 1 / interval

                # For marking procs, each proc is 1 hit - don't multiply by targets again
                # (the proc rate already accounts for number of marks/targets)
                mob_damage = dmg_mob * 1 * procs_per_second_mob * fight_duration * mob_time_fraction
                boss_damage = dmg_boss * 1 * procs_per_second_boss * fight_duration * (1 - mob_time_fraction)
            else:
                # Standard proc calculation based on attack rate
                ba_name = self.char.get_active_basic_attack()
                if ba_name:
                    cast_time = self.get_cast_time(1.0, True, attack_speed_mult)
                    attacks_per_second = 1 / cast_time
                else:
                    attacks_per_second = 2.0

                proc_chance = skill.proc_chance
                if skill.scales_with_attack_speed:
                    proc_chance = min(proc_chance * attack_speed_mult, proc_chance * 2)

                # Effective procs per second (account for ICD if present)
                if skill.cooldown > 0:
                    # Has internal cooldown - max procs limited by ICD
                    mastery_cd_reduction_pct = self.get_mastery_bonus(skill_name, "skill_cooldown_reduction")
                    effective_cd = skill.cooldown * (1 - mastery_cd_reduction_pct)
                    procs_per_second = min(attacks_per_second * proc_chance, 1 / effective_cd)
                else:
                    procs_per_second = attacks_per_second * proc_chance

                # Standard procs hit multiple targets
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
        baseline_normal_mult = 1 + self.char.normal_damage_pct / 100
        baseline_boss_mult = 1 + self.char.boss_damage_pct / 100

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
        def_pen = self.char.defense_pen
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
        defense_pen = new_defense_pen if new_defense_pen is not None else self.char.defense_pen

        # Calculate new universal multiplier
        base_main_stat = main_stat_flat + self.get_global_stat("main_stat_flat")
        total_main_stat = base_main_stat * (1 + (main_stat_pct + self.get_total_stat_bonus("main_stat_pct")) / 100)
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
        new_normal = new_normal_damage_pct if new_normal_damage_pct is not None else self.char.normal_damage_pct
        new_boss = new_boss_damage_pct if new_boss_damage_pct is not None else self.char.boss_damage_pct

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
        for skill_name, skill in self._skills.items():
            if skill.skill_type != SkillType.SKILL_ENHANCER:
                continue
            if not self.char.is_skill_unlocked(skill_name):
                continue
            if not skill.skill_bonuses:
                continue

            level = self.char.get_effective_skill_level(skill_name)

            for target_skill, (base, per_level) in skill.skill_bonuses.items():
                # Check if target skill exists
                if target_skill not in self._skills:
                    continue

                value = int(base + per_level * level)

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
    char.boss_damage_pct = 20
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
        boss_damage_pct=20, crit_rate=70, crit_damage=200,
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
            boss_damage_pct=20, crit_rate=70, crit_damage=200,
            attack_speed_pct=50,
        )
        print(f"  Level {test_level}: +1 All Skills = +{inc:.4f}% DPS")
