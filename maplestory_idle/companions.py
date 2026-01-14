"""
MapleStory Idle - Companion System
==================================
Companion mechanics, stats, and inventory effects.

Based on actual game screenshots and user corrections (Dec 29, 2025)

Companions provide:
- On-Equip Effects: Only active when equipped in a slot (7 slots: 1 Main + 6 Sub)
- Inventory Effects: ALWAYS active (all owned companions contribute)

Tier Structure:
- Basic (Grey): 4 companions, max level 100, Inventory: Attack + HP
- 1st Job (Blue): 8 companions, max level 50, Inventory: Attack + HP
- 2nd Job (Purple): 8 companions, max level 30, Inventory: Flat Main Stat
- 3rd Job: 8 companions, max level 10, Inventory: Damage %
- 4th Job: 8 companions, max level 10, Inventory: Damage %

Last Updated: December 29, 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class CompanionJob(Enum):
    """Job classes for companions."""
    BASIC = "basic"  # Aspiring companions
    BOWMASTER = "bowmaster"
    MARKSMAN = "marksman"
    NIGHT_LORD = "night_lord"
    SHADOWER = "shadower"
    HERO = "hero"
    DARK_KNIGHT = "dark_knight"
    ARCH_MAGE_FP = "arch_mage_fp"
    ARCH_MAGE_IL = "arch_mage_il"


class JobAdvancement(Enum):
    """Job advancement tier (determines inventory effect type and max level)."""
    BASIC = 0   # Grey, max 100, Attack + HP inventory
    FIRST = 1   # Blue, max 50, Attack + HP inventory
    SECOND = 2  # Purple, max 30, Main Stat inventory
    THIRD = 3   # max 10, Damage % inventory
    FOURTH = 4  # max 10, Damage % inventory


class OnEquipStatType(Enum):
    """Stats that companions can provide as on-equip effects."""
    FLAT_ATTACK = "flat_attack"  # Basic tier
    ATTACK_SPEED = "attack_speed"
    MIN_DMG_MULT = "min_dmg_mult"
    MAX_DMG_MULT = "max_dmg_mult"
    BOSS_DAMAGE = "boss_damage"
    NORMAL_DAMAGE = "normal_damage"
    CRIT_RATE = "crit_rate"
    STATUS_EFFECT_DMG = "status_effect_dmg"
    ACCURACY = "accuracy"


# =============================================================================
# CONSTANTS
# =============================================================================

# Max levels by job advancement (CORRECTED from user feedback)
MAX_LEVELS = {
    JobAdvancement.BASIC: 100,
    JobAdvancement.FIRST: 50,
    JobAdvancement.SECOND: 30,
    JobAdvancement.THIRD: 10,
    JobAdvancement.FOURTH: 10,
}

# Number of equip slots
MAIN_SLOTS = 1
SUB_SLOTS = 6
TOTAL_EQUIP_SLOTS = 7

# Inventory effect scaling per level by job advancement
# From screenshots:
# - Aspiring Warrior Lv 100: Attack 1703, Max HP 17034 → 17.03 attack/level, 170.34 HP/level
# - Hero (1st) Lv 50: Attack 951, Max HP 9515 → 19.02 attack/level, 190.3 HP/level
# - Hero (2nd) Lv 26: Main Stat 508 → ~19.5 main stat/level
# - 3rd Job: ~1% Damage per level (7.8% at lv4 → 11.9% at lv8)
# - 4th Job: ~2% Damage per level (10% at lv1 → 16% at higher levels)
INVENTORY_SCALING = {
    JobAdvancement.BASIC: {
        "attack_per_level": 17.03,  # 1703 / 100 from Aspiring Warrior screenshot
        "max_hp_per_level": 170.34,  # 17034 / 100 from screenshot
    },
    JobAdvancement.FIRST: {
        "attack_per_level": 19.02,  # 951 / 50 from Hero (1st) screenshot
        "max_hp_per_level": 190.3,  # 9515 / 50 from screenshot
    },
    JobAdvancement.SECOND: {
        # Hero (2nd) Lv 26: Main Stat 508, Max HP 12722 → 19.54/level, 489.3 HP/level
        # Dark Knight (2nd) Lv 27: Main Stat 531, Max HP 13282 → 19.67/level, 491.9 HP/level
        "main_stat_per_level": 19.6,  # Average of 19.54 and 19.67
        "max_hp_per_level": 490.5,    # Average of 489.3 and 491.9
    },
    JobAdvancement.THIRD: {
        # 3rd job gives Damage % as inventory effect
        # ~1% per level, starting around 4.8% at level 1
        "damage_base": 4.8,
        "damage_per_level": 1.0,
    },
    JobAdvancement.FOURTH: {
        # 4th job gives Damage % as inventory effect
        # ~2% per level, starting around 8% at level 1
        "damage_base": 8.0,
        "damage_per_level": 2.0,
    },
}

# On-equip scaling - CORRECTED based on user feedback
# Bowmaster (4th): 20% at lv1, 26% at lv4 → base=20, per_level=2
# Format: {stat_type: {advancement: (base_at_lv1, per_level)}}
ON_EQUIP_VALUES = {
    OnEquipStatType.FLAT_ATTACK: {
        # Basic tier - flat attack
        # Aspiring Warrior Lv 100: 654 on-equip attack → 6.54 per level
        JobAdvancement.BASIC: (6.54, 6.54),  # 654 / 100 = 6.54 per level (base + per_level*99)
        # 1st Job - flat attack (Hero 1st Lv 50: 1180 attack → 23.6 per level)
        JobAdvancement.FIRST: (23.6, 23.6),  # 1180 / 50 = 23.6 per level
    },
    OnEquipStatType.ATTACK_SPEED: {
        JobAdvancement.SECOND: (10.0, 0.23),  # ~17% at lv30
        JobAdvancement.THIRD: (14.0, 0.3),    # ~17% at lv10
        JobAdvancement.FOURTH: (20.0, 2.0),   # 20% at lv1, 26% at lv4
    },
    OnEquipStatType.MIN_DMG_MULT: {
        JobAdvancement.SECOND: (10.0, 0.23),
        JobAdvancement.THIRD: (14.0, 0.4),
        JobAdvancement.FOURTH: (20.0, 2.0),   # 24-26% range at low levels
    },
    OnEquipStatType.MAX_DMG_MULT: {
        # Hero (2nd) Lv 26: 17.5% → base + 25*per_level = 17.5
        # Assuming base ~5%, per_level = 0.5: 5 + 25*0.5 = 17.5 ✓
        JobAdvancement.SECOND: (5.0, 0.5),
        JobAdvancement.THIRD: (12.0, 0.35),
        JobAdvancement.FOURTH: (18.0, 1.5),   # ~20% at lv1
    },
    OnEquipStatType.BOSS_DAMAGE: {
        JobAdvancement.SECOND: (10.0, 0.23),
        JobAdvancement.THIRD: (14.0, 0.4),
        JobAdvancement.FOURTH: (20.0, 1.5),   # 22-24% range
    },
    OnEquipStatType.NORMAL_DAMAGE: {
        JobAdvancement.SECOND: (10.0, 0.23),
        JobAdvancement.THIRD: (15.0, 0.4),
        JobAdvancement.FOURTH: (18.0, 1.5),   # ~20% at lv1
    },
    OnEquipStatType.CRIT_RATE: {
        JobAdvancement.SECOND: (5.0, 0.1),
        JobAdvancement.THIRD: (7.0, 0.2),
        JobAdvancement.FOURTH: (11.0, 1.1),   # 13.2% at lv2
    },
    OnEquipStatType.STATUS_EFFECT_DMG: {
        JobAdvancement.SECOND: (15.0, 0.5),
        JobAdvancement.THIRD: (20.0, 0.6),    # 25.6% at lv10
        JobAdvancement.FOURTH: (30.0, 2.0),   # 38.4% estimate
    },
    OnEquipStatType.ACCURACY: {
        # Dark Knight (2nd) Lv 27: 21 accuracy → base + 26*per_level = 21
        # Assuming base ~8, per_level = 0.5: 8 + 26*0.5 = 21 ✓
        JobAdvancement.SECOND: (8.0, 0.5),
        JobAdvancement.THIRD: (12.0, 0.6),    # ~18 at lv10
        JobAdvancement.FOURTH: (16.0, 1.0),
    },
}

# Display names
ON_EQUIP_DISPLAY = {
    OnEquipStatType.FLAT_ATTACK: "Flat Attack",
    OnEquipStatType.ATTACK_SPEED: "Attack Speed %",
    OnEquipStatType.MIN_DMG_MULT: "Min Dmg Mult %",
    OnEquipStatType.MAX_DMG_MULT: "Max Dmg Mult %",
    OnEquipStatType.BOSS_DAMAGE: "Boss Damage %",
    OnEquipStatType.NORMAL_DAMAGE: "Normal Damage %",
    OnEquipStatType.CRIT_RATE: "Crit Rate %",
    OnEquipStatType.STATUS_EFFECT_DMG: "Status Effect Dmg %",
    OnEquipStatType.ACCURACY: "Accuracy",
}

TIER_DISPLAY = {
    JobAdvancement.BASIC: "Basic",
    JobAdvancement.FIRST: "1st Job",
    JobAdvancement.SECOND: "2nd Job",
    JobAdvancement.THIRD: "3rd Job",
    JobAdvancement.FOURTH: "4th Job",
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CompanionDefinition:
    """Definition of a companion type."""
    name: str
    job: CompanionJob
    advancement: JobAdvancement
    on_equip_type: OnEquipStatType

    @property
    def max_level(self) -> int:
        """Get max level for this companion."""
        return MAX_LEVELS.get(self.advancement, 10)

    def get_on_equip_value(self, level: int) -> float:
        """Get on-equip effect value at given level."""
        level = max(1, min(level, self.max_level))

        values = ON_EQUIP_VALUES.get(self.on_equip_type, {})
        base, per_level = values.get(self.advancement, (10.0, 0.5))

        return base + (level - 1) * per_level

    def get_inventory_stats(self, level: int) -> Dict[str, float]:
        """Get inventory effect stats at given level.

        Returns stats using standardized stat names from stat_names.py:
        - attack_flat: Flat attack bonus
        - main_stat_flat: Flat main stat (resolved by job class)
        - damage_pct: Damage percentage
        - max_hp: Max HP
        """
        level = max(0, min(level, self.max_level))
        if level == 0:
            return {}

        stats = {}

        if self.advancement == JobAdvancement.BASIC:
            # Basic gives Attack + Max HP
            scaling = INVENTORY_SCALING[JobAdvancement.BASIC]
            stats["attack_flat"] = level * scaling["attack_per_level"]
            stats["max_hp"] = level * scaling["max_hp_per_level"]

        elif self.advancement == JobAdvancement.FIRST:
            # 1st job gives Attack + Max HP
            scaling = INVENTORY_SCALING[JobAdvancement.FIRST]
            stats["attack_flat"] = level * scaling["attack_per_level"]
            stats["max_hp"] = level * scaling["max_hp_per_level"]

        elif self.advancement == JobAdvancement.SECOND:
            # 2nd job gives Main Stat + Max HP (confirmed from screenshots)
            scaling = INVENTORY_SCALING[JobAdvancement.SECOND]
            stats["main_stat_flat"] = level * scaling["main_stat_per_level"]
            stats["max_hp"] = level * scaling["max_hp_per_level"]

        elif self.advancement == JobAdvancement.THIRD:
            # 3rd job gives generic Damage % (NOT their on-equip stat type)
            scaling = INVENTORY_SCALING[JobAdvancement.THIRD]
            stats["damage_pct"] = scaling["damage_base"] + (level - 1) * scaling["damage_per_level"]

        elif self.advancement == JobAdvancement.FOURTH:
            # 4th job gives generic Damage % (NOT their on-equip stat type)
            scaling = INVENTORY_SCALING[JobAdvancement.FOURTH]
            stats["damage_pct"] = scaling["damage_base"] + (level - 1) * scaling["damage_per_level"]

        return stats


@dataclass
class CompanionInstance:
    """An owned companion with specific level."""
    definition: CompanionDefinition
    level: int = 1

    def __post_init__(self):
        self.level = max(0, min(self.level, self.definition.max_level))

    def get_on_equip_value(self) -> float:
        """Get on-equip effect value."""
        if self.level == 0:
            return 0
        return self.definition.get_on_equip_value(self.level)

    def get_inventory_stats(self) -> Dict[str, float]:
        """Get inventory effect stats."""
        return self.definition.get_inventory_stats(self.level)


@dataclass
class CompanionConfig:
    """Player's companion configuration."""
    # Equipped companions (7 slots: 1 main + 6 sub)
    equipped: List[Optional[CompanionInstance]] = field(default_factory=lambda: [None] * 7)
    # All owned companions (for inventory effects)
    inventory: List[CompanionInstance] = field(default_factory=list)

    def get_on_equip_stats(self) -> Dict[str, float]:
        """Get total on-equip stats from equipped companions."""
        stats = {}

        for companion in self.equipped:
            if companion is not None and companion.level > 0:
                stat_type = companion.definition.on_equip_type.value
                value = companion.get_on_equip_value()
                stats[stat_type] = stats.get(stat_type, 0) + value

        return stats

    def get_inventory_stats(self) -> Dict[str, float]:
        """Get total inventory stats from ALL owned companions."""
        stats = {
            "attack": 0,
            "main_stat": 0,
            "max_hp": 0,
            "damage": 0,  # Generic damage % from 3rd/4th job
        }

        for companion in self.inventory:
            if companion.level > 0:
                inv_stats = companion.get_inventory_stats()
                for key, value in inv_stats.items():
                    if key in stats:
                        stats[key] = stats.get(key, 0) + value

        return stats

    def get_all_stats(self) -> Dict[str, float]:
        """Get all companion stats combined for damage calculation."""
        stats = {}

        # Add on-equip stats (converted to damage calc keys)
        on_equip = self.get_on_equip_stats()
        stats["on_equip_flat_attack"] = on_equip.get("flat_attack", 0)
        stats["on_equip_attack_speed"] = on_equip.get("attack_speed", 0)
        stats["on_equip_min_dmg_mult"] = on_equip.get("min_dmg_mult", 0)
        stats["on_equip_max_dmg_mult"] = on_equip.get("max_dmg_mult", 0)
        stats["on_equip_boss_damage"] = on_equip.get("boss_damage", 0)
        stats["on_equip_normal_damage"] = on_equip.get("normal_damage", 0)
        stats["on_equip_crit_rate"] = on_equip.get("crit_rate", 0)

        # Add inventory stats
        inventory = self.get_inventory_stats()
        stats["inv_attack"] = inventory.get("attack", 0)
        stats["inv_main_stat"] = inventory.get("main_stat", 0)
        stats["inv_max_hp"] = inventory.get("max_hp", 0)
        stats["inv_damage"] = inventory.get("damage", 0)  # Generic Damage % from 3rd/4th

        # Combined totals for damage calc compatibility
        stats["attack_speed"] = stats["on_equip_attack_speed"]
        stats["min_dmg_mult"] = stats["on_equip_min_dmg_mult"]
        stats["max_dmg_mult"] = stats["on_equip_max_dmg_mult"]
        stats["boss_damage"] = stats["on_equip_boss_damage"]
        stats["normal_damage"] = stats["on_equip_normal_damage"]
        stats["crit_rate"] = stats["on_equip_crit_rate"]

        # For backward compatibility with damage calc
        stats["flat_main_stat"] = stats["inv_main_stat"]
        stats["flat_attack"] = stats["inv_attack"] + stats["on_equip_flat_attack"]
        stats["damage"] = stats["inv_damage"]  # Generic Damage % from inventory

        return stats

    def get_attack_speed_sources(self) -> List[Tuple[str, float]]:
        """
        Get list of individual attack speed sources from equipped companions.

        Returns a list of (source_name, value) tuples for each equipped companion
        that provides attack speed. This is needed because attack speed uses
        a diminishing returns formula rather than simple addition.

        Formula: atk_spd += (150 - atk_spd) * (source / 100)
        Each source is applied against the remaining gap to the 150% cap.
        """
        sources = []

        for i, companion in enumerate(self.equipped):
            if companion is not None and companion.level > 0:
                if companion.definition.on_equip_type == OnEquipStatType.ATTACK_SPEED:
                    value = companion.get_on_equip_value()
                    slot_name = "Main" if i == 0 else f"Sub {i}"
                    source_name = f"{companion.definition.name} ({slot_name})"
                    sources.append((source_name, value))

        return sources

    def get_inventory_stats_total(self) -> Dict[str, float]:
        """Get total inventory stats from all owned companions.

        Returns aggregated stats using standardized names:
        - attack_flat: Total flat attack
        - main_stat_flat: Total flat main stat (resolved by job class)
        - damage_pct: Total damage percentage
        - max_hp: Total max HP
        """
        totals: Dict[str, float] = {}

        for companion in self.inventory:
            if companion.level == 0:
                continue

            inv_stats = companion.get_inventory_stats()
            for stat_key, value in inv_stats.items():
                totals[stat_key] = totals.get(stat_key, 0.0) + value

        return totals

    def to_dict(self) -> Dict:
        """Serialize to dict for saving."""
        def companion_to_dict(c: Optional[CompanionInstance]) -> Optional[Dict]:
            if c is None:
                return None
            return {
                "key": get_companion_key(c.definition),
                "level": c.level,
            }

        return {
            "equipped": [companion_to_dict(c) for c in self.equipped],
            "inventory": [companion_to_dict(c) for c in self.inventory],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CompanionConfig":
        """Deserialize from dict."""
        config = cls()

        # Load equipped
        for i, eq_data in enumerate(data.get("equipped", [])):
            if eq_data and i < len(config.equipped):
                key = eq_data.get("key")
                level = eq_data.get("level", 1)
                if key in COMPANIONS:
                    config.equipped[i] = CompanionInstance(
                        definition=COMPANIONS[key],
                        level=level
                    )

        # Load inventory
        for inv_data in data.get("inventory", []):
            if inv_data:
                key = inv_data.get("key")
                level = inv_data.get("level", 1)
                if key in COMPANIONS:
                    config.inventory.append(CompanionInstance(
                        definition=COMPANIONS[key],
                        level=level
                    ))

        return config

    def get_stats(self, job_class=None):
        """
        Get all companion stats as a StatBlock.

        Note: Attack speed is NOT included here because it uses diminishing returns
        and needs special handling. Use get_attack_speed_sources() for attack speed.

        Args:
            job_class: Job class for main_stat mapping (defaults to Bowmaster)

        Returns:
            StatBlock with all companion stats
        """
        from stats import create_stat_block_for_job
        from job_classes import JobClass

        if job_class is None:
            job_class = JobClass.BOWMASTER

        all_stats = self.get_all_stats()

        return create_stat_block_for_job(
            job_class=job_class,
            main_stat_flat=all_stats.get('flat_main_stat', 0),
            attack_flat=all_stats.get('flat_attack', 0),
            damage_pct=all_stats.get('damage', 0),
            boss_damage=all_stats.get('boss_damage', 0),
            normal_damage=all_stats.get('normal_damage', 0),
            crit_rate=all_stats.get('crit_rate', 0),
            min_dmg_mult=all_stats.get('min_dmg_mult', 0),
            max_dmg_mult=all_stats.get('max_dmg_mult', 0),
            max_hp=all_stats.get('inv_max_hp', 0),
            # Note: attack_speed excluded - needs special handling
        )


# =============================================================================
# COMPANION DEFINITIONS
# =============================================================================

COMPANIONS = {
    # Basic Tier (Grey, max level 100, 4 companions)
    "aspiring_warrior": CompanionDefinition(
        name="Aspiring Warrior",
        job=CompanionJob.BASIC,
        advancement=JobAdvancement.BASIC,
        on_equip_type=OnEquipStatType.FLAT_ATTACK,
    ),
    "aspiring_mage": CompanionDefinition(
        name="Aspiring Mage",
        job=CompanionJob.BASIC,
        advancement=JobAdvancement.BASIC,
        on_equip_type=OnEquipStatType.FLAT_ATTACK,
    ),
    "aspiring_bowman": CompanionDefinition(
        name="Aspiring Bowman",
        job=CompanionJob.BASIC,
        advancement=JobAdvancement.BASIC,
        on_equip_type=OnEquipStatType.FLAT_ATTACK,
    ),
    "aspiring_thief": CompanionDefinition(
        name="Aspiring Thief",
        job=CompanionJob.BASIC,
        advancement=JobAdvancement.BASIC,
        on_equip_type=OnEquipStatType.FLAT_ATTACK,
    ),

    # 4th Job Companions (max level 10)
    "bowmaster_4th": CompanionDefinition(
        name="Bowmaster (4th)",
        job=CompanionJob.BOWMASTER,
        advancement=JobAdvancement.FOURTH,
        on_equip_type=OnEquipStatType.ATTACK_SPEED,
    ),
    "marksman_4th": CompanionDefinition(
        name="Marksman (4th)",
        job=CompanionJob.MARKSMAN,
        advancement=JobAdvancement.FOURTH,
        on_equip_type=OnEquipStatType.STATUS_EFFECT_DMG,
    ),
    "night_lord_4th": CompanionDefinition(
        name="Night Lord (4th)",
        job=CompanionJob.NIGHT_LORD,
        advancement=JobAdvancement.FOURTH,
        on_equip_type=OnEquipStatType.BOSS_DAMAGE,
    ),
    "shadower_4th": CompanionDefinition(
        name="Shadower (4th)",
        job=CompanionJob.SHADOWER,
        advancement=JobAdvancement.FOURTH,
        on_equip_type=OnEquipStatType.MIN_DMG_MULT,
    ),
    "hero_4th": CompanionDefinition(
        name="Hero (4th)",
        job=CompanionJob.HERO,
        advancement=JobAdvancement.FOURTH,
        on_equip_type=OnEquipStatType.MAX_DMG_MULT,
    ),
    "dark_knight_4th": CompanionDefinition(
        name="Dark Knight (4th)",
        job=CompanionJob.DARK_KNIGHT,
        advancement=JobAdvancement.FOURTH,
        on_equip_type=OnEquipStatType.BOSS_DAMAGE,
    ),
    "arch_mage_fp_4th": CompanionDefinition(
        name="Arch Mage F/P (4th)",
        job=CompanionJob.ARCH_MAGE_FP,
        advancement=JobAdvancement.FOURTH,
        on_equip_type=OnEquipStatType.CRIT_RATE,
    ),
    "arch_mage_il_4th": CompanionDefinition(
        name="Arch Mage I/L (4th)",
        job=CompanionJob.ARCH_MAGE_IL,
        advancement=JobAdvancement.FOURTH,
        on_equip_type=OnEquipStatType.NORMAL_DAMAGE,
    ),

    # 3rd Job Companions (max level 10)
    "bowmaster_3rd": CompanionDefinition(
        name="Bowmaster (3rd)",
        job=CompanionJob.BOWMASTER,
        advancement=JobAdvancement.THIRD,
        on_equip_type=OnEquipStatType.ATTACK_SPEED,
    ),
    "marksman_3rd": CompanionDefinition(
        name="Marksman (3rd)",
        job=CompanionJob.MARKSMAN,
        advancement=JobAdvancement.THIRD,
        on_equip_type=OnEquipStatType.STATUS_EFFECT_DMG,
    ),
    "night_lord_3rd": CompanionDefinition(
        name="Night Lord (3rd)",
        job=CompanionJob.NIGHT_LORD,
        advancement=JobAdvancement.THIRD,
        on_equip_type=OnEquipStatType.BOSS_DAMAGE,
    ),
    "shadower_3rd": CompanionDefinition(
        name="Shadower (3rd)",
        job=CompanionJob.SHADOWER,
        advancement=JobAdvancement.THIRD,
        on_equip_type=OnEquipStatType.MIN_DMG_MULT,
    ),
    "hero_3rd": CompanionDefinition(
        name="Hero (3rd)",
        job=CompanionJob.HERO,
        advancement=JobAdvancement.THIRD,
        on_equip_type=OnEquipStatType.MAX_DMG_MULT,
    ),
    "dark_knight_3rd": CompanionDefinition(
        name="Dark Knight (3rd)",
        job=CompanionJob.DARK_KNIGHT,
        advancement=JobAdvancement.THIRD,
        on_equip_type=OnEquipStatType.ACCURACY,
    ),
    "arch_mage_fp_3rd": CompanionDefinition(
        name="Arch Mage F/P (3rd)",
        job=CompanionJob.ARCH_MAGE_FP,
        advancement=JobAdvancement.THIRD,
        on_equip_type=OnEquipStatType.CRIT_RATE,
    ),
    "arch_mage_il_3rd": CompanionDefinition(
        name="Arch Mage I/L (3rd)",
        job=CompanionJob.ARCH_MAGE_IL,
        advancement=JobAdvancement.THIRD,
        on_equip_type=OnEquipStatType.NORMAL_DAMAGE,
    ),

    # 2nd Job Companions (max level 30)
    "bowmaster_2nd": CompanionDefinition(
        name="Bowmaster (2nd)",
        job=CompanionJob.BOWMASTER,
        advancement=JobAdvancement.SECOND,
        on_equip_type=OnEquipStatType.ATTACK_SPEED,
    ),
    "marksman_2nd": CompanionDefinition(
        name="Marksman (2nd)",
        job=CompanionJob.MARKSMAN,
        advancement=JobAdvancement.SECOND,
        on_equip_type=OnEquipStatType.STATUS_EFFECT_DMG,
    ),
    "night_lord_2nd": CompanionDefinition(
        name="Night Lord (2nd)",
        job=CompanionJob.NIGHT_LORD,
        advancement=JobAdvancement.SECOND,
        on_equip_type=OnEquipStatType.BOSS_DAMAGE,
    ),
    "shadower_2nd": CompanionDefinition(
        name="Shadower (2nd)",
        job=CompanionJob.SHADOWER,
        advancement=JobAdvancement.SECOND,
        on_equip_type=OnEquipStatType.MIN_DMG_MULT,
    ),
    "hero_2nd": CompanionDefinition(
        name="Hero (2nd)",
        job=CompanionJob.HERO,
        advancement=JobAdvancement.SECOND,
        on_equip_type=OnEquipStatType.MAX_DMG_MULT,
    ),
    "dark_knight_2nd": CompanionDefinition(
        name="Dark Knight (2nd)",
        job=CompanionJob.DARK_KNIGHT,
        advancement=JobAdvancement.SECOND,
        on_equip_type=OnEquipStatType.ACCURACY,
    ),
    "arch_mage_fp_2nd": CompanionDefinition(
        name="Arch Mage F/P (2nd)",
        job=CompanionJob.ARCH_MAGE_FP,
        advancement=JobAdvancement.SECOND,
        on_equip_type=OnEquipStatType.CRIT_RATE,
    ),
    "arch_mage_il_2nd": CompanionDefinition(
        name="Arch Mage I/L (2nd)",
        job=CompanionJob.ARCH_MAGE_IL,
        advancement=JobAdvancement.SECOND,
        on_equip_type=OnEquipStatType.NORMAL_DAMAGE,
    ),

    # 1st Job Companions (max level 50) - ALL give flat attack as on-equip
    "bowmaster_1st": CompanionDefinition(
        name="Bowmaster (1st)",
        job=CompanionJob.BOWMASTER,
        advancement=JobAdvancement.FIRST,
        on_equip_type=OnEquipStatType.FLAT_ATTACK,
    ),
    "marksman_1st": CompanionDefinition(
        name="Marksman (1st)",
        job=CompanionJob.MARKSMAN,
        advancement=JobAdvancement.FIRST,
        on_equip_type=OnEquipStatType.FLAT_ATTACK,
    ),
    "night_lord_1st": CompanionDefinition(
        name="Night Lord (1st)",
        job=CompanionJob.NIGHT_LORD,
        advancement=JobAdvancement.FIRST,
        on_equip_type=OnEquipStatType.FLAT_ATTACK,
    ),
    "shadower_1st": CompanionDefinition(
        name="Shadower (1st)",
        job=CompanionJob.SHADOWER,
        advancement=JobAdvancement.FIRST,
        on_equip_type=OnEquipStatType.FLAT_ATTACK,
    ),
    "hero_1st": CompanionDefinition(
        name="Hero (1st)",
        job=CompanionJob.HERO,
        advancement=JobAdvancement.FIRST,
        on_equip_type=OnEquipStatType.FLAT_ATTACK,
    ),
    "dark_knight_1st": CompanionDefinition(
        name="Dark Knight (1st)",
        job=CompanionJob.DARK_KNIGHT,
        advancement=JobAdvancement.FIRST,
        on_equip_type=OnEquipStatType.FLAT_ATTACK,
    ),
    "arch_mage_fp_1st": CompanionDefinition(
        name="Arch Mage F/P (1st)",
        job=CompanionJob.ARCH_MAGE_FP,
        advancement=JobAdvancement.FIRST,
        on_equip_type=OnEquipStatType.FLAT_ATTACK,
    ),
    "arch_mage_il_1st": CompanionDefinition(
        name="Arch Mage I/L (1st)",
        job=CompanionJob.ARCH_MAGE_IL,
        advancement=JobAdvancement.FIRST,
        on_equip_type=OnEquipStatType.FLAT_ATTACK,
    ),
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_companion_key(definition: CompanionDefinition) -> Optional[str]:
    """Get the key for a companion definition."""
    for key, defn in COMPANIONS.items():
        if defn == definition:
            return key
    return None


def create_companion_instance(
    companion_key: str,
    level: int = 1,
) -> Optional[CompanionInstance]:
    """Create a companion instance from definition key."""
    if companion_key not in COMPANIONS:
        return None

    definition = COMPANIONS[companion_key]
    return CompanionInstance(
        definition=definition,
        level=min(level, definition.max_level),
    )


def get_companion_by_job_advancement(
    job: CompanionJob,
    advancement: JobAdvancement
) -> Optional[CompanionDefinition]:
    """Get companion definition by job and advancement."""
    for key, companion in COMPANIONS.items():
        if companion.job == job and companion.advancement == advancement:
            return companion
    return None


def get_companions_by_advancement(advancement: JobAdvancement) -> Dict[str, CompanionDefinition]:
    """Get all companions of a specific advancement tier."""
    return {
        key: companion
        for key, companion in COMPANIONS.items()
        if companion.advancement == advancement
    }


def create_full_companion_inventory(levels: Dict[str, int] = None) -> List[CompanionInstance]:
    """
    Create a full inventory with all companions at specified levels.
    levels: dict mapping companion_key to level, defaults to 0 for unspecified (not owned)
    """
    if levels is None:
        levels = {}

    inventory = []
    for key, definition in COMPANIONS.items():
        level = levels.get(key, 0)
        if level > 0:  # Only add if level > 0 (0 means not owned)
            inventory.append(CompanionInstance(definition=definition, level=level))

    return inventory


# =============================================================================
# MAIN (Testing)
# =============================================================================

if __name__ == "__main__":
    print("MapleStory Idle - Companion System Module")
    print("=" * 60)

    # Test tier structure
    print("\nTier Structure:")
    for adv in JobAdvancement:
        count = len(get_companions_by_advancement(adv))
        max_lv = MAX_LEVELS[adv]
        print(f"  {TIER_DISPLAY[adv]}: {count} companions, max level {max_lv}")

    # Test on-equip scaling - Bowmaster (4th) at Lv1 and Lv4
    print("\nOn-Equip Validation (Bowmaster 4th - Attack Speed):")
    bm4 = COMPANIONS["bowmaster_4th"]
    for lv in [1, 2, 3, 4, 5, 10]:
        val = bm4.get_on_equip_value(lv)
        print(f"  Lv{lv}: {val:.1f}%")

    # Test inventory effects
    print("\nInventory Effect Validation:")

    # 3rd job damage % test
    print("\n  3rd Job Damage % (per companion):")
    bm3 = COMPANIONS["bowmaster_3rd"]
    for lv in [1, 4, 7, 10]:
        stats = bm3.get_inventory_stats(lv)
        print(f"    Lv{lv}: {stats.get('damage', 0):.1f}%")

    # 4th job damage % test
    print("\n  4th Job Damage % (per companion):")
    bm4 = COMPANIONS["bowmaster_4th"]
    for lv in [1, 4, 7, 10]:
        stats = bm4.get_inventory_stats(lv)
        print(f"    Lv{lv}: {stats.get('damage', 0):.1f}%")

    # Test with sample levels to estimate target values
    # Target: ~166% Damage from 3rd+4th, ~2658 flat DEX from 2nd
    print("\n" + "=" * 60)
    print("Sample Inventory Test (targeting ~166% Damage, ~2658 Main Stat):")

    # Sample levels based on user data
    levels = {
        # Basic (max 100)
        "aspiring_warrior": 100,
        "aspiring_mage": 100,
        "aspiring_bowman": 100,
        "aspiring_thief": 100,

        # 1st Job (max 50)
        "hero_1st": 50,
        "bowmaster_1st": 50,
        "marksman_1st": 50,
        "night_lord_1st": 50,
        "shadower_1st": 50,
        "dark_knight_1st": 50,
        "arch_mage_fp_1st": 50,
        "arch_mage_il_1st": 50,

        # 2nd Job (max 30) - targeting ~2658 total main stat / 8 companions / 19.5 per level = ~17 avg
        "hero_2nd": 26,
        "bowmaster_2nd": 26,
        "marksman_2nd": 26,
        "night_lord_2nd": 26,
        "shadower_2nd": 2,
        "dark_knight_2nd": 27,
        "arch_mage_fp_2nd": 1,
        "arch_mage_il_2nd": 0,  # Not owned

        # 3rd Job (max 10)
        "hero_3rd": 7,
        "bowmaster_3rd": 7,
        "marksman_3rd": 7,
        "night_lord_3rd": 7,
        "shadower_3rd": 7,
        "dark_knight_3rd": 7,
        "arch_mage_fp_3rd": 7,
        "arch_mage_il_3rd": 8,

        # 4th Job (max 10)
        "hero_4th": 1,
        "bowmaster_4th": 4,
        "marksman_4th": 3,
        "night_lord_4th": 3,
        "shadower_4th": 3,
        "dark_knight_4th": 0,
        "arch_mage_fp_4th": 2,
        "arch_mage_il_4th": 1,
    }

    inventory = create_full_companion_inventory(levels)
    config = CompanionConfig()
    config.inventory = inventory

    summary = config.get_inventory_summary()
    print(f"\nBasic ({summary['basic_count']}): Attack {summary['basic_attack']:.0f}, Max HP {summary['basic_max_hp']:.0f}")
    print(f"1st Job ({summary['1st_job_count']}): Attack {summary['1st_job_attack']:.0f}, Max HP {summary['1st_job_max_hp']:.0f}")
    print(f"2nd Job ({summary['2nd_job_count']}): Main Stat {summary['2nd_job_main_stat']:.0f}")
    print(f"3rd Job ({summary['3rd_job_count']}): Damage {summary['3rd_job_damage']:.1f}%")
    print(f"4th Job ({summary['4th_job_count']}): Damage {summary['4th_job_damage']:.1f}%")
    print(f"\nTotal Attack: {summary.get('total_attack', 0):.0f}")
    print(f"Total Damage %: {summary['total_damage']:.1f}%")
