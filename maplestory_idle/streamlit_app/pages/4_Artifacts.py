"""
Artifacts Page
Configure equipped artifacts, inventory effects, potentials, and cost calculator.
Matches the original Tkinter app artifacts tab.
"""
import streamlit as st
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.data_manager import save_user_data
from artifacts import (
    ARTIFACTS, ArtifactTier, PotentialTier,
    ArtifactDefinition, ArtifactInstance, ArtifactConfig, ArtifactPotentialLine,
    POTENTIAL_SLOT_UNLOCKS, ARTIFACT_DROP_RATES, ARTIFACT_CHEST_COSTS,
    calculate_hex_multiplier, calculate_book_of_ancient_bonus,
    calculate_artifact_upgrade_efficiency, calculate_specific_legendary_cost,
    TOTAL_DUPLICATES_TO_STAR,
)

st.set_page_config(page_title="Artifacts", page_icon="💎", layout="wide")

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
    .stat-value { color: #7fff7f; font-weight: bold; }
    .result-box {
        background: #2a2a4e;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        font-family: monospace;
    }
    .tier-legendary { color: #7fff7f; }
    .tier-unique { color: #ffaa00; }
    .tier-epic { color: #aa77ff; }
</style>
""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

# Build artifact name lists
ARTIFACT_NAMES_BY_TIER = {
    ArtifactTier.LEGENDARY: [],
    ArtifactTier.UNIQUE: [],
    ArtifactTier.EPIC: [],
}
ALL_ARTIFACT_NAMES = ["(Empty)"]
ARTIFACT_KEY_BY_NAME = {}

for key, defn in ARTIFACTS.items():
    ARTIFACT_NAMES_BY_TIER[defn.tier].append(defn.name)
    ALL_ARTIFACT_NAMES.append(defn.name)
    ARTIFACT_KEY_BY_NAME[defn.name] = key

TIER_COLORS = {
    ArtifactTier.LEGENDARY: "#7fff7f",
    ArtifactTier.UNIQUE: "#ffaa00",
    ArtifactTier.EPIC: "#aa77ff",
}

POTENTIAL_STATS = ["---", "main_stat", "damage", "boss_damage", "normal_damage",
                   "def_pen", "crit_rate", "min_max_damage"]
POTENTIAL_TIERS = ["rare", "epic", "unique", "legendary", "mystic"]


def auto_save():
    save_user_data(st.session_state.username, data)


def ensure_artifact_data():
    """Ensure artifact data structures exist."""
    if not hasattr(data, 'artifacts_equipped') or not data.artifacts_equipped:
        data.artifacts_equipped = {}
    if not hasattr(data, 'artifacts_inventory') or not data.artifacts_inventory:
        data.artifacts_inventory = {}
    if not hasattr(data, 'artifacts_resonance') or not data.artifacts_resonance:
        data.artifacts_resonance = {'total_stars': 0, 'main_stat_bonus': 0, 'hp_bonus': 0}

    # Initialize equipped slots
    for i in range(3):
        slot_key = f'slot{i}'
        if slot_key not in data.artifacts_equipped:
            data.artifacts_equipped[slot_key] = {'name': '', 'stars': 0, 'potentials': []}


def get_artifact_definition(name: str):
    """Get artifact definition by name."""
    key = ARTIFACT_KEY_BY_NAME.get(name)
    if key:
        return ARTIFACTS.get(key)
    return None


def calculate_inventory_stats():
    """Calculate total stats from artifact inventory."""
    stats = {
        'attack_flat': 0, 'damage': 0, 'boss_damage': 0, 'normal_damage': 0,
        'crit_damage': 0, 'def_pen': 0, 'max_damage_mult': 0, 'main_stat': 0,
    }

    for art_key, art_data in data.artifacts_inventory.items():
        if art_key not in ARTIFACTS:
            continue
        # Handle case where art_data might be a non-dict value
        if not isinstance(art_data, dict):
            continue
        defn = ARTIFACTS[art_key]
        stars = art_data.get('stars', 0)
        if not isinstance(stars, (int, float)):
            stars = 0

        # Inventory effect
        inv_stat = defn.inventory_stat
        inv_value = defn.get_inventory_value(int(stars))
        if inv_stat in stats:
            stats[inv_stat] += inv_value

        # Potentials
        potentials = art_data.get('potentials', [])
        if isinstance(potentials, list):
            for pot in potentials:
                if isinstance(pot, dict):
                    pot_stat = pot.get('stat', '')
                    pot_value = pot.get('value', 0)
                    if pot_stat in stats and isinstance(pot_value, (int, float)):
                        # Potentials are stored as percentages, convert to decimal
                        stats[pot_stat] += pot_value / 100.0

    return stats


def calculate_active_effects():
    """Calculate active effects from equipped artifacts."""
    effects = {
        'hex_multiplier': None,
        'crit_rate': 0,
        'crit_damage_book': 0,
        'boss_damage': 0,
        'final_damage': 0,
    }

    equipped_names = []
    for i in range(3):
        slot_data = data.artifacts_equipped.get(f'slot{i}', {})
        if not isinstance(slot_data, dict):
            continue
        name = slot_data.get('name', '')
        if name and name != '(Empty)':
            stars = slot_data.get('stars', 0)
            if not isinstance(stars, (int, float)):
                stars = 0
            equipped_names.append((name, int(stars)))

    # Calculate specific artifact effects
    for name, stars in equipped_names:
        key = ARTIFACT_KEY_BY_NAME.get(name)
        if not key:
            continue

        if key == 'hexagon_necklace':
            effects['hex_multiplier'] = calculate_hex_multiplier(stars, stacks=3)

        elif key == 'book_of_ancient':
            # Estimate current crit rate (simplified)
            base_cr = 0.50  # 50% base assumption
            cr_bonus, cd_bonus = calculate_book_of_ancient_bonus(stars, base_cr)
            effects['crit_rate'] = cr_bonus
            effects['crit_damage_book'] = cd_bonus

        elif key == 'star_rock':
            defn = ARTIFACTS[key]
            effects['boss_damage'] += defn.get_active_value(stars)

        elif key in ['chalice', 'lit_lamp', 'soul_contract', 'ancient_text_piece', 'clear_spring_water']:
            defn = ARTIFACTS[key]
            if 'final_damage' in defn.active_stat:
                effects['final_damage'] += defn.get_active_value(stars)

    return effects


ensure_artifact_data()

st.title("💎 Artifacts")

# Create tabs
tab_config, tab_calculator = st.tabs(["Configuration", "Cost Calculator"])

# ============================================================================
# TAB 1: ARTIFACT CONFIGURATION
# ============================================================================
with tab_config:
    col_left, col_right = st.columns([1, 1])

    # ========== LEFT COLUMN ==========
    with col_left:
        # EQUIPPED ARTIFACTS (3 slots)
        st.markdown("<div class='section-header'>Equipped Artifacts (Active Effects)</div>", unsafe_allow_html=True)

        for slot_idx in range(3):
            slot_key = f'slot{slot_idx}'
            slot_data = data.artifacts_equipped.get(slot_key, {'name': '', 'stars': 0})

            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                current_name = slot_data.get('name', '')
                current_idx = ALL_ARTIFACT_NAMES.index(current_name) if current_name in ALL_ARTIFACT_NAMES else 0
                new_name = st.selectbox(
                    f"Slot {slot_idx + 1}",
                    options=ALL_ARTIFACT_NAMES,
                    index=current_idx,
                    key=f"equipped_art_{slot_idx}",
                    format_func=lambda x: x if x != "(Empty)" else "--- Empty ---"
                )
                if new_name != current_name:
                    slot_data['name'] = new_name if new_name != "(Empty)" else ""
                    # Sync stars from inventory if available
                    art_key = ARTIFACT_KEY_BY_NAME.get(new_name)
                    if art_key and art_key in data.artifacts_inventory:
                        slot_data['stars'] = data.artifacts_inventory[art_key].get('stars', 0)
                    data.artifacts_equipped[slot_key] = slot_data
                    auto_save()

            with col2:
                st.markdown(f"<br>", unsafe_allow_html=True)
                st.markdown(f"★{slot_data.get('stars', 0)}")

            with col3:
                # Show tier color
                defn = get_artifact_definition(slot_data.get('name', ''))
                if defn:
                    color = TIER_COLORS.get(defn.tier, "#888")
                    st.markdown(f"<br><span style='color:{color};'>{defn.tier.value.title()}</span>", unsafe_allow_html=True)

        # ACTIVE EFFECTS SUMMARY
        st.markdown("---")
        st.markdown("<div class='section-header'>Active Effect Summary</div>", unsafe_allow_html=True)

        effects = calculate_active_effects()

        effect_rows = [
            ("Hex Multiplier", f"×{effects['hex_multiplier']:.2f}" if effects['hex_multiplier'] else "---"),
            ("Crit Rate", f"+{effects['crit_rate']*100:.0f}%" if effects['crit_rate'] else "---"),
            ("Crit Dmg (Book)", f"+{effects['crit_damage_book']*100:.1f}%" if effects['crit_damage_book'] else "---"),
            ("Boss Damage", f"+{effects['boss_damage']*100:.1f}%" if effects['boss_damage'] else "---"),
            ("Final Damage", f"+{effects['final_damage']*100:.1f}%" if effects['final_damage'] else "---"),
        ]

        for label, value in effect_rows:
            st.markdown(f"<div class='stat-row'><span class='stat-label'>{label}:</span> <span class='stat-value'>{value}</span></div>", unsafe_allow_html=True)

        # ARTIFACT INVENTORY
        st.markdown("---")
        st.markdown("<div class='section-header'>Artifact Inventory (Awakening Levels)</div>", unsafe_allow_html=True)

        with st.container(height=300):
            for tier_name, tier_enum in [("Legendary", ArtifactTier.LEGENDARY), ("Unique", ArtifactTier.UNIQUE), ("Epic", ArtifactTier.EPIC)]:
                tier_artifacts = [(k, v) for k, v in ARTIFACTS.items() if v.tier == tier_enum]
                if not tier_artifacts:
                    continue

                tier_color = TIER_COLORS.get(tier_enum, "#888")
                st.markdown(f"<span style='color:{tier_color}; font-weight:bold;'>── {tier_name} ──</span>", unsafe_allow_html=True)

                for art_key, defn in tier_artifacts:
                    if art_key not in data.artifacts_inventory:
                        data.artifacts_inventory[art_key] = {'stars': 0, 'potentials': []}

                    art_data = data.artifacts_inventory[art_key]

                    col1, col2, col3 = st.columns([3, 1, 1])

                    with col1:
                        st.markdown(f"<span style='color:{tier_color};'>{defn.name}</span>", unsafe_allow_html=True)

                    with col2:
                        current_stars = art_data.get('stars', 0)
                        new_stars = st.selectbox(
                            "★",
                            options=list(range(6)),
                            index=current_stars,
                            key=f"inv_stars_{art_key}",
                            label_visibility="collapsed"
                        )
                        if new_stars != current_stars:
                            art_data['stars'] = new_stars
                            data.artifacts_inventory[art_key] = art_data
                            # Update equipped artifacts if this one is equipped
                            for i in range(3):
                                slot = data.artifacts_equipped.get(f'slot{i}', {})
                                if ARTIFACT_KEY_BY_NAME.get(slot.get('name', '')) == art_key:
                                    slot['stars'] = new_stars
                            auto_save()
                            st.rerun()

                    with col3:
                        inv_value = defn.get_inventory_value(art_data.get('stars', 0))
                        st.markdown(f"+{inv_value*100:.1f}%" if inv_value < 10 else f"+{inv_value:.0f}")

    # ========== RIGHT COLUMN ==========
    with col_right:
        # INVENTORY EFFECTS SUMMARY
        st.markdown("<div class='section-header'>Inventory Effects (Always Active)</div>", unsafe_allow_html=True)

        inv_stats = calculate_inventory_stats()

        inv_display = [
            ("Attack Flat", f"+{inv_stats['attack_flat']:,.0f}"),
            ("Damage %", f"+{inv_stats['damage']*100:.1f}%"),
            ("Boss Damage %", f"+{inv_stats['boss_damage']*100:.1f}%"),
            ("Normal Damage %", f"+{inv_stats['normal_damage']*100:.1f}%"),
            ("Crit Damage %", f"+{inv_stats['crit_damage']*100:.1f}%"),
            ("Def Pen %", f"+{inv_stats['def_pen']*100:.1f}%"),
            ("Max Dmg Mult %", f"+{inv_stats['max_damage_mult']*100:.1f}%"),
        ]

        for label, value in inv_display:
            st.markdown(f"<div class='stat-row'><span class='stat-label'>{label}:</span> <span class='stat-value'>{value}</span></div>", unsafe_allow_html=True)

        # RESONANCE
        st.markdown("---")
        st.markdown("<div class='section-header'>Resonance (Editable)</div>", unsafe_allow_html=True)

        # Calculate resonance from inventory (with type safety)
        def get_stars_safe(art_data):
            if isinstance(art_data, dict):
                stars = art_data.get('stars', 0)
                return int(stars) if isinstance(stars, (int, float)) else 0
            return 0

        calculated_stars = sum(get_stars_safe(art) for art in data.artifacts_inventory.values())
        calculated_main_stat = calculated_stars * 10  # 10 main stat per star
        calculated_hp = calculated_stars * 100  # 100 HP per star

        col1, col2 = st.columns(2)

        with col1:
            res_stars = st.number_input(
                "Total Stars",
                min_value=0, max_value=500,
                value=data.artifacts_resonance.get('total_stars', calculated_stars),
                key="res_stars"
            )
            if res_stars != data.artifacts_resonance.get('total_stars'):
                data.artifacts_resonance['total_stars'] = res_stars
                auto_save()
            st.caption(f"(calc: ★{calculated_stars})")

        with col2:
            res_main = st.number_input(
                "Main Stat Bonus",
                min_value=0, max_value=10000,
                value=data.artifacts_resonance.get('main_stat_bonus', calculated_main_stat),
                key="res_main"
            )
            if res_main != data.artifacts_resonance.get('main_stat_bonus'):
                data.artifacts_resonance['main_stat_bonus'] = res_main
                auto_save()
            st.caption(f"(calc: +{calculated_main_stat})")

        res_hp = st.number_input(
            "HP Bonus",
            min_value=0, max_value=100000,
            value=data.artifacts_resonance.get('hp_bonus', calculated_hp),
            key="res_hp"
        )
        if res_hp != data.artifacts_resonance.get('hp_bonus'):
            data.artifacts_resonance['hp_bonus'] = res_hp
            auto_save()
        st.caption(f"(calc: +{calculated_hp})")

        # ARTIFACT POTENTIALS
        st.markdown("---")
        st.markdown("<div class='section-header'>Artifact Potentials</div>", unsafe_allow_html=True)

        # Artifact selector for potentials
        pot_artifact_names = [defn.name for defn in ARTIFACTS.values()]
        selected_pot_artifact = st.selectbox(
            "Select Artifact",
            options=pot_artifact_names,
            key="pot_artifact_selector"
        )

        selected_key = ARTIFACT_KEY_BY_NAME.get(selected_pot_artifact)
        if selected_key and selected_key in data.artifacts_inventory:
            art_data = data.artifacts_inventory[selected_key]
            stars = art_data.get('stars', 0)
            slots_unlocked = POTENTIAL_SLOT_UNLOCKS.get(stars, 0)
            defn = ARTIFACTS[selected_key]

            # Non-legendary capped at 2 slots
            if defn.tier != ArtifactTier.LEGENDARY and slots_unlocked > 2:
                slots_unlocked = 2

            st.caption(f"★{stars} → {slots_unlocked} potential slot(s) unlocked")

            # Initialize potentials if needed
            if 'potentials' not in art_data:
                art_data['potentials'] = []

            # Ensure 3 potential slots
            while len(art_data['potentials']) < 3:
                art_data['potentials'].append({'stat': '', 'value': 0, 'tier': 'legendary'})

            potentials_changed = False

            for i in range(3):
                enabled = i < slots_unlocked
                pot = art_data['potentials'][i]

                col1, col2, col3 = st.columns([2, 1, 1])

                with col1:
                    current_stat = pot.get('stat', '')
                    stat_idx = POTENTIAL_STATS.index(current_stat) if current_stat in POTENTIAL_STATS else 0
                    new_stat = st.selectbox(
                        f"Slot {i+1} Stat",
                        options=POTENTIAL_STATS,
                        index=stat_idx,
                        key=f"pot_stat_{selected_key}_{i}",
                        disabled=not enabled,
                        format_func=lambda x: x.replace("_", " ").title() if x != "---" else "---"
                    )
                    if new_stat != current_stat:
                        pot['stat'] = new_stat if new_stat != "---" else ""
                        potentials_changed = True

                with col2:
                    new_value = st.number_input(
                        "Value %",
                        min_value=0.0, max_value=30.0,
                        value=float(pot.get('value', 0)),
                        step=0.5,
                        key=f"pot_val_{selected_key}_{i}",
                        disabled=not enabled,
                        label_visibility="collapsed"
                    )
                    if new_value != pot.get('value', 0):
                        pot['value'] = new_value
                        potentials_changed = True

                with col3:
                    current_tier = pot.get('tier', 'legendary')
                    tier_idx = POTENTIAL_TIERS.index(current_tier) if current_tier in POTENTIAL_TIERS else 3
                    new_tier = st.selectbox(
                        "Tier",
                        options=POTENTIAL_TIERS,
                        index=tier_idx,
                        key=f"pot_tier_{selected_key}_{i}",
                        disabled=not enabled,
                        label_visibility="collapsed"
                    )
                    if new_tier != current_tier:
                        pot['tier'] = new_tier
                        potentials_changed = True

            if potentials_changed:
                data.artifacts_inventory[selected_key] = art_data
                auto_save()

        else:
            st.info("Set awakening stars in the inventory first.")

# ============================================================================
# TAB 2: COST CALCULATOR
# ============================================================================
with tab_calculator:
    col_calc, col_synth = st.columns([1, 1])

    with col_calc:
        st.markdown("<div class='section-header'>Artifact Upgrade Cost</div>", unsafe_allow_html=True)

        # Artifact selector with tier info
        calc_artifact_options = [f"{v.name} ({v.tier.value.title()})" for k, v in ARTIFACTS.items()]
        selected_calc = st.selectbox(
            "Select Artifact",
            options=calc_artifact_options,
            key="calc_artifact_selector"
        )

        # Parse selection
        calc_artifact_name = selected_calc.rsplit(" (", 1)[0] if selected_calc else ""
        calc_artifact_key = ARTIFACT_KEY_BY_NAME.get(calc_artifact_name)

        col1, col2 = st.columns(2)
        with col1:
            current_stars = st.selectbox("Current ★", options=list(range(6)), index=0, key="calc_current")
        with col2:
            target_stars = st.selectbox("Target ★", options=list(range(6)), index=5, key="calc_target")

        if st.button("Calculate Cost", type="primary", key="calc_btn"):
            if calc_artifact_key:
                result = calculate_artifact_upgrade_efficiency(calc_artifact_key, current_stars, target_stars)

                if 'error' not in result:
                    drop_rate = ARTIFACT_DROP_RATES.get(calc_artifact_key, 0)
                    dupes_needed = TOTAL_DUPLICATES_TO_STAR.get(target_stars, 0) - TOTAL_DUPLICATES_TO_STAR.get(current_stars, 0)

                    st.session_state.calc_result = {
                        'drop_rate': drop_rate,
                        'dupes_needed': dupes_needed,
                        'expected_chests': result.get('expected_chests', 0),
                        'blue_diamonds': result.get('blue_diamonds', 0),
                        'effect_gain': result.get('effect_gain', '---'),
                    }
                else:
                    st.error(result.get('error', 'Unknown error'))

        st.markdown("---")
        st.markdown("**RESULTS**")

        if 'calc_result' in st.session_state:
            r = st.session_state.calc_result
            results_display = [
                ("Drop Rate", f"{r['drop_rate']*100:.4f}%" if r['drop_rate'] else "Unknown"),
                ("Duplicates Needed", f"{r['dupes_needed']}"),
                ("Expected Chests", f"{r['expected_chests']:,.0f}"),
                ("Blue Diamonds", f"{r['blue_diamonds']:,.0f}"),
                ("Effect Gain", str(r['effect_gain'])),
            ]

            for label, value in results_display:
                st.markdown(f"<div class='stat-row'><span class='stat-label'>{label}:</span> <span class='stat-value'>{value}</span></div>", unsafe_allow_html=True)
        else:
            st.info("Click Calculate to see results")

    with col_synth:
        st.markdown("<div class='section-header'>Synthesis vs Direct Drop</div>", unsafe_allow_html=True)

        st.caption("For Legendary artifacts only")

        # Get legendary artifacts
        legendary_artifacts = [f"{v.name}" for k, v in ARTIFACTS.items() if v.tier == ArtifactTier.LEGENDARY]
        selected_legendary = st.selectbox(
            "Select Legendary Artifact",
            options=legendary_artifacts,
            key="synth_selector"
        )

        legendary_key = ARTIFACT_KEY_BY_NAME.get(selected_legendary)

        if st.button("Compare Methods", key="synth_btn"):
            if legendary_key:
                synth_result = calculate_specific_legendary_cost(legendary_key)

                if 'error' not in synth_result:
                    st.session_state.synth_result = synth_result

        st.markdown("---")

        if 'synth_result' in st.session_state:
            r = st.session_state.synth_result

            if 'direct_drop' in r:
                st.markdown("**Direct Drop Method:**")
                st.markdown(f"- Expected Chests: **{r['direct_drop']['chests']:,.0f}**")
                st.markdown(f"- Blue Diamonds: **{r['direct_drop']['diamonds']:,.0f}**")

                st.markdown("---")
                st.markdown("**Synthesis Method:**")
                st.markdown(f"- Expected Chests: **{r['synthesis']['chests']:,.0f}**")
                st.markdown(f"- Blue Diamonds: **{r['synthesis']['diamonds']:,.0f}**")

                st.markdown("---")
                rec_color = "#7bed9f" if r['recommendation'] == "Direct drop" else "#ff9f43"
                st.markdown(f"**Recommendation:** <span style='color:{rec_color};'>{r['recommendation']}</span>", unsafe_allow_html=True)
        else:
            st.info("Click Compare Methods to see analysis")

        st.markdown("---")
        st.markdown("<div class='section-header'>Chest Costs Reference</div>", unsafe_allow_html=True)

        st.markdown(f"""
        <div class='result-box'>
        <strong>Blue Diamond Shop:</strong> {ARTIFACT_CHEST_COSTS['blue_diamond']:,} diamonds/chest<br>
        <strong>Red Diamond Shop:</strong> {ARTIFACT_CHEST_COSTS['red_diamond']:,} diamonds/chest<br>
        <strong>Arena Shop:</strong> {ARTIFACT_CHEST_COSTS['arena_coin']:,} coins/chest (FREE)
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        **Drop Rate Tiers:**
        - Epic: ~89.5% (common)
        - Unique: ~9.5% (uncommon)
        - Legendary: ~1% (rare)
        - Specific Legendary: ~0.07% each
        """)
