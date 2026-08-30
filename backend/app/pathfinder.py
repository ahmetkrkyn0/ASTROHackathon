"""High-performance A* pathfinder for the LunaPath lunar rover.

Two-phase design:
  1. Precompute per-cell cost grid via cost_engine.compute_cost_grid()
     (multi-criteria: slope, energy, shadow, thermal + AHP weights).
  2. Run A* with trapezoidal edge interpolation over the cost grid.

Edge cost formula:
  cost(u→v) = distance(u,v) * (1 + (cost_grid[u] + cost_grid[v]) / 2)

Heuristic: Octile distance scaled by (1 + MIN_COST) — admissible & consistent.

Optimisations:
  - NumPy float32/bool/int32 arrays for g_score, closed, came_from
  - heapq with lazy duplicate strategy (no decrease-key)
  - Precomputed 8-direction offset table
  - Diagonal corner-cutting safety checks
  - Tie-breaking: (f, h, counter) — prefer nodes closer to goal
  - Early exit on goal expansion
"""

from __future__ import annotations

import heapq
import math
import time
from typing import Any

import numpy as np

from .cost_engine import (
    COST_MODEL_ID,
    compute_cost_grid,
    f_thermal,
    resolve_weights,
)
from .constants import LOG_BARRIER_MU, get_rover

# Offsets live in _astar_core, built from the grid's ACTUAL resolution. A
# module-level copy used to sit here hardcoding 80 m -- shadowed by the local
# one, so it was dead, and misleading: the production grid is 5 m/px.
# (Backend review, #16.)


# ════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ════════════════════════════════════════════════════════════════════════════

def astar(
    grids: dict[str, Any],
    start: tuple[int, int],
    goal: tuple[int, int],
    weights: dict[str, float] | None = None,
    constraints: dict | None = None,
    rover: dict[str, Any] | None = None,
) -> dict:
    """Run optimised A* and return path + metrics.

    Parameters
    ----------
    grids : dict
        Must contain keys: elevation, slope (or slope_grid), thermal,
        shadow_ratio, traversable, metadata (with resolution_m).
    start, goal : (row, col)
    weights : optional AHP weight overrides
    constraints : optional constraint overrides (unused in fast mode,
                  kept for API compat)

    Returns
    -------
    dict with keys: path_pixels, metrics, error
    """
    t0 = time.perf_counter()

    # ── Unpack grids ────────────────────────────────────────────────────
    traversable = np.asarray(grids["traversable"], dtype=bool)
    rows, cols = traversable.shape
    resolution = float(grids["metadata"]["resolution_m"])

    # Slope grid — accept both naming conventions
    slope_grid = np.asarray(
        grids.get("slope", grids.get("slope_grid", np.zeros((rows, cols)))),
        dtype=np.float64,
    )
    thermal_grid = np.asarray(grids["thermal"], dtype=np.float64)
    shadow_grid = np.asarray(grids["shadow_ratio"], dtype=np.float64)
    elevation = np.asarray(grids["elevation"], dtype=np.float64)

    # ── Bounds / traversability pre-checks ──────────────────────────────
    if not _in_bounds(start[0], start[1], rows, cols):
        return _empty_result("Start out of bounds")
    if not _in_bounds(goal[0], goal[1], rows, cols):
        return _empty_result("Goal out of bounds")
    if not traversable[start]:
        return _empty_result("Start is not traversable")
    if not traversable[goal]:
        return _empty_result("Goal is not traversable")

    # ── Phase 1: Cost grid ──────────────────────────────────────────────
    # Each traversable cell → [0.01, ∞), blocked cells → inf.
    #
    # grids["cost"] is already the grid rover_grids.grids_for_rover computed
    # for exactly this rover and these weights, and recomputing it here threw
    # that away and spent another ~0.75 s per request producing a bit-identical
    # array (/api/compare paid it ten times over). Reuse it when the caller
    # says it matches, and fall back to computing it otherwise. (Review #5.)
    rover_cfg = get_rover() if rover is None else rover
    cost_grid = _resolve_cost_grid(
        grids, slope_grid, thermal_grid, shadow_grid,
        resolution, traversable, weights, rover_cfg,
    )

    # Derive MIN_COST for heuristic scaling (admissibility guarantee)
    finite_mask = np.isfinite(cost_grid)
    if not np.any(finite_mask):
        return _empty_result("No traversable cells")
    min_cost = float(np.min(cost_grid[finite_mask]))  # ≥ 0.01

    # ── Phase 2: A* search ──────────────────────────────────────────────
    # constraints is honoured rather than ignored: /api/plan-multi and
    # /api/compare pass each mission profile's declared limits, and until now
    # this function's own docstring admitted it dropped them on the floor, so
    # a profile advertising a 20 deg ceiling planned identically to one
    # advertising 25. (Round 3 review, M-7.)
    profile_slope_max = None
    if constraints:
        raw = constraints.get("max_slope_deg")
        if raw is not None:
            profile_slope_max = float(raw)

    path_pixels, nodes_expanded, rejections = _astar_core(
        cost_grid, traversable, elevation, thermal_grid, slope_grid,
        start, goal, rows, cols, resolution, min_cost, rover_cfg,
        profile_slope_max,
    )

    comp_ms = (time.perf_counter() - t0) * 1000.0
    if path_pixels is None:
        # A bare "No path found" is useless when the hard edge constraints
        # are what closed the route: on a site whose median slope is 21 deg,
        # a rover with a 15 deg roll-over limit fragments the passable area
        # into components of a few hundred cells, and the caller deserves to
        # be told THAT rather than left to guess. (Round 3 review, H-1.)
        return _empty_result(
            _no_path_reason(rejections, rover_cfg, profile_slope_max),
            comp_ms,
            rejections,
        )

    # ── Post-process metrics ────────────────────────────────────────────
    metrics = _compute_path_metrics(
        path_pixels, elevation, thermal_grid, cost_grid, resolution, comp_ms,
        nodes_expanded, rover_cfg, slope_grid,
    )
    metrics["edges_rejected"] = dict(rejections)
    metrics["constraints_applied"] = {
        "max_slope_deg": (
            profile_slope_max
            if profile_slope_max is not None
            else float(rover_cfg["slope_max_deg"])
        ),
        "slope_lateral_max_deg": float(rover_cfg["slope_lateral_max_deg"]),
        "source": "profile" if profile_slope_max is not None else "rover",
    }

    return {
        "path_pixels": path_pixels,
        "metrics": metrics,
        "error": None,
    }


