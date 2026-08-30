"""LunaPath FastAPI backend."""

from __future__ import annotations

import logging
import math
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, conlist, field_validator

from .constants import (
    DEFAULT_ROVER_ID,
    UnknownRoverError,
    W_ENERGY,
    W_SHADOW,
    W_SLOPE,
    W_THERMAL,
    get_rover,
    rover_catalog,
)
from .cost_cube import (
    auto_slice_hours,
    build_cost_cube,
    build_wait_cost_cube,
    coarsen_grid,
    coarsen_traversable,
)
from .cost_engine import edge_travel_time_s
from .corridor import build_corridor
from .costmap import PlanContext, default_cost_map
from .pathfinder_4d import astar_4d, bfs_move_count
from .data_loader import DATA_DIR, load_and_preprocess_dem, load_preprocessed_grids
from .pathfinder import astar
from .localization import evaluate_pose
from .pose import PoseEstimate
from .replan_triggers import evaluate_triggers_detailed
from .rover_grids import grids_for_rover
from .scenarios import (
    MISSION_PROFILES,
    compare_results,
    get_profile,
    list_profiles,
    list_scenarios,
    load_scenario,
)
from .route_analysis import route_statistics as compute_route_statistics
from .serializer import build_plan_response, lonlat_to_pixel, pixel_to_lonlat
from .simulation import simulate_path, summarize_simulation

