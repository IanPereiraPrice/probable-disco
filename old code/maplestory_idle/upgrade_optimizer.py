# upgrade_optimizer.py - Budget-Constrained Upgrade Path Optimizer

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum
import copy

# Cube analysis imports for enhanced recommendations
from cubes import (
    PotentialTier, CubeType, StatType, PotentialLine,
    POTENTIAL_STATS,
    create_item_score_result, calculate_expected_cubes_fast,
    calculate_stat_rankings, calculate_efficiency_score,
    get_stat_display_name, get_cached_roll_distribution,
)

# Artifact imports
from artifacts import (
    ArtifactTier, ArtifactConfig, ArtifactInstance, ARTIFACTS,
    ARTIFACT_DROP_RATES, ARTIFACT_CHEST_COSTS, TOTAL_DUPLICATES_TO_STAR,
    calculate_artifact_upgrade_efficiency, PotentialTier as ArtifactPotentialTier,
    POTENTIAL_TIER_RATES as ARTIFACT_POT_TIER_RATES,
    POTENTIAL_VALUES as ARTIFACT_POT_VALUES,
    RECONFIGURE_COSTS as ARTIFACT_RECONFIGURE_COSTS,
    POTENTIAL_SLOT_UNLOCKS as ARTIFACT_POT_SLOT_UNLOCKS,
    PREMIUM_STATS as ARTIFACT_PREMIUM_STATS,
    calculate_expected_rolls as calculate_artifact_expected_rolls
)

# Starforce imports - use accurate Markov chain calculations
from starforce_optimizer import (
    find_optimal_per_stage_strategy,
    MESO_TO_DIAMOND as SF_MESO_TO_DIAMOND,
    SCROLL_DIAMOND_COST as SF_SCROLL_COST,
    DESTRUCTION_FEE_DIAMONDS as SF_DESTRUCTION_FEE
)

# Hero Power imports for intelligent recommendations
from hero_power import (
    HeroPowerConfig, HeroPowerLine, HeroPowerTier, HeroPowerStatType,
    HeroPowerLevelConfig, score_hero_power_line, get_line_score_category,
    score_hero_power_line_for_mode, score_config_for_mode,
    calculate_line_dps_value, calculate_config_total_dps,
    rank_all_possible_lines_by_dps, format_line_ranking_for_display,
    STAT_DPS_WEIGHTS, STAT_DISPLAY_NAMES as HP_STAT_DISPLAY_NAMES,
    MODE_STAT_ADJUSTMENTS, STAT_TO_STATS_KEY,
    # Efficiency-based optimization functions
    calculate_probability_of_improvement,
    calculate_reroll_efficiency,
    analyze_lock_strategy,
)


class UpgradeType(Enum):
    """Types of upgrades available."""
    CUBE_REGULAR = "cube_regular"
    CUBE_BONUS = "cube_bonus"
    STARFORCE = "starforce"
    HERO_POWER = "hero_power"
    ARTIFACT = "artifact"
    ARTIFACT_POTENTIAL = "artifact_potential"
    HERO_POWER_POTENTIAL = "hero_power_potential"


@dataclass
class UpgradeOption:
    """A single upgrade option with cost and expected benefit."""
    upgrade_type: UpgradeType
    description: str                    # Human-readable description
    target: str                         # e.g., "hat", "gloves", or "hero_power"

    # Cost in diamonds (primary currency)
    cost_diamonds: float

    # Expected DPS improvement
    expected_dps_gain_pct: float        # e.g., 2.5 means +2.5% DPS

    # Efficiency metric (DPS gain per 1000 diamonds) - calculated in __post_init__
    efficiency: float = 0.0             # expected_dps_gain_pct / (cost_diamonds / 1000)

    # Additional details
    details: Dict = field(default_factory=dict)

    # For starforce: recommended protection strategy
    protection_strategy: Optional[str] = None

    # Current state info
    current_state: str = ""             # e.g., "★15 → ★17" or "Legendary → Mystic"

    def __post_init__(self):
        if self.cost_diamonds > 0:
            self.efficiency = self.expected_dps_gain_pct / (self.cost_diamonds / 1000)
        else:
            self.efficiency = float('inf') if self.expected_dps_gain_pct > 0 else 0


@dataclass
class UpgradePath:
    """A sequence of upgrades within a budget."""
    upgrades: List[UpgradeOption]
    total_cost: float
    total_dps_gain: float
    budget: float

    @property
    def remaining_budget(self) -> float:
        return self.budget - self.total_cost

    @property
    def average_efficiency(self) -> float:
        if self.total_cost > 0:
            return self.total_dps_gain / (self.total_cost / 1000)
        return 0


@dataclass
class EquipmentSummary:
    """Summary of equipment state for display."""
    slot: str
    stars: int
    reg_tier: str
    reg_lines_summary: str
    bonus_tier: str
    bonus_lines_summary: str
    total_dps_contribution: float  # % DPS from this slot's potentials


# =============================================================================
# COST CONSTANTS (in diamonds)
# =============================================================================

# Cube costs (using best available rates)
CUBE_COST_REGULAR = 600      # Monthly package rate
CUBE_COST_BONUS = 700        # Estimated bonus cube cost

# Starforce costs
MESO_TO_DIAMOND = 0.004      # 4 diamonds per 1000 meso
SCROLL_COST = 300            # Monthly package rate
DESTRUCTION_FEE = 4000       # 1M meso = 4000 diamonds

# Hero Power (medals) - need conversion rate
# Medals are earned through gameplay, estimate ~10 diamonds per medal equivalent
MEDAL_TO_DIAMOND = 10


# =============================================================================
# CUBE TIER-UP CALCULATIONS
# =============================================================================

# Tier-up probabilities
TIER_UP_RATES = {
    "rare": 0.06,        # rare -> epic
    "epic": 0.03333,     # epic -> unique
    "unique": 0.006,     # unique -> legendary
    "legendary": 0.0021, # legendary -> mystic
}

# Pity thresholds (regular cubes)
REGULAR_PITY = {
    "rare": 33,
    "epic": 60,
    "unique": 150,
    "legendary": 333,
    "mystic": 714,
}


def calculate_expected_cubes_to_tier(current_tier: str, target_tier: str) -> float:
    """Calculate expected cubes needed to reach target tier from current."""
    tiers = ["rare", "epic", "unique", "legendary", "mystic"]

    if current_tier not in tiers or target_tier not in tiers:
        return 0

    current_idx = tiers.index(current_tier)
    target_idx = tiers.index(target_tier)

    if current_idx >= target_idx:
        return 0

    total_cubes = 0
    for i in range(current_idx, target_idx):
        tier = tiers[i]
        p = TIER_UP_RATES.get(tier, 0.01)
        pity = REGULAR_PITY.get(tiers[i + 1], 100)

        # Truncated geometric distribution
        expected = (1 - (1 - p) ** pity) / p
        total_cubes += expected

    return total_cubes


