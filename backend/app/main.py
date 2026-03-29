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

from .constants import (
    DEFAULT_ROVER_ID,
    W_ENERGY,
    W_SHADOW,
    W_SLOPE,
    W_THERMAL,
    get_rover,
    rover_catalog,
)
from .cost_engine import compute_cost_grid, resolve_weights
from .data_loader import DATA_DIR, load_and_preprocess_dem, load_preprocessed_grids
from .pathfinder import astar
from .scenarios import (
    MISSION_PROFILES,
    compare_results,
    get_profile,
    list_profiles,
    list_scenarios,
    load_scenario,
)
from .serializer import build_plan_response, lonlat_to_pixel, pixel_to_lonlat
from .simulation import simulate_path, summarize_simulation
from .traversability import compute_traversability_bool

logger = logging.getLogger(__name__)

app = FastAPI(title="LunaPath", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_grids: dict | None = None


@app.on_event("startup")
async def _startup_load_grids() -> None:
    """Attempt to load P1 .npy grids at server start."""
    global _grids
    try:
        grids = load_preprocessed_grids()
        _grids = grids
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


def _get_grids() -> dict:
    if _grids is None:
        raise HTTPException(
            status_code=400,
            detail="No grids loaded. Call POST /api/load-preprocessed or POST /api/load-dem first.",
        )
    return _grids


def _active_grids(request: Request) -> dict:
    """Return the active grids dict, preferring app.state over the module global."""
    grids = getattr(request.app.state, "grids", None) or _grids
    if grids is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Grid data not loaded. "
                "Run the P1 pipeline and call POST /api/load-preprocessed, "
                "or wait for server startup to complete."
            ),
        )
    return grids


def _grids_for_rover(
    base_grids: dict,
    rover_id: str = DEFAULT_ROVER_ID,
    weights: dict[str, float] | None = None,
) -> dict:
    """Return grids adapted for the selected rover and weights."""
    rover = get_rover(rover_id)
    metadata = dict(base_grids.get("metadata", {}))
    default_rover_id = metadata.get("default_rover_id", DEFAULT_ROVER_ID)
    stored_weights = metadata.get("cost_weights", {})
    resolved_weights = resolve_weights(weights, rover)

    traversable = (
        base_grids["traversable"]
        if rover_id == default_rover_id
        else compute_traversability_bool(
            base_grids["slope"],
            base_grids["thermal"],
            base_grids.get("elevation"),
            rover=rover,
        )
    )

    needs_cost_recompute = rover_id != default_rover_id or resolved_weights != stored_weights
    cost = (
        compute_cost_grid(
            base_grids["slope"],
            base_grids["thermal"],
            base_grids["shadow_ratio"],
            float(metadata["resolution_m"]),
            traversable=traversable,
            weights=resolved_weights,
            rover=rover,
        )
        if needs_cost_recompute
        else base_grids["cost"]
    )

    metadata["cost_weights"] = resolved_weights
    metadata["rover_id"] = rover_id
    metadata["rover_name"] = rover["name"]
    metadata["default_rover_id"] = default_rover_id

    return {
        **base_grids,
        "traversable": traversable,
        "cost": cost,
        "metadata": metadata,
    }


def _read_grid_value(grid: np.ndarray, row: int, col: int) -> float | None:
    value = grid[row, col]
    return float(value) if np.isfinite(value) else None


def _to_pixel(
    coord: "StartGoalPixel | StartGoalGeo",
    label: str,
    metadata: dict[str, Any] | None = None,
) -> tuple[int, int]:
    """Normalise a start/goal input to (row, col)."""
    if isinstance(coord, StartGoalPixel):
        return coord.row, coord.col
    try:
        return lonlat_to_pixel(coord.lon, coord.lat, metadata)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{label}: {exc}") from exc


class StartGoalPixel(BaseModel):
    row: int
    col: int


class StartGoalGeo(BaseModel):
    lon: float
    lat: float


