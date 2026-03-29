"""Simulation engine for LunaPath rover path execution.

Consumes A* output and simulates rover traversal step-by-step,
tracking battery, energy consumption, thermal exposure, and risk.

No web framework dependencies — fully standalone and testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

import numpy as np

# ── LPR-1 rover constants (v3.2, frozen) ──────────────────────────────────────
BATTERY_CAPACITY_WH: float = 5420.0
DRIVE_POWER_W: float = 200.0
IDLE_POWER_W: float = 40.0
HEATER_POWER_W: float = 25.0
NOMINAL_SPEED_MS: float = 0.2
PIXEL_SIZE_M: float = 80.0

_DIAG_DIST_M: float = PIXEL_SIZE_M * math.sqrt(2)

# ── Slope energy multiplier — piecewise linear (LPR-1 table) ──────────────────
# Each entry: (deg_lo, deg_hi, mult_lo, mult_hi)
_SLOPE_BREAKPOINTS: tuple[tuple[float, float, float, float], ...] = (
    (0.0,  10.0, 1.0, 1.6),
    (10.0, 15.0, 1.6, 1.9),
    (15.0, 25.0, 1.9, 2.5),
)
_SLOPE_MULT_CAP: float = 2.5


def _slope_multiplier(slope_deg: float) -> float:
    """Return piecewise-linear energy multiplier for the given slope."""
    for deg_lo, deg_hi, mult_lo, mult_hi in _SLOPE_BREAKPOINTS:
        if slope_deg <= deg_hi:
            t = (slope_deg - deg_lo) / (deg_hi - deg_lo)
            return mult_lo + t * (mult_hi - mult_lo)
    return _SLOPE_MULT_CAP


def _risk_level(battery_pct: float) -> str:
    if battery_pct > 50.0:
        return "LOW"
    if battery_pct > 25.0:
        return "MEDIUM"
    if battery_pct > 10.0:
        return "HIGH"
    return "CRITICAL"


# ── RoverState ─────────────────────────────────────────────────────────────────

@dataclass
class RoverState:
    step: int
    row: int
    col: int
    distance_m: float           # cumulative metres travelled
    elapsed_hours: float        # cumulative hours elapsed
    battery_wh: float
    battery_pct: float
    risk_level: str
    slope_deg: float
    surface_temp_c: float
    shadow_ratio: float
    node_cost: float
    step_energy_wh: float       # energy consumed this step
    cumulative_cost: float      # running sum of cost_grid values
    recharge_count: int         # cumulative full-battery restores
    recharged_this_step: bool

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "row": self.row,
            "col": self.col,
            "distance_m": round(self.distance_m, 2),
            "elapsed_hours": round(self.elapsed_hours, 2),
            "battery_wh": round(self.battery_wh, 2),
            "battery_pct": round(self.battery_pct, 2),
            "risk_level": self.risk_level,
            "slope_deg": round(self.slope_deg, 2),
            "surface_temp_c": round(self.surface_temp_c, 2),
            "shadow_ratio": round(self.shadow_ratio, 2),
            "node_cost": round(self.node_cost, 2),
            "step_energy_wh": round(self.step_energy_wh, 2),
            "cumulative_cost": round(self.cumulative_cost, 2),
            "recharge_count": self.recharge_count,
            "recharged_this_step": self.recharged_this_step,
        }


# ── simulate_path ──────────────────────────────────────────────────────────────

def simulate_path(
    astar_result: dict,
    cost_grid: np.ndarray,
    slope_grid: np.ndarray,
    thermal_grid: np.ndarray,
    shadow_grid: np.ndarray,
) -> List[RoverState]:
    """Simulate rover traversal over an A* path.

    Parameters
    ----------
    astar_result : dict
        Output from pathfinder.astar() with keys: path_pixels, metrics, error.
    cost_grid : ndarray (500, 500) float32
        Pre-computed multi-criteria cell costs from cost_engine.
    slope_grid : ndarray (500, 500) float32
        Slope in degrees.
    thermal_grid : ndarray (500, 500) float32
        Surface temperature in Celsius.
    shadow_grid : ndarray (500, 500) float32
        Shadow ratio in [0.0, 1.0].

    Returns
    -------
    List[RoverState]
        One RoverState per path node, in traversal order. If the battery is
        depleted mid-mission, it is instantly restored to 100% and the
        simulation continues.

    Raises
    ------
    ValueError
        If astar_result contains a non-None error, or path_pixels is empty.
    """
    if astar_result.get("error") is not None:
        raise ValueError(f"A* result contains error: {astar_result['error']}")

    path_pixels = astar_result.get("path_pixels", [])
    if not path_pixels:
        raise ValueError("path_pixels is empty — nothing to simulate")

    states: List[RoverState] = []
    battery_wh = BATTERY_CAPACITY_WH
    cumulative_dist_m = 0.0
    elapsed_hours = 0.0
    cumulative_cost = 0.0
    recharge_count = 0

    for i, node in enumerate(path_pixels):
        r, c = int(node[0]), int(node[1])

        # 1. Step distance
        if i == 0:
            step_dist = 0.0
        else:
            prev = path_pixels[i - 1]
            pr, pc = int(prev[0]), int(prev[1])
            manhattan = abs(r - pr) + abs(c - pc)
            step_dist = _DIAG_DIST_M if manhattan == 2 else PIXEL_SIZE_M

        # 2. Slope energy multiplier
        slope_deg = float(slope_grid[r, c])
        slope_mult = _slope_multiplier(slope_deg)

        # 3. Actual speed
        speed_factor = max(0.2, 1.0 - slope_deg / 50.0)
        actual_speed = NOMINAL_SPEED_MS * speed_factor

        # 4. Step time (hours); zero for first node
        if i == 0:
            step_time_h = 0.0
        else:
            step_time_h = step_dist / actual_speed / 3600.0

        # 5. Energy consumption
        shadow_ratio = float(shadow_grid[r, c])
        drive_energy = DRIVE_POWER_W * slope_mult * step_time_h
        heater_energy = HEATER_POWER_W * shadow_ratio * step_time_h
        idle_energy = IDLE_POWER_W * step_time_h
        step_energy = drive_energy + heater_energy + idle_energy

        # 6. Battery state
        battery_wh -= step_energy
        recharged_this_step = False
        if i > 0 and battery_wh <= 0.0:
            # Mission rule: if the pack is depleted, it is immediately
            # restored to full charge and traversal continues.
            battery_wh = BATTERY_CAPACITY_WH
            recharge_count += 1
            recharged_this_step = True
        battery_pct = battery_wh / BATTERY_CAPACITY_WH * 100.0

        # 7. Risk level
        risk = _risk_level(battery_pct)

        # Accumulators
        cumulative_dist_m += step_dist
        elapsed_hours += step_time_h
        node_cost = float(cost_grid[r, c])
        cumulative_cost += node_cost

        states.append(RoverState(
            step=i,
            row=r,
            col=c,
            distance_m=cumulative_dist_m,
            elapsed_hours=elapsed_hours,
            battery_wh=battery_wh,
            battery_pct=battery_pct,
            risk_level=risk,
            slope_deg=slope_deg,
            surface_temp_c=float(thermal_grid[r, c]),
            shadow_ratio=shadow_ratio,
            node_cost=node_cost,
            step_energy_wh=step_energy,
            cumulative_cost=cumulative_cost,
            recharge_count=recharge_count,
            recharged_this_step=recharged_this_step,
        ))

    return states


# ── summarize_simulation ───────────────────────────────────────────────────────

def summarize_simulation(states: List[RoverState]) -> dict:
    """Produce aggregate statistics from a simulated state sequence.

    Parameters
    ----------
    states : List[RoverState]
        Output from simulate_path().

    Returns
    -------
    dict
        Keys: total_distance_km, total_elapsed_hours, final_battery_pct,
        min_battery_pct, max_slope_deg, total_energy_consumed_wh,
        total_shadow_exposure, critical_steps_count,
        high_or_above_steps_count, waypoint_count, total_recharges.
    """
    if not states:
        return {
            "total_distance_km": 0.0,
            "total_elapsed_hours": 0.0,
            "final_battery_pct": 0.0,
            "min_battery_pct": 0.0,
            "max_slope_deg": 0.0,
            "total_energy_consumed_wh": 0.0,
            "total_shadow_exposure": 0.0,
            "critical_steps_count": 0,
            "high_or_above_steps_count": 0,
            "waypoint_count": 0,
            "total_recharges": 0,
        }

    last = states[-1]

    # Reconstruct step_time_h per step to compute shadow exposure.
    # step_dist = distance delta between consecutive states.
    total_shadow_exposure = 0.0
    for i in range(1, len(states)):
        s = states[i]
        step_dist = s.distance_m - states[i - 1].distance_m
        if step_dist <= 0.0:
            continue
        speed_factor = max(0.2, 1.0 - s.slope_deg / 50.0)
        actual_speed = NOMINAL_SPEED_MS * speed_factor
        step_time_h = step_dist / actual_speed / 3600.0
        total_shadow_exposure += s.shadow_ratio * step_time_h

    return {
        "total_distance_km": round(last.distance_m / 1000.0, 4),
        "total_elapsed_hours": round(last.elapsed_hours, 4),
        "final_battery_pct": round(last.battery_pct, 2),
        "min_battery_pct": round(min(s.battery_pct for s in states), 2),
        "max_slope_deg": round(max(s.slope_deg for s in states), 2),
        "total_energy_consumed_wh": round(
            sum(s.step_energy_wh for s in states), 2
        ),
        "total_shadow_exposure": round(total_shadow_exposure, 4),
        "critical_steps_count": sum(
            1 for s in states if s.risk_level == "CRITICAL"
        ),
        "high_or_above_steps_count": sum(
            1 for s in states if s.risk_level in ("HIGH", "CRITICAL")
        ),
        "waypoint_count": len(states),
        "total_recharges": max(s.recharge_count for s in states),
    }
