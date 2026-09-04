"""LunaPath FastAPI backend."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, replace as dataclass_replace
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional, Union
from urllib.parse import urlencode
from uuid import uuid4

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
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
from .pathfinder_4d import astar_4d, gated_move_count
from .data_loader import DATA_DIR, load_and_preprocess_dem, load_preprocessed_grids
from .earth_visibility import (
    build_earth_visibility_series,
    comm_window_from_metadata,
    earth_track_for_series,
)
from .grid_frame import map_xy_to_pixel
from .illumination_series import (
    _parse_start_utc,
    body_track_for_series,
    build_shadow_series,
    horizon_cache_path,
    sun_track_for_series,
)
from .thermal_model import (
    REGOLITH_LAG_VALIDITY,
    REGOLITH_THERMAL_TAU_S,
    relax_surface_c,
    shadowed_equilibrium_c,
)
from .pathfinder import astar
from .localization import evaluate_pose
from .pose import PoseEstimate
from .replan_triggers import evaluate_triggers_detailed
from .rover_grids import grids_for_rover
from .safe_haven import (
    DEFAULT_EARTHSET_LOOKAHEAD_HOURS,
    DEFAULT_SAFE_HAVEN_SPAN_HOURS,
    DEFAULT_SAFE_HAVEN_STEP_HOURS,
    block_min,
    earthset_after_horizon_hours,
    hours_until_earthset_cube,
    route_margins,
    safe_haven_for_grids,
    time_to_safe_haven_hours,
)
from .scenarios import (
    MISSION_PROFILES,
    check_profile_constraints,
    compare_results,
    get_profile,
    list_profiles,
    list_scenarios,
    load_scenario,
)
from .route_analysis import route_statistics as compute_route_statistics
from .serializer import build_plan_response, lonlat_to_pixel, pixel_to_lonlat
from .mission_reference import reference_summary
from .simulation import simulate_path, summarize_simulation
from .uncertainty import (
    CLONE_HORIZONS_FILENAME,
    N_PGDA_CLONES,
    UNCERTAINTY_LAYERS,
    illuminated_probability_series,
    load_clone_horizons,
    route_band,
    route_traversable_probability,
    uncertain_fraction,
    uncertainty_layers_for_grids,
    with_uncertainty_layers,
)
from .stress_test import (
    SHERPA_DEFAULTS,
    Perturbations,
    RouteSky,
    route_legs,
    route_sky_columns,
    stress_test_route,
    wilson_interval,
)
from .terrain import (
    BINARY_LAYER_HEADERS,
    BINARY_MEDIA_TYPE,
    SERIES_HEADERS,
    TERRAIN_LAYERS,
    binary_layer_headers,
    encode_layer_f32,
    layer_stats,
    terrain_manifest,
)

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
app.state.active_corridor_id = None
app.state.active_corridor_rover_id = None
# Every corridor this process has published, keyed by id. The single
# `active_corridor` slot is still the default a pose is judged against, but
# endpoints are sync defs running on a threadpool, so two concurrent
# /api/plan calls race for it and the loser's poses were scored against the
# winner's route with nothing but a mismatched corridor_id to reveal it.
# Keeping the corridors addressable lets a caller pin the one it planned.
# (Round 3 review, L-16.)
app.state.corridors = {}
MAX_TRACKED_CORRIDORS = 32

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
    # A browser cannot read a custom response header on a cross-origin
    # request unless the server names it here. The binary layer carries its
    # entire self-description in X-Layer-* -- shape, endianness, effective
    # resolution, value range -- so without this line the 3-D client reads
    # `undefined` for every one of them, and gets no error saying why.
    # X-Series-* is the same contract for /api/illumination-series's binary
    # payload -- it was missing here even though the endpoint set the
    # headers, which is the exact "sets it, but nobody can read it
    # cross-origin" failure this comment already warns about.
    expose_headers=list(BINARY_LAYER_HEADERS) + list(SERIES_HEADERS),
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

# Ceiling on the number of cells /api/layers will serialise in one response.
# The 500x500 production grid at downsample=1 is 250 000 JSON numbers built
# through an object-dtype array, which is both slow and a large response
# nobody asked to be protected from. 65 536 cells is a 256x256 preview --
# plenty for a map overlay -- and the error names the downsample that fits.
# (Round 3 review, L-13.)
MAX_LAYER_CELLS = 65536

# A slice series is (T, H, W) float32 on the wire. At 24 slices the full
# 500x500 grid is 24 MB -- a fine LAN payload and a poor one over anything
# else. 64 MiB is the point past which the caller is asked to decimate
# instead. Like MAX_LAYER_CELLS, the refusal names the number that would fit
# rather than merely saying no.
MAX_SERIES_BYTES = 64 * 1024 * 1024

# MAX_SERIES_BYTES bounds the *response*, computed after downsample -- but
# build_shadow_series's real (spice_horizon) path builds n_slices full-
# resolution float64 grids BEFORE anything downsamples them, same as
# _check_cube_budget's cube below. A caller can ask for downsample=50 and
# still force ~2 GB of allocation at n_slices=1000: 1000 * 500*500*8 bytes,
# while the downsampled-response check above sees only 1000*10*10*4 bytes
# and passes it. Same 512 MiB precedent as MAX_PLAN_4D_CUBE_BYTES, since the
# shape of the risk is identical -- an anonymous GET forcing a large,
# unauthenticated allocation.
MAX_SERIES_WORKING_BYTES = 512 * 1024 * 1024


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
    """Grids for endpoints that take no Request. Same source as _active_grids.

    Answers 503, matching _active_grids. It used to answer 400 for the
    identical server state, so /api/plan-multi and /api/compare called
    "grids not loaded" a caller error while /api/plan called it a service
    condition, and no client could handle "not ready" uniformly. Review #7
    unified the grid STORE; this unifies the status contract.
    (Round 2 review, L-4.)
    """
    grids = _current_grids()
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
    # With an epoch the backend computes comm_minutes_remaining itself, from
    # the rover's cell and the Earth's position, when the caller did not
    # supply one. (A4.)
    utc: Optional[str] = Field(
        default=None,
        description=(
            "UTC instant of this telemetry, e.g. '2026-09-03T12:00:00'. When "
            "given and the horizon cube is cached, comm_minutes_remaining is "
            "computed from the Earth's geometry unless state already carries "
            "it; the computed window is reported as comm_window either way."
        ),
    )

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
    # Illumination is a function of time, so a time-expanded plan needs an
    # epoch to be a plan at all. Without one the shadow field is held
    # constant across slices and the response says so in `shadow_model`.
    # (Round 3 review, M-1.)
    start_utc: Optional[str] = Field(
        default=None,
        description=(
            "UTC instant the first time slice begins, e.g. "
            "'2026-09-01T00:00:00'. Required for time-varying illumination; "
            "without it the shadow field is static and the response reports "
            "shadow_model='static'."
        ),
    )
    # The planner carries the battery in its state: a route is refused where
    # it would drain below the rover's reserve (soc_min_pct) or keep the rover
    # in continuous shadow longer than h_max_shadow_h. Where the rover starts
    # on that scale is the caller's to say; a full battery is the default.
    initial_soc_pct: float = Field(
        default=1.0,
        gt=0.0,
        le=1.0,
        description=(
            "State of charge at the first slice as a fraction of e_cap_wh "
            "(0-1]. The route must keep the battery above the rover's "
            "soc_min_pct reserve; starting under the reserve is allowed only "
            "where waiting in sunlight can charge it back."
        ),
    )
    # VIPER's teleoperation rule: drive only with a direct-to-Earth link.
    # Off by default -- the Earth field is always reported when it can be
    # computed; this makes it a constraint. (A4.)
    require_earth_visibility: bool = Field(
        default=False,
        description=(
            "Refuse any move that arrives in a cell with no line of sight to "
            "Earth at the arrival slice (waiting is never restricted). Needs "
            "start_utc and the horizon cube; without them the request is a "
            "422 rather than a silently unconstrained plan."
        ),
    )
    # VIPER's leg rule: at every moment the rover must still be able to
    # reach a safe haven before the Earth sets on it. The margin is always
    # reported when it can be computed; this makes it a constraint. (A1.)
    require_safe_haven: bool = Field(
        default=False,
        description=(
            "Refuse any state (move or wait) from which the nearest safe "
            "haven could no longer be reached before the cell loses its Earth "
            "link. Needs start_utc, the horizon cube and the kernels; without "
            "them the request is a 422 rather than a silently unconstrained "
            "plan."
        ),
    )


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


# A (row, col, slice) planner state, as /api/plan-4d publishes path_states.
PlannerState = conlist(int, min_length=3, max_length=3)


class PerturbationOverrides(BaseModel):
    """Any of SHERPA's distribution parameters, overriding the defaults in
    stress_test.SHERPA_DEFAULTS. Sigmas are fractions except the delay (h)."""

    start_delay_sigma_h: Optional[float] = Field(default=None, ge=0.0, le=48.0)
    initial_soc_sigma: Optional[float] = Field(default=None, ge=0.0, le=0.9)
    power_draw_sigma: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    speed_sigma: Optional[float] = Field(default=None, ge=0.0, le=0.9)
    speed_multiplier_floor: Optional[float] = Field(default=None, gt=0.0, le=1.0)
    z_max: Optional[float] = Field(default=None, gt=0.0, le=6.0)
    dsn_outage_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    dsn_outage_mean_h: Optional[float] = Field(default=None, ge=0.0, le=336.0)
    sep_event_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    sep_event_mean_h: Optional[float] = Field(default=None, ge=0.0, le=336.0)


class StressTestRequest(BaseModel):
    """SHERPA's Monte Carlo traverse evaluation of a /api/plan-4d route (B5).

    The environment is rebuilt exactly as the plan saw it, so the fields that
    shaped the plan come back with the route: ``rover_id``, ``coarsen``,
    ``slice_hours`` (the plan response echoes it), ``start_utc`` and
    ``initial_soc_pct``.
    """

    path_states: list[PlannerState] = Field(
        ...,
        min_length=1,
        description="path_states from the /api/plan-4d response: [row, col, slice] on the coarse grid.",
    )
    rover_id: str = DEFAULT_ROVER_ID
    coarsen: int = Field(default=4, ge=1, le=16)
    slice_hours: float = Field(
        ..., gt=0.0, le=24.0, description="The plan's slice length (its response's slice_hours)."
    )
    start_utc: Optional[str] = Field(
        default=None,
        description="The plan's epoch. Without it the sky is static and the response says so.",
    )
    initial_soc_pct: float = Field(default=1.0, gt=0.0, le=1.0)
    n_runs: int = Field(default=1000, ge=1, le=20000)
    seed: int = Field(default=0, ge=0)
    perturbations: Optional[PerturbationOverrides] = None
    label: Optional[str] = Field(default=None, max_length=80)
    n_bins: int = Field(default=20, ge=5, le=100)


class DemUncertaintyRequest(BaseModel):
    """The DEM-clone band of a /api/plan-4d route (B3).

    The route is priced once per NASA DEM clone -- the clone's slopes, the
    clone's horizon -- with every SHERPA uncertainty at its nominal value,
    so the band is the DEM's alone; ``with_sherpa`` adds ``n_runs``
    SHERPA-perturbed runs per clone on top. The environment fields are the
    plan's, as for /api/stress-test.
    """

    path_states: list[PlannerState] = Field(
        ...,
        min_length=2,
        description="path_states from the /api/plan-4d response: [row, col, slice] on the coarse grid.",
    )
    rover_id: str = DEFAULT_ROVER_ID
    coarsen: int = Field(default=4, ge=1, le=16)
    slice_hours: float = Field(..., gt=0.0, le=24.0)
    start_utc: Optional[str] = Field(
        default=None,
        description="The plan's epoch. Without it the sky is static and the response says so.",
    )
    initial_soc_pct: float = Field(default=1.0, gt=0.0, le=1.0)
    n_clones: Optional[int] = Field(
        default=None,
        ge=1,
        le=N_PGDA_CLONES,
        description="How many cached clones to use (the first n); default all.",
    )
    with_sherpa: bool = False
    n_runs: int = Field(default=200, ge=1, le=5000, description="SHERPA runs per clone when with_sherpa.")
    seed: int = Field(default=0, ge=0)
    perturbations: Optional[PerturbationOverrides] = None
    label: Optional[str] = Field(default=None, max_length=80)


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
def get_cell_telemetry(
    row: int,
    col: int,
    request: Request,
    rover_id: Optional[str] = Query(
        default=None,
        description=(
            "Rover whose limits and weights explain this cell. Defaults to "
            "the loaded grid's rover, which is what every other planning "
            "endpoint would NOT have used when planning for a different "
            "profile."
        ),
    ),
    start_utc: Optional[str] = Query(
        default=None,
        description=(
            "Epoch for the safe haven verdict (A1): the map is computed over "
            "one synodic month from here. Without it `safe_haven` is null."
        ),
    ),
):
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

    # Explaining a cell with a different rover than the route was planned
    # for makes the "why this route?" tooltip disagree with the route.
    # Base grids carry only default_rover_id, so without the parameter
    # this always answered for lpr_1. (Round 2 review, L-10.)
    rover = get_rover(
        rover_id or metadata.get("rover_id", metadata.get("default_rover_id"))
    )
    thermal_min = grids.get("thermal_min")
    context = PlanContext(
        slope=np.asarray(grids["slope"], dtype=np.float64),
        thermal=np.asarray(grids["thermal"], dtype=np.float64),
        shadow_ratio=np.asarray(grids["shadow_ratio"], dtype=np.float64),
        traversable=np.asarray(grids["traversable"], dtype=bool),
        resolution_m=resolution_m,
        rover=rover,
        thermal_min=(
            None if thermal_min is None
            else np.asarray(thermal_min, dtype=np.float64)
        ),
    )
    cost_map = default_cost_map(
        rover,
        metadata.get("cost_weights"),
        metadata.get("layer_validity"),
    )
    breakdown = cost_map.explain(row, col, context)

    # Safe haven (A1): is this cell one, and how far is the nearest? Cached
    # per (grids, rover, epoch) so a hover does not rebuild the month.
    haven_layers, haven_tts, haven_info = safe_haven_for_grids(
        grids, rover["id"], start_utc
    )
    if haven_layers is None:
        safe_haven = None
    else:
        tts_value = float(haven_tts[row, col])
        safe_haven = {
            "is_safe_haven": bool(haven_layers["safe_haven"][row, col]),
            "max_dark_hours_without_dte_h": round(
                float(haven_layers["max_dark_hours_without_dte"][row, col]), 4
            ),
            "earth_below_hours": round(
                float(haven_layers["earth_below_hours"][row, col]), 4
            ),
            "time_to_safe_haven_h": (
                round(tts_value, 4) if math.isfinite(tts_value) else None
            ),
            "h_max_shadow_h": float(haven_info["h_max_shadow_h"]),
        }

    return {
        "row": row,
        "col": col,
        "lon": round(lon, 6),
        "lat": round(lat, 6),
        "altitude_m": _read_grid_value(grids["elevation"], row, col),
        # Both ends of the cell's temperature range. `thermal_c` is the
        # annual peak, as before; `thermal_min_c` is the cold-end
        # equilibrium the traversability gate actually tests.
        # (Round 4 review, H-3.)
        "thermal_c": _read_grid_value(grids["thermal"], row, col),
        "thermal_min_c": (
            None if grids.get("thermal_min") is None
            else _read_grid_value(grids["thermal_min"], row, col)
        ),
        "resolution_m": resolution_m,
        "span_km": round((rows * resolution_m) / 1000.0, 4),
        "cost_breakdown": breakdown,
        "layer_validity": metadata.get("layer_validity", {}),
        # The safe haven verdict for this cell and the driving hours to the
        # nearest one (None: unreachable). null with the reason in
        # safe_haven_model when no epoch, horizon cube or kernels.
        "safe_haven": safe_haven,
        "safe_haven_model": haven_info,
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
            # Travel time and energy from the grade actually driven, the
            # same geometry the planner gated on. (Round 4 review, L-4.)
            elevation_grid=grids_for_plan["elevation"],
        )
        summary = summarize_simulation(states, rover)
    except Exception:
        logger.error("Simulation failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal simulation error.")

    # A stranded simulation stops partway, so the corridor is built from the
    # prefix the rover can actually execute. Publishing the full route beside
    # a truncated geojson put two different journeys in one response --
    # measured: a 60-waypoint corridor and 295 m of astar_metrics next to an
    # 18-point geojson and 85 m of summary -- and the corridor is the
    # contract a local planner executes, so it is the one that must not
    # describe a drive that ends in a dead battery. (Round 4 review, M-3.)
    planned_pixels = list(astar_result["path_pixels"])
    executable_pixels = planned_pixels[: len(states)] if states else planned_pixels
    stranded = bool(summary.get("stranded"))
    execution = {
        "stranded": stranded,
        "planned_nodes": len(planned_pixels),
        "executable_nodes": len(executable_pixels),
        "truncated": len(executable_pixels) < len(planned_pixels),
        "reason": (
            "battery could not be recovered within one lunar day at the "
            "stranding cell; the corridor covers only the executable prefix"
            if stranded
            else None
        ),
    }

    try:
        corridor_obj = build_corridor(
            executable_pixels,
            grids_for_plan,
            rover,
            elevation=grids_for_plan["elevation"],
        )
        corridor_payload = corridor_obj.model_dump()
    except (ValueError, KeyError) as exc:
        logger.warning("Corridor generation skipped: %s", exc)
        corridor_obj = None
        corridor_payload = None

    corridor_id = uuid4().hex[:12] if corridor_obj is not None else None
    if corridor_payload is not None:
        corridor_payload["corridor_id"] = corridor_id

    try:
        response = build_plan_response(
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
            execution=execution,
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

    # NASA's DEM clones, when cached: the route's passability across them
    # (B3). Absent, not null, without the cache.
    uncertainty_block = _route_uncertainty_block(grids_for_plan, req.rover_id, planned_pixels, 1)
    if uncertainty_block is not None:
        response["uncertainty"] = uncertainty_block

    # Published only once the response the caller receives is fully built.
    # Assigning mid-request meant a plan whose serialisation then failed
    # (422/500) still replaced the corridor /api/pose judges against with
    # one the caller never saw. The id lets a pose report WHICH corridor it
    # was judged against -- endpoints are sync defs on a threadpool, so two
    # concurrent /api/plan calls race for this single slot, and without an
    # identity the loser's poses were scored against the winner's route
    # undetectably. (Round 2 review, L-6.)
    if corridor_obj is not None:
        request.app.state.active_corridor = corridor_obj
        request.app.state.active_corridor_id = corridor_id
        request.app.state.active_corridor_rover_id = req.rover_id
        registry = request.app.state.corridors
        registry[corridor_id] = {
            "corridor": corridor_obj,
            "rover_id": req.rover_id,
        }
        # Bounded: a long-running process planning continuously must not
        # accumulate corridors forever. Oldest first -- dicts preserve
        # insertion order.
        while len(registry) > MAX_TRACKED_CORRIDORS:
            registry.pop(next(iter(registry)))

    return response


def _comm_window_or_none(
    grids: dict | None, row: int, col: int, utc: str | None
) -> dict[str, Any] | None:
    """The Earth link at a cell and instant, or None when it cannot be known.

    None covers "no epoch", "no grids" and "no horizon cube" alike; the
    trigger evaluator then reports comm_window as skipped, which is the
    honest answer. A cell outside the grid is the caller's mistake and a
    422; any other failure (a missing kernel, say) is logged and treated
    as unknown rather than allowed to take the endpoint down.
    """
    if not utc or grids is None:
        return None
    try:
        return comm_window_from_metadata(grids["metadata"], int(row), int(col), utc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("comm window unavailable: %s", exc)
        return None


def _state_with_comm(
    state: dict[str, float], window: dict[str, Any] | None
) -> dict[str, float]:
    """Fill comm_minutes_remaining from the computed window unless the
    caller supplied it: telemetry from the radio beats geometry from the
    map, but geometry beats nothing at all."""
    merged = dict(state)
    if window is not None and "comm_minutes_remaining" not in merged:
        merged["comm_minutes_remaining"] = float(window["trigger_minutes_remaining"])
    return merged


@app.post("/api/replan")
def replan(req: ReplanRequest, request: Request):
    """Re-plan from the rover's current position when a trigger fires."""
    window = None
    if req.utc:
        grids = _current_grids()
        if grids is not None:
            row, col = _to_pixel(req.current, "current", grids["metadata"])
            window = _comm_window_or_none(grids, row, col, req.utc)
    state = _state_with_comm(req.state, window)
    evaluation = evaluate_triggers_detailed(state, get_rover(req.rover_id))
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
            "comm_window": window,
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
        # The Earth link the trigger was judged against, when it was
        # computed here rather than supplied. (A4.)
        "comm_window": window,
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

    corridor_id: Optional[str] = Field(
        default=None,
        description=(
            "Judge this pose against a SPECIFIC corridor rather than "
            "whichever plan ran most recently -- echo back the corridor_id "
            "from the /api/plan response that produced the route this rover "
            "is driving. Two concurrent plans otherwise race for one slot."
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
    if req.corridor_id is not None:
        entry = request.app.state.corridors.get(req.corridor_id)
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"corridor_id {req.corridor_id!r} is not known to this "
                    "process. Corridors live only in memory and only the most "
                    f"recent {MAX_TRACKED_CORRIDORS} are retained; re-plan to "
                    "get a fresh one."
                ),
            )
        corridor = entry["corridor"]
        corridor_id = req.corridor_id
        corridor_rover_id = entry["rover_id"]
    else:
        corridor = request.app.state.active_corridor
        corridor_id = getattr(request.app.state, "active_corridor_id", None)
        corridor_rover_id = getattr(
            request.app.state, "active_corridor_rover_id", None
        )
    if corridor is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "No active corridor. POST /api/plan first -- a pose is only "
                "meaningful against the route the rover is driving."
            ),
        )

    # A pose carries everything the Earth-link geometry needs -- where the
    # rover is and when -- so the comm-window trigger no longer waits for a
    # hand-fed number. A pose off the grid simply gets no window. (A4.)
    window = None
    grids = _current_grids()
    if grids is not None:
        try:
            row, col = map_xy_to_pixel(req.pose.x_m, req.pose.y_m, grids["metadata"])
        except ValueError:
            row = col = None
        if row is not None:
            window = _comm_window_or_none(grids, row, col, req.pose.timestamp_utc)
    state = _state_with_comm(req.state, window)

    result = evaluate_pose(
        req.pose,
        corridor,
        state,
        previous_along_track_m=req.previous_along_track_m,
        rover=get_rover(corridor_rover_id) if corridor_rover_id else None,
    )
    return {
        "corridor_id": corridor_id,
        "corridor_rover_id": corridor_rover_id,
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
        "comm_window": window,
    }


