"""User data CRUD endpoints — GET/POST /api/user-data."""
import api._paths  # noqa: F401

from fastapi import APIRouter, HTTPException
from typing import Any, Dict

from streamlit_app.utils.data_manager import UserData, load_user_data, save_user_data

router = APIRouter(tags=["user-data"])


@router.get("/user-data")
def get_user_data(username: str = "default") -> Dict[str, Any]:
    """Load user data from CSV files and return as JSON."""
    try:
        data = load_user_data(username)
        return data.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user-data")
def post_user_data(body: Dict[str, Any]) -> Dict[str, Any]:
    """Save user data JSON to CSV files. Body must include a 'username' field."""
    username = body.get("username", "default")
    try:
        data = UserData.model_validate(body)
        success = save_user_data(username, data)
        if not success:
            raise HTTPException(status_code=500, detail="Save failed — file may be locked")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
