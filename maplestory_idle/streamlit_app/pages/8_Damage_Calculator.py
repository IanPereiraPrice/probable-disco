"""
Damage Calculator Page
Calculate DPS based on all configured stats.
"""
import streamlit as st
from utils.data_manager import save_user_data, EQUIPMENT_SLOTS

st.set_page_config(page_title="Damage Calculator", page_icon="💥", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

# Constants
HEX_MULTIPLIER = 1.24
BASE_MIN_DMG = 60.0
BASE_MAX_DMG = 100.0
BASE_CRIT_DMG = 30.0


def aggregate_stats():
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

    # Equipment potentials
    for slot in EQUIPMENT_SLOTS:
        pots = data.equipment_potentials.get(slot, {})
        for i in range(1, 4):
            stat = pots.get(f'line{i}_stat', '')
            value = float(pots.get(f'line{i}_value', 0))

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
            elif stat == 'main_stat_flat':
                stats['flat_dex'] += value
            elif stat == 'main_stat_pct':
                stats['dex_percent'] += value
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
    stats['flat_dex'] += passives.get('main_stat', 0) * 100  # Approximate
    stats['damage_percent'] += passives.get('damage', 0) * 2  # Approximate

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

    # Weapons
    for weapon in data.weapons.values():
        stats['base_attack'] *= (1 + weapon.get('atk_pct', 0) / 100)

    return stats


def calculate_dps(stats, combat_mode='stage', enemy_def=0.752):
    """Calculate DPS from stats."""
    # DEX multiplier
    total_dex = stats['flat_dex'] * (1 + stats['dex_percent'] / 100)
    stat_multiplier = 1 + (total_dex / 10000)

    # Damage multiplier with hex
    hex_mult = HEX_MULTIPLIER ** 3  # Assume max stacks
    total_damage_pct = (stats['damage_percent'] / 100) * hex_mult
    base_damage_mult = 1 + total_damage_pct

    # Combat mode weighting
    if combat_mode in ('boss', 'world_boss'):
        damage_multiplier = base_damage_mult * (1 + stats['boss_damage'] / 100)
    else:
        normal_weight = 0.60
        boss_weight = 0.40
        mult_vs_normal = base_damage_mult * (1 + stats['normal_damage'] / 100)
        mult_vs_boss = base_damage_mult * (1 + stats['boss_damage'] / 100)
        damage_multiplier = (normal_weight * mult_vs_normal) + (boss_weight * mult_vs_boss)

    # Final damage (multiplicative)
    fd_multiplier = 1 + stats['final_damage'] / 100

    # Crit damage
    total_crit_dmg = BASE_CRIT_DMG + stats['crit_damage']
    crit_multiplier = 1 + (total_crit_dmg / 100)

    # Defense penetration
    def_pen_decimal = stats['defense_pen'] / 100
    defense_multiplier = 1 / (1 + enemy_def * (1 - def_pen_decimal))

    # Min/Max damage range
    final_min = BASE_MIN_DMG + stats['min_dmg_mult']
    final_max = BASE_MAX_DMG + stats['max_dmg_mult']
    avg_mult = (final_min + final_max) / 2
    dmg_range_mult = avg_mult / 100

    # Attack speed
    atk_spd_mult = 1 + (stats['attack_speed'] / 100)

    # Base attack
    base_atk = max(stats['base_attack'], 10000)  # Minimum for calculation

    # Total DPS
    total = (base_atk * stat_multiplier * damage_multiplier *
             fd_multiplier * crit_multiplier * defense_multiplier *
             dmg_range_mult * atk_spd_mult)

    return {
        'total': total,
        'stat_mult': stat_multiplier,
        'damage_mult': damage_multiplier,
        'fd_mult': fd_multiplier,
        'crit_mult': crit_multiplier,
        'def_mult': defense_multiplier,
        'range_mult': dmg_range_mult,
        'speed_mult': atk_spd_mult,
    }


st.title("💥 Damage Calculator")
st.markdown("Calculate your DPS based on all configured stats.")

# Aggregate stats
stats = aggregate_stats()

# Calculate DPS
combat_mode = data.combat_mode
result = calculate_dps(stats, combat_mode)

# Display DPS
col1, col2 = st.columns([2, 1])

with col1:
    st.metric("Total DPS", f"{result['total']:,.0f}")

with col2:
    st.metric("Combat Mode", combat_mode.replace("_", " ").title())

st.divider()

# Multiplier breakdown
st.subheader("Damage Multipliers")

mult_cols = st.columns(4)

with mult_cols[0]:
    st.metric("Stat (DEX)", f"x{result['stat_mult']:.2f}")
    st.metric("Damage %", f"x{result['damage_mult']:.2f}")

with mult_cols[1]:
    st.metric("Final Damage", f"x{result['fd_mult']:.2f}")
    st.metric("Crit Damage", f"x{result['crit_mult']:.2f}")

with mult_cols[2]:
    st.metric("Defense Pen", f"x{result['def_mult']:.3f}")
    st.metric("Dmg Range", f"x{result['range_mult']:.2f}")

with mult_cols[3]:
    st.metric("Attack Speed", f"x{result['speed_mult']:.2f}")

st.divider()

# Stat summary
st.subheader("Aggregated Stats")

stat_col1, stat_col2, stat_col3 = st.columns(3)

with stat_col1:
    st.markdown("**Main Stats**")
    st.write(f"Flat DEX: {stats['flat_dex']:,.0f}")
    st.write(f"DEX %: {stats['dex_percent']:.1f}%")
    st.write(f"Base Attack: {stats['base_attack']:,.0f}")

with stat_col2:
    st.markdown("**Damage Stats**")
    st.write(f"Damage %: {stats['damage_percent']:.1f}%")
    st.write(f"Boss Damage %: {stats['boss_damage']:.1f}%")
    st.write(f"Normal Damage %: {stats['normal_damage']:.1f}%")
    st.write(f"Crit Damage %: {stats['crit_damage']:.1f}%")
    st.write(f"Final Damage %: {stats['final_damage']:.1f}%")

with stat_col3:
    st.markdown("**Other Stats**")
    st.write(f"Defense Pen %: {stats['defense_pen']:.1f}%")
    st.write(f"Crit Rate %: {stats['crit_rate']:.1f}%")
    st.write(f"Min Dmg Mult %: {stats['min_dmg_mult']:.1f}%")
    st.write(f"Max Dmg Mult %: {stats['max_dmg_mult']:.1f}%")
    st.write(f"Attack Speed %: {stats['attack_speed']:.1f}%")

st.divider()

# Stat priority recommendations
st.subheader("Stat Priority Recommendations")
st.info("""
Based on your current stats, here are general recommendations:
- **Low on Damage %?** Focus on Damage % potentials and Hero Power lines
- **Low on Boss/Normal %?** Prioritize based on your combat mode
- **Low on Crit Damage?** Great value if you have high crit rate
- **Low on Final Damage?** Very valuable as it's multiplicative
- **Low on Defense Pen?** Important for higher chapter progression
""")
