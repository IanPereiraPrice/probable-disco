"""
Complete Starforce Mathematical Analysis
=========================================
Properly accounts for:
1. Decrease chains (going back requires redoing stages)
2. Destruction probability (more attempts = more destruction rolls)
3. Restart costs (destruction resets to star 12)

Uses Markov chain analysis to compute exact expected values.
"""

import sys
import io

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from equipment import STARFORCE_TABLE

MESO_TO_DIAMOND = 4.0 / 1000
SCROLL_DIAMOND_COST = 350
DESTRUCTION_FEE = 1_000_000  # 1M meso

# Last 3 starforce stages cannot use destruction protection
# Stages 22, 23, 24 (to reach stars 23, 24, 25)
NO_DESTROY_PROTECTION_STAGES = {22, 23, 24}

def diamond_cost(meso, scrolls):
    return meso * MESO_TO_DIAMOND + scrolls * SCROLL_DIAMOND_COST


def solve_markov_chain(start_stage, target_stage, use_decrease_prot=False, use_destroy_prot=False):
    """
    Solve the Markov chain for starforce enhancement.

    Returns for each stage:
      - E[X]: expected attempts to reach target or destruction from stage X
      - P_s[X]: probability of success (reaching target) from stage X

    The equations are:
      E[X] = (1 + p*E[X+1] + d*E[dec_target]) / (p + d + x)
      P_s[X] = (p*P_s[X+1] + d*P_s[dec_target]) / (p + d + x)

    Where:
      p = success rate
      d = decrease rate (0 if protected)
      x = destroy rate (halved if protected)
      m = maintain rate = 1 - p - d - x
      dec_target = max(start_stage, X-1)
    """
    stages = list(range(start_stage, target_stage))

    # Initialize: at target, 0 attempts needed, 100% success
    E = {target_stage: 0}
    P_s = {target_stage: 1.0}

    # Initialize estimates for other stages
    for stage in stages:
        data = STARFORCE_TABLE[stage]
        p = data.success_rate
        E[stage] = 1 / p  # Initial guess
        P_s[stage] = 0.9  # Initial guess

    # Iterate until convergence
    for iteration in range(1000):
        max_change = 0

        for stage in reversed(stages):
            data = STARFORCE_TABLE[stage]

            p = data.success_rate
            d = 0 if use_decrease_prot else data.decrease_rate
            # Destruction protection not available for last 3 stages (22, 23, 24)
            can_use_destroy_prot = use_destroy_prot and stage not in NO_DESTROY_PROTECTION_STAGES
            x = data.destroy_rate * (0.5 if can_use_destroy_prot else 1.0)

            # Where does decrease go?
            dec_target = max(start_stage, stage - 1)

            denom = p + d + x
            if denom > 0:
                # E[X] = (1 + p*E[X+1] + d*E[dec_target]) / (p + d + x)
                new_E = (1 + p * E.get(stage + 1, 0) + d * E.get(dec_target, E[stage])) / denom

                # P_s[X] = (p*P_s[X+1] + d*P_s[dec_target]) / (p + d + x)
                new_P_s = (p * P_s.get(stage + 1, 1) + d * P_s.get(dec_target, P_s[stage])) / denom
            else:
                new_E = float('inf')
                new_P_s = 0

            max_change = max(max_change, abs(new_E - E[stage]), abs(new_P_s - P_s[stage]))
            E[stage] = new_E
            P_s[stage] = new_P_s

        if max_change < 1e-10:
            break

    return E, P_s


def calculate_total_cost(start_stage, target_stage, use_decrease_prot=False, use_destroy_prot=False):
    """
    Calculate the total expected diamond cost to go from start_stage to target_stage.

    Accounts for:
    - Enhancement costs (meso + scrolls, with protection multipliers)
    - Destruction fee (1M meso)
    - Restart costs (geometric series from destruction)

    Formula:
      E[total] = (C + P_destroy * fee) / P_success

    Where:
      C = expected enhancement cost for one run
      P_destroy = 1 - P_success
      fee = destruction fee in diamonds
    """
    E, P_s = solve_markov_chain(start_stage, target_stage, use_decrease_prot, use_destroy_prot)

    # Calculate enhancement cost for one run
    enhance_cost = 0
    total_attempts = 0

    for stage in range(start_stage, target_stage):
        data = STARFORCE_TABLE[stage]
        attempts = E[stage]

        # Cost multiplier for protections (only if they do something)
        cost_mult = 1.0
        if use_decrease_prot and data.decrease_rate > 0:
            cost_mult += 1.0
        # Destruction protection not available for last 3 stages (22, 23, 24)
        can_use_destroy_prot = use_destroy_prot and stage not in NO_DESTROY_PROTECTION_STAGES
        if can_use_destroy_prot and data.destroy_rate > 0:
            cost_mult += 1.0

        stage_cost = attempts * diamond_cost(data.meso * cost_mult, data.stones * cost_mult)
        enhance_cost += stage_cost
        total_attempts += attempts

    P_destroy = 1 - P_s[start_stage]
    dest_fee_diamonds = DESTRUCTION_FEE * MESO_TO_DIAMOND

    # E[total] = (C + P_destroy * fee) / P_success
    if P_s[start_stage] > 0:
        total_cost = (enhance_cost + P_destroy * dest_fee_diamonds) / P_s[start_stage]
    else:
        total_cost = float('inf')

    return {
        'attempts': total_attempts,
        'enhance_cost': enhance_cost,
        'p_destroy': P_destroy,
        'p_success': P_s[start_stage],
        'dest_fee': P_destroy * dest_fee_diamonds,
        'total_cost': total_cost,
        'E': E,
        'P_s': P_s,
    }


