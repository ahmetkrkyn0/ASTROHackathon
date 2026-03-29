"""Simulation engine for LunaPath rover path execution."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from .constants import DEFAULT_TARGET_RESOLUTION_M, get_rover

_DEFAULT_ROVER = get_rover()

# Backward-compatible aliases for the default rover.
BATTERY_CAPACITY_WH: float = float(_DEFAULT_ROVER["e_cap_wh"])
DRIVE_POWER_W: float = float(_DEFAULT_ROVER["p_base_w"])
IDLE_POWER_W: float = float(_DEFAULT_ROVER["p_idle_w"])
HEATER_POWER_W: float = float(_DEFAULT_ROVER["p_heater_w"])
NOMINAL_SPEED_MS: float = float(_DEFAULT_ROVER["v_max_ms"])
PIXEL_SIZE_M: float = float(DEFAULT_TARGET_RESOLUTION_M)


def _diag_distance_m(pixel_size_m: float) -> float:
    return pixel_size_m * math.sqrt(2)


# Slope energy multiplier table retained from the original LPR-1 simulation.
_SLOPE_BREAKPOINTS: tuple[tuple[float, float, float, float], ...] = (
    (0.0, 10.0, 1.0, 1.6),
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


@dataclass
class RoverState:
    step: int
    row: int
    col: int
    distance_m: float
    elapsed_hours: float
    battery_wh: float
    battery_pct: float
    risk_level: str
    slope_deg: float
    surface_temp_c: float
    shadow_ratio: float
    node_cost: float
    step_energy_wh: float
    cumulative_cost: float
    recharge_count: int
    recharged_this_step: bool

    def to_dict(self) -> dict[str, Any]:
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


def simulate_path(
    astar_result: dict,
    cost_grid: np.ndarray,
    slope_grid: np.ndarray,
    thermal_grid: np.ndarray,
    shadow_grid: np.ndarray,
    rover: dict[str, Any] | None = None,
    pixel_size_m: float | None = None,
) -> list[RoverState]:
    """Simulate rover traversal over an A* path."""
    if astar_result.get("error") is not None:
        raise ValueError(f"A* result contains error: {astar_result['error']}")

    path_pixels = astar_result.get("path_pixels", [])
    if not path_pixels:
        raise ValueError("path_pixels is empty — nothing to simulate")

    rover_cfg = get_rover() if rover is None else rover
    battery_capacity_wh = float(rover_cfg["e_cap_wh"])
    drive_power_w = float(rover_cfg["p_base_w"])
    idle_power_w = float(rover_cfg["p_idle_w"])
    heater_power_w = float(rover_cfg["p_heater_w"])
    nominal_speed_ms = float(rover_cfg["v_max_ms"])
    step_pixel_size_m = float(pixel_size_m or PIXEL_SIZE_M)
    diag_dist_m = _diag_distance_m(step_pixel_size_m)

    states: list[RoverState] = []
    battery_wh = battery_capacity_wh
    cumulative_dist_m = 0.0
    elapsed_hours = 0.0
    cumulative_cost = 0.0
    recharge_count = 0

    for i, node in enumerate(path_pixels):
        r, c = int(node[0]), int(node[1])

        if i == 0:
            step_dist = 0.0
        else:
            prev = path_pixels[i - 1]
            pr, pc = int(prev[0]), int(prev[1])
            manhattan = abs(r - pr) + abs(c - pc)
            step_dist = diag_dist_m if manhattan == 2 else step_pixel_size_m

        slope_deg = float(slope_grid[r, c])
        slope_mult = _slope_multiplier(slope_deg)

        speed_factor = max(0.2, 1.0 - slope_deg / 50.0)
        actual_speed = nominal_speed_ms * speed_factor

        if i == 0:
            step_time_h = 0.0
        else:
            step_time_h = step_dist / actual_speed / 3600.0

        shadow_ratio = float(shadow_grid[r, c])
        drive_energy = drive_power_w * slope_mult * step_time_h
        heater_energy = heater_power_w * shadow_ratio * step_time_h
        idle_energy = idle_power_w * step_time_h
        step_energy = drive_energy + heater_energy + idle_energy

        battery_wh -= step_energy
        recharged_this_step = False
        if i > 0 and battery_wh <= 0.0:
            battery_wh = battery_capacity_wh
            recharge_count += 1
            recharged_this_step = True
        battery_pct = battery_wh / battery_capacity_wh * 100.0

        cumulative_dist_m += step_dist
        elapsed_hours += step_time_h
        node_cost = float(cost_grid[r, c])
        cumulative_cost += node_cost

        states.append(
            RoverState(
                step=i,
                row=r,
                col=c,
                distance_m=cumulative_dist_m,
                elapsed_hours=elapsed_hours,
                battery_wh=battery_wh,
                battery_pct=battery_pct,
                risk_level=_risk_level(battery_pct),
                slope_deg=slope_deg,
                surface_temp_c=float(thermal_grid[r, c]),
                shadow_ratio=shadow_ratio,
                node_cost=node_cost,
                step_energy_wh=step_energy,
                cumulative_cost=cumulative_cost,
                recharge_count=recharge_count,
                recharged_this_step=recharged_this_step,
            )
        )

    return states


def summarize_simulation(states: list[RoverState]) -> dict[str, Any]:
    """Produce aggregate statistics from a simulated state sequence."""
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
    total_shadow_exposure = 0.0
    for i in range(1, len(states)):
        step_time_h = states[i].elapsed_hours - states[i - 1].elapsed_hours
        if step_time_h <= 0.0:
            continue
        total_shadow_exposure += states[i].shadow_ratio * step_time_h

    return {
        "total_distance_km": round(last.distance_m / 1000.0, 4),
        "total_elapsed_hours": round(last.elapsed_hours, 4),
        "final_battery_pct": round(last.battery_pct, 2),
        "min_battery_pct": round(min(s.battery_pct for s in states), 2),
        "max_slope_deg": round(max(s.slope_deg for s in states), 2),
        "total_energy_consumed_wh": round(sum(s.step_energy_wh for s in states), 2),
        "total_shadow_exposure": round(total_shadow_exposure, 4),
        "critical_steps_count": sum(1 for s in states if s.risk_level == "CRITICAL"),
        "high_or_above_steps_count": sum(
            1 for s in states if s.risk_level in ("HIGH", "CRITICAL")
        ),
        "waypoint_count": len(states),
        "total_recharges": max(s.recharge_count for s in states),
    }
