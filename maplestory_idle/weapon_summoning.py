"""
Weapon Summoning System
=======================
Models the weapon summoning gacha system with level-based drop rates.

The summoning level increases with total summons and affects drop rates.
Higher levels have better chances for rare weapons.

SOURCE OF TRUTH:
- RARITY_RATES[level][rarity] = exact probability (decimal)
- TIER_RATIOS[pattern] = {tier: parts} (whole number ratios)
- Final rate = rarity_rate * (tier_parts / sum(tier_parts))
- LEVEL_THRESHOLDS[level] = total summons required to reach that level

The tier distributions use whole-number ratios that produce exact percentages.
Rarity totals are set so that rarity * tier_pct rounds to wiki values.
"""

from typing import Dict, List, Tuple


# =============================================================================
# TICKET COST
# =============================================================================
# Base cost per summon ticket in diamonds.
# Derived from: 6000 diamonds = 159.5 tickets

DIAMONDS_PER_TICKET = 6000 / 159.5  # ~37.62 diamonds per ticket


# =============================================================================
# AWAKENING & PROMOTION COSTS
# =============================================================================
# Awakening: Uses duplicates to increase awakening level (max A5)
# Duplicates required: A1=1, A2=2, A3=3, A4=4, A5=5

AWAKENING_COSTS = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
TOTAL_AWAKENING_COST = sum(AWAKENING_COSTS.values())  # 15 duplicates to max

# Promotion: After max awakening (A5), 5 more duplicates promotes the weapon
# Special rule: T1 promoted → T4 of next rarity
PROMOTION_COST = 5  # duplicates needed after max awakening

# Total duplicates to max awakening AND promote
TOTAL_MAX_AND_PROMOTE = TOTAL_AWAKENING_COST + PROMOTION_COST  # 20 + 1 initial = 21 total

# Rarity order for promotion paths
RARITY_ORDER = ["normal", "rare", "epic", "unique", "legendary", "mystic", "ancient"]


# =============================================================================
# SUMMONING LEVEL THRESHOLDS
# =============================================================================
# Total number of summons required to reach each level.
# Level 1 is the starting level (0 summons).

LEVEL_THRESHOLDS = {
    1: 0,        # Starting level
    2: 100,
    3: 250,
    4: 500,
    5: 800,
    6: 1300,
    7: 1800,
    8: 2400,
    9: 3200,
    10: 4100,
    11: 5400,
    12: 7000,
    13: 9300,
    14: 12100,
    15: 15600,
    16: 31200,
    17: 46800,
}


# =============================================================================
# TIER DISTRIBUTION PATTERNS (WHOLE NUMBER RATIOS)
# =============================================================================
# These are the exact ratios for tier distribution within each rarity.
# To get percentage: tier_parts / sum(all_parts) * 100

TIER_PATTERNS = {
    # ==========================================================================
    # STANDARD PATTERNS (all percentages divisible by 5)
    # ==========================================================================
    "100": {4: 100},                               # Single tier (T4 only) - on unlock
    "75_25": {4: 75, 3: 25},                       # Two tiers - early split
    "70_30": {4: 70, 3: 30},                       # Two tiers - first split
    "65_25_10": {4: 65, 3: 25, 2: 10},             # Three tiers - Ancient L17
    "60_30_10": {4: 60, 3: 30, 2: 10},             # Three tiers - transition
    "50_30_15_5": {4: 50, 3: 30, 2: 15, 1: 5},     # Four tiers - standard
    "40_30_20_10": {4: 40, 3: 30, 2: 20, 1: 10},   # Four tiers - mature

    # ==========================================================================
    # SPECIAL PATTERNS WITH T1=7% (one tier gets +3% to sum to 100)
    # ==========================================================================
    "50_30_13_7": {4: 50, 3: 30, 2: 13, 1: 7},     # T2=13 (10+3) to balance T1=7
    "40_33_20_7": {4: 40, 3: 33, 2: 20, 1: 7},     # T3=33 (30+3) to balance T1=7
}


def _get_tier_distribution(pattern_name: str) -> Dict[int, float]:
    """Convert tier pattern to decimal distribution (sums to 1.0)."""
    pattern = TIER_PATTERNS.get(pattern_name, {})
    total = sum(pattern.values())
    if total == 0:
        return {}
    # Filter out zero values (e.g., T1=0 cases)
    return {tier: parts / total for tier, parts in pattern.items() if parts > 0}


# =============================================================================
# RARITY RATES BY LEVEL (EXACT SOURCE OF TRUTH)
# =============================================================================
# These are the exact rarity probabilities at each summoning level.
# Values are chosen so that rarity * tier_pct rounds to wiki displayed values.
#
# Note: All values are in decimal form (0.01 = 1%)

RARITY_RATES = {
    # ==========================================================================
    # All values chosen so that:
    # 1. Sum equals exactly 100% at each level
    # 2. Individual weapon rates (rarity * tier%) round to wiki values
    # ==========================================================================
    1: {
        "normal": 0.92,       # 92%
        "rare": 0.08,         # 8%
    },  # Sum: 100%
    2: {
        "normal": 0.88,       # 88%
        "rare": 0.12,         # 12%
    },  # Sum: 100%
    3: {
        "normal": 0.842,      # 84.2%
        "rare": 0.15,         # 15%
        "epic": 0.008,        # 0.8%
    },  # Sum: 100%
    4: {
        "normal": 0.806,      # 80.6%
        "rare": 0.176,        # 17.6%
        "epic": 0.018,        # 1.8%
    },  # Sum: 100%
    5: {
        "normal": 0.773,      # 77.3%
        "rare": 0.202,        # 20.2%
        "epic": 0.023,        # 2.3%
        "unique": 0.002,      # 0.2%
    },  # Sum: 100%
    6: {
        "normal": 0.741,      # 74.1%
        "rare": 0.227,        # 22.7%
        "epic": 0.026,        # 2.6%
        "unique": 0.006,      # 0.6%
    },  # Sum: 100%
    7: {
        "normal": 0.7027,     # 70.27%
        "rare": 0.257,        # 25.7%
        "epic": 0.031,        # 3.1%
        "unique": 0.009,      # 0.9%
        "legendary": 0.0003,  # 0.03%
    },  # Sum: 100%
    8: {
        "normal": 0.6642,     # 66.42%
        "rare": 0.287,        # 28.7%
        "epic": 0.036,        # 3.6%
        "unique": 0.012,      # 1.2%
        "legendary": 0.0008,  # 0.08%
    },  # Sum: 100%
    9: {
        "normal": 0.6253,     # 62.53%
        "rare": 0.317,        # 31.7%
        "epic": 0.041,        # 4.1%
        "unique": 0.015,      # 1.5%
        "legendary": 0.0017,  # 0.17%
    },  # Sum: 100%
    10: {
        "normal": 0.5866,     # 58.66%
        "rare": 0.347,        # 34.7%
        "epic": 0.046,        # 4.6%
        "unique": 0.018,      # 1.8%
        "legendary": 0.0024,  # 0.24% - USER CONFIRMED
    },  # Sum: 100%
    11: {
        "normal": 0.5477,     # 54.77%
        "rare": 0.377,        # 37.7%
        "epic": 0.051,        # 5.1%
        "unique": 0.021,      # 2.1%
        "legendary": 0.0032,  # 0.32% - USER CONFIRMED
        "mystic": 0.0001,     # 0.01% - USER CONFIRMED
    },  # Sum: 100%
    12: {
        "normal": 0.5089,     # 50.89%
        "rare": 0.407,        # 40.7%
        "epic": 0.056,        # 5.6%
        "unique": 0.024,      # 2.4%
        "legendary": 0.0038,  # 0.38%
        "mystic": 0.0003,     # 0.03%
    },  # Sum: 100%
    13: {
        "normal": 0.4701,     # 47.01%
        "rare": 0.437,        # 43.7%
        "epic": 0.061,        # 6.1%
        "unique": 0.027,      # 2.7%
        "legendary": 0.0044,  # 0.44%
        "mystic": 0.0005,     # 0.05%
    },  # Sum: 100%
    14: {
        "normal": 0.4315,     # 43.15%
        "rare": 0.467,        # 46.7%
        "epic": 0.066,        # 6.6%
        "unique": 0.030,      # 3.0%
        "legendary": 0.0048,  # 0.48%
        "mystic": 0.0007,     # 0.07%
    },  # Sum: 100%
    15: {
        "normal": 0.39287,    # 39.287%
        "rare": 0.497,        # 49.7%
        "epic": 0.071,        # 7.1%
        "unique": 0.033,      # 3.3%
        "legendary": 0.0050,  # 0.50%
        "mystic": 0.0011,     # 0.11% - USER CONFIRMED
        "ancient": 0.00003,   # 0.003% (wiki shows 0.00%, but exists)
    },  # Sum: 100%
    16: {
        "normal": 0.39342,    # 39.342%
        "rare": 0.497,        # 49.7%
        "epic": 0.071,        # 7.1%
        "unique": 0.033,      # 3.3%
        "legendary": 0.004,   # 0.4%
        "mystic": 0.0015,     # 0.15%
        "ancient": 0.00008,   # 0.008%
    },  # Sum: 100%
    17: {
        "normal": 0.39297,    # 39.297%
        "rare": 0.497,        # 49.7%
        "epic": 0.071,        # 7.1%
        "unique": 0.033,      # 3.3%
        "legendary": 0.004,   # 0.4%
        "mystic": 0.0019,     # 0.19%
        "ancient": 0.00013,   # 0.013%
    },  # Sum: 100%
}


