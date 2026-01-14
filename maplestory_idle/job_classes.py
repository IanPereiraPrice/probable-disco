"""
MapleStory Idle - Job Class System
===================================
Defines all job classes with their stat type mappings.

Each job class has a main stat and secondary stat that affect damage calculations.
"""

from enum import Enum
from typing import Dict, Tuple


class StatType(Enum):
    """Primary stat types in the game."""
    STR = "str"
    DEX = "dex"
    INT = "int"
    LUK = "luk"


class JobClass(Enum):
    """All playable job classes."""
    # Archer branch (DEX/STR)
    BOWMASTER = "bowmaster"
    MARKSMAN = "marksman"
    # Warrior branch (STR/DEX)
    HERO = "hero"
    DARK_KNIGHT = "dark_knight"
    # Mage branch (INT/LUK)
    ARCHMAGE_FIRE_POISON = "archmage_fire_poison"
    ARCHMAGE_ICE_LIGHTNING = "archmage_ice_lightning"
    # Thief branch (LUK/DEX)
    NIGHT_LORD = "night_lord"
    SHADOWER = "shadower"


# Job class stat mappings: (main_stat, secondary_stat)
JOB_STAT_MAPPING: Dict[JobClass, Tuple[StatType, StatType]] = {
    # Archer branch (DEX/STR)
    JobClass.BOWMASTER: (StatType.DEX, StatType.STR),
    JobClass.MARKSMAN: (StatType.DEX, StatType.STR),
    # Warrior branch (STR/DEX)
    JobClass.HERO: (StatType.STR, StatType.DEX),
    JobClass.DARK_KNIGHT: (StatType.STR, StatType.DEX),
    # Mage branch (INT/LUK)
    JobClass.ARCHMAGE_FIRE_POISON: (StatType.INT, StatType.LUK),
    JobClass.ARCHMAGE_ICE_LIGHTNING: (StatType.INT, StatType.LUK),
    # Thief branch (LUK/DEX)
    JobClass.NIGHT_LORD: (StatType.LUK, StatType.DEX),
    JobClass.SHADOWER: (StatType.LUK, StatType.DEX),
}


# Display names for job classes
JOB_DISPLAY_NAMES: Dict[JobClass, str] = {
    JobClass.BOWMASTER: "Bowmaster",
    JobClass.MARKSMAN: "Marksman",
    JobClass.HERO: "Hero",
    JobClass.DARK_KNIGHT: "Dark Knight",
    JobClass.ARCHMAGE_FIRE_POISON: "Archmage (F/P)",
    JobClass.ARCHMAGE_ICE_LIGHTNING: "Archmage (I/L)",
    JobClass.NIGHT_LORD: "Night Lord",
    JobClass.SHADOWER: "Shadower",
}


# Group jobs by branch for UI display
JOB_GROUPS: Dict[str, list] = {
    "Archer": [JobClass.BOWMASTER, JobClass.MARKSMAN],
    "Warrior": [JobClass.HERO, JobClass.DARK_KNIGHT],
    "Mage": [JobClass.ARCHMAGE_FIRE_POISON, JobClass.ARCHMAGE_ICE_LIGHTNING],
    "Thief": [JobClass.NIGHT_LORD, JobClass.SHADOWER],
}


def get_job_stats(job_class: JobClass) -> Tuple[StatType, StatType]:
    """
    Get main and secondary stat for a job class.

    Args:
        job_class: The job class to look up

    Returns:
        Tuple of (main_stat, secondary_stat)
    """
    return JOB_STAT_MAPPING.get(job_class, (StatType.DEX, StatType.STR))


def get_main_stat_name(job_class: JobClass) -> str:
    """Get the main stat name (e.g., 'dex', 'str') for display."""
    main_stat, _ = get_job_stats(job_class)
    return main_stat.value


def get_secondary_stat_name(job_class: JobClass) -> str:
    """Get the secondary stat name for display."""
    _, secondary_stat = get_job_stats(job_class)
    return secondary_stat.value


def get_stat_key_for_job(job_class: JobClass, stat_type: str) -> str:
    """
    Get the appropriate stat key based on job class and generic stat type.

    This maps generic 'main_stat' or 'secondary_stat' to the actual stat
    (e.g., 'dex', 'str', 'int', 'luk') for the given job class.

    Args:
        job_class: The job class
        stat_type: Either 'main_stat', 'secondary_stat', or a specific stat name

    Returns:
        The actual stat key (e.g., 'dex', 'str')
    """
    main_stat, secondary_stat = get_job_stats(job_class)

    if stat_type == 'main_stat':
        return main_stat.value
    elif stat_type == 'secondary_stat':
        return secondary_stat.value
    else:
        return stat_type


# Export list for convenience
__all__ = [
    'StatType',
    'JobClass',
    'JOB_STAT_MAPPING',
    'JOB_DISPLAY_NAMES',
    'JOB_GROUPS',
    'get_job_stats',
    'get_main_stat_name',
    'get_secondary_stat_name',
    'get_stat_key_for_job',
]
