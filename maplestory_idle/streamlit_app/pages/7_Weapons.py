"""
Weapons Page - Predefined weapons with level and awakening tracking.
All 28 weapons (7 rarities × 4 tiers) are shown.
"""
import streamlit as st
from utils.data_manager import save_user_data
from game.weapons import calculate_weapon_atk_str, BASE_ATK
from game.weapon_mastery import (
    ALL_WEAPONS, WEAPON_MASTERY_REWARDS, RARITIES,
    calculate_mastery_stages_from_weapons, calculate_mastery_stats
)
from optimizers.weapon_optimizer import (
    calculate_optimal_enhancer_allocation, find_best_potential_weapon,
    get_max_level
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

# Auto-equip the best weapon if none is selected but weapons exist
if not data.equipped_weapon_key and data.weapons_data:
    best_key = ""
    best_atk = 0.0
    for key, weapon_data in data.weapons_data.items():
        level = weapon_data.get('level', 0)
        if level <= 0:
            continue
        parts = key.rsplit('_', 1)
        if len(parts) != 2:
            continue
        rarity, tier = parts[0], int(parts[1])
        stats = calculate_weapon_atk_str(rarity, tier, level)
        on_equip_atk = stats['on_equip_atk']
        if on_equip_atk > best_atk:
            best_atk = on_equip_atk
            best_key = key
    if best_key:
        data.equipped_weapon_key = best_key
        auto_save()

st.title("🏹 Weapons")

st.info("""
**How Weapons Work:**
- Each weapon has a **Level** (affects ATK%) and **Awakening** (0-5 stars, affects Mastery bonuses)
- **Duplicates** track progress toward next awakening (A1=1, A2=2, A3=3, A4=4, A5=5 dupes each)
- Set Level to 0 if you don't own the weapon
- Only ONE weapon can be equipped at a time
- **Inventory ATK% = 25%** of On-Equip ATK% (always active for all owned weapons)
""")

# Create tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["All Weapons", "Equipped Weapon", "Stats Summary", "Mastery Bonuses", "Enhancer Optimizer"])

with tab1:
    st.subheader("All Weapons")
    st.markdown("Set **Level** (0 = not owned) and **Awakening** (0-5) for each weapon.")

    # Group by rarity (highest first)
    for rarity in ['ancient', 'mystic', 'legendary', 'unique', 'epic', 'rare', 'normal']:
        color = RARITY_COLORS.get(rarity, "#ffffff")
        st.markdown(f"### <span style='color:{color}'>{rarity.capitalize()}</span>", unsafe_allow_html=True)

        tiers = [1, 2, 3, 4]

        cols = st.columns(len(tiers))
        for i, tier in enumerate(tiers):
            key = f"{rarity}_{tier}"
            weapon_data = data.weapons_data.get(key, {'level': 0, 'awakening': 0, 'duplicates': 0})
            current_level = weapon_data.get('level', 0)
            current_awakening = weapon_data.get('awakening', 0)
            current_duplicates = weapon_data.get('duplicates', 0)

            # Calculate dupes needed for next milestone
            # A0→A1: 1, A1→A2: 2, ..., A4→A5: 5, A5→Promo: 5
            if current_awakening < 5:
                dupes_for_next = current_awakening + 1
                next_milestone = f"A{current_awakening + 1}"
            else:
                dupes_for_next = 5
                next_milestone = "Promo"

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

                # Duplicates input (progress toward next awakening/promotion)
                if level > 0:
                    duplicates = st.number_input(
                        f"Dupes →{next_milestone}",
                        min_value=0,
                        max_value=dupes_for_next - 1,  # Can't reach next level yet
                        value=min(current_duplicates, dupes_for_next - 1),
                        key=f"wdupes_{key}",
                        help=f"{current_duplicates}/{dupes_for_next} toward {next_milestone}"
                    )
                else:
                    duplicates = 0

                # Calculate and show ATK%
                if level > 0:
                    stats = calculate_weapon_atk_str(rarity, tier, level)
                    st.caption(f"+{stats['on_equip_atk']:.1f}% ATK")
                else:
                    st.caption("Not owned")

                # Save if changed
                new_data = {'level': level, 'awakening': awakening, 'duplicates': duplicates}
                if level != current_level or awakening != current_awakening or duplicates != current_duplicates:
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

    # Weapon Summoning Level
    st.markdown("### Weapon Summoning")
    summoning_level = st.number_input(
        "Summoning Level",
        min_value=1,
        max_value=17,
        value=getattr(data, 'summoning_level', 15),
        help="Your weapon summoning level (affects drop rates in Upgrade Optimizer)",
        key="weapon_summoning_level"
    )
    if summoning_level != getattr(data, 'summoning_level', 15):
        data.summoning_level = summoning_level
        auto_save()

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
            num_weapons = 4
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

with tab5:
    st.subheader("Enhancer Budget Optimizer")
    st.markdown("""
    Enter the number of weapon enhancers you have available, and get an optimal
    upgrade path that maximizes your ATK% gain.
    """)

    # Input for available enhancers
    available_enhancers = st.number_input(
        "Available Weapon Enhancers",
        min_value=0,
        max_value=1_000_000_000,
        value=st.session_state.get('weapon_enhancers', 0),
        step=10000,
        format="%d",
        help="Enter how many weapon enhancers you have to spend",
        key="enhancer_budget_input"
    )

    # Store in session state for persistence
    st.session_state.weapon_enhancers = available_enhancers

    # Auto-detect best weapon to treat as equipped
    best_weapon_key = find_best_potential_weapon(data.weapons_data)

    if best_weapon_key:
        best_parts = best_weapon_key.rsplit('_', 1)
        if len(best_parts) == 2:
            best_rarity, best_tier = best_parts[0], int(best_parts[1])
            best_awakening = data.weapons_data.get(best_weapon_key, {}).get('awakening', 0)
            best_max_level = get_max_level(best_awakening)
            best_stats = calculate_weapon_atk_str(best_rarity, best_tier, best_max_level)
            st.info(
                f"**Best Weapon (treated as equipped):** {best_rarity.capitalize()} T{best_tier} "
                f"(max level {best_max_level} with {best_awakening} awakening, "
                f"potential +{best_stats['on_equip_atk']:.1f}% ATK)"
            )

    if available_enhancers > 0:
        recommendations, equipped_key = calculate_optimal_enhancer_allocation(
            weapons_data=data.weapons_data,
            available_enhancers=available_enhancers,
            equipped_weapon_key=None,  # Auto-detect best weapon
        )

        if recommendations:
            st.markdown("### Recommended Upgrades")

            # Summary line (user's requested format)
            summary_parts = []
            for rec in recommendations:
                name = f"{rec.display_name.replace(' (Equipped)', '')}"
                summary_parts.append(f"{name}: {rec.from_level}→{rec.to_level}")

            st.success(", ".join(summary_parts))

            # Totals
            total_cost = sum(r.cost for r in recommendations)
            total_gain = sum(r.atk_gain for r in recommendations)
            remaining = available_enhancers - total_cost

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Cost", f"{total_cost:,} enhancers")
            with col2:
                st.metric("Total ATK% Gain", f"+{total_gain:.1f}%")
            with col3:
                st.metric("Remaining", f"{remaining:,} enhancers")

            # Detailed table
            st.markdown("### Upgrade Details")
            table_data = []
            for rec in recommendations:
                table_data.append({
                    "Weapon": rec.display_name,
                    "Upgrade": f"{rec.from_level} → {rec.to_level}",
                    "Levels": rec.to_level - rec.from_level,
                    "Cost": f"{rec.cost:,}",
                    "ATK% Gain": f"+{rec.atk_gain:.1f}%",
                })

            st.dataframe(table_data, use_container_width=True, hide_index=True)

            # Explanation
            with st.expander("How does this work?"):
                st.markdown("""
                The optimizer uses a **greedy algorithm** that allocates enhancers one level at a time,
                always choosing the upgrade with the best ATK%/enhancer efficiency.

                **Key assumptions:**
                - The weapon with the highest potential ATK% (based on awakening level cap) is treated as "equipped"
                - Equipped weapons contribute full ATK% + inventory bonus (125% total)
                - Non-equipped weapons only contribute inventory bonus (25-28.57% depending on rarity)
                - Higher level upgrades cost more enhancers but give the same ATK% per level (within level ranges)

                This greedy approach is **mathematically optimal** because all weapons have diminishing
                returns on efficiency (cost increases exponentially, ATK gain stays linear).
                """)
        else:
            st.warning("No upgrades recommended. Either all weapons are at max level or the budget is too small for any upgrade.")
    else:
        # Show owned weapons that can be upgraded
        upgradeable = []
        for key, weapon_data in data.weapons_data.items():
            level = weapon_data.get('level', 0)
            if level <= 0:
                continue
            awakening = weapon_data.get('awakening', 0)
            max_level = get_max_level(awakening)
            if level < max_level:
                parts = key.rsplit('_', 1)
                if len(parts) == 2:
                    rarity, tier = parts[0], int(parts[1])
                    upgradeable.append({
                        "Weapon": f"{rarity.capitalize()} T{tier}",
                        "Current Level": level,
                        "Max Level": max_level,
                        "Awakening": awakening,
                    })

        if upgradeable:
            st.markdown("### Weapons Available for Upgrade")
            st.dataframe(upgradeable, use_container_width=True, hide_index=True)
        else:
            st.info("No weapons available for upgrade. Add weapons with Level > 0 in the 'All Weapons' tab.")