# =============================================================================
# TIER PATTERN ASSIGNMENTS BY LEVEL AND RARITY
# =============================================================================
# Maps each (level, rarity) to the tier distribution pattern name

TIER_PATTERN_MAP = {
    # ==========================================================================
    # Level 1: Normal + Rare (first unlock)
    # ==========================================================================
    (1, "normal"): "40_30_20_10",
    (1, "rare"): "70_30",

    # ==========================================================================
    # Level 2: Rare splits to 4 tiers
    # ==========================================================================
    (2, "normal"): "40_30_20_10",
    (2, "rare"): "50_30_15_5",

    # ==========================================================================
    # Level 3: Epic unlocks
    # ==========================================================================
    (3, "normal"): "40_30_20_10",
    (3, "rare"): "40_30_20_10",
    (3, "epic"): "70_30",

    # ==========================================================================
    # Level 4: Epic matures
    # ==========================================================================
    (4, "normal"): "40_30_20_10",
    (4, "rare"): "40_30_20_10",
    (4, "epic"): "40_30_20_10",

    # ==========================================================================
    # Level 5: Unique unlocks
    # ==========================================================================
    (5, "normal"): "40_30_20_10",
    (5, "rare"): "40_30_20_10",
    (5, "epic"): "40_30_20_10",
    (5, "unique"): "70_30",

    # ==========================================================================
    # Level 6: Unique splits
    # ==========================================================================
    (6, "normal"): "40_30_20_10",
    (6, "rare"): "40_30_20_10",
    (6, "epic"): "40_30_20_10",
    (6, "unique"): "50_30_15_5",

    # ==========================================================================
    # Level 7: Legendary unlocks (T4 only)
    # ==========================================================================
    (7, "normal"): "40_30_20_10",
    (7, "rare"): "40_30_20_10",
    (7, "epic"): "40_30_20_10",
    (7, "unique"): "40_30_20_10",
    (7, "legendary"): "100",

    # ==========================================================================
    # Level 8: Legendary splits to T4/T3
    # ==========================================================================
    (8, "normal"): "40_30_20_10",
    (8, "rare"): "40_30_20_10",
    (8, "epic"): "40_30_20_10",
    (8, "unique"): "40_30_20_10",
    (8, "legendary"): "70_30",

    # ==========================================================================
    # Level 9: Legendary gets T2 (3 tiers)
    # ==========================================================================
    (9, "normal"): "40_30_20_10",
    (9, "rare"): "40_30_20_10",
    (9, "epic"): "40_30_20_10",
    (9, "unique"): "40_30_20_10",
    (9, "legendary"): "60_30_10",

    # ==========================================================================
    # Level 10: Legendary gets 4 tiers (50/30/15/5) - USER CONFIRMED
    # ==========================================================================
    (10, "normal"): "40_30_20_10",
    (10, "rare"): "40_30_20_10",
    (10, "epic"): "40_30_20_10",
    (10, "unique"): "40_30_20_10",
    (10, "legendary"): "50_30_15_5",

    # ==========================================================================
    # Level 11: Legendary (40/33/20/7) - USER CONFIRMED, Mystic unlocks
    # ==========================================================================
    (11, "normal"): "40_30_20_10",
    (11, "rare"): "40_30_20_10",
    (11, "epic"): "40_30_20_10",
    (11, "unique"): "40_30_20_10",
    (11, "legendary"): "40_33_20_7",
    (11, "mystic"): "100",

    # ==========================================================================
    # Level 12: Legendary continues, Mystic splits to T4/T3
    # ==========================================================================
    (12, "normal"): "40_30_20_10",
    (12, "rare"): "40_30_20_10",
    (12, "epic"): "40_30_20_10",
    (12, "unique"): "40_30_20_10",
    (12, "legendary"): "40_33_20_7",
    (12, "mystic"): "70_30",

    # ==========================================================================
    # Level 13: Mystic gets 3 tiers
    # ==========================================================================
    (13, "normal"): "40_30_20_10",
    (13, "rare"): "40_30_20_10",
    (13, "epic"): "40_30_20_10",
    (13, "unique"): "40_30_20_10",
    (13, "legendary"): "40_33_20_7",
    (13, "mystic"): "60_30_10",

    # ==========================================================================
    # Level 14: Mystic gets 4 tiers
    # ==========================================================================
    (14, "normal"): "40_30_20_10",
    (14, "rare"): "40_30_20_10",
    (14, "epic"): "40_30_20_10",
    (14, "unique"): "40_30_20_10",
    (14, "legendary"): "40_33_20_7",
    (14, "mystic"): "50_30_15_5",

    # ==========================================================================
    # Level 15: Mystic (50/30/13/7) - USER CONFIRMED, Ancient unlocks
    # ==========================================================================
    (15, "normal"): "40_30_20_10",
    (15, "rare"): "40_30_20_10",
    (15, "epic"): "40_30_20_10",
    (15, "unique"): "40_30_20_10",
    (15, "legendary"): "50_30_13_7",
    (15, "mystic"): "50_30_13_7",
    (15, "ancient"): "100",

    # ==========================================================================
    # Level 16: Ancient splits to T4/T3 (75/25)
    # ==========================================================================
    (16, "normal"): "40_30_20_10",
    (16, "rare"): "40_30_20_10",
    (16, "epic"): "40_30_20_10",
    (16, "unique"): "40_30_20_10",
    (16, "legendary"): "40_30_20_10",
    (16, "mystic"): "40_33_20_7",
    (16, "ancient"): "75_25",

    # ==========================================================================
    # Level 17: Ancient gets 3 tiers (65/25/10)
    # ==========================================================================
    (17, "normal"): "40_30_20_10",
    (17, "rare"): "40_30_20_10",
    (17, "epic"): "40_30_20_10",
    (17, "unique"): "40_30_20_10",
    (17, "legendary"): "40_30_20_10",
    (17, "mystic"): "40_33_20_7",
    (17, "ancient"): "65_25_10",
}


