"""
Artifact Optimizer - DPS efficiency calculations for artifact upgrades.

Integrates with Upgrade Optimizer using same DPS% per 1000 diamonds metric
as cube, starforce, and weapon upgrade recommendations.

Key features:
1. Awakening efficiency (star upgrades)
2. Chest expected value (what each chest is worth)
3. Resonance leveling efficiency
4. Artifact potential rerolling recommendations

All efficiencies are calculated as: DPS% gain per 1000 diamonds
"""

from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass
from copy import deepcopy

from stat_names import (
    DAMAGE_PCT, BOSS_DAMAGE, NORMAL_DAMAGE, CRIT_RATE, DEF_PEN,
    MIN_DMG_MULT, MAX_DMG_MULT, DEFENSE, ACCURACY,
    get_main_stat_flat_key, get_main_stat_pct_key,
)

from artifacts import (
    ARTIFACTS,
    ARTIFACT_DROP_RATES,
    ARTIFACT_TIER_DROP_RATES,
    AWAKENING_COSTS_BY_TIER,
    TOTAL_DUPLICATES_BY_TIER,
    RECONFIGURE_COSTS,
    POTENTIAL_SLOT_UNLOCKS,
    POTENTIAL_TIER_RATES,
    POTENTIAL_STAT_RATES,
    POTENTIAL_VALUES,
    PREMIUM_STATS,
    MAX_POTENTIAL_SLOTS_BY_TIER,
    MYSTIC_LOW_VALUE_CHANCE,
    MYSTIC_HIGH_VALUE_CHANCE,
    ArtifactTier,
    PotentialTier,
    ArtifactPotentialLine,
    ArtifactEffect,
    EffectType,
    calculate_resonance_hp,
    calculate_resonance_main_stat,
    calculate_resonance_upgrade_cost,
    calculate_resonance_max_level,
    calculate_hex_multiplier,
    calculate_book_of_ancient_bonus,
)


# =============================================================================
# CONSTANTS
# =============================================================================

# Diamond conversion rates
CHEST_COST_BLUE = 1500  # Blue diamonds per artifact chest
CHEST_COST_RED = 1500   # Red diamonds per artifact chest
CHEST_COST_ARENA = 500  # Arena coins per artifact chest (converted to diamonds)

# Artifact enhancer exchange rate: 1,500 diamonds = 10,000 enhancers
ENHANCER_EXCHANGE_RATE = 1500 / 10000  # 0.15 diamonds per enhancer

# Meso to diamond conversion (approximate, used for reconfigure cost)
MESO_TO_DIAMOND = 0.004

# Number of equipped artifact slots
EQUIPPED_SLOTS = 3

# Hexagon Necklace stack mechanics
HEX_SECONDS_PER_STACK = 20  # Gain 1 stack every 20 seconds
HEX_MAX_STACKS = 3


@dataclass
class ScenarioConfig:
    """Configuration for a combat scenario."""
    name: str
    duration: float  # Fight duration in seconds
    description: str = ""


# Combat scenario configurations with duration as an attribute
# 'chapter_hunt' uses infinite duration:
# - Cycling buffs (buff+cooldown) maintain their cycle rate
# - Hex Necklace uses max 3 stacks
# - One-time buffs (like Rainbow Snail Shell 15s) approach 0% uptime
# - Uses 50/50 normal/boss split and current stage defense
SCENARIO_CONFIGS = {
    'normal': ScenarioConfig(name='normal', duration=35, description='Normal stage farming'),
    'boss': ScenarioConfig(name='boss', duration=75, description='Boss stage'),
    'world_boss': ScenarioConfig(name='world_boss', duration=75, description='World boss'),
    'guild': ScenarioConfig(name='guild', duration=75, description='Guild content'),
    'arena': ScenarioConfig(name='arena', duration=60, description='Arena PvP'),
    'chapter': ScenarioConfig(name='chapter', duration=60, description='Chapter content'),
    'growth': ScenarioConfig(name='growth', duration=60, description='Growth content'),
    'chapter_hunt': ScenarioConfig(
        name='chapter_hunt',
        duration=float('inf'),
        description='Chapter Hunt (infinite, 50/50 normal/boss, current stage defense)'
    ),
}


def get_scenario_duration(scenario: str) -> float:
    """Get the fight duration for a given scenario."""
    config = SCENARIO_CONFIGS.get(scenario)
    if config:
        return config.duration
    return 35  # Default to normal stage duration


def calculate_average_hex_stacks(duration: float) -> float:
    """
    Calculate time-weighted average Hexagon Necklace stacks for a given fight duration.

    Hex gains 1 stack every 20 seconds, max 3 stacks.

    Examples:
        - 35s fight: 0-20s=0 stacks, 20-35s=1 stack → avg = (20*0 + 15*1) / 35 = 0.43
        - 75s fight: 0-20s=0, 20-40s=1, 40-60s=2, 60-75s=3 → avg = 1.4
        - infinite: always at max stacks → 3.0

    Args:
        duration: Fight duration in seconds (can be float('inf'))

    Returns:
        Average number of stacks over the fight duration
    """
    import math

    if duration <= 0:
        return 0.0

    # At infinite duration, always at max stacks
    if math.isinf(duration):
        return float(HEX_MAX_STACKS)

    total_weighted_stacks = 0.0

    for stack_num in range(HEX_MAX_STACKS + 1):
        # Time when we reach this stack count
        stack_start = stack_num * HEX_SECONDS_PER_STACK
        # Time when we would reach the next stack
        next_stack_time = (stack_num + 1) * HEX_SECONDS_PER_STACK

        if stack_start >= duration:
            break  # Fight ends before reaching this stack level

        # Time spent at this stack level
        time_at_this_stack = min(next_stack_time, duration) - stack_start
        total_weighted_stacks += stack_num * time_at_this_stack

    return total_weighted_stacks / duration


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ArtifactAwakeningRecommendation:
    """Recommendation for awakening an artifact."""
    artifact_key: str
    artifact_name: str
    tier: ArtifactTier
    current_stars: int
    target_stars: int

    # Value breakdown
    inventory_gain: float      # DPS% from inventory effect
    active_gain: float         # DPS% from active effect (if equipped)
    resonance_gain: float      # DPS% from +5 resonance cap
    potential_slot_gain: float # DPS% from new potential slot (if unlocked)
    total_dps_gain: float      # Total DPS% gain

    # Cost
    dupes_needed: int
    expected_chests: float
    diamond_cost: float

    # Efficiency
    efficiency: float          # DPS% per 1000 diamonds

    # Context
    is_equipped: bool
    unlocks_potential_slot: bool


@dataclass
class ResonanceLevelingRecommendation:
    """Recommendation for leveling resonance."""
    current_level: int
    target_level: int
    max_level: int

    # Stats
    main_stat_gain: int
    hp_gain: int

    # Cost
    enhancer_cost: int
    diamond_cost: float

    # DPS impact
    dps_gain: float
    efficiency: float


@dataclass
class ChestExpectedValue:
    """Expected value analysis for artifact chests."""
    expected_dps_per_chest: float
    cost_per_chest: float
    efficiency: float  # DPS% per 1000 diamonds

    # Breakdown by contribution source
    breakdown: List[Dict[str, Any]]


@dataclass
class ArtifactRerollRecommendation:
    """Recommendation for rerolling artifact potentials."""
    artifact_key: str
    artifact_name: str

    # Current state
    current_dps_gain: float
    current_percentile: float
    num_slots: int

    # Expected improvement
    expected_dps_gain: float
    expected_rerolls: float

    # Cost
    cost_per_reroll: float
    total_cost: float

    # Efficiency
    efficiency: float


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_reconfigure_diamond_cost(tier: ArtifactTier) -> float:
    """Calculate diamond equivalent cost for reconfiguring artifact potential."""
    cost = RECONFIGURE_COSTS.get(tier, RECONFIGURE_COSTS[ArtifactTier.LEGENDARY])
    return (
        cost['meso'] * MESO_TO_DIAMOND +
        cost['artifact_enhancers'] * ENHANCER_EXCHANGE_RATE
    )


def get_potential_slots_at_stars(stars: int, tier: ArtifactTier) -> int:
    """Get number of potential slots available at given star level."""
    base_slots = POTENTIAL_SLOT_UNLOCKS.get(stars, 0)
    # Non-legendary artifacts cap at 2 slots
    if tier != ArtifactTier.LEGENDARY and base_slots > 2:
        return 2
    return base_slots


def unlocks_potential_slot(current_stars: int, target_stars: int, tier: ArtifactTier) -> bool:
    """Check if upgrading from current to target stars unlocks a new potential slot."""
    current_slots = get_potential_slots_at_stars(current_stars, tier)
    target_slots = get_potential_slots_at_stars(target_stars, tier)
    return target_slots > current_slots


# =============================================================================
# DPS IMPACT CALCULATIONS
# =============================================================================

def calculate_inventory_effect_dps(
    artifact_key: str,
    stars: int,
    current_stats: Dict[str, Any],
    calculate_dps_func: Callable,
) -> float:
    """
    Calculate DPS% contribution from an artifact's inventory effect.

    Args:
        artifact_key: The artifact identifier
        stars: Current awakening level
        current_stats: Current character stats dict
        calculate_dps_func: Function to calculate DPS from stats

    Returns:
        DPS percentage contribution
    """
    if artifact_key not in ARTIFACTS:
        return 0.0

    definition = ARTIFACTS[artifact_key]
    inv_value = definition.get_inventory_value(stars)
    inv_stat = definition.inventory_stat

    # Get baseline DPS
    baseline_result = calculate_dps_func(current_stats, 'stage')
    baseline_dps = baseline_result.get('total', 1)

    # Calculate DPS with this inventory effect added
    test_stats = deepcopy(current_stats)
    if inv_stat.endswith('_flat'):
        # Flat stat addition (no conversion needed)
        base_stat = inv_stat.replace('_flat', '')
        if base_stat == 'attack':
            # 'attack_flat' maps to 'base_attack' in DPS calc
            test_stats['base_attack'] = test_stats.get('base_attack', 0) + inv_value
        else:
            test_stats[base_stat] = test_stats.get(base_stat, 0) + inv_value
    else:
        # Percentage stat - need to convert decimal to percentage points
        # Artifact uses 0.30 for 30%, DPS calc uses 30.0
        # Map to correct DPS calc stat names
        stat_mapping = {
            'damage': 'damage_percent',
            'crit_rate': 'crit_rate',
            'crit_damage': 'crit_damage',
            'boss_damage': 'boss_damage',
            'normal_damage': 'normal_damage',
            'max_damage_mult': 'max_dmg_mult',
            'basic_attack_damage': 'basic_attack_damage',
            'def_pen': 'def_pen',
            'final_damage': 'final_damage',
        }
        mapped_stat = stat_mapping.get(inv_stat, inv_stat)

        # Stats that need decimal→percentage conversion
        percentage_stats = {
            'crit_rate', 'crit_damage', 'boss_damage', 'normal_damage',
            'damage_percent', 'max_dmg_mult', 'basic_attack_damage',
        }

        if inv_stat in percentage_stats or mapped_stat in percentage_stats:
            converted_value = inv_value * 100
        else:
            # def_pen, final_damage stay as decimals
            converted_value = inv_value

        test_stats[mapped_stat] = test_stats.get(mapped_stat, 0) + converted_value

    new_result = calculate_dps_func(test_stats, 'stage')
    new_dps = new_result.get('total', baseline_dps)

    if baseline_dps > 0:
        return ((new_dps / baseline_dps) - 1) * 100
    return 0.0


