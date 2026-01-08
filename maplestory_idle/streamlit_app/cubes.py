"""
MapleStory Idle - Cube System Constants & Calculations
=======================================================
Complete cube mechanics, probabilities, pity system, and cost calculations.
Based on verified data from CUBE_SYSTEM_GUIDE.md

Last Updated: December 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import Enum
import random


# =============================================================================
# ENUMS
# =============================================================================

class PotentialTier(Enum):
    """Potential tier from lowest to highest."""
    NORMAL = "normal"
    RARE = "rare"
    EPIC = "epic"
    UNIQUE = "unique"
    LEGENDARY = "legendary"
    MYSTIC = "mystic"

    def next_tier(self) -> Optional["PotentialTier"]:
        """Get the next tier up."""
        tiers = list(PotentialTier)
        idx = tiers.index(self)
        if idx < len(tiers) - 1:
            return tiers[idx + 1]
        return None

    def prev_tier(self) -> Optional["PotentialTier"]:
        """Get the previous tier."""
        tiers = list(PotentialTier)
        idx = tiers.index(self)
        if idx > 0:
            return tiers[idx - 1]
        return None


class CubeType(Enum):
    """Type of cube."""
    REGULAR = "regular"
    BONUS = "bonus"


class CombatMode(Enum):
    """Combat mode affects how certain stats are valued."""
    STAGE = "stage"              # Mixed: ~50% mob clearing, 50% boss (default)
    BOSS = "boss"                # Single target boss (stage defense)
    WORLD_BOSS = "world_boss"    # Single target world boss (higher defense)


# BA Targets value multiplier by combat mode
# In stage mode, extra targets are valuable for mob clearing
# In boss modes, extra targets are nearly useless (single target)
BA_TARGETS_MODE_MULTIPLIER: Dict[CombatMode, float] = {
    CombatMode.STAGE: 0.5,       # 50% value - half the time you hit mobs
    CombatMode.BOSS: 0.0,        # 0% value - single target, no extra hits
    CombatMode.WORLD_BOSS: 0.0,  # 0% value - single target, no extra hits
}


class StatType(Enum):
    """Types of potential stats."""
    # Individual main stats (% and flat)
    DEX_PCT = "dex_pct"
    STR_PCT = "str_pct"
    INT_PCT = "int_pct"
    LUK_PCT = "luk_pct"
    DEX_FLAT = "dex_flat"
    STR_FLAT = "str_flat"
    INT_FLAT = "int_flat"
    LUK_FLAT = "luk_flat"
    # Legacy combined types (for backwards compatibility)
    MAIN_STAT_PCT = "main_stat_pct"
    MAIN_STAT_FLAT = "main_stat_flat"
    # Other stats
    DEFENSE = "defense"
    MAX_HP = "max_hp"
    MAX_MP = "max_mp"
    CRIT_RATE = "crit_rate"
    ATTACK_SPEED = "attack_speed"
    DAMAGE_PCT = "damage_pct"
    MIN_DMG_MULT = "min_dmg_mult"
    MAX_DMG_MULT = "max_dmg_mult"
    SKILL_CD = "skill_cd"
    BUFF_DURATION = "buff_duration"
    MAIN_STAT_PER_LEVEL = "main_stat_per_level"
    # Special potentials
    CRIT_DAMAGE = "crit_damage"
    DEF_PEN = "def_pen"
    ALL_SKILLS = "all_skills"
    FINAL_ATK_DMG = "final_atk_dmg"
    BA_TARGETS = "ba_targets"  # Basic Attack Targets +X (for tops)


# =============================================================================
# TIER UP PROBABILITIES
# =============================================================================

TIER_UP_RATES: Dict[PotentialTier, float] = {
    PotentialTier.NORMAL: 0.06,      # 6% to Rare
    PotentialTier.RARE: 0.03333,     # 3.333% to Epic
    PotentialTier.EPIC: 0.006,       # 0.6% to Unique
    PotentialTier.UNIQUE: 0.0021,    # 0.21% to Legendary
    PotentialTier.LEGENDARY: 0.0014, # 0.14% to Mystic
    PotentialTier.MYSTIC: 0.0,       # Can't tier up further
}


# =============================================================================
# PITY SYSTEM
# =============================================================================

REGULAR_PITY: Dict[PotentialTier, int] = {
    PotentialTier.NORMAL: 33,
    PotentialTier.RARE: 60,
    PotentialTier.EPIC: 150,
    PotentialTier.UNIQUE: 333,
    PotentialTier.LEGENDARY: 714,
    PotentialTier.MYSTIC: 999999,  # Can't tier up
}

BONUS_PITY: Dict[PotentialTier, int] = {
    PotentialTier.NORMAL: 45,
    PotentialTier.RARE: 85,
    PotentialTier.EPIC: 150,
    PotentialTier.UNIQUE: 417,
    PotentialTier.LEGENDARY: 714,
    PotentialTier.MYSTIC: 999999,
}


# =============================================================================
# SLOT COLOR SYSTEM (YELLOW VS GREY)
# =============================================================================

SLOT_YELLOW_RATES: Dict[int, float] = {
    1: 1.00,   # Slot 1: 100% current tier
    2: 0.24,   # Slot 2: 24% current tier, 76% grey
    3: 0.08,   # Slot 3: 8% current tier, 92% grey
}


# =============================================================================
# POTENTIAL STAT TABLES BY TIER
# =============================================================================

@dataclass
class PotentialStat:
    """A potential stat with value and probability."""
    stat_type: StatType
    value: float
    probability: float
    is_special: bool = False


# Stats available at each tier with their values and probabilities
# Each main stat (DEX/STR/INT/LUK) has 4.5% chance for %, 9.25% chance for flat
POTENTIAL_STATS: Dict[PotentialTier, List[PotentialStat]] = {
    PotentialTier.NORMAL: [
        PotentialStat(StatType.DEX_PCT, 3.0, 0.045),
        PotentialStat(StatType.STR_PCT, 3.0, 0.045),
        PotentialStat(StatType.INT_PCT, 3.0, 0.045),
        PotentialStat(StatType.LUK_PCT, 3.0, 0.045),
        PotentialStat(StatType.DEFENSE, 3.0, 0.09),
    ],
    PotentialTier.RARE: [
        PotentialStat(StatType.DEX_PCT, 4.5, 0.045),
        PotentialStat(StatType.STR_PCT, 4.5, 0.045),
        PotentialStat(StatType.INT_PCT, 4.5, 0.045),
        PotentialStat(StatType.LUK_PCT, 4.5, 0.045),
        PotentialStat(StatType.DEFENSE, 4.5, 0.09),
        PotentialStat(StatType.CRIT_RATE, 4.5, 0.025),
        PotentialStat(StatType.ATTACK_SPEED, 3.5, 0.025),
        PotentialStat(StatType.DAMAGE_PCT, 8.0, 0.04),
        PotentialStat(StatType.MIN_DMG_MULT, 6.0, 0.04),
        PotentialStat(StatType.MAX_DMG_MULT, 6.0, 0.04),
    ],
    PotentialTier.EPIC: [
        PotentialStat(StatType.DEX_PCT, 6.0, 0.045),
        PotentialStat(StatType.STR_PCT, 6.0, 0.045),
        PotentialStat(StatType.INT_PCT, 6.0, 0.045),
        PotentialStat(StatType.LUK_PCT, 6.0, 0.045),
        PotentialStat(StatType.DEX_FLAT, 200, 0.0925),
        PotentialStat(StatType.STR_FLAT, 200, 0.0925),
        PotentialStat(StatType.INT_FLAT, 200, 0.0925),
        PotentialStat(StatType.LUK_FLAT, 200, 0.0925),
        PotentialStat(StatType.DEFENSE, 6.0, 0.09),
        PotentialStat(StatType.MAX_HP, 12.0, 0.09),
        PotentialStat(StatType.MAX_MP, 6.0, 0.09),
        PotentialStat(StatType.CRIT_RATE, 6.0, 0.025),
        PotentialStat(StatType.ATTACK_SPEED, 4.0, 0.025),
        PotentialStat(StatType.DAMAGE_PCT, 12.0, 0.04),
        PotentialStat(StatType.MIN_DMG_MULT, 8.0, 0.04),
        PotentialStat(StatType.MAX_DMG_MULT, 8.0, 0.04),
    ],
    PotentialTier.UNIQUE: [
        PotentialStat(StatType.DEX_PCT, 9.0, 0.045),
        PotentialStat(StatType.STR_PCT, 9.0, 0.045),
        PotentialStat(StatType.INT_PCT, 9.0, 0.045),
        PotentialStat(StatType.LUK_PCT, 9.0, 0.045),
        PotentialStat(StatType.DEX_FLAT, 400, 0.0925),
        PotentialStat(StatType.STR_FLAT, 400, 0.0925),
        PotentialStat(StatType.INT_FLAT, 400, 0.0925),
        PotentialStat(StatType.LUK_FLAT, 400, 0.0925),
        PotentialStat(StatType.DEFENSE, 9.0, 0.09),
        PotentialStat(StatType.MAX_HP, 15.0, 0.09),
        PotentialStat(StatType.MAX_MP, 9.0, 0.09),
        PotentialStat(StatType.CRIT_RATE, 9.0, 0.025),
        PotentialStat(StatType.ATTACK_SPEED, 5.0, 0.025),
        PotentialStat(StatType.DAMAGE_PCT, 18.0, 0.04),
        PotentialStat(StatType.MIN_DMG_MULT, 10.0, 0.04),
        PotentialStat(StatType.MAX_DMG_MULT, 10.0, 0.04),
        PotentialStat(StatType.SKILL_CD, 1.0, 0.01),
    ],
    PotentialTier.LEGENDARY: [
        PotentialStat(StatType.DEX_PCT, 12.0, 0.045),
        PotentialStat(StatType.STR_PCT, 12.0, 0.045),
        PotentialStat(StatType.INT_PCT, 12.0, 0.045),
        PotentialStat(StatType.LUK_PCT, 12.0, 0.045),
        PotentialStat(StatType.DEX_FLAT, 600, 0.0925),
        PotentialStat(StatType.STR_FLAT, 600, 0.0925),
        PotentialStat(StatType.INT_FLAT, 600, 0.0925),
        PotentialStat(StatType.LUK_FLAT, 600, 0.0925),
        PotentialStat(StatType.DEFENSE, 12.0, 0.09),
        PotentialStat(StatType.MAX_HP, 20.0, 0.09),
        PotentialStat(StatType.MAX_MP, 12.0, 0.09),
        PotentialStat(StatType.CRIT_RATE, 12.0, 0.025),
        PotentialStat(StatType.ATTACK_SPEED, 7.0, 0.025),
        PotentialStat(StatType.DAMAGE_PCT, 25.0, 0.04),
        PotentialStat(StatType.MIN_DMG_MULT, 15.0, 0.04),
        PotentialStat(StatType.MAX_DMG_MULT, 15.0, 0.04),
        PotentialStat(StatType.SKILL_CD, 1.5, 0.01),
    ],
    PotentialTier.MYSTIC: [
        PotentialStat(StatType.DEX_PCT, 15.0, 0.045),
        PotentialStat(StatType.STR_PCT, 15.0, 0.045),
        PotentialStat(StatType.INT_PCT, 15.0, 0.045),
        PotentialStat(StatType.LUK_PCT, 15.0, 0.045),
        PotentialStat(StatType.DEX_FLAT, 1000, 0.0925),
        PotentialStat(StatType.STR_FLAT, 1000, 0.0925),
        PotentialStat(StatType.INT_FLAT, 1000, 0.0925),
        PotentialStat(StatType.LUK_FLAT, 1000, 0.0925),
        PotentialStat(StatType.DEFENSE, 15.0, 0.09),
        PotentialStat(StatType.MAX_HP, 25.0, 0.09),
        PotentialStat(StatType.MAX_MP, 15.0, 0.09),
        PotentialStat(StatType.CRIT_RATE, 15.0, 0.025),
        PotentialStat(StatType.ATTACK_SPEED, 10.0, 0.025),
        PotentialStat(StatType.DAMAGE_PCT, 35.0, 0.04),
        PotentialStat(StatType.MIN_DMG_MULT, 25.0, 0.04),
        PotentialStat(StatType.MAX_DMG_MULT, 25.0, 0.04),
        PotentialStat(StatType.SKILL_CD, 2.0, 0.01),
    ],
}


# =============================================================================
# SPECIAL POTENTIALS BY EQUIPMENT SLOT
# =============================================================================

@dataclass
class SpecialPotential:
    """Special potential available on specific equipment."""
    stat_type: StatType
    values: Dict[PotentialTier, float]  # Tier -> Value


SPECIAL_POTENTIALS: Dict[str, SpecialPotential] = {
    "hat": SpecialPotential(
        StatType.SKILL_CD,
        {
            # Skill Cooldown Decrease (seconds)
            # Applies after % reduction, diminishing returns below 7s, 4s minimum
            PotentialTier.EPIC: 0.5,
            PotentialTier.UNIQUE: 1.0,
            PotentialTier.LEGENDARY: 1.5,
            PotentialTier.MYSTIC: 2.0,
        }
    ),
    "gloves": SpecialPotential(
        StatType.CRIT_DAMAGE,
        {
            PotentialTier.UNIQUE: 20.0,
            PotentialTier.LEGENDARY: 30.0,
            PotentialTier.MYSTIC: 50.0,
        }
    ),
    "shoulder": SpecialPotential(
        StatType.DEF_PEN,
        {
            PotentialTier.UNIQUE: 8.0,
            PotentialTier.LEGENDARY: 12.0,
            PotentialTier.MYSTIC: 20.0,
        }
    ),
    "ring": SpecialPotential(
        StatType.ALL_SKILLS,
        {
            PotentialTier.EPIC: 5,
            PotentialTier.UNIQUE: 8,
            PotentialTier.LEGENDARY: 12,
            PotentialTier.MYSTIC: 16,
        }
    ),
    "necklace": SpecialPotential(
        StatType.ALL_SKILLS,
        {
            PotentialTier.EPIC: 5,
            PotentialTier.UNIQUE: 8,
            PotentialTier.LEGENDARY: 12,
            PotentialTier.MYSTIC: 16,
        }
    ),
    "cape": SpecialPotential(
        StatType.FINAL_ATK_DMG,
        {
            PotentialTier.EPIC: 3.0,
            PotentialTier.UNIQUE: 5.0,
            PotentialTier.LEGENDARY: 8.0,
            PotentialTier.MYSTIC: 12.0,
        }
    ),
    "bottom": SpecialPotential(
        StatType.FINAL_ATK_DMG,
        {
            PotentialTier.EPIC: 3.0,
            PotentialTier.UNIQUE: 5.0,
            PotentialTier.LEGENDARY: 8.0,
            PotentialTier.MYSTIC: 12.0,
        }
    ),
    "belt": SpecialPotential(
        StatType.BUFF_DURATION,
        {
            # Buff Duration Increase (%)
            PotentialTier.EPIC: 5.0,
            PotentialTier.UNIQUE: 8.0,
            PotentialTier.LEGENDARY: 12.0,
            PotentialTier.MYSTIC: 20.0,
        }
    ),
    "face": SpecialPotential(
        StatType.MAIN_STAT_PER_LEVEL,
        {
            # +X Main Stat per 1 Level
            PotentialTier.EPIC: 3.0,
            PotentialTier.UNIQUE: 5.0,
            PotentialTier.LEGENDARY: 8.0,
            PotentialTier.MYSTIC: 12.0,
        }
    ),
    "top": SpecialPotential(
        StatType.BA_TARGETS,
        {
            # Basic Attack Targets +X
            # Each +1 target = another full basic attack hit
            # Value depends on combat mode (useless vs single target bosses)
            PotentialTier.UNIQUE: 1,
            PotentialTier.LEGENDARY: 2,
            PotentialTier.MYSTIC: 3,
        }
    ),
}

SPECIAL_POTENTIAL_RATE = 0.01  # 1% base chance


# =============================================================================
# CUBE SHOP PRICES
# =============================================================================

@dataclass
class CubePrice:
    """Price for cubes from different sources."""
    quantity: int
    cost: int
    currency: str
    limit: str  # "unlimited", "X/week", "X/month"

    @property
    def per_unit(self) -> float:
        return self.cost / self.quantity


CUBE_PRICES: Dict[CubeType, Dict[str, CubePrice]] = {
    CubeType.REGULAR: {
        "normal_shop_diamond": CubePrice(1, 3000, "blue_diamond", "unlimited"),
        "normal_shop_heart": CubePrice(1, 1000, "red_diamond", "5/week"),
        "world_boss": CubePrice(1, 500, "wb_coin", "10/week"),
        "monthly_package": CubePrice(5, 3000, "blue_diamond", "10/month"),
        "weekly_package": CubePrice(30, 21000, "blue_diamond", "10/week"),
    },
    CubeType.BONUS: {
        "normal_shop_diamond": CubePrice(3, 6000, "blue_diamond", "100/week"),
        "normal_shop_heart": CubePrice(1, 1500, "red_diamond", "unlimited"),
        "world_boss": CubePrice(1, 700, "wb_coin", "3/week"),
        "monthly_package": CubePrice(5, 6000, "blue_diamond", "10/month"),
        "weekly_package": CubePrice(15, 21000, "blue_diamond", "10/week"),
    },
}


# =============================================================================
# STAT VALUE RANKINGS
# =============================================================================

STAT_TIER_RANKINGS = {
    # S Tier - Best stats
    StatType.DAMAGE_PCT: "S",
    StatType.DEX_PCT: "S",
    StatType.STR_PCT: "S",
    StatType.INT_PCT: "S",
    StatType.LUK_PCT: "S",
    StatType.MAIN_STAT_PCT: "S",  # Legacy
    StatType.CRIT_DAMAGE: "S",
    StatType.DEF_PEN: "S",
    StatType.FINAL_ATK_DMG: "S",
    StatType.ALL_SKILLS: "S",
    # A Tier - Good stats
    StatType.MAX_DMG_MULT: "A",
    StatType.MIN_DMG_MULT: "A",
    StatType.CRIT_RATE: "A",
    # B Tier - Situational
    StatType.ATTACK_SPEED: "B",
    StatType.SKILL_CD: "B",
    StatType.BUFF_DURATION: "B",
    StatType.MAIN_STAT_PER_LEVEL: "A",
    # F Tier - Useless
    StatType.DEFENSE: "F",
    StatType.MAX_HP: "F",
    StatType.MAX_MP: "F",
    StatType.MAIN_STAT_FLAT: "F",  # Legacy
    StatType.DEX_FLAT: "F",
    StatType.STR_FLAT: "F",
    StatType.INT_FLAT: "F",
    StatType.LUK_FLAT: "F",
}


# =============================================================================
# CALCULATIONS
# =============================================================================

def calculate_expected_cubes_to_tier(
    current_tier: PotentialTier,
    cube_type: CubeType = CubeType.REGULAR
) -> Tuple[float, int]:
    """
    Calculate expected cubes to tier up.

    Returns:
        Tuple of (natural_expected, pity_threshold)
    """
    rate = TIER_UP_RATES.get(current_tier, 0)
    pity = REGULAR_PITY if cube_type == CubeType.REGULAR else BONUS_PITY
    pity_threshold = pity.get(current_tier, 999999)

    if rate <= 0:
        return (float('inf'), pity_threshold)

    natural_expected = 1 / rate
    return (natural_expected, pity_threshold)


def expected_cubes_with_pity(p: float, pity: int) -> float:
    """
    Calculate exact expected cubes using truncated geometric distribution.

    This computes E[min(geometric_roll, pity)] where:
    - p = tier-up probability per cube
    - pity = guaranteed tier-up threshold

    Formula: E[X] = (1 - (1-p)^pity) / p

    This accounts for both the random chance to tier up AND the pity floor.
    """
    if p <= 0:
        return float(pity)
    if p >= 1:
        return 1.0

    q = 1 - p  # failure probability
    return (1 - q**pity) / p


def calculate_realistic_cubes_to_tier(
    current_tier: PotentialTier,
    cube_type: CubeType = CubeType.REGULAR
) -> float:
    """
    Calculate expected cubes to tier up using exact mathematical formula.

    Uses truncated geometric distribution that properly accounts for
    both the random tier-up chance AND the pity guarantee.

    Example at Epic→Unique:
    - Old (wrong): 150 cubes (just pity)
    - New (correct): ~117 cubes (accounts for 0.6% chance per cube)
    """
    # Get tier-up probability
    p = TIER_UP_RATES.get(current_tier, 0)

    # Get pity threshold
    pity_table = REGULAR_PITY if cube_type == CubeType.REGULAR else BONUS_PITY
    pity = pity_table.get(current_tier, 999999)

    # Can't tier up from Mystic
    if current_tier == PotentialTier.MYSTIC or p <= 0:
        return float('inf')

    return expected_cubes_with_pity(p, pity)


def calculate_cost_to_tier(
    current_tier: PotentialTier,
    target_tier: PotentialTier,
    cube_type: CubeType = CubeType.REGULAR,
    price_per_cube: float = 600  # Best rate (monthly package)
) -> Tuple[int, float]:
    """
    Calculate cost to reach target tier.

    Returns:
        Tuple of (total_cubes, total_cost)
    """
    if current_tier == target_tier:
        return (0, 0)

    total_cubes = 0
    tier = current_tier

    while tier != target_tier and tier != PotentialTier.MYSTIC:
        cubes_needed = calculate_realistic_cubes_to_tier(tier, cube_type)
        total_cubes += int(cubes_needed)
        tier = tier.next_tier()

    return (total_cubes, total_cubes * price_per_cube)


def calculate_prob_hit_stat_in_n_cubes(
    stat_prob: float,
    n_cubes: int,
    slot: int = 1
) -> float:
    """
    Calculate probability of hitting a stat at least once in N cubes.

    Args:
        stat_prob: Base probability of the stat
        n_cubes: Number of cubes to use
        slot: Which slot (1, 2, or 3)

    Returns:
        Probability of hitting at least once
    """
    yellow_rate = SLOT_YELLOW_RATES.get(slot, 1.0)
    effective_prob = stat_prob * yellow_rate

    # P(at least one) = 1 - P(none) = 1 - (1-p)^n
    return 1 - ((1 - effective_prob) ** n_cubes)


def calculate_expected_cubes_for_stat(
    stat_prob: float,
    slot: int = 1
) -> float:
    """
    Calculate expected cubes to hit a specific stat.
    """
    yellow_rate = SLOT_YELLOW_RATES.get(slot, 1.0)
    effective_prob = stat_prob * yellow_rate

    if effective_prob <= 0:
        return float('inf')

    return 1 / effective_prob


# =============================================================================
# CUBE SIMULATOR
# =============================================================================

@dataclass
class PotentialLine:
    """A single potential line result."""
    slot: int
    stat_type: StatType
    value: float
    is_yellow: bool
    is_special: bool = False


@dataclass
class CubeResult:
    """Result of using a cube."""
    lines: List[PotentialLine]
    tier_up: bool
    new_tier: Optional[PotentialTier]
    pity_count: int


class CubeSimulator:
    """Simulates cube usage with real probabilities."""

    def __init__(
        self,
        equipment_slot: str,
        current_tier: PotentialTier,
        cube_type: CubeType = CubeType.REGULAR
    ):
        self.equipment_slot = equipment_slot
        self.current_tier = current_tier
        self.cube_type = cube_type
        self.pity_count = 0
        self.total_cubes_used = 0
        self.tier_ups = 0
        self.specials_seen = 0

    def _get_pity_threshold(self) -> int:
        """Get pity threshold for current tier."""
        pity = REGULAR_PITY if self.cube_type == CubeType.REGULAR else BONUS_PITY
        return pity.get(self.current_tier, 999999)

    def _roll_tier_up(self) -> bool:
        """Roll for tier up, considering pity."""
        self.pity_count += 1

        # Check pity
        if self.pity_count >= self._get_pity_threshold():
            self.pity_count = 0
            return True

        # Natural roll
        rate = TIER_UP_RATES.get(self.current_tier, 0)
        if random.random() < rate:
            self.pity_count = 0
            return True

        return False

    def _roll_line(self, slot: int) -> PotentialLine:
        """Roll a single potential line."""
        # Determine if yellow or grey
        yellow_rate = SLOT_YELLOW_RATES.get(slot, 1.0)
        is_yellow = random.random() < yellow_rate

        # Determine tier for this line
        line_tier = self.current_tier if is_yellow else self.current_tier.prev_tier()
        if line_tier is None:
            line_tier = self.current_tier

        # Check for special potential (1% chance, only on yellow)
        if is_yellow and self.equipment_slot in SPECIAL_POTENTIALS:
            if random.random() < SPECIAL_POTENTIAL_RATE:
                special = SPECIAL_POTENTIALS[self.equipment_slot]
                if line_tier in special.values:
                    self.specials_seen += 1
                    return PotentialLine(
                        slot=slot,
                        stat_type=special.stat_type,
                        value=special.values[line_tier],
                        is_yellow=True,
                        is_special=True
                    )

        # Roll regular stat
        stats = POTENTIAL_STATS.get(line_tier, [])
        if not stats:
            # Fallback
            return PotentialLine(slot, StatType.DEFENSE, 3.0, is_yellow)

        # Weighted random selection
        total_prob = sum(s.probability for s in stats)
        roll = random.random() * total_prob
        cumulative = 0

        for stat in stats:
            cumulative += stat.probability
            if roll <= cumulative:
                return PotentialLine(
                    slot=slot,
                    stat_type=stat.stat_type,
                    value=stat.value,
                    is_yellow=is_yellow
                )

        # Fallback to last stat
        stat = stats[-1]
        return PotentialLine(slot, stat.stat_type, stat.value, is_yellow)

    def use_cube(self) -> CubeResult:
        """Use a cube and return the result."""
        self.total_cubes_used += 1

        # Roll all 3 lines
        lines = [self._roll_line(i + 1) for i in range(3)]

        # Roll for tier up
        tier_up = self._roll_tier_up()
        new_tier = None

        if tier_up:
            self.tier_ups += 1
            new_tier = self.current_tier.next_tier()
            if new_tier:
                self.current_tier = new_tier

        return CubeResult(
            lines=lines,
            tier_up=tier_up,
            new_tier=new_tier,
            pity_count=self.pity_count
        )

    def simulate_until_tier(
        self,
        target_tier: PotentialTier,
        max_cubes: int = 10000
    ) -> Tuple[int, bool]:
        """
        Simulate cubing until reaching target tier.

        Returns:
            Tuple of (cubes_used, success)
        """
        start_cubes = self.total_cubes_used

        while self.current_tier != target_tier and self.total_cubes_used - start_cubes < max_cubes:
            self.use_cube()

        return (self.total_cubes_used - start_cubes, self.current_tier == target_tier)

    def get_stats(self) -> Dict:
        """Get simulation statistics."""
        return {
            "total_cubes": self.total_cubes_used,
            "tier_ups": self.tier_ups,
            "specials_seen": self.specials_seen,
            "current_tier": self.current_tier.value,
            "current_pity": self.pity_count,
            "pity_threshold": self._get_pity_threshold(),
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_stat_display_name(stat_type: StatType) -> str:
    """Get human-readable stat name."""
    names = {
        # Individual main stats
        StatType.DEX_PCT: "DEX %",
        StatType.STR_PCT: "STR %",
        StatType.INT_PCT: "INT %",
        StatType.LUK_PCT: "LUK %",
        StatType.DEX_FLAT: "DEX (Flat)",
        StatType.STR_FLAT: "STR (Flat)",
        StatType.INT_FLAT: "INT (Flat)",
        StatType.LUK_FLAT: "LUK (Flat)",
        # Legacy
        StatType.MAIN_STAT_PCT: "Main Stat %",
        StatType.MAIN_STAT_FLAT: "Main Stat (Flat)",
        # Other stats
        StatType.DEFENSE: "Defense %",
        StatType.MAX_HP: "Max HP %",
        StatType.MAX_MP: "Max MP %",
        StatType.CRIT_RATE: "Crit Rate %",
        StatType.ATTACK_SPEED: "Attack Speed %",
        StatType.DAMAGE_PCT: "Damage %",
        StatType.MIN_DMG_MULT: "Min Damage Mult %",
        StatType.MAX_DMG_MULT: "Max Damage Mult %",
        StatType.SKILL_CD: "Skill CD Reduction",
        StatType.BUFF_DURATION: "Buff Duration %",
        StatType.MAIN_STAT_PER_LEVEL: "Main Stat per Level",
        StatType.CRIT_DAMAGE: "Crit Damage %",
        StatType.DEF_PEN: "Defense Pen %",
        StatType.ALL_SKILLS: "All Skills Level",
        StatType.FINAL_ATK_DMG: "Final Attack Damage %",
        StatType.BA_TARGETS: "BA Targets +",
    }
    return names.get(stat_type, stat_type.value)


def get_tier_color(tier: PotentialTier) -> str:
    """Get color for tier display."""
    colors = {
        PotentialTier.NORMAL: "#888888",
        PotentialTier.RARE: "#4a9eff",
        PotentialTier.EPIC: "#9d65c9",
        PotentialTier.UNIQUE: "#ffd700",
        PotentialTier.LEGENDARY: "#00ff88",
        PotentialTier.MYSTIC: "#ff4444",
    }
    return colors.get(tier, "#ffffff")


def format_line(line: PotentialLine) -> str:
    """Format a potential line for display."""
    name = get_stat_display_name(line.stat_type)
    color = "Y" if line.is_yellow else "G"
    special = " [SPECIAL]" if line.is_special else ""

    # Flat stats (no % sign)
    flat_stats = {
        StatType.MAIN_STAT_FLAT, StatType.DEX_FLAT, StatType.STR_FLAT,
        StatType.INT_FLAT, StatType.LUK_FLAT, StatType.ALL_SKILLS
    }

    if line.stat_type in flat_stats:
        return f"[{color}] {name}: +{int(line.value)}{special}"
    elif line.stat_type == StatType.SKILL_CD:
        return f"[{color}] {name}: -{line.value}s{special}"
    else:
        return f"[{color}] {name}: +{line.value:.1f}%{special}"


# =============================================================================
# CACHED ROLL DISTRIBUTION SYSTEM
# =============================================================================
# Optimization: Pre-generate random rolls once per tier, then score them
# with the player's DPS function. This avoids running Monte Carlo per slot.

@dataclass
class CachedRoll:
    """A single pre-generated roll (without slot-specific special potential)."""
    lines: List[PotentialLine]
    yellow_count: int
    # These are populated when scoring with a specific DPS function:
    score: float = 0.0
    dps_gain_pct: float = 0.0


class CachedRollDistribution:
    """
    Pre-generated roll distribution for efficient cube calculations.

    Usage:
        # Generate once per tier (can be reused across all slots)
        cache = CachedRollDistribution(PotentialTier.MYSTIC, n_rolls=5000)

        # Score for a specific slot with player's DPS function
        scored_rolls = cache.score_rolls_for_slot(
            slot="gloves",
            dps_calc_func=my_dps_func,
            current_dps=1000000,
            main_stat_type=StatType.DEX_PCT
        )

        # Get statistics
        prob_above_60 = cache.get_prob_above_score(60)
        expected_cubes = cache.get_expected_cubes_to_score(current_score, target_score)
    """

    def __init__(self, tier: PotentialTier, n_rolls: int = 5000):
        self.tier = tier
        self.n_rolls = n_rolls
        self._rolls: List[CachedRoll] = []
        self._scored = False
        self._slot = None
        self._generate_rolls()

    def _generate_rolls(self):
        """Pre-generate n_rolls random potential rolls for this tier."""
        for _ in range(self.n_rolls):
            lines = []
            yellow_count = 0

            for slot_num in range(1, 4):
                # Determine if yellow or grey
                yellow_rate = SLOT_YELLOW_RATES.get(slot_num, 1.0)
                is_yellow = random.random() < yellow_rate

                if is_yellow:
                    yellow_count += 1

                # Determine tier for this line
                line_tier = self.tier if is_yellow else self.tier.prev_tier()
                if line_tier is None:
                    line_tier = self.tier

                # Roll regular stat (special potential handled separately per-slot)
                stats = POTENTIAL_STATS.get(line_tier, [])
                if not stats:
                    lines.append(PotentialLine(slot_num, StatType.DEFENSE, 3.0, is_yellow))
                    continue

                # Weighted random selection
                total_prob = sum(s.probability for s in stats)
                roll = random.random() * total_prob
                cumulative = 0

                for stat in stats:
                    cumulative += stat.probability
                    if roll <= cumulative:
                        lines.append(PotentialLine(
                            slot=slot_num,
                            stat_type=stat.stat_type,
                            value=stat.value,
                            is_yellow=is_yellow,
                            is_special=False
                        ))
                        break

            self._rolls.append(CachedRoll(
                lines=lines,
                yellow_count=yellow_count,
            ))

    def score_rolls_for_slot(
        self,
        slot: str,
        dps_calc_func,
        current_dps: float,
        main_stat_type: StatType = StatType.DEX_PCT,
    ) -> List[CachedRoll]:
        """
        Score all cached rolls for a specific equipment slot.

        NEW PERCENTILE-BASED SCORING:
        - Score = percentile of this roll's DPS gain among all possible rolls
        - If roll is better than 70% of possibilities, score = 70
        - This scores the COMBINATION, not individual lines

        OPTIMIZED: Pre-calculates stat weights once, then scores all rolls
        using simple multiplication instead of calling dps_calc_func per roll.

        Returns the scored rolls sorted by DPS gain descending.
        """
        # OPTIMIZATION: Pre-calculate DPS weight per stat type (call dps_calc_func ~20 times)
        stat_weights = self._calculate_stat_weights(slot, dps_calc_func, current_dps, main_stat_type)

        # Check if slot has special potential
        has_special = slot in SPECIAL_POTENTIALS
        special_def = SPECIAL_POTENTIALS.get(slot) if has_special else None

        scored_rolls = []

        for cached_roll in self._rolls:
            # Create a copy of lines that may include special potential
            lines = []
            for line in cached_roll.lines:
                # For yellow lines, check if this should be a special (1% chance)
                if has_special and line.is_yellow and random.random() < SPECIAL_POTENTIAL_RATE:
                    if self.tier in special_def.values:
                        lines.append(PotentialLine(
                            slot=line.slot,
                            stat_type=special_def.stat_type,
                            value=special_def.values[self.tier],
                            is_yellow=True,
                            is_special=True
                        ))
                        continue
                lines.append(line)

            # Calculate total DPS gain for this roll combination
            total_dps_gain = 0.0
            for line in lines:
                # Get DPS contribution from weights
                # Special potentials use tuple key (stat_type, True)
                if line.is_special:
                    weight = stat_weights.get((line.stat_type, True), 0.0)
                    base_value = self._get_special_base_value(slot, line.stat_type)
                else:
                    weight = stat_weights.get(line.stat_type, 0.0)
                    base_value = self._get_base_stat_value(line.stat_type)

                line_dps_gain = weight * (line.value / base_value) if base_value > 0 else 0
                total_dps_gain += line_dps_gain

            scored_rolls.append(CachedRoll(
                lines=lines,
                yellow_count=cached_roll.yellow_count,
                score=0.0,  # Will be set after percentile calculation
                dps_gain_pct=total_dps_gain,
            ))

        # Sort by DPS gain descending to calculate percentiles
        scored_rolls.sort(key=lambda r: r.dps_gain_pct, reverse=True)

        # Calculate percentile-based scores
        # Score = what percentage of rolls this roll beats
        n = len(scored_rolls)
        for i, roll in enumerate(scored_rolls):
            # Roll at index 0 (best) beats 100% of rolls
            # Roll at index n-1 (worst) beats 0% of rolls
            percentile = ((n - 1 - i) / (n - 1)) * 100 if n > 1 else 50
            roll.score = percentile

        self._scored = True
        self._slot = slot
        self._scored_rolls = scored_rolls

        return scored_rolls

    def _calculate_stat_weights(
        self,
        slot: str,
        dps_calc_func,
        current_dps: float,
        main_stat_type: StatType,
    ) -> Dict[StatType, float]:
        """
        Pre-calculate DPS weight for each stat type.

        Returns dict mapping StatType -> DPS gain % for base value of that stat.
        This is called once per slot, not per roll.
        """
        weights = {}

        # Get stats available at this tier
        tier_stats = POTENTIAL_STATS.get(self.tier, [])

        # Calculate weight for each unique stat type
        tested_stats = set()
        for stat in tier_stats:
            if stat.stat_type in tested_stats:
                continue
            tested_stats.add(stat.stat_type)

            # Test this stat alone
            test_lines = [PotentialLine(1, stat.stat_type, stat.value, True, False)]
            new_dps = dps_calc_func(test_lines)
            gain = ((new_dps / current_dps) - 1) * 100 if current_dps > 0 else 0

            # Store weight normalized to base value
            weights[stat.stat_type] = gain

        # Also calculate special potential weight if available
        if slot in SPECIAL_POTENTIALS:
            special = SPECIAL_POTENTIALS[slot]
            if self.tier in special.values:
                test_lines = [PotentialLine(1, special.stat_type, special.values[self.tier], True, True)]
                new_dps = dps_calc_func(test_lines)
                gain = ((new_dps / current_dps) - 1) * 100 if current_dps > 0 else 0
                # Mark special stats with a special key
                weights[(special.stat_type, True)] = gain

        return weights

    def _get_base_stat_value(self, stat_type: StatType) -> float:
        """Get the base value for a stat type at this tier (for weight calculation)."""
        tier_stats = POTENTIAL_STATS.get(self.tier, [])
        for stat in tier_stats:
            if stat.stat_type == stat_type:
                return stat.value
        return 1.0  # Fallback

    def _get_special_base_value(self, slot: str, stat_type: StatType) -> float:
        """Get the base value for a special potential at this tier."""
        if slot in SPECIAL_POTENTIALS:
            special = SPECIAL_POTENTIALS[slot]
            if self.tier in special.values:
                return special.values[self.tier]
        return 1.0  # Fallback

    def get_prob_above_score(self, target_score: float) -> float:
        """Get probability of rolling above a target score."""
        if not self._scored:
            raise RuntimeError("Must call score_rolls_for_slot first")

        count = sum(1 for r in self._scored_rolls if r.score >= target_score)
        return count / len(self._scored_rolls)

    def get_percentile_of_score(self, score: float) -> float:
        """Get percentile rank of a score (0-100, higher = better than more rolls)."""
        if not self._scored:
            raise RuntimeError("Must call score_rolls_for_slot first")

        count_below = sum(1 for r in self._scored_rolls if r.score < score)
        return (count_below / len(self._scored_rolls)) * 100

    def get_percentile_of_dps_gain(self, dps_gain: float) -> float:
        """
        Get percentile rank of a DPS gain (0-100).
        Score 70 means this roll beats 70% of possible rolls.
        """
        if not self._scored:
            raise RuntimeError("Must call score_rolls_for_slot first")

        count_below = sum(1 for r in self._scored_rolls if r.dps_gain_pct < dps_gain)
        return (count_below / len(self._scored_rolls)) * 100

    def get_dps_distribution_stats(self) -> Dict[str, float]:
        """Get DPS gain distribution statistics for understanding score thresholds."""
        if not self._scored:
            raise RuntimeError("Must call score_rolls_for_slot first")

        dps_gains = sorted([r.dps_gain_pct for r in self._scored_rolls])
        n = len(dps_gains)

        return {
            "min": dps_gains[0],
            "p10": dps_gains[int(n * 0.1)],
            "p25": dps_gains[int(n * 0.25)],
            "median": dps_gains[int(n * 0.5)],
            "p75": dps_gains[int(n * 0.75)],
            "p90": dps_gains[int(n * 0.9)],
            "max": dps_gains[-1],
        }

    def get_expected_cubes_to_improve(self, current_score: float) -> float:
        """
        Get expected cubes to get any improvement over current score.

        Uses the formula: E[cubes] = 1 / P(improvement)
        """
        prob_improve = 1 - (self.get_percentile_of_score(current_score) / 100)
        if prob_improve <= 0:
            return float('inf')
        return 1 / prob_improve

    def get_expected_cubes_to_score(self, target_score: float) -> float:
        """
        Get expected cubes to reach a target score.

        Uses the formula: E[cubes] = 1 / P(score >= target)
        """
        prob = self.get_prob_above_score(target_score)
        if prob <= 0:
            return float('inf')
        return 1 / prob

    def get_expected_cubes_to_dps_gain(self, target_dps_gain: float) -> float:
        """
        Get expected cubes to reach a target DPS gain.

        More intuitive than score-based: "how many cubes to get 10% DPS?"
        Uses the formula: E[cubes] = 1 / P(dps_gain >= target)
        """
        if not self._scored:
            raise RuntimeError("Must call score_rolls_for_slot first")

        count_above = sum(1 for r in self._scored_rolls if r.dps_gain_pct >= target_dps_gain)
        prob = count_above / len(self._scored_rolls)
        if prob <= 0:
            return float('inf')
        return 1 / prob

    def get_expected_cubes_to_improve_dps(self, current_dps_gain: float) -> float:
        """
        Get expected cubes to get any DPS improvement over current.

        This is what users actually care about - getting a better roll.
        """
        if not self._scored:
            raise RuntimeError("Must call score_rolls_for_slot first")

        count_better = sum(1 for r in self._scored_rolls if r.dps_gain_pct > current_dps_gain)
        prob = count_better / len(self._scored_rolls)
        if prob <= 0:
            return float('inf')
        return 1 / prob

    def get_prob_improve_dps_in_n_cubes(self, current_dps_gain: float, n_cubes: int) -> float:
        """Get probability of improving DPS in N cubes."""
        if not self._scored:
            raise RuntimeError("Must call score_rolls_for_slot first")

        count_better = sum(1 for r in self._scored_rolls if r.dps_gain_pct > current_dps_gain)
        prob_single = count_better / len(self._scored_rolls)
        if prob_single <= 0:
            return 0.0
        # P(improve in N) = 1 - P(no improvement)^N
        return 1 - ((1 - prob_single) ** n_cubes)

    def get_expected_dps_gain_when_improving(self, current_dps_gain: float) -> float:
        """
        Get the expected (median) DPS gain when you DO get an improvement.

        Uses MEDIAN instead of mean because the distribution is heavily skewed
        (special stats create huge outliers that inflate the mean).

        Returns: Expected additional DPS % when you roll better than current.
        """
        if not self._scored:
            raise RuntimeError("Must call score_rolls_for_slot first")

        better_rolls = [r for r in self._scored_rolls if r.dps_gain_pct > current_dps_gain]
        if not better_rolls:
            return 0.0

        # Sort by DPS gain and get MEDIAN (not mean - distribution is skewed)
        better_dps_gains = sorted([r.dps_gain_pct for r in better_rolls])
        median_idx = len(better_dps_gains) // 2
        median_better_dps = better_dps_gains[median_idx]

        # Net improvement = median better roll - current roll
        return median_better_dps - current_dps_gain

    def get_score_distribution(self) -> Dict[str, float]:
        """Get score distribution statistics."""
        if not self._scored:
            raise RuntimeError("Must call score_rolls_for_slot first")

        scores = [r.score for r in self._scored_rolls]
        scores.sort()
        n = len(scores)

        return {
            "min": scores[0],
            "p10": scores[int(n * 0.1)],
            "p25": scores[int(n * 0.25)],
            "median": scores[int(n * 0.5)],
            "p75": scores[int(n * 0.75)],
            "p90": scores[int(n * 0.9)],
            "max": scores[-1],
            "mean": sum(scores) / n,
        }

    def get_distribution_data_for_chart(self, num_points: int = 101) -> Dict:
        """
        Get distribution data formatted for Plotly chart with hover info.

        Returns dict with:
        - percentiles: List[int] (0-100)
        - dps_gains: List[float] (DPS % at each percentile)
        - lines_text: List[str] (formatted lines text for hover)
        - representative_rolls: List[CachedRoll] (the actual roll objects)
        """
        if not self._scored:
            raise RuntimeError("Must call score_rolls_for_slot first")

        # Sort rolls by DPS gain (ascending - worst to best)
        sorted_rolls = sorted(self._scored_rolls, key=lambda r: r.dps_gain_pct)
        n = len(sorted_rolls)

        percentiles = []
        dps_gains = []
        lines_text = []
        representative_rolls = []

        for i in range(num_points):
            percentile = i  # 0 to 100
            # Map percentile to index in sorted rolls
            idx = min(int(percentile / 100 * n), n - 1)
            roll = sorted_rolls[idx]

            percentiles.append(percentile)
            dps_gains.append(roll.dps_gain_pct)
            lines_text.append(format_lines_for_hover(roll.lines))
            representative_rolls.append(roll)

        return {
            "percentiles": percentiles,
            "dps_gains": dps_gains,
            "lines_text": lines_text,
            "representative_rolls": representative_rolls,
        }

    def get_roll_at_percentile(self, percentile: float) -> Optional['CachedRoll']:
        """Get a representative roll at a specific percentile (0-100)."""
        if not self._scored:
            raise RuntimeError("Must call score_rolls_for_slot first")

        sorted_rolls = sorted(self._scored_rolls, key=lambda r: r.dps_gain_pct)
        n = len(sorted_rolls)
        idx = min(int(percentile / 100 * n), n - 1)
        return sorted_rolls[idx]


def format_lines_for_hover(lines: List[PotentialLine]) -> str:
    """
    Format potential lines for display in chart hover tooltip.

    Example output:
    "DEX +8% (Yellow)
    Crit Rate +3%
    Damage +5%"
    """
    formatted = []
    for line in lines:
        name = get_stat_display_name(line.stat_type)
        tier_indicator = " (Yellow)" if line.is_yellow else ""
        special_indicator = " [SPECIAL]" if line.is_special else ""

        # Flat stats (no % sign)
        flat_stats = {
            StatType.MAIN_STAT_FLAT, StatType.DEX_FLAT, StatType.STR_FLAT,
            StatType.INT_FLAT, StatType.LUK_FLAT, StatType.ALL_SKILLS
        }

        if line.stat_type in flat_stats:
            formatted.append(f"{name}: +{int(line.value)}{tier_indicator}{special_indicator}")
        elif line.stat_type == StatType.SKILL_CD:
            formatted.append(f"{name}: -{line.value}s{tier_indicator}{special_indicator}")
        else:
            formatted.append(f"{name}: +{line.value:.1f}%{tier_indicator}{special_indicator}")

    return "<br>".join(formatted)


# Global cache for roll distributions (one per tier)
_ROLL_DISTRIBUTION_CACHE: Dict[PotentialTier, CachedRollDistribution] = {}


def get_cached_roll_distribution(tier: PotentialTier, n_rolls: int = 5000) -> CachedRollDistribution:
    """Get or create a cached roll distribution for a tier."""
    if tier not in _ROLL_DISTRIBUTION_CACHE:
        _ROLL_DISTRIBUTION_CACHE[tier] = CachedRollDistribution(tier, n_rolls)
    return _ROLL_DISTRIBUTION_CACHE[tier]


def clear_roll_distribution_cache():
    """Clear the roll distribution cache (call when tier probabilities change)."""
    global _ROLL_DISTRIBUTION_CACHE
    _ROLL_DISTRIBUTION_CACHE = {}


# =============================================================================
# EXACT PROBABILITY DISTRIBUTION SYSTEM
# =============================================================================
# Instead of Monte Carlo sampling, enumerate all unique DPS outcomes and
# calculate exact probabilities using combinatorics.

@dataclass
class ExactDPSOutcome:
    """A unique DPS outcome with its exact probability."""
    dps_gain_pct: float
    probability: float  # Exact probability of this outcome
    representative_lines: List[PotentialLine]  # One example arrangement
    arrangement_count: int  # How many line arrangements produce this DPS


class ExactRollDistribution:
    """
    Exact probability distribution for cube rolls using combinatorial math.

    Instead of Monte Carlo sampling (5000 random rolls), this class:
    1. Enumerates all unique stat combinations (order-independent for DPS)
    2. Calculates DPS once per unique combination
    3. Sums probabilities of all arrangements that produce each DPS outcome
    4. Stores one representative arrangement per DPS bucket for display

    This gives exact probabilities instead of sampled estimates.

    Usage:
        exact_dist = ExactRollDistribution(PotentialTier.MYSTIC)
        exact_dist.score_for_slot(
            slot="gloves",
            dps_calc_func=my_dps_func,
            current_dps=1000000,
            main_stat_type=StatType.DEX_PCT
        )
        data = exact_dist.get_distribution_data_for_chart()
    """

    def __init__(self, tier: PotentialTier):
        self.tier = tier
        self._outcomes: List[ExactDPSOutcome] = []
        self._scored = False
        self._slot = None

        # Pre-compute tier stats and their probabilities
        self._tier_stats = POTENTIAL_STATS.get(tier, [])
        self._prev_tier_stats = POTENTIAL_STATS.get(tier.prev_tier(), []) if tier.prev_tier() else self._tier_stats

        # Normalize probabilities
        self._yellow_probs = self._normalize_probs(self._tier_stats)
        self._grey_probs = self._normalize_probs(self._prev_tier_stats)

    def _normalize_probs(self, stats: List[PotentialStat]) -> Dict[int, float]:
        """Normalize stat probabilities to sum to 1, return dict of stat_idx -> prob."""
        total = sum(s.probability for s in stats)
        if total == 0:
            return {}
        return {i: s.probability / total for i, s in enumerate(stats)}

    def score_for_slot(
        self,
        slot: str,
        dps_calc_func,
        current_dps: float,
        main_stat_type: StatType = StatType.DEX_PCT,
    ):
        """
        Calculate exact probability distribution for a specific slot.

        This enumerates all possible roll combinations and calculates:
        - The DPS gain for each unique stat combination
        - The exact probability of each outcome
        """
        self._slot = slot

        # Pre-calculate DPS weights for each stat
        stat_weights = self._calculate_stat_weights(slot, dps_calc_func, current_dps, main_stat_type)

        # Check for special potential
        has_special = slot in SPECIAL_POTENTIALS
        special_def = SPECIAL_POTENTIALS.get(slot) if has_special else None
        special_available = has_special and self.tier in special_def.values if special_def else False

        # Build list of (stat_idx, value, weight, is_special) for yellow and grey
        # Pass is_yellow=True for yellow stats (current tier), False for grey (previous tier)
        yellow_stats = self._build_stat_list(self._tier_stats, stat_weights, is_yellow=True)
        grey_stats = self._build_stat_list(self._prev_tier_stats, stat_weights, is_yellow=False)

        # Add special potential to yellow stats if available
        if special_available:
            special_weight = stat_weights.get((special_def.stat_type, True, True), 0.0)
            special_value = special_def.values[self.tier]
            # Special replaces 1% of the distribution - we'll handle this specially
            yellow_stats_with_special = yellow_stats + [(len(self._tier_stats), special_value, special_weight, True, special_def.stat_type)]
        else:
            yellow_stats_with_special = yellow_stats

        # Yellow line probabilities: 24% for line 2, 8% for line 3
        # Line 1 is always yellow
        yellow_rates = {1: 1.0, 2: 0.24, 3: 0.08}

        # Enumerate all possible line configurations
        # For each configuration, calculate DPS and probability
        dps_buckets: Dict[float, Dict] = {}  # dps_gain -> {prob: float, lines: List, count: int}

        # We need to enumerate all combinations of:
        # Line 1: yellow stat (always yellow)
        # Line 2: yellow stat (24%) or grey stat (76%)
        # Line 3: yellow stat (8%) or grey stat (92%)

        # Get normalized probabilities including special potential
        yellow_probs = self._get_stat_probs_with_special(slot, special_available)
        grey_probs = self._grey_probs

        # Enumerate all combinations
        for i1, (_, val1, weight1, is_special1, st1) in enumerate(yellow_stats_with_special):
            prob1 = yellow_probs.get(i1, 0)
            if prob1 == 0:
                continue

            # Line 2 possibilities
            for is_yellow2 in [True, False]:
                stats2 = yellow_stats_with_special if is_yellow2 else grey_stats
                probs2 = yellow_probs if is_yellow2 else grey_probs
                line2_yellow_prob = yellow_rates[2] if is_yellow2 else (1 - yellow_rates[2])

                for i2, (stat_idx2, val2, weight2, is_special2, st2) in enumerate(stats2):
                    prob2 = probs2.get(i2, 0) * line2_yellow_prob
                    if prob2 == 0:
                        continue

                    # Line 3 possibilities
                    for is_yellow3 in [True, False]:
                        stats3 = yellow_stats_with_special if is_yellow3 else grey_stats
                        probs3 = yellow_probs if is_yellow3 else grey_probs
                        line3_yellow_prob = yellow_rates[3] if is_yellow3 else (1 - yellow_rates[3])

                        for i3, (stat_idx3, val3, weight3, is_special3, st3) in enumerate(stats3):
                            prob3 = probs3.get(i3, 0) * line3_yellow_prob
                            if prob3 == 0:
                                continue

                            # Calculate total probability of this exact arrangement
                            total_prob = prob1 * prob2 * prob3

                            # Calculate DPS gain (weights are already % gain per stat)
                            dps_gain = weight1 + weight2 + weight3

                            # Round DPS to avoid floating point issues when bucketing
                            dps_key = round(dps_gain, 4)

                            # Add to bucket
                            if dps_key not in dps_buckets:
                                # Create representative lines
                                lines = [
                                    PotentialLine(1, st1, val1, True, is_special1),
                                    PotentialLine(2, st2, val2, is_yellow2, is_special2),
                                    PotentialLine(3, st3, val3, is_yellow3, is_special3),
                                ]
                                dps_buckets[dps_key] = {
                                    'prob': total_prob,
                                    'lines': lines,
                                    'count': 1
                                }
                            else:
                                dps_buckets[dps_key]['prob'] += total_prob
                                dps_buckets[dps_key]['count'] += 1

        # Convert buckets to sorted outcomes
        self._outcomes = []
        for dps_gain, data in sorted(dps_buckets.items()):
            self._outcomes.append(ExactDPSOutcome(
                dps_gain_pct=dps_gain,
                probability=data['prob'],
                representative_lines=data['lines'],
                arrangement_count=data['count']
            ))

        self._scored = True

    def _build_stat_list(
        self,
        stats: List[PotentialStat],
        stat_weights: Dict,
        is_yellow: bool
    ) -> List[Tuple[int, float, float, bool, StatType]]:
        """
        Build list of (idx, value, weight, is_special, stat_type) for stats.

        Args:
            stats: List of PotentialStat objects
            stat_weights: Dict with keys (stat_type, is_yellow) -> weight
            is_yellow: True for yellow (current tier) stats, False for grey (previous tier)
        """
        result = []
        for i, stat in enumerate(stats):
            # Use the correct weight for yellow vs grey
            weight = stat_weights.get((stat.stat_type, is_yellow), 0.0)
            result.append((i, stat.value, weight, False, stat.stat_type))
        return result

    def _get_stat_probs_with_special(self, slot: str, special_available: bool) -> Dict[int, float]:
        """Get stat probabilities including special potential (1% rate)."""
        if not special_available:
            return self._yellow_probs

        # Special takes 1% of the probability mass
        special_rate = SPECIAL_POTENTIAL_RATE  # 0.01
        regular_rate = 1 - special_rate  # 0.99

        result = {}
        for idx, prob in self._yellow_probs.items():
            result[idx] = prob * regular_rate

        # Special gets the last index
        special_idx = len(self._tier_stats)
        result[special_idx] = special_rate

        return result

    def _calculate_stat_weights(
        self,
        slot: str,
        dps_calc_func,
        current_dps: float,
        main_stat_type: StatType,
    ) -> Dict:
        """
        Pre-calculate DPS weight for each stat type and tier.

        Keys are:
        - (stat_type, True) for yellow stats
        - (stat_type, False) for grey stats
        - (stat_type, True, True) for special potentials
        """
        weights = {}

        # Test each stat in current tier (yellow lines)
        for stat in self._tier_stats:
            key = (stat.stat_type, True)  # (stat_type, is_yellow)
            if key in weights:
                continue
            test_lines = [PotentialLine(1, stat.stat_type, stat.value, True, False)]
            new_dps = dps_calc_func(test_lines)
            gain = ((new_dps / current_dps) - 1) * 100 if current_dps > 0 else 0
            weights[key] = gain

        # Test previous tier stats (grey lines) - these have LOWER values
        for stat in self._prev_tier_stats:
            key = (stat.stat_type, False)  # (stat_type, is_yellow=False for grey)
            if key in weights:
                continue
            test_lines = [PotentialLine(1, stat.stat_type, stat.value, False, False)]
            new_dps = dps_calc_func(test_lines)
            gain = ((new_dps / current_dps) - 1) * 100 if current_dps > 0 else 0
            weights[key] = gain

        # Test special potential if available
        if slot in SPECIAL_POTENTIALS:
            special = SPECIAL_POTENTIALS[slot]
            if self.tier in special.values:
                test_lines = [PotentialLine(1, special.stat_type, special.values[self.tier], True, True)]
                new_dps = dps_calc_func(test_lines)
                gain = ((new_dps / current_dps) - 1) * 100 if current_dps > 0 else 0
                weights[(special.stat_type, True, True)] = gain  # (stat_type, is_yellow, is_special)

        return weights

    def get_distribution_data_for_chart(self, num_points: int = 101, high_res_tail: bool = True) -> Dict:
        """
        Get distribution data formatted for Plotly chart with hover info.

        Args:
            num_points: Number of points for the main distribution (default 101 for 0-100)
            high_res_tail: If True, add extra resolution at the tail (90-100%)
                          with 0.1% increments for P90-99, and 0.01% for P99-100

        Returns dict with:
        - percentiles: List[float] (0-100, with decimals in tail)
        - dps_gains: List[float] (DPS % at each percentile)
        - lines_text: List[str] (formatted lines text for hover)
        - probabilities: List[float] (exact probability at each point)
        """
        if not self._scored:
            raise RuntimeError("Must call score_for_slot first")

        # Build cumulative probability distribution
        cumulative_prob = 0.0
        cumulative_data = []  # [(cumulative_prob, dps_gain, lines, prob)]

        for outcome in self._outcomes:
            cumulative_prob += outcome.probability
            cumulative_data.append((
                cumulative_prob,
                outcome.dps_gain_pct,
                outcome.representative_lines,
                outcome.probability
            ))

        # Build list of percentiles to sample
        # Main points: 0, 1, 2, ... 89 (integer percentiles up to 89)
        # Then high-res tail if enabled
        sample_percentiles = []

        # 0-89 by 1%
        for i in range(90):
            sample_percentiles.append(float(i))

        if high_res_tail:
            # 90-98 by 0.5%
            for i in range(90, 98):
                sample_percentiles.append(float(i))
                sample_percentiles.append(float(i) + 0.5)

            # 98-99 by 0.1%
            for i in range(10):
                pct = 98.0 + i * 0.1
                sample_percentiles.append(round(pct, 1))

            # 99-100 by 0.01% (ultra high resolution for the extreme tail)
            for i in range(101):
                pct = 99.0 + i * 0.01
                sample_percentiles.append(round(pct, 2))

            # Ensure 100.0 is included
            sample_percentiles.append(100.0)
        else:
            # Just 90-100 by 1%
            for i in range(90, 101):
                sample_percentiles.append(float(i))

        # Sort and deduplicate
        sample_percentiles = sorted(set(sample_percentiles))

        # Sample at each percentile
        percentiles = []
        dps_gains = []
        lines_text = []
        probabilities = []

        for pct in sample_percentiles:
            target = pct / 100.0  # Convert to 0.0-1.0

            # Find the outcome at this cumulative percentile
            found = False
            for cum_prob, dps_gain, lines, prob in cumulative_data:
                if cum_prob >= target:
                    percentiles.append(pct)
                    dps_gains.append(dps_gain)
                    lines_text.append(format_lines_for_hover(lines))
                    probabilities.append(prob)
                    found = True
                    break

            if not found and cumulative_data:
                # Edge case: use the last outcome
                _, dps_gain, lines, prob = cumulative_data[-1]
                percentiles.append(pct)
                dps_gains.append(dps_gain)
                lines_text.append(format_lines_for_hover(lines))
                probabilities.append(prob)

        return {
            "percentiles": percentiles,
            "dps_gains": dps_gains,
            "lines_text": lines_text,
            "probabilities": probabilities,
        }

    def get_dps_distribution_stats(self) -> Dict[str, float]:
        """Get DPS gain distribution statistics."""
        if not self._scored:
            raise RuntimeError("Must call score_for_slot first")

        # Build CDF for percentile lookups
        cumulative = 0.0
        p10_dps = p25_dps = median_dps = p75_dps = p90_dps = 0.0

        for outcome in self._outcomes:
            prev_cumulative = cumulative
            cumulative += outcome.probability

            if prev_cumulative < 0.10 <= cumulative:
                p10_dps = outcome.dps_gain_pct
            if prev_cumulative < 0.25 <= cumulative:
                p25_dps = outcome.dps_gain_pct
            if prev_cumulative < 0.50 <= cumulative:
                median_dps = outcome.dps_gain_pct
            if prev_cumulative < 0.75 <= cumulative:
                p75_dps = outcome.dps_gain_pct
            if prev_cumulative < 0.90 <= cumulative:
                p90_dps = outcome.dps_gain_pct

        return {
            "min": self._outcomes[0].dps_gain_pct if self._outcomes else 0,
            "p10": p10_dps,
            "p25": p25_dps,
            "median": median_dps,
            "p75": p75_dps,
            "p90": p90_dps,
            "max": self._outcomes[-1].dps_gain_pct if self._outcomes else 0,
        }

    def get_percentile_of_dps_gain(self, dps_gain: float) -> float:
        """Get percentile rank of a DPS gain (0-100)."""
        if not self._scored:
            raise RuntimeError("Must call score_for_slot first")

        cumulative = 0.0
        for outcome in self._outcomes:
            if outcome.dps_gain_pct >= dps_gain:
                return cumulative * 100
            cumulative += outcome.probability

        return 100.0

    def get_expected_cubes_to_dps_gain(self, target_dps_gain: float) -> float:
        """Get expected cubes to reach a target DPS gain."""
        if not self._scored:
            raise RuntimeError("Must call score_for_slot first")

        prob_above = sum(o.probability for o in self._outcomes if o.dps_gain_pct >= target_dps_gain)
        if prob_above <= 0:
            return float('inf')
        return 1 / prob_above

    def get_expected_cubes_to_improve_dps(self, current_dps_gain: float) -> float:
        """Get expected cubes to get any DPS improvement over current."""
        if not self._scored:
            raise RuntimeError("Must call score_for_slot first")

        prob_better = sum(o.probability for o in self._outcomes if o.dps_gain_pct > current_dps_gain)
        if prob_better <= 0:
            return float('inf')
        return 1 / prob_better

    def get_prob_improve_dps_in_n_cubes(self, current_dps_gain: float, n_cubes: int) -> float:
        """Get probability of improving DPS in N cubes."""
        if not self._scored:
            raise RuntimeError("Must call score_for_slot first")

        prob_better = sum(o.probability for o in self._outcomes if o.dps_gain_pct > current_dps_gain)
        if prob_better <= 0:
            return 0.0
        return 1 - ((1 - prob_better) ** n_cubes)

    def get_total_combinations(self) -> int:
        """Get total number of unique DPS outcomes."""
        return len(self._outcomes)

    def get_total_arrangements(self) -> int:
        """Get total number of line arrangements enumerated."""
        return sum(o.arrangement_count for o in self._outcomes)

    def get_exact_dps_distribution(self) -> Tuple[List[float], List[float]]:
        """
        Get the exact DPS values and their probabilities.

        Returns:
            Tuple of (dps_values, probabilities) where each dps_value has its
            corresponding probability. These are the TRUE probabilities from
            the combinatorial enumeration, properly accounting for duplicates.
        """
        if not self._scored:
            raise RuntimeError("Must call score_for_slot first")

        dps_values = [o.dps_gain_pct for o in self._outcomes]
        probabilities = [o.probability for o in self._outcomes]
        return dps_values, probabilities


# Global cache for exact distributions
_EXACT_DISTRIBUTION_CACHE: Dict[Tuple[PotentialTier, str], ExactRollDistribution] = {}
_CACHE_SESSION_ID: int = 0  # Incremented each analysis session


def get_exact_roll_distribution(
    tier: PotentialTier,
    slot: str,
    dps_calc_func,
    current_dps: float,
    main_stat_type: StatType = StatType.DEX_PCT,
    use_cache: bool = True,
) -> ExactRollDistribution:
    """
    Get or create an exact roll distribution for a tier/slot combination.

    Unlike the Monte Carlo version, this computes exact probabilities.

    Args:
        tier: Potential tier to calculate distribution for
        slot: Equipment slot
        dps_calc_func: Function to calculate DPS with test lines
        current_dps: Baseline DPS for percentage calculations
        main_stat_type: Player's main stat
        use_cache: If True, use cached distribution if available (default True)
    """
    cache_key = (tier, slot)

    # Use cache if enabled and entry exists
    if use_cache and cache_key in _EXACT_DISTRIBUTION_CACHE:
        return _EXACT_DISTRIBUTION_CACHE[cache_key]

    # Calculate new distribution
    dist = ExactRollDistribution(tier)
    dist.score_for_slot(slot, dps_calc_func, current_dps, main_stat_type)
    _EXACT_DISTRIBUTION_CACHE[cache_key] = dist

    return dist


def clear_exact_distribution_cache():
    """Clear the exact distribution cache. Call at start of each analysis session."""
    global _EXACT_DISTRIBUTION_CACHE, _CACHE_SESSION_ID
    _EXACT_DISTRIBUTION_CACHE = {}
    _CACHE_SESSION_ID += 1


# =============================================================================
# DPS-BASED ROLL SCORING SYSTEM
# =============================================================================

@dataclass
class RollScore:
    """Score result for a set of potential lines."""
    lines: List[PotentialLine]
    dps_gain_pct: float      # Total DPS gain from this roll
    score: float             # Score 0-100 (relative to best possible)
    line_contributions: List[float]  # DPS contribution per line


@dataclass
class ItemScoreResult:
    """
    Comprehensive score for an item's potential roll.

    This evaluates the quality of current potential lines relative to
    the best possible roll for this slot/tier combination.

    TWO SCORING SYSTEMS:
    1. total_score (percentile): What % of possible rolls this beats (0-100)
       - Score 70 = better than 70% of rolls
       - Good for comparing to other players
    2. dps_relative_score: DPS gain as % of max possible (0-100)
       - Score 50 = getting 50% of the max possible DPS from this slot
       - Good for understanding improvement room
    """
    total_score: float              # Percentile score: beats X% of possible rolls
    dps_relative_score: float       # DPS-based score: current_dps_gain / max_possible * 100
    line_scores: List[float]        # Per-line DPS gains [L1, L2, L3]
    yellow_count: int               # Number of yellow (current tier) lines
    useful_line_count: int          # Lines with S/A tier stats
    current_dps_gain: float         # DPS gain % from current roll
    best_possible_dps_gain: float   # DPS gain % from perfect roll (3x best yellow)
    tier: PotentialTier
    score_breakdown: Dict[str, float]  # Detailed breakdown for UI


@dataclass
class ExpectedCubesMetrics:
    """
    Expected cubes to reach various improvement thresholds.

    Uses Monte Carlo simulation to estimate cube requirements for
    different score targets, with diminishing returns warnings.
    Also tracks pity progress and tier-up potential.
    """
    current_score: float
    cubes_to_any_improvement: float     # Expected cubes to beat current score
    cubes_to_score_60: float            # Expected cubes to reach 60+ score
    cubes_to_score_80: float            # Expected cubes to reach 80+ score
    cubes_to_score_90: float            # Expected cubes to reach 90+ score
    prob_improve_10_cubes: float        # Probability of improvement in 10 cubes
    prob_improve_50_cubes: float        # Probability of improvement in 50 cubes
    diminishing_returns_warning: str    # Warning text about difficulty
    improvement_difficulty: str         # "Easy", "Medium", "Hard", "Very Hard"
    # Pity and tier-up tracking
    current_pity: int = 0               # Current pity counter
    pity_threshold: int = 999999        # Cubes until guaranteed tier-up
    cubes_to_tier_up: float = 0         # Expected cubes to tier up (accounting for pity)
    tier_up_score_gain: float = 0       # Expected score improvement from tier-up
    tier_up_efficiency_bonus: float = 0 # Additional efficiency from tier-up potential
    # Median improvement for efficiency calculation
    median_dps_improvement: float = 0.0 # Median DPS gain when rolling better than current


@dataclass
class EnhancedCubeRecommendation:
    """
    Complete recommendation for an equipment slot.

    Combines scoring, expected cubes, efficiency metrics, and
    stat rankings into a single recommendation object.
    """
    slot: str
    tier: PotentialTier
    is_bonus: bool                      # Regular vs Bonus potential
    item_score: ItemScoreResult
    expected_cubes: ExpectedCubesMetrics
    efficiency_score: float             # New formula: (room * tier) / (cubes * cost)
    top_stats: List[Tuple[str, float, float]]  # [(stat_name, dps_gain%, probability%), ...]
    current_lines_formatted: List[str]  # Pre-formatted line strings for display
    priority_rank: int                  # 1 = highest priority to cube


class PotentialRollScorer:
    """
    Scores potential rolls based on actual DPS gain.

    Usage:
        scorer = PotentialRollScorer(
            slot="necklace",
            tier=PotentialTier.MYSTIC,
            dps_calc_func=lambda lines: calculate_dps_with_lines(lines),
            current_dps=1000000
        )
        score = scorer.score_lines(roll_lines)
    """

    def __init__(
        self,
        slot: str,
        tier: PotentialTier,
        dps_calc_func,  # Function: (List[PotentialLine]) -> float (new DPS)
        current_dps: float,
        main_stat_type: StatType = StatType.DEX_PCT,  # Player's main stat
    ):
        self.slot = slot
        self.tier = tier
        self.dps_calc_func = dps_calc_func
        self.current_dps = current_dps
        self.main_stat_type = main_stat_type

        # Cache best possible roll for this tier/slot
        self._best_possible_dps_gain = None
        self._best_possible_lines = None

    def _get_dps_gain_pct(self, new_dps: float) -> float:
        """Calculate DPS gain as percentage."""
        if self.current_dps <= 0:
            return 0.0
        return ((new_dps / self.current_dps) - 1) * 100

    def _is_useful_stat(self, stat_type: StatType) -> bool:
        """Check if a stat type contributes to DPS."""
        tier = STAT_TIER_RANKINGS.get(stat_type, "F")
        return tier in ("S", "A")

    def get_best_possible_roll(self) -> Tuple[float, List[PotentialLine]]:
        """
        Calculate the best possible DPS roll for this tier/slot.
        Returns (dps_gain_pct, lines).
        """
        if self._best_possible_dps_gain is not None and self._best_possible_lines is not None:
            return (self._best_possible_dps_gain, self._best_possible_lines)

        tier_stats = POTENTIAL_STATS.get(self.tier, [])

        # Find best stat for slot
        best_stat = None
        best_value = 0

        # Check regular stats
        for stat in tier_stats:
            if self._is_useful_stat(stat.stat_type):
                # Prefer main stat % or damage %
                if stat.stat_type == self.main_stat_type or stat.stat_type == StatType.DAMAGE_PCT:
                    if stat.value > best_value or best_stat is None:
                        best_stat = stat
                        best_value = stat.value

        # Build best possible 3-line roll
        # For perfect roll: 3x best stat (yellow lines)
        best_lines = []

        # Determine which stats are best
        candidate_stats = []

        # Regular stats
        for stat in tier_stats:
            if self._is_useful_stat(stat.stat_type):
                candidate_stats.append((stat.stat_type, stat.value, False))

        # Special potential
        if self.slot in SPECIAL_POTENTIALS:
            special = SPECIAL_POTENTIALS[self.slot]
            if self.tier in special.values:
                candidate_stats.append((special.stat_type, special.values[self.tier], True))

        if not candidate_stats:
            # Fallback to main stat %
            candidate_stats.append((self.main_stat_type, 15.0, False))

        # Test each stat to find actual best DPS contribution
        stat_dps_gains = []
        for stat_type, value, is_special in candidate_stats:
            test_lines = [PotentialLine(1, stat_type, value, True, is_special)]
            new_dps = self.dps_calc_func(test_lines)
            gain = self._get_dps_gain_pct(new_dps)
            stat_dps_gains.append((stat_type, value, is_special, gain))

        # Sort by DPS gain
        stat_dps_gains.sort(key=lambda x: x[3], reverse=True)

        # Build 3 best lines (all yellow, same best stat if stackable)
        # Note: In reality, you can get the same stat multiple times
        best_lines = []
        for i in range(3):
            if stat_dps_gains:
                stat_type, value, is_special, _ = stat_dps_gains[0]  # Best stat
                best_lines.append(PotentialLine(i + 1, stat_type, value, True, is_special))

        # Calculate total DPS gain from best roll
        best_dps = self.dps_calc_func(best_lines)
        self._best_possible_dps_gain = self._get_dps_gain_pct(best_dps)
        self._best_possible_lines = best_lines

        return (self._best_possible_dps_gain, self._best_possible_lines)

    def score_lines(self, lines: List[PotentialLine]) -> RollScore:
        """
        Score a set of potential lines.

        Returns RollScore with:
        - dps_gain_pct: Actual DPS gain from this roll
        - score: 0-100 score relative to best possible
        - line_contributions: DPS contribution per line
        """
        if not lines:
            return RollScore([], 0.0, 0.0, [])

        # Calculate DPS gain from this roll
        new_dps = self.dps_calc_func(lines)
        dps_gain_pct = self._get_dps_gain_pct(new_dps)

        # Get best possible for reference
        best_gain, _ = self.get_best_possible_roll()

        # Calculate score (0-100)
        if best_gain > 0:
            score = (dps_gain_pct / best_gain) * 100
            score = max(0, min(100, score))  # Clamp to 0-100
        else:
            score = 0.0

        # Calculate individual line contributions
        line_contributions = []
        for line in lines:
            # Test this line alone
            test_lines = [PotentialLine(1, line.stat_type, line.value, line.is_yellow, line.is_special)]
            line_dps = self.dps_calc_func(test_lines)
            line_gain = self._get_dps_gain_pct(line_dps)
            line_contributions.append(line_gain)

        return RollScore(
            lines=lines,
            dps_gain_pct=dps_gain_pct,
            score=score,
            line_contributions=line_contributions
        )


# =============================================================================
# ENHANCED SCORING SYSTEM (Per-line + Combined)
# =============================================================================

def score_single_line(
    line: PotentialLine,
    tier: PotentialTier,
    slot: str,
    dps_calc_func,
    current_dps: float,
    best_line_dps_gain: float = None,
) -> float:
    """
    Score a single line relative to best possible for this tier/slot.

    Args:
        line: The potential line to score
        tier: Current potential tier
        slot: Equipment slot name
        dps_calc_func: Function(lines) -> new_dps
        current_dps: Current DPS without these potential lines
        best_line_dps_gain: Optional pre-calculated best line DPS gain

    Returns:
        Score 0-100 for this line (grey lines capped at 70)
    """
    # Calculate this line's DPS gain
    test_lines = [PotentialLine(1, line.stat_type, line.value, line.is_yellow, line.is_special)]
    new_dps = dps_calc_func(test_lines)

    if current_dps <= 0:
        return 0.0

    line_dps_gain = ((new_dps / current_dps) - 1) * 100

    # Calculate best possible single line DPS gain if not provided
    if best_line_dps_gain is None:
        best_line_dps_gain = _get_best_single_line_dps_gain(
            tier, slot, dps_calc_func, current_dps
        )

    if best_line_dps_gain <= 0:
        return 0.0

    # Base score = (this line's DPS / best line's DPS) * 100
    base_score = (line_dps_gain / best_line_dps_gain) * 100

    # Grey lines capped at 70
    if not line.is_yellow:
        base_score = min(base_score * 0.7, 70)

    # Clamp to 0-100
    return max(0, min(100, base_score))


def _get_best_single_line_dps_gain(
    tier: PotentialTier,
    slot: str,
    dps_calc_func,
    current_dps: float,
    main_stat_type: StatType = StatType.DEX_PCT,
) -> float:
    """
    Get the best possible DPS gain from a single line at this tier/slot.

    Tests all useful stats and special potentials to find the highest.
    """
    tier_stats = POTENTIAL_STATS.get(tier, [])
    best_gain = 0.0

    # Test regular stats
    for stat in tier_stats:
        stat_tier = STAT_TIER_RANKINGS.get(stat.stat_type, "F")
        if stat_tier in ("S", "A"):
            test_lines = [PotentialLine(1, stat.stat_type, stat.value, True, False)]
            new_dps = dps_calc_func(test_lines)
            gain = ((new_dps / current_dps) - 1) * 100 if current_dps > 0 else 0
            best_gain = max(best_gain, gain)

    # Test special potential
    if slot in SPECIAL_POTENTIALS:
        special = SPECIAL_POTENTIALS[slot]
        if tier in special.values:
            test_lines = [PotentialLine(1, special.stat_type, special.values[tier], True, True)]
            new_dps = dps_calc_func(test_lines)
            gain = ((new_dps / current_dps) - 1) * 100 if current_dps > 0 else 0
            best_gain = max(best_gain, gain)

    return best_gain


def _get_best_triple_line_dps_gain(
    tier: PotentialTier,
    slot: str,
    dps_calc_func,
    current_dps: float,
    main_stat_type: StatType = StatType.DEX_PCT,
) -> float:
    """
    Get the best possible DPS gain from 3 lines at this tier/slot.

    This tests combinations properly to account for diminishing returns
    on stats like crit rate that cap at 100%.

    Tests top 3 best stats applied together, not just best_single * 3.
    """
    tier_stats = POTENTIAL_STATS.get(tier, [])

    # Get all useful stats with their values
    useful_stats = []
    for stat in tier_stats:
        stat_tier = STAT_TIER_RANKINGS.get(stat.stat_type, "F")
        if stat_tier in ("S", "A"):
            useful_stats.append((stat.stat_type, stat.value))

    # Add special potential if available
    if slot in SPECIAL_POTENTIALS:
        special = SPECIAL_POTENTIALS[slot]
        if tier in special.values:
            useful_stats.append((special.stat_type, special.values[tier]))

    if not useful_stats:
        return 0.0

    # Test each stat individually to find the top 3 by DPS gain
    stat_gains = []
    for stat_type, value in useful_stats:
        test_lines = [PotentialLine(1, stat_type, value, True, False)]
        new_dps = dps_calc_func(test_lines)
        gain = ((new_dps / current_dps) - 1) * 100 if current_dps > 0 else 0
        stat_gains.append((stat_type, value, gain))

    # Sort by gain descending
    stat_gains.sort(key=lambda x: x[2], reverse=True)

    # Now test the ACTUAL best combination of 3 lines
    # Take top 3 stats and test them together
    if len(stat_gains) >= 3:
        # Test top 3 stats together
        test_lines = [
            PotentialLine(1, stat_gains[0][0], stat_gains[0][1], True, False),
            PotentialLine(2, stat_gains[1][0], stat_gains[1][1], True, False),
            PotentialLine(3, stat_gains[2][0], stat_gains[2][1], True, False),
        ]
        new_dps = dps_calc_func(test_lines)
        best_gain = ((new_dps / current_dps) - 1) * 100 if current_dps > 0 else 0

        # Also test triple of the single best stat to see if that's better
        # (e.g., 3x DEX% might be better than DEX% + CR + CD)
        best_stat = stat_gains[0]
        test_lines_triple = [
            PotentialLine(1, best_stat[0], best_stat[1], True, False),
            PotentialLine(2, best_stat[0], best_stat[1], True, False),
            PotentialLine(3, best_stat[0], best_stat[1], True, False),
        ]
        new_dps_triple = dps_calc_func(test_lines_triple)
        triple_gain = ((new_dps_triple / current_dps) - 1) * 100 if current_dps > 0 else 0

        return max(best_gain, triple_gain)

    elif len(stat_gains) >= 1:
        # Only 1-2 useful stats, use triple of best
        best_stat = stat_gains[0]
        test_lines = [
            PotentialLine(1, best_stat[0], best_stat[1], True, False),
            PotentialLine(2, best_stat[0], best_stat[1], True, False),
            PotentialLine(3, best_stat[0], best_stat[1], True, False),
        ]
        new_dps = dps_calc_func(test_lines)
        return ((new_dps / current_dps) - 1) * 100 if current_dps > 0 else 0

    return 0.0


def calculate_combined_score(
    line_scores: List[float],
    is_yellow_flags: List[bool],
) -> float:
    """
    Calculate weighted combined score from individual line scores.

    Weights: Line1=45%, Line2=35%, Line3=20%
    Bonuses: 2 yellows=+5, 3 yellows=+15

    Args:
        line_scores: List of per-line scores [L1, L2, L3] (each 0-100)
        is_yellow_flags: List of whether each line is yellow [True, False, True]

    Returns:
        Combined score 0-100
    """
    if not line_scores:
        return 0.0

    # Ensure we have exactly 3 scores
    while len(line_scores) < 3:
        line_scores.append(0.0)
    while len(is_yellow_flags) < 3:
        is_yellow_flags.append(False)

    # Weighted sum (line 1 most important, line 3 least)
    weights = [0.45, 0.35, 0.20]
    weighted_sum = sum(s * w for s, w in zip(line_scores[:3], weights))

    # Yellow bonus
    yellow_count = sum(is_yellow_flags[:3])
    if yellow_count >= 3:
        weighted_sum += 15
    elif yellow_count >= 2:
        weighted_sum += 5

    return min(100, max(0, weighted_sum))


def create_item_score_result(
    lines: List[PotentialLine],
    tier: PotentialTier,
    slot: str,
    dps_calc_func,
    current_dps: float,
    main_stat_type: StatType = StatType.DEX_PCT,
    roll_cache: 'CachedRollDistribution' = None,
) -> ItemScoreResult:
    """
    Create a comprehensive ItemScoreResult for the given potential lines.

    NEW PERCENTILE-BASED SCORING:
    - Total score = percentile of this roll's DPS among all possible rolls
    - Score 70 means this roll beats 70% of possible rolls
    - Line scores show individual line DPS contributions for display

    Args:
        lines: Current potential lines (3 lines)
        tier: Current potential tier
        slot: Equipment slot name
        dps_calc_func: Function(lines) -> new_dps
        current_dps: Current DPS without these potential lines
        main_stat_type: Player's main stat type
        roll_cache: Optional pre-scored roll distribution for percentile calculation

    Returns:
        ItemScoreResult with complete scoring breakdown
    """
    if not lines:
        return ItemScoreResult(
            total_score=0.0,
            dps_relative_score=0.0,
            line_scores=[0.0, 0.0, 0.0],
            yellow_count=0,
            useful_line_count=0,
            current_dps_gain=0.0,
            best_possible_dps_gain=0.0,
            tier=tier,
            score_breakdown={}
        )

    # Calculate actual DPS gain from current roll (the COMBINATION)
    new_dps = dps_calc_func(lines)
    current_dps_gain = ((new_dps / current_dps) - 1) * 100 if current_dps > 0 else 0

    # Get percentile-based total score from cache if available
    if roll_cache is not None and roll_cache._scored:
        total_score = roll_cache.get_percentile_of_dps_gain(current_dps_gain)
    else:
        # Fallback: Create a temporary cache to get percentile
        temp_cache = get_cached_roll_distribution(tier, 5000)
        temp_cache.score_rolls_for_slot(slot, dps_calc_func, current_dps, main_stat_type)
        total_score = temp_cache.get_percentile_of_dps_gain(current_dps_gain)

    # Calculate individual line DPS gains for display
    # (These don't affect the total score, just show contribution)
    line_dps_gains = []
    is_yellow_flags = []
    useful_count = 0

    for line in lines:
        # Test this line alone to get its individual DPS contribution
        test_lines = [PotentialLine(1, line.stat_type, line.value, line.is_yellow, line.is_special)]
        line_new_dps = dps_calc_func(test_lines)
        line_dps_gain = ((line_new_dps / current_dps) - 1) * 100 if current_dps > 0 else 0
        line_dps_gains.append(line_dps_gain)
        is_yellow_flags.append(line.is_yellow)

        # Count useful lines (S or A tier stats)
        stat_tier = STAT_TIER_RANKINGS.get(line.stat_type, "F")
        if stat_tier in ("S", "A"):
            useful_count += 1

    # Pad to 3 lines if needed
    while len(line_dps_gains) < 3:
        line_dps_gains.append(0.0)
        is_yellow_flags.append(False)

    # Calculate best possible DPS gain for reference
    # Use actual triple-line test to account for diminishing returns (e.g., crit rate cap)
    best_possible_dps_gain = _get_best_triple_line_dps_gain(
        tier, slot, dps_calc_func, current_dps, main_stat_type
    )

    # Calculate DPS-relative score: current_dps / best_possible * 100
    # This shows how much of the potential's max value you're getting
    if best_possible_dps_gain > 0:
        dps_relative_score = (current_dps_gain / best_possible_dps_gain) * 100
        dps_relative_score = min(100.0, max(0.0, dps_relative_score))
    else:
        dps_relative_score = 0.0

    # Build breakdown for UI - show individual line DPS gains
    score_breakdown = {
        "line_1_dps_gain": line_dps_gains[0],
        "line_2_dps_gain": line_dps_gains[1],
        "line_3_dps_gain": line_dps_gains[2],
        "total_dps_gain": current_dps_gain,
        "percentile": total_score,
        "dps_relative": dps_relative_score,
    }

    return ItemScoreResult(
        total_score=total_score,
        dps_relative_score=dps_relative_score,
        line_scores=line_dps_gains[:3],  # Now contains DPS gains instead of arbitrary scores
        yellow_count=sum(is_yellow_flags),
        useful_line_count=useful_count,
        current_dps_gain=current_dps_gain,
        best_possible_dps_gain=best_possible_dps_gain,
        tier=tier,
        score_breakdown=score_breakdown
    )


def detect_diminishing_returns(
    lines: List[PotentialLine],
    tier: PotentialTier,
) -> Tuple[str, str]:
    """
    Detect when improvement is statistically unlikely due to already good roll.

    Returns:
        Tuple of (warning_text, difficulty_level)
        difficulty_level: "Easy", "Medium", "Hard", "Very Hard"
    """
    # Count useful yellow lines
    useful_yellows = 0
    for line in lines:
        if line.is_yellow:
            stat_tier = STAT_TIER_RANKINGS.get(line.stat_type, "F")
            if stat_tier in ("S", "A"):
                useful_yellows += 1

    if useful_yellows >= 3:
        return ("3/3 useful yellows - near perfect!", "Very Hard")
    elif useful_yellows == 2:
        # P(3rd useful yellow) ≈ P(L3 yellow) × P(useful stat)
        # ≈ 8% × 18% = 1.44%
        return ("2/3 useful yellows - ~1.4% per cube for 3rd", "Hard")
    elif useful_yellows == 1:
        # P(2nd useful) ≈ P(L2 yellow) × P(useful)
        # ≈ 24% × 18% = 4.3%
        return ("1/3 useful yellows - ~4% per cube for 2nd", "Medium")
    else:
        return ("0/3 useful lines - high improvement potential", "Easy")


def calculate_stat_rankings(
    slot: str,
    tier: PotentialTier,
    dps_calc_func,
    current_dps: float,
    main_stat_type: StatType = StatType.DEX_PCT,
    top_n: int = 5,
) -> List[Tuple[str, float, float]]:
    """
    Calculate top N stats by DPS gain for this slot/tier.

    Args:
        slot: Equipment slot name
        tier: Current potential tier
        dps_calc_func: Function(lines) -> new_dps
        current_dps: Current DPS without potential lines
        main_stat_type: Player's main stat type
        top_n: Number of top stats to return

    Returns:
        List of tuples: [(stat_display_name, dps_gain%, probability%), ...]
        Special potentials are marked with ⭐
    """
    rankings = []
    tier_stats = POTENTIAL_STATS.get(tier, [])

    # Test regular stats
    for stat in tier_stats:
        stat_tier = STAT_TIER_RANKINGS.get(stat.stat_type, "F")
        if stat_tier in ("S", "A", "B"):  # Include B tier for completeness
            test_lines = [PotentialLine(1, stat.stat_type, stat.value, True, False)]
            new_dps = dps_calc_func(test_lines)
            dps_gain = ((new_dps / current_dps) - 1) * 100 if current_dps > 0 else 0

            display_name = get_stat_display_name(stat.stat_type)
            # Adjust probability for main stat selection (only count player's main stat)
            if stat.stat_type == main_stat_type:
                probability = stat.probability * 100
            elif stat.stat_type in (StatType.DEX_PCT, StatType.STR_PCT, StatType.INT_PCT, StatType.LUK_PCT):
                # Other main stats not useful for player
                continue
            else:
                probability = stat.probability * 100

            rankings.append((display_name, dps_gain, probability))

    # Test special potential
    if slot in SPECIAL_POTENTIALS:
        special = SPECIAL_POTENTIALS[slot]
        if tier in special.values:
            test_lines = [PotentialLine(1, special.stat_type, special.values[tier], True, True)]
            new_dps = dps_calc_func(test_lines)
            dps_gain = ((new_dps / current_dps) - 1) * 100 if current_dps > 0 else 0

            display_name = f"{get_stat_display_name(special.stat_type)} ⭐"
            probability = SPECIAL_POTENTIAL_RATE * 100  # 1%

            rankings.append((display_name, dps_gain, probability))

    # Sort by DPS gain descending
    rankings.sort(key=lambda x: x[1], reverse=True)

    return rankings[:top_n]


def calculate_expected_cubes_to_improve(
    slot: str,
    tier: PotentialTier,
    current_lines: List[PotentialLine],
    dps_calc_func,
    current_dps: float,
    main_stat_type: StatType = StatType.DEX_PCT,
    max_cubes: int = 500,
    iterations: int = 200,
    current_pity: int = 0,
    cube_type: CubeType = CubeType.REGULAR,
) -> ExpectedCubesMetrics:
    """
    Calculate expected cubes to reach various improvement thresholds.

    Uses Monte Carlo simulation to estimate how many cubes are needed to:
    - Get any improvement over current roll
    - Reach score 60+
    - Reach score 80+
    - Reach score 90+

    Also calculates tier-up potential value considering:
    - Current pity progress
    - Expected score gain from higher tier stats
    - Weighted efficiency bonus for items close to tier-up

    Args:
        slot: Equipment slot name
        tier: Current potential tier
        current_lines: Current potential lines
        dps_calc_func: Function(lines) -> new_dps
        current_dps: Current DPS without potential lines
        main_stat_type: Player's main stat type
        max_cubes: Maximum cubes to simulate per target
        iterations: Number of Monte Carlo iterations
        current_pity: Current pity counter (0 to pity_threshold)
        cube_type: Regular or Bonus cubes

    Returns:
        ExpectedCubesMetrics with all threshold data including tier-up info
    """
    # Get current score
    current_item_score = create_item_score_result(
        current_lines, tier, slot, dps_calc_func, current_dps, main_stat_type
    )
    current_score = current_item_score.total_score

    # Detect diminishing returns
    warning, difficulty = detect_diminishing_returns(current_lines, tier)

    # Get pity threshold for current tier
    pity_table = REGULAR_PITY if cube_type == CubeType.REGULAR else BONUS_PITY
    pity_threshold = pity_table.get(tier, 999999)

    # Calculate expected cubes to tier up (accounting for current pity)
    cubes_to_tier_up = _calculate_cubes_to_tier_up(tier, current_pity, cube_type)

    # Calculate expected score gain from tier-up
    tier_up_score_gain = 0.0
    tier_up_efficiency_bonus = 0.0
    next_tier = tier.next_tier()

    if next_tier is not None and tier != PotentialTier.MYSTIC:
        # Estimate average score at next tier (higher tier = better stat values)
        tier_up_score_gain = _estimate_tier_up_score_gain(
            slot, tier, next_tier, dps_calc_func, current_dps, main_stat_type
        )

        # Calculate efficiency bonus from tier-up potential
        # Items close to tier-up get a bonus to their efficiency
        if cubes_to_tier_up > 0 and cubes_to_tier_up < 200:
            # Bonus = (score_gain / cubes_to_tier_up) scaled
            # This represents the "hidden value" of cubing this item
            tier_up_efficiency_bonus = (tier_up_score_gain / cubes_to_tier_up) * 10

    # Define targets
    targets = {
        "any_improvement": current_score + 0.1,  # Any improvement
        "score_60": 60,
        "score_80": 80,
        "score_90": 90,
    }

    # Only simulate targets we haven't already reached
    results = {}
    for target_name, target_score in targets.items():
        if current_score >= target_score:
            results[target_name] = 0  # Already at or above target
        else:
            # Simulate cubes until target
            cubes_needed = _simulate_cubes_until_score(
                slot, tier, target_score, dps_calc_func, current_dps,
                main_stat_type, max_cubes, iterations
            )
            results[target_name] = cubes_needed

    # Calculate probability of improvement in N cubes
    prob_10 = _simulate_prob_improve_in_n(
        slot, tier, current_score, dps_calc_func, current_dps,
        main_stat_type, n_cubes=10, iterations=iterations
    )
    prob_50 = _simulate_prob_improve_in_n(
        slot, tier, current_score, dps_calc_func, current_dps,
        main_stat_type, n_cubes=50, iterations=iterations
    )

    return ExpectedCubesMetrics(
        current_score=current_score,
        cubes_to_any_improvement=results.get("any_improvement", float('inf')),
        cubes_to_score_60=results.get("score_60", float('inf')),
        cubes_to_score_80=results.get("score_80", float('inf')),
        cubes_to_score_90=results.get("score_90", float('inf')),
        prob_improve_10_cubes=prob_10,
        prob_improve_50_cubes=prob_50,
        diminishing_returns_warning=warning,
        improvement_difficulty=difficulty,
        current_pity=current_pity,
        pity_threshold=pity_threshold,
        cubes_to_tier_up=cubes_to_tier_up,
        tier_up_score_gain=tier_up_score_gain,
        tier_up_efficiency_bonus=tier_up_efficiency_bonus,
    )


def calculate_expected_cubes_fast(
    slot: str,
    tier: PotentialTier,
    current_lines: List[PotentialLine],
    dps_calc_func,
    current_dps: float,
    main_stat_type: StatType = StatType.DEX_PCT,
    current_pity: int = 0,
    cube_type: CubeType = CubeType.REGULAR,
    n_cached_rolls: int = 5000,
) -> ExpectedCubesMetrics:
    """
    OPTIMIZED: Calculate expected cubes using cached roll distribution.

    This is much faster than calculate_expected_cubes_to_improve() because:
    1. Pre-generates rolls once per tier (cached globally)
    2. Scores all rolls in a single pass per slot
    3. Uses analytical formulas instead of Monte Carlo per target

    Performance: ~50-100x faster for analyzing all 22 potential sets

    Args:
        slot: Equipment slot name
        tier: Current potential tier
        current_lines: Current potential lines
        dps_calc_func: Function(lines) -> new_dps
        current_dps: Current DPS without potential lines
        main_stat_type: Player's main stat type
        current_pity: Current pity counter (0 to pity_threshold)
        cube_type: Regular or Bonus cubes
        n_cached_rolls: Number of rolls in the cache (higher = more accurate)

    Returns:
        ExpectedCubesMetrics with all threshold data including tier-up info
    """
    # Get or create cached roll distribution for this tier
    cache = get_cached_roll_distribution(tier, n_cached_rolls)

    # Score the cached rolls for this specific slot
    cache.score_rolls_for_slot(slot, dps_calc_func, current_dps, main_stat_type)

    # Score current roll - now includes both percentile and DPS-relative scores
    current_item_score = create_item_score_result(
        current_lines, tier, slot, dps_calc_func, current_dps, main_stat_type, cache
    )
    current_score = current_item_score.total_score  # Percentile score
    current_dps_gain = current_item_score.current_dps_gain
    best_possible_dps = current_item_score.best_possible_dps_gain

    # Use DPS-based improvement calculations (more intuitive for users)
    # "How many cubes until I get a roll with more DPS?"
    cubes_to_any_improvement = cache.get_expected_cubes_to_improve_dps(current_dps_gain)

    # DPS thresholds instead of arbitrary score thresholds
    # Calculate target DPS gains based on max possible
    target_50pct = best_possible_dps * 0.50  # 50% of max possible DPS
    target_70pct = best_possible_dps * 0.70  # 70% of max possible DPS
    target_85pct = best_possible_dps * 0.85  # 85% of max possible DPS

    cubes_to_60 = cache.get_expected_cubes_to_dps_gain(target_50pct) if current_dps_gain < target_50pct else 0
    cubes_to_80 = cache.get_expected_cubes_to_dps_gain(target_70pct) if current_dps_gain < target_70pct else 0
    cubes_to_90 = cache.get_expected_cubes_to_dps_gain(target_85pct) if current_dps_gain < target_85pct else 0

    # Calculate probability of DPS improvement in N cubes
    prob_10 = cache.get_prob_improve_dps_in_n_cubes(current_dps_gain, 10)
    prob_50 = cache.get_prob_improve_dps_in_n_cubes(current_dps_gain, 50)

    # Detect diminishing returns
    warning, difficulty = detect_diminishing_returns(current_lines, tier)

    # Get pity threshold for current tier
    pity_table = REGULAR_PITY if cube_type == CubeType.REGULAR else BONUS_PITY
    pity_threshold = pity_table.get(tier, 999999)

    # Calculate expected cubes to tier up (accounting for current pity)
    cubes_to_tier_up = _calculate_cubes_to_tier_up(tier, current_pity, cube_type)

    # Calculate expected score gain from tier-up
    tier_up_score_gain = 0.0
    tier_up_efficiency_bonus = 0.0
    next_tier = tier.next_tier()

    if next_tier is not None and tier != PotentialTier.MYSTIC:
        tier_up_score_gain = _estimate_tier_up_score_gain(
            slot, tier, next_tier, dps_calc_func, current_dps, main_stat_type
        )

        if cubes_to_tier_up > 0 and cubes_to_tier_up < 200:
            tier_up_efficiency_bonus = (tier_up_score_gain / cubes_to_tier_up) * 10

    # Calculate median DPS improvement when rolling better than current
    median_dps_improvement = cache.get_expected_dps_gain_when_improving(current_dps_gain)

    return ExpectedCubesMetrics(
        current_score=current_score,
        cubes_to_any_improvement=cubes_to_any_improvement,
        cubes_to_score_60=cubes_to_60,
        cubes_to_score_80=cubes_to_80,
        cubes_to_score_90=cubes_to_90,
        prob_improve_10_cubes=prob_10,
        prob_improve_50_cubes=prob_50,
        diminishing_returns_warning=warning,
        improvement_difficulty=difficulty,
        current_pity=current_pity,
        pity_threshold=pity_threshold,
        cubes_to_tier_up=cubes_to_tier_up,
        tier_up_score_gain=tier_up_score_gain,
        tier_up_efficiency_bonus=tier_up_efficiency_bonus,
        median_dps_improvement=median_dps_improvement,
    )


def _calculate_cubes_to_tier_up(
    tier: PotentialTier,
    current_pity: int,
    cube_type: CubeType = CubeType.REGULAR,
) -> float:
    """
    Calculate expected cubes to tier up accounting for current pity.

    Uses truncated geometric distribution:
    E[cubes] = (1 - (1-p)^(pity_remaining)) / p

    Where pity_remaining = pity_threshold - current_pity
    """
    if tier == PotentialTier.MYSTIC:
        return float('inf')  # Can't tier up from Mystic

    # Get tier-up probability
    p = TIER_UP_RATES.get(tier, 0)
    if p <= 0:
        return float('inf')

    # Get pity threshold
    pity_table = REGULAR_PITY if cube_type == CubeType.REGULAR else BONUS_PITY
    pity_threshold = pity_table.get(tier, 999999)

    # Remaining cubes until guaranteed tier-up
    pity_remaining = max(1, pity_threshold - current_pity)

    # Expected cubes using truncated geometric distribution
    return expected_cubes_with_pity(p, pity_remaining)


def _estimate_tier_up_score_gain(
    slot: str,
    current_tier: PotentialTier,
    next_tier: PotentialTier,
    dps_calc_func,
    current_dps: float,
    main_stat_type: StatType,
) -> float:
    """
    Estimate the expected score gain from tiering up.

    Compares average useful stat values between tiers.
    """
    # Get best line DPS at current tier
    current_best = _get_best_single_line_dps_gain(
        current_tier, slot, dps_calc_func, current_dps, main_stat_type
    )

    # Get best line DPS at next tier
    next_best = _get_best_single_line_dps_gain(
        next_tier, slot, dps_calc_func, current_dps, main_stat_type
    )

    if current_best <= 0:
        return 0

    # Score gain is proportional to the ratio of stat improvements
    # For example, Mystic DEX% is 15% vs Legendary 12% = 25% better per line
    # With 3 lines, this translates to significant score improvement
    ratio = next_best / current_best if current_best > 0 else 1.0

    # Estimate: going from tier N to N+1 improves scores by ~15-25 points on average
    # This is based on stat value increases between tiers
    estimated_gain = (ratio - 1) * 100  # Convert to score points

    # Cap at reasonable values
    return min(30, max(5, estimated_gain))


def _simulate_cubes_until_score(
    slot: str,
    tier: PotentialTier,
    target_score: float,
    dps_calc_func,
    current_dps: float,
    main_stat_type: StatType,
    max_cubes: int,
    iterations: int,
) -> float:
    """
    Simulate cubing until reaching target score.

    Returns expected number of cubes needed (average across iterations).
    Returns max_cubes if target not reached in most iterations.
    """
    cubes_needed_list = []

    for _ in range(iterations):
        sim = CubeSimulator(slot, tier, CubeType.REGULAR)
        cubes_used = 0
        reached = False

        for _ in range(max_cubes):
            result = sim.use_cube()
            cubes_used += 1

            # Score this roll using the new system
            item_score = create_item_score_result(
                result.lines, tier, slot, dps_calc_func, current_dps, main_stat_type
            )

            if item_score.total_score >= target_score:
                reached = True
                break

        cubes_needed_list.append(cubes_used if reached else max_cubes)

    # Calculate expected cubes
    successful = [c for c in cubes_needed_list if c < max_cubes]
    if len(successful) >= iterations * 0.1:  # At least 10% success rate
        return sum(successful) / len(successful)
    else:
        # Most iterations failed - return max as indicator
        return float(max_cubes)


def _simulate_prob_improve_in_n(
    slot: str,
    tier: PotentialTier,
    current_score: float,
    dps_calc_func,
    current_dps: float,
    main_stat_type: StatType,
    n_cubes: int,
    iterations: int,
) -> float:
    """
    Simulate probability of improving current score within N cubes.
    """
    improvements = 0

    for _ in range(iterations):
        sim = CubeSimulator(slot, tier, CubeType.REGULAR)
        improved = False

        for _ in range(n_cubes):
            result = sim.use_cube()

            # Score this roll
            item_score = create_item_score_result(
                result.lines, tier, slot, dps_calc_func, current_dps, main_stat_type
            )

            if item_score.total_score > current_score:
                improved = True
                break

        if improved:
            improvements += 1

    return improvements / iterations


def calculate_efficiency_score(
    expected_cubes_to_improve: float,
    diamond_cost_per_cube: float,
    median_dps_improvement: float,
    tier_up_efficiency_bonus: float = 0,
) -> float:
    """
    Calculate efficiency score for cubing this item.

    Formula: Expected DPS% gain per 100k diamonds spent

    This uses the actual median DPS improvement from the roll distribution,
    making it directly comparable with starforce and other upgrade types.

    For cubes: (median_improvement / expected_cubes) / cost_per_cube * 100000
    For starforce: dps_gain / total_cost * 100000 (same formula, guaranteed outcome)

    Args:
        expected_cubes_to_improve: Expected cubes to get any improvement
        diamond_cost_per_cube: Cost per cube in diamonds
        median_dps_improvement: Median DPS% gain when rolling better than current
        tier_up_efficiency_bonus: Pre-calculated bonus from tier-up potential

    Returns:
        Efficiency score: DPS% gain per 100k diamonds (higher = better)
    """
    if expected_cubes_to_improve <= 0 or median_dps_improvement <= 0:
        # No room to improve - just tier-up value
        return tier_up_efficiency_bonus * 10

    if expected_cubes_to_improve >= 500:
        # Very hard to improve - use minimal efficiency
        expected_dps_per_cube = median_dps_improvement * 0.002  # ~0.1% chance
    else:
        # Expected DPS gain per cube = median_improvement / expected_cubes
        # This is probability-weighted: (1/expected_cubes) * median_improvement
        expected_dps_per_cube = median_dps_improvement / expected_cubes_to_improve

    # Efficiency = DPS% per 100k diamonds
    efficiency = (expected_dps_per_cube / diamond_cost_per_cube) * 100_000

    # Add tier-up bonus (items close to tier-up get extra value)
    efficiency += tier_up_efficiency_bonus * 10

    return efficiency


# =============================================================================
# MONTE CARLO CUBE SIMULATION (N cubes, keep best)
# =============================================================================

@dataclass
class CubeSimulationResult:
    """Results from Monte Carlo cube simulation."""
    n_cubes: int
    iterations: int

    # Current roll info
    current_score: float
    current_dps_gain: float

    # Outcome statistics
    prob_improve: float              # Probability of finding better roll
    prob_score_thresholds: Dict[int, float]  # {60: 0.72, 80: 0.28, ...}
    expected_best_score: float
    expected_best_dps_gain: float
    median_best_score: float

    # Risk analysis
    prob_worse: float                # Probability of best found being worse than current

    # Distribution data (for visualization)
    score_distribution: List[float]  # Best scores from each iteration

    # Tier-up tracking
    tier: PotentialTier              # Current tier being simulated
    pity_threshold: int              # Pity threshold for current tier
    expected_pity_after: float       # Expected pity count after N cubes
    prob_tier_up: float              # Probability of tier-up in N cubes
    expected_tier_ups: float         # Expected number of tier-ups


def simulate_n_cubes_keep_best(
    scorer: PotentialRollScorer,
    current_lines: List[PotentialLine],
    n_cubes: int,
    iterations: int = 1000,
    starting_pity: int = 0,
) -> CubeSimulationResult:
    """
    Monte Carlo simulation: Use N cubes and keep the best roll.

    For each iteration:
    1. Simulate N cube uses
    2. Score each roll
    3. Keep track of the best roll found
    4. Record the best score
    5. Track tier-ups and pity progress

    Returns statistics about expected outcomes.
    """
    # Score current lines
    current_score_result = scorer.score_lines(current_lines)
    current_score = current_score_result.score
    current_dps_gain = current_score_result.dps_gain_pct

    # Get pity threshold for this tier
    pity_threshold = REGULAR_PITY.get(scorer.tier, 999999)

    best_scores = []
    best_dps_gains = []
    improvements = 0
    tier_ups_list = []
    final_pity_counts = []

    for _ in range(iterations):
        # Create fresh simulator for each iteration with starting pity
        sim = CubeSimulator(scorer.slot, scorer.tier, CubeType.REGULAR)
        sim.pity_count = starting_pity

        best_score_this_iter = current_score
        best_dps_this_iter = current_dps_gain
        tier_ups_this_iter = 0

        for _ in range(n_cubes):
            # Use a cube and get result
            result = sim.use_cube()

            # Track tier-ups
            if result.tier_up:
                tier_ups_this_iter += 1

            # Score the roll
            roll_score = scorer.score_lines(result.lines)

            # Track best
            if roll_score.score > best_score_this_iter:
                best_score_this_iter = roll_score.score
                best_dps_this_iter = roll_score.dps_gain_pct

        best_scores.append(best_score_this_iter)
        best_dps_gains.append(best_dps_this_iter)
        tier_ups_list.append(tier_ups_this_iter)
        final_pity_counts.append(sim.pity_count)

        if best_score_this_iter > current_score:
            improvements += 1

    # Calculate statistics
    prob_improve = improvements / iterations

    # Score threshold probabilities
    thresholds = [40, 60, 80, 90, 95]
    prob_thresholds = {}
    for thresh in thresholds:
        count = sum(1 for s in best_scores if s >= thresh)
        prob_thresholds[thresh] = count / iterations

    expected_best_score = sum(best_scores) / len(best_scores)
    expected_best_dps = sum(best_dps_gains) / len(best_dps_gains)

    sorted_scores = sorted(best_scores)
    median_score = sorted_scores[len(sorted_scores) // 2]

    # Risk: probability of best found being worse than current
    worse_count = sum(1 for s in best_scores if s < current_score)
    prob_worse = worse_count / iterations

    # Tier-up statistics
    expected_tier_ups = sum(tier_ups_list) / len(tier_ups_list)
    prob_tier_up = sum(1 for t in tier_ups_list if t > 0) / iterations
    expected_pity_after = sum(final_pity_counts) / len(final_pity_counts)

    return CubeSimulationResult(
        n_cubes=n_cubes,
        iterations=iterations,
        current_score=current_score,
        current_dps_gain=current_dps_gain,
        prob_improve=prob_improve,
        prob_score_thresholds=prob_thresholds,
        expected_best_score=expected_best_score,
        expected_best_dps_gain=expected_best_dps,
        median_best_score=median_score,
        prob_worse=prob_worse,
        score_distribution=best_scores,
        tier=scorer.tier,
        pity_threshold=pity_threshold,
        expected_pity_after=expected_pity_after,
        prob_tier_up=prob_tier_up,
        expected_tier_ups=expected_tier_ups,
    )


def format_simulation_result(result: CubeSimulationResult, slot: str, tier: PotentialTier) -> str:
    """Format simulation results for display."""
    lines = []
    lines.append(f"{slot.upper()} [{tier.value.upper()}] - Current Score: {result.current_score:.0f}/100 (+{result.current_dps_gain:.2f}% DPS)")
    lines.append("")
    lines.append(f"With {result.n_cubes} cubes ({result.iterations} simulations):")
    lines.append(f"├─ {result.prob_improve * 100:.0f}% chance to improve")

    for thresh in sorted(result.prob_score_thresholds.keys(), reverse=True):
        prob = result.prob_score_thresholds[thresh]
        if prob > 0.01:  # Only show if > 1% chance
            lines.append(f"├─ {prob * 100:.0f}% chance to hit {thresh}+ score")

    lines.append(f"├─ Expected best: Score {result.expected_best_score:.0f} (+{result.expected_best_dps_gain:.2f}% DPS)")
    lines.append(f"├─ Median best: Score {result.median_best_score:.0f}")
    lines.append(f"└─ {result.prob_worse * 100:.0f}% risk of not improving")

    return "\n".join(lines)


# =============================================================================
# MAIN (Test)
# =============================================================================

if __name__ == "__main__":
    print("MapleStory Idle - Cube System Module")
    print("=" * 50)

    # Test cost calculation
    print("\nCost to reach Legendary from Epic (Regular):")
    cubes, cost = calculate_cost_to_tier(
        PotentialTier.EPIC,
        PotentialTier.LEGENDARY,
        CubeType.REGULAR,
        600
    )
    print(f"  Expected cubes: {cubes}")
    print(f"  Expected cost: {cost:,.0f} diamonds")

    # Test simulation
    print("\nSimulating 10 cubes on Legendary Gloves:")
    sim = CubeSimulator("gloves", PotentialTier.LEGENDARY)

    for i in range(10):
        result = sim.use_cube()
        print(f"\nCube #{i+1}:")
        for line in result.lines:
            print(f"  {format_line(line)}")
        if result.tier_up:
            print(f"  ** TIER UP to {result.new_tier.value}! **")
        print(f"  Pity: {result.pity_count}/{sim._get_pity_threshold()}")

    print(f"\nStats: {sim.get_stats()}")

    # Test ExactRollDistribution
    print("\n" + "=" * 50)
    print("Testing ExactRollDistribution vs Monte Carlo")
    print("=" * 50)

    # Simple DPS calculator that just sums up useful stats
    def simple_dps_calc(lines: List[PotentialLine]) -> float:
        """Simple DPS: base 1000 + sum of useful stat contributions."""
        base_dps = 1000.0
        dps_multiplier = 1.0

        for line in lines:
            if line.stat_type in (StatType.DEX_PCT, StatType.STR_PCT, StatType.INT_PCT, StatType.LUK_PCT):
                dps_multiplier += line.value / 100  # Main stat % adds to multiplier
            elif line.stat_type == StatType.DAMAGE_PCT:
                dps_multiplier += line.value / 100
            elif line.stat_type == StatType.CRIT_RATE:
                dps_multiplier += line.value / 200  # Crit is worth half of main stat
            elif line.stat_type == StatType.CRIT_DAMAGE:
                dps_multiplier += line.value / 150  # Crit damage is good
            elif line.stat_type in (StatType.MIN_DMG_MULT, StatType.MAX_DMG_MULT):
                dps_multiplier += line.value / 200
            # Flat stats, DEF, HP, MP contribute nothing

        return base_dps * dps_multiplier

    tier = PotentialTier.MYSTIC
    slot = "gloves"
    baseline_dps = 1000.0

    print(f"\nTier: {tier.value}, Slot: {slot}")

    # Test exact distribution
    print("\n--- Exact Distribution ---")
    exact = ExactRollDistribution(tier)
    exact.score_for_slot(slot, simple_dps_calc, baseline_dps)

    exact_stats = exact.get_dps_distribution_stats()
    print(f"Unique DPS outcomes: {exact.get_total_combinations()}")
    print(f"Total arrangements: {exact.get_total_arrangements()}")
    print(f"Min DPS gain: {exact_stats['min']:.2f}%")
    print(f"P10 DPS gain: {exact_stats['p10']:.2f}%")
    print(f"P25 DPS gain: {exact_stats['p25']:.2f}%")
    print(f"Median DPS gain: {exact_stats['median']:.2f}%")
    print(f"P75 DPS gain: {exact_stats['p75']:.2f}%")
    print(f"P90 DPS gain: {exact_stats['p90']:.2f}%")
    print(f"Max DPS gain: {exact_stats['max']:.2f}%")

    # Test Monte Carlo for comparison
    print("\n--- Monte Carlo (5000 samples) ---")
    cache = CachedRollDistribution(tier, n_rolls=5000)
    cache.score_rolls_for_slot(slot, simple_dps_calc, baseline_dps)

    mc_stats = cache.get_dps_distribution_stats()
    print(f"Min DPS gain: {mc_stats['min']:.2f}%")
    print(f"P10 DPS gain: {mc_stats['p10']:.2f}%")
    print(f"P25 DPS gain: {mc_stats['p25']:.2f}%")
    print(f"Median DPS gain: {mc_stats['median']:.2f}%")
    print(f"P75 DPS gain: {mc_stats['p75']:.2f}%")
    print(f"P90 DPS gain: {mc_stats['p90']:.2f}%")
    print(f"Max DPS gain: {mc_stats['max']:.2f}%")

    # Compare
    print("\n--- Comparison (Exact - Monte Carlo) ---")
    print(f"Median difference: {exact_stats['median'] - mc_stats['median']:.4f}%")
    print(f"P75 difference: {exact_stats['p75'] - mc_stats['p75']:.4f}%")
    print(f"Max difference: {exact_stats['max'] - mc_stats['max']:.4f}%")

    # Verify probability sums to 1
    total_prob = sum(o.probability for o in exact._outcomes)
    print(f"\nTotal probability (should be 1.0): {total_prob:.6f}")