@app.get("/api/comm-window")
def comm_window_endpoint(
    row: int = Query(..., ge=0),
    col: int = Query(..., ge=0),
    utc: str = Query(..., description="UTC instant, e.g. '2026-09-03T12:00:00'"),
    step_minutes: float = Query(30.0, gt=0.0, le=1440.0),
    max_hours: float = Query(336.0, gt=0.0, le=24.0 * 60.0),
):
    """When does this cell's direct-to-Earth link next open or close?

    ``trigger_minutes_remaining`` is the number ``POST /api/replan`` and
    ``POST /api/pose`` feed to the comm-window trigger; the rest says why.
    Needs the horizon cube beside the processed grids (409 without it).
    """
    grids = _get_grids()
    try:
        window = comm_window_from_metadata(
            grids["metadata"], row, col, utc, step_minutes=step_minutes, max_hours=max_hours
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if window is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "No horizon cube beside the processed grids, so Earth "
                "visibility cannot be computed; run "
                "scripts/build_horizon_cache.py and reload."
            ),
        )
    return window


def _earthset_lookahead(
    metadata: dict,
    start_utc: str,
    n_slices: int,
    slice_hours: float,
    coarsen: int,
) -> tuple[np.ndarray | None, dict[str, Any]]:
    """Hours past the plan's last slice until each coarse cell loses its
    Earth link, or ``None`` (open-ended) with the reason.

    The Earth sets on a scale of days and a plan spans hours, so the
    deadline that matters usually lies BEYOND the horizon; without this the
    rule would only ever bind in the last hours before an Earthset that
    happened to fall inside the window. (A1.)
    """
    from datetime import timedelta

    cache_path = horizon_cache_path(metadata)
    if cache_path is None:
        return None, {
            "model": "unavailable",
            "reason": "no horizon cube; the link is treated as open-ended past the horizon",
        }
    try:
        end = _parse_start_utc(start_utc) + timedelta(
            hours=float(slice_hours) * (int(n_slices) - 1)
        )
        fine = earthset_after_horizon_hours(
            np.load(cache_path, mmap_mode="r"),
            metadata,
            end.strftime("%Y-%m-%dT%H:%M:%S"),
            lookahead_hours=DEFAULT_EARTHSET_LOOKAHEAD_HOURS,
            step_hours=1.0,
        )
    except Exception as exc:
        logger.warning("Earthset lookahead unavailable: %s", exc)
        return None, {
            "model": "unavailable",
            "reason": f"Earthset lookahead unavailable ({exc}); the link is treated as open-ended past the horizon",
        }
    return block_min(fine, coarsen), {
        "model": "spice_horizon",
        "from_utc": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lookahead_hours": DEFAULT_EARTHSET_LOOKAHEAD_HOURS,
        "step_hours": 1.0,
    }