def _resolve_cost_grid(
    grids: dict[str, Any],
    slope_grid: np.ndarray,
    thermal_grid: np.ndarray,
    shadow_grid: np.ndarray,
    resolution: float,
    traversable: np.ndarray,
    weights: dict[str, float] | None,
    rover_cfg: dict[str, Any],
) -> np.ndarray:
    """Reuse the caller's cost grid when it was built for this exact request.

    ``grids_for_rover`` stamps ``metadata["rover_id"]`` and
    ``metadata["cost_weights"]`` onto the grids it adapts, so a cost grid is
    reusable only when BOTH match what this call was asked for -- and only
    when its shape matches the grids it is supposed to describe.
    """
    metadata = grids.get("metadata") or {}
    cached = grids.get("cost")

    if cached is not None and np.asarray(cached).shape == slope_grid.shape:
        resolved = resolve_weights(weights, rover_cfg)
        stamped_rover = metadata.get("rover_id")
        stamped_weights = metadata.get("cost_weights")
        if (
            stamped_rover is not None
            and stamped_rover == rover_cfg.get("id")
            and stamped_weights == resolved
            # A grid produced by an older formula (a P1 .npy on disk) is not
            # this build's grid even when the rover and weights agree.
            and metadata.get("cost_model") == COST_MODEL_ID
        ):
            return np.asarray(cached, dtype=np.float32)

    return compute_cost_grid(
        slope_grid, thermal_grid, shadow_grid,
        resolution_m=resolution,
        traversable=traversable,
        weights=weights,
        rover=rover_cfg,
    ).astype(np.float32)


# ════════════════════════════════════════════════════════════════════════════
#  HARD-CONSTRAINT BARRIER
# ════════════════════════════════════════════════════════════════════════════

_BARRIER_EPS: float = 1e-9


_BARRIER_TABLE_BINS: int = 1024


