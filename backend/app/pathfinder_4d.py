"""Time-expanded A*: states are (row, col, time_slice).

Two edge families:

* MOVE  (r, c, t) -> (r', c', t + dt)   dt = ceil(travel_time / slice_hours)
* WAIT  (r, c, t) -> (r,  c,  t + 1)

The WAIT edge is the point of the whole thing. On the lunar pole the right
answer is often "stop, let the Sun come, then cross" -- a decision a static
planner cannot express.

The 2-D ``app.pathfinder.astar`` is untouched; this is an additional
planner, not a replacement.
"""

from __future__ import annotations

import heapq
import math
import time
from collections import deque
from collections.abc import Mapping
from typing import Any

import numpy as np

from .cost_engine import edge_travel_time_s, lateral_slope_tan

# Every reason this planner can refuse an edge. Declared once so the metrics
# always carry the full set of keys and a caller can tell "checked, none"
# from "not counted". (Round 4 review, H-2.)
REJECTION_KEYS: tuple[str, ...] = (
    "step_slope",
    "lateral_slope",
    "nan_elevation",
    "untraversable",
    "corner_cut",
    "cost_infinite",
    "horizon",
)


def _empty_rejections() -> dict[str, int]:
    return {key: 0 for key in REJECTION_KEYS}


def no_path_reason_4d(
    rejections: dict[str, int],
    rover: Mapping[str, Any],
    n_slices: int,
    slice_hours: float,
) -> str:
    """Explain which constraint closed a 4-D route.

    Round 3 gave the 2-D planner ``_no_path_reason`` and left this planner
    with one string: "No path found within the time horizon". That message is
    not merely unhelpful, it is usually WRONG. At the default ``coarsen=4``,
    618 of 8 768 passable coarse cells -- 7.0 percent -- have no surviving
    edge at all once the cross-slope gate is applied, and a plan starting
    from one of them returned the horizon message however many slices the
    caller granted: reproduced at 800 slices against a 103-move route.
    (Round 4 review, H-2.)
    """
    lateral = rejections.get("lateral_slope", 0)
    along = rejections.get("step_slope", 0)
    horizon = rejections.get("horizon", 0)
    blocked = rejections.get("cost_infinite", 0)
    unknown = rejections.get("nan_elevation", 0)

    parts: list[str] = []
    if lateral:
        parts.append(
            f"{lateral} edges exceeded the {rover['slope_lateral_max_deg']} deg "
            "roll-over (cross-slope) limit"
        )
    if along:
        parts.append(
            f"{along} edges exceeded the {rover['slope_max_deg']} deg "
            "step-slope limit"
        )
    if blocked:
        parts.append(f"{blocked} edges led into cells with no finite cost")
    if unknown:
        parts.append(f"{unknown} edges crossed cells with no elevation")
    if horizon:
        parts.append(
            f"{horizon} edges would have arrived past the last of "
            f"{n_slices} slices ({n_slices * slice_hours:.1f} h)"
        )

    if not parts:
        return (
            "No path found: the goal is not reachable from the start through "
            "passable cells at this coarsen factor."
        )
    lead = "No path found"
    if horizon and not (lateral or along or blocked or unknown):
        lead = "No path found within the time horizon"
    return (
        f"{lead} for {rover.get('name', rover.get('id', 'this rover'))}: "
        + "; ".join(parts)
        + "."
    )

_OFFSETS: tuple[tuple[int, int, bool], ...] = (
    (-1, 0, False), (1, 0, False), (0, -1, False), (0, 1, False),
    (-1, -1, True), (-1, 1, True), (1, -1, True), (1, 1, True),
)


