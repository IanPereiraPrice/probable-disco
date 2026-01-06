"""
MapleStory Idle - Core Math Module
===================================
Single source of truth for all damage calculations, stat formulas, and game constants.

All other modules should import from here rather than implementing their own formulas.
"""

from .constants import (
    # Damage constants
    BASE_CRIT_DMG,
    BASE_MIN_DMG,
    BASE_MAX_DMG,
    DEF_PEN_CAP,
    ATK_SPD_CAP,
    # Enemy values
    ENEMY_DEFENSE_VALUES,
    ENEMY_DEF_PER_CHAPTER,
    WORLD_BOSS_DEFENSE,
    get_enemy_defense,
    # Stat stacking
    StatStackingType,
    STAT_STACKING,
    # Equipment
    EQUIPMENT_SLOTS,
    # Bowmaster specific
    BOWMASTER_FD_SOURCES,
    # Shop
    SHOP_PRICES,
)

from .damage import (
    # Core calculation
    calculate_damage,
    calculate_damage_simple,
    DamageResult,
    # Helper functions
    calculate_total_dex,
    calculate_stat_proportional_damage,
    calculate_damage_amp_multiplier,
    calculate_final_damage_mult,
    calculate_final_damage_total,
    calculate_defense_pen,
    calculate_defense_multiplier,
    calculate_effective_crit_multiplier,
    calculate_attack_speed,
)

from .stats import (
    CharacterStats,
    aggregate_stats,
)

__all__ = [
    # Constants
    'BASE_CRIT_DMG',
    'BASE_MIN_DMG',
    'BASE_MAX_DMG',
    'DEF_PEN_CAP',
    'ATK_SPD_CAP',
    'ENEMY_DEFENSE_VALUES',
    'ENEMY_DEF_PER_CHAPTER',
    'WORLD_BOSS_DEFENSE',
    'get_enemy_defense',
    'StatStackingType',
    'STAT_STACKING',
    'EQUIPMENT_SLOTS',
    'BOWMASTER_FD_SOURCES',
    'SHOP_PRICES',
    # Damage calculation
    'calculate_damage',
    'calculate_damage_simple',
    'DamageResult',
    'calculate_total_dex',
    'calculate_stat_proportional_damage',
    'calculate_damage_amp_multiplier',
    'calculate_final_damage_mult',
    'calculate_final_damage_total',
    'calculate_defense_pen',
    'calculate_defense_multiplier',
    'calculate_effective_crit_multiplier',
    'calculate_attack_speed',
    # Stats aggregation
    'CharacterStats',
    'aggregate_stats',
]
