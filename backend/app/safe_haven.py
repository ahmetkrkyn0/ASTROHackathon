"""Safe Havens: where a rover survives the two weeks without an Earth link (A1).

VIPER's traverse is a sequence of legs, and every leg ends at a *Safe
Haven*: a place the rover can park through the ~two weeks each month when
the Earth is below its horizon and no command can reach it. NASA's
definition (Shirley & Balaban 2022; Ennico-Smith et al. 2023):

    a location where, while the Earth is below the horizon, the continuous
    shadow duration does not exceed 50 hours and the rover can generate
    power while stationary.

The 50 h is VIPER's minimum-power endurance; LunaPath carries it per rover
as ``h_max_shadow_h`` (LPR-1 50 h, NASA VIPER 50 h, LUVMI-M 4 h, Yutu-2
2 h), so the same rule produces a different map for each profile.

Three pieces, each a pure function of arrays until the very end:

* the counting rule -- :func:`max_dark_hours_without_dte` runs the Sun's and
  the Earth's visibility series over one synodic month and measures, per
  cell, the longest continuous darkness that falls INSIDE a no-link period.
  Darkness while the Earth is up does not count: the rover can be commanded
  away from it;
* the mask -- :func:`safe_haven_mask` applies the endurance, the "can
  generate power" clause (lit at least once) and traversability;
* the distance -- :func:`time_to_safe_haven_hours`, driving HOURS from every
  cell to the nearest haven over the same gated graph the planners use.

Nothing here fabricates a field it cannot compute: without an epoch, the
horizon cube or the kernels the map is reported ``unavailable`` with the
reason, never as an empty or all-safe grid.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .cost_engine import edge_travel_time_s_array

#: One synodic month: long enough to contain a full no-link period for every
#: cell, whatever its horizon.
DEFAULT_SAFE_HAVEN_SPAN_HOURS: float = 708.7
#: SHERPA's planning cadence for the shadow series.
DEFAULT_SAFE_HAVEN_STEP_HOURS: float = 2.0
#: How far past a plan's horizon to look for the next Earthset -- half a
#: libration cycle, the same span comm_window searches.
DEFAULT_EARTHSET_LOOKAHEAD_HOURS: float = 336.0


def max_dark_hours_without_dte(
    sun_visible: np.ndarray, earth_visible: np.ndarray, step_hours: float
) -> np.ndarray:
    """Longest continuous darkness that falls inside a no-Earth-link period.

    *sun_visible* and *earth_visible* are ``(T, H, W)`` boolean series at a
    common cadence of *step_hours*. A step adds to a cell's run when the
    cell is dark AND the Earth is below its horizon; a lit step or a linked
    step resets the run. Returns hours, ``(H, W)``.

    Counting only the unlinked steps is the letter of NASA's definition
    ("while the Earth is below the horizon"). Darkness the rover sits in
    while it still has a link is a planning matter, not a survival one.
    """
    sun = np.asarray(sun_visible, dtype=bool)
    earth = np.asarray(earth_visible, dtype=bool)
    if sun.ndim != 3 or sun.shape != earth.shape:
        raise ValueError(
            f"sun_visible {sun.shape} and earth_visible {earth.shape} must both "
            "be (T, H, W) of the same shape"
        )
    step = float(step_hours)
    if not (step > 0.0):
        raise ValueError("step_hours must be positive")

    tally = _DarkRunTally(sun.shape[1:], step)
    for index in range(sun.shape[0]):
        tally.push(sun[index], earth[index])
    return tally.longest


class _DarkRunTally:
    """The counting rule as a streaming accumulator.

    :func:`max_dark_hours_without_dte` and :func:`build_safe_haven_map` share
    it: the first feeds it whole series, the second one step at a time so a
    month of 500x500 masks is never held in memory at once.
    """

    def __init__(self, shape: tuple[int, ...], step_hours: float) -> None:
        self.step = float(step_hours)
        self.run = np.zeros(shape, dtype=np.float64)
        self.longest = np.zeros(shape, dtype=np.float64)
        self.ever_lit = np.zeros(shape, dtype=bool)
        self.unlinked_steps = np.zeros(shape, dtype=np.int64)
        self.n_steps = 0

    def push(self, sun_visible: np.ndarray, earth_visible: np.ndarray) -> None:
        lit = np.asarray(sun_visible, dtype=bool)
        linked = np.asarray(earth_visible, dtype=bool)
        counts = ~lit & ~linked
        self.run = np.where(counts, self.run + self.step, 0.0)
        np.maximum(self.longest, self.run, out=self.longest)
        self.ever_lit |= lit
        self.unlinked_steps += ~linked
        self.n_steps += 1


def safe_haven_mask(
    max_dark_no_dte_h: np.ndarray,
    ever_lit: np.ndarray,
    traversable: np.ndarray,
    h_max_shadow_h: float,
) -> np.ndarray:
    """``(H, W)`` bool: cells that satisfy the Safe Haven rule for this rover.

    Three clauses, all from the definition: the longest unlinked darkness is
    within the rover's endurance; the cell is lit at some point, so a parked
    rover can generate power (a permanently dark cell whose no-link period
    happened to be short is NOT a haven); and the rover can actually park
    there (traversable).
    """
    dark = np.asarray(max_dark_no_dte_h, dtype=np.float64)
    lit = np.asarray(ever_lit, dtype=bool)
    passable = np.asarray(traversable, dtype=bool)
    if not (dark.shape == lit.shape == passable.shape):
        raise ValueError("max_dark_no_dte_h, ever_lit and traversable must share a shape")
    endurance = float(h_max_shadow_h)
    return passable & lit & (dark <= endurance + 1e-9)


# ── time-to-safe-haven ───────────────────────────────────────────────────────

# The four "forward" neighbour offsets. The graph is undirected -- every gate
# below reads the same in both directions (|dz|, |cross-slope|, the corner
# rule, the trapezoidal slope) -- so each pair is stored once and the solver
# is told so.
_HALF_OFFSETS: tuple[tuple[int, int, bool], ...] = (
    (0, 1, False),
    (1, 0, False),
    (1, 1, True),
    (1, -1, True),
)


def _terrain_gradient(elev: np.ndarray, resolution_m: float) -> tuple[np.ndarray, np.ndarray]:
    """``np.gradient`` that tolerates a single row or column.

    The planners' grids are always 2-D in both axes; the toy fixtures are
    not, and ``np.gradient`` refuses an axis with fewer than two samples.
    Along such an axis the slope is zero by construction.
    """
    grad_row = np.zeros(elev.shape, dtype=np.float64)
    grad_col = np.zeros(elev.shape, dtype=np.float64)
    if elev.shape[0] >= 2:
        grad_row = np.gradient(elev, float(resolution_m), axis=0)
    if elev.shape[1] >= 2:
        grad_col = np.gradient(elev, float(resolution_m), axis=1)
    return np.nan_to_num(grad_row, nan=0.0), np.nan_to_num(grad_col, nan=0.0)


def _gated_edges(
    passable: np.ndarray,
    elevation: np.ndarray | None,
    slope: np.ndarray | None,
    resolution_m: float,
    rover: Any,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(source, target, hours)`` for every drivable cell pair, vectorised.

    The same three gates :func:`app.pathfinder_4d.gated_move_count` and
    ``astar_4d`` apply per edge -- both cells passable and no corner cut;
    along-track step slope within ``slope_max_deg``; cross-slope within
    ``slope_lateral_max_deg`` -- and the same travel time: the mean of the
    two cell slopes through ``cost_engine.edge_travel_time_s`` -- its
    vectorised twin ``edge_travel_time_s_array``, same operation order, slip
    included since C3, bit-equal to the scalar the planner calls per edge.
    Kept identical on purpose: the deadline the planner enforces is measured
    on this graph, and a cell the planner can reach that this graph cannot
    (or the reverse) would make the rule lie in one direction or the other.
    """
    mask = np.asarray(passable, dtype=bool)
    height, width = mask.shape
    index = np.arange(height * width).reshape(height, width)
    elev = None if elevation is None else np.asarray(elevation, dtype=np.float64)
    slopes = (
        np.zeros(mask.shape, dtype=np.float64)
        if slope is None
        else np.asarray(slope, dtype=np.float64)
    )
    if elev is not None and elev.shape != mask.shape:
        raise ValueError("elevation shape must match traversable")
    if slopes.shape != mask.shape:
        raise ValueError("slope shape must match traversable")

    res = float(resolution_m)
    tan_slope_max = math.tan(math.radians(float(rover["slope_max_deg"])))
    tan_lat_max_sq = math.tan(math.radians(float(rover["slope_lateral_max_deg"]))) ** 2
    if elev is not None:
        grad_row, grad_col = _terrain_gradient(elev, res)

    sources: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    hours: list[np.ndarray] = []
    for d_row, d_col, diagonal in _HALF_OFFSETS:
        r0, r1 = max(0, -d_row), height - max(0, d_row)
        c0, c1 = max(0, -d_col), width - max(0, d_col)
        if r1 <= r0 or c1 <= c0:
            continue
        src = (slice(r0, r1), slice(c0, c1))
        dst = (slice(r0 + d_row, r1 + d_row), slice(c0 + d_col, c1 + d_col))
        ok = mask[src] & mask[dst]
        if diagonal:
            # Both cardinal neighbours must be passable: the same corner
            # rule as the two A* loops and bfs_move_count.
            ok &= mask[(slice(r0, r1), slice(c0 + d_col, c1 + d_col))]
            ok &= mask[(slice(r0 + d_row, r1 + d_row), slice(c0, c1))]
        distance_m = res * math.sqrt(2.0) if diagonal else res
        if elev is not None:
            dz = elev[dst] - elev[src]
            ok &= np.isfinite(dz) & (np.abs(dz) / distance_m <= tan_slope_max)
            norm = math.hypot(d_row, d_col)
            unit_r, unit_c = d_row / norm, d_col / norm
            g_row = 0.5 * (grad_row[src] + grad_row[dst])
            g_col = 0.5 * (grad_col[src] + grad_col[dst])
            # cost_engine.lateral_slope_tan, on arrays.
            lat_tan = np.abs(g_row * -unit_c + g_col * unit_r)
            ok &= lat_tan * lat_tan <= tan_lat_max_sq
        edge_slope = 0.5 * (slopes[src] + slopes[dst])
        # The planner's own edge_travel_time_s, vectorised in the same
        # operation order (slip included since C3): bit-equal to the scalar
        # the planner calls per edge, so a move of exactly one slice never
        # rounds differently here and there.
        travel_h = edge_travel_time_s_array(edge_slope, distance_m, rover) / 3600.0
        ok &= np.isfinite(travel_h)
        sources.append(index[src][ok])
        targets.append(index[dst][ok])
        hours.append(travel_h[ok])

    if not sources:
        empty = np.zeros(0, dtype=np.int64)
        return empty, empty, np.zeros(0, dtype=np.float64)
    return (
        np.concatenate(sources).astype(np.int64),
        np.concatenate(targets).astype(np.int64),
        np.concatenate(hours).astype(np.float64),
    )