# =============================================================================
# DERIVED TIER DISTRIBUTIONS (COMPUTED FROM PATTERNS)
# =============================================================================

def _build_tier_distributions() -> Dict[int, Dict[str, Dict[int, float]]]:
    """Build tier distributions from pattern map."""
    result = {}
    for (level, rarity), pattern_name in TIER_PATTERN_MAP.items():
        if level not in result:
            result[level] = {}
        result[level][rarity] = _get_tier_distribution(pattern_name)
    return result


TIER_DISTRIBUTIONS = _build_tier_distributions()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_level_from_summons(total_summons: int) -> int:
    """Get the summoning level based on total summons performed."""
    level = 1
    for lvl, threshold in sorted(LEVEL_THRESHOLDS.items()):
        if total_summons >= threshold:
            level = lvl
        else:
            break
    return level


def get_summons_for_level(level: int) -> int:
    """Get the total summons required to reach a specific level."""
    level = min(max(level, 1), 17)
    return LEVEL_THRESHOLDS.get(level, 0)


def get_summons_to_next_level(current_summons: int) -> int:
    """Get remaining summons needed to reach the next level."""
    current_level = get_level_from_summons(current_summons)
    if current_level >= 17:
        return 0  # Already at max level
    next_level_threshold = LEVEL_THRESHOLDS.get(current_level + 1, 0)
    return max(0, next_level_threshold - current_summons)


def get_rarity_rate(level: int, rarity: str) -> float:
    """Get the probability of a rarity at a summoning level."""
    level = min(max(level, 1), 17)
    rates = RARITY_RATES.get(level, {})
    return rates.get(rarity.lower(), 0.0)


def get_tier_distribution(level: int, rarity: str) -> Dict[int, float]:
    """Get the tier distribution within a rarity at a summoning level."""
    level = min(max(level, 1), 17)
    dists = TIER_DISTRIBUTIONS.get(level, {})
    return dists.get(rarity.lower(), {})


def get_weapon_rate(level: int, rarity: str, tier: int) -> float:
    """
    Get the drop rate for a specific weapon.

    Rate = rarity_rate * tier_distribution[tier]
    """
    rarity_rate = get_rarity_rate(level, rarity)
    tier_dist = get_tier_distribution(level, rarity)
    tier_pct = tier_dist.get(tier, 0.0)
    return rarity_rate * tier_pct


def get_all_weapon_rates(level: int) -> Dict[Tuple[str, int], float]:
    """Get all weapon drop rates at a summoning level."""
    level = min(max(level, 1), 17)
    rates = {}

    for rarity, rarity_rate in RARITY_RATES.get(level, {}).items():
        tier_dist = get_tier_distribution(level, rarity)
        for tier, tier_pct in tier_dist.items():
            rates[(rarity, tier)] = rarity_rate * tier_pct

    return rates


# =============================================================================
# AWAKENING & PROMOTION HELPERS
# =============================================================================

def get_duplicates_for_awakening(target_awakening: int) -> int:
    """
    Get total duplicates needed to reach a target awakening level.

    Args:
        target_awakening: Target awakening level (1-5)

    Returns:
        Total duplicates needed (e.g., A3 needs 1+2+3 = 6)
    """
    if target_awakening < 1:
        return 0
    target_awakening = min(target_awakening, 5)
    return sum(AWAKENING_COSTS.get(i, 0) for i in range(1, target_awakening + 1))


def get_total_copies_for_awakening(target_awakening: int) -> int:
    """
    Get total copies needed to have a weapon at target awakening.

    This includes the initial copy plus all duplicates for awakening.

    Args:
        target_awakening: Target awakening level (0-5, 0 = no awakening)

    Returns:
        Total copies needed (e.g., A5 needs 1 + 15 = 16 copies)
    """
    return 1 + get_duplicates_for_awakening(target_awakening)


def get_total_copies_to_promote(from_tier: int) -> int:
    """
    Get total copies needed to max awaken and promote a weapon.

    Args:
        from_tier: The tier of the weapon to promote (1-4)

    Returns:
        Total copies needed: 1 initial + 15 awakening + 5 promotion = 21
    """
    # All tiers require same number of copies to max and promote
    return 1 + TOTAL_AWAKENING_COST + PROMOTION_COST  # 21


def get_promotion_result(rarity: str, tier: int) -> Tuple[str, int]:
    """
    Get the resulting weapon after promotion.

    Promotion rule: T1 promoted → T4 of next rarity

    Args:
        rarity: Current weapon rarity
        tier: Current weapon tier (must be 1 for cross-rarity promotion)

    Returns:
        Tuple of (new_rarity, new_tier) or (None, None) if can't promote
    """
    rarity = rarity.lower()

    if rarity not in RARITY_ORDER:
        return (None, None)

    rarity_idx = RARITY_ORDER.index(rarity)

    if tier == 1:
        # T1 promotes to T4 of next rarity
        if rarity_idx + 1 < len(RARITY_ORDER):
            return (RARITY_ORDER[rarity_idx + 1], 4)
        return (None, None)  # Ancient T1 can't promote further
    else:
        # T2-T4 promote to T(tier-1) of same rarity
        return (rarity, tier - 1)


def get_promotion_path_to(target_rarity: str, target_tier: int) -> list:
    """
    Get the promotion path to reach a target weapon.

    Returns the chain of weapons needed, starting from lowest.
    Only considers T1 → next rarity T4 promotions.

    Args:
        target_rarity: Target weapon rarity
        target_tier: Target weapon tier

    Returns:
        List of (rarity, tier) tuples from source to target
        Empty list if no promotion path exists
    """
    target_rarity = target_rarity.lower()

    if target_rarity not in RARITY_ORDER:
        return []

    # Only T4 targets can be reached via T1 promotion
    if target_tier != 4:
        return []

    target_idx = RARITY_ORDER.index(target_rarity)

    # Can't promote to Normal (lowest rarity)
    if target_idx == 0:
        return []

    # Source is T1 of previous rarity
    source_rarity = RARITY_ORDER[target_idx - 1]

    return [(source_rarity, 1), (target_rarity, 4)]


# =============================================================================
# EXPECTED VALUE CALCULATIONS
# =============================================================================

def calculate_expected_tickets(level: int, rarity: str, tier: int) -> float:
    """
    Calculate expected number of tickets to obtain a specific weapon.

    Uses geometric distribution: E[X] = 1/p

    Returns float('inf') if weapon not available at this level.
    """
    rate = get_weapon_rate(level, rarity, tier)
    if rate <= 0:
        return float('inf')
    return 1.0 / rate


def calculate_expected_diamonds(level: int, rarity: str, tier: int) -> float:
    """
    Calculate expected diamond cost to obtain a specific weapon.

    Returns float('inf') if weapon not available at this level.
    """
    expected_tickets = calculate_expected_tickets(level, rarity, tier)
    return expected_tickets * DIAMONDS_PER_TICKET


