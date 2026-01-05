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
from typing import Dict, List, Optional, Tuple
import math


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


class DamageType(Enum):
    BASIC = "basic"      # Scales with Basic Attack Damage %
    SKILL = "skill"      # Scales with Skill Damage %


class Job(Enum):
    FIRST = 1    # Level 1-29
    SECOND = 2   # Level 30-59
    THIRD = 3    # Level 60-99 (skill points 60-99)
    FOURTH = 4   # Level 100+ (skill points 100+)


# Job advancement levels
JOB_LEVEL_RANGES = {
    Job.FIRST: (1, 29),
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

    # For passive stat skills
    stat_type: str = ""             # "crit_rate", "attack_speed", etc.
    base_stat_value: float = 0      # Value at level 1
    stat_per_level: float = 0       # Additional value per level


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
    MasteryNode("Flash Mirage II - Enhance & Target", 138, 16500, "skill_final_damage_and_targets", "flash_mirage", 50, "Flash Mirage II Final Damage +50%, targets +3"),

    # Skill-specific: Sharp Eyes
    MasteryNode("Sharp Eyes - Persistence", 126, 14250, "skill_duration", "sharp_eyes", 0.5, "Sharp Eyes duration +50%"),

    # Skill-specific: Illusion Step
    MasteryNode("Illusion Step - Enhance", 118, 12750, "skill_effect", "illusion_step", 2, "Attack increase effect doubled"),

    # Skill-specific: Enchanted Quiver
    MasteryNode("Enchanted Quiver - Drain", 130, 15000, "skill_effect", "enchanted_quiver", 1, "Quiver heals 1% HP on hit"),
]


def get_unlocked_masteries(level: int) -> List[MasteryNode]:
    """Get all masteries unlocked at the given level."""
    return [m for m in BOWMASTER_MASTERIES if m.unlock_level <= level]