logger = logging.getLogger(__name__)

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Startup/shutdown hook.

    Replaces @app.on_event("startup"), deprecated in FastAPI 0.115.
    (Backend review, #19.)
    """
    await _startup_load_grids()
    yield


app = FastAPI(title="LunaPath", version="0.3.0", lifespan=_lifespan)
# The corridor of the most recent successful plan; what /api/pose projects
# against. Declared here so the attribute always exists -- getattr guards
# elsewhere would hide a typo in the attribute name.
app.state.active_corridor = None

# allow_origins=["*"] together with allow_credentials=True is not a valid
# CORS combination -- it asks browsers to send cookies/auth headers to a
# wildcard origin. There is no authentication on this API today, so nothing
# is exploitable yet; declaring credentials=False keeps it that way rather
# than leaving a CSRF hole armed for whoever adds auth. Set
# LUNAPATH_CORS_ORIGINS (comma-separated) to lock this down further.
# (Backend review, #15.)
_cors_origins = [
    origin.strip()
    for origin in os.environ.get("LUNAPATH_CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(UnknownRoverError)
def _handle_unknown_rover(request: Request, exc: UnknownRoverError) -> JSONResponse:
    """An unrecognised rover_id is the caller's mistake, not a server
    error: without this handler it reached Starlette as a bare KeyError
    and turned into an unhandled 500. (Faz 1-2-3 review, L4.)"""
    return JSONResponse(status_code=422, content={"detail": str(exc)})


# A 4-D cube is (T, H', W') float64 twice over; at a physical slice length a
# week-long horizon is thousands of slices. Cap the slice count so a request
# cannot ask the server to allocate gigabytes. (Faz 3 review, C1.)
MAX_PLAN_4D_SLICES = 1000
# The slice cap alone does not bound memory: build_cost_cube materialises
# (T, H', W') float64 and build_wait_cost_cube another, so the real cost is
# T * H' * W' * 8 * 2 bytes -- and H'/W' shrink with coarsen, which the slice
# cap never saw. At coarsen=1 the 500x500 grid at 1000 slices asked for 4 GB
# from a single request. Bound the bytes, not the slice count. (Review #6.)
MAX_PLAN_4D_CUBE_BYTES = 512 * 1024 * 1024  # 512 MiB across both cubes


def _check_cube_budget(n_slices: int, coarse_shape: tuple[int, int]) -> None:
    """Reject a (slice count, coarse grid) pair that would not fit in memory."""
    height, width = coarse_shape
    needed = n_slices * height * width * 8 * 2  # cost cube + wait cube
    if needed > MAX_PLAN_4D_CUBE_BYTES:
        affordable = max(
            2, MAX_PLAN_4D_CUBE_BYTES // max(1, height * width * 8 * 2)
        )
        raise HTTPException(
            status_code=422,
            detail=(
                f"{n_slices} slices over a {height}x{width} coarse grid needs "
                f"{needed / 2**20:.0f} MiB of cost cubes, over the "
                f"{MAX_PLAN_4D_CUBE_BYTES / 2**20:.0f} MiB budget; "
                f"raise coarsen or keep the horizon at or under {affordable} "
                "slices."
            ),
        )
# Extra slices added on top of the exact MOVE-only horizon (bfs_move_count *
# worst-case slices-per-move) so the planner has room to choose to WAIT --
# waiting costs time, not coarse distance, so it does not show up in the
# BFS move count at all. (Faz 1-2-3 review, H1.)
DEFAULT_HORIZON_WAIT_PAD_SLICES = 20

# app.state.grids is the ONE place the loaded grids live. There used to be a
# module-level _grids global alongside it, hand-synchronised at four call
# sites: _get_grids read only the global, _active_grids read both, and
# /api/health read only the global, so an update that missed one left
# different endpoints serving different grids. (Backend review, #7.)


def _set_grids(grids: dict | None) -> None:
    app.state.grids = grids


def _current_grids() -> dict | None:
    return getattr(app.state, "grids", None)


async def _startup_load_grids() -> None:
    """Attempt to load P1 .npy grids at server start."""
    try:
        grids = load_preprocessed_grids()
        _set_grids(grids)
        shape = grids["metadata"]["shape"]
        logger.info("Grids loaded at startup: shape=%s", shape)
    except FileNotFoundError as exc:
        logger.warning(
            "Grid files not found at startup (%s). "
            "Call POST /api/load-preprocessed or POST /api/load-dem before planning.",
            exc,
        )
        _set_grids(None)
    except Exception as exc:
        logger.error("Unexpected error loading grids at startup: %s", exc)
        _set_grids(None)


def _get_grids() -> dict:
    """Grids for endpoints that take no Request. Same source as _active_grids."""
    grids = _current_grids()
    if grids is None:
        raise HTTPException(
            status_code=400,
            detail="No grids loaded. Call POST /api/load-preprocessed or POST /api/load-dem first.",
        )
    return grids


def _active_grids(request: Request) -> dict:
    """Return the active grids dict."""
    grids = getattr(request.app.state, "grids", None)
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


def _read_grid_value(grid: np.ndarray, row: int, col: int) -> float | None:
    value = grid[row, col]
    return float(value) if np.isfinite(value) else None


def _resolve_dem_path(dem_file: str) -> Path:
    """Resolve *dem_file* inside the DEM directory, refusing to escape it.

    ``os.path.join(DATA_DIR, "dem", dem_file)`` silently DISCARDS the first
    two components when ``dem_file`` is absolute, so "C:/Windows/win.ini"
    (or "/etc/shadow") resolved to that file itself rather than to anything
    under DATA_DIR. ``..`` segments walked out just as freely. Resolving
    both sides and checking containment closes both. (Backend review, #3.)
    """
    dem_root = Path(DATA_DIR, "dem").resolve()
    candidate = (dem_root / dem_file).resolve()
    if candidate != dem_root and dem_root not in candidate.parents:
        raise HTTPException(
            status_code=422,
            detail="dem_file must name a file inside the DEM directory.",
        )
    return candidate


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


def _reject_non_finite_telemetry(state: dict[str, float]) -> dict[str, float]:
    """Refuse NaN/inf telemetry at the API boundary.

    ``dict[str, float]`` does not stop them: a bare ``NaN`` literal is
    legal to Python's JSON decoder, so a plain client sends one without
    trying. Downstream, evaluate_triggers_detailed now skips such values
    rather than reporting them as checked (round 2, H-1), but a caller
    who sent broken telemetry deserves to be told at the door instead of
    reading a skipped list to discover its packet was unusable. It also
    keeps the value out of the response: Starlette serialises with
    allow_nan=False, and /api/pose echoes trigger_state back, so a NaN
    that got this far returned an opaque 500.
    """
    bad = sorted(key for key, value in state.items() if not math.isfinite(value))
    if bad:
        raise ValueError(
            f"non-finite telemetry values for {bad}; "
            "send a finite number or omit the key"
        )
    return state


class ReplanRequest(BaseModel):
    current: Union[StartGoalPixel, StartGoalGeo]
    goal: Union[StartGoalPixel, StartGoalGeo]
    rover_id: str = DEFAULT_ROVER_ID
    weights: PlanWeights = Field(default_factory=PlanWeights)
    state: dict[str, float] = Field(
        default_factory=dict,
        description="Telemetry snapshot evaluated against the replan triggers.",
    )
    force: bool = False

    _check_state = field_validator("state")(_reject_non_finite_telemetry)


class Plan4DRequest(BaseModel):
    start: Union[StartGoalPixel, StartGoalGeo]
    goal: Union[StartGoalPixel, StartGoalGeo]
    rover_id: str = DEFAULT_ROVER_ID
    weights: PlanWeights = Field(default_factory=PlanWeights)
    # n_slices bounds the cube; horizon_hours states the mission window and
    # lets the slice count follow from the slice length. Give one or neither.
    n_slices: Optional[int] = Field(default=None, ge=2, le=MAX_PLAN_4D_SLICES)
    horizon_hours: Optional[float] = Field(default=None, gt=0.0, le=168.0)
    # Omitted by default: a fixed 1 h slice was longer than any real edge
    # traversal, so every move rounded up to exactly one slice and the time
    # axis counted steps instead of hours. When absent the slice is derived
    # from the grid via cost_cube.auto_slice_hours. (Faz 3 review, C1.)
    slice_hours: Optional[float] = Field(default=None, gt=0.0, le=24.0)
    coarsen: int = Field(default=4, ge=1, le=16)


# A bare list[int] let a 3-element start reach astar and raise IndexError as
# an unhandled 500; /api/plan validated this and these two did not. (#10.)
PixelPair = conlist(int, min_length=2, max_length=2)


class PlanMultiRequest(BaseModel):
    start: PixelPair
    goal: PixelPair
    profiles: list[str]
    rover_id: str = DEFAULT_ROVER_ID


class CompareRequest(BaseModel):
    start: PixelPair
    goal: PixelPair
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
    grids = _current_grids()
    loaded = grids is not None
    shape = grids["metadata"]["shape"] if loaded else None
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
    try:
        grids = load_preprocessed_grids(
            processed_dir=req.processed_dir,
            weights=req.weights,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    _set_grids(grids)
    return {"status": "loaded", "metadata": grids["metadata"]}


@app.post("/api/load-dem")
def load_dem(req: LoadDEMRequest):
    dem_path = _resolve_dem_path(req.dem_file)
    if not dem_path.is_file():
        raise HTTPException(status_code=404, detail=f"DEM file not found: {req.dem_file}")
    try:
        grids = load_and_preprocess_dem(
            str(dem_path),
            req.target_resolution_m,
            use_cache=req.use_cache,
            weights=req.weights,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _set_grids(grids)
    return {"status": "loaded", "metadata": grids["metadata"]}


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

    rover = get_rover(metadata.get("rover_id", metadata.get("default_rover_id")))
    context = PlanContext(
        slope=np.asarray(grids["slope"], dtype=np.float64),
        thermal=np.asarray(grids["thermal"], dtype=np.float64),
        shadow_ratio=np.asarray(grids["shadow_ratio"], dtype=np.float64),
        traversable=np.asarray(grids["traversable"], dtype=bool),
        resolution_m=resolution_m,
        rover=rover,
    )
    cost_map = default_cost_map(
        rover,
        metadata.get("cost_weights"),
        metadata.get("layer_validity"),
    )
    breakdown = cost_map.explain(row, col, context)

    return {
        "row": row,
        "col": col,
        "lon": round(lon, 6),
        "lat": round(lat, 6),
        "altitude_m": _read_grid_value(grids["elevation"], row, col),
        "thermal_c": _read_grid_value(grids["thermal"], row, col),
        "resolution_m": resolution_m,
        "span_km": round((rows * resolution_m) / 1000.0, 4),
        "cost_breakdown": breakdown,
        "layer_validity": metadata.get("layer_validity", {}),
    }


@app.post("/api/plan")
def plan(req: PlanRequest, request: Request):
    """Plan a single route with physics simulation."""
    grids = _active_grids(request)
    rover = get_rover(req.rover_id)
    weights_dict = req.weights.model_dump()
    grids_for_plan = grids_for_rover(grids, req.rover_id, weights_dict)

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
        corridor_obj = build_corridor(astar_result["path_pixels"], grids_for_plan, rover)
        corridor_payload = corridor_obj.model_dump()
        # The most recent successfully planned corridor becomes the one
        # /api/pose projects against. Single-slot state, like app.state.grids:
        # LunaPath plans for one rover, and a pose only makes sense against
        # the route that rover is currently driving.
        request.app.state.active_corridor = corridor_obj
    except (ValueError, KeyError) as exc:
        logger.warning("Corridor generation skipped: %s", exc)
        corridor_payload = None

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
            corridor=corridor_payload,
            route_statistics=compute_route_statistics(states),
        )
    except ValueError as exc:
        # pixel_to_lonlat rejects a grid whose pixels do not project into the
        # lunar south polar region. That is a bad origin/CRS in the loaded
        # grids -- the pipeline's input, not a server fault -- and the blanket
        # 500 hid the real reason behind "Internal serialization error".
        # (Backend review, #11.)
        logger.warning("Projection rejected the loaded grid geometry: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.error("Response serialization failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal serialization error.")


@app.post("/api/replan")
def replan(req: ReplanRequest, request: Request):
    """Re-plan from the rover's current position when a trigger fires."""
    evaluation = evaluate_triggers_detailed(req.state)
    fired = evaluation["fired"]
    if not fired and not req.force:
        # "skipped" is reported so an empty trigger list is never mistaken
        # for an all-clear: a telemetry packet missing actual_soc used to
        # answer "no replan needed" at 1% battery, silently. (Review #4.)
        skipped = evaluation["skipped"]
        return {
            "replanned": False,
            "triggers": [],
            "evaluated": evaluation["evaluated"],
            "skipped": skipped,
            "reason": (
                "no replan trigger fired"
                if not skipped
                else (
                    f"no replan trigger fired, but {len(skipped)} trigger(s) "
                    "could not be evaluated -- telemetry fields are missing"
                )
            ),
        }

    plan_request = PlanRequest(
        start=req.current,
        goal=req.goal,
        rover_id=req.rover_id,
        weights=req.weights,
        include_simulation=True,
    )
    payload = plan(plan_request, request)
    return {
        "replanned": True,
        "triggers": [
            {"trigger_id": t.trigger_id, "detail": t.detail} for t in fired
        ],
        "evaluated": evaluation["evaluated"],
        "skipped": evaluation["skipped"],
        "plan": payload,
    }


class PoseRequest(BaseModel):
    pose: PoseEstimate
    state: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Telemetry the pose alone cannot supply (SoC, temperatures, "
            "comm window), merged under the pose-derived keys -- same shape "
            "as ReplanRequest.state."
        ),
    )

    previous_along_track_m: Optional[float] = Field(
        default=None,
        ge=0.0,
        description=(
            "How far along the corridor this rover was at the last update "
            "-- echo back corridor_fix.along_track_m from the previous "
            "/api/pose response. Used as a progress prior so a switchback's "
            "outbound leg cannot capture a pose driving the return leg. "
            "Omit on the first pose of a traverse."
        ),
    )

    _check_state = field_validator("state")(_reject_non_finite_telemetry)


@app.post("/api/pose")
def pose(req: PoseRequest, request: Request):
    """Locate a pose in the active corridor and evaluate the replan triggers.

    This endpoint closes the loop Phase 7 exists for:
    pose -> deviation -> trigger -> replan. The returned ``trigger_state``
    is exactly what ``POST /api/replan`` accepts as ``state``, so a caller
    that sees fired triggers forwards it unchanged.

    LunaPath consumes this pose; it does not produce one. Whatever stack
    estimated it declares itself in ``pose.source``.
    """
    corridor = request.app.state.active_corridor
    if corridor is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "No active corridor. POST /api/plan first -- a pose is only "
                "meaningful against the route the rover is driving."
            ),
        )

    result = evaluate_pose(
        req.pose,
        corridor,
        req.state,
        previous_along_track_m=req.previous_along_track_m,
    )
    return {
        "corridor_fix": result["corridor_fix"].to_dict(),
        "pose_source": req.pose.source,
        "fired_triggers": [
            {"trigger_id": t.trigger_id, "detail": t.detail}
            for t in result["fired"]
        ],
        "evaluated": result["evaluated"],
        "skipped": result["skipped"],
        "trigger_state": result["trigger_state"],
        "recommended_action": result["recommended_action"],
    }


