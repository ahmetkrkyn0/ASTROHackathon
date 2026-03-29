"""Unit tests for backend/app/simulation.py.

No DEM file required — all grids are synthetic numpy arrays.
Run with: python test_simulation.py  (from backend/)
"""

from __future__ import annotations

import math
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from app.simulation import (
    BATTERY_CAPACITY_WH,
    DRIVE_POWER_W,
    HEATER_POWER_W,
    IDLE_POWER_W,
    NOMINAL_SPEED_MS,
    PIXEL_SIZE_M,
    RoverState,
    _slope_multiplier,
    simulate_path,
    summarize_simulation,
)

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


# ── _slope_multiplier ──────────────────────────────────────────────────────────

def test_slope_multiplier_boundaries():
    check(abs(_slope_multiplier(0.0) - 1.0) < 1e-9, "0deg = 1.0")
    check(abs(_slope_multiplier(10.0) - 1.6) < 1e-9, "10deg = 1.6")
    check(abs(_slope_multiplier(15.0) - 1.9) < 1e-9, "15deg = 1.9")
    check(abs(_slope_multiplier(25.0) - 2.5) < 1e-9, "25deg = 2.5")
    check(abs(_slope_multiplier(30.0) - 2.5) < 1e-9, "30deg = 2.5 (cap)")


def test_slope_multiplier_midpoint():
    # Midpoint of 0-10 range: 5deg = 1.3
    check(abs(_slope_multiplier(5.0) - 1.3) < 1e-9, "5deg = 1.3 (midpoint)")
    # Midpoint of 10-15: 12.5deg = 1.75
    check(abs(_slope_multiplier(12.5) - 1.75) < 1e-9, "12.5deg = 1.75 (midpoint)")
    # Midpoint of 15-25: 20deg = 2.2
    check(abs(_slope_multiplier(20.0) - 2.2) < 1e-9, "20deg = 2.2 (midpoint)")


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
    expected_time_h = PIXEL_SIZE_M / NOMINAL_SPEED_MS / 3600.0
    check(abs(s1.elapsed_hours - expected_time_h) < 1e-9, "elapsed_hours matches")

    # slope_mult at 0° = 1.0, shadow=0
    expected_energy = (DRIVE_POWER_W * 1.0 + IDLE_POWER_W) * expected_time_h
    check(abs(s1.step_energy_wh - expected_energy) < 1e-6, "step_energy_wh correct")
    expected_battery = BATTERY_CAPACITY_WH - expected_energy
    check(abs(s1.battery_wh - expected_battery) < 1e-6, "battery_wh depletes correctly")


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
    step_time_h = PIXEL_SIZE_M / NOMINAL_SPEED_MS / 3600.0
    expected_energy = (
        DRIVE_POWER_W * 1.0
        + HEATER_POWER_W * shadow
        + IDLE_POWER_W
    ) * step_time_h
    check(abs(s1.step_energy_wh - expected_energy) < 1e-6, "heater energy included")


# ── simulate_path — battery floor ─────────────────────────────────────────────

def test_battery_does_not_go_negative():
    # Very steep + many steps: battery should floor at 0
    grids = _flat_grids(slope=24.0, shadow=1.0)
    # Build a path that stays within GRID_SHAPE (50x50)
    path = [[0, i] for i in range(GRID_SHAPE[1])]
    states = simulate_path(_astar_result(path), *grids)
    for s in states:
        check(s.battery_wh >= 0.0, f"battery_wh >= 0 at step {s.step}")
        check(s.battery_pct >= 0.0, f"battery_pct >= 0 at step {s.step}")


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


def test_summarize_shadow_exposure():
    shadow = 1.0  # full shadow every cell
    grids = _flat_grids(slope=0.0, shadow=shadow)
    path = [[0, i] for i in range(3)]
    states = simulate_path(_astar_result(path), *grids)
    s = summarize_simulation(states)
    # 2 moving steps, each full shadow
    step_time_h = PIXEL_SIZE_M / NOMINAL_SPEED_MS / 3600.0
    expected = 2 * shadow * step_time_h
    # summarize rounds to 4 decimal places, so allow 1e-4 tolerance
    check(abs(s["total_shadow_exposure"] - round(expected, 4)) < 1e-6,
          "total_shadow_exposure correct")


def test_summarize_risk_counts():
    # Force battery depletion to trigger HIGH/CRITICAL
    grids = _flat_grids(slope=24.9, shadow=1.0)
    path = [[0, i] for i in range(GRID_SHAPE[1])]
    states = simulate_path(_astar_result(path), *grids)
    s = summarize_simulation(states)
    check(s["critical_steps_count"] + s["high_or_above_steps_count"] >= 0,
          "risk counts non-negative")
    # With heavy drain, expect at least some high-risk steps
    check(s["high_or_above_steps_count"] > 0,
          "heavy drain produces high-risk steps")


if __name__ == "__main__":
    tests = [
        test_slope_multiplier_boundaries,
        test_slope_multiplier_midpoint,
        test_simulate_raises_on_error,
        test_simulate_raises_on_empty_path,
        test_single_node_path,
        test_cardinal_step,
        test_diagonal_step,
        test_shadow_heater_contribution,
        test_battery_does_not_go_negative,
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
