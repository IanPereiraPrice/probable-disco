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
from libs.stat_names import (
    get_display_name,
    DAMAGE_PCT, BOSS_DAMAGE, NORMAL_DAMAGE, DEF_PEN,
    MAX_DMG_MULT, MIN_DMG_MULT, CRIT_RATE,
    MAIN_STAT_FLAT, ATTACK_FLAT, ATTACK_SPEED, MAX_HP, ACCURACY, DEFENSE
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
# Authoritative source: data_mine/TextAsset/HeroPowerAbilityOptionTable.json
# (mapping: Grade1=Common, Grade2=Rare, Grade3=Epic, Grade4=Unique,
#  Grade5=Legendary, Grade6=Mystic — confirmed by HeroPowerAbilityGradeProbTable
#  whose Grade1..Grade6 probabilities at level 15 exactly match the in-game
#  common/rare/epic/unique/legendary/mystic rates.)
#
# Datamine percentage stats are stored ×10 (e.g. AttackPowerToBoss 280-400
# displays as 28-40%). Flat stats (MainStat, MaxHp) use their raw values.
#
# Key insight (CORRECTED from a prior incorrect table): higher tiers strictly
# dominate lower tiers in BOTH stat selection AND value ranges. Mystic is the
# best tier for every offensive stat. Boss Damage / Normal Damage / Def Pen
# (PiercePower) only roll at Legendary or Mystic.
HERO_POWER_STAT_RANGES: Dict[HeroPowerTier, Dict[HeroPowerStatType, Tuple[float, float]]] = {
    # Common (Grade1): only main stat + utility (no offensive stats)
    HeroPowerTier.COMMON: {
        HeroPowerStatType.MAIN_STAT_FLAT: (40, 60),
        HeroPowerStatType.MAX_HP: (1200, 1500),
    },
    # Rare (Grade2): adds AttackPower (Damage %)
    HeroPowerTier.RARE: {
        HeroPowerStatType.MAIN_STAT_FLAT: (100, 150),
        HeroPowerStatType.MAX_HP: (1800, 3000),
        HeroPowerStatType.DAMAGE: (3.0, 5.0),
    },
    # Epic (Grade3): adds Min/Max Damage Ratio and Crit Chance
    HeroPowerTier.EPIC: {
        HeroPowerStatType.MAIN_STAT_FLAT: (200, 300),
        HeroPowerStatType.MAX_HP: (4500, 9000),
        HeroPowerStatType.DAMAGE: (7.0, 10.0),
        HeroPowerStatType.MIN_DMG_MULT: (7.0, 10.0),
        HeroPowerStatType.MAX_DMG_MULT: (7.0, 10.0),
        HeroPowerStatType.CRIT_RATE: (3.0, 6.0),
    },
    # Unique (Grade4): adds Attack Speed
    HeroPowerTier.UNIQUE: {
        HeroPowerStatType.MAIN_STAT_FLAT: (400, 700),
        HeroPowerStatType.MAX_HP: (15000, 30000),
        HeroPowerStatType.DAMAGE: (12.0, 15.0),
        HeroPowerStatType.MIN_DMG_MULT: (12.0, 15.0),
        HeroPowerStatType.MAX_DMG_MULT: (12.0, 15.0),
        HeroPowerStatType.CRIT_RATE: (7.0, 9.0),
        HeroPowerStatType.ATTACK_SPEED: (7.0, 9.0),
    },
    # Legendary (Grade5): adds Pierce Power (Def Pen) and Boss/Normal Damage
    HeroPowerTier.LEGENDARY: {
        HeroPowerStatType.MAIN_STAT_FLAT: (800, 1200),
        HeroPowerStatType.MAX_HP: (35000, 65000),
        HeroPowerStatType.DAMAGE: (18.0, 25.0),
        HeroPowerStatType.MIN_DMG_MULT: (18.0, 25.0),
        HeroPowerStatType.MAX_DMG_MULT: (18.0, 25.0),
        HeroPowerStatType.CRIT_RATE: (10.0, 14.0),
        HeroPowerStatType.ATTACK_SPEED: (10.0, 14.0),
        HeroPowerStatType.DEF_PEN: (8.0, 12.0),
        HeroPowerStatType.BOSS_DAMAGE: (18.0, 25.0),
        HeroPowerStatType.NORMAL_DAMAGE: (18.0, 25.0),
    },
    # Mystic (Grade6): strictly best across the board
    HeroPowerTier.MYSTIC: {
        HeroPowerStatType.MAIN_STAT_FLAT: (1500, 2500),
        HeroPowerStatType.MAX_HP: (70000, 115000),
        HeroPowerStatType.DAMAGE: (28.0, 40.0),
        HeroPowerStatType.MIN_DMG_MULT: (28.0, 40.0),
        HeroPowerStatType.MAX_DMG_MULT: (28.0, 40.0),
        HeroPowerStatType.CRIT_RATE: (15.0, 20.0),
        HeroPowerStatType.ATTACK_SPEED: (15.0, 20.0),
        HeroPowerStatType.DEF_PEN: (14.0, 20.0),
        HeroPowerStatType.BOSS_DAMAGE: (28.0, 40.0),
        HeroPowerStatType.NORMAL_DAMAGE: (28.0, 40.0),
    },
}


# Total number of distinct stats that can roll at each tier per the datamine,
# INCLUDING utility stats not tracked here (MaxMp, HitChance, AvoidChance,
# MpRegen, DebuffResist, CriticalResist, Toughness, BonusGold/ExpPercent).
# Used for accurate per-line probability: P(specific stat) = tier_rate / N.
# Source: data_mine/TextAsset/HeroPowerAbilityOptionTable.json grouped by GradeType.
STATS_PER_GRADE: Dict[HeroPowerTier, int] = {
    HeroPowerTier.COMMON: 6,      # Grade1
    HeroPowerTier.RARE: 8,        # Grade2
    HeroPowerTier.EPIC: 12,       # Grade3
    HeroPowerTier.UNIQUE: 14,     # Grade4
    HeroPowerTier.LEGENDARY: 19,  # Grade5
    HeroPowerTier.MYSTIC: 19,     # Grade6
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

    # Tiers with offensive stats worth evaluating
    valuable_tiers = [
        HeroPowerTier.RARE, HeroPowerTier.EPIC,
        HeroPowerTier.UNIQUE, HeroPowerTier.LEGENDARY,
    ]
    offensive_stats = [
        HeroPowerStatType.DEF_PEN, HeroPowerStatType.BOSS_DAMAGE,
        HeroPowerStatType.DAMAGE, HeroPowerStatType.MAX_DMG_MULT,
        HeroPowerStatType.NORMAL_DAMAGE, HeroPowerStatType.MAIN_STAT_FLAT,
        HeroPowerStatType.CRIT_RATE, HeroPowerStatType.ATTACK_SPEED,
        HeroPowerStatType.MIN_DMG_MULT,
    ]

    # When real DPS callbacks are present, compute baseline ONCE and use the
    # hypothetical-line evaluator (which correctly handles source-list stats
    # like def_pen / attack_speed). calc_dps_func returns DPS for a single
    # combat mode, so all 3 mode keys end up with identical real-DPS rankings
    # (the per-mode distinction only matters in the heuristic fallback below).
    use_real_dps = calc_dps_func is not None and get_stats_func is not None
    current_stats = get_stats_func() if use_real_dps else None
    current_dps = calc_dps_func(current_stats) if use_real_dps and current_stats else 0
    if use_real_dps and current_dps <= 0:
        use_real_dps = False  # Bad stats; fall back to heuristics

    for mode in combat_modes:
        mode_lines = []

        for tier in valuable_tiers:
            tier_ranges = HERO_POWER_STAT_RANGES.get(tier, {})

            for stat_type in offensive_stats:
                if stat_type not in tier_ranges:
                    continue

                min_val, max_val = tier_ranges[stat_type]
                hypothetical_line = HeroPowerLine(
                    slot=0, stat_type=stat_type, value=max_val,
                    tier=tier, is_locked=False,
                )

                if use_real_dps:
                    dps_contribution = calculate_hypothetical_line_dps_value(
                        hypothetical_line, current_stats, current_dps, calc_dps_func,
                    )
                else:
                    # Heuristic fallback: per-mode weights × base weight × value
                    base_weight = STAT_DPS_WEIGHTS.get(stat_type, 0.5)
                    mode_adjustments = MODE_STAT_ADJUSTMENTS.get(mode, {})
                    mode_mult = mode_adjustments.get(stat_type, 1.0)
                    if stat_type == HeroPowerStatType.MAIN_STAT_FLAT:
                        dps_contribution = max_val / 1000.0 * base_weight * mode_mult
                    else:
                        dps_contribution = max_val * base_weight * mode_mult * 0.05

                stat_name = STAT_DISPLAY_NAMES.get(stat_type, stat_type.value)
                tier_name = tier.value.capitalize()
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

        mode_lines.sort(key=lambda x: x['dps_contribution'], reverse=True)
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
        from game.job_classes import JobClass

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


def calculate_hypothetical_line_dps_value(
    line: HeroPowerLine,
    current_stats: Dict,
    current_dps: float,
    calc_dps_func: Callable,
) -> float:
    """
    Compute % DPS gain from ADDING a hypothetical line to current_stats.

    Unlike calculate_line_dps_value (which subtracts an existing line to find
    baseline), this is for evaluating lines that are NOT currently in the
    user's data — e.g., for reference tables and "what if I rolled X" rankings.

    Caller pre-computes current_stats and current_dps once so this helper can
    be called many times cheaply (just one extra DPS call per evaluation).
    """
    stats_key = STAT_TO_STATS_KEY.get(line.stat_type)
    if not stats_key or current_dps <= 0:
        return 0.0

    test_stats = copy.deepcopy(current_stats)

    if stats_key == 'def_pen':
        # Multiplicative source list — append as a new source
        # decimal value, priority 50 (matches existing hero power lines)
        test_stats.setdefault('def_pen_sources', []).append(
            ('hypothetical_hero_power', line.value / 100, 50)
        )
    elif stats_key == 'attack_speed':
        test_stats.setdefault('attack_speed_sources', []).append(
            ('hypothetical_hero_power', line.value)
        )
    elif stats_key == 'main_stat_flat':
        # Resolves to job-specific flat key (dex_flat, str_flat, etc.)
        main_stat_type = test_stats.get('main_stat_type', 'dex')
        actual_key = f'{main_stat_type}_flat'
        test_stats[actual_key] = test_stats.get(actual_key, 0) + line.value
    else:
        test_stats[stats_key] = test_stats.get(stats_key, 0) + line.value

    try:
        test_dps = calc_dps_func(test_stats)
    except Exception:
        return 0.0

    return max(0.0, (test_dps / current_dps - 1) * 100)


def compute_dps_reference_table_for_character(
    calc_dps_func: Callable,
    get_stats_func: Callable,
) -> Dict[str, List[Dict]]:
    """
    Build a per-tier DPS reference table using the user's actual character
    stats. Same shape as DPS_REFERENCE_TABLE but populated with real numbers.
    """
    current_stats = get_stats_func()
    current_dps = calc_dps_func(current_stats) if current_stats else 0
    if current_dps <= 0:
        return {}

    result: Dict[str, List[Dict]] = {}

    # Annotate notes for stats whose value depends on combat context
    NOTES = {
        HeroPowerStatType.BOSS_DAMAGE: 'boss only',
        HeroPowerStatType.NORMAL_DAMAGE: 'mob only',
        HeroPowerStatType.MAX_HP: 'defensive only',
    }

    for tier, ranges in HERO_POWER_STAT_RANGES.items():
        tier_name = tier.value
        entries: List[Dict] = []
        for stat_type, (low, high) in ranges.items():
            mid = (low + high) / 2

            def _eval(val: float) -> float:
                line = HeroPowerLine(
                    slot=0, stat_type=stat_type, value=val,
                    tier=tier, is_locked=False,
                )
                return calculate_hypothetical_line_dps_value(
                    line, current_stats, current_dps, calc_dps_func,
                )

            entries.append({
                'stat': STAT_DISPLAY_NAMES.get(stat_type, stat_type.value),
                'stat_type': stat_type,
                'low': low,
                'mid': mid,
                'high': high,
                'dps_low': _eval(low),
                'dps_mid': _eval(mid),
                'dps_high': _eval(high),
                'note': NOTES.get(stat_type, ''),
            })
        result[tier_name] = entries
    return result


def compute_best_lines_ranking_for_character(
    calc_dps_func: Callable,
    get_stats_func: Callable,
    level_config: Optional['HeroPowerLevelConfig'] = None,
    top_n: int = 10,
) -> List[Dict]:
    """
    Rank top-N best (tier, stat) combinations to roll for, based on the user's
    actual character stats. Same shape as BEST_LINES_RANKING.

    Probability per line ≈ tier_rate / number_of_stats_at_that_tier
    (uniform-within-tier assumption matches the hardcoded table).
    """
    current_stats = get_stats_func()
    current_dps = calc_dps_func(current_stats) if current_stats else 0
    if current_dps <= 0:
        return []

    # Map tier → rate from level config (% per roll). Default to a reasonable
    # spread when no level config provided so the table still renders.
    if level_config is not None:
        tier_rates = {
            HeroPowerTier.MYSTIC: level_config.mystic_rate,
            HeroPowerTier.LEGENDARY: level_config.legendary_rate,
            HeroPowerTier.UNIQUE: level_config.unique_rate,
            HeroPowerTier.EPIC: level_config.epic_rate,
            HeroPowerTier.RARE: level_config.rare_rate,
            HeroPowerTier.COMMON: level_config.common_rate,
        }
    else:
        tier_rates = {t: 0.0 for t in HeroPowerTier}

    candidates: List[Dict] = []
    for tier, ranges in HERO_POWER_STAT_RANGES.items():
        # Use the FULL stat count per grade from the datamine (includes utility
        # stats not tracked in HERO_POWER_STAT_RANGES) so probabilities reflect
        # what the game actually rolls.
        stats_at_tier = STATS_PER_GRADE.get(tier, len(ranges))
        if stats_at_tier == 0:
            continue
        tier_rate = tier_rates.get(tier, 0.0)
        per_line_prob = tier_rate / stats_at_tier

        for stat_type, (low, high) in ranges.items():
            line = HeroPowerLine(
                slot=0, stat_type=stat_type, value=high,
                tier=tier, is_locked=False,
            )
            max_dps = calculate_hypothetical_line_dps_value(
                line, current_stats, current_dps, calc_dps_func,
            )
            # Format max value
            if stat_type in (HeroPowerStatType.MAIN_STAT_FLAT, HeroPowerStatType.MAX_HP):
                max_value_str = f"{high:.0f}"
            else:
                max_value_str = f"{high:.0f}%"

            candidates.append({
                'tier': tier.value.capitalize(),
                'stat': STAT_DISPLAY_NAMES.get(stat_type, stat_type.value),
                'max_value': max_value_str,
                'max_dps': max_dps,
                'probability': f"{per_line_prob:.2f}%",
            })

    candidates.sort(key=lambda x: x['max_dps'], reverse=True)
    for i, entry in enumerate(candidates[:top_n], 1):
        entry['rank'] = i
    return candidates[:top_n]


# =============================================================================
# BUDGET-DRIVEN OPTIMIZER
# =============================================================================
# Replaces the older strategy-preset system (Conservative / Balanced / Aggressive
# / Efficiency / Line Count). The user enters a medal budget; the optimizer
# enumerates all 2^6 lock subsets (filtered by any user-explicit locks),
# computes expected end-state DPS under each via the closed-form
#   E[max(C, best of N draws)]
# where N is the budget divided by the cost-per-reroll at that lock count, and
# returns the subset with highest expected total. A "cascade ladder" of
# reservation values at each potential lock count is also returned so the user
# can see the aggressive-early / lenient-late lock threshold curve.

def _build_fresh_roll_distribution(
    current_stats: Dict,
    current_dps: float,
    calc_dps_func: Callable,
    level_config: 'HeroPowerLevelConfig',
) -> List[Tuple[float, float]]:
    """
    Returns the discrete distribution of DPS contribution from one fresh-rolled
    hero power line, as a list of (dps_value, probability) tuples sorted by dps.
    Includes utility/defensive stats (dps=0) for their share of probability mass.
    """
    tier_rates_decimal = {
        HeroPowerTier.MYSTIC: level_config.mystic_rate / 100,
        HeroPowerTier.LEGENDARY: level_config.legendary_rate / 100,
        HeroPowerTier.UNIQUE: level_config.unique_rate / 100,
        HeroPowerTier.EPIC: level_config.epic_rate / 100,
        HeroPowerTier.RARE: level_config.rare_rate / 100,
        HeroPowerTier.COMMON: level_config.common_rate / 100,
    }

    raw: List[Tuple[float, float]] = []
    for tier, ranges in HERO_POWER_STAT_RANGES.items():
        tier_rate = tier_rates_decimal.get(tier, 0.0)
        if tier_rate <= 0:
            continue
        n_total = STATS_PER_GRADE.get(tier, len(ranges))
        if n_total <= 0:
            continue
        n_tracked = len(ranges)
        # 3 sample points per stat range, uniform-within-stat assumption
        per_sample = tier_rate * (1.0 / n_total) * (1.0 / 3)
        for stat_type, (lo, hi) in ranges.items():
            mid = (lo + hi) / 2
            for val in (lo, mid, hi):
                line = HeroPowerLine(
                    slot=0, stat_type=stat_type, value=val,
                    tier=tier, is_locked=False,
                )
                dps = calculate_hypothetical_line_dps_value(
                    line, current_stats, current_dps, calc_dps_func,
                )
                raw.append((dps, per_sample))
        # Untracked utility stats contribute dps=0 with their probability share
        n_untracked = n_total - n_tracked
        if n_untracked > 0:
            utility_prob = tier_rate * n_untracked / n_total
            raw.append((0.0, utility_prob))

    # Merge duplicate dps values to keep the CDF clean
    from collections import defaultdict
    merged: Dict[float, float] = defaultdict(float)
    for d, p in raw:
        merged[round(d, 9)] += p  # tiny rounding to merge near-duplicates
    return sorted(merged.items())


def _expected_max_of_current_and_best_of_n(
    current: float,
    N: int,
    distribution: List[Tuple[float, float]],
) -> float:
    """
    Closed-form E[max(current, best of N i.i.d. draws from `distribution`)].
    `distribution` is a sorted ascending list of (dps_value, probability).
    """
    if N <= 0 or not distribution:
        return current

    # F(current) = P(draw <= current)
    F_at_current = sum(p for d, p in distribution if d <= current)
    P_all_below = F_at_current ** N

    # E = current * P(max_N <= current) + sum over d > current of d * P(max_N = d)
    result = current * P_all_below
    cum = F_at_current
    prev_FN = P_all_below
    for d, p in distribution:
        if d <= current:
            continue
        cum += p
        FN = cum ** N
        result += d * (FN - prev_FN)
        prev_FN = FN
    return result


def _expected_best_of_n(
    N: int,
    distribution: List[Tuple[float, float]],
) -> float:
    """E[best of N draws] — equivalent to max(0, M_N) when distribution >= 0."""
    return _expected_max_of_current_and_best_of_n(0.0, N, distribution)


def analyze_budget(
    config: 'HeroPowerConfig',
    level_config: 'HeroPowerLevelConfig',
    budget_medals: float,
    calc_dps_func: Callable,
    get_stats_func: Callable,
) -> Dict:
    """
    Budget-driven hero power optimizer.

    Algorithm matches how rerolls actually work in-game: each reroll
    overwrites the unlocked lines, you don't get to keep "the best so far"
    unless you LOCK that line at the moment you see a great value. So the
    optimal strategy is a threshold rule: lock anything above the
    reservation R_K (where K is the current lock count), reroll the rest.

    For each lock count K in 0..5:
        cost_K = base + K * 43
        N_K = floor(budget / cost_K)   (each reroll attempts all unlocked
                                        slots simultaneously, so the slot
                                        sees N_K attempts)
        R_K = expected best of N_K draws from the fresh-roll DPS distribution

    R_K decreases with K (more locks → higher cost → fewer rerolls → lower
    expected best), which gives the "aggressive at 0 locks, lenient at 5"
    behaviour the user wants.

    Lock-set decision: walk slots in DESCENDING order of current DPS
    contribution; lock a slot if its current contribution beats R_K
    (where K is the size of the lock-set built so far). Stop when no more
    additions qualify.

    User-explicit locks (line.is_locked=True) are forced locked.

    See plan: C:/Users/ianpr/.claude/plans/sorted-nibbling-meteor.md
    """
    current_stats = get_stats_func()
    if not current_stats:
        return {'budget_medals': budget_medals, 'error': 'no current stats'}
    current_dps = calc_dps_func(current_stats)
    if current_dps <= 0:
        return {'budget_medals': budget_medals, 'error': 'current dps is zero'}

    # 1) Per-slot current DPS contributions
    per_slot_dps: Dict[int, float] = {}
    for line in config.lines:
        per_slot_dps[line.slot] = calculate_line_dps_value(
            line, calc_dps_func, get_stats_func,
        )
    current_total_dps_pct = sum(per_slot_dps.values())

    # 2) Fresh-roll DPS distribution
    distribution = _build_fresh_roll_distribution(
        current_stats, current_dps, calc_dps_func, level_config,
    )

    # 3) Cascade ladder. N_K = budget / cost_K (one slot's perspective —
    #    each reroll counts as one attempt for every unlocked slot).
    cascade = []
    for K in range(6):
        cost_K = level_config.get_reroll_cost(K)
        N_K = int(budget_medals / cost_K) if cost_K > 0 else 0
        R_K = _expected_best_of_n(N_K, distribution)
        cascade.append({
            'locks_held': K,
            'cost_per_reroll': cost_K,
            'rerolls_in_budget': N_K,
            'reservation_dps_pct': R_K,
        })

    # 4) Greedy lock decision.
    user_locked = {line.slot for line in config.lines if line.is_locked}
    locked = set(user_locked)
    # Walk slots in DESCENDING current DPS so the best candidates get
    # evaluated first against the (still low) lock count threshold.
    flexible_sorted = sorted(
        (line.slot for line in config.lines if line.slot not in user_locked),
        key=lambda s: per_slot_dps[s],
        reverse=True,
    )
    for slot in flexible_sorted:
        K = len(locked)
        R_K = cascade[min(K, 5)]['reservation_dps_pct']
        if per_slot_dps[slot] >= R_K:
            locked.add(slot)
        # If the slot fails, all remaining slots have even lower current DPS
        # (we sorted descending), but R_K rises only as K grows. So once one
        # fails, none below it could pass either at this K — but K may have
        # changed earlier locks. Re-check each slot independently to be safe.

    final_K = len(locked)
    final_cost = level_config.get_reroll_cost(final_K)
    final_N = int(budget_medals / final_cost) if final_cost > 0 else 0
    final_R = cascade[min(final_K, 5)]['reservation_dps_pct']

    # 5) Expected end-state DPS.
    #    Locked slots keep their current C. Unlocked slots: under a threshold
    #    strategy, if no roll exceeds R within N attempts, the slot ends at
    #    the LAST roll (random fresh value, expected = mean of distribution).
    #    If at least one roll exceeds R, the slot ends at E[fresh | fresh > R].
    expected_total = 0.0
    mean_fresh = sum(d * p for d, p in distribution)
    p_above_R = sum(p for d, p in distribution if d > final_R)
    e_above_R = (
        sum(d * p for d, p in distribution if d > final_R) / p_above_R
        if p_above_R > 0 else mean_fresh
    )

    for line in config.lines:
        slot = line.slot
        C = per_slot_dps[slot]
        if slot in locked:
            expected_total += C
        else:
            # Outcome modelling: the slot ends at max(threshold_hit_value, C)
            # because if we never hit R, we end on a random fresh draw — but
            # we might still keep an existing-above-current value via the
            # threshold strategy IF we set the threshold = max(R, C). Simpler
            # conservative model: the slot ends at E[max(C, fresh_outcome)]
            # under no rerolls if rerolling would be net-negative; otherwise
            # at e_above_R with probability of hitting it within N attempts.
            #
            # Practical model the user can defend:
            #   - With prob P_success = 1 - (1 - p_above_R)^N, we lock at
            #     a value drawn from {d > R} → average e_above_R.
            #   - With prob (1 - P_success), we never hit R → fall back to
            #     last roll (mean_fresh) OR if mean_fresh < C, the user
            #     would have re-locked the original (C). Use max(C, mean).
            P_success = 1 - (1 - p_above_R) ** final_N if final_N > 0 else 0
            fallback = max(C, mean_fresh)
            expected_total += P_success * e_above_R + (1 - P_success) * fallback

    # 6) Per-line analysis with cascade-anchored reasoning.
    line_analysis = []
    for line in config.lines:
        slot = line.slot
        C = per_slot_dps[slot]
        is_locked_rec = slot in locked

        if is_locked_rec:
            stop_value = None
            if slot in user_locked:
                reason = (
                    f"User-locked. Contributes {C:.2f}% DPS."
                )
            else:
                # Find the K-state at which this slot was locked (the K
                # of the lock-set before this slot was added).
                slot_K = list(sorted(locked, key=lambda s: per_slot_dps[s], reverse=True)).index(slot) + len(user_locked)
                reason = (
                    f"Current {C:.2f}% beats the lock threshold "
                    f"{cascade[min(slot_K, 5)]['reservation_dps_pct']:.2f}% "
                    f"at {slot_K} locks. Keep it."
                )
            p_improve = None
        else:
            stop_value = final_R
            p_above = sum(p for d, p in distribution if d > final_R)
            p_improve = p_above
            if p_above > 1e-9:
                expected_attempts = 1.0 / p_above
                expected_cost = expected_attempts * final_cost
                reason = (
                    f"Current {C:.2f}% is below the lock threshold {final_R:.2f}% "
                    f"at {final_K} locks. Reroll until you see >= {final_R:.2f}%, "
                    f"then lock. Avg ~{expected_attempts:,.0f} rerolls "
                    f"(~{expected_cost:,.0f} medals) per success."
                )
            else:
                reason = (
                    f"Threshold {final_R:.2f}% is unreachable in the budget. "
                    f"Reroll, lock whatever lands above {C:.2f}%."
                )

        line_analysis.append({
            'slot': slot,
            'stat': STAT_DISPLAY_NAMES.get(line.stat_type, line.stat_type.value),
            'tier': line.tier.value.capitalize(),
            'value': line.value,
            'current_dps_pct': C,
            'recommendation': 'LOCK' if is_locked_rec else 'REROLL',
            'reasoning': reason,
            'stop_value_pct': stop_value,
            'p_improvement_per_reroll': p_improve,
        })

    has_unlocked = any(la['recommendation'] == 'REROLL' for la in line_analysis)
    expected_medals_spent = float(budget_medals) if has_unlocked else 0.0

    return {
        'budget_medals': float(budget_medals),
        'recommended_locks': sorted(locked),
        'cost_per_reroll': final_cost,
        'expected_rerolls': final_N,
        'expected_medals_spent': expected_medals_spent,
        'current_total_dps_pct': current_total_dps_pct,
        'expected_total_dps_pct': expected_total,
        'expected_gain_pct': expected_total - current_total_dps_pct,
        'cascade': cascade,
        'line_analysis': line_analysis,
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