def calculate_active_effect_dps(
    artifact_key: str,
    stars: int,
    current_stats: Dict[str, Any],
    calculate_dps_func: Callable,
    scenario: str = 'chapter_hunt',
) -> float:
    """
    Calculate DPS% contribution from an artifact's active effect when equipped.

    Uses the real DPS calculator to properly evaluate effect value.
    Handles both legacy single-stat and new active_effects formats.

    Args:
        artifact_key: The artifact identifier
        stars: Current awakening level
        current_stats: Current character stats dict
        calculate_dps_func: Function to calculate DPS from stats
        scenario: Combat scenario for uptime calculation

    Returns:
        DPS percentage contribution (with uptime factored in)
    """
    if artifact_key not in ARTIFACTS:
        return 0.0

    definition = ARTIFACTS[artifact_key]

    # Check if artifact applies to this scenario
    if not definition.applies_to_scenario(scenario):
        return 0.0

    # Get baseline DPS
    baseline_result = calculate_dps_func(current_stats, 'stage')
    baseline_dps = baseline_result.get('total', 1)

    # Calculate uptime based on scenario duration
    fight_duration = get_scenario_duration(scenario)
    uptime = definition.get_effective_uptime(fight_duration)

    # Build stats with active effects applied
    # IMPORTANT: Use deepcopy to avoid modifying the original current_stats
    # (shallow copy shares list objects like attack_speed_sources)
    test_stats = deepcopy(current_stats)

    # Special handling for Book of Ancient:
    # The DPS calculator handles CR→CD conversion via book_of_ancient_stars
    # So we just need to set that value and let calculate_dps handle it
    if artifact_key == 'book_of_ancient':
        test_stats['book_of_ancient_stars'] = stars
        # Also add the flat crit rate bonus from the active effect
        for effect in definition.active_effects:
            if effect.effect_type == EffectType.FLAT and effect.stat == 'crit_rate':
                cr_bonus = effect.get_value(stars) * uptime * 100  # Convert to percentage points
                test_stats['crit_rate'] = test_stats.get('crit_rate', 0) + cr_bonus
                break
        # Calculate DPS with Book equipped
        new_result = calculate_dps_func(test_stats, 'stage')
        new_dps = new_result.get('total', baseline_dps)
        if baseline_dps > 0:
            return ((new_dps / baseline_dps) - 1) * 100
        return 0.0

    # All artifacts now use active_effects format
    if not definition.active_effects:
        # No active effects defined - return baseline
        return 0.0

    # First pass: collect flat values (needed for derived calculations)
    flat_values = {}
    for effect in definition.active_effects:
        if effect.effect_type == EffectType.FLAT:
            value = effect.get_value(stars) * uptime
            # Handle per-target effects (Fire Flower)
            if effect.max_stacks > 0 and effect.stat == 'final_damage':
                # Use average of 5 targets (stage estimate)
                value = value * min(5, effect.max_stacks)
            flat_values[effect.stat] = value
            _apply_stat_to_dict(test_stats, effect.stat, value)

        elif effect.effect_type == EffectType.MULTIPLICATIVE:
            # Hex Necklace: Set hex_multiplier directly (DPS calc applies it separately)
            if artifact_key == 'hexagon_necklace':
                from artifacts import calculate_hex_average_multiplier
                fight_duration = get_scenario_duration(scenario)
                hex_mult = calculate_hex_average_multiplier(stars, fight_duration)
                test_stats['hex_multiplier'] = hex_mult
            else:
                # Other multiplicative effects (if any)
                fight_duration = get_scenario_duration(scenario)
                if effect.max_stacks > 1:
                    avg_stacks = calculate_average_hex_stacks(fight_duration)
                    value = effect.get_value(stars, stacks=1) * avg_stacks * uptime
                else:
                    value = effect.get_value(stars) * uptime
                _apply_stat_to_dict(test_stats, effect.stat, value)

    # Second pass: derived effects
    for effect in definition.active_effects:
        if effect.effect_type == EffectType.DERIVED:
            conversion_rate = effect.get_value(stars)
            source_stat = effect.derived_from

            # Get source value from test_stats (which now includes flat effects added in first pass)
            source_value = 0.0

            if source_stat == 'crit_rate':
                # Crit rate is stored directly as percentage points
                source_value = test_stats.get('crit_rate', 0) / 100
            elif source_stat == 'attack_speed':
                # Attack speed is stored as a list of (source, value) tuples
                # The first pass already added the artifact's attack_speed to this list
                atk_spd_sources = test_stats.get('attack_speed_sources', [])
                if atk_spd_sources:
                    # Sum all sources (each value is already in percentage form)
                    total_atk_spd = sum(val for _, val in atk_spd_sources)
                    source_value = total_atk_spd / 100  # Convert to decimal
            else:
                # For other stats, use flat_values (what artifact added) + existing stats
                source_value = flat_values.get(source_stat, 0) + test_stats.get(source_stat, 0)

            derived_value = conversion_rate * source_value * uptime
            _apply_stat_to_dict(test_stats, effect.stat, derived_value)

    # Calculate new DPS
    new_result = calculate_dps_func(test_stats, 'stage')
    new_dps = new_result.get('total', baseline_dps)

    if baseline_dps > 0:
        return ((new_dps / baseline_dps) - 1) * 100
    return 0.0


def _apply_stat_to_dict(stats: Dict[str, Any], stat: str, value: float) -> None:
    """
    Helper to apply a stat value to the stats dict correctly.

    IMPORTANT: The DPS calculator expects most stats in PERCENTAGE POINTS
    (e.g., 50.0 for 50%), but artifact definitions store values as DECIMALS
    (e.g., 0.50 for 50%). This function handles the conversion.

    Uses standard stat names from stat_names.py.
    """
    from stat_names import (
        DAMAGE_PCT, ATTACK_PCT, CRIT_RATE, CRIT_DAMAGE, BOSS_DAMAGE,
        NORMAL_DAMAGE, MAX_DMG_MULT, MIN_DMG_MULT, DEF_PEN, FINAL_DAMAGE,
        ATTACK_SPEED, BUFF_DURATION, SKILL_CD,
    )

    # Utility stats that don't affect DPS - skip silently
    utility_stats = {
        BUFF_DURATION, 'hp_recovery', 'hp_mp_recovery',
        'companion_duration', 'cooldown_reduction', 'utility',
    }
    if stat in utility_stats:
        return

    # Special handling: final_damage and enemy_damage_taken go to final_damage_sources LIST
    if stat in (FINAL_DAMAGE, 'final_damage', 'enemy_damage_taken'):
        if 'final_damage_sources' not in stats:
            stats['final_damage_sources'] = []
        if value > 0:
            stats['final_damage_sources'].append(value)
        return

    # Special handling: attack_speed goes to attack_speed_sources LIST
    if stat in (ATTACK_SPEED, 'attack_speed'):
        if 'attack_speed_sources' not in stats:
            stats['attack_speed_sources'] = []
        if value > 0:
            stats['attack_speed_sources'].append(('artifact_effect', value * 100))
        return

    # Artifact-specific stat name translations (only non-standard names)
    artifact_stat_mapping = {
        'damage': DAMAGE_PCT,               # artifact 'damage' -> standard 'damage_pct'
        'attack_buff': ATTACK_PCT,          # artifact 'attack_buff' -> standard 'attack_pct'
        'max_damage_mult': MAX_DMG_MULT,    # artifact 'max_damage_mult' -> standard 'max_dmg_mult'
    }

    # Get the standard stat name (pass through if already standard)
    mapped_stat = artifact_stat_mapping.get(stat, stat)

    # Stats that need decimal→percentage conversion (* 100)
    percentage_stats = {
        CRIT_RATE, CRIT_DAMAGE, BOSS_DAMAGE, NORMAL_DAMAGE,
        DAMAGE_PCT, ATTACK_PCT, MAX_DMG_MULT, MIN_DMG_MULT,
        'damage', 'attack_buff', 'max_damage_mult',  # artifact names too
    }

    # Stats that stay as decimals (no conversion)
    decimal_stats = {DEF_PEN, 'def_pen'}

    # Convert to percentage points if needed
    if stat in percentage_stats or mapped_stat in percentage_stats:
        converted_value = value * 100
    elif stat in decimal_stats or mapped_stat in decimal_stats:
        converted_value = value
    else:
        converted_value = value * 100

    stats[mapped_stat] = stats.get(mapped_stat, 0) + converted_value


def calculate_resonance_stat_value(
    levels: int,
    current_level: int,
    current_stats: Dict[str, Any],
    calculate_dps_func: Callable,
) -> float:
    """
    Calculate DPS% value of gaining resonance levels.

    Args:
        levels: Number of levels gained
        current_level: Current resonance level
        current_stats: Current character stats
        calculate_dps_func: DPS calculation function

    Returns:
        DPS percentage gain from resonance levels
    """
    if levels <= 0:
        return 0.0

    # Calculate stat gains
    old_main = calculate_resonance_main_stat(current_level)
    new_main = calculate_resonance_main_stat(current_level + levels)
    main_gain = new_main - old_main

    old_hp = calculate_resonance_hp(current_level)
    new_hp = calculate_resonance_hp(current_level + levels)
    hp_gain = new_hp - old_hp

    # Get baseline DPS
    baseline_result = calculate_dps_func(current_stats, 'stage')
    baseline_dps = baseline_result.get('total', 1)

    # Add resonance stats
    test_stats = deepcopy(current_stats)
    # aggregate_stats() uses 'flat_dex' for main stat (DEX for Bowmaster)
    test_stats['flat_dex'] = test_stats.get('flat_dex', 0) + main_gain
    # HP doesn't directly affect DPS, but keep for completeness
    test_stats['max_hp'] = test_stats.get('max_hp', 0) + hp_gain

    new_result = calculate_dps_func(test_stats, 'stage')
    new_dps = new_result.get('total', baseline_dps)

    if baseline_dps > 0:
        return ((new_dps / baseline_dps) - 1) * 100
    return 0.0


