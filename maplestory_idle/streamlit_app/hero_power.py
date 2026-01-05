# hero_power.py - Hero Power System Data Structures and Simulation Logic
"""
MapleStory Idle - Hero Power System
====================================
Hero Power provides stats through two separate systems:

1. ABILITY LINES - 5 rerollable lines with random stats/tiers
2. PASSIVE STATS - Levelable stats that provide flat bonuses (Stage 6 max)

Last Updated: December 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum
import random
import copy


# =============================================================================
# ENUMS
# =============================================================================

class HeroPowerPassiveStatType(Enum):
    """Types of passive stats in Hero Power (leveled, not rerolled)."""
    MAIN_STAT = "main_stat"          # Flat DEX/STR/INT/LUK
    DAMAGE_PERCENT = "damage_percent"  # Damage %
    ATTACK = "attack"                # Flat Attack
    MAX_HP = "max_hp"                # Flat Max HP
    ACCURACY = "accuracy"            # Flat Accuracy
    DEFENSE = "defense"              # Flat Defense


class HeroPowerTier(Enum):
    """Hero Power line tier."""
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"
    UNIQUE = "unique"
    LEGENDARY = "legendary"
    MYSTIC = "mystic"


class HeroPowerStatType(Enum):
    """Available stats for Hero Power lines."""
    DAMAGE = "damage"
    BOSS_DAMAGE = "boss_damage"
    NORMAL_DAMAGE = "normal_damage"
    DEF_PEN = "def_pen"
    MAX_DMG_MULT = "max_dmg_mult"
    MIN_DMG_MULT = "min_dmg_mult"
    CRIT_RATE = "crit_rate"
    CRIT_DAMAGE = "crit_damage"
    MAIN_STAT_PCT = "main_stat_pct"
    ATTACK_PCT = "attack_pct"
    DEFENSE = "defense"
    MAX_HP = "max_hp"


# Display names for UI
STAT_DISPLAY_NAMES: Dict[HeroPowerStatType, str] = {
    HeroPowerStatType.DAMAGE: "Damage %",
    HeroPowerStatType.BOSS_DAMAGE: "Boss Damage %",
    HeroPowerStatType.NORMAL_DAMAGE: "Normal Damage %",
    HeroPowerStatType.DEF_PEN: "Defense Penetration %",
    HeroPowerStatType.MAX_DMG_MULT: "Max Damage Multiplier %",
    HeroPowerStatType.MIN_DMG_MULT: "Min Damage Multiplier %",
    HeroPowerStatType.CRIT_RATE: "Critical Rate %",
    HeroPowerStatType.CRIT_DAMAGE: "Critical Damage %",
    HeroPowerStatType.MAIN_STAT_PCT: "Main Stat (flat)",  # Applied before DEX%
    HeroPowerStatType.ATTACK_PCT: "Attack %",
    HeroPowerStatType.DEFENSE: "Defense",
    HeroPowerStatType.MAX_HP: "Max HP",
}

# Tier display colors (matching existing app style)
TIER_COLORS: Dict[HeroPowerTier, str] = {
    HeroPowerTier.COMMON: "#888888",
    HeroPowerTier.RARE: "#4a9eff",
    HeroPowerTier.EPIC: "#9d65c9",
    HeroPowerTier.UNIQUE: "#ffd700",
    HeroPowerTier.LEGENDARY: "#00ff88",
    HeroPowerTier.MYSTIC: "#ff4444",
}


# =============================================================================
# CONSTANTS - PASSIVE STATS (Levelable)
# =============================================================================

# Hero Power Passive Stats definitions (Stage 6 values - verified)
# Format: {stat_type: {"max_level": int, "per_level": float, "description": str}}
HERO_POWER_PASSIVE_STATS = {
    HeroPowerPassiveStatType.MAIN_STAT: {
        "max_level": 60,
        "per_level": 27.5,  # 1650 / 60 = 27.5 per level
        "description": "Main Stat +27.5 per level (max 1,650)",
    },
    HeroPowerPassiveStatType.DAMAGE_PERCENT: {
        "max_level": 60,
        "per_level": 0.75,  # 45% / 60 = 0.75% per level
        "description": "Damage +0.75% per level (max 45%)",
    },
    HeroPowerPassiveStatType.ATTACK: {
        "max_level": 60,
        "per_level": 103.75,  # 6225 / 60 = 103.75 per level
        "description": "Attack +103.75 per level (max 6,225)",
    },
    HeroPowerPassiveStatType.MAX_HP: {
        "max_level": 60,
        "per_level": 2075.0,  # 124500 / 60 = 2075 per level
        "description": "Max HP +2,075 per level (max 124,500)",
    },
    HeroPowerPassiveStatType.ACCURACY: {
        "max_level": 20,
        "per_level": 2.25,  # 45 / 20 = 2.25 per level
        "description": "Accuracy +2.25 per level (max 45)",
    },
    HeroPowerPassiveStatType.DEFENSE: {
        "max_level": 60,
        "per_level": 93.75,  # 5625 / 60 = 93.75 per level
        "description": "Defense +93.75 per level (max 5,625)",
    },
}

# Display names for passive stats
PASSIVE_STAT_DISPLAY_NAMES: Dict[HeroPowerPassiveStatType, str] = {
    HeroPowerPassiveStatType.MAIN_STAT: "Main Stat (DEX/STR/INT/LUK)",
    HeroPowerPassiveStatType.DAMAGE_PERCENT: "Damage %",
    HeroPowerPassiveStatType.ATTACK: "Attack",
    HeroPowerPassiveStatType.MAX_HP: "Max HP",
    HeroPowerPassiveStatType.ACCURACY: "Accuracy",
    HeroPowerPassiveStatType.DEFENSE: "Defense",
}


# =============================================================================
# CONSTANTS - ABILITY LINES (Rerollable)
# =============================================================================

# Reroll costs in Medals based on locked lines
HERO_POWER_REROLL_COSTS: Dict[int, int] = {
    0: 86,   # 0 locked lines
    1: 129,  # 1 locked
    2: 172,  # 2 locked
    3: 215,  # 3 locked
    4: 258,  # 4 locked
    5: 301,  # 5 locked (only 1 line rerolls)
}

# Tier probabilities per line when rerolling (from knowledge base)
HERO_POWER_TIER_RATES: Dict[HeroPowerTier, float] = {
    HeroPowerTier.MYSTIC: 0.0012,      # 0.12%
    HeroPowerTier.LEGENDARY: 0.0154,   # 1.54%
    HeroPowerTier.UNIQUE: 0.05,        # ~5% (estimated)
    HeroPowerTier.EPIC: 0.15,          # ~15% (estimated)
    HeroPowerTier.RARE: 0.30,          # ~30% (estimated)
    HeroPowerTier.COMMON: 0.4834,      # remainder
}

# Valuable stats - these are the stats worth targeting
VALUABLE_STATS: List[HeroPowerStatType] = [
    HeroPowerStatType.DAMAGE,
    HeroPowerStatType.BOSS_DAMAGE,
    HeroPowerStatType.DEF_PEN,
    HeroPowerStatType.MAX_DMG_MULT,
    HeroPowerStatType.CRIT_DAMAGE,
]

# LEGACY: Arbitrary DPS weights - kept for fallback when calc_dps_func not available
# These are used when we can't calculate actual DPS impact
STAT_DPS_WEIGHTS: Dict[HeroPowerStatType, float] = {
    HeroPowerStatType.DEF_PEN: 2.5,         # Defense Penetration is very strong
    HeroPowerStatType.BOSS_DAMAGE: 2.0,     # Boss Damage is highly valuable
    HeroPowerStatType.DAMAGE: 1.8,          # Damage % is great
    HeroPowerStatType.MAX_DMG_MULT: 1.5,    # Max Damage Mult is good
    HeroPowerStatType.CRIT_DAMAGE: 1.5,     # Crit Damage is good
    HeroPowerStatType.MAIN_STAT_PCT: 1.4,   # Flat main stat applied before DEX% - valuable!
    HeroPowerStatType.CRIT_RATE: 1.2,       # Crit Rate is decent
    HeroPowerStatType.ATTACK_PCT: 1.0,      # Attack % is okay
    HeroPowerStatType.MIN_DMG_MULT: 0.6,    # Min Damage is less valuable
    HeroPowerStatType.NORMAL_DAMAGE: 0.5,   # Normal Damage is situational
    HeroPowerStatType.DEFENSE: 0.1,         # Defensive stats low value
    HeroPowerStatType.MAX_HP: 0.1,          # Defensive stats low value
}

# Mapping from HeroPowerStatType to the stats dict key used in DPS calculation
STAT_TO_STATS_KEY: Dict[HeroPowerStatType, str] = {
    HeroPowerStatType.DAMAGE: "damage_percent",
    HeroPowerStatType.BOSS_DAMAGE: "boss_damage",
    HeroPowerStatType.NORMAL_DAMAGE: "normal_damage",
    HeroPowerStatType.DEF_PEN: "defense_pen",  # Fixed: matches _get_damage_stats key
    HeroPowerStatType.MAX_DMG_MULT: "max_dmg_mult",  # Fixed: matches _get_damage_stats key
    HeroPowerStatType.MIN_DMG_MULT: "min_dmg_mult",  # Fixed: matches _get_damage_stats key
    HeroPowerStatType.CRIT_RATE: "crit_rate",
    HeroPowerStatType.CRIT_DAMAGE: "crit_damage",
    HeroPowerStatType.MAIN_STAT_PCT: "dex_flat",  # This is flat main stat (e.g., +2000 DEX)
    HeroPowerStatType.ATTACK_PCT: "attack_percent",
    HeroPowerStatType.DEFENSE: None,  # Defensive, no DPS impact
    HeroPowerStatType.MAX_HP: None,   # Defensive, no DPS impact
}

# Tier multiplier for scoring (higher tier = better)
TIER_SCORE_MULTIPLIERS: Dict[HeroPowerTier, float] = {
    HeroPowerTier.MYSTIC: 1.0,
    HeroPowerTier.LEGENDARY: 0.75,
    HeroPowerTier.UNIQUE: 0.5,
    HeroPowerTier.EPIC: 0.3,
    HeroPowerTier.RARE: 0.15,
    HeroPowerTier.COMMON: 0.05,
}

# Mode-specific stat weight adjustments
# These multiply the base STAT_DPS_WEIGHTS for combat mode optimization
# Key is mode string (matches CombatMode.value from cubes.py)
MODE_STAT_ADJUSTMENTS: Dict[str, Dict[HeroPowerStatType, float]] = {
    "stage": {
        # Stage: mix of mobs and boss - normal damage has some value
        HeroPowerStatType.NORMAL_DAMAGE: 1.5,  # Normal damage useful for mobs
        HeroPowerStatType.BOSS_DAMAGE: 0.7,    # Less boss time in stages
    },
    "boss": {
        # Regular boss: single target, stage-level defense
        HeroPowerStatType.BOSS_DAMAGE: 1.5,    # Boss damage very important
        HeroPowerStatType.NORMAL_DAMAGE: 0.0,  # Useless on bosses
    },
    "world_boss": {
        # World boss: single target, HIGH defense
        HeroPowerStatType.DEF_PEN: 1.5,        # High def = def pen very valuable
        HeroPowerStatType.BOSS_DAMAGE: 1.5,    # It's a boss
        HeroPowerStatType.NORMAL_DAMAGE: 0.0,  # Useless
    },
}


# =============================================================================
# HERO POWER LEVEL CONFIG
# =============================================================================

@dataclass
class HeroPowerLevelConfig:
    """
    Configuration for Hero Power level, which affects tier probabilities and base cost.

    Level progression is not a simple formula - user inputs their current level's values.
    Example data:
      Level 15: 0.14%/1.63%/3.3%/37.93%/32%/25%, base cost 89 medals
      Level 16: 0.16%/1.72%/3.25%/37.87%/32%/25%
    """
    level: int = 15
    mystic_rate: float = 0.14       # % (e.g., 0.14 means 0.14%)
    legendary_rate: float = 1.63    # %
    unique_rate: float = 3.3        # %
    epic_rate: float = 37.93        # %
    rare_rate: float = 32.0         # %
    common_rate: float = 25.0       # %
    base_cost: int = 89             # medals per reroll (0 locked lines)

    def get_tier_rates(self) -> Dict[HeroPowerTier, float]:
        """Return tier rates dict for simulation (as decimals, not percentages)."""
        return {
            HeroPowerTier.MYSTIC: self.mystic_rate / 100,
            HeroPowerTier.LEGENDARY: self.legendary_rate / 100,
            HeroPowerTier.UNIQUE: self.unique_rate / 100,
            HeroPowerTier.EPIC: self.epic_rate / 100,
            HeroPowerTier.RARE: self.rare_rate / 100,
            HeroPowerTier.COMMON: self.common_rate / 100,
        }

    def get_reroll_cost(self, locked_lines: int) -> int:
        """Get reroll cost with level-adjusted base cost."""
        # The cost increase per locked line stays the same (43 medals per lock)
        # Only the base cost changes with level
        cost_per_lock = 43
        return self.base_cost + (locked_lines * cost_per_lock)

    def to_dict(self) -> Dict:
        """Serialize to dict for saving."""
        return {
            "level": self.level,
            "mystic_rate": self.mystic_rate,
            "legendary_rate": self.legendary_rate,
            "unique_rate": self.unique_rate,
            "epic_rate": self.epic_rate,
            "rare_rate": self.rare_rate,
            "common_rate": self.common_rate,
            "base_cost": self.base_cost,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "HeroPowerLevelConfig":
        """Deserialize from dict."""
        return cls(
            level=data.get("level", 15),
            mystic_rate=data.get("mystic_rate", 0.14),
            legendary_rate=data.get("legendary_rate", 1.63),
            unique_rate=data.get("unique_rate", 3.3),
            epic_rate=data.get("epic_rate", 37.93),
            rare_rate=data.get("rare_rate", 32.0),
            common_rate=data.get("common_rate", 25.0),
            base_cost=data.get("base_cost", 89),
        )


def create_default_level_config() -> HeroPowerLevelConfig:
    """Create a default level 15 configuration."""
    return HeroPowerLevelConfig()


# Stat probabilities when rolling (simplified - valuable stats more likely at higher tiers)
STAT_PROBABILITIES: Dict[HeroPowerTier, Dict[HeroPowerStatType, float]] = {
    HeroPowerTier.MYSTIC: {
        HeroPowerStatType.DAMAGE: 0.20,
        HeroPowerStatType.BOSS_DAMAGE: 0.20,
        HeroPowerStatType.DEF_PEN: 0.15,
        HeroPowerStatType.MAX_DMG_MULT: 0.15,
        HeroPowerStatType.CRIT_DAMAGE: 0.10,
        HeroPowerStatType.MIN_DMG_MULT: 0.05,
        HeroPowerStatType.MAIN_STAT_PCT: 0.05,
        HeroPowerStatType.CRIT_RATE: 0.05,
        HeroPowerStatType.ATTACK_PCT: 0.03,
        HeroPowerStatType.NORMAL_DAMAGE: 0.02,
    },
    HeroPowerTier.LEGENDARY: {
        HeroPowerStatType.DAMAGE: 0.18,
        HeroPowerStatType.BOSS_DAMAGE: 0.18,
        HeroPowerStatType.DEF_PEN: 0.12,
        HeroPowerStatType.MAX_DMG_MULT: 0.12,
        HeroPowerStatType.CRIT_DAMAGE: 0.08,
        HeroPowerStatType.MIN_DMG_MULT: 0.08,
        HeroPowerStatType.MAIN_STAT_PCT: 0.08,
        HeroPowerStatType.CRIT_RATE: 0.06,
        HeroPowerStatType.ATTACK_PCT: 0.05,
        HeroPowerStatType.NORMAL_DAMAGE: 0.05,
    },
}

# Default stat probabilities for lower tiers (more junk stats)
DEFAULT_STAT_PROBS: Dict[HeroPowerStatType, float] = {
    HeroPowerStatType.DAMAGE: 0.10,
    HeroPowerStatType.BOSS_DAMAGE: 0.08,
    HeroPowerStatType.DEF_PEN: 0.06,
    HeroPowerStatType.MAX_DMG_MULT: 0.08,
    HeroPowerStatType.CRIT_DAMAGE: 0.05,
    HeroPowerStatType.MIN_DMG_MULT: 0.10,
    HeroPowerStatType.MAIN_STAT_PCT: 0.12,
    HeroPowerStatType.CRIT_RATE: 0.08,
    HeroPowerStatType.ATTACK_PCT: 0.08,
    HeroPowerStatType.NORMAL_DAMAGE: 0.10,
    HeroPowerStatType.DEFENSE: 0.08,
    HeroPowerStatType.MAX_HP: 0.07,
}

# Stat value ranges by tier (min, max) - percentages
# From knowledge base: Mystic has Damage 28-40%, DEF_PEN 14-20%, etc.
HERO_POWER_STAT_RANGES: Dict[HeroPowerTier, Dict[HeroPowerStatType, Tuple[float, float]]] = {
    HeroPowerTier.MYSTIC: {
        HeroPowerStatType.DAMAGE: (28.0, 40.0),
        HeroPowerStatType.BOSS_DAMAGE: (28.0, 40.0),
        HeroPowerStatType.NORMAL_DAMAGE: (28.0, 40.0),  # Same as Boss Damage
        HeroPowerStatType.DEF_PEN: (14.0, 20.0),
        HeroPowerStatType.MAX_DMG_MULT: (28.0, 40.0),
        HeroPowerStatType.MIN_DMG_MULT: (28.0, 40.0),
        HeroPowerStatType.CRIT_DAMAGE: (20.0, 30.0),
        HeroPowerStatType.MAIN_STAT_PCT: (1500, 2500),  # Flat main stat (e.g., +2000 DEX)
        HeroPowerStatType.CRIT_RATE: (8.0, 12.0),
        HeroPowerStatType.ATTACK_PCT: (12.0, 18.0),
    },
    HeroPowerTier.LEGENDARY: {
        HeroPowerStatType.DAMAGE: (18.0, 25.0),
        HeroPowerStatType.BOSS_DAMAGE: (18.0, 25.0),
        HeroPowerStatType.NORMAL_DAMAGE: (18.0, 25.0),  # Same as Boss Damage
        HeroPowerStatType.DEF_PEN: (10.0, 14.0),
        HeroPowerStatType.MAX_DMG_MULT: (18.0, 25.0),
        HeroPowerStatType.MIN_DMG_MULT: (18.0, 25.0),
        HeroPowerStatType.CRIT_DAMAGE: (14.0, 20.0),
        HeroPowerStatType.MAIN_STAT_PCT: (800, 1200),  # Flat main stat
        HeroPowerStatType.CRIT_RATE: (5.0, 8.0),
        HeroPowerStatType.ATTACK_PCT: (8.0, 12.0),
    },
    HeroPowerTier.UNIQUE: {
        HeroPowerStatType.DAMAGE: (12.0, 18.0),
        HeroPowerStatType.BOSS_DAMAGE: (12.0, 18.0),
        HeroPowerStatType.NORMAL_DAMAGE: (12.0, 18.0),  # Same as Boss Damage
        HeroPowerStatType.DEF_PEN: (6.0, 10.0),
        HeroPowerStatType.MAX_DMG_MULT: (12.0, 18.0),
        HeroPowerStatType.MIN_DMG_MULT: (12.0, 18.0),
        HeroPowerStatType.CRIT_DAMAGE: (10.0, 14.0),
        HeroPowerStatType.MAIN_STAT_PCT: (400, 700),  # Flat main stat
        HeroPowerStatType.CRIT_RATE: (3.0, 5.0),
        HeroPowerStatType.ATTACK_PCT: (5.0, 8.0),
    },
    HeroPowerTier.EPIC: {
        HeroPowerStatType.DAMAGE: (8.0, 12.0),
        HeroPowerStatType.BOSS_DAMAGE: (8.0, 12.0),
        HeroPowerStatType.NORMAL_DAMAGE: (8.0, 12.0),  # Same as Boss Damage
        HeroPowerStatType.DEF_PEN: (4.0, 6.0),
        HeroPowerStatType.MAX_DMG_MULT: (8.0, 12.0),
        HeroPowerStatType.MIN_DMG_MULT: (8.0, 12.0),
        HeroPowerStatType.CRIT_DAMAGE: (6.0, 10.0),
        HeroPowerStatType.MAIN_STAT_PCT: (200, 300),  # Flat main stat
        HeroPowerStatType.CRIT_RATE: (2.0, 3.0),
        HeroPowerStatType.ATTACK_PCT: (3.0, 5.0),
        HeroPowerStatType.DEFENSE: (100, 200),
        HeroPowerStatType.MAX_HP: (500, 1000),
    },
    HeroPowerTier.RARE: {
        HeroPowerStatType.DAMAGE: (4.0, 8.0),
        HeroPowerStatType.BOSS_DAMAGE: (4.0, 8.0),
        HeroPowerStatType.NORMAL_DAMAGE: (4.0, 8.0),  # Same as Boss Damage
        HeroPowerStatType.DEF_PEN: (2.0, 4.0),
        HeroPowerStatType.MAX_DMG_MULT: (4.0, 8.0),
        HeroPowerStatType.MIN_DMG_MULT: (4.0, 8.0),
        HeroPowerStatType.CRIT_DAMAGE: (3.0, 6.0),
        HeroPowerStatType.MAIN_STAT_PCT: (100, 150),  # Flat main stat
        HeroPowerStatType.CRIT_RATE: (1.0, 2.0),
        HeroPowerStatType.ATTACK_PCT: (2.0, 3.0),
        HeroPowerStatType.DEFENSE: (50, 100),
        HeroPowerStatType.MAX_HP: (200, 500),
    },
    HeroPowerTier.COMMON: {
        HeroPowerStatType.DAMAGE: (1.0, 4.0),
        HeroPowerStatType.BOSS_DAMAGE: (1.0, 4.0),
        HeroPowerStatType.NORMAL_DAMAGE: (1.0, 4.0),  # Same as Boss Damage
        HeroPowerStatType.DEF_PEN: (1.0, 2.0),
        HeroPowerStatType.MAX_DMG_MULT: (1.0, 4.0),
        HeroPowerStatType.MIN_DMG_MULT: (1.0, 4.0),
        HeroPowerStatType.CRIT_DAMAGE: (1.0, 3.0),
        HeroPowerStatType.MAIN_STAT_PCT: (40, 60),  # Flat main stat
        HeroPowerStatType.CRIT_RATE: (0.5, 1.0),
        HeroPowerStatType.ATTACK_PCT: (1.0, 2.0),
        HeroPowerStatType.DEFENSE: (20, 50),
        HeroPowerStatType.MAX_HP: (100, 200),
    },
}


# =============================================================================
# DATA CLASSES - PASSIVE STATS
# =============================================================================

@dataclass
class HeroPowerPassiveConfig:
    """
    Hero Power Passive Stats configuration.

    These are leveled stats (not rerolled) that provide flat bonuses.
    Stage 6 max levels: Main Stat, Damage%, Attack, Max HP at 60/60; Accuracy at 20/20; Defense at 60/60
    """
    # Level for each passive stat (0 to max_level)
    stat_levels: Dict[HeroPowerPassiveStatType, int] = field(default_factory=dict)

    def __post_init__(self):
        # Initialize all passive stats to 0 if not provided
        for stat_type in HeroPowerPassiveStatType:
            if stat_type not in self.stat_levels:
                self.stat_levels[stat_type] = 0

    def get_stat_level(self, stat_type: HeroPowerPassiveStatType) -> int:
        """Get current level of a passive stat."""
        return self.stat_levels.get(stat_type, 0)

    def set_stat_level(self, stat_type: HeroPowerPassiveStatType, level: int) -> None:
        """Set passive stat level, clamped to valid range."""
        if stat_type in HERO_POWER_PASSIVE_STATS:
            max_level = HERO_POWER_PASSIVE_STATS[stat_type]["max_level"]
            self.stat_levels[stat_type] = max(0, min(level, max_level))

    def get_stat_value(self, stat_type: HeroPowerPassiveStatType) -> float:
        """Get the total bonus value for a passive stat at current level."""
        if stat_type not in HERO_POWER_PASSIVE_STATS:
            return 0.0
        level = self.get_stat_level(stat_type)
        per_level = HERO_POWER_PASSIVE_STATS[stat_type]["per_level"]
        return level * per_level

    def get_all_stats(self) -> Dict[str, float]:
        """
        Get all Hero Power passive stats for damage calculation.
        Returns dict with stat keys matching damage calc expectations.
        """
        return {
            "main_stat_flat": self.get_stat_value(HeroPowerPassiveStatType.MAIN_STAT),
            "damage_percent": self.get_stat_value(HeroPowerPassiveStatType.DAMAGE_PERCENT),
            "attack_flat": self.get_stat_value(HeroPowerPassiveStatType.ATTACK),
            "max_hp": self.get_stat_value(HeroPowerPassiveStatType.MAX_HP),
            "accuracy": self.get_stat_value(HeroPowerPassiveStatType.ACCURACY),
            "defense": self.get_stat_value(HeroPowerPassiveStatType.DEFENSE),
        }

    def to_dict(self) -> Dict:
        """Serialize to dict for saving."""
        return {
            "stat_levels": {
                stat.value: level
                for stat, level in self.stat_levels.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "HeroPowerPassiveConfig":
        """Deserialize from dict."""
        config = cls()
        stat_data = data.get("stat_levels", {})
        for stat_type in HeroPowerPassiveStatType:
            level = stat_data.get(stat_type.value, 0)
            config.stat_levels[stat_type] = level
        return config


def create_default_passive_config() -> HeroPowerPassiveConfig:
    """Create a default (all zeros) Hero Power passive configuration."""
    return HeroPowerPassiveConfig()


def create_maxed_passive_config() -> HeroPowerPassiveConfig:
    """Create a maxed Hero Power passive configuration (Stage 6 max)."""
    config = HeroPowerPassiveConfig()
    for stat_type in HeroPowerPassiveStatType:
        max_level = HERO_POWER_PASSIVE_STATS[stat_type]["max_level"]
        config.set_stat_level(stat_type, max_level)
    return config


def get_max_passive_stats() -> Dict[str, float]:
    """Get stats if all Hero Power passive stats are maxed."""
    return create_maxed_passive_config().get_all_stats()


# =============================================================================
# DATA CLASSES - ABILITY LINES
# =============================================================================

@dataclass
class HeroPowerLine:
    """A single Hero Power line."""
    slot: int                          # 1-5
    stat_type: HeroPowerStatType
    value: float                       # Actual percentage value
    tier: HeroPowerTier
    is_locked: bool = False

    def format_display(self) -> str:
        """Format the line for display."""
        stat_name = STAT_DISPLAY_NAMES.get(self.stat_type, self.stat_type.value)
        # Flat stats (no % sign): Defense, Max HP, Main Stat
        if self.stat_type in (HeroPowerStatType.DEFENSE, HeroPowerStatType.MAX_HP,
                              HeroPowerStatType.MAIN_STAT_PCT):
            return f"{stat_name}: {self.value:.0f} ({self.tier.value.capitalize()})"
        return f"{stat_name}: {self.value:.1f}% ({self.tier.value.capitalize()})"


def calculate_line_dps_value(
    line: HeroPowerLine,
    calc_dps_func: Optional[Callable] = None,
    get_stats_func: Optional[Callable] = None,
) -> float:
    """
    Calculate the actual DPS contribution of a Hero Power line.

    This calculates real DPS impact by:
    1. Getting current stats
    2. Removing this line's contribution
    3. Calculating baseline DPS
    4. Adding this line's contribution back
    5. Calculating new DPS
    6. Returning the % DPS gain

    Args:
        line: The Hero Power line to evaluate
        calc_dps_func: Callback to calculate DPS from stats dict
        get_stats_func: Callback to get current stats dict

    Returns:
        float: DPS % contribution of this line (e.g., 2.5 means this line adds 2.5% DPS)
    """
    if not calc_dps_func or not get_stats_func:
        # Fallback to arbitrary weight * value
        weight = STAT_DPS_WEIGHTS.get(line.stat_type, 0.5)
        # For flat stats (Main Stat, Defense, Max HP), use different scaling
        if line.stat_type == HeroPowerStatType.MAIN_STAT_PCT:
            # Flat main stat: ~1000 DEX ≈ 1% DPS gain (rough estimate)
            return line.value / 1000.0 * weight
        elif line.stat_type in (HeroPowerStatType.DEFENSE, HeroPowerStatType.MAX_HP):
            # Defensive stats: minimal DPS impact
            return 0.0
        else:
            # Percentage stats: weight * value * 0.01 to get DPS %
            return line.value * weight * 0.01

    # Get the stats key for this stat type
    stats_key = STAT_TO_STATS_KEY.get(line.stat_type)
    if not stats_key:
        # Defensive stat, no DPS impact
        return 0.0

    try:
        # Get current stats
        current_stats = get_stats_func()
        if not current_stats:
            return 0.0

        # Make a copy and remove this line's contribution
        baseline_stats = dict(current_stats)
        current_value = baseline_stats.get(stats_key, 0)
        baseline_stats[stats_key] = current_value - line.value

        # Calculate baseline DPS (without this line)
        baseline_dps = calc_dps_func(baseline_stats)
        if baseline_dps <= 0:
            return 0.0

        # Calculate DPS with this line (current state)
        current_dps = calc_dps_func(current_stats)

        # Return % DPS gain from this line
        dps_gain_pct = ((current_dps / baseline_dps) - 1) * 100
        return max(0, dps_gain_pct)

    except Exception:
        # Fallback to arbitrary weight
        weight = STAT_DPS_WEIGHTS.get(line.stat_type, 0.5)
        return line.value * weight * 0.01


def score_hero_power_line_dps(
    line: HeroPowerLine,
    calc_dps_func: Optional[Callable] = None,
    get_stats_func: Optional[Callable] = None,
    max_dps_contribution: float = 5.0,
) -> float:
    """
    Score a Hero Power line from 0-100 based on actual DPS contribution.

    This is the DPS-based version of score_hero_power_line().
    Score is based on real DPS impact rather than arbitrary weights.

    Args:
        line: The Hero Power line to score
        calc_dps_func: Callback to calculate DPS from stats dict
        get_stats_func: Callback to get current stats dict
        max_dps_contribution: Expected max DPS% a single line can provide (for scaling)

    Returns:
        float: Score from 0-100 (100 = max expected DPS contribution)
    """
    # Get actual DPS contribution
    dps_contribution = calculate_line_dps_value(line, calc_dps_func, get_stats_func)

    # Scale to 0-100 based on expected max contribution
    # A perfect mystic line might give ~3-5% DPS, so use that as 100
    score = (dps_contribution / max_dps_contribution) * 100

    # Ensure score is in 0-100 range
    return max(0, min(100, score))


def score_hero_power_line(
    line: HeroPowerLine,
    calc_dps_func: Optional[Callable] = None,
    get_stats_func: Optional[Callable] = None,
) -> float:
    """
    Score a Hero Power line from 0-100 based on stat type, tier, and value.

    If calc_dps_func and get_stats_func are provided, uses actual DPS calculations.
    Otherwise falls back to arbitrary weight-based scoring.

    Scoring factors (DPS-based mode):
    1. Actual DPS contribution from this line
    2. Scaled to 0-100 where 5% DPS = 100

    Scoring factors (fallback mode):
    1. Stat type weight (some stats are more valuable for DPS)
    2. Tier multiplier (higher tier = better)
    3. Value within tier range (higher value within range = better)

    Returns:
        float: Score from 0-100 (100 = perfect mystic line with best stat)
    """
    # If DPS functions provided, use DPS-based scoring
    if calc_dps_func and get_stats_func:
        return score_hero_power_line_dps(line, calc_dps_func, get_stats_func)

    # Fallback: Use arbitrary weights
    # Get stat weight (how valuable is this stat type?)
    stat_weight = STAT_DPS_WEIGHTS.get(line.stat_type, 0.5)

    # Get tier multiplier
    tier_mult = TIER_SCORE_MULTIPLIERS.get(line.tier, 0.05)

    # Get value score (how good is the value within this tier's range?)
    ranges = HERO_POWER_STAT_RANGES.get(line.tier, {})
    value_score = 0.5  # Default to middle if not in ranges

    if line.stat_type in ranges:
        min_val, max_val = ranges[line.stat_type]
        if max_val > min_val:
            # Normalize value to 0-1 within tier range
            value_score = (line.value - min_val) / (max_val - min_val)
            value_score = max(0, min(1, value_score))  # Clamp to 0-1
    elif line.value > 0:
        # For stats not in range table, use value directly (scaled)
        value_score = min(1.0, line.value / 40)  # 40% = max expected

    # Combine factors:
    # - Max stat weight is 2.5 (DEF_PEN), normalize to ~1
    # - Tier mult is 0-1
    # - Value score is 0-1
    # Result: (stat_weight / 2.5) * tier_mult * value_score * 100

    normalized_stat_weight = stat_weight / 2.5  # Normalize to 0-1
    raw_score = normalized_stat_weight * tier_mult * (0.5 + 0.5 * value_score) * 100

    # Ensure score is in 0-100 range
    return max(0, min(100, raw_score))


def get_line_score_category(score: float) -> Tuple[str, str]:
    """
    Get a category and color for a line score.

    Returns:
        Tuple of (category_name, color_hex)
    """
    if score >= 80:
        return ("Excellent", "#00ff88")  # Green
    elif score >= 60:
        return ("Good", "#7bed9f")       # Light green
    elif score >= 40:
        return ("Average", "#ffd700")    # Yellow
    elif score >= 20:
        return ("Poor", "#ff9f43")       # Orange
    else:
        return ("Trash", "#ff6b6b")      # Red


def score_hero_power_line_for_mode(
    line: HeroPowerLine,
    mode: str,
    calc_dps_func: Optional[Callable] = None,
    get_stats_func: Optional[Callable] = None,
) -> float:
    """
    Score a Hero Power line for a specific combat mode.

    If calc_dps_func and get_stats_func are provided, uses actual DPS calculations.
    The DPS calculation already accounts for combat mode (boss damage applies only to bosses, etc.)

    Args:
        line: The Hero Power line to score
        mode: Combat mode string ("stage", "boss", or "world_boss")
        calc_dps_func: Callback to calculate DPS from stats dict
        get_stats_func: Callback to get current stats dict

    Returns:
        float: Score from 0-100, adjusted for mode-specific stat values
    """
    # If DPS functions provided, use DPS-based scoring
    # The calc_dps_func should already account for combat mode
    if calc_dps_func and get_stats_func:
        dps_contribution = calculate_line_dps_value(line, calc_dps_func, get_stats_func)
        # Scale to 0-100 (5% DPS = 100)
        score = (dps_contribution / 5.0) * 100
        return max(0, min(100, score))

    # Fallback: Use arbitrary weights with mode adjustments
    # Get base stat weight
    base_weight = STAT_DPS_WEIGHTS.get(line.stat_type, 0.5)

    # Apply mode-specific adjustment
    mode_adjustments = MODE_STAT_ADJUSTMENTS.get(mode, {})
    mode_mult = mode_adjustments.get(line.stat_type, 1.0)

    # If mode_mult is 0, stat is worthless in this mode
    if mode_mult == 0:
        return 0.0

    adjusted_weight = base_weight * mode_mult

    # Get tier multiplier
    tier_mult = TIER_SCORE_MULTIPLIERS.get(line.tier, 0.05)

    # Get value score (how good is the value within this tier's range?)
    ranges = HERO_POWER_STAT_RANGES.get(line.tier, {})
    value_score = 0.5

    if line.stat_type in ranges:
        min_val, max_val = ranges[line.stat_type]
        if max_val > min_val:
            value_score = (line.value - min_val) / (max_val - min_val)
            value_score = max(0, min(1, value_score))
    elif line.value > 0:
        value_score = min(1.0, line.value / 40)

    # Normalize adjusted weight (max is now ~3.75 with mode adjustments)
    normalized_weight = adjusted_weight / 3.75
    raw_score = normalized_weight * tier_mult * (0.5 + 0.5 * value_score) * 100

    return max(0, min(100, raw_score))


def rank_all_possible_lines_by_dps(
    calc_dps_func: Optional[Callable] = None,
    get_stats_func: Optional[Callable] = None,
) -> Dict[str, List[Dict]]:
    """
    Rank ALL possible Hero Power lines by DPS contribution for each combat mode.

    This creates a simple lookup table showing the best possible lines you could roll,
    ranked by their actual DPS contribution.

    Returns:
        Dict with keys "stage", "boss", "world_boss", each containing a list of
        dicts with line info sorted by DPS contribution (highest first).

        Each entry: {
            'stat': str,           # e.g., "Def Pen %"
            'tier': str,           # e.g., "Mystic"
            'value_range': str,    # e.g., "14-20%"
            'max_value': float,    # e.g., 20.0
            'dps_contribution': float,  # e.g., 3.5 (% DPS gain)
            'rank': int,           # 1, 2, 3...
        }
    """
    combat_modes = ["stage", "boss", "world_boss"]
    results: Dict[str, List[Dict]] = {mode: [] for mode in combat_modes}

    # Iterate through all tiers (only valuable ones: Mystic, Legendary, Unique)
    valuable_tiers = [HeroPowerTier.MYSTIC, HeroPowerTier.LEGENDARY, HeroPowerTier.UNIQUE]

    # Stats to evaluate (skip defensive stats)
    offensive_stats = [
        HeroPowerStatType.DEF_PEN,
        HeroPowerStatType.BOSS_DAMAGE,
        HeroPowerStatType.DAMAGE,
        HeroPowerStatType.CRIT_DAMAGE,
        HeroPowerStatType.MAX_DMG_MULT,
        HeroPowerStatType.NORMAL_DAMAGE,
        HeroPowerStatType.MAIN_STAT_PCT,
        HeroPowerStatType.CRIT_RATE,
        HeroPowerStatType.ATTACK_PCT,
        HeroPowerStatType.MIN_DMG_MULT,
    ]

    for mode in combat_modes:
        mode_lines = []

        for tier in valuable_tiers:
            tier_ranges = HERO_POWER_STAT_RANGES.get(tier, {})

            for stat_type in offensive_stats:
                if stat_type not in tier_ranges:
                    continue

                min_val, max_val = tier_ranges[stat_type]

                # Create a hypothetical line with max value to calculate DPS
                hypothetical_line = HeroPowerLine(
                    slot=0,
                    stat_type=stat_type,
                    value=max_val,
                    tier=tier,
                    is_locked=False
                )

                # Calculate DPS contribution using mode-specific scoring
                if calc_dps_func and get_stats_func:
                    dps_contribution = calculate_line_dps_value(
                        hypothetical_line, calc_dps_func, get_stats_func
                    )
                else:
                    # Fallback: use weight-based estimation with mode adjustments
                    base_weight = STAT_DPS_WEIGHTS.get(stat_type, 0.5)
                    mode_adjustments = MODE_STAT_ADJUSTMENTS.get(mode, {})
                    mode_mult = mode_adjustments.get(stat_type, 1.0)

                    # For flat stats, use different scaling
                    if stat_type == HeroPowerStatType.MAIN_STAT_PCT:
                        dps_contribution = max_val / 1000.0 * base_weight * mode_mult
                    else:
                        dps_contribution = max_val * base_weight * mode_mult * 0.05

                # Get display name
                stat_name = STAT_DISPLAY_NAMES.get(stat_type, stat_type.value)
                tier_name = tier.value.capitalize()

                # Format value range
                if stat_type == HeroPowerStatType.MAIN_STAT_PCT:
                    value_range = f"{min_val:.0f}-{max_val:.0f}"
                else:
                    value_range = f"{min_val:.0f}-{max_val:.0f}%"

                mode_lines.append({
                    'stat': stat_name,
                    'stat_type': stat_type,
                    'tier': tier_name,
                    'tier_enum': tier,
                    'value_range': value_range,
                    'min_value': min_val,
                    'max_value': max_val,
                    'dps_contribution': dps_contribution,
                })

        # Sort by DPS contribution (highest first)
        mode_lines.sort(key=lambda x: x['dps_contribution'], reverse=True)

        # Add rank
        for i, line in enumerate(mode_lines, 1):
            line['rank'] = i

        results[mode] = mode_lines

    return results


def format_line_ranking_for_display(
    rankings: Dict[str, List[Dict]],
    top_n: int = 15
) -> str:
    """
    Format line rankings for display in the UI.

    Args:
        rankings: Output from rank_all_possible_lines_by_dps()
        top_n: Number of top lines to show per mode

    Returns:
        Formatted string for display
    """
    mode_display = {"stage": "STAGE", "boss": "BOSS", "world_boss": "WORLD BOSS"}

    lines = []
    lines.append("═" * 60)
    lines.append("HERO POWER LINE RANKING BY DPS")
    lines.append("Shows best possible lines to aim for when rerolling")
    lines.append("═" * 60)

    for mode in ["stage", "boss", "world_boss"]:
        lines.append("")
        lines.append(f"▼ {mode_display[mode]} MODE ▼")
        lines.append("-" * 50)
        lines.append(f"{'#':>2} {'Stat':<20} {'Tier':<10} {'Range':<12} {'DPS':>6}")
        lines.append("-" * 50)

        mode_ranking = rankings.get(mode, [])
        for entry in mode_ranking[:top_n]:
            stat_short = entry['stat'][:18]
            lines.append(
                f"{entry['rank']:>2}. {stat_short:<18} {entry['tier']:<10} "
                f"{entry['value_range']:<12} +{entry['dps_contribution']:.2f}%"
            )

    lines.append("")
    lines.append("═" * 60)
    lines.append("TIP: Lock lines with Mystic/Legendary tier in top stats above")
    lines.append("═" * 60)

    return "\n".join(lines)


def score_config_for_mode(
    config: "HeroPowerConfig",
    mode: str,
    calc_dps_func: Optional[Callable] = None,
    get_stats_func: Optional[Callable] = None,
) -> float:
    """
    Score a complete Hero Power config for a specific combat mode.

    If calc_dps_func and get_stats_func are provided, uses actual DPS calculations.

    Args:
        config: HeroPowerConfig with 6 lines
        mode: Combat mode string ("stage", "boss", or "world_boss")
        calc_dps_func: Callback to calculate DPS from stats dict
        get_stats_func: Callback to get current stats dict

    Returns:
        float: Total score (sum of all 6 line scores for this mode)
    """
    total_score = 0.0
    for line in config.lines:
        total_score += score_hero_power_line_for_mode(line, mode, calc_dps_func, get_stats_func)
    return total_score


def calculate_config_total_dps(
    config: "HeroPowerConfig",
    calc_dps_func: Optional[Callable] = None,
    get_stats_func: Optional[Callable] = None,
) -> float:
    """
    Calculate the total DPS contribution of all lines in a Hero Power config.

    Args:
        config: HeroPowerConfig with 6 lines
        calc_dps_func: Callback to calculate DPS from stats dict
        get_stats_func: Callback to get current stats dict

    Returns:
        float: Total DPS % contribution from all lines combined
    """
    if not calc_dps_func or not get_stats_func:
        # Fallback: sum of arbitrary weighted values
        total = 0.0
        for line in config.lines:
            weight = STAT_DPS_WEIGHTS.get(line.stat_type, 0.5)
            total += line.value * weight * 0.01
        return total

    # Calculate total DPS contribution from all lines
    total_contribution = 0.0
    for line in config.lines:
        total_contribution += calculate_line_dps_value(line, calc_dps_func, get_stats_func)
    return total_contribution


@dataclass
class HeroPowerConfig:
    """Complete 6-line Hero Power configuration."""
    lines: List[HeroPowerLine] = field(default_factory=list)
    preset_name: str = "Default"

    def __post_init__(self):
        # Initialize 6 empty lines if not provided
        if not self.lines:
            self.lines = [
                HeroPowerLine(
                    slot=i + 1,
                    stat_type=HeroPowerStatType.DAMAGE,
                    value=0.0,
                    tier=HeroPowerTier.COMMON
                )
                for i in range(6)
            ]
        # Upgrade existing 5-line configs to 6 lines
        elif len(self.lines) == 5:
            self.lines.append(HeroPowerLine(
                slot=6,
                stat_type=HeroPowerStatType.DAMAGE,
                value=0.0,
                tier=HeroPowerTier.COMMON
            ))

    def get_locked_count(self) -> int:
        """Count locked lines."""
        return sum(1 for line in self.lines if line.is_locked)

    def get_reroll_cost(self) -> int:
        """Get medal cost for one reroll."""
        return HERO_POWER_REROLL_COSTS.get(self.get_locked_count(), 258)

    def get_stat_total(self, stat_type: HeroPowerStatType) -> float:
        """Get total value for a specific stat type."""
        return sum(line.value for line in self.lines if line.stat_type == stat_type)

    def get_all_stats(self) -> Dict[HeroPowerStatType, float]:
        """Get totals for all stats."""
        totals: Dict[HeroPowerStatType, float] = {}
        for line in self.lines:
            if line.stat_type not in totals:
                totals[line.stat_type] = 0.0
            totals[line.stat_type] += line.value
        return totals

    def count_lines_meeting_criteria(
        self,
        stat_types: List[HeroPowerStatType],
        min_tier: HeroPowerTier
    ) -> int:
        """Count lines that have a matching stat type at or above min tier."""
        tier_order = [
            HeroPowerTier.COMMON, HeroPowerTier.RARE, HeroPowerTier.EPIC,
            HeroPowerTier.UNIQUE, HeroPowerTier.LEGENDARY, HeroPowerTier.MYSTIC
        ]
        min_tier_idx = tier_order.index(min_tier)

        count = 0
        for line in self.lines:
            line_tier_idx = tier_order.index(line.tier)
            if line.stat_type in stat_types and line_tier_idx >= min_tier_idx:
                count += 1
        return count


@dataclass
class SimulationTarget:
    """Target configuration for simulation."""
    # For custom stat targets: list of (stat_type, required_count)
    # e.g., [(DEF_PEN, 2), (DAMAGE, 2)] = need 2x DEF_PEN + 2x Damage lines
    stat_requirements: List[Tuple[HeroPowerStatType, int]] = field(default_factory=list)

    # OR for DPS improvement targets
    dps_improvement_pct: Optional[float] = None  # e.g., 5.0 = improve by 5%

    # Minimum tier requirement for counting
    min_tier: HeroPowerTier = HeroPowerTier.LEGENDARY

    def is_dps_mode(self) -> bool:
        """Check if this is a DPS improvement target."""
        return self.dps_improvement_pct is not None


@dataclass
class HeroPowerSimulationResult:
    """Results from Monte Carlo simulation."""
    iterations: int
    target: SimulationTarget

    # Statistics
    success_rate: float              # % of simulations hitting target
    expected_rerolls: float          # Average rerolls needed
    expected_medals: float           # Average medals spent

    median_rerolls: int
    percentile_90_rerolls: int       # 90th percentile (worst 10%)

    # Distribution data (for visualization)
    reroll_distribution: List[int] = field(default_factory=list)

    # Whether simulation was capped
    capped_iterations: int = 0  # How many hit max_rerolls


# =============================================================================
# SIMULATION FUNCTIONS
# =============================================================================

def roll_hero_power_tier(level_config: Optional[HeroPowerLevelConfig] = None) -> HeroPowerTier:
    """Roll a random tier based on probabilities.

    Args:
        level_config: Optional level config with custom tier rates.
                     If None, uses default HERO_POWER_TIER_RATES.
    """
    if level_config:
        tier_rates = level_config.get_tier_rates()
    else:
        tier_rates = HERO_POWER_TIER_RATES

    roll = random.random()
    cumulative = 0.0

    for tier, prob in tier_rates.items():
        cumulative += prob
        if roll <= cumulative:
            return tier

    return HeroPowerTier.COMMON


def roll_hero_power_stat(tier: HeroPowerTier) -> HeroPowerStatType:
    """Roll a random stat type based on tier probabilities."""
    probs = STAT_PROBABILITIES.get(tier, DEFAULT_STAT_PROBS)

    roll = random.random()
    cumulative = 0.0

    for stat_type, prob in probs.items():
        cumulative += prob
        if roll <= cumulative:
            return stat_type

    # Fallback to random from available stats
    return random.choice(list(HeroPowerStatType))


def roll_hero_power_value(tier: HeroPowerTier, stat_type: HeroPowerStatType) -> float:
    """Roll a random value within the tier's range for the stat."""
    ranges = HERO_POWER_STAT_RANGES.get(tier, {})
    if stat_type in ranges:
        min_val, max_val = ranges[stat_type]
        return round(random.uniform(min_val, max_val), 1)

    # Fallback for stats not in range table
    return 0.0


