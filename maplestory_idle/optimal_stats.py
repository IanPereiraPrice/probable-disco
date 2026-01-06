# optimal_stats.py - Optimal Stat Distribution Calculator
# Calculates theoretically optimal stat allocation across all sources
# Accounts for diminishing returns, slot exclusivity, and stat source priority

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable, Any
from enum import Enum
import copy


# =============================================================================
# STAT CATEGORIES (How stats combine in DPS formula)
# =============================================================================

class StatCategory(Enum):
    """How stats combine in the DPS formula."""
    ADDITIVE_DAMAGE = "additive_damage"      # Damage%, Boss%, Normal% - sum then multiply
    ADDITIVE_CRIT = "additive_crit"          # CritDamage% - sum then multiply
    ADDITIVE_MAIN_STAT = "additive_main"     # DEX%, flat DEX - sum then multiply
    MULTIPLICATIVE_FD = "mult_fd"            # Final Damage - each source multiplies
    MULTIPLICATIVE_DEF = "mult_def"          # Defense Penetration - each source multiplies
    ADDITIVE_OTHER = "additive_other"        # Min/Max dmg, crit rate, etc.


# Map stat types to their category
STAT_CATEGORIES = {
    'damage': StatCategory.ADDITIVE_DAMAGE,
    'damage_pct': StatCategory.ADDITIVE_DAMAGE,
    'boss_damage': StatCategory.ADDITIVE_DAMAGE,
    'normal_damage': StatCategory.ADDITIVE_DAMAGE,
    'crit_damage': StatCategory.ADDITIVE_CRIT,
    'dex_pct': StatCategory.ADDITIVE_MAIN_STAT,
    'str_pct': StatCategory.ADDITIVE_MAIN_STAT,
    'int_pct': StatCategory.ADDITIVE_MAIN_STAT,
    'luk_pct': StatCategory.ADDITIVE_MAIN_STAT,
    'dex_flat': StatCategory.ADDITIVE_MAIN_STAT,
    'str_flat': StatCategory.ADDITIVE_MAIN_STAT,
    'final_damage': StatCategory.MULTIPLICATIVE_FD,
    'final_atk_dmg': StatCategory.MULTIPLICATIVE_FD,
    'def_pen': StatCategory.MULTIPLICATIVE_DEF,
    'min_dmg_mult': StatCategory.ADDITIVE_OTHER,
    'max_dmg_mult': StatCategory.ADDITIVE_OTHER,
    'crit_rate': StatCategory.ADDITIVE_OTHER,
    'attack_speed': StatCategory.ADDITIVE_OTHER,
    'all_skills': StatCategory.ADDITIVE_OTHER,
}


# =============================================================================
# STAT SOURCE DEFINITIONS
# =============================================================================

@dataclass
class StatSource:
    """A configurable stat source with constraints."""
    source_type: str            # "equipment_regular", "equipment_bonus", "hero_power", "artifact"
    source_id: str              # Unique identifier (e.g., "shoulder_reg_1", "hero_power_3")
    slot: Optional[str]         # Equipment slot if applicable
    line_num: int               # Line number (1-3 for equipment, 1-6 for hero power)

    # Stats available at this source
    available_stats: List[str]
    exclusive_stats: List[str]  # Stats ONLY available here (e.g., def_pen on shoulder)

    # Value ranges by stat and tier: {stat: {tier: max_value}}
    stat_max_values: Dict[str, Dict[str, float]]

    def get_max_value(self, stat: str, tier: str = "mystic") -> float:
        """Get maximum value for a stat at a tier."""
        if stat in self.stat_max_values:
            return self.stat_max_values[stat].get(tier, 0)
        return 0


@dataclass
class StatAllocation:
    """A single stat allocation to a source."""
    source_id: str
    source_type: str
    slot: Optional[str]
    stat_type: str
    value: float
    tier: str
    is_exclusive: bool
    max_possible: float
    efficiency_score: float = 0.0  # DPS per stat point at this source


