"""
MapleStory Idle - Equipment Sets (Medals & Costumes)
=====================================================
Medals and Costumes provide flat main stat bonuses through inventory effects.

Last Updated: December 2025
"""

from dataclasses import dataclass, field
from typing import Dict
from enum import Enum


# =============================================================================
# CONSTANTS
# =============================================================================

# Medal inventory effect provides flat main stat
# Max: +1,500 DEX (user has 780/1,500)
MEDAL_INVENTORY_EFFECT = {
    "max_value": 1500,
    "stat_type": "main_stat_flat",
    "description": "Medal Inventory Effect: +X Main Stat (max 1,500)",
}

# Costume inventory effect provides flat main stat
# Max: +1,500 DEX (user has 1,500/1,500 = MAX)
COSTUME_INVENTORY_EFFECT = {
    "max_value": 1500,
    "stat_type": "main_stat_flat",
    "description": "Costume Inventory Effect: +X Main Stat (max 1,500)",
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MedalConfig:
    """
    Medal configuration for inventory effect.

    Medals provide flat main stat through their inventory effect.
    The effect scales based on medals collected/upgraded.
    """
    inventory_effect: int = 0  # Current flat main stat bonus (0-1500)

    def get_main_stat(self) -> int:
        """Get flat main stat from medal inventory effect."""
        return min(self.inventory_effect, MEDAL_INVENTORY_EFFECT["max_value"])

    def get_all_stats(self) -> Dict[str, float]:
        """Get all medal stats for damage calculation."""
        return {
            "main_stat_flat": float(self.get_main_stat()),
        }

    def to_dict(self) -> Dict:
        """Serialize to dict for saving."""
        return {
            "inventory_effect": self.inventory_effect,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "MedalConfig":
        """Deserialize from dict."""
        return cls(
            inventory_effect=data.get("inventory_effect", 0),
        )


@dataclass
class CostumeConfig:
    """
    Costume/Cosmetic configuration for inventory effect.

    Costumes provide flat main stat through their inventory effect.
    The effect scales based on costumes collected/upgraded.
    """
    inventory_effect: int = 0  # Current flat main stat bonus (0-1500)

    def get_main_stat(self) -> int:
        """Get flat main stat from costume inventory effect."""
        return min(self.inventory_effect, COSTUME_INVENTORY_EFFECT["max_value"])

    def get_all_stats(self) -> Dict[str, float]:
        """Get all costume stats for damage calculation."""
        return {
            "main_stat_flat": float(self.get_main_stat()),
        }

    def to_dict(self) -> Dict:
        """Serialize to dict for saving."""
        return {
            "inventory_effect": self.inventory_effect,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CostumeConfig":
        """Deserialize from dict."""
        return cls(
            inventory_effect=data.get("inventory_effect", 0),
        )


@dataclass
class EquipmentSetsConfig:
    """
    Combined configuration for all equipment set systems (Medals + Costumes).
    """
    medal_config: MedalConfig = field(default_factory=MedalConfig)
    costume_config: CostumeConfig = field(default_factory=CostumeConfig)

    def get_total_main_stat(self) -> int:
        """Get combined flat main stat from all equipment sets."""
        return self.medal_config.get_main_stat() + self.costume_config.get_main_stat()

    def get_all_stats(self) -> Dict[str, float]:
        """Get all equipment set stats for damage calculation."""
        medal_stats = self.medal_config.get_all_stats()
        costume_stats = self.costume_config.get_all_stats()

        # Combine stats
        combined = {}
        for key in set(medal_stats.keys()) | set(costume_stats.keys()):
            combined[key] = medal_stats.get(key, 0) + costume_stats.get(key, 0)

        return combined

    def to_dict(self) -> Dict:
        """Serialize to dict for saving."""
        return {
            "medal": self.medal_config.to_dict(),
            "costume": self.costume_config.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "EquipmentSetsConfig":
        """Deserialize from dict."""
        return cls(
            medal_config=MedalConfig.from_dict(data.get("medal", {})),
            costume_config=CostumeConfig.from_dict(data.get("costume", {})),
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_default_config() -> EquipmentSetsConfig:
    """Create default (empty) equipment sets configuration."""
    return EquipmentSetsConfig()


def create_maxed_config() -> EquipmentSetsConfig:
    """Create maxed equipment sets configuration."""
    return EquipmentSetsConfig(
        medal_config=MedalConfig(inventory_effect=MEDAL_INVENTORY_EFFECT["max_value"]),
        costume_config=CostumeConfig(inventory_effect=COSTUME_INVENTORY_EFFECT["max_value"]),
    )


def get_max_stats() -> Dict[str, float]:
    """Get stats if all equipment sets are maxed."""
    return create_maxed_config().get_all_stats()


# =============================================================================
# MAIN (Testing)
# =============================================================================

if __name__ == "__main__":
    print("MapleStory Idle - Equipment Sets Module")
    print("=" * 60)

    # Test default config
    print("\nDefault Config (all zeros):")
    config = create_default_config()
    print(f"  Medal Main Stat: {config.medal_config.get_main_stat()}")
    print(f"  Costume Main Stat: {config.costume_config.get_main_stat()}")
    print(f"  Total Main Stat: {config.get_total_main_stat()}")

    # Test maxed config
    print("\nMaxed Config:")
    max_config = create_maxed_config()
    print(f"  Medal Main Stat: {max_config.medal_config.get_main_stat()}")
    print(f"  Costume Main Stat: {max_config.costume_config.get_main_stat()}")
    print(f"  Total Main Stat: {max_config.get_total_main_stat()}")

    # Test user values (from stat mapping doc)
    print("\nUser Values (from screenshots):")
    user_config = EquipmentSetsConfig(
        medal_config=MedalConfig(inventory_effect=780),
        costume_config=CostumeConfig(inventory_effect=1500),
    )
    print(f"  Medal (780/1500): {user_config.medal_config.get_main_stat()}")
    print(f"  Costume (1500/1500): {user_config.costume_config.get_main_stat()}")
    print(f"  Total Main Stat: {user_config.get_total_main_stat()}")
    print(f"  Expected Total: 2,280")

    # Test serialization
    print("\nSerialization Test:")
    data = user_config.to_dict()
    restored = EquipmentSetsConfig.from_dict(data)
    print(f"  Original Total: {user_config.get_total_main_stat()}")
    print(f"  Restored Total: {restored.get_total_main_stat()}")
    print(f"  Match: {'YES' if user_config.get_total_main_stat() == restored.get_total_main_stat() else 'NO'}")
