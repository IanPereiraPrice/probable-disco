"""
MapleStory Idle - Stage/Combat Settings
========================================
Combat scenario parameters for DPS calculations.

This module centralizes all combat mode settings used by:
- DPS Calculator (aggregate_stats, calculate_dps)
- Artifact Optimizer (uptime calculations)
- Upgrade Optimizer (recommendations)

Last Updated: January 2025
"""

from dataclasses import dataclass
from typing import Dict
from enum import Enum


class CombatMode(Enum):
    """Combat mode affects how certain stats are valued."""
    STAGE = "stage"              # Mixed: ~60% mob clearing, 40% boss
    CHAPTER_HUNT = "chapter_hunt"  # 100% mob clearing, infinite duration
    BOSS = "boss"                # Single target boss (stage defense)
    WORLD_BOSS = "world_boss"    # Single target world boss (higher defense)


@dataclass
class CombatScenarioConfig:
    """Configuration for a combat scenario."""
    num_enemies: int          # Max enemies present during mob waves
    mob_time_fraction: float  # Fraction of fight spent on mobs (0.0-1.0)
    fight_duration: float     # Seconds (float('inf') for steady state)
    boss_hp_weight: float = 0.5  # Fraction of total HP that comes from boss (0.0-1.0)
    description: str = ""


# Combat scenario parameters for DPS calculations
# - num_enemies: Max enemies present during mob waves (stage has 12 mobs)
# - mob_time_fraction: Fraction of fight spent on mob waves (1.0 = 100% mobs, 0.0 = 100% boss)
# - fight_duration: Seconds for fight duration (inf = steady state, used for chapter hunt)
# - boss_hp_weight: Fraction of total HP from boss (used to weight boss vs normal damage value)
#   For stage mode, boss has ~70% of total HP despite only 40% of time
COMBAT_SCENARIO_PARAMS: Dict[CombatMode, CombatScenarioConfig] = {
    CombatMode.STAGE: CombatScenarioConfig(
        num_enemies=12,
        mob_time_fraction=0.6,
        fight_duration=60.0,
        boss_hp_weight=0.7,  # Boss has ~70% of total HP
        description="Stage farming (60% mobs, 40% boss)",
    ),
    CombatMode.CHAPTER_HUNT: CombatScenarioConfig(
        num_enemies=10,
        mob_time_fraction=1.0,
        fight_duration=float('inf'),
        boss_hp_weight=0.0,  # No boss
        description="Chapter Hunt (infinite, 100% mobs)",
    ),
    CombatMode.BOSS: CombatScenarioConfig(
        num_enemies=1,
        mob_time_fraction=0.0,
        fight_duration=60.0,
        boss_hp_weight=1.0,  # 100% boss
        description="Boss stage (100% boss)",
    ),
    CombatMode.WORLD_BOSS: CombatScenarioConfig(
        num_enemies=1,
        mob_time_fraction=0.0,
        fight_duration=75.0,
        boss_hp_weight=1.0,  # 100% boss
        description="World Boss (100% boss, longer fight)",
    ),
}


def get_combat_mode_from_string(mode_str: str) -> CombatMode:
    """Convert a string combat mode to CombatMode enum.

    Args:
        mode_str: One of 'stage', 'boss', 'world_boss', 'chapter_hunt'

    Returns:
        Corresponding CombatMode enum value
    """
    mode_map = {
        'stage': CombatMode.STAGE,
        'boss': CombatMode.BOSS,
        'world_boss': CombatMode.WORLD_BOSS,
        'chapter_hunt': CombatMode.CHAPTER_HUNT,
    }
    return mode_map.get(mode_str, CombatMode.STAGE)


def get_fight_duration(mode: CombatMode) -> float:
    """Get fight duration for a combat mode.

    Args:
        mode: CombatMode enum value

    Returns:
        Fight duration in seconds (may be float('inf'))
    """
    config = COMBAT_SCENARIO_PARAMS.get(mode, COMBAT_SCENARIO_PARAMS[CombatMode.STAGE])
    return config.fight_duration


def get_fight_duration_from_string(mode_str: str) -> float:
    """Get fight duration from a string combat mode.

    Args:
        mode_str: One of 'stage', 'boss', 'world_boss', 'chapter_hunt'

    Returns:
        Fight duration in seconds (may be float('inf'))
    """
    mode = get_combat_mode_from_string(mode_str)
    return get_fight_duration(mode)