def calculate_expected_tickets_for_rarity(level: int, rarity: str) -> float:
    """
    Calculate expected tickets to obtain ANY weapon of a specific rarity.
    """
    rate = get_rarity_rate(level, rarity)
    if rate <= 0:
        return float('inf')
    return 1.0 / rate


def calculate_prob_in_n_tickets(
    level: int,
    rarity: str,
    tier: int,
    num_tickets: int
) -> float:
    """
    Calculate probability of obtaining target weapon within N tickets.

    Uses: P(at least 1) = 1 - (1-p)^n
    """
    rate = get_weapon_rate(level, rarity, tier)
    if rate <= 0:
        return 0.0
    if rate >= 1:
        return 1.0
    return 1.0 - ((1.0 - rate) ** num_tickets)


def calculate_tickets_for_probability(
    level: int,
    rarity: str,
    tier: int,
    target_prob: float
) -> float:
    """
    Calculate tickets needed to achieve a target probability.

    Solves: target_prob = 1 - (1-p)^n
    => n = log(1 - target_prob) / log(1 - p)
    """
    import math

    rate = get_weapon_rate(level, rarity, tier)
    if rate <= 0:
        return float('inf')
    if rate >= 1:
        return 1.0
    if target_prob <= 0:
        return 0.0
    if target_prob >= 1:
        return float('inf')

    return math.log(1 - target_prob) / math.log(1 - rate)


def calculate_expected_tickets_for_copies(
    level: int,
    rarity: str,
    tier: int,
    copies: int
) -> float:
    """
    Calculate expected tickets to obtain N copies of a specific weapon.

    Since each summon is independent, expected tickets for N copies = N × (1/p)

    Args:
        level: Summoning level
        rarity: Weapon rarity
        tier: Weapon tier
        copies: Number of copies needed

    Returns:
        Expected tickets (float('inf') if weapon unavailable)
    """
    if copies <= 0:
        return 0.0
    expected_per_copy = calculate_expected_tickets(level, rarity, tier)
    return copies * expected_per_copy


def calculate_expected_diamonds_for_copies(
    level: int,
    rarity: str,
    tier: int,
    copies: int
) -> float:
    """
    Calculate expected diamond cost to obtain N copies of a specific weapon.

    Args:
        level: Summoning level
        rarity: Weapon rarity
        tier: Weapon tier
        copies: Number of copies needed

    Returns:
        Expected diamonds (float('inf') if weapon unavailable)
    """
    expected_tickets = calculate_expected_tickets_for_copies(level, rarity, tier, copies)
    return expected_tickets * DIAMONDS_PER_TICKET


def calculate_awakening_cost(
    level: int,
    rarity: str,
    tier: int,
    current_awakening: int,
    target_awakening: int
) -> dict:
    """
    Calculate expected cost to awaken a weapon from current to target level.

    Args:
        level: Summoning level
        rarity: Weapon rarity
        tier: Weapon tier
        current_awakening: Current awakening level (0-5)
        target_awakening: Target awakening level (1-5)

    Returns:
        Dict with 'copies_needed', 'expected_tickets', 'expected_diamonds'
    """
    current_awakening = max(0, min(current_awakening, 5))
    target_awakening = max(1, min(target_awakening, 5))

    if target_awakening <= current_awakening:
        return {
            'copies_needed': 0,
            'expected_tickets': 0.0,
            'expected_diamonds': 0.0,
        }

    # Calculate duplicates needed
    copies_at_current = get_total_copies_for_awakening(current_awakening)
    copies_at_target = get_total_copies_for_awakening(target_awakening)
    copies_needed = copies_at_target - copies_at_current

    expected_tickets = calculate_expected_tickets_for_copies(level, rarity, tier, copies_needed)
    expected_diamonds = expected_tickets * DIAMONDS_PER_TICKET

    return {
        'copies_needed': copies_needed,
        'expected_tickets': expected_tickets,
        'expected_diamonds': expected_diamonds,
    }


def calculate_promotion_path_cost(
    level: int,
    target_rarity: str,
    target_tier: int
) -> dict:
    """
    Calculate expected cost to obtain a weapon via promotion path.

    Only works for T4 targets (from promoting T1 of lower rarity).

    Args:
        level: Summoning level
        target_rarity: Target weapon rarity
        target_tier: Target weapon tier (must be 4)

    Returns:
        Dict with promotion path details, or empty dict if no path exists
    """
    path = get_promotion_path_to(target_rarity, target_tier)

    if not path:
        return {}

    source_rarity, source_tier = path[0]

    # Total copies needed: 1 initial + 15 awakening + 5 promotion = 21
    total_copies = get_total_copies_to_promote(source_tier)

    expected_tickets = calculate_expected_tickets_for_copies(
        level, source_rarity, source_tier, total_copies
    )
    expected_diamonds = expected_tickets * DIAMONDS_PER_TICKET

    # Compare with direct summoning cost
    direct_tickets = calculate_expected_tickets(level, target_rarity, target_tier)
    direct_diamonds = direct_tickets * DIAMONDS_PER_TICKET

    return {
        'source_rarity': source_rarity,
        'source_tier': source_tier,
        'target_rarity': target_rarity,
        'target_tier': target_tier,
        'copies_needed': total_copies,
        'expected_tickets': expected_tickets,
        'expected_diamonds': expected_diamonds,
        'direct_tickets': direct_tickets,
        'direct_diamonds': direct_diamonds,
        'promotion_cheaper': expected_tickets < direct_tickets,
    }


def compare_acquisition_methods(
    level: int,
    rarity: str,
    tier: int
) -> dict:
    """
    Compare direct summoning vs promotion path for acquiring a weapon.

    Args:
        level: Summoning level
        rarity: Target weapon rarity
        tier: Target weapon tier

    Returns:
        Dict with comparison details
    """
    # Direct summoning cost
    direct_tickets = calculate_expected_tickets(level, rarity, tier)
    direct_diamonds = direct_tickets * DIAMONDS_PER_TICKET

    result = {
        'rarity': rarity,
        'tier': tier,
        'direct_tickets': direct_tickets,
        'direct_diamonds': direct_diamonds,
        'promotion_path': None,
        'recommendation': 'direct',
    }

    # Check promotion path (only for T4)
    if tier == 4:
        promo = calculate_promotion_path_cost(level, rarity, tier)
        if promo:
            result['promotion_path'] = promo
            if promo['promotion_cheaper']:
                result['recommendation'] = 'promotion'

    return result


# =============================================================================
# SUMMONING VALUE ANALYSIS
# =============================================================================