def simulate_hero_power_reroll(
    config: HeroPowerConfig,
    level_config: Optional[HeroPowerLevelConfig] = None
) -> HeroPowerConfig:
    """Simulate one reroll of unlocked lines.

    Args:
        config: Current Hero Power configuration
        level_config: Optional level config with custom tier rates.
    """
    new_lines = []

    for line in config.lines:
        if line.is_locked:
            new_lines.append(copy.copy(line))
        else:
            # Roll new tier (using level config if provided)
            tier = roll_hero_power_tier(level_config)

            # Roll stat type
            stat_type = roll_hero_power_stat(tier)

            # Roll value
            value = roll_hero_power_value(tier, stat_type)

            new_lines.append(HeroPowerLine(
                slot=line.slot,
                stat_type=stat_type,
                value=value,
                tier=tier,
                is_locked=False
            ))

    return HeroPowerConfig(lines=new_lines, preset_name=config.preset_name)


def check_target_achieved(config: HeroPowerConfig, target: SimulationTarget) -> bool:
    """Check if current config meets the simulation target."""
    if target.is_dps_mode():
        # DPS mode is checked externally with actual damage calc
        return False

    # Custom stat target mode
    for stat_type, required_count in target.stat_requirements:
        actual_count = config.count_lines_meeting_criteria([stat_type], target.min_tier)
        if actual_count < required_count:
            return False

    return True