def calculate_cube_upgrade_cost(current_tier: str, target_tier: str,
                                cube_type: str = "regular") -> float:
    """Calculate expected diamond cost for cube tier upgrade."""
    cubes_needed = calculate_expected_cubes_to_tier(current_tier, target_tier)
    cost_per_cube = CUBE_COST_REGULAR if cube_type == "regular" else CUBE_COST_BONUS
    return cubes_needed * cost_per_cube


# =============================================================================
# STARFORCE CALCULATIONS
# =============================================================================

# Simplified starforce data (success rate, destroy rate, meso cost)
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

# Sub-stat amplification by star level
STARFORCE_SUB_AMPLIFY = {
    0: 0, 5: 0, 10: 0.10, 12: 0.15, 13: 0.20, 14: 0.25,
    15: 0.35, 16: 0.45, 17: 0.55, 18: 0.70, 19: 0.85, 20: 1.00,
    21: 1.10, 22: 1.35, 23: 1.65, 24: 2.00, 25: 2.50
}


def calculate_starforce_cost(current_stars: int, target_stars: int,
                            use_protection: bool = True) -> Tuple[float, str]:
    """
    Calculate expected diamond cost for starforce upgrade.
    Returns (cost, protection_strategy).
    """
    if current_stars >= target_stars:
        return 0, "none"

    total_cost = 0
    protection_strategy = "none"

    # Simple estimation: for each star level
    for star in range(current_stars, target_stars):
        if star not in STARFORCE_DATA:
            continue

        success_rate, destroy_rate, meso_cost = STARFORCE_DATA[star]

        # Convert meso to diamonds
        diamond_cost = meso_cost * MESO_TO_DIAMOND + SCROLL_COST

        # Expected attempts to succeed
        if success_rate > 0:
            expected_attempts = 1 / success_rate
        else:
            expected_attempts = 100  # Fallback

        # Add destruction risk cost (if star >= 15)
        if star >= 15 and destroy_rate > 0:
            if use_protection and star >= 17:
                # Use protection - doubles attempt cost but halves destroy
                diamond_cost *= 2
                destroy_rate /= 2
                protection_strategy = "both"

            # Expected destruction events before success
            expected_destructions = destroy_rate * expected_attempts
            destruction_cost = expected_destructions * DESTRUCTION_FEE

            # Add rebuild cost from ★12
            if expected_destructions > 0.1:  # Significant risk
                rebuild_cost, _ = calculate_starforce_cost(12, star, use_protection)
                destruction_cost += expected_destructions * rebuild_cost

            diamond_cost += destruction_cost / expected_attempts

        total_cost += diamond_cost * expected_attempts

    return total_cost, protection_strategy


def calculate_starforce_dps_gain(current_stars: int, target_stars: int,
                                 current_sub_stats_pct: float) -> float:
    """
    Estimate DPS gain from starforce upgrade based on sub-stat amplification.
    current_sub_stats_pct: total % stats from potentials (damage%, boss%, etc.)
    """
    if current_stars >= target_stars:
        return 0

    current_amp = STARFORCE_SUB_AMPLIFY.get(current_stars, 0)
    target_amp = STARFORCE_SUB_AMPLIFY.get(target_stars, current_amp)

    # Sub stats are multiplied by (1 + amp)
    # DPS scales roughly linearly with these stats
    current_mult = 1 + current_amp
    target_mult = 1 + target_amp

    # Estimate: if you have X% sub stats, going from 1.5x to 2.0x amp
    # gives you roughly (X * 0.5) / (100 + X * 1.5) additional DPS %
    # Simplified: assume sub stats contribute ~50% of DPS multiplier

    if current_mult > 0:
        dps_gain = ((target_mult / current_mult) - 1) * 100 * 0.3  # 30% scaling factor
    else:
        dps_gain = (target_mult - 1) * 100 * 0.3

    return dps_gain


# =============================================================================
# HERO POWER CALCULATIONS
# =============================================================================

def calculate_hero_power_upgrade_cost(target_improvement_pct: float,
                                      locked_lines: int = 0) -> float:
    """
    Estimate medal cost (converted to diamonds) for hero power improvement.
    Based on simulation results for typical targets.
    """
    # Reroll costs by locked lines
    reroll_costs = {0: 86, 1: 129, 2: 172, 3: 215, 4: 258}
    cost_per_reroll = reroll_costs.get(locked_lines, 86)

    # Rough estimation based on tier probabilities
    # Mystic: 0.12%, Legendary: 1.54%
    # For 5% DPS improvement, typically need ~500-2000 rerolls

    # Scale rerolls needed with target improvement
    base_rerolls = 500
    rerolls_needed = base_rerolls * (target_improvement_pct / 5.0) ** 1.5

    medals_needed = rerolls_needed * cost_per_reroll
    diamonds_equivalent = medals_needed * MEDAL_TO_DIAMOND

    return diamonds_equivalent


# =============================================================================
# UPGRADE OPTIMIZER
# =============================================================================

