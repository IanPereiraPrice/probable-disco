"""
MapleStory Idle - Core Constants
================================
Single source of truth for all game constants, enums, and reference data.

All values have been verified through in-game testing unless noted otherwise.
"""

from enum import Enum
from typing import Dict, Tuple, List


# =============================================================================
# ENUMS
# =============================================================================

class StatStackingType(Enum):
    """
    How different stat types combine in damage calculation.
    Each type has a specific formula.
    """
    # Simple sum: total = sum(sources)
    ADDITIVE = "additive"

    # Final Damage: mult = (1 + FD1) * (1 + FD2) * ... ; total = mult - 1
    MULT_FINAL_DAMAGE = "mult_final_damage"

    # Defense Pen: remaining = (1 - IED1) * (1 - IED2) * ... ; total = 1 - remaining
    # Each source reduces the remaining defense to penetrate
    MULT_DEF_PEN = "mult_def_pen"

    # Attack Speed: atk += (cap - atk) * (source / cap)
    # Diminishing returns approaching the cap (150%)
    DIMINISHING_ATK_SPD = "diminishing_atk_spd"


class Rarity(Enum):
    """Equipment/artifact rarity tiers from lowest to highest."""
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
    EYE = "eye"
    FACE = "face"


# =============================================================================
# CORE DAMAGE CONSTANTS (VERIFIED)
# =============================================================================

# Damage Amplification divisor - verified through scroll testing
# Formula: amp_mult = 1 + (damage_amp% / 396.5)
DAMAGE_AMP_DIVISOR = 396.5

# Hexagon Necklace buff multiplier per stack
# Formula: total_dmg% = base_dmg% * (1.24 ^ stacks)
HEX_MULTIPLIER = 1.24
HEX_MAX_STACKS = 3

# Base damage stats
BASE_CRIT_DMG = 30.0   # Base crit damage % before bonuses
BASE_MIN_DMG = 60.0    # Base min damage %
BASE_MAX_DMG = 100.0   # Base max damage %

# Defense Penetration cap (100%)
DEF_PEN_CAP = 100.0

# Attack Speed cap (150%)
ATK_SPD_CAP = 150.0

# Book of Ancient special effect
# "Critical Damage by 36% of Critical Rate"
BOOK_OF_ANCIENT_CD_RATE = 0.36

# Fire Flower artifact
FIRE_FLOWER_FD_PER_TARGET = 0.012  # 1.2% per target
FIRE_FLOWER_MAX_TARGETS = 10


# =============================================================================
# STAT STACKING BEHAVIOR
# =============================================================================

STAT_STACKING: Dict[str, Tuple[StatStackingType, str]] = {
    # Additive stats - just sum all sources
    "dex_percent": (StatStackingType.ADDITIVE, "All %DEX sources sum together"),
    "dex_flat": (StatStackingType.ADDITIVE, "Sum, then multiplied by (1 + %DEX)"),
    "damage_percent": (StatStackingType.ADDITIVE, "Sum, then Hex Necklace MULTIPLIES the total"),
    "damage_amplification": (StatStackingType.ADDITIVE, "Separate multiplier, scrolls ONLY"),
    "critical_rate": (StatStackingType.ADDITIVE, "All sources sum"),
    "critical_damage": (StatStackingType.ADDITIVE, "All sources sum"),
    "min_dmg_mult": (StatStackingType.ADDITIVE, "All sources sum"),
    "max_dmg_mult": (StatStackingType.ADDITIVE, "All sources sum"),
    "boss_damage": (StatStackingType.ADDITIVE, "All sources sum"),
    "normal_damage": (StatStackingType.ADDITIVE, "All sources sum"),

    # Final Damage - multiplicative: (1+FD1) * (1+FD2) * ...
    "final_damage": (StatStackingType.MULT_FINAL_DAMAGE,
                     "mult = (1+FD1)*(1+FD2)*... ; total = mult - 1"),

    # Defense Penetration - multiplicative on remaining: (1-IED1) * (1-IED2) * ...
    "defense_penetration": (StatStackingType.MULT_DEF_PEN,
                            "remaining = (1-IED1)*(1-IED2)*... ; total = 1 - remaining"),

    # Attack Speed - diminishing returns to cap
    "attack_speed": (StatStackingType.DIMINISHING_ATK_SPD,
                     "atk += (150 - atk) * (source / 150) ; cap at 150%"),
}


# =============================================================================
# ENEMY DEFENSE VALUES
# =============================================================================
# Formula from data mine MonsterTierTable: enemy_def = max(0, 0.028*ch - 0.004)
# Ch1-3: boss tier StatRatio = 1000 (neutral) → 0.0
# Ch4+: boss_raw = 1800 + 50*ch, enemy_def = 0.00056*boss_raw - 1.012 = 0.028*ch - 0.004

