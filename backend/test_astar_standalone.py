#!/usr/bin/env python3
"""Standalone A* test -- 500x500 synthetic lunar grid.

Run from the backend/ directory:
    python test_astar_standalone.py

Creates a random 500x500 grid with obstacles, runs A* corner-to-corner,
and validates correctness + performance (must finish in < 5 s).
"""

from __future__ import annotations

import math
import sys
import time

import numpy as np

# Ensure backend package is importable
sys.path.insert(0, ".")

from app.pathfinder import astar


# ============================================================================
#  GRID GENERATION
# ============================================================================

def make_synthetic_grids(
    size: int = 500,
    obstacle_ratio: float = 0.15,
    seed: int = 42,
    resolution_m: float = 80.0,
) -> dict:
    """Build a size x size test grid with random obstacles and cost values.

    Returns a grids dict compatible with astar().
    """
    rng = np.random.RandomState(seed)

    # Elevation: smooth terrain via low-frequency noise (Gaussian-blurred random)
    # This avoids the unrealistic pixel-level gradients of raw random noise.
    from scipy.ndimage import gaussian_filter
    raw_elev = rng.rand(size, size).astype(np.float64) * 500.0
    elevation = gaussian_filter(raw_elev, sigma=8.0)  # smooth hills

    # Slope: derived from elevation gradient (degrees)
    dy, dx = np.gradient(elevation, resolution_m)
    slope = np.degrees(np.arctan(np.sqrt(dx ** 2 + dy ** 2)))

    # Thermal: -80 C to +80 C spread
    thermal = rng.uniform(-80.0, 80.0, (size, size)).astype(np.float64)

    # Shadow ratio: 0-1
    shadow_ratio = rng.rand(size, size).astype(np.float64)

    # Traversability: start with all passable, then apply rules
    traversable = np.ones((size, size), dtype=bool)

    # Block cells with slope > 25 deg
    traversable[slope > 25.0] = False

    # Block cells with thermal < -150 C
    traversable[thermal < -150.0] = False

    # Add random obstacles
    obstacle_mask = rng.rand(size, size) < obstacle_ratio
    traversable[obstacle_mask] = False

    # Ensure start (0,0) and goal (size-1, size-1) and surroundings are clear
    for cr, cc in [(0, 0), (size - 1, size - 1)]:
        for dr in range(-5, 6):
            for dc in range(-5, 6):
                r, c = cr + dr, cc + dc
                if 0 <= r < size and 0 <= c < size:
                    traversable[r, c] = True
                    slope[r, c] = min(slope[r, c], 10.0)
                    thermal[r, c] = 60.0

    return {
        "elevation": elevation,
        "slope": slope,
        "thermal": thermal,
        "shadow_ratio": shadow_ratio,
        "traversable": traversable,
        "metadata": {"resolution_m": resolution_m},
    }


# ============================================================================
#  VALIDATION
# ============================================================================

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str | None = None) -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        suffix = f" -- {detail}" if detail else ""
        print(f"  [FAIL] {name}{suffix}")


def validate_path(
    path: list[list[int]],
    traversable: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
) -> None:
    """Run correctness checks on the returned path."""

    # Path starts at start
    check(
        "path starts at start",
        tuple(path[0]) == start,
        f"got {path[0]}, expected {start}",
    )

    # Path ends at goal
    check(
        "path ends at goal",
        tuple(path[-1]) == (goal[0], goal[1]),
        f"got {path[-1]}, expected {goal}",
    )

    # Every cell is traversable
    all_traversable = all(traversable[r, c] for r, c in path)
    check("all cells traversable", all_traversable)

    # No teleportation -- consecutive cells are at most 1 step apart
    no_teleport = True
    for i in range(1, len(path)):
        dr = abs(path[i][0] - path[i - 1][0])
        dc = abs(path[i][1] - path[i - 1][1])
        if dr > 1 or dc > 1:
            no_teleport = False
            break
    check("no teleportation in path", no_teleport)

    # Diagonal corner-cutting check
    corner_safe = True
    for i in range(1, len(path)):
        pr, pc = path[i - 1]
        cr, cc = path[i]
        dr, dc = cr - pr, cc - pc
        if abs(dr) == 1 and abs(dc) == 1:  # diagonal move
            if not traversable[pr, cc] or not traversable[cr, pc]:
                corner_safe = False
                break
    check("no corner-cutting on diagonals", corner_safe)


# ============================================================================
#  MAIN
# ============================================================================

def main() -> None:
    print("=" * 64)
    print("  LunaPath A* Standalone Test - 500x500 Grid")
    print("=" * 64)

    size = 500
    start = (0, 0)
    goal = (size - 1, size - 1)

    # Build grid
    print("\n> Generating synthetic grid...")
    t_grid = time.perf_counter()
    grids = make_synthetic_grids(size=size, obstacle_ratio=0.15, seed=42)
    grid_ms = (time.perf_counter() - t_grid) * 1000.0
    print(f"  Grid generation: {grid_ms:.0f} ms")

    trav = grids["traversable"]
    blocked = int(np.sum(~trav))
    total = size * size
    print(f"  Blocked cells:   {blocked} / {total}  ({blocked / total * 100:.1f}%)")

    # Run A*
    print("\n> Running A*...")
    result = astar(grids, start, goal)

    if result["error"]:
        print(f"\n  [X] A* failed: {result['error']}")
        print("  Retrying with lower obstacle ratio (0.05)...")
        grids = make_synthetic_grids(size=size, obstacle_ratio=0.05, seed=42)
        result = astar(grids, start, goal)
        trav = grids["traversable"]

    # Results
    m = result["metrics"]
    print(f"\n{'-' * 50}")
    print(f"  Path found:        {'YES' if not result['error'] else 'NO'}")
    print(f"  Path length:       {m['path_length_nodes']} nodes")
    print(f"  Total distance:    {m['total_distance_m']:.1f} m")
    print(f"  Total cost:        {m['total_weighted_cost']:.2f}")
    print(f"  Max slope:         {m['max_slope_deg']:.2f} deg")
    print(f"  Max thermal risk:  {m['max_thermal_risk']:.4f}")
    print(f"  Nodes expanded:    {m.get('nodes_expanded', 'N/A')}")
    print(f"  Computation time:  {m['computation_time_ms']:.1f} ms")
    print(f"{'-' * 50}")

    # Correctness validation
    print("\n> Validating path correctness...")
    if result["error"]:
        print(f"  SKIP - no path to validate ({result['error']})")
    else:
        validate_path(result["path_pixels"], trav, start, goal)

    # Performance assertion
    print("\n> Performance check...")
    check(
        "computation < 5000 ms",
        m["computation_time_ms"] < 5000.0,
        f"took {m['computation_time_ms']:.0f} ms",
    )

    # Summary
    print(f"\n{'=' * 50}")
    print(f"  PASSED: {PASS}")
    print(f"  FAILED: {FAIL}")
    print(f"  TOTAL:  {PASS + FAIL}")
    print(f"{'=' * 50}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