def get_mastery_bonuses(level: int) -> Dict[str, Dict[str, float]]:
    """
    Calculate total mastery bonuses at a given level.

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

    for mastery in get_unlocked_masteries(level):
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
        unlock_level=1,
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
        stat_type="crit_rate",
        base_stat_value=5.0,
        stat_per_level=0.0146,  # (6.5 - 5) / 103
    ),

    "archer_mastery": SkillData(
        name="Archer Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FIRST,
        unlock_level=10,
        stat_type="attack_speed",
        base_stat_value=5.0,
        stat_per_level=0.0146,
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
        stat_type="attack_speed",
        base_stat_value=5.0,
        stat_per_level=0.0148,  # (7.2 - 5) / 149
    ),

    "bow_mastery": SkillData(
        name="Bow Mastery",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=43,
        stat_type="min_dmg_mult",
        base_stat_value=15.0,
        stat_per_level=0.045,  # (21.7 - 15) / 149
    ),

    "soul_arrow": SkillData(
        name="Soul Arrow: Bow",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.SECOND,
        unlock_level=45,
        stat_type="dex_flat",
        base_stat_value=50.0,
        stat_per_level=0.67,  # Scales up to 150 with AS
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
        stat_type="basic_attack_damage",
        base_stat_value=10.0,
        stat_per_level=0.030,  # (14.5 - 10) / 149
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
    ),

    "extreme_archery": SkillData(
        name="Extreme Archery: Bow",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=75,
        stat_type="final_damage",
        base_stat_value=15.0,
        stat_per_level=0.045,  # (23.6 - 15) / 191
    ),

    "mortal_blow": SkillData(
        name="Mortal Blow",
        skill_type=SkillType.PASSIVE_BUFF,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=72,
        stat_type="final_damage",
        base_stat_value=10.0,
        stat_per_level=0.030,  # (15.7 - 10) / 191
    ),

    "concentration": SkillData(
        name="Concentration",
        skill_type=SkillType.PASSIVE_BUFF,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=66,
        stat_type="crit_damage",
        base_stat_value=3.0,  # Per stack, 7 stacks max
        stat_per_level=0.0089,  # (4.7 - 3) / 191
    ),

    "marksmanship": SkillData(
        name="Marksmanship",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.THIRD,
        unlock_level=74,
        stat_type="attack_pct",
        base_stat_value=20.0,
        stat_per_level=0.060,  # (31.5 - 20) / 191
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
        # Buff values handled separately
    ),

    "enchanted_quiver": SkillData(
        name="Enchanted Quiver",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=107,
        stat_type="quiver_final_damage",
        base_stat_value=500.0,  # +500% FD to Quiver
        stat_per_level=2.05,  # (590 - 500) / 44
    ),

    "flash_mirage_2": SkillData(
        name="Flash Mirage II",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=110,
        stat_type="flash_mirage_final_damage",
        base_stat_value=400.0,  # +400% FD to Flash Mirage
        stat_per_level=1.64,  # (472 - 400) / 44
    ),

    "illusion_step": SkillData(
        name="Illusion Step",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=117,
        stat_type="attack_pct",
        base_stat_value=10.0,
        stat_per_level=0.030,  # (11.3 - 10) / 44
    ),

    "advanced_final_attack": SkillData(
        name="Advanced Final Attack",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=105,
        stat_type="final_attack_final_damage",
        base_stat_value=500.0,  # +500% FD to Final Attack
        stat_per_level=2.05,  # (590 - 500) / 44
    ),

    "bow_expert": SkillData(
        name="Bow Expert",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=120,
        stat_type="skill_damage",
        base_stat_value=15.0,
        stat_per_level=0.045,  # (17 - 15) / 44
    ),

    "armor_break": SkillData(
        name="Armor Break",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=125,
        stat_type="defense_pen_and_final_damage",
        base_stat_value=10.0,  # Both def pen and FD
        stat_per_level=0.030,  # (11.3 - 10) / 44
    ),

    "maple_hero": SkillData(
        name="Maple Hero",
        skill_type=SkillType.PASSIVE_STAT,
        damage_type=DamageType.SKILL,
        job=Job.FOURTH,
        unlock_level=100,
        stat_type="skill_specific_final_damage",
        # Arrow Platter +25%, Phoenix +30%, Covering Fire +100% at level 1
        # Your level shows: Arrow Platter 81.2%, Phoenix 97.5%, Covering Fire 325%
        base_stat_value=25.0,  # Base for Arrow Platter
        stat_per_level=1.28,  # (81.2 - 25) / 44
    ),
}


# =============================================================================
# CHARACTER STATE
# =============================================================================

@dataclass
class CharacterState:
    """Complete state of a Bowmaster character."""
    level: int = 100

    # Skill levels (base level, before +All Skills)
    skill_levels: Dict[str, int] = field(default_factory=dict)

    # +All Skills bonus from potentials
    all_skills_bonus: int = 0

    # Equipment stats
    attack: float = 1000
    main_stat_flat: float = 0  # Flat DEX/main stat
    main_stat_pct: float = 0   # DEX%/main stat %
    damage_pct: float = 0
    boss_damage_pct: float = 0
    crit_rate: float = 50.0
    crit_damage: float = 150.0
    min_dmg_mult: float = 0
    max_dmg_mult: float = 0
    skill_damage_pct: float = 0
    basic_attack_dmg_pct: float = 0
    final_damage_pct: float = 0
    defense_pen: float = 0
    attack_speed_pct: float = 0

    # Skill cooldown reduction from hat special potential (flat seconds)
    skill_cd_reduction: float = 0.0

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
        """Get effective skill level including +All Skills bonus."""
        base = self.skill_levels.get(skill_name, 1)
        return base + self.all_skills_bonus

    def get_current_job(self) -> Job:
        """Get current job advancement."""
        return get_job_for_level(self.level)

    def is_skill_unlocked(self, skill_name: str) -> bool:
        """Check if a skill is unlocked at current level."""
        if skill_name not in BOWMASTER_SKILLS:
            return False
        return self.level >= BOWMASTER_SKILLS[skill_name].unlock_level

    def get_active_basic_attack(self) -> str:
        """Get the highest tier basic attack available."""
        if self.level >= 100:
            return "arrow_stream"
        elif self.level >= 60:
            return "wind_arrow_2"
        elif self.level >= 30:
            return "wind_arrow"
        else:
            return "arrow_blow"


def create_character_at_level(level: int, all_skills_bonus: int = 0) -> CharacterState:
    """
    Create a character state at the given level with default skill distribution.

    Assumes:
    - 3 skill points per level into current job skills
    - Skills are leveled somewhat evenly
    """
    char = CharacterState(level=level, all_skills_bonus=all_skills_bonus)

    # Set skill levels based on available skill points
    # This is a simplified model - in practice players optimize differently

    for skill_name, skill_data in BOWMASTER_SKILLS.items():
        if level >= skill_data.unlock_level:
            # Skill is unlocked, calculate approximate level
            # Simplified: assume base level 1 for now, since +All Skills is the focus
            char.skill_levels[skill_name] = 1

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


class DPSCalculator:
    """
    Calculates DPS for Bowmaster given character state.

    Now includes:
    - Mastery bonuses
    - Level-appropriate skills
    - Proper skill unlocking
    """

    def __init__(self, char: CharacterState):
        self.char = char
        self.mastery_bonuses = get_mastery_bonuses(char.level)

    def get_mastery_bonus(self, skill_name: str, effect_type: str) -> float:
        """Get total mastery bonus for a skill and effect type."""
        total = 0

        # Check skill-specific bonuses
        if skill_name in self.mastery_bonuses:
            total += self.mastery_bonuses[skill_name].get(effect_type, 0)

        # Note: Global bonuses are applied separately via get_global_stat()
        # This method is for skill-specific mastery bonuses only

        return total

    def get_global_stat(self, stat_type: str) -> float:
        """Get global stat bonus from masteries (applies to character, not specific skills)."""
        if "global" in self.mastery_bonuses:
            return self.mastery_bonuses["global"].get(stat_type, 0)
        return 0

    def get_effective_attack_speed(self) -> float:
        """Get attack speed multiplier (capped at 2.5x = 150% bonus)."""
        # Base attack speed from equipment/character
        total_as = self.char.attack_speed_pct

        # Add from passive skills (these scale with +All Skills)
        for skill_name in ["archer_mastery", "bow_acceleration"]:
            if self.char.is_skill_unlocked(skill_name):
                skill = BOWMASTER_SKILLS[skill_name]
                level = self.char.get_effective_skill_level(skill_name)
                total_as += skill.base_stat_value + skill.stat_per_level * (level - 1)

        # Add global mastery bonus (fixed, doesn't scale with +All Skills)
        total_as += self.get_global_stat("attack_speed")

        return min(1 + total_as / 100, 2.5)

    def get_cast_time(self, base_time: float = 1.0, scales_with_as: bool = True) -> float:
        """Calculate actual cast time with attack speed."""
        if not scales_with_as:
            return base_time
        return base_time / self.get_effective_attack_speed()

    def calculate_mortal_blow_uptime(self) -> float:
        """
        Calculate Mortal Blow uptime based on hit rate.

        Mortal Blow activates after 50 hits, lasts 5 sec (+ 5 sec with mastery = 10 sec).
        Hit sources that COUNT:
        - Arrow Stream/basic attacks (5 hits per attack)
        - Phoenix (1 hit per attack)
        - Final Attack procs (1 hit)
        - Flash Mirage procs (1 hit)
        - Covering Fire (3 hits)

        Hit sources that DON'T count:
        - Arrow Platter
        - Quiver Cartridge
        """
        if not self.char.is_skill_unlocked("mortal_blow"):
            return 0.0

        # Get attack speed multiplier
        cast_time = self.get_cast_time(1.0, True)

        # Calculate hits per second from each source
        hits_per_second = 0.0

        # Basic attack (Arrow Stream at 100+, Wind Arrow II at 60+, etc.)
        basic_skill_name = self.char.get_active_basic_attack()
        if basic_skill_name and self.char.is_skill_unlocked(basic_skill_name):
            basic_hits = self.get_skill_hits(basic_skill_name)
            attacks_per_second = 1 / cast_time
            hits_per_second += basic_hits * attacks_per_second

        # Phoenix (attacks every 3 seconds, 1 hit, independent of AS)
        if self.char.is_skill_unlocked("phoenix"):
            phoenix_interval = 3.0
            # Check for mastery reducing interval by 30%
            if self.char.level >= 82:
                phoenix_interval *= 0.7
            # Phoenix uptime (20s duration, 60s CD, or 30s with mastery reduction)
            phoenix_cd = 60.0
            mastery_pct_reduction = 50.0 if self.char.level >= 104 else 0.0
            phoenix_cd = self.char.get_effective_skill_cooldown(phoenix_cd, mastery_pct_reduction)
            phoenix_uptime = min(20.0 / phoenix_cd, 1.0)
            hits_per_second += (1 / phoenix_interval) * phoenix_uptime

        # Final Attack (25% proc chance per attack, 1 hit)
        if self.char.is_skill_unlocked("final_attack"):
            fa_skill = BOWMASTER_SKILLS["final_attack"]
            proc_chance = fa_skill.proc_chance  # 0.25
            attacks_per_second = 1 / cast_time
            hits_per_second += proc_chance * attacks_per_second

        # Flash Mirage (20% proc chance, 5s ICD, 1 hit)
        if self.char.is_skill_unlocked("flash_mirage"):
            fm_skill = BOWMASTER_SKILLS["flash_mirage"]
            # With ICD, max procs per second = 1 / cooldown
            fm_cd = fm_skill.cooldown  # 5.0
            mastery_pct_reduction = 40.0 if self.char.level >= 122 else 0.0
            fm_cd = self.char.get_effective_skill_cooldown(fm_cd, mastery_pct_reduction)
            hits_per_second += 1 / fm_cd

        # Covering Fire (3 hits, 19s CD)
        if self.char.is_skill_unlocked("covering_fire"):
            cf_skill = BOWMASTER_SKILLS["covering_fire"]
            cf_hits = cf_skill.base_hits  # 3
            cf_cd = self.char.get_effective_skill_cooldown(cf_skill.cooldown, 0)
            hits_per_second += cf_hits / cf_cd

        # Calculate build time to reach 50 hits
        hits_to_activate = 50
        build_time = hits_to_activate / hits_per_second if hits_per_second > 0 else 999

        # Duration: 5 sec base + 5 sec from mastery (level 90+) = 10 sec
        duration = 5.0
        if self.char.level >= 90:
            duration += 5.0

        # Uptime = duration / (duration + build_time)
        uptime = duration / (duration + build_time)

        return uptime

    def get_skill_damage_pct(self, skill_name: str) -> float:
        """Get total damage % for a skill including level scaling and masteries."""
        if skill_name not in BOWMASTER_SKILLS:
            return 0

        skill = BOWMASTER_SKILLS[skill_name]
        level = self.char.get_effective_skill_level(skill_name)

        # Base + level scaling
        damage = skill.base_damage_pct + skill.damage_per_level * (level - 1)

        # Add mastery damage bonus (additive to base)
        mastery_bonus = self.get_mastery_bonus(skill_name, "skill_damage_pct")
        # Mastery bonuses are often percentage increases on top
        damage *= (1 + mastery_bonus / 100)

        return damage

    def get_skill_hits(self, skill_name: str) -> int:
        """Get total hits for a skill including masteries."""
        if skill_name not in BOWMASTER_SKILLS:
            return 1

        skill = BOWMASTER_SKILLS[skill_name]
        hits = skill.base_hits

        # Add mastery hit bonuses
        hits += int(self.get_mastery_bonus(skill_name, "skill_hits"))

        # Hurricane special case
        if skill_name == "hurricane" and self.char.level >= 134:
            hits = 35  # Hurricane - Extend mastery

        return hits

    def get_skill_targets(self, skill_name: str) -> int:
        """Get total targets for a skill including masteries."""
        if skill_name not in BOWMASTER_SKILLS:
            return 1

        skill = BOWMASTER_SKILLS[skill_name]
        targets = skill.base_targets

        # Add mastery target bonuses
        targets += int(self.get_mastery_bonus(skill_name, "skill_targets"))

        return targets

    def get_total_stat_bonus(self, stat_type: str) -> float:
        """
        Get total bonus for a stat type from passive skills and global masteries.

        Passive skills: Scale with +All Skills
        Global masteries: Fixed bonuses, don't scale with +All Skills
        """
        total = 0

        # From passive stat skills (these SCALE with +All Skills)
        for skill_name, skill in BOWMASTER_SKILLS.items():
            if skill.skill_type == SkillType.PASSIVE_STAT and skill.stat_type == stat_type:
                if self.char.is_skill_unlocked(skill_name):
                    level = self.char.get_effective_skill_level(skill_name)
                    total += skill.base_stat_value + skill.stat_per_level * (level - 1)

        # From global masteries (FIXED, don't scale with +All Skills)
        total += self.get_global_stat(stat_type)

        return total

    def calculate_hit_damage(
        self,
        skill_damage_pct: float,
        damage_type: DamageType,
        skill_name: str = "",
    ) -> float:
        """Calculate damage for a single hit."""

        base = self.char.attack * (skill_damage_pct / 100)

        # Main stat - same formula as simple calculator
        # total_dex = flat * (1 + pct/100), then stat_mult = 1 + (total_dex / 10000)
        total_main_stat = self.char.main_stat_flat * (1 + (self.char.main_stat_pct + self.get_total_stat_bonus("main_stat_pct")) / 100)
        main_stat_mult = 1 + (total_main_stat / 10000)

        # Damage %
        damage_mult = 1 + (self.char.damage_pct + self.get_total_stat_bonus("damage_pct")) / 100

        # Boss damage (for single target boss)
        boss_dmg = self.char.boss_damage_pct
        boss_dmg += self.get_mastery_bonus(skill_name, "skill_boss_damage")
        boss_mult = 1 + boss_dmg / 100

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
        final_mult = 1 + self.char.final_damage_pct / 100

        # Extreme Archery
        if self.char.is_skill_unlocked("extreme_archery"):
            ea_level = self.char.get_effective_skill_level("extreme_archery")
            ea_skill = BOWMASTER_SKILLS["extreme_archery"]
            ea_fd = ea_skill.base_stat_value + ea_skill.stat_per_level * (ea_level - 1)
            final_mult *= (1 + ea_fd / 100)

        # Armor Break (both def pen and FD)
        if self.char.is_skill_unlocked("armor_break"):
            ab_level = self.char.get_effective_skill_level("armor_break")
            ab_skill = BOWMASTER_SKILLS["armor_break"]
            ab_val = ab_skill.base_stat_value + ab_skill.stat_per_level * (ab_level - 1)
            final_mult *= (1 + ab_val / 100)

        # Mortal Blow - calculate uptime based on hit rate
        if self.char.is_skill_unlocked("mortal_blow"):
            mb_level = self.char.get_effective_skill_level("mortal_blow")
            mb_skill = BOWMASTER_SKILLS["mortal_blow"]
            mb_fd = mb_skill.base_stat_value + mb_skill.stat_per_level * (mb_level - 1)

            # Calculate Mortal Blow uptime
            mb_uptime = self.calculate_mortal_blow_uptime()
            final_mult *= (1 + (mb_fd * mb_uptime) / 100)

        # Skill-specific final damage (Advanced Final Attack, Flash Mirage II, etc.)
        if skill_name == "final_attack" and self.char.is_skill_unlocked("advanced_final_attack"):
            afa_level = self.char.get_effective_skill_level("advanced_final_attack")
            afa_skill = BOWMASTER_SKILLS["advanced_final_attack"]
            afa_fd = afa_skill.base_stat_value + afa_skill.stat_per_level * (afa_level - 1)
            # Add mastery bonus
            afa_fd += self.get_mastery_bonus("final_attack", "skill_final_damage")
            final_mult *= (1 + afa_fd / 100)

        if skill_name == "flash_mirage" and self.char.is_skill_unlocked("flash_mirage_2"):
            fm2_level = self.char.get_effective_skill_level("flash_mirage_2")
            fm2_skill = BOWMASTER_SKILLS["flash_mirage_2"]
            fm2_fd = fm2_skill.base_stat_value + fm2_skill.stat_per_level * (fm2_level - 1)
            # Add mastery bonus
            fm2_fd += self.get_mastery_bonus("flash_mirage", "skill_final_damage")
            final_mult *= (1 + fm2_fd / 100)

        if skill_name == "quiver_cartridge" and self.char.is_skill_unlocked("enchanted_quiver"):
            eq_level = self.char.get_effective_skill_level("enchanted_quiver")
            eq_skill = BOWMASTER_SKILLS["enchanted_quiver"]
            eq_fd = eq_skill.base_stat_value + eq_skill.stat_per_level * (eq_level - 1)
            final_mult *= (1 + eq_fd / 100)

        # Maple Hero (skill-specific FD for certain skills)
        if skill_name in ["arrow_platter", "phoenix", "covering_fire"]:
            if self.char.is_skill_unlocked("maple_hero"):
                mh_level = self.char.get_effective_skill_level("maple_hero")
                mh_skill = BOWMASTER_SKILLS["maple_hero"]
                # Different skills get different bonuses
                if skill_name == "arrow_platter":
                    mh_fd = 25 + 1.28 * (mh_level - 1)  # 25% -> 81.2%
                elif skill_name == "phoenix":
                    mh_fd = 30 + 1.53 * (mh_level - 1)  # 30% -> 97.5%
                elif skill_name == "covering_fire":
                    mh_fd = 100 + 5.11 * (mh_level - 1)  # 100% -> 325%
                else:
                    mh_fd = 0
                final_mult *= (1 + mh_fd / 100)

        # Crit calculation
        crit_rate_bonus = self.get_total_stat_bonus("crit_rate")
        crit_rate = min((self.char.crit_rate + crit_rate_bonus) / 100, 1.0)

        # Concentration (crit damage stacks)
        crit_dmg_bonus = 0
        if self.char.is_skill_unlocked("concentration"):
            conc_level = self.char.get_effective_skill_level("concentration")
            conc_skill = BOWMASTER_SKILLS["concentration"]
            conc_per_stack = conc_skill.base_stat_value + conc_skill.stat_per_level * (conc_level - 1)
            # 7 stacks, ~100% uptime (TODO: implement precise uptime calculation)
            crit_dmg_bonus = conc_per_stack * 7

        crit_damage = self.char.crit_damage + crit_dmg_bonus
        crit_mult = 1 + crit_rate * (crit_damage / 100)

        # Defense penetration
        def_pen = self.char.defense_pen
        if self.char.is_skill_unlocked("armor_break"):
            ab_level = self.char.get_effective_skill_level("armor_break")
            ab_skill = BOWMASTER_SKILLS["armor_break"]
            def_pen += ab_skill.base_stat_value + ab_skill.stat_per_level * (ab_level - 1)
        def_pen_mult = 1 + def_pen / 100 * 0.3

        damage = base * main_stat_mult * damage_mult * boss_mult * type_mult
        damage *= final_mult * crit_mult * def_pen_mult

        return damage

    def calculate_total_dps(self) -> DPSResult:
        """Calculate total DPS with current character state."""

        cast_time = self.get_cast_time(1.0, True)
        rotation_length = 60.0

        basic_dps = 0
        active_dps = 0
        summon_dps = 0
        proc_dps = 0
        skills_used = []

        # Basic attack (current tier)
        basic_skill_name = self.char.get_active_basic_attack()
        if basic_skill_name and self.char.is_skill_unlocked(basic_skill_name):
            basic_skill = BOWMASTER_SKILLS[basic_skill_name]
            damage = self.calculate_hit_damage(
                self.get_skill_damage_pct(basic_skill_name),
                basic_skill.damage_type,
                basic_skill_name,
            )
            hits = self.get_skill_hits(basic_skill_name)
            targets = self.get_skill_targets(basic_skill_name)
            attacks_per_second = 1 / cast_time
            basic_dps = damage * hits * min(targets, 1) * attacks_per_second  # Single target
            skills_used.append(basic_skill_name)

        # Active skills
        active_skill_time_used = 0
        for skill_name in ["hurricane", "covering_fire"]:
            if not self.char.is_skill_unlocked(skill_name):
                continue

            skill = BOWMASTER_SKILLS[skill_name]
            skill_cast_time = self.get_cast_time(1.0, skill.scales_with_attack_speed)

            if skill.cooldown > 0:
                # Apply skill CD reduction from hat potential
                effective_cd = self.char.get_effective_skill_cooldown(skill.cooldown, 0)
                uses_per_rotation = rotation_length / effective_cd
                time_per_rotation = skill_cast_time * uses_per_rotation
                active_skill_time_used += time_per_rotation

                damage = self.calculate_hit_damage(
                    self.get_skill_damage_pct(skill_name),
                    skill.damage_type,
                    skill_name,
                )
                hits = self.get_skill_hits(skill_name)
                total_damage = damage * hits * uses_per_rotation
                active_dps += total_damage / rotation_length
                skills_used.append(skill_name)

        # Adjust basic DPS for time spent on actives
        basic_time_ratio = max(0, rotation_length - active_skill_time_used) / rotation_length
        basic_dps *= basic_time_ratio

        # Summons
        for skill_name in ["phoenix", "arrow_platter", "quiver_cartridge"]:
            if not self.char.is_skill_unlocked(skill_name):
                continue

            skill = BOWMASTER_SKILLS[skill_name]
            damage = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
            )

            if skill.duration > 0 and skill.attack_interval > 0:
                # Calculate uptime
                if skill.cooldown > 0:
                    # Phoenix cooldown reduction from mastery
                    cd = skill.cooldown
                    mastery_pct_reduction = 0.0
                    if skill_name == "phoenix" and self.char.level >= 104:
                        mastery_pct_reduction = 50.0  # 50% reduction from mastery
                    # Apply skill CD reduction from hat potential
                    cd = self.char.get_effective_skill_cooldown(cd, mastery_pct_reduction)

                    uptime = min(skill.duration / cd, 1.0)
                else:
                    uptime = 1.0

                # Attack interval (may scale with AS for quiver)
                interval = skill.attack_interval
                if skill_name == "quiver_cartridge":
                    # Scales with AS up to 2x
                    as_mult = min(self.get_effective_attack_speed(), 2.0)
                    interval = skill.attack_interval / as_mult

                attacks_per_second = 1 / interval
                targets = self.get_skill_targets(skill_name)
                summon_dps += damage * min(targets, 1) * attacks_per_second * uptime
                skills_used.append(skill_name)

        # Procs
        for skill_name in ["final_attack", "flash_mirage"]:
            if not self.char.is_skill_unlocked(skill_name):
                continue

            skill = BOWMASTER_SKILLS[skill_name]
            damage = self.calculate_hit_damage(
                self.get_skill_damage_pct(skill_name),
                skill.damage_type,
                skill_name,
            )

            # Proc chance (may scale with AS)
            proc_chance = skill.proc_chance
            if skill.scales_with_attack_speed:
                # Flash mirage proc chance scales with AS up to 2x
                proc_chance = min(proc_chance * self.get_effective_attack_speed(), proc_chance * 2)

            # Account for internal cooldown
            if skill.cooldown > 0:
                # Can only proc once per cooldown
                # Flash Mirage has 40% CD reduction from mastery at level 122+
                mastery_pct_reduction = 0.0
                if skill_name == "flash_mirage" and self.char.level >= 122:
                    mastery_pct_reduction = 40.0
                effective_cd = self.char.get_effective_skill_cooldown(skill.cooldown, mastery_pct_reduction)
                procs_per_second = min(1 / cast_time * proc_chance, 1 / effective_cd)
            else:
                procs_per_second = 1 / cast_time * proc_chance

            proc_dps += damage * procs_per_second
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
    **extra_stats,
) -> CharacterState:
    """
    Create a character with job-specific skill bonuses.

    This allows for equipment like "+5 3rd Job Skills" to be modeled.
    """
    char = CharacterState(level=level)

    # Set skill levels based on job bonuses
    for skill_name, skill_data in BOWMASTER_SKILLS.items():
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
