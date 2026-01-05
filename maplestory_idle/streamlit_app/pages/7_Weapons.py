"""
Weapons Page
Track weapon ATK% bonuses.
"""
import streamlit as st
from utils.data_manager import save_user_data

st.set_page_config(page_title="Weapons", page_icon="🏹", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data


def auto_save():
    save_user_data(st.session_state.username, data)


st.title("🏹 Weapons")
st.markdown("Track your weapon inventory and ATK% bonuses.")

st.info("""
**How Weapon ATK% Works:**
- Each weapon in your inventory provides an ATK% bonus
- These bonuses stack additively
- Higher tier weapons provide more ATK%
""")

# Initialize weapons if needed
if not data.weapons:
    data.weapons = {}

# Add new weapon
st.subheader("Add Weapon")

col1, col2, col3 = st.columns([3, 2, 1])

with col1:
    new_weapon_name = st.text_input("Weapon Name", placeholder="e.g., Maple Bow +10")

with col2:
    new_weapon_atk = st.number_input("ATK %", min_value=0.0, max_value=50.0, value=0.0, step=0.5)

with col3:
    st.markdown("<br>", unsafe_allow_html=True)  # Spacing
    if st.button("Add Weapon"):
        if new_weapon_name:
            weapon_id = f"weapon_{len(data.weapons) + 1}"
            data.weapons[weapon_id] = {
                'name': new_weapon_name,
                'atk_pct': new_weapon_atk
            }
            auto_save()
            st.rerun()
        else:
            st.warning("Please enter a weapon name")

st.divider()

# List existing weapons
st.subheader("Weapon Inventory")

if data.weapons:
    total_atk_pct = 0.0

    for weapon_id, weapon in list(data.weapons.items()):
        col1, col2, col3 = st.columns([3, 2, 1])

        with col1:
            st.text(weapon.get('name', 'Unknown'))

        with col2:
            new_atk = st.number_input(
                "ATK %",
                min_value=0.0,
                max_value=50.0,
                value=float(weapon.get('atk_pct', 0)),
                step=0.5,
                key=f"edit_atk_{weapon_id}",
                label_visibility="collapsed"
            )
            if new_atk != weapon.get('atk_pct'):
                weapon['atk_pct'] = new_atk
                auto_save()

        with col3:
            if st.button("🗑️", key=f"del_{weapon_id}"):
                del data.weapons[weapon_id]
                auto_save()
                st.rerun()

        total_atk_pct += weapon.get('atk_pct', 0)

    st.divider()
    st.metric("Total Weapon ATK %", f"+{total_atk_pct:.1f}%")

else:
    st.info("No weapons added yet. Add weapons above to track their ATK% bonuses.")

st.divider()

# Summary
st.subheader("Weapon Summary")

if data.weapons:
    summary_data = [
        {"Weapon": w.get('name', ''), "ATK %": f"+{w.get('atk_pct', 0):.1f}%"}
        for w in data.weapons.values()
    ]
    st.dataframe(summary_data, width='stretch', hide_index=True)
