"""
Weapon Upgrade Optimizer
========================
Analyzes weapon upgrade efficiency and provides recommendations
for which weapons to level up based on DPS gain per diamond spent.

Key concepts:
- Only the equipped weapon gets full ATK% (on_equip + inventory)
- Non-equipped weapons only contribute inventory ATK% (~25%)
- Level cap = 100 + (awakening * 20), max 200
- DPS gain formula: atk_gain / (1 + total_atk%/100) due to diminishing returns
- Efficiency: DPS% gain per 1000 diamonds spent
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from weapons import (
    get_base_atk, get_level_multiplier, get_inventory_ratio,
    calculate_level_cost, DIAMONDS_TO_ENHANCERS, BASE_ATK
)


# =============================================================================
# CONSTANTS
# =============================================================================

MAX_WEAPON_LEVEL = 200
BASE_MAX_LEVEL = 100
LEVEL_PER_AWAKENING = 20


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def get_max_level(awakening: int) -> int:
    """
    Calculate max level based on awakening stages.

    Formula: max_level = 100 + (awakening * 20)
    - 0 awakening: max 100
    - 5 awakening: max 200
    """
    return min(BASE_MAX_LEVEL + awakening * LEVEL_PER_AWAKENING, MAX_WEAPON_LEVEL)


def calculate_atk_at_level(rarity: str, tier: int, level: int) -> float:
    """Calculate on-equip ATK% at a specific level."""
    if level <= 0:
        return 0.0
    base = get_base_atk(rarity, tier)
    multiplier = get_level_multiplier(level)
    return base * multiplier


def calculate_atk_gain_for_level(rarity: str, tier: int, from_level: int) -> float:
    """Calculate ATK% gain from leveling from from_level to from_level+1."""
    current = calculate_atk_at_level(rarity, tier, from_level)
    next_level = calculate_atk_at_level(rarity, tier, from_level + 1)
    return next_level - current


def calculate_total_weapon_atk_percent(
    weapons_data: Dict[str, Dict],
    equipped_key: str
) -> float:
    """
    Calculate total weapon ATK% from all weapons.

    Args:
        weapons_data: Dict mapping "rarity_tier" -> {level, awakening}
        equipped_key: Key of currently equipped weapon (e.g., "ancient_2")

    Returns:
        Total ATK% contribution from all weapons
    """
    total = 0.0

    for key, data in weapons_data.items():
        level = data.get('level', 0)
        if level <= 0:
            continue

        parts = key.rsplit('_', 1)
        if len(parts) != 2:
            continue

        rarity, tier = parts[0], int(parts[1])
        on_equip = calculate_atk_at_level(rarity, tier, level)
        inv_ratio = get_inventory_ratio(rarity)
        inventory = on_equip * inv_ratio

        if key == equipped_key:
            # Equipped weapon: full on-equip + inventory
            total += on_equip + inventory
        else:
            # Non-equipped: only inventory
            total += inventory

    return total


def calculate_dps_gain(atk_gain: float, current_total_atk_percent: float) -> float:
    """
    Calculate DPS% gain from ATK% increase, accounting for diminishing returns.

    Formula: dps_gain = atk_gain / (1 + total_atk%/100)

    This works because:
    - DPS = base_damage * (1 + total_atk%/100) * other_multipliers
    - d(DPS)/d(atk%) = base_damage * other_multipliers / 100
    - Relative DPS gain = atk_gain / (1 + total_atk%/100)
    """
    return atk_gain / (1 + current_total_atk_percent / 100)


def calculate_upgrade_cost_diamonds(rarity: str, tier: int, from_level: int) -> float:
    """Calculate cost in diamonds to level up once."""
    enhancers = calculate_level_cost(rarity, tier, from_level)
    return enhancers / DIAMONDS_TO_ENHANCERS


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class WeaponUpgradeRecommendation:
    """A single weapon upgrade recommendation."""
    weapon_key: str
    rarity: str
    tier: int
    current_level: int
    target_level: int
    max_level: int
    awakening: int

    # Stats
    atk_gain: float          # Total ATK% gained
    dps_gain_percent: float  # DPS% gain (after diminishing returns)

    # Costs
    cost_enhancers: int
    cost_diamonds: float

    # Efficiency
    efficiency: float        # DPS% gain per 1000 diamonds

    # Context
    is_equipped: bool
    uses_inventory_only: bool
    can_become_best: bool    # True if this weapon could overtake equipped
    crossover_level: Optional[int] = None  # Level at which it overtakes equipped

    # Stopping info
    stop_reason: str = ""    # Why to stop at target_level


@dataclass
class WeaponOptimizerResult:
    """Complete weapon optimization analysis."""
    recommendations: List[WeaponUpgradeRecommendation]
    current_total_atk_percent: float
    equipped_weapon_key: str
    best_weapon_key: str     # Which weapon has highest ATK% potential


# =============================================================================
# MAIN OPTIMIZER
# =============================================================================

def find_best_weapon_at_max_level(weapons_data: Dict[str, Dict]) -> Tuple[str, float]:
    """
    Find which owned weapon would be best if maxed out.

    Returns:
        (weapon_key, max_on_equip_atk%)
    """
    best_key = ""
    best_atk = 0.0

    for key, data in weapons_data.items():
        level = data.get('level', 0)
        if level <= 0:
            continue

        parts = key.rsplit('_', 1)
        if len(parts) != 2:
            continue

        rarity, tier = parts[0], int(parts[1])
        awakening = data.get('awakening', 0)
        max_level = get_max_level(awakening)

        max_atk = calculate_atk_at_level(rarity, tier, max_level)
        if max_atk > best_atk:
            best_atk = max_atk
            best_key = key

    return best_key, best_atk


def find_crossover_level(
    weapon_key: str,
    weapon_data: Dict,
    equipped_key: str,
    weapons_data: Dict[str, Dict]
) -> Optional[int]:
    """
    Find the level at which a weapon would overtake the currently equipped weapon.

    Returns:
        Level at which weapon_key would have higher on_equip ATK than equipped, or None
    """
    if weapon_key == equipped_key:
        return None

    # Get equipped weapon's max ATK
    eq_data = weapons_data.get(equipped_key, {})
    eq_level = eq_data.get('level', 0)
    eq_awakening = eq_data.get('awakening', 0)

    if eq_level <= 0:
        return 1  # Any weapon beats no weapon

    eq_parts = equipped_key.rsplit('_', 1)
    if len(eq_parts) != 2:
        return None

    eq_rarity, eq_tier = eq_parts[0], int(eq_parts[1])
    eq_max_level = get_max_level(eq_awakening)
    eq_max_atk = calculate_atk_at_level(eq_rarity, eq_tier, eq_max_level)

    # Check if this weapon can ever beat equipped weapon
    parts = weapon_key.rsplit('_', 1)
    if len(parts) != 2:
        return None

    rarity, tier = parts[0], int(parts[1])
    awakening = weapon_data.get('awakening', 0)
    max_level = get_max_level(awakening)

    # Binary search for crossover level
    for level in range(weapon_data.get('level', 1), max_level + 1):
        atk = calculate_atk_at_level(rarity, tier, level)
        if atk > eq_max_atk:
            return level

    return None  # Never crosses over


def analyze_single_weapon_upgrade(
    weapon_key: str,
    weapons_data: Dict[str, Dict],
    equipped_key: str,
    current_total_atk: float,
    levels_to_analyze: int = 1
) -> Optional[WeaponUpgradeRecommendation]:
    """
    Analyze upgrading a single weapon by a specified number of levels.

    Args:
        weapon_key: Weapon to analyze
        weapons_data: All weapon data
        equipped_key: Currently equipped weapon
        current_total_atk: Current total weapon ATK%
        levels_to_analyze: How many levels to consider upgrading

    Returns:
        WeaponUpgradeRecommendation or None if can't upgrade
    """
    data = weapons_data.get(weapon_key, {})
    current_level = data.get('level', 0)
    awakening = data.get('awakening', 0)

    if current_level <= 0:
        return None

    parts = weapon_key.rsplit('_', 1)
    if len(parts) != 2:
        return None

    rarity, tier = parts[0], int(parts[1])
    max_level = get_max_level(awakening)

    if current_level >= max_level:
        return None

    is_equipped = (weapon_key == equipped_key)
    inv_ratio = get_inventory_ratio(rarity)

    # Calculate target level (limited by max)
    target_level = min(current_level + levels_to_analyze, max_level)
    actual_levels = target_level - current_level

    if actual_levels <= 0:
        return None

    # Calculate ATK% gain
    atk_before = calculate_atk_at_level(rarity, tier, current_level)
    atk_after = calculate_atk_at_level(rarity, tier, target_level)
    on_equip_gain = atk_after - atk_before

    if is_equipped:
        # Equipped: gain full on_equip + inventory
        effective_atk_gain = on_equip_gain * (1 + inv_ratio)
    else:
        # Non-equipped: only inventory effect
        effective_atk_gain = on_equip_gain * inv_ratio

    # Calculate DPS gain (with diminishing returns)
    dps_gain = calculate_dps_gain(effective_atk_gain, current_total_atk)

    # Calculate cost
    total_enhancers = 0
    for lvl in range(current_level, target_level):
        total_enhancers += calculate_level_cost(rarity, tier, lvl)

    cost_diamonds = total_enhancers / DIAMONDS_TO_ENHANCERS

    # Calculate efficiency (DPS% per 1000 diamonds)
    efficiency = (dps_gain * 100 / cost_diamonds) * 1000 if cost_diamonds > 0 else 0

    # Check crossover potential for non-equipped weapons
    crossover_level = None
    can_become_best = False

    if not is_equipped:
        crossover_level = find_crossover_level(weapon_key, data, equipped_key, weapons_data)
        can_become_best = crossover_level is not None

    return WeaponUpgradeRecommendation(
        weapon_key=weapon_key,
        rarity=rarity,
        tier=tier,
        current_level=current_level,
        target_level=target_level,
        max_level=max_level,
        awakening=awakening,
        atk_gain=effective_atk_gain,
        dps_gain_percent=dps_gain * 100,
        cost_enhancers=total_enhancers,
        cost_diamonds=cost_diamonds,
        efficiency=efficiency,
        is_equipped=is_equipped,
        uses_inventory_only=not is_equipped,
        can_become_best=can_become_best,
        crossover_level=crossover_level,
    )


def analyze_all_weapon_upgrades(
    weapons_data: Dict[str, Dict],
    equipped_key: str,
    min_efficiency_threshold: float = 0.0
) -> WeaponOptimizerResult:
    """
    Analyze all weapon upgrade options and return ranked recommendations.

    Args:
        weapons_data: Dict mapping "rarity_tier" -> {level, awakening}
        equipped_key: Currently equipped weapon key
        min_efficiency_threshold: Minimum efficiency to include in results

    Returns:
        WeaponOptimizerResult with sorted recommendations
    """
    current_total_atk = calculate_total_weapon_atk_percent(weapons_data, equipped_key)
    best_key, _ = find_best_weapon_at_max_level(weapons_data)

    recommendations = []

    for weapon_key in weapons_data.keys():
        rec = analyze_single_weapon_upgrade(
            weapon_key,
            weapons_data,
            equipped_key,
            current_total_atk,
            levels_to_analyze=1
        )

        if rec and rec.efficiency >= min_efficiency_threshold:
            recommendations.append(rec)

    # Sort by efficiency (highest first)
    recommendations.sort(key=lambda r: r.efficiency, reverse=True)

    return WeaponOptimizerResult(
        recommendations=recommendations,
        current_total_atk_percent=current_total_atk,
        equipped_weapon_key=equipped_key,
        best_weapon_key=best_key,
    )


def generate_weapon_upgrade_path(
    weapons_data: Dict[str, Dict],
    equipped_key: str,
    budget_diamonds: float = 100000,
    stop_efficiency: float = 0.0
) -> List[WeaponUpgradeRecommendation]:
    """
    Generate optimal upgrade path up to a budget or efficiency threshold.

    This simulates upgrading weapons one level at a time, always picking
    the highest efficiency option, until budget is exhausted or efficiency
    drops below threshold.

    Args:
        weapons_data: Current weapon state (will be copied, not modified)
        equipped_key: Currently equipped weapon
        budget_diamonds: Maximum diamonds to spend
        stop_efficiency: Stop when best option drops below this efficiency

    Returns:
        List of upgrades in order they should be performed
    """
    import copy

    working_data = copy.deepcopy(weapons_data)
    working_equipped = equipped_key

    path = []
    spent = 0.0

    while spent < budget_diamonds:
        result = analyze_all_weapon_upgrades(working_data, working_equipped)

        if not result.recommendations:
            break

        best = result.recommendations[0]

        if best.efficiency < stop_efficiency:
            break

        if spent + best.cost_diamonds > budget_diamonds:
            break

        # Apply the upgrade
        path.append(best)
        spent += best.cost_diamonds

        # Update working data
        working_data[best.weapon_key]['level'] = best.target_level

        # Check if we should switch equipped weapon
        if best.can_become_best and best.crossover_level:
            if best.target_level >= best.crossover_level:
                working_equipped = best.weapon_key

    return path


def get_weapon_upgrade_for_optimizer(
    weapons_data: Dict[str, Dict],
    equipped_key: str
) -> List[Dict]:
    """
    Get weapon upgrades formatted for the main Upgrade Optimizer.

    Returns a list of dicts compatible with the existing upgrade format:
    {
        'type': 'Weapon',
        'description': str,
        'dps_gain': float (percentage),
        'cost': float (diamonds),
        'efficiency': float,
        ...
    }
    """
    result = analyze_all_weapon_upgrades(weapons_data, equipped_key)

    upgrades = []
    for rec in result.recommendations:
        equipped_str = " (Equipped)" if rec.is_equipped else " (Inventory only)"
        if rec.can_become_best and rec.crossover_level:
            equipped_str = f" (Can become best at Lv.{rec.crossover_level})"

        description = (
            f"{rec.rarity.capitalize()} T{rec.tier} "
            f"Lv.{rec.current_level} -> {rec.target_level}{equipped_str}"
        )

        upgrades.append({
            'type': 'Weapon',
            'subtype': rec.weapon_key,
            'description': description,
            'dps_gain': rec.dps_gain_percent,
            'cost': rec.cost_diamonds,
            'efficiency': rec.efficiency,
            'current_level': rec.current_level,
            'target_level': rec.target_level,
            'max_level': rec.max_level,
            'is_equipped': rec.is_equipped,
            'can_become_best': rec.can_become_best,
            'crossover_level': rec.crossover_level,
        })

    return upgrades


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("Weapon Optimizer Test")
    print("=" * 60)

    # Test data
    test_weapons = {
        "ancient_2": {"level": 50, "awakening": 3},
        "ancient_3": {"level": 80, "awakening": 2},
        "ancient_4": {"level": 100, "awakening": 5},
        "mystic_1": {"level": 120, "awakening": 4},
        "legendary_2": {"level": 60, "awakening": 1},
    }

    equipped = "ancient_2"

    print(f"\nEquipped: {equipped}")
    print(f"Weapons: {test_weapons}")

    # Test total ATK calculation
    total_atk = calculate_total_weapon_atk_percent(test_weapons, equipped)
    print(f"\nTotal Weapon ATK%: {total_atk:.1f}%")

    # Test upgrade analysis
    result = analyze_all_weapon_upgrades(test_weapons, equipped)

    print(f"\nBest weapon at max level: {result.best_weapon_key}")
    print(f"\nTop 5 Upgrade Recommendations:")
    print("-" * 60)

    for i, rec in enumerate(result.recommendations[:5], 1):
        status = "Equipped" if rec.is_equipped else "Inventory"
        print(f"{i}. {rec.rarity.capitalize()} T{rec.tier} Lv.{rec.current_level} -> {rec.target_level}")
        print(f"   Status: {status} | ATK gain: +{rec.atk_gain:.2f}%")
        print(f"   DPS gain: +{rec.dps_gain_percent:.4f}% | Cost: {rec.cost_diamonds:.1f} diamonds")
        print(f"   Efficiency: {rec.efficiency:.4f} DPS%/1000d")
        if rec.can_become_best:
            print(f"   ** Can become best at level {rec.crossover_level} **")
        print()

    # Test optimizer format
    print("\nOptimizer format output:")
    print("-" * 60)
    upgrades = get_weapon_upgrade_for_optimizer(test_weapons, equipped)
    for u in upgrades[:3]:
        print(f"  {u['description']}")
        print(f"    DPS: +{u['dps_gain']:.4f}% | Cost: {u['cost']:.1f}d | Eff: {u['efficiency']:.4f}")