def run_custom_target_simulation(
    target: SimulationTarget,
    locked_lines: List[int] = None,  # slot numbers to lock (1-6)
    iterations: int = 10000,
    max_rerolls: int = 50000,
    level_config: Optional[HeroPowerLevelConfig] = None
) -> HeroPowerSimulationResult:
    """
    Simulate rerolling until achieving specific stat targets.

    Args:
        target: SimulationTarget with stat requirements or DPS target
        locked_lines: List of slot numbers to lock (1-6)
        iterations: Number of simulation runs
        max_rerolls: Max rerolls per simulation before capping
        level_config: Optional level config for tier rates and costs

    Example target: 2x DEF_PEN + 2x DAMAGE at Legendary+ tier
    """
    reroll_counts = []
    successes = 0
    capped = 0

    for _ in range(iterations):
        # Fresh config with specified locks
        config = HeroPowerConfig()
        if locked_lines:
            for line in config.lines:
                if line.slot in locked_lines:
                    line.is_locked = True

        rerolls = 0

        while rerolls < max_rerolls:
            # Check if target achieved
            if check_target_achieved(config, target):
                successes += 1
                break

            # Simulate reroll of unlocked lines (using level config)
            config = simulate_hero_power_reroll(config, level_config)
            rerolls += 1
        else:
            # Hit max_rerolls without success
            capped += 1

        reroll_counts.append(rerolls)

    # Calculate statistics
    sorted_counts = sorted(reroll_counts)
    median_idx = len(sorted_counts) // 2
    p90_idx = int(len(sorted_counts) * 0.9)

    # Get cost per reroll from level config if provided
    num_locked = len(locked_lines or [])
    if level_config:
        cost_per_reroll = level_config.get_reroll_cost(num_locked)
    else:
        cost_per_reroll = HERO_POWER_REROLL_COSTS.get(num_locked, 86)

    return HeroPowerSimulationResult(
        iterations=iterations,
        target=target,
        success_rate=successes / iterations if iterations > 0 else 0,
        expected_rerolls=sum(reroll_counts) / len(reroll_counts) if reroll_counts else 0,
        expected_medals=(sum(reroll_counts) / len(reroll_counts) * cost_per_reroll) if reroll_counts else 0,
        median_rerolls=sorted_counts[median_idx] if sorted_counts else 0,
        percentile_90_rerolls=sorted_counts[p90_idx] if sorted_counts else 0,
        reroll_distribution=reroll_counts,
        capped_iterations=capped,
    )


