"""LunaPath FastAPI backend."""

import os
from typing import Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .data_loader import load_and_preprocess_dem, DATA_DIR
from .pathfinder import astar
from .scenarios import (
    MISSION_PROFILES,
    compare_results,
    get_profile,
    list_profiles,
    list_scenarios,
    load_scenario,
)

app = FastAPI(title="LunaPath", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory grid store (loaded once)
_grids: dict | None = None


def _get_grids() -> dict:
    global _grids
    if _grids is None:
        raise HTTPException(status_code=400, detail="No DEM loaded. Call POST /api/load-dem first.")
    return _grids


# ── Models ───────────────────────────────────────────────────────────────────

class LoadDEMRequest(BaseModel):
    dem_file: str
    target_resolution_m: float = 50

class PlanRequest(BaseModel):
    start: list[int]  # [row, col]
    goal: list[int]
    profile_id: str
    custom_weights: Optional[dict[str, float]] = None

class PlanMultiRequest(BaseModel):
    start: list[int]
    goal: list[int]
    profiles: list[str]

class CompareRequest(BaseModel):
    start: list[int]
    goal: list[int]


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    loaded = _grids is not None
    shape = _grids["metadata"]["shape"] if loaded else None
    return {"status": "ok", "version": "0.1.0", "dem_loaded": loaded, "grid_shape": shape}


@app.post("/api/load-dem")
def load_dem(req: LoadDEMRequest):
    global _grids
    dem_path = os.path.join(DATA_DIR, "dem", req.dem_file)
    if not os.path.exists(dem_path):
        raise HTTPException(status_code=404, detail=f"DEM file not found: {req.dem_file}")
    _grids = load_and_preprocess_dem(dem_path, req.target_resolution_m)
    meta = _grids["metadata"]
    return {"status": "loaded", "metadata": meta}


@app.post("/api/plan")
def plan(req: PlanRequest):
    grids = _get_grids()
    profile = get_profile(req.profile_id)
    if profile is None and req.custom_weights is None:
        raise HTTPException(status_code=400, detail=f"Unknown profile: {req.profile_id}")

    weights = req.custom_weights or profile["weights"]
    constraints = profile["constraints"] if profile else None

    result = astar(grids, tuple(req.start), tuple(req.goal), weights, constraints)
    result["profile_id"] = req.profile_id
    result["profile_name"] = profile["name"] if profile else "Custom"
    result["color"] = profile["color"] if profile else "#888888"
    return result


@app.post("/api/plan-multi")
def plan_multi(req: PlanMultiRequest):
    grids = _get_grids()
    results = []
    for pid in req.profiles:
        profile = get_profile(pid)
        if profile is None:
            results.append({"profile_id": pid, "error": f"Unknown profile: {pid}", "path_pixels": [], "metrics": {}})
            continue
        r = astar(grids, tuple(req.start), tuple(req.goal), profile["weights"], profile["constraints"])
        r["profile_id"] = pid
        r["profile_name"] = profile["name"]
        r["color"] = profile["color"]
        results.append(r)
    return {"results": results}


@app.post("/api/compare")
def compare(req: CompareRequest):
    grids = _get_grids()
    results = []
    for pid, profile in MISSION_PROFILES.items():
        r = astar(grids, tuple(req.start), tuple(req.goal), profile["weights"], profile["constraints"])
        r["profile_id"] = pid
        r["profile_name"] = profile["name"]
        r["color"] = profile["color"]
        results.append(r)
    comparison = compare_results(results)
    return {"start": req.start, "goal": req.goal, "results": results, "comparison": comparison}


@app.get("/api/layers/{layer_name}")
def get_layer(layer_name: str, downsample: int = 1):
    """Return a grid layer as a JSON 2D array (downsampled for frontend)."""
    grids = _get_grids()
    valid = ("elevation", "slope", "thermal", "shadow_ratio")
    if layer_name not in valid:
        raise HTTPException(status_code=400, detail=f"Layer must be one of {valid}")
    arr = grids[layer_name]
    if downsample > 1:
        arr = arr[::downsample, ::downsample]
    # Replace NaN with None for JSON
    data = np.where(np.isnan(arr), None, arr)
    return {
        "layer": layer_name,
        "shape": list(arr.shape),
        "data": data.tolist(),
    }


@app.get("/api/profiles")
def profiles():
    return list_profiles()


@app.get("/api/scenarios")
def scenarios():
    return {"scenarios": list_scenarios()}


@app.post("/api/scenarios/{scenario_id}/load")
def load_scenario_endpoint(scenario_id: str):
    sc = load_scenario(scenario_id)
    if sc is None:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {scenario_id}")
    # Auto-load the DEM if specified
    if "dem_file" in sc:
        global _grids
        dem_path = os.path.join(DATA_DIR, "dem", sc["dem_file"])
        if os.path.exists(dem_path):
            res = sc.get("grid_resolution_m", 50)
            _grids = load_and_preprocess_dem(dem_path, res)
    return sc