def time_to_safe_haven_hours(
    safe: np.ndarray,
    traversable: np.ndarray,
    elevation: np.ndarray | None,
    slope: np.ndarray | None,
    resolution_m: float,
    rover: Any,
) -> np.ndarray:
    """``(H, W)`` float64: driving hours from every cell to its nearest haven.

    Zero on a haven, ``inf`` where no haven can be reached (or the cell is
    impassable). Multi-source Dijkstra over the gated graph of
    :func:`_gated_edges`, solved by SciPy's C implementation: the fine
    500x500 production grid is a quarter-million nodes and a million edges,
    which a Python heap loop would take seconds per request to cover.

    Time, not weighted cost: VIPER's rule compares the way to the haven
    against the hours until the Earth sets, and both sides have to be
    hours. The cost cube's shadow and thermal penalties price how
    UNPLEASANT the drive is; they do not change how long it takes in this
    model (``edge_travel_time_s`` depends on slope alone), so the layer is
    spatial and the time-dependence lives on the deadline side.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra

    mask = np.asarray(traversable, dtype=bool)
    havens = np.asarray(safe, dtype=bool)
    if havens.shape != mask.shape:
        raise ValueError("safe shape must match traversable")
    height, width = mask.shape
    n_cells = height * width
    result = np.full(n_cells, np.inf, dtype=np.float64)

    sources = np.flatnonzero((havens & mask).ravel())
    if sources.size == 0:
        return result.reshape(height, width)

    src, dst, hours = _gated_edges(mask, elevation, slope, resolution_m, rover)
    if src.size == 0:
        result[sources] = 0.0
        return result.reshape(height, width)

    graph = coo_matrix((hours, (src, dst)), shape=(n_cells, n_cells)).tocsr()
    distances = dijkstra(graph, directed=False, indices=sources, min_only=True)
    result[:] = distances
    result[sources] = 0.0
    return result.reshape(height, width)


def gated_shortest_drive(
    traversable: np.ndarray,
    elevation: np.ndarray | None,
    slope: np.ndarray | None,
    resolution_m: float,
    rover: Any,
    start: tuple[int, int],
    goal: tuple[int, int],
) -> tuple[float, int] | None:
    """``(hours, moves)`` of the FASTEST drivable route from *start* to
    *goal* on the gated graph, or ``None`` when no route exists.

    Sizes ``/api/plan-4d``'s default horizon (C3). The planner advances time
    in whole slices per move, ``ceil(edge hours / slice)``, so along the
    fastest route it arrives no later than ``ceil(hours / slice) + moves``
    slices -- each move can lose at most one slice to rounding -- and a
    horizon of that length plus a wait pad is sufficient whenever the pair
    is connected. The previous sizing multiplied the BFS move count by the
    slowest conceivable edge (``slope_max_deg``, diagonal); with slip that
    edge is ten times slower than a typical one and the product overshot
    ``MAX_PLAN_4D_SLICES`` on routes that fit in a quarter of it.

    Same graph, same hours as :func:`time_to_safe_haven_hours`; single-
    source Dijkstra with predecessors so the move count is that route's.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra

    mask = np.asarray(traversable, dtype=bool)
    height, width = mask.shape
    for cell in (start, goal):
        if not (0 <= cell[0] < height and 0 <= cell[1] < width) or not mask[cell]:
            return None
    origin = int(start[0]) * width + int(start[1])
    target = int(goal[0]) * width + int(goal[1])
    if origin == target:
        return 0.0, 0

    src, dst, hours = _gated_edges(mask, elevation, slope, resolution_m, rover)
    if src.size == 0:
        return None
    n_cells = height * width
    graph = coo_matrix((hours, (src, dst)), shape=(n_cells, n_cells)).tocsr()
    distances, predecessors = dijkstra(
        graph, directed=False, indices=origin, return_predecessors=True
    )
    total = float(distances[target])
    if not math.isfinite(total):
        return None
    moves = 0
    node = target
    while node != origin:
        node = int(predecessors[node])
        if node < 0:
            return None
        moves += 1
    return total, moves


