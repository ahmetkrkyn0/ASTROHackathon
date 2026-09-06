"""Unit tests for backend/app/simulation.py.

No DEM file required — all grids are synthetic numpy arrays.
Run with: python test_simulation.py  (from backend/)
"""

from __future__ import annotations

import math
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from app.simulation import (
    BATTERY_CAPACITY_WH,
    DRIVE_POWER_W,
    HEATER_POWER_W,
    IDLE_POWER_W,
    PIXEL_SIZE_M,
    RoverState,
    simulate_path,
    summarize_simulation,
)
from app.constants import get_rover
from app.cost_engine import edge_travel_time_s  # C3: flat ground still slips a little

GRID_SHAPE = (50, 50)


def check(condition: bool, label: str) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        sys.exit(1)


def _flat_grids(slope=0.0, temp=-50.0, shadow=0.0, cost=0.5):
    """Return four identical flat grids for controlled tests."""
    s_g = np.full(GRID_SHAPE, slope, dtype=np.float32)
    t_g = np.full(GRID_SHAPE, temp, dtype=np.float32)
    sh_g = np.full(GRID_SHAPE, shadow, dtype=np.float32)
    c_g = np.full(GRID_SHAPE, cost, dtype=np.float32)
    return c_g, s_g, t_g, sh_g


def _astar_result(path):
    return {"path_pixels": path, "metrics": {}, "error": None}


def _snake_path(steps):
    """A path of exactly *steps* waypoints, snaking row by row.

    simulate_path now uses the cost engine's travel-time model instead of
    the old linear speed factor, which is roughly 40 percent faster on a
    steep cell and therefore 40 percent cheaper per step. A single 50-step
    row no longer drains the battery to its reserve, so the drain tests
    walk far enough to actually get there. (Round 3 review, M-9.)
    """
    path = []
    row = 0
    while len(path) < steps:
        cols = range(GRID_SHAPE[1]) if row % 2 == 0 else reversed(range(GRID_SHAPE[1]))
        for col in cols:
            path.append([row, col])
            if len(path) == steps:
                return path
        row += 1
    return path


# ── slope energy model ─────────────────────────────────────────────────────────
# The piecewise _slope_multiplier table these tests used to pin is gone: it
# was a SECOND energy model, disagreeing with the cost engine the planner
# uses and carrying no mu_coeff, so every rover was simulated with LPR-1's
# slope response. simulate_path now calls cost_engine directly, and these
# assert the properties that actually matter. (Round 3 review, M-9.)

def test_slope_energy_is_monotone_and_rover_specific():
    from app.cost_engine import gross_energy_per_metre_wh
    from app.constants import get_rover as _gr

    lpr = _gr("lpr_1")
    values = [gross_energy_per_metre_wh(t, 0.0, lpr) for t in (0.0, 5.0, 10.0, 20.0)]
    check(all(b > a for a, b in zip(values, values[1:])), "energy rises with slope")

    # mu_coeff differs by a factor of 2.7 between these two profiles, so the
    # slope RESPONSE must differ too. The old shared table made them equal.
    luvmi = _gr("luvmi_m")
    lpr_ratio = gross_energy_per_metre_wh(20.0, 0.0, lpr) / gross_energy_per_metre_wh(
        0.0, 0.0, lpr
    )
    luvmi_ratio = gross_energy_per_metre_wh(
        20.0, 0.0, luvmi
    ) / gross_energy_per_metre_wh(0.0, 0.0, luvmi)
    check(
        abs(lpr_ratio - luvmi_ratio) > 0.2,
        f"slope response is rover-specific ({lpr_ratio:.2f} vs {luvmi_ratio:.2f})",
    )


def test_simulation_time_matches_the_cost_engine():
    from app.cost_engine import edge_travel_time_s
    from app.constants import get_rover as _gr

    rover = _gr("lpr_1")
    grids = _uniform_grids(slope=20.0)
    states = simulate_path(
        {"path_pixels": [[1, 1], [1, 2]], "error": None},
        grids["cost"],
        grids["slope"],
        grids["thermal"],
        grids["shadow"],
        rover=rover,
        pixel_size_m=10.0,
    )
    expected_h = edge_travel_time_s(20.0, 10.0, rover) / 3600.0
    check(
        abs(states[-1].elapsed_hours - expected_h) < 1e-9,
        "simulated step time == cost_engine edge_travel_time_s",
    )


