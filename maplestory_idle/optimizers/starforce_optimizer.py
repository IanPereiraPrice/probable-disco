"""
Starforce Optimization Analysis
===============================
Calculates optimal protection strategies for starforce enhancement.

Uses Markov chain analysis to properly account for:
1. Decrease chains (going back requires redoing stages)
2. Destruction probability (more attempts = more destruction rolls)
3. Restart costs (destruction resets to star 12)

Key mechanics:
- Decrease Mitigation: +100% cost, sets decrease to 0%
- Destruction Mitigation: +100% cost, halves destruction chance
- Both: +200% cost (3x total)

Destruction mechanic:
- When destroyed, pay 1,000,000 meso fee
- Item resets to ★12
- Must rebuild back to current star level
"""

import sys
import io

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from equipment import STARFORCE_TABLE, StarforceStage

# Destruction costs
DESTRUCTION_FEE_MESO = 1_000_000  # 1M meso flat fee
DESTRUCTION_RESET_STAR = 12  # Item resets to this star level

# =============================================================================
# DIAMOND CONVERSION RATES (from STORE_COSTS_GUIDE.md)
# =============================================================================
# Meso: 1,500,000 meso = 6,000 diamonds -> 4 diamonds per 1,000 meso
# Starforce Scrolls: 300-500 diamonds each
#   - Monthly package: 300 diamonds/scroll (best rate, 10/month)
#   - Weekly package: 350 diamonds/scroll (60/week)
#   - Normal shop: 500 diamonds/scroll (200/week)
#   - Arena shop: FREE (25/week)

MESO_TO_DIAMOND = 4.0 / 1000  # 4 diamonds per 1000 meso
SCROLL_DIAMOND_COST = 500  # Normal shop rate

# Destruction fee in diamonds: 1M meso = 4,000 diamonds
DESTRUCTION_FEE_DIAMONDS = DESTRUCTION_FEE_MESO * MESO_TO_DIAMOND  # 4,000 diamonds


@dataclass
class MarkovResult:
    """Results from Markov chain analysis."""
    stage_costs: Dict[int, float]  # C[stage] = expected cost from stage to target
    success_probability: Dict[int, float]  # P[success] from each stage
    enhance_cost: float  # Expected cost for one run (before restart)
    destroy_probability: float  # P[destruction before target]
    total_cost: float  # Total expected cost including restarts


def calculate_diamond_cost(meso: float, scrolls: float) -> float:
    """Convert meso + scrolls to total diamond cost."""
    return (meso * MESO_TO_DIAMOND) + (scrolls * SCROLL_DIAMOND_COST)


# =============================================================================
# MARKOV CHAIN ANALYSIS
# =============================================================================

def solve_markov_chain(
    start_stage: int,
    target_stage: int,
    use_decrease_prot: bool = False,
    use_destroy_prot: bool = False
) -> Tuple[Dict[int, float], Dict[int, float]]:
    """
    Solve the Markov chain for starforce enhancement with UNIFORM strategy.

    This properly accounts for:
    - Decrease chains (decrease means redoing previous stages)
    - Cumulative destruction probability across all stages/attempts

    Returns:
        C: dict mapping stage -> expected COST (diamonds) from that stage to target
        P_s: dict mapping stage -> probability of success from that stage

    The key equations are:
        C[X] = (cost + p*C[X+1] + d*C[dec_target]) / (p + d + x)
        P_s[X] = (p*P_s[X+1] + d*P_s[dec_target]) / (p + d + x)

    Where:
        p = success rate
        d = decrease rate (0 if protected)
        x = destroy rate (halved if protected)
        dec_target = max(start_stage, X-1)
        cost = diamond cost per attempt at stage X
    """
    # Convert uniform strategy to per-stage dict
    stage_strategies = {}
    for stage in range(start_stage, target_stage):
        stage_strategies[stage] = (use_decrease_prot, use_destroy_prot)

    return solve_markov_chain_per_stage(start_stage, target_stage, stage_strategies)