def _geometric_barrier(
    along_deg: float,
    lateral_deg: float,
    slope_max_deg: float,
    lateral_max_deg: float,
    mu: float = LOG_BARRIER_MU,
) -> float:
    """Log-barrier on the two geometric limits.

    Same shape as ``cost_engine.edge_barrier_penalty`` but without the
    thermal terms, which are precomputed per cell. Reference form; the A*
    loop uses the tabulated version below.
    """
    slack_slope = 1.0 - along_deg / slope_max_deg
    slack_lat = 1.0 - lateral_deg / lateral_max_deg
    if slack_slope <= _BARRIER_EPS or slack_lat <= _BARRIER_EPS:
        return math.inf
    return -mu * (math.log(min(1.0, slack_slope)) + math.log(min(1.0, slack_lat)))


def _barrier_table(
    limit_deg: float, bins: int = _BARRIER_TABLE_BINS, mu: float = LOG_BARRIER_MU
) -> tuple[list[float], float]:
    """Tabulate ``-mu * log(1 - atan(t)/limit)`` over t in [0, tan(limit)].

    The A* inner loop evaluates the barrier once per candidate edge --
    roughly 1.6 million times on the production grid -- and the exact form
    costs an ``atan``, a ``degrees`` and a ``log`` each time. Tabulating
    against the TANGENT (which the loop already has, because the hard
    rejections are done in tangent space to avoid trigonometry) turns that
    into an integer index and a list lookup. Measured on the 500x500 grid:
    8.8 s of planning back down to the pre-barrier range.

    The barrier is a soft shaping term whose whole purpose is a gradient
    away from a wall the hard gate already enforces, so quantising it at
    1024 bins changes no decision the exact form would make differently at
    any resolution the grid can express.

    Returns ``(table, inverse_step)`` where the index for a tangent ``t`` is
    ``int(t * inverse_step)``, clamped to the last bin.
    """
    tan_limit = math.tan(math.radians(limit_deg))
    if tan_limit <= 0.0:
        return [math.inf], 0.0
    step = tan_limit / (bins - 1)
    table: list[float] = []
    for i in range(bins):
        degrees_here = math.degrees(math.atan(i * step))
        slack = 1.0 - degrees_here / limit_deg
        table.append(
            math.inf if slack <= _BARRIER_EPS else -mu * math.log(min(1.0, slack))
        )
    return table, 1.0 / step


def _thermal_barrier_grid(
    thermal: np.ndarray, rover: dict[str, Any], mu: float = LOG_BARRIER_MU
) -> np.ndarray:
    """Per-cell thermal barrier, vectorised.

    The barrier's thermal terms depend only on the cell being entered, so
    evaluating them once per cell instead of once per edge keeps the inner
    loop's added cost down to two logarithms.

    Anchored to ``THERMAL_MIN_TRAVERSABLE_C`` and the rover's own electronics
    ceiling -- see ``cost_engine.thermal_barrier_terms`` for why the spec's
    fixed -20/+95 inner-temperature band was not usable here.
    """
    from . import constants as C
    from .cost_engine import _surface_ceiling_c

    surface = np.asarray(thermal, dtype=np.float64)
    cold_floor = float(C.THERMAL_MIN_TRAVERSABLE_C)
    cold_span = abs(cold_floor)

    with np.errstate(divide="ignore", invalid="ignore"):
        slack_cold = np.minimum(1.0, (surface - cold_floor) / cold_span)
        total = -mu * np.log(slack_cold)

        ceiling = _surface_ceiling_c(rover)
        if ceiling is not None and float(ceiling) > 0.0:
            slack_hot = np.minimum(1.0, (float(ceiling) - surface) / float(ceiling))
            total = total - mu * np.log(slack_hot)

    # Non-finite means "outside the barrier's domain", which the caller must
    # treat as an impassable edge. NaN thermal lands here too, which is the
    # honest answer for a cell with no temperature.
    return np.where(np.isfinite(total), total, np.inf)


# ════════════════════════════════════════════════════════════════════════════
#  A* CORE — tight inner loop
# ════════════════════════════════════════════════════════════════════════════