def _uniform_grids(slope: float, shadow: float = 0.0, thermal: float = -50.0):
    shape = (4, 4)
    return {
        "cost": np.full(shape, 0.5),
        "slope": np.full(shape, slope),
        "thermal": np.full(shape, thermal),
        "shadow": np.full(shape, shadow),
    }



# ── simulate_path — error cases ────────────────────────────────────────────────

def test_simulate_raises_on_error():
    grids = _flat_grids()
    bad_result = {"path_pixels": [], "metrics": {}, "error": "No path found"}
    raised = False
    try:
        simulate_path(bad_result, *grids)
    except ValueError:
        raised = True
    check(raised, "ValueError raised when error is not None")


def test_simulate_raises_on_empty_path():
    grids = _flat_grids()
    raised = False
    try:
        simulate_path(_astar_result([]), *grids)
    except ValueError:
        raised = True
    check(raised, "ValueError raised on empty path_pixels")


# ── simulate_path — single node ────────────────────────────────────────────────

def test_single_node_path():
    grids = _flat_grids(slope=5.0, temp=-60.0, shadow=0.3, cost=0.4)
    states = simulate_path(_astar_result([[10, 10]]), *grids)
    check(len(states) == 1, "Single node -> 1 state")
    s = states[0]
    check(s.step == 0, "step index is 0")
    check(s.distance_m == 0.0, "distance_m is 0 for first node")
    check(s.elapsed_hours == 0.0, "elapsed_hours is 0 for first node")
    check(s.step_energy_wh == 0.0, "step_energy_wh is 0 for first node")
    check(abs(s.battery_wh - BATTERY_CAPACITY_WH) < 1e-6, "battery full at start")
    check(s.recharge_count == 0, "recharge_count starts at 0")
    check(not s.recharged_this_step, "start node is not a recharge step")
    check(s.risk_level == "LOW", "risk is LOW at full battery")
    check(abs(s.slope_deg - 5.0) < 1e-4, "slope_deg read from grid")
    check(abs(s.surface_temp_c - (-60.0)) < 1e-4, "surface_temp from grid")
    check(abs(s.shadow_ratio - 0.3) < 1e-4, "shadow_ratio from grid")


# ── simulate_path — two cardinal nodes ────────────────────────────────────────

def test_cardinal_step():
    slope = 0.0
    grids = _flat_grids(slope=slope, temp=-50.0, shadow=0.0)
    path = [[0, 0], [0, 1]]  # cardinal (dc=1)
    states = simulate_path(_astar_result(path), *grids)
    check(len(states) == 2, "Two nodes -> 2 states")

    s1 = states[1]
    check(abs(s1.distance_m - PIXEL_SIZE_M) < 1e-6, "cardinal step_dist = 80 m")

    # At 0° slope: speed_factor=1.0, actual_speed=0.2 m/s
    expected_time_h = edge_travel_time_s(0.0, PIXEL_SIZE_M, get_rover()) / 3600.0
    check(abs(s1.elapsed_hours - expected_time_h) < 1e-9, "elapsed_hours matches")

    # slope_mult at 0° = 1.0, shadow=0
    expected_energy = (DRIVE_POWER_W * 1.0 + IDLE_POWER_W) * expected_time_h
    check(abs(s1.step_energy_wh - expected_energy) < 1e-6, "step_energy_wh correct")
    # The battery sees the DRAW MINUS the array's income while driving -- the
    # same signed drain the 4-D planner integrates (cost_engine.
    # move_battery_drain_wh) -- capped at capacity. In full sunlight LPR-1's
    # 410 W array outproduces a flat drive, so a full battery stays full. (B5,
    # doc 11 item 3: one energy model for planner, simulator and Monte Carlo.)
    expected_solar = float(get_rover()["p_solar_w"]) * expected_time_h
    check(abs(s1.step_solar_wh - expected_solar) < 1e-6, "step_solar_wh is the array income")
    expected_battery = min(
        BATTERY_CAPACITY_WH, BATTERY_CAPACITY_WH - expected_energy + expected_solar
    )
    check(abs(s1.battery_wh - expected_battery) < 1e-6, "battery_wh follows the net drain")