# ── The Earthset deadline ────────────────────────────────────────────────────


def hours_until_earthset_cube(
    earth_cube: np.ndarray,
    slice_hours: float,
    after_end_h: np.ndarray | None = None,
) -> np.ndarray:
    """``(T, H, W)`` float64: at slice *t*, hours until the cell loses its
    Earth link -- VIPER's deadline for reaching a haven.

    Zero where the cell has no link at *t*. Where the link holds through
    the last slice the run is open-ended: ``inf`` unless *after_end_h*, the
    per-cell hours from the last slice's instant to the next loss of link
    (:func:`earthset_after_horizon_hours`), is given, in which case it is
    added to the hours remaining in the horizon.
    """
    earth = np.asarray(earth_cube, dtype=bool)
    if earth.ndim != 3:
        raise ValueError(f"earth_cube must be (T, H, W), got {earth.shape}")
    n_slices = earth.shape[0]
    step = float(slice_hours)
    if not (step > 0.0):
        raise ValueError("slice_hours must be positive")

    tail = (
        np.full(earth.shape[1:], np.inf, dtype=np.float64)
        if after_end_h is None
        else np.asarray(after_end_h, dtype=np.float64)
    )
    if tail.shape != earth.shape[1:]:
        raise ValueError("after_end_h shape must match the cube's slices")

    out = np.empty(earth.shape, dtype=np.float64)
    # Backward scan: hours until the first unlinked slice at or after t.
    following = tail
    for index in range(n_slices - 1, -1, -1):
        linked = earth[index]
        if index == n_slices - 1:
            here = np.where(linked, tail, 0.0)
        else:
            here = np.where(linked, following + step, 0.0)
        out[index] = here
        following = here
    return out


