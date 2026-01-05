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

# Potential values by tier (stat: {tier: (low, high)})
POTENTIAL_VALUES = {
    "main_stat": {
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
    "def_pen": {
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
    "min_max_damage": {
        PotentialTier.RARE: (2.0, 2.0),
        PotentialTier.EPIC: (3.0, 3.0),
        PotentialTier.UNIQUE: (4.5, 4.5),
        PotentialTier.LEGENDARY: (7.0, 7.0),
        PotentialTier.MYSTIC: (10.0, 12.0),
    },
}

# Premium stats appear at half rate
PREMIUM_STATS = ["boss_damage", "normal_damage", "damage", "def_pen"]

# Reconfigure costs
RECONFIGURE_COSTS = {
    ArtifactTier.LEGENDARY: {"meso": 20000, "stones": 2000},
    ArtifactTier.UNIQUE: {"meso": 15000, "stones": 1500},
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
ARTIFACT_DROP_RATES = {
    # Epic tier (common) - 22.375% each, 4 artifacts = 89.5% total
    "shamaness_marble": 0.22375,
    "contract_of_darkness": 0.22375,
    "epic_artifact_3": 0.22375,  # placeholder
    "epic_artifact_4": 0.22375,  # placeholder

    # Unique tier (uncommon) - 1.3571% each
    "rainbow_snail_shell": 0.013571,
    "arwens_glass_shoes": 0.013571,
    "mushmom_cap": 0.013571,
    "clear_spring_water": 0.013571,
    "athena_pierces_old_gloves": 0.013571,
    "zakums_stone_piece": 0.013571,

    # Unique tier (rare) - 0.07143% each
    "chalice": 0.0007143,
    "old_music_box": 0.0007143,
    "silver_pendant": 0.0007143,

    # Legendary tier - 0.07143% each
    "hexagon_necklace": 0.0007143,
    "book_of_ancient": 0.0007143,
    "star_rock": 0.0007143,
    "fire_flower": 0.0007143,
    "soul_contract": 0.0007143,
    "lit_lamp": 0.0007143,
    "ancient_text_piece": 0.0007143,
    "sayrams_necklace": 0.0007143,
    "icy_soul_rock": 0.0007143,
    "soul_pouch": 0.0007143,
    "lunar_dew": 0.0007143,
    "flaming_lava": 0.0007143,
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
    # 20 Epic (★5) → 1 Random Unique
    (ArtifactTier.EPIC, ArtifactTier.UNIQUE): 20,
    # 15 Unique (★5) → 1 Random Legendary
    (ArtifactTier.UNIQUE, ArtifactTier.LEGENDARY): 15,
}

# =============================================================================
# AWAKENING COSTS
# =============================================================================

# Cost to awaken artifact (duplicate artifacts needed per star)
# Going from ★0 to ★1 needs 1 duplicate, ★1 to ★2 needs 1, etc.
AWAKENING_COSTS = {
    # star_level: duplicates_needed
    1: 1,  # ★0 → ★1
    2: 1,  # ★1 → ★2
    3: 2,  # ★2 → ★3
    4: 2,  # ★3 → ★4
    5: 3,  # ★4 → ★5
}

# Total duplicates needed to reach each star level from ★0
TOTAL_DUPLICATES_TO_STAR = {
    0: 0,
    1: 1,   # 1 duplicate
    2: 2,   # 1 + 1
    3: 4,   # 1 + 1 + 2
    4: 6,   # 1 + 1 + 2 + 2
    5: 9,   # 1 + 1 + 2 + 2 + 3
}

# =============================================================================
# ARTIFACT CHEST COSTS
# =============================================================================

ARTIFACT_CHEST_COSTS = {
    "blue_diamond": 1500,    # 300/week limit
    "red_diamond": 1500,     # 5/week limit
    "arena_coin": 500,       # 10/week limit
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


@dataclass
class ArtifactDefinition:
    """Definition of an artifact type with scaling."""
    name: str
    tier: ArtifactTier

    # Active effect (when equipped in slot)
    active_description: str
    active_stat: str  # What stat it affects
    active_base: float  # Value at ★0
    active_per_star: float  # Additional value per star

    # Inventory effect (always active)
    inventory_description: str
    inventory_stat: str
    inventory_base: float
    inventory_per_star: float

    # Special mechanics
    max_stacks: int = 1  # For stackable effects like Hex
    scales_with: Optional[str] = None  # For Book of Ancient (scales with crit_rate)
    conversion_rate_base: float = 0.0  # Base conversion rate
    conversion_rate_per_star: float = 0.0  # Per star increase

    def get_active_value(self, stars: int) -> float:
        """Get active effect value at given awakening level."""
        return self.active_base + (stars * self.active_per_star)

    def get_inventory_value(self, stars: int) -> float:
        """Get inventory effect value at given awakening level."""
        return self.inventory_base + (stars * self.inventory_per_star)

    def get_conversion_rate(self, stars: int) -> float:
        """Get conversion rate at given awakening level (for Book of Ancient)."""
        return self.conversion_rate_base + (stars * self.conversion_rate_per_star)


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
            "main_stat", "damage", "boss_damage", "normal_damage",
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
        """Get bonus stats from resonance."""
        resonance = self.get_resonance()
        # Approximate scaling based on known values
        # ★55 = +500 main stat, +5003 HP
        # ★65 = +650 main stat, +6504 HP
        main_stat_per_star = 10.0
        hp_per_star = 100.0
        return {
            "main_stat_flat": resonance * main_stat_per_star,
            "max_hp_flat": resonance * hp_per_star,
        }

    def get_equipped_active_stats(self) -> Dict[str, float]:
        """Get total active stats from equipped artifacts."""
        stats = {}
        for artifact in self.equipped:
            if artifact is None:
                continue
            stat = artifact.definition.active_stat
            value = artifact.get_active_value()
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


# =============================================================================
# ARTIFACT DEFINITIONS
# =============================================================================

ARTIFACTS = {
    # -------------------------------------------------------------------------
    # LEGENDARY ARTIFACTS
    # -------------------------------------------------------------------------
    "hexagon_necklace": ArtifactDefinition(
        name="Hexagon Necklace",
        tier=ArtifactTier.LEGENDARY,
        active_description="Damage +X% per stack (max 3 stacks)",
        active_stat="hex_damage_per_stack",
        active_base=0.20,  # 20% at ★0
        active_per_star=0.02,  # +2% per star
        inventory_description="Attack +600 (flat, doesn't scale)",
        inventory_stat="attack_flat",
        inventory_base=600,
        inventory_per_star=0,  # Doesn't scale
        max_stacks=3,
    ),

    "book_of_ancient": ArtifactDefinition(
        name="Book of Ancient",
        tier=ArtifactTier.LEGENDARY,
        active_description="Crit Rate +X%, Crit Damage by Y% of Crit Rate",
        active_stat="crit_rate",
        active_base=0.10,  # 10% at ★0
        active_per_star=0.02,  # +2% per star
        inventory_description="Crit Damage +X% (MP>=50%), doubled at MP>=75%",
        inventory_stat="crit_damage_conditional",
        inventory_base=0.20,  # 20% at ★0
        inventory_per_star=0.04,  # +4% per star
        scales_with="crit_rate",
        conversion_rate_base=0.30,  # 30% of CR to CD at ★0
        conversion_rate_per_star=0.06,  # +6% per star
    ),

    "chalice": ArtifactDefinition(
        name="Chalice",
        tier=ArtifactTier.LEGENDARY,
        active_description="Final Damage +X% for 30s on boss kill",
        active_stat="final_damage_conditional",
        active_base=0.18,  # 18% at ★0
        active_per_star=0.03,  # +3% per star (from ★2)
        inventory_description="Damage +X%",
        inventory_stat="damage",
        inventory_base=0.35,  # 35% at ★0
        inventory_per_star=0.035,  # +3.5% per star
    ),

    "star_rock": ArtifactDefinition(
        name="Star Rock",
        tier=ArtifactTier.LEGENDARY,
        active_description="Enemy Dmg Taken +X%, Boss Damage +Y%",
        active_stat="boss_damage",
        active_base=0.50,  # 50% boss dmg at ★0
        active_per_star=0.10,  # +10% per star
        inventory_description="Defense +X%",
        inventory_stat="defense",
        inventory_base=0.10,  # 10% at ★0
        inventory_per_star=0.02,  # +2% per star
    ),

    "sayrams_necklace": ArtifactDefinition(
        name="Sayram's Necklace",
        tier=ArtifactTier.LEGENDARY,
        active_description="Normal Dmg +X% (2+ targets), Boss +Y% (1 target)",
        active_stat="normal_damage",
        active_base=0.30,  # 30% normal at ★0
        active_per_star=0.06,  # +6% per star
        inventory_description="Basic Attack Damage +X%",
        inventory_stat="basic_attack_damage",
        inventory_base=0.15,  # 15% at ★0
        inventory_per_star=0.03,  # +3% per star
    ),

    "lit_lamp": ArtifactDefinition(
        name="Lit Lamp",
        tier=ArtifactTier.LEGENDARY,
        active_description="[World Boss] Final Damage +X%",
        active_stat="final_damage_world_boss",
        active_base=0.20,  # 20% at ★0
        active_per_star=0.04,  # +4% per star
        inventory_description="Boss Monster Damage +X%",
        inventory_stat="boss_damage",
        inventory_base=0.15,  # 15% at ★0
        inventory_per_star=0.03,  # +3% per star
    ),

    "soul_contract": ArtifactDefinition(
        name="Soul Contract",
        tier=ArtifactTier.LEGENDARY,
        active_description="[Chapter Hunt] Cooldown -X%",
        active_stat="cooldown_reduction",
        active_base=0.20,  # 20% at ★0
        active_per_star=0.04,  # +4% per star
        inventory_description="Damage +X%",
        inventory_stat="damage",
        inventory_base=0.15,  # 15% at ★0
        inventory_per_star=0.03,  # +3% per star
    ),

    "ancient_text_piece": ArtifactDefinition(
        name="Ancient Text Piece",
        tier=ArtifactTier.LEGENDARY,
        active_description="[Guild Conquest] Final Damage +X%",
        active_stat="final_damage_guild",
        active_base=0.20,  # 20% at ★0
        active_per_star=0.04,  # +4% per star
        inventory_description="Max Damage Multiplier +X%",
        inventory_stat="max_damage_mult",
        inventory_base=0.15,  # 15% at ★0
        inventory_per_star=0.03,  # +3% per star
    ),

    "clear_spring_water": ArtifactDefinition(
        name="Clear Spring Water",
        tier=ArtifactTier.LEGENDARY,
        active_description="[Growth Dungeon] Final Damage +X%",
        active_stat="final_damage_growth",
        active_base=0.12,  # 12% at ★0
        active_per_star=0.04,  # +4% per star
        inventory_description="Max Damage Multiplier +X%",
        inventory_stat="max_damage_mult",
        inventory_base=0.15,  # 15% at ★0
        inventory_per_star=0.03,  # +3% per star
    ),

    # -------------------------------------------------------------------------
    # UNIQUE ARTIFACTS
    # -------------------------------------------------------------------------
    "fire_flower": ArtifactDefinition(
        name="Fire Flower",
        tier=ArtifactTier.UNIQUE,
        active_description="Final Damage +X% per target (max 10)",
        active_stat="final_damage_per_target",
        active_base=0.01,  # 1% at ★0
        active_per_star=0.002,  # +0.2% per star
        inventory_description="Normal Monster Damage +X%",
        inventory_stat="normal_damage",
        inventory_base=0.15,  # 15% at ★0
        inventory_per_star=0.03,  # +3% per star
    ),

    "icy_soul_rock": ArtifactDefinition(
        name="Icy Soul Rock",
        tier=ArtifactTier.UNIQUE,
        active_description="MP regen + Crit Damage +X% at MP>=50% (doubled at 75%)",
        active_stat="crit_damage_mp_conditional",
        active_base=0.20,  # 20% at ★0
        active_per_star=0.04,  # +4% per star
        inventory_description="Critical Damage +X%",
        inventory_stat="crit_damage",
        inventory_base=0.10,  # 10% at ★0
        inventory_per_star=0.03,  # +3% per star
    ),

    "silver_pendant": ArtifactDefinition(
        name="Silver Pendant",
        tier=ArtifactTier.UNIQUE,
        active_description="Target damage taken +10%, HP recovery -5%",
        active_stat="enemy_damage_taken",
        active_base=0.10,
        active_per_star=0,
        inventory_description="Defense Penetration +X%",
        inventory_stat="def_pen",
        inventory_base=0.05,  # 5% at ★0
        inventory_per_star=0.01,  # +1% per star
    ),

    # -------------------------------------------------------------------------
    # EPIC ARTIFACTS (shared inventory effect)
    # -------------------------------------------------------------------------
    "rainbow_snail_shell": ArtifactDefinition(
        name="Rainbow-colored Snail Shell",
        tier=ArtifactTier.EPIC,
        active_description="+30% CR, +40% CD for 15s at battle start",
        active_stat="battle_start_buff",
        active_base=0.30,
        active_per_star=0,
        inventory_description="Attack +X / Defense +Y",
        inventory_stat="attack_flat",
        inventory_base=1600,
        inventory_per_star=80,  # 2000 at ★5
    ),

    "mushmom_cap": ArtifactDefinition(
        name="Mushmom's Cap",
        tier=ArtifactTier.EPIC,
        active_description="+2% damage per Acc exceeding Evasion (max 40%)",
        active_stat="accuracy_damage",
        active_base=0.02,
        active_per_star=0,
        inventory_description="Attack +X / Defense +Y",
        inventory_stat="attack_flat",
        inventory_base=1600,
        inventory_per_star=80,
    ),
}


# =============================================================================
# CALCULATIONS
# =============================================================================

def calculate_hex_multiplier(stars: int, stacks: int = 3) -> float:
    """
    Calculate Hexagon Necklace total damage multiplier.

    At 3 stacks:
    ★0: 1.60, ★1: 1.66, ★2: 1.72, ★3: 1.78, ★4: 1.84, ★5: 1.90
    """
    hex_def = ARTIFACTS["hexagon_necklace"]
    per_stack = hex_def.get_active_value(stars)
    return 1 + (min(stacks, 3) * per_stack)


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

    # Calculate duplicates needed
    current_dupes = TOTAL_DUPLICATES_TO_STAR.get(current_stars, 0)
    target_dupes = TOTAL_DUPLICATES_TO_STAR.get(target_stars, 0)
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