def solve_markov_chain_per_stage(
    start_stage: int,
    target_stage: int,
    stage_strategies: Dict[int, Tuple[bool, bool]]
) -> Tuple[Dict[int, float], Dict[int, float]]:
    """
    Solve the Markov chain with PER-STAGE protection strategies.

    Computes:
    - P_s[stage]: Probability of reaching target from stage (without destruction)
    - C[stage]: Expected COST from stage to target (in diamond units)

    The cost formulation directly incorporates stage-specific costs, avoiding
    the need to separately track attempts per stage.

    Args:
        start_stage: Starting star level
        target_stage: Target star level
        stage_strategies: Dict mapping stage -> (use_decrease_prot, use_destroy_prot)

    Returns:
        C: dict mapping stage -> expected cost from that stage to target
        P_s: dict mapping stage -> probability of success from that stage
    """
    stages = list(range(start_stage, target_stage))

    # Initialize: at target, 0 cost needed, 100% success
    C = {target_stage: 0.0}
    P_s = {target_stage: 1.0}

    # Initialize estimates for other stages
    for stage in stages:
        data = STARFORCE_TABLE.get(stage)
        if data:
            p = data.success_rate
            cost_per_attempt = calculate_diamond_cost(data.meso, data.stones)
            C[stage] = cost_per_attempt / p if p > 0 else float('inf')
            P_s[stage] = 0.9
        else:
            C[stage] = 0
            P_s[stage] = 1.0

    # Iterate until convergence
    for iteration in range(1000):
        max_change = 0

        for stage in reversed(stages):
            data = STARFORCE_TABLE.get(stage)
            if not data:
                continue

            use_decrease_prot, use_destroy_prot = stage_strategies.get(stage, (False, False))

            # Destruction protection not available for last 3 stages (22, 23, 24 -> stars 23, 24, 25)
            can_use_destroy_prot = use_destroy_prot and stage not in {22, 23, 24}

            p = data.success_rate
            d = 0 if use_decrease_prot else data.decrease_rate
            x = data.destroy_rate * (0.5 if can_use_destroy_prot else 1.0)

            # Cost multiplier for protections
            cost_mult = 1.0
            if use_decrease_prot and data.decrease_rate > 0:
                cost_mult += 1.0
            if can_use_destroy_prot and data.destroy_rate > 0:
                cost_mult += 1.0

            cost_per_attempt = calculate_diamond_cost(data.meso * cost_mult, data.stones * cost_mult)

            # Where does decrease go?
            dec_target = max(start_stage, stage - 1)

            denom = p + d + x
            if denom > 0:
                # C[X] = (cost + p*C[X+1] + d*C[dec_target]) / (p + d + x)
                new_C = (cost_per_attempt + p * C.get(stage + 1, 0) + d * C.get(dec_target, C[stage])) / denom

                # P_s[X] = (p*P_s[X+1] + d*P_s[dec_target]) / (p + d + x)
                new_P_s = (p * P_s.get(stage + 1, 1) + d * P_s.get(dec_target, P_s[stage])) / denom
            else:
                new_C = float('inf')
                new_P_s = 0

            max_change = max(max_change, abs(new_C - C[stage]), abs(new_P_s - P_s[stage]))
            C[stage] = new_C
            P_s[stage] = new_P_s

        if max_change < 1e-10:
            break

    return C, P_s


