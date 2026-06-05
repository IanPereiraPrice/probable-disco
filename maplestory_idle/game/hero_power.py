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

# Import standardized stat names and utilities
from stat_names import (
    get_display_name,
    DAMAGE_PCT, BOSS_DAMAGE, NORMAL_DAMAGE, DEF_PEN,
    MAX_DMG_MULT, MIN_DMG_MULT, CRIT_RATE,
    MAIN_STAT_FLAT, ATTACK_FLAT, ATTACK_SPEED, MAX_HP, ACCURACY
)


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
    """Available stats for Hero Power ability lines.

    From https://idle.maplestorywiki.net/w/Ability
    Note: Crit Damage and Defense are NOT available as ability stats.
    """
    DAMAGE = "damage"
    BOSS_DAMAGE = "boss_damage"
    NORMAL_DAMAGE = "normal_damage"
    DEF_PEN = "def_pen"
    MAX_DMG_MULT = "max_dmg_mult"
    MIN_DMG_MULT = "min_dmg_mult"
    CRIT_RATE = "crit_rate"
    MAIN_STAT_FLAT = "main_stat_flat"  # Flat main stat (e.g., +2000 DEX) - NOT percentage
    ATTACK_SPEED = "attack_speed"  # Attack Speed %
    MAX_HP = "max_hp"