def _astar_core(
    cost_grid: np.ndarray,
    traversable: np.ndarray,
    elevation: np.ndarray,
    thermal: np.ndarray,
    slope_grid: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    rows: int,
    cols: int,
    resolution: float,
    min_cost: float,
    rover: dict[str, Any],
    profile_slope_max_deg: float | None = None,
) -> tuple[list[list[int]] | None, int, dict[str, int]]:
    """Inner A* loop. Returns (path_pixels or None, nodes_expanded, rejections).

    Hard constraints enforced per EDGE, which is the only place they can be
    expressed (round 3 review, H-1 and H-2):

    * **Along-track step slope.** ``traversable`` gates on the ``np.gradient``
      slope grid -- a central difference, so effectively a two-cell baseline
      and a smoothed value. The rover does not drive that; it drives the
      one-cell step between adjacent centres. On the production grid 920
      passable-to-passable cardinal neighbour pairs had a step steeper than
      lpr_1's 25 deg limit, and routes did take them: the default plan
      reported a 25.08 deg segment, and at w_thermal=2.0 a 27.10 deg one --
      over a ceiling the API and ``Corridor.max_slope_deg`` both publish as a
      safety limit. The step slope is now computed from elevation and
      rejected against the same limit.

    * **Lateral (roll-over) slope.** ``slope_lateral_max_deg`` appeared
      exactly once in the entire codebase, inside a log-barrier function no
      production caller ever invoked, so the rover's tip-over limit was
      checked nowhere. Cross-slope is a property of the edge's direction, not
      of the cell, which is why no cell mask could ever have expressed it.

    A soft ``edge_barrier_penalty`` rides on top, so the planner is pushed
    away from both limits before it reaches them rather than only refused at
    the wall.
    """

    # Distance multipliers relative to resolution
    cardinal_dist = resolution
    diagonal_dist = resolution * math.sqrt(2)

    # Update offsets with actual resolution. The last two entries are the
    # unit travel direction in (row, col) space, used to resolve the terrain
    # gradient into along-track and cross-track components.
    _r2 = 1.0 / math.sqrt(2.0)
    offsets = (
        (-1,  0, cardinal_dist, False, -1.0,  0.0),
        ( 1,  0, cardinal_dist, False,  1.0,  0.0),
        ( 0, -1, cardinal_dist, False,  0.0, -1.0),
        ( 0,  1, cardinal_dist, False,  0.0,  1.0),
        (-1, -1, diagonal_dist, True,  -_r2, -_r2),
        (-1,  1, diagonal_dist, True,  -_r2,  _r2),
        ( 1, -1, diagonal_dist, True,   _r2, -_r2),
        ( 1,  1, diagonal_dist, True,   _r2,  _r2),
    )

    # ── Hard-constraint geometry ────────────────────────────────────────
    # Compared in TANGENT space so the inner loop needs no trigonometry: a
    # step is too steep when |dz| / horizontal > tan(limit), and Pythagoras
    # on the gradient vector gives the cross-slope as
    # tan(lat)^2 = tan(cell)^2 - tan(along)^2 (see cost_engine.lateral_slope_deg).
    slope_max_deg = float(rover["slope_max_deg"])
    if profile_slope_max_deg is not None:
        slope_max_deg = min(slope_max_deg, float(profile_slope_max_deg))
    lateral_max_deg = float(rover["slope_lateral_max_deg"])
    tan_slope_max = math.tan(math.radians(slope_max_deg))
    tan_lat_max_sq = math.tan(math.radians(lateral_max_deg)) ** 2
    slope_barrier_table, slope_barrier_scale = _barrier_table(slope_max_deg)
    lat_barrier_table, lat_barrier_scale = _barrier_table(lateral_max_deg)
    slope_barrier_last = len(slope_barrier_table) - 1
    lat_barrier_last = len(lat_barrier_table) - 1

    # The terrain gradient, as rise per metre along each axis. Both
    # components come from the SAME elevation field, so decomposing them
    # into along-track and cross-track is internally consistent -- unlike
    # subtracting a one-cell step slope from the np.gradient cell slope,
    # which mixes two different estimators of the same quantity and, on this
    # grid, left a residual so noisy that it cut connectivity from 97.2 to
    # 0 percent. Measured with the decomposition below, the 18 deg roll-over
    # limit keeps 92.7 percent of passable cells mutually reachable.
    grad_row, grad_col = np.gradient(
        np.asarray(elevation, dtype=np.float64), float(resolution)
    )
    # .tolist() rather than a NumPy view: every read in the inner loop would
    # otherwise allocate a NumPy scalar, and this loop performs millions of
    # them. Python lists of floats index straight to a float object.
    grad_row_flat = np.nan_to_num(grad_row, nan=0.0).ravel().tolist()
    grad_col_flat = np.nan_to_num(grad_col, nan=0.0).ravel().tolist()

    # The thermal half of the barrier depends only on the destination cell,
    # so it is evaluated once per cell rather than once per edge.
    thermal_barrier_flat = _thermal_barrier_grid(thermal, rover).ravel().tolist()
    elev_flat = np.asarray(elevation, dtype=np.float64).ravel().tolist()

    # ── Heuristic: octile distance × (1 + min_cost) ────────────────────
    gr, gc = goal
    h_scale = 1.0 + min_cost  # admissible scaling factor

    def heuristic(r: int, c: int) -> float:
        dr = abs(r - gr)
        dc = abs(c - gc)
        # octile = cardinal_dist * (dr+dc) + (diagonal_dist - 2*cardinal_dist) * min(dr,dc)
        return h_scale * (
            cardinal_dist * (dr + dc)
            + (diagonal_dist - 2.0 * cardinal_dist) * min(dr, dc)
        )

    # ── NumPy-backed storage ────────────────────────────────────────────
    total_cells = rows * cols

    # Python lists, not NumPy arrays. These are touched once per candidate
    # edge -- millions of times on the production grid -- and every NumPy
    # element read allocates a scalar object. Lists also keep full float64
    # precision, where the previous float32 g_score quantised path costs to
    # about 0.06 once they passed 1e6.
    g_score = [math.inf] * total_cells
    closed = [False] * total_cells
    came_from = [-1] * total_cells

    # Flatten helpers
    start_idx = start[0] * cols + start[1]
    goal_idx = goal[0] * cols + goal[1]

    g_score[start_idx] = 0.0
    h_start = heuristic(start[0], start[1])

    # Priority queue: (f_score, h_score, counter, flat_index)
    # Tie-break: lower h preferred (closer to goal)
    counter = 0
    open_heap: list[tuple[float, float, int, int]] = []
    heapq.heappush(open_heap, (h_start, h_start, counter, start_idx))

    nodes_expanded = 0
    rejections = {"step_slope": 0, "lateral_slope": 0, "thermal_barrier": 0}

    # ── Flat cost/traversable views for fast indexing ───────────────────
    cost_flat = cost_grid.ravel().tolist()
    trav_flat = traversable.ravel().tolist()

    while open_heap:
        f_cur, _, _, cur_idx = heapq.heappop(open_heap)

        # Lazy duplicate skip
        if closed[cur_idx]:
            continue
        closed[cur_idx] = True
        nodes_expanded += 1

        # Early exit
        if cur_idx == goal_idx:
            return (
                _reconstruct_path(came_from, goal_idx, cols),
                nodes_expanded,
                rejections,
            )

        cur_r = cur_idx // cols
        cur_c = cur_idx % cols
        cur_g = g_score[cur_idx]
        cur_cost = cost_flat[cur_idx]
        cur_elev = elev_flat[cur_idx]

        for dr, dc, dist, is_diag, unit_r, unit_c in offsets:
            nr = cur_r + dr
            nc = cur_c + dc

            # Bounds check
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue

            n_idx = nr * cols + nc

            # Skip closed or non-traversable
            if closed[n_idx] or not trav_flat[n_idx]:
                continue

            # ── Diagonal corner-cutting safety ──────────────────────
            if is_diag:
                # Both adjacent cardinal cells must be traversable
                adj1_idx = cur_r * cols + nc  # (cur_r, nc)
                adj2_idx = nr * cols + cur_c  # (nr, cur_c)
                if not trav_flat[adj1_idx] or not trav_flat[adj2_idx]:
                    continue

            # ── Hard constraints on the edge itself ─────────────────
            dz = elev_flat[n_idx] - cur_elev
            if not (dz == dz):  # NaN elevation: unknown geometry, refuse
                continue
            along_tan = abs(dz) / dist
            if along_tan > tan_slope_max:
                rejections["step_slope"] += 1
                continue
            # Cross-slope: the terrain gradient projected on to the
            # direction perpendicular to travel. The perpendicular of the
            # unit vector (unit_r, unit_c) is (-unit_c, unit_r).
            g_row = 0.5 * (grad_row_flat[cur_idx] + grad_row_flat[n_idx])
            g_col = 0.5 * (grad_col_flat[cur_idx] + grad_col_flat[n_idx])
            lat_tan = g_row * (-unit_c) + g_col * unit_r
            lat_tan_sq = lat_tan * lat_tan
            if lat_tan_sq > tan_lat_max_sq:
                rejections["lateral_slope"] += 1
                continue

            barrier = thermal_barrier_flat[n_idx]
            if barrier == math.inf:
                rejections["thermal_barrier"] += 1
                continue
            slope_bin = int(along_tan * slope_barrier_scale)
            if slope_bin > slope_barrier_last:
                slope_bin = slope_barrier_last
            lat_bin = int(abs(lat_tan) * lat_barrier_scale)
            if lat_bin > lat_barrier_last:
                lat_bin = lat_barrier_last
            barrier += slope_barrier_table[slope_bin] + lat_barrier_table[lat_bin]
            if barrier == math.inf:
                rejections["step_slope"] += 1
                continue

            # ── Trapezoidal edge cost ───────────────────────────────
            n_cost = cost_flat[n_idx]
            edge_cost = dist * (1.0 + (cur_cost + n_cost) * 0.5 + barrier)

            tentative_g = cur_g + edge_cost
            if tentative_g >= g_score[n_idx]:
                continue

            g_score[n_idx] = tentative_g
            came_from[n_idx] = cur_idx
            h_val = heuristic(nr, nc)
            counter += 1
            heapq.heappush(
                open_heap,
                (tentative_g + h_val, h_val, counter, n_idx),
            )

    return None, nodes_expanded, rejections  # No path found


