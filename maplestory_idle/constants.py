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
# RARITY DISPLAY (Colors, Abbreviations)
# =============================================================================

RARITY_COLORS: Dict[Rarity, str] = {
    Rarity.NORMAL: "#888888",
    Rarity.RARE: "#5599ff",
    Rarity.EPIC: "#cc77ff",
    Rarity.UNIQUE: "#ffcc00",
    Rarity.LEGENDARY: "#66ff66",
    Rarity.MYSTIC: "#ff6666",
    Rarity.ANCIENT: "#ff9933",
}

RARITY_ABBREVIATIONS: Dict[Rarity, str] = {
    Rarity.NORMAL: "NOR",
    Rarity.RARE: "RAR",
    Rarity.EPIC: "EPC",
    Rarity.UNIQUE: "UNI",
    Rarity.LEGENDARY: "LEG",
    Rarity.MYSTIC: "MYS",
    Rarity.ANCIENT: "ANC",
}


def get_rarity_color(rarity: Rarity) -> str:
    """Get hex color for a rarity tier."""
    return RARITY_COLORS.get(rarity, "#ffffff")


def get_rarity_abbreviation(rarity: Rarity) -> str:
    """Get 3-letter abbreviation for a rarity tier."""
    return RARITY_ABBREVIATIONS.get(rarity, "???")


def rarity_from_string(s: str) -> Rarity:
    """Parse rarity from string (case-insensitive)."""
    try:
        return Rarity(s.lower())
    except ValueError:
        return Rarity.LEGENDARY  # Default


# =============================================================================
# STAT DISPLAY NAMES (Short & Long)
# =============================================================================

# Short names for compact UI (stat_name -> abbreviation)
STAT_SHORT_NAMES: Dict[str, str] = {
    # Main stats %
    "dex_pct": "DEX%",
    "str_pct": "STR%",
    "int_pct": "INT%",
    "luk_pct": "LUK%",
    # Main stats flat
    "dex_flat": "DEX",
    "str_flat": "STR",
    "int_flat": "INT",
    "luk_flat": "LUK",
    # Damage stats
    "damage_pct": "DMG%",
    "crit_rate": "CR%",
    "crit_damage": "CD%",
    "def_pen": "DP%",
    "final_damage": "FD%",
    "min_dmg_mult": "MinD%",
    "max_dmg_mult": "MaxD%",
    # Special stats
    "all_skills": "AS",
    "attack_speed": "AtkSpd%",
    "skill_cd": "CDR",
    "buff_duration": "Buff%",
    "main_stat_per_level": "S/Lv",
    "ba_targets": "BA+",
    # Defense stats
    "defense": "DEF%",
    "max_hp": "HP%",
    "max_mp": "MP%",
}

# Full display names
STAT_DISPLAY_NAMES: Dict[str, str] = {
    # Main stats %
    "dex_pct": "DEX %",
    "str_pct": "STR %",
    "int_pct": "INT %",
    "luk_pct": "LUK %",
    # Main stats flat
    "dex_flat": "DEX (Flat)",
    "str_flat": "STR (Flat)",
    "int_flat": "INT (Flat)",
    "luk_flat": "LUK (Flat)",
    # Damage stats
    "damage_pct": "Damage %",
    "crit_rate": "Crit Rate %",
    "crit_damage": "Crit Damage %",
    "def_pen": "Defense Pen %",
    "final_damage": "Final Damage %",
    "min_dmg_mult": "Min Damage Mult %",
    "max_dmg_mult": "Max Damage Mult %",
    # Special stats
    "all_skills": "All Skills Level",
    "attack_speed": "Attack Speed %",
    "skill_cd": "Skill CD Reduction",
    "buff_duration": "Buff Duration %",
    "main_stat_per_level": "Main Stat per Level",
    "ba_targets": "BA Targets +",
    # Defense stats
    "defense": "Defense %",
    "max_hp": "Max HP %",
    "max_mp": "Max MP %",
}


def get_stat_short_name(stat_name: str) -> str:
    """Get short display name for a stat."""
    return STAT_SHORT_NAMES.get(stat_name, stat_name)


def get_stat_display_name(stat_name: str) -> str:
    """Get full display name for a stat."""
    return STAT_DISPLAY_NAMES.get(stat_name, stat_name.replace("_", " ").title())


def is_percentage_stat(stat_name: str) -> bool:
    """
    Determine if a stat should be displayed as a percentage.

    Flat stats: dex_flat, str_flat, int_flat, luk_flat, all_skills, ba_targets, accuracy
    Percentage stats: Everything else (_pct suffix, damage_pct, crit_rate, etc.)
    """
    # Explicit flat stats (no % sign)
    flat_stats = {
        "dex_flat", "str_flat", "int_flat", "luk_flat",
        "all_skills", "ba_targets", "accuracy",
        "attack_flat", "main_stat_flat",
    }

    # Flat stats by suffix
    if stat_name in flat_stats:
        return False
    if stat_name.endswith('_flat'):
        return False

    # Everything else is a percentage stat
    return True


def format_stat_value(stat_name: str, value: float) -> str:
    """Format a stat value with appropriate suffix."""
    if value == 0:
        return "—"

    if stat_name == "skill_cd":
        return f"-{value:.1f}s"
    elif is_percentage_stat(stat_name):
        return f"+{value:.1f}%"
    else:
        return f"+{int(value)}"


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