# Display names for UI - use stat_names.py definitions
STAT_DISPLAY_NAMES: Dict[HeroPowerStatType, str] = {
    HeroPowerStatType.DAMAGE: get_display_name("damage_pct"),
    HeroPowerStatType.BOSS_DAMAGE: get_display_name("boss_damage"),
    HeroPowerStatType.NORMAL_DAMAGE: get_display_name("normal_damage"),
    HeroPowerStatType.DEF_PEN: get_display_name("def_pen"),
    HeroPowerStatType.MAX_DMG_MULT: get_display_name("max_dmg_mult"),
    HeroPowerStatType.MIN_DMG_MULT: get_display_name("min_dmg_mult"),
    HeroPowerStatType.CRIT_RATE: get_display_name("crit_rate"),
    HeroPowerStatType.MAIN_STAT_FLAT: get_display_name("main_stat_flat"),
    HeroPowerStatType.ATTACK_SPEED: get_display_name("attack_speed"),
    HeroPowerStatType.MAX_HP: get_display_name("max_hp"),
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

# Valuable stats - these are the stats worth targeting for DPS
# Note: Best offensive stats (Boss Dmg 28-40%, Def Pen 14-20%) are only at Rare tier!
VALUABLE_STATS: List[HeroPowerStatType] = [
    HeroPowerStatType.BOSS_DAMAGE,      # Rare: 28-40%, Epic: 18-25%
    HeroPowerStatType.DEF_PEN,          # Rare: 14-20%, Epic: 8-12%
    HeroPowerStatType.NORMAL_DAMAGE,    # Rare: 28-40%, Epic: 18-25%
    HeroPowerStatType.DAMAGE,           # Legendary: 28-40%, Unique: 18-25%, Epic: 12-15%
    HeroPowerStatType.MAX_DMG_MULT,     # Unique: 28-40%, Epic: 18-25%
    HeroPowerStatType.MIN_DMG_MULT,     # Unique: 28-40%, Epic: 18-25%
    HeroPowerStatType.CRIT_RATE,        # Unique: 15-20%, Epic: 10-14%
    HeroPowerStatType.ATTACK_SPEED,     # Epic: 15-20%, Rare: 10-14%
]

# Mapping from HeroPowerStatType to the stats dict key used in DPS calculation
STAT_TO_STATS_KEY: Dict[HeroPowerStatType, str] = {
    HeroPowerStatType.DAMAGE: DAMAGE_PCT,
    HeroPowerStatType.BOSS_DAMAGE: BOSS_DAMAGE,
    HeroPowerStatType.NORMAL_DAMAGE: NORMAL_DAMAGE,
    HeroPowerStatType.DEF_PEN: DEF_PEN,
    HeroPowerStatType.MAX_DMG_MULT: MAX_DMG_MULT,
    HeroPowerStatType.MIN_DMG_MULT: MIN_DMG_MULT,
    HeroPowerStatType.CRIT_RATE: CRIT_RATE,
    HeroPowerStatType.MAIN_STAT_FLAT: MAIN_STAT_FLAT,  # Generic - resolved by job class in DPS calc
    HeroPowerStatType.ATTACK_SPEED: ATTACK_SPEED,
    HeroPowerStatType.MAX_HP: None,   # Defensive, no DPS impact
}

# Tier multiplier for scoring
# Note: This is DEPRECATED - tier doesn't correlate with DPS value!
# Best offensive stats (Boss Dmg 28-40%, Def Pen 14-20%) are at RARE tier
# Mystic only has Main Stat and HP - no offensive stats
# Use DPS-based scoring instead of tier-based scoring
TIER_SCORE_MULTIPLIERS: Dict[HeroPowerTier, float] = {
    HeroPowerTier.RARE: 1.0,      # Best offensive stats (Boss/Def Pen/Normal)
    HeroPowerTier.EPIC: 0.8,      # Good offensive stats
    HeroPowerTier.UNIQUE: 0.6,    # Dmg%, Min/Max Dmg, Crit Rate
    HeroPowerTier.LEGENDARY: 0.4, # Dmg%, Main Stat, HP
    HeroPowerTier.MYSTIC: 0.3,    # Only Main Stat and HP
    HeroPowerTier.COMMON: 0.1,    # Low values
}

# DEPRECATED: Fallback DPS weights for when actual DPS calc is not available
# These are rough estimates - use actual DPS calculation instead when possible
# Note: The actual DPS value varies greatly depending on current stats
#
# IMPORTANT: Attack speed has a breakpoint system (0%, 33%, 66%, 100%, 133%)
# AS value is HIGHLY context-dependent:
#   - 0% DPS if no breakpoint is crossed
#   - 20-30% DPS if a breakpoint IS crossed
# The weight below is meaningless without knowing current AS - always use DPS calc!
STAT_DPS_WEIGHTS: Dict[HeroPowerStatType, float] = {
    HeroPowerStatType.DEF_PEN: 2.0,        # Very valuable, multiplicative with other stats
    HeroPowerStatType.BOSS_DAMAGE: 1.5,    # Strong in boss modes
    HeroPowerStatType.NORMAL_DAMAGE: 1.2,  # Strong in stage mode
    HeroPowerStatType.DAMAGE: 1.0,         # Always useful
    HeroPowerStatType.MAX_DMG_MULT: 1.0,   # Helps with damage variance
    HeroPowerStatType.MIN_DMG_MULT: 0.8,   # Less impactful than max
    HeroPowerStatType.CRIT_RATE: 0.7,      # Depends on current crit rate
    HeroPowerStatType.ATTACK_SPEED: 0.0,   # CONTEXT-DEPENDENT: use DPS calc (see breakpoint note above)
    HeroPowerStatType.MAIN_STAT_FLAT: 0.3, # Small impact (flat stat)
    HeroPowerStatType.MAX_HP: 0.0,         # No DPS impact
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


# Stat probabilities when rolling - based on available stats at each tier
# From https://idle.maplestorywiki.net/w/Ability
# Probabilities are estimates - wiki doesn't provide exact stat weights
STAT_PROBABILITIES: Dict[HeroPowerTier, Dict[HeroPowerStatType, float]] = {
    # Mystic: Only Main Stat and Max HP (+ utility stats we don't track)
    HeroPowerTier.MYSTIC: {
        HeroPowerStatType.MAIN_STAT_FLAT: 0.50,
        HeroPowerStatType.MAX_HP: 0.50,
        # Other stats (Accuracy, Evasion, MP Recovery, Max MP) not tracked for DPS
    },
    # Legendary: Main Stat, Max HP, Damage%
    HeroPowerTier.LEGENDARY: {
        HeroPowerStatType.MAIN_STAT_FLAT: 0.35,
        HeroPowerStatType.MAX_HP: 0.35,
        HeroPowerStatType.DAMAGE: 0.30,
    },
    # Unique: Main Stat, Max HP, Damage%, Min/Max Dmg Mult, Crit Rate
    HeroPowerTier.UNIQUE: {
        HeroPowerStatType.MAIN_STAT_FLAT: 0.20,
        HeroPowerStatType.MAX_HP: 0.20,
        HeroPowerStatType.DAMAGE: 0.20,
        HeroPowerStatType.MAX_DMG_MULT: 0.15,
        HeroPowerStatType.MIN_DMG_MULT: 0.15,
        HeroPowerStatType.CRIT_RATE: 0.10,
    },
    # Epic: Many offensive stats available
    HeroPowerTier.EPIC: {
        HeroPowerStatType.MAIN_STAT_FLAT: 0.12,
        HeroPowerStatType.MAX_HP: 0.12,
        HeroPowerStatType.DAMAGE: 0.12,
        HeroPowerStatType.MAX_DMG_MULT: 0.10,
        HeroPowerStatType.MIN_DMG_MULT: 0.10,
        HeroPowerStatType.CRIT_RATE: 0.10,
        HeroPowerStatType.ATTACK_SPEED: 0.10,
        HeroPowerStatType.DEF_PEN: 0.08,
        HeroPowerStatType.BOSS_DAMAGE: 0.08,
        HeroPowerStatType.NORMAL_DAMAGE: 0.08,
    },
    # Rare: BEST offensive stats (Def Pen 14-20%, Boss/Normal 28-40%)
    HeroPowerTier.RARE: {
        HeroPowerStatType.MAIN_STAT_FLAT: 0.10,
        HeroPowerStatType.MAX_HP: 0.10,
        HeroPowerStatType.DAMAGE: 0.10,
        HeroPowerStatType.MAX_DMG_MULT: 0.10,
        HeroPowerStatType.MIN_DMG_MULT: 0.10,
        HeroPowerStatType.CRIT_RATE: 0.10,
        HeroPowerStatType.ATTACK_SPEED: 0.10,
        HeroPowerStatType.DEF_PEN: 0.10,
        HeroPowerStatType.BOSS_DAMAGE: 0.10,
        HeroPowerStatType.NORMAL_DAMAGE: 0.10,
    },
    # Common: Basic stats
    HeroPowerTier.COMMON: {
        HeroPowerStatType.MAIN_STAT_FLAT: 0.15,
        HeroPowerStatType.MAX_HP: 0.15,
        HeroPowerStatType.DAMAGE: 0.15,
        HeroPowerStatType.MAX_DMG_MULT: 0.15,
        HeroPowerStatType.MIN_DMG_MULT: 0.15,
        HeroPowerStatType.CRIT_RATE: 0.15,
        HeroPowerStatType.ATTACK_SPEED: 0.10,
    },
}

# Default stat probabilities (fallback if tier not in STAT_PROBABILITIES)
DEFAULT_STAT_PROBS: Dict[HeroPowerStatType, float] = {
    HeroPowerStatType.MAIN_STAT_FLAT: 0.15,
    HeroPowerStatType.MAX_HP: 0.15,
    HeroPowerStatType.DAMAGE: 0.15,
    HeroPowerStatType.MAX_DMG_MULT: 0.10,
    HeroPowerStatType.MIN_DMG_MULT: 0.10,
    HeroPowerStatType.CRIT_RATE: 0.10,
    HeroPowerStatType.ATTACK_SPEED: 0.10,
    HeroPowerStatType.DEF_PEN: 0.05,
    HeroPowerStatType.BOSS_DAMAGE: 0.05,
    HeroPowerStatType.NORMAL_DAMAGE: 0.05,
}

# Stat value ranges by tier (min, max)
# From https://idle.maplestorywiki.net/w/Ability
# Note: Not all stats are available at all tiers - N/A means stat cannot roll at that tier
# Key insight: Best offensive stats (Boss Dmg, Def Pen) are only at LOWER tiers (Rare/Epic)!
HERO_POWER_STAT_RANGES: Dict[HeroPowerTier, Dict[HeroPowerStatType, Tuple[float, float]]] = {
    # Mystic: Only defensive/utility stats - NO offensive stats!
    HeroPowerTier.MYSTIC: {
        HeroPowerStatType.MAIN_STAT_FLAT: (1500, 2500),
        HeroPowerStatType.MAX_HP: (70000, 115000),
        # No offensive stats available at Mystic tier
    },
    # Legendary: Main stat, HP, Damage%, but NO def pen/boss dmg/crit rate/attack speed
    HeroPowerTier.LEGENDARY: {
        HeroPowerStatType.MAIN_STAT_FLAT: (800, 1200),
        HeroPowerStatType.MAX_HP: (35000, 65000),
        HeroPowerStatType.DAMAGE: (28.0, 40.0),
        # No def pen, boss dmg, normal dmg, crit rate, attack speed at this tier
    },
    # Unique: Damage%, Min/Max Dmg Mult, Crit Rate
    HeroPowerTier.UNIQUE: {
        HeroPowerStatType.MAIN_STAT_FLAT: (400, 700),
        HeroPowerStatType.MAX_HP: (15000, 30000),
        HeroPowerStatType.DAMAGE: (18.0, 25.0),
        HeroPowerStatType.MAX_DMG_MULT: (28.0, 40.0),
        HeroPowerStatType.MIN_DMG_MULT: (28.0, 40.0),
        HeroPowerStatType.CRIT_RATE: (15.0, 20.0),
        # No def pen, boss dmg, normal dmg, attack speed at this tier
    },
    # Epic: Attack Speed, Crit Rate, Def Pen, Boss/Normal Dmg become available here
    HeroPowerTier.EPIC: {
        HeroPowerStatType.MAIN_STAT_FLAT: (200, 300),
        HeroPowerStatType.MAX_HP: (4500, 9000),
        HeroPowerStatType.DAMAGE: (12.0, 15.0),
        HeroPowerStatType.MAX_DMG_MULT: (18.0, 25.0),
        HeroPowerStatType.MIN_DMG_MULT: (18.0, 25.0),
        HeroPowerStatType.CRIT_RATE: (10.0, 14.0),
        HeroPowerStatType.ATTACK_SPEED: (15.0, 20.0),
        HeroPowerStatType.DEF_PEN: (8.0, 12.0),
        HeroPowerStatType.BOSS_DAMAGE: (18.0, 25.0),
        HeroPowerStatType.NORMAL_DAMAGE: (18.0, 25.0),
    },
    # Rare: BEST tier for Def Pen (14-20%) and Boss/Normal Dmg (28-40%)!
    HeroPowerTier.RARE: {
        HeroPowerStatType.MAIN_STAT_FLAT: (100, 150),
        HeroPowerStatType.MAX_HP: (1800, 3000),
        HeroPowerStatType.DAMAGE: (7.0, 10.0),
        HeroPowerStatType.MAX_DMG_MULT: (12.0, 15.0),
        HeroPowerStatType.MIN_DMG_MULT: (12.0, 15.0),
        HeroPowerStatType.CRIT_RATE: (7.0, 9.0),
        HeroPowerStatType.ATTACK_SPEED: (10.0, 14.0),
        HeroPowerStatType.DEF_PEN: (14.0, 20.0),  # BEST def pen is at Rare!
        HeroPowerStatType.BOSS_DAMAGE: (28.0, 40.0),  # BEST boss dmg is at Rare!
        HeroPowerStatType.NORMAL_DAMAGE: (28.0, 40.0),  # BEST normal dmg is at Rare!
    },
    # Common (Normal): Lowest tier
    HeroPowerTier.COMMON: {
        HeroPowerStatType.MAIN_STAT_FLAT: (40, 60),
        HeroPowerStatType.MAX_HP: (1200, 1500),
        HeroPowerStatType.DAMAGE: (3.0, 5.0),
        HeroPowerStatType.MAX_DMG_MULT: (7.0, 10.0),
        HeroPowerStatType.MIN_DMG_MULT: (7.0, 10.0),
        HeroPowerStatType.CRIT_RATE: (3.0, 6.0),
        HeroPowerStatType.ATTACK_SPEED: (7.0, 9.0),
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
        Returns dict with stat keys from stat_names.py.
        """
        return {
            MAIN_STAT_FLAT: self.get_stat_value(HeroPowerPassiveStatType.MAIN_STAT),
            DAMAGE_PCT: self.get_stat_value(HeroPowerPassiveStatType.DAMAGE_PERCENT),
            ATTACK_FLAT: self.get_stat_value(HeroPowerPassiveStatType.ATTACK),
            MAX_HP: self.get_stat_value(HeroPowerPassiveStatType.MAX_HP),
            ACCURACY: self.get_stat_value(HeroPowerPassiveStatType.ACCURACY),
            DEFENSE: self.get_stat_value(HeroPowerPassiveStatType.DEFENSE),
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
        # Flat stats (no % sign): Max HP, Main Stat
        if self.stat_type in (HeroPowerStatType.MAX_HP, HeroPowerStatType.MAIN_STAT_FLAT):
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
        # Fallback: estimate DPS value based on stat type
        # For flat stats (Main Stat, Max HP), use different scaling
        if line.stat_type == HeroPowerStatType.MAIN_STAT_FLAT:
            # Flat main stat: ~1000 DEX ≈ 1% DPS gain (rough estimate)
            return line.value / 1000.0
        elif line.stat_type == HeroPowerStatType.MAX_HP:
            # Defensive stat: minimal DPS impact
            return 0.0
        else:
            # Percentage stats: value * 0.05 to estimate DPS %
            # (rough estimate - actual value depends on current stats)
            return line.value * 0.05

    # Get the stats key for this stat type
    stats_key = STAT_TO_STATS_KEY.get(line.stat_type)
    if not stats_key:
        # Defensive stat, no DPS impact
        return 0.0

    # Stats stored as source lists (multiplicative stats) need special handling
    # These are stored as lists of tuples, not scalar values
    SOURCE_LIST_STATS = {
        'def_pen': 'def_pen_sources',      # List of (source, value/100, priority)
        'attack_speed': 'attack_speed_sources',  # List of (source, value)
    }

    try:
        # Get current stats
        current_stats = get_stats_func()
        if not current_stats:
            return 0.0

        # Calculate current DPS first
        current_dps = calc_dps_func(current_stats)
        if current_dps <= 0:
            return 0.0

        # Make a deep copy for baseline calculation
        baseline_stats = copy.deepcopy(current_stats)

        # Handle stats stored in source lists vs scalar values
        if stats_key in SOURCE_LIST_STATS:
            # Multiplicative stat stored as source list
            source_list_key = SOURCE_LIST_STATS[stats_key]
            if source_list_key in baseline_stats:
                # Filter out this specific hero_power line from the source list
                # Source names are like 'hero_power_line1', 'hero_power_line2', etc. (no underscore before number)
                original_sources = baseline_stats[source_list_key]
                line_source_name = f'hero_power_line{line.slot}'
                filtered_sources = [
                    entry for entry in original_sources
                    if entry[0].lower() != line_source_name
                ]
                baseline_stats[source_list_key] = filtered_sources
        else:
            # Scalar stat - subtract line value
            # Handle main_stat_flat specially - it gets resolved to job-specific keys (dex_flat, str_flat, etc.)
            if stats_key == 'main_stat_flat':
                # The stats dict includes 'main_stat_type' which tells us the job's main stat
                # e.g., 'dex' for Bowmaster, 'str' for Warrior, etc.
                main_stat_type = baseline_stats.get('main_stat_type', 'dex')
                actual_key = f'{main_stat_type}_flat'
                baseline_stats[actual_key] = baseline_stats.get(actual_key, 0) - line.value
            else:
                current_value = baseline_stats.get(stats_key, 0)
                baseline_stats[stats_key] = current_value - line.value

        # Calculate baseline DPS (without this line)
        baseline_dps = calc_dps_func(baseline_stats)
        if baseline_dps <= 0:
            return 0.0

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

    # Iterate through tiers with offensive stats
    # Note: Rare has the BEST offensive stats (Boss Dmg 28-40%, Def Pen 14-20%)
    # Mystic only has Main Stat and HP - no offensive stats!
    valuable_tiers = [
        HeroPowerTier.RARE,       # Best: Boss/Normal 28-40%, Def Pen 14-20%
        HeroPowerTier.EPIC,       # Good: Boss/Normal 18-25%, Def Pen 8-12%, AS 15-20%
        HeroPowerTier.UNIQUE,     # Dmg 18-25%, Min/Max 28-40%, CR 15-20%
        HeroPowerTier.LEGENDARY,  # Dmg 28-40%, Main Stat, HP
    ]

    # Stats to evaluate for DPS ranking
    # Note: Crit Damage is NOT available as an ability stat
    offensive_stats = [
        HeroPowerStatType.DEF_PEN,
        HeroPowerStatType.BOSS_DAMAGE,
        HeroPowerStatType.DAMAGE,
        HeroPowerStatType.MAX_DMG_MULT,
        HeroPowerStatType.NORMAL_DAMAGE,
        HeroPowerStatType.MAIN_STAT_FLAT,
        HeroPowerStatType.CRIT_RATE,
        HeroPowerStatType.ATTACK_SPEED,
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
                    if stat_type == HeroPowerStatType.MAIN_STAT_FLAT:
                        dps_contribution = max_val / 1000.0 * base_weight * mode_mult
                    else:
                        dps_contribution = max_val * base_weight * mode_mult * 0.05

                # Get display name
                stat_name = STAT_DISPLAY_NAMES.get(stat_type, stat_type.value)
                tier_name = tier.value.capitalize()

                # Format value range
                if stat_type == HeroPowerStatType.MAIN_STAT_FLAT:
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

    def get_stats(self, job_class=None):
        """
        Get all hero power stats as a StatBlock.

        Note: Defense Pen is NOT included here because it stacks multiplicatively
        and needs special handling. Use get_stat_total(HeroPowerStatType.DEF_PEN).

        Args:
            job_class: Job class for main_stat mapping (defaults to Bowmaster)

        Returns:
            StatBlock with all hero power stats (except def_pen)
        """
        from stats import create_stat_block_for_job
        from job_classes import JobClass

        if job_class is None:
            job_class = JobClass.BOWMASTER

        all_stats = self.get_all_stats()

        return create_stat_block_for_job(
            job_class=job_class,
            main_stat_flat=all_stats.get(HeroPowerStatType.MAIN_STAT_FLAT, 0),
            attack_speed=all_stats.get(HeroPowerStatType.ATTACK_SPEED, 0),
            damage_pct=all_stats.get(HeroPowerStatType.DAMAGE, 0),
            boss_damage=all_stats.get(HeroPowerStatType.BOSS_DAMAGE, 0),
            normal_damage=all_stats.get(HeroPowerStatType.NORMAL_DAMAGE, 0),
            crit_rate=all_stats.get(HeroPowerStatType.CRIT_RATE, 0),
            # Note: Crit Damage is NOT available as an ability stat
            min_dmg_mult=all_stats.get(HeroPowerStatType.MIN_DMG_MULT, 0),
            max_dmg_mult=all_stats.get(HeroPowerStatType.MAX_DMG_MULT, 0),
            max_hp=all_stats.get(HeroPowerStatType.MAX_HP, 0),
            # Note: Defense is NOT available as an ability stat
            # Note: def_pen excluded - needs multiplicative handling
        )


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
# DPS OPTIMIZER - Strategy-Based Optimization
# =============================================================================

class OptimizationStrategy(Enum):
    """Optimization strategies for Hero Power rerolling."""
    CONSERVATIVE = "conservative"     # Lock early, minimize medal spend
    BALANCED = "balanced"             # Default - balance cost vs improvement
    AGGRESSIVE = "aggressive"         # Keep rerolling for near-perfect lines
    EFFICIENCY = "efficiency"         # Pure DPS/1000 medals optimization
    LINE_COUNT = "line_count"         # Target X/6 good lines


# Strategy parameters
STRATEGY_PARAMS: Dict[OptimizationStrategy, Dict] = {
    OptimizationStrategy.CONSERVATIVE: {
        'lock_threshold_score': 50,      # Lock lines scoring 50+
        'stop_at_good_lines': 4,         # Stop when 4/6 lines are good
        'max_rerolls': 500,              # Cap at 500 rerolls
        'description': "Lock early, minimize medal spend",
    },
    OptimizationStrategy.BALANCED: {
        'lock_threshold_score': 60,      # Lock lines scoring 60+
        'stop_at_good_lines': 5,         # Stop when 5/6 lines are good
        'max_rerolls': 2000,
        'description': "Balance between cost and improvement",
    },
    OptimizationStrategy.AGGRESSIVE: {
        'lock_threshold_score': 75,      # Only lock excellent lines
        'stop_at_good_lines': 6,         # Want all 6 good
        'max_rerolls': 10000,
        'description': "Keep rerolling for near-perfect lines",
    },
    OptimizationStrategy.EFFICIENCY: {
        'min_efficiency': 0.01,          # Stop when < 0.01% DPS per 1000 medals
        'dynamic_threshold': True,       # Use calculate_reroll_efficiency()
        'description': "Pure DPS per medal efficiency",
    },
    OptimizationStrategy.LINE_COUNT: {
        'target_good_lines': 5,          # Default 5/6
        'good_line_threshold': 60,       # Score >= 60 is "good"
        'description': "Target specific number of good lines",
    },
}


# DPS Reference Table - Shows estimated DPS gain for each tier/stat combo
# Based on typical endgame stats: ~40k main stat, ~200% damage, ~50% def pen
DPS_REFERENCE_TABLE: Dict[str, List[Dict]] = {
    'mystic': [
        {'stat': 'Main Stat', 'low': 1500, 'mid': 2000, 'high': 2500,
         'dps_low': 0.5, 'dps_mid': 0.7, 'dps_high': 0.8, 'note': ''},
        {'stat': 'Max HP', 'low': 70000, 'mid': 92500, 'high': 115000,
         'dps_low': 0, 'dps_mid': 0, 'dps_high': 0, 'note': 'defensive only'},
    ],
    'legendary': [
        {'stat': 'Main Stat', 'low': 800, 'mid': 1000, 'high': 1200,
         'dps_low': 0.25, 'dps_mid': 0.35, 'dps_high': 0.4, 'note': ''},
        {'stat': 'Damage %', 'low': 28, 'mid': 34, 'high': 40,
         'dps_low': 1.4, 'dps_mid': 1.7, 'dps_high': 2.0, 'note': ''},
        {'stat': 'Max HP', 'low': 35000, 'mid': 50000, 'high': 65000,
         'dps_low': 0, 'dps_mid': 0, 'dps_high': 0, 'note': 'defensive only'},
    ],
    'unique': [
        {'stat': 'Main Stat', 'low': 400, 'mid': 550, 'high': 700,
         'dps_low': 0.1, 'dps_mid': 0.14, 'dps_high': 0.18, 'note': ''},
        {'stat': 'Damage %', 'low': 18, 'mid': 21.5, 'high': 25,
         'dps_low': 0.9, 'dps_mid': 1.1, 'dps_high': 1.25, 'note': ''},
        {'stat': 'Max Dmg Mult', 'low': 28, 'mid': 34, 'high': 40,
         'dps_low': 0.9, 'dps_mid': 1.1, 'dps_high': 1.3, 'note': ''},
        {'stat': 'Min Dmg Mult', 'low': 28, 'mid': 34, 'high': 40,
         'dps_low': 0.5, 'dps_mid': 0.6, 'dps_high': 0.7, 'note': ''},
        {'stat': 'Crit Rate', 'low': 15, 'mid': 17.5, 'high': 20,
         'dps_low': 0.6, 'dps_mid': 0.7, 'dps_high': 0.8, 'note': ''},
    ],
    'epic': [
        {'stat': 'Def Pen', 'low': 8, 'mid': 10, 'high': 12,
         'dps_low': 1.6, 'dps_mid': 2.0, 'dps_high': 2.4, 'note': ''},
        {'stat': 'Boss Dmg', 'low': 18, 'mid': 21.5, 'high': 25,
         'dps_low': 0.7, 'dps_mid': 0.9, 'dps_high': 1.0, 'note': 'boss only'},
        {'stat': 'Normal Dmg', 'low': 18, 'mid': 21.5, 'high': 25,
         'dps_low': 0.7, 'dps_mid': 0.9, 'dps_high': 1.0, 'note': 'mob only'},
        {'stat': 'Damage %', 'low': 12, 'mid': 13.5, 'high': 15,
         'dps_low': 0.6, 'dps_mid': 0.68, 'dps_high': 0.75, 'note': ''},
        {'stat': 'Attack Speed', 'low': 15, 'mid': 17.5, 'high': 20,
         'dps_low': 0.75, 'dps_mid': 0.9, 'dps_high': 1.0, 'note': ''},
        {'stat': 'Crit Rate', 'low': 10, 'mid': 12, 'high': 14,
         'dps_low': 0.4, 'dps_mid': 0.5, 'dps_high': 0.6, 'note': ''},
    ],
    'rare': [
        {'stat': 'Def Pen', 'low': 14, 'mid': 17, 'high': 20,
         'dps_low': 2.8, 'dps_mid': 3.4, 'dps_high': 4.0, 'note': 'BEST'},
        {'stat': 'Boss Dmg', 'low': 28, 'mid': 34, 'high': 40,
         'dps_low': 1.1, 'dps_mid': 1.4, 'dps_high': 1.6, 'note': 'boss only'},
        {'stat': 'Normal Dmg', 'low': 28, 'mid': 34, 'high': 40,
         'dps_low': 1.1, 'dps_mid': 1.4, 'dps_high': 1.6, 'note': 'mob only'},
        {'stat': 'Attack Speed', 'low': 10, 'mid': 12, 'high': 14,
         'dps_low': 0.5, 'dps_mid': 0.6, 'dps_high': 0.7, 'note': ''},
        {'stat': 'Damage %', 'low': 7, 'mid': 8.5, 'high': 10,
         'dps_low': 0.35, 'dps_mid': 0.42, 'dps_high': 0.5, 'note': ''},
    ],
}


# Best lines ranking - sorted by max DPS gain
BEST_LINES_RANKING: List[Dict] = [
    {'rank': 1, 'tier': 'Rare', 'stat': 'Def Pen', 'max_value': '20%', 'max_dps': 4.0, 'probability': '3%'},
    {'rank': 2, 'tier': 'Epic', 'stat': 'Def Pen', 'max_value': '12%', 'max_dps': 2.4, 'probability': '1.2%'},
    {'rank': 3, 'tier': 'Legendary', 'stat': 'Damage %', 'max_value': '40%', 'max_dps': 2.0, 'probability': '0.46%'},
    {'rank': 4, 'tier': 'Rare', 'stat': 'Boss Dmg', 'max_value': '40%', 'max_dps': 1.6, 'probability': '3%'},
    {'rank': 5, 'tier': 'Rare', 'stat': 'Normal Dmg', 'max_value': '40%', 'max_dps': 1.6, 'probability': '3%'},
    {'rank': 6, 'tier': 'Unique', 'stat': 'Max Dmg', 'max_value': '40%', 'max_dps': 1.3, 'probability': '0.75%'},
    {'rank': 7, 'tier': 'Unique', 'stat': 'Damage %', 'max_value': '25%', 'max_dps': 1.25, 'probability': '1%'},
    {'rank': 8, 'tier': 'Epic', 'stat': 'Boss Dmg', 'max_value': '25%', 'max_dps': 1.0, 'probability': '1.2%'},
    {'rank': 9, 'tier': 'Epic', 'stat': 'Attack Speed', 'max_value': '20%', 'max_dps': 1.0, 'probability': '1.5%'},
    {'rank': 10, 'tier': 'Mystic', 'stat': 'Main Stat', 'max_value': '2500', 'max_dps': 0.8, 'probability': '0.06%'},
]


def auto_detect_goal(
    config: HeroPowerConfig,
    level_config: HeroPowerLevelConfig,
    calc_dps_func: Optional[Callable] = None,
    get_stats_func: Optional[Callable] = None,
) -> Dict:
    """
    Analyze current config and suggest realistic improvement goals.

    Args:
        config: Current HeroPowerConfig with 6 lines
        level_config: Level config for tier rates and costs
        calc_dps_func: Optional callback for actual DPS calculation
        get_stats_func: Optional callback to get current stats

    Returns:
        Dict with current state and suggested goals
    """
    # Calculate current line scores
    line_scores = []
    for line in config.lines:
        score = score_hero_power_line(line, calc_dps_func, get_stats_func)
        dps_value = calculate_line_dps_value(line, calc_dps_func, get_stats_func)
        line_scores.append({
            'slot': line.slot,
            'score': score,
            'dps_value': dps_value,
            'tier': line.tier.value,
            'stat': STAT_DISPLAY_NAMES.get(line.stat_type, line.stat_type.value),
        })

    # Sort by score descending to find best/worst lines
    sorted_scores = sorted(line_scores, key=lambda x: x['score'], reverse=True)

    # Count "good" lines (score >= 60)
    good_lines = sum(1 for ls in line_scores if ls['score'] >= 60)
    excellent_lines = sum(1 for ls in line_scores if ls['score'] >= 75)

    # Calculate total DPS contribution
    total_dps = sum(ls['dps_value'] for ls in line_scores)

    # Find best and worst lines
    best_line = sorted_scores[0] if sorted_scores else None
    worst_line = sorted_scores[-1] if sorted_scores else None

    # Calculate average score
    avg_score = sum(ls['score'] for ls in line_scores) / len(line_scores) if line_scores else 0

    # Generate suggested goals
    goals = []

    # Goal 1: +1 good line (if not all good)
    if good_lines < 6:
        goals.append({
            'name': f'{good_lines + 1}/6 Good Lines',
            'type': 'line_count',
            'target_good_lines': good_lines + 1,
            'description': f'Improve from {good_lines} to {good_lines + 1} lines with score >= 60',
            'difficulty': 'Easy' if good_lines < 3 else 'Medium',
        })

    # Goal 2: +2% total DPS
    if total_dps < 15:  # If total DPS contribution is under 15%
        goals.append({
            'name': f'+2% Total DPS',
            'type': 'dps_improvement',
            'target_dps': total_dps + 2.0,
            'description': f'Increase total DPS contribution from {total_dps:.1f}% to {total_dps + 2:.1f}%',
            'difficulty': 'Medium',
        })

    # Goal 3: Replace worst line
    if worst_line and worst_line['score'] < 40:
        goals.append({
            'name': f'Replace Worst Line (Slot {worst_line["slot"]})',
            'type': 'replace_worst',
            'target_slot': worst_line['slot'],
            'current_score': worst_line['score'],
            'description': f'Replace {worst_line["stat"]} ({worst_line["tier"]}) with better stat',
            'difficulty': 'Easy',
        })

    # Goal 4: All good lines (ambitious)
    if good_lines < 6:
        goals.append({
            'name': '6/6 Good Lines',
            'type': 'line_count',
            'target_good_lines': 6,
            'description': 'Achieve 6 lines with score >= 60 (may take many rerolls)',
            'difficulty': 'Hard',
        })

    # Goal 5: Maximum efficiency (keep going while worthwhile)
    goals.append({
        'name': 'Maximum Efficiency',
        'type': 'efficiency',
        'min_efficiency': 0.01,
        'description': 'Keep rerolling while DPS gain per 1000 medals > 0.01%',
        'difficulty': 'Variable',
    })

    return {
        'current_state': {
            'total_dps': total_dps,
            'good_lines': good_lines,
            'excellent_lines': excellent_lines,
            'avg_score': avg_score,
            'best_line': best_line,
            'worst_line': worst_line,
        },
        'line_scores': line_scores,
        'suggested_goals': goals,
    }


def estimate_cost_to_goal(
    current_config: HeroPowerConfig,
    goal: Dict,
    level_config: HeroPowerLevelConfig,
    strategy: OptimizationStrategy = OptimizationStrategy.BALANCED,
    iterations: int = 1000,
    max_rerolls: int = 10000,
    calc_dps_func: Optional[Callable] = None,
    get_stats_func: Optional[Callable] = None,
) -> Dict:
    """
    Monte Carlo simulation to estimate cost to reach a goal.

    Args:
        current_config: Starting HeroPowerConfig
        goal: Goal dict from auto_detect_goal()
        level_config: Level config for tier rates and costs
        strategy: Optimization strategy to use
        iterations: Number of simulation runs
        max_rerolls: Max rerolls per simulation
        calc_dps_func: Optional DPS calculation callback
        get_stats_func: Optional stats callback

    Returns:
        Dict with cost estimates and statistics
    """
    goal_type = goal.get('type', 'line_count')
    strategy_params = STRATEGY_PARAMS.get(strategy, STRATEGY_PARAMS[OptimizationStrategy.BALANCED])

    reroll_counts = []
    medal_costs = []
    successes = 0
    capped = 0

    for _ in range(iterations):
        # Make a copy of the config
        config = copy.deepcopy(current_config)

        # Calculate which lines to lock based on strategy
        lock_threshold = strategy_params.get('lock_threshold_score', 60)
        for line in config.lines:
            score = score_hero_power_line(line, calc_dps_func, get_stats_func)
            line.is_locked = score >= lock_threshold

        rerolls = 0
        total_medals = 0

        while rerolls < max_rerolls:
            # Check if goal achieved
            goal_achieved = False

            if goal_type == 'line_count':
                target = goal.get('target_good_lines', 5)
                good_count = sum(
                    1 for line in config.lines
                    if score_hero_power_line(line, calc_dps_func, get_stats_func) >= 60
                )
                goal_achieved = good_count >= target

            elif goal_type == 'dps_improvement':
                target_dps = goal.get('target_dps', 10)
                current_dps = sum(
                    calculate_line_dps_value(line, calc_dps_func, get_stats_func)
                    for line in config.lines
                )
                goal_achieved = current_dps >= target_dps

            elif goal_type == 'efficiency':
                # For efficiency mode, check if any line is worth rerolling
                min_efficiency = goal.get('min_efficiency', 0.01)
                worth_rerolling = False
                for line in config.lines:
                    if line.is_locked:
                        continue
                    line_dps = calculate_line_dps_value(line, calc_dps_func, get_stats_func)
                    eff = calculate_reroll_efficiency(
                        line_dps, config.get_locked_count(), level_config,
                        calc_dps_func, get_stats_func
                    )
                    if eff['efficiency'] >= min_efficiency:
                        worth_rerolling = True
                        break
                goal_achieved = not worth_rerolling

            elif goal_type == 'replace_worst':
                target_slot = goal.get('target_slot', 1)
                target_line = next((l for l in config.lines if l.slot == target_slot), None)
                if target_line:
                    new_score = score_hero_power_line(target_line, calc_dps_func, get_stats_func)
                    goal_achieved = new_score >= 60

            if goal_achieved:
                successes += 1
                break

            # Reroll unlocked lines
            cost = level_config.get_reroll_cost(config.get_locked_count())
            config = simulate_hero_power_reroll(config, level_config)
            rerolls += 1
            total_medals += cost

            # Re-evaluate locks after reroll
            for line in config.lines:
                if not line.is_locked:
                    score = score_hero_power_line(line, calc_dps_func, get_stats_func)
                    if score >= lock_threshold:
                        line.is_locked = True
        else:
            capped += 1

        reroll_counts.append(rerolls)
        medal_costs.append(total_medals)

    # Calculate statistics
    if not reroll_counts:
        return {
            'expected_rerolls': 0,
            'expected_medals': 0,
            'median_rerolls': 0,
            'median_medals': 0,
            'p90_rerolls': 0,
            'p90_medals': 0,
            'success_rate': 0,
            'capped_simulations': 0,
        }

    sorted_rerolls = sorted(reroll_counts)
    sorted_medals = sorted(medal_costs)
    median_idx = len(sorted_rerolls) // 2
    p90_idx = int(len(sorted_rerolls) * 0.9)

    return {
        'expected_rerolls': sum(reroll_counts) / len(reroll_counts),
        'expected_medals': sum(medal_costs) / len(medal_costs),
        'median_rerolls': sorted_rerolls[median_idx],
        'median_medals': sorted_medals[median_idx],
        'p90_rerolls': sorted_rerolls[p90_idx],
        'p90_medals': sorted_medals[p90_idx],
        'success_rate': successes / iterations,
        'capped_simulations': capped,
        'iterations': iterations,
    }


def analyze_with_strategy(
    config: HeroPowerConfig,
    level_config: HeroPowerLevelConfig,
    strategy: OptimizationStrategy = OptimizationStrategy.BALANCED,
    calc_dps_func: Optional[Callable] = None,
    get_stats_func: Optional[Callable] = None,
) -> Dict:
    """
    Analyze a config using a specific strategy to determine lock/reroll decisions.

    Args:
        config: HeroPowerConfig to analyze
        level_config: Level config for costs and rates
        strategy: Which strategy to use
        calc_dps_func: Optional DPS callback
        get_stats_func: Optional stats callback

    Returns:
        Dict with lock/reroll recommendations and reasoning
    """
    strategy_params = STRATEGY_PARAMS.get(strategy, STRATEGY_PARAMS[OptimizationStrategy.BALANCED])

    # Analyze each line
    line_analysis = []
    for line in config.lines:
        score = score_hero_power_line(line, calc_dps_func, get_stats_func)
        dps_value = calculate_line_dps_value(line, calc_dps_func, get_stats_func)

        # Determine lock recommendation based on strategy
        if strategy == OptimizationStrategy.EFFICIENCY:
            # Use efficiency calculation
            num_locked = sum(1 for la in line_analysis if la.get('recommendation') == 'LOCK')
            eff_result = calculate_reroll_efficiency(
                dps_value, num_locked, level_config, calc_dps_func, get_stats_func
            )
            recommendation = eff_result['recommendation']
            reasoning = eff_result['reasoning']
        else:
            # Use score threshold
            lock_threshold = strategy_params.get('lock_threshold_score', 60)
            recommendation = 'LOCK' if score >= lock_threshold else 'REROLL'
            reasoning = f"Score {score:.0f} {'≥' if score >= lock_threshold else '<'} threshold {lock_threshold}"

        line_analysis.append({
            'slot': line.slot,
            'stat': STAT_DISPLAY_NAMES.get(line.stat_type, line.stat_type.value),
            'tier': line.tier.value.capitalize(),
            'value': line.value,
            'score': score,
            'dps_value': dps_value,
            'recommendation': recommendation,
            'reasoning': reasoning,
        })

    # Sort by score for display
    line_analysis.sort(key=lambda x: x['score'], reverse=True)

    # Calculate summary stats
    lines_to_lock = [la['slot'] for la in line_analysis if la['recommendation'] == 'LOCK']
    lines_to_reroll = [la['slot'] for la in line_analysis if la['recommendation'] == 'REROLL']

    cost_per_reroll = level_config.get_reroll_cost(len(lines_to_lock))

    return {
        'strategy': strategy.value,
        'strategy_description': strategy_params.get('description', ''),
        'line_analysis': line_analysis,
        'lines_to_lock': lines_to_lock,
        'lines_to_reroll': lines_to_reroll,
        'cost_per_reroll': cost_per_reroll,
        'total_dps': sum(la['dps_value'] for la in line_analysis),
        'avg_score': sum(la['score'] for la in line_analysis) / len(line_analysis) if line_analysis else 0,
    }


def get_dps_reference_for_tier(tier: str) -> List[Dict]:
    """Get DPS reference data for a specific tier."""
    return DPS_REFERENCE_TABLE.get(tier.lower(), [])


def get_best_lines_ranking() -> List[Dict]:
    """Get the ranking of best possible lines by DPS gain."""
    return BEST_LINES_RANKING


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