@dataclass(frozen=True)
class _CoarseGeometry:
    """The planner's grid at a coarsen factor: what /api/plan-4d searches on
    and what /api/stress-test replays on."""

    traversable: np.ndarray
    slope: np.ndarray
    elevation: np.ndarray
    resolution_m: float


def _coarse_geometry(grids_for_plan: dict, coarsen: int) -> _CoarseGeometry:
    """Block-reduce the rover's grids the way the 4-D planner does.

    Traversability is the conservative AND, slope the block maximum, and the
    elevation the block CENTRE -- not the mean: path_pixels publishes block
    centres as waypoints, so the geometry a rover meets driving between two
    of them is the geometry at those centres. A block mean smooths the
    terrain -- measured at coarsen=4 it left the step-slope gate rejecting
    nothing at all where the fine gate rejected 1 894 edges. (Round 4
    review, L-11.)
    """
    metadata = grids_for_plan["metadata"]
    rows, cols = int(metadata["shape"][0]), int(metadata["shape"][1])
    if rows % coarsen or cols % coarsen:
        raise HTTPException(
            status_code=422,
            detail=f"grid {rows}x{cols} is not divisible by coarsen={coarsen}",
        )
    return _CoarseGeometry(
        traversable=coarsen_traversable(grids_for_plan["traversable"], coarsen),
        slope=coarsen_grid(grids_for_plan["slope"], coarsen, how="max"),
        elevation=coarsen_grid(grids_for_plan["elevation"], coarsen, how="center"),
        resolution_m=float(metadata["resolution_m"]) * coarsen,
    )