# ── simulate_path — diagonal step ─────────────────────────────────────────────

def test_diagonal_step():
    grids = _flat_grids(slope=0.0, temp=-50.0, shadow=0.0)
    path = [[0, 0], [1, 1]]  # diagonal
    states = simulate_path(_astar_result(path), *grids)
    s1 = states[1]
    expected_dist = PIXEL_SIZE_M * math.sqrt(2)
    check(abs(s1.distance_m - expected_dist) < 1e-6, "diagonal step_dist = 80*sqrt(2)")


# ── simulate_path — shadow heater energy ──────────────────────────────────────

def test_shadow_heater_contribution():
    shadow = 0.5
    grids = _flat_grids(slope=0.0, shadow=shadow)
    path = [[0, 0], [0, 1]]
    states = simulate_path(_astar_result(path), *grids)
    s1 = states[1]
    step_time_h = edge_travel_time_s(0.0, PIXEL_SIZE_M, get_rover()) / 3600.0
    expected_energy = (
        DRIVE_POWER_W * 1.0
        + HEATER_POWER_W * shadow
        + IDLE_POWER_W
    ) * step_time_h
    check(abs(s1.step_energy_wh - expected_energy) < 1e-6, "heater energy included")


def test_custom_rover_changes_energy_and_speed():
    rover = get_rover("luvmi_m")
    grids = _flat_grids(slope=0.0, shadow=0.0)
    path = [[0, 0], [0, 1]]
    states = simulate_path(_astar_result(path), *grids, rover=rover)
    s1 = states[1]

    expected_time_h = edge_travel_time_s(0.0, PIXEL_SIZE_M, rover) / 3600.0
    expected_energy = (float(rover["p_base_w"]) + float(rover["p_idle_w"])) * expected_time_h
    expected_solar = float(rover["p_solar_w"]) * expected_time_h
    expected_battery = min(
        float(rover["e_cap_wh"]),
        float(rover["e_cap_wh"]) - expected_energy + expected_solar,
    )

    check(abs(s1.elapsed_hours - expected_time_h) < 1e-9, "custom rover speed affects elapsed time")
    check(abs(s1.step_energy_wh - expected_energy) < 1e-6, "custom rover power affects energy use")
    check(abs(s1.battery_wh - expected_battery) < 1e-6, "custom rover battery capacity is used")


# ── simulate_path — one energy model with the planner (B5, doc 11 item 3) ────


def test_drive_drain_matches_the_planners_signed_drain():
    """The battery change over a driven step is exactly
    cost_engine.move_battery_drain_wh -- the quantity the 4-D planner
    integrates -- so /api/plan and /api/plan-4d agree about the battery."""
    from app.cost_engine import move_battery_drain_wh

    rover = get_rover()
    grids = _flat_grids(slope=10.0, shadow=0.6)
    path = [[0, 0], [0, 1]]
    states = simulate_path(_astar_result(path), *grids, rover=rover)
    s0, s1 = states
    # The grids are float32, so compare against the value the simulator read.
    expected = move_battery_drain_wh(10.0, PIXEL_SIZE_M, float(grids[3][0, 1]), rover)
    assert expected > 0.0  # a shaded climb drains
    assert s0.battery_wh - s1.battery_wh == pytest.approx(expected, abs=1e-6)
    assert s1.step_energy_wh - s1.step_solar_wh == pytest.approx(expected, abs=1e-6)


def test_a_drive_in_full_shadow_drains_the_gross_draw():
    grids = _flat_grids(slope=5.0, shadow=1.0)
    states = simulate_path(_astar_result([[0, 0], [0, 1]]), *grids)
    s0, s1 = states
    assert s1.step_solar_wh == 0.0
    assert s0.battery_wh - s1.battery_wh == pytest.approx(s1.step_energy_wh, abs=1e-9)


def test_summary_reports_the_solar_income():
    grids = _flat_grids(slope=3.0, shadow=0.4)
    states = simulate_path(_astar_result(_snake_path(6)), *grids)
    summary = summarize_simulation(states)
    # The summary rounds to two decimals.
    assert summary["total_solar_energy_wh"] == pytest.approx(
        sum(s.step_solar_wh for s in states), abs=0.006
    )
    assert summary["total_solar_energy_wh"] > 0.0
    assert "step_solar_wh" in states[1].to_dict()
    assert summarize_simulation([])["total_solar_energy_wh"] == 0.0


