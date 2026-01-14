"""
MapleStory Idle - Standardized Stat Definitions
================================================
Central definition of all stats used throughout the application.

All sources (equipment, artifacts, companions, guild, etc.) should use these
standard stat keys for consistency.

Naming Conventions:
- Flat stats: {stat}_flat (e.g., dex_flat, str_flat)
- Percentage stats: {stat}_pct (e.g., dex_pct, damage_pct)
- Generic main stat: main_stat_flat, main_stat_pct (resolved by job class)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class StatCategory(Enum):
    """Categories of stats for grouping in UI."""
    MAIN_STAT = "main_stat"
    DAMAGE = "damage"
    CRITICAL = "critical"
    ATTACK = "attack"
    SKILL = "skill"
    DEFENSE = "defense"
    UTILITY = "utility"
    MULTIPLICATIVE = "multiplicative"


class StatType(Enum):
    """How the stat is applied in calculations."""
    FLAT = "flat"           # Added directly (e.g., +500 DEX)
    PERCENT = "percent"     # Percentage bonus (e.g., +10% DEX)
    MULTIPLICATIVE = "mult" # Multiplicative stacking (e.g., def pen, final damage)


@dataclass
class StatDefinition:
    """Definition of a stat with all metadata."""
    key: str                          # Internal key (e.g., "dex_flat")
    display_name: str                 # Display name (e.g., "DEX (Flat)")
    category: StatCategory            # Category for grouping
    stat_type: StatType               # How it's applied
    description: str = ""             # Detailed description
    format_suffix: str = ""           # e.g., "%" for percentages
    is_dps_stat: bool = True          # Whether it affects DPS

    def format_value(self, value: float) -> str:
        """Format a value for display."""
        if self.stat_type == StatType.FLAT:
            return f"{value:,.0f}"
        elif self.stat_type == StatType.PERCENT:
            return f"{value:.1f}%"
        else:
            return f"{value:.2f}%"


# =============================================================================
# STAT KEY CONSTANTS (use these for consistency)
# =============================================================================

# Main Stats - Flat
DEX_FLAT = "dex_flat"
STR_FLAT = "str_flat"
INT_FLAT = "int_flat"
LUK_FLAT = "luk_flat"
MAIN_STAT_FLAT = "main_stat_flat"  # Generic - resolved by job class

# Main Stats - Percentage
DEX_PCT = "dex_pct"
STR_PCT = "str_pct"
INT_PCT = "int_pct"
LUK_PCT = "luk_pct"
MAIN_STAT_PCT = "main_stat_pct"  # Generic - resolved by job class

# Damage Stats
DAMAGE_PCT = "damage_pct"
BOSS_DAMAGE = "boss_damage"
NORMAL_DAMAGE = "normal_damage"

# Critical Stats
CRIT_RATE = "crit_rate"
CRIT_DAMAGE = "crit_damage"

# Damage Range Stats
MIN_DMG_MULT = "min_dmg_mult"
MAX_DMG_MULT = "max_dmg_mult"

# Attack Stats
ATTACK_FLAT = "attack_flat"
ATTACK_PCT = "attack_pct"

# Skill Stats
SKILL_DAMAGE = "skill_damage"
ALL_SKILLS = "all_skills"
SKILL_CD = "skill_cd"
BUFF_DURATION = "buff_duration"
SKILL_1ST = "skill_1st"
SKILL_2ND = "skill_2nd"
SKILL_3RD = "skill_3rd"
SKILL_4TH = "skill_4th"

# Utility Stats
ACCURACY = "accuracy"
BA_TARGETS = "ba_targets"
BASIC_ATTACK_DAMAGE = "basic_attack_damage"

# Multiplicative Stats (special handling required)
DEF_PEN = "def_pen"
FINAL_DAMAGE = "final_damage"
ATTACK_SPEED = "attack_speed"

# Defense Stats (non-DPS)
MAX_HP = "max_hp"
DEFENSE = "defense"


# =============================================================================
# STAT DEFINITIONS REGISTRY
# =============================================================================

STAT_DEFINITIONS = {
    # Main Stats - Flat
    DEX_FLAT: StatDefinition(
        key=DEX_FLAT,
        display_name="DEX (Flat)",
        category=StatCategory.MAIN_STAT,
        stat_type=StatType.FLAT,
        description="Flat DEX added before percentage bonuses",
    ),
    STR_FLAT: StatDefinition(
        key=STR_FLAT,
        display_name="STR (Flat)",
        category=StatCategory.MAIN_STAT,
        stat_type=StatType.FLAT,
        description="Flat STR added before percentage bonuses",
    ),
    INT_FLAT: StatDefinition(
        key=INT_FLAT,
        display_name="INT (Flat)",
        category=StatCategory.MAIN_STAT,
        stat_type=StatType.FLAT,
        description="Flat INT added before percentage bonuses",
    ),
    LUK_FLAT: StatDefinition(
        key=LUK_FLAT,
        display_name="LUK (Flat)",
        category=StatCategory.MAIN_STAT,
        stat_type=StatType.FLAT,
        description="Flat LUK added before percentage bonuses",
    ),
    MAIN_STAT_FLAT: StatDefinition(
        key=MAIN_STAT_FLAT,
        display_name="Main Stat (Flat)",
        category=StatCategory.MAIN_STAT,
        stat_type=StatType.FLAT,
        description="Generic main stat - resolves to DEX/STR/INT/LUK based on job",
    ),

    # Main Stats - Percentage
    DEX_PCT: StatDefinition(
        key=DEX_PCT,
        display_name="DEX %",
        category=StatCategory.MAIN_STAT,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Percentage bonus to total DEX",
    ),
    STR_PCT: StatDefinition(
        key=STR_PCT,
        display_name="STR %",
        category=StatCategory.MAIN_STAT,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Percentage bonus to total STR",
    ),
    INT_PCT: StatDefinition(
        key=INT_PCT,
        display_name="INT %",
        category=StatCategory.MAIN_STAT,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Percentage bonus to total INT",
    ),
    LUK_PCT: StatDefinition(
        key=LUK_PCT,
        display_name="LUK %",
        category=StatCategory.MAIN_STAT,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Percentage bonus to total LUK",
    ),
    MAIN_STAT_PCT: StatDefinition(
        key=MAIN_STAT_PCT,
        display_name="Main Stat %",
        category=StatCategory.MAIN_STAT,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Generic main stat % - resolves to DEX%/STR%/INT%/LUK% based on job",
    ),

    # Damage Stats
    DAMAGE_PCT: StatDefinition(
        key=DAMAGE_PCT,
        display_name="Damage %",
        category=StatCategory.DAMAGE,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Additive damage percentage bonus",
    ),
    BOSS_DAMAGE: StatDefinition(
        key=BOSS_DAMAGE,
        display_name="Boss Damage %",
        category=StatCategory.DAMAGE,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Extra damage vs boss monsters",
    ),
    NORMAL_DAMAGE: StatDefinition(
        key=NORMAL_DAMAGE,
        display_name="Normal Damage %",
        category=StatCategory.DAMAGE,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Extra damage vs normal monsters",
    ),

    # Critical Stats
    CRIT_RATE: StatDefinition(
        key=CRIT_RATE,
        display_name="Crit Rate %",
        category=StatCategory.CRITICAL,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Chance to deal critical hits",
    ),
    CRIT_DAMAGE: StatDefinition(
        key=CRIT_DAMAGE,
        display_name="Crit Damage %",
        category=StatCategory.CRITICAL,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Extra damage on critical hits",
    ),

    # Damage Range Stats
    MIN_DMG_MULT: StatDefinition(
        key=MIN_DMG_MULT,
        display_name="Min Damage %",
        category=StatCategory.DAMAGE,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Minimum damage multiplier",
    ),
    MAX_DMG_MULT: StatDefinition(
        key=MAX_DMG_MULT,
        display_name="Max Damage %",
        category=StatCategory.DAMAGE,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Maximum damage multiplier",
    ),

    # Attack Stats
    ATTACK_FLAT: StatDefinition(
        key=ATTACK_FLAT,
        display_name="Attack (Flat)",
        category=StatCategory.ATTACK,
        stat_type=StatType.FLAT,
        description="Flat attack value",
    ),
    ATTACK_PCT: StatDefinition(
        key=ATTACK_PCT,
        display_name="Attack %",
        category=StatCategory.ATTACK,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Percentage bonus to attack",
    ),

    # Skill Stats
    SKILL_DAMAGE: StatDefinition(
        key=SKILL_DAMAGE,
        display_name="Skill Damage %",
        category=StatCategory.SKILL,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Extra damage from active skills",
    ),
    ALL_SKILLS: StatDefinition(
        key=ALL_SKILLS,
        display_name="All Skills",
        category=StatCategory.SKILL,
        stat_type=StatType.FLAT,
        description="Bonus levels to all skills",
    ),
    SKILL_CD: StatDefinition(
        key=SKILL_CD,
        display_name="Skill CD %",
        category=StatCategory.SKILL,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Skill cooldown reduction",
    ),
    BUFF_DURATION: StatDefinition(
        key=BUFF_DURATION,
        display_name="Buff Duration %",
        category=StatCategory.SKILL,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Extended buff duration",
    ),
    SKILL_1ST: StatDefinition(
        key=SKILL_1ST,
        display_name="1st Job Skills",
        category=StatCategory.SKILL,
        stat_type=StatType.FLAT,
        description="Bonus levels to 1st job skills",
    ),
    SKILL_2ND: StatDefinition(
        key=SKILL_2ND,
        display_name="2nd Job Skills",
        category=StatCategory.SKILL,
        stat_type=StatType.FLAT,
        description="Bonus levels to 2nd job skills",
    ),
    SKILL_3RD: StatDefinition(
        key=SKILL_3RD,
        display_name="3rd Job Skills",
        category=StatCategory.SKILL,
        stat_type=StatType.FLAT,
        description="Bonus levels to 3rd job skills",
    ),
    SKILL_4TH: StatDefinition(
        key=SKILL_4TH,
        display_name="4th Job Skills",
        category=StatCategory.SKILL,
        stat_type=StatType.FLAT,
        description="Bonus levels to 4th job skills",
    ),

    # Utility Stats
    ACCURACY: StatDefinition(
        key=ACCURACY,
        display_name="Accuracy",
        category=StatCategory.UTILITY,
        stat_type=StatType.FLAT,
        description="Hit chance against higher-level monsters",
    ),
    BA_TARGETS: StatDefinition(
        key=BA_TARGETS,
        display_name="BA Targets",
        category=StatCategory.UTILITY,
        stat_type=StatType.FLAT,
        description="Additional basic attack targets",
    ),
    BASIC_ATTACK_DAMAGE: StatDefinition(
        key=BASIC_ATTACK_DAMAGE,
        display_name="BA Damage %",
        category=StatCategory.UTILITY,
        stat_type=StatType.PERCENT,
        format_suffix="%",
        description="Extra damage from basic attacks",
    ),

    # Multiplicative Stats
    DEF_PEN: StatDefinition(
        key=DEF_PEN,
        display_name="Defense Penetration %",
        category=StatCategory.MULTIPLICATIVE,
        stat_type=StatType.MULTIPLICATIVE,
        format_suffix="%",
        description="Ignores enemy defense (multiplicative stacking)",
    ),
    FINAL_DAMAGE: StatDefinition(
        key=FINAL_DAMAGE,
        display_name="Final Damage %",
        category=StatCategory.MULTIPLICATIVE,
        stat_type=StatType.MULTIPLICATIVE,
        format_suffix="%",
        description="Final damage multiplier (multiplicative stacking)",
    ),
    ATTACK_SPEED: StatDefinition(
        key=ATTACK_SPEED,
        display_name="Attack Speed %",
        category=StatCategory.MULTIPLICATIVE,
        stat_type=StatType.MULTIPLICATIVE,
        format_suffix="%",
        description="Attack speed bonus (soft cap at 100%)",
    ),

    # Defense Stats
    MAX_HP: StatDefinition(
        key=MAX_HP,
        display_name="Max HP",
        category=StatCategory.DEFENSE,
        stat_type=StatType.FLAT,
        is_dps_stat=False,
        description="Maximum hit points",
    ),
    DEFENSE: StatDefinition(
        key=DEFENSE,
        display_name="Defense",
        category=StatCategory.DEFENSE,
        stat_type=StatType.FLAT,
        is_dps_stat=False,
        description="Damage reduction from enemies",
    ),
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_stat_definition(stat_key: str) -> Optional[StatDefinition]:
    """Get the definition for a stat key."""
    return STAT_DEFINITIONS.get(stat_key)


def get_display_name(stat_key: str) -> str:
    """Get the display name for a stat key."""
    defn = STAT_DEFINITIONS.get(stat_key)
    if defn:
        return defn.display_name
    # Fallback: convert key to title case
    return stat_key.replace("_", " ").title()


def format_stat_value(stat_key: str, value: float) -> str:
    """Format a stat value for display."""
    defn = STAT_DEFINITIONS.get(stat_key)
    if defn:
        return defn.format_value(value)
    # Fallback
    return f"{value:.1f}"


def is_multiplicative_stat(stat_key: str) -> bool:
    """Check if a stat uses multiplicative stacking."""
    defn = STAT_DEFINITIONS.get(stat_key)
    if defn:
        return defn.stat_type == StatType.MULTIPLICATIVE
    return stat_key in {DEF_PEN, FINAL_DAMAGE, ATTACK_SPEED}


def get_main_stat_flat_key(main_stat: str) -> str:
    """Get the flat stat key for a main stat type (e.g., 'dex' -> 'dex_flat')."""
    return f"{main_stat}_flat"


def get_main_stat_pct_key(main_stat: str) -> str:
    """Get the percent stat key for a main stat type (e.g., 'dex' -> 'dex_pct')."""
    return f"{main_stat}_pct"


# =============================================================================
# STAT SETS (for validation and iteration)
# =============================================================================

# Stats that can be added directly with stats[key] += value
ADDITIVE_STATS = {
    DEX_FLAT, STR_FLAT, INT_FLAT, LUK_FLAT,
    DEX_PCT, STR_PCT, INT_PCT, LUK_PCT,
    DAMAGE_PCT, BOSS_DAMAGE, NORMAL_DAMAGE,
    CRIT_RATE, CRIT_DAMAGE,
    MIN_DMG_MULT, MAX_DMG_MULT,
    ATTACK_FLAT, ATTACK_PCT,
    SKILL_DAMAGE, ALL_SKILLS, SKILL_CD, BUFF_DURATION,
    ACCURACY, BA_TARGETS, BASIC_ATTACK_DAMAGE,
    SKILL_1ST, SKILL_2ND, SKILL_3RD, SKILL_4TH,
    MAX_HP, DEFENSE,
}

# Stats that need special handling (collected as lists)
MULTIPLICATIVE_STATS = {DEF_PEN, FINAL_DAMAGE, ATTACK_SPEED}

# Generic stat keys that need to be resolved by job class
GENERIC_STAT_KEYS = {MAIN_STAT_FLAT, MAIN_STAT_PCT}

# All DPS-affecting stats
DPS_STATS = {key for key, defn in STAT_DEFINITIONS.items() if defn.is_dps_stat}
