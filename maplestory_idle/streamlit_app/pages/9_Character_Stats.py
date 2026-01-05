"""
Character Stats Page
View aggregated stats from all sources with stat comparison and manual adjustments.
Enter your actual in-game values to identify gaps and fine-tune calculations.
"""
import streamlit as st
from utils.data_manager import save_user_data, EQUIPMENT_SLOTS
from hero_power import HeroPowerPassiveStatType, HERO_POWER_PASSIVE_STATS
from maple_rank import (
    MapleRankStatType, MAPLE_RANK_STATS,
    get_cumulative_main_stat, MAIN_STAT_SPECIAL
)
from companions import COMPANIONS
from weapons import calculate_weapon_atk_str

st.set_page_config(page_title="Character Stats", page_icon="S", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

# Baselines (game defaults)
BASE_MIN_DMG = 60.0
BASE_MAX_DMG = 100.0
BASE_CRIT_DMG = 30.0
BASE_CRIT_RATE = 5.0

# Manual adjustment stat keys with display names
MANUAL_STATS = [
    ("dex_flat", "DEX (Flat)", False),
    ("dex_percent", "DEX %", True),
    ("damage_percent", "Damage %", True),
    ("boss_damage", "Boss Damage %", True),
    ("normal_damage", "Normal Damage %", True),
    ("crit_rate", "Crit Rate %", True),
    ("crit_damage", "Crit Damage %", True),
    ("defense_pen", "Defense Pen %", True),
    ("final_damage", "Final Damage %", True),
    ("attack_flat", "Attack (Flat)", False),
    ("attack_speed", "Attack Speed %", True),
    ("min_dmg_mult", "Min Dmg Mult %", True),
    ("max_dmg_mult", "Max Dmg Mult %", True),
    ("skill_damage", "Skill Damage %", True),
]


def auto_save():
    save_user_data(st.session_state.username, data)


def get_stats_from_all_sources():
    """Calculate stats from all tracked sources."""
    stats = {
        "dex_flat": 0.0,
        "dex_percent": 0.0,
        "damage_percent": 0.0,
        "boss_damage": 0.0,
        "normal_damage": 0.0,
        "crit_rate": BASE_CRIT_RATE,
        "crit_damage": BASE_CRIT_DMG,
        "defense_pen": 0.0,
        "final_damage": 0.0,
        "attack_flat": 0.0,
        "attack_percent": 0.0,
        "attack_speed": 0.0,
        "min_dmg_mult": BASE_MIN_DMG,
        "max_dmg_mult": BASE_MAX_DMG,
        "skill_damage": 0.0,
        "accuracy": 0.0,
    }

    sources = {}

    # -------------------------------------------------------------------------
    # Equipment Potentials
    # -------------------------------------------------------------------------
    pot_stats = {}
    for slot in EQUIPMENT_SLOTS:
        pots = data.equipment_potentials.get(slot, {})
        # Regular potentials (3 lines)
        for i in range(1, 4):
            stat = pots.get(f'line{i}_stat', '')
            value = float(pots.get(f'line{i}_value', 0) or 0)
            if stat and value > 0:
                pot_stats[stat] = pot_stats.get(stat, 0) + value
        # Bonus potentials (3 lines)
        for i in range(1, 4):
            stat = pots.get(f'bonus_line{i}_stat', '')
            value = float(pots.get(f'bonus_line{i}_value', 0) or 0)
            if stat and value > 0:
                pot_stats[stat] = pot_stats.get(stat, 0) + value

    sources['Equipment Potentials'] = pot_stats

    # Map potential stats to our stat keys
    stats["dex_flat"] += pot_stats.get("main_stat_flat", 0) + pot_stats.get("dex_flat", 0)
    stats["dex_percent"] += pot_stats.get("main_stat_pct", 0) + pot_stats.get("dex_pct", 0)
    stats["damage_percent"] += pot_stats.get("damage", 0) + pot_stats.get("damage_pct", 0)
    stats["boss_damage"] += pot_stats.get("boss_damage", 0)
    stats["crit_damage"] += pot_stats.get("crit_damage", 0)
    stats["defense_pen"] += pot_stats.get("def_pen", 0) + pot_stats.get("defense_pen", 0)
    stats["final_damage"] += pot_stats.get("final_damage", 0)
    stats["attack_speed"] += pot_stats.get("attack_speed", 0)
    stats["min_dmg_mult"] += pot_stats.get("min_dmg_mult", 0)
    stats["max_dmg_mult"] += pot_stats.get("max_dmg_mult", 0)

    # -------------------------------------------------------------------------
    # Hero Power Lines (Ability Lines)
    # -------------------------------------------------------------------------
    hp_stats = {}
    for line_key, line in data.hero_power_lines.items():
        stat = line.get('stat', '')
        value = float(line.get('value', 0) or 0)
        if stat and value > 0:
            hp_stats[stat] = hp_stats.get(stat, 0) + value

    sources['Hero Power Lines'] = hp_stats

    stats["damage_percent"] += hp_stats.get("damage", 0)
    stats["boss_damage"] += hp_stats.get("boss_damage", 0)
    stats["crit_damage"] += hp_stats.get("crit_damage", 0)
    stats["defense_pen"] += hp_stats.get("def_pen", 0)
    stats["dex_flat"] += hp_stats.get("main_stat_pct", 0)  # HP main stat is flat
    stats["attack_percent"] += hp_stats.get("attack_pct", 0)
    stats["normal_damage"] += hp_stats.get("normal_damage", 0)

    # -------------------------------------------------------------------------
    # Hero Power Passives
    # -------------------------------------------------------------------------
    hpp_stats = {}
    passives = data.hero_power_passives or {}

    for stat_type in HeroPowerPassiveStatType:
        stat_key = stat_type.value
        level = passives.get(stat_key, 0)
        if level > 0:
            stat_info = HERO_POWER_PASSIVE_STATS.get(stat_type, {})
            per_level = stat_info.get("per_level", 1.0)
            value = level * per_level
            hpp_stats[stat_key] = value

    sources['Hero Power Passives'] = hpp_stats

    stats["dex_flat"] += hpp_stats.get("main_stat", 0)
    stats["damage_percent"] += hpp_stats.get("damage_percent", 0)
    stats["attack_flat"] += hpp_stats.get("attack", 0)
    stats["accuracy"] += hpp_stats.get("accuracy", 0)

    # -------------------------------------------------------------------------
    # Maple Rank
    # -------------------------------------------------------------------------
    mr_stats = {}
    mr = data.maple_rank or {}

    # Main stat from stages
    stage = mr.get('current_stage', 1)
    ms_level = mr.get('main_stat_level', 0)
    special = mr.get('special_main_stat', 0)

    regular_ms = get_cumulative_main_stat(stage, ms_level)
    special_ms = MAIN_STAT_SPECIAL["base_value"] + special * MAIN_STAT_SPECIAL["per_point"]
    total_ms = regular_ms + special_ms

    if total_ms > 0:
        mr_stats['main_stat_flat'] = total_ms

    # Stat bonuses
    stat_levels = mr.get('stat_levels', {})
    if isinstance(stat_levels, dict):
        for stat_type in MapleRankStatType:
            if stat_type in MAPLE_RANK_STATS:
                stat_key = stat_type.value
                level = stat_levels.get(stat_key, 0)
                if level > 0:
                    per_level = MAPLE_RANK_STATS[stat_type]["per_level"]
                    value = level * per_level
                    mr_stats[stat_key] = value

    sources['Maple Rank'] = mr_stats

    stats["dex_flat"] += mr_stats.get('main_stat_flat', 0)
    stats["damage_percent"] += mr_stats.get('damage_percent', 0)
    stats["boss_damage"] += mr_stats.get('boss_damage', 0)
    stats["normal_damage"] += mr_stats.get('normal_damage', 0)
    stats["crit_damage"] += mr_stats.get('crit_damage', 0)
    stats["crit_rate"] += mr_stats.get('crit_rate', 0)
    stats["skill_damage"] += mr_stats.get('skill_damage', 0)
    stats["min_dmg_mult"] += mr_stats.get('min_dmg_mult', 0)
    stats["max_dmg_mult"] += mr_stats.get('max_dmg_mult', 0)
    stats["attack_speed"] += mr_stats.get('attack_speed', 0)
    stats["accuracy"] += mr_stats.get('accuracy', 0)

    # -------------------------------------------------------------------------
    # Companions
    # -------------------------------------------------------------------------
    comp_stats = {}
    companion_levels = data.companion_levels or {}

    # On-equip stats from equipped companions
    on_equip_totals = {
        "attack_speed": 0.0,
        "min_dmg_mult": 0.0,
        "max_dmg_mult": 0.0,
        "boss_damage": 0.0,
        "normal_damage": 0.0,
        "crit_rate": 0.0,
        "flat_attack": 0.0,
    }

    for comp_key in (data.equipped_companions or []):
        if not comp_key or comp_key not in COMPANIONS:
            continue

        level = companion_levels.get(comp_key, 0)
        if level <= 0:
            continue

        companion = COMPANIONS[comp_key]
        on_equip_val = companion.get_on_equip_value(level)
        stat_type = companion.on_equip_type.value  # e.g., "attack_speed", "boss_damage"

        if stat_type in on_equip_totals:
            on_equip_totals[stat_type] += on_equip_val

    comp_stats.update({f"on_equip_{k}": v for k, v in on_equip_totals.items() if v > 0})

    # Inventory stats from ALL owned companions
    inv_totals = {
        "attack": 0.0,
        "main_stat": 0.0,
        "damage": 0.0,
        "max_hp": 0.0,
    }

    for comp_key, level in companion_levels.items():
        if level <= 0 or comp_key not in COMPANIONS:
            continue

        companion = COMPANIONS[comp_key]
        inv_stats = companion.get_inventory_stats(level)

        for k, v in inv_stats.items():
            if k in inv_totals:
                inv_totals[k] += v

    comp_stats.update({f"inv_{k}": v for k, v in inv_totals.items() if v > 0})

    sources['Companions'] = comp_stats

    # Apply companion stats
    stats["boss_damage"] += on_equip_totals.get("boss_damage", 0)
    stats["normal_damage"] += on_equip_totals.get("normal_damage", 0)
    stats["crit_rate"] += on_equip_totals.get("crit_rate", 0)
    stats["min_dmg_mult"] += on_equip_totals.get("min_dmg_mult", 0)
    stats["max_dmg_mult"] += on_equip_totals.get("max_dmg_mult", 0)
    stats["attack_speed"] += on_equip_totals.get("attack_speed", 0)
    stats["attack_flat"] += on_equip_totals.get("flat_attack", 0)
    stats["damage_percent"] += inv_totals.get("damage", 0)
    stats["dex_flat"] += inv_totals.get("main_stat", 0)
    stats["attack_flat"] += inv_totals.get("attack", 0)

    # -------------------------------------------------------------------------
    # Weapons
    # -------------------------------------------------------------------------
    weapon_stats = {}

    # New format weapons
    total_inventory_atk = 0.0
    equipped_atk = 0.0

    for idx, weapon in enumerate(data.weapon_inventory or []):
        rarity = weapon.get('rarity', 'normal')
        tier = weapon.get('tier', 4)
        level = weapon.get('level', 1)
        calc_stats = calculate_weapon_atk_str(rarity, tier, level)

        total_inventory_atk += calc_stats['inventory_atk']
        if data.equipped_weapon == idx:
            equipped_atk = calc_stats['on_equip_atk']

    weapon_stats['attack_percent'] = equipped_atk + total_inventory_atk

    sources['Weapons'] = weapon_stats
    stats["attack_percent"] += weapon_stats.get('attack_percent', 0)

    # -------------------------------------------------------------------------
    # Equipment Sets (Medals & Costumes)
    # -------------------------------------------------------------------------
    sets_stats = {}
    if data.equipment_sets.get('medal', 0) > 0:
        sets_stats['medal_main_stat'] = data.equipment_sets['medal']
        stats["dex_flat"] += data.equipment_sets['medal']
    if data.equipment_sets.get('costume', 0) > 0:
        sets_stats['costume_main_stat'] = data.equipment_sets['costume']
        stats["dex_flat"] += data.equipment_sets['costume']

    sources['Equipment Sets'] = sets_stats

    # -------------------------------------------------------------------------
    # Artifacts
    # -------------------------------------------------------------------------
    art_stats = {}
    for slot_key, artifact in data.artifacts_equipped.items():
        for i in range(1, 4):
            stat = artifact.get(f'pot{i}', '')
            value = float(artifact.get(f'pot{i}_val', 0) or 0)
            if stat and value > 0:
                art_stats[stat] = art_stats.get(stat, 0) + value

    sources['Artifacts'] = art_stats

    stats["damage_percent"] += art_stats.get("damage", 0) * 100
    stats["boss_damage"] += art_stats.get("boss_damage", 0) * 100
    stats["crit_damage"] += art_stats.get("crit_damage", 0) * 100
    stats["defense_pen"] += art_stats.get("def_pen", 0) * 100
    stats["dex_flat"] += art_stats.get("main_stat_flat", 0)
    stats["dex_percent"] += art_stats.get("main_stat", 0) * 100
    stats["attack_flat"] += art_stats.get("attack_flat", 0)

    return stats, sources


def get_final_stats(calculated_stats):
    """Apply manual adjustments to calculated stats."""
    final = calculated_stats.copy()
    adj = data.manual_adjustments or {}

    for stat_key, _, _ in MANUAL_STATS:
        final[stat_key] = final.get(stat_key, 0) + adj.get(stat_key, 0)

    return final


st.title("Character Stats")
st.markdown("View aggregated stats and fine-tune with manual adjustments.")

# Initialize manual adjustments if needed
if not data.manual_adjustments:
    data.manual_adjustments = {stat_key: 0.0 for stat_key, _, _ in MANUAL_STATS}

# Quick summary
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Character Level", data.character_level)
with col2:
    st.metric("All Skills", f"+{data.all_skills}")
with col3:
    st.metric("Combat Mode", data.combat_mode.replace("_", " ").title())
with col4:
    st.metric("Chapter", data.chapter.replace("Chapter ", "Ch. "))

st.divider()

# Get calculated stats
calculated_stats, sources = get_stats_from_all_sources()
final_stats = get_final_stats(calculated_stats)

tab1, tab2, tab3, tab4 = st.tabs(["Stat Comparison", "Manual Adjustments", "Stats by Source", "Summary"])

# ============================================================================
# TAB 1: STAT COMPARISON
# ============================================================================
with tab1:
    st.markdown("**Compare Calculated vs Actual** - Enter your in-game values to find gaps")

    # Initialize actual stats if not present
    if 'actual_stats' not in st.session_state:
        st.session_state.actual_stats = {}

    # Comparison table
    comparison_data = []

    col_calc, col_adj, col_final, col_actual, col_gap = st.columns([1.5, 1, 1.5, 1.5, 1])

    with col_calc:
        st.markdown("**Calculated**")
    with col_adj:
        st.markdown("**Adjustment**")
    with col_final:
        st.markdown("**Final**")
    with col_actual:
        st.markdown("**Actual (In-Game)**")
    with col_gap:
        st.markdown("**Gap**")

    for stat_key, display_name, is_pct in MANUAL_STATS:
        calc_val = calculated_stats.get(stat_key, 0)
        adj_val = data.manual_adjustments.get(stat_key, 0)
        final_val = final_stats.get(stat_key, 0)

        col_calc, col_adj, col_final, col_actual, col_gap = st.columns([1.5, 1, 1.5, 1.5, 1])

        with col_calc:
            if is_pct:
                st.text(f"{display_name}: {calc_val:.2f}%")
            else:
                st.text(f"{display_name}: {calc_val:,.0f}")

        with col_adj:
            if adj_val != 0:
                st.text(f"{adj_val:+.1f}")
            else:
                st.text("-")

        with col_final:
            if is_pct:
                st.text(f"{final_val:.2f}%")
            else:
                st.text(f"{final_val:,.0f}")

        with col_actual:
            actual_key = f"actual_{stat_key}"
            current_actual = st.session_state.actual_stats.get(stat_key, final_val)
            new_actual = st.number_input(
                f"Actual {stat_key}",
                value=float(current_actual),
                step=0.1 if is_pct else 1.0,
                key=actual_key,
                label_visibility="collapsed"
            )
            st.session_state.actual_stats[stat_key] = new_actual

        with col_gap:
            gap = new_actual - final_val
            if abs(gap) > 0.01:
                color = "red" if gap < 0 else "green"
                st.markdown(f":{color}[{gap:+.1f}]")
            else:
                st.text("0")

    st.divider()

    # Action buttons
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Auto-Fill Adjustments from Gap", key="auto_fill"):
            for stat_key, _, _ in MANUAL_STATS:
                actual = st.session_state.actual_stats.get(stat_key, 0)
                calc = calculated_stats.get(stat_key, 0)
                data.manual_adjustments[stat_key] = actual - calc
            auto_save()
            st.rerun()

    with col2:
        if st.button("Reset All Adjustments", key="reset_adj"):
            for stat_key, _, _ in MANUAL_STATS:
                data.manual_adjustments[stat_key] = 0.0
            auto_save()
            st.rerun()

    with col3:
        if st.button("Copy Final to Actual", key="copy_final"):
            for stat_key, _, _ in MANUAL_STATS:
                st.session_state.actual_stats[stat_key] = final_stats.get(stat_key, 0)
            st.rerun()

# ============================================================================
# TAB 2: MANUAL ADJUSTMENTS
# ============================================================================
with tab2:
    st.markdown("**Manual Adjustments** - Fine-tune stats that don't match in-game values")
    st.caption("These adjustments are added to the calculated stats to produce final values.")

    col1, col2 = st.columns(2)

    for idx, (stat_key, display_name, is_pct) in enumerate(MANUAL_STATS):
        current_adj = data.manual_adjustments.get(stat_key, 0)

        with col1 if idx < len(MANUAL_STATS) // 2 else col2:
            new_adj = st.number_input(
                display_name,
                value=float(current_adj),
                step=0.1 if is_pct else 1.0,
                key=f"adj_{stat_key}",
                help=f"Adjustment for {display_name}"
            )

            if new_adj != current_adj:
                data.manual_adjustments[stat_key] = new_adj
                auto_save()

    st.divider()

    # Quick actions
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Reset All to Zero", key="reset_all"):
            for stat_key, _, _ in MANUAL_STATS:
                data.manual_adjustments[stat_key] = 0.0
            auto_save()
            st.rerun()

    # Show active adjustments summary
    active = [(k, v) for k, v, _ in MANUAL_STATS if data.manual_adjustments.get(k, 0) != 0]
    if active:
        st.markdown("**Active Adjustments:**")
        adj_summary = ", ".join([f"{k}: {data.manual_adjustments[k]:+.1f}" for k, _, _ in MANUAL_STATS if data.manual_adjustments.get(k, 0) != 0])
        st.info(adj_summary)

# ============================================================================
# TAB 3: STATS BY SOURCE
# ============================================================================
with tab3:
    st.markdown("**Stats Breakdown by Source**")

    for source_name, source_stats in sources.items():
        if source_stats:
            with st.expander(f"**{source_name}**", expanded=True):
                stat_items = list(source_stats.items())
                cols = st.columns(3)
                for idx, (stat, value) in enumerate(stat_items):
                    with cols[idx % 3]:
                        display = stat.replace("_", " ").title()
                        if isinstance(value, float):
                            st.write(f"{display}: **+{value:.2f}**")
                        else:
                            st.write(f"{display}: **+{value:,}**")

# ============================================================================
# TAB 4: SUMMARY
# ============================================================================
with tab4:
    st.markdown("**Final Stats Summary** - Calculated + Adjustments")

    # Key stats
    st.markdown("### Key Combat Stats")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("DEX (Flat)", f"+{final_stats['dex_flat']:,.0f}")
        st.metric("DEX %", f"+{final_stats['dex_percent']:.2f}%")
        st.metric("Attack (Flat)", f"+{final_stats['attack_flat']:,.0f}")
        st.metric("Attack %", f"+{final_stats['attack_percent']:.2f}%")

    with col2:
        st.metric("Damage %", f"+{final_stats['damage_percent']:.2f}%")
        st.metric("Boss Damage %", f"+{final_stats['boss_damage']:.2f}%")
        st.metric("Normal Damage %", f"+{final_stats['normal_damage']:.2f}%")
        st.metric("Crit Damage %", f"+{final_stats['crit_damage']:.2f}%")

    with col3:
        st.metric("Defense Pen %", f"+{final_stats['defense_pen']:.2f}%")
        st.metric("Final Damage %", f"+{final_stats['final_damage']:.2f}%")
        st.metric("Crit Rate %", f"+{final_stats['crit_rate']:.2f}%")
        st.metric("Skill Damage %", f"+{final_stats['skill_damage']:.2f}%")

    st.divider()

    st.markdown("### Multiplier Stats")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Min Damage Mult %", f"+{final_stats['min_dmg_mult']:.2f}%")
    with col2:
        st.metric("Max Damage Mult %", f"+{final_stats['max_dmg_mult']:.2f}%")
    with col3:
        st.metric("Attack Speed %", f"+{final_stats['attack_speed']:.2f}%")

    st.divider()

    # Full stats table
    st.markdown("### All Stats Table")
    stats_table = []
    for stat_key, display_name, is_pct in MANUAL_STATS:
        calc = calculated_stats.get(stat_key, 0)
        adj = data.manual_adjustments.get(stat_key, 0)
        final = final_stats.get(stat_key, 0)

        if is_pct:
            stats_table.append({
                "Stat": display_name,
                "Calculated": f"{calc:.2f}%",
                "Adjustment": f"{adj:+.2f}%" if adj != 0 else "-",
                "Final": f"{final:.2f}%",
            })
        else:
            stats_table.append({
                "Stat": display_name,
                "Calculated": f"{calc:,.0f}",
                "Adjustment": f"{adj:+.0f}" if adj != 0 else "-",
                "Final": f"{final:,.0f}",
            })

    st.dataframe(stats_table, use_container_width=True, hide_index=True)

    st.divider()

    # Notes
    st.markdown("### Notes")
    st.info("""
**Baseline Values Included:**
- Min Damage Mult: +60% baseline
- Max Damage Mult: +100% baseline
- Crit Damage: +30% baseline
- Crit Rate: +5% baseline

**Manual Adjustments:**
Use the Stat Comparison tab to enter your actual in-game values.
Click "Auto-Fill Adjustments from Gap" to automatically calculate the adjustments needed.

**Missing Sources:**
Some stats may not be fully tracked. Use manual adjustments to compensate for untracked sources like:
- Guild stats
- Passive skills
- Equipment base stats
    """)