# =============================================================================
# EFFICIENCY-BASED LOCK/REROLL OPTIMIZATION
# =============================================================================

def calculate_probability_of_improvement(
    current_line_dps: float,
    level_config: HeroPowerLevelConfig,
    calc_dps_func: Optional[Callable] = None,
    get_stats_func: Optional[Callable] = None,
) -> Tuple[float, float]:
    """
    Calculate probability and expected value of rolling a line better than current.

    This enumerates all possible rolls (tier × stat × value samples) and calculates
    what fraction would give better DPS than the current line.

    Args:
        current_line_dps: DPS contribution (%) of the current line
        level_config: HeroPowerLevelConfig with tier rates
        calc_dps_func: Callback to calculate DPS from stats dict
        get_stats_func: Callback to get current stats dict

    Returns:
        Tuple of (probability_of_improvement, expected_dps_if_better)
    """
    tier_rates = level_config.get_tier_rates()

    total_prob_better = 0.0
    weighted_dps_sum = 0.0

    for tier, tier_prob in tier_rates.items():
        stat_probs = STAT_PROBABILITIES.get(tier, DEFAULT_STAT_PROBS)

        for stat_type, stat_prob in stat_probs.items():
            ranges = HERO_POWER_STAT_RANGES.get(tier, {})
            if stat_type not in ranges:
                continue

            min_val, max_val = ranges[stat_type]
            joint_prob = tier_prob * stat_prob

            # Sample 3 points in the range to estimate DPS distribution
            sample_values = [min_val, (min_val + max_val) / 2, max_val]
            for val in sample_values:
                sample_line = HeroPowerLine(
                    slot=0,
                    stat_type=stat_type,
                    value=val,
                    tier=tier,
                    is_locked=False
                )
                sample_dps = calculate_line_dps_value(
                    sample_line, calc_dps_func, get_stats_func
                )

                if sample_dps > current_line_dps:
                    # This sample point is better - count it
                    prob_this_point = joint_prob / len(sample_values)
                    total_prob_better += prob_this_point
                    weighted_dps_sum += prob_this_point * sample_dps

    # Calculate expected DPS if we roll better
    expected_dps_if_better = (
        weighted_dps_sum / total_prob_better if total_prob_better > 0 else 0
    )

    return (total_prob_better, expected_dps_if_better)