@dataclass
class OptimalBuild:
    """Complete optimal stat distribution result."""
    allocations: List[StatAllocation]
    total_stats: Dict[str, float]  # Aggregated stats
    estimated_dps_gain: float      # Total % DPS from all allocations
    efficiency_by_source: Dict[str, float]  # Efficiency score per source
    tier_mode: str                 # "mystic" or "current"


# =============================================================================
# STAT RANGES BY SOURCE
# =============================================================================

# Equipment potential max values by tier
EQUIPMENT_POTENTIAL_VALUES = {
    # Regular stats available on all slots
    'damage': {'mystic': 35.0, 'legendary': 25.0, 'unique': 18.0, 'epic': 12.0},
    'dex_pct': {'mystic': 15.0, 'legendary': 12.0, 'unique': 9.0, 'epic': 6.0},
    'str_pct': {'mystic': 15.0, 'legendary': 12.0, 'unique': 9.0, 'epic': 6.0},
    'int_pct': {'mystic': 15.0, 'legendary': 12.0, 'unique': 9.0, 'epic': 6.0},
    'luk_pct': {'mystic': 15.0, 'legendary': 12.0, 'unique': 9.0, 'epic': 6.0},
    'boss_damage': {'mystic': 35.0, 'legendary': 25.0, 'unique': 18.0, 'epic': 12.0},
    'normal_damage': {'mystic': 35.0, 'legendary': 25.0, 'unique': 18.0, 'epic': 12.0},
    'crit_rate': {'mystic': 15.0, 'legendary': 12.0, 'unique': 9.0, 'epic': 6.0},
    'min_dmg_mult': {'mystic': 25.0, 'legendary': 15.0, 'unique': 10.0, 'epic': 8.0},
    'max_dmg_mult': {'mystic': 25.0, 'legendary': 15.0, 'unique': 10.0, 'epic': 8.0},
    'attack_speed': {'mystic': 10.0, 'legendary': 7.0, 'unique': 5.0, 'epic': 4.0},
    'dex_flat': {'mystic': 1000, 'legendary': 600, 'unique': 400, 'epic': 200},
}

# Slot-exclusive special potentials
SLOT_EXCLUSIVE_STATS = {
    'shoulder': {
        'def_pen': {'mystic': 20.0, 'legendary': 12.0, 'unique': 8.0}
    },
    'gloves': {
        'crit_damage': {'mystic': 50.0, 'legendary': 30.0, 'unique': 20.0}
    },
    'cape': {
        'final_atk_dmg': {'mystic': 12.0, 'legendary': 8.0, 'unique': 5.0}
    },
    'bottom': {
        'final_atk_dmg': {'mystic': 12.0, 'legendary': 8.0, 'unique': 5.0}
    },
    'ring': {
        'all_skills': {'mystic': 16, 'legendary': 12, 'unique': 8}
    },
    'necklace': {
        'all_skills': {'mystic': 16, 'legendary': 12, 'unique': 8}
    },
    'top': {
        'ba_targets': {'mystic': 3, 'legendary': 2, 'unique': 1}
    },
    'hat': {
        'skill_cd': {'mystic': 2.0, 'legendary': 1.5, 'unique': 1.0}
    },
    'belt': {
        'buff_duration': {'mystic': 20.0, 'legendary': 12.0, 'unique': 8.0}
    },
    'face': {
        'main_stat_per_level': {'mystic': 12, 'legendary': 8, 'unique': 5}
    },
}

# Hero Power stat ranges (max values at each tier)
HERO_POWER_VALUES = {
    'damage': {'mystic': 40.0, 'legendary': 25.0, 'unique': 18.0},
    'boss_damage': {'mystic': 40.0, 'legendary': 25.0, 'unique': 18.0},
    'normal_damage': {'mystic': 40.0, 'legendary': 25.0, 'unique': 18.0},
    'def_pen': {'mystic': 20.0, 'legendary': 14.0, 'unique': 10.0},
    'crit_damage': {'mystic': 30.0, 'legendary': 20.0, 'unique': 14.0},
    'max_dmg_mult': {'mystic': 40.0, 'legendary': 25.0, 'unique': 18.0},
    'min_dmg_mult': {'mystic': 40.0, 'legendary': 25.0, 'unique': 18.0},
    'crit_rate': {'mystic': 12.0, 'legendary': 8.0, 'unique': 5.0},
    'attack_pct': {'mystic': 18.0, 'legendary': 12.0, 'unique': 8.0},
    'main_stat_flat': {'mystic': 2500, 'legendary': 1200, 'unique': 700},
}

