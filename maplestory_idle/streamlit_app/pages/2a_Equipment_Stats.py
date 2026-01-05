"""
Equipment Stats & Starforce Page
Manage equipment base stats, starforce levels, calculator, and simulator.
Matches the original Tkinter app starforce tab.
"""
import streamlit as st
import random
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.data_manager import save_user_data, EQUIPMENT_SLOTS
from equipment import STARFORCE_TABLE, get_amplify_multiplier, calculate_starforce_expected_cost
from starforce_optimizer import (
    find_optimal_per_stage_strategy,
    find_optimal_strategy,
    MESO_TO_DIAMOND,
    SCROLL_DIAMOND_COST,
)

st.set_page_config(page_title="Equipment Stats", page_icon="⭐", layout="wide")

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
    .stat-row {
        display: flex;
        justify-content: space-between;
        padding: 4px 0;
        border-bottom: 1px solid #333;
        font-family: monospace;
    }
    .stat-label { color: #aaa; }
    .stat-value { color: #66ff66; font-weight: bold; }
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
</style>
""", unsafe_allow_html=True)

# Initialize session - redirect if not logged in
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first")
    st.switch_page("app.py")
    st.stop()

if 'user_data' not in st.session_state or st.session_state.user_data is None:
    st.warning("No user data found. Please login.")
    st.switch_page("app.py")
    st.stop()

data = st.session_state.user_data

# Constants
RARITY_COLORS = {
    "Normal": "#888", "Epic": "#9d65c9", "Unique": "#ff9f43",
    "Legendary": "#4a9eff", "Mystic": "#ff6b6b", "Ancient": "#ffd700",
}
RARITY_OPTIONS = ["Normal", "Epic", "Unique", "Legendary", "Mystic", "Ancient"]

SLOT_THIRD_STAT = {
    "hat": "Defense", "top": "Defense", "bottom": "Accuracy", "gloves": "Accuracy",
    "shoes": "Max MP", "belt": "Max MP", "shoulder": "Evasion", "cape": "Evasion",
    "ring": "Main Stat", "necklace": "Main Stat", "face": "Main Stat",
}

SPECIAL_STAT_OPTIONS = {"damage_pct": "Damage %", "all_skills": "All Skills", "final_damage": "Final Damage %"}

# Diamond costs for conversion
MESO_TO_DIAMOND = 0.00001  # 100k meso = 1 diamond
SCROLL_DIAMOND_COST = 50   # Each scroll ~50 diamonds


def ensure_item_fields(item: dict) -> dict:
    """Ensure all item fields exist."""
    defaults = {
        'name': '', 'rarity': 'Normal', 'tier': 1, 'stars': 0, 'is_special': False,
        'base_attack': 0, 'base_max_hp': 0, 'base_third_stat': 0,
        'sub_boss_damage': 0, 'sub_normal_damage': 0, 'sub_crit_rate': 0,
        'sub_crit_damage': 0, 'sub_attack_flat': 0,
        'sub_skill_1st': 0, 'sub_skill_2nd': 0, 'sub_skill_3rd': 0, 'sub_skill_4th': 0,
        'special_stat_type': 'damage_pct', 'special_stat_value': 0,
    }
    for k, v in defaults.items():
        if k not in item:
            item[k] = v
    return item


def auto_save():
    save_user_data(st.session_state.username, data)


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
# PAGE LAYOUT - Tabs for Equipment and Starforce
# ============================================================================

st.title("⭐ Equipment & Starforce")

tab_equip, tab_starforce = st.tabs(["Equipment Stats", "Starforce Calculator"])

# ============================================================================
# TAB 1: EQUIPMENT STATS
# ============================================================================
with tab_equip:
    # Ensure all slots have data
    for slot in EQUIPMENT_SLOTS:
        if slot not in data.equipment_items:
            data.equipment_items[slot] = {}
        data.equipment_items[slot] = ensure_item_fields(data.equipment_items[slot])

    if 'selected_equip_stat_slot' not in st.session_state:
        st.session_state.selected_equip_stat_slot = EQUIPMENT_SLOTS[0]

    col_list, col_editor = st.columns([1, 1.5])

    # LEFT: Equipment List
    with col_list:
        st.markdown("<div class='section-header'>Equipment List</div>", unsafe_allow_html=True)

        # Calculate totals
        total_attack = total_hp = total_boss = total_normal = total_cr = total_cd = 0
        for slot in EQUIPMENT_SLOTS:
            item = data.equipment_items.get(slot, {})
            stars = int(item.get('stars', 0))
            main_mult = get_amplify_multiplier(stars, is_sub=False)
            sub_mult = get_amplify_multiplier(stars, is_sub=True)
            total_attack += item.get('base_attack', 0) * main_mult
            total_hp += item.get('base_max_hp', 0) * main_mult
            total_boss += item.get('sub_boss_damage', 0) * sub_mult
            total_normal += item.get('sub_normal_damage', 0) * sub_mult
            total_cr += item.get('sub_crit_rate', 0) * sub_mult
            total_cd += item.get('sub_crit_damage', 0) * sub_mult

        # Equipment rows
        for slot in EQUIPMENT_SLOTS:
            item = data.equipment_items.get(slot, {})
            name = item.get('name', slot.title()) or slot.title()
            rarity = item.get('rarity', 'Normal')
            stars = item.get('stars', 0)
            rarity_color = RARITY_COLORS.get(rarity, "#888")

            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                if st.button(f"{slot.title()}", key=f"slot_{slot}", use_container_width=True):
                    st.session_state.selected_equip_stat_slot = slot
                    st.rerun()
            with col2:
                st.markdown(f"<span style='color:{rarity_color};font-size:12px;'>{name[:12]}</span>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<span style='color:#ffd700;'>★{stars}</span>", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("<div class='section-header'>Total Stats (with SF)</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style='font-family:monospace; font-size:12px;'>
        <div class='stat-row'><span class='stat-label'>Attack:</span> <span class='stat-value'>{total_attack:,.0f}</span></div>
        <div class='stat-row'><span class='stat-label'>Max HP:</span> <span class='stat-value'>{total_hp:,.0f}</span></div>
        <div class='stat-row'><span class='stat-label'>Boss Dmg:</span> <span class='stat-value'>{total_boss:.1f}%</span></div>
        <div class='stat-row'><span class='stat-label'>Normal Dmg:</span> <span class='stat-value'>{total_normal:.1f}%</span></div>
        <div class='stat-row'><span class='stat-label'>Crit Rate:</span> <span class='stat-value'>{total_cr:.1f}%</span></div>
        <div class='stat-row'><span class='stat-label'>Crit Dmg:</span> <span class='stat-value'>{total_cd:.1f}%</span></div>
        </div>
        """, unsafe_allow_html=True)

    # RIGHT: Equipment Editor
    with col_editor:
        selected_slot = st.session_state.selected_equip_stat_slot
        item = data.equipment_items[selected_slot]

        st.markdown(f"<div class='section-header'>Edit: {selected_slot.title()}</div>", unsafe_allow_html=True)

        # Basic info
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("Name", value=item.get('name', ''), key="eq_name")
            if new_name != item.get('name'):
                item['name'] = new_name
                auto_save()
        with col2:
            rarity_idx = RARITY_OPTIONS.index(item.get('rarity', 'Normal')) if item.get('rarity') in RARITY_OPTIONS else 0
            new_rarity = st.selectbox("Rarity", RARITY_OPTIONS, index=rarity_idx, key="eq_rarity")
            if new_rarity != item.get('rarity'):
                item['rarity'] = new_rarity
                auto_save()

        col1, col2 = st.columns(2)
        with col1:
            tiers = [4, 3, 2, 1]
            tier_idx = tiers.index(item.get('tier', 4)) if item.get('tier', 4) in tiers else 0
            new_tier = st.selectbox("Tier", tiers, index=tier_idx, key="eq_tier")
            if new_tier != item.get('tier'):
                item['tier'] = new_tier
                auto_save()
        with col2:
            new_stars = st.slider("Stars", 0, 25, int(item.get('stars', 0)), key="eq_stars")
            if new_stars != item.get('stars'):
                item['stars'] = new_stars
                auto_save()

        main_mult = get_amplify_multiplier(new_stars, is_sub=False)
        sub_mult = get_amplify_multiplier(new_stars, is_sub=True)
        st.caption(f"Main Amplify: +{(main_mult-1)*100:.0f}% | Sub Amplify: +{(sub_mult-1)*100:.0f}%")

        st.markdown("---")
        st.markdown("**Main Stats** (Main Amplify)")

        col1, col2 = st.columns(2)
        with col1:
            new_atk = st.number_input("Base Attack", 0, 999999, int(item.get('base_attack', 0)), key="eq_atk")
            if new_atk != item.get('base_attack'):
                item['base_attack'] = new_atk
                auto_save()
        with col2:
            st.metric("After SF", f"{new_atk * main_mult:,.0f}")

        col1, col2 = st.columns(2)
        with col1:
            new_hp = st.number_input("Base Max HP", 0, 999999, int(item.get('base_max_hp', 0)), key="eq_hp")
            if new_hp != item.get('base_max_hp'):
                item['base_max_hp'] = new_hp
                auto_save()
        with col2:
            st.metric("After SF", f"{new_hp * main_mult:,.0f}")

        third_label = SLOT_THIRD_STAT.get(selected_slot, "Third Stat")
        col1, col2 = st.columns(2)
        with col1:
            new_third = st.number_input(f"Base {third_label}", 0, 999999, int(item.get('base_third_stat', 0)), key="eq_third")
            if new_third != item.get('base_third_stat'):
                item['base_third_stat'] = new_third
                auto_save()
        with col2:
            st.metric("After SF", f"{new_third * main_mult:,.0f}")

        st.markdown("---")
        st.markdown("**Sub Stats** (Sub Amplify)")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            new_boss = st.number_input("Boss%", 0.0, 100.0, float(item.get('sub_boss_damage', 0)), step=0.1, key="eq_boss")
            if new_boss != item.get('sub_boss_damage'):
                item['sub_boss_damage'] = new_boss
                auto_save()
        with col2:
            new_normal = st.number_input("Normal%", 0.0, 100.0, float(item.get('sub_normal_damage', 0)), step=0.1, key="eq_normal")
            if new_normal != item.get('sub_normal_damage'):
                item['sub_normal_damage'] = new_normal
                auto_save()
        with col3:
            new_cr = st.number_input("CR%", 0.0, 100.0, float(item.get('sub_crit_rate', 0)), step=0.1, key="eq_cr")
            if new_cr != item.get('sub_crit_rate'):
                item['sub_crit_rate'] = new_cr
                auto_save()
        with col4:
            new_cd = st.number_input("CD%", 0.0, 100.0, float(item.get('sub_crit_damage', 0)), step=0.1, key="eq_cd")
            if new_cd != item.get('sub_crit_damage'):
                item['sub_crit_damage'] = new_cd
                auto_save()

        st.caption(f"After SF: Boss {new_boss*sub_mult:.1f}% | Normal {new_normal*sub_mult:.1f}% | CR {new_cr*sub_mult:.1f}% | CD {new_cd*sub_mult:.1f}%")


# ============================================================================
# TAB 2: STARFORCE CALCULATOR
# ============================================================================
with tab_starforce:
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
            if st.button("Calculate", type="primary", use_container_width=True):
                if target_stars <= current_stars:
                    st.error("Target must be higher than current!")
                else:
                    # Use optimal per-stage strategy
                    stage_names, result = find_optimal_per_stage_strategy(current_stars, target_stars)
                    _, _, all_results = find_optimal_strategy(current_stars, target_stars)

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
                    }

        with col2:
            sim_btn = st.button("Simulate (1000x)", use_container_width=True)
            if sim_btn:
                if target_stars <= current_stars:
                    st.error("Target must be higher than current!")
                else:
                    with st.spinner("Running simulation..."):
                        # Get optimal strategies first
                        stage_names, _ = find_optimal_per_stage_strategy(current_stars, target_stars)
                        result = simulate_starforce(current_stars, target_stars, stage_names, 1000)
                        st.session_state.sf_sim_result = result
                        st.session_state.sf_sim_result['current'] = current_stars
                        st.session_state.sf_sim_result['target'] = target_stars
                        st.session_state.sf_sim_result['stage_names'] = stage_names

        # Expected Costs Display
        st.markdown("---")
        st.markdown("**EXPECTED COSTS**")

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
            st.info("Click Calculate to see expected costs")

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
            st.info("Click 'Calculate' to see optimal strategy")

        # Simulation Results
        st.markdown("---")
        st.markdown("**SIMULATION RESULTS**")

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
            <strong>STONES:</strong><br>
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
            st.info("Click 'Simulate (1000x)' to run Monte Carlo simulation")

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