def _coarse_time_to_haven(
    grids_for_plan: dict,
    rover_id: str,
    start_utc: str | None,
    rover: dict,
    geometry: _CoarseGeometry,
    coarsen: int,
) -> tuple[np.ndarray | None, np.ndarray | None, dict[str, Any]]:
    """``(coarse_safe, coarse_tts, info)``: the month's safe haven map on
    the fine grid (cached), coarsened like traversability (a block is a
    haven only if every fine cell is), and the driving hours to the nearest
    haven on the planner's own grid. ``(None, None, info)`` with the reason
    when the map is unavailable. (A1.)
    """
    haven_layers, _fine_tts, haven_info = safe_haven_for_grids(
        grids_for_plan, rover_id, start_utc
    )
    if haven_layers is None:
        return None, None, dict(haven_info)
    coarse_safe = coarsen_traversable(haven_layers["safe_haven"], coarsen)
    coarse_tts = time_to_safe_haven_hours(
        coarse_safe,
        geometry.traversable,
        geometry.elevation,
        geometry.slope,
        geometry.resolution_m,
        rover,
    )
    return coarse_safe, coarse_tts, {
        **haven_info,
        "coarse_safe_haven_cells": int(coarse_safe.sum()),
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
    geometry = _coarse_geometry(grids_for_plan, req.coarsen)
    coarse_traversable = geometry.traversable
    coarse_slope = geometry.slope
    coarse_elevation = geometry.elevation
    effective_resolution_m = geometry.resolution_m

    # coarsen_traversable is conservative (AND over every fine cell in a
    # block), so a coarse cell it marks passable is guaranteed finite-cost:
    # every fine cell inside satisfies slope <= slope_max_deg, which is the
    # only source of infinite cost in the coarse cube (see SlopeLayer /
    # f_slope). bfs_move_count is therefore both a reachability check AND an
    # exact distance bound for the planner that follows -- no separate
    # "usable" mask is needed. (Faz 1-2-3 review, H1/H3.)
    # Reachability through the graph the planner will ACTUALLY search --
    # cells AND the hard edge gates. The ungated count called routes reachable
    # that the cross-slope limit closes, so the planner then reported them as
    # horizon-limited however many slices it was given. (Round 4 review, H-2.)
    move_count = gated_move_count(
        coarse_traversable,
        coarse_start,
        coarse_goal,
        coarse_elevation,
        effective_resolution_m,
        rover,
    )
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
                f"start {start} and goal {goal} are not connected at "
                f"coarsen={req.coarsen} once {rover['name']}'s "
                f"{rover['slope_max_deg']:g} deg step-slope and "
                f"{rover['slope_lateral_max_deg']:g} deg roll-over limits are "
                "applied to each edge: the terrain between them splits into "
                "regions this rover cannot cross between. Lower coarsen, "
                "choose a different pair, or use a rover with a higher "
                "roll-over limit. No time horizon would have helped."
            ),
        )

    # Size the time slice to a real cell crossing unless the caller pinned it.
    # (Faz 3 review, C1.)
    if req.slice_hours is None:
        # The FINE slope distribution over a COARSE cell's length. Passing the
        # how="max" coarsened grid made this a median of block maxima --
        # biased high, and biased by the coarsen factor, which has nothing to
        # do with how long a crossing takes. (Round 4 review, L-7.)
        slice_hours = auto_slice_hours(
            grids_for_plan["slope"],
            grids_for_plan["traversable"],
            resolution_m=effective_resolution_m,
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
        diag_m = effective_resolution_m * math.sqrt(2.0)
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

    # A time-expanded plan whose environment never changes cannot express
    # the one decision it exists for. build_shadow_series produces the real
    # per-slice illumination when a horizon cache and an epoch are available,
    # and reports honestly when it cannot. (Round 3 review, M-1.)
    base_shadow = np.asarray(grids_for_plan["shadow_ratio"], dtype=np.float64)
    shadow_series, shadow_provenance = build_shadow_series(
        base_shadow, metadata, n_slices, slice_hours, req.start_utc
    )
    illum_series = [1.0 - snapshot for snapshot in shadow_series]

    cost_cube = build_cost_cube(
        grids_for_plan,
        shadow_series,
        rover,
        weights_dict,
        coarsen=req.coarsen,
        # The thermal state is integrated across slices with the regolith
        # time constant, so the cube needs to know how long a slice is.
        # (Round 4 review, H-1 and H-3.)
        slice_hours=slice_hours,
    )
    wait_cube = build_wait_cost_cube(
        illum_series, rover, slice_hours, weights_dict, coarsen=req.coarsen
    )
    # The illumination each label is exposed to, on the planner's own grid:
    # this is what drains or charges the battery and what counts as shadow
    # time, so it has to be the same field the cubes were built from.
    shadow_cube = np.stack(
        [coarsen_grid(snapshot, req.coarsen) for snapshot in shadow_series], axis=0
    )

    # Direct-to-Earth visibility per slice, on the planner's grid. Always
    # reported when it can be computed; enforced on request. Coarsened the
    # way traversability is -- a coarse cell has a link only if every fine
    # cell in it does -- so the rule is conservative at the block edges.
    # (A4.)
    earth_base = grids_for_plan.get("earth_visibility")
    earth_series, earth_provenance = build_earth_visibility_series(
        None if earth_base is None else np.asarray(earth_base, dtype=np.float64),
        metadata,
        n_slices,
        slice_hours,
        req.start_utc,
    )
    if earth_series:
        earth_cube = np.stack(
            [
                coarsen_traversable(np.asarray(snapshot) > 0.5, req.coarsen)
                for snapshot in earth_series
            ],
            axis=0,
        )
    else:
        earth_cube = None
    if req.require_earth_visibility and earth_cube is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "require_earth_visibility needs an Earth visibility field and "
                f"none could be computed: {earth_provenance.get('reason')}"
            ),
        )

    # Safe haven (A1): the month's map on the fine grid (cached), coarsened
    # like traversability (a block is a haven only if every fine cell is),
    # the driving time to the nearest haven on the planner's own grid, and
    # the hours of Earth link left per (slice, cell) -- inside the horizon
    # from the Earth cube, beyond it from a 14-day lookahead.
    deadline_cube = None
    coarse_safe, coarse_tts, haven_info = _coarse_time_to_haven(
        grids_for_plan, req.rover_id, req.start_utc, rover, geometry, req.coarsen
    )
    if coarse_safe is None:
        haven_provenance: dict[str, Any] = dict(haven_info)
    elif earth_cube is None or not earth_provenance.get("time_varying"):
        haven_provenance = {
            "model": "unavailable",
            "reason": (
                "the Earthset deadline needs the time-varying Earth visibility "
                f"series and it is {earth_provenance.get('model')}: "
                f"{earth_provenance.get('reason', 'no reason given')}"
            ),
        }
    else:
        after_end, lookahead = _earthset_lookahead(
            metadata, req.start_utc, n_slices, slice_hours, req.coarsen
        )
        deadline_cube = hours_until_earthset_cube(earth_cube, slice_hours, after_end)
        haven_provenance = {**haven_info, "earthset_lookahead": lookahead}
    if req.require_safe_haven and deadline_cube is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "require_safe_haven needs a safe haven map and an Earthset "
                f"deadline and they could not be computed: "
                f"{haven_provenance.get('reason')}"
            ),
        )

    result = astar_4d(
        cost_cube,
        wait_cube,
        coarse_traversable,
        start=coarse_start,
        goal=coarse_goal,
        resolution_m=effective_resolution_m,
        slice_hours=slice_hours,
        rover=rover,
        slope_grid=coarse_slope,
        # Same hard edge constraints the 2-D planner enforces; without the
        # elevation the 4-D planner could not evaluate either of them and
        # the two planners disagreed about which edges are safe.
        # (Round 3 review, H-1 and H-2.)
        elevation_grid=coarse_elevation,
        shadow_cube=shadow_cube,
        initial_soc_frac=req.initial_soc_pct,
        earth_visible_cube=earth_cube,
        require_earth_visibility=req.require_earth_visibility,
        time_to_haven_hours=coarse_tts,
        hours_until_earthset_cube=deadline_cube,
        require_safe_haven=req.require_safe_haven,
    )
    if result["error"]:
        # move_count already accounted for the edge gates, so a failure here
        # is a horizon, envelope or cost problem rather than a geometric one
        # -- and the planner's own message now names which. (Round 4 review,
        # H-2.)
        detail = (
            f"{result['error']} (the shortest gated coarse route needs at "
            f"least {move_count} moves at {n_slices} slices of "
            f"{slice_hours:.4f} h)"
        )
        # Say when the site itself is dark: a refusal at a lunar-night epoch
        # used to read as a slope problem. The first lit slice, if any, is
        # the number a caller needs to pick a horizon or an epoch.
        if shadow_provenance.get("time_varying"):
            lit_fraction = [float(np.mean(1.0 - snapshot)) for snapshot in shadow_series]
            first_lit = next(
                (index for index, value in enumerate(lit_fraction) if value > 0.01),
                None,
            )
            horizon_h = n_slices * slice_hours
            if first_lit is None:
                detail += (
                    f" The site is in darkness for the entire {horizon_h:.1f} h "
                    "horizon from start_utc: no slice is lit, so the route must "
                    "run on battery, or start at a lit epoch."
                )
            elif first_lit > 0:
                detail += (
                    f" The site is dark until {first_lit * slice_hours:.1f} h "
                    f"into the {horizon_h:.1f} h horizon."
                )
        # Same courtesy for the Earth: when the rule closed the route, say
        # whether the link ever opens anywhere in the window.
        if req.require_earth_visibility and earth_cube is not None:
            linked = [float(np.mean(snapshot)) for snapshot in earth_cube]
            first_linked = next(
                (index for index, value in enumerate(linked) if value > 0.0), None
            )
            horizon_h = n_slices * slice_hours
            if first_linked is None:
                detail += (
                    f" No cell has Earth visibility at any slice of the "
                    f"{horizon_h:.1f} h horizon from start_utc, so no move is "
                    "allowed under require_earth_visibility."
                )
            elif first_linked > 0:
                detail += (
                    f" Earth visibility opens {first_linked * slice_hours:.1f} h "
                    f"into the {horizon_h:.1f} h horizon."
                )
        # And for the haven rule: how many havens the coarse grid has, and
        # the start's own margin, which is the number a caller needs to pick
        # an earlier epoch or a closer goal.
        if req.require_safe_haven and deadline_cube is not None:
            start_tts = float(coarse_tts[coarse_start])
            start_deadline = float(deadline_cube[0][coarse_start])
            detail += (
                f" Safe-haven rule: {int(coarse_safe.sum())} coarse cells are "
                f"havens for {rover['name']} ({float(rover['h_max_shadow_h']):g} h "
                "endurance); the start block is "
                + ("unreachable from any haven" if not math.isfinite(start_tts)
                   else f"{start_tts:.2f} h from the nearest")
                + " with "
                + ("no Earthset in sight" if not math.isfinite(start_deadline)
                   else f"{start_deadline:.1f} h of Earth link left")
                + "."
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
    # SHERPA's margins along the route (A1): time-to-sun-shadow,
    # time-to-DSN-shadow, time-to-0-SOC. None where open-ended or unknown.
    e_cap_wh = float(rover["e_cap_wh"])
    metrics.update(
        route_margins(
            result["path_states"],
            [pct / 100.0 * e_cap_wh for pct in result["path_battery_pct"]],
            shadow_cube,
            deadline_cube,
            slice_hours,
            rover,
        )
    )

    return {
        "path_pixels": fine_pixels,
        "path_pixels_coarse": result["path_pixels"],
        "path_states": result["path_states"],
        # One entry per state: the battery the planner accounted for and the
        # continuous shadow the rover had accrued on arrival there.
        "path_battery_pct": result["path_battery_pct"],
        "path_dark_hours": result["path_dark_hours"],
        # One entry per state: whether the cell saw the Earth at that slice.
        # None when the field was unavailable (see earth_model.reason).
        "path_earth_visible": result["path_earth_visible"],
        "metrics": metrics,
        # Whether the cube this plan solved actually varied with time, and
        # why not when it did not. A caller reading wait_steps needs this to
        # know whether a zero means "waiting did not help" or "waiting could
        # not have helped". (Round 3 review, M-1.)
        "shadow_model": shadow_provenance,
        # Same three-way honesty for the Earth field: spice_horizon, static
        # (the long-run layer) or unavailable, with the reason. (A4.)
        "earth_model": earth_provenance,
        # The safe haven map's provenance (spice_horizon / unavailable +
        # reason) and, per state, the driving hours to the nearest haven,
        # the Earth link left and their difference. (A1.)
        "safe_haven_model": haven_provenance,
        "path_time_to_haven_h": result["path_time_to_haven_h"],
        "path_hours_until_earthset": result["path_hours_until_earthset"],
        "path_haven_margin_h": result["path_haven_margin_h"],
        "n_slices": n_slices,
        "slice_hours": slice_hours,
        "slice_hours_source": slice_hours_source,
        "horizon_hours": n_slices * slice_hours,
        "coarsen": req.coarsen,
        "effective_resolution_m": effective_resolution_m,
        "rover_id": req.rover_id,
        # NASA's DEM clones, when cached: the route's passability across
        # them on the planner's own grid (B3). Absent without the cache.
        **(
            {"uncertainty": block}
            if (
                block := _route_uncertainty_block(
                    grids_for_plan, req.rover_id, result["path_pixels"], req.coarsen
                )
            )
            is not None
            else {}
        ),
    }


#: The route-local sky may not run past this many slices, lookahead included.
MAX_STRESS_TEST_SLICES = 60_000


def _stress_test_sky(
    grids_for_plan: dict,
    rover: dict,
    req: "StressTestRequest",
    legs,
    perturbations: Perturbations,
    geometry: _CoarseGeometry,
) -> tuple[RouteSky, dict[str, Any], dict[str, Any], float]:
    """``(sky, sky_model, safe_haven_model, sky_ms)`` for the route.

    The sky is built for the route's cells only, over a horizon long enough
    for the slowest sampled run (planned duration over the speed floor, plus
    the largest start delay and the injected outages) and, for the Earth,
    the 14-day Earthset lookahead -- so no run outlives it and the deadline
    is exact rather than open-ended. Time-varying needs an epoch, the
    horizon cube and the kernels; otherwise the long-run layers are held
    constant and ``sky_model`` says why, as /api/plan-4d does.
    """
    import time as _time

    t0 = _time.perf_counter()
    metadata = grids_for_plan["metadata"]
    p = perturbations
    outage_pad = 0.0
    if p.dsn_outage_probability > 0.0:
        outage_pad += 2.5 * p.dsn_outage_mean_h
    if p.sep_event_probability > 0.0:
        outage_pad += 2.5 * p.sep_event_mean_h
    longest_h = (
        legs.planned_duration_h / max(p.speed_multiplier_floor, 1e-3)
        + p.z_max * p.start_delay_sigma_h
        + outage_pad
    )
    n_extended = int(math.ceil(longest_h / req.slice_hours)) + 2
    lookahead_slices = int(math.ceil(DEFAULT_EARTHSET_LOOKAHEAD_HOURS / req.slice_hours))
    n_total = n_extended + lookahead_slices
    if n_total > MAX_STRESS_TEST_SLICES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"the stress test needs {n_total} slices of {req.slice_hours:.4f} h "
                f"to cover the slowest run plus the Earthset lookahead, over the "
                f"{MAX_STRESS_TEST_SLICES} cap; raise slice_hours."
            ),
        )
    cells = [(int(r), int(c)) for r, c in legs.cells]
    rows = np.asarray([r for r, _ in cells])
    cols = np.asarray([c for _, c in cells])

    def _static(reason: str) -> tuple[RouteSky, dict[str, Any], dict[str, Any], float]:
        base = coarsen_grid(np.asarray(grids_for_plan["shadow_ratio"], dtype=np.float64), req.coarsen)
        shadow = np.tile(base[rows, cols], (n_extended, 1))
        earth_base = grids_for_plan.get("earth_visibility")
        earth = None
        if earth_base is not None:
            linked = coarsen_traversable(np.asarray(earth_base, dtype=np.float64) > 0.5, req.coarsen)
            earth = np.tile(linked[rows, cols], (n_extended, 1))
        sky = RouteSky(shadow, earth, None, None, req.slice_hours, time_varying=False)
        sky_model = {
            "model": "static",
            "time_varying": False,
            "reason": reason,
            "n_slices_extended": n_extended,
            "horizon_hours_extended": round(n_extended * req.slice_hours, 4),
        }
        haven_model = {
            "model": "unavailable",
            "reason": "the safe haven fields need the time-varying sky: " + reason,
        }
        return sky, sky_model, haven_model, (_time.perf_counter() - t0) * 1000.0

    if req.start_utc is None:
        return _static(
            "no start epoch given; illumination is a function of time and cannot "
            "vary without one"
        )
    cache_path = horizon_cache_path(metadata)
    if cache_path is None:
        return _static(
            "no horizon_map.npy beside the processed grids; run "
            "scripts/build_horizon_cache.py to enable time-varying shadow"
        )
    try:
        shadow, earth = route_sky_columns(
            np.load(cache_path, mmap_mode="r"),
            metadata,
            cells,
            req.coarsen,
            req.start_utc,
            n_total,
            req.slice_hours,
        )
    except Exception as exc:
        # The same reasoning as build_shadow_series: a missing kernel
        # degrades to the honest static sky rather than a 500.
        return _static(f"real illumination unavailable ({exc})")

    deadline = hours_until_earthset_cube(earth[:, :, None], req.slice_hours)[:, :, 0]
    coarse_safe, coarse_tts, haven_info = _coarse_time_to_haven(
        grids_for_plan, req.rover_id, req.start_utc, rover, geometry, req.coarsen
    )
    tts = None if coarse_tts is None else coarse_tts[rows, cols]
    sky = RouteSky(shadow, earth, deadline, tts, req.slice_hours, time_varying=True)
    sky_model = {
        "model": "spice_horizon",
        "time_varying": True,
        "horizon_cache": cache_path,
        "start_utc": req.start_utc,
        "n_slices_extended": n_extended,
        "horizon_hours_extended": round(n_extended * req.slice_hours, 4),
        "earthset_lookahead_hours": DEFAULT_EARTHSET_LOOKAHEAD_HOURS,
    }
    return sky, sky_model, dict(haven_info), (_time.perf_counter() - t0) * 1000.0