def bfs_move_count(
    traversable: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
) -> int | None:
    """Minimum number of 8-connected MOVE steps from *start* to *goal*.

    Unweighted and time-free -- it answers the same reachability question
    ``astar_4d`` does, but cheaply enough to check before spending time
    building a cost cube, and exactly enough to size a time horizon instead
    of guessing a slice count. Returns ``None`` when *start* or *goal* is
    out of bounds, either is blocked, or no route exists between them.

    A fixed default slice count (the pre-fix behaviour) starved routes
    whose start and goal were genuinely far apart on the production grid;
    an unbounded default risked masking a start/goal that coarsening had
    disconnected. This distinguishes the two cases up front instead of
    letting ``astar_4d`` exhaust its search and report a single generic
    "not found". (Faz 1-2-3 review, H1/H3.)
    """
    mask = np.asarray(traversable, dtype=bool)
    height, width = mask.shape
    if not (0 <= start[0] < height and 0 <= start[1] < width):
        return None
    if not (0 <= goal[0] < height and 0 <= goal[1] < width):
        return None
    if not mask[start] or not mask[goal]:
        return None
    if start == goal:
        return 0

    dist = np.full(mask.shape, -1, dtype=np.int64)
    dist[start] = 0
    queue: deque[tuple[int, int]] = deque([start])
    offsets = [(d_row, d_col) for d_row, d_col, _ in _OFFSETS]

    while queue:
        row, col = queue.popleft()
        # No goal test on pop: start == goal returned above, and every other
        # cell has its distance fixed when it is PUSHED, so the goal is
        # detected there. (Backend review, #20.)
        for d_row, d_col in offsets:
            nr, nc = row + d_row, col + d_col
            if (
                0 <= nr < height
                and 0 <= nc < width
                and mask[nr, nc]
                and dist[nr, nc] < 0
            ):
                # Same corner-cutting rule as astar_4d's MOVE edges: this
                # count sizes the planner's horizon, so counting a route
                # the planner cannot take would size it for a plan that
                # never happens. (Round 2 review, M-1.)
                if d_row and d_col and not (mask[row, nc] and mask[nr, col]):
                    continue
                dist[nr, nc] = dist[row, col] + 1
                if (nr, nc) == goal:
                    return int(dist[nr, nc])
                queue.append((nr, nc))
    return None


def gated_move_count(
    traversable: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    elevation: np.ndarray | None,
    resolution_m: float,
    rover: Mapping[str, Any],
) -> int | None:
    """:func:`bfs_move_count`, but honouring the hard EDGE gates as well.

    ``bfs_move_count`` answers reachability through passable CELLS.
    ``astar_4d`` additionally refuses edges on step slope and cross-slope, so
    the two graphs are not the same one -- and on the production grid at
    ``coarsen=4`` the difference is large: 83.5 percent of the passable area
    is reachable through cells, and the gated graph's largest component is
    76.4 percent, with 7.0 percent of cells isolated outright.

    Sizing the time horizon from the ungated count is therefore sizing it for
    a route the planner cannot take, and checking reachability with the
    ungated count reports a plan as merely horizon-limited when it is
    geometrically impossible. (Round 4 review, H-2.)
    """
    mask = np.asarray(traversable, dtype=bool)
    height, width = mask.shape
    if not (0 <= start[0] < height and 0 <= start[1] < width):
        return None
    if not (0 <= goal[0] < height and 0 <= goal[1] < width):
        return None
    if not mask[start] or not mask[goal]:
        return None
    if start == goal:
        return 0

    if elevation is None:
        return bfs_move_count(mask, start, goal)

    elev = np.asarray(elevation, dtype=np.float64)
    grad_row, grad_col = np.gradient(elev, float(resolution_m))
    grad_row = np.nan_to_num(grad_row, nan=0.0)
    grad_col = np.nan_to_num(grad_col, nan=0.0)
    tan_slope_max = math.tan(math.radians(float(rover["slope_max_deg"])))
    tan_lat_max_sq = math.tan(math.radians(float(rover["slope_lateral_max_deg"]))) ** 2
    diag_m = float(resolution_m) * math.sqrt(2.0)

    dist = np.full(mask.shape, -1, dtype=np.int64)
    dist[start] = 0
    queue: deque[tuple[int, int]] = deque([start])
    while queue:
        row, col = queue.popleft()
        for d_row, d_col, diagonal in _OFFSETS:
            nr, nc = row + d_row, col + d_col
            if not (0 <= nr < height and 0 <= nc < width):
                continue
            if not mask[nr, nc] or dist[nr, nc] >= 0:
                continue
            if diagonal and not (mask[row, nc] and mask[nr, col]):
                continue
            distance_m = diag_m if diagonal else float(resolution_m)
            dz = elev[nr, nc] - elev[row, col]
            if not math.isfinite(dz) or abs(dz) / distance_m > tan_slope_max:
                continue
            norm = math.hypot(d_row, d_col)
            unit_r, unit_c = d_row / norm, d_col / norm
            lat_tan = lateral_slope_tan(
                0.5 * (grad_row[row, col] + grad_row[nr, nc]),
                0.5 * (grad_col[row, col] + grad_col[nr, nc]),
                unit_r,
                unit_c,
            )
            if lat_tan * lat_tan > tan_lat_max_sq:
                continue
            dist[nr, nc] = dist[row, col] + 1
            if (nr, nc) == goal:
                return int(dist[nr, nc])
            queue.append((nr, nc))
    return None