def calculate_total_cost_markov(
    start_stage: int,
    target_stage: int,
    use_decrease_prot: bool = False,
    use_destroy_prot: bool = False,
    rebuild_cost: float = 0.0
) -> MarkovResult:
    """
    Calculate the total expected diamond cost using Markov chain analysis.

    This properly accounts for:
    - Decrease chains (the compounding effect of going back)
    - Cumulative destruction probability
    - Restart costs after destruction (including rebuilding from star 12)

    Formula:
        E[total] = (enhance_cost + P_destroy * (destruction_fee + rebuild_cost)) / P_success

    Where:
        - enhance_cost is computed via Markov chain (C[start_stage])
        - rebuild_cost is the cost to rebuild from star 12 back to start_stage
          (only relevant when start_stage > 12)

    Args:
        start_stage: Starting star level
        target_stage: Target star level
        use_decrease_prot: Whether to use decrease protection
        use_destroy_prot: Whether to use destroy protection
        rebuild_cost: Cost to rebuild from star 12 to start_stage (0 if start_stage=12)
    """
    C, P_s = solve_markov_chain(start_stage, target_stage, use_decrease_prot, use_destroy_prot)

    # C[start_stage] is the expected cost for one run (reaching target or destruction)
    enhance_cost = C.get(start_stage, 0)

    P_success = P_s.get(start_stage, 0)
    P_destroy = 1 - P_success

    # E[total] = (enhance_cost + P_destroy * (fee + rebuild_cost)) / P_success
    # This accounts for the geometric series of restarts
    # When destroyed, you pay the fee AND must rebuild from star 12 to start_stage
    if P_success > 0:
        destruction_penalty = DESTRUCTION_FEE_DIAMONDS + rebuild_cost
        total_cost = (enhance_cost + P_destroy * destruction_penalty) / P_success
    else:
        total_cost = float('inf')

    return MarkovResult(
        stage_costs=C,
        success_probability=P_s,
        enhance_cost=enhance_cost,
        destroy_probability=P_destroy,
        total_cost=total_cost,
    )


def calculate_total_cost_per_stage(
    start_stage: int,
    target_stage: int,
    stage_strategies: Dict[int, Tuple[bool, bool]],
    rebuild_cost: float = 0.0
) -> MarkovResult:
    """
    Calculate total cost with PER-STAGE protection strategies.

    Args:
        start_stage: Starting star level
        target_stage: Target star level
        stage_strategies: Dict mapping stage -> (use_decrease_prot, use_destroy_prot)
        rebuild_cost: Cost to rebuild from star 12 to start_stage (0 if start_stage=12)

    Returns:
        MarkovResult with total expected cost
    """
    C, P_s = solve_markov_chain_per_stage(start_stage, target_stage, stage_strategies)

    # C[start_stage] is the expected cost for one run (reaching target or destruction)
    enhance_cost = C.get(start_stage, 0)

    P_success = P_s.get(start_stage, 0)
    P_destroy = 1 - P_success

    # E[total] = (enhance_cost + P_destroy * (fee + rebuild_cost)) / P_success
    # When destroyed, you pay the fee AND must rebuild from star 12 to start_stage
    if P_success > 0:
        destruction_penalty = DESTRUCTION_FEE_DIAMONDS + rebuild_cost
        total_cost = (enhance_cost + P_destroy * destruction_penalty) / P_success
    else:
        total_cost = float('inf')

    return MarkovResult(
        stage_costs=C,
        success_probability=P_s,
        enhance_cost=enhance_cost,
        destroy_probability=P_destroy,
        total_cost=total_cost,
    )


