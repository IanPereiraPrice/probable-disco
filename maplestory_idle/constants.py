"""
MapleStory Idle - Shared Constants
==================================
Enums, constants, and reference data used across modules.
"""

from enum import Enum
from typing import Dict


# =============================================================================
# ENUMS
# =============================================================================

class StatStackingType(Enum):
    """How different stat types combine."""
    ADDITIVE = "additive"
    MULTIPLICATIVE = "multiplicative"


class Rarity(Enum):
    """Equipment/artifact rarity tiers."""
    RARE = "rare"
    NORMAL = "normal"
    EPIC = "epic"
    UNIQUE = "unique"
    LEGENDARY = "legendary"
    MYSTIC = "mystic"
    ANCIENT = "ancient"


class EquipmentSlot(Enum):
    """All equipment slots."""
    WEAPON = "weapon"
    HAT = "hat"
    TOP = "top"
    BOTTOM = "bottom"
    GLOVES = "gloves"
    SHOES = "shoes"
    BELT = "belt"
    SHOULDER = "shoulder"
    CAPE = "cape"
    RING = "ring"
    NECKLACE = "necklace"
    FACE = "face"


# =============================================================================
# CORE CONSTANTS
# =============================================================================

# Damage Amplification divisor (verified through testing)
DAMAGE_AMP_DIVISOR = 396.5

# Hexagon Necklace multiplier per stack
HEX_MULTIPLIER_PER_STACK = 1.24
HEX_MAX_STACKS = 3

# Book of Ancient CR to CD conversion rate
BOOK_OF_ANCIENT_CD_RATE = 0.36

# Fire Flower FD per target
FIRE_FLOWER_FD_PER_TARGET = 0.012
FIRE_FLOWER_MAX_TARGETS = 10


# =============================================================================
# STAT STACKING REFERENCE
# =============================================================================

STAT_STACKING: Dict[str, tuple] = {
    "dex_percent": (StatStackingType.ADDITIVE, "All %DEX sources sum together"),
    "dex_flat": (StatStackingType.ADDITIVE, "Then multiplied by (1 + %DEX)"),
    "damage_percent": (StatStackingType.ADDITIVE, "Hex Necklace MULTIPLIES the total"),
    "damage_amplification": (StatStackingType.ADDITIVE, "Separate multiplier, scrolls ONLY"),
    "final_damage": (StatStackingType.MULTIPLICATIVE, "Each source multiplies separately"),
    "defense_penetration": (StatStackingType.MULTIPLICATIVE, "Each source multiplies"),
    "critical_rate": (StatStackingType.ADDITIVE, "All sources sum"),
    "critical_damage": (StatStackingType.ADDITIVE, "All sources sum"),
    "min_max_damage_mult": (StatStackingType.ADDITIVE, "All sources sum"),
    "boss_normal_damage": (StatStackingType.ADDITIVE, "Additive within category"),
}


# =============================================================================
# ENEMY DEFENSE VALUES BY CHAPTER
# =============================================================================
# Defense values scale approximately linearly with chapter number.
# Based on verified data points: Maple=0, Aquarium(14)=0.388, Mu Lung(27)=0.752
# Approximate formula: def ≈ chapter * 0.028 (rough estimate for missing data)

ENEMY_DEFENSE_VALUES: Dict[str, float] = {
    # Chapters 1-31
    "Chapter 1": 0.0,
    "Chapter 2": 0.03,
    "Chapter 3": 0.06,
    "Chapter 4": 0.09,
    "Chapter 5": 0.12,
    "Chapter 6": 0.15,
    "Chapter 7": 0.18,
    "Chapter 8": 0.21,
    "Chapter 9": 0.24,
    "Chapter 10": 0.27,
    "Chapter 11": 0.30,
    "Chapter 12": 0.33,
    "Chapter 13": 0.36,
    "Chapter 14": 0.388,  # Verified (Aquarium)
    "Chapter 15": 0.41,
    "Chapter 16": 0.44,
    "Chapter 17": 0.47,
    "Chapter 18": 0.50,
    "Chapter 19": 0.53,
    "Chapter 20": 0.56,
    "Chapter 21": 0.59,
    "Chapter 22": 0.62,
    "Chapter 23": 0.65,
    "Chapter 24": 0.68,
    "Chapter 25": 0.71,
    "Chapter 26": 0.74,
    "Chapter 27": 0.752,  # Verified (Mu Lung)
    "Chapter 28": 0.78,
    "Chapter 29": 0.81,
    "Chapter 30": 0.84,
    "Chapter 31": 0.87,
    # World Boss
    "World Boss": 6.527,  # Verified (King Castle Golem)
}


# =============================================================================
# BOWMASTER FINAL DAMAGE SOURCES
# =============================================================================

BOWMASTER_FD_SOURCES: Dict[str, dict] = {
    "bottom_pot_bonus": {"value": 0.13, "condition": "Always", "description": "Bottom equipment potential + bonus"},
    "guild_skill": {"value": 0.10, "condition": "Always", "description": "Guild passive"},
    "extreme_archery_bow": {"value": 0.217, "condition": "Always", "description": "Skill passive"},
    "mortal_blow": {"value": 0.144, "condition": "After 50 hits, 5s", "description": "Conditional buff"},
    "fire_flower": {"value": 0.12, "condition": "Max 10 targets", "description": "Artifact active"},
}


# =============================================================================
# RARITY & TIER MULTIPLIERS
# =============================================================================

RARITY_MULTIPLIERS: Dict[Rarity, float] = {
    Rarity.EPIC: 1.0,
    Rarity.UNIQUE: 2.0,
    Rarity.LEGENDARY: 3.4,
    Rarity.MYSTIC: 5.0,
    Rarity.ANCIENT: 7.0,
}

TIER_MULTIPLIERS: Dict[int, float] = {
    4: 1.0,
    3: 1.15,
    2: 1.32,
    1: 1.52,
}


# =============================================================================
# SHOP PRICES (VERIFIED)
# =============================================================================

SHOP_PRICES: Dict[str, Dict[str, int]] = {
    "starforce_scroll": {
        "blue_diamond": 6000,
        "red_diamond": 1500,
        "arena_coin": 500,
    },
    "potential_cube": {
        "blue_diamond": 3000,
        "red_diamond": 1000,
        "world_boss_coin": 500,
    },
    "bonus_potential_cube": {
        "blue_diamond": 2000,
        "red_diamond": 1500,
        "world_boss_coin": 700,
    },
    "artifact_chest": {
        "blue_diamond": 1500,
        "red_diamond": 1500,
        "arena_coin": 500,
    },
}