# ════════════════════════════════════════════════════════════════════════════
#  PATH RECONSTRUCTION
# ════════════════════════════════════════════════════════════════════════════

def _reconstruct_path(
    came_from: np.ndarray,
    goal_idx: int,
    cols: int,
) -> list[list[int]]:
    """Walk came_from chain backwards and return [[row,col], ...] start→goal."""
    path: list[list[int]] = []
    idx = goal_idx
    while idx != -1:
        r = idx // cols
        c = idx % cols
        path.append([r, c])
        idx = int(came_from[idx])
    path.reverse()
    return path


# ════════════════════════════════════════════════════════════════════════════
#  METRICS
# ════════════════════════════════════════════════════════════════════════════

def _compute_path_metrics(
    path_pixels: list[list[int]],
    elevation: np.ndarray,
    thermal: np.ndarray,
    cost_grid: np.ndarray,
    resolution: float,
    comp_ms: float,
    nodes_expanded: int,
    rover: dict[str, Any] | None = None,
    slope_grid: np.ndarray | None = None,
) -> dict:
    """Compute post-hoc path metrics for API response.

    *rover* selects the thermal envelope max_thermal_risk is measured
    against. Without it f_thermal falls back to the DEFAULT rover, so a
    plan requested for any other profile reported a risk computed from
    lpr_1's battery limits -- luvmi_m, whose envelope reaches -100 C, was
    told a comfortable -60 C route was risky, and /api/compare fed that
    number into its safest-profile ranking. (Round 2 review, M-2.)
    """
    if len(path_pixels) < 2:
        return _zero_metrics(comp_ms, nodes_expanded)

    total_distance = 0.0
    max_slope = 0.0
    max_cell_slope = 0.0
    total_weighted_cost = 0.0
    path_temps: list[float] = []

    for i, (r, c) in enumerate(path_pixels):
        path_temps.append(float(thermal[r, c]))
        if slope_grid is not None:
            cell_slope = float(slope_grid[r, c])
            if math.isfinite(cell_slope):
                max_cell_slope = max(max_cell_slope, cell_slope)
        if i == 0:
            continue

        pr, pc = path_pixels[i - 1]
        is_diag = abs(r - pr) + abs(c - pc) == 2
        d_horiz = resolution * (math.sqrt(2) if is_diag else 1.0)
        dz = float(elevation[r, c] - elevation[pr, pc])
        seg_slope = math.degrees(math.atan2(abs(dz), d_horiz))
        total_distance += math.sqrt(d_horiz ** 2 + dz ** 2)
        max_slope = max(max_slope, seg_slope)

        # Accumulate trapezoidal cost
        c_prev = float(cost_grid[pr, pc])
        c_cur = float(cost_grid[r, c])
        total_weighted_cost += d_horiz * (1.0 + (c_prev + c_cur) * 0.5)

    goal_r, goal_c = path_pixels[-1]

    return {
        "total_distance_m": round(total_distance, 2),
        "total_energy_wh": 0.0,  # Not tracked in fast mode
        "total_shadow_hours": 0.0,  # Not tracked in fast mode
        # Two different quantities used to share this one name across a
        # single /api/plan response: here it is the SEGMENT slope, computed
        # from the elevation difference across each step the rover actually
        # drives, while summary.max_slope_deg is the CELL slope from the
        # np.gradient grid. On one production route they read 25.08 and
        # 24.89. Both are now named for what they measure and both are
        # reported here, so nothing has to be inferred from context.
        # (Round 3 review, H-2.)
        "max_slope_deg": round(max_slope, 2),
        "max_segment_slope_deg": round(max_slope, 2),
        "max_cell_slope_deg": round(max_cell_slope, 2),
        "slope_definitions": {
            "max_segment_slope_deg": "elevation difference across each driven step",
            "max_cell_slope_deg": "np.gradient slope grid, the traversability gate",
        },
        "max_thermal_risk": round(
            max(f_thermal(t, rover=rover) for t in path_temps), 4
        ),
        "min_surface_temp_c": round(min(path_temps), 2),
        "total_weighted_cost": round(total_weighted_cost, 4),
        # Weighted METRES. app.pathfinder_4d's total_cost is in weighted
        # HOURS -- the two planners minimise different objectives, so their
        # totals are not comparable and the unit says so. (Round 3, M-6.)
        "cost_units": "weighted_metres",
        "path_length_nodes": len(path_pixels),
        "computation_time_ms": round(comp_ms, 1),
        "nodes_expanded": nodes_expanded,
    }


