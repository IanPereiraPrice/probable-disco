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

# Base ATK% rates at Tier 4 (T4 is the baseline)
# Higher rarity = higher base rate
# VERIFIED from user screenshots (Dec 29, 2025)
BASE_RATES_T4 = {
    WeaponRarity.NORMAL: 0.16,      # 32% / 200 = 0.16
    WeaponRarity.RARE: 0.334,       # 66.8% / 200 = 0.334
    WeaponRarity.EPIC: 0.816,       # 163.2% / 200 = 0.816
    WeaponRarity.UNIQUE: 2.517,     # 251.7% / 100 = 2.517
    WeaponRarity.LEGENDARY: 7.188,  # 718.8% / 100 = 7.188
    WeaponRarity.MYSTIC: 23.86,     # 2027.8% / 85 = 23.86
    WeaponRarity.ANCIENT: 66.72,    # 6672.1% / 100 = 66.72
}

# String keys for convenience
BASE_RATES_T4_STR = {
    "normal": 0.16,
    "rare": 0.334,
    "epic": 0.816,
    "unique": 2.517,
    "legendary": 7.188,
    "mystic": 23.86,
    "ancient": 66.72,
}

# Tier multiplier: higher tier = higher multiplier
# T4 is baseline (1.0x), T3 = 1.3x, T2 = 1.69x, T1 = 2.197x
# Verified from Legendary weapons: T1/T4 = 2.197, T2/T4 = 1.69, T3/T4 = 1.3
TIER_MULTIPLIER = 1.3

# Mystic weapons have different tier multipliers (verified from screenshots)
# T4: 1.0x, T3: 1.271x, T2: 1.409x, T1: 1.748x
MYSTIC_TIER_MULTIPLIERS = {
    4: 1.0,
    3: 1.271,
    2: 1.409,
    1: 1.748,
}

# Unique weapons T1 has different multiplier (verified from screenshots)
# T1: 1.881x instead of standard 2.197x
UNIQUE_TIER_MULTIPLIERS = {
    4: 1.0,
    3: 1.3,
    2: 1.69,
    1: 1.881,  # Different from standard 2.197
}

# Epic weapons have different tier multipliers (verified from screenshots)
# T1: 2.373x, T2: 1.897x, T3: 1.250x
EPIC_TIER_MULTIPLIERS = {
    4: 1.0,
    3: 1.250,
    2: 1.897,
    1: 2.373,
}

# Inventory effect is 1/4 of on-equip effect
INVENTORY_RATIO = 0.25

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

def get_rate_per_level(rarity: WeaponRarity, tier: int) -> float:
    """
    Get ATK% gained per level for a weapon.

    Args:
        rarity: Weapon rarity (normal to ancient)
        tier: Weapon tier (1-4, where T1 is highest)

    Returns:
        ATK% per level
    """
    base = BASE_RATES_T4.get(rarity, 0.16)

    # Mystic weapons have different tier scaling
    if rarity == WeaponRarity.MYSTIC:
        return base * MYSTIC_TIER_MULTIPLIERS.get(tier, 1.0)

    # Unique weapons have different T1 multiplier
    if rarity == WeaponRarity.UNIQUE:
        return base * UNIQUE_TIER_MULTIPLIERS.get(tier, 1.0)

    # Epic weapons have different tier multipliers
    if rarity == WeaponRarity.EPIC:
        return base * EPIC_TIER_MULTIPLIERS.get(tier, 1.0)

    # Standard tier scaling (T4 baseline, lower tier number = higher mult)
    # T4: 1.3^0 = 1.0, T3: 1.3^1 = 1.3, T2: 1.3^2 = 1.69, T1: 1.3^3 = 2.197
    return base * (TIER_MULTIPLIER ** (4 - tier))


def get_rate_per_level_str(rarity: str, tier: int) -> float:
    """String-based version of get_rate_per_level."""
    base = BASE_RATES_T4_STR.get(rarity.lower(), 0.16)

    # Mystic weapons have different tier scaling
    if rarity.lower() == "mystic":
        return base * MYSTIC_TIER_MULTIPLIERS.get(tier, 1.0)

    # Unique weapons have different T1 multiplier
    if rarity.lower() == "unique":
        return base * UNIQUE_TIER_MULTIPLIERS.get(tier, 1.0)

    # Epic weapons have different tier multipliers
    if rarity.lower() == "epic":
        return base * EPIC_TIER_MULTIPLIERS.get(tier, 1.0)

    return base * (TIER_MULTIPLIER ** (4 - tier))


def calculate_weapon_atk(rarity: WeaponRarity, tier: int, level: int) -> Dict[str, float]:
    """
    Calculate weapon ATK% values.

    Args:
        rarity: Weapon rarity
        tier: Weapon tier (1-4)
        level: Current weapon level

    Returns:
        Dict with on_equip_atk, inventory_atk, rate_per_level
    """
    rate = get_rate_per_level(rarity, tier)
    on_equip = level * rate
    inventory = on_equip * INVENTORY_RATIO

    return {
        "on_equip_atk": round(on_equip, 1),
        "inventory_atk": round(inventory, 1),
        "rate_per_level": round(rate, 2),
        "total_atk": round(on_equip + inventory, 1),
    }


def calculate_weapon_atk_str(rarity: str, tier: int, level: int) -> Dict[str, float]:
    """String-based version of calculate_weapon_atk."""
    rate = get_rate_per_level_str(rarity, tier)
    on_equip = level * rate
    inventory = on_equip * INVENTORY_RATIO

    return {
        "on_equip_atk": round(on_equip, 1),
        "inventory_atk": round(inventory, 1),
        "rate_per_level": round(rate, 2),
        "total_atk": round(on_equip + inventory, 1),
    }


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
