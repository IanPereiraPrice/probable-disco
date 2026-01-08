"""
Weapons Page - Predefined weapons with level and awakening tracking.
All 27 weapons (7 rarities × 4 tiers, minus Ancient T1) are shown.
"""
import streamlit as st
from utils.data_manager import save_user_data
from weapons import calculate_weapon_atk_str, BASE_ATK
from weapon_mastery import (
    ALL_WEAPONS, WEAPON_MASTERY_REWARDS, RARITIES,
    calculate_mastery_stages_from_weapons, calculate_mastery_stats
)

st.set_page_config(page_title="Weapons", page_icon="🏹", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

RARITY_COLORS = {
    "normal": "#aaaaaa",
    "rare": "#5588ff",
    "epic": "#aa77ff",
    "unique": "#ffaa00",
    "legendary": "#7fff7f",
    "mystic": "#ff77ff",
    "ancient": "#ff5555",
}


def auto_save():
    save_user_data(st.session_state.username, data)


# Initialize weapons_data if not present
if not hasattr(data, 'weapons_data') or data.weapons_data is None:
    data.weapons_data = {}

if not hasattr(data, 'equipped_weapon_key') or data.equipped_weapon_key is None:
    data.equipped_weapon_key = ""

st.title("🏹 Weapons")

st.info("""
**How Weapons Work:**
- Each weapon has a **Level** (affects ATK%) and **Awakening** (0-5 stars, affects Mastery bonuses)
- Set Level to 0 if you don't own the weapon
- Only ONE weapon can be equipped at a time
- **Inventory ATK% = 25%** of On-Equip ATK% (always active for all owned weapons)
""")

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs(["All Weapons", "Equipped Weapon", "Stats Summary", "Mastery Bonuses"])

with tab1:
    st.subheader("All Weapons")
    st.markdown("Set **Level** (0 = not owned) and **Awakening** (0-5) for each weapon.")

    # Group by rarity (highest first)
    for rarity in ['ancient', 'mystic', 'legendary', 'unique', 'epic', 'rare', 'normal']:
        color = RARITY_COLORS.get(rarity, "#ffffff")
        st.markdown(f"### <span style='color:{color}'>{rarity.capitalize()}</span>", unsafe_allow_html=True)

        # Get tiers for this rarity (Ancient has no T1)
        tiers = [1, 2, 3, 4] if rarity != 'ancient' else [2, 3, 4]

        cols = st.columns(len(tiers))
        for i, tier in enumerate(tiers):
            key = f"{rarity}_{tier}"
            weapon_data = data.weapons_data.get(key, {'level': 0, 'awakening': 0})
            current_level = weapon_data.get('level', 0)
            current_awakening = weapon_data.get('awakening', 0)

            with cols[i]:
                st.markdown(f"**T{tier}**")

                # Level input
                level = st.number_input(
                    "Level",
                    min_value=0,
                    max_value=300,
                    value=current_level,
                    key=f"wlevel_{key}",
                    help="Set to 0 if not owned"
                )

                # Awakening input (0-5 stars per weapon)
                awakening = st.number_input(
                    "⭐ Awakening",
                    min_value=0,
                    max_value=5,
                    value=current_awakening,
                    key=f"wawaken_{key}",
                )

                # Calculate and show ATK%
                if level > 0:
                    stats = calculate_weapon_atk_str(rarity, tier, level)
                    st.caption(f"+{stats['on_equip_atk']:.1f}% ATK")
                else:
                    st.caption("Not owned")

                # Save if changed
                new_data = {'level': level, 'awakening': awakening}
                if level != current_level or awakening != current_awakening:
                    data.weapons_data[key] = new_data
                    # If this weapon was equipped and level is now 0, unequip it
                    if level == 0 and data.equipped_weapon_key == key:
                        data.equipped_weapon_key = ""
                    auto_save()

        st.divider()

with tab2:
    st.subheader("Equipped Weapon")
    st.markdown("Select which weapon is currently equipped. Only ONE weapon can be equipped at a time.")

    # Build options from weapons with level > 0
    options = [("", "--- None ---")]
    for rarity, tier in ALL_WEAPONS:
        key = f"{rarity}_{tier}"
        weapon_data = data.weapons_data.get(key, {'level': 0})
        level = weapon_data.get('level', 0)
        if level > 0:
            stats = calculate_weapon_atk_str(rarity, tier, level)
            color = RARITY_COLORS.get(rarity, "#ffffff")
            label = f"{rarity.capitalize()} T{tier} Lv.{level} (+{stats['on_equip_atk']:.1f}% ATK)"
            options.append((key, label))

    if len(options) > 1:
        current_idx = 0
        for i, (k, _) in enumerate(options):
            if k == data.equipped_weapon_key:
                current_idx = i
                break

        selected = st.selectbox(
            "Select equipped weapon",
            options=options,
            index=current_idx,
            format_func=lambda x: x[1],
            key="equipped_weapon_select"
        )

        if selected[0] != data.equipped_weapon_key:
            data.equipped_weapon_key = selected[0]
            auto_save()
            st.rerun()

        # Show equipped weapon stats
        if data.equipped_weapon_key:
            parts = data.equipped_weapon_key.rsplit('_', 1)
            if len(parts) == 2:
                rarity, tier = parts[0], int(parts[1])
                weapon_data = data.weapons_data.get(data.equipped_weapon_key, {})
                level = weapon_data.get('level', 0)
                awakening = weapon_data.get('awakening', 0)

                if level > 0:
                    stats = calculate_weapon_atk_str(rarity, tier, level)
                    color = RARITY_COLORS.get(rarity, "#ffffff")

                    st.markdown("### Currently Equipped")
                    st.markdown(
                        f"<span style='color:{color}; font-size:1.2em; font-weight:bold;'>"
                        f"{rarity.capitalize()} T{tier} Lv.{level}</span>",
                        unsafe_allow_html=True
                    )

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("On-Equip ATK%", f"+{stats['on_equip_atk']:.1f}%")
                    with col2:
                        st.metric("Rate per Level", f"+{stats['rate_per_level']:.2f}%")
                    with col3:
                        st.metric("Awakening", f"⭐ {awakening}/5")
    else:
        st.info("Add weapons to your inventory first (set Level > 0) before equipping.")

with tab3:
    st.subheader("Weapon Stats Summary")

    # Calculate totals
    total_inventory_atk = 0.0
    equipped_atk = 0.0

    for key, weapon_data in data.weapons_data.items():
        level = weapon_data.get('level', 0)
        if level > 0:
            parts = key.rsplit('_', 1)
            if len(parts) == 2:
                rarity, tier = parts[0], int(parts[1])
                stats = calculate_weapon_atk_str(rarity, tier, level)
                total_inventory_atk += stats['inventory_atk']

                if key == data.equipped_weapon_key:
                    equipped_atk = stats['on_equip_atk']

    total_atk = equipped_atk + total_inventory_atk

    # Display summary
    st.markdown("### Total Weapon ATK%")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Equipped ATK%", f"+{equipped_atk:.1f}%", help="From your currently equipped weapon")
    with col2:
        st.metric("Inventory ATK%", f"+{total_inventory_atk:.1f}%", help="25% of all weapons' on-equip ATK% (always active)")
    with col3:
        st.metric("Total ATK%", f"+{total_atk:.1f}%", help="Equipped + Inventory")

    st.divider()

    # Weapon breakdown table
    st.markdown("### Weapon Breakdown")
    table_data = []
    for rarity, tier in ALL_WEAPONS:
        key = f"{rarity}_{tier}"
        weapon_data = data.weapons_data.get(key, {'level': 0, 'awakening': 0})
        level = weapon_data.get('level', 0)
        awakening = weapon_data.get('awakening', 0)

        if level > 0:
            stats = calculate_weapon_atk_str(rarity, tier, level)
            is_equipped = "✓" if key == data.equipped_weapon_key else ""

            table_data.append({
                "Equipped": is_equipped,
                "Weapon": f"{rarity.capitalize()} T{tier}",
                "Level": level,
                "Awakening": f"⭐{awakening}",
                "On-Equip ATK%": f"+{stats['on_equip_atk']:.1f}%",
                "Inventory ATK%": f"+{stats['inventory_atk']:.1f}%",
            })

    if table_data:
        st.dataframe(table_data, use_container_width=True, hide_index=True)
    else:
        st.info("No weapons owned yet. Set Level > 0 for weapons you own.")

    st.divider()

    # ATK% reference table
    with st.expander("Base ATK% Reference (at Level 1)"):
        st.markdown("Base ATK% values at Level 1 (before level multiplier):")
        ref_data = []
        for rarity in RARITIES:
            # Get base ATK for each tier
            t4 = BASE_ATK.get((rarity, 4), 0)
            t3 = BASE_ATK.get((rarity, 3), 0)
            t2 = BASE_ATK.get((rarity, 2), 0)
            t1 = BASE_ATK.get((rarity, 1), 0)
            ref_data.append({
                "Rarity": rarity.capitalize(),
                "T4 Base": f"{t4:.1f}%",
                "T3 Base": f"{t3:.1f}%",
                "T2 Base": f"{t2:.1f}%",
                "T1 Base": f"{t1:.1f}%" if t1 > 0 else "N/A",
            })
        st.dataframe(ref_data, use_container_width=True, hide_index=True)
        st.caption("Formula: ATK% = BaseATK × LevelMultiplier. See weapons.py for level multiplier formula.")

with tab4:
    st.subheader("⭐ Weapon Mastery Bonuses")
    st.markdown("""
    Earn permanent stat bonuses by reaching total awakening stages across all weapons of each rarity.
    Each weapon can have 0-5 awakening stars.
    """)

    # Calculate mastery
    mastery_stages = calculate_mastery_stages_from_weapons(data.weapons_data)
    mastery_stats = calculate_mastery_stats(mastery_stages)

    # Display totals
    st.markdown("### Current Bonuses")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Attack", f"+{mastery_stats['attack']:,}")
    with col2:
        st.metric("Main Stat", f"+{mastery_stats['main_stat']:,}")
    with col3:
        st.metric("Accuracy", f"+{mastery_stats['accuracy']}")

    if mastery_stats['min_dmg_mult'] > 0 or mastery_stats['max_dmg_mult'] > 0:
        col4, col5 = st.columns(2)
        with col4:
            st.metric("Min Damage Mult", f"+{mastery_stats['min_dmg_mult']:.1f}%")
        with col5:
            st.metric("Max Damage Mult", f"+{mastery_stats['max_dmg_mult']:.1f}%")

    st.divider()

    # Progress by rarity
    st.markdown("### Progress by Rarity")
    for rarity in ['ancient', 'mystic', 'legendary', 'unique', 'epic', 'rare']:
        current = mastery_stages.get(rarity, 0)
        rewards = WEAPON_MASTERY_REWARDS.get(rarity, [])
        if rewards:
            max_stage = max(r.stage for r in rewards)
            # Count how many weapons of this rarity
            num_weapons = 3 if rarity == 'ancient' else 4
            max_possible = num_weapons * 5  # 5 awakening per weapon

            color = RARITY_COLORS.get(rarity, "#ffffff")
            with st.expander(f"{rarity.capitalize()} - {current}/{max_possible} stages ({num_weapons} weapons × 5 awakening)"):
                for reward in rewards:
                    achieved = "✅" if current >= reward.stage else "⬜"
                    parts = []
                    if reward.attack:
                        parts.append(f"ATK +{reward.attack:,}")
                    if reward.main_stat:
                        parts.append(f"Main Stat +{reward.main_stat:,}")
                    if reward.accuracy:
                        parts.append(f"Accuracy +{reward.accuracy}")
                    if reward.min_dmg_mult:
                        parts.append(f"Min Dmg +{reward.min_dmg_mult}%")
                    if reward.max_dmg_mult:
                        parts.append(f"Max Dmg +{reward.max_dmg_mult}%")
                    st.write(f"{achieved} **Stage {reward.stage}**: {', '.join(parts)}")