def _zero_metrics(comp_ms: float = 0.0, nodes_expanded: int = 0) -> dict:
    return {
        "constraints_applied": None,
        "edges_rejected": {},
        "total_distance_m": 0.0,
        "total_energy_wh": 0.0,
        "total_shadow_hours": 0.0,
        "max_slope_deg": 0.0,
        "max_segment_slope_deg": 0.0,
        "max_cell_slope_deg": 0.0,
        "max_thermal_risk": 0.0,
        "min_surface_temp_c": 0.0,
        "total_weighted_cost": 0.0,
        "cost_units": "weighted_metres",
        "path_length_nodes": 0,
        "computation_time_ms": round(comp_ms, 1),
        "nodes_expanded": nodes_expanded,
    }


# ════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _empty_result(
    error: str,
    comp_time_ms: float = 0.0,
    rejections: dict[str, int] | None = None,
) -> dict:
    metrics = _zero_metrics(comp_time_ms)
    if rejections is not None:
        metrics["edges_rejected"] = dict(rejections)
    return {
        "path_pixels": [],
        "metrics": metrics,
        "error": error,
    }


def _no_path_reason(
    rejections: dict[str, int],
    rover: dict[str, Any],
    profile_slope_max_deg: float | None,
) -> str:
    """Explain which constraint closed the route, when one did."""
    lateral = rejections.get("lateral_slope", 0)
    along = rejections.get("step_slope", 0)
    thermal = rejections.get("thermal_barrier", 0)
    if not (lateral or along or thermal):
        return "No path found"

    slope_limit = float(rover["slope_max_deg"])
    if profile_slope_max_deg is not None:
        slope_limit = min(slope_limit, float(profile_slope_max_deg))

    parts: list[str] = []
    if lateral:
        parts.append(
            f"{lateral} edges exceeded the {rover['slope_lateral_max_deg']} deg "
            "roll-over (cross-slope) limit"
        )
    if along:
        parts.append(
            f"{along} edges exceeded the {slope_limit:g} deg step-slope limit"
        )
    if thermal:
        parts.append(f"{thermal} edges entered cells outside the thermal envelope")
    return (
        "No path found for "
        f"{rover.get('name', rover.get('id', 'this rover'))}: "
        + "; ".join(parts)
        + ". The terrain between these points is steeper than this rover can "
        "cross safely -- try a rover with a higher roll-over limit, or points "
        "in gentler terrain."
    )


def _in_bounds(r: int, c: int, rows: int, cols: int) -> bool:
    return 0 <= r < rows and 0 <= c < cols
