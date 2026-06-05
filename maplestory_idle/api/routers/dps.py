"""DPS calculation endpoints — /api/aggregate-stats, /api/calculate-dps."""
import api._paths  # noqa: F401

from fastapi import APIRouter, HTTPException
from typing import Any, Dict

from api.routers.user_data import _dict_to_user_data
from streamlit_app.utils.dps_calculator import aggregate_stats, calculate_dps
from game.job_classes import JobClass

router = APIRouter(tags=["dps"])


def _make_serializable(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable types (tuples, sets) to lists."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(i) for i in obj]
    return obj


@router.post("/aggregate-stats")
def aggregate_stats_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate all stat sources from user data into a flat stats dict."""
    try:
        user_data = _dict_to_user_data(body)
        stats = aggregate_stats(user_data)
        return _make_serializable(stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate-dps")
def calculate_dps_endpoint(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the full DPS pipeline and return DPS result.

    Body fields:
      - user_data: dict — the UserData fields
      - combat_mode: str — 'stage' | 'boss' | 'world_boss' | 'chapter_hunt'
      - enemy_def: float — enemy defense (0.0-1.0), optional
      - use_realistic_dps: bool — use phase-aware simulation, optional
      - boss_importance: float — 0.0-1.0, optional
    """
    try:
        user_data_dict = body.get("user_data", body)
        user_data = _dict_to_user_data(user_data_dict)

        combat_mode = body.get("combat_mode", user_data.combat_mode)
        enemy_def = float(body.get("enemy_def", 0.752))
        use_realistic = bool(body.get("use_realistic_dps", False))
        boss_importance = float(body.get("boss_importance", 0.7))

        job_class = JobClass(user_data.job_class)

        stats = aggregate_stats(user_data)
        result = calculate_dps(
            stats,
            combat_mode=combat_mode,
            enemy_def=enemy_def,
            job_class=job_class,
            use_realistic_dps=use_realistic,
            boss_importance=boss_importance,
        )
        return _make_serializable(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