@app.post("/api/stress-test")
def stress_test(req: StressTestRequest, request: Request):
    """SHERPA's "Traverse Evaluation" for a /api/plan-4d route (B5).

    The route is executed ``n_runs`` times with the physics the planner
    used to choose it and the uncertainties VIPER's team injects -- start
    delay, initial battery, power draw and effective speed as truncated
    Gaussians, optional DSN outages and SEP events -- under the operator's
    policy (ahead: hold; behind: skip charge breaks and drive through
    shadow). Returned: completion and full-success rates with Wilson 95
    percent intervals, first-cause failure counts, SHERPA's metric
    distributions (p5/p50/p95), histograms, the per-state arrival and
    battery envelope, the unperturbed run for reference and a verdict.
    """
    import time as _time

    t0 = _time.perf_counter()
    grids = _active_grids(request)
    rover = get_rover(req.rover_id)
    grids_for_plan = grids_for_rover(grids, req.rover_id, PlanWeights().model_dump())
    geometry = _coarse_geometry(grids_for_plan, req.coarsen)

    try:
        legs = route_legs(
            req.path_states,
            geometry.slope,
            geometry.resolution_m,
            rover,
            req.slice_hours,
            traversable=geometry.traversable,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"path_states: {exc}") from exc

    overrides = {} if req.perturbations is None else {
        key: value
        for key, value in req.perturbations.model_dump().items()
        if value is not None
    }
    perturbations = dataclass_replace(SHERPA_DEFAULTS, **overrides)

    sky, sky_model, haven_model, sky_ms = _stress_test_sky(
        grids_for_plan, rover, req, legs, perturbations, geometry
    )
    result = stress_test_route(
        legs,
        sky,
        rover,
        initial_soc_frac=req.initial_soc_pct,
        n_runs=req.n_runs,
        seed=req.seed,
        perturbations=perturbations,
        n_bins=req.n_bins,
    )
    runs_ms = result.pop("timing_ms")["runs"]
    return {
        "label": req.label,
        "rover_id": req.rover_id,
        "coarsen": req.coarsen,
        "slice_hours": req.slice_hours,
        "start_utc": req.start_utc,
        "initial_soc_pct": req.initial_soc_pct,
        **result,
        "sky_model": sky_model,
        "safe_haven_model": haven_model,
        "timing_ms": {
            "sky": round(sky_ms, 3),
            "runs": runs_ms,
            "total": round((_time.perf_counter() - t0) * 1000.0, 3),
        },
    }


def _route_uncertainty_block(
    grids_for_plan: dict, rover_id: str, cells: Any, coarsen: int
) -> dict[str, Any] | None:
    """The cheap ``uncertainty`` block a plan response carries when NASA's
    DEM clones are cached (B3): how many clones keep every route cell
    passable, and the route's lowest and mean per-cell passability. No
    simulation -- the per-clone masks are read at the route. ``None``
    without the cache, so the field is absent rather than null."""
    layers, info = uncertainty_layers_for_grids(grids_for_plan, rover_id)
    if layers is None:
        return None
    route_cells = [(int(cell[0]), int(cell[1])) for cell in cells]
    per_state, feasible = route_traversable_probability(
        layers["clone_traversable"], route_cells, coarsen
    )
    return {
        "model": info["model"],
        "n_clones": int(feasible.shape[0]),
        "coarsen": int(coarsen),
        "p_traversable_min": round(float(per_state.min()), 4) if per_state.size else None,
        "p_traversable_mean": round(float(per_state.mean()), 4) if per_state.size else None,
        "route_feasible_fraction": round(float(feasible.mean()), 4) if feasible.size else None,
        "band_url": "/api/dem-uncertainty",
        "product_url": info.get("product_url"),
    }


def _dem_uncertainty_sky(
    grids_for_plan: dict,
    req: "DemUncertaintyRequest",
    legs,
    n_use: int,
    info: dict[str, Any],
    perturbations: Perturbations | None,
) -> tuple[list, Any, dict[str, Any], float]:
    """``(skies, nominal_sky, sky_model, sky_ms)`` for the band: one route-
    local sky per clone from the clone horizon cubes, the surface DEM's own
    from the production cube at the same block centres, or -- without an
    epoch, the cubes, a matching stride or the kernels -- one static sky for
    all, labelled with the reason."""
    import time as _time

    from .illumination import illuminated_mask

    t0 = _time.perf_counter()
    metadata = grids_for_plan["metadata"]
    cells = [(int(r), int(c)) for r, c in legs.cells]
    rows = np.asarray([r for r, _ in cells])
    cols = np.asarray([c for _, c in cells])
    if perturbations is not None:
        longest_h = (
            legs.planned_duration_h / max(perturbations.speed_multiplier_floor, 1e-3)
            + perturbations.z_max * perturbations.start_delay_sigma_h
        )
    else:
        longest_h = legs.planned_duration_h + 2.0 * req.slice_hours
    n_slices = min(MAX_STRESS_TEST_SLICES, int(math.ceil(longest_h / req.slice_hours)) + 2)
    common = {
        "n_slices": n_slices,
        "horizon_hours": round(n_slices * req.slice_hours, 4),
        "far_field_held_fixed": True,
        "near_range_m": info.get("near_range_m"),
        "earth_visibility_cloned": False,
    }

    def _static(reason: str):
        base = coarsen_grid(np.asarray(grids_for_plan["shadow_ratio"], dtype=np.float64), req.coarsen)
        shadow = np.tile(base[rows, cols], (n_slices, 1))
        sky = RouteSky(shadow, None, None, None, req.slice_hours, time_varying=False)
        model = {"model": "static", "time_varying": False, "reason": reason, **common}
        return [sky] * n_use, sky, model, (_time.perf_counter() - t0) * 1000.0

    if req.start_utc is None:
        return _static(
            "no start epoch given; illumination is a function of time and cannot "
            "vary without one"
        )
    processed_dir = metadata.get("processed_dir")
    try:
        cubes, cube_meta = load_clone_horizons(str(processed_dir)) if processed_dir else (None, None)
    except ValueError as exc:
        return _static(f"clone horizon cache unusable ({exc})")
    if cubes is None:
        return _static(
            f"no {CLONE_HORIZONS_FILENAME} beside the processed grids; run "
            "scripts/build_dem_clone_cache.py with horizon_map.npy present"
        )
    stride = int(cube_meta.get("stride", 1))
    if stride != req.coarsen:
        return _static(
            f"the clone horizon cubes are at stride {stride}; the clone sky needs "
            f"coarsen={stride} (got {req.coarsen})"
        )
    cache_path = horizon_cache_path(metadata)
    if cache_path is None:
        return _static("no horizon_map.npy beside the processed grids for the surface DEM's own sky")
    if int(cubes.shape[0]) < n_use:
        return _static(
            f"only {int(cubes.shape[0])} clone horizon cubes are cached for {n_use} clones"
        )
    if rows.max() >= cubes.shape[2] or cols.max() >= cubes.shape[3]:
        return _static("a route cell lies outside the clone horizon cubes")
    try:
        sun = body_track_for_series(metadata, n_slices, req.slice_hours, req.start_utc, body="SUN")
    except Exception as exc:
        return _static(f"real illumination unavailable ({exc})")

    offset = stride // 2
    surface = np.load(cache_path, mmap_mode="r")
    n_azimuth = int(cubes.shape[1])
    if surface.shape[0] != n_azimuth:
        return _static("horizon_map.npy and the clone cubes disagree on the azimuth count")
    # (A, N+1, S): the route's profiles in every clone, the surface's last.
    clone_profiles = np.asarray(cubes[:n_use][:, :, rows, cols])            # (N, A, S)
    surface_profiles = np.asarray(surface[:, offset::stride, offset::stride][:, rows, cols])  # (A, S)
    profiles = np.concatenate(
        [clone_profiles.transpose(1, 0, 2), surface_profiles[:, None, :]], axis=1
    )
    shadow = np.empty((n_slices, n_use + 1, rows.size), dtype=np.float64)
    for index in range(n_slices):
        lit = illuminated_mask(profiles, sun[index]["azimuth_grid_deg"], sun[index]["elevation_deg"])
        shadow[index] = 1.0 - lit
    skies = [
        RouteSky(shadow[:, k, :], None, None, None, req.slice_hours, time_varying=True)
        for k in range(n_use)
    ]
    nominal_sky = RouteSky(shadow[:, n_use, :], None, None, None, req.slice_hours, time_varying=True)
    model = {
        "model": "clone_horizon",
        "time_varying": True,
        "reason": None,
        "start_utc": req.start_utc,
        "stride": stride,
        "columns": (
            "the block-centre cell of each coarse route cell, lit or not per "
            "slice (the plan's cube is the block mean of the fine cells)"
        ),
        "neglected_horizon_shift_deg_max": cube_meta.get("neglected_horizon_shift_deg_max"),
        **common,
    }
    return skies, nominal_sky, model, (_time.perf_counter() - t0) * 1000.0


@app.post("/api/dem-uncertainty")
def dem_uncertainty(req: DemUncertaintyRequest, request: Request):
    """The DEM-clone band of a /api/plan-4d route (B3).

    NASA's statistical DEM clones each give the route different slopes and
    a different horizon. The route is priced and driven once per clone with
    the planner's own arithmetic (B5's legs and runs, SHERPA's sigmas at
    zero), and the band -- duration, drive hours, drive energy, battery,
    continuous shadow -- is reported as p5/p50/p95 across clones, with the
    surface DEM's own numbers beside it. Also: in how many clones the route
    stays passable at all, and the route's per-cell passability. With
    ``with_sherpa`` the SHERPA protocol runs on every clone and the pooled
    completion rate is added. 404 without the clone cache.
    """
    import time as _time

    t0 = _time.perf_counter()
    grids = _active_grids(request)
    rover = get_rover(req.rover_id)
    grids_for_plan = grids_for_rover(grids, req.rover_id, PlanWeights().model_dump())
    layers, info = uncertainty_layers_for_grids(grids_for_plan, req.rover_id)
    if layers is None:
        raise HTTPException(
            status_code=404,
            detail=f"the DEM clone ensemble is not available: {info.get('reason')}",
        )
    n_available = int(layers["clone_traversable"].shape[0])
    n_use = n_available if req.n_clones is None else int(req.n_clones)
    if n_use > n_available:
        raise HTTPException(
            status_code=422,
            detail=(
                f"n_clones={req.n_clones} but only {n_available} clones are cached; "
                "run scripts/build_dem_clone_cache.py --n-clones to fetch more."
            ),
        )
    geometry = _coarse_geometry(grids_for_plan, req.coarsen)
    try:
        legs = route_legs(
            req.path_states,
            geometry.slope,
            geometry.resolution_m,
            rover,
            req.slice_hours,
            traversable=geometry.traversable,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"path_states: {exc}") from exc

    cells = [(int(r), int(c)) for r, c in legs.cells]
    per_state, feasible = route_traversable_probability(
        layers["clone_traversable"][:n_use], cells, req.coarsen
    )
    clone_slopes = np.stack(
        [coarsen_grid(layers["clone_slopes"][k], req.coarsen, how="max") for k in range(n_use)]
    )

    sherpa = None
    perturbations = None
    if req.with_sherpa:
        overrides = {} if req.perturbations is None else {
            key: value
            for key, value in req.perturbations.model_dump().items()
            if value is not None
        }
        perturbations = dataclass_replace(SHERPA_DEFAULTS, **overrides)
        sherpa = {"n_runs": req.n_runs, "seed": req.seed, "perturbations": perturbations}

    skies, nominal_sky, sky_model, sky_ms = _dem_uncertainty_sky(
        grids_for_plan, req, legs, n_use, info, perturbations
    )
    t_runs = _time.perf_counter()
    band = route_band(
        req.path_states,
        clone_slopes,
        geometry.resolution_m,
        rover,
        req.slice_hours,
        skies,
        initial_soc_frac=req.initial_soc_pct,
        nominal_slope=geometry.slope,
        nominal_sky=nominal_sky,
        sherpa=sherpa,
    )
    runs_ms = (_time.perf_counter() - t_runs) * 1000.0
    feasible_count = int(feasible.sum())
    low, high = wilson_interval(feasible_count, n_use)
    return {
        "label": req.label,
        "rover_id": req.rover_id,
        "coarsen": req.coarsen,
        "slice_hours": req.slice_hours,
        "start_utc": req.start_utc,
        "initial_soc_pct": req.initial_soc_pct,
        **band,
        "route_feasible": {
            "count": feasible_count,
            "fraction": round(feasible_count / n_use, 4),
            "ci95": [round(low, 4), round(high, 4)],
        },
        "p_traversable": {
            "min": round(float(per_state.min()), 4),
            "mean": round(float(per_state.mean()), 4),
            "per_state": [round(float(v), 4) for v in per_state],
        },
        "sky_model": sky_model,
        "provenance": {
            "model": info["model"],
            "product_url": info.get("product_url"),
            "reference": info.get("reference"),
            "n_clones_available": n_available,
            "clone_indices": (info.get("clone_indices") or [])[:n_use],
            "thermal_field_held_fixed": True,
            "far_field_held_fixed": True,
            "earth_visibility_cloned": False,
        },
        "timing_ms": {
            "sky": round(sky_ms, 3),
            "runs": round(runs_ms, 3),
            "total": round((_time.perf_counter() - t0) * 1000.0, 3),
        },
    }


