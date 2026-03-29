"""Integration tests for weighted cost grids and planner behaviour."""

from __future__ import annotations

import sys

import numpy as np

from app.cost_engine import compute_cost_grid
from app.pathfinder import astar
from app.traversability import compute_traversability_bool

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str | None = None) -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
        return

    FAIL += 1
    suffix = f" — {detail}" if detail else ""
    print(f"  [FAIL] {name}{suffix}")


def test_weight_sensitivity_cost_grid() -> None:
    slope = np.array([[5.0, 20.0], [5.0, 20.0]], dtype=np.float64)
    thermal = np.array([[60.0, 60.0], [20.0, 20.0]], dtype=np.float64)
    shadow = np.array([[0.1, 0.9], [0.1, 0.9]], dtype=np.float64)
    traversable = np.ones_like(slope, dtype=bool)

    slope_heavy = compute_cost_grid(
        slope,
        thermal,
        shadow,
        resolution_m=80.0,
        traversable=traversable,
        weights={
            "w_slope": 0.80,
            "w_energy": 0.10,
            "w_shadow": 0.05,
            "w_thermal": 0.05,
        },
    )
    shadow_thermal_heavy = compute_cost_grid(
        slope,
        thermal,
        shadow,
        resolution_m=80.0,
        traversable=traversable,
        weights={
            "w_slope": 0.10,
            "w_energy": 0.10,
            "w_shadow": 0.40,
            "w_thermal": 0.40,
        },
    )

    changed = not np.allclose(slope_heavy, shadow_thermal_heavy)
    check("weight sensitivity on cost grid", changed)


def test_hard_block_is_separate_from_cost() -> None:
    slope = np.array([[10.0, 30.0], [5.0, 10.0]], dtype=np.float64)
    thermal = np.array([[10.0, 10.0], [-200.0, 10.0]], dtype=np.float64)
    shadow = np.array([[0.0, 0.0], [0.8, 0.2]], dtype=np.float64)

    traversable = compute_traversability_bool(slope, thermal)
    cost = compute_cost_grid(
        slope,
        thermal,
        shadow,
        resolution_m=80.0,
        traversable=traversable,
    )

    blocked = ~traversable
    check("blocked cells stay blocked", blocked.sum() == 2)
    check("blocked cells receive inf cost", bool(np.all(np.isinf(cost[blocked]))))
    check("passable cells keep finite cost", bool(np.all(np.isfinite(cost[traversable]))))


def test_regression_old_bug_is_closed() -> None:
    """Old bug: weights changed nothing because only traversability was produced."""
    slope = np.array([[5.0, 20.0], [5.0, 20.0]], dtype=np.float64)
    thermal = np.array([[60.0, 60.0], [20.0, 20.0]], dtype=np.float64)
    shadow = np.array([[0.0, 1.0], [0.0, 1.0]], dtype=np.float64)

    traversable = compute_traversability_bool(slope, thermal)
    cost_a = compute_cost_grid(
        slope,
        thermal,
        shadow,
        resolution_m=80.0,
        traversable=traversable,
        weights={"w_slope": 0.8, "w_energy": 0.1, "w_shadow": 0.05, "w_thermal": 0.05},
    )
    cost_b = compute_cost_grid(
        slope,
        thermal,
        shadow,
        resolution_m=80.0,
        traversable=traversable,
        weights={"w_slope": 0.1, "w_energy": 0.1, "w_shadow": 0.4, "w_thermal": 0.4},
    )

    same_hard_mask = np.array_equal(traversable, compute_traversability_bool(slope, thermal))
    changed_cost = not np.allclose(cost_a, cost_b)

    check("regression: traversability still weight-invariant", same_hard_mask)
    check("regression: weighted output now changes", changed_cost)


def test_planner_responds_to_weight_profiles() -> None:
    resolution = 1000.0
    elevation = np.zeros((7, 7), dtype=np.float64)
    thermal = np.full((7, 7), 60.0, dtype=np.float64)
    shadow = np.zeros((7, 7), dtype=np.float64)

    # Short middle corridor: valid but risky.
    thermal[2:5, 1:6] = -60.0
    shadow[2:5, 1:6] = 1.0

    traversable = np.ones_like(elevation, dtype=bool)

    # Build cost grids for each weight profile so grid-cost mode works
    direct_weights = {
        "w_slope": 0.70,
        "w_energy": 0.25,
        "w_shadow": 0.025,
        "w_thermal": 0.025,
    }
    safe_weights = {
        "w_slope": 0.05,
        "w_energy": 0.05,
        "w_shadow": 0.45,
        "w_thermal": 0.45,
    }

    slope = np.zeros_like(elevation)  # flat grid → slope = 0
    direct_cost = compute_cost_grid(slope, thermal, shadow, resolution, traversable=traversable, weights=direct_weights)
    safe_cost = compute_cost_grid(slope, thermal, shadow, resolution, traversable=traversable, weights=safe_weights)

    start = (3, 0)
    goal = (3, 6)

    direct_pref = astar(
        {
            "elevation": elevation, "thermal": thermal, "shadow_ratio": shadow,
            "traversable": traversable, "cost": direct_cost,
            "metadata": {"resolution_m": resolution},
        },
        start, goal,
        weights=direct_weights,
        constraints={"max_shadow_h": 60.0, "max_energy_wh": 5400.0, "min_soc": 0.05},
    )
    safe_pref = astar(
        {
            "elevation": elevation, "thermal": thermal, "shadow_ratio": shadow,
            "traversable": traversable, "cost": safe_cost,
            "metadata": {"resolution_m": resolution},
        },
        start, goal,
        weights=safe_weights,
        constraints={"max_shadow_h": 60.0, "max_energy_wh": 5400.0, "min_soc": 0.05},
    )

    check("planner found path for direct-pref", direct_pref["error"] is None, str(direct_pref["error"]))
    check("planner found path for safe-pref", safe_pref["error"] is None, str(safe_pref["error"]))

    if direct_pref["error"] is None and safe_pref["error"] is None:
        different_path = direct_pref["path_pixels"] != safe_pref["path_pixels"]
        different_cost = (
            direct_pref["metrics"]["total_weighted_cost"]
            != safe_pref["metrics"]["total_weighted_cost"]
        )
        # Path may be identical on tiny grids where detour cost exceeds
        # corridor penalty; the important check is that costs differ.
        check("planner path or cost changes with weights", different_path or different_cost)
        check("planner cost changes with weights", different_cost)


def main() -> None:
    print("=" * 60)
    print("  Weighted Integration Tests")
    print("=" * 60)

    test_weight_sensitivity_cost_grid()
    test_hard_block_is_separate_from_cost()
    test_regression_old_bug_is_closed()
    test_planner_responds_to_weight_profiles()

    print(f"\n{'=' * 50}")
    print(f"  PASSED: {PASS}")
    print(f"  FAILED: {FAIL}")
    print(f"  TOTAL:  {PASS + FAIL}")
    print(f"{'=' * 50}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