def calculate_potential_slot_expected_value(
    tier: ArtifactTier,
    is_equipped: bool,
    current_stats: Dict[str, Any],
    calculate_dps_func: Callable,
) -> float:
    """
    Calculate expected DPS% value of a new potential slot.

    For equipped artifacts: Full potential value with DPS stats
    For inventory artifacts: Reduced value (only inventory effects count)

    Uses expected value over all possible potential rolls.
    """
    # Calculate expected DPS contribution from one potential slot
    # E[DPS] = Σ (P(tier) × P(stat) × E[value|tier,stat] × DPS_impact)

    total_ev = 0.0

    for pot_tier, tier_prob in POTENTIAL_TIER_RATES.items():
        for stat_key, stat_prob in POTENTIAL_STAT_RATES.items():
            # Get value range for this tier/stat combo
            values = POTENTIAL_VALUES.get(stat_key, {}).get(pot_tier)
            if not values:
                continue

            low_val, high_val = values
            # For Mystic: 75% low, 25% high
            if pot_tier == PotentialTier.MYSTIC and low_val != high_val:
                expected_val = low_val * 0.75 + high_val * 0.25
            else:
                expected_val = (low_val + high_val) / 2

            # Check if this stat provides DPS value
            dps_stats = {'damage', 'boss_damage', 'normal_damage', 'crit_rate',
                        'crit_damage', 'def_pen', 'main_stat', 'min_damage_mult',
                        'max_damage_mult'}

            if stat_key in dps_stats:
                # Weight by how impactful this stat is
                # This is a simplification - real impact depends on current stats
                impact_weights = {
                    'damage': 1.0,
                    'boss_damage': 0.8,  # Only for bosses
                    'normal_damage': 0.5,  # Only for normals
                    'def_pen': 1.2,  # Very valuable
                    'crit_rate': 0.6,  # Often capped
                    'crit_damage': 0.8,
                    'main_stat': 0.3,  # Less impactful %
                    'min_damage_mult': 0.4,
                    'max_damage_mult': 0.4,
                }
                weight = impact_weights.get(stat_key, 0.5)

                # Convert to DPS%
                # Rough approximation: 1% damage ≈ 1% DPS
                # Premium stats have higher values but premium weight
                dps_contribution = expected_val * weight * 0.01 * 100  # Back to %

                total_ev += tier_prob * stat_prob * dps_contribution

    # If not equipped, potential provides reduced value
    # (only contributes to inventory totals, not active)
    if not is_equipped:
        total_ev *= 0.3  # 30% of equipped value

    return total_ev


# =============================================================================
# AWAKENING EFFICIENCY
# =============================================================================

def calculate_awakening_efficiency(
    artifact_key: str,
    current_stars: int,
    is_equipped: bool,
    current_stats: Dict[str, Any],
    current_resonance_level: int,
    calculate_dps_func: Callable,
    scenario: str = 'chapter_hunt',
) -> Optional[ArtifactAwakeningRecommendation]:
    """
    Calculate efficiency of awakening an artifact by one star.

    Args:
        scenario: Combat scenario to evaluate. Defaults to 'chapter_hunt'.
                  Scenario-restricted artifacts only count active effects
                  when their scenario matches.

    Returns recommendation with DPS gain breakdown and efficiency score.
    """
    if artifact_key not in ARTIFACTS:
        return None

    definition = ARTIFACTS[artifact_key]
    tier = definition.tier

    # Check if already maxed
    if current_stars >= 5:
        return None

    target_stars = current_stars + 1

    # Calculate dupes needed and cost
    tier_costs = AWAKENING_COSTS_BY_TIER.get(tier, AWAKENING_COSTS_BY_TIER[ArtifactTier.LEGENDARY])
    dupes_needed = tier_costs.get(target_stars, 1)

    drop_rate = ARTIFACT_DROP_RATES.get(artifact_key, 0.01)
    expected_chests = dupes_needed / drop_rate if drop_rate > 0 else float('inf')
    diamond_cost = expected_chests * CHEST_COST_BLUE

    # Calculate DPS gains from each source using the actual DPS calculator

    # 1. Inventory effect improvement (per star)
    # Calculate DPS with old vs new inventory value using real DPS calc
    old_inv_dps = calculate_inventory_effect_dps(
        artifact_key=artifact_key,
        stars=current_stars,
        current_stats=current_stats,
        calculate_dps_func=calculate_dps_func,
    )
    new_inv_dps = calculate_inventory_effect_dps(
        artifact_key=artifact_key,
        stars=target_stars,
        current_stats=current_stats,
        calculate_dps_func=calculate_dps_func,
    )
    inv_dps_gain = new_inv_dps - old_inv_dps

    # 2. Active effect improvement (if equipped AND scenario matches)
    # Scenario-restricted artifacts only count active effects in their scenario
    if is_equipped and definition.applies_to_scenario(scenario):
        old_active_dps = calculate_active_effect_dps(
            artifact_key=artifact_key,
            stars=current_stars,
            current_stats=current_stats,
            calculate_dps_func=calculate_dps_func,
            scenario=scenario,
        )
        new_active_dps = calculate_active_effect_dps(
            artifact_key=artifact_key,
            stars=target_stars,
            current_stats=current_stats,
            calculate_dps_func=calculate_dps_func,
            scenario=scenario,
        )
        active_dps_gain = new_active_dps - old_active_dps
    else:
        active_dps_gain = 0.0

    # 3. Resonance cap increase (+5 levels per star)
    # Value depends on whether player can use those levels
    resonance_dps_gain = calculate_resonance_stat_value(
        levels=5,
        current_level=current_resonance_level,
        current_stats=current_stats,
        calculate_dps_func=calculate_dps_func,
    )

    # 4. Potential slot unlock (at ★1, ★3, ★5)
    unlocks_slot = unlocks_potential_slot(current_stars, target_stars, tier)
    if unlocks_slot:
        potential_dps_gain = calculate_potential_slot_expected_value(
            tier=tier,
            is_equipped=is_equipped,
            current_stats=current_stats,
            calculate_dps_func=calculate_dps_func,
        )
    else:
        potential_dps_gain = 0.0

    # Total DPS gain
    total_dps_gain = inv_dps_gain + active_dps_gain + resonance_dps_gain + potential_dps_gain

    # Efficiency: DPS% per 1000 diamonds
    efficiency = total_dps_gain / (diamond_cost / 1000) if diamond_cost > 0 else 0.0

    return ArtifactAwakeningRecommendation(
        artifact_key=artifact_key,
        artifact_name=definition.name,
        tier=tier,
        current_stars=current_stars,
        target_stars=target_stars,
        inventory_gain=inv_dps_gain,
        active_gain=active_dps_gain,
        resonance_gain=resonance_dps_gain,
        potential_slot_gain=potential_dps_gain,
        total_dps_gain=total_dps_gain,
        dupes_needed=dupes_needed,
        expected_chests=expected_chests,
        diamond_cost=diamond_cost,
        efficiency=efficiency,
        is_equipped=is_equipped,
        unlocks_potential_slot=unlocks_slot,
    )


# =============================================================================
# RESONANCE LEVELING EFFICIENCY
# =============================================================================

def calculate_resonance_leveling_efficiency(
    current_level: int,
    max_level: int,
    current_stats: Dict[str, Any],
    calculate_dps_func: Callable,
    levels_to_check: int = 10,
) -> Optional[ResonanceLevelingRecommendation]:
    """
    Calculate efficiency of leveling resonance.

    Evaluates leveling by 'levels_to_check' levels and returns best option.
    """
    if current_level >= max_level:
        return None

    # Calculate for a batch of levels (to amortize small gains)
    target_level = min(current_level + levels_to_check, max_level)
    actual_levels = target_level - current_level

    if actual_levels <= 0:
        return None

    # Calculate stat gains
    main_gain = calculate_resonance_main_stat(target_level) - calculate_resonance_main_stat(current_level)
    hp_gain = calculate_resonance_hp(target_level) - calculate_resonance_hp(current_level)

    # Calculate cost (sum of upgrade costs for each level)
    total_enhancer_cost = sum(
        calculate_resonance_upgrade_cost(lvl)
        for lvl in range(current_level, target_level)
    )
    diamond_cost = total_enhancer_cost * ENHANCER_EXCHANGE_RATE

    # Calculate DPS gain
    dps_gain = calculate_resonance_stat_value(
        levels=actual_levels,
        current_level=current_level,
        current_stats=current_stats,
        calculate_dps_func=calculate_dps_func,
    )

    # Efficiency
    efficiency = dps_gain / (diamond_cost / 1000) if diamond_cost > 0 else 0.0

    return ResonanceLevelingRecommendation(
        current_level=current_level,
        target_level=target_level,
        max_level=max_level,
        main_stat_gain=main_gain,
        hp_gain=hp_gain,
        enhancer_cost=total_enhancer_cost,
        diamond_cost=diamond_cost,
        dps_gain=dps_gain,
        efficiency=efficiency,
    )


# =============================================================================
# CHEST EXPECTED VALUE
# =============================================================================

def calculate_dupe_value(
    artifact_key: str,
    current_stars: int,
    current_dupes: int,
    full_star_value: float,
) -> float:
    """
    Calculate value of getting one more duplicate of an artifact.

    If at ★2 needing 3 dupes for ★3, each dupe is worth 1/3 of ★3 value.
    """
    if artifact_key not in ARTIFACTS:
        return 0.0

    definition = ARTIFACTS[artifact_key]
    tier = definition.tier

    if current_stars >= 5:
        return 0.0  # Already maxed

    next_star = current_stars + 1
    tier_costs = AWAKENING_COSTS_BY_TIER.get(tier, AWAKENING_COSTS_BY_TIER[ArtifactTier.LEGENDARY])
    dupes_needed = tier_costs.get(next_star, 1)

    # Value of one dupe = (full star value) / (dupes needed)
    return full_star_value / dupes_needed if dupes_needed > 0 else 0.0


