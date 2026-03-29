"""LunaPath FastAPI backend."""

import os
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .cost_engine import compute_cost_grid, resolve_weights
from .data_loader import load_and_preprocess_dem, load_preprocessed_grids, DATA_DIR
from .pathfinder import astar
from .scenarios import (
    MISSION_PROFILES,
    compare_results,
    get_profile,
    list_profiles,
    list_scenarios,
    load_scenario,
)

app = FastAPI(title="LunaPath", version="0.2.0")

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
    if _grids is None:
        raise HTTPException(
            status_code=400,
            detail="No grids loaded. Call POST /api/load-preprocessed or POST /api/load-dem first.",
        )
    return _grids


def _grids_with_weights(base_grids: dict, weights: dict[str, float] | None) -> dict:
    """Return grids dict with cost layer recomputed for the given weights.

    If *weights* match the stored cost weights (or are None), return as-is
    to avoid redundant work.
    """
    if weights is None:
        return base_grids
    stored = base_grids.get("metadata", {}).get("cost_weights", {})
    resolved = resolve_weights(weights)
    if resolved == stored:
        return base_grids
    # Recompute cost grid for this weight profile
    new_cost = compute_cost_grid(
        base_grids["slope"],
        base_grids["thermal"],
        base_grids["shadow_ratio"],
        float(base_grids["metadata"]["resolution_m"]),
        traversable=base_grids["traversable"],
        weights=resolved,
    )
    return {**base_grids, "cost": new_cost}


class LoadDEMRequest(BaseModel):
    dem_file: str
    target_resolution_m: float = 80
    use_cache: bool = True
    weights: dict[str, float] | None = None


class LoadPreprocessedRequest(BaseModel):
    processed_dir: str | None = None
    weights: dict[str, float] | None = None


class PlanRequest(BaseModel):
    start: list[int]
    goal: list[int]
    profile_id: str | None = None
    custom_weights: dict[str, float] | None = None
    constraints: dict[str, float] | None = None


class PlanMultiRequest(BaseModel):
    start: list[int]
    goal: list[int]
    profiles: list[str]


class CompareRequest(BaseModel):
    start: list[int]
    goal: list[int]


@app.get("/api/health")
def health():
    loaded = _grids is not None
    shape = _grids["metadata"]["shape"] if loaded else None
    return {"status": "ok", "version": "0.2.0", "dem_loaded": loaded, "grid_shape": shape}


@app.post("/api/load-preprocessed")
def load_preprocessed(req: LoadPreprocessedRequest):
    """Load pre-computed .npy grids from the P1 pipeline output.

    This is the preferred loading method — avoids duplicate DEM processing.
    """
    global _grids
    try:
        _grids = load_preprocessed_grids(
            processed_dir=req.processed_dir,
            weights=req.weights,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "loaded", "metadata": _grids["metadata"]}


@app.post("/api/load-dem")
def load_dem(req: LoadDEMRequest):
    global _grids
    dem_path = os.path.join(DATA_DIR, "dem", req.dem_file)
    if not os.path.exists(dem_path):
        raise HTTPException(status_code=404, detail=f"DEM file not found: {req.dem_file}")
    try:
        _grids = load_and_preprocess_dem(
            dem_path,
            req.target_resolution_m,
            use_cache=req.use_cache,
            weights=req.weights,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    meta = _grids["metadata"]
    return {"status": "loaded", "metadata": meta}


@app.post("/api/plan")
def plan(req: PlanRequest):
    base_grids = _get_grids()
    profile = get_profile(req.profile_id) if req.profile_id else None

    if req.profile_id and profile is None:
        raise HTTPException(status_code=400, detail=f"Unknown profile: {req.profile_id}")

    weights = req.custom_weights or (profile["weights"] if profile else None)
    constraints = dict(profile["constraints"]) if profile else {}
    if req.constraints:
        constraints.update(req.constraints)

    grids = _grids_with_weights(base_grids, weights)
    result = astar(
        grids,
        tuple(req.start),
        tuple(req.goal),
        weights=weights,
        constraints=constraints or None,
    )
    result["profile_id"] = req.profile_id or "custom"
    result["profile_name"] = profile["name"] if profile else "Custom"
    result["color"] = profile["color"] if profile else "#64748B"
    return result


@app.post("/api/plan-multi")
def plan_multi(req: PlanMultiRequest):
    base_grids = _get_grids()
    results: list[dict[str, Any]] = []
    for profile_id in req.profiles:
        profile = get_profile(profile_id)
        if profile is None:
            results.append(
                {
                    "profile_id": profile_id,
                    "profile_name": None,
                    "color": "#64748B",
                    "path_pixels": [],
                    "metrics": {},
                    "error": f"Unknown profile: {profile_id}",
                }
            )
            continue
        grids = _grids_with_weights(base_grids, profile["weights"])
        result = astar(
            grids,
            tuple(req.start),
            tuple(req.goal),
            weights=profile["weights"],
            constraints=profile["constraints"],
        )
        result["profile_id"] = profile_id
        result["profile_name"] = profile["name"]
        result["color"] = profile["color"]
        results.append(result)
    return {"results": results}


@app.post("/api/compare")
def compare(req: CompareRequest):
    base_grids = _get_grids()
    results = []
    for profile_id, profile in MISSION_PROFILES.items():
        grids = _grids_with_weights(base_grids, profile["weights"])
        result = astar(
            grids,
            tuple(req.start),
            tuple(req.goal),
            weights=profile["weights"],
            constraints=profile["constraints"],
        )
        result["profile_id"] = profile_id
        result["profile_name"] = profile["name"]
        result["color"] = profile["color"]
        results.append(result)
    return {
        "start": req.start,
        "goal": req.goal,
        "results": results,
        "comparison": compare_results(results),
    }


@app.get("/api/layers/{layer_name}")
def get_layer(layer_name: str, downsample: int = 1):
    grids = _get_grids()
    valid_layers = (
        "elevation",
        "slope",
        "aspect",
        "thermal",
        "shadow_ratio",
        "cost",
        "traversable",
    )
    if layer_name not in valid_layers:
        raise HTTPException(status_code=400, detail=f"Layer must be one of {valid_layers}")

    layer = grids[layer_name]
    if downsample > 1:
        layer = layer[::downsample, ::downsample]

    if layer_name == "traversable":
        serializable = layer.astype(np.uint8).tolist()
    else:
        serializable = np.where(np.isfinite(layer), layer, None).tolist()

    return {
        "layer": layer_name,
        "shape": list(layer.shape),
        "metadata": grids["metadata"],
        "data": serializable,
    }


@app.get("/api/profiles")
def profiles():
    return list_profiles()


@app.get("/api/scenarios")
def scenarios():
    return {"scenarios": list_scenarios()}


@app.post("/api/scenarios/{scenario_id}/load")
def load_scenario_endpoint(scenario_id: str):
    scenario = load_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {scenario_id}")

    if "dem_file" in scenario:
        global _grids
        dem_path = os.path.join(DATA_DIR, "dem", scenario["dem_file"])
        if os.path.exists(dem_path):
            _grids = load_and_preprocess_dem(
                dem_path,
                scenario.get("grid_resolution_m", 80),
                weights=scenario.get("weights"),
            )
    return scenario
