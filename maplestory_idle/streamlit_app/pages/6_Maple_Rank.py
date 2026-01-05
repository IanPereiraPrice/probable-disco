"""
Maple Rank Page
Track Maple Rank progression and stat bonuses.
"""
import streamlit as st
from utils.data_manager import save_user_data

st.set_page_config(page_title="Maple Rank", page_icon="🍁", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

# Maple Rank stat types
MAPLE_RANK_STATS = [
    ("attack_speed", "Attack Speed %"),
    ("crit_rate", "Crit Rate %"),
    ("damage", "Damage %"),
    ("boss_damage", "Boss Damage %"),
    ("normal_damage", "Normal Damage %"),
    ("crit_damage", "Crit Damage %"),
    ("skill_damage", "Skill Damage %"),
    ("def_pen", "Defense Pen %"),
    ("min_dmg_mult", "Min Damage %"),
    ("max_dmg_mult", "Max Damage %"),
]


def auto_save():
    save_user_data(st.session_state.username, data)


st.title("🍁 Maple Rank")
st.markdown("Track your Maple Rank progression and stat bonuses.")

# Initialize if needed
if not data.maple_rank:
    data.maple_rank = {
        'current_stage': 1,
        'main_stat_level': 0,
        'special_main_stat': 0,
    }

col1, col2 = st.columns(2)

with col1:
    st.subheader("Stage Progress")

    # Current Stage
    new_stage = st.number_input(
        "Current Stage",
        min_value=1,
        max_value=30,
        value=data.maple_rank.get('current_stage', 1),
        help="Your highest unlocked Maple Rank stage"
    )
    if new_stage != data.maple_rank.get('current_stage'):
        data.maple_rank['current_stage'] = new_stage
        auto_save()

    # Main Stat Level within stage
    new_ms_level = st.number_input(
        "Main Stat Level (in current stage)",
        min_value=0,
        max_value=10,
        value=data.maple_rank.get('main_stat_level', 0),
        help="Progress within current stage (0-10)"
    )
    if new_ms_level != data.maple_rank.get('main_stat_level'):
        data.maple_rank['main_stat_level'] = new_ms_level
        auto_save()

    # Special Main Stat
    new_special = st.number_input(
        "Special Main Stat Points",
        min_value=0,
        max_value=160,
        value=data.maple_rank.get('special_main_stat', 0),
        help="Additional main stat from special rewards (0-160)"
    )
    if new_special != data.maple_rank.get('special_main_stat'):
        data.maple_rank['special_main_stat'] = new_special
        auto_save()

    st.divider()

    # Estimated main stat
    stage = data.maple_rank.get('current_stage', 1)
    ms_level = data.maple_rank.get('main_stat_level', 0)
    special = data.maple_rank.get('special_main_stat', 0)

    # Approximate main stat formula (simplified)
    base_main_stat = (stage - 1) * 100 + ms_level * 10 + special
    st.metric("Estimated Main Stat from Maple Rank", f"+{base_main_stat:,}")

with col2:
    st.subheader("Stat Bonuses")
    st.markdown("Configure your unlocked Maple Rank stat bonuses.")

    # Initialize stat levels
    if 'stat_levels' not in data.maple_rank:
        data.maple_rank['stat_levels'] = {}

    for stat_key, stat_name in MAPLE_RANK_STATS:
        current_level = data.maple_rank.get('stat_levels', {}).get(stat_key, 0)
        new_level = st.slider(
            stat_name,
            min_value=0,
            max_value=20,
            value=current_level,
            key=f"mr_stat_{stat_key}"
        )
        if new_level != current_level:
            if 'stat_levels' not in data.maple_rank:
                data.maple_rank['stat_levels'] = {}
            data.maple_rank['stat_levels'][stat_key] = new_level
            auto_save()

st.divider()

# Summary
st.subheader("Maple Rank Summary")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Current Stage", data.maple_rank.get('current_stage', 1))

with col2:
    st.metric("Stage Progress", f"{data.maple_rank.get('main_stat_level', 0)}/10")

with col3:
    st.metric("Special Main Stat", data.maple_rank.get('special_main_stat', 0))

# Stat bonuses summary
stat_levels = data.maple_rank.get('stat_levels', {})
active_stats = [(name, stat_levels.get(key, 0)) for key, name in MAPLE_RANK_STATS if stat_levels.get(key, 0) > 0]

if active_stats:
    st.markdown("**Active Stat Bonuses:**")
    summary_data = [{"Stat": name, "Level": level} for name, level in active_stats]
    st.dataframe(summary_data, width='stretch', hide_index=True)
