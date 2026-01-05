"""
Weapons Page
Track weapon inventory with rarity, tier, and level for ATK% calculations.
"""
import streamlit as st
from utils.data_manager import save_user_data
from weapons import (
    WeaponRarity, calculate_weapon_atk_str, INVENTORY_RATIO,
    BASE_RATES_T4_STR
)

st.set_page_config(page_title="Weapons", page_icon="🏹", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

RARITIES = ["normal", "rare", "epic", "unique", "legendary", "mystic", "ancient"]
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


# Initialize weapon_inventory if not present
if not hasattr(data, 'weapon_inventory') or data.weapon_inventory is None:
    data.weapon_inventory = []

# Initialize equipped_weapon if not present
if not hasattr(data, 'equipped_weapon') or data.equipped_weapon is None:
    data.equipped_weapon = None


st.title("🏹 Weapons")

st.info("""
**How Weapon ATK% Works:**
- Each weapon provides **On-Equip ATK%** (only when equipped) and **Inventory ATK%** (always active)
- **Inventory ATK% = 25% of On-Equip ATK%**
- ATK% per level varies by **Rarity** and **Tier** (T1 is highest, T4 is lowest)
- Higher rarity and lower tier number = more ATK% per level
""")

# Create tabs
tab1, tab2, tab3 = st.tabs(["Weapon Inventory", "Equipped Weapon", "Stats Summary"])

with tab1:
    st.subheader("Weapon Inventory")
    st.markdown("Add all weapons you own. Inventory ATK% from ALL weapons is always active.")

    # Add new weapon section
    st.markdown("### Add New Weapon")
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

    with col1:
        new_rarity = st.selectbox(
            "Rarity",
            options=RARITIES,
            index=5,  # Default to mystic
            format_func=lambda x: x.capitalize(),
            key="new_weapon_rarity"
        )

    with col2:
        new_tier = st.selectbox(
            "Tier",
            options=[1, 2, 3, 4],
            index=0,  # Default to T1
            format_func=lambda x: f"T{x}",
            key="new_weapon_tier"
        )

    with col3:
        new_level = st.number_input(
            "Level",
            min_value=1,
            max_value=300,
            value=100,
            key="new_weapon_level"
        )

    with col4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Add Weapon", key="add_weapon_btn"):
            # Calculate ATK% for preview
            stats = calculate_weapon_atk_str(new_rarity, new_tier, new_level)

            new_weapon = {
                'rarity': new_rarity,
                'tier': new_tier,
                'level': new_level,
                'on_equip_atk': stats['on_equip_atk'],
                'inventory_atk': stats['inventory_atk'],
            }
            data.weapon_inventory.append(new_weapon)
            auto_save()
            st.rerun()

    # Show ATK% preview for new weapon
    if new_rarity and new_tier and new_level:
        preview_stats = calculate_weapon_atk_str(new_rarity, new_tier, new_level)
        st.caption(
            f"Preview: {new_rarity.capitalize()} T{new_tier} Lv.{new_level} → "
            f"On-Equip: +{preview_stats['on_equip_atk']:.1f}% ATK, "
            f"Inventory: +{preview_stats['inventory_atk']:.1f}% ATK "
            f"(Rate: +{preview_stats['rate_per_level']:.2f}%/level)"
        )

    st.divider()

    # List existing weapons
    st.markdown("### Your Weapons")

    if data.weapon_inventory:
        # Sort by rarity (highest first), then tier (lowest first), then level (highest first)
        rarity_order = {r: i for i, r in enumerate(reversed(RARITIES))}
        sorted_weapons = sorted(
            enumerate(data.weapon_inventory),
            key=lambda x: (rarity_order.get(x[1].get('rarity', 'normal'), 0), x[1].get('tier', 4), -x[1].get('level', 1))
        )

        for orig_idx, weapon in sorted_weapons:
            rarity = weapon.get('rarity', 'normal')
            tier = weapon.get('tier', 4)
            level = weapon.get('level', 1)

            # Recalculate ATK% in case formula changed
            stats = calculate_weapon_atk_str(rarity, tier, level)

            color = RARITY_COLORS.get(rarity, "#ffffff")

            col1, col2, col3, col4, col5 = st.columns([3, 1, 2, 2, 1])

            with col1:
                st.markdown(f"<span style='color:{color}; font-weight:bold;'>{rarity.capitalize()} T{tier}</span>", unsafe_allow_html=True)

            with col2:
                new_lvl = st.number_input(
                    "Level",
                    min_value=1,
                    max_value=300,
                    value=level,
                    key=f"weapon_level_{orig_idx}",
                    label_visibility="collapsed"
                )
                if new_lvl != level:
                    data.weapon_inventory[orig_idx]['level'] = new_lvl
                    new_stats = calculate_weapon_atk_str(rarity, tier, new_lvl)
                    data.weapon_inventory[orig_idx]['on_equip_atk'] = new_stats['on_equip_atk']
                    data.weapon_inventory[orig_idx]['inventory_atk'] = new_stats['inventory_atk']
                    auto_save()

            with col3:
                st.caption(f"On-Equip: +{stats['on_equip_atk']:.1f}%")

            with col4:
                st.caption(f"Inventory: +{stats['inventory_atk']:.1f}%")

            with col5:
                if st.button("🗑️", key=f"del_weapon_{orig_idx}"):
                    # Check if this weapon is equipped
                    if data.equipped_weapon == orig_idx:
                        data.equipped_weapon = None
                    elif data.equipped_weapon is not None and data.equipped_weapon > orig_idx:
                        data.equipped_weapon -= 1
                    data.weapon_inventory.pop(orig_idx)
                    auto_save()
                    st.rerun()

    else:
        st.info("No weapons added yet. Add weapons above to track their ATK% bonuses.")

with tab2:
    st.subheader("Equipped Weapon")
    st.markdown("Select which weapon is currently equipped. Only ONE weapon can be equipped at a time.")

    if data.weapon_inventory:
        # Build options list
        weapon_options = [(-1, "--- None ---")]
        for idx, weapon in enumerate(data.weapon_inventory):
            rarity = weapon.get('rarity', 'normal')
            tier = weapon.get('tier', 4)
            level = weapon.get('level', 1)
            stats = calculate_weapon_atk_str(rarity, tier, level)
            label = f"{rarity.capitalize()} T{tier} Lv.{level} (+{stats['on_equip_atk']:.1f}% On-Equip)"
            weapon_options.append((idx, label))

        current_equipped = data.equipped_weapon if data.equipped_weapon is not None else -1
        option_indices = [opt[0] for opt in weapon_options]

        current_idx = option_indices.index(current_equipped) if current_equipped in option_indices else 0

        selected = st.selectbox(
            "Equipped Weapon",
            options=option_indices,
            index=current_idx,
            format_func=lambda x: dict(weapon_options).get(x, "--- None ---"),
            key="equipped_weapon_select"
        )

        if selected != current_equipped:
            data.equipped_weapon = selected if selected >= 0 else None
            auto_save()

        # Show equipped weapon stats
        if data.equipped_weapon is not None and data.equipped_weapon >= 0:
            weapon = data.weapon_inventory[data.equipped_weapon]
            rarity = weapon.get('rarity', 'normal')
            tier = weapon.get('tier', 4)
            level = weapon.get('level', 1)
            stats = calculate_weapon_atk_str(rarity, tier, level)

            color = RARITY_COLORS.get(rarity, "#ffffff")
            st.markdown(f"### Currently Equipped")
            st.markdown(f"<span style='color:{color}; font-size:1.2em; font-weight:bold;'>{rarity.capitalize()} T{tier} Lv.{level}</span>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                st.metric("On-Equip ATK%", f"+{stats['on_equip_atk']:.1f}%")
            with col2:
                st.metric("Rate per Level", f"+{stats['rate_per_level']:.2f}%")
    else:
        st.info("Add weapons to your inventory first before equipping.")

with tab3:
    st.subheader("Weapon Stats Summary")

    # Calculate totals
    total_inventory_atk = 0.0
    equipped_atk = 0.0

    for idx, weapon in enumerate(data.weapon_inventory or []):
        rarity = weapon.get('rarity', 'normal')
        tier = weapon.get('tier', 4)
        level = weapon.get('level', 1)
        stats = calculate_weapon_atk_str(rarity, tier, level)

        total_inventory_atk += stats['inventory_atk']

        if data.equipped_weapon == idx:
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
    if data.weapon_inventory:
        table_data = []
        for idx, weapon in enumerate(data.weapon_inventory):
            rarity = weapon.get('rarity', 'normal')
            tier = weapon.get('tier', 4)
            level = weapon.get('level', 1)
            stats = calculate_weapon_atk_str(rarity, tier, level)

            is_equipped = "✓" if data.equipped_weapon == idx else ""

            table_data.append({
                "Equipped": is_equipped,
                "Weapon": f"{rarity.capitalize()} T{tier}",
                "Level": level,
                "On-Equip ATK%": f"+{stats['on_equip_atk']:.1f}%",
                "Inventory ATK%": f"+{stats['inventory_atk']:.1f}%",
                "Rate/Level": f"+{stats['rate_per_level']:.2f}%",
            })

        st.dataframe(table_data, use_container_width=True, hide_index=True)
    else:
        st.info("No weapons in inventory.")

    st.divider()

    # ATK% reference table
    with st.expander("ATK% Rate Reference (per level at T4)"):
        st.markdown("Base ATK% rates per level (T4 baseline):")
        ref_data = []
        for rarity in RARITIES:
            rate = BASE_RATES_T4_STR.get(rarity, 0)
            ref_data.append({
                "Rarity": rarity.capitalize(),
                "T4 Rate": f"+{rate:.3f}%",
                "T3 Rate": f"+{rate * 1.3:.3f}%",
                "T2 Rate": f"+{rate * 1.69:.3f}%",
                "T1 Rate": f"+{rate * 2.197:.3f}%",
            })
        st.dataframe(ref_data, use_container_width=True, hide_index=True)
        st.caption("Note: Mystic, Unique, and Epic have slightly different tier multipliers. See weapons.py for exact values.")