def calculate_new_artifact_value(
    artifact_key: str,
    current_stats: Dict[str, Any],
    calculate_dps_func: Callable,
    scenario: str = 'chapter_hunt',
    include_active: bool = False,
) -> float:
    """
    Calculate DPS% value of obtaining an artifact for the first time.

    Includes:
    - Base inventory effect (★0)
    - Active effect at ★0 (if include_active=True and artifact applies to scenario)

    Args:
        artifact_key: The artifact identifier
        current_stats: Current character stats dict
        calculate_dps_func: Function to calculate DPS from stats
        scenario: Combat scenario for active effect evaluation
        include_active: Whether to include active effect value (for top N artifacts)
    """
    if artifact_key not in ARTIFACTS:
        return 0.0

    definition = ARTIFACTS[artifact_key]

    # Base inventory effect at ★0
    inv_value = definition.get_inventory_value(0)
    if definition.inventory_stat.endswith('_flat'):
        inv_dps = inv_value / 1000 * 100 * 0.01
    else:
        inv_dps = inv_value * 100

    # Active effect at ★0 (if this would be a top artifact)
    active_dps = 0.0
    if include_active and definition.applies_to_scenario(scenario):
        active_dps = calculate_active_effect_dps(
            artifact_key=artifact_key,
            stars=0,
            current_stats=current_stats,
            calculate_dps_func=calculate_dps_func,
            scenario=scenario,
        )

    # Base resonance (1 star worth = 5 levels)
    # New artifact at ★0 doesn't add resonance until awakened

    return inv_dps + active_dps


def calculate_chest_expected_value(
    owned_artifacts: Dict[str, Dict],
    equipped_artifact_keys: List[str],
    current_stats: Dict[str, Any],
    current_resonance_level: int,
    calculate_dps_func: Callable,
    scenario: str = 'chapter_hunt',
    top_n: int = 5,
) -> ChestExpectedValue:
    """
    Calculate expected DPS value from opening one artifact chest.

    E[value] = Σ (drop_rate × artifact_value)

    Active effects are only counted for artifacts that would be in the top N
    for the current scenario. This prevents overvaluing artifacts that would
    never actually be equipped.

    Args:
        owned_artifacts: Dict mapping artifact_key to {'stars': int, 'dupes': int}
        equipped_artifact_keys: List of artifact keys currently equipped
        current_stats: Current character stats
        current_resonance_level: Current resonance level
        calculate_dps_func: DPS calculation function
        scenario: Combat scenario for active effect evaluation
        top_n: Number of top artifacts to consider for active effects (default 5)

    Returns:
        ChestExpectedValue with breakdown
    """
    total_ev = 0.0
    breakdown = []

    # Get current artifact ranking for this scenario to determine top N
    current_ranking = get_artifact_ranking_for_equip(
        owned_artifacts=owned_artifacts,
        scenario=scenario,
        current_stats=current_stats,
        calculate_dps_func=calculate_dps_func,
    )

    # Build set of top N artifact keys (these would be equipped)
    top_artifact_keys = set()
    for i, score in enumerate(current_ranking):
        if i >= top_n:
            break
        top_artifact_keys.add(score.artifact_key)

    for artifact_key, drop_rate in ARTIFACT_DROP_RATES.items():
        if artifact_key not in ARTIFACTS:
            continue

        owned = owned_artifacts.get(artifact_key, {})
        current_stars = owned.get('stars', -1)  # -1 = not owned
        current_dupes = owned.get('dupes', 0)

        # Artifact counts as "would be equipped" if:
        # 1. It's in the current top N, OR
        # 2. It's currently equipped (user choice override)
        # This determines whether active effects count toward value
        would_be_equipped = artifact_key in top_artifact_keys or artifact_key in equipped_artifact_keys

        if current_stars < 0:
            # Don't own yet - value is first copy
            # For new artifacts, check if they would potentially rank in top N
            # We estimate conservatively: only count active if it's a strong artifact type
            value = calculate_new_artifact_value(
                artifact_key, current_stats, calculate_dps_func,
                scenario=scenario,
                include_active=would_be_equipped,
            )
            reason = "New artifact"
        elif current_stars >= 5:
            # Maxed - no value from duplicates
            value = 0.0
            reason = "Already maxed"
        else:
            # Owned but not maxed - value is progress toward next star
            # First calculate value of reaching next star
            awakening_rec = calculate_awakening_efficiency(
                artifact_key=artifact_key,
                current_stars=current_stars,
                is_equipped=would_be_equipped,
                current_stats=current_stats,
                current_resonance_level=current_resonance_level,
                calculate_dps_func=calculate_dps_func,
                scenario=scenario,
            )

            if awakening_rec:
                full_star_value = awakening_rec.total_dps_gain
                value = calculate_dupe_value(
                    artifact_key, current_stars, current_dupes, full_star_value
                )
                reason = f"★{current_stars}→★{current_stars+1} progress"
            else:
                value = 0.0
                reason = "Error calculating"

        contribution = drop_rate * value
        total_ev += contribution

        breakdown.append({
            'artifact_key': artifact_key,
            'artifact_name': ARTIFACTS[artifact_key].name,
            'tier': ARTIFACTS[artifact_key].tier.value,
            'drop_rate': drop_rate,
            'drop_rate_pct': drop_rate * 100,
            'value': value,
            'contribution': contribution,
            'reason': reason,
            'current_stars': current_stars,
            'is_equipped': artifact_key in equipped_artifact_keys,
            'would_be_equipped': would_be_equipped,
        })

    # Sort by contribution
    breakdown.sort(key=lambda x: x['contribution'], reverse=True)

    # Efficiency
    cost = CHEST_COST_BLUE
    efficiency = total_ev / (cost / 1000) if cost > 0 else 0.0

    return ChestExpectedValue(
        expected_dps_per_chest=total_ev,
        cost_per_chest=cost,
        efficiency=efficiency,
        breakdown=breakdown,
    )


# =============================================================================
# ARTIFACT POTENTIAL DISTRIBUTION (EXACT PROBABILITIES)
# =============================================================================

@dataclass
class ArtifactPotentialOutcome:
    """A single potential roll outcome with its exact probability and DPS contribution."""
    potentials: List[Tuple[str, float, str]]  # [(stat, value, tier_name), ...]
    probability: float
    dps_gain_pct: float = 0.0  # DPS% contribution using real DPS calculator


