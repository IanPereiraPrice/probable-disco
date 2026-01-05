"""
MapleStory Idle - Game Mechanics Library
=========================================
A Python library for MapleStory Idle damage calculations,
stat optimization, and game system analysis.

Modules:
    formulas    - Core damage formulas and stat calculations
    equipment   - Equipment, starforce, and potential systems
    artifacts   - Artifact mechanics and awakening
    calculator  - Interactive CLI calculator
    constants   - Shared constants and enums

Last Updated: December 2025
Character: Bowmaster Lv.96 - Quarts
"""

__version__ = "1.0.0"
__author__ = "MapleStory Idle Research Project"

from .constants import *
from .formulas import (
    calculate_total_dex,
    calculate_stat_proportional_damage,
    calculate_damage_percent,
    calculate_damage_amp_multiplier,
    calculate_final_damage,
    calculate_defense_penetration,
    calculate_full_damage,
)