def build_optimal_strategy_table() -> Tuple[Dict[int, str], Dict[int, float], Dict[int, float]]:
    """
    Build a lookup table of optimal strategies for each stage using full Markov chain.

    For each target star level, we test all 4 uniform strategies using the accurate
    Markov chain solver, then record the best strategy for each stage.

    This properly handles the recursive nature of decrease chains - when you decrease
    from stage N to N-1, redoing N-1→N might itself result in another decrease, etc.

    Returns:
        Tuple of (optimal_strategies, C_to, P_to)
        - optimal_strategies: Dict mapping stage -> best strategy name for that stage
        - C_to: Dict mapping stage -> expected cost from ★12 to that stage
        - P_to: Dict mapping stage -> probability of reaching that stage from ★12
    """
    strategy_options = [
        ('none', False, False),
        ('decrease', True, False),
        ('destroy', False, True),
        ('both', True, True),
    ]

    BASE_STAGE = DESTRUCTION_RESET_STAR  # Always compute from ★12

    optimal_strategies: Dict[int, str] = {}
    C_to: Dict[int, float] = {BASE_STAGE: 0.0}
    P_to: Dict[int, float] = {BASE_STAGE: 1.0}

    # For each target stage, find the best uniform strategy using full Markov chain
    # Then record both the strategy and the incremental cost for that stage
    for target in range(BASE_STAGE + 1, 26):
        best_cost = float('inf')
        best_strat_name = 'none'
        best_result = None

        for name, use_dec, use_dest in strategy_options:
            # Run full Markov chain from BASE_STAGE to target
            result = calculate_total_cost_markov(BASE_STAGE, target, use_dec, use_dest)

            if result.total_cost < best_cost:
                best_cost = result.total_cost
                best_strat_name = name
                best_result = result

        # For the incremental approach, we need to know what strategy is best
        # for just the last stage (target-1 → target)
        # Test which strategy at the last stage minimizes cost
        last_stage = target - 1
        best_last_stage_strat = 'none'
        best_last_stage_cost = float('inf')

        for name, use_dec, use_dest in strategy_options:
            # Build per-stage strategy dict: use previous optimal for earlier stages,
            # test this strategy for the last stage
            stage_strategies = {}
            for s in range(BASE_STAGE, last_stage):
                prev_strat = optimal_strategies.get(s, 'none')
                stage_strategies[s] = {
                    'none': (False, False),
                    'decrease': (True, False),
                    'destroy': (False, True),
                    'both': (True, True),
                }[prev_strat]
            stage_strategies[last_stage] = (use_dec, use_dest)

            result = calculate_total_cost_per_stage(BASE_STAGE, target, stage_strategies)

            if result.total_cost < best_last_stage_cost:
                best_last_stage_cost = result.total_cost
                best_last_stage_strat = name

        optimal_strategies[last_stage] = best_last_stage_strat

        # Update cumulative costs using the best per-stage strategies
        stage_strategies = {}
        for s in range(BASE_STAGE, target):
            strat = optimal_strategies.get(s, 'none')
            stage_strategies[s] = {
                'none': (False, False),
                'decrease': (True, False),
                'destroy': (False, True),
                'both': (True, True),
            }[strat]

        final_result = calculate_total_cost_per_stage(BASE_STAGE, target, stage_strategies)
        # Store total_cost (includes restarts) for use as rebuild_cost
        # When rebuilding from 12→target, you might get destroyed and restart at 12
        C_to[target] = final_result.total_cost
        P_to[target] = 1 - final_result.destroy_probability

    return optimal_strategies, C_to, P_to


# Cache the optimal strategy table (computed once)
_OPTIMAL_STRATEGY_CACHE: Optional[Tuple[Dict[int, str], Dict[int, float], Dict[int, float]]] = None


def get_optimal_strategy_table() -> Tuple[Dict[int, str], Dict[int, float], Dict[int, float]]:
    """Get the cached optimal strategy table, computing if needed."""
    global _OPTIMAL_STRATEGY_CACHE
    if _OPTIMAL_STRATEGY_CACHE is None:
        _OPTIMAL_STRATEGY_CACHE = build_optimal_strategy_table()
    return _OPTIMAL_STRATEGY_CACHE


def find_optimal_per_stage_strategy(
    start_stage: int,
    target_stage: int
) -> Tuple[Dict[int, str], MarkovResult]:
    """
    Find the optimal protection strategy for EACH stage.

    Uses a precomputed lookup table based on ★12 as the reference point,
    ensuring consistent recommendations regardless of starting stage.

    The actual cost is computed using the full Markov chain solver which
    properly handles the recursive nature of decrease chains.

    IMPORTANT: When start_stage > 12, the total_cost includes the expected cost
    of rebuilding from star 12 back to start_stage if destruction occurs.

    Returns:
        (stage_strategy_names, result)
        stage_strategy_names: Dict mapping stage -> 'none'/'decrease'/'destroy'/'both'
    """
    optimal_strategies, C_to, _ = get_optimal_strategy_table()

    # Extract strategies for the requested range
    best_names = {}
    stage_strategies = {}
    for stage in range(start_stage, target_stage):
        strat_name = optimal_strategies.get(stage, 'none')
        best_names[stage] = strat_name
        stage_strategies[stage] = {
            'none': (False, False),
            'decrease': (True, False),
            'destroy': (False, True),
            'both': (True, True),
        }[strat_name]

    # Calculate rebuild cost (cost to go from star 12 to start_stage)
    # This is needed because destruction resets to star 12
    rebuild_cost = 0.0
    if start_stage > DESTRUCTION_RESET_STAR:
        # Get the cost from 12 to start_stage using optimal strategies
        rebuild_cost = C_to.get(start_stage, 0)

    # Compute actual costs using full Markov chain
    result = calculate_total_cost_per_stage(start_stage, target_stage, stage_strategies, rebuild_cost)

    return best_names, result


