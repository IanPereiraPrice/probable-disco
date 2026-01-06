"""
UNUSED/REFERENCE CODE - Custom cube analysis functions that were replaced by the original
cube_analyzer.py system from the Tkinter app.

These functions implemented a simpler approach to cube analysis but were not as accurate
as the original system which uses:
- create_item_score_result
- calculate_expected_cubes_fast
- calculate_efficiency_score
- calculate_stat_rankings

Kept for reference in case any of this logic is useful later.
"""

from typing import Dict, List, Any


def analyze_cube_priorities_detailed_UNUSED(baseline_dps: float, data, EQUIPMENT_SLOTS,
                                            get_potential_lines_summary, BONUS_DIAMOND_PER_CUBE,
                                            REGULAR_DIAMOND_PER_CUBE, aggregate_stats_without_potential_lines,
                                            aggregate_stats_with_perfect_lines, calculate_dps,
                                            SLOT_TARGET_STATS) -> List[Dict]:
    """
    Analyze cube priorities with detailed breakdown using REAL DPS calculations.

    Args:
        baseline_dps: The current total DPS (calculated once and passed in)

    NOTE: This was replaced by analyze_all_cube_priorities from cube_analyzer.py
    which uses the original Tkinter app's sophisticated scoring system.
    """
    results = []

    for slot in EQUIPMENT_SLOTS:
        for is_bonus in [False, True]:
            summary = get_potential_lines_summary(slot, is_bonus)
            pot_type = "Bonus" if is_bonus else "Regular"
            diamond_cost = BONUS_DIAMOND_PER_CUBE if is_bonus else REGULAR_DIAMOND_PER_CUBE

            # Calculate DPS WITHOUT these potential lines (baseline for this slot)
            stats_without_lines = aggregate_stats_without_potential_lines(slot, is_bonus)
            dps_without_lines = calculate_dps(stats_without_lines, data.combat_mode)['total']

            # Current DPS contribution from these lines
            if dps_without_lines > 0:
                current_dps_gain_pct = ((baseline_dps / dps_without_lines) - 1) * 100
            else:
                current_dps_gain_pct = 0

            # Calculate best possible DPS from perfect lines
            best_stats = aggregate_stats_with_perfect_lines(slot, is_bonus, summary['tier'])
            best_total_dps = calculate_dps(best_stats, data.combat_mode)['total']
            if dps_without_lines > 0:
                best_dps_gain_pct = ((best_total_dps / dps_without_lines) - 1) * 100
            else:
                best_dps_gain_pct = 0

            improvement_room = best_dps_gain_pct - current_dps_gain_pct

            # Score based on current vs best (0-100)
            if best_dps_gain_pct > 0:
                score = (current_dps_gain_pct / best_dps_gain_pct) * 100
            else:
                score = 100 if current_dps_gain_pct > 0 else 0

            score = max(0, min(100, score))

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
                'current_dps': current_dps_gain_pct,
                'best_dps': best_dps_gain_pct,
                'improvement_room': improvement_room,
                'score': score,
                'indicator': indicator,
                'cubes_to_improve': cubes_to_improve,
                'expected_cost': expected_cost,
                'expected_gain': expected_gain,
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


