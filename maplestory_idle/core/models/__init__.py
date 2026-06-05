"""
Pydantic models for MapleStory Idle — typed, validated data structures.

Phase 1: Leaf models for stat sources.
Phase 2: CharacterModel — unified character class replacing CharacterState +
         CharacterStats + aggregate_stats dict.
Phase 3+: CharacterModel fully replaces CharacterState inside skills.py.
"""

from .stat_sources import (
    WeaponEntry,
    HeroPowerLine,
    HeroPowerData,
    ArtifactSlot,
    ArtifactData,
    CompanionData,
    MapleRankData,
)
from .character import CharacterModel

__all__ = [
    "WeaponEntry",
    "HeroPowerLine",
    "HeroPowerData",
    "ArtifactSlot",
    "ArtifactData",
    "CompanionData",
    "MapleRankData",
    "CharacterModel",
]
