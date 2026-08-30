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
    """Return piecewise-linear energy multiplier for the given slope.

    Clamped at 0: slope grids carry a MAGNITUDE, so a negative value is bad
    input rather than a downhill stretch. Extrapolating the first segment
    below 0 returned multipliers under 1.0 (0.70 at -5 deg), i.e. free
    energy. The production grid never goes negative, so this is a guard
    against bad input, not a live fix. (Backend review, #21.)
    """
    theta = max(0.0, float(slope_deg))
    for deg_lo, deg_hi, mult_lo, mult_hi in _SLOPE_BREAKPOINTS:
        if theta <= deg_hi:
            t = (theta - deg_lo) / (deg_hi - deg_lo)
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
    # Battery level at this step's lowest point, before any recharge stop.
    # Equal to battery_pct on steps that did not recharge.
    battery_low_pct: float = 100.0

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
            "battery_low_pct": round(self.battery_low_pct, 2),
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
    solar_power_w = float(rover_cfg.get("p_solar_w") or 0.0)
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
        # Bank the drive time before any recharge stop extends it, so the
        # clock advances exactly once per step.
        elapsed_hours += step_time_h

        # The level BEFORE any recharge. min_battery_pct is the answer to
        # "how close did we get to empty", and recharging happens before
        # the state is recorded -- so a step that flattened the battery
        # recorded 100% and the dip vanished. A route that ran the battery
        # to zero seven times reported a 100% minimum.
        # (Round 2 review, M-7.)
        battery_low_wh = battery_wh
        recharged_this_step = False
        if i > 0 and battery_wh <= 0.0:
            # Recharging took ZERO time and required no sunlight: the rover
            # refilled to 100% in place, in shadow, without the clock moving,
            # which is an unbounded free-energy source that made routes look
            # feasible when they are not. Charge at the solar input the cell
            # actually offers and CHARGE THE TIME IT TAKES, so elapsed_hours
            # (and everything derived from it) reflects the stop. A cell with
            # no usable sunlight cannot recharge at all. (Backend review, #13.)
            solar_in_w = solar_power_w * (1.0 - shadow_ratio)
            net_charge_w = solar_in_w - idle_power_w - heater_power_w * shadow_ratio
            if net_charge_w > 0.0:
                deficit_wh = battery_capacity_wh - battery_wh
                recharge_hours = deficit_wh / net_charge_w
                battery_wh = battery_capacity_wh
                elapsed_hours += recharge_hours
                step_time_h += recharge_hours
                recharge_count += 1
                recharged_this_step = True
            else:
                # Stranded: no sunlight to recover on. Report the flat
                # battery rather than inventing energy.
                battery_wh = 0.0
        battery_pct = battery_wh / battery_capacity_wh * 100.0

        cumulative_dist_m += step_dist
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
                battery_low_pct=max(0.0, battery_low_wh)
                / battery_capacity_wh
                * 100.0,
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
        "min_battery_pct": round(min(s.battery_low_pct for s in states), 2),
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