ENEMY_DEF_PER_CHAPTER = 0.028
ENEMY_DEF_OFFSET = 0.004


def get_enemy_defense(chapter: int) -> float:
    """Get enemy defense for a chapter from data mine formula."""
    if chapter <= 3:
        return 0.0
    return max(0.0, chapter * ENEMY_DEF_PER_CHAPTER - ENEMY_DEF_OFFSET)


# World Boss Stage 10+ endgame defense (stages 10-20 are capped at this value)
WORLD_BOSS_DEFENSE = 33.764

# Pre-computed values (formula: max(0, 0.028*ch - 0.004), 0 for Ch1-3)
ENEMY_DEFENSE_VALUES: Dict[str, float] = {
    "Chapter 1": 0.0,
    "Chapter 2": 0.0,
    "Chapter 3": 0.0,
    "Chapter 4": 0.108,
    "Chapter 5": 0.136,
    "Chapter 6": 0.164,
    "Chapter 7": 0.192,
    "Chapter 8": 0.220,
    "Chapter 9": 0.248,
    "Chapter 10": 0.276,
    "Chapter 11": 0.304,
    "Chapter 12": 0.332,
    "Chapter 13": 0.360,
    "Chapter 14": 0.388,
    "Chapter 15": 0.416,
    "Chapter 16": 0.444,
    "Chapter 17": 0.472,
    "Chapter 18": 0.500,
    "Chapter 19": 0.528,
    "Chapter 20": 0.556,
    "Chapter 21": 0.584,
    "Chapter 22": 0.612,
    "Chapter 23": 0.640,
    "Chapter 24": 0.668,
    "Chapter 25": 0.696,
    "Chapter 26": 0.724,
    "Chapter 27": 0.752,
    "Chapter 28": 0.780,
    "Chapter 29": 0.808,
    "Chapter 30": 0.836,
    "Chapter 31": 0.864,
    "Chapter 32": 0.892,
    "Chapter 33": 0.920,
    "Chapter 34": 0.948,
    "Chapter 35": 0.976,
    "Chapter 36": 1.004,
    "Chapter 37": 1.032,
    "Chapter 38": 1.060,
    # World Boss — 20 stages
    "World Boss Stage 1": 0.0,
    "World Boss Stage 2": 0.668,
    "World Boss Stage 3": 1.508,
    "World Boss Stage 4": 3.356,
    "World Boss Stage 5": 6.380,
    "World Boss Stage 6": 11.980,
    "World Boss Stage 7": 18.980,
    "World Boss Stage 8": 29.508,
    "World Boss Stage 9": 45.188,
    "World Boss Stage 10": 33.764,
    "World Boss Stage 11": 33.764,
    "World Boss Stage 12": 33.764,
    "World Boss Stage 13": 33.764,
    "World Boss Stage 14": 33.764,
    "World Boss Stage 15": 33.764,
    "World Boss Stage 16": 33.764,
    "World Boss Stage 17": 33.764,
    "World Boss Stage 18": 33.764,
    "World Boss Stage 19": 33.764,
    "World Boss Stage 20": 33.764,
}


# =============================================================================
# EQUIPMENT SLOTS
# =============================================================================

EQUIPMENT_SLOTS: List[str] = [
    'hat', 'top', 'bottom', 'gloves', 'shoes', 'belt',
    'shoulder', 'cape', 'ring', 'necklace', 'eye', 'face'
]


# =============================================================================
# BOWMASTER FINAL DAMAGE SOURCES (for reference)
# =============================================================================
# Note: Actual values depend on equipment and skills - these are examples

BOWMASTER_FD_SOURCES: Dict[str, Dict] = {
    "bottom_pot_bonus": {
        "value": 0.13,
        "condition": "Always",
        "description": "Bottom equipment potential + bonus"
    },
    "guild_skill": {
        "value": 0.10,
        "condition": "Always",
        "description": "Guild passive"
    },
    "extreme_archery_bow": {
        "value": 0.217,
        "condition": "Always",
        "description": "Skill passive (21.7%)"
    },
    "mortal_blow": {
        "value": 0.144,
        "condition": "After 50 hits, 5s duration",
        "description": "Conditional buff"
    },
    "fire_flower": {
        "value": 0.12,
        "condition": "Max 10 targets",
        "description": "Artifact active (1.2% per target)"
    },
}


# =============================================================================
# SHOP PRICES (VERIFIED)
# =============================================================================

SHOP_PRICES: Dict[str, Dict[str, float]] = {
    "regular_cube": {
        "blue_diamond": 1000,
    },
    "bonus_cube": {
        "blue_diamond": 2000,
    },
    "starforce_scroll": {
        "blue_diamond": 500,
    },
    "meso_exchange": {
        "blue_diamond": 6000,
        "meso": 1_500_000,  # 6000 blue diamonds = 1.5M mesos
    },
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