def analyze_summoning_value(
    level: int,
    current_weapons: Dict[str, Dict],
    ticket_cost_diamonds: float = 100.0
) -> list:
    """
    Analyze which weapons are worth summoning for.

    Args:
        level: Current summoning level
        current_weapons: Dict of weapon_key -> {level, awakening}
        ticket_cost_diamonds: Diamond cost per summon ticket

    Returns:
        List of weapon analysis dicts sorted by value
    """
    from weapons import get_base_atk, get_inventory_ratio

    results = []
    all_rates = get_all_weapon_rates(level)

    for (rarity, tier), rate in all_rates.items():
        if rate <= 0:
            continue

        weapon_key = f"{rarity}_{tier}"
        existing = current_weapons.get(weapon_key, {})
        existing_level = existing.get('level', 0)
        existing_awakening = existing.get('awakening', 0)

        expected_tickets = 1.0 / rate
        expected_diamonds = expected_tickets * ticket_cost_diamonds

        # Determine use case
        if existing_level == 0:
            use_case = "new"
            # Value = inventory ATK at level 1
            base_atk = get_base_atk(rarity, tier)
            inv_ratio = get_inventory_ratio(rarity)
            atk_value = base_atk * 1.0 * inv_ratio  # Level 1 multiplier ~1.0
        elif existing_awakening < 5:
            use_case = "awakening"
            # Value = +20 level cap (indirect value)
            atk_value = 0  # Hard to quantify directly
        else:
            use_case = "max_awakening"
            atk_value = 0

        results.append({
            'rarity': rarity,
            'tier': tier,
            'weapon_key': weapon_key,
            'drop_rate': rate,
            'expected_tickets': expected_tickets,
            'expected_diamonds': expected_diamonds,
            'use_case': use_case,
            'atk_value': atk_value,
            'existing_level': existing_level,
            'existing_awakening': existing_awakening,
        })

    # Sort by drop rate (most accessible first)
    results.sort(key=lambda x: -x['drop_rate'])

    return results


# =============================================================================
# DISPLAY HELPERS
# =============================================================================

def format_rate(rate: float) -> str:
    """Format a rate for display."""
    if rate >= 0.01:
        return f"{rate * 100:.2f}%"
    elif rate >= 0.0001:
        return f"{rate * 100:.3f}%"
    else:
        return f"{rate * 100:.4f}%"


def print_level_summary(level: int, show_tier_pct: bool = False):
    """Print a summary of drop rates at a summoning level."""
    print(f"\n=== Summoning Level {level} ===")

    for rarity in ['normal', 'rare', 'epic', 'unique', 'legendary', 'mystic', 'ancient']:
        rarity_rate = get_rarity_rate(level, rarity)
        if rarity_rate <= 0:
            continue

        print(f"\n{rarity.capitalize()}: {format_rate(rarity_rate)} total")

        tier_dist = get_tier_distribution(level, rarity)
        for tier in [4, 3, 2, 1]:
            if tier in tier_dist:
                tier_pct = tier_dist[tier] * 100  # % within rarity
                weapon_rate = get_weapon_rate(level, rarity, tier)
                expected = calculate_expected_tickets(level, rarity, tier)
                if show_tier_pct:
                    print(f"  T{tier}: {tier_pct:.1f}% of {rarity} -> {format_rate(weapon_rate)} overall ({expected:.0f} tickets)")
                else:
                    print(f"  T{tier}: {format_rate(weapon_rate)} ({expected:.0f} expected tickets)")


# =============================================================================
# VALIDATION
# =============================================================================

# Wiki reference values for validation (rounded to 2 decimal places)
_WIKI_REFERENCE = {
    1: {
        ("normal", 4): 36.80, ("normal", 3): 27.60, ("normal", 2): 18.40, ("normal", 1): 9.20,
        ("rare", 4): 5.60, ("rare", 3): 2.40,
    },
    2: {
        ("normal", 4): 35.20, ("normal", 3): 26.40, ("normal", 2): 17.60, ("normal", 1): 8.80,
        ("rare", 4): 6.00, ("rare", 3): 3.60, ("rare", 2): 1.80, ("rare", 1): 0.60,
    },
    3: {
        ("normal", 4): 33.68, ("normal", 3): 25.26, ("normal", 2): 16.84, ("normal", 1): 8.42,
        ("rare", 4): 6.00, ("rare", 3): 4.50, ("rare", 2): 3.00, ("rare", 1): 1.50,
        ("epic", 4): 0.56, ("epic", 3): 0.24,
    },
    4: {
        ("normal", 4): 32.24, ("normal", 3): 24.18, ("normal", 2): 16.12, ("normal", 1): 8.06,
        ("rare", 4): 7.04, ("rare", 3): 5.28, ("rare", 2): 3.52, ("rare", 1): 1.76,
        ("epic", 4): 0.72, ("epic", 3): 0.54, ("epic", 2): 0.36, ("epic", 1): 0.18,
    },
    5: {
        ("normal", 4): 30.94, ("normal", 3): 23.20, ("normal", 2): 15.47, ("normal", 1): 7.74,
        ("rare", 4): 8.06, ("rare", 3): 6.04, ("rare", 2): 4.03, ("rare", 1): 2.02,
        ("epic", 4): 0.92, ("epic", 3): 0.69, ("epic", 2): 0.46, ("epic", 1): 0.23,
        ("unique", 4): 0.14, ("unique", 3): 0.06,
    },
    6: {
        ("normal", 4): 29.64, ("normal", 3): 22.23, ("normal", 2): 14.82, ("normal", 1): 7.41,
        ("rare", 4): 9.08, ("rare", 3): 6.81, ("rare", 2): 4.54, ("rare", 1): 2.27,
        ("epic", 4): 1.04, ("epic", 3): 0.78, ("epic", 2): 0.52, ("epic", 1): 0.26,
        ("unique", 4): 0.30, ("unique", 3): 0.18, ("unique", 2): 0.09, ("unique", 1): 0.03,
    },
    7: {
        ("normal", 4): 28.11, ("normal", 3): 21.08, ("normal", 2): 14.05, ("normal", 1): 7.03,
        ("rare", 4): 10.28, ("rare", 3): 7.71, ("rare", 2): 5.14, ("rare", 1): 2.57,
        ("epic", 4): 1.24, ("epic", 3): 0.93, ("epic", 2): 0.62, ("epic", 1): 0.31,
        ("unique", 4): 0.36, ("unique", 3): 0.27, ("unique", 2): 0.18, ("unique", 1): 0.09,
        ("legendary", 4): 0.03,
    },
    8: {
        ("normal", 4): 26.57, ("normal", 3): 19.93, ("normal", 2): 13.28, ("normal", 1): 6.64,
        ("rare", 4): 11.48, ("rare", 3): 8.61, ("rare", 2): 5.74, ("rare", 1): 2.87,
        ("epic", 4): 1.44, ("epic", 3): 1.08, ("epic", 2): 0.72, ("epic", 1): 0.36,
        ("unique", 4): 0.48, ("unique", 3): 0.36, ("unique", 2): 0.24, ("unique", 1): 0.12,
        ("legendary", 4): 0.06, ("legendary", 3): 0.02,
    },
    9: {
        ("normal", 4): 25.02, ("normal", 3): 18.76, ("normal", 2): 12.51, ("normal", 1): 6.25,
        ("rare", 4): 12.68, ("rare", 3): 9.51, ("rare", 2): 6.34, ("rare", 1): 3.17,
        ("epic", 4): 1.64, ("epic", 3): 1.23, ("epic", 2): 0.82, ("epic", 1): 0.41,
        ("unique", 4): 0.60, ("unique", 3): 0.45, ("unique", 2): 0.30, ("unique", 1): 0.15,
        ("legendary", 4): 0.10, ("legendary", 3): 0.05, ("legendary", 2): 0.02,
    },
    10: {
        ("normal", 4): 23.46, ("normal", 3): 17.60, ("normal", 2): 11.73, ("normal", 1): 5.87,
        ("rare", 4): 13.88, ("rare", 3): 10.41, ("rare", 2): 6.94, ("rare", 1): 3.47,
        ("epic", 4): 1.84, ("epic", 3): 1.38, ("epic", 2): 0.92, ("epic", 1): 0.46,
        ("unique", 4): 0.72, ("unique", 3): 0.54, ("unique", 2): 0.36, ("unique", 1): 0.18,
        ("legendary", 4): 0.12, ("legendary", 3): 0.07, ("legendary", 2): 0.04,
    },
    11: {
        ("normal", 4): 21.91, ("normal", 3): 16.43, ("normal", 2): 10.95, ("normal", 1): 5.48,
        ("rare", 4): 15.08, ("rare", 3): 11.31, ("rare", 2): 7.54, ("rare", 1): 3.77,
        ("epic", 4): 2.04, ("epic", 3): 1.53, ("epic", 2): 1.02, ("epic", 1): 0.51,
        ("unique", 4): 0.84, ("unique", 3): 0.63, ("unique", 2): 0.42, ("unique", 1): 0.21,
        ("legendary", 4): 0.13, ("legendary", 3): 0.11, ("legendary", 2): 0.06,
        ("mystic", 4): 0.01,
    },
    12: {
        ("normal", 4): 20.37, ("normal", 3): 15.28, ("normal", 2): 10.18, ("normal", 1): 5.09,
        ("rare", 4): 16.28, ("rare", 3): 12.21, ("rare", 2): 8.14, ("rare", 1): 4.07,
        ("epic", 4): 2.24, ("epic", 3): 1.68, ("epic", 2): 1.12, ("epic", 1): 0.56,
        ("unique", 4): 0.96, ("unique", 3): 0.72, ("unique", 2): 0.48, ("unique", 1): 0.24,
        ("legendary", 4): 0.14, ("legendary", 3): 0.12, ("legendary", 2): 0.07, ("legendary", 1): 0.01,
        ("mystic", 4): 0.02, ("mystic", 3): 0.01,
    },
    13: {
        ("normal", 4): 18.82, ("normal", 3): 14.12, ("normal", 2): 9.41, ("normal", 1): 4.71,
        ("rare", 4): 17.48, ("rare", 3): 13.11, ("rare", 2): 8.74, ("rare", 1): 4.37,
        ("epic", 4): 2.44, ("epic", 3): 1.83, ("epic", 2): 1.22, ("epic", 1): 0.61,
        ("unique", 4): 1.08, ("unique", 3): 0.81, ("unique", 2): 0.54, ("unique", 1): 0.27,
        ("legendary", 4): 0.16, ("legendary", 3): 0.13, ("legendary", 2): 0.08, ("legendary", 1): 0.01,
        ("mystic", 4): 0.03, ("mystic", 3): 0.01, ("mystic", 2): 0.01,
    },
    14: {
        ("normal", 4): 17.29, ("normal", 3): 12.97, ("normal", 2): 8.65, ("normal", 1): 4.32,
        ("rare", 4): 18.68, ("rare", 3): 14.01, ("rare", 2): 9.34, ("rare", 1): 4.67,
        ("epic", 4): 2.64, ("epic", 3): 1.98, ("epic", 2): 1.32, ("epic", 1): 0.66,
        ("unique", 4): 1.20, ("unique", 3): 0.90, ("unique", 2): 0.60, ("unique", 1): 0.30,
        ("legendary", 4): 0.16, ("legendary", 3): 0.13, ("legendary", 2): 0.08, ("legendary", 1): 0.00,
        ("mystic", 4): 0.04, ("mystic", 3): 0.02, ("mystic", 2): 0.01, ("mystic", 1): 0.00,
    },
    15: {
        ("normal", 4): 15.75, ("normal", 3): 11.82, ("normal", 2): 7.88, ("normal", 1): 3.94,
        ("rare", 4): 19.88, ("rare", 3): 14.91, ("rare", 2): 9.94, ("rare", 1): 4.97,
        ("epic", 4): 2.84, ("epic", 3): 2.13, ("epic", 2): 1.42, ("epic", 1): 0.71,
        ("unique", 4): 1.32, ("unique", 3): 0.99, ("unique", 2): 0.66, ("unique", 1): 0.33,
        ("legendary", 4): 0.16, ("legendary", 3): 0.13, ("legendary", 2): 0.08, ("legendary", 1): 0.03,
        ("mystic", 4): 0.06, ("mystic", 3): 0.03, ("mystic", 2): 0.01, ("mystic", 1): 0.01,
        ("ancient", 4): 0.00,  # Actually 0.003%
    },
}


