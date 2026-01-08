"""
Upgrade Path Optimizer Page
Comprehensive upgrade recommendations with detailed DPS analysis and specific targets.
Includes optimal stat distribution analysis with marginal value optimization.

Uses core/ module for all damage calculations - single source of truth.
All DPS calculations use the same method as the original Tkinter app:
- Calculate baseline DPS with current stats
- Calculate DPS with modified stats
- Compare the difference

Key principle: Calculate REAL DPS gains by actually running damage formulas,
not arbitrary weights or estimates.
"""
import streamlit as st
from typing import Dict, List, Any, Optional, Tuple
import sys
import os
from pathlib import Path
import copy
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core import (
    calculate_damage,
    calculate_total_dex,
    calculate_final_damage_mult,
    calculate_defense_pen,
    calculate_attack_speed,
    calculate_effective_crit_multiplier,
    BASE_CRIT_DMG,
    BASE_MIN_DMG,
    BASE_MAX_DMG,
    EQUIPMENT_SLOTS,
    ENEMY_DEFENSE_VALUES,
    get_enemy_defense,
)
from utils.data_manager import save_user_data
from utils.cube_analyzer import (
    analyze_all_cube_priorities, CubeRecommendation,
    format_stat_display, REGULAR_DIAMOND_PER_CUBE, BONUS_DIAMOND_PER_CUBE,
    get_distribution_data_for_slot,
    analyze_all_tier_upgrades, TierUpgradeRecommendation,
)
from utils.distribution_chart import create_dps_distribution_chart, get_percentile_label, get_percentile_color
from optimal_stats import (
    calculate_slot_efficiency, calculate_source_ranking, calculate_optimal_distribution,
    get_optimal_stat_for_slot, format_stat_name, SLOT_EXCLUSIVE_STATS,
    EQUIPMENT_SLOTS as OPTIMAL_EQUIPMENT_SLOTS, HERO_POWER_VALUES, ARTIFACT_POTENTIAL_VALUES
)
from starforce_optimizer import (
    calculate_total_cost_markov,
    find_optimal_per_stage_strategy,
    MESO_TO_DIAMOND as SF_MESO_TO_DIAMOND,
    SCROLL_DIAMOND_COST as SF_SCROLL_COST,
)
from equipment import STARFORCE_TABLE, get_amplify_multiplier
from weapon_optimizer import get_weapon_upgrade_for_optimizer, calculate_total_weapon_atk_percent
from weapon_summoning import get_summon_recommendations_for_optimizer
from utils.dps_calculator import (
    aggregate_stats as shared_aggregate_stats,
    calculate_dps as shared_calculate_dps,
    get_all_skills_dps_value,
    calculate_ba_percent_of_dps,
    calculate_skill_cd_dps_value,
    calculate_buff_duration_dps_value,
    get_combat_mode_enum,
    calculate_crit_rate_dps_value,
    BASE_MIN_DMG,
    BASE_MAX_DMG,
)


# =============================================================================
# Wrapper functions for shared DPS calculator (uses user data from session)
# =============================================================================
def aggregate_stats(star_overrides: Dict[str, int] = None) -> Dict[str, Any]:
    """Wrapper that calls shared aggregate_stats with user data."""
    return shared_aggregate_stats(data, star_overrides)


def calculate_dps(stats: Dict[str, Any], combat_mode: str = 'stage', enemy_def: float = None, book_of_ancient_stars: int = None) -> Dict[str, Any]:
    """Wrapper that calls shared calculate_dps with correct enemy defense for combat mode."""
    # Determine enemy defense based on combat mode if not explicitly provided
    if enemy_def is None:
        if combat_mode == 'world_boss':
            enemy_def = ENEMY_DEFENSE_VALUES.get('World Boss', 6.527)
        else:
            # Get chapter number from user data (e.g., "Chapter 27" -> 27)
            chapter_str = getattr(data, 'chapter', 'Chapter 27')
            try:
                chapter_num = int(chapter_str.replace('Chapter ', '').strip())
            except (ValueError, AttributeError):
                chapter_num = 27  # Default fallback
            enemy_def = get_enemy_defense(chapter_num)
    # book_of_ancient_stars=None means use value from stats (from user's artifact inventory)
    return shared_calculate_dps(stats, combat_mode, enemy_def, book_of_ancient_stars)