def _body_directions(metadata: dict[str, Any], moment, bodies: tuple[str, ...]):
    """Grid-frame azimuth and elevation of each body at *moment*."""
    from . import ephemeris
    from .illumination_series import _grid_north_azimuth, _window_centre_latlon

    lat_deg, lon_deg = _window_centre_latlon(metadata)
    north_grid_az = _grid_north_azimuth(metadata)
    et = ephemeris.utc_to_et(moment.strftime("%Y-%m-%dT%H:%M:%S"))
    out: dict[str, tuple[float, float]] = {}
    for body in bodies:
        true_az, elev = ephemeris.sun_azel_from_vector(
            ephemeris.body_vector_body(body, et), lat_deg, lon_deg
        )
        out[body] = (
            float(ephemeris.true_azimuth_to_grid_azimuth(true_az, north_grid_az)),
            float(elev),
        )
    return out


def earthset_after_horizon_hours(
    horizon: np.ndarray,
    metadata: dict[str, Any],
    end_utc: str,
    lookahead_hours: float = DEFAULT_EARTHSET_LOOKAHEAD_HOURS,
    step_hours: float = 1.0,
) -> np.ndarray:
    """``(H, W)`` float64: hours after *end_utc* until each cell first loses
    its Earth link, sampled every *step_hours* for up to *lookahead_hours*;
    ``inf`` where the link outlasts the lookahead.

    Samples start one step AFTER *end_utc*: the instant itself is the plan's
    last slice, which the plan's own Earth cube already describes.
    """
    from datetime import timedelta

    from .earth_visibility import earth_visible_mask
    from .illumination_series import _parse_start_utc

    cube = np.asarray(horizon)
    if cube.ndim != 3:
        raise ValueError(f"horizon must be (n_azimuth, H, W), got {cube.shape}")
    start = _parse_start_utc(end_utc)
    step = float(step_hours)
    if not (step > 0.0):
        raise ValueError("step_hours must be positive")
    n_steps = max(1, int(math.ceil(float(lookahead_hours) / step)))

    result = np.full(cube.shape[1:], np.inf, dtype=np.float64)
    for index in range(1, n_steps + 1):
        moment = start + timedelta(hours=step * index)
        grid_az, elev = _body_directions(metadata, moment, ("EARTH",))["EARTH"]
        linked = earth_visible_mask(cube, grid_az, elev)
        newly_lost = np.isinf(result) & ~linked
        result[newly_lost] = step * index
        if not np.isinf(result).any():
            break
    return result


