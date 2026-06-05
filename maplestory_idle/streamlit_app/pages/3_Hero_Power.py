"""
Hero Power Page
Configure hero power rerollable lines, passive stats, level config, and get reroll recommendations.
Now with 10 preset tabs like the original app!
"""
import streamlit as st
import sys
import copy
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for core imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.data_manager import save_user_data
from utils.dps_calculator import (
    aggregate_stats, calculate_dps,
    compute_phase_dps, STAGE_MOB_FRACTION, STAGE_BOSS_FRACTION,
)
from core import ENEMY_DEFENSE_VALUES, get_enemy_defense
from game.hero_power import (
    HeroPowerStatType, HeroPowerTier, HeroPowerPassiveStatType,
    STAT_DISPLAY_NAMES, TIER_COLORS, HERO_POWER_PASSIVE_STATS,
    PASSIVE_STAT_DISPLAY_NAMES, HERO_POWER_STAT_RANGES,
    HERO_POWER_REROLL_COSTS, HeroPowerLine, HeroPowerConfig,
    HeroPowerLevelConfig, score_hero_power_line, get_line_score_category,
    score_hero_power_line_for_mode, analyze_lock_strategy,
    rank_all_possible_lines_by_dps, MODE_STAT_ADJUSTMENTS,
    STAT_DPS_WEIGHTS, TIER_SCORE_MULTIPLIERS,
    calculate_line_dps_value,
    compute_dps_reference_table_for_character,
    compute_best_lines_ranking_for_character,
    analyze_budget,
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

# Number of preset tabs
PRESET_COUNT = 10


def auto_save():
    save_user_data(st.session_state.username, data)


# DPS calculation wrappers (same pattern as other pages)
def get_stats_for_dps() -> Dict[str, Any]:
    """Get aggregated stats dict."""
    return aggregate_stats(data)


def calc_dps_from_stats(stats: Dict[str, Any]) -> float:
    """
    Calculate DPS from stats dict.

    For stage combat mode, returns the PHASE-WEIGHTED score
    (mob_dps * 0.6 + boss_dps * 0.4) so that boss% and normal% damage stats
    are credited by their actual phase-time share, not by raw absolute DPS
    (which is dominated by multi-target mob phase in realistic mode).

    For other modes, returns the raw total.
    """
    # Look up by string key so "World Boss Stage N" works as well as
    # "Chapter N" (the int(chapter_str.replace('Chapter ', '')) pattern used
    # to silently fall back to Chapter 27 for World Boss entries, which made
    # def_pen value-per-point appear unchanged when switching combat target).
    chapter_str = getattr(data, 'chapter', 'Chapter 27')
    enemy_def = ENEMY_DEFENSE_VALUES.get(chapter_str, 0.752)

    from game.job_classes import JobClass
    job_class = JobClass(data.job_class)
    use_realistic = getattr(data, 'use_realistic_dps', False)
    boss_importance = getattr(data, 'boss_importance', 70) / 100.0
    boss_damage_multiplier = getattr(data, 'boss_damage_multiplier', 1.0)
    combat_mode = getattr(data, 'combat_mode', 'stage')

    def _dps_result(s, mode):
        # Return the FULL result dict so compute_phase_dps can read
        # mob_phase_dps / boss_phase_dps directly in realistic mode.
        return calculate_dps(
            s, mode, enemy_def,
            job_class=job_class,
            use_realistic_dps=use_realistic,
            boss_importance=boss_importance,
            boss_damage_multiplier=boss_damage_multiplier,
        )

    if combat_mode == 'stage':
        mob, boss = compute_phase_dps(stats, _dps_result)
        if mob > 0 and boss > 0:
            # Geometric mean of phase DPS, weighted 60/40.
            # Chosen so (new/old - 1) approximates the phase-weighted gain:
            #   ln(new/old) = 0.6*ln(mob_ratio) + 0.4*ln(boss_ratio)
            #              ≈ 0.6*mob_gain + 0.4*boss_gain
            # An additive scalar (mob*0.6 + boss*0.4) would NOT have this
            # property — its ratio is dominated by whichever phase is larger
            # in absolute terms (mob in stage mode for multi-target classes).
            return (mob ** STAGE_MOB_FRACTION) * (boss ** STAGE_BOSS_FRACTION)
        # Fall through if a phase couldn't be computed
    return _dps_result(stats, combat_mode).get('total', 0)


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


def build_hero_power_config(lines_data: dict) -> HeroPowerConfig:
    """Build HeroPowerConfig from lines data."""
    lines = []
    for i in range(1, 7):
        line_key = f'line{i}'
        line_data = lines_data.get(line_key, {})
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


def get_default_lines() -> dict:
    """Get default empty lines for a new preset."""
    return {
        f'line{i}': {'stat': '', 'value': 0.0, 'tier': 'common', 'locked': False}
        for i in range(1, 7)
    }


st.title("Hero Power")

# ============================================================================
# INITIALIZE 10 PRESETS
# ============================================================================

# Initialize all 10 presets if they don't exist
if not data.hero_power_presets:
    data.hero_power_presets = {}

for preset_idx in range(1, PRESET_COUNT + 1):
    preset_name = str(preset_idx)
    if preset_name not in data.hero_power_presets:
        data.hero_power_presets[preset_name] = {'lines': get_default_lines()}

# Ensure active preset is valid
if not data.active_hero_power_preset or data.active_hero_power_preset not in data.hero_power_presets:
    data.active_hero_power_preset = "1"
    auto_save()

# ============================================================================
# PRESET TAB SELECTION
# ============================================================================

st.markdown("### Preset Selection")
st.caption("Click a preset to switch. Each preset saves separately.")

# Create a row of buttons for preset selection
preset_cols = st.columns(PRESET_COUNT)
for idx, col in enumerate(preset_cols):
    preset_name = str(idx + 1)
    is_active = preset_name == data.active_hero_power_preset

    with col:
        button_type = "primary" if is_active else "secondary"
        if st.button(
            f"{preset_name}",
            key=f"preset_btn_{preset_name}",
            type=button_type,
            use_container_width=True
        ):
            if not is_active:
                # Save current preset's lines before switching (deep copy to avoid shared refs)
                data.hero_power_presets[data.active_hero_power_preset] = {
                    'lines': copy.deepcopy(data.hero_power_lines)
                }
                # Switch to new preset, deep copy to keep presets independent
                data.active_hero_power_preset = preset_name
                preset_data = data.hero_power_presets.get(preset_name, {})
                data.hero_power_lines = copy.deepcopy(preset_data.get('lines', get_default_lines()))
                auto_save()
                st.rerun()

# Show current preset indicator
st.info(f"Currently editing **Preset {data.active_hero_power_preset}**")

st.divider()

# ============================================================================
# LOAD CURRENT PRESET DATA
# ============================================================================

# Ensure hero_power_lines has the current preset's data
preset_data = data.hero_power_presets.get(data.active_hero_power_preset, {})
if not data.hero_power_lines or data.hero_power_lines != preset_data.get('lines', {}):
    data.hero_power_lines = copy.deepcopy(preset_data.get('lines', get_default_lines()))

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

# ============================================================================
# MAIN CONTENT TABS
# ============================================================================

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["Ability Lines", "Line Analysis", "Passive Stats", "Level Config", "Summary", "Optimizer", "Preset Comparison"])

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
    # Widget keys include active preset so Streamlit creates fresh widgets on preset switch,
    # preventing stale session state from contaminating the newly loaded preset.
    p = data.active_hero_power_preset
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
                key=f"hp_lock_{i}_{p}",
                help=f"Lock Line {i}"
            )
            if new_locked != line.get('locked'):
                line['locked'] = new_locked
                data.hero_power_presets[data.active_hero_power_preset] = {'lines': copy.deepcopy(data.hero_power_lines)}
                auto_save()

        with col_tier:
            tier_idx = HP_TIERS.index(tier_str) if tier_str in HP_TIERS else 0
            new_tier = st.selectbox(
                f"L{i} Tier",
                options=HP_TIERS,
                index=tier_idx,
                key=f"hp_tier_{i}_{p}",
                format_func=lambda x: HP_TIER_DISPLAY.get(x, x),
                label_visibility="collapsed"
            )
            if new_tier != tier_str:
                line['tier'] = new_tier
                data.hero_power_presets[data.active_hero_power_preset] = {'lines': copy.deepcopy(data.hero_power_lines)}
                auto_save()

        with col_stat:
            stat_idx = HP_STATS.index(stat_str) if stat_str in HP_STATS else 0
            new_stat = st.selectbox(
                f"L{i} Stat",
                options=HP_STATS,
                index=stat_idx,
                key=f"hp_stat_{i}_{p}",
                format_func=lambda x: HP_STAT_DISPLAY.get(x, x),
                label_visibility="collapsed"
            )
            if new_stat != stat_str:
                line['stat'] = new_stat
                data.hero_power_presets[data.active_hero_power_preset] = {'lines': copy.deepcopy(data.hero_power_lines)}
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
                key=f"hp_val_{i}_{p}",
                label_visibility="collapsed"
            )
            if new_value != line.get('value'):
                line['value'] = new_value
                data.hero_power_presets[data.active_hero_power_preset] = {'lines': copy.deepcopy(data.hero_power_lines)}
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
                    score = score_hero_power_line(hp_line, calc_dps_from_stats, get_stats_for_dps)
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

    # Use combat mode from character settings
    analysis_mode = getattr(data, 'combat_mode', 'stage')
    st.info(f"**Optimizing for:** {COMBAT_MODE_DISPLAY.get(analysis_mode, analysis_mode)} (set in Character Settings)")

    # Build current config
    hp_config = build_hero_power_config(data.hero_power_lines)
    level_config = get_level_config()

    # Analyze lock strategy with real DPS callbacks
    analysis = analyze_lock_strategy(hp_config, level_config, calc_dps_from_stats, get_stats_for_dps)

    st.markdown("### Current Lines Analysis")

    # Show each line with its analysis
    analysis_rows = []
    total_dps_contribution = 0.0

    for la in analysis['efficiency_analysis']:
        line = la['line']
        eff = la['efficiency_result']

        # Calculate actual DPS contribution for this line
        dps_value = calculate_line_dps_value(line, calc_dps_from_stats, get_stats_for_dps)
        total_dps_contribution += dps_value

        # Calculate mode-specific score (real DPS)
        mode_score = score_hero_power_line_for_mode(line, analysis_mode, calc_dps_from_stats, get_stats_for_dps)
        category, color = get_line_score_category(mode_score)

        # Recommendation
        rec = eff['recommendation']

        analysis_rows.append({
            "Slot": line.slot,
            "Stat": STAT_DISPLAY_NAMES.get(line.stat_type, line.stat_type.value),
            "Tier": line.tier.value.capitalize(),
            "Value": f"{line.value:.1f}" if line.stat_type not in [HeroPowerStatType.MAIN_STAT_FLAT, HeroPowerStatType.MAX_HP] else f"{line.value:,.0f}",
            "DPS": f"+{dps_value:.2f}%",
            "Category": category,
            "P(Better)": f"{eff['probability_of_improvement']:.1%}",
            "Rec": rec,
        })

    st.dataframe(analysis_rows, use_container_width=True, hide_index=True)

    # Show total DPS from all lines
    st.markdown(f"**Total DPS from Hero Power Lines: +{total_dps_contribution:.2f}%**")

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

    rankings = rank_all_possible_lines_by_dps(calc_dps_from_stats, get_stats_for_dps)
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
    st.markdown("**Passive Stats** - Enter the actual values from your game")
    st.caption("Type the total value you see in-game for each stat")

    # Initialize passive stat VALUES if not present
    if not hasattr(data, 'hero_power_passive_values') or data.hero_power_passive_values is None:
        data.hero_power_passive_values = {}

    col1, col2 = st.columns(2)

    passive_types = list(HeroPowerPassiveStatType)

    for idx, stat_type in enumerate(passive_types):
        stat_key = stat_type.value
        display_name = PASSIVE_STAT_DISPLAY_NAMES.get(stat_type, stat_key)
        current_value = float(data.hero_power_passive_values.get(stat_key, 0))

        with col1 if idx < 3 else col2:
            st.markdown(f"**{display_name}**")

            if stat_type == HeroPowerPassiveStatType.DAMAGE_PERCENT:
                new_value = st.number_input(
                    f"{display_name} value",
                    min_value=0.0,
                    max_value=500.0,
                    value=current_value,
                    step=0.5,
                    format="%.2f",
                    key=f"passive_val_{stat_key}",
                    label_visibility="collapsed"
                )
            else:
                new_value = st.number_input(
                    f"{display_name} value",
                    min_value=0.0,
                    max_value=999999.0,
                    value=current_value,
                    step=100.0,
                    format="%.0f",
                    key=f"passive_val_{stat_key}",
                    label_visibility="collapsed"
                )

            if new_value != current_value:
                data.hero_power_passive_values[stat_key] = new_value
                auto_save()

    st.divider()

    # Passive stats summary
    st.markdown("**Passive Stats Totals**")
    passive_totals = []
    passive_vals = data.hero_power_passive_values if hasattr(data, 'hero_power_passive_values') and data.hero_power_passive_values else {}

    for stat_type in HeroPowerPassiveStatType:
        stat_key = stat_type.value
        display_name = PASSIVE_STAT_DISPLAY_NAMES.get(stat_type, stat_key)
        current_value = passive_vals.get(stat_key, 0)

        if stat_type == HeroPowerPassiveStatType.DAMAGE_PERCENT:
            current_str = f"{current_value:.2f}%"
        else:
            current_str = f"{current_value:,.0f}"

        passive_totals.append({
            "Stat": display_name,
            "Value": current_str,
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
    passive_vals = data.hero_power_passive_values if hasattr(data, 'hero_power_passive_values') and data.hero_power_passive_values else {}

    for stat_type in HeroPowerPassiveStatType:
        stat_key = stat_type.value
        display_name = PASSIVE_STAT_DISPLAY_NAMES.get(stat_type, stat_key)
        value = passive_vals.get(stat_key, 0)

        if value > 0:
            if stat_type == HeroPowerPassiveStatType.DAMAGE_PERCENT:
                val_str = f"+{value:.2f}%"
            else:
                val_str = f"+{value:,.0f}"
            passive_summary.append({"Stat": display_name, "Total": val_str})

    if passive_summary:
        st.dataframe(passive_summary, use_container_width=True, hide_index=True)
    else:
        st.info("No passive stats configured")

    st.divider()

    # Combined important stats
    st.markdown("### Key Stats Combined")

    # Get passive values directly
    passive_vals = data.hero_power_passive_values if hasattr(data, 'hero_power_passive_values') and data.hero_power_passive_values else {}
    dmg_passive = passive_vals.get('damage_percent', 0)
    main_stat_passive = passive_vals.get('main_stat', 0)
    atk_passive = passive_vals.get('attack', 0)

    # Damage %
    dmg_lines = line_totals.get('damage', 0)
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
        main_stat_lines = line_totals.get('main_stat_flat', 0)
        st.metric("Main Stat (flat)", f"+{main_stat_lines + main_stat_passive:,.0f}")
    with col2:
        st.metric("Attack (flat)", f"+{atk_passive:,.0f}")

    st.divider()

    # Total config score
    st.markdown("### Config Score by Mode")
    hp_config = build_hero_power_config(data.hero_power_lines)

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

# ============================================================================
# TAB 6: OPTIMIZER - DPS-based optimization with strategies
# ============================================================================
with tab6:
    st.markdown("**Hero Power Optimizer** — budget-driven")
    st.caption(
        "Enter your medal budget. The optimizer picks a lock pattern that "
        "maximizes expected DPS gain within that budget. Aggressive at low "
        "lock counts (cheap rerolls), lenient as locks add up (rerolls get expensive)."
    )

    hp_config = build_hero_power_config(data.hero_power_lines)
    level_config = get_level_config()
    base_cost = level_config.base_cost

    col_b, col_help = st.columns([1, 2])
    with col_b:
        budget_medals = st.number_input(
            "Budget (medals)",
            min_value=0, max_value=1_000_000_000, value=100_000, step=1_000,
            key="hp_budget_medals",
            help=f"Cost per reroll: {base_cost} + 43 × (lines locked).",
        )

    with st.spinner("Computing optimal lock recommendation..."):
        budget_result = analyze_budget(
            hp_config, level_config, budget_medals,
            calc_dps_from_stats, get_stats_for_dps,
        )

    if budget_result.get('error'):
        st.warning(f"Cannot run analysis: {budget_result['error']}")
    else:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            locks = budget_result['recommended_locks']
            st.metric(
                "Lock these",
                ", ".join(str(s) for s in locks) if locks else "None",
            )
        with col2:
            st.metric("Cost / reroll", f"{budget_result['cost_per_reroll']:,}")
        with col3:
            st.metric("Rerolls in budget", f"{budget_result['expected_rerolls']:,}")
        with col4:
            gain = budget_result['expected_gain_pct']
            st.metric(
                "Expected DPS gain",
                f"+{gain:.2f}%",
                delta=f"from current +{budget_result['current_total_dps_pct']:.2f}%",
            )

        st.markdown("### Lock-threshold cascade")
        st.caption(
            "Be picky at 0 locks (high threshold) and progressively lenient as "
            "locks accumulate — because each lock raises the per-reroll cost, "
            "shrinking the remaining budget."
        )
        cascade_rows = []
        for c in budget_result['cascade']:
            cascade_rows.append({
                "Locks held": c['locks_held'],
                "Cost / reroll": f"{c['cost_per_reroll']:,}",
                "Rerolls left in budget": f"{c['rerolls_in_budget']:,}",
                "Lock next line if DPS >=": f"{c['reservation_dps_pct']:.2f}%",
            })
        st.dataframe(cascade_rows, use_container_width=True, hide_index=True)

        st.markdown("### Per-line recommendations")
        analysis_rows = []
        for la in budget_result['line_analysis']:
            val_str = (
                f"{la['value']:,.0f}"
                if la['value'] >= 1000
                else f"{la['value']:.1f}"
            )
            stop = (
                f"{la['stop_value_pct']:.2f}%"
                if la['stop_value_pct'] is not None
                else "—"
            )
            analysis_rows.append({
                "Slot": la['slot'],
                "Stat": la['stat'],
                "Tier": la['tier'],
                "Value": val_str,
                "Current DPS": f"+{la['current_dps_pct']:.2f}%",
                "Action": la['recommendation'],
                "Stop at": stop,
                "Reason": la['reasoning'],
            })
        st.dataframe(analysis_rows, use_container_width=True, hide_index=True)

    st.divider()

    # DPS Reference Tables — computed live from the user's current stats
    st.markdown("### DPS Reference by Tier")
    st.caption(f"Real DPS gain for each tier/stat/value combination against your current build (combat mode: {COMBAT_MODE_DISPLAY.get(getattr(data, 'combat_mode', 'stage'), 'Stage')}).")

    # Build the computed table once (used by both the per-tier display and the ranking)
    computed_ref = compute_dps_reference_table_for_character(calc_dps_from_stats, get_stats_for_dps)

    tier_tabs = st.tabs(["Rare", "Epic", "Unique", "Legendary", "Mystic"])
    tier_order = ['rare', 'epic', 'unique', 'legendary', 'mystic']
    for tier_idx, tier_name in enumerate(tier_order):
        with tier_tabs[tier_idx]:
            tier_data = computed_ref.get(tier_name, [])
            if tier_data:
                ref_rows = []
                for entry in tier_data:
                    is_flat = entry['high'] > 1000  # Flat stats: Main Stat, Max HP
                    if is_flat:
                        low_val = f"{entry['low']:,.0f}"
                        mid_val = f"{entry['mid']:,.0f}"
                        high_val = f"{entry['high']:,.0f}"
                    else:
                        low_val = f"{entry['low']:.1f}%"
                        mid_val = f"{entry['mid']:.1f}%"
                        high_val = f"{entry['high']:.1f}%"

                    ref_rows.append({
                        "Stat": entry['stat'],
                        "Low": low_val,
                        "Mid": mid_val,
                        "High": high_val,
                        "DPS (Low)": f"+{entry['dps_low']:.2f}%" if entry['dps_low'] > 0 else "0%",
                        "DPS (Mid)": f"+{entry['dps_mid']:.2f}%" if entry['dps_mid'] > 0 else "0%",
                        "DPS (High)": f"+{entry['dps_high']:.2f}%" if entry['dps_high'] > 0 else "0%",
                        "Note": entry.get('note', ''),
                    })
                st.dataframe(ref_rows, use_container_width=True, hide_index=True)
            else:
                st.info(f"No data for {tier_name} tier")

    st.divider()

    # Best Lines Ranking — computed for the user
    st.markdown("### Best Lines Ranked by Max DPS Gain")
    st.caption("Top 10 most valuable lines to aim for when rerolling, ranked by real DPS gain against your build. Probability uses your hero power level config.")

    computed_ranking = compute_best_lines_ranking_for_character(
        calc_dps_from_stats, get_stats_for_dps, level_config, top_n=10,
    )
    ranking_rows = []
    for entry in computed_ranking:
        ranking_rows.append({
            "Rank": entry['rank'],
            "Tier": entry['tier'],
            "Stat": entry['stat'],
            "Max Value": entry['max_value'],
            "Max DPS": f"+{entry['max_dps']:.2f}%",
            "Probability": entry['probability'],
        })
    st.dataframe(ranking_rows, use_container_width=True, hide_index=True)

# ============================================================================
# TAB 7: PRESET COMPARISON - Actual DPS for all 10 presets, ranked
# ============================================================================
with tab7:
    st.markdown("**Preset Comparison**")
    st.caption(f"Real DPS for each preset against your current stats (combat mode: {COMBAT_MODE_DISPLAY.get(getattr(data, 'combat_mode', 'stage'), 'Stage')}).")

    original_active = data.active_hero_power_preset
    comparison_rows = []
    try:
        for preset_id in range(1, PRESET_COUNT + 1):
            preset_name = str(preset_id)
            preset_info = data.hero_power_presets.get(preset_name, {})
            preset_lines = preset_info.get('lines', {})

            # Temporarily activate this preset so aggregate_stats picks it up
            data.active_hero_power_preset = preset_name
            stats = aggregate_stats(data)
            preset_dps = calc_dps_from_stats(stats)

            # Count configured lines
            configured = sum(1 for ln in preset_lines.values() if ln.get('stat', ''))
            locked = sum(1 for ln in preset_lines.values() if ln.get('locked', False))

            comparison_rows.append({
                'preset': preset_name,
                'is_active': preset_name == original_active,
                'dps': preset_dps,
                'configured_lines': configured,
                'locked_lines': locked,
            })
    finally:
        # Always restore the original active preset, even if a calc raises
        data.active_hero_power_preset = original_active

    # Find the best preset for delta calculation
    best_dps = max((r['dps'] for r in comparison_rows), default=0)
    active_dps = next((r['dps'] for r in comparison_rows if r['is_active']), 0)

    # Build display rows ranked by DPS
    display_rows = []
    for r in sorted(comparison_rows, key=lambda x: x['dps'], reverse=True):
        delta_vs_best = (r['dps'] / best_dps - 1) * 100 if best_dps > 0 else 0
        delta_vs_active = (r['dps'] / active_dps - 1) * 100 if active_dps > 0 else 0
        display_rows.append({
            "Preset": ("* " if r['is_active'] else "") + r['preset'],
            "DPS": f"{r['dps']:,.0f}",
            "vs Best": f"{delta_vs_best:+.2f}%" if delta_vs_best != 0 else "-- (best)",
            "vs Active": f"{delta_vs_active:+.2f}%" if not r['is_active'] else "-- (active)",
            "Lines": f"{r['configured_lines']}/6",
            "Locked": r['locked_lines'],
        })

    st.dataframe(display_rows, use_container_width=True, hide_index=True)
    st.caption("* = currently active preset. DPS uses your character's current stats with each preset's hero power lines applied.")

    # Quick summary
    if comparison_rows:
        best = max(comparison_rows, key=lambda x: x['dps'])
        if best['preset'] != original_active and best_dps > active_dps:
            gain_pct = (best_dps / active_dps - 1) * 100 if active_dps > 0 else 0
            st.success(f"Preset **{best['preset']}** is the best — switching from preset {original_active} would gain **{gain_pct:+.2f}%** DPS.")
        elif best['preset'] == original_active:
            st.info(f"Preset **{original_active}** is already your best.")