def validate_against_wiki():
    """
    Validate our calculated rates against the wiki reference values.
    Returns True if all values match within tolerance.
    """
    print("\n" + "=" * 80)
    print("VALIDATION: Comparing calculated rates to wiki reference values")
    print("=" * 80)

    all_match = True
    tolerance = 0.015  # Allow 0.015% difference for rounding

    for level in range(1, 16):
        wiki_level = _WIKI_REFERENCE.get(level, {})
        errors = []

        for (rarity, tier), wiki_pct in wiki_level.items():
            # Calculate our rate
            our_rate = get_weapon_rate(level, rarity, tier) * 100  # Convert to %

            # Skip Ancient since wiki shows 0.00% but we use 0.003%
            if rarity == "ancient" and wiki_pct == 0.00:
                continue

            # Check if it matches within tolerance
            diff = abs(our_rate - wiki_pct)
            if diff > tolerance:
                errors.append(f"  {rarity.capitalize()} T{tier}: ours={our_rate:.3f}%, wiki={wiki_pct:.2f}%, diff={diff:.3f}")
                all_match = False

        if errors:
            print(f"\nLevel {level} - MISMATCHES:")
            for e in errors:
                print(e)
        else:
            print(f"Level {level} - OK")

    # Verify totals sum to ~100%
    print("\n" + "-" * 40)
    print("Total probability verification:")
    for level in range(1, 16):
        our_total = sum(RARITY_RATES.get(level, {}).values()) * 100
        status = "OK" if abs(our_total - 100.0) < 0.1 else f"SUM={our_total:.3f}%"
        print(f"  Level {level}: {our_total:.3f}% {status}")

    return all_match


# =============================================================================
# SUMMON OPTIMIZER INTEGRATION
# =============================================================================