# Artifact potential stat ranges
ARTIFACT_POTENTIAL_VALUES = {
    'damage': {'mystic': 24.0, 'legendary': 14.0, 'unique': 9.0},
    'boss_damage': {'mystic': 24.0, 'legendary': 14.0, 'unique': 9.0},
    'normal_damage': {'mystic': 24.0, 'legendary': 14.0, 'unique': 9.0},
    'def_pen': {'mystic': 12.0, 'legendary': 7.0, 'unique': 4.5},
    'main_stat_pct': {'mystic': 12.0, 'legendary': 7.0, 'unique': 4.5},
    'crit_rate': {'mystic': 12.0, 'legendary': 7.0, 'unique': 4.5},
    'min_max_damage': {'mystic': 12.0, 'legendary': 7.0, 'unique': 4.5},
}


# =============================================================================
# EQUIPMENT SLOTS
# =============================================================================

EQUIPMENT_SLOTS = ['hat', 'top', 'bottom', 'gloves', 'shoes', 'belt',
                   'shoulder', 'cape', 'ring', 'necklace', 'face']


# =============================================================================
# SOURCE GENERATION
# =============================================================================

def generate_all_sources(include_artifacts: bool = True) -> List[StatSource]:
    """Generate all configurable stat sources."""
    sources = []

    # Equipment potentials (regular and bonus, 3 lines each)
    for slot in EQUIPMENT_SLOTS:
        # Get available stats for this slot
        base_stats = list(EQUIPMENT_POTENTIAL_VALUES.keys())
        exclusive_stats = list(SLOT_EXCLUSIVE_STATS.get(slot, {}).keys())

        # Build stat_max_values including exclusives
        stat_values = dict(EQUIPMENT_POTENTIAL_VALUES)
        if slot in SLOT_EXCLUSIVE_STATS:
            for stat, tiers in SLOT_EXCLUSIVE_STATS[slot].items():
                stat_values[stat] = tiers

        for pot_type in ['regular', 'bonus']:
            for line_num in range(1, 4):
                sources.append(StatSource(
                    source_type=f"equipment_{pot_type}",
                    source_id=f"{slot}_{pot_type}_{line_num}",
                    slot=slot,
                    line_num=line_num,
                    available_stats=base_stats + exclusive_stats,
                    exclusive_stats=exclusive_stats,
                    stat_max_values=stat_values,
                ))

    # Hero Power lines (6 lines)
    hp_stats = list(HERO_POWER_VALUES.keys())
    for line_num in range(1, 7):
        sources.append(StatSource(
            source_type="hero_power",
            source_id=f"hero_power_{line_num}",
            slot=None,
            line_num=line_num,
            available_stats=hp_stats,
            exclusive_stats=[],
            stat_max_values=HERO_POWER_VALUES,
        ))

    # Artifact potentials (3 artifacts × 3 lines = 9 lines, but simplified to 3 main)
    if include_artifacts:
        artifact_stats = list(ARTIFACT_POTENTIAL_VALUES.keys())
        for art_num in range(1, 4):
            for line_num in range(1, 4):
                sources.append(StatSource(
                    source_type="artifact",
                    source_id=f"artifact_{art_num}_line_{line_num}",
                    slot=None,
                    line_num=line_num,
                    available_stats=artifact_stats,
                    exclusive_stats=[],
                    stat_max_values=ARTIFACT_POTENTIAL_VALUES,
                ))

    return sources


# =============================================================================
# MARGINAL DPS CALCULATION
# =============================================================================