# ── simulate_path — battery floor ─────────────────────────────────────────────

def test_battery_does_not_go_negative():
    # Very steep + many steps: battery should never go negative
    grids = _flat_grids(slope=24.0, shadow=1.0)
    # Build a path that stays within GRID_SHAPE (50x50)
    path = [[0, i] for i in range(GRID_SHAPE[1])]
    states = simulate_path(_astar_result(path), *grids)
    for s in states:
        check(s.battery_wh >= 0.0, f"battery_wh >= 0 at step {s.step}")
        check(s.battery_pct >= 0.0, f"battery_pct >= 0 at step {s.step}")


def test_battery_recharges_to_full_when_depleted():
    # shadow=0.5: recharging now requires usable sunlight and costs the time
    # it takes. Under the old model the rover refilled instantly even in full
    # shadow, which was an unbounded free-energy source. (Backend review #13.)
    # Half shadow rather than full sun: with the array credited while
    # driving (B5), a 24-degree climb in full sunlight nets only ~15 Wh per
    # step for LPR-1 and 140 steps never reach the reserve; at half shadow the
    # net drain is ~44 Wh per step and the stop still charges (205 W in
    # against 52.5 W of housekeeping).
    grids = _flat_grids(slope=24.0, shadow=0.5)
    path = _snake_path(140)
    states = simulate_path(_astar_result(path), *grids)

    recharge_steps = [
        i for i in range(1, len(states))
        if states[i].battery_pct > states[i - 1].battery_pct + 1e-6
    ]

    check(len(recharge_steps) > 0, "battery recharge happens on long traversal")
    check(
        any(abs(states[i].battery_pct - 100.0) < 1e-6 for i in recharge_steps),
        "recharged state returns to 100%",
    )
    check(
        any(states[i].recharged_this_step for i in recharge_steps),
        "recharged steps are flagged on the state",
    )


# ── simulate_path — cumulative fields ────────────────────────────────────────

def test_cumulative_distance_monotone():
    grids = _flat_grids()
    path = [[0, i] for i in range(10)]
    states = simulate_path(_astar_result(path), *grids)
    for i in range(1, len(states)):
        check(
            states[i].distance_m >= states[i - 1].distance_m,
            f"distance_m monotone at step {i}",
        )


def test_cumulative_cost_matches_sum():
    cost_val = 0.7
    grids = _flat_grids(cost=cost_val)
    path = [[0, i] for i in range(5)]
    states = simulate_path(_astar_result(path), *grids)
    for i, s in enumerate(states):
        expected = cost_val * (i + 1)
        check(abs(s.cumulative_cost - expected) < 1e-4, f"cumulative_cost at step {i}")


# ── RoverState.to_dict ────────────────────────────────────────────────────────

def test_to_dict_rounds_floats():
    grids = _flat_grids()
    path = [[0, 0], [0, 1]]
    states = simulate_path(_astar_result(path), *grids)
    d = states[1].to_dict()
    for key in ("distance_m", "elapsed_hours", "battery_wh", "battery_pct",
                "slope_deg", "surface_temp_c", "shadow_ratio",
                "node_cost", "step_energy_wh", "cumulative_cost"):
        val = d[key]
        check(isinstance(val, float), f"to_dict[{key}] is float")
        # Verify it's rounded to at most 2 decimal places
        check(abs(val - round(val, 2)) < 1e-9, f"to_dict[{key}] rounded to 2dp")
    check(d["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL"),
          "risk_level is valid string")


# ── summarize_simulation ──────────────────────────────────────────────────────

def test_summarize_empty():
    summary = summarize_simulation([])
    check(summary["waypoint_count"] == 0, "empty states -> waypoint_count 0")
    check(summary["total_distance_km"] == 0.0, "empty states -> distance 0")


