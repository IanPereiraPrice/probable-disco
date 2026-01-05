"""
Hero Power Page
Configure hero power rerollable lines, passive stats, level config, and get reroll recommendations.
"""
import streamlit as st
from utils.data_manager import save_user_data
from hero_power import (
    HeroPowerStatType, HeroPowerTier, HeroPowerPassiveStatType,
    STAT_DISPLAY_NAMES, TIER_COLORS, HERO_POWER_PASSIVE_STATS,
    PASSIVE_STAT_DISPLAY_NAMES, HERO_POWER_STAT_RANGES,
    HERO_POWER_REROLL_COSTS, HeroPowerLine, HeroPowerConfig,
    HeroPowerLevelConfig, score_hero_power_line, get_line_score_category,
    score_hero_power_line_for_mode, analyze_lock_strategy,
    rank_all_possible_lines_by_dps, MODE_STAT_ADJUSTMENTS,
    STAT_DPS_WEIGHTS, TIER_SCORE_MULTIPLIERS
)

st.set_page_config(page_title="Hero Power", page_icon="*", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

# Build stat options from enum
HP_STATS = [""] + [s.value for s in HeroPowerStatType]
HP_STAT_DISPLAY = {s.value: STAT_DISPLAY_NAMES.get(s, s.value) for s in HeroPowerStatType}
HP_STAT_DISPLAY[""] = "---"

HP_TIERS = [t.value for t in HeroPowerTier]
HP_TIER_DISPLAY = {t.value: t.value.capitalize() for t in HeroPowerTier}

COMBAT_MODES = ["stage", "boss", "world_boss"]
COMBAT_MODE_DISPLAY = {"stage": "Stage", "boss": "Boss", "world_boss": "World Boss"}


def auto_save():
    save_user_data(st.session_state.username, data)


def get_value_range(tier_str: str, stat_str: str) -> tuple:
    """Get min/max value range for a stat at a given tier."""
    if not tier_str or not stat_str:
        return (0, 100)
    try:
        tier = HeroPowerTier(tier_str)
        stat = HeroPowerStatType(stat_str)
        ranges = HERO_POWER_STAT_RANGES.get(tier, {})
        if stat in ranges:
            return ranges[stat]
    except (ValueError, KeyError):
        pass
    return (0, 100)


def get_level_config() -> HeroPowerLevelConfig:
    """Build HeroPowerLevelConfig from user data."""
    lc = data.hero_power_level or {}
    return HeroPowerLevelConfig(
        level=lc.get('level', 15),
        mystic_rate=lc.get('mystic_rate', 0.14),
        legendary_rate=lc.get('legendary_rate', 1.63),
        unique_rate=lc.get('unique_rate', 3.3),
        epic_rate=lc.get('epic_rate', 37.93),
        rare_rate=lc.get('rare_rate', 32.0),
        common_rate=lc.get('common_rate', 25.0),
        base_cost=lc.get('base_cost', 89),
    )


def build_hero_power_config() -> HeroPowerConfig:
    """Build HeroPowerConfig from current user data lines."""
    lines = []
    for i in range(1, 7):
        line_key = f'line{i}'
        line_data = data.hero_power_lines.get(line_key, {})
        stat_str = line_data.get('stat', '')
        tier_str = line_data.get('tier', 'common').lower()
        value = float(line_data.get('value', 0))
        locked = line_data.get('locked', False)

        try:
            stat_type = HeroPowerStatType(stat_str) if stat_str else HeroPowerStatType.DAMAGE
        except ValueError:
            stat_type = HeroPowerStatType.DAMAGE

        try:
            tier = HeroPowerTier(tier_str)
        except ValueError:
            tier = HeroPowerTier.COMMON

        lines.append(HeroPowerLine(
            slot=i,
            stat_type=stat_type,
            value=value,
            tier=tier,
            is_locked=locked
        ))

    return HeroPowerConfig(lines=lines)


def init_preset_if_needed():
    """Initialize presets with Default if empty."""
    if not data.hero_power_presets:
        # Copy current lines to Default preset
        data.hero_power_presets["Default"] = {'lines': dict(data.hero_power_lines)}
        data.active_hero_power_preset = "Default"
        auto_save()


def switch_preset(preset_name: str):
    """Switch to a different preset, saving current first."""
    # Save current lines to current preset
    if data.active_hero_power_preset:
        data.hero_power_presets[data.active_hero_power_preset] = {'lines': dict(data.hero_power_lines)}

    # Load new preset
    if preset_name in data.hero_power_presets:
        preset_data = data.hero_power_presets[preset_name]
        data.hero_power_lines = dict(preset_data.get('lines', {}))

    data.active_hero_power_preset = preset_name
    auto_save()


st.title("Hero Power")

# Initialize presets
init_preset_if_needed()

# Initialize hero power lines if not present
for i in range(1, 7):
    line_key = f'line{i}'
    if line_key not in data.hero_power_lines:
        data.hero_power_lines[line_key] = {
            'stat': '',
            'value': 0.0,
            'tier': 'common',
            'locked': False,
        }

# Preset management in sidebar-like area
with st.expander("Preset Management", expanded=False):
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        preset_names = list(data.hero_power_presets.keys()) if data.hero_power_presets else ["Default"]
        current_preset = data.active_hero_power_preset if data.active_hero_power_preset in preset_names else preset_names[0]
        current_idx = preset_names.index(current_preset) if current_preset in preset_names else 0

        selected_preset = st.selectbox(
            "Active Preset",
            options=preset_names,
            index=current_idx,
            key="preset_select"
        )

        if selected_preset != data.active_hero_power_preset:
            switch_preset(selected_preset)
            st.rerun()

    with col2:
        new_preset_name = st.text_input("New Preset", key="new_preset_name", placeholder="Name...")
        if st.button("Create", key="create_preset"):
            if new_preset_name and new_preset_name not in data.hero_power_presets:
                # Copy current lines to new preset
                data.hero_power_presets[new_preset_name] = {'lines': dict(data.hero_power_lines)}
                data.active_hero_power_preset = new_preset_name
                auto_save()
                st.rerun()

    with col3:
        st.write("")  # Spacer
        if st.button("Delete Current", key="delete_preset"):
            if len(data.hero_power_presets) > 1 and data.active_hero_power_preset in data.hero_power_presets:
                del data.hero_power_presets[data.active_hero_power_preset]
                data.active_hero_power_preset = list(data.hero_power_presets.keys())[0]
                # Load the new active preset
                preset_data = data.hero_power_presets[data.active_hero_power_preset]
                data.hero_power_lines = dict(preset_data.get('lines', {}))
                auto_save()
                st.rerun()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Ability Lines", "Line Analysis", "Passive Stats", "Level Config", "Summary"])

# ============================================================================
# TAB 1: ABILITY LINES (6 rerollable lines)
# ============================================================================
with tab1:
    st.markdown("**6 Rerollable Lines** - Lock valuable lines before rerolling")

    # Calculate reroll cost based on locked lines
    locked_count = sum(1 for i in range(1, 7) if data.hero_power_lines.get(f'line{i}', {}).get('locked', False))
    level_config = get_level_config()
    reroll_cost = level_config.get_reroll_cost(locked_count)

    st.caption(f"Locked: {locked_count}/6 | Reroll Cost: {reroll_cost} Medals")

    # Display all 6 lines in a dense format
    for i in range(1, 7):
        line_key = f'line{i}'
        line = data.hero_power_lines[line_key]

        tier_str = line.get('tier', 'common').lower()
        stat_str = line.get('stat', '')
        try:
            tier_color = TIER_COLORS.get(HeroPowerTier(tier_str), "#888888")
        except ValueError:
            tier_color = "#888888"

        col_lock, col_tier, col_stat, col_val, col_score = st.columns([0.6, 1.2, 2.2, 1.2, 1.0])

        with col_lock:
            new_locked = st.checkbox(
                "",
                value=line.get('locked', False),
                key=f"hp_lock_{i}",
                help=f"Lock Line {i}"
            )
            if new_locked != line.get('locked'):
                line['locked'] = new_locked
                auto_save()

        with col_tier:
            tier_idx = HP_TIERS.index(tier_str) if tier_str in HP_TIERS else 0
            new_tier = st.selectbox(
                f"L{i} Tier",
                options=HP_TIERS,
                index=tier_idx,
                key=f"hp_tier_{i}",
                format_func=lambda x: HP_TIER_DISPLAY.get(x, x),
                label_visibility="collapsed"
            )
            if new_tier != tier_str:
                line['tier'] = new_tier
                auto_save()

        with col_stat:
            stat_idx = HP_STATS.index(stat_str) if stat_str in HP_STATS else 0
            new_stat = st.selectbox(
                f"L{i} Stat",
                options=HP_STATS,
                index=stat_idx,
                key=f"hp_stat_{i}",
                format_func=lambda x: HP_STAT_DISPLAY.get(x, x),
                label_visibility="collapsed"
            )
            if new_stat != stat_str:
                line['stat'] = new_stat
                auto_save()

        with col_val:
            min_val, max_val = get_value_range(new_tier, new_stat)
            min_val_f = float(min_val)
            max_val_f = float(max_val)
            current_val = float(line.get('value', 0))
            current_val = max(min_val_f, min(max_val_f, current_val))
            step_val = 0.5 if max_val_f < 100 else 10.0

            new_value = st.number_input(
                f"L{i} Value",
                min_value=min_val_f,
                max_value=max_val_f,
                value=current_val,
                step=step_val,
                key=f"hp_val_{i}",
                label_visibility="collapsed"
            )
            if new_value != line.get('value'):
                line['value'] = new_value
                auto_save()

        with col_score:
            # Calculate and display line score
            if new_stat:
                try:
                    hp_line = HeroPowerLine(
                        slot=i,
                        stat_type=HeroPowerStatType(new_stat),
                        value=new_value,
                        tier=HeroPowerTier(new_tier),
                        is_locked=new_locked
                    )
                    score = score_hero_power_line(hp_line)
                    category, color = get_line_score_category(score)
                    lock_icon = "L" if new_locked else ""
                    st.markdown(f"<span style='color:{color};'>{lock_icon}{score:.0f} ({category})</span>", unsafe_allow_html=True)
                except (ValueError, KeyError):
                    st.write("---")
            else:
                st.write("---")

    st.divider()

    # Lines summary table
    st.markdown("**Lines Summary**")
    summary_rows = []
    for i in range(1, 7):
        line = data.hero_power_lines[f'line{i}']
        stat_str = line.get('stat', '')
        if stat_str:
            tier_str = line.get('tier', 'common')
            val = line.get('value', 0)
            locked = "L" if line.get('locked') else ""

            # Format value (flat stats vs %)
            is_flat = stat_str in ['main_stat_pct', 'defense', 'max_hp']
            val_str = f"{val:,.0f}" if is_flat else f"{val:.1f}%"

            summary_rows.append({
                "Line": i,
                "Lock": locked,
                "Tier": tier_str.capitalize(),
                "Stat": HP_STAT_DISPLAY.get(stat_str, stat_str),
                "Value": val_str,
            })

    if summary_rows:
        st.dataframe(summary_rows, use_container_width=True, hide_index=True)

# ============================================================================
# TAB 2: LINE ANALYSIS & RECOMMENDATIONS
# ============================================================================
with tab2:
    st.markdown("**Line Analysis & Reroll Recommendations**")

    # Combat mode selector for analysis
    analysis_mode = st.selectbox(
        "Optimize for",
        options=COMBAT_MODES,
        format_func=lambda x: COMBAT_MODE_DISPLAY.get(x, x),
        key="analysis_mode"
    )

    # Build current config
    hp_config = build_hero_power_config()
    level_config = get_level_config()

    # Analyze lock strategy
    analysis = analyze_lock_strategy(hp_config, level_config)

    st.markdown("### Current Lines Analysis")

    # Show each line with its analysis
    analysis_rows = []
    for la in analysis['efficiency_analysis']:
        line = la['line']
        eff = la['efficiency_result']

        # Calculate mode-specific score
        mode_score = score_hero_power_line_for_mode(line, analysis_mode)
        category, color = get_line_score_category(mode_score)

        # Recommendation
        rec = eff['recommendation']
        rec_color = "#00ff88" if rec == "LOCK" else "#ff9f43"

        analysis_rows.append({
            "Slot": line.slot,
            "Stat": STAT_DISPLAY_NAMES.get(line.stat_type, line.stat_type.value),
            "Tier": line.tier.value.capitalize(),
            "Value": f"{line.value:.1f}" if line.stat_type not in [HeroPowerStatType.MAIN_STAT_PCT, HeroPowerStatType.DEFENSE, HeroPowerStatType.MAX_HP] else f"{line.value:,.0f}",
            "Score": f"{mode_score:.0f}",
            "Category": category,
            "P(Better)": f"{eff['probability_of_improvement']:.1%}",
            "Recommendation": rec,
        })

    st.dataframe(analysis_rows, use_container_width=True, hide_index=True)

    # Show strategy summary
    col1, col2, col3 = st.columns(3)
    with col1:
        lock_slots = ", ".join(str(s) for s in analysis['lines_to_lock']) if analysis['lines_to_lock'] else "None"
        st.metric("Lines to Lock", lock_slots)
    with col2:
        reroll_slots = ", ".join(str(s) for s in analysis['lines_to_reroll']) if analysis['lines_to_reroll'] else "None"
        st.metric("Lines to Reroll", reroll_slots)
    with col3:
        st.metric("Reroll Cost", f"{analysis['cost_per_reroll']} Medals")

    st.divider()

    # Best lines reference
    st.markdown("### Best Lines to Target")
    st.caption("Shows the most valuable lines to aim for when rerolling")

    rankings = rank_all_possible_lines_by_dps()
    mode_rankings = rankings.get(analysis_mode, [])

    top_lines = []
    for entry in mode_rankings[:12]:
        top_lines.append({
            "Rank": entry['rank'],
            "Stat": entry['stat'],
            "Tier": entry['tier'],
            "Range": entry['value_range'],
            "Est. DPS": f"+{entry['dps_contribution']:.2f}%",
        })

    if top_lines:
        st.dataframe(top_lines, use_container_width=True, hide_index=True)

    st.divider()

    # Mode-specific tips
    st.markdown("### Mode-Specific Tips")
    mode_adj = MODE_STAT_ADJUSTMENTS.get(analysis_mode, {})

    tips = []
    if analysis_mode == "stage":
        tips = [
            "Normal Damage has value for clearing mobs",
            "Boss Damage is less valuable (less boss time)",
            "Balanced approach works well"
        ]
    elif analysis_mode == "boss":
        tips = [
            "Boss Damage is very important",
            "Normal Damage is USELESS on bosses",
            "Defense Penetration is strong"
        ]
    elif analysis_mode == "world_boss":
        tips = [
            "Defense Penetration is VERY valuable (high enemy DEF)",
            "Boss Damage is important",
            "Normal Damage is USELESS"
        ]

    for tip in tips:
        st.markdown(f"- {tip}")

# ============================================================================
# TAB 3: PASSIVE STATS (Levelable)
# ============================================================================
with tab3:
    st.markdown("**Passive Stats** - Upgraded with Gold (Stage 6 max levels)")

    # Initialize passive stats if not present
    if not data.hero_power_passives:
        data.hero_power_passives = {}
        for stat_type in HeroPowerPassiveStatType:
            data.hero_power_passives[stat_type.value] = 0

    col1, col2 = st.columns(2)

    passive_types = list(HeroPowerPassiveStatType)

    for idx, stat_type in enumerate(passive_types):
        stat_key = stat_type.value
        stat_info = HERO_POWER_PASSIVE_STATS.get(stat_type, {})
        max_level = stat_info.get("max_level", 60)
        per_level = stat_info.get("per_level", 1.0)
        display_name = PASSIVE_STAT_DISPLAY_NAMES.get(stat_type, stat_key)

        current_level = data.hero_power_passives.get(stat_key, 0)
        current_value = current_level * per_level

        with col1 if idx < 3 else col2:
            # Show stat name and current value
            if stat_type == HeroPowerPassiveStatType.DAMAGE_PERCENT:
                value_str = f"{current_value:.1f}%"
            else:
                value_str = f"{current_value:,.0f}"

            st.markdown(f"**{display_name}**: {value_str}")

            new_level = st.slider(
                f"Level ({stat_key})",
                min_value=0,
                max_value=max_level,
                value=current_level,
                key=f"passive_{stat_key}",
                label_visibility="collapsed"
            )

            if new_level != current_level:
                data.hero_power_passives[stat_key] = new_level
                auto_save()

            st.caption(f"Lv {new_level}/{max_level} | +{per_level:.2f}/lv")

    st.divider()

    # Passive stats summary
    st.markdown("**Passive Stats Totals**")
    passive_totals = []
    for stat_type in HeroPowerPassiveStatType:
        stat_key = stat_type.value
        stat_info = HERO_POWER_PASSIVE_STATS.get(stat_type, {})
        max_level = stat_info.get("max_level", 60)
        per_level = stat_info.get("per_level", 1.0)
        display_name = PASSIVE_STAT_DISPLAY_NAMES.get(stat_type, stat_key)

        level = data.hero_power_passives.get(stat_key, 0)
        current_value = level * per_level
        max_value = max_level * per_level

        if stat_type == HeroPowerPassiveStatType.DAMAGE_PERCENT:
            current_str = f"{current_value:.1f}%"
            max_str = f"{max_value:.1f}%"
        else:
            current_str = f"{current_value:,.0f}"
            max_str = f"{max_value:,.0f}"

        passive_totals.append({
            "Stat": display_name,
            "Level": f"{level}/{max_level}",
            "Current": current_str,
            "Max": max_str,
        })

    st.dataframe(passive_totals, use_container_width=True, hide_index=True)

# ============================================================================
# TAB 4: LEVEL CONFIG (affects tier rates and costs)
# ============================================================================
with tab4:
    st.markdown("**Hero Power Level** - Affects tier probabilities and reroll cost")
    st.caption("Enter your Hero Power level's tier rates (shown in-game)")

    # Initialize level config if not present
    if not data.hero_power_level:
        data.hero_power_level = {
            'level': 15,
            'mystic_rate': 0.14,
            'legendary_rate': 1.63,
            'unique_rate': 3.3,
            'epic_rate': 37.93,
            'rare_rate': 32.0,
            'common_rate': 25.0,
            'base_cost': 89,
        }

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Level & Cost**")
        new_level = st.number_input(
            "Hero Power Level",
            min_value=1,
            max_value=30,
            value=data.hero_power_level.get('level', 15),
            key="hp_level"
        )
        if new_level != data.hero_power_level.get('level'):
            data.hero_power_level['level'] = new_level
            auto_save()

        new_base_cost = st.number_input(
            "Base Reroll Cost (0 locks)",
            min_value=1,
            max_value=500,
            value=data.hero_power_level.get('base_cost', 89),
            key="hp_base_cost"
        )
        if new_base_cost != data.hero_power_level.get('base_cost'):
            data.hero_power_level['base_cost'] = new_base_cost
            auto_save()

    with col2:
        st.markdown("**Tier Rates (%)**")

        tiers_config = [
            ('mystic_rate', 'Mystic %', 0.14),
            ('legendary_rate', 'Legendary %', 1.63),
            ('unique_rate', 'Unique %', 3.3),
            ('epic_rate', 'Epic %', 37.93),
            ('rare_rate', 'Rare %', 32.0),
            ('common_rate', 'Common %', 25.0),
        ]

        for key, label, default in tiers_config:
            new_rate = st.number_input(
                label,
                min_value=0.0,
                max_value=100.0,
                value=float(data.hero_power_level.get(key, default)),
                step=0.01,
                format="%.2f",
                key=f"hp_rate_{key}"
            )
            if new_rate != data.hero_power_level.get(key):
                data.hero_power_level[key] = new_rate
                auto_save()

    st.divider()

    # Show reroll costs
    st.markdown("**Reroll Cost by Locked Lines**")
    base = data.hero_power_level.get('base_cost', 89)
    cost_table = []
    for locks in range(6):
        cost = base + (locks * 43)
        cost_table.append({"Locked Lines": locks, "Medal Cost": cost})
    st.dataframe(cost_table, use_container_width=True, hide_index=True)

# ============================================================================
# TAB 5: SUMMARY (Total stats from Hero Power)
# ============================================================================
with tab5:
    st.markdown("**Hero Power Stats Summary**")

    # Ability Lines totals
    st.markdown("### From Ability Lines")
    line_totals = {}
    for i in range(1, 7):
        line = data.hero_power_lines.get(f'line{i}', {})
        stat_str = line.get('stat', '')
        if stat_str:
            val = line.get('value', 0)
            if stat_str not in line_totals:
                line_totals[stat_str] = 0
            line_totals[stat_str] += val

    if line_totals:
        line_summary = []
        for stat_str, total in line_totals.items():
            display = HP_STAT_DISPLAY.get(stat_str, stat_str)
            is_flat = stat_str in ['main_stat_pct', 'defense', 'max_hp']
            val_str = f"+{total:,.0f}" if is_flat else f"+{total:.1f}%"
            line_summary.append({"Stat": display, "Total": val_str})
        st.dataframe(line_summary, use_container_width=True, hide_index=True)
    else:
        st.info("No ability lines configured")

    st.divider()

    # Passive Stats totals
    st.markdown("### From Passive Stats")
    passive_summary = []
    for stat_type in HeroPowerPassiveStatType:
        stat_key = stat_type.value
        stat_info = HERO_POWER_PASSIVE_STATS.get(stat_type, {})
        per_level = stat_info.get("per_level", 1.0)
        display_name = PASSIVE_STAT_DISPLAY_NAMES.get(stat_type, stat_key)

        level = data.hero_power_passives.get(stat_key, 0)
        value = level * per_level

        if value > 0:
            if stat_type == HeroPowerPassiveStatType.DAMAGE_PERCENT:
                val_str = f"+{value:.1f}%"
            else:
                val_str = f"+{value:,.0f}"
            passive_summary.append({"Stat": display_name, "Total": val_str})

    if passive_summary:
        st.dataframe(passive_summary, use_container_width=True, hide_index=True)
    else:
        st.info("No passive stats leveled")

    st.divider()

    # Combined important stats
    st.markdown("### Key Stats Combined")

    # Damage %
    dmg_lines = line_totals.get('damage', 0)
    dmg_passive = data.hero_power_passives.get('damage_percent', 0) * 0.75
    st.metric("Damage %", f"+{dmg_lines + dmg_passive:.1f}%",
              delta=f"Lines: {dmg_lines:.1f}% + Passive: {dmg_passive:.1f}%")

    col1, col2, col3 = st.columns(3)
    with col1:
        boss_dmg = line_totals.get('boss_damage', 0)
        st.metric("Boss Damage %", f"+{boss_dmg:.1f}%")
    with col2:
        def_pen = line_totals.get('def_pen', 0)
        st.metric("Def Penetration %", f"+{def_pen:.1f}%")
    with col3:
        crit_dmg = line_totals.get('crit_damage', 0)
        st.metric("Crit Damage %", f"+{crit_dmg:.1f}%")

    # Flat stats
    col1, col2 = st.columns(2)
    with col1:
        main_stat_lines = line_totals.get('main_stat_pct', 0)
        main_stat_passive = data.hero_power_passives.get('main_stat', 0) * 27.5
        st.metric("Main Stat (flat)", f"+{main_stat_lines + main_stat_passive:,.0f}")
    with col2:
        atk_passive = data.hero_power_passives.get('attack', 0) * 103.75
        st.metric("Attack (flat)", f"+{atk_passive:,.0f}")

    st.divider()

    # Total config score
    st.markdown("### Config Score by Mode")
    hp_config = build_hero_power_config()

    score_cols = st.columns(3)
    for idx, mode in enumerate(COMBAT_MODES):
        total_score = sum(
            score_hero_power_line_for_mode(line, mode)
            for line in hp_config.lines
            if line.stat_type
        )
        with score_cols[idx]:
            st.metric(
                COMBAT_MODE_DISPLAY[mode],
                f"{total_score:.0f}",
                help="Sum of all line scores for this mode (0-600 max)"
            )
