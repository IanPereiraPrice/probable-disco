"""
MapleStory Idle - Core Damage Calculation
==========================================
Single source of truth for all damage formulas.

All formulas have been verified through in-game testing.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .constants import (
    BASE_CRIT_DMG,
    DEF_PEN_CAP,
    ATK_SPD_CAP,
)


# =============================================================================
# RESULT DATACLASS
# =============================================================================

@dataclass
class DamageResult:
    """Complete damage calculation result with breakdown."""
    total: float
    base_atk: float
    stat_mult: float
    damage_mult: float
    amp_mult: float
    fd_mult: float
    crit_mult: float
    def_mult: float
    total_dex: float

    def breakdown(self) -> str:
        """Return formatted breakdown of damage calculation."""
        return f"""
Damage Calculation Breakdown
============================
Base ATK:           {self.base_atk:,.0f}
x Stat Prop:        {self.stat_mult:.4f}
x Damage %:         {self.damage_mult:.4f}
x Damage Amp:       {self.amp_mult:.4f}
x Final Damage:     {self.fd_mult:.4f}
x Crit Damage:      {self.crit_mult:.4f}
x Defense:          {self.def_mult:.4f}
----------------------------
= Total Damage:     {self.total:,.0f}
"""


# =============================================================================
# DEX CALCULATION
# =============================================================================

def calculate_total_dex(flat_dex_pool: float, percent_dex: float) -> float:
    """
    Calculate total DEX from flat pool and percentage bonus.

    Formula:
        Total_DEX = Flat_DEX_Pool * (1 + %DEX/100)

    Args:
        flat_dex_pool: Sum of all flat DEX sources
        percent_dex: Total %DEX bonus (e.g., 126.5 for 126.5%)

    Returns:
        Total DEX value
    """
    return flat_dex_pool * (1 + percent_dex / 100)


def calculate_stat_proportional_damage(total_dex: float, total_str: float = 0) -> float:
    """
    Calculate stat-based damage multiplier.

    Formula (for Bowmaster):
        Stat_Prop_Damage% = (Total_DEX * 1%) + (Total_STR * 0.25%)

    Args:
        total_dex: Total DEX after all bonuses
        total_str: Total STR after all bonuses (secondary stat)

    Returns:
        Stat proportional damage as decimal (e.g., 4.234 for 423.4%)
    """
    return (total_dex * 0.01) + (total_str * 0.0025)


# =============================================================================
# DAMAGE AMPLIFICATION
# =============================================================================

def calculate_damage_amp_multiplier(damage_amp_percent: float) -> float:
    """
    Calculate Damage Amplification multiplier.

    Formula:
        Multiplier = 1 + (DamageAmp% / 100)

    Example: 23.2% damage amp → 1.232x multiplier

    Source: Scrolls

    Args:
        damage_amp_percent: Total Damage Amplification % from scrolls

    Returns:
        Damage Amplification multiplier

    Note:
        Old formula used a divisor of 396.5: 1 + (damage_amp / 396.5)
        This was incorrect - damage amp is a straight percentage multiplier.
    """
    return 1 + (damage_amp_percent / 100)


# =============================================================================
# FINAL DAMAGE (MULTIPLICATIVE)
# =============================================================================

def calculate_final_damage_mult(sources: List[float]) -> float:
    """
    Calculate Final Damage multiplier from multiplicative sources.

    Formula:
        Multiplier = (1 + FD1) * (1 + FD2) * (1 + FD3) * ...

    Each source as decimal (e.g., 0.13 for 13%).

    Args:
        sources: List of Final Damage values as decimals

    Returns:
        Final Damage multiplier (NOT percentage - use directly)
    """
    mult = 1.0
    for fd in sources:
        mult *= (1 + fd)
    return mult


def calculate_final_damage_total(sources: List[float]) -> float:
    """
    Calculate total Final Damage percentage.

    Formula:
        Total = [(1 + FD1) * (1 + FD2) * ...] - 1

    Args:
        sources: List of Final Damage values as decimals

    Returns:
        Total Final Damage as decimal (e.g., 0.518 for 51.8%)
    """
    return calculate_final_damage_mult(sources) - 1


# =============================================================================
# CRITICAL DAMAGE
# =============================================================================

def calculate_effective_crit_multiplier(crit_rate: float, crit_damage: float) -> float:
    """
    Calculate effective crit multiplier based on crit rate and crit damage.

    Formula:
        - If crit_rate >= 100%: Always crit, so multiplier = 1 + (crit_damage / 100)
        - If crit_rate < 100%: Weighted average of crit and non-crit hits
          Multiplier = (crit_rate/100) * (1 + crit_damage/100) + (1 - crit_rate/100) * 1

    Simplified:
        Multiplier = 1 + (min(crit_rate, 100) / 100) * (crit_damage / 100)

    Args:
        crit_rate: Total crit rate % (e.g., 85.0 for 85%)
        crit_damage: Total crit damage % including base (e.g., 214.5 for 214.5%)

    Returns:
        Effective crit multiplier
    """
    effective_crit_rate = min(crit_rate, 100.0) / 100.0
    crit_dmg_bonus = crit_damage / 100.0

    # Weighted average: crit hits do (1 + crit_damage), non-crits do 1x
    return 1 + (effective_crit_rate * crit_dmg_bonus)


# =============================================================================
# DEFENSE PENETRATION (MULTIPLICATIVE ON REMAINING)
# =============================================================================

def calculate_defense_pen(sources: List[float]) -> float:
    """
    Calculate total Defense Penetration from multiplicative sources.

    Formula:
        Remaining = (1 - IED1) * (1 - IED2) * (1 - IED3) * ...
        Total Def Pen = 1 - Remaining

    Each source reduces the REMAINING defense, not the original.
    Cap is 100%.

    Example:
        Sources: [0.424, 0.19, 0.165] (42.4%, 19%, 16.5%)
        Remaining = (1-0.424) * (1-0.19) * (1-0.165) = 0.389
        Total = 1 - 0.389 = 0.611 (61.1%)

    Args:
        sources: List of Defense Penetration values as decimals

    Returns:
        Total Defense Penetration as decimal (capped at 1.0)
    """
    remaining = 1.0
    for ied in sources:
        remaining *= (1 - ied)
    total = 1 - remaining
    return min(total, DEF_PEN_CAP / 100)  # Cap at 100%


# =============================================================================
# DEFENSE MULTIPLIER
# =============================================================================

def calculate_defense_multiplier(def_pen: float, enemy_def: float) -> float:
    """
    Calculate damage multiplier vs enemy defense.

    Formula:
        Multiplier = 1 / (1 + EnemyDef * (1 - DefPen))

    Args:
        def_pen: Your total defense penetration as decimal (0-1)
        enemy_def: Enemy's defense value (not percentage)

    Returns:
        Defense multiplier (0-1)
    """
    return 1 / (1 + enemy_def * (1 - def_pen))


# =============================================================================
# ATTACK SPEED (DIMINISHING RETURNS)
# =============================================================================

def calculate_attack_speed(sources: List[Tuple[str, float]]) -> float:
    """
    Calculate total attack speed using diminishing returns formula.

    Formula:
        For each source: atk += (150 - atk) * (source / 150)

    Each source is applied against the remaining gap to the 150% cap.

    Example:
        Sources: +15%, +10%, +7%, +5%
        150 * (1 - (1-15/150) * (1-10/150) * (1-7/150) * (1-5/150)) = 33.884%

    Args:
        sources: List of (source_name, value) tuples where value is percent

    Returns:
        Total attack speed percentage (capped at 150%)
    """
    atk_spd = 0.0

    for source_name, source_value in sources:
        if source_value > 0:
            # Each source multiplies against remaining gap to cap
            gain = (ATK_SPD_CAP - atk_spd) * (source_value / ATK_SPD_CAP)
            atk_spd += gain

    return min(atk_spd, ATK_SPD_CAP)


# =============================================================================
# MASTER DAMAGE CALCULATION
# =============================================================================

def calculate_damage(
    base_atk: float,
    dex_flat: float,
    dex_percent: float,
    damage_percent: float,
    damage_amp: float,
    final_damage_sources: List[float],
    crit_rate: float,
    crit_damage: float,
    defense_pen: float,
    enemy_def: float,
    boss_damage: float = 0,
    str_flat: float = 0,
) -> DamageResult:
    """
    Calculate total damage using the master formula.

    Master Formula:
        Damage = Base_ATK * Stat_Mult * Damage_Mult * Amp_Mult * FD_Mult * Crit_Mult * Def_Mult

    Where:
        - Stat_Mult = 1 + (Total_DEX * 0.01) + (Total_STR * 0.0025)
        - Damage_Mult = 1 + (Damage% / 100) + (Boss% / 100)
        - Amp_Mult = 1 + (Damage_Amp / 100)
        - FD_Mult = (1 + FD1) * (1 + FD2) * ...
        - Crit_Mult = effective multiplier based on crit rate and crit damage
        - Def_Mult = 1 / (1 + Enemy_Def * (1 - Def_Pen))

    Args:
        base_atk: Total attack value
        dex_flat: Flat DEX pool before percentage
        dex_percent: DEX % bonus (e.g., 126.5)
        damage_percent: Total Damage % (e.g., 484.1)
        damage_amp: Damage Amplification % from scrolls
        final_damage_sources: List of FD values as decimals (e.g., [0.13, 0.10])
        crit_rate: Crit Rate % (e.g., 85.0)
        crit_damage: Crit Damage % bonus, not including base 30% (e.g., 184.5)
        defense_pen: Total Defense Penetration as decimal (e.g., 0.609)
        enemy_def: Enemy defense value
        boss_damage: Boss Damage % bonus (e.g., 64.5)
        str_flat: Flat STR (secondary stat, optional)

    Returns:
        DamageResult with total damage and breakdown
    """
    # DEX calculation
    total_dex = calculate_total_dex(dex_flat, dex_percent)
    stat_mult = 1 + calculate_stat_proportional_damage(total_dex, str_flat)

    # Damage %
    damage_mult = 1 + (damage_percent / 100) + (boss_damage / 100)

    # Damage Amplification - straight percentage multiplier
    amp_mult = calculate_damage_amp_multiplier(damage_amp)

    # Final Damage (multiplicative)
    fd_mult = calculate_final_damage_mult(final_damage_sources)

    # Crit Damage - effective multiplier based on crit rate
    total_crit_dmg = BASE_CRIT_DMG + crit_damage
    crit_mult = calculate_effective_crit_multiplier(crit_rate, total_crit_dmg)

    # Defense
    def_mult = calculate_defense_multiplier(defense_pen, enemy_def)

    # Total damage
    total = base_atk * stat_mult * damage_mult * amp_mult * fd_mult * crit_mult * def_mult

    return DamageResult(
        total=total,
        base_atk=base_atk,
        stat_mult=stat_mult,
        damage_mult=damage_mult,
        amp_mult=amp_mult,
        fd_mult=fd_mult,
        crit_mult=crit_mult,
        def_mult=def_mult,
        total_dex=total_dex,
    )


def calculate_damage_simple(
    base_atk: float,
    total_dex: float,
    damage_percent: float,
    final_damage: float,
    crit_rate: float,
    crit_damage: float,
    defense_pen: float,
    enemy_def: float,
    boss_damage: float = 0,
    damage_amp: float = 0,
) -> float:
    """
    Simplified damage calculation for quick comparisons.

    Args:
        base_atk: Total attack value
        total_dex: Total DEX after percentage bonus
        damage_percent: Total Damage %
        final_damage: Total Final Damage as decimal (already multiplicatively combined)
        crit_rate: Crit Rate % (e.g., 85.0)
        crit_damage: Total Crit Damage % including base 30% (e.g., 214.5)
        defense_pen: Total Defense Penetration as decimal
        enemy_def: Enemy defense value
        boss_damage: Boss Damage % (default 0)
        damage_amp: Damage Amplification % (default 0)

    Returns:
        Total damage as float
    """
    # Stat multiplier
    stat_mult = 1 + (total_dex * 0.01)

    # Damage multiplier
    damage_mult = 1 + (damage_percent / 100) + (boss_damage / 100)

    # Other multipliers
    amp_mult = 1 + (damage_amp / 100)
    fd_mult = 1 + final_damage
    crit_mult = calculate_effective_crit_multiplier(crit_rate, crit_damage)
    def_mult = 1 / (1 + enemy_def * (1 - defense_pen))

    return base_atk * stat_mult * damage_mult * amp_mult * fd_mult * crit_mult * def_mult
