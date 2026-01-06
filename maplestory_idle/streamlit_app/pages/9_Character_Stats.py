"""
Character Stats Page
View aggregated stats from all sources with stat comparison and manual adjustments.
Enter your actual in-game values to identify gaps and fine-tune calculations.

Uses the shared aggregate_stats function from dps_calculator for consistency.
"""
import streamlit as st
from utils.data_manager import save_user_data
from utils.dps_calculator import (
    aggregate_stats as shared_aggregate_stats,
    calculate_dps as shared_calculate_dps,
    calculate_effective_defense_pen_with_sources,
    calculate_effective_attack_speed_with_sources,
)

st.set_page_config(page_title="Character Stats", page_icon="S", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

# Baselines (game defaults)
BASE_MIN_DMG = 60.0
BASE_MAX_DMG = 100.0
BASE_CRIT_DMG = 30.0
BASE_CRIT_RATE = 5.0

# Manual adjustment stat keys with display names
MANUAL_STATS = [
    ("flat_dex", "DEX (Flat)", False),
    ("dex_percent", "DEX %", True),
    ("damage_percent", "Damage %", True),
    ("boss_damage", "Boss Damage %", True),
    ("normal_damage", "Normal Damage %", True),
    ("crit_rate", "Crit Rate %", True),
    ("crit_damage", "Crit Damage %", True),
    ("defense_pen", "Defense Pen %", True),
    ("final_damage", "Final Damage %", True),
    ("base_attack", "Attack (Base)", False),
    ("attack_speed", "Attack Speed %", True),
    ("min_dmg_mult", "Min Dmg Mult %", True),
    ("max_dmg_mult", "Max Dmg Mult %", True),
]


def auto_save():
    save_user_data(st.session_state.username, data)


def get_stats_from_shared():
    """
    Get stats using the shared aggregate_stats function.
    Returns stats dict compatible with this page's display format.
    """
    # Get raw stats from shared function
    raw_stats = shared_aggregate_stats(data)

    # Convert to this page's expected format
    stats = {
        "flat_dex": raw_stats.get('flat_dex', 0),
        "dex_percent": raw_stats.get('dex_percent', 0),
        "damage_percent": raw_stats.get('damage_percent', 0),
        "boss_damage": raw_stats.get('boss_damage', 0),
        "normal_damage": raw_stats.get('normal_damage', 0),
        "crit_rate": raw_stats.get('crit_rate', 0) + BASE_CRIT_RATE,  # Add baseline
        "crit_damage": raw_stats.get('crit_damage', 0) + BASE_CRIT_DMG,  # Add baseline
        "base_attack": raw_stats.get('base_attack', 0),
        "min_dmg_mult": raw_stats.get('min_dmg_mult', 0) + BASE_MIN_DMG,  # Add baseline
        "max_dmg_mult": raw_stats.get('max_dmg_mult', 0) + BASE_MAX_DMG,  # Add baseline
        "all_skills": raw_stats.get('all_skills', 0),
    }

    # Calculate defense pen total from sources
    def_pen_sources = raw_stats.get('defense_pen_sources', [])
    if def_pen_sources:
        total_def_pen, _ = calculate_effective_defense_pen_with_sources(def_pen_sources)
        stats["defense_pen"] = total_def_pen * 100  # Convert to percentage
    else:
        stats["defense_pen"] = 0

    # Calculate attack speed total from sources
    atk_spd_sources = raw_stats.get('attack_speed_sources', [])
    if atk_spd_sources:
        total_atk_spd, _ = calculate_effective_attack_speed_with_sources(atk_spd_sources)
        stats["attack_speed"] = total_atk_spd
    else:
        stats["attack_speed"] = 0

    # Calculate final damage total from sources (multiplicative)
    fd_sources = raw_stats.get('final_damage_sources', [])
    if fd_sources:
        fd_mult = 1.0
        for fd in fd_sources:
            fd_mult *= (1 + fd)
        stats["final_damage"] = (fd_mult - 1) * 100  # Convert to percentage
    else:
        stats["final_damage"] = 0

    return stats, raw_stats


def get_final_stats(calculated_stats):
    """Apply manual adjustments to calculated stats."""
    final = calculated_stats.copy()
    adj = data.manual_adjustments or {}

    for stat_key, _, _ in MANUAL_STATS:
        final[stat_key] = final.get(stat_key, 0) + adj.get(stat_key, 0)

    return final


st.title("Character Stats")
st.markdown("View aggregated stats and fine-tune with manual adjustments.")

# Link to Guild Skills page
st.info("⚔️ Configure guild skills on the **Guild Skills** page in the sidebar.")

st.divider()

# Initialize manual adjustments if needed
if not data.manual_adjustments:
    data.manual_adjustments = {stat_key: 0.0 for stat_key, _, _ in MANUAL_STATS}

# Quick summary
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Character Level", data.character_level)
with col2:
    st.metric("All Skills", f"+{data.all_skills}")
with col3:
    st.metric("Combat Mode", data.combat_mode.replace("_", " ").title())
with col4:
    st.metric("Chapter", data.chapter.replace("Chapter ", "Ch. "))

st.divider()

# Get calculated stats using shared function
calculated_stats, raw_stats = get_stats_from_shared()
final_stats = get_final_stats(calculated_stats)

tab1, tab2, tab3 = st.tabs(["Stat Comparison", "Manual Adjustments", "Summary"])

# ============================================================================
# TAB 1: STAT COMPARISON
# ============================================================================
with tab1:
    st.markdown("**Compare Calculated vs Actual** - Enter your in-game values to find gaps")

    # Initialize actual stats if not present
    if 'actual_stats' not in st.session_state:
        st.session_state.actual_stats = {}

    # Comparison table
    col_calc, col_adj, col_final, col_actual, col_gap = st.columns([1.5, 1, 1.5, 1.5, 1])

    with col_calc:
        st.markdown("**Calculated**")
    with col_adj:
        st.markdown("**Adjustment**")
    with col_final:
        st.markdown("**Final**")
    with col_actual:
        st.markdown("**Actual (In-Game)**")
    with col_gap:
        st.markdown("**Gap**")

    for stat_key, display_name, is_pct in MANUAL_STATS:
        calc_val = calculated_stats.get(stat_key, 0)
        adj_val = data.manual_adjustments.get(stat_key, 0)
        final_val = final_stats.get(stat_key, 0)

        col_calc, col_adj, col_final, col_actual, col_gap = st.columns([1.5, 1, 1.5, 1.5, 1])

        with col_calc:
            if is_pct:
                st.text(f"{display_name}: {calc_val:.2f}%")
            else:
                st.text(f"{display_name}: {calc_val:,.0f}")

        with col_adj:
            if adj_val != 0:
                st.text(f"{adj_val:+.1f}")
            else:
                st.text("-")

        with col_final:
            if is_pct:
                st.text(f"{final_val:.2f}%")
            else:
                st.text(f"{final_val:,.0f}")

        with col_actual:
            actual_key = f"actual_{stat_key}"
            current_actual = st.session_state.actual_stats.get(stat_key, final_val)
            new_actual = st.number_input(
                f"Actual {stat_key}",
                value=float(current_actual),
                step=0.1 if is_pct else 1.0,
                key=actual_key,
                label_visibility="collapsed"
            )
            st.session_state.actual_stats[stat_key] = new_actual

        with col_gap:
            gap = new_actual - final_val
            if abs(gap) > 0.01:
                color = "red" if gap < 0 else "green"
                st.markdown(f":{color}[{gap:+.1f}]")
            else:
                st.text("0")

    st.divider()

    # Action buttons
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Auto-Fill Adjustments from Gap", key="auto_fill"):
            for stat_key, _, _ in MANUAL_STATS:
                actual = st.session_state.actual_stats.get(stat_key, 0)
                calc = calculated_stats.get(stat_key, 0)
                data.manual_adjustments[stat_key] = actual - calc
            auto_save()
            st.rerun()

    with col2:
        if st.button("Reset All Adjustments", key="reset_adj"):
            for stat_key, _, _ in MANUAL_STATS:
                data.manual_adjustments[stat_key] = 0.0
            auto_save()
            st.rerun()

    with col3:
        if st.button("Copy Final to Actual", key="copy_final"):
            for stat_key, _, _ in MANUAL_STATS:
                st.session_state.actual_stats[stat_key] = final_stats.get(stat_key, 0)
            st.rerun()

# ============================================================================
# TAB 2: MANUAL ADJUSTMENTS
# ============================================================================
with tab2:
    st.markdown("**Manual Adjustments** - Fine-tune stats that don't match in-game values")
    st.caption("These adjustments are added to the calculated stats to produce final values.")

    col1, col2 = st.columns(2)

    for idx, (stat_key, display_name, is_pct) in enumerate(MANUAL_STATS):
        current_adj = data.manual_adjustments.get(stat_key, 0)

        with col1 if idx < len(MANUAL_STATS) // 2 else col2:
            new_adj = st.number_input(
                display_name,
                value=float(current_adj),
                step=0.1 if is_pct else 1.0,
                key=f"adj_{stat_key}",
                help=f"Adjustment for {display_name}"
            )

            if new_adj != current_adj:
                data.manual_adjustments[stat_key] = new_adj
                auto_save()

    st.divider()

    # Quick actions
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Reset All to Zero", key="reset_all"):
            for stat_key, _, _ in MANUAL_STATS:
                data.manual_adjustments[stat_key] = 0.0
            auto_save()
            st.rerun()

    # Show active adjustments summary
    active = [(k, v) for k, v, _ in MANUAL_STATS if data.manual_adjustments.get(k, 0) != 0]
    if active:
        st.markdown("**Active Adjustments:**")
        adj_summary = ", ".join([f"{k}: {data.manual_adjustments[k]:+.1f}" for k, _, _ in MANUAL_STATS if data.manual_adjustments.get(k, 0) != 0])
        st.info(adj_summary)

# ============================================================================
# TAB 3: SUMMARY
# ============================================================================
with tab3:
    st.markdown("**Final Stats Summary** - Calculated + Adjustments")

    # Key stats
    st.markdown("### Key Combat Stats")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("DEX (Flat)", f"+{final_stats.get('flat_dex', 0):,.0f}")
        st.metric("DEX %", f"+{final_stats.get('dex_percent', 0):.2f}%")
        st.metric("Attack (Base)", f"+{final_stats.get('base_attack', 0):,.0f}")

    with col2:
        st.metric("Damage %", f"+{final_stats.get('damage_percent', 0):.2f}%")
        st.metric("Boss Damage %", f"+{final_stats.get('boss_damage', 0):.2f}%")
        st.metric("Normal Damage %", f"+{final_stats.get('normal_damage', 0):.2f}%")
        st.metric("Crit Damage %", f"+{final_stats.get('crit_damage', 0):.2f}%")

    with col3:
        st.metric("Defense Pen %", f"+{final_stats.get('defense_pen', 0):.2f}%")
        st.metric("Final Damage %", f"+{final_stats.get('final_damage', 0):.2f}%")
        st.metric("Crit Rate %", f"+{final_stats.get('crit_rate', 0):.2f}%")
        st.metric("Attack Speed %", f"+{final_stats.get('attack_speed', 0):.2f}%")

    st.divider()

    st.markdown("### Multiplier Stats")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Min Damage Mult %", f"+{final_stats.get('min_dmg_mult', 0):.2f}%")
    with col2:
        st.metric("Max Damage Mult %", f"+{final_stats.get('max_dmg_mult', 0):.2f}%")

    st.divider()

    # Defense Pen Breakdown
    def_pen_sources = raw_stats.get('defense_pen_sources', [])
    if def_pen_sources:
        st.markdown("### Defense Penetration Breakdown (Priority Order)")
        total_def_pen, breakdown = calculate_effective_defense_pen_with_sources(def_pen_sources)
        for source_name, raw_value, effective_gain in breakdown:
            display_name = source_name.replace('_', ' ').title()
            st.write(f"- **{display_name}**: {raw_value*100:.1f}% (effective: +{effective_gain*100:.1f}%)")
        st.write(f"**Total: {total_def_pen*100:.1f}%**")

    # Attack Speed Breakdown
    atk_spd_sources = raw_stats.get('attack_speed_sources', [])
    if atk_spd_sources:
        st.markdown("### Attack Speed Breakdown (Diminishing Returns)")
        total_atk_spd, breakdown = calculate_effective_attack_speed_with_sources(atk_spd_sources)
        for source_name, raw_value, effective_gain in breakdown:
            display_name = source_name.replace('_', ' ').title()
            st.write(f"- **{display_name}**: {raw_value:.1f}% (effective: +{effective_gain:.1f}%)")
        st.write(f"**Total: {total_atk_spd:.1f}%**")

    # Final Damage Sources
    fd_sources = raw_stats.get('final_damage_sources', [])
    if fd_sources:
        st.markdown("### Final Damage Sources (Multiplicative)")
        for i, fd in enumerate(fd_sources):
            st.write(f"- Source {i+1}: +{fd*100:.1f}%")

    st.divider()

    # Full stats table
    st.markdown("### All Stats Table")
    stats_table = []
    for stat_key, display_name, is_pct in MANUAL_STATS:
        calc = calculated_stats.get(stat_key, 0)
        adj = data.manual_adjustments.get(stat_key, 0)
        final = final_stats.get(stat_key, 0)

        if is_pct:
            stats_table.append({
                "Stat": display_name,
                "Calculated": f"{calc:.2f}%",
                "Adjustment": f"{adj:+.2f}%" if adj != 0 else "-",
                "Final": f"{final:.2f}%",
            })
        else:
            stats_table.append({
                "Stat": display_name,
                "Calculated": f"{calc:,.0f}",
                "Adjustment": f"{adj:+.0f}" if adj != 0 else "-",
                "Final": f"{final:,.0f}",
            })

    st.dataframe(stats_table, use_container_width=True, hide_index=True)

    st.divider()

    # Notes
    st.markdown("### Notes")
    st.info("""
**Baseline Values Included:**
- Min Damage Mult: +60% baseline
- Max Damage Mult: +100% baseline
- Crit Damage: +30% baseline
- Crit Rate: +5% baseline

**Manual Adjustments:**
Use the Stat Comparison tab to enter your actual in-game values.
Click "Auto-Fill Adjustments from Gap" to automatically calculate the adjustments needed.

**Stat Sources:**
Stats are aggregated from Equipment, Potentials, Hero Power, Maple Rank, Companions, Weapons, Artifacts, and Guild Skills.
    """)
