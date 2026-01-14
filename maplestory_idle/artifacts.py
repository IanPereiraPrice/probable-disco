"""
MapleStory Idle - Artifact System
==================================
Artifact mechanics, awakening, potentials, and calculations.

Last Updated: December 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class ArtifactTier(Enum):
    """Artifact rarity tiers."""
    EPIC = "epic"
    UNIQUE = "unique"
    LEGENDARY = "legendary"


class CombatScenario(Enum):
    """Combat scenarios for conditional artifact effects."""
    NORMAL = "normal"       # Regular stage farming
    BOSS = "boss"           # Boss stages (single target)
    WORLD_BOSS = "world_boss"  # World Boss content


class PotentialTier(Enum):
    """Artifact potential tiers."""
    RARE = "rare"
    EPIC = "epic"
    UNIQUE = "unique"
    LEGENDARY = "legendary"
    MYSTIC = "mystic"


# =============================================================================
# CONSTANTS
# =============================================================================

# Potential tier probabilities (per slot)
POTENTIAL_TIER_RATES = {
    PotentialTier.MYSTIC: 0.009675,
    PotentialTier.LEGENDARY: 0.071236,
    PotentialTier.UNIQUE: 0.193493,
    PotentialTier.EPIC: 0.2902388,
    PotentialTier.RARE: 0.435358,
}

# Stat roll probabilities (independent of tier)
# Standard stats: 10.5075% each, Premium stats: 5.2895% each (half rate)
STANDARD_STAT_RATE = 0.105075
PREMIUM_STAT_RATE = 0.052895  # Half of standard

POTENTIAL_STAT_RATES = {
    # Standard stats (10.5075% each)
    "main_stat_pct": STANDARD_STAT_RATE,
    "damage_taken_decrease": STANDARD_STAT_RATE,
    "defense": STANDARD_STAT_RATE,
    "accuracy": STANDARD_STAT_RATE,
    "crit_rate": STANDARD_STAT_RATE,
    "min_damage_mult": STANDARD_STAT_RATE,
    "max_damage_mult": STANDARD_STAT_RATE,
    # Premium stats (5.2895% each - half rate)
    "boss_damage": PREMIUM_STAT_RATE,
    "normal_damage": PREMIUM_STAT_RATE,
    "status_effect_damage": PREMIUM_STAT_RATE,
    "damage": PREMIUM_STAT_RATE,
    "def_pen": PREMIUM_STAT_RATE,
}

# Mystic tier value distribution (for stats with two values)
MYSTIC_LOW_VALUE_CHANCE = 0.75   # 75% chance for lower value
MYSTIC_HIGH_VALUE_CHANCE = 0.25  # 25% chance for higher value

# Potential values by tier (stat: {tier: (low, high)})
# For Mystic tier with two values: low has 75% chance, high has 25% chance
POTENTIAL_VALUES = {
    "main_stat_pct": {
        PotentialTier.RARE: (2.0, 2.0),
        PotentialTier.EPIC: (3.0, 3.0),
        PotentialTier.UNIQUE: (4.5, 4.5),
        PotentialTier.LEGENDARY: (7.0, 7.0),
        PotentialTier.MYSTIC: (10.0, 12.0),
    },
    "damage_taken_decrease": {
        PotentialTier.RARE: (2.0, 2.0),
        PotentialTier.EPIC: (3.0, 3.0),
        PotentialTier.UNIQUE: (4.5, 4.5),
        PotentialTier.LEGENDARY: (7.0, 7.0),
        PotentialTier.MYSTIC: (10.0, 12.0),
    },
    "defense": {
        PotentialTier.RARE: (2.0, 2.0),
        PotentialTier.EPIC: (3.0, 3.0),
        PotentialTier.UNIQUE: (4.5, 4.5),
        PotentialTier.LEGENDARY: (7.0, 7.0),
        PotentialTier.MYSTIC: (10.0, 12.0),
    },
    "accuracy": {
        PotentialTier.RARE: (2.0, 2.0),
        PotentialTier.EPIC: (3.0, 3.0),
        PotentialTier.UNIQUE: (4.5, 4.5),
        PotentialTier.LEGENDARY: (7.0, 7.0),
        PotentialTier.MYSTIC: (10.0, 12.0),
    },
    "crit_rate": {
        PotentialTier.RARE: (2.0, 2.0),
        PotentialTier.EPIC: (3.0, 3.0),
        PotentialTier.UNIQUE: (4.5, 4.5),
        PotentialTier.LEGENDARY: (7.0, 7.0),
        PotentialTier.MYSTIC: (10.0, 12.0),
    },
    "min_damage_mult": {
        PotentialTier.RARE: (2.0, 2.0),
        PotentialTier.EPIC: (3.0, 3.0),
        PotentialTier.UNIQUE: (4.5, 4.5),
        PotentialTier.LEGENDARY: (7.0, 7.0),
        PotentialTier.MYSTIC: (10.0, 12.0),
    },
    "max_damage_mult": {
        PotentialTier.RARE: (2.0, 2.0),
        PotentialTier.EPIC: (3.0, 3.0),
        PotentialTier.UNIQUE: (4.5, 4.5),
        PotentialTier.LEGENDARY: (7.0, 7.0),
        PotentialTier.MYSTIC: (10.0, 12.0),
    },
    "damage": {
        PotentialTier.RARE: (4.0, 4.0),
        PotentialTier.EPIC: (6.0, 6.0),
        PotentialTier.UNIQUE: (9.0, 9.0),
        PotentialTier.LEGENDARY: (14.0, 14.0),
        PotentialTier.MYSTIC: (20.0, 24.0),
    },
    "boss_damage": {
        PotentialTier.RARE: (4.0, 4.0),
        PotentialTier.EPIC: (6.0, 6.0),
        PotentialTier.UNIQUE: (9.0, 9.0),
        PotentialTier.LEGENDARY: (14.0, 14.0),
        PotentialTier.MYSTIC: (20.0, 24.0),
    },
    "normal_damage": {
        PotentialTier.RARE: (4.0, 4.0),
        PotentialTier.EPIC: (6.0, 6.0),
        PotentialTier.UNIQUE: (9.0, 9.0),
        PotentialTier.LEGENDARY: (14.0, 14.0),
        PotentialTier.MYSTIC: (20.0, 24.0),
    },
    "status_effect_damage": {
        PotentialTier.RARE: (4.0, 4.0),
        PotentialTier.EPIC: (6.0, 6.0),
        PotentialTier.UNIQUE: (9.0, 9.0),
        PotentialTier.LEGENDARY: (14.0, 14.0),
        PotentialTier.MYSTIC: (20.0, 24.0),
    },
    "def_pen": {
        PotentialTier.RARE: (2.0, 2.0),
        PotentialTier.EPIC: (3.0, 3.0),
        PotentialTier.UNIQUE: (4.5, 4.5),
        PotentialTier.LEGENDARY: (7.0, 7.0),
        PotentialTier.MYSTIC: (10.0, 12.0),
    },
}

# Premium stats appear at half rate
PREMIUM_STATS = ["boss_damage", "normal_damage", "status_effect_damage", "damage", "def_pen"]

# Reconfigure costs (meso + artifact enhancers)
RECONFIGURE_COSTS = {
    ArtifactTier.LEGENDARY: {"meso": 20000, "artifact_enhancers": 2000},
    ArtifactTier.UNIQUE: {"meso": 15000, "artifact_enhancers": 1500},
    ArtifactTier.EPIC: {"meso": 10000, "artifact_enhancers": 1000},
}

# Maximum potential slots by artifact tier
# Epic: 1 slot max, Unique: 2 slots max, Legendary: 3 slots max
MAX_POTENTIAL_SLOTS_BY_TIER = {
    ArtifactTier.EPIC: 1,
    ArtifactTier.UNIQUE: 2,
    ArtifactTier.LEGENDARY: 3,
}

# Potential slots unlock at these awakening levels
POTENTIAL_SLOT_UNLOCKS = {
    0: 0,  # 0 slots at ★0
    1: 1,  # 1 slot at ★1
    2: 1,
    3: 2,  # 2 slots at ★3
    4: 2,
    5: 3,  # 3 slots at ★5 (Legendary only)
}

# =============================================================================
# ARTIFACT CHEST DROP RATES
# =============================================================================

# Drop rates from artifact chests (per artifact)
# Tier rates: Epic 89.5%, Unique 9.5%, Legendary 1%
# Individual rates = tier rate / number of artifacts in tier
ARTIFACT_DROP_RATES = {
    # Epic tier: 89.5% / 4 artifacts = 22.375% each
    "shamaness_marble": 0.22375,
    "contract_of_darkness": 0.22375,
    "charm_of_undead": 0.22375,
    "pigs_ribbon": 0.22375,

    # Unique tier: 9.5% / 7 artifacts = 1.357% each
    "rainbow_snail_shell": 0.013571,
    "arwens_glass_shoes": 0.013571,
    "mushmom_cap": 0.013571,
    "clear_spring_water": 0.013571,
    "athena_pierces_gloves": 0.013571,
    "hexagon_necklace": 0.013571,
    "zakum_raid_artifact": 0.013571,

    # Legendary tier: 1% / 14 artifacts = 0.0714% each
    "chalice": 0.000714,
    "old_music_box": 0.000714,
    "silver_pendant": 0.000714,
    "book_of_ancient": 0.000714,
    "star_rock": 0.000714,
    "fire_flower": 0.000714,
    "soul_contract": 0.000714,
    "lit_lamp": 0.000714,
    "ancient_text_piece": 0.000714,
    "sayrams_necklace": 0.000714,
    "icy_soul_rock": 0.000714,
    "soul_pouch": 0.000714,
    "lunar_dew": 0.000714,
    "flaming_lava": 0.000714,
}

# Tier totals
ARTIFACT_TIER_DROP_RATES = {
    ArtifactTier.EPIC: 0.895,      # ~89.5% chance for any epic
    ArtifactTier.UNIQUE: 0.095,    # ~9.5% chance for any unique
    ArtifactTier.LEGENDARY: 0.01,  # ~1% chance for any legendary
}

# =============================================================================
# SYNTHESIS SYSTEM
# =============================================================================

# Synthesis costs (number of max-star artifacts needed)
SYNTHESIS_COSTS = {
    # 20 max-star Epic → 1 Random Unique
    (ArtifactTier.EPIC, ArtifactTier.UNIQUE): 20,
    # 15 max-star Unique → 1 Random Legendary
    (ArtifactTier.UNIQUE, ArtifactTier.LEGENDARY): 15,
}

# =============================================================================
# AWAKENING COSTS (Per Tier)
# =============================================================================

# Cost to awaken artifact (duplicate artifacts needed per star)
# Costs vary by tier
AWAKENING_COSTS_BY_TIER = {
    ArtifactTier.EPIC: {
        # star_level: duplicates_needed
        1: 5,   # ★0 → ★1
        2: 7,   # ★1 → ★2
        3: 12,  # ★2 → ★3
        4: 16,  # ★3 → ★4
        5: 20,  # ★4 → ★5
    },
    ArtifactTier.UNIQUE: {
        1: 2,   # ★0 → ★1
        2: 4,   # ★1 → ★2
        3: 6,   # ★2 → ★3
        4: 10,  # ★3 → ★4
        5: 15,  # ★4 → ★5
    },
    ArtifactTier.LEGENDARY: {
        1: 1,   # ★0 → ★1
        2: 2,   # ★1 → ★2
        3: 3,   # ★2 → ★3
        4: 4,   # ★3 → ★4
        5: 5,   # ★4 → ★5
    },
}

# Total duplicates needed to reach each star level from ★0 (by tier)
TOTAL_DUPLICATES_BY_TIER = {
    ArtifactTier.EPIC: {
        0: 0,
        1: 5,    # 5
        2: 12,   # 5 + 7
        3: 24,   # 5 + 7 + 12
        4: 40,   # 5 + 7 + 12 + 16
        5: 60,   # 5 + 7 + 12 + 16 + 20
    },
    ArtifactTier.UNIQUE: {
        0: 0,
        1: 2,    # 2
        2: 6,    # 2 + 4
        3: 12,   # 2 + 4 + 6
        4: 22,   # 2 + 4 + 6 + 10
        5: 37,   # 2 + 4 + 6 + 10 + 15
    },
    ArtifactTier.LEGENDARY: {
        0: 0,
        1: 1,    # 1
        2: 3,    # 1 + 2
        3: 6,    # 1 + 2 + 3
        4: 10,   # 1 + 2 + 3 + 4
        5: 15,   # 1 + 2 + 3 + 4 + 5
    },
}

# Legacy: Default awakening costs (Legendary tier for backwards compatibility)
AWAKENING_COSTS = AWAKENING_COSTS_BY_TIER[ArtifactTier.LEGENDARY]
TOTAL_DUPLICATES_TO_STAR = TOTAL_DUPLICATES_BY_TIER[ArtifactTier.LEGENDARY]

# =============================================================================
# ARTIFACT CHEST COSTS
# =============================================================================

ARTIFACT_CHEST_COSTS = {
    "blue_diamond": 1500,    # 300/week limit
    "red_diamond": 1500,     # 5/week limit
    "arena_coin": 500,       # 10/week limit
}


# =============================================================================
# RESONANCE SYSTEM
# =============================================================================

# Resonance level cap formula:
# max_level = RESONANCE_BASE_LEVEL_CAP + (total_artifact_stars * RESONANCE_LEVELS_PER_STAR)
RESONANCE_BASE_LEVEL_CAP = 80
RESONANCE_LEVELS_PER_STAR = 5

# Maximum possible resonance level (25 artifacts × 5 stars × 5 levels/star + 80 base)
# = 125 × 5 + 80 = 705
RESONANCE_MAX_LEVEL = 705


def calculate_resonance_max_level(total_artifact_stars: int) -> int:
    """
    Calculate maximum resonance level based on total artifact stars.

    Args:
        total_artifact_stars: Sum of all artifact star levels (0-125 for 25 artifacts at 5 stars each)

    Returns:
        Maximum resonance level achievable
    """
    return RESONANCE_BASE_LEVEL_CAP + (total_artifact_stars * RESONANCE_LEVELS_PER_STAR)


def calculate_resonance_hp(level: int) -> int:
    """
    Calculate HP bonus at a given resonance level using geometric series.

    Formula: HP(L) = round(1000 + 33.392 × (1.0035^L - 1.0035) / 0.0035)

    The HP bonus grows at 0.35% per level, starting from 1000 at level 1.
    Max error: ±1 across all tested levels (1-361).

    Args:
        level: Resonance level (1 to 705)

    Returns:
        Max HP bonus
    """
    if level < 1:
        return 0
    if level == 1:
        return 1000
    # Geometric series: HP = base + A * (B^L - B) / (B - 1)
    A = 33.392
    B = 1.0035
    return round(1000 + A * (B ** level - B) / (B - 1))


def calculate_resonance_main_stat(level: int) -> int:
    """
    Calculate main stat bonus (FLAT) at a given resonance level.

    Formula: Main(L) = floor(HP(L) / 10)

    Main stat is derived from HP, maintaining perfect 10:1 ratio.
    Max error: ±1 across all tested levels (1-361).

    Args:
        level: Resonance level (1 to 705)

    Returns:
        Main stat bonus (DEX/STR/INT/LUK depending on class) - FLAT, not percentage
    """
    if level < 1:
        return 0
    return calculate_resonance_hp(level) // 10


def calculate_resonance_upgrade_cost(level: int) -> int:
    """
    Calculate artifact enhancer cost to upgrade FROM a given level to level+1.

    Formula: round(1490 + 18.28*L + 0.01537*L² + 0.0000195*L³)

    Args:
        level: Current resonance level

    Returns:
        Artifact enhancers needed to upgrade to next level
    """
    if level < 1:
        return 0
    return round(1490.0031 + 18.280250 * level + 0.01536632 * level**2 + 0.0000194991 * level**3)


def calculate_resonance_total_cost(from_level: int, to_level: int) -> int:
    """
    Calculate total artifact enhancer cost to upgrade from one level to another.

    Args:
        from_level: Starting resonance level
        to_level: Target resonance level

    Returns:
        Total artifact enhancers needed
    """
    if to_level <= from_level:
        return 0
    return sum(calculate_resonance_upgrade_cost(lvl) for lvl in range(from_level, to_level))


def calculate_resonance_stats_at_level(level: int) -> Dict[str, int]:
    """
    Get all resonance stats at a given level.

    Args:
        level: Resonance level

    Returns:
        Dict with 'main_stat_flat' (FLAT bonus) and 'max_hp' values
    """
    return {
        'main_stat_flat': calculate_resonance_main_stat(level),
        'max_hp': calculate_resonance_hp(level),
    }


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ArtifactPotentialLine:
    """A single potential line on an artifact."""
    stat: str
    value: float
    tier: PotentialTier
    slot: int  # 1, 2, or 3


class EffectType(Enum):
    """Types of artifact effects."""
    FLAT = "flat"  # Direct additive bonus: stat += value
    DERIVED = "derived"  # Value derived from another stat: stat += source_stat * multiplier
    MULTIPLICATIVE = "multiplicative"  # Multiplicative bonus: applied as multiplier (e.g., Hex)


@dataclass
class ArtifactEffect:
    """
    A single stat effect from an artifact.

    Effect types:
    1. FLAT: Direct stat bonus (stat += base + stars * per_star)
    2. DERIVED: Bonus derived from another stat (stat += source_stat * multiplier)
    3. MULTIPLICATIVE: Applied as a multiplier (e.g., Hex's damage × multiplier)
    """
    stat: str  # Target stat to modify (e.g., "crit_rate", "max_damage_mult")
    base: float  # Value at ★0 (or base multiplier for derived)
    per_star: float  # Increase per star level
    effect_type: EffectType = EffectType.FLAT

    # For DERIVED effects: source stat to read from aggregated stats
    derived_from: Optional[str] = None

    # For MULTIPLICATIVE effects with stacking (e.g., Hex)
    max_stacks: int = 1

    def get_value(self, stars: int, stacks: Optional[int] = None) -> float:
        """Get the value at given star level and stacks."""
        base_value = self.base + (stars * self.per_star)

        if self.effect_type == EffectType.MULTIPLICATIVE and self.max_stacks > 1:
            # For stacking multiplicative effects like Hex
            effective_stacks = min(stacks if stacks is not None else self.max_stacks, self.max_stacks)
            return base_value * effective_stacks

        return base_value

    def is_derived(self) -> bool:
        """Check if this is a derived effect."""
        return self.effect_type == EffectType.DERIVED


@dataclass
class ArtifactDefinition:
    """Definition of an artifact type with scaling."""
    name: str
    tier: ArtifactTier

    # Active effects (when equipped in slot) - list of ArtifactEffect
    # Examples:
    #   - Simple: [ArtifactEffect("crit_rate", 0.10, 0.02)]
    #   - Two stats (Rainbow): [ArtifactEffect("crit_rate", 0.15, 0.03),
    #                           ArtifactEffect("crit_damage", 0.20, 0.04)]
    #   - Derived (Athena): [ArtifactEffect("attack_speed", 0.08, 0.016),
    #                        ArtifactEffect("max_damage_mult", 0.25, 0.05, DERIVED, "attack_speed")]
    #   - Multiplicative (Hex): [ArtifactEffect("damage_multiplier", 0.15, 0.03, MULTIPLICATIVE, max_stacks=3)]
    active_effects: List[ArtifactEffect] = field(default_factory=list)

    # Active description for UI display
    active_description: str = ""

    # Inventory effect (always active) - could also be a list but keeping simple for now
    inventory_description: str = ""
    inventory_stat: str = ""
    inventory_base: float = 0.0
    inventory_per_star: float = 0.0

    # LEGACY fields - will be removed once all artifacts are migrated
    active_stat: str = ""  # What stat it affects
    active_base: float = 0.0  # Value at ★0
    active_per_star: float = 0.0  # Additional value per star
    max_stacks: int = 1  # For stackable effects like Hex
    scales_with: Optional[str] = None  # For Book of Ancient
    conversion_rate_base: float = 0.0
    conversion_rate_per_star: float = 0.0

    # Uptime mechanics (for DPS calculation)
    scenario: Optional[str] = None  # Restrict to specific scenario (e.g., "world_boss")
    buff_duration: float = 0.0  # Duration in seconds (0 = permanent)
    buff_cooldown: float = 0.0  # Cooldown between procs (for timed buffs)
    trigger_delay: float = 0.0  # Delay before first trigger (for boss-kill buffs like Chalice)
    proc_chance: float = 1.0  # 1.0 = always, 0.15 = 15% proc rate
    ramp_time: float = 0.0  # Time to reach max stacks (seconds)
    max_targets: int = 0  # For per-target effects (Fire Flower)

    def get_active_value(self, stars: int) -> float:
        """Get active effect value at given awakening level."""
        return self.active_base + (stars * self.active_per_star)

    def get_inventory_value(self, stars: int) -> float:
        """Get inventory effect value at given awakening level."""
        return self.inventory_base + (stars * self.inventory_per_star)

    def get_conversion_rate(self, stars: int) -> float:
        """Get conversion rate at given awakening level (for Book of Ancient)."""
        return self.conversion_rate_base + (stars * self.conversion_rate_per_star)

    def get_effective_uptime(self, fight_duration: float = 60.0) -> float:
        """Calculate effective uptime for DPS calculations.

        Uses the unified cooldown_calc module for consistent calculations
        across artifacts and skills.

        Returns a value between 0.0 and 1.0 representing the fraction of time
        the effect is active.
        """
        from cooldown_calc import calculate_buff_uptime
        import math

        # Handle trigger delay (e.g., Chalice waits for boss kill at ~10s)
        # The delay shifts when the buff can first trigger, reducing effective buff time
        trigger_delay = self.trigger_delay

        # Timed buffs with cooldown - use unified module
        if self.buff_duration > 0 and self.buff_cooldown > 0:
            # Calculate uptime on the remaining fight duration after delay
            remaining_duration = fight_duration - trigger_delay if not math.isinf(fight_duration) else fight_duration
            if remaining_duration <= 0:
                return 0.0
            # Get uptime for the remaining duration
            remaining_uptime = calculate_buff_uptime(
                cooldown=self.buff_cooldown,
                buff_duration=self.buff_duration,
                fight_duration=remaining_duration,
            )
            # Scale back to full fight duration
            return remaining_uptime * remaining_duration / fight_duration if not math.isinf(fight_duration) else remaining_uptime

        # Stacking buffs: reduced effectiveness during ramp-up
        if self.ramp_time > 0:
            # At infinite fight duration, always at max stacks
            if math.isinf(fight_duration):
                return 1.0
            if fight_duration <= 0:
                return 0.0
            # Average effectiveness = (full_duration + ramp_duration/2) / total_duration
            full_duration = max(0, fight_duration - self.ramp_time)
            if fight_duration > self.ramp_time:
                return (full_duration + self.ramp_time * 0.5) / fight_duration
            else:
                # Fight ends during ramp
                return 0.5 * fight_duration / self.ramp_time * 0.5

        # Proc-based effects
        if self.proc_chance < 1.0:
            return self.proc_chance

        # Always-on effects
        return 1.0

    def get_effective_value(self, stars: int, scenario: str = "normal",
                            fight_duration: float = 60.0) -> float:
        """Get effective active value accounting for uptime and scenario.

        Returns 0 if the artifact doesn't apply to the given scenario.
        """
        # Check scenario restriction
        if self.scenario and self.scenario != scenario:
            return 0.0

        base_value = self.get_active_value(stars)
        uptime = self.get_effective_uptime(fight_duration)
        return base_value * uptime

    def applies_to_scenario(self, scenario: str) -> bool:
        """Check if this artifact's active effect applies to a scenario."""
        if self.scenario is None:
            return True  # Universal effect
        return self.scenario == scenario


@dataclass
class ArtifactInstance:
    """A player's specific artifact with awakening and potentials."""
    definition: ArtifactDefinition
    awakening_stars: int = 0
    potentials: List[ArtifactPotentialLine] = field(default_factory=list)

    @property
    def potential_slots(self) -> int:
        """Number of potential slots available."""
        slots = POTENTIAL_SLOT_UNLOCKS.get(self.awakening_stars, 0)
        # Legendary gets 3 slots at ★5, others cap at 2
        if self.definition.tier != ArtifactTier.LEGENDARY and slots > 2:
            slots = 2
        return slots

    def get_active_value(self) -> float:
        """Get current active effect value."""
        return self.definition.get_active_value(self.awakening_stars)

    def get_inventory_value(self) -> float:
        """Get current inventory effect value."""
        return self.definition.get_inventory_value(self.awakening_stars)

    def get_potential_stats(self) -> Dict[str, float]:
        """Get total stats from potentials.

        IMPORTANT: Potential values are stored as percentages (e.g., 14 for 14%)
        but inventory effects use decimals (e.g., 0.15 for 15%). This method
        normalizes potential values to decimals for consistency.
        """
        # Stats that are percentages and need to be converted to decimals
        PERCENTAGE_STATS = {
            "main_stat_pct", "damage", "boss_damage", "normal_damage",
            "def_pen", "crit_rate", "min_max_damage"
        }

        stats = {}
        for pot in self.potentials[:self.potential_slots]:
            value = pot.value
            # Convert percentage stats to decimals (14% -> 0.14)
            if pot.stat in PERCENTAGE_STATS:
                value = value / 100.0
            if pot.stat in stats:
                stats[pot.stat] += value
            else:
                stats[pot.stat] = value
        return stats


@dataclass
class ArtifactConfig:
    """Player's complete artifact configuration."""
    # Three equipped artifact slots
    equipped: List[Optional[ArtifactInstance]] = field(default_factory=lambda: [None, None, None])

    # All owned artifacts (for inventory effects)
    inventory: List[ArtifactInstance] = field(default_factory=list)

    # Resonance (sum of all awakening stars)
    def get_resonance(self) -> int:
        """Get total resonance from all artifacts."""
        total = 0
        for artifact in self.inventory:
            total += artifact.awakening_stars
        return total

    def get_resonance_bonus(self) -> Dict[str, float]:
        """Get bonus stats from resonance (FLAT main stat, not percentage)."""
        resonance = self.get_resonance()
        # See TODO_REFACTOR.md - this linear approximation should use calculate_resonance_stats_at_level()
        main_stat_per_star = 10.0
        hp_per_star = 100.0
        return {
            "main_stat_flat": resonance * main_stat_per_star,
            "max_hp": resonance * hp_per_star,
        }

    def get_equipped_active_stats(self) -> Dict[str, float]:
        """Get total active stats from equipped artifacts."""
        stats = {}
        for artifact in self.equipped:
            if artifact is None:
                continue
            # Use active_effects (all artifacts now use this format)
            for effect in artifact.definition.active_effects:
                # Skip derived effects - they're calculated from other stats
                if effect.effect_type == EffectType.DERIVED:
                    continue
                stat = effect.stat
                value = effect.get_value(artifact.stars)
                if stat in stats:
                    stats[stat] += value
                else:
                    stats[stat] = value
        return stats

    def get_inventory_stats(self) -> Dict[str, float]:
        """Get total inventory stats from ALL artifacts."""
        stats = {}
        for artifact in self.inventory:
            stat = artifact.definition.inventory_stat
            value = artifact.get_inventory_value()
            if stat in stats:
                stats[stat] += value
            else:
                stats[stat] = value
            # Also add potential stats
            for pot_stat, pot_value in artifact.get_potential_stats().items():
                if pot_stat in stats:
                    stats[pot_stat] += pot_value
                else:
                    stats[pot_stat] = pot_value
        return stats

    def get_all_stats(self) -> Dict[str, float]:
        """Get all artifact stats combined."""
        stats = {}

        # Active effects from equipped
        for key, value in self.get_equipped_active_stats().items():
            stats[key] = stats.get(key, 0) + value

        # Inventory effects from all
        for key, value in self.get_inventory_stats().items():
            stats[key] = stats.get(key, 0) + value

        # Resonance bonus
        for key, value in self.get_resonance_bonus().items():
            stats[key] = stats.get(key, 0) + value

        return stats

    def get_stats(self, job_class=None):
        """
        Get all artifact stats as a StatBlock.

        Note: This returns ADDITIVE stats only. Multiplicative effects like
        Hex damage multiplier and derived effects (Book of Ancient CD from CR)
        need special handling in DPS calculation.

        Args:
            job_class: Job class for main_stat mapping (defaults to Bowmaster)

        Returns:
            StatBlock with all artifact stats
        """
        from stats import StatBlock, create_stat_block_for_job
        from job_classes import JobClass

        if job_class is None:
            job_class = JobClass.BOWMASTER

        all_stats = self.get_all_stats()

        # Map artifact stats to StatBlock fields
        # Note: main_stat_flat from resonance, main_stat_pct from potentials
        return create_stat_block_for_job(
            job_class=job_class,
            main_stat_flat=all_stats.get('main_stat_flat', 0),
            main_stat_pct=all_stats.get('main_stat', 0),  # Artifact potentials use 'main_stat' for %
            attack_flat=all_stats.get('attack_flat', 0),
            damage_pct=all_stats.get('damage', 0) * 100 if all_stats.get('damage', 0) < 1 else all_stats.get('damage', 0),
            boss_damage=all_stats.get('boss_damage', 0) * 100 if all_stats.get('boss_damage', 0) < 1 else all_stats.get('boss_damage', 0),
            normal_damage=all_stats.get('normal_damage', 0) * 100 if all_stats.get('normal_damage', 0) < 1 else all_stats.get('normal_damage', 0),
            crit_rate=all_stats.get('crit_rate', 0) * 100 if all_stats.get('crit_rate', 0) < 1 else all_stats.get('crit_rate', 0),
            crit_damage=all_stats.get('crit_damage', 0) * 100 if all_stats.get('crit_damage', 0) < 1 else all_stats.get('crit_damage', 0),
            final_damage=all_stats.get('final_damage', 0) * 100 if all_stats.get('final_damage', 0) < 1 else all_stats.get('final_damage', 0),
            max_hp=all_stats.get('max_hp', 0),
            def_pen=all_stats.get('def_pen', 0) * 100 if all_stats.get('def_pen', 0) < 1 else all_stats.get('def_pen', 0),
            max_dmg_mult=all_stats.get('max_damage_mult', 0) * 100 if all_stats.get('max_damage_mult', 0) < 1 else all_stats.get('max_damage_mult', 0),
            basic_attack_damage=all_stats.get('basic_attack_damage', 0) * 100 if all_stats.get('basic_attack_damage', 0) < 1 else all_stats.get('basic_attack_damage', 0),
        )


# =============================================================================
# ARTIFACT DEFINITIONS
# =============================================================================

ARTIFACTS = {
    # -------------------------------------------------------------------------
    # LEGENDARY ARTIFACTS
    # -------------------------------------------------------------------------
    "hexagon_necklace": ArtifactDefinition(
        name="Hexagon Necklace",
        tier=ArtifactTier.UNIQUE,  # Unique tier, not Legendary
        active_description="Damage +X% per stack (max 3 stacks)",
        active_effects=[
            ArtifactEffect(
                stat="damage_multiplier",  # Applied as multiplier in DPS calc
                base=0.15,  # 15% per stack at ★0
                per_star=0.03,  # +3% per star → 30% per stack at ★5
                effect_type=EffectType.MULTIPLICATIVE,
                max_stacks=3,
            ),
        ],
        inventory_description="Attack +X (flat)",
        inventory_stat="attack_flat",
        inventory_base=400,
        inventory_per_star=320,  # → 2000 at ★5 (same as other Uniques)
        ramp_time=40.0,  # ~40s to reach 3 stacks
    ),

    "book_of_ancient": ArtifactDefinition(
        name="Book of Ancient",
        tier=ArtifactTier.LEGENDARY,
        active_description="Crit Rate +X%, Crit Damage by Y% of Crit Rate",
        active_effects=[
            ArtifactEffect(stat="crit_rate", base=0.10, per_star=0.02),  # 10→20%
            ArtifactEffect(
                stat="crit_damage",
                base=0.30,  # 30% of CR → CD at ★0
                per_star=0.06,  # +6% per star → 60% at ★5
                effect_type=EffectType.DERIVED,
                derived_from="crit_rate",
            ),
        ],
        inventory_description="Crit Rate +X%",
        inventory_stat="crit_rate",
        inventory_base=0.05,  # 5% at ★0
        inventory_per_star=0.01,  # +1% per star → 10% at ★5
    ),

    "chalice": ArtifactDefinition(
        name="Chalice",
        tier=ArtifactTier.LEGENDARY,
        active_description="Final Damage +X% for 30s on boss kill",
        active_effects=[
            ArtifactEffect(stat="final_damage", base=0.15, per_star=0.03),  # 15→30%
        ],
        inventory_description="Damage +X%",
        inventory_stat="damage",
        inventory_base=0.30,  # 30% at ★0
        inventory_per_star=0.06,  # +6% per star → 60% at ★5
        buff_duration=30.0,  # 30s after boss kill
        buff_cooldown=10.0,  # Average time between boss kills on stages with normals
        trigger_delay=10.0,  # Initial delay before first boss kill
    ),

    "star_rock": ArtifactDefinition(
        name="Star Rock",
        tier=ArtifactTier.LEGENDARY,
        active_description="Self Dmg Taken +X%, Boss Damage +Y%",
        active_effects=[
            ArtifactEffect(stat="boss_damage", base=0.50, per_star=0.10),  # 50→100%
        ],
        inventory_description="Defense +X%",
        inventory_stat="defense",
        inventory_base=0.08,  # 8% at ★0
        inventory_per_star=0.02,  # +2% per star → 18% at ★5
    ),

    "sayrams_necklace": ArtifactDefinition(
        name="Sayram's Necklace",
        tier=ArtifactTier.LEGENDARY,
        active_description="Normal Dmg +X% (2+ targets), Boss +Y% (1 target)",
        active_effects=[
            ArtifactEffect(stat="normal_damage", base=0.30, per_star=0.06),  # 30→60%
        ],
        inventory_description="Basic Attack Damage +X%",
        inventory_stat="basic_attack_damage",
        inventory_base=0.15,  # 15% at ★0
        inventory_per_star=0.03,  # +3% per star → 30% at ★5 (★2 = 21%)
    ),

    "lit_lamp": ArtifactDefinition(
        name="Lit Lamp",
        tier=ArtifactTier.LEGENDARY,
        active_description="[World Boss] Final Damage +X%",
        active_effects=[
            ArtifactEffect(stat="final_damage", base=0.20, per_star=0.04),  # 20→40%
        ],
        inventory_description="Boss Monster Damage +X%",
        inventory_stat="boss_damage",
        inventory_base=0.15,  # 15% at ★0
        inventory_per_star=0.03,  # +3% per star → 30% at ★5
        scenario="world_boss",  # Only active in World Boss
    ),

    "soul_contract": ArtifactDefinition(
        name="Soul Contract",
        tier=ArtifactTier.LEGENDARY,
        active_description="[Chapter Hunt] Cooldown -X%",
        active_effects=[
            ArtifactEffect(stat="cooldown_reduction", base=0.20, per_star=0.04),  # 20→40%
        ],
        inventory_description="Damage +X%",
        inventory_stat="damage",
        inventory_base=0.15,  # 15% at ★0
        inventory_per_star=0.03,  # +3% per star → 30% at ★5
        scenario="chapter",  # Only active in Chapter Hunt
    ),

    "ancient_text_piece": ArtifactDefinition(
        name="Ancient Text Piece",
        tier=ArtifactTier.LEGENDARY,
        active_description="[Guild Conquest] Final Damage +X%",
        active_effects=[
            ArtifactEffect(stat="final_damage", base=0.20, per_star=0.04),  # 20→40%
        ],
        inventory_description="Max Damage Multiplier +X%",
        inventory_stat="max_damage_mult",
        inventory_base=0.15,  # 15% at ★0
        inventory_per_star=0.03,  # +3% per star → 30% at ★5
        scenario="guild",  # Only active in Guild Conquest
    ),

    "clear_spring_water": ArtifactDefinition(
        name="Clear Spring Water",
        tier=ArtifactTier.UNIQUE,  # Unique tier, not Legendary
        active_description="[Growth Dungeon] Final Damage +X%",
        active_effects=[
            ArtifactEffect(stat="final_damage", base=0.10, per_star=0.02),  # 10→20%
        ],
        inventory_description="Attack +X (flat)",
        inventory_stat="attack_flat",
        inventory_base=400,  # ~400 at ★0
        inventory_per_star=320,  # → 2000 at ★5
        scenario="growth",  # Only active in Growth Dungeon
    ),

    # -------------------------------------------------------------------------
    # LEGENDARY ARTIFACTS (continued)
    # -------------------------------------------------------------------------
    "fire_flower": ArtifactDefinition(
        name="Fire Flower",
        tier=ArtifactTier.LEGENDARY,  # Legendary tier
        active_description="Final Damage +X% per target (max 10)",
        active_effects=[
            ArtifactEffect(
                stat="final_damage",
                base=0.01,  # 1% per target at ★0
                per_star=0.002,  # +0.2% per star → 2% per target at ★5
                effect_type=EffectType.FLAT,
                max_stacks=10,  # Max 10 targets
            ),
        ],
        inventory_description="Normal Monster Damage +X%",
        inventory_stat="normal_damage",
        inventory_base=0.15,  # 15% at ★0
        inventory_per_star=0.03,  # +3% per star → 30% at ★5
        max_targets=10,
    ),

    "icy_soul_rock": ArtifactDefinition(
        name="Icy Soul Rock",
        tier=ArtifactTier.LEGENDARY,  # Legendary tier
        active_description="MP regen + Crit Damage +X% at MP>=50% (doubled at 75%)",
        active_effects=[
            # Assumes 75%+ MP uptime (doubled value)
            ArtifactEffect(stat="crit_damage", base=0.40, per_star=0.08),  # 40→80% (doubled from 20→40%)
        ],
        inventory_description="Critical Damage +X%",
        inventory_stat="crit_damage",
        inventory_base=0.09,  # 9% at ★0
        inventory_per_star=0.03,  # +3% per star → 24% at ★5
    ),

    "silver_pendant": ArtifactDefinition(
        name="Silver Pendant",
        tier=ArtifactTier.LEGENDARY,  # Legendary tier
        active_description="Target damage taken +X% (15% proc)",
        active_effects=[
            ArtifactEffect(stat="enemy_damage_taken", base=0.10, per_star=0.02),  # 10→20%
        ],
        inventory_description="Defense Penetration +X%",
        inventory_stat="def_pen",
        inventory_base=0.05,  # 5% at ★0
        inventory_per_star=0.01,  # +1% per star → 10% at ★5
        proc_chance=0.15,  # 15% proc rate
    ),

    # -------------------------------------------------------------------------
    # UNIQUE ARTIFACTS
    # -------------------------------------------------------------------------
    "rainbow_snail_shell": ArtifactDefinition(
        name="Rainbow-colored Snail Shell",
        tier=ArtifactTier.UNIQUE,
        active_description="CR +X%, CD +Y% for 15s at battle start",
        active_effects=[
            ArtifactEffect(stat="crit_rate", base=0.15, per_star=0.03),  # 15→30%
            ArtifactEffect(stat="crit_damage", base=0.20, per_star=0.04),  # 20→40%
        ],
        inventory_description="Attack +X (flat)",
        inventory_stat="attack_flat",
        inventory_base=400,
        inventory_per_star=320,  # → 2000 at ★5
        buff_duration=15.0,  # 15s at battle start
        buff_cooldown=float('inf'),  # One-time buff (never cycles) → 0% uptime at infinite duration
    ),

    "mushmom_cap": ArtifactDefinition(
        name="Mushmom's Cap",
        tier=ArtifactTier.UNIQUE,
        active_description="Damage +X% per Acc exceeding Evasion (max Y%)",
        active_effects=[
            # Accuracy-based damage is complex; using average estimate of 50% of max cap
            ArtifactEffect(stat="damage", base=0.10, per_star=0.02),  # ~10→20% (half of max 20→40%)
        ],
        inventory_description="Attack +X (flat)",
        inventory_stat="attack_flat",
        inventory_base=400,
        inventory_per_star=320,  # → 2000 at ★5
        # Max cap: 20% at ★0 → 40% at ★5
    ),

    # -------------------------------------------------------------------------
    # EPIC ARTIFACTS
    # -------------------------------------------------------------------------
    "shamaness_marble": ArtifactDefinition(
        name="Shamaness Marble",
        tier=ArtifactTier.EPIC,
        active_description="Buff duration +X%",
        active_effects=[
            ArtifactEffect(stat="buff_duration", base=0.06, per_star=0.012),  # 6→12% (utility, no direct DPS)
        ],
        inventory_description="Attack +X (flat)",
        inventory_stat="attack_flat",
        inventory_base=200,
        inventory_per_star=160,  # → 1000 at ★5
    ),

    "contract_of_darkness": ArtifactDefinition(
        name="Contract of Darkness",
        tier=ArtifactTier.EPIC,
        active_description="Crit Rate +X% vs bosses",
        active_effects=[
            ArtifactEffect(stat="crit_rate", base=0.08, per_star=0.016),  # 8→16% (vs bosses, but counted as general CR)
        ],
        inventory_description="Attack +X (flat)",
        inventory_stat="attack_flat",
        inventory_base=200,
        inventory_per_star=160,  # → 1000 at ★5
    ),

    "charm_of_undead": ArtifactDefinition(
        name="Charm of the Undead",
        tier=ArtifactTier.EPIC,
        active_description="ATK +X% for 5s every 10s",
        active_effects=[
            ArtifactEffect(stat="attack_buff", base=0.10, per_star=0.02),  # 10→20%
        ],
        inventory_description="Attack +X (flat)",
        inventory_stat="attack_flat",
        inventory_base=200,
        inventory_per_star=160,  # → 1000 at ★5
        buff_duration=5.0,
        buff_cooldown=10.0,  # 50% uptime
    ),

    "pigs_ribbon": ArtifactDefinition(
        name="Pig's Ribbon",
        tier=ArtifactTier.EPIC,
        active_description="HP/MP recovery +X% on attack",
        active_effects=[
            ArtifactEffect(stat="hp_mp_recovery", base=0.01, per_star=0.002),  # 1→2% (utility, no DPS)
        ],
        inventory_description="Attack +X (flat)",
        inventory_stat="attack_flat",
        inventory_base=200,
        inventory_per_star=160,  # → 1000 at ★5
    ),

    # -------------------------------------------------------------------------
    # UNIQUE ARTIFACTS (additional)
    # -------------------------------------------------------------------------
    "arwens_glass_shoes": ArtifactDefinition(
        name="Arwen's Glass Shoes",
        tier=ArtifactTier.UNIQUE,
        active_description="Companion duration +X%",
        active_effects=[
            ArtifactEffect(stat="companion_duration", base=0.20, per_star=0.04),  # 20→40% (utility, no direct DPS)
        ],
        inventory_description="Attack +X (flat)",
        inventory_stat="attack_flat",
        inventory_base=400,
        inventory_per_star=320,  # → 2000 at ★5
    ),

    "athena_pierces_gloves": ArtifactDefinition(
        name="Athena Pierce's Old Gloves",
        tier=ArtifactTier.UNIQUE,
        active_description="Atk Spd +X%, Max Dmg +Y% of Atk Spd",
        active_effects=[
            ArtifactEffect(stat="attack_speed", base=0.08, per_star=0.016),  # 8→16%
            ArtifactEffect(
                stat="max_damage_mult",
                base=0.25,  # 25% of Atk Speed → Max Dmg at ★0
                per_star=0.05,  # +5% per star → 50% at ★5
                effect_type=EffectType.DERIVED,
                derived_from="attack_speed",
            ),
        ],
        inventory_description="Attack +X (flat)",
        inventory_stat="attack_flat",
        inventory_base=400,
        inventory_per_star=320,  # → 2000 at ★5
    ),

    # -------------------------------------------------------------------------
    # LEGENDARY ARTIFACTS (additional)
    # -------------------------------------------------------------------------
    "old_music_box": ArtifactDefinition(
        name="Old Music Box",
        tier=ArtifactTier.LEGENDARY,
        active_description="ATK +X% for 25s on debuff (CD 20s)",
        active_effects=[
            ArtifactEffect(stat="attack_buff", base=0.25, per_star=0.05),  # 25→50%
        ],
        inventory_description="Debuff Tolerance +X",
        inventory_stat="debuff_tolerance",
        inventory_base=8,  # 8 at ★0
        inventory_per_star=2,  # +2 per star → 18 at ★5
        buff_duration=25.0,
        buff_cooldown=20.0,  # ~55% uptime
    ),

    "lunar_dew": ArtifactDefinition(
        name="Lunar Dew",
        tier=ArtifactTier.LEGENDARY,
        active_description="HP recovery +X% on hit",
        active_effects=[
            ArtifactEffect(stat="hp_recovery", base=0.03, per_star=0.006),  # 3→6% (utility, no DPS)
        ],
        inventory_description="Damage Taken Decrease +X%",
        inventory_stat="damage_taken_decrease",
        inventory_base=0.04,  # 4% at ★0
        inventory_per_star=0.01,  # +1% per star → 9% at ★5
    ),

    "soul_pouch": ArtifactDefinition(
        name="Soul Pouch",
        tier=ArtifactTier.LEGENDARY,
        active_description="[Arena] Final Damage +X%",
        active_effects=[
            ArtifactEffect(stat="final_damage", base=0.20, per_star=0.04),  # 20→40%
        ],
        inventory_description="Evasion +X",
        inventory_stat="evasion",
        inventory_base=16,  # 16 at ★0
        inventory_per_star=4,  # +4 per star → 36 at ★5
        scenario="arena",  # Only active in Arena
    ),

    # -------------------------------------------------------------------------
    # ZAKUM RAID ARTIFACT
    # -------------------------------------------------------------------------
    "zakum_raid_artifact": ArtifactDefinition(
        name="Zakum Raid Artifact",
        tier=ArtifactTier.UNIQUE,
        active_description="[Zakum Raid] Final Damage +X%",
        active_effects=[
            ArtifactEffect(stat="final_damage", base=0.20, per_star=0.08),  # 20→60%
        ],
        inventory_description="Final Damage +X%",
        inventory_stat="final_damage",
        inventory_base=0.01,  # 1% at ★0
        inventory_per_star=0.002,  # +0.2% per star → 2% at ★5
        scenario="zakum",  # Only active in Zakum Raid
    ),

    # -------------------------------------------------------------------------
    # FLAMING LAVA (Complex active effect - simplified)
    # -------------------------------------------------------------------------
    "flaming_lava": ArtifactDefinition(
        name="Flaming Lava",
        tier=ArtifactTier.LEGENDARY,
        active_description="Complex effect (simplified model)",
        active_effects=[
            ArtifactEffect(stat="utility", base=0.0, per_star=0.0),  # Hard to model, treating as utility
        ],
        inventory_description="Accuracy +X",
        inventory_stat="accuracy",
        inventory_base=10,  # 10 at ★0
        inventory_per_star=2,  # +2 per star → 20 at ★5
    ),
}


# =============================================================================
# CALCULATIONS
# =============================================================================

def calculate_hex_multiplier(stars: int, stacks: int = 3) -> float:
    """
    Calculate Hexagon Necklace total damage multiplier at a given stack count.

    At 3 stacks:
    ★0: 1.45, ★1: 1.54, ★2: 1.63, ★3: 1.72, ★4: 1.81, ★5: 1.90
    """
    hex_def = ARTIFACTS["hexagon_necklace"]
    # Get per-stack value from active_effects (new format)
    # Use stacks=1 to get single-stack value, then multiply by actual stacks
    if hex_def.active_effects:
        effect = hex_def.active_effects[0]
        per_stack = effect.base + (stars * effect.per_star)  # base value without stacks multiplier
    else:
        per_stack = hex_def.get_active_value(stars)
    return 1 + (min(stacks, 3) * per_stack)


def calculate_hex_average_multiplier(stars: int, fight_duration: float) -> float:
    """
    Calculate average Hex Necklace multiplier over a fight.

    Hex stacks build up every 20 seconds:
    - 0-20s: 0 stacks (multiplier = 1.0)
    - 21-40s: 1 stack
    - 41-60s: 2 stacks
    - 61+s: 3 stacks (max)

    Args:
        stars: Artifact star level (0-5)
        fight_duration: Total fight duration in seconds (use inf for long/infinite fights)

    Returns:
        Time-weighted average multiplier over the fight
    """
    if fight_duration <= 0:
        return 1.0

    hex_def = ARTIFACTS["hexagon_necklace"]
    # Get per-stack value from active_effects (new format)
    # Use base value directly without stacks multiplier
    if hex_def.active_effects:
        effect = hex_def.active_effects[0]
        per_stack = effect.base + (stars * effect.per_star)
    else:
        per_stack = hex_def.get_active_value(stars)

    # For infinite duration, return max stacks multiplier
    if fight_duration == float('inf'):
        return 1 + (3 * per_stack)  # Max 3 stacks

    # Stack thresholds (in seconds)
    stack_times = [20, 40, 60]  # Time when stack 1, 2, 3 become active

    # Calculate weighted average multiplier
    total_weight = 0.0
    weighted_mult = 0.0

    prev_time = 0
    for i, threshold in enumerate(stack_times):
        stacks = i  # 0, 1, 2 stacks during this period
        if fight_duration <= threshold:
            # Fight ends before reaching this threshold
            duration = fight_duration - prev_time
            if duration > 0:
                mult = 1 + (stacks * per_stack)
                weighted_mult += mult * duration
                total_weight += duration
            break
        else:
            # Full duration at this stack count
            duration = threshold - prev_time
            mult = 1 + (stacks * per_stack)
            weighted_mult += mult * duration
            total_weight += duration
            prev_time = threshold
    else:
        # Fight continues past 60s at 3 stacks
        remaining = fight_duration - 60
        if remaining > 0:
            mult = 1 + (3 * per_stack)  # Max 3 stacks
            weighted_mult += mult * remaining
            total_weight += remaining

    return weighted_mult / total_weight if total_weight > 0 else 1.0


def calculate_book_of_ancient_bonus(stars: int, crit_rate: float) -> Tuple[float, float]:
    """
    Calculate Book of Ancient bonuses.

    Args:
        stars: Awakening level
        crit_rate: Current crit rate as decimal (1.119 for 111.9%)

    Returns:
        (crit_rate_bonus, crit_damage_bonus)
    """
    book_def = ARTIFACTS["book_of_ancient"]
    cr_bonus = book_def.get_active_value(stars)
    conversion_rate = book_def.get_conversion_rate(stars)

    # CD bonus = conversion_rate * (current CR + CR bonus from artifact)
    total_cr = crit_rate + cr_bonus
    cd_bonus = total_cr * conversion_rate

    return (cr_bonus, cd_bonus)


def calculate_fire_flower_fd(stars: int, targets: int) -> float:
    """
    Calculate Fire Flower Final Damage bonus.

    Args:
        stars: Awakening level
        targets: Number of nearby targets

    Returns:
        Final Damage bonus as decimal
    """
    ff_def = ARTIFACTS["fire_flower"]
    per_target = ff_def.get_active_value(stars)
    return min(targets, 10) * per_target


def calculate_potential_roll_chance(
    target_stat: str,
    target_tier: PotentialTier,
    num_slots: int = 1
) -> float:
    """
    Calculate chance to roll a specific potential.

    Args:
        target_stat: The stat to target
        target_tier: The tier to target
        num_slots: Number of potential slots available

    Returns:
        Probability of getting at least one matching line
    """
    tier_rate = POTENTIAL_TIER_RATES.get(target_tier, 0)

    # Premium stats have half the appearance rate
    stat_multiplier = 0.5 if target_stat in PREMIUM_STATS else 1.0

    # Assume equal distribution among ~10 stats
    stat_rate = 0.1 * stat_multiplier

    single_slot_chance = tier_rate * stat_rate

    # For multiple slots: P(at least one) = 1 - P(none)
    return 1 - ((1 - single_slot_chance) ** num_slots)


def calculate_expected_rolls(
    target_stat: str,
    target_tier: PotentialTier,
    num_slots: int = 1
) -> float:
    """
    Calculate expected number of reconfigures to hit target.
    """
    chance = calculate_potential_roll_chance(target_stat, target_tier, num_slots)
    if chance <= 0:
        return float('inf')
    return 1 / chance


# =============================================================================
# ARTIFACT ACQUISITION CALCULATIONS
# =============================================================================

def calculate_expected_chests_for_artifact(
    artifact_key: str,
    target_tier: Optional[ArtifactTier] = None
) -> float:
    """
    Calculate expected number of chests to get a specific artifact.

    Args:
        artifact_key: The artifact to target
        target_tier: If specified, calculate for any artifact of this tier

    Returns:
        Expected number of chests needed
    """
    if target_tier:
        rate = ARTIFACT_TIER_DROP_RATES.get(target_tier, 0)
    else:
        rate = ARTIFACT_DROP_RATES.get(artifact_key, 0)

    if rate <= 0:
        return float('inf')
    return 1 / rate


def calculate_chests_for_max_star(
    artifact_key: str,
    current_stars: int = 0
) -> float:
    """
    Calculate expected chests to max-star (★5) an artifact.

    To reach ★5, you need the base artifact + 9 duplicates = 10 total copies.

    Args:
        artifact_key: The artifact to target
        current_stars: Current awakening level

    Returns:
        Expected number of chests needed
    """
    rate = ARTIFACT_DROP_RATES.get(artifact_key, 0)
    if rate <= 0:
        return float('inf')

    # Total copies needed to reach ★5 from current state
    copies_owned = 1 + TOTAL_DUPLICATES_TO_STAR.get(current_stars, 0)
    copies_needed = 10 - copies_owned  # 10 total for ★5

    if copies_needed <= 0:
        return 0

    # Expected chests = copies_needed / drop_rate
    return copies_needed / rate


def calculate_synthesis_cost(
    target_tier: ArtifactTier,
    via_synthesis: bool = True
) -> Dict[str, Any]:
    """
    Calculate cost to obtain one artifact of target tier via synthesis.

    Synthesis path:
    - Epic → Unique: 20 Epic (★5) = 20 * 10 = 200 Epic copies
    - Unique → Legendary: 15 Unique (★5) = 15 * 10 = 150 Unique copies
    - Epic → Legendary: 200 * 20 * 15 = ... (very expensive)

    Args:
        target_tier: The tier to synthesize to
        via_synthesis: If True, calculate full synthesis path from Epic

    Returns:
        Dict with 'chests_needed' and 'diamonds_needed'
    """
    if target_tier == ArtifactTier.EPIC:
        # Just need 1 epic, ~1.12 chests expected
        chests = 1 / ARTIFACT_TIER_DROP_RATES[ArtifactTier.EPIC]
        return {
            "chests_needed": chests,
            "diamonds_needed": chests * ARTIFACT_CHEST_COSTS["blue_diamond"],
            "method": "Direct drop",
        }

    if target_tier == ArtifactTier.UNIQUE:
        if via_synthesis:
            # 20 Epic (★5) needed, each ★5 needs 10 copies
            epic_copies = 20 * 10  # 200 epic copies
            chests = epic_copies / ARTIFACT_TIER_DROP_RATES[ArtifactTier.EPIC]
        else:
            # Direct drop
            chests = 1 / ARTIFACT_TIER_DROP_RATES[ArtifactTier.UNIQUE]
        return {
            "chests_needed": chests,
            "diamonds_needed": chests * ARTIFACT_CHEST_COSTS["blue_diamond"],
            "method": "Synthesis from Epic" if via_synthesis else "Direct drop",
        }

    if target_tier == ArtifactTier.LEGENDARY:
        if via_synthesis:
            # Need 15 Unique (★5), each Unique (★5) needs 10 Unique copies
            # Each Unique (★5) can come from synthesis (200 epics) or direct
            # Using synthesis: 15 * 10 * 200 = 30,000 epic copies
            # Or: 15 * 10 = 150 unique copies

            # Method 1: Direct unique drops → synthesize
            unique_copies = 15 * 10  # 150 unique copies
            chests_via_unique = unique_copies / ARTIFACT_TIER_DROP_RATES[ArtifactTier.UNIQUE]

            # Method 2: Pure synthesis from epic
            epic_copies = 15 * 10 * 20 * 10  # insanely expensive
            chests_via_epic = epic_copies / ARTIFACT_TIER_DROP_RATES[ArtifactTier.EPIC]

            # Use the cheaper method (unique drops)
            chests = chests_via_unique
            method = "Synthesis from Unique drops"
        else:
            # Direct legendary drop
            chests = 1 / ARTIFACT_TIER_DROP_RATES[ArtifactTier.LEGENDARY]
            method = "Direct drop"

        return {
            "chests_needed": chests,
            "diamonds_needed": chests * ARTIFACT_CHEST_COSTS["blue_diamond"],
            "method": method,
        }

    return {"chests_needed": float('inf'), "diamonds_needed": float('inf'), "method": "Unknown"}


def calculate_specific_legendary_cost(artifact_key: str) -> Dict[str, Any]:
    """
    Calculate expected cost to obtain a specific legendary artifact.

    Two methods:
    1. Direct drop: ~1400 chests (0.07143% rate)
    2. Synthesis: Get any legendary, hope it's the right one (~1/12 chance)

    Args:
        artifact_key: The legendary artifact to target

    Returns:
        Dict with cost breakdown for each method
    """
    direct_rate = ARTIFACT_DROP_RATES.get(artifact_key, 0)
    if direct_rate <= 0:
        return {"error": "Unknown artifact"}

    # Method 1: Direct drop
    direct_chests = 1 / direct_rate
    direct_diamonds = direct_chests * ARTIFACT_CHEST_COSTS["blue_diamond"]

    # Method 2: Synthesis random legendary, need ~12 tries for specific one
    # (assuming 12 legendary artifacts)
    num_legendaries = sum(1 for k, v in ARTIFACT_DROP_RATES.items()
                          if v == 0.0007143 and k not in ["chalice", "old_music_box", "silver_pendant"])
    synth_cost = calculate_synthesis_cost(ArtifactTier.LEGENDARY, via_synthesis=True)
    synthesis_chests = synth_cost["chests_needed"] * num_legendaries
    synthesis_diamonds = synthesis_chests * ARTIFACT_CHEST_COSTS["blue_diamond"]

    return {
        "direct_drop": {
            "chests": direct_chests,
            "diamonds": direct_diamonds,
        },
        "synthesis": {
            "chests": synthesis_chests,
            "diamonds": synthesis_diamonds,
        },
        "recommendation": "Direct drop" if direct_diamonds < synthesis_diamonds else "Synthesis",
    }


def calculate_artifact_upgrade_efficiency(
    artifact_key: str,
    current_stars: int,
    target_stars: int,
    current_dps_stats: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Calculate efficiency of awakening an artifact.

    Args:
        artifact_key: The artifact to upgrade
        current_stars: Current awakening level
        target_stars: Target awakening level
        current_dps_stats: Current character stats for DPS estimation

    Returns:
        Dict with cost and expected DPS gain
    """
    if artifact_key not in ARTIFACTS:
        return {"error": "Unknown artifact"}

    definition = ARTIFACTS[artifact_key]
    drop_rate = ARTIFACT_DROP_RATES.get(artifact_key, 0)

    # Get tier-specific duplicate costs
    tier = definition.tier
    tier_dupes = TOTAL_DUPLICATES_BY_TIER.get(tier, TOTAL_DUPLICATES_BY_TIER[ArtifactTier.LEGENDARY])

    # Calculate duplicates needed
    current_dupes = tier_dupes.get(current_stars, 0)
    target_dupes = tier_dupes.get(target_stars, 0)
    dupes_needed = target_dupes - current_dupes

    if dupes_needed <= 0:
        return {"error": "Already at or above target"}

    # Calculate expected chests
    if drop_rate > 0:
        expected_chests = dupes_needed / drop_rate
    else:
        expected_chests = float('inf')

    expected_diamonds = expected_chests * ARTIFACT_CHEST_COSTS["blue_diamond"]

    # Calculate stat improvement
    current_active = definition.get_active_value(current_stars)
    target_active = definition.get_active_value(target_stars)
    current_inv = definition.get_inventory_value(current_stars)
    target_inv = definition.get_inventory_value(target_stars)

    return {
        "artifact": definition.name,
        "upgrade": f"★{current_stars} → ★{target_stars}",
        "duplicates_needed": dupes_needed,
        "expected_chests": expected_chests,
        "expected_diamonds": expected_diamonds,
        "active_effect_gain": target_active - current_active,
        "inventory_effect_gain": target_inv - current_inv,
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_artifact_by_name(name: str) -> Optional[ArtifactDefinition]:
    """Get artifact definition by name."""
    name_lower = name.lower().replace(" ", "_").replace("'", "")
    for key, artifact in ARTIFACTS.items():
        if key == name_lower or artifact.name.lower() == name.lower():
            return artifact
    return None


def create_artifact_instance(
    artifact_key: str,
    stars: int = 0,
    potentials: Optional[List[Tuple[str, float, PotentialTier]]] = None
) -> Optional[ArtifactInstance]:
    """Create an artifact instance from definition key."""
    if artifact_key not in ARTIFACTS:
        return None

    definition = ARTIFACTS[artifact_key]
    instance = ArtifactInstance(definition=definition, awakening_stars=stars)

    if potentials:
        for i, (stat, value, tier) in enumerate(potentials):
            instance.potentials.append(ArtifactPotentialLine(
                stat=stat, value=value, tier=tier, slot=i+1
            ))

    return instance


# =============================================================================
# MAIN (Testing)
# =============================================================================

if __name__ == "__main__":
    print("MapleStory Idle - Artifact System Module")
    print("=" * 60)

    # Test Hexagon Necklace
    print("\nHexagon Necklace Damage Multiplier (3 stacks):")
    for stars in range(6):
        mult = calculate_hex_multiplier(stars, 3)
        print(f"  ★{stars}: ×{mult:.2f}")

    # Test Book of Ancient
    print("\nBook of Ancient at 111.9% CR:")
    for stars in range(6):
        cr_bonus, cd_bonus = calculate_book_of_ancient_bonus(stars, 1.119)
        print(f"  ★{stars}: CR +{cr_bonus*100:.0f}%, CD +{cd_bonus*100:.1f}%")

    # Test Fire Flower
    print("\nFire Flower Final Damage (10 targets):")
    for stars in range(6):
        fd = calculate_fire_flower_fd(stars, 10)
        print(f"  ★{stars}: +{fd*100:.0f}%")

    # Test Chalice inventory effect
    print("\nChalice Inventory Damage %:")
    chalice = ARTIFACTS["chalice"]
    for stars in range(6):
        dmg = chalice.get_inventory_value(stars)
        print(f"  ★{stars}: +{dmg*100:.1f}%")

    # Test expected rolls
    print("\nExpected Rolls for Legendary Damage 14% (2 slots):")
    rolls = calculate_expected_rolls("damage", PotentialTier.LEGENDARY, 2)
    print(f"  ~{rolls} rolls")

    print("\nExpected Rolls for Mystic Damage 20% (3 slots):")
    rolls = calculate_expected_rolls("damage", PotentialTier.MYSTIC, 3)
    print(f"  ~{rolls} rolls")
