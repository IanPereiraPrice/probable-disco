"""
Character Stats Page
Compare calculated stats vs actual in-game values to identify gaps.
Click on any stat to see a breakdown of all contributing sources.

Adjustments are applied to DPS calculations throughout the app.
"""
import streamlit as st
from typing import Dict, Any, List, Tuple
from utils.data_manager import save_user_data, EQUIPMENT_SLOTS
from utils.dps_calculator import (
    aggregate_stats as shared_aggregate_stats,
    calculate_dps as shared_calculate_dps,
    calculate_effective_defense_pen_with_sources,
    calculate_effective_attack_speed_with_sources,
    BASE_MIN_DMG,
    BASE_MAX_DMG,
)
from equipment import get_amplify_multiplier
from job_classes import JobClass, get_main_stat_name, get_secondary_stat_name
from constants import is_percentage_stat

st.set_page_config(page_title="Character Stats", page_icon="📊", layout="wide")

# Custom CSS for the stat comparison table
st.markdown("""
<style>
    .stat-table {
        width: 100%;
        border-collapse: collapse;
        font-family: monospace;
        font-size: 14px;
    }
    .stat-table th {
        background: #2a2a4e;
        color: #ffd700;
        padding: 10px;
        text-align: center;
        border-bottom: 2px solid #444;
    }
    .stat-table td {
        padding: 8px 12px;
        border-bottom: 1px solid #333;
        text-align: center;
    }
    .stat-table tr:hover {
        background: #1a1a2e;
    }
    .stat-name {
        text-align: left !important;
        color: #fff;
        font-weight: bold;
    }
    .stat-calc { color: #66ff66; }
    .stat-adj { color: #ffaa00; }
    .stat-final { color: #66ccff; }
    .stat-actual { color: #ffffff; }
    .gap-positive { color: #66ff66; }
    .gap-negative { color: #ff6666; }
    .gap-zero { color: #888; }
    .clickable-stat {
        cursor: pointer;
        text-decoration: underline;
        color: #66ccff;
    }
    .clickable-stat:hover {
        color: #99ddff;
    }
    .section-header {
        font-size: 18px;
        font-weight: bold;
        color: #ffd700;
        margin: 20px 0 10px 0;
        padding: 10px;
        background: #2a2a4e;
        border-radius: 4px;
    }
    .source-row {
        display: flex;
        justify-content: space-between;
        padding: 4px 8px;
        border-bottom: 1px solid #333;
    }
    .source-name { color: #aaa; }
    .source-value { color: #66ff66; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

# Baselines
BASE_CRIT_DMG = 30.0
BASE_CRIT_RATE = 5.0


def auto_save():
    save_user_data(st.session_state.username, data)


def get_stat_sources(stat_key: str, raw_stats: Dict, job_class: JobClass = None) -> List[Tuple[str, float]]:
    """
    Get breakdown of sources for a specific stat.
    Returns list of (source_name, value) tuples.

    Uses standardized stat names (attack_flat, dex_pct, damage_pct, etc.)
    """
    sources = []

    # Get main stat keys for this job class
    if job_class is None:
        job_class = JobClass.BOWMASTER
    main_stat = get_main_stat_name(job_class)  # e.g., 'dex'
    main_flat_key = f'{main_stat}_flat'
    main_pct_key = f'{main_stat}_pct'

    # Equipment base stats (with starforce)
    if stat_key in ['attack_flat', main_flat_key]:
        for slot in EQUIPMENT_SLOTS:
            item = data.equipment_items.get(slot, {})
            stars = int(item.get('stars', 0))
            main_mult = get_amplify_multiplier(stars, is_sub=False)
            sub_mult = get_amplify_multiplier(stars, is_sub=True)

            if stat_key == 'attack_flat':
                base_val = item.get('base_attack', 0) * main_mult
                sub_val = item.get('sub_attack_flat', 0) * sub_mult
                total = base_val + sub_val
                if total > 0:
                    sources.append((f"{slot.title()} (Base)", base_val))
                    if sub_val > 0:
                        sources.append((f"{slot.title()} (Sub)", sub_val))

    # Equipment potentials
    pot_stats = {}
    for slot in EQUIPMENT_SLOTS:
        pots = data.equipment_potentials.get(slot, {})
        for prefix in ['', 'bonus_']:
            for i in range(1, 4):
                stat = pots.get(f'{prefix}line{i}_stat', '')
                value = float(pots.get(f'{prefix}line{i}_value', 0) or 0)
                if stat and value > 0:
                    key = f"{slot}_{prefix}pot"
                    if key not in pot_stats:
                        pot_stats[key] = {}
                    pot_stats[key][stat] = pot_stats[key].get(stat, 0) + value

    # Map stat_key to potential stat names (using standardized names)
    pot_stat_mapping = {
        main_pct_key: [main_pct_key, 'main_stat_pct'],
        main_flat_key: [main_flat_key, 'main_stat_flat'],
        'damage_pct': ['damage_pct', 'damage'],
        'boss_damage': ['boss_damage'],
        'normal_damage': ['normal_damage'],
        'crit_rate': ['crit_rate'],
        'crit_damage': ['crit_damage'],
        'def_pen': ['def_pen'],
        'final_damage': ['final_damage'],
        'attack_speed': ['attack_speed'],
        'min_dmg_mult': ['min_dmg_mult'],
        'max_dmg_mult': ['max_dmg_mult'],
    }

    pot_names = pot_stat_mapping.get(stat_key, [])
    for slot_key, stats in pot_stats.items():
        slot_total = sum(stats.get(pn, 0) for pn in pot_names)
        if slot_total > 0:
            is_bonus = 'bonus_' in slot_key
            # Extract just the slot name (e.g., "hat" from "hat_bonus_pot" or "hat_pot")
            slot_name = slot_key.replace('_bonus_pot', '').replace('_pot', '')
            label = f"{slot_name.title()} {'Bonus ' if is_bonus else ''}Potential"
            sources.append((label, slot_total))

    # Hero Power Lines (uses standardized stat names)
    # Note: Hero Power's 'main_stat_pct' is actually flat main stat (legacy naming issue)
    hp_stat_mapping = {
        'damage_pct': 'damage_pct',
        'boss_damage': 'boss_damage',
        'normal_damage': 'normal_damage',
        'crit_damage': 'crit_damage',
        'def_pen': 'def_pen',
        'min_dmg_mult': 'min_dmg_mult',
        'max_dmg_mult': 'max_dmg_mult',
        main_flat_key: 'main_stat_pct',  # Hero Power's main_stat_pct provides flat stat
    }
    hp_name = hp_stat_mapping.get(stat_key)
    if hp_name:
        hp_total = 0
        for line_key, line in data.hero_power_lines.items():
            if line.get('stat') == hp_name:
                hp_total += float(line.get('value', 0) or 0)
        if hp_total > 0:
            sources.append(("Hero Power Lines", hp_total))

    # Hero Power Passives
    from hero_power import HeroPowerPassiveStatType, HERO_POWER_PASSIVE_STATS
    hpp_mapping = {
        main_flat_key: 'main_stat',
        'damage_pct': 'damage_percent',
        'attack_flat': 'attack',
    }
    hpp_key = hpp_mapping.get(stat_key)
    if hpp_key:
        passives = data.hero_power_passives or {}
        for stat_type in HeroPowerPassiveStatType:
            if stat_type.value == hpp_key:
                level = passives.get(hpp_key, 0)
                if level > 0:
                    stat_info = HERO_POWER_PASSIVE_STATS.get(stat_type, {})
                    per_level = stat_info.get("per_level", 1.0)
                    value = level * per_level
                    sources.append(("Hero Power Passives", value))

    # Maple Rank
    from maple_rank import MapleRankStatType, MAPLE_RANK_STATS, get_cumulative_main_stat, MAIN_STAT_SPECIAL
    mr = data.maple_rank or {}
    mr_mapping = {
        main_flat_key: 'main_stat_flat',
        'damage_pct': 'damage_percent',
        'boss_damage': 'boss_damage',
        'normal_damage': 'normal_damage',
        'crit_damage': 'crit_damage',
        'crit_rate': 'crit_rate',
        'min_dmg_mult': 'min_dmg_mult',
        'max_dmg_mult': 'max_dmg_mult',
        'attack_speed': 'attack_speed',
    }

    if stat_key == main_flat_key:
        stage = mr.get('current_stage', 1)
        ms_level = mr.get('main_stat_level', 0)
        special = mr.get('special_main_stat', 0)
        regular_ms = get_cumulative_main_stat(stage, ms_level)
        special_ms = MAIN_STAT_SPECIAL["base_value"] + special * MAIN_STAT_SPECIAL["per_point"]
        total_ms = regular_ms + special_ms
        if total_ms > 0:
            sources.append(("Maple Rank", total_ms))
    else:
        mr_key = mr_mapping.get(stat_key)
        if mr_key:
            stat_levels = mr.get('stat_levels', {})
            for stat_type in MapleRankStatType:
                if stat_type.value == mr_key and stat_type in MAPLE_RANK_STATS:
                    level = stat_levels.get(mr_key, 0)
                    if level > 0:
                        per_level = MAPLE_RANK_STATS[stat_type]["per_level"]
                        value = level * per_level
                        sources.append(("Maple Rank", value))

    # Companions (inventory stats use standardized names)
    from companions import COMPANIONS
    companion_levels = data.companion_levels or {}
    comp_mapping = {
        'boss_damage': 'boss_damage',
        'normal_damage': 'normal_damage',
        'crit_rate': 'crit_rate',
        'min_dmg_mult': 'min_dmg_mult',
        'max_dmg_mult': 'max_dmg_mult',
        'attack_speed': 'attack_speed',
        'attack_flat': 'attack_flat',
        'damage_pct': 'damage_pct',
        main_flat_key: 'main_stat_flat',
    }
    comp_stat = comp_mapping.get(stat_key)
    if comp_stat:
        on_equip_total = 0
        inv_total = 0

        # On-equip from equipped companions
        for comp_key in (data.equipped_companions or []):
            if not comp_key or comp_key not in COMPANIONS:
                continue
            level = companion_levels.get(comp_key, 0)
            if level <= 0:
                continue
            companion = COMPANIONS[comp_key]
            if companion.on_equip_type.value == comp_stat:
                on_equip_total += companion.get_on_equip_value(level)

        # Inventory stats
        for comp_key, level in companion_levels.items():
            if level <= 0 or comp_key not in COMPANIONS:
                continue
            companion = COMPANIONS[comp_key]
            inv_stats = companion.get_inventory_stats(level)
            if comp_stat in inv_stats:
                inv_total += inv_stats[comp_stat]

        if on_equip_total > 0:
            sources.append(("Companions (Equipped)", on_equip_total))
        if inv_total > 0:
            sources.append(("Companions (Inventory)", inv_total))

    # Artifacts - read from artifacts_inventory using new potentials format
    art_mapping = {
        'damage_pct': 'damage',
        'boss_damage': 'boss_damage',
        'crit_damage': 'crit_damage',
        'def_pen': 'def_pen',
        main_flat_key: 'main_stat_flat',
        main_pct_key: 'main_stat',
        'attack_flat': 'attack_flat',
    }
    art_stat = art_mapping.get(stat_key)
    if art_stat:
        art_total = 0
        # Read from artifacts_inventory which uses new format
        artifacts_inventory = getattr(data, 'artifacts_inventory', {}) or {}
        for art_key, art_data in artifacts_inventory.items():
            if not isinstance(art_data, dict):
                continue
            potentials = art_data.get('potentials', [])
            if isinstance(potentials, list):
                for pot in potentials:
                    if isinstance(pot, dict):
                        pot_stat = pot.get('stat', '')
                        pot_value = float(pot.get('value', 0) or 0)
                        if pot_stat == art_stat and pot_value > 0:
                            # Potentials are stored as percentages (e.g., 10 for 10%)
                            # Add directly - no conversion needed
                            art_total += pot_value
        if art_total > 0:
            sources.append(("Artifacts", art_total))

    # Guild Skills
    guild_skills = getattr(data, 'guild_skills', {}) or {}
    guild_mapping = {
        'def_pen': 'def_pen',
        'final_damage': 'final_damage',
        'damage_pct': 'damage',
        'boss_damage': 'boss_damage',
        'crit_damage': 'crit_damage',
        main_pct_key: 'main_stat',
        'attack_flat': 'attack',
    }
    guild_stat = guild_mapping.get(stat_key)
    if guild_stat:
        guild_val = guild_skills.get(guild_stat, 0)
        if guild_val > 0:
            sources.append(("Guild Skills", guild_val))

    # Equipment Sets (medal, costume)
    if stat_key == main_flat_key:
        medal_val = data.equipment_sets.get('medal', 0)
        costume_val = data.equipment_sets.get('costume', 0)
        if medal_val > 0:
            sources.append(("Medal Set", medal_val))
        if costume_val > 0:
            sources.append(("Costume Set", costume_val))

    # Weapon Mastery stats (from weapon awakening levels)
    from weapon_mastery import calculate_mastery_stages_from_weapons, calculate_mastery_stats
    weapons_data = getattr(data, 'weapons_data', {}) or {}
    if weapons_data:
        mastery_stages = calculate_mastery_stages_from_weapons(weapons_data)
        mastery_stats = calculate_mastery_stats(mastery_stages)

        mastery_mapping = {
            'attack_flat': 'attack',
            main_flat_key: 'main_stat',
            'accuracy': 'accuracy',
            'min_dmg_mult': 'min_dmg_mult',
            'max_dmg_mult': 'max_dmg_mult',
        }
        mastery_key = mastery_mapping.get(stat_key)
        if mastery_key and mastery_stats.get(mastery_key, 0) > 0:
            sources.append(("Weapon Mastery", mastery_stats[mastery_key]))

    # Weapons (attack %)
    if stat_key == 'attack_pct':
        from weapons import calculate_weapon_atk_str, get_inventory_ratio
        weapons_data = getattr(data, 'weapons_data', {}) or {}
        equipped_weapon_key = getattr(data, 'equipped_weapon_key', '') or ''

        total_inv_atk = 0.0
        equipped_atk = 0.0

        for key, weapon_data in weapons_data.items():
            level = weapon_data.get('level', 0)
            if level <= 0:
                continue

            parts = key.rsplit('_', 1)
            if len(parts) != 2:
                continue

            rarity, tier = parts[0], int(parts[1])
            calc_stats = calculate_weapon_atk_str(rarity, tier, level)

            # Inventory ATK always applies
            total_inv_atk += calc_stats['inventory_atk']

            # Equipped weapon also gets on_equip ATK
            if key == equipped_weapon_key:
                equipped_atk = calc_stats['on_equip_atk']

        if equipped_atk > 0:
            sources.append(("Weapon (Equipped)", equipped_atk))
        if total_inv_atk > 0:
            sources.append(("Weapon (Inventory)", total_inv_atk))

    return sources


def show_stat_breakdown_dialog(stat_name: str, stat_key: str, raw_stats: Dict, calculated_value: float, job_class: JobClass = None):
    """Show a dialog with stat breakdown."""
    sources = get_stat_sources(stat_key, raw_stats, job_class)
    is_pct = is_percentage_stat(stat_key)

    with st.container():
        st.markdown(f"### {stat_name} (Calculated)")
        st.markdown(f"**Total: {calculated_value:,.1f}{'%' if is_pct else ''}**")

        if sources:
            st.markdown("---")
            for source_name, value in sources:
                if is_pct:
                    st.write(f"**{source_name}:** {value:.1f}%")
                else:
                    st.write(f"**{source_name}:** {value:,.0f}")
        else:
            st.write("*No sources tracked for this stat*")


# ============================================================================
# STAT DEFINITIONS (Using standardized stat names)
# ============================================================================

def get_stat_definitions(job_class: JobClass = None):
    """Get stat definitions with dynamic main stat based on job class."""
    if job_class is None:
        job_class = JobClass.BOWMASTER
    main_stat = get_main_stat_name(job_class).upper()  # e.g., 'DEX', 'STR'
    main_stat_lower = main_stat.lower()

    # Define all stats to show in the comparison table
    # (key, display_name, is_percentage, include_baseline, baseline_value)
    return [
        # Main stats (dynamic based on job)
        ("total_main_stat", f"{main_stat} (Total)", False, False, 0),
        (f"{main_stat_lower}_flat", f"{main_stat} (Flat)", False, False, 0),
        (f"{main_stat_lower}_pct", f"{main_stat} %", True, False, 0),
        # Attack
        ("total_attack", "Attack (Total)", False, False, 0),
        ("attack_flat", "Attack (Flat)", False, False, 0),
        ("attack_pct", "Attack %", True, False, 0),
        # Damage stats
        ("damage_pct", "Damage %", True, False, 0),
        ("boss_damage", "Boss Damage %", True, False, 0),
        ("normal_damage", "Normal Dmg %", True, False, 0),
        # Crit stats
        ("crit_rate", "Crit Rate %", True, True, BASE_CRIT_RATE),
        ("crit_damage", "Crit Damage %", True, True, BASE_CRIT_DMG),
        # Defense/Final
        ("def_pen", "Defense Pen %", True, False, 0),
        ("final_damage", "Final Damage %", True, False, 0),
        # Other
        ("skill_damage", "Skill Damage %", True, False, 0),
        ("min_dmg_mult", "Min Dmg Mult %", True, True, BASE_MIN_DMG),
        ("max_dmg_mult", "Max Dmg Mult %", True, True, BASE_MAX_DMG),
        ("attack_speed", "Attack Speed %", True, False, 0),
        ("accuracy", "Accuracy", False, False, 0),
    ]


def get_calculated_stats(job_class: JobClass = None) -> Tuple[Dict[str, float], Dict, JobClass]:
    """Get all calculated stats from the shared aggregate function.

    Uses apply_adjustments=False to get raw calculated values
    (before manual adjustments are applied).

    Returns (stats_dict, raw_stats, job_class)
    """
    raw_stats = shared_aggregate_stats(data, apply_adjustments=False)

    # Determine job class for main stat keys
    if job_class is None:
        job_class_str = getattr(data, 'job_class', 'bowmaster')
        try:
            job_class = JobClass(job_class_str.lower())
        except ValueError:
            job_class = JobClass.BOWMASTER

    main_stat = get_main_stat_name(job_class)  # e.g., 'dex'
    main_flat_key = f'{main_stat}_flat'
    main_pct_key = f'{main_stat}_pct'

    stats = {}

    # Main stats (using standardized names)
    stats[main_flat_key] = raw_stats.get(main_flat_key, 0)
    stats[main_pct_key] = raw_stats.get(main_pct_key, 0)
    stats['attack_flat'] = raw_stats.get('attack_flat', 0)
    stats['attack_pct'] = raw_stats.get('attack_pct', 0)
    stats['damage_pct'] = raw_stats.get('damage_pct', 0)
    stats['boss_damage'] = raw_stats.get('boss_damage', 0)
    stats['normal_damage'] = raw_stats.get('normal_damage', 0)
    stats['crit_rate'] = raw_stats.get('crit_rate', 0) + BASE_CRIT_RATE
    stats['crit_damage'] = raw_stats.get('crit_damage', 0) + BASE_CRIT_DMG
    stats['skill_damage'] = raw_stats.get('skill_damage', 0)
    stats['min_dmg_mult'] = raw_stats.get('min_dmg_mult', 0) + BASE_MIN_DMG
    stats['max_dmg_mult'] = raw_stats.get('max_dmg_mult', 0) + BASE_MAX_DMG
    stats['accuracy'] = raw_stats.get('accuracy', 0)

    # Calculate total main stat
    stats['total_main_stat'] = stats[main_flat_key] * (1 + stats[main_pct_key] / 100)

    # Calculate total attack (base * (1 + atk%/100))
    stats['total_attack'] = stats['attack_flat'] * (1 + stats['attack_pct'] / 100)

    # Defense pen from sources
    def_pen_sources = raw_stats.get('def_pen_sources', [])
    if def_pen_sources:
        total_def_pen, _ = calculate_effective_defense_pen_with_sources(def_pen_sources)
        stats['def_pen'] = total_def_pen * 100
    else:
        stats['def_pen'] = 0

    # Attack speed from sources
    atk_spd_sources = raw_stats.get('attack_speed_sources', [])
    if atk_spd_sources:
        total_atk_spd, _ = calculate_effective_attack_speed_with_sources(atk_spd_sources)
        stats['attack_speed'] = total_atk_spd
    else:
        stats['attack_speed'] = 0

    # Final damage from sources
    fd_sources = raw_stats.get('final_damage_sources', [])
    if fd_sources:
        fd_mult = 1.0
        for fd in fd_sources:
            fd_mult *= (1 + fd)
        stats['final_damage'] = (fd_mult - 1) * 100
    else:
        stats['final_damage'] = 0

    return stats, raw_stats, job_class


# ============================================================================
# PAGE LAYOUT
# ============================================================================

st.title("📊 Character Stats")

# Initialize manual adjustments if needed
if not hasattr(data, 'manual_adjustments') or data.manual_adjustments is None:
    data.manual_adjustments = {}

# Initialize actual stats in session state
if 'actual_stats' not in st.session_state:
    st.session_state.actual_stats = {}

# Quick info bar
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Level", data.character_level)
with col2:
    st.metric("All Skills", f"+{data.all_skills}")
with col3:
    st.metric("Combat Mode", data.combat_mode.replace("_", " ").title())
with col4:
    st.metric("Chapter", data.chapter.replace("Chapter ", "Ch. "))

# Medal/Costume inputs
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    medal_val = st.number_input(
        "Medal Main Stat",
        min_value=0, max_value=1500,
        value=int(data.equipment_sets.get('medal', 0)),
        help="Total main stat from medal set"
    )
    if medal_val != data.equipment_sets.get('medal', 0):
        data.equipment_sets['medal'] = medal_val
        auto_save()
with col2:
    costume_val = st.number_input(
        "Costume Main Stat",
        min_value=0, max_value=1500,
        value=int(data.equipment_sets.get('costume', 0)),
        help="Total main stat from costume set"
    )
    if costume_val != data.equipment_sets.get('costume', 0):
        data.equipment_sets['costume'] = costume_val
        auto_save()

st.markdown("---")

# Get calculated stats (with job class)
calculated_stats, raw_stats, current_job_class = get_calculated_stats()

# Get stat definitions for this job class
STAT_DEFINITIONS = get_stat_definitions(current_job_class)

# ============================================================================
# STAT COMPARISON TABLE
# ============================================================================

st.markdown("<div class='section-header'>Stat Comparison (Calculated vs Actual)</div>", unsafe_allow_html=True)
st.caption("Enter your actual in-game values to identify gaps in our model")

# Track which stat to show breakdown for
if 'breakdown_stat' not in st.session_state:
    st.session_state.breakdown_stat = None

# Header row
header_cols = st.columns([2, 1.5, 1, 1.5, 1.5, 1])
with header_cols[0]:
    st.markdown("**Stat**")
with header_cols[1]:
    st.markdown("**Calculated**")
with header_cols[2]:
    st.markdown("**Adjustment**")
with header_cols[3]:
    st.markdown("**Final**")
with header_cols[4]:
    st.markdown("**Actual**")
with header_cols[5]:
    st.markdown("**Gap**")

st.markdown("---")

# Stat rows
for stat_key, display_name, is_pct, has_baseline, baseline in STAT_DEFINITIONS:
    calc_val = calculated_stats.get(stat_key, 0)
    adj_val = data.manual_adjustments.get(stat_key, 0)
    final_val = calc_val + adj_val

    # Get actual from session state or default to final
    actual_val = st.session_state.actual_stats.get(stat_key, final_val)

    gap = actual_val - final_val

    cols = st.columns([2, 1.5, 1, 1.5, 1.5, 1])

    with cols[0]:
        # Clickable stat name
        if st.button(f"▸ {display_name}", key=f"btn_{stat_key}", use_container_width=True):
            st.session_state.breakdown_stat = stat_key

    with cols[1]:
        if is_pct:
            st.markdown(f"<span style='color:#66ff66;'>{calc_val:.1f}%</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"<span style='color:#66ff66;'>{calc_val:,.0f}</span>", unsafe_allow_html=True)

    with cols[2]:
        if adj_val != 0:
            color = "#ffaa00"
            st.markdown(f"<span style='color:{color};'>{adj_val:+.1f}</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span style='color:#888;'>-</span>", unsafe_allow_html=True)

    with cols[3]:
        if is_pct:
            st.markdown(f"<span style='color:#66ccff;'>{final_val:.1f}%</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"<span style='color:#66ccff;'>{final_val:,.0f}</span>", unsafe_allow_html=True)

    with cols[4]:
        new_actual = st.number_input(
            f"actual_{stat_key}",
            value=float(actual_val),
            step=0.1 if is_pct else 1.0,
            label_visibility="collapsed",
            key=f"actual_{stat_key}"
        )
        st.session_state.actual_stats[stat_key] = new_actual

    with cols[5]:
        gap = new_actual - final_val
        if abs(gap) > 0.01:
            color = "#66ff66" if gap > 0 else "#ff6666"
            if is_pct:
                st.markdown(f"<span style='color:{color};'>{gap:+.1f}%</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"<span style='color:{color};'>{gap:+,.0f}</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span style='color:#888;'>0</span>", unsafe_allow_html=True)

# ============================================================================
# ACTION BUTTONS
# ============================================================================

st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Apply Adjustments", type="primary", use_container_width=True):
        # Save current adjustments
        auto_save()
        st.success("Adjustments saved!")
        st.rerun()

with col2:
    if st.button("Auto-Fill from Gap", use_container_width=True):
        for stat_key, _, _, _, _ in STAT_DEFINITIONS:
            actual = st.session_state.actual_stats.get(stat_key, 0)
            calc = calculated_stats.get(stat_key, 0)
            data.manual_adjustments[stat_key] = actual - calc
        auto_save()
        st.success("Adjustments auto-filled from gaps!")
        st.rerun()

with col3:
    if st.button("Reset Adjustments", use_container_width=True):
        data.manual_adjustments = {}
        auto_save()
        st.success("Adjustments reset!")
        st.rerun()

# ============================================================================
# STAT BREAKDOWN DIALOG
# ============================================================================

if st.session_state.breakdown_stat:
    stat_key = st.session_state.breakdown_stat
    # Find display name
    display_name = stat_key
    for key, name, _, _, _ in STAT_DEFINITIONS:
        if key == stat_key:
            display_name = name
            break

    calc_val = calculated_stats.get(stat_key, 0)
    is_pct = is_percentage_stat(stat_key)

    @st.dialog(f"Stat Breakdown: {display_name} (Calculated)")
    def show_breakdown():
        st.markdown(f"### {display_name} (Calculated)")
        if is_pct:
            st.markdown(f"**Total: {calc_val:.1f}%**")
        else:
            st.markdown(f"**Total: {calc_val:,.0f}**")

        sources = get_stat_sources(stat_key, raw_stats, current_job_class)

        if sources:
            st.markdown("---")
            for source_name, value in sources:
                if is_pct:
                    st.write(f"**{source_name}:** {value:.1f}%")
                else:
                    st.write(f"**{source_name}:** {value:,.0f}")
        else:
            st.info("No tracked sources for this stat. The value may come from baseline or untracked sources.")

        # Add baseline info if applicable
        for key, name, _, has_baseline, baseline in STAT_DEFINITIONS:
            if key == stat_key and has_baseline:
                st.markdown("---")
                st.write(f"*Includes baseline: +{baseline:.0f}%*")
                break

        if st.button("Close"):
            st.session_state.breakdown_stat = None
            st.rerun()

    show_breakdown()

# ============================================================================
# ADDITIONAL COMBAT STATS
# ============================================================================

st.markdown("---")
st.markdown("<div class='section-header'>Additional Combat Stats (click for breakdown)</div>", unsafe_allow_html=True)

# Show defense pen and attack speed breakdowns
col1, col2 = st.columns(2)

with col1:
    def_pen_sources = raw_stats.get('def_pen_sources', [])
    if def_pen_sources:
        total_def_pen, breakdown = calculate_effective_defense_pen_with_sources(def_pen_sources)
        with st.expander(f"▸ Defense Pen %: {total_def_pen*100:.1f}%"):
            for source_name, raw_value, effective_gain in breakdown:
                display_name = source_name.replace('_', ' ').title()
                st.write(f"**{display_name}:** {raw_value*100:.1f}% (eff: +{effective_gain*100:.1f}%)")

with col2:
    atk_spd_sources = raw_stats.get('attack_speed_sources', [])
    if atk_spd_sources:
        total_atk_spd, breakdown = calculate_effective_attack_speed_with_sources(atk_spd_sources)
        with st.expander(f"▸ Attack Speed %: {total_atk_spd:.1f}%"):
            for source_name, raw_value, effective_gain in breakdown:
                display_name = source_name.replace('_', ' ').title()
                st.write(f"**{display_name}:** {raw_value:.1f}% (eff: +{effective_gain:.1f}%)")

# Final damage sources
fd_sources = raw_stats.get('final_damage_sources', [])
if fd_sources:
    fd_mult = 1.0
    for fd in fd_sources:
        fd_mult *= (1 + fd)
    total_fd = (fd_mult - 1) * 100
    with st.expander(f"▸ Final Damage %: {total_fd:.1f}% (Multiplicative)"):
        for i, fd in enumerate(fd_sources):
            st.write(f"**Source {i+1}:** +{fd*100:.1f}%")
        st.write(f"*Multiplied: {' × '.join([f'(1+{fd*100:.1f}%)' for fd in fd_sources])} = {fd_mult:.4f}*")

# ============================================================================
# INFO
# ============================================================================

st.markdown("---")
st.info("""
**How to use this page:**
1. Click on any stat name to see a breakdown of all contributing sources
2. Enter your actual in-game values in the "Actual" column
3. Click "Auto-Fill from Gap" to automatically calculate adjustments
4. Click "Apply Adjustments" to save - these will be used in all DPS calculations

**Note:** Adjustments help account for stats from sources we don't track (passive skills, buffs, etc.)
""")
