"""
Starforce Calculator Page
Calculate expected costs and run Monte Carlo simulations for starforce enhancement.
Matches the original Tkinter app starforce tab.
"""
import streamlit as st
import random
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from equipment import STARFORCE_TABLE, get_amplify_multiplier
from starforce_optimizer import (
    find_optimal_per_stage_strategy,
    find_optimal_strategy,
    calculate_total_cost_markov,
    MESO_TO_DIAMOND,
    SCROLL_DIAMOND_COST,
    DESTRUCTION_FEE_DIAMONDS,
)

st.set_page_config(page_title="Starforce Calculator", page_icon="⭐", layout="wide")

# Compact CSS styling
st.markdown("""
<style>
    .block-container { padding-top: 1rem; }
    .section-header {
        font-size: 16px;
        font-weight: bold;
        color: #ffd700;
        margin-bottom: 8px;
        padding: 8px;
        background: #2a2a4e;
        border-radius: 4px;
    }
    .result-box {
        background: #2a2a4e;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        font-family: monospace;
    }
    .table-header {
        background: #3a3a5e;
        padding: 4px 8px;
        font-weight: bold;
        color: #ccc;
    }
    .table-row {
        padding: 2px 8px;
        border-bottom: 1px solid #333;
    }
    .star-gold { color: #ffd700; }
    .success-green { color: #7bed9f; }
    .danger-red { color: #ff6b6b; }
    .warning-orange { color: #ff9f43; }
    .stat-value { color: #66ff66; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# Initialize session - redirect if not logged in
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first")
    st.stop()


def simulate_starforce(start: int, target: int, stage_strategies: dict, iterations: int = 1000) -> dict:
    """
    Run Monte Carlo simulation for starforce enhancement using optimal per-stage strategies.

    Args:
        start: Starting star level
        target: Target star level
        stage_strategies: Dict mapping stage -> strategy name ('none', 'decrease', 'destroy', 'both')
        iterations: Number of simulation runs
    """
    results = []

    for _ in range(iterations):
        stars = start
        meso = 0
        stones = 0
        attempts = 0
        destructions = 0
        max_attempts = 10000

        while stars < target and attempts < max_attempts:
            if stars not in STARFORCE_TABLE:
                break

            stage = STARFORCE_TABLE[stars]

            # Get strategy for current stage
            strat = stage_strategies.get(stars, 'none')
            protect_dec = strat in ('decrease', 'both')
            protect_dest = strat in ('destroy', 'both')

            # Calculate cost with protections
            cost_mult = 1.0
            if protect_dec and stage.decrease_rate > 0:
                cost_mult += 1.0
            if protect_dest and stage.destroy_rate > 0:
                cost_mult += 1.0

            meso += int(stage.meso * cost_mult)
            stones += int(stage.stones * cost_mult)
            attempts += 1

            # Adjust probabilities based on protection
            success_rate = stage.success_rate
            maintain_rate = stage.maintain_rate
            decrease_rate = 0 if protect_dec else stage.decrease_rate
            destroy_rate = stage.destroy_rate * (0.5 if protect_dest else 1.0)

            # Maintain rate absorbs the protected decrease
            if protect_dec and stage.decrease_rate > 0:
                maintain_rate += stage.decrease_rate

            roll = random.random()

            if roll < success_rate:
                stars += 1
            elif roll < success_rate + maintain_rate:
                pass  # Maintain
            elif roll < success_rate + maintain_rate + decrease_rate:
                stars = max(start, stars - 1)
            else:
                destructions += 1
                meso += 1_000_000  # Destruction fee
                stars = 12  # Reset to 12

        results.append({
            "meso": meso, "stones": stones, "attempts": attempts,
            "destructions": destructions, "success": stars >= target
        })

    # Calculate statistics
    mesos = [r['meso'] for r in results]
    stones_list = [r['stones'] for r in results]
    attempts_list = [r['attempts'] for r in results]
    destructions_list = [r['destructions'] for r in results]

    return {
        "avg_meso": sum(mesos) / len(mesos),
        "med_meso": sorted(mesos)[len(mesos) // 2],
        "min_meso": min(mesos),
        "max_meso": max(mesos),
        "p95_meso": sorted(mesos)[int(len(mesos) * 0.95)],
        "avg_stones": sum(stones_list) / len(stones_list),
        "avg_attempts": sum(attempts_list) / len(attempts_list),
        "avg_destructions": sum(destructions_list) / len(destructions_list),
        "total_destructions": sum(destructions_list),
        "success_rate": sum(1 for r in results if r['success']) / len(results) * 100,
        "iterations": iterations,
    }


# ============================================================================
# PAGE LAYOUT
# ============================================================================

st.title("⭐ Starforce Calculator")
st.markdown("Calculate expected costs and run simulations for starforce enhancement.")

col_calc, col_ref = st.columns([1.5, 1])

with col_calc:
    # Calculator Section
    st.markdown("<div class='section-header'>STARFORCE CALCULATOR</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        current_stars = st.selectbox("Current Stars", list(range(0, 25)), index=10, key="sf_current")
    with col2:
        target_stars = st.selectbox("Target Stars", list(range(1, 26)), index=15, key="sf_target")

    st.caption("(Uses optimal per-stage protection strategy)")

    col1, col2 = st.columns(2)
    with col1:
        calc_btn = st.button("Calculate", type="primary", use_container_width=True)
    with col2:
        sim_btn = st.button("Simulate (1000x)", use_container_width=True)

    # Process Calculate button
    if calc_btn:
        if target_stars <= current_stars:
            st.error("Target must be higher than current!")
        else:
            with st.spinner("Calculating optimal strategy..."):
                # Use optimal per-stage strategy
                stage_names, result = find_optimal_per_stage_strategy(current_stars, target_stars)
                _, _, all_results = find_optimal_strategy(current_stars, target_stars)

                # Calculate per-stage costs for all 4 strategies
                per_stage_costs = {}
                for stage in range(current_stars, target_stars):
                    stage_costs = {}
                    for strat_name, (use_dec, use_dest) in [
                        ('none', (False, False)),
                        ('decrease', (True, False)),
                        ('destroy', (False, True)),
                        ('both', (True, True)),
                    ]:
                        # Calculate cost for single stage transition
                        stage_result = calculate_total_cost_markov(stage, stage + 1, use_dec, use_dest)
                        stage_costs[strat_name] = stage_result.total_cost
                    per_stage_costs[stage] = stage_costs

                # Estimate meso and scrolls from diamond cost
                total_meso_weight = 0
                total_scroll_weight = 0
                for stage in range(current_stars, target_stars):
                    sf_data = STARFORCE_TABLE.get(stage)
                    if sf_data:
                        strat = stage_names.get(stage, 'none')
                        cost_mult = 1.0
                        if strat in ('decrease', 'both') and sf_data.decrease_rate > 0:
                            cost_mult += 1.0
                        if strat in ('destroy', 'both') and sf_data.destroy_rate > 0:
                            cost_mult += 1.0
                        total_meso_weight += sf_data.meso * cost_mult
                        total_scroll_weight += sf_data.stones * cost_mult

                if total_meso_weight + total_scroll_weight > 0:
                    meso_diamonds = total_meso_weight * MESO_TO_DIAMOND
                    scroll_diamonds = total_scroll_weight * SCROLL_DIAMOND_COST
                    meso_ratio = meso_diamonds / (meso_diamonds + scroll_diamonds)
                    scroll_ratio = scroll_diamonds / (meso_diamonds + scroll_diamonds)
                    total_meso = int((result.total_cost * meso_ratio) / MESO_TO_DIAMOND)
                    total_scrolls = int((result.total_cost * scroll_ratio) / SCROLL_DIAMOND_COST)
                else:
                    total_meso = 0
                    total_scrolls = 0

                st.session_state.sf_calc_result = {
                    "current": current_stars, "target": target_stars,
                    "meso": total_meso, "stones": total_scrolls,
                    "destroy_prob": result.destroy_probability,
                    "total_diamonds": result.total_cost,
                    "stage_names": stage_names,
                    "all_results": all_results,
                    "per_stage_costs": per_stage_costs,
                }

    # Process Simulate button
    if sim_btn:
        if target_stars <= current_stars:
            st.error("Target must be higher than current!")
        else:
            with st.spinner("Running 1000 simulations..."):
                # Get optimal strategies first
                stage_names, _ = find_optimal_per_stage_strategy(current_stars, target_stars)
                result = simulate_starforce(current_stars, target_stars, stage_names, 1000)
                st.session_state.sf_sim_result = result
                st.session_state.sf_sim_result['current'] = current_stars
                st.session_state.sf_sim_result['target'] = target_stars
                st.session_state.sf_sim_result['stage_names'] = stage_names

    # Expected Costs Display
    st.markdown("---")
    st.markdown("<div class='section-header'>EXPECTED COSTS</div>", unsafe_allow_html=True)

    if 'sf_calc_result' in st.session_state:
        r = st.session_state.sf_calc_result
        st.markdown(f"""
        <div class='result-box'>
        <span class='star-gold'>★{r['current']} → ★{r['target']} (Optimal)</span><br>
        ───────────────────<br>
        Expected Meso: <span class='stat-value'>{r['meso']:,}</span><br>
        Expected Scrolls: <span class='stat-value'>{r['stones']:,}</span><br>
        P(Destroy): <span class='danger-red'>{r['destroy_prob']*100:.1f}%</span><br>
        Total Diamonds: <span class='stat-value'>{r['total_diamonds']:,.0f}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Click **Calculate** to see expected costs")

    # Optimal Strategy Section
    st.markdown("---")
    st.markdown("<div class='section-header'>OPTIMAL STRATEGY (Markov Analysis)</div>", unsafe_allow_html=True)
    st.caption("Properly accounts for decrease chains and cumulative destruction probability")

    if 'sf_calc_result' in st.session_state and 'stage_names' in st.session_state.sf_calc_result:
        r = st.session_state.sf_calc_result
        stage_names = r['stage_names']
        all_results = r.get('all_results', {})

        strat_names_full = {
            'none': 'No Protection',
            'decrease': 'Decrease Only',
            'destroy': 'Destroy Only',
            'both': 'Both Protections'
        }

        # Group consecutive stages with same strategy
        zones = []
        zone_start = r['current']
        zone_strat = stage_names.get(r['current'], 'none')

        for stage in range(r['current'], r['target']):
            strat = stage_names.get(stage, 'none')
            if strat != zone_strat:
                zones.append((zone_start, stage, zone_strat))
                zone_start = stage
                zone_strat = strat
        zones.append((zone_start, r['target'], zone_strat))

        # Build strategy display
        strategy_text = "<strong>PROTECTION BY STAGE:</strong><br>"
        for start, end, strat in zones:
            color = "#7bed9f" if strat == 'none' else "#ff9f43" if strat in ('decrease', 'destroy') else "#ff6b6b"
            strategy_text += f"&nbsp;&nbsp;<span style='color:#ffd700;'>★{start}→{end}:</span> <span style='color:{color};'>{strat_names_full[strat]}</span><br>"

        strategy_text += f"<br>{'─' * 35}<br>"
        strategy_text += f"<strong>COST:</strong> {r['total_diamonds']:,.0f} diamonds<br>"
        strategy_text += f"<strong>P(Destroy):</strong> <span class='danger-red'>{r['destroy_prob']*100:.1f}%</span><br>"

        # Show savings vs no protection
        if 'none' in all_results:
            none_cost = all_results['none'].total_cost
            if none_cost > r['total_diamonds']:
                total_savings = none_cost - r['total_diamonds']
                total_pct = total_savings / none_cost * 100
                strategy_text += f"<br><span class='success-green'>Saves {total_savings:,.0f} ({total_pct:.1f}%)</span><br>"
                strategy_text += "vs no protection"

        st.markdown(f"<div class='result-box'>{strategy_text}</div>", unsafe_allow_html=True)
    else:
        st.info("Click **Calculate** to see optimal strategy")

    # Per-Stage Cost Comparison Section
    st.markdown("---")
    st.markdown("<div class='section-header'>STRATEGY COST COMPARISON BY STAGE</div>", unsafe_allow_html=True)
    st.caption("Expected diamond cost for each stage with all 4 strategies. Savings vs next-best alternative shown.")

    if 'sf_calc_result' in st.session_state and 'per_stage_costs' in st.session_state.sf_calc_result:
        r = st.session_state.sf_calc_result
        per_stage_costs = r['per_stage_costs']
        stage_names = r['stage_names']

        strat_names_short = {
            'none': 'None',
            'decrease': 'Dec',
            'destroy': 'Dest',
            'both': 'Both'
        }

        # Build table header
        table_html = """
        <div style='overflow-x: auto;'>
        <table style='width:100%; font-family:monospace; font-size:11px; border-collapse:collapse;'>
        <tr style='background:#3a3a5e; color:#ccc;'>
            <th style='padding:6px; text-align:left;'>Stage</th>
            <th style='padding:6px; text-align:right;'>None</th>
            <th style='padding:6px; text-align:right;'>Decrease</th>
            <th style='padding:6px; text-align:right;'>Destroy</th>
            <th style='padding:6px; text-align:right;'>Both</th>
            <th style='padding:6px; text-align:center;'>Best</th>
            <th style='padding:6px; text-align:right;'>Savings</th>
        </tr>
        """

        for stage in sorted(per_stage_costs.keys()):
            costs = per_stage_costs[stage]
            optimal_strat = stage_names.get(stage, 'none')

            # Sort strategies by cost to find best and second best
            sorted_strats = sorted(costs.items(), key=lambda x: x[1])
            best_strat, best_cost = sorted_strats[0]
            second_best_cost = sorted_strats[1][1] if len(sorted_strats) > 1 else best_cost

            # Calculate savings vs second best
            savings = second_best_cost - best_cost
            savings_pct = (savings / second_best_cost * 100) if second_best_cost > 0 else 0

            # Build row with highlighting for best strategy
            row = f"<tr style='border-bottom:1px solid #333;'>"
            row += f"<td style='padding:4px; color:#ffd700;'>★{stage}→{stage+1}</td>"

            for strat in ['none', 'decrease', 'destroy', 'both']:
                cost = costs.get(strat, 0)
                is_best = (strat == best_strat)
                color = '#7bed9f' if is_best else '#ccc'
                weight = 'bold' if is_best else 'normal'
                row += f"<td style='padding:4px; text-align:right; color:{color}; font-weight:{weight};'>{cost:,.0f}</td>"

            # Best strategy column
            best_color = '#7bed9f' if best_strat == 'none' else '#ff9f43' if best_strat in ('decrease', 'destroy') else '#ff6b6b'
            row += f"<td style='padding:4px; text-align:center; color:{best_color};'>{strat_names_short[best_strat]}</td>"

            # Savings column
            if savings > 0:
                row += f"<td style='padding:4px; text-align:right; color:#7bed9f;'>{savings:,.0f} ({savings_pct:.0f}%)</td>"
            else:
                row += f"<td style='padding:4px; text-align:right; color:#888;'>-</td>"

            row += "</tr>"
            table_html += row

        table_html += "</table></div>"
        st.markdown(table_html, unsafe_allow_html=True)

        # Summary of total costs for each uniform strategy
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Total Expected Cost (Uniform Strategy):**")

        all_results = r.get('all_results', {})
        if all_results:
            # Sort by cost
            sorted_results = sorted(all_results.items(), key=lambda x: x[1].total_cost)
            best_uniform = sorted_results[0]
            second_uniform = sorted_results[1] if len(sorted_results) > 1 else sorted_results[0]

            summary_html = "<div style='font-family:monospace; font-size:12px;'>"
            for name, res in sorted_results:
                is_best = (name == best_uniform[0])
                color = '#7bed9f' if is_best else '#ccc'
                savings_vs_none = all_results['none'].total_cost - res.total_cost
                savings_text = f" (saves {savings_vs_none:,.0f})" if savings_vs_none > 0 else ""
                summary_html += f"<span style='color:{color};'>{'→ ' if is_best else '  '}{name.upper()}: {res.total_cost:,.0f} diamonds{savings_text}</span><br>"
            summary_html += "</div>"
            st.markdown(summary_html, unsafe_allow_html=True)

            # Show optimal per-stage total vs best uniform
            optimal_total = r['total_diamonds']
            best_uniform_cost = best_uniform[1].total_cost
            if optimal_total < best_uniform_cost:
                per_stage_savings = best_uniform_cost - optimal_total
                st.markdown(f"<span style='color:#7bed9f;'>**Per-Stage Optimal: {optimal_total:,.0f}** (saves {per_stage_savings:,.0f} vs uniform {best_uniform[0]})</span>", unsafe_allow_html=True)
    else:
        st.info("Click **Calculate** to see strategy cost comparison")

    # Simulation Results Section
    st.markdown("---")
    st.markdown("<div class='section-header'>SIMULATION RESULTS</div>", unsafe_allow_html=True)

    if 'sf_sim_result' in st.session_state:
        r = st.session_state.sf_sim_result
        st.markdown(f"""
        <div class='result-box'>
        <span class='star-gold'>SIMULATION: ★{r['current']} → ★{r['target']} ({r['iterations']} runs)</span><br>
        {'═' * 40}<br><br>
        <strong>MESO COSTS:</strong><br>
        &nbsp;&nbsp;Average: <span class='stat-value'>{r['avg_meso']:,.0f}</span><br>
        &nbsp;&nbsp;Median: <span class='stat-value'>{r['med_meso']:,.0f}</span><br>
        &nbsp;&nbsp;Min: <span class='success-green'>{r['min_meso']:,.0f}</span><br>
        &nbsp;&nbsp;Max: <span class='danger-red'>{r['max_meso']:,.0f}</span><br>
        &nbsp;&nbsp;95th %ile: <span class='warning-orange'>{r['p95_meso']:,.0f}</span><br><br>
        <strong>SCROLLS:</strong><br>
        &nbsp;&nbsp;Average: {r['avg_stones']:.0f}<br><br>
        <strong>ATTEMPTS:</strong><br>
        &nbsp;&nbsp;Average: {r['avg_attempts']:.1f}<br><br>
        <strong>DESTRUCTIONS:</strong><br>
        &nbsp;&nbsp;Average: <span class='danger-red'>{r['avg_destructions']:.2f}</span><br>
        &nbsp;&nbsp;Total across runs: {r['total_destructions']}<br><br>
        <strong>SUCCESS RATE:</strong> <span class='success-green'>{r['success_rate']:.1f}%</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Click **Simulate (1000x)** to run Monte Carlo simulation")

# Reference Tables (Right Column)
with col_ref:
    st.markdown("<div class='section-header'>STARFORCE TABLE</div>", unsafe_allow_html=True)

    # Headers
    st.markdown("""
    <div class='table-header' style='display:flex;'>
        <span style='width:50px;'>★</span>
        <span style='width:60px;'>Succ</span>
        <span style='width:50px;'>Dec</span>
        <span style='width:50px;'>Dest</span>
        <span style='width:70px;'>Meso</span>
    </div>
    """, unsafe_allow_html=True)

    # Show destruction zone (15-24)
    for stage in range(15, 25):
        if stage not in STARFORCE_TABLE:
            continue
        d = STARFORCE_TABLE[stage]
        dec_color = "#ff6b6b" if d.decrease_rate > 0 else "#888"
        dest_color = "#ff4757" if d.destroy_rate > 0 else "#888"

        st.markdown(f"""
        <div class='table-row' style='display:flex; font-family:monospace; font-size:12px;'>
            <span style='width:50px; color:#ffd700;'>★{stage}</span>
            <span style='width:60px; color:#7bed9f;'>{d.success_rate*100:.1f}%</span>
            <span style='width:50px; color:{dec_color};'>{d.decrease_rate*100:.0f}%</span>
            <span style='width:50px; color:{dest_color};'>{d.destroy_rate*100:.1f}%</span>
            <span style='width:70px; color:#ccc;'>{d.meso//1000}k</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("<div class='section-header'>AMPLIFICATION TABLE</div>", unsafe_allow_html=True)

    # Headers
    st.markdown("""
    <div class='table-header' style='display:flex;'>
        <span style='width:60px;'>Stars</span>
        <span style='width:80px;'>Main</span>
        <span style='width:80px;'>Sub</span>
    </div>
    """, unsafe_allow_html=True)

    # Key milestones
    for stars in [0, 5, 10, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]:
        main_m = get_amplify_multiplier(stars, is_sub=False)
        sub_m = get_amplify_multiplier(stars, is_sub=True)

        st.markdown(f"""
        <div class='table-row' style='display:flex; font-family:monospace; font-size:12px;'>
            <span style='width:60px; color:#ffd700;'>★{stars}</span>
            <span style='width:80px; color:#4a9eff;'>{main_m:.1f}x</span>
            <span style='width:80px; color:#ff9f43;'>{sub_m:.2f}x</span>
        </div>
        """, unsafe_allow_html=True)

    # Additional info
    st.markdown("---")
    st.markdown("<div class='section-header'>PROTECTION INFO</div>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size:12px; color:#ccc;'>
    <strong>Decrease Mitigation:</strong><br>
    &nbsp;&nbsp;• +100% cost<br>
    &nbsp;&nbsp;• Sets decrease chance to 0%<br><br>
    <strong>Destruction Mitigation:</strong><br>
    &nbsp;&nbsp;• +100% cost<br>
    &nbsp;&nbsp;• Halves destruction chance<br><br>
    <strong>Both Protections:</strong><br>
    &nbsp;&nbsp;• +200% cost (3x total)<br>
    &nbsp;&nbsp;• Best for high stars (20+)
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("<div class='section-header'>RECOMMENDATIONS</div>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size:12px; color:#ccc;'>
    <span style='color:#7bed9f;'>★12 → ★17:</span> No Protection<br>
    <span style='color:#ff9f43;'>★12 → ★18:</span> No Protection<br>
    <span style='color:#ff9f43;'>★12 → ★19+:</span> Decrease or Both<br>
    <span style='color:#ff6b6b;'>★12 → ★20+:</span> Both (recommended)<br>
    <span style='color:#ff6b6b;'>★12 → ★22+:</span> Both (essential)<br>
    <span style='color:#ff6b6b;'>★12 → ★25:</span> Both (saves 90%+)
    </div>
    """, unsafe_allow_html=True)
