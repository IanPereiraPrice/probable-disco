"""
MapleStory Idle - Maple Rank System
====================================
Maple Rank provides significant stat bonuses through stage progression.

Each stage has multiple stat categories that can be leveled independently.
Main stat scaling follows a verified formula that increases per stage.

Last Updated: December 2025
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class MapleRankStatType(Enum):
    """Types of stats available in Maple Rank."""
    MAIN_STAT_REGULAR = "main_stat_regular"
    MAIN_STAT_SPECIAL = "main_stat_special"
    ATTACK_SPEED = "attack_speed"
    CRIT_RATE = "crit_rate"
    MIN_DMG_MULT = "min_dmg_mult"
    MAX_DMG_MULT = "max_dmg_mult"
    ACCURACY = "accuracy"
    CRIT_DAMAGE = "crit_damage"
    NORMAL_DAMAGE = "normal_damage"
    BOSS_DAMAGE = "boss_damage"
    SKILL_DAMAGE = "skill_damage"
    DAMAGE_PERCENT = "damage_percent"


# =============================================================================
# CONSTANTS
# =============================================================================

# Maple Rank stat definitions
# Format: {stat_type: {"max_level": int, "per_level": float, "description": str}}
MAPLE_RANK_STATS = {
    MapleRankStatType.ATTACK_SPEED: {
        "max_level": 20,
        "per_level": 0.35,  # 7% / 20 = 0.35% per level
        "description": "Attack Speed +0.35% per level (max 7%)",
    },
    MapleRankStatType.CRIT_RATE: {
        "max_level": 10,
        "per_level": 1.0,  # 10% / 10 = 1% per level
        "description": "Critical Rate +1% per level (max 10%)",
    },
    MapleRankStatType.MIN_DMG_MULT: {
        "max_level": 20,
        "per_level": 0.55,  # 11% / 20 = 0.55% per level
        "description": "Min Damage Multiplier +0.55% per level (max 11%)",
    },
    MapleRankStatType.MAX_DMG_MULT: {
        "max_level": 20,
        "per_level": 0.55,  # 11% / 20 = 0.55% per level
        "description": "Max Damage Multiplier +0.55% per level (max 11%)",
    },
    MapleRankStatType.ACCURACY: {
        "max_level": 20,
        "per_level": 1.15,  # 23 / 20 = 1.15 per level
        "description": "Accuracy +1.15 per level (max 23)",
    },
    MapleRankStatType.CRIT_DAMAGE: {
        "max_level": 30,
        "per_level": 0.667,  # 20% / 30 = 0.667% per level
        "description": "Critical Damage +0.67% per level (max 20%)",
    },
    MapleRankStatType.NORMAL_DAMAGE: {
        "max_level": 30,
        "per_level": 0.667,  # 20% / 30 = 0.667% per level
        "description": "Normal Monster Damage +0.67% per level (max 20%)",
    },
    MapleRankStatType.BOSS_DAMAGE: {
        "max_level": 30,
        "per_level": 0.667,  # 20% / 30 = 0.667% per level
        "description": "Boss Monster Damage +0.67% per level (max 20%)",
    },
    MapleRankStatType.SKILL_DAMAGE: {
        "max_level": 30,
        "per_level": 0.833,  # 25% / 30 = 0.833% per level
        "description": "Skill Damage +0.83% per level (max 25%)",
    },
    MapleRankStatType.DAMAGE_PERCENT: {
        "max_level": 50,
        "per_level": 0.7,  # 35% / 50 = 0.7% per level
        "description": "Damage +0.7% per level (max 35%)",
    },
}

# Main stat special pool
# Base of 300 at level 0, then +5 per point
# At 20 points: 300 + (20 × 5) = 400 DEX
# At 160 points (max): 300 + (160 × 5) = 1,100 DEX
MAIN_STAT_SPECIAL = {
    "max_points": 160,
    "base_value": 300,  # Starts at 300 even at 0 points
    "per_point": 5,  # +5 main stat per point
    "description": "Main Stat: 300 base + 5 per point (max 1,100)",
}

# Display names for UI
STAT_DISPLAY_NAMES = {
    MapleRankStatType.MAIN_STAT_REGULAR: "Main Stat (Regular)",
    MapleRankStatType.MAIN_STAT_SPECIAL: "Main Stat (Special)",
    MapleRankStatType.ATTACK_SPEED: "Attack Speed %",
    MapleRankStatType.CRIT_RATE: "Critical Rate %",
    MapleRankStatType.MIN_DMG_MULT: "Min Damage Mult %",
    MapleRankStatType.MAX_DMG_MULT: "Max Damage Mult %",
    MapleRankStatType.ACCURACY: "Accuracy",
    MapleRankStatType.CRIT_DAMAGE: "Critical Damage %",
    MapleRankStatType.NORMAL_DAMAGE: "Normal Monster Dmg %",
    MapleRankStatType.BOSS_DAMAGE: "Boss Monster Dmg %",
    MapleRankStatType.SKILL_DAMAGE: "Skill Damage %",
    MapleRankStatType.DAMAGE_PERCENT: "Damage %",
}


# =============================================================================
# MAIN STAT SCALING FORMULA (VERIFIED)
# =============================================================================

def get_main_stat_per_point(stage: int) -> int:
    """
    Get main stat value per point at a given stage.

    Verified formula from user testing:
    - Stages 1-7: +2/stage increment → 1, 3, 5, 7, 9, 11, 13 per point
    - Stages 8-10: +4/stage increment → 17, 21, 25 per point
    - Stages 11-21+: +5/stage increment → 30, 35, 40, ..., 80 per point

    Args:
        stage: Current Maple Rank stage (1-21+)

    Returns:
        Main stat value per point at this stage
    """
    if stage < 1:
        return 0
    elif stage <= 7:
        # Stages 1-7: starts at 1, +2 per stage
        return 1 + 2 * (stage - 1)  # 1, 3, 5, 7, 9, 11, 13
    elif stage <= 10:
        # Stages 8-10: continues from 17, +4 per stage
        return 17 + 4 * (stage - 8)  # 17, 21, 25
    else:
        # Stages 11+: continues from 30, +5 per stage
        return 30 + 5 * (stage - 11)  # 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80


def get_cumulative_main_stat(stage: int, level: int) -> int:
    """
    Calculate cumulative main stat from all stages up to and including current.

    Each stage has 10 levels (points). When you complete a stage, you keep
    all the main stat from previous stages.

    Args:
        stage: Current stage (1-21+)
        level: Current level within the stage (0-10)

    Returns:
        Total cumulative main stat
    """
    total = 0

    # Add main stat from completed stages (all at level 10)
    for s in range(1, stage):
        total += get_main_stat_per_point(s) * 10

    # Add main stat from current stage at current level
    if stage >= 1 and level > 0:
        total += get_main_stat_per_point(stage) * level

    return total


def get_stage_main_stat_table() -> Dict[int, Dict]:
    """
    Generate a table of main stat values for each stage.

    Returns:
        Dict mapping stage -> {per_point, max_at_stage, cumulative_max}
    """
    table = {}
    cumulative = 0

    for stage in range(1, 26):  # Up to stage 25 for future
        per_point = get_main_stat_per_point(stage)
        max_at_stage = per_point * 10
        cumulative += max_at_stage
        table[stage] = {
            "per_point": per_point,
            "max_at_stage": max_at_stage,
            "cumulative_max": cumulative,
        }

    return table


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MapleRankConfig:
    """
    Player's Maple Rank configuration.

    Tracks the current stage and levels for each stat type.
    """
    # Current highest stage unlocked
    current_stage: int = 1

    # Level within current stage for main stat (0-10)
    main_stat_level: int = 0

    # Special main stat points (separate pool, 0-160)
    special_main_stat_points: int = 0

    # Levels for each stat type (0 to max_level)
    stat_levels: Dict[MapleRankStatType, int] = field(default_factory=dict)

    def __post_init__(self):
        # Initialize all stats to 0 if not provided
        for stat_type in MAPLE_RANK_STATS:
            if stat_type not in self.stat_levels:
                self.stat_levels[stat_type] = 0

    def get_stat_level(self, stat_type: MapleRankStatType) -> int:
        """Get current level of a stat."""
        return self.stat_levels.get(stat_type, 0)

    def set_stat_level(self, stat_type: MapleRankStatType, level: int) -> None:
        """Set stat level, clamped to valid range."""
        if stat_type in MAPLE_RANK_STATS:
            max_level = MAPLE_RANK_STATS[stat_type]["max_level"]
            self.stat_levels[stat_type] = max(0, min(level, max_level))

    def get_stat_value(self, stat_type: MapleRankStatType) -> float:
        """Get the total bonus value for a stat at current level."""
        if stat_type not in MAPLE_RANK_STATS:
            return 0.0
        level = self.get_stat_level(stat_type)
        per_level = MAPLE_RANK_STATS[stat_type]["per_level"]
        return level * per_level

    def get_regular_main_stat(self) -> int:
        """Get total regular main stat from all stages."""
        return get_cumulative_main_stat(self.current_stage, self.main_stat_level)

    def get_special_main_stat(self) -> int:
        """Get total special main stat (base 300 + 5 per point)."""
        return MAIN_STAT_SPECIAL["base_value"] + self.special_main_stat_points * MAIN_STAT_SPECIAL["per_point"]

    def get_total_main_stat(self) -> int:
        """Get combined regular + special main stat."""
        return self.get_regular_main_stat() + self.get_special_main_stat()

    def get_all_stats(self) -> Dict[str, float]:
        """
        Get all Maple Rank stats for damage calculation.
        Returns dict with stat keys matching damage calc expectations.
        """
        stats = {
            "main_stat_flat": float(self.get_total_main_stat()),
            "main_stat_regular": float(self.get_regular_main_stat()),
            "main_stat_special": float(self.get_special_main_stat()),
            "attack_speed": self.get_stat_value(MapleRankStatType.ATTACK_SPEED),
            "crit_rate": self.get_stat_value(MapleRankStatType.CRIT_RATE),
            "min_dmg_mult": self.get_stat_value(MapleRankStatType.MIN_DMG_MULT),
            "max_dmg_mult": self.get_stat_value(MapleRankStatType.MAX_DMG_MULT),
            "accuracy": self.get_stat_value(MapleRankStatType.ACCURACY),
            "crit_damage": self.get_stat_value(MapleRankStatType.CRIT_DAMAGE),
            "normal_damage": self.get_stat_value(MapleRankStatType.NORMAL_DAMAGE),
            "boss_damage": self.get_stat_value(MapleRankStatType.BOSS_DAMAGE),
            "skill_damage": self.get_stat_value(MapleRankStatType.SKILL_DAMAGE),
            "damage_percent": self.get_stat_value(MapleRankStatType.DAMAGE_PERCENT),
        }
        return stats

    def to_dict(self) -> Dict:
        """Serialize to dict for saving."""
        return {
            "current_stage": self.current_stage,
            "main_stat_level": self.main_stat_level,
            "special_main_stat_points": self.special_main_stat_points,
            "stat_levels": {
                stat.value: level
                for stat, level in self.stat_levels.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "MapleRankConfig":
        """Deserialize from dict."""
        config = cls(
            current_stage=data.get("current_stage", 1),
            main_stat_level=data.get("main_stat_level", 0),
            special_main_stat_points=data.get("special_main_stat_points", 0),
        )
        stat_data = data.get("stat_levels", {})
        for stat_type in MapleRankStatType:
            if stat_type in MAPLE_RANK_STATS:
                level = stat_data.get(stat_type.value, 0)
                config.stat_levels[stat_type] = level
        return config


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_max_maple_rank_stats() -> Dict[str, float]:
    """Get stats if all Maple Rank stats are maxed (Stage 21, all stats maxed)."""
    config = MapleRankConfig(
        current_stage=21,
        main_stat_level=10,
        special_main_stat_points=160,
    )
    for stat_type in MAPLE_RANK_STATS:
        max_level = MAPLE_RANK_STATS[stat_type]["max_level"]
        config.set_stat_level(stat_type, max_level)
    return config.get_all_stats()


def create_default_config() -> MapleRankConfig:
    """Create a default Maple Rank configuration."""
    return MapleRankConfig()


# =============================================================================
# MAIN (Testing)
# =============================================================================

if __name__ == "__main__":
    print("MapleStory Idle - Maple Rank System Module")
    print("=" * 60)

    # Test main stat scaling formula
    print("\nMain Stat Scaling by Stage:")
    print("-" * 40)
    table = get_stage_main_stat_table()
    for stage in range(1, 22):
        info = table[stage]
        print(f"  Stage {stage:2d}: {info['per_point']:3d}/point, "
              f"max {info['max_at_stage']:4d}, cumulative {info['cumulative_max']:5d}")

    # Test specific values from user data
    print("\nValidation (User Data: Stage 21 @ 5/10 = 6,770):")
    test_config = MapleRankConfig(current_stage=21, main_stat_level=5)
    calculated = test_config.get_regular_main_stat()
    expected = 6770
    print(f"  Calculated: {calculated}")
    print(f"  Expected: {expected}")
    print(f"  Match: {'YES' if calculated == expected else 'NO - needs adjustment'}")

    # Test with special points
    print("\nWith Special Points (20 pts × 20/pt = +400):")
    test_config.special_main_stat_points = 20
    print(f"  Regular Main Stat: {test_config.get_regular_main_stat()}")
    print(f"  Special Main Stat: {test_config.get_special_main_stat()}")
    print(f"  Total Main Stat: {test_config.get_total_main_stat()}")

    # Test default config
    print("\nDefault Config (all zeros):")
    config = create_default_config()
    print(f"  Stats: {config.get_all_stats()}")

    # Test maxed config
    print("\nMaxed Config (Stage 21, all stats maxed):")
    max_stats = get_max_maple_rank_stats()
    for key, value in max_stats.items():
        if value > 0:
            if "main_stat" in key:
                print(f"  {key}: {value:.0f}")
            else:
                print(f"  {key}: {value:.1f}%")

    # Test serialization
    print("\nSerialization Test:")
    config.current_stage = 15
    config.main_stat_level = 7
    config.set_stat_level(MapleRankStatType.DAMAGE_PERCENT, 35)
    config.set_stat_level(MapleRankStatType.BOSS_DAMAGE, 20)
    data = config.to_dict()
    restored = MapleRankConfig.from_dict(data)
    print(f"  Original stage: {config.current_stage}, Restored: {restored.current_stage}")
    print(f"  Original main_stat_level: {config.main_stat_level}, Restored: {restored.main_stat_level}")
    print(f"  Damage % matches: {config.get_stat_value(MapleRankStatType.DAMAGE_PERCENT) == restored.get_stat_value(MapleRankStatType.DAMAGE_PERCENT)}")