def _empty(
    error: str,
    elapsed_ms: float = 0.0,
    rejections: dict[str, int] | None = None,
    nodes_expanded: int = 0,
) -> dict[str, Any]:
    """A failed plan.

    ``total_cost`` is ``None``, not ``inf``: this dict is a candidate for
    direct JSON serialisation and Starlette renders with ``allow_nan=False``,
    so a bare ``inf`` turns the response into a 500. ``None`` is the
    convention the rest of this API already uses for unrepresentable values
    (``main._read_grid_value``, ``main.get_layer``, ``CostMap.explain``).
    """
    tally = _empty_rejections() if rejections is None else dict(rejections)
    return {
        "path_states": [],
        "path_pixels": [],
        "metrics": {
            "wait_steps": 0,
            "move_steps": 0,
            "arrival_slice": None,
            "total_cost": None,
            "cost_units": "weighted_hours",
            # Threaded through rather than reported as a flat 0 beside a
            # non-empty rejection tally. (Round 4 review, M-2.)
            "nodes_expanded": nodes_expanded,
            "computation_time_ms": round(elapsed_ms, 3),
            "edges_rejected": tally,
            "edges_dropped_at_horizon": tally.get("horizon", 0),
            "horizon_truncated": tally.get("horizon", 0) > 0,
        },
        "error": error,
    }


