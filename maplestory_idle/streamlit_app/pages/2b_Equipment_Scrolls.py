"""
Equipment Scrolls Page
Manage scroll bonuses (damage amp, flat attack, flat main stat) per equipment slot.
Independent system from starforce.
"""
import streamlit as st
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.data_manager import save_user_data, EQUIPMENT_SLOTS

st.set_page_config(page_title="Equipment Scrolls", page_icon="📜", layout="wide")

# CSS styling
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
    .scroll-row {
        background: #1e1e1e;
        padding: 8px 12px;
        margin: 4px 0;
        border-radius: 4px;
        border-left: 3px solid #4a9eff;
    }
    .scroll-row:hover { background: #2a2a2a; }
    .stat-total {
        font-size: 20px;
        font-weight: bold;
        color: #66ff66;
    }
    .stat-label {
        font-size: 12px;
        color: #888;
    }
    .total-box {
        background: #1a1a2e;
        padding: 12px;
        border-radius: 8px;
        text-align: center;
        margin: 4px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session - redirect if not logged in
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first")
    st.stop()

if 'user_data' not in st.session_state or st.session_state.user_data is None:
    st.warning("No user data found. Please login.")
    st.stop()

data = st.session_state.user_data

# Ensure equipment_scrolls exists in user data
if not hasattr(data, 'equipment_scrolls') or data.equipment_scrolls is None:
    data.equipment_scrolls = {}


def ensure_scroll_fields(scroll_data: dict) -> dict:
    """Ensure all scroll fields exist with defaults."""
    defaults = {
        'damage_amp': 0.0,      # Damage Amp %
        'flat_attack': 0,       # Flat Attack
        'flat_main_stat': 0,    # Flat Main Stat
    }
    for k, v in defaults.items():
        if k not in scroll_data:
            scroll_data[k] = v
    return scroll_data


def auto_save():
    """Save data and update timestamp."""
    save_user_data(st.session_state.username, data)
    st.session_state.last_scroll_save_time = datetime.now()


# Ensure all slots have scroll data
for slot in EQUIPMENT_SLOTS:
    if slot not in data.equipment_scrolls:
        data.equipment_scrolls[slot] = {}
    data.equipment_scrolls[slot] = ensure_scroll_fields(data.equipment_scrolls[slot])

# Page title
st.title("📜 Equipment Scrolls")
st.caption("Add scroll bonuses to equipment. Independent from starforce.")

# Calculate totals
total_damage_amp = sum(data.equipment_scrolls[slot].get('damage_amp', 0) for slot in EQUIPMENT_SLOTS)
total_flat_attack = sum(data.equipment_scrolls[slot].get('flat_attack', 0) for slot in EQUIPMENT_SLOTS)
total_flat_main_stat = sum(data.equipment_scrolls[slot].get('flat_main_stat', 0) for slot in EQUIPMENT_SLOTS)

# Totals section at top
st.markdown("<div class='section-header'>Total Scroll Stats</div>", unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"""
    <div class='total-box'>
        <div class='stat-total'>+{total_damage_amp:.1f}%</div>
        <div class='stat-label'>Damage Amp</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class='total-box'>
        <div class='stat-total'>+{total_flat_attack:,}</div>
        <div class='stat-label'>Flat Attack</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class='total-box'>
        <div class='stat-total'>+{total_flat_main_stat:,}</div>
        <div class='stat-label'>Flat Main Stat</div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# Equipment list with scroll inputs
st.markdown("<div class='section-header'>Scroll Stats by Equipment</div>", unsafe_allow_html=True)

# Save indicator
if 'last_scroll_save_time' in st.session_state:
    save_time = st.session_state.last_scroll_save_time
    st.caption(f"Last saved: {save_time.strftime('%H:%M:%S')}")

# Create a grid layout for equipment slots
for slot in EQUIPMENT_SLOTS:
    scroll_data = data.equipment_scrolls[slot]

    with st.container():
        st.markdown(f"<div class='scroll-row'><b>{slot.upper()}</b></div>", unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)

        with c1:
            new_dmg_amp = st.number_input(
                "Damage Amp %",
                min_value=0.0,
                max_value=100.0,
                value=float(scroll_data.get('damage_amp', 0)),
                step=0.5,
                key=f"scroll_dmg_{slot}",
                format="%.1f"
            )
            if new_dmg_amp != scroll_data.get('damage_amp', 0):
                scroll_data['damage_amp'] = new_dmg_amp
                auto_save()
                st.rerun()

        with c2:
            new_flat_atk = st.number_input(
                "Flat Attack",
                min_value=0,
                max_value=50000,
                value=int(scroll_data.get('flat_attack', 0)),
                step=100,
                key=f"scroll_atk_{slot}"
            )
            if new_flat_atk != scroll_data.get('flat_attack', 0):
                scroll_data['flat_attack'] = new_flat_atk
                auto_save()
                st.rerun()

        with c3:
            new_flat_stat = st.number_input(
                "Flat Main Stat",
                min_value=0,
                max_value=50000,
                value=int(scroll_data.get('flat_main_stat', 0)),
                step=100,
                key=f"scroll_stat_{slot}"
            )
            if new_flat_stat != scroll_data.get('flat_main_stat', 0):
                scroll_data['flat_main_stat'] = new_flat_stat
                auto_save()
                st.rerun()

st.divider()

# Quick actions
st.markdown("<div class='section-header'>Quick Actions</div>", unsafe_allow_html=True)

col_clear, col_copy = st.columns(2)

with col_clear:
    if st.button("Clear All Scrolls", type="secondary"):
        for slot in EQUIPMENT_SLOTS:
            data.equipment_scrolls[slot] = {'damage_amp': 0.0, 'flat_attack': 0, 'flat_main_stat': 0}
        auto_save()
        st.rerun()

with col_copy:
    st.caption("Scroll stats are saved automatically when changed.")
