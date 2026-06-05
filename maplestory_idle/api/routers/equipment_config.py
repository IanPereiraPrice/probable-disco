"""
Static equipment/potential configuration endpoint.
Returns all tier values, stat options, and pity thresholds in one shot.
This data is static (game constants), so it can be cached forever by the frontend.
"""
import api._paths  # noqa: F401

from fastapi import APIRouter
from typing import Any, Dict

from game.cubes import (
    PotentialTier,
    StatType,
    POTENTIAL_STATS,
    SPECIAL_POTENTIALS,
    REGULAR_PITY,
    BONUS_PITY,
    get_available_stats_for_slot,
    get_stat_value_at_tier,
    get_stat_display_name,
    get_stat_short_name,
)
from streamlit_app.utils.data_manager import EQUIPMENT_SLOTS

router = APIRouter(tags=["equipment-config"])

TIERS = [
    PotentialTier.RARE,
    PotentialTier.EPIC,
    PotentialTier.UNIQUE,
    PotentialTier.LEGENDARY,
    PotentialTier.MYSTIC,
]


@router.get("/potential-config")
def potential_config() -> Dict[str, Any]:
    """
    Return all static potential configuration data:
      - available stat types per slot (with display/short names)
      - yellow value and grey value per (slot, tier, stat)
      - pity thresholds per tier
      - special stat per slot
    """
    # ── Stat display names ────────────────────────────────────────────────────
    stat_labels: Dict[str, Dict[str, str]] = {}
    all_stat_types = list(StatType)
    for st in all_stat_types:
        stat_labels[st.value] = {
            "display": get_stat_display_name(st),
            "short": get_stat_short_name(st),
        }

    # ── Per-slot stat options ─────────────────────────────────────────────────
    slot_stats: Dict[str, list] = {}
    for slot in EQUIPMENT_SLOTS:
        available = get_available_stats_for_slot(slot)
        slot_stats[slot] = [s.value for s in available]

    # ── Special stat per slot ─────────────────────────────────────────────────
    special_per_slot: Dict[str, str | None] = {}
    for slot in EQUIPMENT_SLOTS:
        if slot in SPECIAL_POTENTIALS:
            special_per_slot[slot] = SPECIAL_POTENTIALS[slot].stat_type.value
        else:
            special_per_slot[slot] = None

    # ── Value table: slot → tier → stat → {yellow, grey} ─────────────────────
    # Pre-compute so the frontend only needs a single lookup
    value_table: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}
    for slot in EQUIPMENT_SLOTS:
        value_table[slot] = {}
        available = get_available_stats_for_slot(slot)
        for tier in TIERS:
            tier_key = tier.value
            value_table[slot][tier_key] = {}
            for stat_type in available:
                yellow_val = get_stat_value_at_tier(stat_type, tier, slot, is_yellow=True)
                grey_val   = get_stat_value_at_tier(stat_type, tier, slot, is_yellow=False)
                value_table[slot][tier_key][stat_type.value] = {
                    "yellow": yellow_val,
                    "grey": grey_val,
                }

    # ── Pity thresholds ───────────────────────────────────────────────────────
    regular_pity = {tier.value: REGULAR_PITY[tier] for tier in TIERS}
    bonus_pity   = {tier.value: BONUS_PITY[tier]   for tier in TIERS}

    return {
        "tiers": [t.value for t in TIERS],
        "stat_labels": stat_labels,
        "slot_stats": slot_stats,
        "special_per_slot": special_per_slot,
        "value_table": value_table,
        "regular_pity_thresholds": regular_pity,
        "bonus_pity_thresholds": bonus_pity,
    }
