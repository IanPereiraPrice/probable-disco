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
# Defense values scale linearly: def = chapter * 0.028 (approximate)
# Verified data points: Chapter 1=0, Chapter 14=0.388, Chapter 27=0.752

# Linear coefficient for chapter-based defense calculation
ENEMY_DEF_PER_CHAPTER = 0.028


def get_enemy_defense(chapter: int) -> float:
    """Get enemy defense value for a chapter (linear approximation)."""
    return chapter * ENEMY_DEF_PER_CHAPTER


# Special case: World Boss doesn't follow linear formula
WORLD_BOSS_DEFENSE = 6.527  # King Castle Golem - verified

# Pre-computed common values for convenience
ENEMY_DEFENSE_VALUES: Dict[str, float] = {
    "Chapter 1": 0.0,      # Maple Island - no defense (verified)
    "Chapter 14": 0.388,   # Aquarium (verified)
    "Chapter 27": 0.752,   # Mu Lung (verified)
    "World Boss": 6.527,   # King Castle Golem (verified)
}


# =============================================================================
# EQUIPMENT SLOTS
# =============================================================================

EQUIPMENT_SLOTS: List[str] = [
    'hat', 'top', 'bottom', 'gloves', 'shoes', 'belt',
    'shoulder', 'cape', 'ring', 'necklace', 'face'
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
