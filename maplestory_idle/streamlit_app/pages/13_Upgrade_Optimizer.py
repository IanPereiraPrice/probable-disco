"""
Upgrade Path Optimizer Page
Comprehensive upgrade recommendations with budget planning and efficiency scoring.
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

# Starforce data
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
# Upgrade Analysis Functions
# ==============================================================================
def analyze_starforce_upgrades() -> List[Dict]:
    """Analyze starforce upgrade opportunities."""
    upgrades = []

    for slot in EQUIPMENT_SLOTS:
        item = data.equipment_items.get(slot, {})
        current_stars = item.get('stars', 0)

        if current_stars >= 25 or current_stars < 10:
            continue

        target_stars = current_stars + 1

        # Calculate cost
        cost = 0
        for star in range(current_stars, target_stars):
            if star in STARFORCE_DATA:
                success_rate, destroy_rate, meso_cost = STARFORCE_DATA[star]
                diamond_cost = meso_cost * MESO_TO_DIAMOND + SCROLL_COST
                expected_attempts = 1 / success_rate if success_rate > 0 else 100

                if star >= 15 and destroy_rate > 0:
                    expected_destructions = destroy_rate * expected_attempts
                    destruction_cost = expected_destructions * DESTRUCTION_FEE
                    diamond_cost += destruction_cost / expected_attempts

                cost += diamond_cost * expected_attempts

        # Calculate DPS gain from sub-stat amplification
        current_amp = STARFORCE_SUB_AMPLIFY.get(current_stars, 0)
        target_amp = STARFORCE_SUB_AMPLIFY.get(target_stars, current_amp)
        dps_gain = ((target_amp - current_amp) / (1 + current_amp)) * 100 * 0.3

        # Risk assessment
        if target_stars <= 14:
            risk = "Safe"
            risk_color = "🟢"
        elif target_stars == 15:
            risk = "Low (3%)"
            risk_color = "🟡"
        elif target_stars <= 17:
            risk = "Medium (4-5%)"
            risk_color = "🟠"
        else:
            risk = "High (6%+)"
            risk_color = "🔴"

        efficiency = (dps_gain / (cost / 1000)) if cost > 0 else 0

        upgrades.append({
            'slot': slot,
            'type': 'Starforce',
            'current': f'★{current_stars}',
            'target': f'★{target_stars}',
            'cost': cost,
            'dps_gain': dps_gain,
            'efficiency': efficiency,
            'risk': f'{risk_color} {risk}',
            'description': f'{slot.title()} ★{current_stars} → ★{target_stars}',
        })

    return upgrades


def analyze_hero_power_upgrades() -> List[Dict]:
    """Analyze hero power passive upgrade opportunities."""
    upgrades = []

    passives = data.hero_power_passives
    passive_info = {
        'main_stat': {'name': 'Main Stat', 'max': 10, 'dps_per_level': 0.5},
        'damage': {'name': 'Damage', 'max': 10, 'dps_per_level': 0.8},
        'attack': {'name': 'Attack', 'max': 10, 'dps_per_level': 0.3},
    }

    for stat_key, info in passive_info.items():
        current = passives.get(stat_key, 0)
        if current >= info['max']:
            continue

        target = min(current + 1, info['max'])
        dps_gain = info['dps_per_level']

        # Estimate cost (varies by passive type and level)
        cost = 1000 * (current + 1)  # Rough estimate

        efficiency = (dps_gain / (cost / 1000)) if cost > 0 else 0

        upgrades.append({
            'slot': 'hero_power',
            'type': 'Hero Power Passive',
            'current': f'Lv{current}',
            'target': f'Lv{target}',
            'cost': cost,
            'dps_gain': dps_gain,
            'efficiency': efficiency,
            'risk': '🟢 None',
            'description': f'{info["name"]} Passive Lv{current} → Lv{target}',
        })

    return upgrades


def analyze_hero_power_lines() -> Dict:
    """Analyze hero power line quality."""
    lines = data.hero_power_lines
    good_stats = {'damage', 'boss_damage', 'crit_damage', 'def_pen'}

    total_dps = 0
    line_analysis = []

    for i in range(1, 7):
        line = lines.get(f'line{i}', {})
        stat = line.get('stat', '')
        value = float(line.get('value', 0))
        tier = line.get('tier', 'Common')

        is_good = stat in good_stats
        tier_score = {'Common': 1, 'Rare': 2, 'Epic': 3, 'Unique': 4, 'Legendary': 5, 'Mystic': 6}.get(tier, 1)

        if is_good:
            estimated_dps = value * 0.5  # Rough DPS contribution
        else:
            estimated_dps = value * 0.1

        total_dps += estimated_dps

        indicator = '🟢' if is_good and tier_score >= 4 else ('🟡' if is_good else '🔴')

        line_analysis.append({
            'line': i,
            'stat': stat or '(empty)',
            'value': value,
            'tier': tier,
            'dps': estimated_dps,
            'indicator': indicator,
        })

    weak_lines = [l for l in line_analysis if l['indicator'] == '🔴']

    return {
        'lines': line_analysis,
        'total_dps': total_dps,
        'weak_count': len(weak_lines),
        'recommendation': 'Lock good lines, reroll weak ones' if weak_lines else 'All lines good!',
    }


# ==============================================================================
# Main Page
# ==============================================================================
st.title("📈 Upgrade Path Optimizer")
st.markdown("Get intelligent recommendations for the most impactful upgrades based on efficiency and budget.")

# Current DPS display
current_stats = aggregate_stats()
current_dps = calculate_dps(current_stats, data.combat_mode)['total']

col1, col2 = st.columns([1, 2])
with col1:
    st.metric("Current DPS", f"{current_dps:,.0f}")
with col2:
    st.caption(f"Combat Mode: **{data.combat_mode.title()}**")

st.divider()

# ==============================================================================
# Budget Planning Section
# ==============================================================================
st.subheader("💰 Budget Planning")

budget = st.number_input(
    "Diamond Budget",
    min_value=0,
    max_value=10000000,
    value=100000,
    step=10000,
    help="Enter your available diamonds to get optimized upgrade path"
)

st.divider()

# ==============================================================================
# Cube Priority Analysis
# ==============================================================================
st.subheader("🎲 Cube Priority Analysis")

with st.spinner("Analyzing cube priorities..."):
    try:
        cube_recs = analyze_all_cube_priorities(
            user_data=data,
            aggregate_stats_func=aggregate_stats,
            calculate_dps_func=calculate_dps,
        )
    except Exception as e:
        st.error(f"Error analyzing cubes: {e}")
        cube_recs = []

if cube_recs:
    # Build table data
    cube_data = []
    for rec in cube_recs[:15]:  # Top 15
        pot_type = "Bonus" if rec.is_bonus else "Regular"
        diamond_cost = BONUS_DIAMOND_PER_CUBE if rec.is_bonus else REGULAR_DIAMOND_PER_CUBE

        # Score indicator
        score = rec.dps_efficiency
        if score < 30:
            indicator = "🔴"
        elif score < 60:
            indicator = "🟡"
        else:
            indicator = "🟢"

        # Format lines
        lines_str = ""
        for j, (stat, val) in enumerate([
            (rec.line1_stat, rec.line1_value),
            (rec.line2_stat, rec.line2_value),
            (rec.line3_stat, rec.line3_value)
        ]):
            if stat:
                lines_str += f"{format_stat_display(stat)}:{val:.0f} "

        expected_cost = rec.expected_cubes_to_improve * diamond_cost

        cube_data.append({
            "Rank": f"#{rec.priority_rank}",
            "Slot": f"{rec.slot.title()} ({pot_type})",
            "Tier": rec.tier,
            "Score": f"{indicator} {score:.0f}/100",
            "Lines": lines_str.strip() or "(empty)",
            "Cubes to Improve": f"~{rec.expected_cubes_to_improve:.0f}",
            "Est. Cost": f"{expected_cost:,.0f}💎",
            "Difficulty": rec.improvement_difficulty,
        })

    st.dataframe(cube_data, hide_index=True, use_container_width=True)

    # Detailed view for top 3
    with st.expander("🔍 Top 3 Cube Targets - Detailed Analysis"):
        for rec in cube_recs[:3]:
            pot_type = "Bonus" if rec.is_bonus else "Regular"
            col1, col2, col3 = st.columns([1, 2, 1])

            with col1:
                st.markdown(f"**#{rec.priority_rank} {rec.slot.title()} ({pot_type})**")
                st.caption(f"Tier: {rec.tier}")

            with col2:
                st.markdown("**Current Lines:**")
                for j, (stat, val, dps) in enumerate([
                    (rec.line1_stat, rec.line1_value, rec.line1_dps_gain),
                    (rec.line2_stat, rec.line2_value, rec.line2_dps_gain),
                    (rec.line3_stat, rec.line3_value, rec.line3_dps_gain)
                ], 1):
                    if stat:
                        st.caption(f"  L{j}: {format_stat_display(stat)} {val:.1f}% (+{dps:.2f}% DPS)")
                    else:
                        st.caption(f"  L{j}: (empty)")

            with col3:
                st.markdown("**Top Stats to Target:**")
                for stat_name, dps_gain, prob in rec.top_stats[:3]:
                    st.caption(f"  {stat_name}: +{dps_gain:.2f}%")

            st.markdown("---")
else:
    st.info("No cube analysis available. Make sure equipment potentials are configured.")

st.divider()

# ==============================================================================
# Starforce Analysis
# ==============================================================================
st.subheader("⭐ Starforce Analysis")

sf_upgrades = analyze_starforce_upgrades()

if sf_upgrades:
    sf_upgrades.sort(key=lambda x: x['efficiency'], reverse=True)

    sf_data = []
    for upg in sf_upgrades[:10]:
        sf_data.append({
            "Slot": upg['slot'].title(),
            "Current": upg['current'],
            "Target": upg['target'],
            "Cost": f"{upg['cost']:,.0f}💎",
            "DPS Gain": f"+{upg['dps_gain']:.2f}%",
            "Efficiency": f"{upg['efficiency']:.3f}",
            "Risk": upg['risk'],
        })

    st.dataframe(sf_data, hide_index=True, use_container_width=True)
else:
    st.success("All equipment is at max stars or below ★10!")

st.divider()

# ==============================================================================
# Hero Power Analysis
# ==============================================================================
st.subheader("⚡ Hero Power Analysis")

hp_analysis = analyze_hero_power_lines()

# Line-by-line breakdown
st.markdown("**Current Lines:**")
line_cols = st.columns(6)
for i, line in enumerate(hp_analysis['lines']):
    with line_cols[i]:
        st.markdown(f"**L{line['line']}** {line['indicator']}")
        st.caption(f"{line['stat']}")
        if line['value'] > 0:
            st.caption(f"{line['value']:.1f}%")
        st.caption(f"*{line['tier'][:3]}*")

st.markdown(f"**Total estimated DPS contribution:** +{hp_analysis['total_dps']:.1f}%")
st.markdown(f"**Weak lines:** {hp_analysis['weak_count']}")
st.info(f"💡 {hp_analysis['recommendation']}")

# Passive upgrades
hp_passives = analyze_hero_power_upgrades()
if hp_passives:
    st.markdown("**Passive Upgrade Opportunities:**")
    for upg in hp_passives:
        st.caption(f"• {upg['description']} - Est. +{upg['dps_gain']:.1f}% DPS for {upg['cost']:,.0f}💎")

st.divider()

# ==============================================================================
# Optimal Upgrade Path
# ==============================================================================
st.subheader("🎯 Recommended Upgrade Path")
st.caption(f"Budget: {budget:,} diamonds")

# Collect all upgrades
all_upgrades = []

# Add cube upgrades
for rec in cube_recs:
    pot_type = "Bonus" if rec.is_bonus else "Regular"
    diamond_cost = BONUS_DIAMOND_PER_CUBE if rec.is_bonus else REGULAR_DIAMOND_PER_CUBE
    cost = rec.expected_cubes_to_improve * diamond_cost

    # Estimate DPS gain based on improvement room
    improvement_room = rec.best_possible_dps_gain - rec.current_dps_gain
    dps_gain = improvement_room * 0.3  # Conservative estimate

    all_upgrades.append({
        'type': f'Cube ({pot_type})',
        'target': f'{rec.slot.title()}',
        'cost': cost,
        'dps_gain': dps_gain,
        'efficiency': (dps_gain / (cost / 1000)) if cost > 0 else 0,
        'description': f'{rec.slot.title()} {pot_type} potential ({rec.tier})',
        'difficulty': rec.improvement_difficulty,
    })

# Add starforce upgrades
for upg in sf_upgrades:
    all_upgrades.append({
        'type': 'Starforce',
        'target': upg['slot'],
        'cost': upg['cost'],
        'dps_gain': upg['dps_gain'],
        'efficiency': upg['efficiency'],
        'description': upg['description'],
        'difficulty': upg['risk'],
    })

# Add hero power passive upgrades
for upg in hp_passives:
    all_upgrades.append({
        'type': 'Hero Power',
        'target': 'passive',
        'cost': upg['cost'],
        'dps_gain': upg['dps_gain'],
        'efficiency': upg['efficiency'],
        'description': upg['description'],
        'difficulty': 'Safe',
    })

# Sort by efficiency and select within budget
all_upgrades.sort(key=lambda x: x['efficiency'], reverse=True)

selected = []
remaining = budget
used_targets = set()

for upg in all_upgrades:
    target_key = f"{upg['type']}_{upg['target']}"
    if target_key in used_targets:
        continue
    if upg['cost'] <= remaining and upg['cost'] > 0:
        selected.append(upg)
        remaining -= upg['cost']
        used_targets.add(target_key)

if selected:
    total_cost = sum(u['cost'] for u in selected)
    total_gain = sum(u['dps_gain'] for u in selected)

    st.success(f"**Optimal path found!** {len(selected)} upgrades for {total_cost:,.0f}💎 → +{total_gain:.1f}% DPS")

    path_data = []
    for i, upg in enumerate(selected, 1):
        path_data.append({
            "Order": i,
            "Type": upg['type'],
            "Description": upg['description'],
            "Cost": f"{upg['cost']:,.0f}💎",
            "DPS Gain": f"+{upg['dps_gain']:.2f}%",
            "Efficiency": f"{upg['efficiency']:.3f}",
        })

    st.dataframe(path_data, hide_index=True, use_container_width=True)

    st.caption(f"Remaining budget: {remaining:,.0f}💎")
else:
    st.warning("No upgrades fit within your budget. Try increasing your diamond budget.")

st.divider()

# ==============================================================================
# General Tips
# ==============================================================================
with st.expander("📚 Optimization Tips"):
    st.markdown("""
### Priority Order (General)
1. **Starforce to 15+** on all equipment (safe, good returns)
2. **Potential tier to Legendary+** for high-value slots
3. **Fill all potential lines** with good stats
4. **Hero Power passives** (Main Stat and Damage first)
5. **Potential quality** on key slots (Gloves, Cape, Shoulder)

### High-Value Potential Targets
| Slot | Best Stats |
|------|-----------|
| **Gloves** | Crit Damage (30% at Legendary) |
| **Cape/Bottom** | Final Damage (8% at Legendary) |
| **Shoulder** | Defense Pen (12% at Legendary) |
| **Ring/Necklace** | All Skills (+12 at Legendary) |
| **Hat** | Skill CD Reduction (2s at Mystic) |

### Efficiency Tips
- **Low score potentials** (🔴) are easy to improve
- **High score potentials** (🟢) have diminishing returns
- Focus on slots with **highest improvement room**
- Consider **pity progress** when deciding to cube

### Risk Management
- Starforce ★15+ has destruction risk
- Use protection scrolls for ★17+
- Budget for rebuilds when pushing high stars
""")
