"""
Equipment Stats Page
Manage equipment base stats and starforce levels.
"""
import streamlit as st
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.data_manager import save_user_data, EQUIPMENT_SLOTS
from equipment import get_amplify_multiplier

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


def ensure_item_fields(item: dict) -> dict:
    """Ensure all item fields exist with defaults matching the old app."""
    defaults = {
        # Basic info
        'name': '', 'rarity': 'Normal', 'tier': 1, 'stars': 0, 'is_special': False,
        # Main stats (Main Amplify)
        'base_attack': 0, 'base_max_hp': 0, 'base_third_stat': 0,
        # Default sub stats (Sub Amplify) - available on all equipment
        'sub_boss_damage': 0, 'sub_normal_damage': 0, 'sub_crit_rate': 0,
        'sub_crit_damage': 0, 'sub_attack_flat': 0,
        # Job skill bonuses (Sub Amplify) - available on all equipment
        'sub_skill_1st': 0, 'sub_skill_2nd': 0, 'sub_skill_3rd': 0, 'sub_skill_4th': 0,
        # Special stats (Sub Amplify) - only on special items
        'special_stat_type': 'damage_pct', 'special_stat_value': 0,
    }
    for k, v in defaults.items():
        if k not in item:
            item[k] = v
    return item


def auto_save():
    save_user_data(st.session_state.username, data)


# ============================================================================
# PAGE LAYOUT
# ============================================================================

st.title("⭐ Equipment Stats")
st.markdown("Manage equipment base stats, starforce levels, and sub stats.")

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

    # Row 1: Boss, Normal, CR, CD
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

    # Row 2: Attack Flat
    col1, col2 = st.columns(2)
    with col1:
        new_atk_flat = st.number_input("Attack Flat", 0, 99999, int(item.get('sub_attack_flat', 0)), key="eq_atk_flat")
        if new_atk_flat != item.get('sub_attack_flat'):
            item['sub_attack_flat'] = new_atk_flat
            auto_save()
    with col2:
        st.metric("After SF", f"{new_atk_flat * sub_mult:,.0f}")

    # Row 3: Job Skill Bonuses
    st.markdown("**Job Skill Bonuses** (Sub Amplify)")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        new_skill_1st = st.number_input("1st Job", 0, 100, int(item.get('sub_skill_1st', 0)), key="eq_skill_1st")
        if new_skill_1st != item.get('sub_skill_1st'):
            item['sub_skill_1st'] = new_skill_1st
            auto_save()
    with col2:
        new_skill_2nd = st.number_input("2nd Job", 0, 100, int(item.get('sub_skill_2nd', 0)), key="eq_skill_2nd")
        if new_skill_2nd != item.get('sub_skill_2nd'):
            item['sub_skill_2nd'] = new_skill_2nd
            auto_save()
    with col3:
        new_skill_3rd = st.number_input("3rd Job", 0, 100, int(item.get('sub_skill_3rd', 0)), key="eq_skill_3rd")
        if new_skill_3rd != item.get('sub_skill_3rd'):
            item['sub_skill_3rd'] = new_skill_3rd
            auto_save()
    with col4:
        new_skill_4th = st.number_input("4th Job", 0, 100, int(item.get('sub_skill_4th', 0)), key="eq_skill_4th")
        if new_skill_4th != item.get('sub_skill_4th'):
            item['sub_skill_4th'] = new_skill_4th
            auto_save()

    st.caption(f"After SF: 1st +{int(new_skill_1st*sub_mult)} | 2nd +{int(new_skill_2nd*sub_mult)} | 3rd +{int(new_skill_3rd*sub_mult)} | 4th +{int(new_skill_4th*sub_mult)}")

    # Row 4: Special Item Stats
    st.markdown("---")
    st.markdown("**Special Item Stats** (only for special gear)")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        new_is_special = st.checkbox("Is Special", value=item.get('is_special', False), key="eq_is_special")
        if new_is_special != item.get('is_special'):
            item['is_special'] = new_is_special
            auto_save()

    if new_is_special:
        with col2:
            special_types = list(SPECIAL_STAT_OPTIONS.keys())
            special_labels = list(SPECIAL_STAT_OPTIONS.values())
            current_type = item.get('special_stat_type', 'damage_pct')
            type_idx = special_types.index(current_type) if current_type in special_types else 0
            new_special_type = st.selectbox("Special Stat", special_labels, index=type_idx, key="eq_special_type")
            new_special_type_key = special_types[special_labels.index(new_special_type)]
            if new_special_type_key != item.get('special_stat_type'):
                item['special_stat_type'] = new_special_type_key
                auto_save()
        with col3:
            new_special_value = st.number_input("Value", 0.0, 100.0, float(item.get('special_stat_value', 0)), step=0.1, key="eq_special_value")
            if new_special_value != item.get('special_stat_value'):
                item['special_stat_value'] = new_special_value
                auto_save()

        st.caption(f"After SF: {SPECIAL_STAT_OPTIONS.get(item.get('special_stat_type', 'damage_pct'), 'Damage %')} +{new_special_value*sub_mult:.1f}")

# Info box about starforce calculator
st.markdown("---")
st.info("**Tip:** Use the **Starforce Calculator** page to calculate enhancement costs and run simulations.")
