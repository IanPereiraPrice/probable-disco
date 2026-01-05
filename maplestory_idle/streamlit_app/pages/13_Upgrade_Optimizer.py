"""
Upgrade Path Optimizer Page
Comprehensive upgrade recommendations with detailed DPS analysis and specific targets.
Mirrors the old Tkinter app's Upgrade Path tab functionality.
"""
import streamlit as st
from typing import Dict, List, Any, Optional
from utils.data_manager import save_user_data, EQUIPMENT_SLOTS
from utils.cube_analyzer import (
    analyze_all_cube_priorities, CubeRecommendation,
    format_stat_display, REGULAR_DIAMOND_PER_CUBE, BONUS_DIAMOND_PER_CUBE
)

st.set_page_config(page_title="Upgrade Optimizer", page_icon="📈", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

# ==============================================================================
# Constants
# ==============================================================================
HEX_MULTIPLIER = 1.24
BASE_MIN_DMG = 60.0
BASE_MAX_DMG = 100.0
BASE_CRIT_DMG = 30.0

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


# ==============================================================================
# Stat Aggregation and DPS Calculation
# ==============================================================================
def aggregate_stats() -> Dict[str, float]:
    """Aggregate all stats from user data."""
    stats = {
        'flat_dex': 0,
        'dex_percent': 0,
        'damage_percent': 0,
        'boss_damage': 0,
        'normal_damage': 0,
        'crit_damage': 0,
        'crit_rate': 0,
        'final_damage': 0,
        'defense_pen': 0,
        'min_dmg_mult': 0,
        'max_dmg_mult': 0,
        'attack_speed': 0,
        'base_attack': 0,
    }

    # Equipment potentials (regular and bonus)
    for slot in EQUIPMENT_SLOTS:
        pots = data.equipment_potentials.get(slot, {})
        for prefix in ['', 'bonus_']:
            for i in range(1, 4):
                stat = pots.get(f'{prefix}line{i}_stat', '')
                value = float(pots.get(f'{prefix}line{i}_value', 0))

                if stat == 'damage':
                    stats['damage_percent'] += value
                elif stat == 'boss_damage':
                    stats['boss_damage'] += value
                elif stat == 'crit_damage':
                    stats['crit_damage'] += value
                elif stat == 'final_damage':
                    stats['final_damage'] += value
                elif stat == 'def_pen':
                    stats['defense_pen'] += value
                elif stat == 'normal_damage':
                    stats['normal_damage'] += value
                elif stat == 'min_dmg_mult':
                    stats['min_dmg_mult'] += value
                elif stat == 'max_dmg_mult':
                    stats['max_dmg_mult'] += value
                elif stat in ('dex_pct', 'str_pct', 'int_pct', 'luk_pct'):
                    stats['dex_percent'] += value
                elif stat in ('dex_flat', 'str_flat', 'int_flat', 'luk_flat'):
                    stats['flat_dex'] += value
                elif stat == 'crit_rate':
                    stats['crit_rate'] += value

    # Equipment base stats
    for slot in EQUIPMENT_SLOTS:
        item = data.equipment_items.get(slot, {})
        stats['base_attack'] += item.get('base_attack', 0)

    # Hero Power lines
    for line_key, line in data.hero_power_lines.items():
        stat = line.get('stat', '')
        value = float(line.get('value', 0))

        if stat == 'damage':
            stats['damage_percent'] += value
        elif stat == 'boss_damage':
            stats['boss_damage'] += value
        elif stat == 'crit_damage':
            stats['crit_damage'] += value
        elif stat == 'def_pen':
            stats['defense_pen'] += value
        elif stat == 'min_dmg_mult':
            stats['min_dmg_mult'] += value
        elif stat == 'max_dmg_mult':
            stats['max_dmg_mult'] += value

    # Hero Power passives
    passives = data.hero_power_passives
    stats['flat_dex'] += passives.get('main_stat', 0) * 100
    stats['damage_percent'] += passives.get('damage', 0) * 2

    # Maple Rank
    mr = data.maple_rank
    stage = mr.get('current_stage', 1)
    ms_level = mr.get('main_stat_level', 0)
    special = mr.get('special_main_stat', 0)
    stats['flat_dex'] += (stage - 1) * 100 + ms_level * 10 + special

    stat_levels = mr.get('stat_levels', {})
    if isinstance(stat_levels, dict):
        stats['attack_speed'] += stat_levels.get('attack_speed', 0) * 0.5
        stats['crit_rate'] += stat_levels.get('crit_rate', 0) * 1
        stats['damage_percent'] += stat_levels.get('damage', 0) * 2
        stats['boss_damage'] += stat_levels.get('boss_damage', 0) * 2
        stats['normal_damage'] += stat_levels.get('normal_damage', 0) * 2
        stats['crit_damage'] += stat_levels.get('crit_damage', 0) * 2

    # Equipment sets
    stats['flat_dex'] += data.equipment_sets.get('medal', 0)
    stats['flat_dex'] += data.equipment_sets.get('costume', 0)

    return stats


def calculate_dps(stats: Dict[str, float], combat_mode: str = 'stage', enemy_def: float = 0.752) -> Dict[str, Any]:
    """Calculate DPS from stats."""
    total_dex = stats['flat_dex'] * (1 + stats['dex_percent'] / 100)
    stat_multiplier = 1 + (total_dex / 10000)

    hex_mult = HEX_MULTIPLIER ** 3
    total_damage_pct = (stats['damage_percent'] / 100) * hex_mult
    base_damage_mult = 1 + total_damage_pct

    if combat_mode in ('boss', 'world_boss'):
        damage_multiplier = base_damage_mult * (1 + stats['boss_damage'] / 100)
    else:
        normal_weight = 0.60
        boss_weight = 0.40
        mult_vs_normal = base_damage_mult * (1 + stats['normal_damage'] / 100)
        mult_vs_boss = base_damage_mult * (1 + stats['boss_damage'] / 100)
        damage_multiplier = (normal_weight * mult_vs_normal) + (boss_weight * mult_vs_boss)

    fd_multiplier = 1 + stats['final_damage'] / 100
    total_crit_dmg = BASE_CRIT_DMG + stats['crit_damage']
    crit_multiplier = 1 + (total_crit_dmg / 100)

    def_pen_decimal = stats['defense_pen'] / 100
    defense_multiplier = 1 / (1 + enemy_def * (1 - def_pen_decimal))

    final_min = BASE_MIN_DMG + stats['min_dmg_mult']
    final_max = BASE_MAX_DMG + stats['max_dmg_mult']
    avg_mult = (final_min + final_max) / 2
    dmg_range_mult = avg_mult / 100

    atk_spd_mult = 1 + (stats['attack_speed'] / 100)
    base_atk = max(stats['base_attack'], 10000)

    total = (base_atk * stat_multiplier * damage_multiplier *
             fd_multiplier * crit_multiplier * defense_multiplier *
             dmg_range_mult * atk_spd_mult)

    return {'total': total}


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


def analyze_cube_priorities_detailed() -> List[Dict]:
    """Analyze cube priorities with detailed breakdown."""
    results = []

    for slot in EQUIPMENT_SLOTS:
        for is_bonus in [False, True]:
            summary = get_potential_lines_summary(slot, is_bonus)
            pot_type = "Bonus" if is_bonus else "Regular"
            diamond_cost = BONUS_DIAMOND_PER_CUBE if is_bonus else REGULAR_DIAMOND_PER_CUBE

            current_dps = summary['total_dps']
            best_dps = calculate_best_possible_dps(slot, summary['tier'])
            improvement_room = best_dps - current_dps

            # Score based on current vs best
            if best_dps > 0:
                score = (current_dps / best_dps) * 100
            else:
                score = 100

            # Expected cubes to improve
            if score < 30:
                cubes_to_improve = 10
                difficulty = "Easy"
            elif score < 50:
                cubes_to_improve = 25
                difficulty = "Medium"
            elif score < 70:
                cubes_to_improve = 50
                difficulty = "Hard"
            else:
                cubes_to_improve = 100
                difficulty = "Very Hard"

            expected_cost = cubes_to_improve * diamond_cost
            expected_gain = improvement_room * 0.4  # Conservative estimate

            efficiency = (expected_gain / (expected_cost / 1000)) if expected_cost > 0 else 0

            # Score indicator
            if score < 30:
                indicator = "🔴"
            elif score < 60:
                indicator = "🟡"
            else:
                indicator = "🟢"

            results.append({
                'slot': slot,
                'is_bonus': is_bonus,
                'pot_type': pot_type,
                'tier': summary['tier'],
                'pity': summary['pity'],
                'lines': summary['lines'],
                'current_dps': current_dps * 100,  # Convert to %
                'best_dps': best_dps * 100,
                'improvement_room': improvement_room * 100,
                'score': score,
                'indicator': indicator,
                'cubes_to_improve': cubes_to_improve,
                'expected_cost': expected_cost,
                'expected_gain': expected_gain * 100,
                'efficiency': efficiency,
                'difficulty': difficulty,
                'target_stats': SLOT_TARGET_STATS.get(slot, [])[:3],
            })

    # Sort by efficiency (highest first)
    results.sort(key=lambda x: x['efficiency'], reverse=True)

    # Add rank
    for i, r in enumerate(results):
        r['rank'] = i + 1

    return results


def analyze_starforce_detailed() -> List[Dict]:
    """Analyze starforce with detailed cost breakdown."""
    results = []

    for slot in EQUIPMENT_SLOTS:
        item = data.equipment_items.get(slot, {})
        current_stars = item.get('stars', 0)

        if current_stars >= 25 or current_stars < 10:
            continue

        target_stars = current_stars + 1

        # Detailed cost calculation
        if target_stars in STARFORCE_DATA:
            success_rate, destroy_rate, meso_cost = STARFORCE_DATA[target_stars - 1]

            # Base cost per attempt
            base_diamond_cost = meso_cost * MESO_TO_DIAMOND + SCROLL_COST
            expected_attempts = 1 / success_rate if success_rate > 0 else 100

            # Destruction risk
            if destroy_rate > 0:
                expected_destructions = destroy_rate * expected_attempts
                destruction_cost = expected_destructions * DESTRUCTION_FEE
                total_cost = base_diamond_cost * expected_attempts + destruction_cost
            else:
                total_cost = base_diamond_cost * expected_attempts
                expected_destructions = 0
        else:
            total_cost = 5000
            expected_attempts = 2
            expected_destructions = 0

        # DPS gain
        current_amp = STARFORCE_SUB_AMPLIFY.get(current_stars, 0)
        target_amp = STARFORCE_SUB_AMPLIFY.get(target_stars, current_amp)
        amp_gain = target_amp - current_amp
        dps_gain = amp_gain * 30  # Rough: 0.1 amp = 3% DPS

        efficiency = (dps_gain / (total_cost / 1000)) if total_cost > 0 else 0

        # Risk level
        if target_stars <= 14:
            risk = "Safe"
            risk_color = "🟢"
        elif target_stars == 15:
            risk = "Low (3%)"
            risk_color = "🟡"
        elif target_stars <= 17:
            risk = "Medium (4-5%)"
            risk_color = "🟠"
        elif target_stars <= 20:
            risk = "High (6-11%)"
            risk_color = "🔴"
        else:
            risk = "Very High"
            risk_color = "🔴"

        results.append({
            'slot': slot,
            'current_stars': current_stars,
            'target_stars': target_stars,
            'total_cost': total_cost,
            'expected_attempts': expected_attempts,
            'expected_destructions': expected_destructions,
            'dps_gain': dps_gain,
            'efficiency': efficiency,
            'risk': risk,
            'risk_color': risk_color,
            'amp_before': current_amp,
            'amp_after': target_amp,
        })

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

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Current DPS", f"{current_dps:,.0f}")
with col2:
    st.metric("Combat Mode", data.combat_mode.title())
with col3:
    budget = st.number_input("Diamond Budget", min_value=0, max_value=10000000, value=100000, step=10000)

st.divider()

# ==============================================================================
# CUBE PRIORITY (Most Important)
# ==============================================================================
st.subheader("🎲 CUBE PRIORITY RANKING")
st.caption("Sorted by efficiency (DPS gain per diamond spent)")

cube_analysis = analyze_cube_priorities_detailed()

if cube_analysis:
    # Top recommendations table
    cube_table = []
    for rec in cube_analysis[:15]:
        lines_preview = " | ".join([
            f"{l['stat_display'][:8]}:{l['value']:.0f}" if l['stat'] else "---"
            for l in rec['lines']
        ])

        cube_table.append({
            "Rank": f"#{rec['rank']}",
            "Slot": f"{rec['slot'].title()} ({rec['pot_type']})",
            "Tier": rec['tier'],
            "Score": f"{rec['indicator']} {rec['score']:.0f}/100",
            "Current": f"+{rec['current_dps']:.1f}%",
            "Best": f"+{rec['best_dps']:.1f}%",
            "Room": f"+{rec['improvement_room']:.1f}%",
            "Cubes": f"~{rec['cubes_to_improve']:.0f}",
            "Cost": f"{rec['expected_cost']:,.0f}💎",
            "Difficulty": rec['difficulty'],
        })

    st.dataframe(cube_table, hide_index=True, use_container_width=True)

    # Detailed breakdown for top 5
    st.markdown("### Detailed Analysis - Top 5 Targets")

    for rec in cube_analysis[:5]:
        with st.expander(f"#{rec['rank']} {rec['slot'].title()} ({rec['pot_type']}) - {rec['indicator']} Score: {rec['score']:.0f}/100"):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("**Current Lines:**")
                for j, line in enumerate(rec['lines'], 1):
                    if line['stat']:
                        yellow_tag = "[Y]" if line.get('is_yellow') else "[G]"
                        st.markdown(f"L{j}: {yellow_tag} {line['stat_display']} {line['value']:.1f}%")
                    else:
                        st.markdown(f"L{j}: (empty)")

            with col2:
                st.markdown("**DPS Impact:**")
                st.markdown(f"- Current Roll: **+{rec['current_dps']:.2f}%** DPS")
                st.markdown(f"- Best Possible: **+{rec['best_dps']:.2f}%** DPS")
                st.markdown(f"- Room to Improve: **+{rec['improvement_room']:.2f}%** DPS")
                st.markdown(f"- Expected Gain: **+{rec['expected_gain']:.2f}%** DPS")

            with col3:
                st.markdown("**Target Stats:**")
                for stat in rec['target_stats']:
                    st.markdown(f"- {format_stat_display(stat)}")

                st.markdown("")
                st.markdown("**Cost Analysis:**")
                st.markdown(f"- ~{rec['cubes_to_improve']} cubes")
                st.markdown(f"- ~{rec['expected_cost']:,.0f} diamonds")
                st.markdown(f"- Efficiency: {rec['efficiency']:.4f}")

            # Pity progress
            if rec['pity'] > 0:
                st.info(f"Tier-up pity: {rec['pity']} cubes used (closer to guaranteed tier-up!)")

st.divider()

# ==============================================================================
# STARFORCE ANALYSIS
# ==============================================================================
st.subheader("⭐ STARFORCE PRIORITY")

sf_analysis = analyze_starforce_detailed()

if sf_analysis:
    sf_table = []
    for sf in sf_analysis[:10]:
        sf_table.append({
            "Slot": sf['slot'].title(),
            "Current": f"★{sf['current_stars']}",
            "Target": f"★{sf['target_stars']}",
            "Cost": f"{sf['total_cost']:,.0f}💎",
            "DPS Gain": f"+{sf['dps_gain']:.1f}%",
            "Efficiency": f"{sf['efficiency']:.4f}",
            "Risk": f"{sf['risk_color']} {sf['risk']}",
            "Amp": f"{sf['amp_before']:.0%} → {sf['amp_after']:.0%}",
        })

    st.dataframe(sf_table, hide_index=True, use_container_width=True)

    # Warning for risky upgrades
    risky = [sf for sf in sf_analysis if sf['target_stars'] >= 15]
    if risky:
        with st.expander("Starforce Risk Analysis"):
            for sf in risky[:5]:
                st.markdown(f"**{sf['slot'].title()} ★{sf['current_stars']} → ★{sf['target_stars']}**")
                st.markdown(f"- Expected attempts: {sf['expected_attempts']:.1f}")
                st.markdown(f"- Destruction risk: {sf['expected_destructions']:.2f} expected destructions")
                st.markdown(f"- Recommendation: {'Use protection' if sf['target_stars'] >= 17 else 'Consider risk carefully'}")
                st.markdown("---")
else:
    st.success("All equipment at max stars or below ★10!")

st.divider()

# ==============================================================================
# HERO POWER ANALYSIS
# ==============================================================================
st.subheader("⚡ HERO POWER ANALYSIS")

hp_analysis = analyze_hero_power_detailed()

# Current lines display
st.markdown(f"**Preset {hp_analysis['preset']} - Line Analysis:**")

line_cols = st.columns(6)
for i, line in enumerate(hp_analysis['lines']):
    with line_cols[i]:
        st.markdown(f"**L{line['line']}** {line['indicator']}")
        st.caption(f"{line['stat_display']}")
        if line['value'] > 0:
            st.caption(f"{line['value']:.1f}%")
        st.caption(f"*{line['tier'][:3]}*")
        st.caption(f"Score: {line['score']:.0f}")

# Summary
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total DPS Contribution", f"+{hp_analysis['total_dps']:.1f}%")
with col2:
    lock_str = ", ".join([f"L{l}" for l in hp_analysis['lines_to_lock']]) or "None"
    st.metric("Lines to Lock", lock_str)
with col3:
    reroll_str = ", ".join([f"L{l}" for l in hp_analysis['lines_to_reroll']]) or "None"
    st.metric("Lines to Reroll", reroll_str)

# Recommendation
if hp_analysis['lines_to_reroll']:
    st.info(f"""
**Reroll Strategy:**
- Lock {hp_analysis['num_locks']} lines (cost: {hp_analysis['cost_per_reroll']} medals/reroll)
- Estimated rerolls needed: ~{hp_analysis['estimated_rerolls']:.0f}
- Total medal cost: ~{hp_analysis['total_medal_cost']:,.0f} medals ({hp_analysis['diamond_equivalent']:,.0f} diamond equivalent)
- Expected DPS gain: +{hp_analysis['expected_gain']:.1f}%
""")
else:
    st.success("All lines are good! Consider focusing on other upgrades.")

st.divider()

# ==============================================================================
# OPTIMAL UPGRADE PATH
# ==============================================================================
st.subheader("🎯 RECOMMENDED UPGRADE PATH")
st.caption(f"Budget: {budget:,} diamonds | Sorted by efficiency")

# Collect all upgrades
all_upgrades = []

# Cube upgrades
for rec in cube_analysis:
    all_upgrades.append({
        'type': 'Cube',
        'subtype': rec['pot_type'],
        'target': rec['slot'],
        'description': f"{rec['slot'].title()} {rec['pot_type']} ({rec['tier']}) {rec['indicator']}",
        'cost': rec['expected_cost'],
        'dps_gain': rec['expected_gain'],
        'efficiency': rec['efficiency'],
        'details': {
            'current_dps': rec['current_dps'],
            'best_dps': rec['best_dps'],
            'improvement_room': rec['improvement_room'],
            'cubes': rec['cubes_to_improve'],
            'difficulty': rec['difficulty'],
        },
    })

# Starforce upgrades
for sf in sf_analysis:
    all_upgrades.append({
        'type': 'Starforce',
        'subtype': '',
        'target': sf['slot'],
        'description': f"{sf['slot'].title()} ★{sf['current_stars']} → ★{sf['target_stars']} {sf['risk_color']}",
        'cost': sf['total_cost'],
        'dps_gain': sf['dps_gain'],
        'efficiency': sf['efficiency'],
        'details': {
            'risk': sf['risk'],
            'attempts': sf['expected_attempts'],
            'destructions': sf['expected_destructions'],
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
        type_icon = {"Cube": "🎲", "Starforce": "⭐", "Hero Power": "⚡"}.get(upg['type'], "❓")

        with st.container():
            st.markdown(f"### #{i}. {type_icon} {upg['description']}")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**DPS Impact:**")
                st.markdown(f"- Expected Gain: **+{upg['dps_gain']:.2f}%** DPS")
                if 'current_dps' in upg['details']:
                    st.markdown(f"- Current: +{upg['details']['current_dps']:.1f}%")
                    st.markdown(f"- Best Possible: +{upg['details']['best_dps']:.1f}%")

            with col2:
                st.markdown("**Cost Analysis:**")
                st.markdown(f"- Cost: **{upg['cost']:,.0f}** diamonds")
                st.markdown(f"- Efficiency: {upg['efficiency']:.4f}")
                if 'cubes' in upg['details']:
                    st.markdown(f"- ~{upg['details']['cubes']} cubes needed")

            with col3:
                st.markdown("**Additional Info:**")
                if 'difficulty' in upg['details']:
                    st.markdown(f"- Difficulty: {upg['details']['difficulty']}")
                if 'risk' in upg['details']:
                    st.markdown(f"- Risk: {upg['details']['risk']}")
                if 'rerolls' in upg['details']:
                    st.markdown(f"- ~{upg['details']['rerolls']:.0f} rerolls")

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
    for i, upg in enumerate(all_upgrades[:30], 1):
        type_icon = {"Cube": "🎲", "Starforce": "⭐", "Hero Power": "⚡"}.get(upg['type'], "❓")

        # Rank color
        if i <= 3:
            rank_display = f"🥇 #{i}"
        elif i <= 10:
            rank_display = f"#{i}"
        else:
            rank_display = f"#{i}"

        all_table.append({
            "Rank": rank_display,
            "Type": f"{type_icon} {upg['type']}",
            "Target": upg['target'].title(),
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