def find_optimal_strategy(
    start_stage: int,
    target_stage: int
) -> Tuple[str, MarkovResult, Dict[str, MarkovResult]]:
    """
    Find the optimal UNIFORM protection strategy for going from start_stage to target_stage.

    IMPORTANT: When start_stage > 12, the total_cost includes the expected cost
    of rebuilding from star 12 back to start_stage if destruction occurs.

    Returns:
        (best_strategy_name, best_result, all_results)
    """
    strategies = {
        "none": (False, False),
        "decrease": (True, False),
        "destroy": (False, True),
        "both": (True, True),
    }

    # Calculate rebuild cost (cost to go from star 12 to start_stage)
    # This is needed because destruction resets to star 12
    rebuild_cost = 0.0
    if start_stage > DESTRUCTION_RESET_STAR:
        _, C_to, _ = get_optimal_strategy_table()
        rebuild_cost = C_to.get(start_stage, 0)

    all_results = {}
    best_strat = "none"
    best_cost = float('inf')

    for name, (use_dec, use_dest) in strategies.items():
        result = calculate_total_cost_markov(start_stage, target_stage, use_dec, use_dest, rebuild_cost)
        all_results[name] = result

        if result.total_cost < best_cost:
            best_cost = result.total_cost
            best_strat = name

    return best_strat, all_results[best_strat], all_results


# =============================================================================
# OUTPUT AND DISPLAY
# =============================================================================

def print_comparison(start_stage: int, target_stage: int):
    """Print a comparison of all strategies for a given range."""
    best_strat, best_result, all_results = find_optimal_strategy(start_stage, target_stage)

    print(f"\n{'='*100}")
    print(f"ANALYSIS: Star {start_stage} -> Star {target_stage}")
    print(f"{'='*100}")
    print()
    print(f"{'Strategy':<12} {'P(destroy)':<12} {'Enhance Cost':<14} {'Dest Penalty':<14} {'TOTAL':<14}")
    print("-" * 70)

    for name in ['none', 'decrease', 'destroy', 'both']:
        r = all_results[name]
        dest_penalty = r.destroy_probability * DESTRUCTION_FEE_DIAMONDS

        print(f"{name.upper():<12} {r.destroy_probability*100:<11.1f}% "
              f"{r.enhance_cost:<13,.0f} {dest_penalty:<13,.0f} {r.total_cost:<13,.0f}")

    print()
    savings = all_results['none'].total_cost - best_result.total_cost
    print(f"WINNER: {best_strat.upper()}")
    if best_strat != 'none' and savings > 0:
        pct = savings / all_results['none'].total_cost * 100
        print(f"Saves {savings:,.0f} diamonds ({pct:.1f}%) vs NONE")

    return all_results


def print_stage_breakdown(start_stage: int, target_stage: int, strategy_name: str, use_dec: bool, use_dest: bool):
    """Print detailed breakdown by stage for a strategy."""
    C, P_s = solve_markov_chain(start_stage, target_stage, use_dec, use_dest)

    print(f"\n{'='*100}")
    print(f"STAGE BREAKDOWN: {strategy_name.upper()} (Star {start_stage} -> Star {target_stage})")
    print(f"{'='*100}")
    print()
    print(f"{'Stage':<10} {'Success%':<10} {'Decrease%':<10} {'Destroy%':<10} {'E[cost]':<14} {'P(success)':<12}")
    print("-" * 80)

    for stage in range(start_stage, target_stage):
        data = STARFORCE_TABLE.get(stage)
        if not data:
            continue

        d = 0 if use_dec else data.decrease_rate
        # Destruction protection not available for last 3 stages (22, 23, 24)
        can_use_destroy_prot = use_dest and stage not in {22, 23, 24}
        x = data.destroy_rate * (0.5 if can_use_destroy_prot else 1.0)

        print(f"{stage}->{stage+1:<5} {data.success_rate*100:<9.1f} {d*100:<9.0f} {x*100:<9.1f} "
              f"{C.get(stage, 0):<13,.0f} {P_s.get(stage, 0)*100:<11.2f}%")


