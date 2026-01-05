"""
Stat Efficiency Guide - Cross-system stat distribution optimization.

This module helps players understand which stats to prioritize in each system
for optimal long-term stat distribution. Different systems have vastly different
relative efficiency for each stat.

Key insights:
- Equipment Potentials: Best for Damage%, Crit Damage (gloves), Def Pen (shoulder)
- Artifacts: ONLY source for Boss Damage% (equipment has 0%)
- Hero Power: Relatively strong for Min/Max Dmg Mult
- Guild: Only multiplicative Final Damage source
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import Enum


class StatCategory(Enum):
    """Major stat categories for efficiency analysis."""
    DAMAGE_PCT = "Damage %"
    BOSS_DAMAGE = "Boss Damage %"
    NORMAL_DAMAGE = "Normal Damage %"
    CRIT_DAMAGE = "Crit Damage %"
    CRIT_RATE = "Crit Rate %"
    DEF_PEN = "Defense Pen %"
    FINAL_DAMAGE = "Final Damage %"
    MIN_DMG_MULT = "Min Dmg Mult %"
    MAX_DMG_MULT = "Max Dmg Mult %"
    MAIN_STAT_PCT = "Main Stat %"
    MAIN_STAT_FLAT = "Main Stat (Flat)"
    ATTACK_PCT = "Attack %"
    SKILL_DAMAGE = "Skill Damage %"


class SystemType(Enum):
    """Stat source systems."""
    EQUIPMENT = "Equipment"
    ARTIFACTS = "Artifacts"
    HERO_POWER = "Hero Power"
    MAPLE_RANK = "Maple Rank"
    GUILD = "Guild"
    COMPANIONS = "Companions"


# =============================================================================
# MAXIMUM STAT VALUES BY SYSTEM
#
# These are REALISTIC achievable targets, not theoretical maximums:
# - Equipment: 2 good lines per slot at Legendary tier (22 lines across 11 slots)
# - Artifacts: Legendary tier potentials (9 slots across 3 equipped artifacts)
# - Hero Power: Legendary tier lines (Mystic is only 0.12% per roll)
# - Maple Rank: Stage 21 with stats maxed
# - Guild: Level 10 all skills
# - Companions: 3rd/4th job at realistic levels
# =============================================================================

@dataclass
class StatSystemData:
    """Data about a stat in a specific system."""
    max_value: float
    is_best_source: bool = False
    special_slot: Optional[str] = None
    notes: str = ""


# Main data dictionary: SystemType -> StatCategory -> StatSystemData
MAX_STAT_VALUES: Dict[SystemType, Dict[StatCategory, StatSystemData]] = {
    SystemType.EQUIPMENT: {
        StatCategory.DAMAGE_PCT: StatSystemData(
            max_value=550.0,  # 22 lines × 25% at Legendary
            is_best_source=True,
            notes="35%/line at Mystic. Primary source."
        ),
        StatCategory.BOSS_DAMAGE: StatSystemData(
            max_value=0.0,
            is_best_source=False,
            notes="NOT AVAILABLE in equipment potentials!"
        ),
        StatCategory.NORMAL_DAMAGE: StatSystemData(
            max_value=0.0,
            is_best_source=False,
            notes="NOT AVAILABLE in equipment potentials!"
        ),
        StatCategory.CRIT_DAMAGE: StatSystemData(
            max_value=90.0,  # 3 lines × 30% at Legendary (gloves special)
            is_best_source=True,
            special_slot="Gloves",
            notes="50%/line at Mystic. GLOVES SPECIAL - unmatched!"
        ),
        StatCategory.DEF_PEN: StatSystemData(
            max_value=36.0,  # 3 lines × 12% at Legendary (shoulder special)
            is_best_source=True,
            special_slot="Shoulder",
            notes="20%/line at Mystic. SHOULDER SPECIAL."
        ),
        StatCategory.FINAL_DAMAGE: StatSystemData(
            max_value=32.0,  # 4 lines × 8% at Legendary (cape + bottom)
            is_best_source=False,
            special_slot="Cape/Bottom",
            notes="12%/line at Mystic. Final Attack Damage special."
        ),
        StatCategory.MIN_DMG_MULT: StatSystemData(
            max_value=150.0,  # 10 lines × 15% at Legendary
            is_best_source=False,
            notes="25%/line at Mystic."
        ),
        StatCategory.MAX_DMG_MULT: StatSystemData(
            max_value=150.0,
            is_best_source=False,
            notes="25%/line at Mystic."
        ),
        StatCategory.MAIN_STAT_PCT: StatSystemData(
            max_value=264.0,  # 22 lines × 12% at Legendary
            is_best_source=True,
            notes="15%/line at Mystic."
        ),
        StatCategory.CRIT_RATE: StatSystemData(
            max_value=132.0,  # 22 lines × 6% at Legendary (approx)
            is_best_source=False,
            notes="Available but not primary focus."
        ),
    },

    SystemType.ARTIFACTS: {
        StatCategory.DAMAGE_PCT: StatSystemData(
            max_value=63.0,  # 9 slots × 7% at Legendary (conservative)
            is_best_source=False,
            notes="14-24%/slot at Legendary-Mystic. Secondary source."
        ),
        StatCategory.BOSS_DAMAGE: StatSystemData(
            max_value=63.0,
            is_best_source=True,
            notes="14-24%/slot. BEST SOURCE - Equipment has 0%!"
        ),
        StatCategory.NORMAL_DAMAGE: StatSystemData(
            max_value=63.0,
            is_best_source=True,
            notes="14-24%/slot. Primary source for Normal Damage."
        ),
        StatCategory.CRIT_DAMAGE: StatSystemData(
            max_value=31.5,  # 9 slots × 3.5% average
            is_best_source=False,
            notes="Secondary to Equipment (Gloves)."
        ),
        StatCategory.DEF_PEN: StatSystemData(
            max_value=31.5,
            is_best_source=False,
            notes="7-12%/slot. Secondary to Equipment (Shoulder)."
        ),
        StatCategory.CRIT_RATE: StatSystemData(
            max_value=31.5,
            is_best_source=False,
            notes="7-12%/slot."
        ),
        StatCategory.MIN_DMG_MULT: StatSystemData(
            max_value=31.5,
            is_best_source=False,
            notes="7-12%/slot."
        ),
        StatCategory.MAX_DMG_MULT: StatSystemData(
            max_value=31.5,
            is_best_source=False,
            notes="7-12%/slot."
        ),
        StatCategory.MAIN_STAT_PCT: StatSystemData(
            max_value=31.5,
            is_best_source=False,
            notes="7-12%/slot."
        ),
    },

    SystemType.HERO_POWER: {
        StatCategory.DAMAGE_PCT: StatSystemData(
            max_value=70.0,  # ~5 lines × 14% avg at Legendary
            is_best_source=False,
            notes="18-28% per Legendary line. WEAK vs Equipment (550%)."
        ),
        StatCategory.BOSS_DAMAGE: StatSystemData(
            max_value=70.0,
            is_best_source=False,
            notes="18-28% per Legendary line. Secondary to Artifacts."
        ),
        StatCategory.NORMAL_DAMAGE: StatSystemData(
            max_value=70.0,
            is_best_source=False,
            notes="18-28% per Legendary line."
        ),
        StatCategory.DEF_PEN: StatSystemData(
            max_value=35.0,  # 5 lines × 7% avg at Legendary
            is_best_source=False,
            notes="10-14% per Legendary line."
        ),
        StatCategory.MIN_DMG_MULT: StatSystemData(
            max_value=70.0,
            is_best_source=True,
            notes="18-28% per Legendary line. RELATIVELY HIGH here!"
        ),
        StatCategory.MAX_DMG_MULT: StatSystemData(
            max_value=70.0,
            is_best_source=True,
            notes="18-28% per Legendary line. RELATIVELY HIGH here!"
        ),
        StatCategory.CRIT_DAMAGE: StatSystemData(
            max_value=50.0,  # 5 lines × 10% avg at Legendary
            is_best_source=False,
            notes="14-20% per Legendary line."
        ),
        StatCategory.CRIT_RATE: StatSystemData(
            max_value=20.0,
            is_best_source=False,
            notes="4-8% per Legendary line."
        ),
        StatCategory.MAIN_STAT_PCT: StatSystemData(
            max_value=30.0,
            is_best_source=False,
            notes="5-12% per Legendary line."
        ),
    },

    SystemType.MAPLE_RANK: {
        StatCategory.DAMAGE_PCT: StatSystemData(
            max_value=35.0,  # 50 levels × 0.7%
            is_best_source=False,
            notes="Fixed 35% at max. Solid baseline."
        ),
        StatCategory.BOSS_DAMAGE: StatSystemData(
            max_value=20.0,  # 30 levels × 0.667%
            is_best_source=False,
            notes="Fixed 20% at max."
        ),
        StatCategory.NORMAL_DAMAGE: StatSystemData(
            max_value=20.0,
            is_best_source=False,
            notes="Fixed 20% at max."
        ),
        StatCategory.CRIT_DAMAGE: StatSystemData(
            max_value=20.0,  # 30 levels × 0.667%
            is_best_source=False,
            notes="Fixed 20% at max."
        ),
        StatCategory.CRIT_RATE: StatSystemData(
            max_value=10.0,  # 10 levels × 1%
            is_best_source=False,
            notes="Fixed 10% at max."
        ),
        StatCategory.MIN_DMG_MULT: StatSystemData(
            max_value=11.0,  # 20 levels × 0.55%
            is_best_source=False,
            notes="Only 11% max. WEAK for Min/Max Mult."
        ),
        StatCategory.MAX_DMG_MULT: StatSystemData(
            max_value=11.0,
            is_best_source=False,
            notes="Only 11% max. WEAK for Min/Max Mult."
        ),
        StatCategory.SKILL_DAMAGE: StatSystemData(
            max_value=25.0,  # 30 levels × 0.833%
            is_best_source=True,
            notes="Fixed 25% at max. Primary source."
        ),
        StatCategory.MAIN_STAT_FLAT: StatSystemData(
            max_value=8000.0,  # Approximate at Stage 21
            is_best_source=True,
            notes="Major flat main stat source."
        ),
    },

    SystemType.GUILD: {
        StatCategory.FINAL_DAMAGE: StatSystemData(
            max_value=10.0,  # 10 levels × 1%
            is_best_source=True,
            notes="ONLY multiplicative FD source! Very valuable."
        ),
        StatCategory.DAMAGE_PCT: StatSystemData(
            max_value=20.0,  # 10 levels × 2%
            is_best_source=False,
            notes="Small but consistent."
        ),
        StatCategory.BOSS_DAMAGE: StatSystemData(
            max_value=20.0,
            is_best_source=False,
            notes="Secondary to Artifacts."
        ),
        StatCategory.CRIT_DAMAGE: StatSystemData(
            max_value=15.0,  # 10 levels × 1.5%
            is_best_source=False,
            notes="Small contribution."
        ),
        StatCategory.DEF_PEN: StatSystemData(
            max_value=5.0,  # 10 levels × 0.5%
            is_best_source=False,
            notes="Only 5% max. WEAK."
        ),
        StatCategory.MAIN_STAT_PCT: StatSystemData(
            max_value=10.0,
            is_best_source=False,
            notes="Small contribution."
        ),
    },

    SystemType.COMPANIONS: {
        StatCategory.DAMAGE_PCT: StatSystemData(
            max_value=168.0,  # From 3rd/4th job inventory effects
            is_best_source=False,
            notes="From 3rd/4th job inventory effects."
        ),
        StatCategory.MAIN_STAT_FLAT: StatSystemData(
            max_value=2650.0,  # From 2nd job inventory effects
            is_best_source=False,
            notes="From 2nd job inventory effects."
        ),
    },
}


# =============================================================================
# EQUIPMENT SLOT RECOMMENDATIONS
# =============================================================================

@dataclass
class SlotRecommendation:
    """Recommendation for a specific equipment slot."""
    slot: str
    special_stat: Optional[str]
    special_value_legendary: float
    special_value_mystic: float
    primary_recommendation: str
    secondary_stats: List[str]
    avoid_stats: List[str]
    priority_tier: int  # 1 = highest priority, 3 = lowest


EQUIPMENT_SLOT_RECOMMENDATIONS: Dict[str, SlotRecommendation] = {
    "gloves": SlotRecommendation(
        slot="Gloves",
        special_stat="Crit Damage %",
        special_value_legendary=30.0,
        special_value_mystic=50.0,
        primary_recommendation="ALWAYS roll for Crit Damage - 50% per line is UNMATCHED anywhere!",
        secondary_stats=["Damage %", "Main Stat %"],
        avoid_stats=["Defense", "Max HP", "Flat Stats"],
        priority_tier=1,
    ),
    "shoulder": SlotRecommendation(
        slot="Shoulder",
        special_stat="Defense Pen %",
        special_value_legendary=12.0,
        special_value_mystic=20.0,
        primary_recommendation="ALWAYS roll for Def Pen - 20% per line is the BEST source!",
        secondary_stats=["Damage %", "Main Stat %"],
        avoid_stats=["Defense", "Max HP", "Flat Stats"],
        priority_tier=1,
    ),
    "cape": SlotRecommendation(
        slot="Cape",
        special_stat="Final Attack Damage %",
        special_value_legendary=8.0,
        special_value_mystic=12.0,
        primary_recommendation="Final Damage or Damage % - good for FD builds",
        secondary_stats=["Main Stat %", "Min/Max Dmg Mult"],
        avoid_stats=["Defense", "Max HP"],
        priority_tier=2,
    ),
    "bottom": SlotRecommendation(
        slot="Bottom",
        special_stat="Final Attack Damage %",
        special_value_legendary=8.0,
        special_value_mystic=12.0,
        primary_recommendation="Final Damage or Damage % - pairs with Cape for FD",
        secondary_stats=["Main Stat %", "Min/Max Dmg Mult"],
        avoid_stats=["Defense", "Max HP"],
        priority_tier=2,
    ),
    "ring": SlotRecommendation(
        slot="Ring",
        special_stat="All Skills",
        special_value_legendary=12,
        special_value_mystic=16,
        primary_recommendation="Damage % (All Skills is niche for skill builds)",
        secondary_stats=["Main Stat %", "All Skills"],
        avoid_stats=["Defense", "Max HP"],
        priority_tier=3,
    ),
    "necklace": SlotRecommendation(
        slot="Necklace",
        special_stat="All Skills",
        special_value_legendary=12,
        special_value_mystic=16,
        primary_recommendation="Damage % (All Skills is niche for skill builds)",
        secondary_stats=["Main Stat %", "All Skills"],
        avoid_stats=["Defense", "Max HP"],
        priority_tier=3,
    ),
    "belt": SlotRecommendation(
        slot="Belt",
        special_stat="Buff Duration %",
        special_value_legendary=12.0,
        special_value_mystic=20.0,
        primary_recommendation="Damage % (Buff Duration is utility only)",
        secondary_stats=["Main Stat %", "Min/Max Dmg Mult"],
        avoid_stats=["Defense", "Max HP"],
        priority_tier=3,
    ),
    "hat": SlotRecommendation(
        slot="Hat",
        special_stat="Skill Cooldown",
        special_value_legendary=1.5,
        special_value_mystic=2.0,
        primary_recommendation="Damage % or Main Stat % (CD is situational)",
        secondary_stats=["Skill Cooldown", "Min/Max Dmg Mult"],
        avoid_stats=["Defense", "Max HP"],
        priority_tier=3,
    ),
    "face": SlotRecommendation(
        slot="Face",
        special_stat="Main Stat per Level",
        special_value_legendary=8.0,
        special_value_mystic=12.0,
        primary_recommendation="Damage % or Main Stat/Level (if high level)",
        secondary_stats=["Main Stat %"],
        avoid_stats=["Defense", "Max HP"],
        priority_tier=3,
    ),
    "top": SlotRecommendation(
        slot="Top",
        special_stat=None,
        special_value_legendary=0,
        special_value_mystic=0,
        primary_recommendation="Damage % - no special potential",
        secondary_stats=["Main Stat %", "Min/Max Dmg Mult"],
        avoid_stats=["Defense", "Max HP", "Flat Stats"],
        priority_tier=3,
    ),
    "shoes": SlotRecommendation(
        slot="Shoes",
        special_stat=None,
        special_value_legendary=0,
        special_value_mystic=0,
        primary_recommendation="Damage % - no special potential",
        secondary_stats=["Main Stat %", "Min/Max Dmg Mult"],
        avoid_stats=["Defense", "Max HP", "Flat Stats"],
        priority_tier=3,
    ),
}


# =============================================================================
# EFFICIENCY CALCULATION
# =============================================================================

@dataclass
class StatEfficiency:
    """Efficiency score for a stat in a specific system."""
    stat: StatCategory
    system: SystemType
    max_value: float
    efficiency_pct: float  # 0-100, relative to best source
    is_best_source: bool
    star_rating: str  # [*] to [*****]
    notes: str

    @classmethod
    def calculate(cls, stat: StatCategory, system: SystemType) -> Optional["StatEfficiency"]:
        """Calculate efficiency for a stat in a system."""
        system_data = MAX_STAT_VALUES.get(system, {})
        stat_data = system_data.get(stat)

        if stat_data is None or stat_data.max_value == 0:
            return None

        # Find best source for this stat
        best_value = 0
        for sys in SystemType:
            sys_data = MAX_STAT_VALUES.get(sys, {})
            s_data = sys_data.get(stat)
            if s_data and s_data.max_value > best_value:
                best_value = s_data.max_value

        if best_value == 0:
            return None

        efficiency = (stat_data.max_value / best_value) * 100
        star_rating = cls._efficiency_to_stars(efficiency, stat_data.is_best_source)

        return cls(
            stat=stat,
            system=system,
            max_value=stat_data.max_value,
            efficiency_pct=efficiency,
            is_best_source=stat_data.is_best_source,
            star_rating=star_rating,
            notes=stat_data.notes,
        )

    @staticmethod
    def _efficiency_to_stars(efficiency: float, is_best: bool) -> str:
        """Convert efficiency score to star rating."""
        if is_best or efficiency >= 95:
            return "[*****]"
        elif efficiency >= 70:
            return "[****]"
        elif efficiency >= 45:
            return "[***]"
        elif efficiency >= 25:
            return "[**]"
        else:
            return "[*]"


def get_stat_rankings(stat: StatCategory) -> List[StatEfficiency]:
    """
    Get ranked list of systems for a specific stat.
    Returns systems sorted by: best_source first, then efficiency (best first).
    """
    rankings = []

    for system in SystemType:
        eff = StatEfficiency.calculate(stat, system)
        if eff is not None:
            rankings.append(eff)

    # Sort by: is_best_source first, then efficiency (best first)
    rankings.sort(key=lambda x: (x.is_best_source, x.efficiency_pct), reverse=True)

    return rankings


def get_system_priorities(system: SystemType) -> List[StatEfficiency]:
    """
    Get stat priorities for a specific system.
    Returns stats sorted by relative efficiency in this system.
    """
    priorities = []

    for stat in StatCategory:
        eff = StatEfficiency.calculate(stat, system)
        if eff is not None:
            priorities.append(eff)

    # Sort by efficiency (best stats for this system first)
    priorities.sort(key=lambda x: (x.is_best_source, x.efficiency_pct), reverse=True)

    return priorities


# =============================================================================
# KEY INSIGHTS (Pre-computed for display)
# =============================================================================

STAT_INSIGHTS = {
    StatCategory.DAMAGE_PCT: {
        "summary": "Equipment > Artifacts > Maple Rank",
        "key_insight": "Equipment dominates with 550% possible. Focus cubes here.",
        "warning": None,
    },
    StatCategory.BOSS_DAMAGE: {
        "summary": "Artifacts > Hero Power > Guild",
        "key_insight": "Equipment has 0% Boss Damage! Artifacts are essential.",
        "warning": "Equipment potentials cannot roll Boss Damage!",
    },
    StatCategory.CRIT_DAMAGE: {
        "summary": "Equipment (Gloves) >> All others",
        "key_insight": "Gloves special at 50%/line is UNMATCHED anywhere.",
        "warning": None,
    },
    StatCategory.DEF_PEN: {
        "summary": "Equipment (Shoulder) > Artifacts > Hero Power",
        "key_insight": "Shoulder special at 20%/line is the best source.",
        "warning": None,
    },
    StatCategory.FINAL_DAMAGE: {
        "summary": "Guild (multiplicative) + Equipment (Cape/Bottom)",
        "key_insight": "Guild's 10% FD is multiplicative - extremely valuable!",
        "warning": None,
    },
    StatCategory.MIN_DMG_MULT: {
        "summary": "Equipment > Hero Power >> Maple Rank",
        "key_insight": "Hero Power is RELATIVELY strong here (70% vs 11% Maple Rank).",
        "warning": "Maple Rank only gives 11% - very weak.",
    },
    StatCategory.MAX_DMG_MULT: {
        "summary": "Equipment > Hero Power >> Maple Rank",
        "key_insight": "Hero Power is RELATIVELY strong here (70% vs 11% Maple Rank).",
        "warning": "Maple Rank only gives 11% - very weak.",
    },
    StatCategory.NORMAL_DAMAGE: {
        "summary": "Artifacts > Hero Power > Maple Rank",
        "key_insight": "Equipment has 0% Normal Damage - use Artifacts.",
        "warning": "Equipment potentials cannot roll Normal Damage!",
    },
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_priority_slots() -> List[SlotRecommendation]:
    """Get equipment slots sorted by priority (Tier 1 first)."""
    slots = list(EQUIPMENT_SLOT_RECOMMENDATIONS.values())
    slots.sort(key=lambda x: x.priority_tier)
    return slots


def get_best_source_for_stat(stat: StatCategory) -> Optional[Tuple[SystemType, StatSystemData]]:
    """Find the best source system for a specific stat."""
    best_system = None
    best_data = None
    best_value = 0

    for system, stats in MAX_STAT_VALUES.items():
        if stat in stats:
            data = stats[stat]
            if data.is_best_source:
                return (system, data)
            if data.max_value > best_value:
                best_value = data.max_value
                best_system = system
                best_data = data

    return (best_system, best_data) if best_system else None