def _attach_constraint_check(
    result: dict, profile: dict, grids: dict, rover: dict
) -> None:
    """Simulate a profile's route and record which declared limits it met.

    ``max_shadow_h``, ``max_energy_wh`` and ``min_soc`` are path-dependent,
    so they cannot be enforced inside the search -- but they CAN be checked
    against the route that came out, and until round 4 nothing did: three of
    the four constraints every mission profile publishes appeared nowhere
    outside scenarios.py. The simulation is the same one /api/plan runs and
    costs well under a second on the production grid. (Round 4 review, M-4.)
    """
    summary = None
    if not result.get("error") and result.get("path_pixels"):
        try:
            states = simulate_path(
                result,
                grids["cost"],
                grids["slope"],
                grids["thermal"],
                grids["shadow_ratio"],
                rover=rover,
                pixel_size_m=float(grids["metadata"]["resolution_m"]),
                elevation_grid=grids["elevation"],
            )
            summary = summarize_simulation(states, rover)
        except Exception:
            logger.warning(
                "Constraint check skipped for %s: %s",
                result.get("profile_id"),
                traceback.format_exc(),
            )
            summary = None
    result["constraint_check"] = check_profile_constraints(profile, summary)
    result["simulation_summary"] = summary


def _validate_pixel_endpoints(grids: dict, start, goal) -> None:
    """422 for an out-of-grid start/goal, matching /api/plan.

    /api/plan answered 422 for these while /api/plan-multi and /api/compare
    returned HTTP 200 with the failure buried in the results array, so the
    same server state produced two different contracts and no client could
    handle "bad input" uniformly. (Round 3 review, L-12.)
    """
    shape = grids["metadata"]["shape"]
    rows, cols = int(shape[0]), int(shape[1])
    for label, point in (("start", start), ("goal", goal)):
        if not (0 <= point[0] < rows and 0 <= point[1] < cols):
            raise HTTPException(
                status_code=422,
                detail=f"{label} {tuple(point)} is outside the {rows}x{cols} grid.",
            )


@app.post("/api/plan-multi")
def plan_multi(req: PlanMultiRequest):
    base_grids = _get_grids()
    _validate_pixel_endpoints(base_grids, req.start, req.goal)
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
        _attach_constraint_check(result, profile, grids, rover)
        results.append(result)
    return {"results": results}


@app.post("/api/compare")
def compare(req: CompareRequest):
    base_grids = _get_grids()
    _validate_pixel_endpoints(base_grids, req.start, req.goal)
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
        _attach_constraint_check(result, profile, grids, rover)
        results.append(result)
    return {
        "start": req.start,
        "goal": req.goal,
        "results": results,
        "comparison": compare_results(results, rover),
    }


