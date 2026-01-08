"""
MapleStory Idle - Weapon System
===============================
Weapon mechanics, ATK% scaling, and inventory effects.

Weapons provide:
- On-Equip ATK%: Only applies when the weapon is equipped
- Inventory ATK%: Always applies (1/4 of on-equip value)

ATK% is multiplied against base attack to get total attack.

Last Updated: December 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class WeaponRarity(Enum):
    """Weapon rarity tiers (weakest to strongest)."""
    NORMAL = "normal"
    RARE = "rare"
    EPIC = "epic"
    UNIQUE = "unique"
    LEGENDARY = "legendary"
    MYSTIC = "mystic"
    ANCIENT = "ancient"


# =============================================================================
# CONSTANTS
# =============================================================================

# =============================================================================
# BASE ATK% VALUES (from official documentation Jan 2026)
# =============================================================================
# These are the BASE ATK% values at level 1 for each weapon
# Formula: ATK% = BaseATK × LevelMultiplier
# where LevelMultiplier = (0.997 + 0.003 × Level) for levels 1-100

BASE_ATK = {
    # Normal: T4 base, then 1.2x, 1.1666x, 1.19x progression
    ("normal", 4): 15.0,
    ("normal", 3): 18.0,
    ("normal", 2): 21.0,
    ("normal", 1): 25.0,
    # Rare: 1.25x progression between tiers
    ("rare", 4): 31.3,
    ("rare", 3): 39.1,
    ("rare", 2): 48.9,
    ("rare", 1): 61.1,
    # Epic: 1.25x progression
    ("epic", 4): 76.4,
    ("epic", 3): 95.5,
    ("epic", 2): 119.4,
    ("epic", 1): 149.3,
    # Unique: 1.3x progression
    ("unique", 4): 194.1,
    ("unique", 3): 252.3,
    ("unique", 2): 328.0,
    ("unique", 1): 426.4,
    # Legendary: 1.3x progression
    ("legendary", 4): 554.3,
    ("legendary", 3): 720.6,
    ("legendary", 2): 936.8,
    ("legendary", 1): 1217.8,
    # Mystic: 1.33x progression
    ("mystic", 4): 1619.7,
    ("mystic", 3): 2154.2,
    ("mystic", 2): 2865.1,
    ("mystic", 1): 3810.6,
    # Ancient: 1.35x from Mystic T1, only T4 exists currently
    ("ancient", 4): 5144.3,
    ("ancient", 3): 6944.8,   # Estimated: 5144.3 × 1.35
    ("ancient", 2): 9375.5,   # Estimated: 6944.8 × 1.35
}

# =============================================================================
# LEVEL-UP COST (Weapon Enhancers per level)
# =============================================================================
# Base cost depends on rarity and tier
# Formula: FinalCost = BaseCost × CostMultiplier(level)

BASE_COST = {
    # Normal: base 10, then 1.2x per tier
    ("normal", 4): 10,
    ("normal", 3): 12,
    ("normal", 2): 14.4,
    ("normal", 1): 17.28,
    # Rare: 4x of Normal T4, then 1.2x per tier
    ("rare", 4): 40,
    ("rare", 3): 48,
    ("rare", 2): 57.6,
    ("rare", 1): 69.12,
    # Epic: 3.5x of Rare T4, then 1.2x per tier
    ("epic", 4): 140,
    ("epic", 3): 168,
    ("epic", 2): 201.6,
    ("epic", 1): 241.92,
    # Unique: 3.5x of Epic T4, then 1.2x per tier
    ("unique", 4): 490,
    ("unique", 3): 588,
    ("unique", 2): 705.6,
    ("unique", 1): 846.72,
    # Legendary: 3x of Unique T4, then 1.2x per tier
    ("legendary", 4): 1470,
    ("legendary", 3): 1764,
    ("legendary", 2): 2116.8,
    ("legendary", 1): 2540.16,
    # Mystic: 4x of Legendary T4, then 1.2x per tier
    ("mystic", 4): 5880,
    ("mystic", 3): 7056,
    ("mystic", 2): 8467.2,
    ("mystic", 1): 10160.64,
    # Ancient: 4x of Mystic T4
    ("ancient", 4): 23520,
    ("ancient", 3): 70000,    # Verified from user data Jan 2026
    ("ancient", 2): 120000,   # Verified from user data Jan 2026
}

# Diamond to Weapon Enhancer conversion rate
# 3000 diamonds = 60000 weapon enhancers
DIAMONDS_TO_ENHANCERS = 20  # 1 diamond = 20 weapon enhancers

# =============================================================================
# INVENTORY EFFECT RATIOS
# =============================================================================
# Normal through Unique: 1/3.5 = 28.57%
# Legendary and above: 1/4 = 25%

INVENTORY_RATIO_LOW = 1 / 3.5   # ~0.2857 for Normal-Unique
INVENTORY_RATIO_HIGH = 1 / 4   # 0.25 for Legendary+

def get_inventory_ratio(rarity: str) -> float:
    """Get inventory effect ratio based on rarity."""
    rarity_lower = rarity.lower()
    if rarity_lower in ("legendary", "mystic", "ancient"):
        return INVENTORY_RATIO_HIGH
    return INVENTORY_RATIO_LOW

# Legacy constant for backward compatibility
INVENTORY_RATIO = 0.25

# =============================================================================
# ATTACK SPEED % (On-Equip Only)
# =============================================================================
# Attack speed bonus from equipped weapon only (not inventory)
# Starts at Epic rarity

ATTACK_SPEED_BONUS = {
    "normal": 0.0,
    "rare": 0.0,
    "epic": 2.0,
    "unique": 3.0,
    "legendary": 4.0,
    "mystic": 6.0,
    "ancient": 8.0,
}

def get_attack_speed_bonus(rarity: str) -> float:
    """Get the attack speed % bonus for a weapon rarity (on-equip only)."""
    return ATTACK_SPEED_BONUS.get(rarity.lower(), 0.0)

# Max level by rarity (approximate)
MAX_LEVELS = {
    WeaponRarity.NORMAL: 50,
    WeaponRarity.RARE: 70,
    WeaponRarity.EPIC: 90,
    WeaponRarity.UNIQUE: 110,
    WeaponRarity.LEGENDARY: 130,
    WeaponRarity.MYSTIC: 150,
    WeaponRarity.ANCIENT: 200,
}

# Rarity display colors
RARITY_COLORS = {
    WeaponRarity.NORMAL: "#aaaaaa",
    WeaponRarity.RARE: "#5588ff",
    WeaponRarity.EPIC: "#aa77ff",
    WeaponRarity.UNIQUE: "#ffaa00",
    WeaponRarity.LEGENDARY: "#7fff7f",
    WeaponRarity.MYSTIC: "#ff77ff",
    WeaponRarity.ANCIENT: "#ff5555",
}


# =============================================================================
# CALCULATIONS
# =============================================================================

def get_level_multiplier(level: int) -> float:
    """
    Get the level multiplier for ATK% calculation.

    Formula from official docs:
    - Level 1-100:   BaseATK × (0.997 + 0.003 × Level)
    - Level 101-130: BaseATK × (0.596 + 0.007 × Level)
    - Level 131-155: BaseATK × (0.466 + 0.008 × Level)
    - Level 156-175: BaseATK × (0.311 + 0.009 × Level)
    - Level 176-200: BaseATK × (0.136 + 0.010 × Level)
    """
    if level <= 0:
        return 0.0
    elif level <= 100:
        return 0.997 + 0.003 * level
    elif level <= 130:
        return 0.596 + 0.007 * level
    elif level <= 155:
        return 0.466 + 0.008 * level
    elif level <= 175:
        return 0.311 + 0.009 * level
    else:  # 176-200
        return 0.136 + 0.010 * level


def get_base_atk(rarity: str, tier: int) -> float:
    """Get the base ATK% for a weapon (at level 1 multiplier = 1.0)."""
    key = (rarity.lower(), tier)
    return BASE_ATK.get(key, 15.0)  # Default to Normal T4


def get_cost_multiplier(level: int) -> float:
    """
    Get the cost multiplier for leveling from (level) to (level+1).

    Formula from official docs:
    - Level 1-50:   BaseCost × 1.01^(level-1)
    - Level 51-100: BaseCost × 1.01^49 × 1.015^(level-50)
    - Level 101-150: BaseCost × 1.01^49 × 1.015^50 × 1.02^(level-100)
    - Level 151-200: BaseCost × 1.01^49 × 1.015^50 × 1.02^50 × 1.025^(level-150)
    """
    if level <= 0:
        return 0.0
    elif level <= 50:
        return 1.01 ** (level - 1)
    elif level <= 100:
        return (1.01 ** 49) * (1.015 ** (level - 50))
    elif level <= 150:
        return (1.01 ** 49) * (1.015 ** 50) * (1.02 ** (level - 100))
    else:  # 151-200
        return (1.01 ** 49) * (1.015 ** 50) * (1.02 ** 50) * (1.025 ** (level - 150))


def get_base_cost(rarity: str, tier: int) -> float:
    """Get the base cost (Weapon Enhancers) for a weapon."""
    key = (rarity.lower(), tier)
    return BASE_COST.get(key, 10.0)  # Default to Normal T4


def calculate_level_cost(rarity: str, tier: int, from_level: int) -> int:
    """
    Calculate cost to level up from from_level to from_level+1.

    Returns cost in Weapon Enhancers (rounded up).
    """
    import math
    base = get_base_cost(rarity, tier)
    multiplier = get_cost_multiplier(from_level)
    return math.ceil(base * multiplier)


def calculate_total_cost(rarity: str, tier: int, from_level: int, to_level: int) -> int:
    """
    Calculate total cost to level up from from_level to to_level.

    Returns total cost in Weapon Enhancers.
    """
    total = 0
    for level in range(from_level, to_level):
        total += calculate_level_cost(rarity, tier, level)
    return total


def calculate_weapon_atk_str(rarity: str, tier: int, level: int) -> Dict[str, float]:
    """
    Calculate weapon ATK% values using the official formula.

    Formula: ATK% = BaseATK × LevelMultiplier
    Inventory: On-Equip ATK% × InventoryRatio (1/3.5 for Normal-Unique, 1/4 for Legendary+)

    Args:
        rarity: Weapon rarity string (e.g., "mystic", "legendary")
        tier: Weapon tier (1-4, where T1 is highest)
        level: Current weapon level (1-200)

    Returns:
        Dict with on_equip_atk, inventory_atk, base_atk, level_multiplier
    """
    base = get_base_atk(rarity, tier)
    multiplier = get_level_multiplier(level)
    on_equip = base * multiplier

    # Get correct inventory ratio based on rarity
    inv_ratio = get_inventory_ratio(rarity)
    inventory = on_equip * inv_ratio

    # Calculate approximate rate per level (for display purposes)
    # This is the derivative of the formula at the current level
    if level <= 100:
        rate_per_level = base * 0.003
    elif level <= 130:
        rate_per_level = base * 0.007
    elif level <= 155:
        rate_per_level = base * 0.008
    elif level <= 175:
        rate_per_level = base * 0.009
    else:
        rate_per_level = base * 0.010

    return {
        "on_equip_atk": round(on_equip, 1),
        "inventory_atk": round(inventory, 1),
        "rate_per_level": round(rate_per_level, 2),
        "base_atk": round(base, 1),
        "level_multiplier": round(multiplier, 4),
        "total_atk": round(on_equip + inventory, 1),
    }


def calculate_weapon_atk(rarity: WeaponRarity, tier: int, level: int) -> Dict[str, float]:
    """Enum-based version of calculate_weapon_atk_str."""
    return calculate_weapon_atk_str(rarity.value, tier, level)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class WeaponDefinition:
    """Definition of a weapon type."""
    name: str
    rarity: WeaponRarity
    tier: int  # 1-4, T1 is highest

    # Optional: weapon class (bow, staff, etc.)
    weapon_class: str = "bow"

    def get_rate_per_level(self) -> float:
        """Get ATK% per level for this weapon."""
        return get_rate_per_level(self.rarity, self.tier)

    def get_max_level(self) -> int:
        """Get approximate max level for this weapon."""
        return MAX_LEVELS.get(self.rarity, 100)


@dataclass
class WeaponInstance:
    """A player's specific weapon with level."""
    definition: WeaponDefinition
    level: int = 1
    is_equipped: bool = False

    def get_on_equip_atk(self) -> float:
        """Get on-equip ATK% (only applies if equipped)."""
        rate = self.definition.get_rate_per_level()
        return self.level * rate

    def get_inventory_atk(self) -> float:
        """Get inventory ATK% (always applies)."""
        return self.get_on_equip_atk() * INVENTORY_RATIO

    def get_total_atk_contribution(self) -> float:
        """Get total ATK% contribution from this weapon."""
        inv_atk = self.get_inventory_atk()
        if self.is_equipped:
            return self.get_on_equip_atk() + inv_atk
        return inv_atk

    def get_stats(self) -> Dict[str, float]:
        """Get all weapon stats."""
        return calculate_weapon_atk(
            self.definition.rarity,
            self.definition.tier,
            self.level
        )


