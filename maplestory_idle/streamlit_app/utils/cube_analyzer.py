"""
Cube Analyzer - Bridge between Streamlit data and cubes.py analysis functions.

Provides cube priority recommendations using the original DPS calculation methods.
"""
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

# Import from the cubes module in streamlit_app
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from cubes import (
    PotentialLine, PotentialTier, StatType, CubeType,
    create_item_score_result, calculate_expected_cubes_fast,
    calculate_efficiency_score, calculate_stat_rankings,
    ItemScoreResult, ExpectedCubesMetrics, EnhancedCubeRecommendation,
    POTENTIAL_STATS, get_stat_display_name
)

# Equipment slots
EQUIPMENT_SLOTS = [
    "hat", "top", "bottom", "gloves", "shoes",
    "belt", "shoulder", "cape", "ring", "necklace", "face"
]

# Cost per cube in diamonds
REGULAR_DIAMOND_PER_CUBE = 600
BONUS_DIAMOND_PER_CUBE = 1200

# Mapping from Streamlit stat names to StatType enum
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
    "crit_rate": StatType.CRIT_RATE,
    "crit_damage": StatType.CRIT_DAMAGE,
    "def_pen": StatType.DEF_PEN,
    "final_damage": StatType.FINAL_ATK_DMG,
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

    # Calculate efficiency score
    diamond_cost = BONUS_DIAMOND_PER_CUBE if is_bonus else REGULAR_DIAMOND_PER_CUBE
    efficiency = calculate_efficiency_score(
        current_score=item_score.dps_relative_score,
        tier=tier,
        expected_cubes_to_improve=expected_cubes.cubes_to_any_improvement,
        diamond_cost_per_cube=diamond_cost,
        tier_up_efficiency_bonus=expected_cubes.tier_up_efficiency_bonus,
    )

    # Get top stats by DPS gain
    top_stats = calculate_stat_rankings(
        slot=slot,
        tier=tier,
        dps_calc_func=dps_calc_func,
        current_dps=baseline_dps,
        main_stat_type=main_stat_type,
        top_n=5
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

        # Create DPS calculation functions for this slot
        # Regular potential
        def make_dps_func(slot_to_test: str, is_bonus_to_test: bool):
            """Factory to create a DPS calculation function for a specific slot/type."""
            def calc_dps_with_lines(test_lines: List[PotentialLine]) -> float:
                """Calculate DPS with the given potential lines on this slot."""
                # Save current lines
                original_pots = user_data.equipment_potentials.get(slot_to_test, {}).copy()

                # Clear the lines we're testing
                prefix = "bonus_" if is_bonus_to_test else ""
                test_pots = original_pots.copy()
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
                    user_data.equipment_potentials[slot_to_test] = original_pots

                return new_dps

            return calc_dps_with_lines

        # Calculate baseline DPS (with empty potential lines on this slot)
        def get_baseline_dps(slot_to_test: str, is_bonus_to_test: bool) -> float:
            """Calculate DPS with empty potential lines on the specified slot/type."""
            original_pots = user_data.equipment_potentials.get(slot_to_test, {}).copy()

            prefix = "bonus_" if is_bonus_to_test else ""
            test_pots = original_pots.copy()
            for i in range(1, 4):
                test_pots[f"{prefix}line{i}_stat"] = ""
                test_pots[f"{prefix}line{i}_value"] = 0

            user_data.equipment_potentials[slot_to_test] = test_pots

            try:
                stats = aggregate_stats_func()
                result = calculate_dps_func(stats, user_data.combat_mode)
                baseline = result['total']
            finally:
                user_data.equipment_potentials[slot_to_test] = original_pots

            return max(baseline, 1)  # Avoid division by zero

        # Analyze REGULAR potential
        reg_dps_func = make_dps_func(slot, False)
        reg_baseline = get_baseline_dps(slot, False)

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
        bon_dps_func = make_dps_func(slot, True)
        bon_baseline = get_baseline_dps(slot, True)

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
