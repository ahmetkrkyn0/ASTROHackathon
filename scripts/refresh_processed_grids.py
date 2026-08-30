#!/usr/bin/env python3
"""Bring the shipped .npy grids back in sync with the current cost model.

The artefacts in ``lunapath/data/processed/`` drift from the code every time
a penalty formula or a traversability rule changes, because regenerating
them normally means re-running the whole P1 pipeline against the raw DEM --
which is a large download nobody keeps checked out. So they sat stale:
``cost_model`` on disk read ``weighted_cell_cost_without_barrier`` against a
code constant that had moved on twice, ``traversability_grid.npy`` was
written by a call that passed neither a rover nor the elevation NaN check,
and the thermal layer had never been coupled to shadow at all. The backend
recomputed all of it on every request, so nothing was WRONG at runtime --
but anything reading the ``.npy`` files directly (a notebook, a figure, the
frontend) got pre-fix numbers with no way to tell. (Round 3 review, L-6.)

This script needs no DEM. It recomputes everything derivable from the layers
already on disk -- thermal coupling, traversability, cost -- and rewrites
them together with an accurate metadata.json.

Usage:
    python scripts/refresh_processed_grids.py
    python scripts/refresh_processed_grids.py --processed-dir path/to/processed
    python scripts/refresh_processed_grids.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np  # noqa: E402

from app.constants import DEFAULT_ROVER_ID, get_rover  # noqa: E402
from app.cost_engine import (  # noqa: E402
    COST_MODEL_ID,
    compute_cost_grid,
    resolve_weights,
)
from app.thermal_model import couple_shadow_to_thermal  # noqa: E402
from app.traversability import (  # noqa: E402
    compute_traversability_bool,
    weakest_validity,
)

_DEFAULT_PROCESSED = (
    Path(__file__).resolve().parent.parent / "lunapath" / "data" / "processed"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=_DEFAULT_PROCESSED)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would change without writing anything",
    )
    args = parser.parse_args()

    processed: Path = args.processed_dir
    metadata_path = processed / "metadata.json"
    if not metadata_path.exists():
        print(f"metadata.json not found in {processed}", file=sys.stderr)
        return 1

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    validity = dict(metadata.get("layer_validity", {}))

    def load(stem: str) -> np.ndarray:
        return np.load(processed / f"{stem}.npy").astype(np.float64)

    elevation = load("elevation_grid")
    slope = load("slope_grid")
    thermal = load("thermal_grid")
    shadow = load("shadow_ratio_grid")
    old_traversable = np.load(processed / "traversability_grid.npy")

    already_coupled = bool(metadata.get("thermal_shadow_coupled", False))
    thermal_validity = str(validity.get("thermal", "UNKNOWN"))
    shadow_validity = str(validity.get("shadow_ratio", "UNKNOWN"))

    if already_coupled:
        print("thermal grid is already shadow-coupled; leaving it alone")
    else:
        before_min, before_max = float(thermal.min()), float(thermal.max())
        thermal = np.asarray(
            couple_shadow_to_thermal(thermal, shadow), dtype=np.float64
        )
        thermal_validity = weakest_validity(thermal_validity, shadow_validity)
        print(
            f"thermal coupled to shadow: [{before_min:.1f}, {before_max:.1f}] -> "
            f"[{thermal.min():.1f}, {thermal.max():.1f}] C, "
            f"validity {validity.get('thermal')} -> {thermal_validity}"
        )

    rover_id = str(metadata.get("default_rover_id", DEFAULT_ROVER_ID))
    rover = get_rover(rover_id)
    weights = resolve_weights(metadata.get("cost_weights"), rover)

    traversable = compute_traversability_bool(slope, thermal, elevation, rover=rover)
    changed = int(np.count_nonzero(traversable != old_traversable.astype(bool)))
    print(
        f"traversability for {rover_id}: {int(traversable.sum())} passable "
        f"({100.0 * traversable.mean():.1f}%), {changed} cells differ from disk"
    )

    cost = compute_cost_grid(
        slope,
        thermal,
        shadow,
        float(metadata["resolution_m"]),
        traversable=traversable,
        weights=weights,
        rover=rover,
    )
    finite = cost[np.isfinite(cost)]
    print(
        f"cost model {metadata.get('cost_model')!r} -> {COST_MODEL_ID!r}; "
        f"finite range [{finite.min():.4f}, {finite.max():.4f}]"
    )

    metadata["cost_model"] = COST_MODEL_ID
    metadata["cost_weights"] = weights
    metadata["thermal_shadow_coupled"] = True
    validity["thermal"] = thermal_validity
    validity["traversable"] = weakest_validity(
        str(validity.get("slope", "UNKNOWN")), thermal_validity
    )
    validity["cost"] = weakest_validity(
        str(validity.get("slope", "UNKNOWN")), thermal_validity, shadow_validity
    )
    metadata["layer_validity"] = validity

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    np.save(processed / "thermal_grid.npy", thermal)
    np.save(processed / "traversability_grid.npy", traversable.astype(np.float64))
    np.save(processed / "cost_grid.npy", cost)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\nwrote thermal_grid, traversability_grid, cost_grid and metadata.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