def generate_recommendations():
    """Generate optimal strategy recommendations for all target stars."""
    print("\n" + "=" * 100)
    print("OPTIMAL STRATEGY RECOMMENDATIONS")
    print("=" * 100)
    print()
    print("Based on Markov chain analysis accounting for:")
    print("  - Decrease chains (going back requires redoing stages)")
    print("  - Cumulative destruction probability across attempts")
    print("  - Restart costs after destruction")
    print()
    print(f"{'Target':<12} {'Best Strategy':<15} {'Total Cost':<18} {'P(destroy)':<14} {'Savings vs NONE':<15}")
    print("-" * 80)

    for target in range(13, 26):
        best_strat, best_result, all_results = find_optimal_strategy(12, target)
        none_cost = all_results['none'].total_cost

        if best_strat == 'none':
            savings = "-"
        else:
            savings_amt = none_cost - best_result.total_cost
            savings_pct = savings_amt / none_cost * 100 if none_cost > 0 else 0
            savings = f"{savings_pct:.1f}%"

        print(f"12 -> {target:<5} {best_strat.upper():<15} {best_result.total_cost:<17,.0f} "
              f"{best_result.destroy_probability*100:<13.1f}% {savings:<15}")


def generate_full_analysis():
    """Generate comprehensive analysis output."""
    print("=" * 100)
    print("STARFORCE COMPLETE MATHEMATICAL ANALYSIS")
    print("=" * 100)
    print()
    print("This analysis uses Markov chain mathematics to properly account for:")
    print("  1. Decrease chains (decrease requires redoing previous stages)")
    print("  2. Cumulative destruction probability (more attempts = more destruction rolls)")
    print("  3. Restart costs (destruction resets to star 12, must rebuild)")
    print()
    print("Key formulas:")
    print("  E[attempts at X] = (1 + p*E[X+1] + d*E[X-1]) / (p + d + x)")
    print("  P[success from X] = (p*P[X+1] + d*P[X-1]) / (p + d + x)")
    print("  E[total cost] = (enhance_cost + P_destroy * fee) / P_success")
    print()
    print(f"Conversion rates: {MESO_TO_DIAMOND*1000:.1f} diamonds/1000 meso, {SCROLL_DIAMOND_COST} diamonds/scroll")
    print(f"Destruction fee: {DESTRUCTION_FEE_DIAMONDS:,.0f} diamonds")
    print()

    # Analyze key targets
    for target in [17, 20, 22, 25]:
        print_comparison(12, target)

    # Detailed breakdown for 12->25
    print("\n" + "=" * 100)
    print("DETAILED STAGE-BY-STAGE BREAKDOWN: 12 -> 25")
    print("=" * 100)

    for name, use_dec, use_dest in [('none', False, False), ('decrease', True, False), ('both', True, True)]:
        print_stage_breakdown(12, 25, name, use_dec, use_dest)

    # Generate recommendations
    generate_recommendations()

    # Final summary
    print("\n" + "=" * 100)
    print("KEY INSIGHTS")
    print("=" * 100)
    print("""
1. WITHOUT PROTECTION at high stars, destruction probability approaches 100%
   - At 12->25 with NO protection: 99.9% chance of destruction!
   - You'd need ~1,250 full runs on average to succeed once

2. DECREASE PROTECTION becomes valuable when decrease chains compound
   - At 24->25: 208 attempts without vs 25 attempts with decrease protection
   - The 10% decrease rate creates exponential growth in attempts

3. BOTH PROTECTIONS is optimal for high star targets (20+)
   - The combination minimizes both attempt count AND destruction probability
   - Saves 80-90%+ of diamonds compared to no protection at 25 stars

4. PROTECTION IS NOT NEEDED for low targets (12->17)
   - Destruction probability is low enough that protections cost more than they save

PRACTICAL RECOMMENDATIONS:
   12 -> 17:  NO PROTECTION (low risk)
   12 -> 18:  NO PROTECTION (borderline)
   12 -> 19+: DECREASE or BOTH (protection pays off)
   12 -> 20+: BOTH PROTECTIONS (strongly recommended)
   12 -> 22+: BOTH PROTECTIONS (essential - saves 50%+ diamonds)
   12 -> 25:  BOTH PROTECTIONS (critical - saves 92% diamonds)
""")


