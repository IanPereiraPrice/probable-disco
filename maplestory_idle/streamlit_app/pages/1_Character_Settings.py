"""
Character Settings Page
Configure character level, combat mode, and chapter.
All Skills bonus is auto-calculated from equipment sources.
"""
import streamlit as st
from utils.data_manager import save_user_data, export_user_data_csv, import_user_data_csv, EQUIPMENT_SLOTS
from constants import ENEMY_DEFENSE_VALUES
from equipment import get_amplify_multiplier

st.set_page_config(page_title="Character Settings", page_icon="⚔️", layout="wide")

# Check if logged in
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data


def auto_save():
    """Save data after changes."""
    save_user_data(st.session_state.username, data)


def calculate_all_skills() -> int:
    """
    Calculate total All Skills bonus from all equipment sources.

    Sources:
    1. Equipment potentials (regular and bonus) with 'all_skills' stat
       - Potentials are NOT affected by starforce
    2. Equipment special stats (sub stats) where special_stat_type == 'all_skills'
       - Sub stats ARE affected by starforce sub amplify multiplier

    Returns:
        Total All Skills bonus as an integer
    """
    total = 0

    for slot in EQUIPMENT_SLOTS:
        # Get equipment item for starforce multiplier (sub stats only)
        item = data.equipment_items.get(slot, {})
        stars = int(item.get('stars', 0))
        sub_mult = get_amplify_multiplier(stars, is_sub=True)

        # Check potentials (regular and bonus) - NOT affected by starforce
        pots = data.equipment_potentials.get(slot, {})
        for prefix in ['', 'bonus_']:
            for i in range(1, 4):
                stat = pots.get(f'{prefix}line{i}_stat', '')
                value = pots.get(f'{prefix}line{i}_value', 0)
                if stat == 'all_skills' and value > 0:
                    total += int(value)

        # Check special sub stats (only if item is marked as special)
        # Sub stats ARE affected by starforce sub amplify multiplier
        if item.get('is_special', False):
            special_type = item.get('special_stat_type', '')
            special_value = item.get('special_stat_value', 0)
            if special_type == 'all_skills' and special_value > 0:
                total += int(special_value * sub_mult)

    return total


st.title("⚔️ Character Settings")
st.markdown("Configure your character's basic information.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Basic Info")

    # Character Level
    new_level = st.number_input(
        "Character Level",
        min_value=1,
        max_value=300,
        value=data.character_level,
        step=1,
        help="Your character's current level (1-300)"
    )
    if new_level != data.character_level:
        data.character_level = new_level
        auto_save()

    # All Skills (calculated automatically)
    calculated_all_skills = calculate_all_skills()
    st.metric(
        "All Skills Bonus",
        f"+{calculated_all_skills}",
        help="Auto-calculated from equipment potentials and special sub stats"
    )
    st.caption("*From ring/necklace potentials + special sub stats*")

    # Update stored value if different
    if calculated_all_skills != data.all_skills:
        data.all_skills = calculated_all_skills
        auto_save()

    st.divider()

    # Medal/Costume Main Stat
    st.subheader("Equipment Sets")

    medal_val = data.equipment_sets.get('medal', 0)
    costume_val = data.equipment_sets.get('costume', 0)

    new_medal = st.number_input(
        "Medal Main Stat",
        min_value=0,
        max_value=1500,
        value=medal_val,
        step=10,
        help="Main stat from medal inventory effect (0-1500)"
    )
    if new_medal != medal_val:
        data.equipment_sets['medal'] = new_medal
        auto_save()

    new_costume = st.number_input(
        "Costume Main Stat",
        min_value=0,
        max_value=1500,
        value=costume_val,
        step=10,
        help="Main stat from costume inventory effect (0-1500)"
    )
    if new_costume != costume_val:
        data.equipment_sets['costume'] = new_costume
        auto_save()

    total_set_stat = new_medal + new_costume
    st.metric("Total from Sets", f"+{total_set_stat:,}")