class ArtifactPotentialDistribution:
    """
    Exact probability distribution for artifact potential rolls using real DPS calculator.

    Similar to ExactRollDistribution for equipment cubes, this class:
    1. Pre-calculates DPS weight for each (stat, tier, value) combination using real DPS calc
    2. Enumerates all unique potential combinations with exact probabilities
    3. Provides percentile lookups and improvement probability calculations

    For artifact potentials:
    - Each slot independently rolls: tier (from POTENTIAL_TIER_RATES) + stat (from POTENTIAL_STAT_RATES)
    - Mystic tier has 75/25 split for low/high values
    - Slots are order-independent for DPS (we only care about total stats)
    """

    def __init__(self, num_slots: int = 3):
        """
        Initialize distribution for given number of potential slots.

        Args:
            num_slots: Number of potential slots (1-3)
        """
        self.num_slots = min(max(num_slots, 1), 3)
        self._outcomes: List[ArtifactPotentialOutcome] = []
        self._scored = False
        self._stat_weights: Dict[Tuple[str, float], float] = {}  # (stat, value) -> DPS gain %

    def _calculate_stat_weights(
        self,
        dps_calc_func: Callable,
        baseline_dps: float,
        current_stats: Dict[str, Any],
    ) -> Dict[Tuple[str, float], float]:
        """
        Pre-calculate DPS weight for each (stat, value) combination using real DPS calculator.

        This calls dps_calc_func once per unique (stat, tier) combination, not per potential roll.
        Returns dict mapping (stat_key, value) -> DPS gain % for that stat at that value.
        """
        weights = {}
        tested = set()  # Track (stat, value) pairs we've already tested

        for pot_tier, tier_prob in POTENTIAL_TIER_RATES.items():
            for stat_key, stat_prob in POTENTIAL_STAT_RATES.items():
                values = POTENTIAL_VALUES.get(stat_key, {}).get(pot_tier)
                if not values:
                    continue

                low_val, high_val = values

                # Test low value
                if (stat_key, low_val) not in tested:
                    tested.add((stat_key, low_val))
                    gain = self._test_stat_dps_gain(
                        stat_key, low_val, dps_calc_func, baseline_dps, current_stats
                    )
                    weights[(stat_key, low_val)] = gain

                # Test high value if different (Mystic tier)
                if high_val != low_val and (stat_key, high_val) not in tested:
                    tested.add((stat_key, high_val))
                    gain = self._test_stat_dps_gain(
                        stat_key, high_val, dps_calc_func, baseline_dps, current_stats
                    )
                    weights[(stat_key, high_val)] = gain

        return weights

    def _test_stat_dps_gain(
        self,
        stat_key: str,
        value: float,
        dps_calc_func: Callable,
        baseline_dps: float,
        current_stats: Dict[str, Any],
    ) -> float:
        """
        Test a single stat's DPS contribution using the real DPS calculator.

        Args:
            stat_key: Artifact potential stat name (e.g., 'damage', 'crit_rate')
            value: Stat value (e.g., 14.0 for 14% damage)
            dps_calc_func: Function to calculate DPS from stats dict
            baseline_dps: DPS without this potential stat
            current_stats: Current character stats

        Returns:
            DPS% gain from this stat
        """
        test_stats = deepcopy(current_stats)

        # Map artifact potential stat names to standardized DPS calculator stat names
        # Using constants from stat_names.py for consistency
        stat_mapping = {
            'damage': DAMAGE_PCT,
            'boss_damage': BOSS_DAMAGE,
            'normal_damage': NORMAL_DAMAGE,
            'crit_rate': CRIT_RATE,
            'def_pen': DEF_PEN,
            'min_damage_mult': MIN_DMG_MULT,
            'max_damage_mult': MAX_DMG_MULT,
            'status_effect_damage': 'status_effect_damage',
            # Non-DPS stats (defensive/utility)
            'damage_taken_decrease': 'damage_taken_decrease',
            'defense': DEFENSE,
            'accuracy': ACCURACY,
        }

        # Non-DPS stats - no direct DPS contribution
        if stat_key in ('damage_taken_decrease', 'defense', 'accuracy'):
            return 0.0

        # Handle main_stat_pct specially - uses dynamic main stat type from job class
        if stat_key == 'main_stat_pct':
            # Get main stat type from stats dict (e.g., 'dex', 'str', 'int', 'luk')
            main_stat_type = test_stats.get('main_stat_type', 'dex')
            main_flat_key = get_main_stat_flat_key(main_stat_type)
            main_pct_key = get_main_stat_pct_key(main_stat_type)

            # main_stat_pct adds to the main stat percentage bonus
            test_stats[main_pct_key] = test_stats.get(main_pct_key, 0) + value
        elif stat_key == 'def_pen':
            # Defense penetration is stored as decimal (0.07 = 7%)
            mapped_stat = stat_mapping.get(stat_key, stat_key)
            test_stats[mapped_stat] = test_stats.get(mapped_stat, 0) + (value / 100)
        else:
            # Standard percentage stats add directly
            mapped_stat = stat_mapping.get(stat_key, stat_key)
            test_stats[mapped_stat] = test_stats.get(mapped_stat, 0) + value

        # Calculate new DPS
        new_result = dps_calc_func(test_stats, 'stage')
        new_dps = new_result.get('total', baseline_dps)

        if baseline_dps > 0:
            return ((new_dps / baseline_dps) - 1) * 100
        return 0.0

    def compute_distribution(
        self,
        dps_calc_func: Callable,
        baseline_dps: float,
        current_stats: Dict[str, Any],
    ) -> None:
        """
        Compute the full distribution of all possible multi-slot outcomes.

        Uses the real DPS calculator to weight each stat properly.
        """
        from itertools import product

        # Step 1: Pre-calculate DPS weights for all (stat, value) combinations
        self._stat_weights = self._calculate_stat_weights(
            dps_calc_func, baseline_dps, current_stats
        )

        # Step 2: Build list of single-slot outcomes with probabilities
        single_slot_outcomes = []  # [(stat, value, tier, probability, dps_gain), ...]

        for pot_tier, tier_prob in POTENTIAL_TIER_RATES.items():
            for stat_key, stat_prob in POTENTIAL_STAT_RATES.items():
                values = POTENTIAL_VALUES.get(stat_key, {}).get(pot_tier)
                if not values:
                    continue

                low_val, high_val = values
                combined_prob = tier_prob * stat_prob

                # Get DPS weight for this stat/value
                low_gain = self._stat_weights.get((stat_key, low_val), 0.0)
                high_gain = self._stat_weights.get((stat_key, high_val), 0.0)

                # For Mystic with two values, split probability
                if pot_tier == PotentialTier.MYSTIC and low_val != high_val:
                    single_slot_outcomes.append((
                        stat_key, low_val, pot_tier.value,
                        combined_prob * MYSTIC_LOW_VALUE_CHANCE, low_gain
                    ))
                    single_slot_outcomes.append((
                        stat_key, high_val, pot_tier.value,
                        combined_prob * MYSTIC_HIGH_VALUE_CHANCE, high_gain
                    ))
                else:
                    single_slot_outcomes.append((
                        stat_key, low_val, pot_tier.value,
                        combined_prob, low_gain
                    ))

        # Step 3: Enumerate all slot combinations
        slot_outcomes = [single_slot_outcomes] * self.num_slots

        # Group by total DPS gain (order-independent)
        dps_buckets: Dict[float, Dict] = {}  # dps_key -> {prob, potentials}

        for combo in product(*slot_outcomes):
            # combo is tuple of (stat, value, tier, prob, dps_gain) for each slot
            combined_prob = 1.0
            total_dps_gain = 0.0
            potentials = []

            for stat, value, tier, prob, dps_gain in combo:
                combined_prob *= prob
                total_dps_gain += dps_gain
                potentials.append((stat, value, tier))

            # Round DPS to avoid floating point issues when bucketing
            dps_key = round(total_dps_gain, 4)

            # Sort potentials for consistent bucketing (order-independent)
            sorted_pots = tuple(sorted(potentials, key=lambda x: (x[0], x[1])))

            # Add to bucket
            if dps_key not in dps_buckets:
                dps_buckets[dps_key] = {
                    'prob': combined_prob,
                    'potentials': list(sorted_pots),
                }
            else:
                dps_buckets[dps_key]['prob'] += combined_prob

        # Step 4: Convert buckets to sorted outcomes
        self._outcomes = []
        for dps_gain, data in sorted(dps_buckets.items()):
            self._outcomes.append(ArtifactPotentialOutcome(
                potentials=data['potentials'],
                probability=data['prob'],
                dps_gain_pct=dps_gain,
            ))

        self._scored = True

    def get_percentile_of_dps(self, dps_value: float) -> float:
        """
        Get the percentile rank of a given DPS value.

        Args:
            dps_value: The DPS% contribution to look up

        Returns:
            Percentile (0-100) - how many rolls have lower or equal DPS
        """
        if not self._scored:
            raise RuntimeError("Must call compute_distribution first")

        cumulative = 0.0
        for outcome in self._outcomes:
            if outcome.dps_gain_pct > dps_value:
                break
            cumulative += outcome.probability

        return cumulative * 100

    def get_dps_at_percentile(self, percentile: float) -> float:
        """
        Get the DPS value at a given percentile.

        Args:
            percentile: Target percentile (0-100)

        Returns:
            DPS% value at that percentile
        """
        if not self._scored:
            raise RuntimeError("Must call compute_distribution first")

        target = percentile / 100
        cumulative = 0.0

        for outcome in self._outcomes:
            cumulative += outcome.probability
            if cumulative >= target:
                return outcome.dps_gain_pct

        return self._outcomes[-1].dps_gain_pct if self._outcomes else 0.0

    def get_probability_of_improvement(self, current_dps: float) -> float:
        """
        Get probability of rolling strictly better than current DPS.

        Args:
            current_dps: Current DPS% contribution from potentials

        Returns:
            Probability (0-1) of improvement
        """
        if not self._scored:
            raise RuntimeError("Must call compute_distribution first")

        prob_better = sum(
            o.probability for o in self._outcomes
            if o.dps_gain_pct > current_dps
        )
        return prob_better

    def get_expected_improvement(self, current_dps: float) -> Tuple[float, float]:
        """
        Get expected DPS gain and expected rolls to improve.

        This is the key function for optimal stopping: it tells you
        how much you can expect to gain and how many rerolls it will take.

        Args:
            current_dps: Current DPS% contribution

        Returns:
            (expected_dps_gain, expected_rolls_to_improve)
        """
        if not self._scored:
            raise RuntimeError("Must call compute_distribution first")

        prob_better = 0.0
        expected_better_dps = 0.0

        for outcome in self._outcomes:
            if outcome.dps_gain_pct > current_dps:
                prob_better += outcome.probability
                expected_better_dps += outcome.probability * outcome.dps_gain_pct

        if prob_better <= 0:
            return 0.0, float('inf')

        # E[DPS | improvement] = (sum of P(outcome) * DPS for better outcomes) / P(better)
        avg_improved_dps = expected_better_dps / prob_better
        expected_gain = avg_improved_dps - current_dps

        # Expected rolls to improve (geometric distribution)
        expected_rolls = 1.0 / prob_better

        return expected_gain, expected_rolls

    def get_distribution_stats(self) -> Dict[str, float]:
        """
        Get summary statistics of the distribution.

        Returns:
            Dict with min, max, median, mean, std DPS values
        """
        if not self._scored:
            raise RuntimeError("Must call compute_distribution first")

        dps_values = [o.dps_gain_pct for o in self._outcomes]
        probs = [o.probability for o in self._outcomes]

        mean = sum(d * p for d, p in zip(dps_values, probs))
        variance = sum(p * (d - mean) ** 2 for d, p in zip(dps_values, probs))

        return {
            'min': dps_values[0] if dps_values else 0,
            'max': dps_values[-1] if dps_values else 0,
            'median': self.get_dps_at_percentile(50),
            'mean': mean,
            'std': variance ** 0.5,
            'p25': self.get_dps_at_percentile(25),
            'p75': self.get_dps_at_percentile(75),
            'p90': self.get_dps_at_percentile(90),
            'p99': self.get_dps_at_percentile(99),
        }

    def get_distribution_data_for_chart(self, num_points: int = 101) -> Dict:
        """
        Get distribution data suitable for Plotly charts.

        Returns:
            Dict with percentiles, dps_values, and summary stats
        """
        if not self._scored:
            raise RuntimeError("Must call compute_distribution first")

        percentiles = list(range(0, num_points))
        dps_values = [self.get_dps_at_percentile(p * 100 / (num_points - 1)) for p in percentiles]

        return {
            'percentiles': percentiles,
            'dps_values': dps_values,
            'total_outcomes': len(self._outcomes),
            'stats': self.get_distribution_stats(),
        }


# =============================================================================
# ARTIFACT POTENTIAL SCENARIO ANALYSIS
# =============================================================================


@dataclass
class ArtifactPotentialScenario:
    """Analysis for a specific number of potential slots."""
    num_slots: int
    current_dps_gain: float          # DPS% from current potentials (only unlocked slots count)
    current_percentile: float         # Where current roll sits in distribution (0-100)
    expected_dps_gain: float          # E[DPS] from average roll at this slot count
    expected_dps_when_improving: float  # E[DPS | roll > current] - weighted avg of better outcomes
    expected_rolls_to_improve: float  # Geometric: 1 / P(better)
    prob_improve_10_rolls: float      # P(improve in ≤10 rolls)
    prob_improve_50_rolls: float      # P(improve in ≤50 rolls)
    max_dps_gain: float               # Maximum possible DPS% (99th percentile)

    # Reroll costs
    cost_per_roll: float              # Base cost (meso + enhancers in diamond equivalent)
    expected_cost_to_improve: float   # cost × expected_rolls
    efficiency: float                 # Expected improvement DPS% per 1000 diamonds


@dataclass
class ArtifactPotentialAnalysis:
    """Complete analysis for an artifact across all slot scenarios."""
    artifact_key: str
    artifact_name: str
    tier: str  # 'Epic', 'Unique', 'Legendary'
    current_stars: int
    max_slots: int  # 1 for Epic, 2 for Unique, 3 for Legendary
    slots_unlocked: int  # How many currently contribute (based on stars)
    current_potentials: List[ArtifactPotentialLine]

    # Analysis per slot count (only scenarios ≤ max_slots)
    scenario_1_slot: Optional[ArtifactPotentialScenario]
    scenario_2_slots: Optional[ArtifactPotentialScenario]
    scenario_3_slots: Optional[ArtifactPotentialScenario]

    # Recommendations
    should_reroll_now: bool
    recommended_action: str  # "Reroll", "Near-max roll - keep", etc.
    unlock_value_slot2: Optional[float]  # Expected DPS% gain from unlocking slot 2
    unlock_value_slot3: Optional[float]  # Expected DPS% gain from unlocking slot 3


def get_slots_unlocked(stars: int) -> int:
    """Get number of potential slots unlocked for given star level."""
    return POTENTIAL_SLOT_UNLOCKS.get(stars, 0)


