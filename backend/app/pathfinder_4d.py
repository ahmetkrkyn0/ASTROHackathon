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
from collections.abc import Mapping
from typing import Any

import numpy as np

from .cost_engine import edge_travel_time_s

_OFFSETS: tuple[tuple[int, int, bool], ...] = (
    (-1, 0, False), (1, 0, False), (0, -1, False), (0, 1, False),
    (-1, -1, True), (-1, 1, True), (1, -1, True), (1, 1, True),
)


def _empty(error: str, elapsed_ms: float = 0.0) -> dict[str, Any]:
    return {
        "path_states": [],
        "path_pixels": [],
        "metrics": {
            "wait_steps": 0,
            "move_steps": 0,
            "arrival_slice": None,
            "total_cost": float("inf"),
            "nodes_expanded": 0,
            "computation_time_ms": round(elapsed_ms, 3),
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
) -> dict[str, Any]:
    """Plan through space and time. Returns path_states, path_pixels, metrics."""
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

    finite = cost[np.isfinite(cost)]
    min_cost = float(np.min(finite)) if finite.size else 0.01
    diag_m = resolution_m * math.sqrt(2.0)

    def heuristic(r: int, c: int) -> float:
        dr, dc = abs(r - goal[0]), abs(c - goal[1])
        straight, diagonal = abs(dr - dc), min(dr, dc)
        return (straight * resolution_m + diagonal * diag_m) * (1.0 + min_cost)

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
            if not in_bounds(nr, nc) or not passable[nr, nc]:
                continue

            distance_m = diag_m if diagonal else resolution_m
            travel_s = edge_travel_time_s(float(slopes[nr, nc]), distance_m, rover)
            if not math.isfinite(travel_s):
                continue
            d_slices = max(1, int(math.ceil(travel_s / 3600.0 / slice_hours)))
            arrival = slice_index + d_slices
            if arrival >= n_slices:
                continue

            from_cost = cost[slice_index, row, col]
            to_cost = cost[arrival, nr, nc]
            if not (math.isfinite(from_cost) and math.isfinite(to_cost)):
                continue

            step = distance_m * (1.0 + 0.5 * (from_cost + to_cost))
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
        return _empty("No path found within the time horizon", elapsed_ms)

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
            "total_cost": round(g_score[goal_state], 6),
            "nodes_expanded": nodes_expanded,
            "computation_time_ms": round(elapsed_ms, 3),
        },
        "error": None,
    }