def calculate_reroll_efficiency(
    current_line_dps: float,
    num_already_locked: int,
    level_config: HeroPowerLevelConfig,
    calc_dps_func: Optional[Callable] = None,
    get_stats_func: Optional[Callable] = None,
) -> Dict:
    """
    Calculate the efficiency of rerolling vs locking a line.

    The decision to lock or reroll depends on:
    1. Probability of rolling something better
    2. Expected DPS gain if we do roll better
    3. Cost per reroll (increases with more locked lines)

    The efficiency metric is: Expected_DPS_Gain / Cost_Per_Reroll

    The threshold for "worth rerolling" DECREASES as more lines are locked,
    because higher cost means we're more willing to accept mediocre lines.

    Args:
        current_line_dps: DPS contribution (%) of the current line
        num_already_locked: Number of lines already decided to lock
        level_config: HeroPowerLevelConfig with tier rates and costs
        calc_dps_func: Callback to calculate DPS from stats dict
        get_stats_func: Callback to get current stats dict

    Returns:
        Dict with:
        - probability_of_improvement: float (0-1)
        - expected_dps_gain: float (% DPS improvement per reroll)
        - expected_dps_if_better: float (% DPS if we do roll better)
        - cost_per_reroll: int (medals)
        - efficiency: float (expected DPS% gain per 1000 medals)
        - threshold: float (efficiency threshold for reroll decision)
        - recommendation: str ("LOCK" or "REROLL")
        - reasoning: str (human-readable explanation)
    """
    # Get probability and expected value of improvement
    p_better, expected_dps_if_better = calculate_probability_of_improvement(
        current_line_dps, level_config, calc_dps_func, get_stats_func
    )

    # Calculate cost with current number of locks
    cost_per_reroll = level_config.get_reroll_cost(num_already_locked)

    # Expected DPS gain per reroll = P(better) × (E[DPS|better] - current)
    if p_better > 0 and expected_dps_if_better > current_line_dps:
        expected_dps_gain = p_better * (expected_dps_if_better - current_line_dps)
    else:
        expected_dps_gain = 0.0

    # Efficiency = expected DPS gain per 1000 medals
    if cost_per_reroll > 0:
        efficiency = (expected_dps_gain / cost_per_reroll) * 1000
    else:
        efficiency = float('inf') if expected_dps_gain > 0 else 0

    # Dynamic threshold: decreases as cost increases
    # Base threshold: 0.05% DPS per 1000 medals is "worth rerolling"
    # Scale inversely with cost (higher cost = lower threshold = more willing to lock)
    base_threshold = 0.05
    base_cost = level_config.base_cost
    cost_ratio = base_cost / cost_per_reroll if cost_per_reroll > 0 else 1.0
    threshold = base_threshold * cost_ratio

    # Decision: efficiency > threshold means "worth rerolling"
    should_reroll = efficiency > threshold

    return {
        'probability_of_improvement': p_better,
        'expected_dps_gain': expected_dps_gain,
        'expected_dps_if_better': expected_dps_if_better,
        'cost_per_reroll': cost_per_reroll,
        'efficiency': efficiency,
        'threshold': threshold,
        'recommendation': "REROLL" if should_reroll else "LOCK",
        'reasoning': (
            f"P(better)={p_better:.1%}, E[gain]={expected_dps_gain:.3f}%/roll, "
            f"Cost={cost_per_reroll}/roll, Eff={efficiency:.4f} vs thresh={threshold:.4f}"
        ),
    }


