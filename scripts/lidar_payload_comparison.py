#!/usr/bin/env python3
"""Compare a rover profile with and without a LiDAR payload.

Same route, same rover, one difference: a continuous sensor + heater
power draw. This is the whole point of spec 5.2 -- LiDAR does not enter
LunaPath as perception, it enters as a line item in the energy budget.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.constants import get_rover  # noqa: E402
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.pathfinder import astar  # noqa: E402
from app.sensor_payload import (  # noqa: E402
    apply_sensor_overhead_to_summary,
    with_sensor_payload,
)
from app.simulation import simulate_path, summarize_simulation  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rover-id", default="lpr_1")
    # Defaults are a traversable pair on the shipped 500x500 / 5 m-px grid;
    # the plan's (100, 100) lands in a non-traversable cell there.
    parser.add_argument("--start", type=int, nargs=2, default=(150, 150))
    parser.add_argument("--goal", type=int, nargs=2, default=(400, 400))
    parser.add_argument("--payload-w", type=float, default=12.0)
    parser.add_argument("--heater-w", type=float, default=8.0)
    parser.add_argument("--out", default="docs/research/lidar_payload_comparison.md")
    args = parser.parse_args()

    grids = load_preprocessed_grids()
    rover = get_rover(args.rover_id)
    start, goal = tuple(args.start), tuple(args.goal)

    plan = astar(grids, start, goal, rover=rover)
    if plan["error"]:
        raise SystemExit(f"planning failed: {plan['error']}")

    states = simulate_path(
        plan,
        grids["cost"],
        grids["slope"],
        grids["thermal"],
        grids["shadow_ratio"],
        rover=rover,
        pixel_size_m=float(grids["metadata"]["resolution_m"]),
    )
    # Route the baseline through the same adjustment so the LiDAR-less row
    # reports an explicit 0.0 overhead rather than a missing column.
    baseline = apply_sensor_overhead_to_summary(summarize_simulation(states), rover)

    lidar_rover = with_sensor_payload(rover, args.payload_w, args.heater_w)
    with_lidar = apply_sensor_overhead_to_summary(baseline, lidar_rover)

    rows = {
        f"{rover['name']} (LiDAR yok)": baseline,
        f"{lidar_rover['name']} ({args.payload_w:.0f} W + {args.heater_w:.0f} W isitici)": with_lidar,
    }
    columns = [
        "total_energy_consumed_wh",
        "sensor_overhead_wh",
        "final_battery_pct",
        "total_elapsed_hours",
        "waypoint_count",
    ]

    lines = [
        "# LiDAR payload karsilastirmasi",
        "",
        f"Rover `{args.rover_id}`, start `{start}` -> goal `{goal}`.",
        "Ayni rota, ayni rover; tek fark surekli sensor + isitici guc cekisi.",
        "",
        "| Profil | " + " | ".join(columns) + " |",
        "|---|" + "---|" * len(columns),
    ]
    for name, values in rows.items():
        row = [str(values.get(column, "-")) for column in columns]
        lines.append(f"| {name} | " + " | ".join(row) + " |")

    lines += [
        "",
        "**Okuma:** `sensor_overhead_wh`, ayni traverse suresi boyunca LiDAR'in",
        "cekmis olacagi enerjidir. `final_battery_pct` bu kadar duser. Bu,",
        "LunaPath'in bir sensor eklemek yerine bir kaynak butcesi kararini",
        "gosterdigi tek yerdir.",
    ]

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