def analyze_all_strategies(start_stage, target_stage):
    """Analyze all 4 protection strategies for a given range."""
    strategies = [
        ('NONE', False, False),
        ('DECREASE', True, False),
        ('DESTROY', False, True),
        ('BOTH', True, True),
    ]

    results = {}
    for name, use_dec, use_dest in strategies:
        results[name] = calculate_total_cost(start_stage, target_stage, use_dec, use_dest)

    return results


def print_comparison(start_stage, target_stage):
    """Print a comparison of all strategies."""
    results = analyze_all_strategies(start_stage, target_stage)

    print(f"\n{'='*100}")
    print(f"ANALYSIS: Star {start_stage} -> Star {target_stage}")
    print(f"{'='*100}")
    print()
    print(f"{'Strategy':<12} {'Attempts':<12} {'P(destroy)':<12} {'Enhance Cost':<14} {'Dest Penalty':<14} {'TOTAL':<14}")
    print("-" * 90)

    for name in ['NONE', 'DECREASE', 'DESTROY', 'BOTH']:
        r = results[name]
        print(f"{name:<12} {r['attempts']:<11.1f} {r['p_destroy']*100:<11.1f}% "
              f"{r['enhance_cost']:<13,.0f} {r['dest_fee']:<13,.0f} {r['total_cost']:<13,.0f}")

    # Find winner
    winner = min(results, key=lambda x: results[x]['total_cost'])
    savings = results['NONE']['total_cost'] - results[winner]['total_cost']

    print()
    print(f"WINNER: {winner}")
    if winner != 'NONE':
        print(f"Saves {savings:,.0f} diamonds ({savings/results['NONE']['total_cost']*100:.1f}%) vs NONE")

    return results


def print_stage_breakdown(start_stage, target_stage, strategy_name, use_dec, use_dest):
    """Print detailed breakdown by stage for a strategy."""
    E, P_s = solve_markov_chain(start_stage, target_stage, use_dec, use_dest)

    print(f"\n{'='*100}")
    print(f"STAGE BREAKDOWN: {strategy_name} (Star {start_stage} -> Star {target_stage})")
    print(f"{'='*100}")
    print()
    print(f"{'Stage':<10} {'Success%':<10} {'Decrease%':<10} {'Destroy%':<10} {'E[attempts]':<14} {'P(success)':<12}")
    print("-" * 80)

    for stage in range(start_stage, target_stage):
        data = STARFORCE_TABLE[stage]
        d = 0 if use_dec else data.decrease_rate
        # Destruction protection not available for last 3 stages (22, 23, 24)
        can_use_destroy_prot = use_dest and stage not in NO_DESTROY_PROTECTION_STAGES
        x = data.destroy_rate * (0.5 if can_use_destroy_prot else 1.0)

        print(f"{stage}->{stage+1:<5} {data.success_rate*100:<9.1f} {d*100:<9.0f} {x*100:<9.1f} "
              f"{E[stage]:<13.2f} {P_s[stage]*100:<11.2f}%")


if __name__ == "__main__":
    print("=" * 100)
    print("STARFORCE COMPLETE MATHEMATICAL ANALYSIS")
    print("=" * 100)
    print()
    print("This analysis properly accounts for:")
    print("  1. Decrease chains (decrease requires redoing previous stages)")
    print("  2. Destruction probability (more attempts = more destruction rolls)")
    print("  3. Restart costs (destruction resets to star 12, must rebuild)")
    print()
    print("Formula used:")
    print("  E[total cost] = (enhance_cost + P_destroy * destruction_fee) / P_success")
    print()
    print("Where enhance_cost accounts for the compounding effect of decreases,")
    print("and P_success is the probability of reaching target before destruction.")
    print()

    # Analyze key targets
    for target in [17, 20, 22, 25]:
        print_comparison(12, target)

    # Detailed breakdown for 12->25
    print("\n" + "=" * 100)
    print("DETAILED STAGE-BY-STAGE BREAKDOWN: 12 -> 25")
    print("=" * 100)

    for name, use_dec, use_dest in [('NONE', False, False), ('DECREASE', True, False)]:
        print_stage_breakdown(12, 25, name, use_dec, use_dest)

    # Summary recommendations
    print("\n" + "=" * 100)
    print("RECOMMENDATIONS")
    print("=" * 100)

    print("\nBased on mathematical analysis:")
    print()

    recommendations = []
    for target in range(13, 26):
        results = analyze_all_strategies(12, target)
        winner = min(results, key=lambda x: results[x]['total_cost'])
        savings_pct = (results['NONE']['total_cost'] - results[winner]['total_cost']) / results['NONE']['total_cost'] * 100 if results['NONE']['total_cost'] > 0 else 0
        recommendations.append((target, winner, savings_pct))

    print(f"{'Target':<10} {'Best Strategy':<15} {'Savings vs NONE':<15}")
    print("-" * 45)
    for target, winner, savings in recommendations:
        if winner == 'NONE':
            print(f"12 -> {target:<4} {winner:<15} -")
        else:
            print(f"12 -> {target:<4} {winner:<15} {savings:.1f}%")