def calculate_marginal_dps_value(
    current_stats: Dict[str, float],
    stat_type: str,
    amount: float,
    calc_dps_func: Callable,
) -> float:
    """
    Calculate the % DPS gain from adding `amount` of `stat_type`.

    Args:
        current_stats: Current aggregated stats dict
        stat_type: The stat being added (e.g., 'damage', 'def_pen')
        amount: Amount of stat to add
        calc_dps_func: Function that calculates DPS from stats dict

    Returns:
        Percentage DPS gain (e.g., 2.5 means +2.5% DPS)
    """
    # Calculate baseline DPS
    baseline_dps = calc_dps_func(current_stats)
    if baseline_dps <= 0:
        return 0

    # Create modified stats with the new stat added
    modified_stats = copy.deepcopy(current_stats)

    # Map stat_type to the key in stats dict
    stat_key_map = {
        'damage': 'damage_percent',
        'damage_pct': 'damage_percent',
        'boss_damage': 'boss_damage',
        'normal_damage': 'normal_damage',
        'crit_damage': 'crit_damage',
        'def_pen': 'defense_pen',
        'dex_pct': 'dex_percent',
        'str_pct': 'dex_percent',  # Assume main stat
        'int_pct': 'dex_percent',
        'luk_pct': 'dex_percent',
        'dex_flat': 'flat_dex',
        'str_flat': 'flat_dex',
        'min_dmg_mult': 'min_dmg_mult',
        'max_dmg_mult': 'max_dmg_mult',
        'crit_rate': 'crit_rate',
        'attack_speed': 'attack_speed',
        'final_damage': 'final_damage',
        'final_atk_dmg': 'final_damage',
        'main_stat_flat': 'flat_dex',
        'main_stat_pct': 'dex_percent',
        'attack_pct': 'attack_percent',
    }

    stats_key = stat_key_map.get(stat_type, stat_type)

    # Add the stat (handle multiplicative vs additive)
    category = STAT_CATEGORIES.get(stat_type, StatCategory.ADDITIVE_OTHER)

    if category == StatCategory.MULTIPLICATIVE_DEF:
        # Defense penetration stacks multiplicatively
        # New total = 1 - (1 - current)(1 - new)
        current_val = modified_stats.get(stats_key, 0)
        current_remaining = 1 - (current_val / 100)
        new_remaining = current_remaining * (1 - amount / 100)
        modified_stats[stats_key] = (1 - new_remaining) * 100
    elif category == StatCategory.MULTIPLICATIVE_FD:
        # Final damage stacks multiplicatively
        current_val = modified_stats.get(stats_key, 0)
        current_mult = 1 + current_val / 100
        new_mult = current_mult * (1 + amount / 100)
        modified_stats[stats_key] = (new_mult - 1) * 100
    else:
        # Additive stats just sum
        modified_stats[stats_key] = modified_stats.get(stats_key, 0) + amount

    # Calculate new DPS
    new_dps = calc_dps_func(modified_stats)

    # Return percentage gain
    return ((new_dps / baseline_dps) - 1) * 100


def calculate_marginal_efficiency(
    current_stats: Dict[str, float],
    stat_type: str,
    amount: float,
    calc_dps_func: Callable,
) -> float:
    """
    Calculate efficiency: DPS gain per stat point.

    Higher efficiency = more valuable per unit.
    """
    if amount <= 0:
        return 0
    dps_gain = calculate_marginal_dps_value(current_stats, stat_type, amount, calc_dps_func)
    return dps_gain / amount


# =============================================================================
# SLOT EFFICIENCY ANALYSIS
# =============================================================================

