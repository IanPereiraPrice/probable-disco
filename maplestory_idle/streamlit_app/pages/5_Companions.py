"""
Companions Page
Configure companion equipment and levels.
"""
import streamlit as st
from utils.data_manager import save_user_data

st.set_page_config(page_title="Companions", page_icon="🐾", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

# Companion types by advancement
COMPANIONS = {
    "Basic": ["Puffram", "Jr. Boogie", "Orange Mushroom"],
    "1st Job": ["Blue Snail", "Slime", "Stump"],
    "2nd Job": ["Zombie Mushroom", "Stone Golem", "Wild Kargo"],
    "3rd Job": ["Taurospear", "Lycanthrope", "Dark Yeti"],
    "4th Job": ["Griffey", "Papulatus", "Zakum"]
}

ALL_COMPANIONS = [""] + [c for comps in COMPANIONS.values() for c in comps]


def auto_save():
    save_user_data(st.session_state.username, data)


st.title("🐾 Companions")
st.markdown("Configure your equipped companions and their levels.")

# Initialize equipped companions
if not data.companions_equipped:
    for i in range(7):
        data.companions_equipped[f'slot{i}'] = {'name': '', 'level': 1}

st.subheader("Equipped Companions")
st.markdown("You can equip up to 7 companions (1 main + 6 sub).")

# Main companion
st.markdown("### Main Companion (Slot 1)")
main_slot = data.companions_equipped.get('slot0', {'name': '', 'level': 1})

col1, col2 = st.columns([3, 1])
with col1:
    main_index = ALL_COMPANIONS.index(main_slot.get('name', '')) if main_slot.get('name', '') in ALL_COMPANIONS else 0
    new_main = st.selectbox(
        "Companion",
        options=ALL_COMPANIONS,
        index=main_index,
        key="main_comp",
        format_func=lambda x: x if x else "--- Empty ---"
    )
    if new_main != main_slot.get('name'):
        main_slot['name'] = new_main
        data.companions_equipped['slot0'] = main_slot
        auto_save()

with col2:
    new_level = st.number_input(
        "Level",
        min_value=1,
        max_value=50,
        value=main_slot.get('level', 1),
        key="main_level"
    )
    if new_level != main_slot.get('level'):
        main_slot['level'] = new_level
        data.companions_equipped['slot0'] = main_slot
        auto_save()

st.divider()

# Sub companions
st.markdown("### Sub Companions (Slots 2-7)")

sub_cols = st.columns(3)

for idx in range(1, 7):
    slot_key = f'slot{idx}'
    companion = data.companions_equipped.get(slot_key, {'name': '', 'level': 1})

    with sub_cols[(idx - 1) % 3]:
        st.markdown(f"**Slot {idx + 1}**")

        comp_index = ALL_COMPANIONS.index(companion.get('name', '')) if companion.get('name', '') in ALL_COMPANIONS else 0
        new_comp = st.selectbox(
            "Companion",
            options=ALL_COMPANIONS,
            index=comp_index,
            key=f"sub_comp_{idx}",
            format_func=lambda x: x if x else "--- Empty ---"
        )
        if new_comp != companion.get('name'):
            companion['name'] = new_comp
            data.companions_equipped[slot_key] = companion
            auto_save()

        new_lvl = st.number_input(
            "Level",
            min_value=1,
            max_value=50,
            value=companion.get('level', 1),
            key=f"sub_level_{idx}"
        )
        if new_lvl != companion.get('level'):
            companion['level'] = new_lvl
            data.companions_equipped[slot_key] = companion
            auto_save()

        st.markdown("---")

st.divider()

# Summary
st.subheader("Equipped Companions Summary")
summary = []
for idx in range(7):
    companion = data.companions_equipped.get(f'slot{idx}', {})
    if companion.get('name'):
        summary.append({
            "Slot": "Main" if idx == 0 else f"Sub {idx}",
            "Companion": companion.get('name', ''),
            "Level": companion.get('level', 1)
        })

if summary:
    st.dataframe(summary, width='stretch', hide_index=True)
else:
    st.info("No companions equipped yet.")