def analyze_lock_strategy(
    config: HeroPowerConfig,
    level_config: HeroPowerLevelConfig,
    calc_dps_func: Optional[Callable] = None,
    get_stats_func: Optional[Callable] = None,
) -> Dict:
    """
    Analyze the optimal lock/reroll strategy for a Hero Power configuration.

    Uses a greedy approach:
    1. Sort lines by DPS value (best first)
    2. For each line (best to worst), calculate reroll efficiency
    3. Lock lines where efficiency < threshold (hard to improve)
    4. Mark remaining lines for reroll

    The key insight: As we lock more lines, the cost per reroll increases,
    so the threshold for "worth rerolling" decreases. This naturally means:
    - Good lines get locked first (low efficiency = hard to beat)
    - Mediocre lines might also get locked if we already have many locks
    - Only truly bad lines get rerolled

    Args:
        config: HeroPowerConfig with 6 lines to analyze
        level_config: HeroPowerLevelConfig with tier rates and costs
        calc_dps_func: Callback to calculate DPS from stats dict
        get_stats_func: Callback to get current stats dict

    Returns:
        Dict with:
        - lines_to_lock: List of slot numbers (0-5) to lock
        - lines_to_reroll: List of slot numbers (0-5) to reroll
        - expected_rerolls: Estimated number of rerolls needed
        - expected_total_cost: Total medals expected to spend
        - expected_dps_gain: Expected % DPS improvement
        - efficiency_analysis: List of per-line analysis dicts
        - cost_per_reroll: Medal cost per reroll with final lock count
    """
    # Calculate DPS value for each line
    line_analysis = []
    for line in config.lines:
        dps_value = calculate_line_dps_value(line, calc_dps_func, get_stats_func)
        stat_name = STAT_DISPLAY_NAMES.get(line.stat_type, str(line.stat_type.value))
        line_analysis.append({
            'slot': line.slot,
            'line': line,
            'dps_value': dps_value,
            'stat_name': stat_name,
            'tier': line.tier.value,
            'value': line.value,
            'efficiency_result': None,  # Will be filled in
        })

    # Sort by DPS value (best first) - these are candidates for locking
    line_analysis.sort(key=lambda x: x['dps_value'], reverse=True)

    # Iteratively decide which lines to lock
    locked_slots = []
    reroll_slots = []

    for la in line_analysis:
        # Calculate efficiency assuming we've already locked the better lines
        num_locked = len(locked_slots)
        efficiency_result = calculate_reroll_efficiency(
            la['dps_value'],
            num_locked,
            level_config,
            calc_dps_func,
            get_stats_func
        )
        la['efficiency_result'] = efficiency_result

        if efficiency_result['recommendation'] == "LOCK":
            locked_slots.append(la['slot'])
        else:
            reroll_slots.append(la['slot'])

    # Calculate expected cost and DPS gain for this strategy
    final_cost_per_reroll = level_config.get_reroll_cost(len(locked_slots))

    # Sum expected DPS gains from rerolling
    total_expected_gain = sum(
        la['efficiency_result']['expected_dps_gain']
        for la in line_analysis
        if la['slot'] in reroll_slots
    )

    # Estimate rerolls needed
    # P(any line improves) = 1 - product(1 - P(line i improves))
    if reroll_slots:
        p_improvements = [
            la['efficiency_result']['probability_of_improvement']
            for la in line_analysis
            if la['slot'] in reroll_slots
        ]
        # Calculate P(at least one improvement)
        p_no_improvement = 1.0
        for p in p_improvements:
            p_no_improvement *= (1 - p)
        p_any_improvement = 1 - p_no_improvement

        if p_any_improvement > 0:
            # Expected rerolls to get one improvement, times number of lines to improve
            expected_rerolls = (1 / p_any_improvement) * len(reroll_slots)
        else:
            expected_rerolls = 100  # Fallback
    else:
        expected_rerolls = 0
        p_any_improvement = 0

    expected_cost = expected_rerolls * final_cost_per_reroll

    return {
        'lines_to_lock': locked_slots,
        'lines_to_reroll': reroll_slots,
        'expected_rerolls': expected_rerolls,
        'expected_total_cost': expected_cost,
        'expected_dps_gain': total_expected_gain,
        'efficiency_analysis': line_analysis,
        'cost_per_reroll': final_cost_per_reroll,
        'p_any_improvement': p_any_improvement if reroll_slots else 0,
    }