class PlanWeights(BaseModel):
    w_slope: float = W_SLOPE
    w_energy: float = W_ENERGY
    w_shadow: float = W_SHADOW
    w_thermal: float = W_THERMAL

    @field_validator("w_slope", "w_energy", "w_shadow", "w_thermal")
    @classmethod
    def _check_range(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError(f"weight must be in [0.0, 2.0], got {v}")
        return v


class PlanRequest(BaseModel):
    start: Union[StartGoalPixel, StartGoalGeo]
    goal: Union[StartGoalPixel, StartGoalGeo]
    rover_id: str = DEFAULT_ROVER_ID
    weights: PlanWeights = Field(default_factory=PlanWeights)
    include_simulation: bool = True


class PlanMultiRequest(BaseModel):
    start: list[int]
    goal: list[int]
    profiles: list[str]
    rover_id: str = DEFAULT_ROVER_ID


class CompareRequest(BaseModel):
    start: list[int]
    goal: list[int]
    rover_id: str = DEFAULT_ROVER_ID


class LoadDEMRequest(BaseModel):
    dem_file: str
    target_resolution_m: float = 80
    use_cache: bool = True
    weights: dict[str, float] | None = None


class LoadPreprocessedRequest(BaseModel):
    processed_dir: str | None = None
    weights: dict[str, float] | None = None


@app.get("/api/health")
def health():
    loaded = _grids is not None
    shape = _grids["metadata"]["shape"] if loaded else None
    return {"status": "ok", "version": "0.3.0", "dem_loaded": loaded, "grid_shape": shape}


@app.get("/api/rovers")
def rovers():
    return {
        "default_rover_id": DEFAULT_ROVER_ID,
        "rovers": rover_catalog(),
    }


@app.post("/api/load-preprocessed")
def load_preprocessed(req: LoadPreprocessedRequest):
    """Load pre-computed .npy grids from the P1 pipeline output."""
    global _grids
    try:
        _grids = load_preprocessed_grids(
            processed_dir=req.processed_dir,
            weights=req.weights,
        )
        app.state.grids = _grids
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
        app.state.grids = _grids
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    meta = _grids["metadata"]
    return {"status": "loaded", "metadata": meta}


@app.get("/api/cell-telemetry")
def get_cell_telemetry(row: int, col: int, request: Request):
    grids = _active_grids(request)
    metadata = grids["metadata"]
    shape = metadata["shape"]
    rows, cols = int(shape[0]), int(shape[1])

    if not (0 <= row < rows and 0 <= col < cols):
        raise HTTPException(
            status_code=422,
            detail=f"({row}, {col}) is outside the {rows}x{cols} grid.",
        )

    lon, lat = pixel_to_lonlat(row, col, metadata)
    resolution_m = float(metadata["resolution_m"])

    return {
        "row": row,
        "col": col,
        "lon": round(lon, 6),
        "lat": round(lat, 6),
        "altitude_m": _read_grid_value(grids["elevation"], row, col),
        "thermal_c": _read_grid_value(grids["thermal"], row, col),
        "resolution_m": resolution_m,
        "span_km": round((rows * resolution_m) / 1000.0, 4),
    }


@app.post("/api/plan")
def plan(req: PlanRequest, request: Request):
    """Plan a single route with physics simulation."""
    grids = _active_grids(request)
    rover = get_rover(req.rover_id)
    weights_dict = req.weights.model_dump()
    grids_for_plan = _grids_for_rover(grids, req.rover_id, weights_dict)

    metadata = grids_for_plan["metadata"]
    start = _to_pixel(req.start, "start", metadata)
    goal = _to_pixel(req.goal, "goal", metadata)

    shape = metadata["shape"]
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

    traversable = grids_for_plan["traversable"]
    if not bool(traversable[start[0], start[1]]):
        raise HTTPException(
            status_code=422,
            detail=(
                f"start {start} is not traversable for {rover['name']} "
                "(slope limit or extreme thermal)."
            ),
        )
    if not bool(traversable[goal[0], goal[1]]):
        raise HTTPException(
            status_code=422,
            detail=(
                f"goal {goal} is not traversable for {rover['name']} "
                "(slope limit or extreme thermal)."
            ),
        )

    astar_result = astar(
        grids_for_plan,
        start,
        goal,
        weights=weights_dict,
        rover=rover,
    )
    if astar_result.get("error"):
        raise HTTPException(status_code=404, detail=astar_result["error"])

    try:
        states = simulate_path(
            astar_result,
            grids_for_plan["cost"],
            grids_for_plan["slope"],
            grids_for_plan["thermal"],
            grids_for_plan["shadow_ratio"],
            rover=rover,
            pixel_size_m=float(metadata["resolution_m"]),
        )
        summary = summarize_simulation(states)
    except Exception:
        logger.error("Simulation failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal simulation error.")

    try:
        return build_plan_response(
            astar_result,
            states,
            summary,
            req.include_simulation,
            metadata,
            grids_for_plan["elevation"],
            rover_id=req.rover_id,
            rover_name=rover["name"],
        )
    except Exception:
        logger.error("Response serialization failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal serialization error.")


@app.post("/api/plan-multi")
def plan_multi(req: PlanMultiRequest):
    base_grids = _get_grids()
    rover = get_rover(req.rover_id)
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
        grids = _grids_for_rover(base_grids, req.rover_id, profile["weights"])
        result = astar(
            grids,
            tuple(req.start),
            tuple(req.goal),
            weights=profile["weights"],
            constraints=profile["constraints"],
            rover=rover,
        )
        result["profile_id"] = profile_id
        result["profile_name"] = profile["name"]
        result["color"] = profile["color"]
        results.append(result)
    return {"results": results}


@app.post("/api/compare")
def compare(req: CompareRequest):
    base_grids = _get_grids()
    rover = get_rover(req.rover_id)
    results = []
    for profile_id, profile in MISSION_PROFILES.items():
        grids = _grids_for_rover(base_grids, req.rover_id, profile["weights"])
        result = astar(
            grids,
            tuple(req.start),
            tuple(req.goal),
            weights=profile["weights"],
            constraints=profile["constraints"],
            rover=rover,
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
def get_layer(
    layer_name: str,
    downsample: int = 1,
    rover_id: str = DEFAULT_ROVER_ID,
    w_slope: float | None = None,
    w_energy: float | None = None,
    w_shadow: float | None = None,
    w_thermal: float | None = None,
):
    base_grids = _get_grids()
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

    weight_overrides = {
        key: value
        for key, value in {
            "w_slope": w_slope,
            "w_energy": w_energy,
            "w_shadow": w_shadow,
            "w_thermal": w_thermal,
        }.items()
        if value is not None
    }

    rover = get_rover(rover_id)
    grids = (
        _grids_for_rover(base_grids, rover_id, weight_overrides or None)
        if layer_name in ("cost", "traversable") or rover_id != DEFAULT_ROVER_ID or weight_overrides
        else base_grids
    )
    metadata = dict(grids["metadata"])
    metadata["rover_id"] = rover_id
    metadata["rover_name"] = rover["name"]

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
        "metadata": metadata,
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
            app.state.grids = _grids
    return scenario
