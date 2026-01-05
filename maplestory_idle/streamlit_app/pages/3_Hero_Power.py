"""
Hero Power Page
Configure hero power rerollable lines and passive stats.
"""
import streamlit as st
from utils.data_manager import save_user_data

st.set_page_config(page_title="Hero Power", page_icon="⚡", layout="wide")

# Check if logged in
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

# Hero Power stat options
HP_STATS = [
    "", "damage", "boss_damage", "crit_damage", "def_pen",
    "attack_pct", "min_dmg_mult", "max_dmg_mult", "main_stat_pct"
]

HP_TIERS = ["Common", "Rare", "Epic", "Unique", "Legendary", "Mystic"]

# Passive stat types
PASSIVE_STATS = [
    ("main_stat", "Main Stat", 0, 50),
    ("damage", "Damage %", 0, 50),
    ("attack", "Attack", 0, 50),
    ("hp", "Max HP", 0, 50),
    ("accuracy", "Accuracy", 0, 50),
    ("defense", "Defense", 0, 50),
]


def auto_save():
    """Save data after changes."""
    save_user_data(st.session_state.username, data)


st.title("⚡ Hero Power")
st.markdown("Configure your Hero Power ability lines and passive stats.")

tab1, tab2 = st.tabs(["🎯 Ability Lines", "📊 Passive Stats"])

with tab1:
    st.subheader("Rerollable Ability Lines")
    st.markdown("These are the 6 lines you can reroll with Hero Power medals.")

    # Ensure hero power lines exist
    for i in range(1, 7):
        line_key = f'line{i}'
        if line_key not in data.hero_power_lines:
            data.hero_power_lines[line_key] = {
                'stat': '',
                'value': 0.0,
                'tier': 'Common',
                'locked': False,
            }

    # Display lines in 2 columns
    col1, col2 = st.columns(2)

    for i in range(1, 7):
        line_key = f'line{i}'
        line = data.hero_power_lines[line_key]

        with col1 if i <= 3 else col2:
            st.markdown(f"### Line {i}")

            # Stat selection
            stat_index = HP_STATS.index(line.get('stat', '')) if line.get('stat', '') in HP_STATS else 0
            new_stat = st.selectbox(
                f"Stat Type",
                options=HP_STATS,
                index=stat_index,
                key=f"hp_stat_{i}",
                format_func=lambda x: x.replace("_", " ").title() if x else "---"
            )
            if new_stat != line.get('stat'):
                line['stat'] = new_stat
                auto_save()

            # Value
            new_value = st.number_input(
                f"Value (%)",
                min_value=0.0,
                max_value=50.0,
                value=float(line.get('value', 0)),
                step=0.5,
                key=f"hp_val_{i}"
            )
            if new_value != line.get('value'):
                line['value'] = new_value
                auto_save()

            # Tier
            tier_index = HP_TIERS.index(line.get('tier', 'Common')) if line.get('tier') in HP_TIERS else 0
            new_tier = st.selectbox(
                f"Tier",
                options=HP_TIERS,
                index=tier_index,
                key=f"hp_tier_{i}"
            )
            if new_tier != line.get('tier'):
                line['tier'] = new_tier
                auto_save()

            # Locked
            new_locked = st.checkbox(
                f"Locked",
                value=line.get('locked', False),
                key=f"hp_lock_{i}",
                help="Lock this line when rerolling"
            )
            if new_locked != line.get('locked'):
                line['locked'] = new_locked
                auto_save()

            st.divider()

    # Summary
    st.subheader("Lines Summary")
    summary_data = []
    for i in range(1, 7):
        line = data.hero_power_lines[f'line{i}']
        if line.get('stat') and line.get('value', 0) > 0:
            summary_data.append({
                "Line": i,
                "Stat": line['stat'].replace("_", " ").title(),
                "Value": f"{line['value']}%",
                "Tier": line.get('tier', 'Common'),
                "Locked": "🔒" if line.get('locked') else ""
            })

    if summary_data:
        st.dataframe(summary_data, width='stretch', hide_index=True)
    else:
        st.info("No ability lines configured yet.")

with tab2:
    st.subheader("Passive Stats (Leveled)")
    st.markdown("These stats are upgraded with gold, not rerolled.")

    # Ensure passive stats exist
    if not data.hero_power_passives:
        data.hero_power_passives = {stat[0]: 0 for stat in PASSIVE_STATS}

    col1, col2 = st.columns(2)

    for idx, (stat_key, stat_name, min_val, max_val) in enumerate(PASSIVE_STATS):
        with col1 if idx < 3 else col2:
            current_val = data.hero_power_passives.get(stat_key, 0)
            new_val = st.slider(
                stat_name,
                min_value=min_val,
                max_value=max_val,
                value=current_val,
                key=f"passive_{stat_key}"
            )
            if new_val != current_val:
                data.hero_power_passives[stat_key] = new_val
                auto_save()

    st.divider()

    # Passive summary
    st.subheader("Passive Stats Summary")
    passive_summary = []
    for stat_key, stat_name, _, _ in PASSIVE_STATS:
        level = data.hero_power_passives.get(stat_key, 0)
        if level > 0:
            passive_summary.append({
                "Stat": stat_name,
                "Level": level
            })

    if passive_summary:
        st.dataframe(passive_summary, width='stretch', hide_index=True)
    else:
        st.info("No passive stats leveled yet.")
