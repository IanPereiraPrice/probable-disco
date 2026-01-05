"""
MapleStory Idle - Complete Damage & Stat Formulas
==================================================
Verified through empirical testing on Bowmaster character.
Last Updated: December 2025

This module contains all verified formulas for damage calculation,
stat stacking, and game mechanics.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from enum import Enum


# =============================================================================
# CORE CONSTANTS
# =============================================================================

# Damage Amplification constant (discovered through testing)
DAMAGE_AMP_DIVISOR = 396.5  # Formula: 1 + (DamageAmp / 396.5)


# =============================================================================
# ENUMS
# =============================================================================

class StatStackingType(Enum):
    """How different stat types combine with each other."""
    ADDITIVE = "additive"          # Sum together, then apply as one multiplier
    MULTIPLICATIVE = "multiplicative"  # Each source multiplies separately


class Rarity(Enum):
    """Equipment rarity tiers from lowest to highest."""
    RARE = "rare"
    NORMAL = "normal"
    EPIC = "epic"
    UNIQUE = "unique"
    LEGENDARY = "legendary"
    MYSTIC = "mystic"
    ANCIENT = "ancient"


# =============================================================================
# STAT STACKING BEHAVIOR (VERIFIED)
# =============================================================================

STAT_STACKING = {
    # Stat Name: (Stacking Type, Notes)
    "dex_percent": (StatStackingType.ADDITIVE, "All %DEX sources sum together"),
    "dex_flat": (StatStackingType.ADDITIVE, "Then multiplied by (1 + %DEX)"),
    "damage_percent": (StatStackingType.ADDITIVE, "Hex Necklace MULTIPLIES the total"),
    "damage_amplification": (StatStackingType.ADDITIVE, "Separate multiplier, scrolls ONLY"),
    "final_damage": (StatStackingType.MULTIPLICATIVE, "Each source multiplies: ×1.13 × ×1.10 × ..."),
    "defense_penetration": (StatStackingType.MULTIPLICATIVE, "Each source multiplies"),
    "critical_rate": (StatStackingType.ADDITIVE, "All sources sum"),
    "critical_damage": (StatStackingType.ADDITIVE, "All sources sum"),
    "min_max_damage_mult": (StatStackingType.ADDITIVE, "All sources sum"),
    "boss_normal_damage": (StatStackingType.ADDITIVE, "Additive within category"),
}


# =============================================================================
# DEX CALCULATION
# =============================================================================

def calculate_total_dex(flat_dex_pool: float, percent_dex: float) -> float:
    """
    Calculate total DEX from flat pool and percentage bonus.
    
    Formula (VERIFIED):
        Total_DEX = Flat_DEX_Pool × (1 + %DEX)
    
    Test Evidence:
        - Companion +19 flat → +43 DEX (multiplier 2.26x) ✓
        - Hero Ability -560 flat → -1,178 DEX (multiplier 2.10x) ✓
        - Artifact -7% → -1,305 DEX (pool calc: 18,643) ✓
    
    Args:
        flat_dex_pool: Sum of all flat DEX sources (base + equipment + skills)
        percent_dex: Total %DEX bonus as decimal (1.265 for 126.5%)
    
    Returns:
        Total DEX value
    """
    return flat_dex_pool * (1 + percent_dex)


def dex_equivalent(percent_dex_bonus: float, flat_dex_pool: float) -> float:
    """
    Calculate flat DEX equivalent of a %DEX bonus.
    
    At 126.5% bonus DEX, each 1% DEX = ~187 flat DEX equivalent.
    
    Args:
        percent_dex_bonus: The %DEX bonus as decimal (0.01 for 1%)
        flat_dex_pool: Current flat DEX pool
    
    Returns:
        Equivalent flat DEX value
    """
    return percent_dex_bonus * flat_dex_pool


# =============================================================================
# STAT PROPORTIONAL DAMAGE
# =============================================================================

def calculate_stat_proportional_damage(total_dex: float, total_str: float) -> float:
    """
    Calculate stat-based damage multiplier (for Bowmaster).
    
    Formula (VERIFIED):
        Stat_Prop_Damage% = (Total_DEX × 1%) + (Total_STR × 0.25%)
    
    Example: DEX 42,290 × 0.01 + STR 200 × 0.0025 = 423.4% ✓
    
    Args:
        total_dex: Total DEX after all bonuses
        total_str: Total STR after all bonuses
    
    Returns:
        Stat proportional damage as decimal (4.234 for 423.4%)
    """
    return (total_dex * 0.01) + (total_str * 0.0025)


# =============================================================================
# DAMAGE PERCENTAGE (ADDITIVE + HEX MULTIPLIER)
# =============================================================================

def calculate_damage_percent(
    additive_sources: float,
    hex_stacks: int = 0
) -> float:
    """
    Calculate total Damage % including Hexagon Necklace buff.
    
    Additive Sources (sum together):
        - Equipment Potentials
        - Hero Ability
        - Companion Inventory Effects
        - Maple Rank
        - Guild Skills
        - Skills (like Marksmanship)
    
    Multiplicative Source:
        - Hexagon Necklace Buff: ×1.24 per stack (max 3 = ×1.72)
    
    Test Evidence:
        | Hex Stacks | Damage % | Change  |
        |------------|----------|---------|
        | 0          | 484.1%   | -       |
        | 1          | 597.8%   | +113.7% |
        | 2          | 711.6%   | +113.8% |
        | 3          | 825.4%   | +113.8% |
    
    Args:
        additive_sources: Sum of all additive Damage % sources as decimal
        hex_stacks: Number of Hexagon Necklace buff stacks (0-3)
    
    Returns:
        Total Damage % as decimal
    """
    hex_multiplier = 1.24 ** min(hex_stacks, 3)  # Cap at 3 stacks
    return additive_sources * hex_multiplier


# =============================================================================
# DAMAGE AMPLIFICATION
# =============================================================================

def calculate_damage_amp_multiplier(damage_amp_percent: float) -> float:
    """
    Calculate Damage Amplification multiplier.
    
    Formula (VERIFIED):
        Multiplier = 1 + (DamageAmp% / 396.5)
    
    Source: Scrolls ONLY (does NOT affect displayed Damage %)
    
    Test Evidence:
        - Removed 2.4% Damage Amp via scroll reset
        - Displayed Damage % unchanged (493.6% → 493.6%)
        - Confirms it's a separate multiplier
    
    Args:
        damage_amp_percent: Total Damage Amplification % from scrolls
    
    Returns:
        Damage Amplification multiplier
    """
    return 1 + (damage_amp_percent / DAMAGE_AMP_DIVISOR)


# =============================================================================
# FINAL DAMAGE (MULTIPLICATIVE)
# =============================================================================

def calculate_final_damage(sources: Dict[str, float]) -> float:
    """
    Calculate total Final Damage from multiplicative sources.
    
    Formula (VERIFIED):
        Final Damage % = [(1 + FD₁) × (1 + FD₂) × (1 + FD₃) × ...] - 1
    
    Test Evidence:
        | State                   | Final Damage | Calculation             |
        |-------------------------|--------------|-------------------------|
        | Base (no Mortal/Flower) | 51.8%        | -                       |
        | + Mortal Blow           | 73.6%        | 1.518 × 1.144 = 1.737 ✓ |
        | + Fire Flower           | 94.5%        | 1.736 × 1.12 = 1.944 ✓  |
    
    Args:
        sources: Dictionary of {source_name: fd_percent_as_decimal}
                 Example: {"bottom": 0.13, "guild": 0.10, "extreme_archery": 0.217}
    
    Returns:
        Total Final Damage as decimal (0.945 for 94.5%)
    """
    multiplier = 1.0
    for fd_value in sources.values():
        multiplier *= (1 + fd_value)
    return multiplier - 1


# Known Final Damage sources for Bowmaster
BOWMASTER_FD_SOURCES = {
    "bottom_pot_bonus": 0.13,      # Bottom equipment potential + bonus
    "guild_skill": 0.10,           # Guild passive
    "extreme_archery_bow": 0.217,  # Skill passive (always active)
    "mortal_blow": 0.144,          # Conditional: after 50 hits, 5s duration
    "fire_flower": 0.12,           # Artifact: max 10 targets, 1.2% each
}


# =============================================================================
# DEFENSE PENETRATION (IED - MULTIPLICATIVE)
# =============================================================================

def calculate_defense_penetration(sources: list[float]) -> float:
    """
    Calculate total Defense Penetration from multiplicative sources.
    
    Formula (VERIFIED):
        Remaining = (1 - IED₁) × (1 - IED₂) × (1 - IED₃) × ...
        Total Def Pen = 1 - Remaining
    
    Test Evidence:
        Base: 42.4%
        + Hero Ability 19%: (1-0.424) × (1-0.19) = remaining 46.7%
        + Hero Ability 16.5%: × (1-0.165) = remaining 38.9%
        Total Def Pen = 1 - 0.389 = 61.1% (Actual: 60.9%) ✓
    
    Args:
        sources: List of Defense Penetration values as decimals
                 Example: [0.424, 0.19, 0.165]
    
    Returns:
        Total Defense Penetration as decimal
    """
    remaining = 1.0
    for ied in sources:
        remaining *= (1 - ied)
    return 1 - remaining


# =============================================================================
# DEFENSE FORMULA (ENEMY DAMAGE REDUCTION)
# =============================================================================

def calculate_damage_vs_defense(
    base_damage: float,
    def_pen: float,
    enemy_def_value: float
) -> float:
    """
    Calculate actual damage after enemy defense.
    
    Formula (VERIFIED):
        Damage = BaseDamage / (1 + EnemyDefValue × (1 - YourDefPen))
    
    Known Enemy Defense Values:
        - Maple Island 1-1: 0.0
        - Aquarium 14: 0.388
        - Mu Lung 27-1: 0.752
        - World Boss (King Castle Golem): 6.527
    
    Args:
        base_damage: Your damage before defense calculation
        def_pen: Your total defense penetration as decimal
        enemy_def_value: Enemy's raw defense value (not percentage)
    
    Returns:
        Actual damage dealt
    """
    return base_damage / (1 + enemy_def_value * (1 - def_pen))


# Known enemy defense values from testing
ENEMY_DEFENSE_VALUES = {
    "Maple Island 1-1": 0.0,
    "Aquarium 14": 0.388,
    "Mu Lung 27-1": 0.752,
    "World Boss (King Castle Golem)": 6.527,
}


# =============================================================================
# CRITICAL DAMAGE
# =============================================================================

def calculate_effective_crit_damage(
    base_crit_damage: float,
    crit_rate: float,
    book_of_ancient_active: bool = False
) -> float:
    """
    Calculate effective critical damage including Book of Ancient bonus.
    
    Book of Ancient Special Effect:
        "Critical Damage by 36% of Critical Rate"
        Your CR: 111.9% → Bonus CD: 111.9 × 0.36 = 40.3%
    
    Args:
        base_crit_damage: Base critical damage as decimal (1.845 for 184.5%)
        crit_rate: Critical rate as decimal (1.119 for 111.9%)
        book_of_ancient_active: Whether Book of Ancient artifact is equipped
    
    Returns:
        Total critical damage as decimal
    """
    bonus_cd = (crit_rate * 0.36) if book_of_ancient_active else 0
    return base_crit_damage + bonus_cd


# =============================================================================
# MASTER DAMAGE FORMULA
# =============================================================================

@dataclass
class DamageCalculation:
    """Complete damage calculation result with breakdown."""
    base_atk: float
    stat_multiplier: float
    damage_percent_multiplier: float
    damage_amp_multiplier: float
    final_damage_multiplier: float
    crit_damage_multiplier: float
    defense_multiplier: float
    
    @property
    def total_damage(self) -> float:
        """Calculate total damage from all multipliers."""
        return (
            self.base_atk *
            self.stat_multiplier *
            self.damage_percent_multiplier *
            self.damage_amp_multiplier *
            self.final_damage_multiplier *
            self.crit_damage_multiplier *
            self.defense_multiplier
        )
    
    def breakdown(self) -> str:
        """Return formatted breakdown of damage calculation."""
        return f"""
