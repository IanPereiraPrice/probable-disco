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
    ARTIFACTS, ArtifactTier, PotentialTier, CombatScenario,
    ArtifactDefinition, ArtifactInstance, ArtifactConfig, ArtifactPotentialLine,
    POTENTIAL_SLOT_UNLOCKS, ARTIFACT_DROP_RATES, ARTIFACT_CHEST_COSTS,
    MAX_POTENTIAL_SLOTS_BY_TIER, POTENTIAL_VALUES,
    calculate_hex_multiplier, calculate_book_of_ancient_bonus,
    calculate_artifact_upgrade_efficiency, calculate_specific_legendary_cost,
    TOTAL_DUPLICATES_TO_STAR, TOTAL_DUPLICATES_BY_TIER,
    calculate_resonance_max_level, calculate_resonance_hp, calculate_resonance_main_stat,
)
from artifact_optimizer import (
    calculate_chest_expected_value,
    calculate_awakening_efficiency,
    calculate_resonance_leveling_efficiency,
    calculate_artifact_reroll_efficiency,
    get_artifact_ranking_for_equip,
    get_scenario_duration,
    ArtifactDPSScore,
    CHEST_COST_BLUE,
)
from stage_settings import get_fight_duration_from_string
from utils.dps_calculator import aggregate_stats, calculate_dps as shared_calculate_dps

st.set_page_config(page_title="Artifacts", page_icon="💎", layout="wide")


def calculate_dps(stats, mode='stage'):
    """Wrapper that respects user's realistic DPS setting."""
    use_realistic = getattr(st.session_state.user_data, 'use_realistic_dps', False)
    boss_importance = getattr(st.session_state.user_data, 'boss_importance', 70) / 100.0
    return shared_calculate_dps(stats, mode, use_realistic_dps=use_realistic, boss_importance=boss_importance)

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

POTENTIAL_STATS = ["---", "main_stat_pct", "damage", "boss_damage", "normal_damage",
                   "def_pen", "crit_rate", "min_damage_mult", "max_damage_mult"]
# Tiers for display - mystic_high is the 25% chance higher roll
POTENTIAL_TIERS = ["rare", "epic", "unique", "legendary", "mystic", "mystic_high"]

# Map UI stat names to POTENTIAL_VALUES keys (most are 1:1 now)
STAT_TO_POTENTIAL_KEY = {
    "main_stat_pct": "main_stat_pct",
    "damage": "damage",
    "boss_damage": "boss_damage",
    "normal_damage": "normal_damage",
    "def_pen": "def_pen",
    "crit_rate": "crit_rate",
    "min_damage_mult": "min_damage_mult",
    "max_damage_mult": "max_damage_mult",
}

def get_potential_value(stat: str, tier: str) -> float:
    """Get the fixed value for a potential stat + tier combo."""
    if not stat or stat == "---":
        return 0.0

    pot_key = STAT_TO_POTENTIAL_KEY.get(stat, stat)
    if pot_key not in POTENTIAL_VALUES:
        return 0.0

    # Handle mystic_high as the high roll of mystic
    is_high = tier == "mystic_high"
    actual_tier = "mystic" if is_high else tier

    tier_enum = {
        "rare": PotentialTier.RARE,
        "epic": PotentialTier.EPIC,
        "unique": PotentialTier.UNIQUE,
        "legendary": PotentialTier.LEGENDARY,
        "mystic": PotentialTier.MYSTIC,
    }.get(actual_tier)

    if not tier_enum or tier_enum not in POTENTIAL_VALUES[pot_key]:
        return 0.0

    low_val, high_val = POTENTIAL_VALUES[pot_key][tier_enum]
    return high_val if is_high else low_val


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
        'crit_damage': 0, 'crit_rate': 0, 'def_pen': 0, 'max_damage_mult': 0,
        'basic_attack_damage': 0, 'main_stat': 0,
        # Utility stats (non-DPS)
        'defense': 0, 'evasion': 0, 'debuff_tolerance': 0, 'damage_taken_decrease': 0,
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


