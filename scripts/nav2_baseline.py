#!/usr/bin/env python3
"""Compare LunaPath's multi-criteria A* against a geometric baseline.

Nav2's SmacPlanner2D searches an 8-connected occupancy costmap: it knows
where the obstacles are, not what the terrain costs. Running both on the same
grid isolates exactly what the multi-criteria cost model buys.

Nav2 itself is only needed for the optional third row; the geometric baseline
here reproduces SmacPlanner2D's objective (shortest traversable path) so the
comparison runs with or without a ROS installation.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.benchmark import shortest_traversable_path  # noqa: E402
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.pathfinder import astar  # noqa: E402


def summarise(path, grids, resolution_m):
    slope = grids["slope"]
    shadow = grids["shadow_ratio"]
    thermal = grids["thermal"]
    length_m = sum(
        resolution_m * (math.sqrt(2.0) if (a[0] != b[0] and a[1] != b[1]) else 1.0)
        for a, b in zip(path[:-1], path[1:])
    )
    cells = np.array([[r, c] for r, c in path])
    rows, cols = cells[:, 0], cells[:, 1]
    return {
        "waypoints": len(path),
        "length_km": round(length_m / 1000.0, 3),
        # nan-aware: a NaN anywhere on the path would otherwise poison max/mean
        "max_slope_deg": round(float(np.nanmax(slope[rows, cols])), 2),
        "mean_shadow_ratio": round(float(np.nanmean(shadow[rows, cols])), 4),
        "min_thermal_c": round(float(np.nanmin(thermal[rows, cols])), 2),
    }


def pick_endpoints(traversable, start, goal):
    """Validate the requested endpoints, with an actionable error."""
    for name, point in (("start", start), ("goal", goal)):
        rows, cols = traversable.shape
        if not (0 <= point[0] < rows and 0 <= point[1] < cols):
            raise SystemExit(f"{name} {point} is outside the {rows}x{cols} grid")
        if not traversable[point]:
            raise SystemExit(
                f"{name} {point} is not traversable; pick another cell "
                f"(np.argwhere(traversable) lists the valid ones)"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    # Matches the sibling comparison scripts: (100, 100) is a
    # non-traversable cell on the shipped 500x500 / 5 m-px grid, so the
    # advertised no-argument invocation always failed.
    # (Round 2 review, L-11.)
    parser.add_argument("--start", type=int, nargs=2, default=(150, 150))
    parser.add_argument("--goal", type=int, nargs=2, default=(400, 400))
    parser.add_argument("--out", default="docs/research/nav2_baseline.md")
    args = parser.parse_args()

    grids = load_preprocessed_grids()
    resolution_m = float(grids["metadata"]["resolution_m"])
    start, goal = tuple(args.start), tuple(args.goal)
    pick_endpoints(grids["traversable"], start, goal)

    t0 = time.perf_counter()
    baseline_path, _ = shortest_traversable_path(
        grids["traversable"], start, goal, resolution_m
    )
    baseline_ms = (time.perf_counter() - t0) * 1000.0

    lunapath = astar(grids, start, goal)
    if lunapath["error"] or not baseline_path:
        raise SystemExit(f"planning failed: {lunapath['error']}")

    rows = {
        "SmacPlanner2D-equivalent (geometric)": {
            **summarise(baseline_path, grids, resolution_m),
            "time_ms": round(baseline_ms, 1),
        },
        "LunaPath multi-criteria A*": {
            **summarise(lunapath["path_pixels"], grids, resolution_m),
            "time_ms": round(lunapath["metrics"]["computation_time_ms"], 1),
        },
    }

    columns = list(next(iter(rows.values())).keys())
    lines = [
        "# Nav2 baseline karsilastirmasi",
        "",
        f"Start `{start}` -> Goal `{goal}`, {resolution_m:g} m/px grid, "
        f"{grids['metadata']['shape'][0]}x{grids['metadata']['shape'][1]}.",
        "",
        "| Planlayici | " + " | ".join(columns) + " |",
        "|---|" + "---|" * len(columns),
    ]
    for name, values in rows.items():
        lines.append(f"| {name} | " + " | ".join(str(values[c]) for c in columns) + " |")
    lines += [
        "",
        "**Okuma:** Geometrik baseline en kisa gecilebilir yolu bulur ve arazinin",
        "maliyetini bilmez. LunaPath'in rotasi daha uzun olabilir; karsiliginda",
        "`max_slope_deg` ve `mean_shadow_ratio` degerleri dusuktur. Fark, cok",
        "kriterli maliyet modelinin satin aldigi seydir.",
        "",
        "```json",
        json.dumps(rows, indent=2),
        "```",
    ]
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