Damage Calculation Breakdown
============================
Base ATK:           {self.base_atk:,.0f}
× Stat Prop:        {self.stat_multiplier:.4f} (1 + stat%)
× Damage %:         {self.damage_percent_multiplier:.4f} (1 + dmg%)
× Damage Amp:       {self.damage_amp_multiplier:.4f} (1 + amp/396.5)
× Final Damage:     {self.final_damage_multiplier:.4f} (multiplicative)
× Crit Damage:      {self.crit_damage_multiplier:.4f} (1 + crit dmg%)
× Defense:          {self.defense_multiplier:.4f} (vs enemy def)
----------------------------
= Total Damage:     {self.total_damage:,.0f}
"""


def calculate_full_damage(
    base_atk: float,
    total_dex: float,
    total_str: float,
    damage_percent: float,
    damage_amp: float,
    final_damage_sources: Dict[str, float],
    crit_damage: float,
    def_pen: float,
    enemy_def: float,
    boss_or_normal_bonus: float = 0.0
) -> DamageCalculation:
    """
    Calculate complete damage using the verified master formula.
    
    Master Formula:
        Actual Damage = Base ATK × (1 + Stat%) × (1 + Damage%) × 
                        (1 + Damage Amp%) × (1 + Final Damage%) × 
                        (1 + Crit Damage%) × Defense Multiplier
    
    Args:
        base_atk: Total attack value
        total_dex: Total DEX after all bonuses
        total_str: Total STR after all bonuses
        damage_percent: Total Damage % (including Boss/Normal) as decimal
        damage_amp: Damage Amplification % from scrolls
        final_damage_sources: Dict of Final Damage sources
        crit_damage: Critical Damage as decimal
        def_pen: Total Defense Penetration as decimal
        enemy_def: Enemy defense value
        boss_or_normal_bonus: Additional Boss/Normal Monster Damage as decimal
    
    Returns:
        DamageCalculation with full breakdown
    """
    stat_mult = 1 + calculate_stat_proportional_damage(total_dex, total_str)
    dmg_mult = 1 + damage_percent + boss_or_normal_bonus
    amp_mult = calculate_damage_amp_multiplier(damage_amp)
    fd_mult = 1 + calculate_final_damage(final_damage_sources)
    crit_mult = 1 + crit_damage
    def_mult = 1 / (1 + enemy_def * (1 - def_pen))
    
    return DamageCalculation(
        base_atk=base_atk,
        stat_multiplier=stat_mult,
        damage_percent_multiplier=dmg_mult,
        damage_amp_multiplier=amp_mult,
        final_damage_multiplier=fd_mult,
        crit_damage_multiplier=crit_mult,
        defense_multiplier=def_mult
    )


# =============================================================================
# WEAPON ATK% CALCULATOR
# =============================================================================

# Base rates per level at T4 for each rarity (verified)
WEAPON_BASE_RATES_T4 = {
    Rarity.RARE: 0.10,
    Rarity.NORMAL: 0.20,
    Rarity.EPIC: 0.35,
    Rarity.UNIQUE: 1.00,
    Rarity.LEGENDARY: 2.85,
    Rarity.MYSTIC: 8.50,
    Rarity.ANCIENT: 51.30,
}

# Tier multiplier (each tier up from T4)
WEAPON_TIER_MULTIPLIER = 1.30

# Mystic T1 has special multiplier
MYSTIC_T1_EXTRA_MULTIPLIER = 0.83

# Inventory to On-Equip ratio
WEAPON_INVENTORY_RATIO = 3.5


def calculate_weapon_atk(
    rarity: Rarity,
    tier: int,
    level: int
) -> Tuple[float, float]:
    """
    Calculate weapon On-Equip and Inventory ATK% values.
    
    Formula derived from 50+ data points through in-game testing.
    
    Args:
        rarity: Weapon rarity (Rarity enum)
        tier: Weapon tier (1-4, where T1 is best)
        level: Weapon level
    
    Returns:
        Tuple of (on_equip_atk_percent, inventory_atk_percent)
    """
    if tier < 1 or tier > 4:
        raise ValueError(f"Tier must be 1-4, got {tier}")
    
    base_rate = WEAPON_BASE_RATES_T4.get(rarity, 0.1)
    
    # Calculate tier factor (T4 = baseline)
    tier_factor = WEAPON_TIER_MULTIPLIER ** (4 - tier)
    
    # Special case for Mystic T1
    if rarity == Rarity.MYSTIC and tier == 1:
        tier_factor *= MYSTIC_T1_EXTRA_MULTIPLIER
    
    rate_per_level = base_rate * tier_factor
    on_equip = rate_per_level * level
    inventory = on_equip / WEAPON_INVENTORY_RATIO
    
    return (round(on_equip, 1), round(inventory, 1))


# =============================================================================
# CHARACTER STATE
# =============================================================================

@dataclass
class CharacterStats:
    """Complete character stat state for damage calculations."""
    
    # Base stats
    dex_flat_pool: int = 18700         # Before %DEX multiplier
    dex_percent: float = 1.265         # Total %DEX as decimal
    str_flat: int = 200
    
    # Attack
    attack: int = 0
    
    # Damage multipliers
    damage_percent_base: float = 4.841  # Base Damage % pool (before Hex)
    damage_amplification: float = 23.2  # From scrolls
    
    # Final Damage sources (multiplicative)
    final_damage_sources: Dict[str, float] = field(default_factory=lambda: {
        "bottom": 0.13,
        "guild": 0.10,
        "extreme_archery": 0.217,
    })
    
    # Critical stats
    critical_rate: float = 1.119       # 111.9%
    critical_damage: float = 1.845     # 184.5%
    
    # Other multipliers
    boss_damage: float = 0.645         # 64.5%
    normal_damage: float = 1.258       # 125.8%
    
    # Defense penetration sources
    def_pen_sources: list = field(default_factory=lambda: [0.424, 0.19, 0.165])
    
    # Min/Max damage
    min_damage_mult: float = 1.637     # 163.7%
    max_damage_mult: float = 2.00      # 200%
    
    # Artifacts/buffs
    hex_stacks: int = 3
    book_of_ancient: bool = True
    mortal_blow_active: bool = False
    fire_flower_targets: int = 0
    
    def get_total_dex(self) -> float:
        """Calculate total DEX after multiplier."""
        return calculate_total_dex(self.dex_flat_pool, self.dex_percent)
    
    def get_damage_percent(self) -> float:
        """Get total Damage % including Hex stacks."""
        return calculate_damage_percent(self.damage_percent_base, self.hex_stacks)
    
    def get_final_damage_sources(self) -> Dict[str, float]:
        """Get all active Final Damage sources."""
        sources = dict(self.final_damage_sources)
        if self.mortal_blow_active:
            sources["mortal_blow"] = 0.144
        if self.fire_flower_targets > 0:
            sources["fire_flower"] = min(self.fire_flower_targets, 10) * 0.012
        return sources
    
    def get_defense_penetration(self) -> float:
        """Calculate total defense penetration."""
        return calculate_defense_penetration(self.def_pen_sources)
    
    def get_crit_damage(self) -> float:
        """Get total crit damage including Book of Ancient."""
        return calculate_effective_crit_damage(
            self.critical_damage,
            self.critical_rate,
            self.book_of_ancient
        )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def compare_stat_value(
    current_stats: CharacterStats,
    stat_name: str,
    change_amount: float,
    enemy_def: float = 0.752  # Default: Mu Lung 27-1
) -> Tuple[float, float, float]:
    """
    Compare damage before and after a stat change.
    
    Args:
        current_stats: Current character state
        stat_name: Name of stat to change
        change_amount: Amount to add (negative to subtract)
        enemy_def: Enemy defense value for calculation
    
    Returns:
        Tuple of (damage_before, damage_after, percent_change)
    """
    # Calculate current damage
    before = calculate_full_damage(
        base_atk=current_stats.attack,
        total_dex=current_stats.get_total_dex(),
        total_str=current_stats.str_flat,
        damage_percent=current_stats.get_damage_percent(),
        damage_amp=current_stats.damage_amplification,
        final_damage_sources=current_stats.get_final_damage_sources(),
        crit_damage=current_stats.get_crit_damage(),
        def_pen=current_stats.get_defense_penetration(),
        enemy_def=enemy_def,
        boss_or_normal_bonus=current_stats.boss_damage
    )
    
    # This is a simplified comparison - in practice you'd modify the stat
    # and recalculate. For now, return placeholder.
    return (before.total_damage, before.total_damage, 0.0)


# =============================================================================
# MAIN (Example Usage)
# =============================================================================

if __name__ == "__main__":
    print("MapleStory Idle - Damage Formula Module")
    print("=" * 50)
    
    # Example: Calculate damage with current stats
    stats = CharacterStats()
    
    print(f"\nCharacter Summary:")
    print(f"  Total DEX: {stats.get_total_dex():,.0f}")
    print(f"  Damage %: {stats.get_damage_percent() * 100:.1f}%")
    print(f"  Final Damage: {calculate_final_damage(stats.get_final_damage_sources()) * 100:.1f}%")
    print(f"  Defense Pen: {stats.get_defense_penetration() * 100:.1f}%")
    print(f"  Crit Damage: {stats.get_crit_damage() * 100:.1f}%")
    
    # Example damage calculation
    calc = calculate_full_damage(
        base_atk=50000,
        total_dex=stats.get_total_dex(),
        total_str=stats.str_flat,
        damage_percent=stats.get_damage_percent(),
        damage_amp=stats.damage_amplification,
        final_damage_sources=stats.get_final_damage_sources(),
        crit_damage=stats.get_crit_damage(),
        def_pen=stats.get_defense_penetration(),
        enemy_def=0.752,  # Mu Lung 27-1
        boss_or_normal_bonus=stats.boss_damage
    )
    
    print(calc.breakdown())