@app.get("/api/layers/{layer_name}")
def get_layer(
    layer_name: str,
    # downsample=0 raised "slice step cannot be zero" as an unhandled 500, and
    # a negative step silently REVERSED the grid -- a correct-looking map with
    # its axes flipped. Bound it at the signature. (Review #9.)
    downsample: int = Query(1, ge=1, le=50),
    # Two representations of one grid. JSON is the map overlay's: readable,
    # capped, and ~17 bytes of text per number. f32 is the 3-D client's: the
    # exact memory layout a Float32Array and a GPU want, at a quarter of the
    # size, which is why the cell ceiling does not apply to it.
    format: str = Query(
        "json",
        pattern="^(json|f32)$",
        description=(
            "json: nested lists, capped at MAX_LAYER_CELLS cells. "
            "f32: raw little-endian float32, row-major, NaN for no-data, "
            "uncapped."
        ),
    ),
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
        "thermal_min",
        "shadow_ratio",
        "cost",
        "traversable",
        "earth_visibility",
        *UNCERTAINTY_LAYERS,
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
    if layer_name in UNCERTAINTY_LAYERS:
        # The ensemble layers depend on the rover's slope limit and live in a
        # cache beside the processed grids; absent cache, absent layer (B3).
        grids = with_uncertainty_layers(grids, rover_id)
    metadata = dict(grids["metadata"])
    metadata["rover_id"] = rover_id
    metadata["rover_name"] = rover["name"]

    if layer_name not in grids:
        if layer_name in UNCERTAINTY_LAYERS:
            detail = (
                f"{layer_name} is not present in the loaded grids. It comes from "
                "NASA's DEM-clone ensemble: run scripts/build_dem_clone_cache.py "
                "(fetches PGDA product 78 for the planning window), then reload "
                "with POST /api/load-preprocessed."
            )
        elif layer_name == "earth_visibility":
            detail = (
                "earth_visibility is not present in the loaded grids. It is "
                "an optional cache: run scripts/build_earth_visibility_cache.py "
                "(needs horizon_map.npy and the NAIF kernels), then reload "
                "with POST /api/load-preprocessed."
            )
        else:
            detail = (
                f"{layer_name} is not present in the loaded grids. It is "
                "derived at load time from the sunlit-peak thermal field; "
                "reload with POST /api/load-preprocessed."
            )
        raise HTTPException(status_code=404, detail=detail)
    layer = grids[layer_name]
    if downsample > 1:
        layer = layer[::downsample, ::downsample]

    if format == "f32":
        # MAX_LAYER_CELLS guards a JSON response, where every number is text
        # built through an object-dtype array. The same 500x500 grid is
        # 1.00 MB of float32 -- less than the capped 256x256 JSON preview
        # costs -- so applying the ceiling here would only deny the caller
        # resolution it can plainly afford.
        return Response(
            content=encode_layer_f32(layer),
            media_type=BINARY_MEDIA_TYPE,
            headers=binary_layer_headers(
                layer_name,
                layer,
                downsample,
                float(metadata.get("resolution_m", 1.0)),
                (metadata.get("layer_validity") or {}).get(layer_name),
            ),
        )

    cells = int(layer.shape[0]) * int(layer.shape[1])
    if cells > MAX_LAYER_CELLS:
        full = grids[layer_name]
        needed = math.ceil(
            math.sqrt((int(full.shape[0]) * int(full.shape[1])) / MAX_LAYER_CELLS)
        )
        raise HTTPException(
            status_code=422,
            detail=(
                f"{layer_name} at downsample={downsample} is {cells} cells, over "
                f"the {MAX_LAYER_CELLS}-cell response budget. "
                f"Use downsample={needed} or higher."
            ),
        )

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


@app.get("/api/terrain")
def terrain(
    rover_id: str = DEFAULT_ROVER_ID,
    w_slope: float | None = None,
    w_energy: float | None = None,
    w_shadow: float | None = None,
    w_thermal: float | None = None,
):
    """Everything a 3-D scene needs before it fetches a byte of grid.

    ``/api/layers`` answers "what are the numbers". This answers "what do
    they mean": mesh dimensions, the georeference that ties the mesh to the
    Moon, the elevation range the displacement scales by, the decode
    contract, and per-layer units, range and provenance with the URL to
    fetch each one. One call, so a client is never assembling a query
    string by hand, guessing an axis direction, or normalising a colour
    ramp against a range it had to compute for itself.
    """
    base_grids = _get_grids()
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
    grids = with_uncertainty_layers(
        grids_for_rover(base_grids, rover_id, weight_overrides or None), rover_id
    )

    # Echoed into every binary_url so the caller can fetch them verbatim.
    # cost and traversable are rover- and weight-dependent; a URL that
    # dropped these would quietly hand back the default rover's grid.
    query = {"rover_id": rover_id}
    query.update({key: repr(value) for key, value in weight_overrides.items()})

    return terrain_manifest(
        grids,
        rover_id=rover_id,
        rover_name=rover["name"],
        # The weights actually resolved for this rover, which are not the
        # overrides the caller sent: grids_for_rover fills the unspecified
        # ones from the rover's own defaults.
        weights=dict((grids["metadata"] or {}).get("cost_weights") or {}) or None,
        layer_names=TERRAIN_LAYERS,
        # urlencode, not a hand-built f-string: rover_id is arbitrary caller
        # input reflected verbatim into a URL every manifest publishes and
        # every client is told to fetch as-is.
        binary_query=urlencode(query),
    )


def _series_field_cube(
    grids: dict,
    shadow_series: list,
    field: str,
    step: int,
    slice_hours: float,
) -> np.ndarray:
    """(T, rows, cols) for one field, decimated by *step*.

    The temperature branch uses the SAME thermal recipe as
    ``cost_cube.build_cost_cube`` -- same initial state, same per-slice
    target, same time constant -- so the surface a viewer animates is the
    surface the planner costed. Deriving it differently here would put a
    field on screen that nothing ever planned against, which is a worse
    failure than not shipping it. The two diverge only in *spatial*
    reduction above ``downsample=1``: this decimates by simple striding
    (``[::step, ::step]``), the same approach ``/api/layers`` already uses
    for its own downsample parameter, while ``build_cost_cube`` block-means
    via ``coarsen_grid``. Identical at native resolution; not literally
    "step for step" once a client asks for a coarser preview.
    """
    stack = np.stack(
        [np.asarray(snapshot, dtype=np.float64)[::step, ::step]
         for snapshot in shadow_series]
    )
    if field == "shadow":
        return stack

    sunlit = np.asarray(grids["thermal_sunlit_peak"], dtype=np.float64)[::step, ::step]
    base_shadow = np.asarray(grids["shadow_ratio"], dtype=np.float64)[::step, ::step]
    # Initial state: equilibrium under the cell's LONG-RUN illumination.
    # Starting at the annual peak would assume the traverse begins at the
    # hottest moment of the year. (Round 4 review, H-3.)
    state = np.asarray(shadowed_equilibrium_c(sunlit, base_shadow), dtype=np.float64)
    dt_s = max(0.0, float(slice_hours)) * 3600.0

    out = np.empty_like(stack)
    for index in range(stack.shape[0]):
        target = np.asarray(
            shadowed_equilibrium_c(sunlit, stack[index]), dtype=np.float64
        )
        state = np.asarray(relax_surface_c(state, target, dt_s), dtype=np.float64)
        out[index] = state
    return out


def _check_series_budget(
    n_slices: int, shape: tuple[int, int], step: int
) -> tuple[int, int]:
    """Refuse a series that would not fit the wire or the working set.

    Shared by ``/api/illumination-series`` and ``/api/earth-series`` so the
    two answer with the same numbers and the same advice. Returns the
    decimated (rows, cols).
    """
    rows = len(range(0, int(shape[0]), step))
    cols = len(range(0, int(shape[1]), step))
    size = int(shape[0]) * int(shape[1])
    needed = int(n_slices) * rows * cols * 4
    if needed > MAX_SERIES_BYTES:
        fits = math.ceil(math.sqrt((int(n_slices) * size * 4) / MAX_SERIES_BYTES))
        raise HTTPException(
            status_code=422,
            detail=(
                f"{n_slices} slices at downsample={step} is "
                f"{needed / 2**20:.0f} MiB, over the "
                f"{MAX_SERIES_BYTES // 2**20} MiB series budget. "
                f"Use downsample={fits} or higher, or ask for fewer slices."
            ),
        )

    # Real check on the WORKING set, independent of downsample -- see
    # MAX_SERIES_WORKING_BYTES above. This is what actually protects the
    # process; the response-size check above only protects the wire.
    working_needed = int(n_slices) * size * 8
    if working_needed > MAX_SERIES_WORKING_BYTES:
        fits = max(1, MAX_SERIES_WORKING_BYTES // max(1, size * 8))
        raise HTTPException(
            status_code=422,
            detail=(
                f"{n_slices} slices at native resolution needs "
                f"{working_needed / 2**20:.0f} MiB to build the series before "
                f"any downsampling, over the "
                f"{MAX_SERIES_WORKING_BYTES // 2**20} MiB working-set budget. "
                f"Ask for at most {fits} slices; downsample does not reduce "
                "this cost."
            ),
        )
    return rows, cols


@app.get("/api/illumination-series")
def illumination_series(
    start_utc: Optional[str] = None,
    n_slices: int = Query(24, ge=1, le=MAX_PLAN_4D_SLICES),
    slice_hours: float = Query(1.0, gt=0.0, le=24.0),
    downsample: int = Query(1, ge=1, le=50),
    format: str = Query("json", pattern="^(json|f32)$"),
    field: str = Query("shadow", pattern="^(shadow|surface_temp_c)$"),
):
    """Illumination and surface temperature over time, for an animated scene.

    The 4-D planner already reasons over exactly this series -- it is what
    makes "wait here for the Sun" a decision rather than a slogan -- but it
    consumed the series privately and published only the route. A client
    that wants to show WHY a route waits needs the same field the planner
    waited on.

    Time-varying illumination needs two things: an epoch, and the horizon
    cube cached beside the processed grids. Without either, the series is
    static and ``shadow_model`` says so and names what was missing. It is
    never disguised as physics.
    """
    grids = _get_grids()
    metadata = grids["metadata"]
    base_shadow = np.asarray(grids["shadow_ratio"], dtype=np.float64)

    step = int(downsample)
    rows, cols = _check_series_budget(int(n_slices), base_shadow.shape, step)

    shadow_series, provenance = build_shadow_series(
        base_shadow, metadata, int(n_slices), float(slice_hours), start_utc
    )

    if format == "f32":
        cube = _series_field_cube(
            grids, shadow_series, field, step, float(slice_hours)
        )
        return Response(
            content=encode_layer_f32(cube.reshape(-1, cube.shape[-1])),
            media_type=BINARY_MEDIA_TYPE,
            headers={
                "X-Series-Field": field,
                "X-Series-Slices": str(int(n_slices)),
                "X-Series-Rows": str(rows),
                "X-Series-Cols": str(cols),
                "X-Series-Downsample": str(step),
                "X-Series-Resolution-M": repr(
                    float(metadata["resolution_m"]) * step
                ),
                "X-Series-Dtype": "float32",
                "X-Series-Endian": "little",
                # Matches the manifest's binary_format.order. The old
                # "row-major" here (an X-Layer-* name reused on a payload
                # that has a time axis a single layer does not) undersold
                # the actual layout and could mislead a header-only
                # consumer that never fetches /api/illumination-series's
                # own JSON manifest.
                "X-Series-Order": "slice-major, then row-major",
            },
        )

    sun: list[dict[str, Any]] = []
    if start_utc:
        try:
            sun = sun_track_for_series(
                metadata, int(n_slices), float(slice_hours), start_utc
            )
        except Exception as exc:
            # Same reasoning as build_shadow_series: a missing kernel must
            # degrade to "no Sun track" and say so, not take the endpoint
            # down. Deliberately broad -- spiceypy maps SPICE failures on to
            # assorted builtin exception types.
            logger.warning("Sun track unavailable: %s", exc)
            sun = []

    # urlencode, not a hand-built f-string: start_utc is arbitrary caller
    # input (an ISO-8601 timestamp can carry a "+" UTC offset, which a plain
    # f-string leaves unescaped and a URL round-trip then decodes as a
    # space) reflected verbatim into a URL every field entry publishes and
    # every client is told to fetch as-is.
    query_params: dict[str, Any] = {
        "n_slices": n_slices,
        "slice_hours": slice_hours,
        "downsample": step,
        "format": "f32",
    }
    if start_utc:
        query_params["start_utc"] = start_utc
    query_base = urlencode(query_params)

    fields: dict[str, Any] = {}
    for name in ("shadow", "surface_temp_c"):
        cube = _series_field_cube(grids, shadow_series, name, step, float(slice_hours))
        finite = cube[np.isfinite(cube)]
        fields[name] = {
            "units": "fraction" if name == "shadow" else "degC",
            "min": float(finite.min()) if finite.size else None,
            "max": float(finite.max()) if finite.size else None,
            "binary_url": f"/api/illumination-series?{query_base}&field={name}",
        }

    return {
        "slices": int(n_slices),
        "slice_hours": float(slice_hours),
        "start_utc": start_utc,
        "grid": {
            "rows": rows,
            "cols": cols,
            "resolution_m": float(metadata["resolution_m"]) * step,
            "downsample": step,
        },
        "shadow_model": provenance,
        "thermal_model": {
            "recipe": "shadowed_equilibrium_c per slice, then relax_surface_c",
            "tau_s": REGOLITH_THERMAL_TAU_S,
            "validity": REGOLITH_LAG_VALIDITY,
        },
        "sun": sun,
        "fields": fields,
        "binary_format": {
            "dtype": "float32",
            "endian": "little",
            "order": "slice-major, then row-major",
            "shape": [int(n_slices), rows, cols],
            "nodata": "NaN",
        },
    }


@app.get("/api/uncertainty-series")
def uncertainty_series(
    start_utc: Optional[str] = None,
    n_slices: int = Query(24, ge=1, le=MAX_PLAN_4D_SLICES),
    slice_hours: float = Query(1.0, gt=0.0, le=24.0),
    format: str = Query("json", pattern="^(json|f32)$"),
    n_clones: Optional[int] = Query(
        None, ge=1, le=N_PGDA_CLONES, description="Use the first n cached clones; default all."
    ),
):
    """P(lit, t) across NASA's DEM clones, on the 4-D planner's block
    centres (B3).

    ``/api/illumination-series`` says whether a cell is lit under the one
    shipped DEM. This says in what fraction of NASA's statistical clones it
    is lit -- the same horizon geometry, one cube per clone, built by
    ``scripts/build_dem_clone_cache.py`` at the planner's coarsen stride.
    The far field beyond the clones' near range is the surface DEM's own
    and is held fixed; the response says so, with the horizon shift that
    could hide. Without the clone cubes, an epoch or the kernels the answer
    is ``unavailable`` with the reason (404 for the binary form).
    """
    grids = _get_grids()
    metadata = grids["metadata"]

    def _unavailable(reason: str):
        if format == "f32":
            raise HTTPException(status_code=404, detail=reason)
        return {
            "model": "unavailable",
            "reason": reason,
            "slices": int(n_slices),
            "slice_hours": float(slice_hours),
            "start_utc": start_utc,
        }

    processed_dir = metadata.get("processed_dir")
    if not processed_dir:
        return _unavailable(
            "the loaded grids carry no processed_dir; the clone horizon cubes live "
            "beside the processed grids (scripts/build_dem_clone_cache.py)"
        )
    try:
        cubes, cube_meta = load_clone_horizons(str(processed_dir))
    except ValueError as exc:
        return _unavailable(
            f"clone horizon cache unusable ({exc}); rebuild it with scripts/build_dem_clone_cache.py"
        )
    if cubes is None:
        return _unavailable(
            f"no {CLONE_HORIZONS_FILENAME} beside the processed grids; run "
            "scripts/build_dem_clone_cache.py (with horizon_map.npy present) to "
            "build one horizon cube per DEM clone"
        )
    if not start_utc:
        return _unavailable(
            "no start epoch given; illumination is a function of time and cannot "
            "vary without one"
        )
    n_available, _n_azimuth, rows, cols = (int(v) for v in cubes.shape)
    n_use = n_available if n_clones is None else int(n_clones)
    if n_use > n_available:
        raise HTTPException(
            status_code=422,
            detail=(
                f"n_clones={n_clones} but only {n_available} clone horizon cubes are "
                "cached; run scripts/build_dem_clone_cache.py --n-clones to build more."
            ),
        )
    stride = int(cube_meta.get("stride", 1))
    needed = int(n_slices) * rows * cols * 4
    if needed > MAX_SERIES_BYTES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{n_slices} slices of {rows}x{cols} is {needed / 2**20:.0f} MiB, over "
                f"the {MAX_SERIES_BYTES // 2**20} MiB series budget; ask for fewer slices."
            ),
        )
    try:
        sun = body_track_for_series(metadata, int(n_slices), float(slice_hours), start_utc, body="SUN")
    except Exception as exc:
        # As build_shadow_series: a missing kernel degrades to an honest
        # answer, not a 500. spiceypy raises assorted builtin types.
        return _unavailable(f"Sun track unavailable ({exc})")
    series = illuminated_probability_series(np.asarray(cubes[:n_use]), sun)
    resolution_m = float(metadata["resolution_m"]) * stride

    if format == "f32":
        return Response(
            content=encode_layer_f32(series.reshape(-1, cols)),
            media_type=BINARY_MEDIA_TYPE,
            headers={
                "X-Series-Field": "p_illuminated",
                "X-Series-Slices": str(int(n_slices)),
                "X-Series-Rows": str(rows),
                "X-Series-Cols": str(cols),
                "X-Series-Downsample": str(stride),
                "X-Series-Resolution-M": repr(resolution_m),
                "X-Series-Dtype": "float32",
                "X-Series-Endian": "little",
                "X-Series-Order": "slice-major, then row-major",
            },
        )

    query_params: dict[str, Any] = {
        "start_utc": start_utc,
        "n_slices": n_slices,
        "slice_hours": slice_hours,
        "format": "f32",
    }
    if n_clones is not None:
        query_params["n_clones"] = n_use
    return {
        "model": "clone_horizon",
        "n_clones": n_use,
        "clone_indices": (cube_meta.get("clone_indices") or [])[:n_use],
        "slices": int(n_slices),
        "slice_hours": float(slice_hours),
        "start_utc": start_utc,
        "grid": {
            "rows": rows,
            "cols": cols,
            "resolution_m": resolution_m,
            "stride": stride,
            # Fine-grid row/col of the first cube cell: the planner's block
            # centre, so the series aligns with path_pixels_coarse.
            "row_offset": int(cube_meta.get("row_offset", 0)),
            "col_offset": int(cube_meta.get("col_offset", 0)),
        },
        "near_range_m": cube_meta.get("near_range_m"),
        "far_field_held_fixed": bool(cube_meta.get("far_field_held_fixed", True)),
        "neglected_horizon_shift_deg_max": cube_meta.get("neglected_horizon_shift_deg_max"),
        "sun": sun,
        "per_slice": {
            "mean": [round(float(frame.mean()), 6) for frame in series],
            "uncertain_fraction": [round(uncertain_fraction(frame), 6) for frame in series],
        },
        "fields": {
            "p_illuminated": {
                "units": "fraction",
                "description": (
                    "Fraction of NASA's DEM clones in which the cell sees the Sun "
                    "at the slice; 0.05-0.95 is the band the ensemble cannot call."
                ),
                "min": float(series.min()) if series.size else None,
                "max": float(series.max()) if series.size else None,
                "binary_url": f"/api/uncertainty-series?{urlencode(query_params)}",
            }
        },
        "binary_format": {
            "dtype": "float32",
            "endian": "little",
            "order": "slice-major, then row-major",
            "shape": [int(n_slices), rows, cols],
            "nodata": "NaN",
        },
    }