def aggregate_stats_without_potential_lines_UNUSED(slot: str, is_bonus: bool, data,
                                                    EQUIPMENT_SLOTS, get_amplify_multiplier) -> Dict[str, Any]:
    """
    Aggregate stats but exclude the specified potential lines.
    Used to calculate the baseline DPS without a specific potential's contribution.

    NOTE: The original Tkinter app does this differently - it temporarily modifies
    the equipment object's lines property instead of creating a new stats dict.
    """
    stats = {
        'flat_dex': 0, 'str_flat': 0, 'dex_percent': 0, 'damage_percent': 0,
        'damage_amp': 0, 'boss_damage': 0, 'normal_damage': 0, 'crit_damage': 0,
        'crit_rate': 0, 'min_dmg_mult': 0, 'max_dmg_mult': 0, 'base_attack': 0,
        'final_damage_sources': [], 'defense_pen_sources': [], 'attack_speed_sources': [],
    }

    def _add_stat(stat_type, value, source):
        if not stat_type or value <= 0:
            return
        stat_type_lower = stat_type.lower().replace(' ', '_')
        if stat_type_lower in ('damage', 'damage_percent', 'dmg', 'dmg%', 'damage_pct'):
            stats['damage_percent'] += value
        elif stat_type_lower in ('boss', 'boss_damage', 'boss_dmg', 'boss%'):
            stats['boss_damage'] += value
        elif stat_type_lower in ('normal', 'normal_damage', 'normal_dmg'):
            stats['normal_damage'] += value
        elif stat_type_lower in ('crit_rate', 'cr', 'crit%'):
            stats['crit_rate'] += value
        elif stat_type_lower in ('crit_damage', 'cd', 'crit_dmg'):
            stats['crit_damage'] += value
        elif stat_type_lower in ('def_pen', 'defense_pen', 'ied', 'ignore_defense'):
            stats['defense_pen_sources'].append(value / 100)
        elif stat_type_lower in ('final_damage', 'fd', 'final_dmg', 'final_atk_dmg'):
            stats['final_damage_sources'].append(value / 100)
        elif stat_type_lower in ('attack_speed', 'atk_spd', 'as'):
            stats['attack_speed_sources'].append((source, value))
        elif stat_type_lower in ('dex', 'dex%', 'dex_percent', 'main_stat_pct', 'dex_pct', 'str_pct', 'int_pct', 'luk_pct'):
            stats['dex_percent'] += value
        elif stat_type_lower in ('flat_dex', 'dex_flat', 'main_stat_flat', 'str_flat', 'int_flat', 'luk_flat'):
            stats['flat_dex'] += value
        elif stat_type_lower in ('min_dmg', 'min_damage', 'min_dmg_mult'):
            stats['min_dmg_mult'] += value
        elif stat_type_lower in ('max_dmg', 'max_damage', 'max_dmg_mult'):
            stats['max_dmg_mult'] += value
        elif stat_type_lower in ('damage_amp', 'dmg_amp'):
            stats['damage_amp'] += value

    # Equipment potentials - EXCLUDE the specified slot/type
    for eq_slot in EQUIPMENT_SLOTS:
        pots = data.equipment_potentials.get(eq_slot, {})
        for prefix in ['', 'bonus_']:
            skip_this = (eq_slot == slot and
                        ((is_bonus and prefix == 'bonus_') or (not is_bonus and prefix == '')))
            if skip_this:
                continue
            for i in range(1, 4):
                stat = pots.get(f'{prefix}line{i}_stat', '')
                value = float(pots.get(f'{prefix}line{i}_value', 0))
                _add_stat(stat, value, f'{eq_slot}_{prefix}pot')

    # Equipment base stats with starforce
    for eq_slot in EQUIPMENT_SLOTS:
        item = data.equipment_items.get(eq_slot, {})
        stars = int(item.get('stars', 0))
        main_mult = get_amplify_multiplier(stars, is_sub=False)
        sub_mult = get_amplify_multiplier(stars, is_sub=True)

        stats['base_attack'] += item.get('base_attack', 0) * main_mult
        stats['boss_damage'] += item.get('sub_boss_damage', 0) * sub_mult
        stats['normal_damage'] += item.get('sub_normal_damage', 0) * sub_mult
        stats['crit_rate'] += item.get('sub_crit_rate', 0) * sub_mult
        stats['crit_damage'] += item.get('sub_crit_damage', 0) * sub_mult
        stats['base_attack'] += item.get('sub_attack_flat', 0) * sub_mult

        if item.get('is_special', False):
            special_type = item.get('special_stat_type', 'damage_pct')
            special_value = item.get('special_stat_value', 0) * sub_mult
            if special_type == 'damage_pct':
                stats['damage_percent'] += special_value
            elif special_type == 'final_damage':
                stats['final_damage_sources'].append(special_value / 100)

        stats['flat_dex'] += item.get('dex', 0)
        stats['str_flat'] += item.get('str', 0)

    # Other stat sources (Hero Power, Maple Rank, Guild, etc.)
    for line_key, line in data.hero_power_lines.items():
        _add_stat(line.get('stat', ''), float(line.get('value', 0)), f'hp_{line_key}')

    passives = data.hero_power_passives
    stats['flat_dex'] += passives.get('main_stat', 0) * 100

    mr = data.maple_rank
    stats['flat_dex'] += (mr.get('current_stage', 1) - 1) * 100 + mr.get('main_stat_level', 0) * 10 + mr.get('special_main_stat', 0)
    stat_levels = mr.get('stat_levels', {})
    if isinstance(stat_levels, dict):
        if stat_levels.get('attack_speed', 0) > 0:
            stats['attack_speed_sources'].append(('MR', stat_levels.get('attack_speed', 0) * 0.5))
        stats['crit_rate'] += stat_levels.get('crit_rate', 0)
        stats['damage_percent'] += stat_levels.get('damage', 0) * 2
        stats['boss_damage'] += stat_levels.get('boss_damage', 0) * 2
        stats['normal_damage'] += stat_levels.get('normal_damage', 0) * 2
        stats['crit_damage'] += stat_levels.get('crit_damage', 0) * 2

    stats['flat_dex'] += data.equipment_sets.get('medal', 0) + data.equipment_sets.get('costume', 0)

    guild = getattr(data, 'guild', {})
    if guild.get('final_damage', 0) > 0:
        stats['final_damage_sources'].append(guild.get('final_damage', 0) / 100)
    stats['damage_percent'] += guild.get('damage', 0)
    stats['crit_rate'] += guild.get('crit_rate', 0)

    companions = getattr(data, 'companions', {})
    for comp_data in companions.values():
        if comp_data.get('equipped', False):
            stat_type = comp_data.get('on_equip_type', '')
            value = float(comp_data.get('on_equip_value', 0))
            if stat_type == 'attack_speed' and value > 0:
                stats['attack_speed_sources'].append(('Comp', value))
            else:
                _add_stat(stat_type, value, 'comp')

    return stats


