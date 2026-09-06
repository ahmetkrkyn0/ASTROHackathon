#!/usr/bin/env python3
"""Build the heat1d envelope cache for GET /api/thermal-envelope (C6).

Runs heat1d (Hayne 2017, GitHub main with slope support) at the loaded
site's latitude for every slope in ``thermal_dwell.ENVELOPE_SLOPES_DEG``,
records the Sun's elevation and azimuth at every output step, and bins the
surface temperature by (Sun elevation x Sun-parallel slope) -- the
counterpart, on LunaPath's model, of JSC's unlimited-operations envelope
chart (ICES-2025-376). Writes

    lunapath/data/processed/thermal_envelope_heat1d.npz
    lunapath/data/processed/thermal_envelope_meta.json

both gitignored. About a minute (ten heat1d runs of ~4 s each at ndays=13).
Without heat1d it says so and writes nothing; no synthetic matrix is ever
written.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np  # noqa: E402

from app import thermal_dwell as TD  # noqa: E402
from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids  # noqa: E402
from app.serializer import pixel_to_lonlat  # noqa: E402
from app.thermal_model import Heat1DModel  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out-dir", default=None, help="directory for the .npz and meta JSON (default: the processed grids)")
    parser.add_argument("--lat", type=float, default=None, help="latitude in degrees (default: the loaded grid's centre)")
    parser.add_argument("--ndays", type=int, default=13, help="lunar days heat1d simulates after equilibration (default 13)")
    parser.add_argument(
        "--slopes", default=None, help="comma-separated slopes in degrees (default thermal_dwell.ENVELOPE_SLOPES_DEG)"
    )
    args = parser.parse_args()

    if not Heat1DModel.available():
        print("heat1d with slope support is not installed; nothing written (pip install heat1d from GitHub main, python/ subdirectory)")
        return 2

    lat = args.lat
    out_dir = Path(args.out_dir) if args.out_dir else Path(_P1_PROCESSED_DIR)
    if lat is None:
        grids = load_preprocessed_grids()
        meta = grids["metadata"]
        rows, cols = meta["shape"]
        _lon, lat = pixel_to_lonlat(rows // 2, cols // 2, meta)
        if args.out_dir is None and meta.get("processed_dir"):
            out_dir = Path(meta["processed_dir"])
    slopes = tuple(TD.ENVELOPE_SLOPES_DEG if args.slopes is None else (float(s) for s in args.slopes.split(",")))

    print(f"heat1d envelope: lat {lat:.4f} deg, slopes {list(slopes)}, ndays {args.ndays}")
    t0 = time.perf_counter()
    samples = TD.heat1d_envelope_samples(float(lat), slopes=slopes, ndays=int(args.ndays))
    seconds = time.perf_counter() - t0
    binned = TD.bin_envelope(samples, TD.ENVELOPE_EL_EDGES, TD.ENVELOPE_SPAR_EDGES)
    try:
        import heat1d

        heat1d_version = str(getattr(heat1d, "__version__", "unknown"))
    except Exception:  # noqa: BLE001
        heat1d_version = "unknown"
    meta_out = {
        "lat_deg": float(lat),
        "slopes_deg": [float(s) for s in slopes],
        "slope_az_deg": 0.0,
        "ndays": int(args.ndays),
        "solver": "crank-nicolson",
        "heat1d_version": heat1d_version,
        "n_samples": int(samples["surface_c"].size),
        "bins_visited": int(np.isfinite(binned["tmax"]).sum()),
        "bins_total": int(binned["tmax"].size),
        "surface_c_min": float(np.nanmin(samples["surface_c"])),
        "surface_c_max": float(np.nanmax(samples["surface_c"])),
        "el_deg_min": float(samples["el_deg"].min()),
        "el_deg_max": float(samples["el_deg"].max()),
        "seconds": round(seconds, 1),
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": (
            "heat1d Model subclass recording Sun elevation/azimuth at every advance(); final-phase "
            "samples aligned with T rows; s_par = atan(tan(slope) * cos(az_sun - slope_az)); per bin "
            "the maximum surface temperature"
        ),
        "validity": TD.THERMAL_DWELL_VALIDITY,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / TD.ENVELOPE_CACHE_FILENAME
    TD.save_envelope_cache(str(path), binned, meta_out)
    print(
        f"wrote {path.name} and {TD.ENVELOPE_META_FILENAME}: {meta_out['n_samples']} samples, "
        f"{meta_out['bins_visited']}/{meta_out['bins_total']} bins, surface {meta_out['surface_c_min']:.1f}.."
        f"{meta_out['surface_c_max']:.1f} C, {seconds:.1f} s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
