"""
Batch Equipment Scanner Page
Upload multiple equipment screenshots at once and auto-extract stats using OCR.
"""
import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.data_manager import save_user_data, EQUIPMENT_SLOTS
from equipment import get_amplify_multiplier

st.set_page_config(page_title="Batch Scanner", page_icon="📷", layout="wide")

# Styling - more compact for batch view
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
    .scan-item {
        background: #1a1a2e;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        border-left: 3px solid #4a9eff;
    }
    .scan-item-error {
        border-left-color: #ff6666;
    }
    .mini-label {
        font-size: 11px;
        color: #888;
        margin-bottom: 2px;
    }
    .pot-summary {
        font-size: 11px;
        color: #aaa;
        background: #2a2a4e;
        padding: 4px 8px;
        border-radius: 4px;
        margin: 2px 0;
    }
    /* Make number inputs more compact */
    .stNumberInput > div > div > input {
        padding: 4px 8px;
    }
</style>
""", unsafe_allow_html=True)

# Auth check
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

if 'user_data' not in st.session_state or st.session_state.user_data is None:
    st.warning("No user data found. Please login.")
    st.stop()

data = st.session_state.user_data

# Constants
POTENTIAL_TIERS = ["Rare", "Epic", "Unique", "Legendary", "Mystic"]

# Third stat varies by slot (same as Equipment Stats page)
SLOT_THIRD_STAT = {
    "hat": "Defense", "top": "Defense", "bottom": "Accuracy", "gloves": "Accuracy",
    "shoes": "Max MP", "belt": "Max MP", "shoulder": "Evasion", "cape": "Evasion",
    "ring": "Main Stat", "necklace": "Main Stat", "face": "Main Stat",
}

# Special stat options (for special gear) - min/max damage can appear together
SPECIAL_STAT_OPTIONS = {
    "damage_pct": "Damage %",
    "all_skills": "All Skills",
    "final_damage": "Final Damage %",
    "min_dmg_mult": "Min Damage %",
    "max_dmg_mult": "Max Damage %",
}

STAT_OPTIONS = [
    "",  # Empty option
    "dex_pct", "str_pct", "int_pct", "luk_pct",
    "dex_flat", "str_flat", "int_flat", "luk_flat",
    "damage", "crit_rate", "crit_damage", "def_pen",
    "final_damage", "all_skills", "min_dmg_mult", "max_dmg_mult",
    "attack_speed", "defense", "max_hp", "max_mp",
    "skill_cd", "buff_duration", "stat_per_level", "ba_targets",
]

STAT_DISPLAY = {
    "": "---",
    "dex_pct": "DEX %", "str_pct": "STR %", "int_pct": "INT %", "luk_pct": "LUK %",
    "dex_flat": "DEX", "str_flat": "STR", "int_flat": "INT", "luk_flat": "LUK",
    "damage": "Dmg %", "crit_rate": "CR %", "crit_damage": "CD %",
    "def_pen": "Def Pen %", "final_damage": "FD %", "all_skills": "All Skills",
    "min_dmg_mult": "Min Dmg %", "max_dmg_mult": "Max Dmg %",
    "attack_speed": "Atk Spd %", "defense": "Def %",
    "max_hp": "HP %", "max_mp": "MP %",
    "skill_cd": "Skill CD", "buff_duration": "Buff Dur %",
    "stat_per_level": "Stat/Lv", "ba_targets": "BA +",
}


def format_stat(stat: str) -> str:
    """Format stat key for display."""
    return STAT_DISPLAY.get(stat, stat.replace("_", " ").title()) if stat else "---"


def format_lines_summary(lines: list) -> str:
    """Format potential lines as a short summary."""
    parts = []
    for line in lines:
        if line.stat:
            stat_name = STAT_DISPLAY.get(line.stat, line.stat)
            parts.append(f"{stat_name}: {line.value}")
    return " | ".join(parts) if parts else "(none)"


# Check if easyocr is installed
try:
    from utils.ocr_scanner import extract_and_parse, ParsedEquipment
    ocr_available = True
except ImportError as e:
    ocr_available = False
    import_error = str(e)

if not ocr_available:
    st.error(f"""
    **OCR library not installed!**

    To use the Equipment Scanner, install EasyOCR:
    ```
    pip install easyocr
    ```

    Error: {import_error}
    """)
    st.stop()


# =============================================================================
# PAGE LAYOUT
# =============================================================================

st.title("📷 Batch Equipment Scanner")
st.markdown("Upload multiple equipment screenshots to scan them all at once.")

# Initialize session state for batch scanning
if 'batch_scans' not in st.session_state:
    st.session_state.batch_scans = {}  # {filename: {...}}
if 'batch_processing' not in st.session_state:
    st.session_state.batch_processing = False
if 'batch_files_processed' not in st.session_state:
    st.session_state.batch_files_processed = set()

# =============================================================================
# UPLOAD SECTION
# =============================================================================

st.markdown("<div class='section-header'>1. Upload Screenshots</div>", unsafe_allow_html=True)

uploaded_files = st.file_uploader(
    "Upload equipment screenshots (you can select multiple)",
    type=['png', 'jpg', 'jpeg'],
    accept_multiple_files=True,
    help="Select multiple equipment screenshots at once. Each will be processed with OCR.",
    label_visibility="collapsed",
)

if uploaded_files:
    new_files = [f for f in uploaded_files if f.name not in st.session_state.batch_files_processed]
    st.info(f"📁 {len(uploaded_files)} file(s) uploaded, {len(new_files)} new to process")

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("🔍 Scan All New", type="primary", use_container_width=True, disabled=len(new_files) == 0):
            st.session_state.batch_processing = True
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, uploaded_file in enumerate(new_files):
                status_text.text(f"Processing {uploaded_file.name}...")
                progress_bar.progress((idx + 1) / len(new_files))

                try:
                    image_bytes = uploaded_file.getvalue()
                    parsed = extract_and_parse(image_bytes)

                    detected_slot = parsed.equipment_slot if parsed.equipment_slot else "hat"

                    # Initialize all editable values from parsed data
                    # OCR gives us DISPLAYED stats (with SF bonus included)
                    # User will enter displayed stats, we calculate and store base stats
                    stars = parsed.stars
                    main_mult = get_amplify_multiplier(stars, is_sub=False)
                    sub_mult = get_amplify_multiplier(stars, is_sub=True)

                    # Get the correct third stat based on slot type
                    # Hat/Top = Defense, Bottom/Gloves = Accuracy, Shoes/Belt = Max MP,
                    # Shoulder/Cape = Evasion, Ring/Necklace/Face = Main Stat
                    slot_third_stat_map = {
                        "hat": parsed.base_def, "top": parsed.base_def,
                        "bottom": parsed.base_accuracy, "gloves": parsed.base_accuracy,
                        "shoes": parsed.base_mp, "belt": parsed.base_mp,
                        "shoulder": parsed.base_evasion, "cape": parsed.base_evasion,
                        "ring": parsed.base_main_stat, "necklace": parsed.base_main_stat,
                        "face": parsed.base_main_stat,
                    }

                    # Displayed stats from OCR (include SF bonus) - this is what user sees
                    displayed_atk = parsed.base_atk
                    displayed_hp = parsed.base_hp
                    displayed_third = slot_third_stat_map.get(detected_slot, parsed.base_def)
                    displayed_cr = parsed.base_crit_rate
                    displayed_cd = parsed.base_crit_damage
                    displayed_boss = parsed.base_boss_dmg
                    displayed_normal = parsed.base_normal_dmg

                    # Calculate base stats by dividing by SF multiplier (for storage)
                    calc_base_atk = int(displayed_atk / main_mult) if main_mult > 0 else displayed_atk
                    calc_base_hp = int(displayed_hp / main_mult) if main_mult > 0 else displayed_hp
                    calc_base_third = int(displayed_third / main_mult) if main_mult > 0 else displayed_third
                    calc_base_cr = round(displayed_cr / sub_mult, 2) if sub_mult > 0 else displayed_cr
                    calc_base_cd = round(displayed_cd / sub_mult, 2) if sub_mult > 0 else displayed_cd
                    calc_base_boss = round(displayed_boss / sub_mult, 2) if sub_mult > 0 else displayed_boss
                    calc_base_normal = round(displayed_normal / sub_mult, 2) if sub_mult > 0 else displayed_normal

                    st.session_state.batch_scans[uploaded_file.name] = {
                        'parsed': parsed,
                        'slot': detected_slot,
                        'include': True,
                        'image_bytes': image_bytes,
                        # Displayed stats from OCR (includes SF bonus) - this is what user enters/edits
                        'displayed_attack': displayed_atk,
                        'displayed_hp': displayed_hp,
                        'displayed_third': displayed_third,
                        'displayed_crit_rate': displayed_cr,
                        'displayed_crit_damage': displayed_cd,
                        'displayed_boss_damage': displayed_boss,
                        'displayed_normal_damage': displayed_normal,
                        # Main stats (Main Amplify) - BASE stats that get SAVED to equipment_items
                        'base_attack': calc_base_atk,
                        'base_max_hp': calc_base_hp,
                        'base_third_stat': calc_base_third,
                        # Sub stats (Sub Amplify) - BASE stats that get SAVED
                        'sub_crit_rate': calc_base_cr,
                        'sub_crit_damage': calc_base_cd,
                        'sub_boss_damage': calc_base_boss,
                        'sub_normal_damage': calc_base_normal,
                        'sub_attack_flat': 0,
                        # Job skill level bonuses (Sub Amplify) - from OCR or 0
                        # Note: We store the BASE value (displayed / sub_mult)
                        'displayed_skill_1st': parsed.base_skill_1st,
                        'displayed_skill_2nd': parsed.base_skill_2nd,
                        'displayed_skill_3rd': parsed.base_skill_3rd,
                        'displayed_skill_4th': parsed.base_skill_4th,
                        'sub_skill_1st': int(parsed.base_skill_1st / sub_mult) if sub_mult > 0 and parsed.base_skill_1st > 0 else 0,
                        'sub_skill_2nd': int(parsed.base_skill_2nd / sub_mult) if sub_mult > 0 and parsed.base_skill_2nd > 0 else 0,
                        'sub_skill_3rd': int(parsed.base_skill_3rd / sub_mult) if sub_mult > 0 and parsed.base_skill_3rd > 0 else 0,
                        'sub_skill_4th': int(parsed.base_skill_4th / sub_mult) if sub_mult > 0 and parsed.base_skill_4th > 0 else 0,
                        # Special stats (for special gear)
                        'is_special': False,
                        'special_stat_type': 'damage_pct',
                        'special_stat_value': 0.0,
                        'special_stat_type_2': 'max_dmg_mult',  # Second special stat (for min/max dmg)
                        'special_stat_value_2': 0.0,
                        # Basic info
                        'stars': stars,
                        'tier': parsed.item_tier,
                        # Potentials
                        'reg_tier': parsed.regular_tier,
                        'reg_pity': parsed.regular_pity,
                        'reg_lines': [(l.stat, l.value) for l in parsed.regular_lines],
                        'bon_tier': parsed.bonus_tier,
                        'bon_pity': parsed.bonus_pity,
                        'bon_lines': [(l.stat, l.value) for l in parsed.bonus_lines],
                    }
                    st.session_state.batch_files_processed.add(uploaded_file.name)
                except Exception as e:
                    st.session_state.batch_scans[uploaded_file.name] = {
                        'parsed': None,
                        'slot': "hat",
                        'include': False,
                        'error': str(e),
                        'image_bytes': uploaded_file.getvalue(),
                    }
                    st.session_state.batch_files_processed.add(uploaded_file.name)

            st.session_state.batch_processing = False
            progress_bar.empty()
            status_text.empty()
            st.rerun()

    with col2:
        if st.button("🔄 Clear All Results", use_container_width=True):
            st.session_state.batch_scans = {}
            st.session_state.batch_files_processed = set()
            st.rerun()

    with col3:
        valid_count = sum(1 for s in st.session_state.batch_scans.values() if s.get('parsed') and s.get('include'))
        st.metric("Ready to Save", f"{valid_count} items")

# =============================================================================
# RESULTS SECTION
# =============================================================================

if st.session_state.batch_scans:
    st.divider()
    st.markdown("<div class='section-header'>2. Review & Edit Scanned Data</div>", unsafe_allow_html=True)
    st.caption("Expand each item to edit stats. Uncheck items you don't want to save.")

    # Display each scanned item
    for filename, scan_data in st.session_state.batch_scans.items():
        parsed = scan_data.get('parsed')
        error = scan_data.get('error')

        if error:
            st.markdown(f"<div class='scan-item scan-item-error'>", unsafe_allow_html=True)
            col1, col2 = st.columns([1, 4])
            with col1:
                st.image(scan_data['image_bytes'], width=80)
            with col2:
                st.error(f"**{filename}**: {error}")
            st.markdown("</div>", unsafe_allow_html=True)
            continue

        # Header row: checkbox, slot, quick summary
        col_chk, col_slot, col_stars, col_summary = st.columns([0.3, 0.8, 0.5, 3])

        with col_chk:
            include = st.checkbox("", value=scan_data['include'], key=f"inc_{filename}")
            st.session_state.batch_scans[filename]['include'] = include

        with col_slot:
            slot_idx = EQUIPMENT_SLOTS.index(scan_data['slot']) if scan_data['slot'] in EQUIPMENT_SLOTS else 0
            new_slot = st.selectbox(
                "Slot", EQUIPMENT_SLOTS, index=slot_idx,
                format_func=lambda x: x.title(),
                key=f"slot_{filename}",
                label_visibility="collapsed"
            )
            st.session_state.batch_scans[filename]['slot'] = new_slot

        with col_stars:
            st.markdown(f"**T{scan_data['tier']}** ★{scan_data['stars']}")

        with col_summary:
            # Quick summary of main stats and potentials
            atk = scan_data['base_attack']
            hp = scan_data['base_max_hp']
            reg_sum = format_lines_summary(parsed.regular_lines)
            st.markdown(f"ATK: **{atk:,}** | HP: **{hp:,}** | Reg: {reg_sum[:50]}...")

        # Expandable details
        with st.expander(f"📋 Edit {filename}", expanded=False):
            col_img, col_main, col_sub, col_pot = st.columns([0.8, 1.2, 1.2, 1.8])

            # Image column
            with col_img:
                st.image(scan_data['image_bytes'], use_container_width=True)
                st.caption(f"{parsed.parse_confidence*100:.0f}% conf")

            # Main Stats column (Main Amplify)
            with col_main:
                st.markdown("**Main Stats**")

                # Stars first - affects base stat calculation
                new_stars = st.slider("Stars ★", 0, 25, int(scan_data['stars']), key=f"stars_{filename}")
                st.session_state.batch_scans[filename]['stars'] = new_stars

                # Calculate SF multipliers
                main_mult = get_amplify_multiplier(new_stars, is_sub=False)
                st.caption(f"Main Amp: {main_mult:.2f}x")

                third_label = SLOT_THIRD_STAT.get(new_slot, "Third Stat")

                # Get currently stored displayed values (what user enters)
                displayed_atk = scan_data.get('displayed_attack', 0)
                displayed_hp = scan_data.get('displayed_hp', 0)
                displayed_third = scan_data.get('displayed_third', 0)

                # User enters AMPLIFIED stats (what they see on screen)
                # We calculate and display the base stat, and store base stat
                st.markdown("<span class='mini-label'>ATK (enter what you see)</span>", unsafe_allow_html=True)
                new_displayed_atk = st.number_input(
                    "Displayed ATK", 0, 999999, int(displayed_atk),
                    key=f"atk_{filename}", label_visibility="collapsed"
                )
                calc_base_atk = int(new_displayed_atk / main_mult) if main_mult > 0 else new_displayed_atk
                st.caption(f"Base: {calc_base_atk:,}")
                st.session_state.batch_scans[filename]['displayed_attack'] = new_displayed_atk
                st.session_state.batch_scans[filename]['base_attack'] = calc_base_atk

                st.markdown("<span class='mini-label'>HP (enter what you see)</span>", unsafe_allow_html=True)
                new_displayed_hp = st.number_input(
                    "Displayed HP", 0, 999999, int(displayed_hp),
                    key=f"hp_{filename}", label_visibility="collapsed"
                )
                calc_base_hp = int(new_displayed_hp / main_mult) if main_mult > 0 else new_displayed_hp
                st.caption(f"Base: {calc_base_hp:,}")
                st.session_state.batch_scans[filename]['displayed_hp'] = new_displayed_hp
                st.session_state.batch_scans[filename]['base_max_hp'] = calc_base_hp

                st.markdown(f"<span class='mini-label'>{third_label} (enter what you see)</span>", unsafe_allow_html=True)
                new_displayed_third = st.number_input(
                    f"Displayed {third_label}", 0, 999999, int(displayed_third),
                    key=f"third_{filename}", label_visibility="collapsed"
                )
                calc_base_third = int(new_displayed_third / main_mult) if main_mult > 0 else new_displayed_third
                st.caption(f"Base: {calc_base_third:,}")
                st.session_state.batch_scans[filename]['displayed_third'] = new_displayed_third
                st.session_state.batch_scans[filename]['base_third_stat'] = calc_base_third

            # Sub Stats column (Sub Amplify)
            with col_sub:
                st.markdown("**Sub Stats**")

                # Sub Amplify multiplier
                sub_mult = get_amplify_multiplier(new_stars, is_sub=True)
                st.caption(f"Sub Amp: {sub_mult:.2f}x")

                # Get displayed sub stats (what user enters)
                displayed_cr = scan_data.get('displayed_crit_rate', 0.0)
                displayed_cd = scan_data.get('displayed_crit_damage', 0.0)
                displayed_boss = scan_data.get('displayed_boss_damage', 0.0)
                displayed_normal = scan_data.get('displayed_normal_damage', 0.0)

                c1, c2 = st.columns(2)
                with c1:
                    # Boss% - user enters what they see, we store base
                    st.markdown("<span class='mini-label'>Boss% (enter what you see)</span>", unsafe_allow_html=True)
                    new_displayed_boss = st.number_input(
                        "Boss%", 0.0, 100.0, float(displayed_boss),
                        step=0.1, key=f"boss_{filename}", label_visibility="collapsed"
                    )
                    calc_base_boss = round(new_displayed_boss / sub_mult, 2) if sub_mult > 0 else new_displayed_boss
                    st.caption(f"Base: {calc_base_boss:.1f}%")
                    st.session_state.batch_scans[filename]['displayed_boss_damage'] = new_displayed_boss
                    st.session_state.batch_scans[filename]['sub_boss_damage'] = calc_base_boss

                    # CR% - user enters what they see, we store base
                    st.markdown("<span class='mini-label'>CR% (enter what you see)</span>", unsafe_allow_html=True)
                    new_displayed_cr = st.number_input(
                        "CR%", 0.0, 100.0, float(displayed_cr),
                        step=0.1, key=f"cr_{filename}", label_visibility="collapsed"
                    )
                    calc_base_cr = round(new_displayed_cr / sub_mult, 2) if sub_mult > 0 else new_displayed_cr
                    st.caption(f"Base: {calc_base_cr:.1f}%")
                    st.session_state.batch_scans[filename]['displayed_crit_rate'] = new_displayed_cr
                    st.session_state.batch_scans[filename]['sub_crit_rate'] = calc_base_cr

                with c2:
                    # Normal% - user enters what they see, we store base
                    st.markdown("<span class='mini-label'>Normal% (enter what you see)</span>", unsafe_allow_html=True)
                    new_displayed_normal = st.number_input(
                        "Normal%", 0.0, 100.0, float(displayed_normal),
                        step=0.1, key=f"normal_{filename}", label_visibility="collapsed"
                    )
                    calc_base_normal = round(new_displayed_normal / sub_mult, 2) if sub_mult > 0 else new_displayed_normal
                    st.caption(f"Base: {calc_base_normal:.1f}%")
                    st.session_state.batch_scans[filename]['displayed_normal_damage'] = new_displayed_normal
                    st.session_state.batch_scans[filename]['sub_normal_damage'] = calc_base_normal

                    # CD% - user enters what they see, we store base
                    st.markdown("<span class='mini-label'>CD% (enter what you see)</span>", unsafe_allow_html=True)
                    new_displayed_cd = st.number_input(
                        "CD%", 0.0, 500.0, float(displayed_cd),
                        step=0.1, key=f"cd_{filename}", label_visibility="collapsed"
                    )
                    calc_base_cd = round(new_displayed_cd / sub_mult, 2) if sub_mult > 0 else new_displayed_cd
                    st.caption(f"Base: {calc_base_cd:.1f}%")
                    st.session_state.batch_scans[filename]['displayed_crit_damage'] = new_displayed_cd
                    st.session_state.batch_scans[filename]['sub_crit_damage'] = calc_base_cd

                new_atk_flat = st.number_input(
                    "Attack Flat", 0, 99999, int(scan_data['sub_attack_flat']),
                    key=f"atkflat_{filename}"
                )
                st.session_state.batch_scans[filename]['sub_attack_flat'] = new_atk_flat

                # Job skill level bonuses
                st.markdown("**Job Skills**")
                c1, c2 = st.columns(2)
                with c1:
                    new_skill_1 = st.number_input(
                        "1st Job", 0, 50, int(scan_data.get('sub_skill_1st', 0)),
                        key=f"skill1_{filename}"
                    )
                    st.session_state.batch_scans[filename]['sub_skill_1st'] = new_skill_1

                    new_skill_3 = st.number_input(
                        "3rd Job", 0, 50, int(scan_data.get('sub_skill_3rd', 0)),
                        key=f"skill3_{filename}"
                    )
                    st.session_state.batch_scans[filename]['sub_skill_3rd'] = new_skill_3
                with c2:
                    new_skill_2 = st.number_input(
                        "2nd Job", 0, 50, int(scan_data.get('sub_skill_2nd', 0)),
                        key=f"skill2_{filename}"
                    )
                    st.session_state.batch_scans[filename]['sub_skill_2nd'] = new_skill_2

                    new_skill_4 = st.number_input(
                        "4th Job", 0, 50, int(scan_data.get('sub_skill_4th', 0)),
                        key=f"skill4_{filename}"
                    )
                    st.session_state.batch_scans[filename]['sub_skill_4th'] = new_skill_4

                # Special stats section
                st.markdown("**Special Stats**")
                new_is_special = st.checkbox(
                    "Is Special", value=scan_data.get('is_special', False),
                    key=f"isspecial_{filename}"
                )
                st.session_state.batch_scans[filename]['is_special'] = new_is_special

                if new_is_special:
                    special_types = list(SPECIAL_STAT_OPTIONS.keys())
                    special_labels = list(SPECIAL_STAT_OPTIONS.values())

                    # First special stat
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        current_type = scan_data.get('special_stat_type', 'damage_pct')
                        type_idx = special_types.index(current_type) if current_type in special_types else 0
                        new_type = st.selectbox(
                            "Type 1", special_labels, index=type_idx,
                            key=f"spectype_{filename}", label_visibility="collapsed"
                        )
                        new_type_key = special_types[special_labels.index(new_type)]
                        st.session_state.batch_scans[filename]['special_stat_type'] = new_type_key
                    with c2:
                        new_val = st.number_input(
                            "Val", 0.0, 100.0, float(scan_data.get('special_stat_value', 0)),
                            step=0.1, key=f"specval_{filename}", label_visibility="collapsed"
                        )
                        st.session_state.batch_scans[filename]['special_stat_value'] = new_val

                    # Second special stat (for items with both min and max damage)
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        current_type_2 = scan_data.get('special_stat_type_2', 'max_dmg_mult')
                        type_idx_2 = special_types.index(current_type_2) if current_type_2 in special_types else 4
                        new_type_2 = st.selectbox(
                            "Type 2", special_labels, index=type_idx_2,
                            key=f"spectype2_{filename}", label_visibility="collapsed"
                        )
                        new_type_key_2 = special_types[special_labels.index(new_type_2)]
                        st.session_state.batch_scans[filename]['special_stat_type_2'] = new_type_key_2
                    with c2:
                        new_val_2 = st.number_input(
                            "Val", 0.0, 100.0, float(scan_data.get('special_stat_value_2', 0)),
                            step=0.1, key=f"specval2_{filename}", label_visibility="collapsed"
                        )
                        st.session_state.batch_scans[filename]['special_stat_value_2'] = new_val_2

            # Potentials column
            with col_pot:
                # Regular Potential
                st.markdown(f"**Regular ({scan_data['reg_tier']})**")
                reg_lines = []
                for i in range(3):
                    existing = scan_data['reg_lines'][i] if i < len(scan_data['reg_lines']) else ("", 0)
                    c1, c2 = st.columns([2.5, 1])
                    with c1:
                        stat_idx = STAT_OPTIONS.index(existing[0]) if existing[0] in STAT_OPTIONS else 0
                        stat = st.selectbox(
                            f"R{i+1}", STAT_OPTIONS, index=stat_idx,
                            format_func=format_stat, key=f"reg_stat_{filename}_{i}",
                            label_visibility="collapsed"
                        )
                    with c2:
                        val = st.number_input(
                            "v", 0.0, 9999.0, float(existing[1]),
                            key=f"reg_val_{filename}_{i}", label_visibility="collapsed"
                        )
                    reg_lines.append((stat, val))
                st.session_state.batch_scans[filename]['reg_lines'] = reg_lines

                # Bonus Potential
                st.markdown(f"**Bonus ({scan_data['bon_tier']})**")
                bon_lines = []
                for i in range(3):
                    existing = scan_data['bon_lines'][i] if i < len(scan_data['bon_lines']) else ("", 0)
                    c1, c2 = st.columns([2.5, 1])
                    with c1:
                        stat_idx = STAT_OPTIONS.index(existing[0]) if existing[0] in STAT_OPTIONS else 0
                        stat = st.selectbox(
                            f"B{i+1}", STAT_OPTIONS, index=stat_idx,
                            format_func=format_stat, key=f"bon_stat_{filename}_{i}",
                            label_visibility="collapsed"
                        )
                    with c2:
                        val = st.number_input(
                            "v", 0.0, 9999.0, float(existing[1]),
                            key=f"bon_val_{filename}_{i}", label_visibility="collapsed"
                        )
                    bon_lines.append((stat, val))
                st.session_state.batch_scans[filename]['bon_lines'] = bon_lines

    # =============================================================================
    # SAVE ALL SECTION
    # =============================================================================

    st.divider()
    st.markdown("<div class='section-header'>3. Save All Equipment</div>", unsafe_allow_html=True)

    # Check for duplicates and preview
    items_to_save = {}
    slot_counts = {}
    for filename, scan_data in st.session_state.batch_scans.items():
        if scan_data.get('parsed') and scan_data.get('include'):
            slot = scan_data['slot']
            items_to_save[slot] = filename
            slot_counts[slot] = slot_counts.get(slot, 0) + 1

    if items_to_save:
        duplicates = [slot for slot, count in slot_counts.items() if count > 1]
        if duplicates:
            st.warning(f"⚠️ Duplicate slots: **{', '.join(d.title() for d in duplicates)}**. "
                       f"Last item for each slot will be saved.")

        st.markdown("**Will save:** " + ", ".join(f"**{s.title()}**" for s in sorted(items_to_save.keys())))

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("💾 Save All Equipment", type="primary", use_container_width=True):
                saved_count = 0

                for filename, scan_data in st.session_state.batch_scans.items():
                    if not scan_data.get('parsed') or not scan_data.get('include'):
                        continue

                    slot = scan_data['slot']

                    # Update equipment_items with all stats
                    item = data.equipment_items.get(slot, {})

                    # Ensure values are correct types (int for stats, float for percentages)
                    item['base_attack'] = int(scan_data.get('base_attack', 0))
                    item['base_max_hp'] = int(scan_data.get('base_max_hp', 0))
                    item['base_third_stat'] = int(scan_data.get('base_third_stat', 0))
                    item['sub_boss_damage'] = float(scan_data.get('sub_boss_damage', 0))
                    item['sub_normal_damage'] = float(scan_data.get('sub_normal_damage', 0))
                    item['sub_crit_rate'] = float(scan_data.get('sub_crit_rate', 0))
                    item['sub_crit_damage'] = float(scan_data.get('sub_crit_damage', 0))
                    item['sub_attack_flat'] = int(scan_data.get('sub_attack_flat', 0))
                    # Job skill level bonuses
                    item['sub_skill_1st'] = int(scan_data.get('sub_skill_1st', 0))
                    item['sub_skill_2nd'] = int(scan_data.get('sub_skill_2nd', 0))
                    item['sub_skill_3rd'] = int(scan_data.get('sub_skill_3rd', 0))
                    item['sub_skill_4th'] = int(scan_data.get('sub_skill_4th', 0))
                    item['stars'] = int(scan_data.get('stars', 0))
                    item['tier'] = int(scan_data.get('tier', 4))
                    # Set name and rarity (use slot name if not provided)
                    item['name'] = scan_data.get('name', slot.title())
                    item['rarity'] = scan_data.get('rarity', 'Legendary')
                    # Special stats
                    item['is_special'] = scan_data.get('is_special', False)
                    item['special_stat_type'] = scan_data.get('special_stat_type', 'damage_pct')
                    item['special_stat_value'] = scan_data.get('special_stat_value', 0)
                    item['special_stat_type_2'] = scan_data.get('special_stat_type_2', 'max_dmg_mult')
                    item['special_stat_value_2'] = scan_data.get('special_stat_value_2', 0)
                    data.equipment_items[slot] = item

                    # Update equipment_potentials
                    pots = data.equipment_potentials.get(slot, {})

                    # Regular potential
                    pots['tier'] = scan_data['reg_tier']
                    pots['regular_pity'] = scan_data['reg_pity']
                    for i, (stat, val) in enumerate(scan_data['reg_lines'], 1):
                        pots[f'line{i}_stat'] = stat
                        pots[f'line{i}_value'] = val
                        pots[f'line{i}_yellow'] = True

                    # Bonus potential
                    pots['bonus_tier'] = scan_data['bon_tier']
                    pots['bonus_pity'] = scan_data['bon_pity']
                    for i, (stat, val) in enumerate(scan_data['bon_lines'], 1):
                        pots[f'bonus_line{i}_stat'] = stat
                        pots[f'bonus_line{i}_value'] = val
                        pots[f'bonus_line{i}_yellow'] = True

                    data.equipment_potentials[slot] = pots
                    saved_count += 1

                save_user_data(st.session_state.username, data)
                st.success(f"✅ Saved {saved_count} equipment items!")

                st.session_state.batch_scans = {}
                st.session_state.batch_files_processed = set()
                st.rerun()
    else:
        st.info("No items selected to save. Check the boxes next to items you want to save.")

else:
    st.info("""
    **How to use Batch Scanner:**
    1. Take screenshots of your equipment's **Potential Options** panel for each piece
    2. Upload all screenshots at once using the file picker above
    3. Click **Scan All New** to process all images with OCR
    4. Expand each item to review/edit the detected values
    5. Uncheck any items you don't want to save
    6. Click **Save All Equipment** to update your data

    **What gets saved:**
    - Main Stats: Base Attack, Base Max HP, Base Third Stat (Defense/Accuracy/etc.)
    - Sub Stats: Boss%, Normal%, Crit Rate%, Crit Damage%, Attack Flat, Job Skills (1st-4th)
    - Potentials: Regular and Bonus (3 lines each)
    - Stars and Tier
    """)

# =============================================================================
# HELP SECTION
# =============================================================================

st.divider()
with st.expander("📖 Scanner Tips"):
    st.markdown("""
    **For best OCR results:**
    - Include the full **Potential Options** panel
    - Make sure tier badge (Legendary, Mystic, etc.) is visible
    - Include the pity counter (e.g., 321/714)

    **What OCR extracts automatically:**
    - Equipment slot (from item name)
    - Base Attack, Max HP, Crit Rate, Crit Damage
    - All 6 potential lines with stats and values
    - Stars and Tier level

    **What you may need to enter manually:**
    - Boss%, Normal%, Attack Flat (not always visible in screenshots)
    - Third stat (Defense, Accuracy, etc.)
    - Job Skill Levels (1st, 2nd, 3rd, 4th job)
    """)
