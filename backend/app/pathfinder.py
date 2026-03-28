"""Multi-criteria A* planner over a weighted lunar grid."""

from __future__ import annotations

import heapq
import math
import time

import numpy as np

from . import constants as C
from .cost_engine import (
    edge_energy_wh,
    edge_shadow_hours,
    f_thermal,
    resolve_weights,
    total_edge_cost,
)

_NEIGHBORS: tuple[tuple[int, int, float], ...] = (
    (-1, 0, 1.0),
    (1, 0, 1.0),
    (0, -1, 1.0),
    (0, 1, 1.0),
    (-1, -1, math.sqrt(2)),
    (-1, 1, math.sqrt(2)),
    (1, -1, math.sqrt(2)),
    (1, 1, math.sqrt(2)),
)


def astar(
    grids: dict,
    start: tuple[int, int],
    goal: tuple[int, int],
    weights: dict[str, float] | None = None,
    constraints: dict | None = None,
) -> dict:
    """Run weighted A* and return path plus metrics."""
    t0 = time.perf_counter()

    elevation = np.asarray(grids["elevation"], dtype=np.float64)
    thermal = np.asarray(grids["thermal"], dtype=np.float64)
    shadow_ratio = np.asarray(grids["shadow_ratio"], dtype=np.float64)
    traversable = np.asarray(grids["traversable"], dtype=bool)
    resolution = float(grids["metadata"]["resolution_m"])

    rows, cols = elevation.shape
    resolved_weights = resolve_weights(weights)
    cons = {
        "max_shadow_h": C.H_MAX_SHADOW_H,
        "max_slope_deg": C.SLOPE_MAX_DEG,
        "max_energy_wh": C.E_CAP_WH * 0.74,
        "min_soc": C.SOC_MIN_PCT,
    }
    if constraints:
        cons.update(constraints)

    if not _in_bounds(start, rows, cols):
        return _empty_result("Start out of bounds")
    if not _in_bounds(goal, rows, cols):
        return _empty_result("Goal out of bounds")
    if not traversable[start]:
        return _empty_result("Start is not traversable")
    if not traversable[goal]:
        return _empty_result("Goal is not traversable")

    def heuristic(row: int, col: int) -> float:
        # Minimum edge cost floor in cost_engine is 0.01.
        return math.hypot(goal[0] - row, goal[1] - col) * 0.01

    open_set: list[tuple[float, int, int, int]] = []
    counter = 0
    heapq.heappush(open_set, (heuristic(*start), counter, start[0], start[1]))

    g_score = np.full((rows, cols), np.inf, dtype=np.float64)
    g_score[start] = 0.0
    energy_acc = np.full((rows, cols), np.inf, dtype=np.float64)
    energy_acc[start] = 0.0
    shadow_acc = np.full((rows, cols), np.inf, dtype=np.float64)
    shadow_acc[start] = 0.0
    came_from = np.full((rows, cols, 2), -1, dtype=np.int32)
    closed = np.zeros((rows, cols), dtype=bool)

    found = False

    while open_set:
        _, _, cur_r, cur_c = heapq.heappop(open_set)

        if closed[cur_r, cur_c]:
            continue
        closed[cur_r, cur_c] = True

        if (cur_r, cur_c) == goal:
            found = True
            break

        cur_energy = float(energy_acc[cur_r, cur_c])
        cur_shadow = float(shadow_acc[cur_r, cur_c])

        for d_row, d_col, distance_mult in _NEIGHBORS:
            next_r = cur_r + d_row
            next_c = cur_c + d_col
            if not _in_bounds((next_r, next_c), rows, cols):
                continue
            if closed[next_r, next_c] or not traversable[next_r, next_c]:
                continue

            d_horiz = resolution * distance_mult
            dz = float(elevation[next_r, next_c] - elevation[cur_r, cur_c])
            edge_slope = math.degrees(math.atan2(abs(dz), d_horiz))
            if edge_slope > min(C.SLOPE_MAX_DEG, float(cons["max_slope_deg"])):
                continue

            edge_energy = edge_energy_wh(edge_slope, d_horiz)
            if math.isinf(edge_energy):
                continue
            new_energy = cur_energy + edge_energy
            if new_energy > float(cons["max_energy_wh"]):
                continue

            soc = 1.0 - new_energy / C.E_CAP_WH
            if soc < float(cons["min_soc"]):
                continue

            edge_shadow = edge_shadow_hours(
                float(shadow_ratio[next_r, next_c]),
                edge_slope,
                d_horiz,
            )
            if math.isinf(edge_shadow):
                continue
            new_shadow = cur_shadow + edge_shadow
            if new_shadow > float(cons["max_shadow_h"]):
                continue

            edge_cost = total_edge_cost(
                edge_slope,
                d_horiz,
                new_shadow,
                float(thermal[next_r, next_c]),
                weights=resolved_weights,
                soc=soc,
            )
            if math.isinf(edge_cost):
                continue

            tentative_g = float(g_score[cur_r, cur_c]) + edge_cost
            if tentative_g >= g_score[next_r, next_c]:
                continue

            g_score[next_r, next_c] = tentative_g
            energy_acc[next_r, next_c] = new_energy
            shadow_acc[next_r, next_c] = new_shadow
            came_from[next_r, next_c, 0] = cur_r
            came_from[next_r, next_c, 1] = cur_c
            counter += 1
            heapq.heappush(
                open_set,
                (tentative_g + heuristic(next_r, next_c), counter, next_r, next_c),
            )

    comp_time_ms = (time.perf_counter() - t0) * 1000.0
    if not found:
        return _empty_result("No path found", comp_time_ms)

    path_pixels = _reconstruct_path(came_from, goal)
    max_slope = 0.0
    total_distance = 0.0
    path_temperatures: list[float] = []

    for row, col in path_pixels:
        path_temperatures.append(float(thermal[row, col]))

    for idx in range(1, len(path_pixels)):
        prev_r, prev_c = path_pixels[idx - 1]
        cur_r, cur_c = path_pixels[idx]
        distance_mult = math.sqrt(2) if abs(cur_r - prev_r) + abs(cur_c - prev_c) == 2 else 1.0
        d_horiz = resolution * distance_mult
        dz = float(elevation[cur_r, cur_c] - elevation[prev_r, prev_c])
        seg_slope = math.degrees(math.atan2(abs(dz), d_horiz))
        total_distance += math.sqrt(d_horiz**2 + dz**2)
        max_slope = max(max_slope, seg_slope)

    return {
        "path_pixels": path_pixels,
        "metrics": {
            "total_distance_m": round(total_distance, 2),
            "total_energy_wh": round(float(energy_acc[goal]), 2),
            "total_shadow_hours": round(float(shadow_acc[goal]), 4),
            "max_slope_deg": round(max_slope, 2),
            "max_thermal_risk": round(max(f_thermal(temp) for temp in path_temperatures), 4),
            "min_surface_temp_c": round(min(path_temperatures), 2),
            "total_weighted_cost": round(float(g_score[goal]), 4),
            "path_length_nodes": len(path_pixels),
            "computation_time_ms": round(comp_time_ms, 1),
        },
        "error": None,
    }


def _empty_result(error: str, comp_time_ms: float = 0.0) -> dict:
    return {
        "path_pixels": [],
        "metrics": {
            "total_distance_m": 0.0,
            "total_energy_wh": 0.0,
            "total_shadow_hours": 0.0,
            "max_slope_deg": 0.0,
            "max_thermal_risk": 0.0,
            "min_surface_temp_c": 0.0,
            "total_weighted_cost": 0.0,
            "path_length_nodes": 0,
            "computation_time_ms": round(comp_time_ms, 1),
        },
        "error": error,
    }


def _reconstruct_path(came_from: np.ndarray, goal: tuple[int, int]) -> list[list[int]]:
    path: list[list[int]] = []
    row, col = goal
    while row != -1 and col != -1:
        path.append([int(row), int(col)])
        prev_row = int(came_from[row, col, 0])
        prev_col = int(came_from[row, col, 1])
        row, col = prev_row, prev_col
    path.reverse()
    return path


def _in_bounds(node: tuple[int, int], rows: int, cols: int) -> bool:
    row, col = node
    return 0 <= row < rows and 0 <= col < cols