def calculate_active_effects(scenario: str = "normal", fight_duration: float = 60.0):
    """Calculate active effects from equipped artifacts for a given scenario.

    Args:
        scenario: Combat scenario string (e.g., 'normal', 'boss', 'chapter_hunt')
        fight_duration: Fight duration in seconds for uptime calculations
    """
    from artifacts import EffectType

    effects = {
        'hex_multiplier': None,
        'crit_rate': 0,
        'crit_damage': 0,
        'crit_damage_book': 0,
        'boss_damage': 0,
        'normal_damage': 0,
        'final_damage': 0,
        'attack_buff': 0,  # From Charm, Old Music Box
        'enemy_damage_taken': 0,  # Silver Pendant
        'damage': 0,  # General damage %
        'uptime_notes': [],  # For displaying uptime info
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

    # Calculate specific artifact effects using active_effects
    for name, stars in equipped_names:
        key = ARTIFACT_KEY_BY_NAME.get(name)
        if not key or key not in ARTIFACTS:
            continue

        defn = ARTIFACTS[key]

        # Check if artifact applies to current scenario
        if not defn.applies_to_scenario(scenario):
            effects['uptime_notes'].append(f"{defn.name}: Not active (requires {defn.scenario})")
            continue

        # Skip artifacts without active effects
        if not defn.active_effects:
            continue

        uptime = defn.get_effective_uptime(fight_duration)

        # Special handling for specific artifacts
        if key == 'hexagon_necklace':
            effects['hex_multiplier'] = calculate_hex_multiplier(stars, stacks=3)
            if uptime < 1.0:
                effects['uptime_notes'].append(f"{defn.name}: ~{uptime*100:.0f}% uptime (ramp)")
            continue

        if key == 'book_of_ancient':
            # Estimate current crit rate (simplified)
            base_cr = 0.50  # 50% base assumption
            cr_bonus, cd_bonus = calculate_book_of_ancient_bonus(stars, base_cr)
            effects['crit_rate'] += cr_bonus
            effects['crit_damage_book'] = cd_bonus
            continue

        # Process all active_effects
        for effect in defn.active_effects:
            # Skip derived effects - they're calculated separately
            if effect.effect_type == EffectType.DERIVED:
                continue

            stat = effect.stat
            value = effect.get_value(stars) * uptime

            # Handle per-target effects (Fire Flower)
            if effect.max_stacks > 0 and stat == 'final_damage':
                targets = 5 if scenario == 'normal' else 1
                value = value * min(targets, effect.max_stacks)
                effects['uptime_notes'].append(f"{defn.name}: {targets} targets")

            # Map stats to effects dict
            if stat == 'boss_damage':
                effects['boss_damage'] += value
            elif stat == 'normal_damage':
                effects['normal_damage'] += value
            elif stat == 'crit_damage':
                effects['crit_damage'] += value
            elif stat == 'crit_rate':
                effects['crit_rate'] += value
            elif stat == 'final_damage':
                effects['final_damage'] += value
                if defn.scenario:
                    effects['uptime_notes'].append(f"{defn.name}: Active ({scenario})")
            elif stat == 'attack_buff':
                effects['attack_buff'] += value
                if uptime < 1.0:
                    effects['uptime_notes'].append(f"{defn.name}: ~{uptime*100:.0f}% uptime")
            elif stat == 'enemy_damage_taken':
                effects['enemy_damage_taken'] += value
                if uptime < 1.0:
                    effects['uptime_notes'].append(f"{defn.name}: ~{uptime*100:.0f}% proc rate")
            elif stat in ('damage', 'damage_multiplier'):
                effects['damage'] += value

    return effects


ensure_artifact_data()

st.title("💎 Artifacts")

# Create tabs
tab_config, tab_calculator, tab_efficiency = st.tabs(["Configuration", "Cost Calculator", "Efficiency Analysis"])

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

        # Scenario selector
        scenario_options = {
            "Normal Hunting": "normal",
            "World Boss": "world_boss",
            "Guild Dungeon": "guild",
            "Growth Dungeon": "growth",
            "Arena": "arena",
            "Chapter Hunt": "chapter",
            "Zakum Raid": "zakum",
        }
        selected_scenario_label = st.selectbox(
            "Scenario",
            options=list(scenario_options.keys()),
            index=0,
            key="artifact_scenario",
            help="Select combat scenario to see which artifact effects are active"
        )
        selected_scenario = scenario_options[selected_scenario_label]

        # Get fight duration from user's combat mode setting
        fight_duration = get_fight_duration_from_string(data.combat_mode)

        effects = calculate_active_effects(selected_scenario, fight_duration)

        effect_rows = [
            ("Hex Multiplier", f"×{effects['hex_multiplier']:.2f}" if effects['hex_multiplier'] else "---"),
            ("Crit Rate", f"+{effects['crit_rate']*100:.0f}%" if effects['crit_rate'] else "---"),
            ("Crit Dmg (Book)", f"+{effects['crit_damage_book']*100:.1f}%" if effects['crit_damage_book'] else "---"),
            ("Crit Dmg", f"+{effects['crit_damage']*100:.1f}%" if effects['crit_damage'] else "---"),
            ("Boss Damage", f"+{effects['boss_damage']*100:.1f}%" if effects['boss_damage'] else "---"),
            ("Normal Damage", f"+{effects['normal_damage']*100:.1f}%" if effects['normal_damage'] else "---"),
            ("Final Damage", f"+{effects['final_damage']*100:.1f}%" if effects['final_damage'] else "---"),
            ("ATK Buff", f"+{effects['attack_buff']*100:.1f}%" if effects['attack_buff'] else "---"),
            ("Enemy Dmg Taken", f"+{effects['enemy_damage_taken']*100:.1f}%" if effects['enemy_damage_taken'] else "---"),
        ]

        for label, value in effect_rows:
            if value != "---":
                st.markdown(f"<div class='stat-row'><span class='stat-label'>{label}:</span> <span class='stat-value'>{value}</span></div>", unsafe_allow_html=True)

        # Show uptime notes
        if effects['uptime_notes']:
            st.caption("Notes:")
            for note in effects['uptime_notes']:
                st.caption(f"• {note}")

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

        # DPS stats
        st.markdown("**DPS Stats:**")
        inv_display_dps = [
            ("Attack Flat", f"+{inv_stats['attack_flat']:,.0f}", inv_stats['attack_flat'] > 0),
            ("Damage %", f"+{inv_stats['damage']*100:.1f}%", inv_stats['damage'] > 0),
            ("Boss Damage %", f"+{inv_stats['boss_damage']*100:.1f}%", inv_stats['boss_damage'] > 0),
            ("Normal Damage %", f"+{inv_stats['normal_damage']*100:.1f}%", inv_stats['normal_damage'] > 0),
            ("Crit Rate %", f"+{inv_stats['crit_rate']*100:.1f}%", inv_stats['crit_rate'] > 0),
            ("Crit Damage %", f"+{inv_stats['crit_damage']*100:.1f}%", inv_stats['crit_damage'] > 0),
            ("Def Pen %", f"+{inv_stats['def_pen']*100:.1f}%", inv_stats['def_pen'] > 0),
            ("Max Dmg Mult %", f"+{inv_stats['max_damage_mult']*100:.1f}%", inv_stats['max_damage_mult'] > 0),
            ("Basic ATK Dmg %", f"+{inv_stats['basic_attack_damage']*100:.1f}%", inv_stats['basic_attack_damage'] > 0),
        ]

        for label, value, show in inv_display_dps:
            if show:
                st.markdown(f"<div class='stat-row'><span class='stat-label'>{label}:</span> <span class='stat-value'>{value}</span></div>", unsafe_allow_html=True)

        # Utility stats
        utility_stats = [
            ("Defense %", f"+{inv_stats['defense']*100:.1f}%", inv_stats['defense'] > 0),
            ("Evasion", f"+{inv_stats['evasion']:.0f}", inv_stats['evasion'] > 0),
            ("Debuff Tolerance", f"+{inv_stats['debuff_tolerance']:.0f}", inv_stats['debuff_tolerance'] > 0),
            ("Dmg Taken Decrease", f"+{inv_stats['damage_taken_decrease']*100:.1f}%", inv_stats['damage_taken_decrease'] > 0),
        ]

        has_utility = any(show for _, _, show in utility_stats)
        if has_utility:
            st.markdown("**Utility Stats:**")
            for label, value, show in utility_stats:
                if show:
                    st.markdown(f"<div class='stat-row'><span class='stat-label'>{label}:</span> <span class='stat-value'>{value}</span></div>", unsafe_allow_html=True)

        # RESONANCE
        st.markdown("---")
        st.markdown("<div class='section-header'>Resonance</div>", unsafe_allow_html=True)

        # Calculate max level from total artifact stars
        def get_stars_safe(art_data):
            if isinstance(art_data, dict):
                stars = art_data.get('stars', 0)
                return int(stars) if isinstance(stars, (int, float)) else 0
            return 0

        total_artifact_stars = sum(get_stars_safe(art) for art in data.artifacts_inventory.values())
        max_resonance_level = calculate_resonance_max_level(total_artifact_stars)

        # Get current resonance level (default to 1)
        current_level = data.artifacts_resonance.get('resonance_level', 1)

        # Editable resonance level
        new_level = st.number_input(
            "Resonance Level",
            min_value=1,
            max_value=max(max_resonance_level, 1),
            value=min(current_level, max(max_resonance_level, 1)),
            key="res_level"
        )
        if new_level != current_level:
            data.artifacts_resonance['resonance_level'] = new_level
            auto_save()

        st.caption(f"Max Level: {max_resonance_level} (from ★{total_artifact_stars} total)")

        # Calculate and display stats from resonance level
        resonance_main_stat = calculate_resonance_main_stat(new_level)
        resonance_hp = calculate_resonance_hp(new_level)

        # Store calculated values for DPS calculations
        data.artifacts_resonance['main_stat_bonus'] = resonance_main_stat
        data.artifacts_resonance['hp_bonus'] = resonance_hp

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"<div class='stat-row'><span class='stat-label'>Main Stat:</span> <span class='stat-value'>+{resonance_main_stat:,}</span></div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div class='stat-row'><span class='stat-label'>HP:</span> <span class='stat-value'>+{resonance_hp:,}</span></div>", unsafe_allow_html=True)

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

            # Ensure art_data is a dict (fix malformed data)
            if not isinstance(art_data, dict):
                art_data = {'stars': 0, 'dupes': 0, 'potentials': []}
                data.artifacts_inventory[selected_key] = art_data
                auto_save()

            stars = art_data.get('stars', 0)
            slots_unlocked = POTENTIAL_SLOT_UNLOCKS.get(stars, 0)
            defn = ARTIFACTS[selected_key]

            # Determine max slots based on artifact tier (Epic=1, Unique=2, Legendary=3)
            max_slots = MAX_POTENTIAL_SLOTS_BY_TIER.get(defn.tier, 3)

            # Cap slots_unlocked by tier's max
            if slots_unlocked > max_slots:
                slots_unlocked = max_slots

            st.caption(f"★{stars} → {slots_unlocked}/{max_slots} potential slot(s) unlocked")

            # Initialize potentials if needed OR if it's not a valid list
            if 'potentials' not in art_data or not isinstance(art_data['potentials'], list):
                art_data['potentials'] = []

            # Ensure potential slots up to tier's max with proper dict format
            while len(art_data['potentials']) < max_slots:
                art_data['potentials'].append({'stat': '', 'value': 0, 'tier': 'legendary'})

            # Fix any malformed potential entries (convert non-dict to dict)
            for idx in range(len(art_data['potentials'])):
                if not isinstance(art_data['potentials'][idx], dict):
                    art_data['potentials'][idx] = {'stat': '', 'value': 0, 'tier': 'legendary'}

            potentials_changed = False

            # Format function for tier display
            def format_tier(t):
                if t == "mystic_high":
                    return "Mystic+"
                return t.title()

            for i in range(max_slots):
                is_unlocked = i < slots_unlocked
                pot = art_data['potentials'][i]

                # Show lock icon for slots not yet unlocked
                unlock_star = 1 if i == 0 else (3 if i == 1 else 5)
                slot_label = f"Slot {i+1}" if is_unlocked else f"🔒 Slot {i+1} (★{unlock_star})"

                col1, col2, col3 = st.columns([2, 1, 1])

                with col1:
                    current_stat = pot.get('stat', '')
                    stat_idx = POTENTIAL_STATS.index(current_stat) if current_stat in POTENTIAL_STATS else 0
                    new_stat = st.selectbox(
                        slot_label,
                        options=POTENTIAL_STATS,
                        index=stat_idx,
                        key=f"pot_stat_{selected_key}_{i}",
                        format_func=lambda x: x.replace("_", " ").replace("pct", "%").title() if x != "---" else "---"
                    )
                    if new_stat != current_stat:
                        pot['stat'] = new_stat if new_stat != "---" else ""
                        potentials_changed = True

                with col2:
                    current_tier = pot.get('tier', 'legendary')
                    tier_idx = POTENTIAL_TIERS.index(current_tier) if current_tier in POTENTIAL_TIERS else 3
                    new_tier = st.selectbox(
                        "Tier",
                        options=POTENTIAL_TIERS,
                        index=tier_idx,
                        key=f"pot_tier_{selected_key}_{i}",
                        format_func=format_tier,
                        label_visibility="collapsed"
                    )
                    if new_tier != current_tier:
                        pot['tier'] = new_tier
                        potentials_changed = True

                with col3:
                    # Auto-calculate value based on CURRENT stat + tier (use new values if changed)
                    display_stat = pot.get('stat', '')
                    display_tier = pot.get('tier', 'legendary')
                    auto_value = get_potential_value(display_stat, display_tier)
                    pot['value'] = auto_value  # Always update to match
                    st.markdown(f"**{auto_value:.1f}%**" if auto_value > 0 else "-")

            if potentials_changed:
                data.artifacts_inventory[selected_key] = art_data
                auto_save()

            # POTENTIAL ANALYSIS SECTION
            st.markdown("---")
            with st.expander("📊 Potential Analysis", expanded=False):
                from artifact_optimizer import (
                    analyze_artifact_potential_scenarios,
                    ArtifactPotentialScenario,
                    ArtifactPotentialAnalysis,
                    ArtifactPotentialDistribution,
                )
                from copy import deepcopy
                import pandas as pd

                # Convert potentials to ArtifactPotentialLine format
                pot_lines = []
                for idx, pot in enumerate(art_data.get('potentials', [])):
                    if isinstance(pot, dict) and pot.get('stat'):
                        tier_map = {
                            'rare': PotentialTier.RARE,
                            'epic': PotentialTier.EPIC,
                            'unique': PotentialTier.UNIQUE,
                            'legendary': PotentialTier.LEGENDARY,
                            'mystic': PotentialTier.MYSTIC,
                            'mystic_high': PotentialTier.MYSTIC,
                        }
                        pot_lines.append(ArtifactPotentialLine(
                            stat=pot.get('stat', ''),
                            value=pot.get('value', 0),
                            tier=tier_map.get(pot.get('tier', 'legendary'), PotentialTier.LEGENDARY),
                            slot=idx + 1,
                        ))

                # Get aggregated stats for DPS calculation
                try:
                    agg_stats = aggregate_stats(data)
                    baseline_result = calculate_dps(agg_stats, 'stage')
                    baseline_dps = baseline_result.get('total', 1)
                except Exception:
                    agg_stats = {}
                    baseline_dps = 1

                # DPS function for analysis
                def analysis_dps_func(stats, mode):
                    merged = agg_stats.copy()
                    merged.update(stats)
                    return calculate_dps(merged, mode)

                # Helper to calculate single stat DPS contribution
                def calc_single_stat_dps(stat_key, value):
                    """Calculate DPS% gain from a single stat."""
                    if baseline_dps <= 0:
                        return 0.0
                    test_stats = deepcopy(agg_stats)

                    # Map artifact stat names to DPS calc names
                    from stat_names import (
                        DAMAGE_PCT, BOSS_DAMAGE, NORMAL_DAMAGE, CRIT_RATE, DEF_PEN,
                        MIN_DMG_MULT, MAX_DMG_MULT, get_main_stat_pct_key,
                    )
                    stat_mapping = {
                        'damage': DAMAGE_PCT,
                        'boss_damage': BOSS_DAMAGE,
                        'normal_damage': NORMAL_DAMAGE,
                        'crit_rate': CRIT_RATE,
                        'def_pen': DEF_PEN,
                        'min_damage_mult': MIN_DMG_MULT,
                        'max_damage_mult': MAX_DMG_MULT,
                    }

                    if stat_key == 'main_stat_pct':
                        main_type = test_stats.get('main_stat_type', 'dex')
                        pct_key = get_main_stat_pct_key(main_type)
                        test_stats[pct_key] = test_stats.get(pct_key, 0) + value
                    elif stat_key == 'def_pen':
                        mapped = stat_mapping.get(stat_key, stat_key)
                        test_stats[mapped] = test_stats.get(mapped, 0) + (value / 100)
                    else:
                        mapped = stat_mapping.get(stat_key, stat_key)
                        test_stats[mapped] = test_stats.get(mapped, 0) + value

                    new_result = analysis_dps_func(test_stats, 'stage')
                    new_dps = new_result.get('total', baseline_dps)
                    return ((new_dps / baseline_dps) - 1) * 100

                if pot_lines and baseline_dps > 0:
                    try:
                        # === CURRENT LINES BREAKDOWN ===
                        st.markdown("**Your Current Potentials:**")
                        current_lines_data = []
                        total_current_dps = 0.0

                        for idx, pot in enumerate(art_data.get('potentials', [])[:slots_unlocked]):
                            if isinstance(pot, dict) and pot.get('stat'):
                                stat_name = pot.get('stat', '')
                                tier_name = pot.get('tier', 'legendary')
                                value = pot.get('value', 0)
                                dps_gain = calc_single_stat_dps(stat_name, value)
                                total_current_dps += dps_gain

                                display_tier = "Mystic+" if tier_name == "mystic_high" else tier_name.title()
                                display_stat = stat_name.replace("_", " ").replace("pct", "%").title()

                                current_lines_data.append({
                                    "Slot": f"{idx + 1}",
                                    "Stat": display_stat,
                                    "Tier": display_tier,
                                    "Value": f"{value:.1f}%",
                                    "DPS%": f"+{dps_gain:.2f}%",
                                })

                        if current_lines_data:
                            st.dataframe(pd.DataFrame(current_lines_data), hide_index=True, use_container_width=True)
                            st.markdown(f"**Total from potentials: +{total_current_dps:.2f}% DPS**")
                        else:
                            st.info("No active potential slots configured.")

                        # === BEST POTENTIAL LINES ===
                        st.markdown("---")
                        st.markdown("**Best Potential Lines (Ranked by DPS):**")
                        st.caption("Using 'stage' mode (60% normal / 40% boss)")

                        # Calculate DPS for all possible stat+tier combos
                        best_lines = []
                        for stat_key in STAT_TO_POTENTIAL_KEY.keys():
                            for tier_name in ['legendary', 'mystic', 'mystic_high']:
                                value = get_potential_value(stat_key, tier_name)
                                if value > 0:
                                    dps = calc_single_stat_dps(stat_key, value)
                                    display_tier = "Mystic+" if tier_name == "mystic_high" else tier_name.title()
                                    display_stat = stat_key.replace("_", " ").replace("pct", "%").title()
                                    best_lines.append({
                                        "Stat": display_stat,
                                        "Tier": display_tier,
                                        "Value": f"{value:.1f}%",
                                        "DPS%": dps,
                                        "_sort": dps,
                                    })

                        best_lines.sort(key=lambda x: x['_sort'], reverse=True)

                        num_to_show = st.slider("Lines to show", min_value=5, max_value=min(25, len(best_lines)), value=10, key="best_lines_slider")
                        top_lines = best_lines[:num_to_show]
                        for line in top_lines:
                            line['DPS%'] = f"+{line['DPS%']:.2f}%"
                            del line['_sort']

                        st.dataframe(pd.DataFrame(top_lines), hide_index=True, use_container_width=True)

                        # === REROLL ANALYSIS ===
                        st.markdown("---")
                        analysis = analyze_artifact_potential_scenarios(
                            artifact_key=selected_key,
                            artifact_tier=defn.tier,
                            current_potentials=pot_lines,
                            current_stars=stars,
                            current_stats=agg_stats,
                            calculate_dps_func=analysis_dps_func,
                            baseline_dps=baseline_dps,
                        )

                        current_scenario = None
                        if analysis.slots_unlocked == 1:
                            current_scenario = analysis.scenario_1_slot
                        elif analysis.slots_unlocked == 2:
                            current_scenario = analysis.scenario_2_slots
                        elif analysis.slots_unlocked == 3:
                            current_scenario = analysis.scenario_3_slots

                        if current_scenario:
                            st.markdown("**Reroll Analysis:**")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Current Percentile", f"{current_scenario.current_percentile:.1f}%")
                                st.metric("Rolls to Improve", f"{current_scenario.expected_rolls_to_improve:.1f}")
                            with col2:
                                st.metric("Cost to Improve", f"{current_scenario.expected_cost_to_improve:,.0f} 💎")
                                expected_gain = current_scenario.expected_dps_when_improving - current_scenario.current_dps_gain
                                st.metric("Expected Gain", f"+{expected_gain:.2f}%")

                            # Recommendation
                            st.info(f"💡 {analysis.recommended_action}")

                    except Exception as e:
                        st.warning(f"Could not analyze potentials: {e}")
                else:
                    st.info("Configure potentials above to see analysis.")

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
                    # Use tier-specific duplicate costs
                    artifact_tier = ARTIFACTS[calc_artifact_key].tier
                    tier_dupes = TOTAL_DUPLICATES_BY_TIER.get(artifact_tier, TOTAL_DUPLICATES_BY_TIER[ArtifactTier.LEGENDARY])
                    dupes_needed = tier_dupes.get(target_stars, 0) - tier_dupes.get(current_stars, 0)

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