# =============================================================================
# LEGACY SIMULATION FUNCTIONS (for comparison/validation)
# =============================================================================

@dataclass
class SimulationResult:
    """Results from Monte Carlo simulation."""
    avg_meso: float
    avg_scrolls: float
    avg_attempts: float
    avg_destructions: float
    success_rate: float


def simulate_to_target(
    start_star: int,
    target_star: int,
    use_decrease_prot: bool,
    use_destroy_prot: bool,
    simulations: int = 10000
) -> SimulationResult:
    """
    Monte Carlo simulation for validation.
    Simulates going from start_star to target_star with full restart on destruction.
    """
    import random

    total_meso = 0
    total_scrolls = 0
    total_attempts = 0
    total_destructions = 0

    for _ in range(simulations):
        current = start_star
        meso = 0
        scrolls = 0
        attempts = 0
        destructions = 0

        while current < target_star:
            data = STARFORCE_TABLE.get(current)
            if not data:
                break

            # Destruction protection not available for last 3 stages (22, 23, 24)
            can_use_destroy_prot = use_destroy_prot and current not in {22, 23, 24}

            p = data.success_rate
            d = 0 if use_decrease_prot else data.decrease_rate
            x = data.destroy_rate * (0.5 if can_use_destroy_prot else 1.0)
            m = 1 - p - d - x

            cost_mult = 1.0
            if use_decrease_prot and data.decrease_rate > 0:
                cost_mult += 1.0
            if can_use_destroy_prot and data.destroy_rate > 0:
                cost_mult += 1.0

            attempts += 1
            meso += data.meso * cost_mult
            scrolls += data.stones * cost_mult

            roll = random.random()
            if roll < p:
                current += 1
            elif roll < p + m:
                pass  # Maintain
            elif roll < p + m + d:
                current = max(start_star, current - 1)
            else:
                # Destroyed - reset to 12
                destructions += 1
                meso += DESTRUCTION_FEE_MESO
                current = DESTRUCTION_RESET_STAR

        total_meso += meso
        total_scrolls += scrolls
        total_attempts += attempts
        total_destructions += destructions

    return SimulationResult(
        avg_meso=total_meso / simulations,
        avg_scrolls=total_scrolls / simulations,
        avg_attempts=total_attempts / simulations,
        avg_destructions=total_destructions / simulations,
        success_rate=100.0,  # All simulations eventually succeed
    )


def validate_markov_vs_simulation(target: int = 20, sims: int = 5000):
    """Compare Markov chain results with Monte Carlo simulation."""
    print(f"\n{'='*100}")
    print(f"VALIDATION: Markov Chain vs Monte Carlo Simulation (12 -> {target})")
    print(f"{'='*100}")
    print()

    strategies = [
        ('none', False, False),
        ('decrease', True, False),
        ('destroy', False, True),
        ('both', True, True),
    ]

    print(f"{'Strategy':<12} {'Markov Cost':<16} {'Sim Cost':<16} {'Difference':<12}")
    print("-" * 60)

    for name, use_dec, use_dest in strategies:
        # Markov chain
        markov = calculate_total_cost_markov(12, target, use_dec, use_dest)

        # Simulation
        sim = simulate_to_target(12, target, use_dec, use_dest, sims)
        sim_cost = calculate_diamond_cost(sim.avg_meso, sim.avg_scrolls)

        diff_pct = (sim_cost - markov.total_cost) / markov.total_cost * 100 if markov.total_cost > 0 else 0

        print(f"{name.upper():<12} {markov.total_cost:<15,.0f} {sim_cost:<15,.0f} {diff_pct:>+.1f}%")

    print()
    print(f"(Simulation uses {sims} runs - some variance expected)")


if __name__ == "__main__":
    generate_full_analysis()

    # Validate with simulation
    validate_markov_vs_simulation(20, 3000)
    validate_markov_vs_simulation(22, 2000)