@app.post("/api/plan-4d")
def plan_4d(req: Plan4DRequest, request: Request):
    """Plan through space AND time, with an explicit WAIT decision.

    Coordinate contract: ``path_pixels`` is in FINE grid pixels, matching
    /api/plan, so the same origin/resolution conversion applies to both.
    ``path_pixels_coarse`` and ``path_states`` are in the coarse planning
    grid whose cell size is ``effective_resolution_m``.

    Time contract: a slice is sized to one cell crossing unless
    ``slice_hours`` is given, so ``arrival_slice`` is a clock rather than a
    step count and ``arrival_hours`` reports it directly. State the window
    as ``horizon_hours`` (slice count follows) or as ``n_slices`` (window
    follows) -- not both.
    """
    grids = _active_grids(request)
    rover = get_rover(req.rover_id)
    weights_dict = req.weights.model_dump()
    grids_for_plan = grids_for_rover(grids, req.rover_id, weights_dict)
    metadata = grids_for_plan["metadata"]

    rows, cols = int(metadata["shape"][0]), int(metadata["shape"][1])
    if rows % req.coarsen or cols % req.coarsen:
        raise HTTPException(
            status_code=422,
            detail=f"grid {rows}x{cols} is not divisible by coarsen={req.coarsen}",
        )

    start = _to_pixel(req.start, "start", metadata)
    goal = _to_pixel(req.goal, "goal", metadata)

    # Coarsening collapses blocks of fine cells onto one planner cell. If the
    # caller's start and goal land in the same block there is nothing to plan:
    # the planner would return a single-state "path", which reads as success
    # but is not the route that was asked for (and build_corridor rejects a
    # one-waypoint path anyway). Say so instead of returning it. (Faz 3 review,
    # I2.)
    coarse_start = (start[0] // req.coarsen, start[1] // req.coarsen)
    coarse_goal = (goal[0] // req.coarsen, goal[1] // req.coarsen)
    if coarse_start == coarse_goal:
        raise HTTPException(
            status_code=422,
            detail=(
                f"start {start} and goal {goal} fall in the same coarse cell "
                f"{coarse_start} at coarsen={req.coarsen}; "
                "lower coarsen or choose points further apart."
            ),
        )

    # Computed once and reused for slice sizing, reachability, and the
    # planner call itself -- coarsen_traversable/coarsen_grid are pure
    # functions of the grid and coarsen factor, not of the request's start
    # or goal, so recomputing them per use (the pre-fix code called
    # coarsen_traversable twice) was wasted work, not a correctness issue.
    coarse_traversable = coarsen_traversable(grids_for_plan["traversable"], req.coarsen)
    coarse_slope = coarsen_grid(grids_for_plan["slope"], req.coarsen, how="max")

    # coarsen_traversable is conservative (AND over every fine cell in a
    # block), so a coarse cell it marks passable is guaranteed finite-cost:
    # every fine cell inside satisfies slope <= slope_max_deg, which is the
    # only source of infinite cost in the coarse cube (see SlopeLayer /
    # f_slope). bfs_move_count is therefore both a reachability check AND an
    # exact distance bound for the planner that follows -- no separate
    # "usable" mask is needed. (Faz 1-2-3 review, H1/H3.)
    move_count = bfs_move_count(coarse_traversable, coarse_start, coarse_goal)
    if not bool(coarse_traversable[coarse_start]):
        raise HTTPException(
            status_code=422,
            detail=(
                f"start {start} falls in coarse block {coarse_start} at "
                f"coarsen={req.coarsen}, which is not traversable: at least "
                "one fine cell inside it exceeds the slope or thermal limit. "
                "Lower coarsen or choose a different start."
            ),
        )
    if not bool(coarse_traversable[coarse_goal]):
        raise HTTPException(
            status_code=422,
            detail=(
                f"goal {goal} falls in coarse block {coarse_goal} at "
                f"coarsen={req.coarsen}, which is not traversable: at least "
                "one fine cell inside it exceeds the slope or thermal limit. "
                "Lower coarsen or choose a different goal."
            ),
        )
    if move_count is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"start {start} and goal {goal} are not connected through "
                f"passable coarse blocks at coarsen={req.coarsen}: terrain "
                "hazards split the grid into disconnected regions here. "
                "Lower coarsen or choose a different pair."
            ),
        )

    # Size the time slice to a real cell crossing unless the caller pinned it.
    # (Faz 3 review, C1.)
    if req.slice_hours is None:
        slice_hours = auto_slice_hours(
            coarse_slope,
            coarse_traversable,
            resolution_m=float(metadata["resolution_m"]) * req.coarsen,
            rover=rover,
        )
        slice_hours_source = "auto"
    else:
        slice_hours = float(req.slice_hours)
        slice_hours_source = "request"

    # n_slices and horizon_hours are two ways to say the same thing; taking
    # both invites a silent disagreement about how far ahead we planned.
    if req.n_slices is not None and req.horizon_hours is not None:
        raise HTTPException(
            status_code=422,
            detail=(
                "give either n_slices or horizon_hours, not both: "
                "horizon_hours derives the slice count from the slice length."
            ),
        )

    if req.horizon_hours is not None:
        n_slices = int(math.ceil(req.horizon_hours / slice_hours))
        if n_slices > MAX_PLAN_4D_SLICES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"horizon_hours={req.horizon_hours} at a {slice_hours:.4f} h "
                    f"slice needs {n_slices} slices, over the {MAX_PLAN_4D_SLICES} "
                    "cap; shorten the horizon, raise coarsen, or pin slice_hours."
                ),
            )
        n_slices = max(2, n_slices)
    elif req.n_slices is not None:
        n_slices = req.n_slices
    else:
        # No explicit horizon: a fixed DEFAULT_PLAN_4D_SLICES=24 starved
        # routes whose start and goal were genuinely far apart on the real
        # production grid -- 24 slices at an auto-derived ~0.03 h/slice
        # covers only ~24 coarse cells, 480 m on a 2.5 km grid (measured:
        # 10/12 random traversable pairs failed). Size the default to the
        # EXACT worst case for the known shortest route: move_count moves,
        # each costing up to the slowest possible edge (slope_max_deg,
        # diagonal), plus a pad for an optional WAIT. This is provably
        # sufficient whenever the route is reachable, not a guessed
        # multiplier. (Faz 1-2-3 review, H1.)
        diag_m = float(metadata["resolution_m"]) * req.coarsen * math.sqrt(2.0)
        worst_edge_s = edge_travel_time_s(float(rover["slope_max_deg"]), diag_m, rover)
        max_slices_per_move = (
            max(1, int(math.ceil(worst_edge_s / 3600.0 / slice_hours)))
            if math.isfinite(worst_edge_s)
            else 1
        )
        default_n_slices = (
            move_count * max_slices_per_move + DEFAULT_HORIZON_WAIT_PAD_SLICES
        )
        if default_n_slices > MAX_PLAN_4D_SLICES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"the shortest coarse route is {move_count} moves, needing "
                    f"up to {default_n_slices} slices at a {slice_hours:.4f} h "
                    f"slice -- over the {MAX_PLAN_4D_SLICES} cap; raise coarsen, "
                    "or pin a shorter horizon_hours/n_slices/slice_hours."
                ),
            )
        n_slices = max(2, default_n_slices)

    # Bound the actual allocation now that both n_slices and the coarse grid
    # shape are known -- MAX_PLAN_4D_SLICES caps the time axis only. (#6.)
    _check_cube_budget(n_slices, coarse_traversable.shape)

    # Until the SPICE-driven illumination cube lands, hold shadow constant
    # across slices: the planner machinery is exercised, the physics is not
    # invented. Replace this series with app.illumination output per slice.
    base_shadow = np.asarray(grids_for_plan["shadow_ratio"], dtype=np.float64)
    shadow_series = [base_shadow] * n_slices
    illum_series = [1.0 - base_shadow] * n_slices

    cost_cube = build_cost_cube(
        grids_for_plan, shadow_series, rover, weights_dict, coarsen=req.coarsen
    )
    wait_cube = build_wait_cost_cube(
        illum_series, rover, slice_hours, weights_dict, coarsen=req.coarsen
    )

    result = astar_4d(
        cost_cube,
        wait_cube,
        coarse_traversable,
        start=coarse_start,
        goal=coarse_goal,
        resolution_m=float(metadata["resolution_m"]) * req.coarsen,
        slice_hours=slice_hours,
        rover=rover,
        slope_grid=coarse_slope,
    )
    if result["error"]:
        # move_count is known reachable at this point (checked above), so
        # this only fires when the caller pinned an n_slices/horizon_hours/
        # slice_hours combination too tight for the route it asked for --
        # tell them the exact number that would have worked.
        detail = (
            f"{result['error']} (the shortest coarse route needs at least "
            f"{move_count} moves; raise n_slices or horizon_hours)"
        )
        raise HTTPException(status_code=404, detail=detail)

    # The planner solves on the coarse grid, but the caller asked in fine
    # pixels and will convert the answer using the fine origin/resolution in
    # metadata. Publishing coarse indices under the same field name /api/plan
    # uses for fine ones is a silent factor-of-coarsen scale error; return the
    # centre of each coarse block instead and keep the coarse path under a
    # name that says what it is. (Faz 3 review, C2.)
    offset = req.coarsen // 2
    fine_pixels = [
        (r * req.coarsen + offset, c * req.coarsen + offset)
        for r, c in result["path_pixels"]
    ]

    # arrival_slice is only a clock when the slice length is physical; expose
    # the hours directly so callers never have to rediscover that. (C1.)
    metrics = dict(result["metrics"])
    arrival = metrics.get("arrival_slice")
    metrics["arrival_hours"] = (
        None if arrival is None else float(arrival) * slice_hours
    )

    return {
        "path_pixels": fine_pixels,
        "path_pixels_coarse": result["path_pixels"],
        "path_states": result["path_states"],
        "metrics": metrics,
        "n_slices": n_slices,
        "slice_hours": slice_hours,
        "slice_hours_source": slice_hours_source,
        "horizon_hours": n_slices * slice_hours,
        "coarsen": req.coarsen,
        "effective_resolution_m": float(metadata["resolution_m"]) * req.coarsen,
        "rover_id": req.rover_id,
    }


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
        grids = grids_for_rover(base_grids, req.rover_id, profile["weights"])
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
        grids = grids_for_rover(base_grids, req.rover_id, profile["weights"])
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
    # downsample=0 raised "slice step cannot be zero" as an unhandled 500, and
    # a negative step silently REVERSED the grid -- a correct-looking map with
    # its axes flipped. Bound it at the signature. (Review #9.)
    downsample: int = Query(1, ge=1, le=50),
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
        grids_for_rover(base_grids, rover_id, weight_overrides or None)
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
        dem_path = _resolve_dem_path(scenario["dem_file"])
        if dem_path.is_file():
            _set_grids(
                load_and_preprocess_dem(
                    str(dem_path),
                    scenario.get("grid_resolution_m", 80),
                    weights=scenario.get("weights"),
                )
            )
    return scenario
