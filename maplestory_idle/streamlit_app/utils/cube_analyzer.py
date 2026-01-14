"""
Cube Analyzer - Bridge between Streamlit data and cubes.py analysis functions.

Provides cube priority recommendations using the original DPS calculation methods.
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from copy import deepcopy

# Import from the cubes module in maplestory_idle root
from cubes import (
    PotentialLine,
    PotentialTier,
    StatType,
    CubeType,
    create_item_score_result,
    calculate_expected_cubes_fast,
    calculate_efficiency_score,
    calculate_stat_rankings,
    ItemScoreResult,
    ExpectedCubesMetrics,
    EnhancedCubeRecommendation,
    POTENTIAL_STATS,
    get_stat_display_name,
    get_cached_roll_distribution,
    format_lines_for_hover,
    ExactRollDistribution,
    get_exact_roll_distribution,
    clear_exact_distribution_cache,
)

# Equipment slots
EQUIPMENT_SLOTS = [
    "hat", "top", "bottom", "gloves", "shoes",
    "belt", "shoulder", "cape", "ring", "necklace", "face"
]

# Cost per cube in diamonds
REGULAR_DIAMOND_PER_CUBE = 1000
BONUS_DIAMOND_PER_CUBE = 2000

# Mapping from Streamlit stat names to StatType enum
# Note: Some stats have multiple keys to support both legacy names and StatType.value names
STAT_NAME_TO_TYPE = {
    "dex_pct": StatType.DEX_PCT,
    "str_pct": StatType.STR_PCT,
    "int_pct": StatType.INT_PCT,
    "luk_pct": StatType.LUK_PCT,
    "dex_flat": StatType.DEX_FLAT,
    "str_flat": StatType.STR_FLAT,
    "int_flat": StatType.INT_FLAT,
    "luk_flat": StatType.LUK_FLAT,
    "damage": StatType.DAMAGE_PCT,
    "damage_pct": StatType.DAMAGE_PCT,  # StatType.DAMAGE_PCT.value
    "crit_rate": StatType.CRIT_RATE,
    "crit_damage": StatType.CRIT_DAMAGE,
    "def_pen": StatType.DEF_PEN,
    "final_damage": StatType.FINAL_DAMAGE,
    "all_skills": StatType.ALL_SKILLS,
    "min_dmg_mult": StatType.MIN_DMG_MULT,
    "max_dmg_mult": StatType.MAX_DMG_MULT,
    "attack_speed": StatType.ATTACK_SPEED,
    "defense": StatType.DEFENSE,
    "max_hp": StatType.MAX_HP,
    "max_mp": StatType.MAX_MP,
    "skill_cd": StatType.SKILL_CD,
    "buff_duration": StatType.BUFF_DURATION,
    "stat_per_level": StatType.MAIN_STAT_PER_LEVEL,
    "ba_targets": StatType.BA_TARGETS,
}

TIER_NAME_TO_ENUM = {
    "Rare": PotentialTier.RARE,
    "Epic": PotentialTier.EPIC,
    "Unique": PotentialTier.UNIQUE,
    "Legendary": PotentialTier.LEGENDARY,
    "Mystic": PotentialTier.MYSTIC,
}


@dataclass
class CubeRecommendation:
    """Detailed cube recommendation for Streamlit display."""
    slot: str
    is_bonus: bool
    tier: str

    # Scores
    current_dps_gain: float      # Current roll DPS gain %
    best_possible_dps_gain: float  # Best possible DPS gain %
    dps_efficiency: float        # current / best * 100
    percentile_score: float      # Beats X% of rolls

    # Current lines info
    line1_stat: str
    line1_value: float
    line1_dps_gain: float
    line1_yellow: bool
    line2_stat: str
    line2_value: float
    line2_dps_gain: float
    line2_yellow: bool
    line3_stat: str
    line3_value: float
    line3_dps_gain: float
    line3_yellow: bool

    # Cubing info
    expected_cubes_to_improve: float
    prob_improve_10_cubes: float
    improvement_difficulty: str
    diminishing_returns_warning: str

    # Pity info
    current_pity: int
    pity_threshold: int
    cubes_to_tier_up: float
    tier_up_score_gain: float

    # Efficiency
    efficiency_score: float
    priority_rank: int

    # Top stats to target
    top_stats: List[tuple]  # [(stat_name, dps_gain, probability), ...]

    # Useful line count
    yellow_count: int
    useful_line_count: int

    # Debug info (default value, must come last)
    baseline_dps: float = 0.0    # Baseline DPS for this slot (DEBUG)


def convert_streamlit_lines_to_potential_lines(
    slot_pots: Dict[str, Any],
    is_bonus: bool = False
) -> List[PotentialLine]:
    """
    Convert Streamlit potential data to PotentialLine objects.

    Args:
        slot_pots: Potential dict for a slot (e.g., data.equipment_potentials['hat'])
        is_bonus: True for bonus potential, False for regular

    Returns:
        List of PotentialLine objects
    """
    lines = []
    prefix = "bonus_" if is_bonus else ""

    for i in range(1, 4):
        stat_key = f"{prefix}line{i}_stat"
        val_key = f"{prefix}line{i}_value"
        yellow_key = f"{prefix}line{i}_yellow"

        stat_name = slot_pots.get(stat_key, "")
        value = float(slot_pots.get(val_key, 0))
        is_yellow = True if i == 1 else slot_pots.get(yellow_key, True)

        if stat_name and value > 0:
            stat_type = STAT_NAME_TO_TYPE.get(stat_name)
            if stat_type:
                # Check if it's a special potential
                is_special = stat_name in ["crit_damage", "def_pen", "all_skills",
                                           "final_damage", "skill_cd", "buff_duration",
                                           "stat_per_level", "ba_targets"]

                lines.append(PotentialLine(
                    slot=i,
                    stat_type=stat_type,
                    value=value,
                    is_yellow=is_yellow,
                    is_special=is_special
                ))

    return lines


def get_tier_enum(tier_str: str) -> PotentialTier:
    """Convert tier string to PotentialTier enum."""
    return TIER_NAME_TO_ENUM.get(tier_str, PotentialTier.LEGENDARY)


def analyze_slot_potentials(
    slot: str,
    slot_pots: Dict[str, Any],
    is_bonus: bool,
    dps_calc_func: Callable[[List[PotentialLine]], float],
    baseline_dps: float,
    main_stat_type: StatType = StatType.DEX_PCT,
) -> Optional[CubeRecommendation]:
    """
    Analyze a single potential type (regular or bonus) for an equipment slot.

    Args:
        slot: Equipment slot name
        slot_pots: Potential data for this slot
        is_bonus: True for bonus potential, False for regular
        dps_calc_func: Function that calculates DPS with given potential lines
        baseline_dps: DPS with empty potential lines on this slot
        main_stat_type: Player's main stat type

    Returns:
        CubeRecommendation or None if no data
    """
    # SANITY CHECK: baseline_dps should be at least 1000 for meaningful calculations
    # If it's too low, the character has almost no stats configured
    if baseline_dps < 1000:
        import logging
        logging.warning(f"analyze_slot_potentials: baseline_dps={baseline_dps} is very low for slot={slot}, is_bonus={is_bonus}")
        # Still continue but results may not be meaningful

    prefix = "bonus_" if is_bonus else ""
    tier_key = f"{prefix}tier" if is_bonus else "tier"
    pity_key = f"{prefix}pity" if is_bonus else "regular_pity"

    tier_str = slot_pots.get(tier_key, "Legendary")
    tier = get_tier_enum(tier_str)
    current_pity = int(slot_pots.get(pity_key, 0))

    # Get tier stats - if none available, skip
    tier_stats = POTENTIAL_STATS.get(tier, [])
    if not tier_stats:
        return None

    # Convert current lines to PotentialLine objects
    current_lines = convert_streamlit_lines_to_potential_lines(slot_pots, is_bonus)

    # Create item score result
    item_score = create_item_score_result(
        lines=current_lines,
        tier=tier,
        slot=slot,
        dps_calc_func=dps_calc_func,
        current_dps=baseline_dps,
        main_stat_type=main_stat_type
    )

    # Calculate expected cubes metrics
    cube_type = CubeType.BONUS if is_bonus else CubeType.REGULAR
    expected_cubes = calculate_expected_cubes_fast(
        slot=slot,
        tier=tier,
        current_lines=current_lines,
        dps_calc_func=dps_calc_func,
        current_dps=baseline_dps,
        main_stat_type=main_stat_type,
        current_pity=current_pity,
        cube_type=cube_type,
        n_cached_rolls=3000,  # Slightly fewer for faster analysis
    )

    # Calculate efficiency score using actual DPS values
    # Efficiency = Expected DPS% gain per 100k diamonds spent
    diamond_cost = BONUS_DIAMOND_PER_CUBE if is_bonus else REGULAR_DIAMOND_PER_CUBE
    efficiency = calculate_efficiency_score(
        expected_cubes_to_improve=expected_cubes.cubes_to_any_improvement,
        diamond_cost_per_cube=diamond_cost,
        median_dps_improvement=expected_cubes.median_dps_improvement,
        tier_up_efficiency_bonus=expected_cubes.tier_up_efficiency_bonus,
    )

    # Get all stats ranked by DPS gain
    top_stats = calculate_stat_rankings(
        slot=slot,
        tier=tier,
        dps_calc_func=dps_calc_func,
        current_dps=baseline_dps,
        main_stat_type=main_stat_type,
        top_n=100  # Show all stats, not just top 5
    )

    # Extract line info for display
    line_stats = ["", "", ""]
    line_values = [0.0, 0.0, 0.0]
    line_dps_gains = [0.0, 0.0, 0.0]
    line_yellows = [True, True, True]

    for i in range(1, 4):
        stat_key = f"{prefix}line{i}_stat"
        val_key = f"{prefix}line{i}_value"
        yellow_key = f"{prefix}line{i}_yellow"

        line_stats[i-1] = slot_pots.get(stat_key, "")
        line_values[i-1] = float(slot_pots.get(val_key, 0))
        line_yellows[i-1] = True if i == 1 else slot_pots.get(yellow_key, True)

        if i-1 < len(item_score.line_scores):
            line_dps_gains[i-1] = item_score.line_scores[i-1]

    return CubeRecommendation(
        slot=slot,
        is_bonus=is_bonus,
        tier=tier_str,
        current_dps_gain=item_score.current_dps_gain,
        best_possible_dps_gain=item_score.best_possible_dps_gain,
        dps_efficiency=item_score.dps_relative_score,
        percentile_score=item_score.total_score,
        baseline_dps=baseline_dps,  # DEBUG field
        line1_stat=line_stats[0],
        line1_value=line_values[0],
        line1_dps_gain=line_dps_gains[0],
        line1_yellow=line_yellows[0],
        line2_stat=line_stats[1],
        line2_value=line_values[1],
        line2_dps_gain=line_dps_gains[1],
        line2_yellow=line_yellows[1],
        line3_stat=line_stats[2],
        line3_value=line_values[2],
        line3_dps_gain=line_dps_gains[2],
        line3_yellow=line_yellows[2],
        expected_cubes_to_improve=expected_cubes.cubes_to_any_improvement,
        prob_improve_10_cubes=expected_cubes.prob_improve_10_cubes,
        improvement_difficulty=expected_cubes.improvement_difficulty,
        diminishing_returns_warning=expected_cubes.diminishing_returns_warning,
        current_pity=current_pity,
        pity_threshold=expected_cubes.pity_threshold,
        cubes_to_tier_up=expected_cubes.cubes_to_tier_up,
        tier_up_score_gain=expected_cubes.tier_up_score_gain,
        efficiency_score=efficiency,
        priority_rank=0,  # Will be set after sorting
        top_stats=top_stats,
        yellow_count=item_score.yellow_count,
        useful_line_count=item_score.useful_line_count,
    )


def analyze_all_cube_priorities(
    user_data,
    aggregate_stats_func: Callable[[], Dict[str, float]],
    calculate_dps_func: Callable[[Dict[str, float]], Dict[str, Any]],
    main_stat_type: StatType = StatType.DEX_PCT,
) -> List[CubeRecommendation]:
    """
    Analyze cube priority for all equipment slots.

    This is the main entry point for the cube recommendation system.

    Args:
        user_data: Streamlit UserData object
        aggregate_stats_func: Function to aggregate all stats (returns stats dict)
        calculate_dps_func: Function to calculate DPS from stats dict
        main_stat_type: Player's main stat type

    Returns:
        List of CubeRecommendation sorted by efficiency (best first)
    """
    results: List[CubeRecommendation] = []

    for slot in EQUIPMENT_SLOTS:
        slot_pots = user_data.equipment_potentials.get(slot, {})

        # Capture original potentials ONCE before any testing
        # This prevents corruption if multiple calls are made
        slot_original_pots = deepcopy(user_data.equipment_potentials.get(slot, {}))

        # Create DPS calculation functions for this slot
        # Regular potential
        def make_dps_func(slot_to_test: str, is_bonus_to_test: bool, captured_original: dict):
            """Factory to create a DPS calculation function for a specific slot/type."""
            def calc_dps_with_lines(test_lines: List[PotentialLine]) -> float:
                """Calculate DPS with the given potential lines on this slot."""
                # Clear the lines we're testing
                prefix = "bonus_" if is_bonus_to_test else ""
                test_pots = deepcopy(captured_original)
                for i in range(1, 4):
                    test_pots[f"{prefix}line{i}_stat"] = ""
                    test_pots[f"{prefix}line{i}_value"] = 0

                # Apply test lines
                for line in test_lines:
                    i = line.slot
                    stat_name = get_stat_name_from_type(line.stat_type)
                    test_pots[f"{prefix}line{i}_stat"] = stat_name
                    test_pots[f"{prefix}line{i}_value"] = line.value

                # Temporarily update user data
                user_data.equipment_potentials[slot_to_test] = test_pots

                # Calculate DPS
                try:
                    stats = aggregate_stats_func()
                    result = calculate_dps_func(stats, user_data.combat_mode)
                    new_dps = result['total']

                finally:
                    # Restore original
                    user_data.equipment_potentials[slot_to_test] = deepcopy(captured_original)

                return new_dps

            return calc_dps_with_lines

        # Calculate baseline DPS (with empty potential lines on this slot)
        def get_baseline_dps(slot_to_test: str, is_bonus_to_test: bool, captured_original: dict) -> float:
            """Calculate DPS with empty potential lines on the specified slot/type."""
            prefix = "bonus_" if is_bonus_to_test else ""
            test_pots = deepcopy(captured_original)
            for i in range(1, 4):
                test_pots[f"{prefix}line{i}_stat"] = ""
                test_pots[f"{prefix}line{i}_value"] = 0

            user_data.equipment_potentials[slot_to_test] = test_pots

            try:
                stats = aggregate_stats_func()
                result = calculate_dps_func(stats, user_data.combat_mode)
                baseline = result['total']

                # DEBUG: Store baseline for sanity check
                if not hasattr(user_data, '_cube_debug'):
                    user_data._cube_debug = {}
                key = f"{slot_to_test}_{'bonus' if is_bonus_to_test else 'reg'}"
                user_data._cube_debug[key] = {
                    'baseline': baseline,
                    'slot': slot_to_test,
                    'is_bonus': is_bonus_to_test,
                    'cleared_pots': {k: v for k, v in test_pots.items() if 'line' in k and 'stat' in k},
                }
            finally:
                user_data.equipment_potentials[slot_to_test] = deepcopy(captured_original)

            return max(baseline, 1)  # Avoid division by zero

        # Analyze REGULAR potential
        reg_dps_func = make_dps_func(slot, False, slot_original_pots)
        reg_baseline = get_baseline_dps(slot, False, slot_original_pots)

        reg_result = analyze_slot_potentials(
            slot=slot,
            slot_pots=slot_pots,
            is_bonus=False,
            dps_calc_func=reg_dps_func,
            baseline_dps=reg_baseline,
            main_stat_type=main_stat_type,
        )
        if reg_result:
            results.append(reg_result)

        # Analyze BONUS potential
        bon_dps_func = make_dps_func(slot, True, slot_original_pots)
        bon_baseline = get_baseline_dps(slot, True, slot_original_pots)

        bon_result = analyze_slot_potentials(
            slot=slot,
            slot_pots=slot_pots,
            is_bonus=True,
            dps_calc_func=bon_dps_func,
            baseline_dps=bon_baseline,
            main_stat_type=main_stat_type,
        )
        if bon_result:
            results.append(bon_result)

    # Sort by efficiency score (higher = better to cube)
    results.sort(key=lambda x: x.efficiency_score, reverse=True)

    # Assign priority ranks
    for i, r in enumerate(results):
        r.priority_rank = i + 1

    return results


def get_stat_name_from_type(stat_type: StatType) -> str:
    """Convert StatType enum to Streamlit stat name string."""
    for name, stype in STAT_NAME_TO_TYPE.items():
        if stype == stat_type:
            return name
    return ""


def format_stat_display(stat_name: str) -> str:
    """Format stat name for display."""
    DISPLAY_NAMES = {
        "dex_pct": "DEX%", "str_pct": "STR%", "int_pct": "INT%", "luk_pct": "LUK%",
        "dex_flat": "DEX", "str_flat": "STR", "int_flat": "INT", "luk_flat": "LUK",
        "damage": "DMG%", "crit_rate": "CR%", "crit_damage": "CD%", "def_pen": "DP%",
        "final_damage": "FD%", "all_skills": "AS", "min_dmg_mult": "MinD%", "max_dmg_mult": "MaxD%",
        "attack_speed": "AS%", "defense": "DEF%", "max_hp": "HP%", "max_mp": "MP%",
        "skill_cd": "CDR", "buff_duration": "Buff%", "stat_per_level": "S/Lv", "ba_targets": "BA+",
    }
    return DISPLAY_NAMES.get(stat_name, stat_name.upper())


# =============================================================================
# TIER UPGRADE CALCULATIONS
# =============================================================================

# Tier-up probabilities (from cubes.py)
TIER_UP_RATES = {
    "Rare": 0.06,        # → Epic (6%)
    "Epic": 0.03333,     # → Unique (3.33%)
    "Unique": 0.006,     # → Legendary (0.6%)
    "Legendary": 0.0021, # → Mystic (0.21%)
    "Mystic": 0.0,       # Can't tier up
}

# Pity thresholds
REGULAR_PITY_THRESHOLDS = {
    "Rare": 33, "Epic": 60, "Unique": 150,
    "Legendary": 333, "Mystic": 714,
}

BONUS_PITY_THRESHOLDS = {
    "Rare": 45, "Epic": 85, "Unique": 150,
    "Legendary": 417, "Mystic": 714,
}

TIER_ORDER = ["Rare", "Epic", "Unique", "Legendary", "Mystic"]


def get_next_tier(current_tier: str) -> Optional[str]:
    """Get the next tier up from current tier."""
    try:
        idx = TIER_ORDER.index(current_tier)
        if idx < len(TIER_ORDER) - 1:
            return TIER_ORDER[idx + 1]
    except ValueError:
        pass
    return None


def calculate_expected_cubes_to_tier_up(
    current_tier: str,
    current_pity: int,
    is_bonus: bool
) -> float:
    """
    Calculate expected cubes to tier up, accounting for current pity progress.

    Uses truncated geometric distribution formula.
    """
    next_tier = get_next_tier(current_tier)
    if not next_tier:
        return float('inf')  # Already at max tier

    p = TIER_UP_RATES.get(current_tier, 0)
    if p <= 0:
        return float('inf')

    pity_thresholds = BONUS_PITY_THRESHOLDS if is_bonus else REGULAR_PITY_THRESHOLDS
    pity_max = pity_thresholds.get(next_tier, 714)
    remaining_to_pity = max(1, pity_max - current_pity)

    # Truncated geometric: E[X] = (1 - (1-p)^n) / p
    # where n = remaining rolls until pity
    expected = (1 - (1 - p) ** remaining_to_pity) / p

    return min(expected, remaining_to_pity)  # Can't exceed pity


# =============================================================================
# OPTIMAL STOPPING CALCULATIONS
# =============================================================================

def calculate_optimal_stopping_at_tier(
    dps_values: List[float],
    probabilities: List[float],
    cube_cost_dps: float,
    next_tier_expected_value: Optional[float] = None,
    tier_up_prob: float = 0.0,
) -> tuple:
    """
    Calculate optimal stopping threshold and expected value for a tier.

    Uses backward induction / value iteration to solve the Bellman equation:
    V(d) = max(d, -cost + p_tierup * E[V_next] + (1-p_tierup) * E[V(d')])

    Args:
        dps_values: List of possible DPS gain values (sorted)
        probabilities: Probability of each DPS value
        cube_cost_dps: Cost per cube in DPS% units
        next_tier_expected_value: E[V] at next tier (None for Mystic)
        tier_up_prob: Probability of tier-up per cube

    Returns:
        (keep_threshold, expected_value, expected_cubes_to_threshold)
    """
    if len(dps_values) != len(probabilities):
        raise ValueError("dps_values and probabilities must have same length")

    n = len(dps_values)
    if n == 0:
        return (0.0, 0.0, 0.0)

    # Sort by DPS value
    sorted_pairs = sorted(zip(dps_values, probabilities), key=lambda x: x[0])
    sorted_dps = [p[0] for p in sorted_pairs]
    sorted_probs = [p[1] for p in sorted_pairs]

    # For Mystic (no tier-up possible), solve classic optimal stopping
    if next_tier_expected_value is None or tier_up_prob <= 0:
        return _solve_optimal_stopping_no_tierup(sorted_dps, sorted_probs, cube_cost_dps)

    # For other tiers, solve with tier-up possibility
    return _solve_optimal_stopping_with_tierup(
        sorted_dps, sorted_probs, cube_cost_dps,
        next_tier_expected_value, tier_up_prob
    )


def _solve_optimal_stopping_no_tierup(
    sorted_dps: List[float],
    sorted_probs: List[float],
    cube_cost_dps: float,
) -> tuple:
    """
    Solve optimal stopping for Mystic tier (no tier-up possible).

    At Mystic, the optimal strategy is to keep rolling until you get a roll
    above some threshold T where:
        T = E[d | d >= T] - cost / P(d >= T)

    This is solved by finding T where continuing has zero expected gain.
    """
    n = len(sorted_dps)

    # Binary search for threshold
    # At threshold T: E[continue] = E[keep]
    # E[continue] = -cost + E[max(new_roll, optimal_value)]
    # E[keep at T] = T

    # Simpler approach: iterate from high to low, find where E[continue] = d
    # E[continue from d] = -cost + sum over d' of P(d') * max(d', threshold)

    best_threshold = sorted_dps[-1]  # Start with highest value
    best_ev = sorted_dps[-1]

    # Try each possible threshold (keeping if >= threshold)
    for i in range(n - 1, -1, -1):
        threshold = sorted_dps[i]

        # If we use threshold T:
        # P(keep) = P(d >= T) = sum of probs for d >= T
        # E[d | keep] = sum of (d * prob) for d >= T / P(keep)
        # E[cubes] = 1 / P(keep)
        # E[value] = E[d | keep] - E[cubes] * cost

        p_keep = sum(sorted_probs[i:])
        if p_keep <= 0:
            continue

        e_d_given_keep = sum(d * p for d, p in zip(sorted_dps[i:], sorted_probs[i:])) / p_keep
        e_cubes = 1.0 / p_keep
        e_value = e_d_given_keep - e_cubes * cube_cost_dps

        if e_value > best_ev:
            best_ev = e_value
            best_threshold = threshold

    # Calculate expected cubes to reach threshold
    p_above_threshold = sum(p for d, p in zip(sorted_dps, sorted_probs) if d >= best_threshold)
    e_cubes = 1.0 / p_above_threshold if p_above_threshold > 0 else float('inf')

    return (best_threshold, best_ev, e_cubes)


def _solve_optimal_stopping_with_tierup(
    sorted_dps: List[float],
    sorted_probs: List[float],
    cube_cost_dps: float,
    next_tier_ev: float,
    tier_up_prob: float,
) -> tuple:
    """
    Solve optimal stopping with tier-up possibility using value iteration.

    The Bellman equation is:
    V(d) = max(d, -cost + p * V_next + (1-p) * E[V(d')])

    where E[V(d')] = sum over d' of P(d') * V(d')

    This is a fixed-point equation. We iterate until convergence.
    """
    n = len(sorted_dps)

    # Initialize V(d) = d for all d (keeping is baseline)
    V = {d: d for d in sorted_dps}

    # Value iteration
    max_iterations = 100
    tolerance = 0.0001

    for iteration in range(max_iterations):
        # E[V(new_roll)] = sum of P(d') * V(d')
        e_v_new_roll = sum(p * V[d] for d, p in zip(sorted_dps, sorted_probs))

        # Expected value of using a cube
        e_cube = -cube_cost_dps + tier_up_prob * next_tier_ev + (1 - tier_up_prob) * e_v_new_roll

        # Update V(d) = max(d, e_cube)
        new_V = {}
        max_change = 0.0
        for d in sorted_dps:
            new_val = max(d, e_cube)
            max_change = max(max_change, abs(new_val - V[d]))
            new_V[d] = new_val

        V = new_V

        if max_change < tolerance:
            break

    # Find threshold: lowest d where V(d) = d (keeping is optimal)
    threshold = sorted_dps[0]
    for d in sorted_dps:
        if V[d] <= d + tolerance:  # Keeping is optimal
            threshold = d
            break

    # Expected value = E[V(d)] over distribution (starting fresh)
    expected_value = sum(p * V[d] for d, p in zip(sorted_dps, sorted_probs))

    # Expected cubes to reach threshold or tier-up
    # This is complex - approximate with geometric
    p_keep = sum(p for d, p in zip(sorted_dps, sorted_probs) if d >= threshold)
    p_stop = p_keep + tier_up_prob * (1 - p_keep)  # Stop if keep OR tier-up
    e_cubes = 1.0 / p_stop if p_stop > 0 else float('inf')

    return (threshold, expected_value, e_cubes)


def calculate_optimal_values_all_tiers(
    slot: str,
    is_bonus: bool,
    dps_calc_func: Callable[[List[PotentialLine]], float],
    baseline_dps: float,
    main_stat_type: StatType = StatType.DEX_PCT,
) -> Dict[str, Dict[str, float]]:
    """
    Calculate optimal stopping values for all tiers using backward induction.

    Returns dict with:
        {tier: {"threshold": float, "expected_value": float, "expected_cubes": float}}
    """
    cube_cost = BONUS_DIAMOND_PER_CUBE if is_bonus else REGULAR_DIAMOND_PER_CUBE
    # Convert cube cost to DPS% units (relative to baseline)
    # If baseline is 1M DPS and cube costs 1000 diamonds, we need a common unit
    # For simplicity, we'll work in DPS% and treat cost as a small constant
    # The actual value depends on how much DPS% a diamond is "worth"
    # Approximation: 1 diamond ≈ 0.0001% DPS (very rough)
    cube_cost_dps = cube_cost * 0.0001  # Tune this based on game economy

    results = {}

    # Work backwards from Mystic
    tiers_reversed = ["Mystic", "Legendary", "Unique", "Epic", "Rare"]
    next_tier_ev = None

    for tier_str in tiers_reversed:
        tier_enum = get_tier_enum(tier_str)

        # Get DPS distribution for this tier
        try:
            dist = get_exact_roll_distribution(
                tier_enum, slot, dps_calc_func, baseline_dps, main_stat_type
            )

            # Get the EXACT DPS values and probabilities from combinatorial enumeration
            # This is the true distribution with proper probability weights
            dps_values, probabilities = dist.get_exact_dps_distribution()

        except Exception:
            # Fallback: use simple distribution
            mean_dps = 2.0 if tier_str == "Mystic" else 1.0  # Rough estimates
            dps_values = [mean_dps * 0.5, mean_dps * 0.75, mean_dps, mean_dps * 1.25, mean_dps * 1.5]
            probabilities = [0.1, 0.2, 0.4, 0.2, 0.1]

        # Get tier-up probability
        tier_up_prob = TIER_UP_RATES.get(tier_str, 0.0)

        # Solve optimal stopping for this tier
        threshold, ev, e_cubes = calculate_optimal_stopping_at_tier(
            dps_values, probabilities, cube_cost_dps,
            next_tier_ev, tier_up_prob
        )

        results[tier_str] = {
            "threshold": threshold,
            "expected_value": ev,
            "expected_cubes": e_cubes,
        }

        # This tier's expected value becomes next tier's reference
        next_tier_ev = ev

    return results


@dataclass
class TierUpgradeRecommendation:
    """Recommendation for upgrading potential tier using optimal stopping."""
    slot: str
    is_bonus: bool
    current_tier: str

    # Current roll info
    current_dps_gain: float      # DPS % from current roll
    current_percentile: float    # Percentile of current roll (0-100)

    # Optimal stopping values
    keep_threshold: float        # DPS % threshold - optimal stopping point
    expected_value_at_tier: float  # Expected DPS % with optimal play at this tier

    # Value comparison
    value_vs_threshold: float    # current_dps_gain - keep_threshold (positive = above threshold)
    value_vs_expected: float     # current_dps_gain - expected_value_at_tier

    # Expected gains from cubing
    expected_dps_gain: float     # expected_value_at_tier - current_dps_gain

    # Path to Mystic info (for context)
    path_tiers: List[str]        # e.g., ["Unique", "Legendary", "Mystic"]
    expected_values_by_tier: Dict[str, float]  # Expected value at each tier

    # Cost estimates
    expected_cubes_to_threshold: float  # Expected cubes to reach keep threshold
    total_cost_diamonds: float          # Expected diamond cost

    # Efficiency (DPS gain per cost) - this is the key metric!
    # Low efficiency = don't cube (great roll or high cost)
    # High efficiency = cube (poor roll relative to expected value)
    efficiency: float            # DPS gain per 1000 diamonds

    # Pity info
    current_pity: int
    pity_threshold: int


def calculate_tier_upgrade_value(
    slot: str,
    slot_pots: Dict[str, Any],
    is_bonus: bool,
    dps_calc_func: Callable[[List[PotentialLine]], float],
    baseline_dps: float,
    main_stat_type: StatType = StatType.DEX_PCT,
) -> Optional[TierUpgradeRecommendation]:
    """
    Calculate the value of cubing using optimal stopping theory.

    Uses backward induction from Mystic to determine:
    1. Keep threshold: DPS value above which you should NOT cube
    2. Expected value: Expected DPS with optimal play
    3. Whether current roll should be cubed or kept

    Args:
        slot: Equipment slot name
        slot_pots: Potential data for this slot
        is_bonus: True for bonus potential
        dps_calc_func: Function to calculate DPS with given lines
        baseline_dps: DPS with empty lines on this slot
        main_stat_type: Player's main stat

    Returns:
        TierUpgradeRecommendation or None if no data
    """
    prefix = "bonus_" if is_bonus else ""
    tier_key = f"{prefix}tier" if is_bonus else "tier"
    pity_key = f"{prefix}pity" if is_bonus else "regular_pity"

    current_tier_str = slot_pots.get(tier_key, "Legendary")
    current_pity = int(slot_pots.get(pity_key, 0))
    current_tier = get_tier_enum(current_tier_str)

    # Get current roll's DPS
    current_lines = convert_streamlit_lines_to_potential_lines(slot_pots, is_bonus)
    if current_lines:
        current_dps = dps_calc_func(current_lines)
        current_dps_gain = ((current_dps / baseline_dps) - 1) * 100 if baseline_dps > 0 else 0
    else:
        current_dps_gain = 0.0

    # Get current roll's percentile at CURRENT tier
    try:
        current_tier_dist = get_exact_roll_distribution(
            current_tier, slot, dps_calc_func, baseline_dps, main_stat_type
        )
        current_percentile = current_tier_dist.get_percentile_of_dps_gain(current_dps_gain)
    except Exception:
        current_percentile = 50.0  # Fallback

    # Calculate optimal stopping values for all tiers
    optimal_values = calculate_optimal_values_all_tiers(
        slot, is_bonus, dps_calc_func, baseline_dps, main_stat_type
    )

    # Get values for current tier
    tier_data = optimal_values.get(current_tier_str, {})
    keep_threshold = tier_data.get("threshold", 0.0)
    expected_value_at_tier = tier_data.get("expected_value", 0.0)

    # Calculate value comparisons
    value_vs_threshold = current_dps_gain - keep_threshold
    value_vs_expected = current_dps_gain - expected_value_at_tier

    # Calculate expected cubes and DPS gain considering BOTH:
    # 1. Better rolls at current tier
    # 2. Tier-up to next tier (with better expected value there)
    try:
        current_tier_dist = get_exact_roll_distribution(
            current_tier, slot, dps_calc_func, baseline_dps, main_stat_type
        )
        dps_values, probabilities = current_tier_dist.get_exact_dps_distribution()

        # P(roll > current at current tier)
        p_better_same_tier = sum(p for d, p in zip(dps_values, probabilities) if d > current_dps_gain)

        # Average DPS of better rolls at current tier
        if p_better_same_tier > 0:
            avg_better_same_tier = sum(d * p for d, p in zip(dps_values, probabilities) if d > current_dps_gain) / p_better_same_tier
        else:
            avg_better_same_tier = current_dps_gain

        # For non-Mystic tiers, also consider tier-up value
        tier_up_prob = TIER_UP_RATES.get(current_tier_str, 0.0)
        next_tier_str = get_next_tier(current_tier_str)

        if tier_up_prob > 0 and next_tier_str:
            # Get next tier distribution to calculate P(better at next tier)
            next_tier_enum = get_tier_enum(next_tier_str)
            next_tier_dist = get_exact_roll_distribution(
                next_tier_enum, slot, dps_calc_func, baseline_dps, main_stat_type
            )
            next_dps_values, next_probs = next_tier_dist.get_exact_dps_distribution()

            # P(better at next tier) - comparing against CURRENT dps, not next tier average
            p_better_next_tier = sum(p for d, p in zip(next_dps_values, next_probs) if d > current_dps_gain)
            if p_better_next_tier > 0:
                avg_better_next_tier = sum(d * p for d, p in zip(next_dps_values, next_probs) if d > current_dps_gain) / p_better_next_tier
            else:
                avg_better_next_tier = current_dps_gain

            # Combined P(improvement) per cube:
            # Either stay at current tier and beat current, OR tier up and beat current
            p_improve = (1 - tier_up_prob) * p_better_same_tier + tier_up_prob * p_better_next_tier

            if p_improve > 0:
                # Expected cubes to improve (geometric distribution)
                expected_cubes = 1.0 / p_improve

                # Weighted average DPS gain when we do improve
                weight_current = (1 - tier_up_prob) * p_better_same_tier / p_improve
                weight_next = tier_up_prob * p_better_next_tier / p_improve

                expected_dps_gain = (
                    weight_current * (avg_better_same_tier - current_dps_gain) +
                    weight_next * (avg_better_next_tier - current_dps_gain)
                )
            else:
                # Best possible roll - no improvement possible at either tier
                expected_cubes = float('inf')
                expected_dps_gain = 0.0
        else:
            # Mystic tier - can only get better rolls at same tier
            if p_better_same_tier > 0:
                expected_cubes = 1.0 / p_better_same_tier
                expected_dps_gain = avg_better_same_tier - current_dps_gain
            else:
                # Best possible roll at Mystic!
                expected_cubes = float('inf')
                expected_dps_gain = 0.0

    except Exception:
        # Fallback to threshold-based estimate
        expected_cubes = tier_data.get("expected_cubes", 10.0)
        expected_dps_gain = expected_value_at_tier - current_dps_gain

    # Build path info
    path_tiers = [current_tier_str]
    tier = current_tier_str
    while tier != "Mystic":
        next_tier = get_next_tier(tier)
        if not next_tier:
            break
        path_tiers.append(next_tier)
        tier = next_tier

    # Expected values by tier (from optimal stopping)
    expected_values_by_tier = {
        tier: optimal_values.get(tier, {}).get("expected_value", 0.0)
        for tier in path_tiers
    }

    # Cost calculation
    diamond_cost = BONUS_DIAMOND_PER_CUBE if is_bonus else REGULAR_DIAMOND_PER_CUBE
    total_cost = expected_cubes * diamond_cost

    # Efficiency (only meaningful if cubing)
    if total_cost > 0 and expected_dps_gain > 0:
        efficiency = expected_dps_gain / (total_cost / 1000)
    else:
        efficiency = 0.0

    # Pity info
    pity_thresholds = BONUS_PITY_THRESHOLDS if is_bonus else REGULAR_PITY_THRESHOLDS
    next_tier = get_next_tier(current_tier_str)
    pity_threshold = pity_thresholds.get(next_tier, 714) if next_tier else 714

    return TierUpgradeRecommendation(
        slot=slot,
        is_bonus=is_bonus,
        current_tier=current_tier_str,
        current_dps_gain=current_dps_gain,
        current_percentile=current_percentile,
        keep_threshold=keep_threshold,
        expected_value_at_tier=expected_value_at_tier,
        value_vs_threshold=value_vs_threshold,
        value_vs_expected=value_vs_expected,
        expected_dps_gain=expected_dps_gain,
        path_tiers=path_tiers,
        expected_values_by_tier=expected_values_by_tier,
        expected_cubes_to_threshold=expected_cubes,
        total_cost_diamonds=total_cost,
        efficiency=efficiency,
        current_pity=current_pity,
        pity_threshold=pity_threshold,
    )


def analyze_all_tier_upgrades(
    user_data,
    aggregate_stats_func: Callable[[], Dict[str, float]],
    calculate_dps_func: Callable[[Dict[str, float]], Dict[str, Any]],
    main_stat_type: StatType = StatType.DEX_PCT,
) -> List[TierUpgradeRecommendation]:
    """
    Analyze tier upgrade value for all equipment slots.

    Returns list of recommendations sorted by efficiency (best first).
    """
    # Clear distribution cache at start of analysis
    # This ensures fresh calculations when equipment changes, while still
    # benefiting from cache reuse within this analysis run
    clear_exact_distribution_cache()

    results: List[TierUpgradeRecommendation] = []

    for slot in EQUIPMENT_SLOTS:
        slot_pots = user_data.equipment_potentials.get(slot, {})

        # Capture original potentials ONCE before any testing
        # This prevents corruption if multiple calls are made
        slot_original_pots = deepcopy(user_data.equipment_potentials.get(slot, {}))

        # Create DPS calc function for this slot
        def make_dps_func(slot_to_test: str, is_bonus_to_test: bool, captured_original: dict):
            def calc_dps_with_lines(test_lines: List[PotentialLine]) -> float:
                prefix = "bonus_" if is_bonus_to_test else ""
                test_pots = deepcopy(captured_original)
                for i in range(1, 4):
                    test_pots[f"{prefix}line{i}_stat"] = ""
                    test_pots[f"{prefix}line{i}_value"] = 0

                for line in test_lines:
                    i = line.slot
                    stat_name = get_stat_name_from_type(line.stat_type)
                    test_pots[f"{prefix}line{i}_stat"] = stat_name
                    test_pots[f"{prefix}line{i}_value"] = line.value

                user_data.equipment_potentials[slot_to_test] = test_pots

                try:
                    stats = aggregate_stats_func()
                    result = calculate_dps_func(stats, user_data.combat_mode)
                    new_dps = result['total']
                finally:
                    user_data.equipment_potentials[slot_to_test] = deepcopy(captured_original)

                return new_dps

            return calc_dps_with_lines

        def get_baseline_dps(slot_to_test: str, is_bonus_to_test: bool, captured_original: dict) -> float:
            prefix = "bonus_" if is_bonus_to_test else ""
            test_pots = deepcopy(captured_original)
            for i in range(1, 4):
                test_pots[f"{prefix}line{i}_stat"] = ""
                test_pots[f"{prefix}line{i}_value"] = 0

            user_data.equipment_potentials[slot_to_test] = test_pots

            try:
                stats = aggregate_stats_func()
                result = calculate_dps_func(stats, user_data.combat_mode)
                baseline = result['total']
            finally:
                user_data.equipment_potentials[slot_to_test] = deepcopy(captured_original)

            return max(baseline, 1)

        # Analyze REGULAR potential tier upgrade
        reg_dps_func = make_dps_func(slot, False, slot_original_pots)
        reg_baseline = get_baseline_dps(slot, False, slot_original_pots)

        reg_result = calculate_tier_upgrade_value(
            slot=slot,
            slot_pots=slot_pots,
            is_bonus=False,
            dps_calc_func=reg_dps_func,
            baseline_dps=reg_baseline,
            main_stat_type=main_stat_type,
        )
        if reg_result:
            results.append(reg_result)

        # Analyze BONUS potential tier upgrade
        bon_dps_func = make_dps_func(slot, True, slot_original_pots)
        bon_baseline = get_baseline_dps(slot, True, slot_original_pots)

        bon_result = calculate_tier_upgrade_value(
            slot=slot,
            slot_pots=slot_pots,
            is_bonus=True,
            dps_calc_func=bon_dps_func,
            baseline_dps=bon_baseline,
            main_stat_type=main_stat_type,
        )
        if bon_result:
            results.append(bon_result)

    # Sort by efficiency (higher = better to cube)
    # Items with negative efficiency (great rolls) will naturally sort lower
    results.sort(key=lambda x: x.efficiency, reverse=True)

    return results


def get_distribution_data_for_slot(
    user_data,
    slot: str,
    is_bonus: bool,
    aggregate_stats_func: Callable[[], Dict[str, float]],
    calculate_dps_func: Callable[[Dict[str, float]], Dict[str, Any]],
    main_stat_type: StatType = StatType.DEX_PCT,
    use_exact: bool = True,
) -> Optional[Dict]:
    """
    Get distribution data for a specific equipment slot's potential.

    This uses either the ExactRollDistribution (combinatorial, exact probabilities)
    or CachedRollDistribution (Monte Carlo sampling) to create data suitable
    for a Plotly distribution chart.

    Args:
        user_data: Streamlit UserData object
        slot: Equipment slot name (e.g., "hat", "gloves")
        is_bonus: True for bonus potential, False for regular
        aggregate_stats_func: Function to aggregate all stats
        calculate_dps_func: Function to calculate DPS from stats dict
        main_stat_type: Player's main stat type
        use_exact: If True (default), use exact probability calculation.
                   If False, use Monte Carlo sampling.

    Returns:
        Dict with distribution data or None if no data available:
        - percentiles: List[int] (0-100)
        - dps_gains: List[float] (DPS % at each percentile)
        - lines_text: List[str] (formatted lines text for hover)
        - median_dps_gain: float (median DPS gain)
        - current_dps_gain: float (current roll's DPS gain)
        - is_exact: bool (True if using exact probabilities)
    """
    slot_pots = user_data.equipment_potentials.get(slot, {})

    # Get tier
    tier_key = "bonus_tier" if is_bonus else "tier"
    tier_str = slot_pots.get(tier_key, "Legendary")
    tier = get_tier_enum(tier_str)

    # Check if tier has stats
    tier_stats = POTENTIAL_STATS.get(tier, [])
    if not tier_stats:
        return None

    # Capture original potentials ONCE before any testing
    # This prevents corruption if multiple calls are made
    slot_original_pots = deepcopy(user_data.equipment_potentials.get(slot, {}))

    # Create DPS calculation function for this slot/type
    def calc_dps_with_lines(test_lines: List[PotentialLine]) -> float:
        """Calculate DPS with the given potential lines on this slot."""
        prefix = "bonus_" if is_bonus else ""
        test_pots = deepcopy(slot_original_pots)

        # Clear the lines
        for i in range(1, 4):
            test_pots[f"{prefix}line{i}_stat"] = ""
            test_pots[f"{prefix}line{i}_value"] = 0

        # Apply test lines
        for line in test_lines:
            i = line.slot
            stat_name = get_stat_name_from_type(line.stat_type)
            test_pots[f"{prefix}line{i}_stat"] = stat_name
            test_pots[f"{prefix}line{i}_value"] = line.value

        # Temporarily update user data
        user_data.equipment_potentials[slot] = test_pots

        try:
            stats = aggregate_stats_func()
            result = calculate_dps_func(stats, user_data.combat_mode)
            new_dps = result['total']
        finally:
            user_data.equipment_potentials[slot] = deepcopy(slot_original_pots)

        return new_dps

    # Get baseline DPS (with empty potential lines)
    def get_baseline_dps() -> float:
        prefix = "bonus_" if is_bonus else ""
        test_pots = deepcopy(slot_original_pots)
        for i in range(1, 4):
            test_pots[f"{prefix}line{i}_stat"] = ""
            test_pots[f"{prefix}line{i}_value"] = 0

        user_data.equipment_potentials[slot] = test_pots

        try:
            stats = aggregate_stats_func()
            result = calculate_dps_func(stats, user_data.combat_mode)
            baseline = result['total']
        finally:
            user_data.equipment_potentials[slot] = deepcopy(slot_original_pots)

        return max(baseline, 1)

    baseline_dps = get_baseline_dps()

    if use_exact:
        # Use exact probability distribution (combinatorial enumeration)
        exact_dist = get_exact_roll_distribution(
            tier, slot, calc_dps_with_lines, baseline_dps, main_stat_type
        )

        # Get distribution data for chart with high-resolution tail
        dist_data = exact_dist.get_distribution_data_for_chart(num_points=101, high_res_tail=True)

        # Get current roll's DPS gain
        current_lines = convert_streamlit_lines_to_potential_lines(slot_pots, is_bonus)
        if current_lines:
            current_dps = calc_dps_with_lines(current_lines)
            current_dps_gain = ((current_dps / baseline_dps) - 1) * 100 if baseline_dps > 0 else 0
        else:
            current_dps_gain = 0.0

        # Get median from exact stats
        stats = exact_dist.get_dps_distribution_stats()
        dist_data["current_dps_gain"] = current_dps_gain
        dist_data["median_dps_gain"] = stats["median"]
        dist_data["is_exact"] = True
        dist_data["total_combinations"] = exact_dist.get_total_combinations()
        dist_data["total_arrangements"] = exact_dist.get_total_arrangements()
    else:
        # Use Monte Carlo sampling (legacy method)
        cache = get_cached_roll_distribution(tier, n_rolls=3000)

        # Score the rolls for this slot
        cache.score_rolls_for_slot(slot, calc_dps_with_lines, baseline_dps, main_stat_type)

        # Get distribution data for chart
        dist_data = cache.get_distribution_data_for_chart(num_points=101)

        # Get current roll's DPS gain
        current_lines = convert_streamlit_lines_to_potential_lines(slot_pots, is_bonus)
        current_item_score = create_item_score_result(
            current_lines, tier, slot, calc_dps_with_lines, baseline_dps, main_stat_type, cache
        )

        # Add current DPS gain to the return data
        dist_data["current_dps_gain"] = current_item_score.current_dps_gain
        dist_data["median_dps_gain"] = dist_data["dps_gains"][50] if len(dist_data["dps_gains"]) > 50 else 0
        dist_data["is_exact"] = False

    return dist_data
