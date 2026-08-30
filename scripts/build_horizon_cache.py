#!/usr/bin/env python3
"""Build the horizon cube the 4-D planner needs for time-varying shadow.

``app.horizon.horizon_map`` depends only on elevation, so it is computed
once and cached. Without this cache ``/api/plan-4d`` falls back to a static
shadow field and says so in its response -- the planner still runs, but its
WAIT edge cannot pay for itself, because nothing about the environment
changes between slices. (Round 3 review, M-1.)

Writes ``horizon_map.npy`` beside the processed grids. On the 500x500
production grid at 72 azimuths this takes a few minutes and about 72 MB
on disk as float32.

Usage:
    python scripts/build_horizon_cache.py
    python scripts/build_horizon_cache.py --processed-dir path/to/processed
    python scripts/build_horizon_cache.py --n-azimuth 36     # coarser, faster
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np  # noqa: E402

from app.horizon import horizon_map  # noqa: E402
from app.illumination_series import HORIZON_CACHE_FILENAME  # noqa: E402

_DEFAULT_PROCESSED = (
    Path(__file__).resolve().parent.parent / "lunapath" / "data" / "processed"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=_DEFAULT_PROCESSED)
    parser.add_argument("--n-azimuth", type=int, default=72)
    parser.add_argument("--max-range-m", type=float, default=10000.0)
    parser.add_argument(
        "--force",
        action="store_true",
        help="rebuild even when a cache already exists",
    )
    args = parser.parse_args()

    processed = args.processed_dir
    elevation_path = processed / "elevation_grid.npy"
    metadata_path = processed / "metadata.json"
    if not elevation_path.exists() or not metadata_path.exists():
        print(
            f"Processed grids not found in {processed}. Run the P1 pipeline first.",
            file=sys.stderr,
        )
        return 1

    out_path = processed / HORIZON_CACHE_FILENAME
    if out_path.exists() and not args.force:
        print(f"{out_path} already exists; pass --force to rebuild.")
        return 0

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    elevation = np.load(elevation_path)
    resolution_m = float(metadata["resolution_m"])

    print(
        f"Building horizon cube: {elevation.shape} at {resolution_m:g} m/px, "
        f"{args.n_azimuth} azimuths, {args.max_range_m:g} m range"
    )
    cube = horizon_map(
        elevation,
        resolution_m=resolution_m,
        n_azimuth=args.n_azimuth,
        max_range_m=args.max_range_m,
        progress=True,
    )
    np.save(out_path, cube)
    print(f"Wrote {out_path} ({cube.nbytes / 2**20:.0f} MiB, shape {cube.shape})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