def get_summon_recommendations_for_optimizer(
    weapons_data: Dict[str, Dict],
    equipped_weapon_key: str,
    summoning_level: int,
    current_total_atk_percent: float,
) -> List[Dict]:
    """
    Get weapon summon recommendations formatted for the Upgrade Optimizer.

    This analyzes the value of summoning for each weapon type, considering:
    1. New weapons: Inventory ATK% value (level 1 weapon)
    2. Duplicates: Awakening value (level cap unlock + mastery potential)
    3. Level progression: Value of moving closer to better drop rates

    Uses a simplified model where each summon's value includes:
    - Expected weapon drop value (weighted by probabilities)
    - Fractional progress toward next level

    Args:
        weapons_data: Dict mapping "rarity_tier" -> {level, awakening}
        equipped_weapon_key: Currently equipped weapon key
        summoning_level: Current summoning level (1-17)
        current_total_atk_percent: Current total ATK% (for diminishing returns)

    Returns:
        List of recommendation dicts compatible with optimizer format
    """
    from weapon_optimizer import calculate_atk_at_level, get_max_level
    from weapons import get_inventory_ratio
    from weapon_mastery import (
        WEAPON_MASTERY_REWARDS,
        calculate_mastery_stages_from_weapons,
    )

    summoning_level = max(1, min(summoning_level, 17))
    recommendations = []

    # Get all possible weapon drops at current level
    all_rates = get_all_weapon_rates(summoning_level)

    # Calculate mastery stages for determining mastery threshold crossing
    current_mastery_stages = calculate_mastery_stages_from_weapons(weapons_data)

    for (rarity, tier), drop_rate in all_rates.items():
        if drop_rate <= 0:
            continue

        weapon_key = f"{rarity}_{tier}"
        existing = weapons_data.get(weapon_key, {})
        existing_level = existing.get('level', 0)
        existing_awakening = existing.get('awakening', 0)

        # Skip weapons already at max awakening
        if existing_awakening >= 5:
            continue

        is_new_weapon = existing_level <= 0
        is_equipped = weapon_key == equipped_weapon_key
        inv_ratio = get_inventory_ratio(rarity)

        # =====================================================================
        # Calculate value of getting this weapon
        # =====================================================================

        total_value = 0.0  # Accumulated ATK% value
        mastery_value = 0.0  # Mastery bonus value (flat stats converted to ATK%)

        if is_new_weapon:
            # Value = inventory ATK% at level 1 (only inventory since not equipped)
            level_1_atk = calculate_atk_at_level(rarity, tier, 1)
            total_value = level_1_atk * inv_ratio

            # Check if getting this weapon unlocks a mastery stage
            new_stages = current_mastery_stages.get(rarity, 0) + 1
            mastery_value = _calculate_mastery_dps_value(
                rarity, current_mastery_stages.get(rarity, 0), new_stages,
                current_total_atk_percent
            )

        else:
            # Value = awakening from A(current) to A(current+1)
            # This unlocks +20 level cap

            # Current and new max levels
            current_max = get_max_level(existing_awakening)
            new_max = get_max_level(existing_awakening + 1)

            # Investment ratio: how much of current cap is already invested
            if existing_level > 0:
                investment_ratio = min(1.0, existing_level / current_max)
            else:
                investment_ratio = 0.0

            # ATK% gain from the new cap if we level to it
            # Scale by investment ratio (higher if closer to cap)
            atk_at_current_max = calculate_atk_at_level(rarity, tier, current_max)
            atk_at_new_max = calculate_atk_at_level(rarity, tier, new_max)
            potential_atk_gain = atk_at_new_max - atk_at_current_max

            # Apply inventory/equipped ratio
            if is_equipped:
                effective_gain = potential_atk_gain * (1 + inv_ratio)
            else:
                effective_gain = potential_atk_gain * inv_ratio

            # Scale by investment ratio
            total_value = effective_gain * investment_ratio

            # Check mastery threshold
            new_stages = current_mastery_stages.get(rarity, 0) + 1
            mastery_value = _calculate_mastery_dps_value(
                rarity, current_mastery_stages.get(rarity, 0), new_stages,
                current_total_atk_percent
            )

        # Add mastery value to total (converted to effective ATK%)
        total_value += mastery_value

        # Convert ATK% to DPS% (diminishing returns formula)
        if current_total_atk_percent > 0:
            dps_gain_percent = total_value / (1 + current_total_atk_percent / 100)
        else:
            dps_gain_percent = total_value

        # =====================================================================
        # Calculate expected cost
        # =====================================================================

        expected_tickets = calculate_expected_tickets(summoning_level, rarity, tier)
        if expected_tickets == float('inf'):
            continue

        expected_diamonds = expected_tickets * DIAMONDS_PER_TICKET

        # =====================================================================
        # Calculate efficiency
        # =====================================================================

        # DPS% gain per 1000 diamonds
        efficiency = (dps_gain_percent / (expected_diamonds / 1000)) if expected_diamonds > 0 else 0

        # =====================================================================
        # Build recommendation
        # =====================================================================

        if is_new_weapon:
            description = f"Summon {rarity.capitalize()} T{tier} (New weapon)"
            use_case = "new"
        else:
            description = f"Summon {rarity.capitalize()} T{tier} (A{existing_awakening}→A{existing_awakening+1})"
            use_case = "awakening"

        # Get duplicates needed info
        if not is_new_weapon:
            copies_needed = get_duplicates_for_awakening(existing_awakening + 1) - get_duplicates_for_awakening(existing_awakening)
        else:
            copies_needed = 1

        recommendations.append({
            'type': 'Summon',
            'subtype': f'summon_{weapon_key}',
            'target': weapon_key,
            'target_display': f"🎲 {rarity.capitalize()} T{tier}",
            'description': f"🎲 {description}",
            'cost': expected_diamonds,
            'dps_gain': dps_gain_percent,
            'efficiency': efficiency,
            'details': {
                'is_new_weapon': is_new_weapon,
                'use_case': use_case,
                'current_awakening': existing_awakening,
                'target_awakening': existing_awakening + 1 if not is_new_weapon else 0,
                'expected_tickets': expected_tickets,
                'drop_rate': drop_rate,
                'drop_rate_pct': drop_rate * 100,
                'copies_needed': copies_needed,
                'value_breakdown': {
                    'atk_value': total_value - mastery_value,
                    'mastery_value': mastery_value,
                },
            },
        })

    # Sort by efficiency
    recommendations.sort(key=lambda x: x['efficiency'], reverse=True)

    return recommendations


def _calculate_mastery_dps_value(
    rarity: str,
    current_stages: int,
    new_stages: int,
    current_total_atk_percent: float
) -> float:
    """
    Calculate the DPS value of crossing mastery thresholds.

    Returns an ATK% equivalent value based on mastery rewards.
    This is an approximation - flat stats are converted to approximate ATK% value.
    """
    from weapon_mastery import WEAPON_MASTERY_REWARDS

    rarity_lower = rarity.lower()
    if rarity_lower not in WEAPON_MASTERY_REWARDS:
        return 0.0

    rewards = WEAPON_MASTERY_REWARDS[rarity_lower]

    # Find any thresholds crossed
    crossed_value = 0.0
    for reward in rewards:
        if current_stages < reward.stage <= new_stages:
            # Convert rewards to approximate ATK% value
            # Attack flat: ~0.1% per point at mid-game
            # Main stat: ~0.05% per point at mid-game
            # Accuracy: ~0.02% per point
            # Dmg mult %: direct value

            crossed_value += reward.attack * 0.1  # Attack flat -> ATK%
            crossed_value += reward.main_stat * 0.05  # Main stat -> ATK%
            crossed_value += reward.accuracy * 0.02  # Accuracy -> ATK%
            crossed_value += reward.min_dmg_mult  # Direct %
            crossed_value += reward.max_dmg_mult  # Direct %

    return crossed_value