# ============================================================================
# TAB 3: EFFICIENCY ANALYSIS
# ============================================================================
with tab_efficiency:
    st.markdown("<div class='section-header'>Artifact Upgrade Efficiency</div>", unsafe_allow_html=True)
    st.caption("Recommendations sorted by DPS% gain per 1,000 diamonds")

    # Build owned artifacts dict from inventory
    owned_artifacts = {}
    for art_key, art_data in data.artifacts_inventory.items():
        if isinstance(art_data, dict):
            owned_artifacts[art_key] = {
                'stars': art_data.get('stars', 0),
                'dupes': art_data.get('dupes', 0),
                'potentials': art_data.get('potentials', []),
            }

    # Get equipped artifact keys
    equipped_artifact_keys = []
    for i in range(3):
        slot_data = data.artifacts_equipped.get(f'slot{i}', {})
        if isinstance(slot_data, dict):
            name = slot_data.get('name', '')
            if name and name != '(Empty)':
                key = ARTIFACT_KEY_BY_NAME.get(name)
                if key:
                    equipped_artifact_keys.append(key)

    # Calculate max resonance from total stars
    total_stars = sum(a.get('stars', 0) for a in owned_artifacts.values())
    current_resonance = data.artifacts_resonance.get('resonance_level', data.artifacts_resonance.get('total_stars', 1))
    max_resonance = calculate_resonance_max_level(total_stars)

    # Get aggregated stats from user data for DPS calculations
    try:
        aggregated_stats = aggregate_stats(data)
    except Exception:
        aggregated_stats = {}

    # For artifact ranking, we need stats WITHOUT artifact active effects
    # This allows us to properly measure each artifact's DPS contribution
    try:
        stats_without_artifact_actives = aggregate_stats(data, skip_artifact_actives=True)
    except Exception:
        stats_without_artifact_actives = {}

    # DPS function wrapper that uses the real calculator
    def real_dps_func(stats, mode):
        """Calculate DPS using the actual damage formula."""
        # Merge test stats with aggregated baseline
        merged = aggregated_stats.copy()
        merged.update(stats)
        return calculate_dps(merged, mode)

    # DPS function for artifact ranking (uses stats WITHOUT artifact actives)
    # This allows accurate measurement of each artifact's contribution
    def ranking_dps_func(stats, mode):
        """Calculate DPS for artifact ranking (no artifact actives in baseline)."""
        merged = stats_without_artifact_actives.copy()
        merged.update(stats)
        return calculate_dps(merged, mode)

    col_left, col_right = st.columns([1, 1])

    with col_left:
        # CHEST EXPECTED VALUE
        st.markdown("### 📦 Artifact Chest Expected Value")

        if owned_artifacts:
            chest_ev = calculate_chest_expected_value(
                owned_artifacts=owned_artifacts,
                equipped_artifact_keys=equipped_artifact_keys,
                current_stats=aggregated_stats,
                current_resonance_level=current_resonance,
                calculate_dps_func=real_dps_func,
                scenario=data.combat_mode,
                top_n=5,
            )

            st.metric("Expected DPS% per chest", f"{chest_ev.expected_dps_per_chest:.4f}%")
            st.metric("Efficiency (DPS%/1000💎)", f"{chest_ev.efficiency:.6f}")
            st.caption(f"Cost per chest: {CHEST_COST_BLUE:,} diamonds")

            # Show top contributors
            st.markdown("**Top Value Contributors:**")
            for contrib in chest_ev.breakdown[:8]:
                if contrib['contribution'] > 0:
                    tier_color = {
                        'legendary': TIER_COLORS[ArtifactTier.LEGENDARY],
                        'unique': TIER_COLORS[ArtifactTier.UNIQUE],
                        'epic': TIER_COLORS[ArtifactTier.EPIC],
                    }.get(contrib['tier'], '#888')

                    st.markdown(f"""
                    <div class='stat-row'>
                        <span style='color:{tier_color};'>{contrib['artifact_name']}</span>
                        <span class='stat-value'>{contrib['drop_rate_pct']:.2f}% × {contrib['value']:.3f}%</span>
                    </div>
                    """, unsafe_allow_html=True)
                    st.caption(f"  └ {contrib['reason']}")

        else:
            st.info("Configure artifacts in the Configuration tab to see expected value.")

        # RESONANCE LEVELING
        st.markdown("---")
        st.markdown("### ✨ Resonance Leveling")

        if max_resonance > 0:
            res_rec = calculate_resonance_leveling_efficiency(
                current_level=current_resonance,
                max_level=max_resonance,
                current_stats=aggregated_stats,
                calculate_dps_func=real_dps_func,
                levels_to_check=10,
            )

            if res_rec:
                st.metric("Stat Gain (10 levels)", f"+{res_rec.main_stat_gain} Main, +{res_rec.hp_gain} HP")
                st.metric("Enhancer Cost", f"{res_rec.enhancer_cost:,}")
                st.metric("Diamond Equivalent", f"{res_rec.diamond_cost:,.0f}")
                st.caption(f"Current: Lv.{current_resonance} / Max: Lv.{max_resonance}")
            else:
                st.info(f"Resonance at max level ({max_resonance})")
        else:
            st.info("Awaken artifacts to increase resonance cap.")

    with col_right:
        # AWAKENING PRIORITIES
        st.markdown("### 🌟 Awakening Priorities")

        awakening_recs = []
        for art_key, art_data in owned_artifacts.items():
            current_stars = art_data.get('stars', 0)
            if current_stars >= 5:
                continue  # Already maxed

            is_equipped = art_key in equipped_artifact_keys

            rec = calculate_awakening_efficiency(
                artifact_key=art_key,
                current_stars=current_stars,
                is_equipped=is_equipped,
                current_stats=aggregated_stats,
                current_resonance_level=current_resonance,
                calculate_dps_func=real_dps_func,
            )

            if rec:
                awakening_recs.append(rec)

        # Sort by efficiency
        awakening_recs.sort(key=lambda x: x.efficiency, reverse=True)

        if awakening_recs:
            for rec in awakening_recs[:10]:
                tier_color = TIER_COLORS.get(rec.tier, '#888')
                equipped_badge = "⚔️" if rec.is_equipped else ""
                slot_badge = "🎰" if rec.unlocks_potential_slot else ""

                st.markdown(f"""
                <div class='result-box'>
                    <span style='color:{tier_color}; font-weight:bold;'>{rec.artifact_name}</span> {equipped_badge}{slot_badge}<br>
                    <span class='stat-label'>★{rec.current_stars} → ★{rec.target_stars}</span><br>
                    <span class='stat-label'>Expected Chests:</span> <span class='stat-value'>{rec.expected_chests:,.0f}</span><br>
                    <span class='stat-label'>Diamond Cost:</span> <span class='stat-value'>{rec.diamond_cost:,.0f}</span><br>
                    <span class='stat-label'>Efficiency:</span> <span class='stat-value'>{rec.efficiency:.6f}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("All artifacts are either maxed or not configured.")

        # POTENTIAL REROLL PRIORITIES
        st.markdown("---")
        st.markdown("### 🎲 Potential Reroll (Equipped)")

        if equipped_artifact_keys:
            reroll_recs = []
            for art_key in equipped_artifact_keys:
                if art_key not in data.artifacts_inventory:
                    continue

                art_data = data.artifacts_inventory[art_key]
                current_stars = art_data.get('stars', 0)
                potentials = art_data.get('potentials', [])

                # Convert to expected format
                pot_lines = []
                for i, pot in enumerate(potentials):
                    if isinstance(pot, dict):
                        from artifacts import ArtifactPotentialLine, PotentialTier
                        tier_map = {
                            'rare': PotentialTier.RARE,
                            'epic': PotentialTier.EPIC,
                            'unique': PotentialTier.UNIQUE,
                            'legendary': PotentialTier.LEGENDARY,
                            'mystic': PotentialTier.MYSTIC,
                            'mystic_high': PotentialTier.MYSTIC,
                        }
                        pot_lines.append(ArtifactPotentialLine(
                            stat=pot.get('stat', ''),
                            value=pot.get('value', 0),
                            tier=tier_map.get(pot.get('tier', 'legendary'), PotentialTier.LEGENDARY),
                            slot=i + 1,
                        ))

                rec = calculate_artifact_reroll_efficiency(
                    artifact_key=art_key,
                    current_potentials=pot_lines,
                    current_stars=current_stars,
                    is_equipped=True,
                    current_stats=aggregated_stats,
                    calculate_dps_func=real_dps_func,
                )

                if rec and rec.efficiency > 0:
                    reroll_recs.append(rec)

            # Sort by efficiency
            reroll_recs.sort(key=lambda x: x.efficiency, reverse=True)

            if reroll_recs:
                for rec in reroll_recs:
                    defn = ARTIFACTS.get(rec.artifact_key)
                    tier_color = TIER_COLORS.get(defn.tier if defn else ArtifactTier.LEGENDARY, '#888')

                    st.markdown(f"""
                    <div class='result-box'>
                        <span style='color:{tier_color}; font-weight:bold;'>{rec.artifact_name}</span><br>
                        <span class='stat-label'>Slots:</span> <span class='stat-value'>{rec.num_slots}</span><br>
                        <span class='stat-label'>Current DPS:</span> <span class='stat-value'>+{rec.current_dps_gain:.2f}%</span><br>
                        <span class='stat-label'>Percentile:</span> <span class='stat-value'>{rec.current_percentile:.0f}th</span><br>
                        <span class='stat-label'>Expected Gain:</span> <span class='stat-value'>+{rec.expected_dps_gain:.2f}%</span><br>
                        <span class='stat-label'>Efficiency:</span> <span class='stat-value'>{rec.efficiency:.6f}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("All equipped artifact potentials are at or above expected value!")
        else:
            st.info("Equip artifacts to see potential reroll recommendations.")

    # DPS RANKING FOR EQUIPMENT SELECTION
    st.markdown("---")
    st.markdown("### 🏆 Artifact DPS Ranking (Which to Equip?)")

    # Use combat mode from Character Settings
    ranking_scenario = data.combat_mode
    scenario_display_names = {
        "stage": "Stage (Mixed)",
        "chapter_hunt": "Chapter Hunt",
        "boss": "Boss Stage",
        "world_boss": "World Boss",
    }
    ranking_scenario_label = scenario_display_names.get(ranking_scenario, ranking_scenario.replace("_", " ").title())
    st.caption(f"Using combat mode: **{ranking_scenario_label}** (change in Character Settings)")

    if owned_artifacts:
        dps_rankings = get_artifact_ranking_for_equip(
            owned_artifacts,
            scenario=ranking_scenario,
            current_stats=stats_without_artifact_actives,
            calculate_dps_func=ranking_dps_func,
        )

        if dps_rankings:
            # Show top 3 recommendation
            top3 = dps_rankings[:3]
            top3_names = [s.artifact_name for s in top3]
            current_equipped_names = [ARTIFACTS[k].name for k in equipped_artifact_keys if k in ARTIFACTS]

            # Check if current loadout matches recommendation
            if set(top3_names) == set(current_equipped_names):
                st.success(f"✅ You have the optimal artifacts equipped for {ranking_scenario_label}!")
            else:
                missing = set(top3_names) - set(current_equipped_names)
                if missing:
                    st.warning(f"💡 Consider equipping: {', '.join(missing)}")

            # Show ranking table
            st.markdown("**All Artifacts Ranked by DPS Score:**")

            for i, score in enumerate(dps_rankings, 1):
                tier_color = TIER_COLORS.get(score.tier, '#888')
                is_equipped = score.artifact_key in equipped_artifact_keys
                is_top3 = i <= 3

                # Badge indicators
                badges = []
                if is_equipped:
                    badges.append("⚔️")
                if is_top3:
                    badges.append(f"#{i}")
                badge_str = " ".join(badges)

                # Background color for top 3
                bg_color = "#2a3a2a" if is_top3 else "#2a2a4e"

                st.markdown(f"""
                <div style='background: {bg_color}; border-radius: 4px; padding: 8px; margin: 4px 0;'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <span style='color:{tier_color}; font-weight:bold;'>{score.artifact_name}</span>
                        <span style='color: #ffd700;'>{badge_str}</span>
                    </div>
                    <div style='font-size: 12px; color: #aaa; margin-top: 4px;'>
                        ★{score.stars} | {score.num_potential_slots} pot slots
                    </div>
                    <div style='display: flex; justify-content: space-between; margin-top: 4px; font-family: monospace;'>
                        <span style='color: #7fff7f;'>Equip Value: +{score.equip_value:.1f}%</span>
                        <span style='color: #888;'>(Active +{score.active_score:.1f}% + Pot +{score.potential_score:.1f}%)</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # Summary
            st.markdown("---")
            st.caption("""
            **Score Breakdown:**
            - **Equip Value** = Active + Potential (what you GAIN by equipping - use this to pick which 3 to equip)
            - Inventory effects are excluded from ranking because they're always active whether equipped or not
            - Higher stars and better potentials increase score
            """)
    else:
        st.info("Configure artifacts in the Configuration tab to see DPS rankings.")

    # LEGEND
    st.markdown("---")
    st.markdown("### 📚 Legend")
    st.markdown("""
    - **⚔️** = Currently equipped artifact
    - **#1-3** = Recommended for equipping (highest DPS score)
    - **🎰** = Unlocks new potential slot at this star level
    - **Efficiency** = DPS% gain per 1,000 diamonds spent
    - **DPS Score** = Approximate DPS% contribution from artifact
    """)
