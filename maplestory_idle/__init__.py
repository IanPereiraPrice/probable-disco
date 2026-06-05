"""
MapleStory Idle - Game Mechanics Library
=========================================
A Python library for MapleStory Idle damage calculations,
stat optimization, and game system analysis.

Modules:
    core/       - Canonical damage formulas and stat calculations
    equipment   - Equipment, starforce, and potential systems
    artifacts   - Artifact mechanics and awakening
    calculator  - Interactive CLI calculator
    constants   - Shared constants and enums
"""

__version__ = "1.0.0"
__author__ = "MapleStory Idle Research Project"

from .constants import *
from .core import (
    calculate_total_dex,
    calculate_stat_proportional_damage,
    calculate_damage_amp_multiplier,
    calculate_final_damage_mult,
    calculate_defense_pen,
    calculate_damage,
)