def calculate_expected_value_per_summon(
    summoning_level: int,
    weapons_data: Dict[str, Dict],
    equipped_weapon_key: str,
    current_total_atk_percent: float,
) -> Dict:
    """
    Calculate the expected DPS value per summon using backward induction.

    This sophisticated model considers:
    1. Immediate weapon drop value at current level
    2. Value of level progression (+1 summon toward better rates)
    3. Future weapon unlocks (Ancient at level 15+)

    The model uses dynamic programming from max level (17) backward to
    calculate the true expected value at each level.

    Args:
        summoning_level: Current summoning level (1-17)
        weapons_data: Current weapon state
        equipped_weapon_key: Currently equipped weapon
        current_total_atk_percent: Total ATK% for diminishing returns

    Returns:
        Dict with expected_value_per_summon, breakdown, etc.
    """
    from weapon_optimizer import calculate_atk_at_level
    from weapons import get_inventory_ratio

    # =========================================================================
    # Phase 1: Calculate immediate weapon drop value at each level
    # =========================================================================

    level_drop_values = {}  # level -> expected ATK% per summon from drops

    for level in range(1, 18):
        drop_value = 0.0
        rates = get_all_weapon_rates(level)

        for (rarity, tier), rate in rates.items():
            if rate <= 0:
                continue

            weapon_key = f"{rarity}_{tier}"
            existing = weapons_data.get(weapon_key, {})
            existing_level = existing.get('level', 0)
            existing_awakening = existing.get('awakening', 0)
            is_new = existing_level <= 0

            if existing_awakening >= 5:
                continue  # Skip maxed weapons

            inv_ratio = get_inventory_ratio(rarity)

            # Calculate weapon value
            if is_new:
                # Level 1 inventory ATK%
                level_1_atk = calculate_atk_at_level(rarity, tier, 1)
                weapon_value = level_1_atk * inv_ratio
            else:
                # Awakening value (simplified as inventory ATK% gain)
                current_max = 100 + existing_awakening * 20
                new_max = current_max + 20
                atk_gain = calculate_atk_at_level(rarity, tier, new_max) - calculate_atk_at_level(rarity, tier, current_max)

                is_equipped = weapon_key == equipped_weapon_key
                if is_equipped:
                    weapon_value = atk_gain * (1 + inv_ratio)
                else:
                    weapon_value = atk_gain * inv_ratio

                # Scale by investment ratio
                investment = min(1.0, existing_level / current_max) if current_max > 0 else 0
                weapon_value *= investment

            # Weight by drop rate
            drop_value += weapon_value * rate

        # Convert to DPS%
        level_drop_values[level] = drop_value / (1 + current_total_atk_percent / 100) if current_total_atk_percent > 0 else drop_value

    # =========================================================================
    # Phase 2: Backward induction to calculate total value at each level
    # =========================================================================

    # V[level] = expected total value of being at that level
    # At each level, value = immediate_drop_value + progress_value

    total_values = {}

    # Start at max level - no progression value
    total_values[17] = level_drop_values[17]

    # Work backward
    for level in range(16, 0, -1):
        immediate_value = level_drop_values[level]

        # Progress value: fractional value of moving toward next level
        current_threshold = LEVEL_THRESHOLDS[level]
        next_threshold = LEVEL_THRESHOLDS.get(level + 1, current_threshold)
        summons_to_next = next_threshold - current_threshold

        if summons_to_next > 0:
            # Value improvement when reaching next level
            next_level_value = total_values.get(level + 1, immediate_value)
            level_improvement = max(0, next_level_value - immediate_value)

            # Each summon gets 1/N of that improvement
            progress_value = level_improvement / summons_to_next
        else:
            progress_value = 0

        total_values[level] = immediate_value + progress_value

    # =========================================================================
    # Return result for current level
    # =========================================================================

    current_immediate = level_drop_values[summoning_level]
    current_total = total_values[summoning_level]
    progress_component = current_total - current_immediate

    return {
        'summoning_level': summoning_level,
        'expected_value_per_summon': current_total,
        'breakdown': {
            'immediate_drop_value': current_immediate,
            'progression_value': progress_component,
        },
        'level_values': total_values,
        'cost_per_summon_diamonds': DIAMONDS_PER_TICKET,
        'efficiency': current_total / (DIAMONDS_PER_TICKET / 1000) if DIAMONDS_PER_TICKET > 0 else 0,
    }


if __name__ == "__main__":
    # Run validation first
    validate_against_wiki()

    print("\n" + "=" * 60)
    print("Weapon Summoning System - Source of Truth")
    print("=" * 60)

    # Test at level 15 with tier % breakdown
    print_level_summary(15, show_tier_pct=True)

    # Verify total sums to 100%
    total = sum(RARITY_RATES.get(15, {}).values())
    print(f"\n  ** Total probability: {total * 100:.4f}% **")

    print("\n" + "=" * 60)
    print("Probability Analysis (100 tickets at Level 15):")
    print("-" * 60)

    for rarity in ['epic', 'unique', 'legendary', 'mystic', 'ancient']:
        for tier in [4, 1]:
            rate = get_weapon_rate(15, rarity, tier)
            if rate > 0:
                prob = calculate_prob_in_n_tickets(15, rarity, tier, 100)
                expected = calculate_expected_tickets(15, rarity, tier)
                print(f"  {rarity.capitalize()} T{tier}: {prob*100:.1f}% chance in 100 tickets "
                      f"(expected: {expected:.0f})")

    print("\n" + "=" * 60)
    print("Tickets for 50% probability (Level 15):")
    print("-" * 60)

    for rarity in ['unique', 'legendary', 'mystic', 'ancient']:
        rate = get_weapon_rate(15, rarity, 4)
        if rate > 0:
            tickets_50 = calculate_tickets_for_probability(15, rarity, 4, 0.50)
            print(f"  {rarity.capitalize()} T4: {tickets_50:.0f} tickets for 50% chance")

    # ==========================================================================
    # AWAKENING & PROMOTION TESTS
    # ==========================================================================
    print("\n" + "=" * 60)
    print("AWAKENING SYSTEM")
    print("=" * 60)

    print("\nDuplicates required per awakening level:")
    for level in range(1, 6):
        total = get_duplicates_for_awakening(level)
        copies = get_total_copies_for_awakening(level)
        print(f"  A{level}: {AWAKENING_COSTS[level]} dupes this level, {total} total dupes, {copies} total copies")

    print(f"\nTotal to max awaken (A5): {TOTAL_AWAKENING_COST} duplicates")
    print(f"Total to max and promote: {TOTAL_MAX_AND_PROMOTE} duplicates + 1 initial = {get_total_copies_to_promote(1)} copies")

    print("\n" + "=" * 60)
    print("PROMOTION PATHS")
    print("=" * 60)

    print("\nPromotion results (T1 -> next rarity T4):")
    for rarity in ['rare', 'epic', 'unique', 'legendary', 'mystic']:
        result = get_promotion_result(rarity, 1)
        print(f"  {rarity.capitalize()} T1 -> {result[0].capitalize() if result[0] else 'N/A'} T{result[1] if result[1] else 'N/A'}")

    print("\n" + "=" * 60)
    print("PROMOTION vs DIRECT COST COMPARISON (Level 15)")
    print("=" * 60)

    for rarity in ['epic', 'unique', 'legendary', 'mystic', 'ancient']:
        comparison = compare_acquisition_methods(15, rarity, 4)
        print(f"\n{rarity.capitalize()} T4:")
        print(f"  Direct: {comparison['direct_tickets']:,.0f} tickets ({comparison['direct_diamonds']:,.0f} diamonds)")

        if comparison['promotion_path']:
            promo = comparison['promotion_path']
            print(f"  Via {promo['source_rarity'].capitalize()} T1 promotion ({promo['copies_needed']} copies):")
            print(f"    {promo['expected_tickets']:,.0f} tickets ({promo['expected_diamonds']:,.0f} diamonds)")
            print(f"  Recommendation: {comparison['recommendation'].upper()}")
        else:
            print(f"  No promotion path available")

    print("\n" + "=" * 60)
    print("AWAKENING COST EXAMPLE (Legendary T4 at Level 15)")
    print("=" * 60)

    for target_awk in [1, 3, 5]:
        cost = calculate_awakening_cost(15, "legendary", 4, 0, target_awk)
        print(f"\n  A0 -> A{target_awk}:")
        print(f"    Copies needed: {cost['copies_needed']}")
        print(f"    Expected tickets: {cost['expected_tickets']:,.0f}")
        print(f"    Expected diamonds: {cost['expected_diamonds']:,.0f}")