# =============================================================================
# MAIN (Testing)
# =============================================================================

if __name__ == "__main__":
    print("MapleStory Idle - Hero Power System Module")
    print("=" * 60)

    # Test Passive Stats
    print("\n--- PASSIVE STATS (Stage 6) ---")
    print("-" * 40)

    # Test default config
    print("\nDefault Config (all zeros):")
    config = create_default_passive_config()
    print(f"  Stats: {config.get_all_stats()}")

    # Test maxed config
    print("\nMaxed Config (Stage 6 max):")
    max_stats = get_max_passive_stats()
    for key, value in max_stats.items():
        if "percent" in key:
            print(f"  {key}: {value:.1f}%")
        else:
            print(f"  {key}: {value:,.0f}")

    # Test specific values from user data (Stage 6)
    print("\nValidation (User Data - Stage 6 Max):")
    print(f"  Main Stat (60/60): {max_stats['main_stat_flat']:,.0f} (expected: 1,650)")
    print(f"  Damage % (60/60): {max_stats['damage_percent']:.1f}% (expected: 45%)")
    print(f"  Attack (60/60): {max_stats['attack_flat']:,.0f} (expected: 6,225)")
    print(f"  Max HP (60/60): {max_stats['max_hp']:,.0f} (expected: 124,500)")
    print(f"  Accuracy (20/20): {max_stats['accuracy']:.0f} (expected: 45)")
    print(f"  Defense (60/60): {max_stats['defense']:,.0f} (expected: 5,625)")

    # Test partial levels (user's current: Defense 48/60)
    print("\nPartial Level Test (Defense 48/60):")
    partial_config = HeroPowerPassiveConfig()
    partial_config.set_stat_level(HeroPowerPassiveStatType.DEFENSE, 48)
    print(f"  Defense at 48/60: {partial_config.get_stat_value(HeroPowerPassiveStatType.DEFENSE):,.0f}")
    print(f"  Expected: {48 * 93.75:,.0f}")

    # Test serialization
    print("\nSerialization Test:")
    test_config = HeroPowerPassiveConfig()
    test_config.set_stat_level(HeroPowerPassiveStatType.MAIN_STAT, 60)
    test_config.set_stat_level(HeroPowerPassiveStatType.DAMAGE_PERCENT, 60)
    test_config.set_stat_level(HeroPowerPassiveStatType.DEFENSE, 48)
    data = test_config.to_dict()
    restored = HeroPowerPassiveConfig.from_dict(data)
    print(f"  Original Main Stat: {test_config.get_stat_level(HeroPowerPassiveStatType.MAIN_STAT)}")
    print(f"  Restored Main Stat: {restored.get_stat_level(HeroPowerPassiveStatType.MAIN_STAT)}")
    print(f"  Match: {'YES' if test_config.get_stat_level(HeroPowerPassiveStatType.MAIN_STAT) == restored.get_stat_level(HeroPowerPassiveStatType.MAIN_STAT) else 'NO'}")
