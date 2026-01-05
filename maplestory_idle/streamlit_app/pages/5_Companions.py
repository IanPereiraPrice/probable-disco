"""
Companions Page
Configure companion inventory levels and equipped companions.
"""
import streamlit as st
from utils.data_manager import save_user_data
from companions import (
    COMPANIONS, JobAdvancement, TIER_DISPLAY, ON_EQUIP_DISPLAY,
    MAX_LEVELS, get_companions_by_advancement
)

st.set_page_config(page_title="Companions", page_icon="🐾", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data


def auto_save():
    save_user_data(st.session_state.username, data)


# Initialize companion_levels if not present
if not hasattr(data, 'companion_levels') or data.companion_levels is None:
    data.companion_levels = {}

# Initialize equipped_companions if not present
if not hasattr(data, 'equipped_companions') or data.equipped_companions is None:
    data.equipped_companions = [None] * 7


st.title("🐾 Companions")

st.info("""
**How Companions Work:**
- **Inventory Effects**: ALL owned companions contribute stats (Attack, Main Stat, Damage %)
- **On-Equip Effects**: Only equipped companions (7 slots) provide additional bonuses
- Set level to 0 if you don't own a companion
""")

# Create tabs for Inventory and Equipped
tab1, tab2, tab3 = st.tabs(["Companion Inventory", "Equipped Companions", "Stats Summary"])

with tab1:
    st.subheader("Companion Inventory")
    st.markdown("Set levels for all companions you own. Level 0 = not owned.")

    # Group companions by advancement tier
    for adv in [JobAdvancement.FOURTH, JobAdvancement.THIRD, JobAdvancement.SECOND,
                JobAdvancement.FIRST, JobAdvancement.BASIC]:
        tier_companions = get_companions_by_advancement(adv)
        max_level = MAX_LEVELS[adv]

        st.markdown(f"### {TIER_DISPLAY[adv]} (Max Level: {max_level})")

        # Determine inventory effect type for this tier
        if adv == JobAdvancement.BASIC:
            inv_effect = "Attack + Max HP"
        elif adv == JobAdvancement.FIRST:
            inv_effect = "Attack + Max HP"
        elif adv == JobAdvancement.SECOND:
            inv_effect = "Main Stat + Max HP"
        else:  # 3rd and 4th
            inv_effect = "Damage %"

        st.caption(f"Inventory Effect: {inv_effect}")

        # Create columns for companions
        cols = st.columns(4)

        for idx, (key, companion) in enumerate(tier_companions.items()):
            col_idx = idx % 4

            with cols[col_idx]:
                current_level = data.companion_levels.get(key, 0)
                on_equip_stat = ON_EQUIP_DISPLAY.get(companion.on_equip_type, "Unknown")

                new_level = st.number_input(
                    f"{companion.name}",
                    min_value=0,
                    max_value=max_level,
                    value=current_level,
                    key=f"inv_{key}",
                    help=f"On-Equip: {on_equip_stat}"
                )

                if new_level != current_level:
                    data.companion_levels[key] = new_level
                    auto_save()

        st.divider()

with tab2:
    st.subheader("Equipped Companions")
    st.markdown("Select which companions are equipped in your 7 slots (1 Main + 6 Sub).")
    st.caption("Only companions with level > 0 in your inventory can be equipped.")

    # Get list of owned companions (level > 0)
    owned_companions = [("", "--- Empty ---")]
    for key, companion in COMPANIONS.items():
        level = data.companion_levels.get(key, 0)
        if level > 0:
            on_equip_stat = ON_EQUIP_DISPLAY.get(companion.on_equip_type, "")
            owned_companions.append((key, f"{companion.name} (Lv{level}) - {on_equip_stat}"))

    # Main slot
    st.markdown("### Main Companion (Slot 1)")
    current_main = data.equipped_companions[0] if data.equipped_companions[0] else ""
    main_options = [k for k, _ in owned_companions]
    main_labels = [v for _, v in owned_companions]

    main_idx = main_options.index(current_main) if current_main in main_options else 0
    new_main = st.selectbox(
        "Main Companion",
        options=main_options,
        index=main_idx,
        format_func=lambda x: dict(owned_companions).get(x, "--- Empty ---"),
        key="equipped_main"
    )

    if new_main != current_main:
        data.equipped_companions[0] = new_main if new_main else None
        auto_save()

    # Show on-equip effect for main
    if new_main and new_main in COMPANIONS:
        comp = COMPANIONS[new_main]
        level = data.companion_levels.get(new_main, 1)
        on_equip_val = comp.get_on_equip_value(level)
        on_equip_stat = ON_EQUIP_DISPLAY.get(comp.on_equip_type, "")
        st.success(f"On-Equip: +{on_equip_val:.1f} {on_equip_stat}")

    st.divider()

    # Sub slots
    st.markdown("### Sub Companions (Slots 2-7)")
    sub_cols = st.columns(3)

    for slot_idx in range(1, 7):
        col_idx = (slot_idx - 1) % 3

        with sub_cols[col_idx]:
            st.markdown(f"**Slot {slot_idx + 1}**")
            current_sub = data.equipped_companions[slot_idx] if slot_idx < len(data.equipped_companions) and data.equipped_companions[slot_idx] else ""

            sub_idx = main_options.index(current_sub) if current_sub in main_options else 0
            new_sub = st.selectbox(
                f"Sub {slot_idx}",
                options=main_options,
                index=sub_idx,
                format_func=lambda x: dict(owned_companions).get(x, "--- Empty ---"),
                key=f"equipped_sub_{slot_idx}",
                label_visibility="collapsed"
            )

            if new_sub != current_sub:
                while len(data.equipped_companions) <= slot_idx:
                    data.equipped_companions.append(None)
                data.equipped_companions[slot_idx] = new_sub if new_sub else None
                auto_save()

            # Show on-equip effect
            if new_sub and new_sub in COMPANIONS:
                comp = COMPANIONS[new_sub]
                level = data.companion_levels.get(new_sub, 1)
                on_equip_val = comp.get_on_equip_value(level)
                on_equip_stat = ON_EQUIP_DISPLAY.get(comp.on_equip_type, "")
                st.caption(f"+{on_equip_val:.1f} {on_equip_stat}")

with tab3:
    st.subheader("Companion Stats Summary")

    # Calculate inventory stats
    total_attack = 0.0
    total_main_stat = 0.0
    total_damage = 0.0
    total_max_hp = 0.0

    tier_summaries = {}

    for key, companion in COMPANIONS.items():
        level = data.companion_levels.get(key, 0)
        if level > 0:
            inv_stats = companion.get_inventory_stats(level)
            adv_name = TIER_DISPLAY[companion.advancement]

            if adv_name not in tier_summaries:
                tier_summaries[adv_name] = {"count": 0, "attack": 0, "main_stat": 0, "damage": 0, "max_hp": 0}

            tier_summaries[adv_name]["count"] += 1
            tier_summaries[adv_name]["attack"] += inv_stats.get("attack", 0)
            tier_summaries[adv_name]["main_stat"] += inv_stats.get("main_stat", 0)
            tier_summaries[adv_name]["damage"] += inv_stats.get("damage", 0)
            tier_summaries[adv_name]["max_hp"] += inv_stats.get("max_hp", 0)

            total_attack += inv_stats.get("attack", 0)
            total_main_stat += inv_stats.get("main_stat", 0)
            total_damage += inv_stats.get("damage", 0)
            total_max_hp += inv_stats.get("max_hp", 0)

    # Display inventory summary
    st.markdown("### Inventory Effects (Always Active)")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Attack", f"+{total_attack:.0f}")
    with col2:
        st.metric("Total Main Stat", f"+{total_main_stat:.0f}")
    with col3:
        st.metric("Total Damage %", f"+{total_damage:.1f}%")
    with col4:
        st.metric("Total Max HP", f"+{total_max_hp:.0f}")

    st.markdown("#### By Tier")
    for tier_name in ["4th Job", "3rd Job", "2nd Job", "1st Job", "Basic"]:
        if tier_name in tier_summaries:
            summary = tier_summaries[tier_name]
            effects = []
            if summary["attack"] > 0:
                effects.append(f"Attack +{summary['attack']:.0f}")
            if summary["main_stat"] > 0:
                effects.append(f"Main Stat +{summary['main_stat']:.0f}")
            if summary["damage"] > 0:
                effects.append(f"Damage +{summary['damage']:.1f}%")

            effect_str = ", ".join(effects) if effects else "None"
            st.markdown(f"**{tier_name}** ({summary['count']} companions): {effect_str}")

    st.divider()

    # Calculate on-equip stats
    st.markdown("### On-Equip Effects (From Equipped Companions)")

    on_equip_stats = {}
    equipped_list = []

    for slot_idx, comp_key in enumerate(data.equipped_companions or []):
        if comp_key and comp_key in COMPANIONS:
            companion = COMPANIONS[comp_key]
            level = data.companion_levels.get(comp_key, 1)
            on_equip_val = companion.get_on_equip_value(level)
            stat_name = ON_EQUIP_DISPLAY.get(companion.on_equip_type, "Unknown")

            on_equip_stats[stat_name] = on_equip_stats.get(stat_name, 0) + on_equip_val

            slot_name = "Main" if slot_idx == 0 else f"Sub {slot_idx}"
            equipped_list.append({
                "Slot": slot_name,
                "Companion": companion.name,
                "Level": level,
                "On-Equip": f"+{on_equip_val:.1f} {stat_name}"
            })

    if equipped_list:
        st.dataframe(equipped_list, use_container_width=True, hide_index=True)

        st.markdown("#### Total On-Equip Bonuses")
        for stat_name, value in on_equip_stats.items():
            st.markdown(f"- **{stat_name}**: +{value:.1f}")
    else:
        st.info("No companions equipped yet.")