@app.get("/api/earth-series")
def earth_series(
    start_utc: Optional[str] = None,
    n_slices: int = Query(24, ge=1, le=MAX_PLAN_4D_SLICES),
    slice_hours: float = Query(1.0, gt=0.0, le=24.0),
    downsample: int = Query(1, ge=1, le=50),
    format: str = Query("json", pattern="^(json|f32)$"),
    field: str = Query("earth_visible", pattern="^(earth_visible)$"),
):
    """Direct-to-Earth visibility over time, beside the illumination series.

    Same parameters, same budget, same binary contract as
    ``/api/illumination-series``; one field, ``earth_visible`` (1.0 where
    the Earth clears the cell's terrain horizon, 0.0 where it does not).
    ``earth`` carries the Earth's azimuth/elevation per slice and the share
    of the grid with a link, which is what a timeline needs to show WHEN the
    site loses contact.

    Three honest outcomes in ``earth_model``: ``spice_horizon`` (epoch +
    horizon cube + kernels), ``static`` (the long-run layer repeated, with
    the reason), or ``unavailable`` (no field at all -- ``fields`` is empty
    and the binary request is a 404, never a cube of zeros).
    """
    grids = _get_grids()
    metadata = grids["metadata"]
    shape = tuple(int(v) for v in np.asarray(grids["elevation"]).shape)

    step = int(downsample)
    rows, cols = _check_series_budget(int(n_slices), shape, step)

    base = grids.get("earth_visibility")
    series, provenance = build_earth_visibility_series(
        None if base is None else np.asarray(base, dtype=np.float64),
        metadata,
        int(n_slices),
        float(slice_hours),
        start_utc,
    )
    available = len(series) > 0

    if format == "f32":
        if not available:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Earth visibility is unavailable for these grids: "
                    f"{provenance.get('reason', 'no field could be computed')}"
                ),
            )
        cube = np.stack(
            [np.asarray(snapshot, dtype=np.float64)[::step, ::step] for snapshot in series]
        )
        return Response(
            content=encode_layer_f32(cube.reshape(-1, cube.shape[-1])),
            media_type=BINARY_MEDIA_TYPE,
            headers={
                "X-Series-Field": field,
                "X-Series-Slices": str(int(n_slices)),
                "X-Series-Rows": str(rows),
                "X-Series-Cols": str(cols),
                "X-Series-Downsample": str(step),
                "X-Series-Resolution-M": repr(float(metadata["resolution_m"]) * step),
                "X-Series-Dtype": "float32",
                "X-Series-Endian": "little",
                "X-Series-Order": "slice-major, then row-major",
            },
        )

    earth: list[dict[str, Any]] = []
    if start_utc and provenance.get("time_varying"):
        try:
            earth = earth_track_for_series(
                metadata, int(n_slices), float(slice_hours), start_utc
            )
        except Exception as exc:
            # Same reasoning as the Sun track: degrade and say so.
            logger.warning("Earth track unavailable: %s", exc)
            earth = []
        for entry, snapshot in zip(earth, series):
            # Share of the grid with a link at this slice. The slices are
            # binary, so this is the mean of the field itself.
            entry["visible_fraction"] = float(np.mean(np.asarray(snapshot, dtype=np.float64)))

    fields: dict[str, Any] = {}
    if available:
        query_params: dict[str, Any] = {
            "n_slices": n_slices,
            "slice_hours": slice_hours,
            "downsample": step,
            "format": "f32",
        }
        if start_utc:
            query_params["start_utc"] = start_utc
        cube = np.stack(
            [np.asarray(snapshot, dtype=np.float64)[::step, ::step] for snapshot in series]
        )
        finite = cube[np.isfinite(cube)]
        fields["earth_visible"] = {
            "units": "fraction",
            "min": float(finite.min()) if finite.size else None,
            "max": float(finite.max()) if finite.size else None,
            "binary_url": (
                f"/api/earth-series?{urlencode(query_params)}&field=earth_visible"
            ),
        }

    return {
        "slices": int(n_slices),
        "slice_hours": float(slice_hours),
        "start_utc": start_utc,
        "grid": {
            "rows": rows,
            "cols": cols,
            "resolution_m": float(metadata["resolution_m"]) * step,
            "downsample": step,
        },
        "earth_model": provenance,
        "earth": earth,
        "fields": fields,
        "binary_format": {
            "dtype": "float32",
            "endian": "little",
            "order": "slice-major, then row-major",
            "shape": [int(n_slices), rows, cols],
            "nodata": "NaN",
        },
    }


_SAFE_HAVEN_FIELDS: tuple[str, ...] = (
    "safe_haven",
    "max_dark_hours_without_dte",
    "earth_below_hours",
    "time_to_safe_haven",
)
_SAFE_HAVEN_UNITS: dict[str, str] = {
    "safe_haven": "bool",
    "max_dark_hours_without_dte": "hours",
    "earth_below_hours": "hours",
    "time_to_safe_haven": "hours",
}


@app.get("/api/safe-haven")
def safe_haven_endpoint(
    start_utc: str = Query(
        ...,
        description=(
            "UTC instant the map's window begins, e.g. '2026-09-07T00:00:00'. "
            "The window spans one synodic month by default, so every cell "
            "sees at least one full period without an Earth link."
        ),
    ),
    rover_id: str = DEFAULT_ROVER_ID,
    span_hours: float = Query(DEFAULT_SAFE_HAVEN_SPAN_HOURS, gt=0.0, le=2000.0),
    step_hours: float = Query(DEFAULT_SAFE_HAVEN_STEP_HOURS, gt=0.0, le=24.0),
    downsample: int = Query(1, ge=1, le=50),
    format: str = Query("json", pattern="^(json|f32)$"),
    field: str = Query(
        "safe_haven",
        pattern="^(safe_haven|max_dark_hours_without_dte|earth_below_hours|time_to_safe_haven)$",
    ),
):
    """VIPER's Safe Haven map for a rover and a month (A1).

    A cell is a safe haven when, while the Earth is below its horizon, its
    continuous shadow never exceeds the rover's ``h_max_shadow_h`` and it is
    lit at least once (Shirley & Balaban 2022). Four binary fields share
    the ``/api/layers`` wire format: the mask (1/0), the longest unlinked
    darkness (h), the hours without a link in the window (h), and the
    driving hours to the nearest haven (NaN where none is reachable).

    Two honest outcomes in ``safe_haven_model``: ``spice_horizon``, or
    ``unavailable`` with the reason -- ``fields`` is then empty and a
    binary request is a 404, never a grid of zeros.
    """
    grids = _get_grids()
    rover = get_rover(rover_id)
    metadata = grids["metadata"]
    resolution_m = float(metadata["resolution_m"])
    step = int(downsample)

    layers, tts, info = safe_haven_for_grids(
        grids, rover_id, start_utc, span_hours=float(span_hours), step_hours=float(step_hours)
    )
    if layers is None:
        if format == "f32":
            raise HTTPException(
                status_code=404,
                detail=(
                    "The safe haven map is unavailable for these grids: "
                    f"{info.get('reason', 'it could not be computed')}"
                ),
            )
        shape = tuple(int(v) for v in np.asarray(grids["elevation"]).shape)
        return {
            "rover_id": rover_id,
            "rover_name": rover["name"],
            "h_max_shadow_h": float(rover["h_max_shadow_h"]),
            "start_utc": start_utc,
            "span_hours": float(span_hours),
            "step_hours": float(step_hours),
            "n_steps": None,
            "safe_haven_model": info,
            "safe_haven_fraction": None,
            "safe_haven_cells": None,
            "traversable_cells": None,
            "earth_below_fraction": None,
            "grid": {
                "rows": len(range(0, shape[0], step)),
                "cols": len(range(0, shape[1], step)),
                "resolution_m": resolution_m * step,
                "downsample": step,
            },
            "fields": {},
            "binary_format": None,
        }

    data = {
        "safe_haven": layers["safe_haven"],
        "max_dark_hours_without_dte": layers["max_dark_hours_without_dte"],
        "earth_below_hours": layers["earth_below_hours"],
        "time_to_safe_haven": tts,
    }

    if format == "f32":
        layer = np.asarray(data[field])[::step, ::step]
        return Response(
            content=encode_layer_f32(layer),
            media_type=BINARY_MEDIA_TYPE,
            headers=binary_layer_headers(field, layer, step, resolution_m, "DERIVED"),
        )

    rows = cols = None
    fields: dict[str, Any] = {}
    for name in _SAFE_HAVEN_FIELDS:
        layer = np.asarray(data[name])[::step, ::step]
        rows, cols = int(layer.shape[0]), int(layer.shape[1])
        stats = layer_stats(layer)
        query = {
            "start_utc": start_utc,
            "rover_id": rover_id,
            "span_hours": span_hours,
            "step_hours": step_hours,
            "downsample": step,
            "format": "f32",
            "field": name,
        }
        fields[name] = {
            "units": _SAFE_HAVEN_UNITS[name],
            "min": stats["min"],
            "max": stats["max"],
            "nodata": stats["nodata"],
            "binary_url": f"/api/safe-haven?{urlencode(query)}",
        }

    return {
        "rover_id": rover_id,
        "rover_name": rover["name"],
        "h_max_shadow_h": float(info["h_max_shadow_h"]),
        "start_utc": info.get("start_utc", start_utc),
        "span_hours": float(info["span_hours"]),
        "step_hours": float(info["step_hours"]),
        "n_steps": int(info["n_steps"]),
        "safe_haven_model": info,
        "safe_haven_fraction": info["safe_haven_fraction"],
        "safe_haven_cells": info["safe_haven_cells"],
        "traversable_cells": info["traversable_cells"],
        "earth_below_fraction": info["earth_below_fraction"],
        "grid": {
            "rows": rows,
            "cols": cols,
            "resolution_m": resolution_m * step,
            "downsample": step,
        },
        "fields": fields,
        "binary_format": {
            "dtype": "float32",
            "endian": "little",
            "order": "row-major",
            "shape": [rows, cols],
            "nodata": "NaN",
        },
    }


@app.get("/api/reference-missions")
def reference_missions():
    """Published real-mission traverse figures, with citations.

    ``app.mission_reference`` is the external reality check the maturity
    assessment asks for, and it had no consumer anywhere outside its own
    tests -- so the one module in the backend whose entire purpose is to be
    compared against was not reachable by anything doing the comparing.
    (Round 4 review, L-9.)
    """
    return reference_summary()


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

    # The load status is reported rather than implied. A missing dem_file
    # used to return the scenario with HTTP 200 and load nothing, so the
    # caller could not tell a loaded scenario from a no-op; and unlike
    # /api/load-dem this path did not map load failures, so a malformed
    # DEM surfaced as an unhandled 500. (Round 2 review, L-5.)
    status = "no_dem_declared"
    if "dem_file" in scenario:
        dem_path = _resolve_dem_path(scenario["dem_file"])
        if not dem_path.is_file():
            status = "dem_missing"
        else:
            try:
                _set_grids(
                    load_and_preprocess_dem(
                        str(dem_path),
                        scenario.get("grid_resolution_m", 80),
                        weights=scenario.get("weights"),
                    )
                )
                status = "loaded"
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {**scenario, "load_status": status}