def astar_4d(
    cost_cube: np.ndarray,
    wait_cost_cube: np.ndarray,
    traversable: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    resolution_m: float,
    slice_hours: float,
    rover: Mapping[str, Any],
    slope_grid: np.ndarray | None = None,
    elevation_grid: np.ndarray | None = None,
) -> dict[str, Any]:
    """Plan through space and time. Returns path_states, path_pixels, metrics.

    *elevation_grid*, when supplied, enables the same two hard edge
    constraints the 2-D planner enforces: the along-track step slope against
    ``slope_max_deg`` and the cross-slope against ``slope_lateral_max_deg``.
    Without it neither can be evaluated, and the two planners in this product
    would disagree about which edges are safe -- the same class of divergence
    round 2 fixed for corner-cutting. (Round 3 review, H-1 and H-2.)
    """
    t0 = time.perf_counter()

    cost = np.asarray(cost_cube, dtype=np.float64)
    wait = np.asarray(wait_cost_cube, dtype=np.float64)
    passable = np.asarray(traversable, dtype=bool)

    if cost.ndim != 3:
        return _empty("cost_cube must be (T, H, W)")
    if wait.shape != cost.shape:
        return _empty("wait_cost_cube shape must match cost_cube")
    n_slices, height, width = cost.shape
    if passable.shape != (height, width):
        return _empty("traversable shape must match cost_cube slices")

    def in_bounds(r: int, c: int) -> bool:
        return 0 <= r < height and 0 <= c < width

    if not in_bounds(*start):
        return _empty("Start out of bounds")
    if not in_bounds(*goal):
        return _empty("Goal out of bounds")
    if not passable[start]:
        return _empty("Start is not traversable")
    if not passable[goal]:
        return _empty("Goal is not traversable")

    slopes = (
        np.zeros((height, width), dtype=np.float64)
        if slope_grid is None
        else np.asarray(slope_grid, dtype=np.float64)
    )

    slope_max_deg = float(rover["slope_max_deg"])
    lateral_max_deg = float(rover["slope_lateral_max_deg"])
    tan_slope_max = math.tan(math.radians(slope_max_deg))
    tan_lat_max_sq = math.tan(math.radians(lateral_max_deg)) ** 2
    if elevation_grid is None:
        elevation = None
        grad_row = grad_col = None
    else:
        elevation = np.asarray(elevation_grid, dtype=np.float64)
        if elevation.shape != (height, width):
            return _empty("elevation_grid shape must match cost_cube slices")
        grad_row, grad_col = np.gradient(elevation, float(resolution_m))
        grad_row = np.nan_to_num(grad_row, nan=0.0)
        grad_col = np.nan_to_num(grad_col, nan=0.0)

    # Every refusal is counted, not just the horizon one. A move rejected
    # because it would land past the last slice is not the same as a move
    # that is unsafe, and until round 4 only the former was tallied -- so
    # when the geometry gates closed a route the planner said the horizon
    # was too short. (Round 3 M-3; round 4 H-2.)
    rejections = _empty_rejections()

    finite = cost[np.isfinite(cost)]
    min_cost = float(np.min(finite)) if finite.size else 0.01
    diag_m = resolution_m * math.sqrt(2.0)
    # MOVE and WAIT edges must live in the same units to trade off against
    # each other at all: MOVE used to cost distance_m * (1 + MRU) while WAIT
    # costs dt_hours * MRU-ish, off by orders of magnitude on the real grid
    # (measured: an average MOVE edge ~29, a dark WAIT step at the auto slice
    # length ~0.0045 -- ~6500x apart, so the planner could never meaningfully
    # choose to wait once the illumination cube stops being held constant
    # across slices). Both now cost hours: MOVE via the same edge_travel_time_s
    # the slice-count budget already uses, WAIT unchanged. The heuristic
    # follows suit, using v_max_ms (the fastest the rover ever moves) as a
    # divisor so distance/v_max stays a true lower bound on travel time for
    # any slope -- admissibility is preserved, not just the ordering.
    # (Faz 1-2-3 review, M2.)
    v_max_ms = float(rover["v_max_ms"])

    def heuristic(r: int, c: int) -> float:
        dr, dc = abs(r - goal[0]), abs(c - goal[1])
        straight, diagonal = abs(dr - dc), min(dr, dc)
        distance_m = straight * resolution_m + diagonal * diag_m
        hours_lower_bound = distance_m / v_max_ms / 3600.0
        return hours_lower_bound * (1.0 + min_cost)

    start_state = (start[0], start[1], 0)
    g_score: dict[tuple[int, int, int], float] = {start_state: 0.0}
    came_from: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    closed: set[tuple[int, int, int]] = set()
    counter = 0
    heap: list[tuple[float, float, int, tuple[int, int, int]]] = [
        (heuristic(*start), 0.0, counter, start_state)
    ]
    nodes_expanded = 0
    goal_state: tuple[int, int, int] | None = None

    while heap:
        _f, _h, _n, state = heapq.heappop(heap)
        if state in closed:
            continue
        closed.add(state)
        nodes_expanded += 1

        row, col, slice_index = state
        if (row, col) == goal:
            goal_state = state
            break

        current_g = g_score[state]

        # WAIT edge
        if slice_index + 1 < n_slices:
            wait_state = (row, col, slice_index + 1)
            tentative = current_g + float(wait[slice_index, row, col])
            if math.isfinite(tentative) and tentative < g_score.get(
                wait_state, math.inf
            ):
                g_score[wait_state] = tentative
                came_from[wait_state] = state
                counter += 1
                h = heuristic(row, col)
                heapq.heappush(heap, (tentative + h, h, counter, wait_state))

        # MOVE edges
        for d_row, d_col, diagonal in _OFFSETS:
            nr, nc = row + d_row, col + d_col
            if not in_bounds(nr, nc):
                continue
            if not passable[nr, nc]:
                rejections["untraversable"] += 1
                continue

            # Diagonal corner-cutting safety, matching pathfinder._astar_core:
            # both adjacent cardinal cells must be passable, or the move
            # squeezes the rover diagonally between two blocked cells. The
            # 2-D planner has always refused this; without the same rule
            # here, /api/plan-4d returned routes through squeezes that
            # /api/plan calls untraversable -- two planners in one product
            # disagreeing about a safety predicate. bfs_move_count carries
            # the same rule so the horizon it sizes stays consistent with
            # the routes this loop can actually take. (Round 2 review, M-1.)
            if diagonal and not (passable[row, nc] and passable[nr, col]):
                rejections["corner_cut"] += 1
                continue

            distance_m = diag_m if diagonal else resolution_m

            # Same hard edge constraints as pathfinder._astar_core.
            if elevation is not None:
                dz = elevation[nr, nc] - elevation[row, col]
                if not math.isfinite(dz):
                    rejections["nan_elevation"] += 1
                    continue
                along_tan = abs(dz) / distance_m
                if along_tan > tan_slope_max:
                    rejections["step_slope"] += 1
                    continue
                norm = math.hypot(d_row, d_col)
                unit_r, unit_c = d_row / norm, d_col / norm
                g_row = 0.5 * (grad_row[row, col] + grad_row[nr, nc])
                g_col = 0.5 * (grad_col[row, col] + grad_col[nr, nc])
                # One shared implementation, in cost_engine. (Round 4, M-5.)
                lat_tan = lateral_slope_tan(g_row, g_col, unit_r, unit_c)
                if lat_tan * lat_tan > tan_lat_max_sq:
                    rejections["lateral_slope"] += 1
                    continue

            # Trapezoidal, matching pathfinder._astar_core's edge cost: an
            # edge is half in each cell, so its travel time follows the mean
            # of the two slopes rather than the destination's alone.
            # (Round 4 review, L-5.)
            edge_slope = 0.5 * (float(slopes[row, col]) + float(slopes[nr, nc]))
            travel_s = edge_travel_time_s(edge_slope, distance_m, rover)
            if not math.isfinite(travel_s):
                rejections["step_slope"] += 1
                continue
            d_slices = max(1, int(math.ceil(travel_s / 3600.0 / slice_hours)))
            arrival = slice_index + d_slices
            if arrival >= n_slices:
                rejections["horizon"] += 1
                continue

            from_cost = cost[slice_index, row, col]
            to_cost = cost[arrival, nr, nc]
            if not (math.isfinite(from_cost) and math.isfinite(to_cost)):
                rejections["cost_infinite"] += 1
                continue

            step = (travel_s / 3600.0) * (1.0 + 0.5 * (from_cost + to_cost))
            neighbour = (nr, nc, arrival)
            tentative = current_g + step
            if tentative < g_score.get(neighbour, math.inf):
                g_score[neighbour] = tentative
                came_from[neighbour] = state
                counter += 1
                h = heuristic(nr, nc)
                heapq.heappush(heap, (tentative + h, h, counter, neighbour))

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    if goal_state is None:
        return _empty(
            no_path_reason_4d(rejections, rover, n_slices, slice_hours),
            elapsed_ms,
            rejections,
            nodes_expanded,
        )

    states: list[tuple[int, int, int]] = [goal_state]
    while states[-1] in came_from:
        states.append(came_from[states[-1]])
    states.reverse()

    wait_steps = sum(
        1
        for previous, current in zip(states[:-1], states[1:])
        if previous[:2] == current[:2]
    )

    return {
        "path_states": states,
        "path_pixels": [(r, c) for r, c, _ in states],
        "metrics": {
            "wait_steps": wait_steps,
            "move_steps": len(states) - 1 - wait_steps,
            "arrival_slice": goal_state[2],
            "total_cost": round(float(g_score[goal_state]), 6),
            # MOVE edges cost travel HOURS scaled by the weighted cell cost,
            # and WAIT edges cost slice hours the same way -- so this total
            # is in weighted hours. app.pathfinder's total_weighted_cost is
            # in weighted METRES. Two endpoints answering different
            # questions under similar field names is a trap; the unit is
            # now stated. (Round 3 review, M-6.)
            "cost_units": "weighted_hours",
            "nodes_expanded": nodes_expanded,
            "computation_time_ms": round(elapsed_ms, 3),
            "edges_rejected": dict(rejections),
            "edges_dropped_at_horizon": rejections["horizon"],
            "horizon_truncated": rejections["horizon"] > 0,
        },
        "error": None,
    }