def calculate_slot_efficiency(
    slot: str,
    current_stats: Dict[str, float],
    calc_dps_func: Callable,
    tier: str = "mystic",
    pot_type: str = "regular",
) -> List[Dict]:
    """
    Calculate efficiency of each stat option for a slot.

    Returns list of {stat, max_value, dps_gain, efficiency, is_exclusive}
    sorted by efficiency (highest first).
    """
    results = []

    # Get available stats for this slot
    base_stats = list(EQUIPMENT_POTENTIAL_VALUES.keys())
    exclusive = SLOT_EXCLUSIVE_STATS.get(slot, {})

    all_stats = {}
    for stat in base_stats:
        all_stats[stat] = EQUIPMENT_POTENTIAL_VALUES[stat].get(tier, 0)
    for stat, tiers in exclusive.items():
        all_stats[stat] = tiers.get(tier, 0)

    for stat, max_value in all_stats.items():
        if max_value <= 0:
            continue

        dps_gain = calculate_marginal_dps_value(
            current_stats, stat, max_value, calc_dps_func
        )
        efficiency = dps_gain / max_value if max_value > 0 else 0

        results.append({
            'stat': stat,
            'max_value': max_value,
            'dps_gain': dps_gain,
            'efficiency': efficiency,
            'is_exclusive': stat in exclusive,
        })

    # Sort by efficiency
    results.sort(key=lambda x: x['efficiency'], reverse=True)

    # Normalize efficiency to 0-100 scale
    if results:
        max_eff = results[0]['efficiency']
        for r in results:
            r['efficiency_normalized'] = (r['efficiency'] / max_eff * 100) if max_eff > 0 else 0

    return results


# =============================================================================
# SOURCE RANKING FOR A STAT
# =============================================================================

def calculate_source_ranking(
    stat_type: str,
    current_stats: Dict[str, float],
    calc_dps_func: Callable,
    tier: str = "mystic",
    include_artifacts: bool = True,
) -> List[Dict]:
    """
    Rank all sources that can provide a specific stat.

    Returns list of {source_type, source_id, slot, max_value, dps_gain, efficiency, is_exclusive}
    sorted by max_value (highest first - best source for this stat).
    """
    results = []

    # Check equipment slots
    for slot in EQUIPMENT_SLOTS:
        # Check if this slot can roll the stat
        exclusive = SLOT_EXCLUSIVE_STATS.get(slot, {})

        if stat_type in exclusive:
            max_value = exclusive[stat_type].get(tier, 0)
            is_exclusive = True
        elif stat_type in EQUIPMENT_POTENTIAL_VALUES:
            max_value = EQUIPMENT_POTENTIAL_VALUES[stat_type].get(tier, 0)
            is_exclusive = False
        else:
            continue

        if max_value > 0:
            dps_gain = calculate_marginal_dps_value(
                current_stats, stat_type, max_value, calc_dps_func
            )

            results.append({
                'source_type': 'equipment',
                'source_id': f"{slot}_potential",
                'slot': slot,
                'max_value': max_value,
                'dps_gain': dps_gain,
                'efficiency': dps_gain / max_value if max_value > 0 else 0,
                'is_exclusive': is_exclusive,
            })

    # Check hero power
    if stat_type in HERO_POWER_VALUES:
        max_value = HERO_POWER_VALUES[stat_type].get(tier, 0)
        if max_value > 0:
            dps_gain = calculate_marginal_dps_value(
                current_stats, stat_type, max_value, calc_dps_func
            )
            results.append({
                'source_type': 'hero_power',
                'source_id': 'hero_power_line',
                'slot': None,
                'max_value': max_value,
                'dps_gain': dps_gain,
                'efficiency': dps_gain / max_value if max_value > 0 else 0,
                'is_exclusive': False,
            })

    # Check artifacts
    if include_artifacts and stat_type in ARTIFACT_POTENTIAL_VALUES:
        max_value = ARTIFACT_POTENTIAL_VALUES[stat_type].get(tier, 0)
        if max_value > 0:
            dps_gain = calculate_marginal_dps_value(
                current_stats, stat_type, max_value, calc_dps_func
            )
            results.append({
                'source_type': 'artifact',
                'source_id': 'artifact_potential',
                'slot': None,
                'max_value': max_value,
                'dps_gain': dps_gain,
                'efficiency': dps_gain / max_value if max_value > 0 else 0,
                'is_exclusive': False,
            })

    # Sort by max_value (best source first)
    results.sort(key=lambda x: x['max_value'], reverse=True)

    # Add rank
    for i, r in enumerate(results):
        r['rank'] = i + 1

    return results


# =============================================================================
# OPTIMAL DISTRIBUTION CALCULATION
# =============================================================================