def test_summarize_basic():
    grids = _flat_grids(slope=0.0, shadow=0.0)
    path = [[0, i] for i in range(5)]
    states = simulate_path(_astar_result(path), *grids)
    s = summarize_simulation(states)

    check(s["waypoint_count"] == 5, "waypoint_count == 5")
    expected_dist_km = (4 * PIXEL_SIZE_M) / 1000.0
    check(abs(s["total_distance_km"] - expected_dist_km) < 1e-4,
          "total_distance_km correct")
    check(s["total_energy_consumed_wh"] > 0, "energy consumed > 0")
    check(s["final_battery_pct"] <= 100.0, "final battery <= 100%")
    check(s["min_battery_pct"] <= s["final_battery_pct"],
          "min_battery <= final")
    check(s["max_slope_deg"] >= 0.0, "max_slope_deg >= 0")
    check(s["critical_steps_count"] >= 0, "critical_steps_count >= 0")
    check(s["high_or_above_steps_count"] >= s["critical_steps_count"],
          "high_or_above includes critical")
    check("total_recharges" in s, "summary includes recharge count")


def test_summarize_shadow_exposure():
    shadow = 1.0  # full shadow every cell
    grids = _flat_grids(slope=0.0, shadow=shadow)
    path = [[0, i] for i in range(3)]
    states = simulate_path(_astar_result(path), *grids)
    s = summarize_simulation(states)
    # 2 moving steps, each full shadow
    step_time_h = edge_travel_time_s(0.0, PIXEL_SIZE_M, get_rover()) / 3600.0
    expected = 2 * shadow * step_time_h
    # summarize rounds to 4 decimal places, so allow 1e-4 tolerance
    check(abs(s["total_shadow_exposure"] - round(expected, 4)) < 1e-6,
          "total_shadow_exposure correct")


def test_summarize_risk_counts():
    # Force battery depletion to trigger HIGH/CRITICAL. Full shadow drains
    # hardest AND now blocks recharging, so this covers the stranded case.
    grids = _flat_grids(slope=24.9, shadow=1.0)
    path = _snake_path(140)
    states = simulate_path(_astar_result(path), *grids)
    s = summarize_simulation(states)
    check(s["critical_steps_count"] + s["high_or_above_steps_count"] >= 0,
          "risk counts non-negative")
    # With heavy drain, expect at least some high-risk steps
    check(s["high_or_above_steps_count"] > 0,
          "heavy drain produces high-risk steps")
    # A rover with no sunlight cannot recover: recharges must be zero, and it
    # ends stranded rather than conjuring energy. (Backend review #13.)
    check(s["total_recharges"] == 0, "no recharge is possible in full shadow")
    # The rover now stops at its SOC reserve rather than at a flat zero, and
    # the traverse is truncated there instead of continuing on a battery it
    # does not have. (Round 3 review, M-10.)
    check(s["stranded"] is True, "a rover with no sunlight ends stranded")
    check(s["stranded_at_step"] is not None, "the stranding step is reported")
    check(s["waypoint_count"] < len(path), "the traverse stops where it strands")

    # With some sunlight the same heavy drain DOES recover, and the recharge
    # costs time. (Half shadow, for the reason given in
    # test_battery_recharges_to_full_when_depleted.)
    lit = summarize_simulation(
        simulate_path(_astar_result(path), *_flat_grids(slope=24.9, shadow=0.5))
    )
    check(lit["total_recharges"] > 0, "heavy drain in sunlight produces recharges")
    check(lit["total_elapsed_hours"] > s["total_elapsed_hours"],
          "recharging advances the clock")


if __name__ == "__main__":
    tests = [
        test_slope_energy_is_monotone_and_rover_specific,
        test_simulation_time_matches_the_cost_engine,
        test_simulate_raises_on_error,
        test_simulate_raises_on_empty_path,
        test_single_node_path,
        test_cardinal_step,
        test_diagonal_step,
        test_shadow_heater_contribution,
        test_custom_rover_changes_energy_and_speed,
        test_battery_does_not_go_negative,
        test_battery_recharges_to_full_when_depleted,
        test_cumulative_distance_monotone,
        test_cumulative_cost_matches_sum,
        test_to_dict_rounds_floats,
        test_summarize_empty,
        test_summarize_basic,
        test_summarize_shadow_exposure,
        test_summarize_risk_counts,
    ]

    print(f"Running {len(tests)} simulation tests...\n")
    for fn in tests:
        print(f"{fn.__name__}:")
        fn()
    print("\nAll tests passed.")
