#!/usr/bin/env python3
"""Build the long-run Earth-visibility layer beside the processed grids.

LunaPath's own version of the LOLA "Average Earth Visibility" product
(Mazarico et al. 2011; PGDA product 69): for every cell, the fraction of
sampled instants in which the Earth clears the local terrain horizon. It
depends on the horizon cube (``horizon_map.npy``, from
``scripts/build_horizon_cache.py``) and on the NAIF kernels; it is computed
once and cached, like the horizon itself.

Writes ``earth_visibility_grid.npy`` (float32 fraction) and
``earth_visibility_meta.json`` (sampling span, step, count, elevation range).
``app.data_loader`` picks both up on the next load, and from then on
``/api/terrain`` lists the layer, ``/api/layers/earth_visibility`` serves it,
and ``/api/earth-series`` falls back to it when no epoch is given.

Sampling. The Earth's elevation at the pole librates with a ~27 day period
and an amplitude of ~6.7 deg, so a year at hourly steps (8 766 samples,
~15 s on the 500x500 grid) resolves the cycle thirteen times over. NASA's
product averages 18.6 years -- the lunar nodal period -- to also flatten the
slow modulation; ``--span-days 6798.4`` reproduces that (163 000 samples,
a few minutes) for a tighter validation.

Usage:
    python scripts/build_earth_visibility_cache.py
    python scripts/build_earth_visibility_cache.py --span-days 6798.4 --step-hours 1
    python scripts/build_earth_visibility_cache.py --start-utc 2026-01-01T00:00:00
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np  # noqa: E402

from app.earth_visibility import (  # noqa: E402
    EARTH_VISIBILITY_CACHE_FILENAME,
    EARTH_VISIBILITY_META_FILENAME,
    long_run_earth_visibility,
)
from app.illumination_series import HORIZON_CACHE_FILENAME  # noqa: E402

_DEFAULT_PROCESSED = (
    Path(__file__).resolve().parent.parent / "lunapath" / "data" / "processed"
)
#: One lunar nodal period, the span NASA's product averages over.
NODAL_PERIOD_DAYS: float = 6798.4


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=_DEFAULT_PROCESSED)
    parser.add_argument(
        "--start-utc",
        default="2026-01-01T00:00:00",
        help="first sampled instant (UTC); the span runs forward from here",
    )
    parser.add_argument(
        "--span-days",
        type=float,
        default=365.25,
        help=f"sampling span in days (NASA's product: {NODAL_PERIOD_DAYS})",
    )
    parser.add_argument("--step-hours", type=float, default=1.0)
    parser.add_argument(
        "--force", action="store_true", help="rebuild even when a cache already exists"
    )
    args = parser.parse_args()

    processed = args.processed_dir
    horizon_path = processed / HORIZON_CACHE_FILENAME
    metadata_path = processed / "metadata.json"
    if not horizon_path.exists():
        print(
            f"{horizon_path} not found. Run scripts/build_horizon_cache.py first.",
            file=sys.stderr,
        )
        return 1
    if not metadata_path.exists():
        print(f"{metadata_path} not found. Run the P1 pipeline first.", file=sys.stderr)
        return 1

    out_path = processed / EARTH_VISIBILITY_CACHE_FILENAME
    meta_out = processed / EARTH_VISIBILITY_META_FILENAME
    if out_path.exists() and not args.force:
        print(f"{out_path} already exists; pass --force to rebuild.")
        return 0

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    # The loader records where the grids live; the series code reads the
    # horizon cube from there. Set it the way data_loader would.
    metadata["processed_dir"] = str(processed)

    horizon = np.load(horizon_path)
    print(
        f"Sampling Earth visibility: {horizon.shape[1]}x{horizon.shape[2]} cells, "
        f"{horizon.shape[0]} azimuths, {args.span_days:g} days from "
        f"{args.start_utc} at {args.step_hours:g} h"
    )
    started = time.perf_counter()
    fraction, info = long_run_earth_visibility(
        horizon,
        metadata,
        start_utc=args.start_utc,
        span_days=args.span_days,
        step_hours=args.step_hours,
        progress=True,
    )
    elapsed = time.perf_counter() - started
    info["build_seconds"] = round(elapsed, 1)
    info["horizon_cache"] = HORIZON_CACHE_FILENAME

    np.save(out_path, fraction)
    meta_out.write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(
        f"Wrote {out_path} (mean fraction {info['mean_fraction']:.3f}, "
        f"Earth elevation {info['earth_elevation_min_deg']:.2f} .. "
        f"{info['earth_elevation_max_deg']:.2f} deg, {info['n_samples']} samples, "
        f"{elapsed:.0f} s)"
    )
    print(f"Wrote {meta_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
