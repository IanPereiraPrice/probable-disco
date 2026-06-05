"""
Pydantic leaf models for individual stat sources.

These represent the typed, canonical shape of each data section in UserData.
They are not yet wired into UserData (Phase 2+), but define the target structure
and are usable for typed access anywhere they're needed now.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Weapons
# ---------------------------------------------------------------------------

class WeaponEntry(BaseModel):
    """A single weapon slot: level and awakening stage."""
    level: int = Field(0, ge=0)
    awakening: int = Field(0, ge=0, le=5)


# ---------------------------------------------------------------------------
# Hero Power
# ---------------------------------------------------------------------------

class HeroPowerLine(BaseModel):
    """One of the 6 Hero Power ability lines."""
    stat: str = ""
    value: float = 0.0
    tier: str = "Common"
    locked: bool = False


class HeroPowerData(BaseModel):
    """
    All Hero Power data: ability lines + passive levels.

    passive_levels: ordered list of 6 passive level values (indices 0-5 map to
    main_stat / damage / attack / hp / accuracy / defense).
    """
    lines: dict[str, HeroPowerLine] = Field(default_factory=dict)  # line1..line6
    passive_levels: dict[str, int] = Field(default_factory=dict)    # stat_type -> level


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------

class ArtifactSlot(BaseModel):
    """One equipped artifact slot."""
    name: str = ""
    stars: int = Field(0, ge=0, le=5)
    level: int = Field(0, ge=0, le=40)
    potentials: list[dict] = Field(default_factory=list)


class ArtifactData(BaseModel):
    """All artifact data: equipped slots + resonance."""
    equipped: dict[str, ArtifactSlot] = Field(default_factory=dict)  # slot -> artifact
    inventory: dict[str, dict] = Field(default_factory=dict)          # artifact_id -> data
    resonance: dict[str, int] = Field(default_factory=dict)           # stat -> level


# ---------------------------------------------------------------------------
# Companions
# ---------------------------------------------------------------------------

class CompanionData(BaseModel):
    """
    Companion levels (inventory) and equipped slot assignment.

    companion_levels: companion_key -> level
    equipped: list of 7 slots, each is a companion_key or None
    """
    companion_levels: dict[str, int] = Field(default_factory=dict)
    equipped: list[Optional[str]] = Field(default_factory=lambda: [None] * 7)


# ---------------------------------------------------------------------------
# Maple Rank
# ---------------------------------------------------------------------------

MAPLE_RANK_PASSIVE_KEYS = [
    "crit_rate", "crit_damage", "damage", "boss_damage", "normal_damage", "attack_speed",
    "main_stat_flat", "attack_flat", "def_pen", "max_hp",
]

class MapleRankData(BaseModel):
    """
    Maple Rank progression.

    current_stage: current unlocked stage (1-based).
    main_stat_level: level of the main stat node.
    stat_levels: per-passive-stat level dict (e.g. crit_rate -> 3).
    special_points: unspent special points.
    """
    current_stage: int = Field(1, ge=1)
    main_stat_level: int = Field(0, ge=0)
    stat_levels: dict[str, int] = Field(default_factory=dict)
    special_points: int = Field(0, ge=0)

    @classmethod
    def from_legacy_dict(cls, d: dict) -> "MapleRankData":
        """Convert the old MapleRankData raw dict to this typed model."""
        return cls(
            current_stage=int(d.get("current_stage", 1)),
            main_stat_level=int(d.get("main_stat_level", 0)),
            stat_levels={k: int(v) for k, v in d.get("stat_levels", {}).items()},
            special_points=int(d.get("special_points", 0)),
        )

    def to_legacy_dict(self) -> dict:
        """Back to the raw dict format for CSV serialization (backwards compat)."""
        return {
            "current_stage": self.current_stage,
            "main_stat_level": self.main_stat_level,
            "stat_levels": dict(self.stat_levels),
            "special_points": self.special_points,
        }