def calculate_optimal_distribution(
    base_stats: Dict[str, float],
    calc_dps_func: Callable,
    tier_mode: str = "mystic",
    include_artifacts: bool = True,
    max_iterations: int = 500,
) -> OptimalBuild:
    """
    Calculate theoretically optimal stat distribution using greedy marginal value.

    Args:
        base_stats: Fixed stats from non-configurable sources
        calc_dps_func: Function to calculate DPS from stats
        tier_mode: "mystic" for theoretical max, or tier name for constrained
        include_artifacts: Whether to include artifact potentials
        max_iterations: Maximum allocation iterations

    Returns:
        OptimalBuild with allocations and analysis
    """
    sources = generate_all_sources(include_artifacts)
    current_stats = copy.deepcopy(base_stats)
    allocations = []
    used_sources = set()  # Track which source_ids have been allocated

    for iteration in range(max_iterations):
        best_option = None
        best_efficiency = -1

        for source in sources:
            if source.source_id in used_sources:
                continue

            # For each available stat at this source
            for stat in source.available_stats:
                max_value = source.get_max_value(stat, tier_mode)
                if max_value <= 0:
                    continue

                # Calculate marginal efficiency
                efficiency = calculate_marginal_efficiency(
                    current_stats, stat, max_value, calc_dps_func
                )

                # Boost exclusive stats (they should always go to their slot)
                if stat in source.exclusive_stats:
                    efficiency *= 1.5  # Prioritize exclusives

                if efficiency > best_efficiency:
                    best_efficiency = efficiency
                    best_option = (source, stat, max_value, efficiency)

        if best_option is None:
            break

        source, stat, value, eff = best_option

        # Apply allocation
        dps_gain = calculate_marginal_dps_value(current_stats, stat, value, calc_dps_func)

        # Update current stats
        stat_key_map = {
            'damage': 'damage_percent',
            'boss_damage': 'boss_damage',
            'crit_damage': 'crit_damage',
            'def_pen': 'defense_pen',
            'dex_pct': 'dex_percent',
            'min_dmg_mult': 'min_dmg_mult',
            'max_dmg_mult': 'max_dmg_mult',
            'final_atk_dmg': 'final_damage',
        }
        stats_key = stat_key_map.get(stat, stat)
        current_stats[stats_key] = current_stats.get(stats_key, 0) + value

        # Record allocation
        allocations.append(StatAllocation(
            source_id=source.source_id,
            source_type=source.source_type,
            slot=source.slot,
            stat_type=stat,
            value=value,
            tier=tier_mode,
            is_exclusive=stat in source.exclusive_stats,
            max_possible=value,
            efficiency_score=eff,
        ))

        used_sources.add(source.source_id)

    # Calculate total DPS gain
    total_dps_gain = sum(
        calculate_marginal_dps_value(base_stats, a.stat_type, a.value, calc_dps_func)
        for a in allocations
    )

    # Build efficiency map
    efficiency_by_source = {a.source_id: a.efficiency_score for a in allocations}

    return OptimalBuild(
        allocations=allocations,
        total_stats=current_stats,
        estimated_dps_gain=total_dps_gain,
        efficiency_by_source=efficiency_by_source,
        tier_mode=tier_mode,
    )


# =============================================================================
# CURRENT VS OPTIMAL COMPARISON
# =============================================================================