class UpgradeOptimizer:
    """
    Analyzes all upgrade options and recommends optimal path within budget.
    """

    def __init__(self,
                 calc_dps_func: Callable,
                 get_stats_func: Callable,
                 equipment_state: Dict,
                 equipment_items: Dict,
                 hero_power_config,
                 current_dps: float,
                 artifact_config: Optional[ArtifactConfig] = None,
                 analyze_potential_func: Callable = None,
                 hero_power_level_config: Optional[HeroPowerLevelConfig] = None,
                 hero_power_presets: Optional[Dict[str, HeroPowerConfig]] = None,
                 combat_mode: str = "stage"):
        """
        Initialize optimizer with callbacks to main app.

        calc_dps_func: Function to calculate DPS from stats dict
        get_stats_func: Function to get current stats dict
        equipment_state: Dict of slot -> EquipmentPotential
        equipment_items: Dict of slot -> EquipmentItem (has starforce levels)
        hero_power_config: HeroPowerConfig object
        current_dps: Current calculated DPS
        artifact_config: ArtifactConfig object with current artifacts
        analyze_potential_func: Function to analyze potential for a slot (from maple_app)
        hero_power_level_config: HeroPowerLevelConfig for tier rates and costs
        hero_power_presets: Dict of preset_name -> HeroPowerConfig for multi-preset optimization
        combat_mode: Current combat mode ("stage", "boss", or "world_boss")
        """
        self.calc_dps = calc_dps_func
        self.get_stats = get_stats_func
        self.equipment = equipment_state
        self.equipment_items = equipment_items
        self.hero_power = hero_power_config
        self.current_dps = current_dps
        self.artifact_config = artifact_config
        self.analyze_potential_func = analyze_potential_func
        self.hero_power_level_config = hero_power_level_config or HeroPowerLevelConfig()
        self.hero_power_presets = hero_power_presets or {}
        self.combat_mode = combat_mode

        self.upgrade_options: List[UpgradeOption] = []

    def analyze_all_upgrades(self) -> List[UpgradeOption]:
        """Analyze all possible upgrades and return sorted by efficiency."""
        self.upgrade_options = []

        self._analyze_cube_upgrades()
        self._analyze_starforce_upgrades()
        self._analyze_hero_power_upgrades()
        self._analyze_hero_power_presets()  # Multi-preset mode optimization
        self._analyze_hero_power_line_ranking()  # Simple line ranking by DPS
        self._analyze_artifact_upgrades()
        # Note: Artifact potential rerolling disabled - needs proper implementation
        # self._analyze_artifact_potential_upgrades()
        # Note: Hero power potential rerolling disabled for now
        # self._analyze_hero_power_potential_upgrades()

        # Sort by efficiency (best first)
        self.upgrade_options.sort(key=lambda x: x.efficiency, reverse=True)

        return self.upgrade_options

    def _analyze_cube_upgrades(self):
        """
        Analyze cube upgrade options for all equipment using the same method as Cube Analyzer.

        Uses analyze_potential_func callback to maple_app._analyze_potential_for_slot()
        which provides:
        - Item score (0-100) rating current roll quality
        - Expected cubes to improve
        - Efficiency score for prioritization
        """
        if not self.analyze_potential_func:
            print("[CUBE] No analyze_potential_func provided, skipping cube analysis")
            return

        print(f"[CUBE] Starting cube analysis for {len(self.equipment)} equipment slots...")

        REGULAR_DIAMOND_PER_CUBE = 600
        BONUS_DIAMOND_PER_CUBE = 1200

        for slot, equip in self.equipment.items():
            # Analyze REGULAR potential using the same method as Cube Analyzer tab
            try:
                reg_result = self.analyze_potential_func(
                    equip, slot, self.current_dps,
                    is_bonus=False,
                    diamond_cost=REGULAR_DIAMOND_PER_CUBE,
                )
                if reg_result:
                    self._convert_cube_result_to_option(reg_result, slot, is_bonus=False)
            except Exception as e:
                import traceback
                print(f"Error analyzing regular potential for {slot}: {e}")
                traceback.print_exc()

            # Analyze BONUS potential
            try:
                bonus_result = self.analyze_potential_func(
                    equip, slot, self.current_dps,
                    is_bonus=True,
                    diamond_cost=BONUS_DIAMOND_PER_CUBE,
                )
                if bonus_result:
                    self._convert_cube_result_to_option(bonus_result, slot, is_bonus=True)
            except Exception as e:
                import traceback
                print(f"Error analyzing bonus potential for {slot}: {e}")
                traceback.print_exc()

        cube_count = len([o for o in self.upgrade_options if o.upgrade_type in (UpgradeType.CUBE_REGULAR, UpgradeType.CUBE_BONUS)])
        print(f"[CUBE] Finished. Added {cube_count} cube options.")

    def _convert_cube_result_to_option(self, result, slot: str, is_bonus: bool):
        """Convert EnhancedCubeRecommendation to UpgradeOption."""
        upgrade_type = UpgradeType.CUBE_BONUS if is_bonus else UpgradeType.CUBE_REGULAR
        pot_type = "Bonus" if is_bonus else "Regular"
        diamond_cost = 1200 if is_bonus else 600

        # Get score and tier info
        score = result.item_score.dps_relative_score
        tier_name = result.tier.value if hasattr(result.tier, 'value') else str(result.tier)

        # Score indicator
        if score < 30:
            score_indicator = "🔴"
        elif score < 60:
            score_indicator = "🟡"
        else:
            score_indicator = "🟢"

        # Calculate expected DPS gain (median improvement when you do improve)
        current_dps_gain = result.item_score.current_dps_gain
        max_dps_gain = result.item_score.best_possible_dps_gain
        improvement_room = max_dps_gain - current_dps_gain

        # Use cubes to any improvement for cost calculation
        cubes_to_improve = result.expected_cubes.cubes_to_any_improvement
        if cubes_to_improve <= 0 or cubes_to_improve > 1000:
            cubes_to_improve = 50  # Fallback

        cost = cubes_to_improve * diamond_cost

        # Expected DPS gain: use ~40% of improvement room as conservative estimate
        expected_dps_gain = improvement_room * 0.4 if improvement_room > 0 else 0.01

        # Build description
        description = (
            f"{slot.capitalize()} {pot_type} [{tier_name.capitalize()}] "
            f"{score_indicator} Score: {score:.0f}/100"
        )

        self.upgrade_options.append(UpgradeOption(
            upgrade_type=upgrade_type,
            description=description,
            target=f"{slot}_{pot_type.lower()}",
            cost_diamonds=cost,
            expected_dps_gain_pct=expected_dps_gain,
            current_state=f"Score {score:.0f}/100 ({result.expected_cubes.improvement_difficulty})",
            details={
                "cube_type": pot_type.lower(),
                "cubes_needed": cubes_to_improve,
                "item_score": score,
                "current_dps_gain": current_dps_gain,
                "max_dps_gain": max_dps_gain,
                "improvement_room": improvement_room,
                "cubes_to_improve": result.expected_cubes.cubes_to_any_improvement,
                "cubes_to_60": result.expected_cubes.cubes_to_score_60,
                "difficulty": result.expected_cubes.improvement_difficulty,
                "efficiency_score": result.efficiency_score,
                "tier": tier_name,
                "current_lines": result.current_lines_formatted,
            }
        ))

    def _analyze_starforce_upgrades(self):
        """Analyze starforce upgrade options - only next star for each item."""
        # Estimate current sub-stats from potentials for DPS gain calc
        total_sub_stats = 0
        for equip in self.equipment.values():
            for line in equip.lines + equip.bonus_lines:
                if hasattr(line, 'value'):
                    total_sub_stats += line.value

        # Analyze upgrades for each equipment item based on current stars
        for slot, item in self.equipment_items.items():
            current_stars = item.stars

            # Skip if already at max stars or below minimum for calculation
            if current_stars >= 25 or current_stars < 12:
                continue

            # Only recommend the NEXT star upgrade (not multiple)
            target_stars = current_stars + 1

            # Determine risk level based on target star
            if target_stars <= 15:
                note = "Safe (no destruction)"
            elif target_stars <= 17:
                note = "Low risk"
            elif target_stars <= 20:
                note = "Moderate risk"
            elif target_stars <= 22:
                note = "High risk"
            else:
                note = "Very high risk"

            # Use accurate Markov chain calculation from starforce_optimizer
            try:
                stage_strategies, result = find_optimal_per_stage_strategy(
                    current_stars, target_stars
                )
                cost = result.total_cost

                # Build protection strategy string from per-stage strategies
                strat_summary = set(stage_strategies.values())
                if len(strat_summary) == 1:
                    protection = list(strat_summary)[0]
                else:
                    protection = "mixed"

                destroy_prob = result.destroy_probability
            except Exception:
                # Fallback to simplified calculation if Markov fails
                cost, protection = calculate_starforce_cost(current_stars, target_stars)
                destroy_prob = 0

            dps_gain = calculate_starforce_dps_gain(current_stars, target_stars, total_sub_stats)

            self.upgrade_options.append(UpgradeOption(
                upgrade_type=UpgradeType.STARFORCE,
                description=f"{slot.capitalize()} ★{current_stars} → ★{target_stars} ({note})",
                target=f"{slot}_sf",
                cost_diamonds=cost,
                expected_dps_gain_pct=dps_gain,
                protection_strategy=protection,
                current_state=f"★{current_stars} → ★{target_stars}",
                details={
                    "slot": slot,
                    "start": current_stars,
                    "end": target_stars,
                    "protection": protection,
                    "destroy_prob": destroy_prob,
                }
            ))

    def _analyze_hero_power_upgrades(self):
        """
        Analyze hero power upgrade options using efficiency-based optimization.

        Uses probability-based analysis to determine lock/reroll decisions:
        - Calculates P(improvement) for each line
        - Accounts for cost scaling with locked lines (+43 medals per lock)
        - Uses efficiency metric: Expected_DPS_Gain / Cost_Per_Reroll
        - Dynamic threshold that DECREASES as more lines are locked

        This approach properly handles:
        - Good lines: Low P(improvement) → low efficiency → LOCK
        - Mediocre lines with many locks: High cost → lower threshold → might LOCK
        - Bad lines: High P(improvement) → high efficiency → REROLL
        """
        if not self.hero_power:
            return

        # Run efficiency-based analysis
        strategy = analyze_lock_strategy(
            self.hero_power,
            self.hero_power_level_config,
            self.calc_dps,
            self.get_stats,
        )

        # Calculate total current DPS value
        current_total_dps = sum(
            la['dps_value'] for la in strategy['efficiency_analysis']
        )

        # Build detailed line analysis for display
        line_details = []
        for la in strategy['efficiency_analysis']:
            eff = la['efficiency_result']
            rec_symbol = "🔒" if eff['recommendation'] == "LOCK" else "🔄"
            line_details.append(
                f"{rec_symbol} L{la['slot']+1}: {la['stat_name'][:12]} ({la['tier'][:3]}) "
                f"+{la['dps_value']:.2f}% DPS | P(better)={eff['probability_of_improvement']:.0%} "
                f"| Eff={eff['efficiency']:.3f}"
            )

        # Build lock/reroll slot strings
        lock_slots = strategy['lines_to_lock']
        reroll_slots = strategy['lines_to_reroll']

        lock_str = ", ".join([f"L{s+1}" for s in lock_slots]) if lock_slots else "None"
        reroll_str = ", ".join([f"L{s+1}" for s in reroll_slots]) if reroll_slots else "None"

        # Target stats reference
        target_stats = [
            ("Def Pen %", "Best for high-def enemies"),
            ("Boss Damage %", "Best for boss fights"),
            ("Damage %", "Universal damage"),
            ("Crit Damage %", "Strong with crit rate"),
        ]
        target_str = "\n".join([f"• {name}: {desc}" for name, desc in target_stats])

        if not reroll_slots:
            # All lines are efficient to keep
            self.upgrade_options.append(UpgradeOption(
                upgrade_type=UpgradeType.HERO_POWER,
                description="Hero Power: All lines efficient ✅",
                target="hero_power",
                cost_diamonds=0,
                expected_dps_gain_pct=0,
                current_state=f"Total: +{current_total_dps:.1f}% DPS (all lines hard to beat)",
                details={
                    "recommendation": "All lines have low improvement probability. Focus elsewhere.",
                    "line_analysis": "\n".join(line_details),
                    "target_stats": target_str,
                    "total_current_dps": current_total_dps,
                    "strategy": strategy,
                }
            ))
            return

        # Calculate costs
        total_medal_cost = strategy['expected_total_cost']
        diamond_cost = total_medal_cost * MEDAL_TO_DIAMOND

        # Determine urgency based on expected gain
        expected_gain = strategy['expected_dps_gain']
        if expected_gain > 0.5:
            indicator = "🔴"
            urgency = "HIGH - Large improvement potential"
        elif expected_gain > 0.2:
            indicator = "🟠"
            urgency = "MEDIUM - Moderate improvement"
        else:
            indicator = "🟡"
            urgency = "LOW - Small improvement possible"

        # Build action string
        num_locks = len(lock_slots)
        num_rerolls = len(reroll_slots)
        if num_locks > 0:
            action = f"Lock {num_locks}, Reroll {num_rerolls}"
        else:
            action = f"Reroll all {num_rerolls}"

        self.upgrade_options.append(UpgradeOption(
            upgrade_type=UpgradeType.HERO_POWER,
            description=f"Hero Power: {action} {indicator}",
            target="hero_power",
            cost_diamonds=diamond_cost,
            expected_dps_gain_pct=expected_gain,
            current_state=f"Lock [{lock_str}] | Reroll [{reroll_str}] | ~{strategy['expected_rerolls']:.0f} rolls",
            details={
                "recommendation": f"{urgency}\n\nStrategy: Lock [{lock_str}], Reroll [{reroll_str}]",
                "line_analysis": "\n".join(line_details),
                "slots_to_lock": [s+1 for s in lock_slots],
                "slots_to_reroll": [s+1 for s in reroll_slots],
                "target_stats": target_str,
                "expected_rerolls": strategy['expected_rerolls'],
                "cost_per_reroll": strategy['cost_per_reroll'],
                "total_medals": total_medal_cost,
                "total_current_dps": current_total_dps,
                "p_any_improvement": strategy.get('p_any_improvement', 0),
                "strategy": strategy,
            }
        ))

    def _analyze_hero_power_presets(self):
        """
        Analyze all Hero Power presets across all combat modes.

        Generates a SINGLE consolidated recommendation with:
        1. Best preset per mode (Stage/Boss/World Boss)
        2. All presets ranked with line-by-line analysis
        3. Total DPS contribution for each preset
        4. Reroll cost estimates for improving each preset
        """
        if not self.hero_power_presets:
            return

        combat_modes = ["stage", "boss", "world_boss"]
        mode_display = {"stage": "Stage", "boss": "Boss", "world_boss": "World Boss"}

        # Analyze each preset in detail
        preset_analysis: Dict[str, Dict] = {}
        for name, config in self.hero_power_presets.items():
            # Score each line
            line_details = []
            total_dps = 0.0
            for i, line in enumerate(config.lines):
                dps_value = calculate_line_dps_value(line, self.calc_dps, self.get_stats)
                score = score_hero_power_line(line, self.calc_dps, self.get_stats)
                category, color = get_line_score_category(score)
                stat_name = HP_STAT_DISPLAY_NAMES.get(line.stat_type, str(line.stat_type.value))
                total_dps += dps_value
                line_details.append({
                    'slot': i + 1,
                    'stat': stat_name,
                    'tier': line.tier.value,
                    'value': line.value,
                    'dps': dps_value,
                    'score': score,
                    'category': category,
                })

            # Score for each mode
            mode_scores = {}
            for mode in combat_modes:
                mode_scores[mode] = score_config_for_mode(
                    config, mode, self.calc_dps, self.get_stats
                )

            # Count good lines (score >= 50) - these would be locked during reroll
            good_lines = sum(1 for ld in line_details if ld['score'] >= 50)
            bad_lines = 6 - good_lines

            # === REROLL COST ESTIMATION ===
            # Calculate cost to reroll this preset to improve it
            # Strategy: Lock all "good" lines (score >= 50), reroll the rest
            lines_to_lock = [ld for ld in line_details if ld['score'] >= 50]
            lines_to_reroll = [ld for ld in line_details if ld['score'] < 50]
            num_locks = len(lines_to_lock)

            # Get cost per reroll from level config
            cost_per_reroll = self.hero_power_level_config.get_reroll_cost(num_locks)

            # Estimate number of rerolls needed based on how bad the lines are
            if lines_to_reroll:
                avg_bad_score = sum(ld['score'] for ld in lines_to_reroll) / len(lines_to_reroll)
                avg_bad_dps = sum(ld['dps'] for ld in lines_to_reroll) / len(lines_to_reroll)

                # Target: get each bad line to at least "Average" (score ~40, ~0.8% DPS each)
                target_dps_per_line = 0.8
                dps_gap_per_line = max(0, target_dps_per_line - avg_bad_dps)

                # Rough estimation: ~30-50 rerolls per 0.5% DPS improvement per line
                # More rerolls needed for worse lines
                base_rerolls = 40 * len(lines_to_reroll)

                # Scale by how far below target we are
                difficulty_mult = 1 + (dps_gap_per_line / target_dps_per_line)
                estimated_rerolls = int(base_rerolls * difficulty_mult)
                estimated_rerolls = max(20, min(500, estimated_rerolls))  # Clamp to reasonable range

                # Expected DPS gain = (target - current) for each bad line
                expected_dps_gain = dps_gap_per_line * len(lines_to_reroll) * 0.5  # Conservative 50%
            else:
                # All lines are good - minimal improvement possible
                estimated_rerolls = 100
                expected_dps_gain = 0.2  # Marginal improvement from already-good lines
                avg_bad_score = 0
                avg_bad_dps = 0

            # Total cost in medals
            total_medals = estimated_rerolls * cost_per_reroll
            diamond_cost = total_medals * MEDAL_TO_DIAMOND

            # Store reroll analysis
            reroll_analysis = {
                'lines_to_lock': [(ld['slot'], ld['stat'][:10], ld['tier'][:3].upper()) for ld in lines_to_lock],
                'lines_to_reroll': [(ld['slot'], ld['stat'][:10], ld['tier'][:3].upper()) for ld in lines_to_reroll],
                'num_locks': num_locks,
                'cost_per_reroll': cost_per_reroll,
                'estimated_rerolls': estimated_rerolls,
                'total_medals': total_medals,
                'diamond_cost': diamond_cost,
                'expected_dps_gain': expected_dps_gain,
                'avg_bad_line_score': avg_bad_score,
                'avg_bad_line_dps': avg_bad_dps,
            }

            preset_analysis[name] = {
                'lines': line_details,
                'total_dps': total_dps,
                'mode_scores': mode_scores,
                'good_lines': good_lines,
                'bad_lines': bad_lines,
                'reroll': reroll_analysis,
            }

        # Find best preset per mode
        best_per_mode: Dict[str, Tuple[str, float]] = {}
        for mode in combat_modes:
            best_name = max(preset_analysis.keys(), key=lambda n: preset_analysis[n]['mode_scores'][mode])
            best_score = preset_analysis[best_name]['mode_scores'][mode]
            best_per_mode[mode] = (best_name, best_score)

        # Rank all presets by total DPS
        ranked_presets = sorted(
            preset_analysis.items(),
            key=lambda x: x[1]['total_dps'],
            reverse=True
        )

        # Build summary text
        summary_lines = ["═══ BEST PRESET PER MODE ═══"]
        for mode in combat_modes:
            name, score = best_per_mode[mode]
            dps = preset_analysis[name]['total_dps']
            summary_lines.append(f"  {mode_display[mode]}: {name} (+{dps:.1f}% DPS)")

        summary_lines.append("")
        summary_lines.append("═══ ALL PRESETS RANKED ═══")
        for rank, (name, data) in enumerate(ranked_presets, 1):
            reroll = data['reroll']
            # Main preset line with DPS and reroll cost summary
            summary_lines.append(f"#{rank}. {name}: +{data['total_dps']:.1f}% DPS ({data['good_lines']} good, {data['bad_lines']} bad)")

            # Show lines for this preset
            for ld in data['lines']:
                tier_short = ld['tier'][:3].upper()
                lock_indicator = "🔒" if ld['score'] >= 50 else "🔄"
                summary_lines.append(f"    {lock_indicator} L{ld['slot']}: {ld['stat'][:12]} ({tier_short}) +{ld['dps']:.2f}% [{ld['category']}]")

            # Reroll cost estimate
            if data['bad_lines'] > 0:
                summary_lines.append(f"    📊 Reroll Est: ~{reroll['estimated_rerolls']} rolls × {reroll['cost_per_reroll']} medals = {reroll['total_medals']:,.0f} medals")
                summary_lines.append(f"       → Lock {reroll['num_locks']} lines, expect +{reroll['expected_dps_gain']:.1f}% DPS")
            else:
                summary_lines.append(f"    ✅ All lines good! Minor improvements possible (~100 rolls)")
            summary_lines.append("")  # Blank line between presets

        # Add single consolidated recommendation
        best_overall_name = ranked_presets[0][0] if ranked_presets else "None"
        best_overall_dps = ranked_presets[0][1]['total_dps'] if ranked_presets else 0

        self.upgrade_options.append(UpgradeOption(
            upgrade_type=UpgradeType.HERO_POWER,
            description=f"Hero Power Presets Analysis",
            target="hero_power_presets_summary",
            cost_diamonds=0,
            expected_dps_gain_pct=0,  # Informational
            current_state=f"Best: {best_overall_name} (+{best_overall_dps:.1f}% DPS)",
            details={
                "summary": "\n".join(summary_lines),
                "best_per_mode": {mode: {"name": n, "score": s} for mode, (n, s) in best_per_mode.items()},
                "preset_analysis": preset_analysis,
                "ranked_presets": [(name, data['total_dps']) for name, data in ranked_presets],
                "recommendation_type": "presets_summary",
            }
        ))

    def _analyze_hero_power_line_ranking(self):
        """
        Generate a simple ranking of all possible Hero Power lines by DPS contribution.

        This is a backup/reference showing what lines to aim for when rerolling,
        independent of current presets. Useful when preset analysis is complex.
        """
        # Generate the ranking using DPS callbacks
        rankings = rank_all_possible_lines_by_dps(self.calc_dps, self.get_stats)

        # Format for display
        ranking_text = format_line_ranking_for_display(rankings, top_n=10)

        # Also create a structured summary for the current combat mode
        current_mode_ranking = rankings.get(self.combat_mode, rankings.get("stage", []))
        mode_display = {"stage": "Stage", "boss": "Boss", "world_boss": "World Boss"}

        # Top 5 lines for current mode
        top_5_summary = []
        for entry in current_mode_ranking[:5]:
            top_5_summary.append(
                f"{entry['rank']}. {entry['tier']} {entry['stat']}: "
                f"{entry['value_range']} (+{entry['dps_contribution']:.2f}% DPS)"
            )

        self.upgrade_options.append(UpgradeOption(
            upgrade_type=UpgradeType.HERO_POWER,
            description=f"Hero Power Line Ranking ({mode_display.get(self.combat_mode, 'Stage')})",
            target="hero_power_line_ranking",
            cost_diamonds=0,
            expected_dps_gain_pct=0,  # Informational only
            current_state=f"Top: {current_mode_ranking[0]['tier']} {current_mode_ranking[0]['stat']}" if current_mode_ranking else "N/A",
            details={
                "ranking_text": ranking_text,
                "rankings_by_mode": rankings,
                "current_mode": self.combat_mode,
                "top_5_current_mode": "\n".join(top_5_summary),
                "recommendation_type": "line_ranking",
            }
        ))

    def _analyze_artifact_upgrades(self):
        """Analyze artifact upgrade options (awakening and acquisition)."""
        if not self.artifact_config:
            return

        # Get current artifacts from inventory
        owned_artifacts = {}
        for art in self.artifact_config.inventory:
            # Find artifact key
            for key, defn in ARTIFACTS.items():
                if defn.name == art.definition.name:
                    owned_artifacts[key] = art.awakening_stars
                    break

        # DPS value estimates per stat type (rough multipliers)
        # These convert artifact stat gains to approximate DPS%
        STAT_DPS_VALUE = {
            "hex_damage_per_stack": 8.0,     # Hex is very strong (3 stacks)
            "crit_rate": 2.0,                # CR has moderate value
            "boss_damage": 1.5,              # Boss damage direct %
            "final_damage_conditional": 3.0, # FD is strong
            "final_damage_world_boss": 2.5,
            "final_damage_guild": 2.0,
            "final_damage_growth": 2.0,
            "final_damage_per_target": 2.0,  # Fire Flower
            "damage": 1.2,                   # Damage %
            "crit_damage": 1.0,              # CD
            "normal_damage": 1.0,            # Normal damage
            "attack_flat": 0.001,            # Flat attack (low value per point)
            "def_pen": 1.5,                  # Defense pen
            "max_damage_mult": 0.8,          # Max damage multiplier
        }

        # Priority artifacts to analyze (key offensive ones)
        priority_artifacts = [
            "hexagon_necklace",   # Best damage artifact
            "book_of_ancient",    # Crit scaling
            "chalice",            # Final damage + damage%
            "star_rock",          # Boss damage
            "fire_flower",        # FD per target (mobs)
            "lit_lamp",           # World boss FD
            "icy_soul_rock",      # Crit damage
        ]

        for artifact_key in priority_artifacts:
            if artifact_key not in ARTIFACTS:
                continue

            definition = ARTIFACTS[artifact_key]
            drop_rate = ARTIFACT_DROP_RATES.get(artifact_key, 0)

            if drop_rate <= 0:
                continue

            # Current stars (0 if not owned)
            current_stars = owned_artifacts.get(artifact_key, 0)

            # Analyze upgrade options
            # Option 1: Get the artifact (if not owned, target ★1)
            if current_stars == 0:
                # Cost to get first copy
                expected_chests = 1 / drop_rate
                cost_diamonds = expected_chests * ARTIFACT_CHEST_COSTS["blue_diamond"]

                # DPS gain from having the artifact at ★0 + awakening to ★1
                active_value_0 = definition.get_active_value(0)
                inv_value_0 = definition.get_inventory_value(0)

                # Get DPS value based on stat type
                active_dps_mult = STAT_DPS_VALUE.get(definition.active_stat, 1.0)
                inv_dps_mult = STAT_DPS_VALUE.get(definition.inventory_stat, 1.0)

                # Calculate DPS gain
                dps_gain = (active_value_0 * 100 * active_dps_mult +
                           inv_value_0 * 100 * inv_dps_mult)

                # Cap at reasonable values
                dps_gain = min(dps_gain, 15.0)

                tier_label = definition.tier.value.capitalize()
                self.upgrade_options.append(UpgradeOption(
                    upgrade_type=UpgradeType.ARTIFACT,
                    description=f"Acquire {definition.name} ({tier_label})",
                    target=artifact_key,
                    cost_diamonds=cost_diamonds,
                    expected_dps_gain_pct=dps_gain,
                    current_state="Not owned → ★0",
                    details={
                        "artifact": artifact_key,
                        "chests_needed": expected_chests,
                        "tier": tier_label,
                    }
                ))

            # Option 2: Awaken existing artifact
            if current_stars < 5:
                # Analyze upgrades to ★3 and ★5 (major breakpoints for potentials)
                target_options = []
                if current_stars < 3:
                    target_options.append((3, "Unlock 2nd potential slot"))
                if current_stars < 5:
                    target_options.append((5, "Max awakening"))

                for target_stars, note in target_options:
                    if target_stars <= current_stars:
                        continue

                    result = calculate_artifact_upgrade_efficiency(
                        artifact_key, current_stars, target_stars
                    )

                    if "error" in result:
                        continue

                    cost_diamonds = result.get("expected_diamonds", 0)
                    if cost_diamonds <= 0:
                        continue

                    # Calculate DPS gain from awakening
                    active_gain = result.get("active_effect_gain", 0)
                    inv_gain = result.get("inventory_effect_gain", 0)

                    active_dps_mult = STAT_DPS_VALUE.get(definition.active_stat, 1.0)
                    inv_dps_mult = STAT_DPS_VALUE.get(definition.inventory_stat, 1.0)

                    dps_gain = (active_gain * 100 * active_dps_mult +
                               inv_gain * 100 * inv_dps_mult)

                    # Add bonus for potential slot unlocks
                    if target_stars >= 3 and current_stars < 3:
                        dps_gain += 2.0  # Bonus for 2nd potential slot
                    if target_stars >= 5 and current_stars < 5:
                        dps_gain += 3.0  # Bonus for 3rd potential (legendary only)

                    # Cap at reasonable values
                    dps_gain = min(max(dps_gain, 0.5), 10.0)

                    tier_label = definition.tier.value.capitalize()
                    self.upgrade_options.append(UpgradeOption(
                        upgrade_type=UpgradeType.ARTIFACT,
                        description=f"Awaken {definition.name} ★{current_stars}→★{target_stars} ({note})",
                        target=f"{artifact_key}_awaken_{target_stars}",
                        cost_diamonds=cost_diamonds,
                        expected_dps_gain_pct=dps_gain,
                        current_state=f"★{current_stars} → ★{target_stars}",
                        details={
                            "artifact": artifact_key,
                            "chests_needed": result.get("expected_chests", 0),
                            "duplicates": result.get("duplicates_needed", 0),
                            "tier": tier_label,
                        }
                    ))

    def _analyze_artifact_potential_upgrades(self):
        """Analyze artifact potential reroll options."""
        if not self.artifact_config:
            return

        # DPS value estimates per artifact potential stat
        # These convert potential stat gains to approximate DPS%
        STAT_DPS_VALUE = {
            "main_stat": 1.5,         # Main stat % is good but not amazing
            "damage": 1.8,            # Damage % is valuable
            "boss_damage": 2.0,       # Boss damage is highly valuable
            "normal_damage": 1.2,     # Normal damage less valuable
            "def_pen": 2.2,           # Defense pen is very strong
            "crit_rate": 1.8,         # Crit rate is good
            "min_max_damage": 1.0,    # Min/max damage is okay
        }

        # Reconfigure cost per roll (meso + stones converted to diamond equivalent)
        # Rough conversion: 1M meso ~ 50 diamonds, 1000 stones ~ 100 diamonds
        MESO_TO_DIAMOND = 50 / 1000000  # 50 diamonds per 1M meso
        STONE_TO_DIAMOND = 100 / 1000   # 100 diamonds per 1000 stones

        # Get equipped artifacts
        for slot_idx in range(3):
            if slot_idx >= len(self.artifact_config.equipped):
                continue
            artifact = self.artifact_config.equipped[slot_idx]
            if not artifact:
                continue

            artifact_key = None
            for key, defn in ARTIFACTS.items():
                if defn.name == artifact.definition.name:
                    artifact_key = key
                    break

            if not artifact_key:
                continue

            # Get artifact tier for reconfigure costs
            artifact_tier = artifact.definition.tier
            if artifact_tier not in ARTIFACT_RECONFIGURE_COSTS:
                continue

            costs = ARTIFACT_RECONFIGURE_COSTS[artifact_tier]
            cost_per_roll = (costs["meso"] * MESO_TO_DIAMOND +
                            costs["stones"] * STONE_TO_DIAMOND)

            # Get number of potential slots based on awakening
            num_slots = ARTIFACT_POT_SLOT_UNLOCKS.get(artifact.awakening_stars, 0)
            if num_slots == 0:
                continue

            # Analyze current potentials
            current_dps_value = 0.0
            current_lines_desc = []
            for pot in artifact.potentials:
                if pot.stat_type and pot.tier:
                    dps_mult = STAT_DPS_VALUE.get(pot.stat_type, 1.0)
                    current_dps_value += pot.value * dps_mult
                    tier_name = pot.tier.value if hasattr(pot.tier, 'value') else str(pot.tier)
                    current_lines_desc.append(f"{pot.stat_type} {pot.value:.1f}% ({tier_name})")

            # Target: Best possible roll (all mystic with best stats)
            best_stats = ["boss_damage", "def_pen", "damage"]
            max_dps_value = 0.0
            for i in range(num_slots):
                stat = best_stats[i % len(best_stats)]
                if stat in ARTIFACT_POT_VALUES:
                    mystic_range = ARTIFACT_POT_VALUES[stat].get(ArtifactPotentialTier.MYSTIC)
                    if mystic_range:
                        max_value = mystic_range[1]  # High end
                        dps_mult = STAT_DPS_VALUE.get(stat, 1.0)
                        max_dps_value += max_value * dps_mult

            # Calculate improvement potential
            room_to_improve = max_dps_value - current_dps_value
            if room_to_improve <= 0:
                continue  # Already near-optimal

            # Expected rolls to improve significantly (targeting 50% of max)
            target_50pct = max_dps_value * 0.50
            target_70pct = max_dps_value * 0.70

            # Simple probability estimation for improvement
            # Getting any legendary+ stat on one slot is ~8% per roll
            # Getting any good stat is higher
            prob_improvement_per_roll = 0.15  # ~15% chance to improve significantly

            if current_dps_value < target_50pct:
                expected_rolls = calculate_artifact_expected_rolls("damage", ArtifactPotentialTier.LEGENDARY, num_slots)
                expected_rolls = min(expected_rolls, 100)  # Cap at 100
                dps_gain = (target_50pct - current_dps_value) * 0.01  # Convert to %
            else:
                expected_rolls = calculate_artifact_expected_rolls("boss_damage", ArtifactPotentialTier.MYSTIC, num_slots)
                expected_rolls = min(expected_rolls, 200)
                dps_gain = (target_70pct - current_dps_value) * 0.01

            dps_gain = max(0.5, min(dps_gain, 5.0))  # Reasonable range

            total_cost = expected_rolls * cost_per_roll
            if total_cost <= 0:
                continue

            self.upgrade_options.append(UpgradeOption(
                upgrade_type=UpgradeType.ARTIFACT_POTENTIAL,
                description=f"Reroll {artifact.definition.name} potentials",
                target=f"artifact_pot_{artifact_key}",
                cost_diamonds=total_cost,
                expected_dps_gain_pct=dps_gain,
                current_state="; ".join(current_lines_desc) if current_lines_desc else "No potentials",
                details={
                    "artifact": artifact_key,
                    "slot": slot_idx,
                    "current_dps_value": current_dps_value,
                    "max_dps_value": max_dps_value,
                    "expected_rolls": expected_rolls,
                    "num_slots": num_slots,
                }
            ))

    def _analyze_hero_power_potential_upgrades(self):
        """Analyze hero power ability reroll options."""
        if not self.hero_power:
            return

        # Hero power uses same potential system as equipment
        # Cost is typically a specific item or diamonds

        # DPS value estimates per hero power potential stat
        # Keys match HeroPowerStatType enum values
        STAT_DPS_VALUE = {
            "damage": 1.5,           # Damage %
            "boss_damage": 2.0,      # Boss Damage %
            "normal_damage": 1.2,    # Normal Damage %
            "crit_damage": 1.8,      # Crit Damage %
            "crit_rate": 1.5,        # Crit Rate %
            "def_pen": 2.2,          # Defense Penetration %
            "main_stat_pct": 1.2,    # Main Stat %
            "attack_pct": 1.5,       # Attack %
            "max_dmg_mult": 1.0,     # Max Damage Mult %
            "min_dmg_mult": 0.8,     # Min Damage Mult %
            # Defensive stats (low DPS value)
            "defense": 0.1,
            "max_hp": 0.1,
        }

        # Hero ability reroll cost (estimate in diamonds)
        REROLL_COST_DIAMONDS = 300  # Approximate cost per reroll

        # Analyze current hero power lines
        current_dps_value = 0.0
        current_lines_desc = []

        for line in self.hero_power.lines:
            if hasattr(line, 'stat_type') and hasattr(line, 'value'):
                stat_key = line.stat_type.value if hasattr(line.stat_type, 'value') else str(line.stat_type)
                dps_mult = STAT_DPS_VALUE.get(stat_key, 1.0)
                current_dps_value += line.value * dps_mult

                tier_str = line.tier.value if hasattr(line, 'tier') and hasattr(line.tier, 'value') else "?"
                current_lines_desc.append(f"{stat_key} {line.value:.1f}% ({tier_str})")

        # Count number of useful lines (offensive stats only)
        offensive_stats = {"damage", "boss_damage", "normal_damage", "crit_damage",
                          "crit_rate", "def_pen", "main_stat_pct", "attack_pct",
                          "max_dmg_mult", "min_dmg_mult"}
        useful_lines = sum(1 for line in self.hero_power.lines
                         if hasattr(line, 'stat_type') and
                         (line.stat_type.value if hasattr(line.stat_type, 'value') else str(line.stat_type))
                         in offensive_stats)

        # Max value estimate (5 perfect mystic lines)
        max_lines = 5
        max_dps_value = max_lines * 20 * 2.0  # 5 lines × 20% × 2.0 dps mult = 200

        room_to_improve = max_dps_value - current_dps_value
        if room_to_improve <= 10:  # Already pretty good
            return

        # Calculate expected rolls to improve
        if useful_lines < 3:
            # Easy to improve - targeting any good line
            expected_rolls = 10
            dps_gain = room_to_improve * 0.3 * 0.01  # Expect 30% improvement
        elif useful_lines < 5:
            # Medium difficulty
            expected_rolls = 30
            dps_gain = room_to_improve * 0.2 * 0.01
        else:
            # Hard to improve further
            expected_rolls = 100
            dps_gain = room_to_improve * 0.1 * 0.01

        dps_gain = max(0.3, min(dps_gain, 3.0))
        total_cost = expected_rolls * REROLL_COST_DIAMONDS

        self.upgrade_options.append(UpgradeOption(
            upgrade_type=UpgradeType.HERO_POWER_POTENTIAL,
            description=f"Reroll Hero Power abilities",
            target="hero_power_potential",
            cost_diamonds=total_cost,
            expected_dps_gain_pct=dps_gain,
            current_state=f"{useful_lines}/5 useful lines",
            details={
                "current_dps_value": current_dps_value,
                "max_dps_value": max_dps_value,
                "expected_rolls": expected_rolls,
                "useful_lines": useful_lines,
                "current_lines": current_lines_desc,
            }
        ))

    def get_optimal_path(self, budget: float) -> UpgradePath:
        """
        Get the optimal upgrade path within budget.
        Uses greedy algorithm: always pick highest efficiency option that fits.
        """
        if not self.upgrade_options:
            self.analyze_all_upgrades()

        selected = []
        remaining_budget = budget
        used_targets = set()  # Track which slots/systems already upgraded

        # Sort by efficiency
        sorted_options = sorted(self.upgrade_options,
                               key=lambda x: x.efficiency, reverse=True)

        for option in sorted_options:
            # Skip if already upgraded this target
            target_key = f"{option.upgrade_type.value}_{option.target}"
            if target_key in used_targets:
                continue

            # Check if fits budget
            if option.cost_diamonds <= remaining_budget:
                selected.append(option)
                remaining_budget -= option.cost_diamonds
                used_targets.add(target_key)

        total_cost = sum(opt.cost_diamonds for opt in selected)
        total_gain = sum(opt.expected_dps_gain_pct for opt in selected)

        return UpgradePath(
            upgrades=selected,
            total_cost=total_cost,
            total_dps_gain=total_gain,
            budget=budget
        )

    def get_equipment_summary(self) -> List[EquipmentSummary]:
        """Get summary of all equipment for display."""
        summaries = []

        for slot, equip in self.equipment.items():
            # Format regular lines
            reg_lines = []
            for line in equip.lines:
                if hasattr(line, 'stat_type') and hasattr(line, 'value'):
                    stat_name = line.stat_type.value if hasattr(line.stat_type, 'value') else str(line.stat_type)
                    reg_lines.append(f"{stat_name}: {line.value:.1f}%")

            # Format bonus lines
            bonus_lines = []
            for line in equip.bonus_lines:
                if hasattr(line, 'stat_type') and hasattr(line, 'value'):
                    stat_name = line.stat_type.value if hasattr(line.stat_type, 'value') else str(line.stat_type)
                    bonus_lines.append(f"{stat_name}: {line.value:.1f}%")

            # Get tier strings
            reg_tier = equip.tier.value if hasattr(equip.tier, 'value') else str(equip.tier)
            bonus_tier = equip.bonus_tier.value if hasattr(equip.bonus_tier, 'value') else str(equip.bonus_tier)

            summaries.append(EquipmentSummary(
                slot=slot,
                stars=0,  # Will be filled from equipment_items if available
                reg_tier=reg_tier,
                reg_lines_summary=", ".join(reg_lines) if reg_lines else "(empty)",
                bonus_tier=bonus_tier,
                bonus_lines_summary=", ".join(bonus_lines) if bonus_lines else "(empty)",
                total_dps_contribution=0  # Would need DPS calc to fill
            ))

        return summaries
