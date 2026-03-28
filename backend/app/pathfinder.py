"""Multi-criteria A* on an 8-connected grid."""

import heapq
import math
import time

import numpy as np

from . import constants as C
from .cost_engine import f_energy, f_shadow, f_slope, f_thermal, log_barrier_penalty, surface_to_inner

# 8-directional neighbors: (drow, dcol, distance_multiplier)
_NEIGHBORS = [
    (-1, 0, 1.0),
    (1, 0, 1.0),
    (0, -1, 1.0),
    (0, 1, 1.0),
    (-1, -1, math.sqrt(2)),
    (-1, 1, math.sqrt(2)),
    (1, -1, math.sqrt(2)),
    (1, 1, math.sqrt(2)),
]


def astar(
    grids: dict,
    start: tuple[int, int],
    goal: tuple[int, int],
    weights: dict[str, float],
    constraints: dict | None = None,
) -> dict:
    """Run A* and return a PathResult dict.

    grids: output of data_loader.load_and_preprocess_dem
    start/goal: (row, col)
    weights: {w_slope, w_energy, w_shadow, w_thermal}
    constraints: {max_shadow_h, max_slope_deg, max_energy_wh, min_soc}
    """
    t0 = time.perf_counter()

    elevation = grids["elevation"]
    slope_grid = grids["slope"]
    thermal_grid = grids["thermal"]
    shadow_ratio = grids["shadow_ratio"]
    traversable = grids["traversable"]
    resolution = grids["metadata"]["resolution_m"]

    rows, cols = elevation.shape
    cons = constraints or {
        "max_shadow_h": C.H_MAX_SHADOW_H,
        "max_slope_deg": C.SLOPE_MAX_DEG,
        "max_energy_wh": C.E_CAP_WH * 0.74,
        "min_soc": C.SOC_MIN_PCT,
    }

    if not (0 <= start[0] < rows and 0 <= start[1] < cols):
        return _empty_result("Start out of bounds")
    if not (0 <= goal[0] < rows and 0 <= goal[1] < cols):
        return _empty_result("Goal out of bounds")
    if not traversable[start[0], start[1]]:
        return _empty_result("Start is not traversable")
    if not traversable[goal[0], goal[1]]:
        return _empty_result("Goal is not traversable")

    # Heuristic: Euclidean distance * minimum possible edge cost
    def heuristic(r, c):
        dr = abs(r - goal[0])
        dc = abs(c - goal[1])
        return math.sqrt(dr * dr + dc * dc) * resolution * 0.01

    # Priority queue: (f_score, counter, row, col)
    counter = 0
    open_set: list[tuple[float, int, int, int]] = []
    heapq.heappush(open_set, (heuristic(start[0], start[1]), counter, start[0], start[1]))

    g_score = np.full((rows, cols), np.inf, dtype=np.float64)
    g_score[start[0], start[1]] = 0.0

    # Cumulative energy and shadow tracking
    energy_acc = np.full((rows, cols), np.inf, dtype=np.float64)
    energy_acc[start[0], start[1]] = 0.0
    shadow_acc = np.full((rows, cols), np.inf, dtype=np.float64)
    shadow_acc[start[0], start[1]] = 0.0

    came_from = np.full((rows, cols, 2), -1, dtype=np.int32)
    closed = np.zeros((rows, cols), dtype=bool)

    found = False

    while open_set:
        _, _, cr, cc = heapq.heappop(open_set)

        if cr == goal[0] and cc == goal[1]:
            found = True
            break

        if closed[cr, cc]:
            continue
        closed[cr, cc] = True

        cur_energy = energy_acc[cr, cc]
        cur_shadow = shadow_acc[cr, cc]

        for dr, dc, dist_mult in _NEIGHBORS:
            nr, nc = cr + dr, cc + dc
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue
            if closed[nr, nc] or not traversable[nr, nc]:
                continue

            # Edge slope from elevation difference
            dz = float(elevation[nr, nc] - elevation[cr, cc])
            d_horiz = resolution * dist_mult
            edge_slope = math.degrees(math.atan2(abs(dz), d_horiz))

            if edge_slope > cons["max_slope_deg"]:
                continue

            # Penalty components
            ps = f_slope(edge_slope)
            if math.isinf(ps):
                continue

            pe = f_energy(edge_slope, d_horiz)

            # Shadow accumulation for this edge
            speed = C.V_MAX_MS * math.cos(math.radians(edge_slope))
            if speed <= 0:
                continue
            L = d_horiz / math.cos(math.radians(edge_slope))
            dt_hours = (L / speed) / 3600.0
            dark_ratio = float(shadow_ratio[nr, nc])
            edge_shadow_h = dark_ratio * dt_hours
            new_shadow = cur_shadow + edge_shadow_h

            psh = f_shadow(new_shadow)
            pt = f_thermal(float(thermal_grid[nr, nc]))

            # Energy for this edge
            mu = 1.0 + C.MU_COEFF * math.sin(math.radians(edge_slope))
            t_s = L / speed
            edge_energy_wh = C.P_BASE_W * mu * t_s / 3600.0
            new_energy = cur_energy + edge_energy_wh

            if new_energy > cons["max_energy_wh"]:
                continue

            soc = 1.0 - new_energy / C.E_CAP_WH
            if soc < cons["min_soc"]:
                continue

            # Log-barrier
            T_inner = surface_to_inner(float(thermal_grid[nr, nc]))
            J = log_barrier_penalty(edge_slope, 0.0, soc, T_inner)
            if math.isinf(J):
                continue

            edge_cost = (
                weights["w_slope"] * ps
                + weights["w_energy"] * pe
                + weights["w_shadow"] * psh
                + weights["w_thermal"] * pt
                + J
            )
            edge_cost = max(0.01, edge_cost)

            tentative_g = g_score[cr, cc] + edge_cost

            if tentative_g < g_score[nr, nc]:
                g_score[nr, nc] = tentative_g
                energy_acc[nr, nc] = new_energy
                shadow_acc[nr, nc] = new_shadow
                came_from[nr, nc, 0] = cr
                came_from[nr, nc, 1] = cc
                counter += 1
                f = tentative_g + heuristic(nr, nc)
                heapq.heappush(open_set, (f, counter, nr, nc))

    comp_time = (time.perf_counter() - t0) * 1000  # ms

    if not found:
        return _empty_result("No path found", comp_time)

    # Reconstruct path
    path = []
    r, c = goal
    while r != -1:
        path.append([int(r), int(c)])
        pr, pc = int(came_from[r, c, 0]), int(came_from[r, c, 1])
        r, c = pr, pc
    path.reverse()

    # Compute metrics along path
    total_dist = 0.0
    max_slope = 0.0
    for i in range(1, len(path)):
        r0, c0 = path[i - 1]
        r1, c1 = path[i]
        dr_abs = abs(r1 - r0)
        dc_abs = abs(c1 - c0)
        mult = math.sqrt(2) if (dr_abs + dc_abs == 2) else 1.0
        d_h = resolution * mult
        dz = float(elevation[r1, c1] - elevation[r0, c0])
        seg_slope = math.degrees(math.atan2(abs(dz), d_h))
        total_dist += math.sqrt(d_h**2 + dz**2)
        max_slope = max(max_slope, seg_slope)

    final_energy = float(energy_acc[goal[0], goal[1]])
    final_shadow = float(shadow_acc[goal[0], goal[1]])
    max_thermal = float(np.max([thermal_grid[r, c] for r, c in path]))

    return {
        "path_pixels": path,
        "metrics": {
            "total_distance_m": round(total_dist, 2),
            "total_energy_wh": round(final_energy, 2),
            "max_slope_deg": round(max_slope, 2),
            "total_shadow_hours": round(final_shadow, 4),
            "max_thermal_risk": round(f_thermal(max_thermal), 4),
            "path_length_nodes": len(path),
            "computation_time_ms": round(comp_time, 1),
        },
        "error": None,
    }


def _empty_result(error: str, comp_time: float = 0.0) -> dict:
    return {
        "path_pixels": [],
        "metrics": {
            "total_distance_m": 0,
            "total_energy_wh": 0,
            "max_slope_deg": 0,
            "total_shadow_hours": 0,
            "max_thermal_risk": 0,
            "path_length_nodes": 0,
            "computation_time_ms": round(comp_time, 1),
        },
        "error": error,
    }