def get_max_slots(tier: ArtifactTier) -> int:
    """Get maximum potential slots for given artifact tier."""
    return MAX_POTENTIAL_SLOTS_BY_TIER.get(tier, 1)


def get_reroll_cost_diamonds(tier: ArtifactTier) -> float:
    """
    Get reconfigure cost in diamond equivalent.

    Combines meso and artifact enhancer costs into diamond equivalent.
    """
    costs = RECONFIGURE_COSTS.get(tier, {"meso": 10000, "artifact_enhancers": 1000})
    meso_cost = costs.get("meso", 0)
    enhancer_cost = costs.get("artifact_enhancers", 0)

    # Convert to diamond equivalent
    diamond_from_meso = meso_cost * MESO_TO_DIAMOND
    diamond_from_enhancers = enhancer_cost * ENHANCER_EXCHANGE_RATE

    return diamond_from_meso + diamond_from_enhancers


def calculate_current_potential_dps(
    potentials: List[ArtifactPotentialLine],
    slots_to_count: int,
    distribution: ArtifactPotentialDistribution,
) -> float:
    """
    Calculate DPS% contribution from current potentials using distribution's stat weights.

    Args:
        potentials: List of current potential lines
        slots_to_count: How many slots are actually unlocked (contributing)
        distribution: The computed distribution (has stat weights)

    Returns:
        Total DPS% contribution from the unlocked potentials
    """
    total_dps = 0.0
    for i, pot in enumerate(potentials[:slots_to_count]):
        # Use distribution's pre-calculated stat weights
        weight = distribution._stat_weights.get((pot.stat, pot.value), 0.0)
        total_dps += weight
    return total_dps


def analyze_artifact_potential_scenarios(
    artifact_key: str,
    artifact_tier: ArtifactTier,
    current_potentials: List[ArtifactPotentialLine],
    current_stars: int,
    current_stats: Dict[str, Any],
    calculate_dps_func: Callable,
    baseline_dps: float,
) -> ArtifactPotentialAnalysis:
    """
    Analyze artifact potentials across 1/2/3 slot scenarios.

    For each scenario (up to artifact's max slots):
    1. Create ArtifactPotentialDistribution for N slots
    2. Compute the full probability distribution using real DPS calc
    3. Calculate current DPS contribution (only unlocked slots count)
    4. Get percentile, improvement probability, expected rolls
    5. Calculate E[DPS | improvement] - the weighted average of better outcomes
    6. Calculate reroll costs and efficiency

    Args:
        artifact_key: Unique identifier for the artifact
        artifact_tier: ArtifactTier enum (EPIC, UNIQUE, LEGENDARY)
        current_potentials: List of current potential lines on the artifact
        current_stars: Current awakening star level (0-5)
        current_stats: Current character stats dict
        calculate_dps_func: Function to calculate DPS from stats
        baseline_dps: Current DPS without any potential changes

    Returns:
        ArtifactPotentialAnalysis with scenarios and recommendations
    """
    # Get artifact info
    artifact_def = ARTIFACTS.get(artifact_key)
    artifact_name = artifact_def.name if artifact_def else artifact_key

    # Determine slot counts
    max_slots = get_max_slots(artifact_tier)
    slots_unlocked = min(get_slots_unlocked(current_stars), max_slots)

    # Get reroll cost
    cost_per_roll = get_reroll_cost_diamonds(artifact_tier)

    # Build scenarios for each possible slot count
    scenarios = {}
    distributions = {}

    for num_slots in range(1, max_slots + 1):
        # Create and compute distribution for this slot count
        dist = ArtifactPotentialDistribution(num_slots=num_slots)
        dist.compute_distribution(calculate_dps_func, baseline_dps, current_stats)
        distributions[num_slots] = dist

        # Calculate current DPS for unlocked slots only
        # If we're looking at a scenario with more slots than unlocked,
        # we still use the current potentials for unlocked slots
        slots_to_count = min(slots_unlocked, num_slots, len(current_potentials))
        current_dps = calculate_current_potential_dps(
            current_potentials, slots_to_count, dist
        )

        # Get distribution stats
        dist_stats = dist.get_distribution_stats()
        expected_dps = dist_stats['mean']
        max_dps = dist_stats['p99']  # Use 99th percentile as "max"

        # Get percentile and improvement probability
        percentile = dist.get_percentile_of_dps(current_dps)
        prob_improve = dist.get_probability_of_improvement(current_dps)
        expected_gain, expected_rolls = dist.get_expected_improvement(current_dps)

        # Calculate E[DPS | improvement] = current + expected_gain
        expected_dps_when_improving = current_dps + expected_gain

        # Calculate probability of improvement in N rolls
        # P(improve in ≤N) = 1 - (1 - p)^N
        prob_10 = 1 - ((1 - prob_improve) ** 10) if prob_improve < 1 else 1.0
        prob_50 = 1 - ((1 - prob_improve) ** 50) if prob_improve < 1 else 1.0

        # Calculate costs
        expected_cost = cost_per_roll * expected_rolls if expected_rolls < float('inf') else float('inf')

        # Calculate efficiency (expected improvement DPS% per 1000 diamonds)
        if expected_cost > 0 and expected_cost < float('inf'):
            efficiency = (expected_gain / expected_cost) * 1000
        else:
            efficiency = 0.0

        scenarios[num_slots] = ArtifactPotentialScenario(
            num_slots=num_slots,
            current_dps_gain=current_dps,
            current_percentile=percentile,
            expected_dps_gain=expected_dps,
            expected_dps_when_improving=expected_dps_when_improving,
            expected_rolls_to_improve=expected_rolls,
            prob_improve_10_rolls=prob_10,
            prob_improve_50_rolls=prob_50,
            max_dps_gain=max_dps,
            cost_per_roll=cost_per_roll,
            expected_cost_to_improve=expected_cost,
            efficiency=efficiency,
        )

    # Calculate unlock values (expected DPS gain from unlocking next slot)
    unlock_value_slot2 = None
    unlock_value_slot3 = None

    if max_slots >= 2 and 2 in scenarios and 1 in scenarios:
        # Value of slot 2 = E[DPS|2 slots] - E[DPS|1 slot]
        unlock_value_slot2 = scenarios[2].expected_dps_gain - scenarios[1].expected_dps_gain

    if max_slots >= 3 and 3 in scenarios and 2 in scenarios:
        # Value of slot 3 = E[DPS|3 slots] - E[DPS|2 slots]
        unlock_value_slot3 = scenarios[3].expected_dps_gain - scenarios[2].expected_dps_gain

    # Generate recommendation
    current_scenario = scenarios.get(slots_unlocked) or scenarios.get(1)
    current_percentile = current_scenario.current_percentile if current_scenario else 0

    should_reroll_now = False
    recommended_action = "No potentials to analyze"

    if current_scenario:
        # Only recommend "keep" if at 99.5th percentile or above (near-max roll)
        if current_percentile >= 99.5:
            recommended_action = "Near-max roll - keep"
        elif current_percentile >= 95:
            recommended_action = f"Excellent roll ({current_percentile:.1f}%ile) - consider keeping"
        else:
            # Always show reroll info with expected improvement
            should_reroll_now = True
            expected_improvement = current_scenario.expected_dps_when_improving - current_scenario.current_dps_gain
            recommended_action = f"Reroll - expect +{expected_improvement:.2f}% DPS in ~{current_scenario.expected_rolls_to_improve:.0f} rolls"

    # Build result
    tier_name = artifact_tier.value if hasattr(artifact_tier, 'value') else str(artifact_tier)

    return ArtifactPotentialAnalysis(
        artifact_key=artifact_key,
        artifact_name=artifact_name,
        tier=tier_name,
        current_stars=current_stars,
        max_slots=max_slots,
        slots_unlocked=slots_unlocked,
        current_potentials=current_potentials,
        scenario_1_slot=scenarios.get(1),
        scenario_2_slots=scenarios.get(2),
        scenario_3_slots=scenarios.get(3),
        should_reroll_now=should_reroll_now,
        recommended_action=recommended_action,
        unlock_value_slot2=unlock_value_slot2,
        unlock_value_slot3=unlock_value_slot3,
    )


# =============================================================================
# ARTIFACT POTENTIAL REROLL EFFICIENCY
# =============================================================================


def calculate_artifact_reroll_efficiency(
    artifact_key: str,
    current_potentials: List[ArtifactPotentialLine],
    current_stars: int,
    is_equipped: bool,
    current_stats: Dict[str, Any],
    calculate_dps_func: Callable,
) -> Optional[ArtifactRerollRecommendation]:
    """
    Calculate efficiency of rerolling artifact potentials using the real DPS calculator.

    This is the preferred method as it uses exact probability distributions and
    the actual DPS calculator to evaluate stat contributions accurately.

    Args:
        artifact_key: The artifact to analyze
        current_potentials: Current potential lines
        current_stars: Current awakening level
        is_equipped: Whether artifact is in an equipped slot
        current_stats: Current character stats for DPS calculation
        calculate_dps_func: Function to calculate DPS from stats dict

    Returns:
        ArtifactRerollRecommendation or None if no slots available
    """
    if artifact_key not in ARTIFACTS:
        return None

    definition = ARTIFACTS[artifact_key]
    tier = definition.tier

    # Get available slots
    max_slots = MAX_POTENTIAL_SLOTS_BY_TIER.get(tier, 3)
    unlocked_slots = POTENTIAL_SLOT_UNLOCKS.get(current_stars, 0)
    num_slots = min(unlocked_slots, max_slots)

    if num_slots <= 0:
        return None

    # Get reroll cost in diamonds
    cost_per_reroll = get_reconfigure_diamond_cost(tier)

    # Get baseline DPS (without artifact potentials)
    # We need to calculate baseline by removing current potentials from stats
    baseline_result = calculate_dps_func(current_stats, 'stage')
    baseline_dps = baseline_result.get('total', 1)

    # Create distribution and compute with real DPS calc
    dist = ArtifactPotentialDistribution(num_slots)
    dist.compute_distribution(calculate_dps_func, baseline_dps, current_stats)

    # Calculate current DPS contribution from existing potentials
    # We test each potential line using the same method as the distribution
    current_dps = 0.0
    for pot in current_potentials[:num_slots]:
        if pot.stat and pot.value > 0:
            # Look up the weight from the distribution's pre-calculated weights
            weight = dist._stat_weights.get((pot.stat, pot.value), 0.0)
            current_dps += weight

    # Get exact percentile and improvement statistics
    percentile = dist.get_percentile_of_dps(current_dps)
    expected_gain, expected_rerolls = dist.get_expected_improvement(current_dps)

    # If not equipped, reduce the value (potentials less impactful)
    if not is_equipped:
        expected_gain *= 0.3  # 30% of equipped value

    # Total cost and efficiency
    total_cost = expected_rerolls * cost_per_reroll
    efficiency = expected_gain / (total_cost / 1000) if total_cost > 0 else 0

    return ArtifactRerollRecommendation(
        artifact_key=artifact_key,
        artifact_name=definition.name,
        current_dps_gain=current_dps,
        current_percentile=percentile,
        num_slots=num_slots,
        expected_dps_gain=expected_gain,
        expected_rerolls=expected_rerolls,
        cost_per_reroll=cost_per_reroll,
        total_cost=total_cost,
        efficiency=efficiency,
    )


