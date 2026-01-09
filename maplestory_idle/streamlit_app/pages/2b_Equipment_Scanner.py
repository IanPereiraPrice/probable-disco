"""
Equipment Scanner Page
Upload equipment screenshots and auto-extract stats using OCR.
"""
import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.data_manager import save_user_data, EQUIPMENT_SLOTS

st.set_page_config(page_title="Equipment Scanner", page_icon="📷", layout="wide")

# Styling
st.markdown("""
<style>
    .block-container { padding-top: 1rem; }
    .confidence-high { color: #66ff66; font-weight: bold; }
    .confidence-medium { color: #ffcc00; font-weight: bold; }
    .confidence-low { color: #ff6666; font-weight: bold; }
    .raw-text {
        font-family: monospace;
        font-size: 11px;
        color: #888;
        max-height: 200px;
        overflow-y: auto;
        background: #1a1a2e;
        padding: 8px;
        border-radius: 4px;
    }
    .section-header {
        font-size: 16px;
        font-weight: bold;
        color: #ffd700;
        margin-bottom: 8px;
        padding: 8px;
        background: #2a2a4e;
        border-radius: 4px;
    }
    .line-row {
        background: #1e1e1e;
        padding: 4px 8px;
        border-radius: 4px;
        margin: 2px 0;
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

# All possible stats for dropdowns
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
    "dex_flat": "DEX (flat)", "str_flat": "STR (flat)", "int_flat": "INT (flat)", "luk_flat": "LUK (flat)",
    "damage": "Damage %", "crit_rate": "Crit Rate %", "crit_damage": "Crit Damage %",
    "def_pen": "Def Pen %", "final_damage": "Final Damage %", "all_skills": "All Skills",
    "min_dmg_mult": "Min Damage %", "max_dmg_mult": "Max Damage %",
    "attack_speed": "Attack Speed %", "defense": "Defense %",
    "max_hp": "Max HP %", "max_mp": "Max MP %",
    "skill_cd": "Skill CD", "buff_duration": "Buff Duration %",
    "stat_per_level": "Stat per Level", "ba_targets": "BA Targets +",
}


def format_stat(stat: str) -> str:
    """Format stat key for display."""
    return STAT_DISPLAY.get(stat, stat.replace("_", " ").title()) if stat else "---"


def get_confidence_display(confidence: float) -> tuple:
    """Get confidence class and label."""
    if confidence >= 0.8:
        return "confidence-high", "High"
    elif confidence >= 0.5:
        return "confidence-medium", "Medium"
    else:
        return "confidence-low", "Low"


# =============================================================================
# PAGE LAYOUT
# =============================================================================

st.title("📷 Equipment Scanner")
st.markdown("Upload an equipment screenshot to auto-extract potential stats using OCR.")

# Initialize session state
if 'parsed_equip' not in st.session_state:
    st.session_state.parsed_equip = None
if 'ocr_error' not in st.session_state:
    st.session_state.ocr_error = None
if 'last_uploaded_file' not in st.session_state:
    st.session_state.last_uploaded_file = None

# Clear stale parsed data if it's missing the debug_info attribute (from old version)
if st.session_state.parsed_equip and not hasattr(st.session_state.parsed_equip, 'debug_info'):
    st.session_state.parsed_equip = None

# Check if easyocr is installed
try:
    from utils.ocr_scanner import extract_and_parse, ParsedEquipment, STAT_VOCABULARY
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

# Two-column layout for upload and slot selection
col_upload, col_settings = st.columns([1.2, 0.8])

with col_upload:
    st.markdown("<div class='section-header'>1. Upload Screenshot</div>", unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Choose equipment screenshot",
        type=['png', 'jpg', 'jpeg'],
        help="Upload a screenshot of your equipment's Potential Options panel",
        label_visibility="collapsed",
    )

    # Detect when a NEW file is uploaded and clear old parsed data
    if uploaded_file:
        # Use file name + size as a unique identifier
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        if st.session_state.last_uploaded_file != file_id:
            # New file uploaded - clear old results
            st.session_state.parsed_equip = None
            st.session_state.ocr_error = None
            st.session_state.last_uploaded_file = file_id

        st.image(uploaded_file, caption="Uploaded Screenshot", use_container_width=True)

with col_settings:
    st.markdown("<div class='section-header'>2. Select Equipment Slot</div>", unsafe_allow_html=True)

    selected_slot = st.selectbox(
        "Which slot is this equipment?",
        options=EQUIPMENT_SLOTS,
        format_func=lambda x: x.title(),
        key="scanner_slot",
        label_visibility="collapsed",
    )

    st.caption(f"Data will be saved to: **{selected_slot.title()}**")

    # Scan button
    if uploaded_file:
        col_scan, col_clear = st.columns(2)
        with col_scan:
            if st.button("🔍 Scan Screenshot", type="primary", use_container_width=True):
                with st.spinner("Running OCR... (first run downloads ~100MB model)"):
                    try:
                        image_bytes = uploaded_file.getvalue()
                        parsed = extract_and_parse(image_bytes)
                        st.session_state.parsed_equip = parsed
                        st.session_state.ocr_error = None

                        # Auto-select the detected equipment slot
                        if parsed.equipment_slot and parsed.equipment_slot in EQUIPMENT_SLOTS:
                            st.session_state.scanner_slot = parsed.equipment_slot

                        st.rerun()
                    except Exception as e:
                        st.session_state.ocr_error = str(e)
                        st.session_state.parsed_equip = None
                        st.rerun()
        with col_clear:
            if st.button("🔄 Clear Results", use_container_width=True):
                st.session_state.parsed_equip = None
                st.session_state.ocr_error = None
                st.session_state.last_uploaded_file = None
                st.rerun()

    # Show error if any
    if st.session_state.ocr_error:
        st.error(f"OCR Error: {st.session_state.ocr_error}")

    # Show confidence and detected slot if parsed
    if st.session_state.parsed_equip:
        parsed = st.session_state.parsed_equip
        conf_class, conf_label = get_confidence_display(parsed.parse_confidence)
        st.markdown(
            f"**Parse Confidence:** <span class='{conf_class}'>{conf_label} ({parsed.parse_confidence*100:.0f}%)</span>",
            unsafe_allow_html=True
        )

        # Show detected slot
        if parsed.equipment_slot:
            st.success(f"Detected: **{parsed.equipment_slot.title()}**")
        else:
            st.warning("Could not detect equipment slot")

        # Debug info expander
        with st.expander("🔧 Debug Info (parsing details)"):
            if parsed.debug_info:
                for info in parsed.debug_info:
                    st.text(info)
            else:
                st.caption("No debug info")

        # Raw OCR text expander
        with st.expander("📜 Raw OCR Text"):
            if parsed.raw_text:
                st.markdown(
                    "<div class='raw-text'>" + "<br>".join(parsed.raw_text) + "</div>",
                    unsafe_allow_html=True
                )
            else:
                st.caption("No text extracted")

st.divider()

# =============================================================================
# PARSED RESULTS (EDITABLE)
# =============================================================================

if st.session_state.parsed_equip:
    parsed = st.session_state.parsed_equip

    st.markdown("<div class='section-header'>3. Verify & Edit Extracted Data</div>", unsafe_allow_html=True)
    st.caption("Review the OCR results below. Use the dropdowns to correct any misread stats.")

    col_basic, col_regular, col_bonus = st.columns([0.8, 1.1, 1.1])

    with col_basic:
        st.markdown("**Basic Info**")

        edited_stars = st.slider(
            "Stars ★", 0, 25, parsed.stars, key="edit_stars"
        )

        if parsed.tier_level:
            st.caption(f"Detected: {parsed.tier_level}")

    with col_regular:
        st.markdown("**Regular Potential**")

        reg_tier_idx = POTENTIAL_TIERS.index(parsed.regular_tier) if parsed.regular_tier in POTENTIAL_TIERS else 3
        edited_reg_tier = st.selectbox(
            "Tier", POTENTIAL_TIERS, index=reg_tier_idx, key="edit_reg_tier"
        )

        edited_reg_pity = st.number_input(
            f"Pity (/{parsed.regular_pity_max or 714})",
            0, 9999, parsed.regular_pity, key="edit_reg_pity"
        )

        st.markdown("**Lines:**")
        reg_lines_edited = []
        for i in range(3):
            line = parsed.regular_lines[i] if i < len(parsed.regular_lines) else None

            col_stat, col_val = st.columns([2, 1])
            with col_stat:
                default_stat = line.stat if line and line.stat else ""
                stat_idx = STAT_OPTIONS.index(default_stat) if default_stat in STAT_OPTIONS else 0
                stat = st.selectbox(
                    f"L{i+1} Stat", STAT_OPTIONS, index=stat_idx,
                    format_func=format_stat, key=f"reg_l{i}_stat",
                    label_visibility="collapsed"
                )
            with col_val:
                default_val = line.value if line else 0.0
                val = st.number_input(
                    f"L{i+1} Value", 0.0, 9999.0, float(default_val),
                    key=f"reg_l{i}_val", label_visibility="collapsed"
                )
            reg_lines_edited.append((stat, val))

            # Show confidence indicator for this line
            if line and line.stat and line.confidence > 0:
                conf_pct = int(line.confidence * 100)
                if line.confidence >= 0.8:
                    st.caption(f"✓ {conf_pct}% match")
                elif line.confidence >= 0.5:
                    st.caption(f"⚠ {conf_pct}% match - verify")

    with col_bonus:
        st.markdown("**Bonus Potential**")

        bon_tier_idx = POTENTIAL_TIERS.index(parsed.bonus_tier) if parsed.bonus_tier in POTENTIAL_TIERS else 2
        edited_bon_tier = st.selectbox(
            "Tier", POTENTIAL_TIERS, index=bon_tier_idx, key="edit_bon_tier"
        )

        edited_bon_pity = st.number_input(
            f"Pity (/{parsed.bonus_pity_max or 417})",
            0, 9999, parsed.bonus_pity, key="edit_bon_pity"
        )

        st.markdown("**Lines:**")
        bon_lines_edited = []
        for i in range(3):
            line = parsed.bonus_lines[i] if i < len(parsed.bonus_lines) else None

            col_stat, col_val = st.columns([2, 1])
            with col_stat:
                default_stat = line.stat if line and line.stat else ""
                stat_idx = STAT_OPTIONS.index(default_stat) if default_stat in STAT_OPTIONS else 0
                stat = st.selectbox(
                    f"L{i+1} Stat", STAT_OPTIONS, index=stat_idx,
                    format_func=format_stat, key=f"bon_l{i}_stat",
                    label_visibility="collapsed"
                )
            with col_val:
                default_val = line.value if line else 0.0
                val = st.number_input(
                    f"L{i+1} Value", 0.0, 9999.0, float(default_val),
                    key=f"bon_l{i}_val", label_visibility="collapsed"
                )
            bon_lines_edited.append((stat, val))

            # Show confidence indicator
            if line and line.stat and line.confidence > 0:
                conf_pct = int(line.confidence * 100)
                if line.confidence >= 0.8:
                    st.caption(f"✓ {conf_pct}% match")
                elif line.confidence >= 0.5:
                    st.caption(f"⚠ {conf_pct}% match - verify")

    st.divider()

    # Save button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("💾 Save to Equipment", type="primary", use_container_width=True):
            slot = st.session_state.scanner_slot

            # Update potentials
            pots = data.equipment_potentials.get(slot, {})

            # Regular potential
            pots['tier'] = edited_reg_tier
            pots['regular_pity'] = edited_reg_pity

            for i, (stat, val) in enumerate(reg_lines_edited, 1):
                pots[f'line{i}_stat'] = stat
                pots[f'line{i}_value'] = val
                pots[f'line{i}_yellow'] = True  # Assume yellow for scanned

            # Bonus potential
            pots['bonus_tier'] = edited_bon_tier
            pots['bonus_pity'] = edited_bon_pity

            for i, (stat, val) in enumerate(bon_lines_edited, 1):
                pots[f'bonus_line{i}_stat'] = stat
                pots[f'bonus_line{i}_value'] = val
                pots[f'bonus_line{i}_yellow'] = True

            data.equipment_potentials[slot] = pots

            # Update stars in equipment_items
            item = data.equipment_items.get(slot, {})
            item['stars'] = edited_stars
            data.equipment_items[slot] = item

            # Save
            save_user_data(st.session_state.username, data)
            st.success(f"✅ Saved to {slot.title()}!")

            # Clear parsed data
            st.session_state.parsed_equip = None
            st.rerun()

else:
    # No parsed data yet - show instructions
    st.info("""
    **How to use:**
    1. Take a screenshot of your equipment's **Potential Options** panel in-game
    2. Upload the screenshot above
    3. Select which equipment slot this is
    4. Click **Scan Screenshot** to extract the stats
    5. Review and correct any OCR errors
    6. Click **Save to Equipment** to update your data
    """)

# =============================================================================
# HELP SECTION
# =============================================================================

st.divider()
with st.expander("📖 Scanner Tips & Troubleshooting"):
    st.markdown("""
    **For best OCR results:**
    - Include the full **Potential Options** panel in your screenshot
    - Make sure the tier badge (Legendary, Mystic, etc.) is visible
    - Include the pity counter (e.g., 321/714)
    - Avoid cropping too tightly around the text

    **What gets extracted:**
    - ⭐ Star level
    - 📊 Regular potential: tier, pity, 3 stat lines
    - 📊 Bonus potential: tier, pity, 3 stat lines

    **Common issues:**
    - **Wrong stat detected?** Use the dropdown to select the correct stat
    - **Value incorrect?** Manually type the correct value
    - **Low confidence?** The OCR wasn't sure - double-check against your screenshot

    **First-time setup:**
    - The first scan will download the OCR model (~100MB)
    - This only happens once - subsequent scans are faster
    """)