with col2:
    st.subheader("Combat Settings")

    # Combat Mode
    combat_modes = {
        "stage": "Stage (Mixed) - 60% normal, 40% boss",
        "boss": "Boss (Single) - 100% boss damage",
        "world_boss": "World Boss - 100% boss damage"
    }

    current_mode = data.combat_mode
    mode_index = list(combat_modes.keys()).index(current_mode) if current_mode in combat_modes else 0

    new_mode = st.radio(
        "Combat Mode",
        options=list(combat_modes.keys()),
        format_func=lambda x: combat_modes[x],
        index=mode_index,
        help="Affects how normal% and boss% damage bonuses are weighted"
    )
    if new_mode != data.combat_mode:
        data.combat_mode = new_mode
        auto_save()

    st.divider()

    # Chapter Selection
    st.subheader("Chapter/Stage")

    chapters = list(ENEMY_DEFENSE_VALUES.keys())
    current_chapter = data.chapter if data.chapter in chapters else "Chapter 27"
    chapter_index = chapters.index(current_chapter) if current_chapter in chapters else 0

    new_chapter = st.selectbox(
        "Current Chapter",
        options=chapters,
        index=chapter_index,
        help="Select your current chapter for enemy defense calculations"
    )
    if new_chapter != data.chapter:
        data.chapter = new_chapter
        auto_save()

    # Show enemy defense
    enemy_def = ENEMY_DEFENSE_VALUES.get(new_chapter, 0.752)
    st.metric("Enemy Defense", f"{enemy_def:.3f}")

    st.info("""
    **Combat Mode Effects:**
    - **Stage**: Normal% affects 60% of damage, Boss% affects 40%
    - **Boss**: Only Boss% applies (100%)
    - **World Boss**: Only Boss% applies (100%)
    """)

st.divider()

# Summary
st.subheader("Current Settings Summary")
summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)

with summary_col1:
    st.metric("Level", data.character_level)
with summary_col2:
    st.metric("All Skills", f"+{data.all_skills}")
with summary_col3:
    st.metric("Combat Mode", data.combat_mode.replace("_", " ").title())
with summary_col4:
    st.metric("Chapter", data.chapter.replace("Chapter ", ""))

st.divider()

# ============================================================================
# DATA IMPORT/EXPORT
# ============================================================================

st.subheader("Data Management")
st.markdown("Export your build to share with others, or import someone else's build.")

exp_col, imp_col = st.columns(2)

with exp_col:
    st.markdown("**Export Build**")
    st.caption("Download your current build as a CSV file to share with others.")

    # Generate CSV content
    csv_content = export_user_data_csv(data)
    filename = f"{st.session_state.username}_build.csv"

    st.download_button(
        label="Download Build CSV",
        data=csv_content,
        file_name=filename,
        mime="text/csv",
        help="Download your complete build data as a CSV file"
    )

with imp_col:
    st.markdown("**Import Build**")
    st.caption("Upload a CSV file to load someone else's build (overwrites your current data).")

    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type=['csv'],
        help="Upload a build CSV file to import",
        key="import_csv"
    )

    if uploaded_file is not None:
        # Read the file content
        csv_text = uploaded_file.getvalue().decode('utf-8')

        # Show preview
        with st.expander("Preview imported data", expanded=False):
            st.text(csv_text[:1000] + "..." if len(csv_text) > 1000 else csv_text)

        if st.button("Import Build", type="primary"):
            imported_data = import_user_data_csv(csv_text, st.session_state.username)
            if imported_data:
                # Update session state
                st.session_state.user_data = imported_data
                # Save to file
                save_user_data(st.session_state.username, imported_data)
                st.success("Build imported successfully! Refresh the page to see changes.")
                st.rerun()
            else:
                st.error("Failed to import build. Please check the CSV format.")

st.info("""
**Sharing Builds:**
1. Click "Download Build CSV" to export your current build
2. Share the CSV file with friends
3. They can upload it using "Import Build" to load your stats
""")