# ── The map ──────────────────────────────────────────────────────────────────


def build_safe_haven_map(
    horizon: np.ndarray,
    metadata: dict[str, Any],
    traversable: np.ndarray,
    rover: Any,
    start_utc: str,
    span_hours: float = DEFAULT_SAFE_HAVEN_SPAN_HOURS,
    step_hours: float = DEFAULT_SAFE_HAVEN_STEP_HOURS,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Run the Sun and the Earth over one window and apply the rule.

    Returns ``(layers, info)``. ``layers``: ``safe_haven`` (bool),
    ``max_dark_hours_without_dte`` (h), ``earth_below_hours`` (h without a
    link in the window), ``ever_lit`` (bool). ``info`` carries the window,
    the rover's endurance and the summary counts.

    Raises whatever spiceypy raises without kernels; :func:`safe_haven_for_grids`
    turns that into an ``unavailable`` verdict.
    """
    from datetime import timedelta

    from .earth_visibility import earth_visible_mask
    from .illumination import illuminated_mask
    from .illumination_series import _parse_start_utc

    cube = np.asarray(horizon)
    passable = np.asarray(traversable, dtype=bool)
    if cube.ndim != 3 or tuple(cube.shape[1:]) != passable.shape:
        raise ValueError(
            f"horizon {cube.shape} does not match the traversable grid {passable.shape}"
        )
    step = float(step_hours)
    if not (step > 0.0) or not (float(span_hours) > 0.0):
        raise ValueError("span_hours and step_hours must be positive")
    n_steps = max(1, int(math.ceil(float(span_hours) / step)))
    start = _parse_start_utc(start_utc)

    tally = _DarkRunTally(passable.shape, step)
    for index in range(n_steps):
        moment = start + timedelta(hours=step * index)
        directions = _body_directions(metadata, moment, ("SUN", "EARTH"))
        sun_az, sun_el = directions["SUN"]
        earth_az, earth_el = directions["EARTH"]
        tally.push(
            illuminated_mask(cube, sun_az, sun_el),
            earth_visible_mask(cube, earth_az, earth_el),
        )

    endurance = float(rover["h_max_shadow_h"])
    safe = safe_haven_mask(tally.longest, tally.ever_lit, passable, endurance)
    earth_below_hours = tally.unlinked_steps.astype(np.float64) * step
    n_traversable = int(passable.sum())
    n_safe = int(safe.sum())

    layers = {
        "safe_haven": safe,
        "max_dark_hours_without_dte": tally.longest,
        "earth_below_hours": earth_below_hours,
        "ever_lit": tally.ever_lit,
    }
    info = {
        "model": "spice_horizon",
        "rule": (
            "safe haven: while the Earth is below the horizon, continuous shadow "
            "<= h_max_shadow_h, and lit at least once in the window (VIPER; "
            "Shirley & Balaban 2022)"
        ),
        "start_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "span_hours": float(span_hours),
        "step_hours": step,
        "n_steps": int(n_steps),
        "rover_id": rover.get("id"),
        "h_max_shadow_h": endurance,
        "safe_haven_cells": n_safe,
        "traversable_cells": n_traversable,
        "safe_haven_fraction": (n_safe / n_traversable) if n_traversable else 0.0,
        "earth_below_fraction": float(np.mean(tally.unlinked_steps / float(n_steps))),
    }
    return layers, info


# ── For the loaded grids, with a small cache ─────────────────────────────────

_CACHE_LIMIT: int = 8
_cache: dict[tuple, tuple[dict[str, np.ndarray], np.ndarray, dict[str, Any]]] = {}


def clear_safe_haven_cache() -> None:
    _cache.clear()


def safe_haven_for_grids(
    grids: dict[str, Any],
    rover_id: str,
    start_utc: str | None,
    span_hours: float = DEFAULT_SAFE_HAVEN_SPAN_HOURS,
    step_hours: float = DEFAULT_SAFE_HAVEN_STEP_HOURS,
) -> tuple[dict[str, np.ndarray] | None, np.ndarray | None, dict[str, Any]]:
    """The map and the time-to-haven layer for the loaded grids and a rover.

    ``(layers, time_to_haven_h, info)``; the first two are ``None`` and
    ``info["model"] == "unavailable"`` (with ``reason``) when there is no
    epoch, no horizon cube beside the processed grids, or no kernels.

    A month of masks plus a Dijkstra over the fine grid is ~1 s, and
    ``/api/cell-telemetry`` is a hover endpoint, so results are kept in a
    small cache keyed by (processed_dir, rover, epoch, window).
    """
    from .constants import get_rover
    from .illumination_series import HORIZON_CACHE_FILENAME, horizon_cache_path
    from .rover_grids import grids_for_rover

    metadata = grids.get("metadata") or {}
    if not start_utc:
        return None, None, {
            "model": "unavailable",
            "reason": (
                "no start epoch given; a safe haven is defined against the "
                "Earth's and the Sun's motion and cannot be computed without one"
            ),
        }
    cache_path = horizon_cache_path(metadata)
    if cache_path is None:
        return None, None, {
            "model": "unavailable",
            "reason": (
                f"no {HORIZON_CACHE_FILENAME} beside the processed grids; run "
                "scripts/build_horizon_cache.py to enable the safe haven map"
            ),
        }

    shape = tuple(int(v) for v in np.asarray(grids["elevation"]).shape)
    key = (
        str(metadata.get("processed_dir")),
        str(rover_id),
        str(start_utc),
        float(span_hours),
        float(step_hours),
        shape,
    )
    hit = _cache.get(key)
    if hit is not None:
        return hit

    try:
        rover = get_rover(rover_id)
        for_rover = grids_for_rover(grids, rover_id)
        horizon = np.load(cache_path, mmap_mode="r")
        if horizon.ndim != 3 or tuple(horizon.shape[1:]) != shape:
            raise ValueError(
                f"horizon cache {horizon.shape} does not match the grid {shape}"
            )
        layers, info = build_safe_haven_map(
            horizon, metadata, for_rover["traversable"], rover, start_utc,
            span_hours=span_hours, step_hours=step_hours,
        )
        time_to_haven = time_to_safe_haven_hours(
            layers["safe_haven"],
            for_rover["traversable"],
            grids.get("elevation"),
            grids.get("slope"),
            float(metadata["resolution_m"]),
            rover,
        )
    except Exception as exc:
        # Deliberately broad, as build_shadow_series: spiceypy raises assorted
        # builtin types when kernels are missing, and a missing kernel must
        # degrade to an honest verdict rather than take an endpoint down.
        return None, None, {
            "model": "unavailable",
            "reason": f"safe haven map unavailable ({exc})",
        }

    info["horizon_cache"] = cache_path
    passable = np.asarray(for_rover["traversable"], dtype=bool)
    info["time_to_haven_finite_fraction"] = (
        float(np.isfinite(time_to_haven[passable]).mean()) if passable.any() else 0.0
    )
    if len(_cache) >= _CACHE_LIMIT:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (layers, time_to_haven, info)
    return layers, time_to_haven, info


# ── SHERPA's margins along a route ───────────────────────────────────────────

#: A slice counts as dark when at least this much of it is shadowed -- the
#: planner's own threshold (pathfinder_4d._DARK_RATIO_THRESHOLD).
_DARK_RATIO_THRESHOLD: float = 0.5


def route_margins(
    states: list[tuple[int, int, int]],
    batteries_wh: list[float] | None,
    shadow_cube: np.ndarray | None,
    earthset_cube: np.ndarray | None,
    slice_hours: float,
    rover: Any,
) -> dict[str, float | None]:
    """SHERPA's three margins for a planned route (Shirley & Balaban 2022).

    * ``time_to_sun_shadow_min_h`` / ``_mean_h``: at each state, hours until
      that cell next goes dark in the shadow cube (0 if it is dark now; a
      cell lit through the horizon is open-ended and not counted); the min
      and mean of the counted states.
    * ``time_to_dsn_shadow_min_h``: the shortest Earth-link time left at any
      state -- the deadline cube read along the route.
    * ``time_to_zero_soc_min_h``: at each state, how long the battery would
      last if the rover stopped there in full shadow (housekeeping power
      alone, the same ``p_shadow_w`` the planner drains by); the minimum.

    ``None`` wherever a margin is open-ended or its input was not supplied
    -- never a fabricated number.
    """
    from .cost_engine import housekeeping_power_w

    step = float(slice_hours)

    def _summary(values: list[float]) -> tuple[float | None, float | None]:
        if not values:
            return None, None
        return round(min(values), 4), round(float(np.mean(values)), 4)

    to_shadow: list[float] = []
    if shadow_cube is not None:
        shadow = np.asarray(shadow_cube, dtype=np.float64)
        n_slices = shadow.shape[0]
        for row, col, index in states:
            column = shadow[index:, row, col] >= _DARK_RATIO_THRESHOLD
            dark_at = np.flatnonzero(column)
            if dark_at.size:
                to_shadow.append(float(dark_at[0]) * step)
    shadow_min, shadow_mean = _summary(to_shadow)

    dsn_min: float | None = None
    if earthset_cube is not None:
        deadline = np.asarray(earthset_cube, dtype=np.float64)
        finite = [
            float(deadline[t, r, c])
            for r, c, t in states
            if math.isfinite(float(deadline[t, r, c]))
        ]
        dsn_min = round(min(finite), 4) if finite else None

    zero_soc_min: float | None = None
    if batteries_wh is not None:
        dark_w = housekeeping_power_w(1.0, rover)
        if dark_w > 0.0:
            zero_soc_min = round(min(float(b) / dark_w for b in batteries_wh), 4)

    return {
        "time_to_sun_shadow_min_h": shadow_min,
        "time_to_sun_shadow_mean_h": shadow_mean,
        "time_to_dsn_shadow_min_h": dsn_min,
        "time_to_zero_soc_min_h": zero_soc_min,
    }


def block_min(grid: np.ndarray, factor: int) -> np.ndarray:
    """Block-reduce by taking each block's MINIMUM.

    The Earthset lookahead is coarsened this way for the planner: a coarse
    block has lost its link as soon as any fine cell in it has, the same
    conservative direction as ``coarsen_traversable``'s AND.
    """
    arr = np.asarray(grid, dtype=np.float64)
    factor = int(factor)
    if factor <= 1:
        return arr
    height, width = arr.shape
    if height % factor or width % factor:
        raise ValueError(f"shape {arr.shape} is not divisible by factor {factor}")
    return arr.reshape(height // factor, factor, width // factor, factor).min(axis=(1, 3))