def compare_current_to_optimal(
    current_allocations: List[Dict],  # User's current stat choices
    optimal_build: OptimalBuild,
    calc_dps_func: Callable,
    base_stats: Dict[str, float],
) -> Dict:
    """
    Compare user's current build to optimal.

    Returns:
        Dict with gap analysis and recommendations
    """
    # Calculate current DPS
    current_stats = copy.deepcopy(base_stats)
    for alloc in current_allocations:
        stat_key = alloc.get('stat_key', alloc.get('stat'))
        value = alloc.get('value', 0)
        current_stats[stat_key] = current_stats.get(stat_key, 0) + value

    current_dps = calc_dps_func(current_stats)
    optimal_dps = calc_dps_func(optimal_build.total_stats)

    dps_gap = ((optimal_dps / current_dps) - 1) * 100 if current_dps > 0 else 0

    # Find slots that differ from optimal
    priority_fixes = []

    # Group optimal allocations by slot
    optimal_by_slot = {}
    for alloc in optimal_build.allocations:
        if alloc.slot:
            if alloc.slot not in optimal_by_slot:
                optimal_by_slot[alloc.slot] = []
            optimal_by_slot[alloc.slot].append(alloc)

    # Compare each slot
    for slot, optimal_allocs in optimal_by_slot.items():
        # Find what user has for this slot
        current_slot_stats = [a for a in current_allocations if a.get('slot') == slot]

        # Calculate gap for this slot
        optimal_slot_dps = sum(a.efficiency_score * a.value for a in optimal_allocs)
        current_slot_dps = sum(a.get('efficiency', 0) * a.get('value', 0) for a in current_slot_stats)

        gap = optimal_slot_dps - current_slot_dps
        if gap > 0.1:  # Meaningful gap
            priority_fixes.append({
                'slot': slot,
                'gap_score': gap,
                'optimal_stats': [a.stat_type for a in optimal_allocs],
                'current_stats': [a.get('stat') for a in current_slot_stats],
            })

    # Sort by gap
    priority_fixes.sort(key=lambda x: x['gap_score'], reverse=True)

    return {
        'current_dps': current_dps,
        'optimal_dps': optimal_dps,
        'dps_gap_percent': dps_gap,
        'priority_fixes': priority_fixes[:10],  # Top 10 fixes
    }


# =============================================================================
# HELPER: GET OPTIMAL STAT FOR SLOT
# =============================================================================

def get_optimal_stat_for_slot(
    slot: str,
    current_stats: Dict[str, float],
    calc_dps_func: Callable,
    tier: str = "mystic",
) -> Dict:
    """
    Get the single best stat for a slot given current stats.

    Returns dict with best stat info.
    """
    efficiency = calculate_slot_efficiency(slot, current_stats, calc_dps_func, tier)

    if efficiency:
        best = efficiency[0]
        return {
            'slot': slot,
            'best_stat': best['stat'],
            'max_value': best['max_value'],
            'dps_gain': best['dps_gain'],
            'efficiency': best['efficiency'],
            'is_exclusive': best['is_exclusive'],
            'all_options': efficiency[:5],  # Top 5 options
        }

    return {'slot': slot, 'best_stat': None}


# =============================================================================
# FORMAT HELPERS
# =============================================================================

STAT_DISPLAY_NAMES = {
    'damage': 'Damage %',
    'damage_pct': 'Damage %',
    'boss_damage': 'Boss Damage %',
    'normal_damage': 'Normal Damage %',
    'crit_damage': 'Crit Damage %',
    'def_pen': 'Defense Pen %',
    'dex_pct': 'DEX %',
    'str_pct': 'STR %',
    'int_pct': 'INT %',
    'luk_pct': 'LUK %',
    'dex_flat': 'DEX Flat',
    'min_dmg_mult': 'Min Damage %',
    'max_dmg_mult': 'Max Damage %',
    'crit_rate': 'Crit Rate %',
    'attack_speed': 'Attack Speed %',
    'final_atk_dmg': 'Final Damage %',
    'final_damage': 'Final Damage %',
    'all_skills': 'All Skills',
    'ba_targets': 'BA Targets',
    'skill_cd': 'Skill CD (sec)',
    'buff_duration': 'Buff Duration %',
    'main_stat_per_level': 'Main Stat/Level',
}


def format_stat_name(stat: str) -> str:
    """Get display name for a stat."""
    return STAT_DISPLAY_NAMES.get(stat, stat.replace('_', ' ').title())


def format_allocation_summary(allocations: List[StatAllocation]) -> str:
    """Format allocations as readable summary."""
    lines = []

    # Group by slot
    by_slot = {}
    for a in allocations:
        key = a.slot or a.source_type
        if key not in by_slot:
            by_slot[key] = []
        by_slot[key].append(a)

    for key, allocs in sorted(by_slot.items()):
        stats = [f"{format_stat_name(a.stat_type)} {a.value:.0f}%" for a in allocs]
        lines.append(f"{key.title()}: {' > '.join(stats)}")

    return "\n".join(lines)