@dataclass
class WeaponConfig:
    """Player's complete weapon configuration."""
    # Currently equipped weapon
    equipped: Optional[WeaponInstance] = None

    # All owned weapons (for inventory effects)
    inventory: List[WeaponInstance] = field(default_factory=list)

    def get_total_inventory_atk(self) -> float:
        """Get total inventory ATK% from all weapons."""
        total = 0.0
        for weapon in self.inventory:
            total += weapon.get_inventory_atk()
        return total

    def get_equipped_atk(self) -> float:
        """Get on-equip ATK% from equipped weapon."""
        if self.equipped:
            return self.equipped.get_on_equip_atk()
        return 0.0

    def get_total_atk_percent(self) -> float:
        """Get total ATK% contribution (equipped + all inventory)."""
        return self.get_equipped_atk() + self.get_total_inventory_atk()

    def get_all_stats(self) -> Dict[str, float]:
        """Get all weapon stats for damage calculation."""
        return {
            "weapon_atk_percent": self.get_total_atk_percent(),
            "weapon_equipped_atk": self.get_equipped_atk(),
            "weapon_inventory_atk": self.get_total_inventory_atk(),
        }


# =============================================================================
# WEAPON DEFINITIONS
# =============================================================================

# Common weapon definitions (can be expanded)
WEAPON_DEFINITIONS = {
    # Ancient weapons
    "ancient_bow_t1": WeaponDefinition("Ancient Bow", WeaponRarity.ANCIENT, 1, "bow"),
    "ancient_bow_t2": WeaponDefinition("Ancient Bow", WeaponRarity.ANCIENT, 2, "bow"),
    "ancient_bow_t3": WeaponDefinition("Ancient Bow", WeaponRarity.ANCIENT, 3, "bow"),
    "ancient_bow_t4": WeaponDefinition("Ancient Bow", WeaponRarity.ANCIENT, 4, "bow"),

    # Mystic weapons
    "mystic_bow_t1": WeaponDefinition("Mystic Bow", WeaponRarity.MYSTIC, 1, "bow"),
    "mystic_bow_t2": WeaponDefinition("Mystic Bow", WeaponRarity.MYSTIC, 2, "bow"),
    "mystic_bow_t3": WeaponDefinition("Mystic Bow", WeaponRarity.MYSTIC, 3, "bow"),
    "mystic_bow_t4": WeaponDefinition("Mystic Bow", WeaponRarity.MYSTIC, 4, "bow"),

    # Legendary weapons
    "legendary_bow_t1": WeaponDefinition("Legendary Bow", WeaponRarity.LEGENDARY, 1, "bow"),
    "legendary_bow_t2": WeaponDefinition("Legendary Bow", WeaponRarity.LEGENDARY, 2, "bow"),
    "legendary_bow_t3": WeaponDefinition("Legendary Bow", WeaponRarity.LEGENDARY, 3, "bow"),
    "legendary_bow_t4": WeaponDefinition("Legendary Bow", WeaponRarity.LEGENDARY, 4, "bow"),

    # Unique weapons
    "unique_bow_t1": WeaponDefinition("Unique Bow", WeaponRarity.UNIQUE, 1, "bow"),
    "unique_bow_t2": WeaponDefinition("Unique Bow", WeaponRarity.UNIQUE, 2, "bow"),
    "unique_bow_t3": WeaponDefinition("Unique Bow", WeaponRarity.UNIQUE, 3, "bow"),
    "unique_bow_t4": WeaponDefinition("Unique Bow", WeaponRarity.UNIQUE, 4, "bow"),

    # Epic weapons
    "epic_bow_t1": WeaponDefinition("Epic Bow", WeaponRarity.EPIC, 1, "bow"),
    "epic_bow_t2": WeaponDefinition("Epic Bow", WeaponRarity.EPIC, 2, "bow"),
    "epic_bow_t3": WeaponDefinition("Epic Bow", WeaponRarity.EPIC, 3, "bow"),
    "epic_bow_t4": WeaponDefinition("Epic Bow", WeaponRarity.EPIC, 4, "bow"),
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_weapon_instance(
    rarity: str,
    tier: int,
    level: int,
    weapon_class: str = "bow",
    is_equipped: bool = False
) -> WeaponInstance:
    """Create a weapon instance from parameters."""
    rarity_enum = WeaponRarity(rarity.lower())
    definition = WeaponDefinition(
        name=f"{rarity.capitalize()} {weapon_class.capitalize()}",
        rarity=rarity_enum,
        tier=tier,
        weapon_class=weapon_class,
    )
    return WeaponInstance(
        definition=definition,
        level=level,
        is_equipped=is_equipped,
    )


def get_rarity_color(rarity: WeaponRarity) -> str:
    """Get display color for rarity."""
    return RARITY_COLORS.get(rarity, "#ffffff")


def compare_weapons(weapon1: WeaponInstance, weapon2: WeaponInstance) -> Dict[str, float]:
    """Compare two weapons and return stat differences."""
    stats1 = weapon1.get_stats()
    stats2 = weapon2.get_stats()

    return {
        "on_equip_diff": stats2["on_equip_atk"] - stats1["on_equip_atk"],
        "inventory_diff": stats2["inventory_atk"] - stats1["inventory_atk"],
        "total_diff": stats2["total_atk"] - stats1["total_atk"],
    }


def calculate_level_for_target_atk(
    rarity: WeaponRarity,
    tier: int,
    target_atk: float,
    include_inventory: bool = True
) -> int:
    """Calculate the level needed to reach a target ATK%."""
    rate = get_rate_per_level(rarity, tier)

    if include_inventory:
        # Total ATK = level * rate * 1.25 (on-equip + inventory)
        effective_rate = rate * (1 + INVENTORY_RATIO)
    else:
        effective_rate = rate

    if effective_rate <= 0:
        return 0

    return int(target_atk / effective_rate) + 1


# =============================================================================
# DISPLAY HELPERS
# =============================================================================

def format_weapon_stats(weapon: WeaponInstance) -> str:
    """Format weapon stats for display."""
    stats = weapon.get_stats()
    return (
        f"{weapon.definition.name} (T{weapon.definition.tier}) Lv.{weapon.level}\n"
        f"  On-Equip: +{stats['on_equip_atk']:.1f}% ATK\n"
        f"  Inventory: +{stats['inventory_atk']:.1f}% ATK\n"
        f"  Rate: +{stats['rate_per_level']:.2f}% per level"
    )


def print_rarity_comparison(tier: int = 1, level: int = 100):
    """Print ATK% comparison across all rarities at given tier/level."""
    print(f"\n{'='*60}")
    print(f"WEAPON ATK% COMPARISON - Tier {tier}, Level {level}")
    print(f"{'='*60}")
    print(f"{'Rarity':<12} {'Rate/Lv':<10} {'On-Equip':<12} {'Inventory':<12} {'Total':<10}")
    print("-" * 60)

    for rarity in WeaponRarity:
        stats = calculate_weapon_atk(rarity, tier, level)
        print(f"{rarity.value.capitalize():<12} "
              f"{stats['rate_per_level']:<10.2f} "
              f"{stats['on_equip_atk']:<12.1f} "
              f"{stats['inventory_atk']:<12.1f} "
              f"{stats['total_atk']:<10.1f}")


# =============================================================================
# MAIN (Testing)
# =============================================================================

if __name__ == "__main__":
    print("MapleStory Idle - Weapon System Module")
    print("=" * 60)

    # Test Mystic T1 at level 130 (from user's example)
    print("\nMystic T1 at Level 130:")
    result = calculate_weapon_atk(WeaponRarity.MYSTIC, 1, 130)
    print(f"  On-Equip ATK: {result['on_equip_atk']}%")
    print(f"  Inventory ATK: {result['inventory_atk']}%")
    print(f"  Rate per level: {result['rate_per_level']}%")

    # Comparison tables
    print_rarity_comparison(tier=1, level=100)
    print_rarity_comparison(tier=4, level=100)

    # Test weapon instance
    print("\n" + "=" * 60)
    print("WEAPON INSTANCE TEST")
    print("=" * 60)

    weapon = create_weapon_instance("mystic", 1, 130, "bow", True)
    print(format_weapon_stats(weapon))
    print(f"\nTotal contribution: +{weapon.get_total_atk_contribution():.1f}% ATK")

    # Test weapon config
    print("\n" + "=" * 60)
    print("WEAPON CONFIG TEST")
    print("=" * 60)

    config = WeaponConfig()
    config.equipped = create_weapon_instance("mystic", 1, 130, "bow", True)
    config.inventory.append(config.equipped)
    config.inventory.append(create_weapon_instance("legendary", 2, 80, "bow", False))
    config.inventory.append(create_weapon_instance("unique", 3, 60, "bow", False))

    print(f"Equipped ATK%: {config.get_equipped_atk():.1f}%")
    print(f"Total Inventory ATK%: {config.get_total_inventory_atk():.1f}%")
    print(f"Total ATK%: {config.get_total_atk_percent():.1f}%")