# =============================================================================
# ARTIFACT DPS SCORING (FOR EQUIPMENT SELECTION)
# =============================================================================


def _calculate_active_score_with_dps(
    artifact_key: str,
    stars: int,
    scenario: str,
    current_stats: Dict[str, Any],
    calculate_dps_func: Callable,
) -> float:
    """
    Calculate DPS% from artifact's active effect using the actual DPS calculator.

    This properly evaluates the real DPS impact of active effects by running
    the damage formula with and without the effect applied.

    Args:
        artifact_key: The artifact identifier
        stars: Current awakening level
        scenario: Combat scenario for uptime calculation
        current_stats: Current character stats dict
        calculate_dps_func: Function to calculate DPS from stats

    Returns:
        DPS percentage contribution (with uptime factored in)
    """
    # Use the existing calculate_active_effect_dps which already does this correctly
    return calculate_active_effect_dps(
        artifact_key=artifact_key,
        stars=stars,
        current_stats=current_stats,
        calculate_dps_func=calculate_dps_func,
        scenario=scenario,
    )


def _calculate_inventory_score_with_dps(
    artifact_key: str,
    stars: int,
    current_stats: Dict[str, Any],
    calculate_dps_func: Callable,
) -> float:
    """
    Calculate DPS% from artifact's inventory effect using the actual DPS calculator.

    Args:
        artifact_key: The artifact identifier
        stars: Current awakening level
        current_stats: Current character stats dict
        calculate_dps_func: Function to calculate DPS from stats

    Returns:
        DPS percentage contribution
    """
    # Use the existing calculate_inventory_effect_dps which already does this correctly
    return calculate_inventory_effect_dps(
        artifact_key=artifact_key,
        stars=stars,
        current_stats=current_stats,
        calculate_dps_func=calculate_dps_func,
    )


def _calculate_potential_score_with_dps(
    potentials: List[ArtifactPotentialLine],
    current_stats: Dict[str, Any],
    calculate_dps_func: Callable,
) -> float:
    """
    Calculate DPS% from artifact potentials using the actual DPS calculator.

    Args:
        potentials: List of ArtifactPotentialLine to evaluate
        current_stats: Current character stats dict
        calculate_dps_func: Function to calculate DPS from stats

    Returns:
        DPS percentage contribution from potentials
    """
    if not potentials:
        return 0.0

    # Get baseline DPS
    baseline_result = calculate_dps_func(current_stats, 'stage')
    baseline_dps = baseline_result.get('total', 0)

    if baseline_dps <= 0:
        return 0.0

    # Build test stats with potentials applied
    test_stats = deepcopy(current_stats)

    # Map artifact potential stat names to standardized DPS calculator stat names
    stat_mapping = {
        'damage': DAMAGE_PCT,
        'boss_damage': BOSS_DAMAGE,
        'normal_damage': NORMAL_DAMAGE,
        'crit_rate': CRIT_RATE,
        'def_pen': DEF_PEN,
        'min_damage_mult': MIN_DMG_MULT,
        'max_damage_mult': MAX_DMG_MULT,
        'status_effect_damage': 'status_effect_damage',
    }

    # Non-DPS stats that don't affect DPS calculation
    non_dps_stats = {'damage_taken_decrease', 'defense', 'accuracy'}

    for potential in potentials:
        stat_key = potential.stat
        value = potential.value

        if stat_key in non_dps_stats:
            continue

        # Handle main_stat_pct specially - uses dynamic main stat type from job class
        if stat_key == 'main_stat_pct':
            main_stat_type = test_stats.get('main_stat_type', 'dex')
            main_pct_key = get_main_stat_pct_key(main_stat_type)
            test_stats[main_pct_key] = test_stats.get(main_pct_key, 0) + value
        elif stat_key == 'def_pen':
            # Defense penetration is stored as decimal (0.07 = 7%)
            mapped_stat = stat_mapping.get(stat_key, stat_key)
            test_stats[mapped_stat] = test_stats.get(mapped_stat, 0) + (value / 100)
        else:
            # Standard percentage stats add directly
            mapped_stat = stat_mapping.get(stat_key, stat_key)
            test_stats[mapped_stat] = test_stats.get(mapped_stat, 0) + value

    # Calculate new DPS with potentials
    new_result = calculate_dps_func(test_stats, 'stage')
    new_dps = new_result.get('total', baseline_dps)

    return ((new_dps / baseline_dps) - 1) * 100


@dataclass
class ArtifactDPSScore:
    """DPS score breakdown for an artifact."""
    artifact_key: str
    artifact_name: str
    tier: ArtifactTier
    stars: int

    # Score components
    active_score: float       # DPS% from active effect (when equipped)
    inventory_score: float    # DPS% from inventory effect (always active)
    potential_score: float    # DPS% from potential lines

    # Totals
    equip_value: float        # What you GAIN by equipping = active + potential (for ranking)
    equipped_score: float     # Total if equipped (active + inventory + potential)
    inventory_only_score: float  # Total if not equipped (inventory + potential)

    # Additional info
    scenario: str             # Which scenario the active effect applies to
    uptime: float             # Uptime percentage for active effect
    num_potential_slots: int


def calculate_artifact_dps_score(
    artifact_key: str,
    stars: int,
    potentials: List[ArtifactPotentialLine],
    scenario: str = "normal",
    current_stats: Optional[Dict[str, Any]] = None,
    calculate_dps_func: Optional[Callable] = None,
) -> Optional[ArtifactDPSScore]:
    """
    Calculate a DPS score for an artifact to help with equipment selection.

    Uses the actual DPS calculator to properly evaluate effect values.
    The score represents DPS% contribution from each source:
    - Active effect (only when equipped, scenario-dependent)
    - Inventory effect (always active regardless of equip status)
    - Potential lines (always active)

    Args:
        artifact_key: The artifact identifier
        stars: Current awakening level
        potentials: Current potential lines
        scenario: Combat scenario for active effect calculation
        current_stats: Current character stats dict for DPS calculation
        calculate_dps_func: Function to calculate DPS from stats

    Returns:
        ArtifactDPSScore with breakdown, or None if artifact not found
    """
    if artifact_key not in ARTIFACTS:
        return None

    definition = ARTIFACTS[artifact_key]
    tier = definition.tier

    # Default stats if not provided
    if current_stats is None:
        current_stats = {}

    # Artifacts with zero DPS active effects (utility only)
    ZERO_DPS_ACTIVE_ARTIFACTS = {
        'old_music_box',    # ATK buff dependent on debuff procs - too variable to model
        'flaming_lava',     # Complex utility effect, no direct DPS
        'lunar_dew',        # HP recovery only
    }

    # 1. Active Effect Score (only applies when equipped and scenario matches)
    active_score = 0.0
    fight_duration = get_scenario_duration(scenario)
    uptime = 1.0

    if artifact_key not in ZERO_DPS_ACTIVE_ARTIFACTS and definition.applies_to_scenario(scenario):
        uptime = definition.get_effective_uptime(fight_duration)

        if calculate_dps_func is not None:
            # Use actual DPS calculator
            active_score = _calculate_active_score_with_dps(
                artifact_key, stars, scenario, current_stats, calculate_dps_func
            )
        # If no DPS func provided, active_score stays 0

    # 2. Inventory Effect Score (always active)
    inventory_score = 0.0

    if calculate_dps_func is not None:
        # Use actual DPS calculator
        inventory_score = _calculate_inventory_score_with_dps(
            artifact_key, stars, current_stats, calculate_dps_func
        )
    # If no DPS func provided, inventory_score stays 0

    # 3. Potential Score
    max_slots = MAX_POTENTIAL_SLOTS_BY_TIER.get(tier, 3)
    unlocked_slots = POTENTIAL_SLOT_UNLOCKS.get(stars, 0)
    num_slots = min(unlocked_slots, max_slots)

    active_potentials = potentials[:num_slots] if potentials else []
    potential_score = 0.0

    if calculate_dps_func is not None and active_potentials:
        # Use actual DPS calculator for potential score
        potential_score = _calculate_potential_score_with_dps(
            active_potentials, current_stats, calculate_dps_func
        )

    # Calculate totals
    # equip_value = what you GAIN by equipping (active + potential only)
    # Inventory effects are always active whether equipped or not, so they don't affect equip decision
    equip_value = active_score + potential_score
    equipped_score = active_score + inventory_score + potential_score
    inventory_only_score = inventory_score + potential_score

    return ArtifactDPSScore(
        artifact_key=artifact_key,
        artifact_name=definition.name,
        tier=tier,
        stars=stars,
        active_score=active_score,
        inventory_score=inventory_score,
        potential_score=potential_score,
        equip_value=equip_value,
        equipped_score=equipped_score,
        inventory_only_score=inventory_only_score,
        scenario=scenario,
        uptime=uptime,
        num_potential_slots=num_slots,
    )


