"""Simulation engine for LunaPath rover path execution."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from .constants import DEFAULT_TARGET_RESOLUTION_M, get_rover
from .cost_engine import (
    edge_travel_time_s,
    gross_energy_per_metre_wh,
    housekeeping_power_w,
)

_DEFAULT_ROVER = get_rover()

# Backward-compatible aliases for the default rover.
BATTERY_CAPACITY_WH: float = float(_DEFAULT_ROVER["e_cap_wh"])
DRIVE_POWER_W: float = float(_DEFAULT_ROVER["p_base_w"])
IDLE_POWER_W: float = float(_DEFAULT_ROVER["p_idle_w"])
HEATER_POWER_W: float = float(_DEFAULT_ROVER["p_heater_w"])
NOMINAL_SPEED_MS: float = float(_DEFAULT_ROVER["v_max_ms"])
PIXEL_SIZE_M: float = float(DEFAULT_TARGET_RESOLUTION_M)

# One lunar day. A recharge stop longer than this is not a stop, it is the
# end of the mission: the Sun has come round again and the rover still has
# not filled its battery, which means the cell cannot support the load at
# all. The previous code had no bound whatsoever -- a cell offering
# 0.001 W of net charge produced a ~618-year recharge, reported without
# comment as an ordinary total_elapsed_hours. (Round 3 review, M-10.)
MAX_RECHARGE_HOURS: float = 29.53 * 24.0


def _diag_distance_m(pixel_size_m: float) -> float:
    return pixel_size_m * math.sqrt(2)


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
    # The grade actually driven into this cell, from the elevation
    # difference across the step. Equal to slope_deg when no elevation grid
    # was supplied. (Round 4 review, L-4.)
    segment_slope_deg: float = 0.0
    # Battery level at this step's lowest point, before any recharge stop.
    # Equal to battery_pct on steps that did not recharge.
    battery_low_pct: float = 100.0
    # True once a recharge stop was needed and the cell could not supply it
    # within one lunar day. Everything after this point is not a drive, it
    # is a rover waiting to die; the summary reports it rather than
    # continuing to quote a battery percentage as if the traverse succeeded.
    stranded: bool = False
    # The array's income while driving this step (p_solar_w scaled by the
    # cell's illumination, over the drive time). The battery moves by
    # step_energy_wh minus this -- cost_engine.move_battery_drain_wh, the
    # same signed drain the 4-D planner integrates. Until B5 the simulator
    # charged the gross draw and credited nothing, so /api/plan and
    # /api/plan-4d disagreed about the battery on every lit cell (doc 11,
    # section 2.3, item 3).
    step_solar_wh: float = 0.0

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
            "segment_slope_deg": round(self.segment_slope_deg, 2),
            "surface_temp_c": round(self.surface_temp_c, 2),
            "shadow_ratio": round(self.shadow_ratio, 2),
            "node_cost": round(self.node_cost, 2),
            "step_energy_wh": round(self.step_energy_wh, 2),
            "cumulative_cost": round(self.cumulative_cost, 2),
            "recharge_count": self.recharge_count,
            "recharged_this_step": self.recharged_this_step,
            "battery_low_pct": round(self.battery_low_pct, 2),
            "stranded": self.stranded,
            "step_solar_wh": round(self.step_solar_wh, 2),
        }


def simulate_path(
    astar_result: dict,
    cost_grid: np.ndarray,
    slope_grid: np.ndarray,
    thermal_grid: np.ndarray,
    shadow_grid: np.ndarray,
    rover: dict[str, Any] | None = None,
    pixel_size_m: float | None = None,
    elevation_grid: np.ndarray | None = None,
    solar_gain: float = 1.0,
) -> list[RoverState]:
    """Simulate rover traversal over an A* path.

    *solar_gain* is C1's panel gain (:mod:`app.panel`), a single scalar here
    because a 2-D route carries no time axis: the 2-D grid's shadow ratio is
    a long-run fraction, so the only gain that pairs with it is a long-run
    one. 1.0 -- the default -- is the pre-C1 model and is bit-for-bit the
    identity.

    Physics model
    -------------
    Travel time and traction energy come from ``cost_engine`` -- the same
    ``edge_travel_time_s`` and slope multiplier the planner used to choose
    this route. This module used to carry a SECOND, incompatible model: a
    ``max(0.2, 1 - slope/50)`` speed factor against the cost engine's
    ``v_max * cos(theta)``, and a fixed piecewise energy table against the
    engine's ``1 + mu_coeff * sin(theta)``. At 20 degrees the two travel
    times differed by 47 percent, so every route was CHOSEN under one model
    and REPORTED under another -- and because the table carried no
    ``mu_coeff``, LUVMI-M (1.296) and LPR-1 (3.471) were simulated with
    identical slope energy despite a factor of 2.7 between their published
    traction coefficients. (Round 3 review, M-9.)

    *elevation_grid*, when given, supplies the SEGMENT slope -- the elevation
    difference across each driven step. Round 3 (H-2) established that this
    and the ``np.gradient`` cell slope are different quantities, made the
    planner gate on the segment one, and reported both; the simulator kept
    computing travel time and energy from the cell slope alone, so the route
    was validated against one geometry and costed against another. The drive
    grade is now the worse of the two, which is the conservative reading and
    never under-reports a climb. (Round 4 review, L-4.)
    """
    if astar_result.get("error") is not None:
        raise ValueError(f"A* result contains error: {astar_result['error']}")

    path_pixels = astar_result.get("path_pixels", [])
    if not path_pixels:
        raise ValueError("path_pixels is empty — nothing to simulate")

    rover_cfg = get_rover() if rover is None else rover
    battery_capacity_wh = float(rover_cfg["e_cap_wh"])
    solar_power_w = float(rover_cfg.get("p_solar_w") or 0.0) * float(solar_gain)
    soc_min_pct = float(rover_cfg.get("soc_min_pct") or 0.0)
    # The reserve the rover is not supposed to spend. The barrier term of the
    # documented cost function encodes it, but the barrier had no production
    # caller, so nothing enforced it anywhere -- and this simulator ran the
    # battery to a flat 0 percent before even considering a recharge.
    # (Round 3 review, H-1 and M-10.)
    reserve_wh = battery_capacity_wh * soc_min_pct
    step_pixel_size_m = float(pixel_size_m or PIXEL_SIZE_M)
    diag_dist_m = _diag_distance_m(step_pixel_size_m)

    states: list[RoverState] = []
    battery_wh = battery_capacity_wh
    cumulative_dist_m = 0.0
    elapsed_hours = 0.0
    cumulative_cost = 0.0
    recharge_count = 0
    stranded = False

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
        shadow_ratio = float(shadow_grid[r, c])

        segment_slope_deg = slope_deg
        if i > 0 and elevation_grid is not None:
            prev = path_pixels[i - 1]
            dz = float(elevation_grid[r, c]) - float(
                elevation_grid[int(prev[0]), int(prev[1])]
            )
            if math.isfinite(dz):
                segment_slope_deg = math.degrees(math.atan2(abs(dz), step_dist))
        drive_slope_deg = max(slope_deg, segment_slope_deg)

        if i == 0:
            step_time_h = 0.0
            step_energy = 0.0
            step_solar = 0.0
        else:
            travel_s = edge_travel_time_s(drive_slope_deg, step_dist, rover_cfg)
            if not math.isfinite(travel_s):
                raise ValueError(
                    f"step {i} at ({r}, {c}) has slope {drive_slope_deg} deg, which "
                    "the travel-time model cannot cross; the planner should not "
                    "have produced this edge"
                )
            step_time_h = travel_s / 3600.0
            step_energy = (
                gross_energy_per_metre_wh(drive_slope_deg, shadow_ratio, rover_cfg)
                * step_dist
            )
            # The array keeps producing while the rover drives. Draw minus
            # this income is cost_engine.move_battery_drain_wh -- the signed
            # drain the 4-D planner integrates -- and the battery is capped
            # at capacity, as there. (B5; doc 11 section 2.3, item 3.)
            step_solar = solar_power_w * (1.0 - shadow_ratio) * step_time_h

        battery_wh = min(battery_capacity_wh, battery_wh - step_energy + step_solar)
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
        if i > 0 and not stranded and battery_wh <= reserve_wh:
            # Recharging took ZERO time and required no sunlight: the rover
            # refilled to 100% in place, in shadow, without the clock moving,
            # which is an unbounded free-energy source that made routes look
            # feasible when they are not. Charge at the solar input the cell
            # actually offers and CHARGE THE TIME IT TAKES, so elapsed_hours
            # (and everything derived from it) reflects the stop. A cell with
            # no usable sunlight cannot recharge at all. (Backend review, #13.)
            solar_in_w = solar_power_w * (1.0 - shadow_ratio)
            net_charge_w = solar_in_w - housekeeping_power_w(shadow_ratio, rover_cfg)
            if net_charge_w > 0.0:
                deficit_wh = battery_capacity_wh - battery_wh
                recharge_hours = deficit_wh / net_charge_w
                if recharge_hours > MAX_RECHARGE_HOURS:
                    # The cell cannot refill the battery inside a lunar day.
                    # Charge for as long as that day allows, bank what it
                    # bought, and report the rover as stranded rather than
                    # quoting a recharge that outlasts the mission.
                    battery_wh += net_charge_w * MAX_RECHARGE_HOURS
                    elapsed_hours += MAX_RECHARGE_HOURS
                    step_time_h += MAX_RECHARGE_HOURS
                    stranded = True
                else:
                    battery_wh = battery_capacity_wh
                    elapsed_hours += recharge_hours
                    step_time_h += recharge_hours
                    recharge_count += 1
                    recharged_this_step = True
            else:
                # Stranded: no sunlight to recover on. Report the flat
                # battery rather than inventing energy.
                battery_wh = max(0.0, battery_wh)
                stranded = True
        battery_pct = battery_wh / battery_capacity_wh * 100.0
        battery_low_pct = max(0.0, battery_low_wh) / battery_capacity_wh * 100.0

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
                # Risk is read off the step's LOW point, not the level after
                # a recharge stop. Recharging happens before the state is
                # recorded, so a route that repeatedly ran down to its
                # reserve and refilled reported every step as LOW -- the
                # same shape as the min_battery_pct bug round 2 fixed one
                # field over. (Round 3 review, M-10.)
                risk_level=_risk_level(battery_low_pct),
                slope_deg=slope_deg,
                segment_slope_deg=segment_slope_deg,
                surface_temp_c=float(thermal_grid[r, c]),
                shadow_ratio=shadow_ratio,
                node_cost=node_cost,
                step_energy_wh=step_energy,
                cumulative_cost=cumulative_cost,
                recharge_count=recharge_count,
                recharged_this_step=recharged_this_step,
                battery_low_pct=battery_low_pct,
                stranded=stranded,
                step_solar_wh=step_solar,
            )
        )

        if stranded:
            # The traverse ends here. Emitting the remaining waypoints would
            # report distance the rover cannot cover and a battery it does
            # not have; the caller learns how far it got from
            # waypoint_count and why from the stranded flag.
            break

    return states


def _shadow_and_power_checks(
    states: list[RoverState], rover: dict[str, Any]
) -> dict[str, Any]:
    """Constraint checks against rover-catalogue limits nothing used to read.

    ``h_max_shadow_h`` and ``p_peak_w`` were published through /api/rovers as
    if they bounded something. They bounded nothing. Both are now checked
    against the simulated route and reported. (Round 3 review, M-8.)
    """
    h_max_shadow_h = rover.get("h_max_shadow_h")
    p_peak_w = rover.get("p_peak_w")
    p_base_w = float(rover["p_base_w"])
    mu_coeff = float(rover["mu_coeff"])

    max_continuous_shadow_h = 0.0
    running_shadow_h = 0.0
    peak_power_exceeded_steps = 0

    for index in range(1, len(states)):
        step_time_h = states[index].elapsed_hours - states[index - 1].elapsed_hours
        if step_time_h < 0.0:
            step_time_h = 0.0
        # "In shadow" is the same 0.2 threshold corridor.py uses to decide
        # whether a cell counts as a safe haven, so the two agree on what
        # "lit" means.
        if states[index].shadow_ratio > 0.2:
            running_shadow_h += step_time_h
            max_continuous_shadow_h = max(max_continuous_shadow_h, running_shadow_h)
        else:
            running_shadow_h = 0.0

        traction_w = p_base_w * (
            1.0 + mu_coeff * math.sin(math.radians(max(0.0, states[index].slope_deg)))
        )
        if p_peak_w is not None and traction_w > float(p_peak_w):
            peak_power_exceeded_steps += 1

    return {
        "max_continuous_shadow_h": round(max_continuous_shadow_h, 4),
        "shadow_limit_h": None if h_max_shadow_h is None else float(h_max_shadow_h),
        "shadow_limit_exceeded": (
            None
            if h_max_shadow_h is None
            else bool(max_continuous_shadow_h > float(h_max_shadow_h))
        ),
        "peak_power_exceeded_steps": peak_power_exceeded_steps,
    }


def summarize_simulation(
    states: list[RoverState], rover: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Produce aggregate statistics from a simulated state sequence."""
    if not states:
        return {
            "total_distance_km": 0.0,
            "total_elapsed_hours": 0.0,
            "final_battery_pct": 0.0,
            "min_battery_pct": 0.0,
            "max_slope_deg": 0.0,
            "max_segment_slope_deg": 0.0,
            "total_energy_consumed_wh": 0.0,
            "total_solar_energy_wh": 0.0,
            "total_shadow_exposure": 0.0,
            "critical_steps_count": 0,
            "high_or_above_steps_count": 0,
            "waypoint_count": 0,
            "total_recharges": 0,
            "stranded": False,
            "stranded_at_step": None,
            "max_continuous_shadow_h": 0.0,
            "shadow_limit_h": None,
            "shadow_limit_exceeded": None,
            "peak_power_exceeded_steps": 0,
        }

    rover_cfg = get_rover() if rover is None else rover

    last = states[-1]
    total_shadow_exposure = 0.0
    for i in range(1, len(states)):
        step_time_h = states[i].elapsed_hours - states[i - 1].elapsed_hours
        if step_time_h <= 0.0:
            continue
        total_shadow_exposure += states[i].shadow_ratio * step_time_h

    summary = {
        "total_distance_km": round(last.distance_m / 1000.0, 4),
        "total_elapsed_hours": round(last.elapsed_hours, 4),
        "final_battery_pct": round(last.battery_pct, 2),
        "min_battery_pct": round(min(s.battery_low_pct for s in states), 2),
        "max_slope_deg": round(max(s.slope_deg for s in states), 2),
        "max_segment_slope_deg": round(
            max(s.segment_slope_deg for s in states), 2
        ),
        "total_energy_consumed_wh": round(sum(s.step_energy_wh for s in states), 2),
        # The array's income over the driven steps (recharge stops are not
        # included: they are reported through total_recharges and the clock).
        "total_solar_energy_wh": round(sum(s.step_solar_wh for s in states), 2),
        "total_shadow_exposure": round(total_shadow_exposure, 4),
        "critical_steps_count": sum(1 for s in states if s.risk_level == "CRITICAL"),
        "high_or_above_steps_count": sum(
            1 for s in states if s.risk_level in ("HIGH", "CRITICAL")
        ),
        "waypoint_count": len(states),
        "total_recharges": max(s.recharge_count for s in states),
        "stranded": bool(last.stranded),
        "stranded_at_step": last.step if last.stranded else None,
    }
    summary.update(_shadow_and_power_checks(states, rover_cfg))
    return summary
