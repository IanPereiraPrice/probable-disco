"""
MapleStory Idle - Equipment & Starforce System
===============================================
Complete equipment stat calculations, starforce enhancement,
and potential system mechanics.

Last Updated: December 2025
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class Rarity(Enum):
    """Equipment rarity tiers from lowest to highest."""
    EPIC = "epic"
    UNIQUE = "unique"
    LEGENDARY = "legendary"
    MYSTIC = "mystic"
    ANCIENT = "ancient"


class EquipmentSlot(Enum):
    """All equipment slots."""
    WEAPON = "weapon"
    HAT = "hat"
    TOP = "top"
    BOTTOM = "bottom"
    GLOVES = "gloves"
    SHOES = "shoes"
    BELT = "belt"
    SHOULDER = "shoulder"
    CAPE = "cape"
    RING = "ring"
    NECKLACE = "necklace"
    FACE = "face"


# =============================================================================
# SLOT-BASED STAT RULES
# =============================================================================

# Third main stat for each slot (first two are always Attack, Max HP)
SLOT_THIRD_MAIN_STAT: Dict[str, str] = {
    "weapon": "main_stat",
    "hat": "defense",
    "top": "defense",
    "bottom": "accuracy",
    "gloves": "accuracy",
    "shoes": "max_mp",
    "belt": "max_mp",
    "shoulder": "evasion",
    "cape": "evasion",
    "ring": "main_stat",
    "necklace": "main_stat",
    "face": "main_stat",
}

# Default on-equip sub-stats available for all equipment
# These use Sub Amplify from starforce
DEFAULT_SUB_STATS = [
    "boss_damage",
    "normal_damage",
    "crit_rate",
    "crit_damage",
    "attack_flat",      # Flat attack bonus
    "first_job",        # Job-specific skill bonuses available on any item
    "second_job",
    "third_job",
    "fourth_job",
]

# Sub-stats that only appear on special items (is_special=True)
SPECIAL_SUB_STATS = [
    "damage_pct",       # Damage %
    "all_skills",       # +All Skills
    "final_damage",     # Final Damage %
]

# Slots that can have Damage % as default (not just on special items)
DAMAGE_PCT_SLOTS = ["ring", "necklace", "face"]


# =============================================================================
# STARFORCE DATA (VERIFIED)
# =============================================================================

@dataclass
class StarforceStage:
    """Data for a single starforce enhancement stage."""
    stage: int
    success_rate: float
    maintain_rate: float
    decrease_rate: float
    destroy_rate: float
    main_amplify_before: float
    main_amplify_after: float
    sub_amplify_before: Optional[float]
    sub_amplify_after: Optional[float]
    stones: int
    meso: int


# Complete starforce table (verified from in-game screenshots December 2025)
# Format: stage, success, maintain, decrease, destroy, main_amp_before, main_amp_after, sub_amp_before, sub_amp_after, stones, meso
STARFORCE_TABLE: Dict[int, StarforceStage] = {
    # Safe Zone (0-12): No decrease or destruction
    0: StarforceStage(0, 1.00, 0.00, 0.00, 0.00, 0.00, 0.10, None, None, 1, 30000),
    1: StarforceStage(1, 1.00, 0.00, 0.00, 0.00, 0.10, 0.20, None, None, 1, 30000),
    2: StarforceStage(2, 0.90, 0.10, 0.00, 0.00, 0.20, 0.30, None, None, 2, 40000),
    3: StarforceStage(3, 0.85, 0.15, 0.00, 0.00, 0.30, 0.40, None, None, 3, 50000),
    4: StarforceStage(4, 0.80, 0.20, 0.00, 0.00, 0.40, 0.60, 0.00, 0.10, 4, 60000),
    5: StarforceStage(5, 0.70, 0.30, 0.00, 0.00, 0.60, 0.75, 0.10, 0.10, 5, 70000),
    6: StarforceStage(6, 0.65, 0.35, 0.00, 0.00, 0.75, 0.90, 0.10, 0.10, 6, 90000),
    7: StarforceStage(7, 0.60, 0.40, 0.00, 0.00, 0.90, 1.05, 0.10, 0.10, 7, 110000),
    8: StarforceStage(8, 0.55, 0.45, 0.00, 0.00, 1.05, 1.20, 0.10, 0.10, 8, 130000),
    9: StarforceStage(9, 0.50, 0.50, 0.00, 0.00, 1.20, 1.50, 0.10, 0.25, 9, 150000),
    10: StarforceStage(10, 0.35, 0.65, 0.00, 0.00, 1.50, 1.75, 0.25, 0.25, 10, 170000),
    11: StarforceStage(11, 0.34, 0.66, 0.00, 0.00, 1.75, 2.00, 0.25, 0.25, 11, 190000),
    12: StarforceStage(12, 0.33, 0.67, 0.00, 0.00, 2.00, 2.25, 0.25, 0.25, 12, 210000),
    # Decrease Zone (13-14): 12% decrease chance, no destruction
    13: StarforceStage(13, 0.32, 0.56, 0.12, 0.00, 2.25, 2.50, 0.25, 0.25, 13, 230000),
    14: StarforceStage(14, 0.31, 0.57, 0.12, 0.00, 2.50, 3.00, 0.25, 0.50, 14, 250000),
    # Destruction Zone (15+): Destruction chance starts
    15: StarforceStage(15, 0.30, 0.67, 0.00, 0.03, 3.00, 3.50, 0.50, 0.60, 15, 270000),
    16: StarforceStage(16, 0.275, 0.53, 0.15, 0.045, 3.50, 4.00, 0.60, 0.70, 16, 300000),
    17: StarforceStage(17, 0.25, 0.54, 0.15, 0.06, 4.00, 4.50, 0.70, 0.80, 17, 330000),
    18: StarforceStage(18, 0.225, 0.55, 0.15, 0.075, 4.50, 5.00, 0.80, 0.90, 18, 360000),
    19: StarforceStage(19, 0.20, 0.56, 0.15, 0.09, 5.00, 6.00, 0.90, 1.00, 19, 390000),
    # High Stars (20+): Major amplify jumps, 10%+ destruction
    20: StarforceStage(20, 0.14, 0.75, 0.00, 0.11, 6.00, 7.00, 1.00, 1.10, 20, 420000),
    21: StarforceStage(21, 0.10, 0.70, 0.10, 0.10, 7.00, 9.00, 1.10, 1.30, 25, 470000),
    22: StarforceStage(22, 0.08, 0.72, 0.10, 0.10, 9.00, 12.00, 1.30, 1.60, 30, 520000),
    23: StarforceStage(23, 0.06, 0.74, 0.10, 0.10, 12.00, 15.00, 1.60, 2.00, 35, 570000),
    24: StarforceStage(24, 0.04, 0.76, 0.10, 0.10, 15.00, 20.00, 2.00, 2.50, 40, 620000),
}


def get_amplify_multiplier(stars: int, is_sub: bool = False) -> float:
    """
    Get the stat multiplier for a given star count.

    Args:
        stars: Current star count (0-25)
        is_sub: True for sub stats, False for main stats

    Returns:
        Multiplier (e.g., 4.50 for ★16 main stats = 350% amplify)
    """
    if stars < 0:
        return 1.0

    # Find the stage data - look for the stage BEFORE current stars
    # e.g., at ★16, we use stage 15's "after" value which equals 350%
    if stars > 0 and (stars - 1) in STARFORCE_TABLE:
        stage = STARFORCE_TABLE[stars - 1]
        amplify = stage.sub_amplify_after if is_sub else stage.main_amplify_after
        if amplify is not None:
            return 1 + amplify

    # For ★0, no amplify
    if stars == 0:
        return 1.0

    # For ★25 (completed 24→25), use stage 24's after value
    if stars >= 25:
        return 1 + (20.00 if not is_sub else 2.50)  # ★25 = 2000% main, 250% sub

    # Fallback for any edge cases
    return 1.0


def calculate_base_stat(total_stat: float, stars: int, is_sub: bool = False) -> float:
    """
    Calculate base stat from total stat after starforce.
    
    Formula (VERIFIED):
        Base Stat = Total Stat ÷ (1 + Amplify%)
    
    Args:
        total_stat: The displayed stat value
        stars: Current star count
        is_sub: True for sub stats (Damage %, etc.)
    
    Returns:
        Base stat before starforce
    """
    multiplier = get_amplify_multiplier(stars, is_sub)
    return total_stat / multiplier


def calculate_starforce_expected_cost(
    current_stars: int,
    target_stars: int,
    use_decrease_protection: bool = False,
    use_destroy_protection: bool = False
) -> Tuple[int, int, float]:
    """
    Calculate expected cost to enhance from current to target stars.
    
    Args:
        current_stars: Starting star count
        target_stars: Target star count
        use_decrease_protection: Use decrease mitigation (2x cost)
        use_destroy_protection: Use destruction mitigation (2x cost)
    
    Returns:
        Tuple of (expected_meso, expected_stones, expected_attempts)
    """
    if target_stars <= current_stars:
        return (0, 0, 0.0)
    
    total_meso = 0
    total_stones = 0
    total_attempts = 0.0
    
    star = current_stars
    while star < target_stars:
        if star not in STARFORCE_TABLE:
            break
            
        stage = STARFORCE_TABLE[star]
        
        # Calculate effective success rate considering failures
        success = stage.success_rate
        decrease = 0 if use_decrease_protection else stage.decrease_rate
        destroy = stage.destroy_rate * (0.5 if use_destroy_protection else 1.0)
        
        # Expected attempts to get +1 star (simplified model)
        # This doesn't account for star regression fully
        expected_attempts_this_stage = 1 / success if success > 0 else float('inf')
        
        # Cost multiplier for protections
        cost_mult = 1.0
        if use_decrease_protection and stage.decrease_rate > 0:
            cost_mult += 1.0
        if use_destroy_protection and stage.destroy_rate > 0:
            cost_mult += 1.0
        
        meso_per_attempt = stage.meso * cost_mult
        stones_per_attempt = stage.stones * cost_mult
        
        total_meso += int(meso_per_attempt * expected_attempts_this_stage)
        total_stones += int(stones_per_attempt * expected_attempts_this_stage)
        total_attempts += expected_attempts_this_stage
        
        star += 1
    
    return (total_meso, total_stones, total_attempts)


# =============================================================================
# EQUIPMENT POTENTIAL SYSTEM
# =============================================================================

@dataclass
class PotentialLine:
    """A single potential line on equipment."""
    stat: str
    value: float
    tier: str  # "yellow" or "grey"
    slot: int  # 1, 2, or 3


# Slot probability distribution (verified)
SLOT_TIER_RATES = {
    1: {"yellow": 1.00, "grey": 0.00},  # 100% current tier
    2: {"yellow": 0.24, "grey": 0.76},  # 24% yellow / 76% grey
    3: {"yellow": 0.08, "grey": 0.92},  # 8% yellow / 92% grey
}

# Tier upgrade probabilities when cubing
TIER_UPGRADE_RATES = {
    "normal_to_rare": 0.06,      # 6%
    "rare_to_epic": 0.0167,      # 1.67%
    "epic_to_unique": 0.006,     # 0.6%
    "unique_to_legendary": 0.0021,  # 0.21%
    "legendary_to_mystic": 0.00083, # 0.083%
}

# Special potential rates
SPECIAL_POTENTIAL_RATE = 0.01  # 1% chance for special line

# Potential stat tables by tier
POTENTIAL_STATS = {
    "normal": {
        "main_stat_pct": {"value": 3, "prob": 0.045},
        "attack": {"value": 30, "prob": 0.045},
        "damage": {"value": 6, "prob": 0.028},
        "crit_rate": {"value": 3, "prob": 0.018},
        "crit_damage": {"value": 3, "prob": 0.018},
    },
    "epic": {
        "main_stat_pct": {"value": 6, "prob": 0.029},
        "attack": {"value": 90, "prob": 0.029},
        "damage": {"value": 12, "prob": 0.018},
        "crit_rate": {"value": 6, "prob": 0.018},
        "crit_damage": {"value": 6, "prob": 0.018},
        "boss_damage": {"value": 12, "prob": 0.012},
    },
    "unique": {
        "main_stat_pct": {"value": 9, "prob": 0.029},
        "attack": {"value": 135, "prob": 0.029},
        "damage": {"value": 18, "prob": 0.018},
        "crit_rate": {"value": 9, "prob": 0.018},
        "crit_damage": {"value": 9, "prob": 0.018},
        "boss_damage": {"value": 18, "prob": 0.012},
        "final_damage": {"value": 3, "prob": 0.01},  # Special
    },
    "legendary": {
        "main_stat_pct": {"value": 12, "prob": 0.022},
        "attack": {"value": 180, "prob": 0.022},
        "damage": {"value": 24, "prob": 0.018},
        "crit_rate": {"value": 12, "prob": 0.018},
        "crit_damage": {"value": 12, "prob": 0.018},
        "boss_damage": {"value": 24, "prob": 0.01},
        "final_damage": {"value": 5, "prob": 0.01},  # Special
    },
    "mystic": {
        "main_stat_pct": {"value": 15, "prob": 0.022},
        "attack": {"value": 225, "prob": 0.022},
        "damage": {"value": 30, "prob": 0.018},
        "crit_rate": {"value": 15, "prob": 0.018},
        "crit_damage": {"value": 15, "prob": 0.018},
        "boss_damage": {"value": 30, "prob": 0.01},
        "final_damage": {"value": 8, "prob": 0.01},  # Special
    },
}

# Special potentials by slot
SPECIAL_POTENTIALS = {
    EquipmentSlot.RING: ["all_skills_1"],
    EquipmentSlot.NECKLACE: ["all_skills_1"],
    EquipmentSlot.GLOVES: ["crit_damage_10"],  # 10.9% CD verified
    EquipmentSlot.SHOULDER: ["def_pen_5"],
    EquipmentSlot.BOTTOM: ["final_damage_8"],  # 8% FD slot 1 seen
}


def calculate_cube_expected_cost(
    target_tier: str,
    target_stat: str,
    slot: int = 1,
    cubes_per_roll: int = 1,
    cube_cost: int = 3000  # Blue diamonds per cube
) -> Tuple[int, float]:
    """
    Calculate expected cubes to hit a target stat.
    
    Args:
        target_tier: Target potential tier
        target_stat: Target stat name
        slot: Which slot to target (1, 2, or 3)
        cubes_per_roll: Cubes used per reroll
        cube_cost: Cost per cube in diamonds
    
    Returns:
        Tuple of (expected_cubes, expected_cost)
    """
    if target_tier not in POTENTIAL_STATS:
        return (0, 0.0)
    
    tier_data = POTENTIAL_STATS[target_tier]
    if target_stat not in tier_data:
        return (0, 0.0)
    
    stat_prob = tier_data[target_stat]["prob"]
    slot_yellow_rate = SLOT_TIER_RATES[slot]["yellow"]
    
    # Probability of hitting target stat on that slot
    hit_prob = stat_prob * slot_yellow_rate
    
    if hit_prob <= 0:
        return (float('inf'), float('inf'))
    
    expected_rolls = 1 / hit_prob
    expected_cubes = expected_rolls * cubes_per_roll
    expected_cost = expected_cubes * cube_cost
    
    return (int(expected_cubes), expected_cost)


# =============================================================================
# EQUIPMENT STATS
# =============================================================================

@dataclass
class EquipmentStats:
    """Stats for a single piece of equipment."""
    slot: EquipmentSlot
    name: str
    tier: int  # 1-4, T1 is best
    rarity: Rarity
    level: int
    stars: int
    
    # Main stats (after starforce)
    attack: int = 0
    max_hp: int = 0
    third_stat: int = 0  # Defense, Accuracy, Max MP, etc.
    main_stat: int = 0   # DEX/STR/INT/LUK
    
    # Sub stats (after starforce)
    sub_attack: int = 0
    sub_damage_pct: float = 0.0  # Only Ring/Necklace/Face/Special
    sub_crit_rate: float = 0.0
    sub_crit_damage: float = 0.0
    sub_boss_damage: float = 0.0
    sub_normal_damage: float = 0.0
    sub_final_damage: float = 0.0  # Special items only
    
    # Potential lines
    potentials: List[PotentialLine] = None
    bonus_potentials: List[PotentialLine] = None
    
    def get_base_attack(self) -> float:
        """Get base attack before starforce."""
        return calculate_base_stat(self.attack, self.stars, is_sub=False)
    
    def get_base_sub_damage(self) -> float:
        """Get base Damage % before starforce."""
        return calculate_base_stat(self.sub_damage_pct, self.stars, is_sub=True)


# Slots that can have Damage % as on-equip effect
DAMAGE_PCT_SLOTS = [
    EquipmentSlot.RING,
    EquipmentSlot.NECKLACE,
    EquipmentSlot.FACE,
    # Plus special helmets like Zakum
]

# Equipment slots to track (excludes weapon)
EQUIPMENT_SLOTS = [
    "hat", "top", "bottom", "gloves", "shoes",
    "belt", "shoulder", "cape", "ring", "necklace", "face"
]


@dataclass
class EquipmentItem:
    """
    Complete equipment item with all stats for tracking and damage calculation.

    Main stats (Attack, Max HP, 3rd stat) use Main Amplify from starforce.
    ALL Sub stats use Sub Amplify from starforce.

    The 3rd main stat varies by slot (Defense/Accuracy/MaxMP/Evasion/MainStat).

    Default sub stats available on all equipment:
    - Boss Damage %, Normal Damage %, Crit Rate %, Crit Damage %, Flat Attack
    - Job-specific skill bonuses (1st-4th Job)

    Special items (is_special=True) can additionally have:
    - Damage %, All Skills, Final Damage %
    """
    slot: str
    name: str = ""
    rarity: str = "unique"  # epic/unique/legendary/mystic
    tier: int = 4           # 1-4, T1 is best
    stars: int = 0          # 0-25
    is_special: bool = False  # Special items have access to Damage %, All Skills, Final Damage %

    # Main stats (before starforce) - use Main Amplify
    base_attack: float = 0.0
    base_max_hp: float = 0.0
    base_third_stat: float = 0.0  # Defense/Accuracy/MaxMP/Evasion/MainStat

    # Default sub stats (before starforce) - ALL use Sub Amplify
    sub_boss_damage: float = 0.0
    sub_normal_damage: float = 0.0
    sub_crit_rate: float = 0.0
    sub_crit_damage: float = 0.0
    sub_attack_flat: float = 0.0  # Flat attack bonus
    sub_skill_first_job: int = 0   # Job-specific skill bonuses (available on any item)
    sub_skill_second_job: int = 0
    sub_skill_third_job: int = 0
    sub_skill_fourth_job: int = 0

    # Special sub stat (only on special items) - uses Sub Amplify
    # Only ONE special stat type can be active per item
    special_stat_type: str = "damage_pct"  # "damage_pct", "all_skills", or "final_damage"
    special_stat_value: float = 0.0        # The value of the special stat

    def get_third_stat_name(self) -> str:
        """Get the name of the 3rd main stat for this slot."""
        return SLOT_THIRD_MAIN_STAT.get(self.slot, "main_stat")

    def get_main_multiplier(self) -> float:
        """Get Main Option Amplify multiplier for current stars."""
        return get_amplify_multiplier(self.stars, is_sub=False)

    def get_sub_multiplier(self) -> float:
        """Get Sub Option Amplify multiplier for current stars."""
        return get_amplify_multiplier(self.stars, is_sub=True)

    def get_all_stats(self) -> Dict[str, float]:
        """
        Get all final stats with starforce amplification applied.
        Main stats use Main Amplify, Sub stats use Sub Amplify.
        """
        main_mult = self.get_main_multiplier()
        sub_mult = self.get_sub_multiplier()

        stats = {
            # Main stats (Main Amplify)
            "attack": round(self.base_attack * main_mult),
            "max_hp": round(self.base_max_hp * main_mult),
            self.get_third_stat_name(): round(self.base_third_stat * main_mult),

            # Default sub stats (Sub Amplify)
            "boss_damage": round(self.sub_boss_damage * sub_mult, 2),
            "normal_damage": round(self.sub_normal_damage * sub_mult, 2),
            "crit_rate": round(self.sub_crit_rate * sub_mult, 2),
            "crit_damage": round(self.sub_crit_damage * sub_mult, 2),
            "attack_flat": round(self.sub_attack_flat * sub_mult),
            "first_job": round(self.sub_skill_first_job * sub_mult),
            "second_job": round(self.sub_skill_second_job * sub_mult),
            "third_job": round(self.sub_skill_third_job * sub_mult),
            "fourth_job": round(self.sub_skill_fourth_job * sub_mult),
        }

        # Add special stat if this is a special item
        if self.is_special and self.special_stat_value > 0:
            if self.special_stat_type == "all_skills":
                stats[self.special_stat_type] = round(self.special_stat_value * sub_mult)
            else:
                stats[self.special_stat_type] = round(self.special_stat_value * sub_mult, 2)

        return stats

    # Legacy getters for backward compatibility
    def get_final_attack(self) -> float:
        return self.base_attack * self.get_main_multiplier()

    def get_final_hp(self) -> float:
        return self.base_max_hp * self.get_main_multiplier()

    def get_final_main_stat(self) -> float:
        """Legacy: returns 3rd stat if it's main_stat, else 0."""
        if self.get_third_stat_name() == "main_stat":
            return self.base_third_stat * self.get_main_multiplier()
        return 0

    def get_final_damage_pct(self) -> float:
        if self.is_special and self.special_stat_type == "damage_pct":
            return self.special_stat_value * self.get_sub_multiplier()
        return 0

    def get_final_boss_damage(self) -> float:
        return self.sub_boss_damage * self.get_sub_multiplier()

    def get_final_crit_rate(self) -> float:
        return self.sub_crit_rate * self.get_sub_multiplier()

    def get_final_crit_damage(self) -> float:
        return self.sub_crit_damage * self.get_sub_multiplier()

    def can_have_damage_pct(self) -> bool:
        """Check if this item can have Damage % sub stat."""
        return self.is_special

    def to_dict(self) -> dict:
        """Convert to dictionary for CSV export."""
        return {
            "slot": self.slot,
            "name": self.name,
            "rarity": self.rarity,
            "tier": self.tier,
            "stars": self.stars,
            "is_special": self.is_special,
            # Main stats
            "base_attack": self.base_attack,
            "base_hp": self.base_max_hp,
            "base_third": self.base_third_stat,
            # Default sub stats
            "boss_dmg": self.sub_boss_damage,
            "normal_dmg": self.sub_normal_damage,
            "crit_rate": self.sub_crit_rate,
            "crit_dmg": self.sub_crit_damage,
            "attack_flat": self.sub_attack_flat,
            "skill_1st": self.sub_skill_first_job,
            "skill_2nd": self.sub_skill_second_job,
            "skill_3rd": self.sub_skill_third_job,
            "skill_4th": self.sub_skill_fourth_job,
            # Special stat (only on special items)
            "special_stat_type": self.special_stat_type,
            "special_stat_value": self.special_stat_value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EquipmentItem":
        """Create from dictionary (CSV import)."""
        # Handle legacy format (base_main -> base_third)
        base_third = float(data.get("base_third", data.get("base_main", 0)))

        # Handle legacy special stats format (separate fields -> unified)
        special_stat_type = data.get("special_stat_type", "damage_pct")
        special_stat_value = float(data.get("special_stat_value", 0))

        # Migration from old format: check for legacy fields
        if special_stat_value == 0:
            if float(data.get("dmg_pct", 0)) > 0:
                special_stat_type = "damage_pct"
                special_stat_value = float(data.get("dmg_pct", 0))
            elif int(data.get("skill_all", data.get("all_skills", 0))) > 0:
                special_stat_type = "all_skills"
                special_stat_value = float(data.get("skill_all", data.get("all_skills", 0)))
            elif float(data.get("final_dmg", 0)) > 0:
                special_stat_type = "final_damage"
                special_stat_value = float(data.get("final_dmg", 0))

        return cls(
            slot=data.get("slot", ""),
            name=data.get("name", ""),
            rarity=data.get("rarity", "unique"),
            tier=int(data.get("tier", 4)),
            stars=int(data.get("stars", 0)),
            is_special=str(data.get("is_special", "False")).lower() == "true",
            # Main stats
            base_attack=float(data.get("base_attack", 0)),
            base_max_hp=float(data.get("base_hp", 0)),
            base_third_stat=base_third,
            # Default sub stats
            sub_boss_damage=float(data.get("boss_dmg", 0)),
            sub_normal_damage=float(data.get("normal_dmg", 0)),
            sub_crit_rate=float(data.get("crit_rate", 0)),
            sub_crit_damage=float(data.get("crit_dmg", data.get("crit_damage", 0))),
            sub_attack_flat=float(data.get("attack_flat", 0)),
            sub_skill_first_job=int(data.get("skill_1st", data.get("first_job", 0))),
            sub_skill_second_job=int(data.get("skill_2nd", data.get("second_job", 0))),
            sub_skill_third_job=int(data.get("skill_3rd", data.get("third_job", 0))),
            sub_skill_fourth_job=int(data.get("skill_4th", data.get("fourth_job", 0))),
            # Special stat
            special_stat_type=special_stat_type,
            special_stat_value=special_stat_value,
        )


# =============================================================================
# RARITY SCALING
# =============================================================================

# Approximate rarity multipliers (relative to Epic baseline)
RARITY_MULTIPLIERS = {
    Rarity.EPIC: 1.0,
    Rarity.UNIQUE: 2.0,
    Rarity.LEGENDARY: 3.4,
    Rarity.MYSTIC: 5.0,  # Estimated
    Rarity.ANCIENT: 7.0,  # Estimated
}

# Tier multipliers (relative to T4 baseline)
TIER_MULTIPLIERS = {
    4: 1.0,
    3: 1.15,
    2: 1.32,
    1: 1.52,
}


def estimate_base_attack(
    slot: EquipmentSlot,
    rarity: Rarity,
    tier: int,
    level: int,
    reference_attack: int = 1000  # T4 Epic baseline
) -> float:
    """
    Estimate base attack for equipment based on parameters.
    
    Args:
        slot: Equipment slot
        rarity: Equipment rarity
        tier: Equipment tier (1-4)
        level: Equipment level
    
    Returns:
        Estimated base attack
    """
    rarity_mult = RARITY_MULTIPLIERS.get(rarity, 1.0)
    tier_mult = TIER_MULTIPLIERS.get(tier, 1.0)
    level_factor = level / 100  # Normalize around level 100
    
    return reference_attack * rarity_mult * tier_mult * level_factor


# =============================================================================
# SHOP PRICES (VERIFIED)
# =============================================================================

SHOP_PRICES = {
    "starforce_scroll": {
        "blue_diamond": 6000,    # Normal shop
        "red_diamond": 1500,     # Normal shop, 3/week limit
        "arena_coin": 500,       # Arena shop, 25/week limit
        "monthly_pack": 300,     # Monthly package
        "weekly_pack": 350,      # Weekly package
    },
    "potential_cube": {
        "blue_diamond": 3000,    # Regular cube
        "red_diamond": 1000,     # 5/week limit
        "world_boss_coin": 500,  # 10/week limit
    },
    "bonus_potential_cube": {
        "blue_diamond": 2000,    # 3 for 6000
        "red_diamond": 1500,     # Unlimited
        "world_boss_coin": 700,  # 3/week limit
    },
    "artifact_chest": {
        "blue_diamond": 1500,    # 300/week limit
        "red_diamond": 1500,     # 5/week limit
        "arena_coin": 500,       # 10/week limit
    },
}


# =============================================================================
# OPTIMIZATION HELPERS
# =============================================================================

def calculate_upgrade_efficiency(
    damage_gain_pct: float,
    cost: int,
    currency: str = "blue_diamond"
) -> float:
    """
    Calculate efficiency of an upgrade (cost per 1% damage).
    
    Args:
        damage_gain_pct: Expected damage increase as percentage
        cost: Total cost
        currency: Currency type
    
    Returns:
        Cost per 1% damage (lower is better)
    """
    if damage_gain_pct <= 0:
        return float('inf')
    return cost / damage_gain_pct


def rank_upgrade_priority(upgrades: List[dict]) -> List[dict]:
    """
    Rank upgrades by efficiency (best to worst).
    
    Args:
        upgrades: List of upgrade dicts with 'name', 'damage_gain', 'cost'
    
    Returns:
        Sorted list with 'efficiency' added
    """
    for upgrade in upgrades:
        upgrade['efficiency'] = calculate_upgrade_efficiency(
            upgrade['damage_gain'],
            upgrade['cost']
        )
    
    return sorted(upgrades, key=lambda x: x['efficiency'])


# =============================================================================
# MAIN (Example Usage)
# =============================================================================

if __name__ == "__main__":
    print("MapleStory Idle - Equipment System Module")
    print("=" * 50)
    
    # Example: Calculate starforce cost
    print("\nStarforce Cost Estimate (★10 → ★16):")
    meso, stones, attempts = calculate_starforce_expected_cost(10, 16)
    print(f"  Expected Meso: {meso:,}")
    print(f"  Expected Stones: {stones:,}")
    print(f"  Expected Attempts: {attempts:.1f}")
    
    # With protection
    print("\nWith Protections (★15 → ★16):")
    meso, stones, attempts = calculate_starforce_expected_cost(
        15, 16, 
        use_decrease_protection=True,
        use_destroy_protection=True
    )
    print(f"  Expected Meso: {meso:,}")
    print(f"  Expected Stones: {stones:,}")
    print(f"  Expected Attempts: {attempts:.1f}")
    
    # Example: Calculate base stat
    print("\n★19 Necklace with 68.5% Damage %:")
    base_dmg = calculate_base_stat(68.5, 19, is_sub=True)
    print(f"  Base Damage %: {base_dmg:.1f}%")
    print(f"  SF Bonus: {68.5 - base_dmg:.1f}%")