st.set_page_config(page_title="Upgrade Optimizer", page_icon="📈", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

# ==============================================================================
# Constants (imported from core, plus optimizer-specific ones)
# ==============================================================================

# Starforce data: (success_rate, destroy_rate, meso_cost)
STARFORCE_DATA = {
    12: (0.54, 0.00, 180000),
    13: (0.32, 0.00, 230000),
    14: (0.31, 0.00, 250000),
    15: (0.30, 0.03, 270000),
    16: (0.28, 0.04, 300000),
    17: (0.26, 0.05, 330000),
    18: (0.23, 0.06, 360000),
    19: (0.20, 0.09, 390000),
    20: (0.14, 0.11, 420000),
    21: (0.11, 0.10, 450000),
    22: (0.08, 0.10, 530000),
    23: (0.06, 0.10, 570000),
    24: (0.04, 0.10, 620000),
}

STARFORCE_SUB_AMPLIFY = {
    0: 0, 5: 0.05, 10: 0.10, 12: 0.15, 13: 0.20, 14: 0.25,
    15: 0.35, 16: 0.45, 17: 0.55, 18: 0.70, 19: 0.85, 20: 1.00,
    21: 1.10, 22: 1.35, 23: 1.65, 24: 2.00, 25: 2.50
}

MESO_TO_DIAMOND = 0.004
SCROLL_COST = 300
DESTRUCTION_FEE = 4000
MEDAL_TO_DIAMOND = 10

# DPS weights for stats
STAT_DPS_WEIGHTS = {
    'damage': 1.5,
    'boss_damage': 2.0,
    'normal_damage': 1.0,
    'crit_damage': 1.8,
    'def_pen': 2.2,
    'final_damage': 2.5,
    'dex_pct': 1.2,
    'str_pct': 1.2,
    'int_pct': 1.2,
    'luk_pct': 1.2,
    'attack_pct': 1.5,
    'crit_rate': 1.5,
    'min_dmg_mult': 0.8,
    'max_dmg_mult': 0.8,
    'all_skills': 1.0,
}

# Best stats to target by slot
SLOT_TARGET_STATS = {
    'hat': ['damage', 'boss_damage', 'skill_cd', 'dex_pct'],
    'top': ['final_damage', 'damage', 'dex_pct', 'ba_targets'],
    'bottom': ['final_damage', 'damage', 'dex_pct'],
    'gloves': ['crit_damage', 'damage', 'dex_pct'],
    'shoes': ['damage', 'min_dmg_mult', 'dex_pct'],
    'belt': ['damage', 'boss_damage', 'dex_pct'],
    'shoulder': ['def_pen', 'final_damage', 'damage'],
    'cape': ['final_damage', 'damage', 'dex_pct'],
    'ring': ['all_skills', 'damage', 'boss_damage'],
    'necklace': ['all_skills', 'damage', 'boss_damage'],
    'face': ['damage', 'boss_damage', 'dex_pct'],
}


# NOTE: aggregate_stats() and calculate_dps() are now imported from utils/dps_calculator.py
# The wrapper functions at the top of this file (lines 73-80) call the shared module.


# ==============================================================================
# Detailed Upgrade Analysis
# ==============================================================================

def get_potential_lines_summary(slot: str, is_bonus: bool = False) -> Dict:
    """Get summary of current potential lines for a slot."""
    pots = data.equipment_potentials.get(slot, {})
    prefix = 'bonus_' if is_bonus else ''
    tier = pots.get(f'{prefix}tier', 'Rare')
    pity = pots.get(f'{prefix}pity', 0)

    lines = []
    total_dps = 0
    for i in range(1, 4):
        stat = pots.get(f'{prefix}line{i}_stat', '')
        value = float(pots.get(f'{prefix}line{i}_value', 0))
        is_yellow = pots.get(f'{prefix}line{i}_yellow', False)
        is_special = pots.get(f'{prefix}line{i}_special', False)

        if stat:
            weight = STAT_DPS_WEIGHTS.get(stat, 0.5)
            dps_contrib = value * weight * 0.01
            total_dps += dps_contrib

            # Format line
            stat_display = format_stat_display(stat)
            yellow_tag = "[Y]" if is_yellow else "[G]"
            special_tag = "*" if is_special else ""
            lines.append({
                'stat': stat,
                'stat_display': stat_display,
                'value': value,
                'dps': dps_contrib,
                'is_yellow': is_yellow,
                'is_special': is_special,
                'formatted': f"{yellow_tag}{special_tag} {stat_display}: {value:.1f}%"
            })
        else:
            lines.append({
                'stat': '',
                'stat_display': '(empty)',
                'value': 0,
                'dps': 0,
                'is_yellow': False,
                'is_special': False,
                'formatted': "(empty)"
            })

    return {
        'tier': tier,
        'pity': pity,
        'lines': lines,
        'total_dps': total_dps,
    }


def calculate_best_possible_dps(slot: str, tier: str) -> float:
    """Calculate the best possible DPS from perfect 3-line roll at given tier."""
    # Best stats for the slot
    target_stats = SLOT_TARGET_STATS.get(slot, ['damage', 'boss_damage', 'dex_pct'])

    # Tier values (mystic > legendary > unique)
    tier_multipliers = {
        'Mystic': 1.5,
        'Legendary': 1.2,
        'Unique': 1.0,
        'Epic': 0.75,
        'Rare': 0.5,
    }
    tier_mult = tier_multipliers.get(tier, 0.5)

    # Calculate best possible
    best_dps = 0
    for stat in target_stats[:3]:
        weight = STAT_DPS_WEIGHTS.get(stat, 0.5)
        # Approximate best values by tier
        best_value = 25 * tier_mult  # e.g., 30% damage at Legendary
        best_dps += best_value * weight * 0.01

    return best_dps


# NOTE: Custom cube analysis functions moved to utils/unused_optimizer_functions.py
# Now using analyze_all_cube_priorities from cube_analyzer.py (same as Tkinter app)


def analyze_starforce_detailed(baseline_dps: float) -> List[Dict]:
    """
    Analyze starforce upgrades for each equipment slot.

    Evaluates EACH star level (not just milestones) to find the most efficient
    next upgrade. This properly accounts for diminishing returns where going
    17→18 is much cheaper than 19→20 for similar DPS gain.

    Uses:
    - Markov chain analysis from starforce_optimizer for accurate cost estimates
    - Actual DPS calculations to determine real gain from stat amplification

    Args:
        baseline_dps: The current total DPS (calculated once and passed in)
    """
    results = []

    for slot in EQUIPMENT_SLOTS:
        item = data.equipment_items.get(slot, {})
        current_stars = int(item.get('stars', 0))

        if current_stars >= 25 or current_stars < 10:
            continue

        # Evaluate EACH possible target star (not just milestones)
        # This finds the most efficient next step
        best_upgrade = None
        best_efficiency = -1

        # Consider each star from current+1 to 25
        for target_stars in range(current_stars + 1, 26):
            if target_stars <= current_stars:
                continue

            # Use Markov chain analysis for accurate cost estimate
            # This calculates the full path cost (e.g., 19→22 includes 19→20→21→22)
            stage_strategies, markov_result = find_optimal_per_stage_strategy(current_stars, target_stars)

            # Total cost in diamonds from Markov analysis
            total_cost = markov_result.total_cost
            destroy_prob = markov_result.destroy_probability

            # Calculate REAL DPS gain by comparing baseline vs upgraded
            upgraded_stats = aggregate_stats(star_overrides={slot: target_stars})
            upgraded_dps_result = calculate_dps(upgraded_stats, data.combat_mode)
            upgraded_dps = upgraded_dps_result['total']

            # Calculate actual DPS gain percentage
            if baseline_dps > 0:
                dps_gain = ((upgraded_dps / baseline_dps) - 1) * 100
            else:
                dps_gain = 0

            # Calculate efficiency: DPS% gain per 1000 diamonds (same formula as cube efficiency)
            # efficiency = dps_gain / (total_cost / 1000) = dps_gain * 1000 / total_cost
            efficiency = dps_gain / (total_cost / 1000) if total_cost > 0 else 0

            # Track best option based on efficiency
            if efficiency > best_efficiency:
                best_efficiency = efficiency

                # Get amplify multipliers for display
                current_amp = get_amplify_multiplier(current_stars, is_sub=True)
                target_amp = get_amplify_multiplier(target_stars, is_sub=True)

                # Risk level based on destruction probability
                if destroy_prob <= 0:
                    risk = "Safe"
                    risk_color = "🟢"
                elif destroy_prob < 0.05:
                    risk = f"Low ({destroy_prob*100:.0f}%)"
                    risk_color = "🟡"
                elif destroy_prob < 0.15:
                    risk = f"Medium ({destroy_prob*100:.0f}%)"
                    risk_color = "🟠"
                elif destroy_prob < 0.30:
                    risk = f"High ({destroy_prob*100:.0f}%)"
                    risk_color = "🔴"
                else:
                    risk = f"Very High ({destroy_prob*100:.0f}%)"
                    risk_color = "🔴"

                # Get the actual sub-stats being amplified for display
                sub_stats_detail = []
                if item.get('sub_boss_damage', 0) > 0:
                    sub_stats_detail.append(f"Boss {item['sub_boss_damage']:.1f}%")
                if item.get('sub_crit_damage', 0) > 0:
                    sub_stats_detail.append(f"CD {item['sub_crit_damage']:.1f}%")
                if item.get('sub_crit_rate', 0) > 0:
                    sub_stats_detail.append(f"CR {item['sub_crit_rate']:.1f}%")
                if item.get('sub_attack_flat', 0) > 0:
                    sub_stats_detail.append(f"ATK {item['sub_attack_flat']:.0f}")
                if item.get('is_special', False) and item.get('special_stat_value', 0) > 0:
                    special_type = item.get('special_stat_type', 'damage_pct')
                    special_name = {'damage_pct': 'Dmg%', 'final_damage': 'FD%', 'all_skills': 'AllSkill'}.get(special_type, special_type)
                    sub_stats_detail.append(f"{special_name} {item['special_stat_value']:.1f}")

                # Get optimal strategy for display (uses the first stage's strategy)
                optimal_strat = stage_strategies.get(current_stars, 'none')

                # Estimate expected attempts (rough estimate for display)
                sf_data = STARFORCE_TABLE.get(current_stars)
                if sf_data:
                    success_rate = sf_data.success_rate
                    expected_attempts = 1 / success_rate if success_rate > 0 else 100
                else:
                    expected_attempts = 2

                best_upgrade = {
                    'slot': slot,
                    'current_stars': current_stars,
                    'target_stars': target_stars,
                    'total_cost': total_cost,
                    'expected_attempts': expected_attempts,
                    'destroy_prob': destroy_prob,
                    'optimal_strategy': optimal_strat,
                    'dps_gain': dps_gain,
                    'efficiency': efficiency,
                    'risk': risk,
                    'risk_color': risk_color,
                    'amp_before': current_amp,
                    'amp_after': target_amp,
                    'baseline_dps': baseline_dps,
                    'upgraded_dps': upgraded_dps,
                    'sub_stats_detail': sub_stats_detail,
                }

        # Only add the best upgrade for this slot
        if best_upgrade:
            results.append(best_upgrade)

    results.sort(key=lambda x: x['efficiency'], reverse=True)
    return results


def analyze_hero_power_detailed() -> Dict:
    """Analyze hero power lines with detailed recommendations."""
    lines = data.hero_power_lines
    preset = data.active_hero_power_preset or "1"

    good_stats = {'damage', 'boss_damage', 'crit_damage', 'def_pen'}
    great_tiers = {'Mystic', 'Legendary'}

    line_analysis = []
    total_dps = 0
    lines_to_lock = []
    lines_to_reroll = []

    for i in range(1, 7):
        line = lines.get(f'line{i}', {})
        stat = line.get('stat', '')
        value = float(line.get('value', 0))
        tier = line.get('tier', 'Common')
        locked = line.get('locked', False)

        # Calculate DPS contribution
        weight = STAT_DPS_WEIGHTS.get(stat, 0.2)
        dps = value * weight * 0.5  # Hero power weight

        # Tier multiplier
        tier_mult = {'Mystic': 1.5, 'Legendary': 1.2, 'Unique': 1.0, 'Epic': 0.8, 'Rare': 0.6, 'Common': 0.4}.get(tier, 0.5)

        # Calculate score (0-100)
        is_good_stat = stat in good_stats
        is_great_tier = tier in great_tiers

        if is_good_stat and is_great_tier:
            score = 80 + (value * 0.5)
            recommendation = "LOCK"
            indicator = "🟢"
            lines_to_lock.append(i)
        elif is_good_stat:
            score = 50 + (value * 0.5)
            recommendation = "LOCK"
            indicator = "🟡"
            lines_to_lock.append(i)
        elif is_great_tier:
            score = 40 + (value * 0.3)
            recommendation = "CONSIDER"
            indicator = "🟡"
        else:
            score = 10 + (value * 0.2)
            recommendation = "REROLL"
            indicator = "🔴"
            lines_to_reroll.append(i)

        total_dps += dps

        stat_display = format_stat_display(stat) if stat else "(empty)"
        line_analysis.append({
            'line': i,
            'stat': stat,
            'stat_display': stat_display,
            'value': value,
            'tier': tier,
            'dps': dps,
            'score': min(100, score),
            'recommendation': recommendation,
            'indicator': indicator,
            'locked': locked,
        })

    # Calculate reroll cost
    num_locks = len(lines_to_lock)
    hp_level = data.hero_power_level or {}
    base_cost = hp_level.get('base_cost', 89)
    cost_per_reroll = base_cost + (num_locks * 43)

    # Expected improvement
    avg_weak_score = sum(l['score'] for l in line_analysis if l['recommendation'] == 'REROLL') / max(1, len(lines_to_reroll))
    expected_gain = (50 - avg_weak_score) * 0.02 * len(lines_to_reroll)  # Rough estimate

    # Estimated rerolls
    if lines_to_reroll:
        estimated_rerolls = 50 + (avg_weak_score * 2)  # More rerolls if already decent
    else:
        estimated_rerolls = 0

    total_medal_cost = estimated_rerolls * cost_per_reroll
    diamond_equivalent = total_medal_cost * MEDAL_TO_DIAMOND

    return {
        'preset': preset,
        'lines': line_analysis,
        'total_dps': total_dps,
        'lines_to_lock': lines_to_lock,
        'lines_to_reroll': lines_to_reroll,
        'num_locks': num_locks,
        'cost_per_reroll': cost_per_reroll,
        'estimated_rerolls': estimated_rerolls,
        'total_medal_cost': total_medal_cost,
        'diamond_equivalent': diamond_equivalent,
        'expected_gain': expected_gain,
    }


# ==============================================================================
# Main Page
# ==============================================================================
st.title("📈 Upgrade Path Optimizer")
st.markdown("Detailed upgrade recommendations with specific targets and DPS impact analysis.")

# Current DPS display
current_stats = aggregate_stats()
current_dps = calculate_dps(current_stats, data.combat_mode)['total']

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Current DPS", f"{current_dps:,.0f}")
with col2:
    st.metric("Combat Mode", data.combat_mode.title())
with col3:
    budget = st.number_input("Diamond Budget", min_value=0, max_value=10000000, value=100000, step=10000)
with col4:
    summoning_level = st.number_input(
        "Summoning Level",
        min_value=1,
        max_value=17,
        value=getattr(data, 'summoning_level', 15),
        help="Your weapon summoning level (affects drop rates)"
    )
    # Save to user data if changed
    if summoning_level != getattr(data, 'summoning_level', 15):
        data.summoning_level = summoning_level
        save_user_data(data.username, data)

# Warning if DPS is too low for meaningful analysis
if current_dps < 10000:
    st.warning("""
    ⚠️ **Low DPS Warning**: Your calculated DPS is very low ({:,.0f}).

    This usually means your character stats aren't fully configured. Please ensure you have:
    - Base Attack values set in **Equipment Stats**
    - Main stats (DEX/STR/etc.) configured
    - Weapon stats set in **Weapons** page

    The upgrade recommendations below may not be accurate until your stats are properly configured.
    """.format(current_dps))

st.divider()

# ==============================================================================
# Run all analyses (used for overall recommendations)
# ==============================================================================

# Add refresh button for manual re-analysis
refresh_col1, refresh_col2 = st.columns([1, 4])
with refresh_col1:
    refresh_clicked = st.button("🔄 Refresh Analysis", help="Re-run all upgrade analyses with latest data")

# Run analysis on first load or when refresh is clicked
if refresh_clicked or 'optimizer_analysis_time' not in st.session_state:
    # Cube analysis using original Tkinter app system
    cube_analysis = analyze_all_cube_priorities(
        user_data=data,
        aggregate_stats_func=aggregate_stats,
        calculate_dps_func=calculate_dps,
    )

    # Starforce analysis
    sf_analysis = analyze_starforce_detailed(current_dps)

    # Hero power analysis
    hp_analysis = analyze_hero_power_detailed()

    # Tier upgrade analysis
    tier_upgrade_analysis = analyze_all_tier_upgrades(
        user_data=data,
        aggregate_stats_func=aggregate_stats,
        calculate_dps_func=calculate_dps,
    )

    # Weapon upgrade analysis
    weapons_data = getattr(data, 'weapons_data', {}) or {}
    equipped_weapon = getattr(data, 'equipped_weapon_key', '') or ''
    if weapons_data:
        weapon_analysis = get_weapon_upgrade_for_optimizer(weapons_data, equipped_weapon)
    else:
        weapon_analysis = []

    # Weapon summon analysis
    if weapons_data:
        # Calculate current total weapon ATK% for diminishing returns
        current_weapon_atk = calculate_total_weapon_atk_percent(weapons_data, equipped_weapon)
        summon_analysis = get_summon_recommendations_for_optimizer(
            weapons_data,
            equipped_weapon,
            summoning_level,
            current_weapon_atk,
        )
    else:
        summon_analysis = []

    # Cache results in session state
    st.session_state.optimizer_cube_analysis = cube_analysis
    st.session_state.optimizer_sf_analysis = sf_analysis
    st.session_state.optimizer_hp_analysis = hp_analysis
    st.session_state.optimizer_tier_upgrade_analysis = tier_upgrade_analysis
    st.session_state.optimizer_weapon_analysis = weapon_analysis
    st.session_state.optimizer_summon_analysis = summon_analysis
    st.session_state.optimizer_analysis_time = datetime.now()

    if refresh_clicked:
        st.success(f"Analysis refreshed! Found {len(cube_analysis or [])} cube, {len(tier_upgrade_analysis or [])} tier-up, {len(weapon_analysis)} weapon, {len(summon_analysis)} summon recommendations.")
else:
    # Use cached results
    cube_analysis = st.session_state.get('optimizer_cube_analysis', [])
    sf_analysis = st.session_state.get('optimizer_sf_analysis', [])
    hp_analysis = st.session_state.get('optimizer_hp_analysis', {})
    tier_upgrade_analysis = st.session_state.get('optimizer_tier_upgrade_analysis', [])
    weapon_analysis = st.session_state.get('optimizer_weapon_analysis', [])
    summon_analysis = st.session_state.get('optimizer_summon_analysis', [])

# Show when analysis was last run
with refresh_col2:
    if 'optimizer_analysis_time' in st.session_state:
        analysis_time = st.session_state.optimizer_analysis_time
        st.caption(f"Last analyzed: {analysis_time.strftime('%H:%M:%S')}")

# ==============================================================================
# DEBUG: Cube Analysis Raw Values
# ==============================================================================
with st.expander("🔧 DEBUG: Raw Cube Analysis Data (for troubleshooting)"):
    st.write(f"**Overall Current DPS:** {current_dps:,.0f}")
    st.write(f"**Number of cube analyses:** {len(cube_analysis) if cube_analysis else 0}")

    # Show what potentials are configured for first slot
    first_slot = EQUIPMENT_SLOTS[0]
    first_pots = data.equipment_potentials.get(first_slot, {})
    st.write(f"---")
    st.write(f"**Sample: {first_slot} potential data:**")
    st.write(f"- Tier: {first_pots.get('tier', 'N/A')}")
    st.write(f"- Line1: {first_pots.get('line1_stat', 'empty')} = {first_pots.get('line1_value', 0)}")
    st.write(f"- Line2: {first_pots.get('line2_stat', 'empty')} = {first_pots.get('line2_value', 0)}")
    st.write(f"- Line3: {first_pots.get('line3_stat', 'empty')} = {first_pots.get('line3_value', 0)}")
    st.write(f"- Bonus Tier: {first_pots.get('bonus_tier', 'N/A')}")
    st.write(f"- Bonus Line1: {first_pots.get('bonus_line1_stat', 'empty')} = {first_pots.get('bonus_line1_value', 0)}")

    if cube_analysis:
        debug_data = []
        for i, rec in enumerate(cube_analysis[:10]):  # Show first 10
            debug_data.append({
                "Slot": rec.slot,
                "Type": "Bonus" if rec.is_bonus else "Regular",
                "Tier": rec.tier,
                "Baseline DPS": f"{rec.baseline_dps:,.0f}",
                "Current DPS Gain%": f"{rec.current_dps_gain:.2f}%",
                "Best Possible%": f"{rec.best_possible_dps_gain:.2f}%",
                "DPS Efficiency": f"{rec.dps_efficiency:.1f}%",
                "Exp. Cubes": f"{rec.expected_cubes_to_improve:.1f}",
                "Efficiency Score": f"{rec.efficiency_score:.4f}",
                "L1 Stat": rec.line1_stat or "(empty)",
                "L1 Value": f"{rec.line1_value:.1f}",
            })
        st.dataframe(debug_data, use_container_width=True)

        # Show a specific example in detail
        if cube_analysis:
            first = cube_analysis[0]
            st.write("---")
            st.write("**First recommendation details:**")
            st.write(f"- Slot: {first.slot} ({'Bonus' if first.is_bonus else 'Regular'})")
            st.write(f"- **Baseline DPS (for this slot):** {first.baseline_dps:,.0f}")
            st.write(f"- Current lines: L1={first.line1_stat}:{first.line1_value}, L2={first.line2_stat}:{first.line2_value}, L3={first.line3_stat}:{first.line3_value}")
            st.write(f"- Current DPS gain: {first.current_dps_gain:.2f}%")
            st.write(f"- Best possible DPS gain: {first.best_possible_dps_gain:.2f}%")
            st.write(f"- Expected cubes to improve: {first.expected_cubes_to_improve:.1f}")
            st.write(f"- Diamond cost per cube: {BONUS_DIAMOND_PER_CUBE if first.is_bonus else REGULAR_DIAMOND_PER_CUBE} (monthly pkg rate)")
            st.write(f"- Estimated diamond cost: {first.expected_cubes_to_improve * (BONUS_DIAMOND_PER_CUBE if first.is_bonus else REGULAR_DIAMOND_PER_CUBE):,.0f}")

            if first.baseline_dps < 1000:
                st.error("⚠️ Baseline DPS is very low! This indicates stats are not properly configured, leading to unrealistic cube recommendations.")
    else:
        st.warning("No cube analysis results!")

# ==============================================================================
# OVERALL RECOMMENDED UPGRADE PATH
# ==============================================================================
st.subheader("🎯 RECOMMENDED UPGRADE PATH")
st.caption(f"Budget: {budget:,} diamonds | Sorted by efficiency")

# Collect all upgrades
all_upgrades = []

# NOTE: Cube upgrades now come from tier_upgrade_analysis below (line 694+)
# The old cube_analysis uses a heuristic efficiency_score that's not comparable
# with the DPS%/diamond efficiency used by starforce and tier upgrades.

# Starforce upgrades
for sf in sf_analysis:
    all_upgrades.append({
        'type': 'Starforce',
        'subtype': f"★{sf['current_stars']}→★{sf['target_stars']}",
        'target': sf['slot'],
        'target_display': f"{sf['slot'].title()} ★{sf['current_stars']}→★{sf['target_stars']}",
        'description': f"{sf['slot'].title()} ★{sf['current_stars']} → ★{sf['target_stars']} {sf['risk_color']}",
        'cost': sf['total_cost'],
        'dps_gain': sf['dps_gain'],
        'efficiency': sf['efficiency'],
        'details': {
            'risk': sf['risk'],
            'attempts': sf['expected_attempts'],
            'destroy_prob': sf['destroy_prob'],
            'optimal_strategy': sf['optimal_strategy'],
            'current_stars': sf['current_stars'],
            'target_stars': sf['target_stars'],
        },
    })

# Hero power (if there are lines to reroll)
if hp_analysis['lines_to_reroll'] and hp_analysis['diamond_equivalent'] > 0:
    all_upgrades.append({
        'type': 'Hero Power',
        'subtype': 'Reroll',
        'target': 'lines',
        'description': f"Hero Power: Lock {hp_analysis['num_locks']}, Reroll {len(hp_analysis['lines_to_reroll'])}",
        'cost': hp_analysis['diamond_equivalent'],
        'dps_gain': hp_analysis['expected_gain'],
        'efficiency': (hp_analysis['expected_gain'] / (hp_analysis['diamond_equivalent'] / 1000)) if hp_analysis['diamond_equivalent'] > 0 else 0,
        'details': {
            'medals': hp_analysis['total_medal_cost'],
            'rerolls': hp_analysis['estimated_rerolls'],
        },
    })

# Weapon upgrades
for wu in (weapon_analysis or []):
    # Skip if efficiency is very low
    if wu['efficiency'] <= 0:
        continue

    all_upgrades.append({
        'type': 'Weapon',
        'subtype': wu['subtype'],
        'target': wu['subtype'],
        'target_display': wu['description'],
        'description': f"🗡️ {wu['description']}",
        'cost': wu['cost'],
        'dps_gain': wu['dps_gain'],
        'efficiency': wu['efficiency'],
        'details': {
            'current_level': wu['current_level'],
            'target_level': wu['target_level'],
            'max_level': wu['max_level'],
            'is_equipped': wu['is_equipped'],
            'can_become_best': wu.get('can_become_best', False),
            'crossover_level': wu.get('crossover_level'),
        },
    })

# Weapon summon recommendations
for summon_rec in (summon_analysis or []):
    # Skip if efficiency is very low or cost is infinite
    if summon_rec['efficiency'] <= 0 or summon_rec['cost'] == float('inf'):
        continue

    all_upgrades.append({
        'type': 'Summon',
        'subtype': summon_rec['subtype'],
        'target': summon_rec['target'],
        'target_display': summon_rec['target_display'],
        'description': summon_rec['description'],
        'cost': summon_rec['cost'],
        'dps_gain': summon_rec['dps_gain'],
        'efficiency': summon_rec['efficiency'],
        'details': summon_rec['details'],
    })

# Optimal stopping cube recommendations
for tier_rec in (tier_upgrade_analysis or []):
    pot_type = "Bonus" if tier_rec.is_bonus else "Regular"
    path_str = " → ".join(tier_rec.path_tiers)

    # Skip if efficiency is very low or negative (great rolls)
    # These will show at the bottom anyway due to sorting
    if tier_rec.efficiency <= 0:
        continue

    all_upgrades.append({
        'type': 'Cube',
        'subtype': f'Optimal {pot_type}',
        'target': tier_rec.slot,
        'description': f"🎯 {tier_rec.slot.title()} {pot_type} ({tier_rec.current_tier})",
        'cost': tier_rec.total_cost_diamonds,
        'dps_gain': tier_rec.expected_dps_gain,
        'efficiency': tier_rec.efficiency,
        'details': {
            'current_dps': tier_rec.current_dps_gain,
            'current_percentile': tier_rec.current_percentile,
            'keep_threshold': tier_rec.keep_threshold,
            'expected_value_at_tier': tier_rec.expected_value_at_tier,
            'value_vs_threshold': tier_rec.value_vs_threshold,
            'path_tiers': tier_rec.path_tiers,
            'expected_cubes': tier_rec.expected_cubes_to_threshold,
            'current_pity': tier_rec.current_pity,
            'pity_threshold': tier_rec.pity_threshold,
            'current_tier': tier_rec.current_tier,
            'path_str': path_str,
        },
    })

# Sort by efficiency
all_upgrades.sort(key=lambda x: x['efficiency'], reverse=True)

# Select within budget
selected = []
remaining = budget
used_targets = set()

for upg in all_upgrades:
    target_key = f"{upg['type']}_{upg['target']}_{upg['subtype']}"
    if target_key in used_targets:
        continue
    if upg['cost'] <= remaining and upg['cost'] > 0:
        selected.append(upg)
        remaining -= upg['cost']
        used_targets.add(target_key)

# Display path
if selected:
    total_cost = sum(u['cost'] for u in selected)
    total_gain = sum(u['dps_gain'] for u in selected)

    st.success(f"**{len(selected)} upgrades selected** | Total: {total_cost:,.0f}💎 | Expected: +{total_gain:.1f}% DPS")

    # Detailed path display
    for i, upg in enumerate(selected, 1):
        type_icon = {"Cube": "🎲", "Starforce": "⭐", "Hero Power": "⚡", "Weapon": "🗡️", "Summon": "🎰"}.get(upg['type'], "❓")

        with st.container():
            st.markdown(f"### #{i}. {type_icon} {upg['description']}")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**DPS Impact:**")
                st.markdown(f"- Expected Gain: **+{upg['dps_gain']:.2f}%** DPS")
                if 'current_dps' in upg['details']:
                    st.markdown(f"- Current: +{upg['details']['current_dps']:.1f}%")
                    if 'best_dps' in upg['details']:
                        st.markdown(f"- Best Possible: +{upg['details']['best_dps']:.1f}%")
                    elif 'expected_value_at_tier' in upg['details']:
                        # Optimal stopping - show expected value
                        st.markdown(f"- E[Value]: +{upg['details']['expected_value_at_tier']:.2f}%")
                        if 'value_vs_threshold' in upg['details']:
                            vs_thresh = upg['details']['value_vs_threshold']
                            if vs_thresh < 0:
                                st.markdown(f"- Below threshold by {abs(vs_thresh):.2f}%")
                            else:
                                st.markdown(f"- Above threshold by {vs_thresh:.2f}%")
                    elif 'target_dps' in upg['details']:
                        # Legacy tier upgrade display
                        st.markdown(f"- Target at Mystic: +{upg['details']['target_dps']:.1f}%")
                        if 'current_percentile' in upg['details']:
                            st.markdown(f"- Current roll: {upg['details']['current_percentile']:.0f}th percentile")

            with col2:
                st.markdown("**Cost Analysis:**")
                st.markdown(f"- Cost: **{upg['cost']:,.0f}** diamonds")
                st.markdown(f"- Efficiency: {upg['efficiency']:.4f}")
                if 'cubes' in upg['details']:
                    st.markdown(f"- ~{upg['details']['cubes']:.0f} cubes needed")
                elif 'expected_cubes' in upg['details']:
                    # Optimal stopping info
                    st.markdown(f"- ~{upg['details']['expected_cubes']:.0f} cubes expected")
                    if 'keep_threshold' in upg['details']:
                        st.markdown(f"- Keep threshold: {upg['details']['keep_threshold']:.2f}%")
                elif 'path_tiers' in upg['details'] and 'cubes_per_step' in upg['details']:
                    # Multi-tier path breakdown (legacy)
                    path_tiers = upg['details']['path_tiers']
                    cubes_per_step = upg['details']['cubes_per_step']
                    path_parts = []
                    for i in range(len(cubes_per_step)):
                        path_parts.append(f"{path_tiers[i][:3]}(~{cubes_per_step[i]:.0f})")
                    path_parts.append("Mys")
                    st.markdown(f"- Path: {' → '.join(path_parts)}")
                    st.markdown(f"- Settle: ~{upg['details']['cubes_to_settle']:.0f} cubes")

            with col3:
                st.markdown("**Additional Info:**")
                # Show potential type prominently for cube upgrades
                if upg['type'] == 'Cube':
                    is_bonus = 'Bonus' in upg['subtype']
                    pot_label = "🟩 Bonus Potential" if is_bonus else "🟪 Regular Potential"
                    st.markdown(f"- **{pot_label}**")
                if upg['type'] == 'Weapon':
                    # Weapon upgrade specific info
                    is_equipped = upg['details'].get('is_equipped', False)
                    equipped_label = "✓ Equipped" if is_equipped else "📦 Inventory only"
                    st.markdown(f"- **{equipped_label}**")
                    max_level = upg['details'].get('max_level', 200)
                    target_level = upg['details'].get('target_level', 0)
                    st.markdown(f"- Level cap: {max_level}")
                    if upg['details'].get('can_become_best') and upg['details'].get('crossover_level'):
                        st.markdown(f"- ⚡ Can become best at Lv.{upg['details']['crossover_level']}")
                if upg['type'] == 'Summon':
                    # Summon recommendation specific info
                    use_case = upg['details'].get('use_case', 'new')
                    if use_case == 'new':
                        st.markdown("- **🆕 New weapon**")
                    else:
                        curr_awk = upg['details'].get('current_awakening', 0)
                        target_awk = upg['details'].get('target_awakening', 1)
                        st.markdown(f"- **⬆️ Awakening A{curr_awk} → A{target_awk}**")
                    drop_pct = upg['details'].get('drop_rate_pct', 0)
                    tickets = upg['details'].get('expected_tickets', 0)
                    st.markdown(f"- Drop rate: {drop_pct:.3f}%")
                    st.markdown(f"- ~{tickets:.0f} tickets expected")
                if 'difficulty' in upg['details']:
                    st.markdown(f"- Difficulty: {upg['details']['difficulty']}")
                if 'risk' in upg['details']:
                    st.markdown(f"- Risk: {upg['details']['risk']}")
                if 'rerolls' in upg['details']:
                    st.markdown(f"- ~{upg['details']['rerolls']:.0f} rerolls")
                if 'current_pity' in upg['details'] and 'pity_threshold' in upg['details']:
                    st.markdown(f"- Pity: {upg['details']['current_pity']}/{upg['details']['pity_threshold']}")

            # Add DPS Distribution Chart for Cube upgrades
            if upg['type'] == 'Cube':
                is_bonus = 'Bonus' in upg['subtype']  # Works for both "Bonus" and "Tier-Up Bonus"
                slot = upg['target']
                if st.checkbox(f"Show DPS Distribution", key=f"opt_dist_{slot}_{is_bonus}_{i}"):
                    with st.spinner("Generating distribution..."):
                        try:
                            dist_data = get_distribution_data_for_slot(
                                user_data=data,
                                slot=slot,
                                is_bonus=is_bonus,
                                aggregate_stats_func=aggregate_stats,
                                calculate_dps_func=calculate_dps,
                            )
                            if dist_data:
                                fig = create_dps_distribution_chart(
                                    distribution_data=dist_data,
                                    current_dps_gain=dist_data["current_dps_gain"],
                                    slot_name=slot,
                                    is_bonus=is_bonus,
                                    height=250,
                                )
                                st.plotly_chart(fig, use_container_width=True)

                                # Show percentile interpretation
                                # Find the matching recommendation
                                matching_rec = None
                                for rec in (cube_analysis or []):
                                    if rec.slot == slot and rec.is_bonus == is_bonus:
                                        matching_rec = rec
                                        break

                                if matching_rec:
                                    current_pct = matching_rec.percentile_score
                                    label = get_percentile_label(current_pct)
                                    color = get_percentile_color(current_pct)
                                    st.markdown(f"""
                                    <div style='font-family:monospace; font-size:11px; text-align:center;'>
                                    Your roll is <span style='color:{color}; font-weight:bold'>{label}</span>
                                    (beats {current_pct:.0f}% of possible rolls) |
                                    Median DPS gain: <span style='color:#ffc107'>+{dist_data['median_dps_gain']:.2f}%</span>
                                    </div>
                                    """, unsafe_allow_html=True)
                            else:
                                st.warning("Could not generate distribution for this slot.")
                        except Exception as e:
                            st.error(f"Error generating distribution: {e}")

            st.markdown("---")

    st.caption(f"Remaining budget: {remaining:,.0f}💎")

else:
    st.warning("No upgrades fit within your budget. Try increasing it!")

st.divider()

# ==============================================================================
# ALL OPTIONS RANKED
# ==============================================================================
with st.expander("📊 All Upgrade Options Ranked"):
    all_table = []
    for i, upg in enumerate(all_upgrades, 1):  # Show all upgrades, not just top 30
        type_icon = {"Cube": "🎲", "Starforce": "⭐", "Hero Power": "⚡", "Weapon": "🗡️", "Summon": "🎰"}.get(upg['type'], "❓")

        # Rank color
        if i <= 3:
            rank_display = f"🥇 #{i}"
        elif i <= 10:
            rank_display = f"#{i}"
        else:
            rank_display = f"#{i}"

        # Use target_display if available (for starforce), otherwise slot name
        target_text = upg.get('target_display', upg['target'].title())

        # For cube upgrades, add potential type indicator
        if upg['type'] == 'Cube':
            is_bonus = 'Bonus' in upg['subtype']
            pot_indicator = "🟩" if is_bonus else "🟪"
            target_text = f"{pot_indicator} {target_text}"

        all_table.append({
            "Rank": rank_display,
            "Type": f"{type_icon} {upg['type']}",
            "Target": target_text,
            "DPS Gain": f"+{upg['dps_gain']:.2f}%",
            "Cost": f"{upg['cost']:,.0f}💎",
            "Efficiency": f"{upg['efficiency']:.4f}",
        })

    st.dataframe(all_table, hide_index=True, use_container_width=True)

# ==============================================================================
# TIPS
# ==============================================================================
with st.expander("📚 Optimization Legend & Tips"):
    st.markdown("""
### Score Indicators
- 🔴 **Low Score (<30%)**: Easy to improve, high priority
- 🟡 **Medium Score (30-60%)**: Moderate improvement potential
- 🟢 **High Score (60%+)**: Already good, diminishing returns

### Efficiency Metric
`Efficiency = DPS Gain % / (Cost / 1000 diamonds)`

Higher efficiency = better value for your diamonds.

### Potential Types
- 🟪 = **Regular Potential** (cubed with normal cubes)
- 🟩 = **Bonus Potential** (cubed with bonus cubes)

### Line Tags
- **[Y]** = Yellow line (current tier, best value)
- **[G]** = Grey line (lower tier, weaker value)
- ***** = Special/rare potential

### Priority Order (General)
1. Cube low-score potentials (🔴) first
2. Starforce to ★15 (safe, good returns)
3. Fill empty potential lines
4. Push starforce to ★17-20 (risk vs reward)
5. Perfect high-score potentials (diminishing returns)

### Best Stats by Slot
| Slot | Top Stats |
|------|-----------|
| **Gloves** | Crit Damage, Damage% |
| **Cape/Bottom** | Final Damage, Damage% |
| **Shoulder** | Defense Pen, Final Damage |
| **Ring/Necklace** | All Skills, Damage% |
| **Hat** | Skill CD Reduction, Damage% |
| **Top** | BA Targets, Final Damage |
""")

# ==============================================================================
# ADVANCED: OPTIMAL STAT DISTRIBUTION ANALYSIS
# ==============================================================================
st.divider()
st.header("📊 Advanced: Optimal Stat Distribution")
st.caption("Theoretical optimal stat allocation - expand sections below for detailed analysis")

# Create a DPS function wrapper for the optimizer
def calc_dps_for_optimizer(stats: Dict[str, float]) -> float:
    """Wrapper for DPS calculation compatible with optimal_stats module."""
    return calculate_dps(stats, data.combat_mode)['total']

# Tier mode selection
tier_col1, tier_col2 = st.columns(2)
with tier_col1:
    tier_mode = st.selectbox(
        "Tier Mode",
        ["mystic", "legendary", "unique"],
        help="Mystic = theoretical max, or select your current average tier"
    )
with tier_col2:
    include_artifacts = st.checkbox("Include Artifacts", value=True)

# Get current stats for efficiency calculation
efficiency_stats = current_stats.copy()

# ==============================================================================
# SLOT EFFICIENCY ANALYSIS
# ==============================================================================
st.subheader("🔍 Slot Efficiency Analysis")
st.caption("For each slot, shows how efficient each stat option is (DPS gain per stat point)")

# Show efficiency for each slot with exclusive stats
slots_with_exclusive = ['shoulder', 'gloves', 'cape', 'bottom', 'ring', 'necklace', 'top', 'hat']

efficiency_tabs = st.tabs([s.title() for s in slots_with_exclusive])

for i, slot in enumerate(slots_with_exclusive):
    with efficiency_tabs[i]:
        efficiency = calculate_slot_efficiency(slot, efficiency_stats, calc_dps_for_optimizer, tier_mode)

        if efficiency:
            # Display as bar chart
            eff_data = []
            for e in efficiency[:6]:  # Top 6 options
                stat_name = format_stat_name(e['stat'])
                exclusive_tag = " (EXCLUSIVE)" if e['is_exclusive'] else ""
                eff_data.append({
                    'Stat': f"{stat_name}{exclusive_tag}",
                    'Max Value': f"{e['max_value']:.0f}%",
                    'DPS Gain': f"+{e['dps_gain']:.2f}%",
                    'Efficiency': e['efficiency_normalized'],
                })

            # Show as table with visual bars
            for j, e in enumerate(eff_data):
                bar_width = int(e['Efficiency'])
                bar = "█" * (bar_width // 5) + "░" * ((100 - bar_width) // 5)

                cols = st.columns([2, 1, 1, 4])
                with cols[0]:
                    st.write(e['Stat'])
                with cols[1]:
                    st.write(e['Max Value'])
                with cols[2]:
                    st.write(e['DPS Gain'])
                with cols[3]:
                    st.write(f"{bar} {e['Efficiency']:.0f}%")

            # Highlight if exclusive stat available
            if slot in SLOT_EXCLUSIVE_STATS:
                exclusive_stats = list(SLOT_EXCLUSIVE_STATS[slot].keys())
                st.info(f"**Exclusive stats on {slot.title()}:** {', '.join([format_stat_name(s) for s in exclusive_stats])}")

st.divider()

# ==============================================================================
# SOURCE RANKING FOR KEY STATS
# ==============================================================================
st.subheader("Source Ranking by Stat")
st.caption("For key stats, shows which sources provide the best value")

key_stats = ['def_pen', 'crit_damage', 'final_atk_dmg', 'damage', 'boss_damage']
stat_tabs = st.tabs([format_stat_name(s) for s in key_stats])

for i, stat in enumerate(key_stats):
    with stat_tabs[i]:
        ranking = calculate_source_ranking(stat, efficiency_stats, calc_dps_for_optimizer, tier_mode, include_artifacts)

        if ranking:
            st.markdown(f"**Where to get {format_stat_name(stat)}?**")

            ranking_table = []
            for r in ranking[:8]:
                source_display = r['slot'].title() if r['slot'] else r['source_type'].replace('_', ' ').title()
                exclusive_tag = " (EXCLUSIVE)" if r['is_exclusive'] else ""

                ranking_table.append({
                    'Rank': f"#{r['rank']}",
                    'Source': f"{source_display}{exclusive_tag}",
                    'Max Value': f"{r['max_value']:.0f}%",
                    'DPS Gain': f"+{r['dps_gain']:.2f}%",
                    'Efficiency': f"{r['efficiency']:.4f}",
                })

            st.dataframe(ranking_table, hide_index=True, use_container_width=True)

            # Best source recommendation
            if ranking:
                best = ranking[0]
                source_name = best['slot'].title() if best['slot'] else best['source_type'].replace('_', ' ').title()
                st.success(f"**Best source for {format_stat_name(stat)}:** {source_name} ({best['max_value']:.0f}% max)")
        else:
            st.warning(f"{format_stat_name(stat)} is not available at {tier_mode} tier")

st.divider()

# ==============================================================================
# OPTIMAL BUILD TEMPLATE
# ==============================================================================
st.subheader("Optimal Build Template")
st.caption(f"Theoretically optimal stat distribution at {tier_mode.title()} tier")

# Calculate optimal distribution
try:
    optimal_build = calculate_optimal_distribution(
        current_stats, calc_dps_for_optimizer, tier_mode, include_artifacts
    )

    # Group allocations by slot/source
    alloc_by_slot = {}
    for alloc in optimal_build.allocations:
        key = alloc.slot or alloc.source_type
        if key not in alloc_by_slot:
            alloc_by_slot[key] = []
        alloc_by_slot[key].append(alloc)

    # Display as expandable sections
    for slot_key in sorted(alloc_by_slot.keys()):
        allocs = alloc_by_slot[slot_key]

        with st.expander(f"{slot_key.title().replace('_', ' ')} - {len(allocs)} lines", expanded=False):
            for alloc in allocs:
                exclusive_tag = " (EXCLUSIVE)" if alloc.is_exclusive else ""
                st.markdown(f"- **{format_stat_name(alloc.stat_type)}** {alloc.value:.0f}%{exclusive_tag}")

            # Show total DPS contribution from this slot
            slot_dps = sum(a.efficiency_score * a.value for a in allocs)
            st.caption(f"Efficiency score: {slot_dps:.2f}")

    # Summary stats
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Allocations", len(optimal_build.allocations))
    with col2:
        st.metric("Tier Mode", tier_mode.title())
    with col3:
        if include_artifacts:
            st.metric("Includes", "Equipment + HP + Artifacts")
        else:
            st.metric("Includes", "Equipment + Hero Power")

except Exception as e:
    st.error(f"Could not calculate optimal distribution: {e}")
    st.caption("This may occur if base stats are not fully configured.")

st.divider()

# ==============================================================================
# CURRENT VS OPTIMAL COMPARISON
# ==============================================================================
st.subheader("Current vs Optimal Gap")
st.caption("Shows how your current build compares to optimal")

# Build current allocations from user data
current_allocations = []

# Equipment potentials
for slot in EQUIPMENT_SLOTS:
    pots = data.equipment_potentials.get(slot, {})
    for prefix in ['', 'bonus_']:
        for i in range(1, 4):
            stat = pots.get(f'{prefix}line{i}_stat', '')
            value = float(pots.get(f'{prefix}line{i}_value', 0))
            if stat and value > 0:
                current_allocations.append({
                    'slot': slot,
                    'stat': stat,
                    'value': value,
                    'source_type': f'equipment_{prefix.rstrip("_") or "regular"}',
                })

# Hero Power
for line_key, line in data.hero_power_lines.items():
    stat = line.get('stat', '')
    value = float(line.get('value', 0))
    if stat and value > 0:
        current_allocations.append({
            'slot': None,
            'stat': stat,
            'value': value,
            'source_type': 'hero_power',
        })

# Calculate gap for each slot
if current_allocations:
    st.markdown("**Slot-by-Slot Analysis:**")

    gap_analysis = []
    for slot in EQUIPMENT_SLOTS:
        # Current stats for this slot
        current_slot = [a for a in current_allocations if a.get('slot') == slot]
        current_stats_slot = {}
        for a in current_slot:
            current_stats_slot[a['stat']] = current_stats_slot.get(a['stat'], 0) + a['value']

        # Get optimal for this slot
        optimal_info = get_optimal_stat_for_slot(slot, efficiency_stats, calc_dps_for_optimizer, tier_mode)

        if optimal_info.get('best_stat'):
            best_stat = optimal_info['best_stat']
            best_value = optimal_info['max_value']

            # Check if user has this stat
            user_value = current_stats_slot.get(best_stat, 0)
            gap = best_value - user_value

            # Calculate efficiency score
            if user_value >= best_value * 0.8:
                status = "Good"
                indicator = "green"
            elif user_value >= best_value * 0.5:
                status = "Fair"
                indicator = "orange"
            else:
                status = "Needs Work"
                indicator = "red"

            gap_analysis.append({
                'Slot': slot.title(),
                'Best Stat': format_stat_name(best_stat),
                'Optimal': f"{best_value:.0f}%",
                'Current': f"{user_value:.0f}%",
                'Gap': f"{gap:.0f}%",
                'Status': status,
            })

    if gap_analysis:
        # Sort by gap (largest first)
        gap_analysis.sort(key=lambda x: float(x['Gap'].rstrip('%')), reverse=True)
        st.dataframe(gap_analysis, hide_index=True, use_container_width=True)

        # Priority fixes
        needs_work = [g for g in gap_analysis if g['Status'] == 'Needs Work']
        if needs_work:
            st.warning(f"**Priority Fixes:** {', '.join([g['Slot'] for g in needs_work[:5]])}")

        good_slots = [g for g in gap_analysis if g['Status'] == 'Good']
        if good_slots:
            st.success(f"**Well Optimized:** {', '.join([g['Slot'] for g in good_slots])}")
else:
    st.info("Configure your equipment potentials and hero power to see gap analysis.")