def get_artifact_ranking_for_equip(
    owned_artifacts: Dict[str, Dict],
    scenario: str = "normal",
    current_stats: Optional[Dict[str, Any]] = None,
    calculate_dps_func: Optional[Callable] = None,
) -> List[ArtifactDPSScore]:
    """
    Rank all owned artifacts by their equip value (what you GAIN by equipping).

    Uses the actual DPS calculator when provided to get accurate scores.

    Ranking is by equip_value = active_score + potential_score.
    Inventory effects are excluded from ranking because they're always active
    regardless of whether the artifact is equipped.

    Args:
        owned_artifacts: Dict mapping artifact_key to {'stars': int, 'potentials': [...]}
        scenario: Combat scenario for active effect calculation
        current_stats: Current character stats dict for DPS calculation
        calculate_dps_func: Function to calculate DPS from stats

    Returns:
        List sorted by equip_value (highest first).
        Use this to decide which 3 artifacts to equip.
    """
    scores = []

    for artifact_key, art_data in owned_artifacts.items():
        if artifact_key not in ARTIFACTS:
            continue

        stars = art_data.get('stars', 0)
        potentials_raw = art_data.get('potentials', [])

        # Convert potentials to ArtifactPotentialLine objects
        potentials = []
        for i, pot in enumerate(potentials_raw):
            if isinstance(pot, ArtifactPotentialLine):
                potentials.append(pot)
            elif isinstance(pot, dict):
                potentials.append(ArtifactPotentialLine(
                    stat=pot.get('stat', ''),
                    value=pot.get('value', 0),
                    tier=pot.get('tier', PotentialTier.LEGENDARY),
                    slot=i + 1,
                ))

        score = calculate_artifact_dps_score(
            artifact_key=artifact_key,
            stars=stars,
            potentials=potentials,
            scenario=scenario,
            current_stats=current_stats,
            calculate_dps_func=calculate_dps_func,
        )

        if score:
            scores.append(score)

    # Sort by equip_value (what you GAIN by equipping = active + potential)
    # Inventory effects don't affect equip decision since they're always active
    scores.sort(key=lambda x: x.equip_value, reverse=True)

    return scores


# =============================================================================
# MAIN ENTRY POINT FOR OPTIMIZER
# =============================================================================

def get_artifact_recommendations_for_optimizer(
    owned_artifacts: Dict[str, Dict],
    equipped_artifact_keys: List[str],
    current_resonance_level: int,
    resonance_max_level: int,
    current_stats: Dict[str, Any],
    calculate_dps_func: Callable,
    scenario: str = 'chapter_hunt',
) -> List[Dict[str, Any]]:
    """
    Get all artifact upgrade recommendations for the Upgrade Optimizer.

    Returns a list of recommendations in the same format as cube/starforce,
    ready to be merged into the all_upgrades list.

    Args:
        owned_artifacts: Dict mapping artifact_key to {'stars': int, 'dupes': int}
        equipped_artifact_keys: List of artifact keys currently equipped
        current_resonance_level: Current resonance level
        resonance_max_level: Max resonance level from total artifact stars
        current_stats: Current character stats
        calculate_dps_func: DPS calculation function
        scenario: Combat scenario for active effect evaluation

    Returns:
        List of recommendation dicts with keys:
        - type: "Artifact" or "Resonance"
        - subtype: specific action type
        - target: artifact name or "Resonance"
        - description: human readable description
        - cost: diamond cost
        - dps_gain: DPS% gain
        - efficiency: DPS% per 1000 diamonds
        - details: additional info dict
    """
    recommendations = []

    # Get current artifact ranking for this scenario to determine top N
    current_ranking = get_artifact_ranking_for_equip(
        owned_artifacts=owned_artifacts,
        scenario=scenario,
        current_stats=current_stats,
        calculate_dps_func=calculate_dps_func,
    )

    # Build set of top 5 artifact keys (these would be equipped)
    top_artifact_keys = set()
    for i, score in enumerate(current_ranking):
        if i >= 5:
            break
        top_artifact_keys.add(score.artifact_key)

    # 1. Awakening recommendations for each artifact
    for artifact_key in owned_artifacts:
        if artifact_key not in ARTIFACTS:
            continue

        artifact_data = owned_artifacts[artifact_key]
        current_stars = artifact_data.get('stars', 0)
        # Artifact counts as "would be equipped" if in top 5 or currently equipped
        is_equipped = artifact_key in top_artifact_keys or artifact_key in equipped_artifact_keys

        if current_stars >= 5:
            continue  # Already maxed

        rec = calculate_awakening_efficiency(
            artifact_key=artifact_key,
            current_stars=current_stars,
            is_equipped=is_equipped,
            current_stats=current_stats,
            current_resonance_level=current_resonance_level,
            calculate_dps_func=calculate_dps_func,
            scenario=scenario,
        )

        if rec and rec.efficiency > 0:
            equipped_tag = " (Equipped)" if is_equipped else ""
            slot_tag = " +Slot" if rec.unlocks_potential_slot else ""

            recommendations.append({
                'type': 'Artifact',
                'subtype': 'Awakening',
                'target': artifact_key,
                'target_display': f"{rec.artifact_name} ★{current_stars}→★{rec.target_stars}{equipped_tag}{slot_tag}",
                'description': f"🏺 {rec.artifact_name} ★{current_stars}→★{rec.target_stars}{equipped_tag}{slot_tag}",
                'cost': rec.diamond_cost,
                'dps_gain': rec.total_dps_gain,
                'efficiency': rec.efficiency,
                'details': {
                    'tier': rec.tier.value,
                    'dupes_needed': rec.dupes_needed,
                    'expected_chests': rec.expected_chests,
                    'is_equipped': is_equipped,
                    'unlocks_slot': rec.unlocks_potential_slot,
                    'breakdown': {
                        'inventory': rec.inventory_gain,
                        'active': rec.active_gain,
                        'resonance': rec.resonance_gain,
                        'potential_slot': rec.potential_slot_gain,
                    },
                },
            })

    # 2. Resonance leveling recommendation
    res_rec = calculate_resonance_leveling_efficiency(
        current_level=current_resonance_level,
        max_level=resonance_max_level,
        current_stats=current_stats,
        calculate_dps_func=calculate_dps_func,
        levels_to_check=10,  # Evaluate 10 levels at a time
    )

    if res_rec and res_rec.efficiency > 0:
        recommendations.append({
            'type': 'Resonance',
            'subtype': 'Leveling',
            'target': 'Resonance',
            'target_display': f"Resonance {res_rec.current_level}→{res_rec.target_level}",
            'description': f"✨ Resonance {res_rec.current_level}→{res_rec.target_level} (+{res_rec.main_stat_gain} Main)",
            'cost': res_rec.diamond_cost,
            'dps_gain': res_rec.dps_gain,
            'efficiency': res_rec.efficiency,
            'details': {
                'current_level': res_rec.current_level,
                'target_level': res_rec.target_level,
                'max_level': res_rec.max_level,
                'main_stat_gain': res_rec.main_stat_gain,
                'hp_gain': res_rec.hp_gain,
                'enhancer_cost': res_rec.enhancer_cost,
            },
        })

    # 3. Chest expected value (as a single recommendation)
    chest_ev = calculate_chest_expected_value(
        owned_artifacts=owned_artifacts,
        equipped_artifact_keys=equipped_artifact_keys,
        current_stats=current_stats,
        current_resonance_level=current_resonance_level,
        calculate_dps_func=calculate_dps_func,
        scenario=scenario,
        top_n=5,
    )

    if chest_ev.efficiency > 0:
        # Get top contributors for display
        top_contributors = chest_ev.breakdown[:5]

        recommendations.append({
            'type': 'Artifact',
            'subtype': 'Chest',
            'target': 'Artifact Chest',
            'target_display': 'Artifact Chest (Expected Value)',
            'description': f"📦 Artifact Chest (E[DPS]: {chest_ev.expected_dps_per_chest:.4f}%)",
            'cost': chest_ev.cost_per_chest,
            'dps_gain': chest_ev.expected_dps_per_chest,
            'efficiency': chest_ev.efficiency,
            'details': {
                'expected_value_per_chest': chest_ev.expected_dps_per_chest,
                'top_contributors': top_contributors,
            },
        })

    # 4. Artifact potential reroll recommendations (for equipped artifacts)
    # Use the DPS-based calculation for accurate results
    for artifact_key in equipped_artifact_keys:
        if artifact_key not in ARTIFACTS:
            continue

        artifact_data = owned_artifacts.get(artifact_key, {})
        current_stars = artifact_data.get('stars', 0)
        current_potentials = artifact_data.get('potentials', [])

        # Convert potential data to ArtifactPotentialLine objects if needed
        pot_lines = []
        for i, pot_data in enumerate(current_potentials):
            if isinstance(pot_data, ArtifactPotentialLine):
                pot_lines.append(pot_data)
            elif isinstance(pot_data, dict):
                pot_lines.append(ArtifactPotentialLine(
                    stat=pot_data.get('stat', ''),
                    value=pot_data.get('value', 0),
                    tier=pot_data.get('tier', PotentialTier.RARE),
                    slot=i + 1,
                ))

        # Use the DPS-based reroll efficiency calculation
        reroll_rec = calculate_artifact_reroll_efficiency(
            artifact_key=artifact_key,
            current_potentials=pot_lines,
            current_stars=current_stars,
            is_equipped=True,
            current_stats=current_stats,
            calculate_dps_func=calculate_dps_func,
        )

        if reroll_rec and reroll_rec.efficiency > 0:
            recommendations.append({
                'type': 'Artifact',
                'subtype': 'Potential Reroll',
                'target': artifact_key,
                'target_display': f"{reroll_rec.artifact_name} Potential ({reroll_rec.num_slots} slots)",
                'description': f"🎲 {reroll_rec.artifact_name} Potential Reroll (P{reroll_rec.current_percentile:.0f})",
                'cost': reroll_rec.total_cost,
                'dps_gain': reroll_rec.expected_dps_gain,
                'efficiency': reroll_rec.efficiency,
                'details': {
                    'current_dps': reroll_rec.current_dps_gain,
                    'current_percentile': reroll_rec.current_percentile,
                    'num_slots': reroll_rec.num_slots,
                    'expected_rerolls': reroll_rec.expected_rerolls,
                    'cost_per_reroll': reroll_rec.cost_per_reroll,
                },
            })

    # Sort by efficiency
    recommendations.sort(key=lambda x: x['efficiency'], reverse=True)

    return recommendations


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("Artifact Optimizer Module")
    print("=" * 60)

    # Test with sample data
    owned = {
        'book_of_ancient': {'stars': 2, 'dupes': 1},
        'chalice': {'stars': 1, 'dupes': 0},
        'star_rock': {'stars': 0, 'dupes': 0},
    }
    equipped = ['book_of_ancient', 'chalice', 'star_rock']

    # Mock DPS function
    def mock_dps(stats, mode):
        return {'total': 1000000}

    recs = get_artifact_recommendations_for_optimizer(
        owned_artifacts=owned,
        equipped_artifact_keys=equipped,
        current_resonance_level=100,
        resonance_max_level=150,
        current_stats={},
        calculate_dps_func=mock_dps,
    )

    print(f"\nFound {len(recs)} recommendations:")
    for rec in recs:
        print(f"  {rec['type']}/{rec['subtype']}: {rec['target_display']}")
        print(f"    Cost: {rec['cost']:,.0f}💎, Gain: {rec['dps_gain']:.4f}%, Eff: {rec['efficiency']:.6f}")