def aggregate_stats_with_perfect_lines_UNUSED(slot: str, is_bonus: bool, tier: str,
                                               aggregate_stats_without_potential_lines_func,
                                               SLOT_TARGET_STATS) -> Dict[str, Any]:
    """
    Aggregate stats replacing specified potential lines with perfect lines for that tier/slot.

    NOTE: The original Tkinter app doesn't use this approach - instead it uses
    calculate_stat_rankings from cubes.py to determine the best stats by actual DPS gain.
    """
    stats = aggregate_stats_without_potential_lines_func(slot, is_bonus)

    target_stats = SLOT_TARGET_STATS.get(slot, ['damage', 'boss_damage', 'dex_pct'])
    tier_max = {
        'Mystic': {'damage': 12, 'boss_damage': 12, 'crit_damage': 8, 'def_pen': 12,
                   'final_atk_dmg': 8, 'dex_pct': 12, 'attack_pct': 12, 'min_dmg_mult': 10, 'max_dmg_mult': 10},
        'Legendary': {'damage': 9, 'boss_damage': 9, 'crit_damage': 6, 'def_pen': 9,
                      'final_atk_dmg': 6, 'dex_pct': 9, 'attack_pct': 9, 'min_dmg_mult': 7, 'max_dmg_mult': 7},
        'Unique': {'damage': 6, 'boss_damage': 6, 'crit_damage': 4, 'def_pen': 6,
                   'final_atk_dmg': 4, 'dex_pct': 6, 'attack_pct': 6, 'min_dmg_mult': 5, 'max_dmg_mult': 5},
        'Epic': {'damage': 4, 'boss_damage': 4, 'crit_damage': 3, 'dex_pct': 4, 'min_dmg_mult': 3},
        'Rare': {'damage': 3, 'boss_damage': 3, 'crit_damage': 2, 'dex_pct': 3, 'min_dmg_mult': 2},
    }
    tier_values = tier_max.get(tier, tier_max.get('Legendary', {}))

    for stat in target_stats[:3]:
        value = tier_values.get(stat, 6)
        stat_l = stat.lower()
        if stat_l in ('damage', 'damage_percent', 'dmg'):
            stats['damage_percent'] += value
        elif stat_l in ('boss', 'boss_damage'):
            stats['boss_damage'] += value
        elif stat_l in ('crit_damage', 'cd'):
            stats['crit_damage'] += value
        elif stat_l in ('def_pen', 'defense_pen'):
            stats['defense_pen_sources'].append(value / 100)
        elif stat_l in ('final_atk_dmg', 'final_damage', 'fd'):
            stats['final_damage_sources'].append(value / 100)
        elif stat_l in ('dex_pct', 'dex%', 'main_stat_pct'):
            stats['dex_percent'] += value
        elif stat_l in ('min_dmg_mult', 'min_dmg'):
            stats['min_dmg_mult'] += value
        elif stat_l in ('max_dmg_mult', 'max_dmg'):
            stats['max_dmg_mult'] += value

    return stats
