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
        "--raw-dem",
        type=Path,
        default=(
            Path(__file__).resolve().parent.parent
            / "lunapath" / "data" / "raw" / "Site01_final_adj_5mpp_surf.tif"
        ),
        help=(
            "DEM the planning window was cut from. When present the horizon "
            "is marched over the window's real surroundings instead of the "
            "crop alone -- on the production site that is worth 260 extra "
            "permanently shadowed cells. (Round 4 review, H-4.)"
        ),
    )
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

    # A ray leaving the crop is not the same thing as a ray finding no
    # obstruction, and at a polar site the long shadow is cast by the ridge
    # a few kilometres away. Read the window's surroundings when the raw DEM
    # is at hand. (Round 4 review, H-4.)
    context, roi = elevation, None
    offset = metadata.get("window_offset") or {}
    if args.raw_dem.exists() and offset:
        import rasterio
        from rasterio.windows import Window

        rows, cols = elevation.shape
        row_off, col_off = int(offset.get("row", 0)), int(offset.get("col", 0))
        pad = int(round(float(args.max_range_m) / resolution_m))
        with rasterio.open(args.raw_dem) as src:
            r0, c0 = max(0, row_off - pad), max(0, col_off - pad)
            r1 = min(src.height, row_off + rows + pad)
            c1 = min(src.width, col_off + cols + pad)
            context = src.read(1, window=Window(c0, r0, c1 - c0, r1 - r0)).astype(
                np.float64
            )
            context = np.where(context < -1e6, np.nan, context)
            if src.nodata is not None and np.isfinite(src.nodata):
                context = np.where(
                    np.isclose(context, float(src.nodata)), np.nan, context
                )
        roi = (row_off - r0, row_off - r0 + rows, col_off - c0, col_off - c0 + cols)
        print(f"Using the window's real context: {context.shape}, ROI {roi}")
    else:
        print("Raw DEM not available; marching over the crop alone (see H-4).")

    print(
        f"Building horizon cube: ROI {elevation.shape} at {resolution_m:g} m/px, "
        f"{args.n_azimuth} azimuths, {args.max_range_m:g} m range"
    )
    cube = horizon_map(
        context,
        resolution_m=resolution_m,
        n_azimuth=args.n_azimuth,
        max_range_m=args.max_range_m,
        roi=roi,
        progress=True,
    )
    np.save(out_path, cube)
    print(f"Wrote {out_path} ({cube.nbytes / 2**20:.0f} MiB, shape {cube.shape})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
