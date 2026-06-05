"""
FastAPI entry point for the MapleStory Idle Calculator backend.
Wraps the existing Python calc engine (skills.py, dps_calculator.py) as REST endpoints.
"""
import api._paths  # noqa: F401 — configures sys.path before any other imports

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import user_data, dps, skills, equipment_config

app = FastAPI(title="MapleStory Idle Calculator API", version="1.0.0")

# Allow the React dev server (port 5173) and any localhost origin during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_data.router, prefix="/api")
app.include_router(dps.router, prefix="/api")
app.include_router(skills.router, prefix="/api")
app.include_router(equipment_config.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
