"""LunaPath FastAPI backend."""

from __future__ import annotations

import logging
import os
import traceback
from typing import Any, Union

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .constants import DEFAULT_ROVER_ID, ROVERS, get_rover, list_rovers
from .cost_engine import compute_cost_grid, resolve_weights
from .data_loader import load_and_preprocess_dem, load_preprocessed_grids, DATA_DIR
from .pathfinder import astar
from .scenarios import (
    MISSION_PROFILES,
    compare_results,
    get_profile,
    get_profiles,
    list_profiles,
    list_scenarios,
    load_scenario,
)
from .serializer import build_plan_response, lonlat_to_pixel
from .simulation import simulate_path, summarize_simulation

logger = logging.getLogger(__name__)

app = FastAPI(title="LunaPath", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory grid store — populated at startup and/or via load endpoints.
# Keyed by rover_id so each rover can have its own traversability/cost grids.
_grids_by_rover: dict[str, dict] = {}


def _default_grids() -> dict | None:
    """Return grids for the default rover, or None."""
    return _grids_by_rover.get(DEFAULT_ROVER_ID)


# ── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def _startup_load_grids() -> None:
    """Attempt to load P1 .npy grids at server start for the default rover."""
    try:
        grids = load_preprocessed_grids()
        _grids_by_rover[DEFAULT_ROVER_ID] = grids
        app.state.grids = grids
        shape = grids["metadata"]["shape"]
        logger.info("Grids loaded at startup: shape=%s", shape)
    except FileNotFoundError as exc:
        logger.warning(
            "Grid files not found at startup (%s). "
            "Call POST /api/load-preprocessed or POST /api/load-dem before planning.",
            exc,
        )
        app.state.grids = None
    except Exception as exc:
        logger.error("Unexpected error loading grids at startup: %s", exc)
        app.state.grids = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resolve_rover(rover_id: str | None) -> tuple[str, dict]:
    """Return (rover_id, rover_config). Raises 400 on unknown ID."""
    rid = rover_id or DEFAULT_ROVER_ID
    try:
        rc = get_rover(rid)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return rid, rc


def _get_grids_for_rover(
    rover_id: str | None = None,
    rover_config: dict | None = None,
) -> dict:
    """Return loaded grids for the given rover. Loads on-demand if needed."""
    rid = rover_id or DEFAULT_ROVER_ID
    rc = rover_config or get_rover(rid)

    if rid in _grids_by_rover:
        return _grids_by_rover[rid]

    # For non-default rovers, try to load grids with rover-specific params
    if DEFAULT_ROVER_ID in _grids_by_rover:
        # Recompute traversability and cost from the default rover's base grids
        base = _grids_by_rover[DEFAULT_ROVER_ID]
        try:
            grids = load_preprocessed_grids(
                processed_dir=base["metadata"].get("processed_dir"),
                rover_config=rc,
            )
            _grids_by_rover[rid] = grids
            return grids
        except Exception:
            pass

    raise HTTPException(
        status_code=400,
        detail="No grids loaded. Call POST /api/load-preprocessed or POST /api/load-dem first.",
    )


def _grids_with_weights(
    base_grids: dict,
    weights: dict[str, float] | None,
    rover_config: dict | None = None,
) -> dict:
    """Return grids dict with cost layer recomputed for the given weights."""
    rc = rover_config or get_rover()
    if weights is None:
        return base_grids
    stored = base_grids.get("metadata", {}).get("cost_weights", {})
    resolved = resolve_weights(weights, rc)
    if resolved == stored:
        return base_grids
    new_cost = compute_cost_grid(
        base_grids["slope"],
        base_grids["thermal"],
        base_grids["shadow_ratio"],
        float(base_grids["metadata"]["resolution_m"]),
        traversable=base_grids["traversable"],
        weights=resolved,
        rover_config=rc,
    )
    return {**base_grids, "cost": new_cost}


def _to_pixel(coord: "StartGoalPixel | StartGoalGeo", label: str) -> tuple[int, int]:
    """Normalise a start/goal input to (row, col)."""
    if isinstance(coord, StartGoalPixel):
        return coord.row, coord.col
    try:
        return lonlat_to_pixel(coord.lon, coord.lat)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{label}: {exc}") from exc


# ── Request models ─────────────────────────────────────────────────────────────

class StartGoalPixel(BaseModel):
    row: int
    col: int


class StartGoalGeo(BaseModel):
    lon: float
    lat: float


class PlanWeights(BaseModel):
    w_slope: float = 0.409
    w_energy: float = 0.259
    w_shadow: float = 0.142
    w_thermal: float = 0.190

    @field_validator("w_slope", "w_energy", "w_shadow", "w_thermal")
    @classmethod
    def _check_range(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError(f"weight must be in [0.0, 2.0], got {v}")
        return v


class PlanRequest(BaseModel):
    start: Union[StartGoalPixel, StartGoalGeo]
    goal: Union[StartGoalPixel, StartGoalGeo]
    weights: PlanWeights = Field(default_factory=PlanWeights)
    include_simulation: bool = True
    rover_id: str | None = None


class PlanMultiRequest(BaseModel):
    start: list[int]
    goal: list[int]
    profiles: list[str]
    rover_id: str | None = None


class CompareRequest(BaseModel):
    start: list[int]
    goal: list[int]
    rover_id: str | None = None


class LoadDEMRequest(BaseModel):
    dem_file: str
    target_resolution_m: float = 80
    use_cache: bool = True
    weights: dict[str, float] | None = None
    rover_id: str | None = None


class LoadPreprocessedRequest(BaseModel):
    processed_dir: str | None = None
    weights: dict[str, float] | None = None
    rover_id: str | None = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    default_grids = _default_grids()
    loaded = default_grids is not None
    shape = default_grids["metadata"]["shape"] if loaded else None
    return {
        "status": "ok",
        "version": "0.4.0",
        "dem_loaded": loaded,
        "grid_shape": shape,
        "loaded_rovers": list(_grids_by_rover.keys()),
    }


@app.get("/api/rovers")
def rovers_endpoint():
    """List all available rovers with their full configuration."""
    return {
        "default": DEFAULT_ROVER_ID,
        "rovers": {
            rid: {
                "name": cfg["name"],
                "mass_kg": cfg["mass_kg"],
                "v_max_ms": cfg["v_max_ms"],
                "e_cap_wh": cfg["e_cap_wh"],
                "slope_max_deg": cfg["slope_max_deg"],
                "w_slope": cfg["w_slope"],
                "w_energy": cfg["w_energy"],
                "w_shadow": cfg["w_shadow"],
                "w_thermal": cfg["w_thermal"],
            }
            for rid, cfg in ROVERS.items()
        },
    }


@app.post("/api/load-preprocessed")
def load_preprocessed(req: LoadPreprocessedRequest):
    """Load pre-computed .npy grids from the P1 pipeline output."""
    rid, rc = _resolve_rover(req.rover_id)
    try:
        grids = load_preprocessed_grids(
            processed_dir=req.processed_dir,
            weights=req.weights,
            rover_config=rc,
        )
        _grids_by_rover[rid] = grids
        if rid == DEFAULT_ROVER_ID:
            app.state.grids = grids
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "loaded", "rover_id": rid, "metadata": grids["metadata"]}


@app.post("/api/load-dem")
def load_dem(req: LoadDEMRequest):
    rid, rc = _resolve_rover(req.rover_id)
    dem_path = os.path.join(DATA_DIR, "dem", req.dem_file)
    if not os.path.exists(dem_path):
        raise HTTPException(status_code=404, detail=f"DEM file not found: {req.dem_file}")
    try:
        grids = load_and_preprocess_dem(
            dem_path,
            req.target_resolution_m,
            use_cache=req.use_cache,
            weights=req.weights,
            rover_config=rc,
        )
        _grids_by_rover[rid] = grids
        if rid == DEFAULT_ROVER_ID:
            app.state.grids = grids
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    meta = grids["metadata"]
    return {"status": "loaded", "rover_id": rid, "metadata": meta}


@app.post("/api/plan")
def plan(req: PlanRequest, request: Request):
    """Plan a single route with physics simulation."""
    rid, rc = _resolve_rover(req.rover_id)
    grids = _get_grids_for_rover(rid, rc)

    # 1. Normalise coordinates
    start = _to_pixel(req.start, "start")
    goal = _to_pixel(req.goal, "goal")

    # 2. Bounds and traversability checks
    shape = grids["metadata"]["shape"]
    rows, cols = shape[0], shape[1]

    if not (0 <= start[0] < rows and 0 <= start[1] < cols):
        raise HTTPException(
            status_code=422,
            detail=f"start {start} is outside the {rows}x{cols} grid.",
        )
    if not (0 <= goal[0] < rows and 0 <= goal[1] < cols):
        raise HTTPException(
            status_code=422,
            detail=f"goal {goal} is outside the {rows}x{cols} grid.",
        )

    traversable = grids["traversable"]
    if not bool(traversable[start[0], start[1]]):
        raise HTTPException(
            status_code=422,
            detail=f"start {start} is not traversable for rover {rid}.",
        )
    if not bool(traversable[goal[0], goal[1]]):
        raise HTTPException(
            status_code=422,
            detail=f"goal {goal} is not traversable for rover {rid}.",
        )

    # 3. Cost grid (recompute if custom weights differ from stored)
    weights_dict = req.weights.model_dump()
    grids_for_plan = _grids_with_weights(grids, weights_dict, rc)

    # 4. A*
    astar_result = astar(
        grids_for_plan,
        start,
        goal,
        weights=weights_dict,
        rover_config=rc,
    )
    if astar_result.get("error"):
        raise HTTPException(status_code=404, detail=astar_result["error"])

    # 5. Physics simulation
    try:
        states = simulate_path(
            astar_result,
            grids_for_plan["cost"],
            grids["slope"],
            grids["thermal"],
            grids["shadow_ratio"],
            rover_config=rc,
        )
        summary = summarize_simulation(states, rover_config=rc)
    except Exception:
        logger.error("Simulation failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal simulation error.")

    # 6. Serialise and return
    try:
        response = build_plan_response(astar_result, states, summary, req.include_simulation)
        response["rover_id"] = rid
        response["rover_name"] = rc["name"]
        return response
    except Exception:
        logger.error("Response serialization failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal serialization error.")


@app.post("/api/plan-multi")
def plan_multi(req: PlanMultiRequest):
    rid, rc = _resolve_rover(req.rover_id)
    base_grids = _get_grids_for_rover(rid, rc)
    results: list[dict[str, Any]] = []
    for profile_id in req.profiles:
        profile = get_profile(profile_id, rc)
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
        grids = _grids_with_weights(base_grids, profile["weights"], rc)
        result = astar(
            grids,
            tuple(req.start),
            tuple(req.goal),
            weights=profile["weights"],
            constraints=profile["constraints"],
            rover_config=rc,
        )
        result["profile_id"] = profile_id
        result["profile_name"] = profile["name"]
        result["color"] = profile["color"]
        results.append(result)
    return {"rover_id": rid, "results": results}


@app.post("/api/compare")
def compare(req: CompareRequest):
    rid, rc = _resolve_rover(req.rover_id)
    base_grids = _get_grids_for_rover(rid, rc)
    profiles = get_profiles(rc)
    results = []
    for profile_id, profile in profiles.items():
        grids = _grids_with_weights(base_grids, profile["weights"], rc)
        result = astar(
            grids,
            tuple(req.start),
            tuple(req.goal),
            weights=profile["weights"],
            constraints=profile["constraints"],
            rover_config=rc,
        )
        result["profile_id"] = profile_id
        result["profile_name"] = profile["name"]
        result["color"] = profile["color"]
        results.append(result)
    return {
        "rover_id": rid,
        "start": req.start,
        "goal": req.goal,
        "results": results,
        "comparison": compare_results(results),
    }


@app.get("/api/layers/{layer_name}")
def get_layer(layer_name: str, downsample: int = 1, rover_id: str | None = None):
    rid, rc = _resolve_rover(rover_id)
    grids = _get_grids_for_rover(rid, rc)
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
        "rover_id": rid,
        "metadata": grids["metadata"],
        "data": serializable,
    }


@app.get("/api/profiles")
def profiles(rover_id: str | None = None):
    _, rc = _resolve_rover(rover_id)
    return list_profiles(rc)


@app.get("/api/scenarios")
def scenarios():
    return {"scenarios": list_scenarios()}


@app.post("/api/scenarios/{scenario_id}/load")
def load_scenario_endpoint(scenario_id: str):
    scenario = load_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {scenario_id}")

    if "dem_file" in scenario:
        dem_path = os.path.join(DATA_DIR, "dem", scenario["dem_file"])
        if os.path.exists(dem_path):
            grids = load_and_preprocess_dem(
                dem_path,
                scenario.get("grid_resolution_m", 80),
                weights=scenario.get("weights"),
            )
            _grids_by_rover[DEFAULT_ROVER_ID] = grids
            app.state.grids = grids
    return scenario
