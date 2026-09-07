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

Two scales
----------
The fine pass marches the site's 5 m DEM out to ``--max-range-m`` (10 km).
That is not far enough at a polar site: A4's comparison against NASA's
LOLA Earth-visibility product showed a crater-rim window whose horizon
drops 20 deg into the floor within 10 km and never comes back up, because
the far wall and the plateau beyond it lie past the fine DEM's edge. The
Earth (elevation within +/-7 deg) and the Sun (within +/-2 deg) are both
decided by exactly that far horizon. So a second pass marches a wide,
coarse DEM -- LOLA's 40 m south-polar product, ``ldem_85s_40m.img`` from
PDS Geosciences -- from the fine range outward to ``--far-range-m``, on the
fine DEM's height datum, and the cube is the maximum of the two. The far
DEM is optional: without it the cube is what it always was, and the
provenance file says so.

Usage:
    python scripts/build_horizon_cache.py
    python scripts/build_horizon_cache.py --processed-dir path/to/processed
    python scripts/build_horizon_cache.py --n-azimuth 36     # coarser, faster
    python scripts/build_horizon_cache.py --far-dem lunapath/data/raw/ldem_85s_40m.img
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

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_PROCESSED = _REPO / "lunapath" / "data" / "processed"
_RAW = _REPO / "lunapath" / "data" / "raw"
#: Site DEMs this repository has shipped with, newest first. The one that
#: actually CONTAINS the processed window is used; see _matching_raw_dem.
_RAW_DEM_CANDIDATES = (
    _RAW / "Site11_final_adj_5mpp_surf.tif",
    _RAW / "Site01_final_adj_5mpp_surf.tif",
)
_DEFAULT_FAR_DEM = _RAW / "ldem_85s_40m.img"
#: Provenance of the cube, beside it.
HORIZON_META_FILENAME = "horizon_map_meta.json"


def read_pds_polar_dem(img_path: Path) -> tuple[np.ndarray, dict]:
    """A LOLA GDR polar DEM (detached PDS3 label + raw int16 image).

    Returns heights in metres above the 1737.4 km sphere and the mapping
    from map metres to pixel indices. The label's LINE/SAMPLE_PROJECTION_OFFSET
    put the pole at the shared corner of the four central pixels, so the
    centre of 0-based pixel (i, j) sits at
    ``x = (j - sample_offset) * scale``, ``y = (line_offset - i) * scale``.
    """
    label_path = img_path.with_suffix(".lbl")
    if not label_path.exists():
        label_path = img_path.with_suffix(".LBL")
    text = label_path.read_text(encoding="utf-8", errors="replace")

    def _value(key: str) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(key) and "=" in stripped:
                return stripped.split("=", 1)[1].split("<")[0].strip().strip('"')
        raise KeyError(f"{key} not in {label_path}")

    lines = int(_value("LINES"))
    samples = int(_value("LINE_SAMPLES"))
    scaling = float(_value("SCALING_FACTOR"))
    bits = int(_value("SAMPLE_BITS"))
    scale_m = float(_value("MAP_SCALE"))
    line_offset = float(_value("LINE_PROJECTION_OFFSET"))
    sample_offset = float(_value("SAMPLE_PROJECTION_OFFSET"))
    if bits != 16:
        raise ValueError(f"expected a 16-bit LOLA GDR, got {bits}-bit")
    raw = np.fromfile(img_path, dtype="<i2")
    if raw.size != lines * samples:
        raise ValueError(
            f"{img_path} holds {raw.size} samples, label says {lines}x{samples}"
        )
    heights = raw.reshape(lines, samples).astype(np.float64) * scaling
    info = {
        "path": str(img_path),
        "lines": lines,
        "samples": samples,
        "scale_m": scale_m,
        "line_offset": line_offset,
        "sample_offset": sample_offset,
        "scaling_factor": scaling,
    }
    return heights, info


def _matching_raw_dem(
    elevation: np.ndarray, offset: dict, explicit: Path | None
) -> Path | None:
    """The raw DEM whose window at *offset* IS the processed elevation.

    metadata.json's window_offset only means something against the DEM the
    window was cut from. This repository once carried a Site11 metadata
    beside Site01 grids -- the offset pointed at terrain 40 km from the
    grids' real location, and a horizon built through it would have been
    the horizon of the wrong ground. Verifying the match costs one read.
    """
    import rasterio
    from rasterio.windows import Window

    candidates = [explicit] if explicit is not None else list(_RAW_DEM_CANDIDATES)
    rows, cols = elevation.shape
    row_off, col_off = int(offset.get("row", 0)), int(offset.get("col", 0))
    for candidate in candidates:
        if candidate is None or not candidate.exists():
            continue
        with rasterio.open(candidate) as src:
            if row_off + rows > src.height or col_off + cols > src.width:
                continue
            window = src.read(1, window=Window(col_off, row_off, cols, rows)).astype(
                np.float64
            )
        if np.allclose(window, elevation, atol=0.5, equal_nan=True):
            return candidate
        print(f"  {candidate.name}: window at {offset} is NOT the processed grid")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=_DEFAULT_PROCESSED)
    parser.add_argument("--n-azimuth", type=int, default=72)
    parser.add_argument("--max-range-m", type=float, default=10000.0)
    parser.add_argument(
        "--raw-dem",
        type=Path,
        default=None,
        help=(
            "DEM the planning window was cut from. When present the horizon "
            "is marched over the window's real surroundings instead of the "
            "crop alone -- on the production site that is worth 260 extra "
            "permanently shadowed cells. (Round 4 review, H-4.) By default "
            "the shipped site DEMs are tried and the one whose window at "
            "metadata's window_offset matches the processed grid is used."
        ),
    )
    parser.add_argument(
        "--far-dem",
        type=Path,
        default=_DEFAULT_FAR_DEM,
        help=(
            "Wide, coarse DEM for the far-field pass (LOLA ldem_85s_40m.img). "
            "Marched from --max-range-m out to --far-range-m on the fine "
            "DEM's datum; skipped, and said so, when the file is absent."
        ),
    )
    parser.add_argument("--far-range-m", type=float, default=150000.0)
    parser.add_argument("--far-max-steps", type=int, default=400)
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
    provenance: dict = {
        "n_azimuth": int(args.n_azimuth),
        "fine": {"max_range_m": float(args.max_range_m), "context": "crop"},
        "far": {"used": False},
    }

    # A ray leaving the crop is not the same thing as a ray finding no
    # obstruction, and at a polar site the long shadow is cast by the ridge
    # a few kilometres away. Read the window's surroundings when the raw DEM
    # is at hand. (Round 4 review, H-4.)
    context, roi = elevation, None
    offset = metadata.get("window_offset") or {}
    raw_dem = _matching_raw_dem(elevation, offset, args.raw_dem) if offset else None
    if args.raw_dem is not None and raw_dem is None:
        print(
            f"{args.raw_dem} does not contain the processed window at "
            f"window_offset {offset}; refusing to march the wrong terrain.",
            file=sys.stderr,
        )
        return 1
    if raw_dem is not None and offset:
        import rasterio
        from rasterio.windows import Window

        rows, cols = elevation.shape
        row_off, col_off = int(offset.get("row", 0)), int(offset.get("col", 0))
        pad = int(round(float(args.max_range_m) / resolution_m))
        provenance["fine"]["context"] = str(raw_dem)
        with rasterio.open(raw_dem) as src:
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

    # -- Far field -----------------------------------------------------------
    if args.far_dem is not None and args.far_dem.exists():
        far_cube, far_info = far_field_horizon(
            args.far_dem,
            elevation,
            metadata,
            n_azimuth=int(args.n_azimuth),
            min_range_m=float(args.max_range_m),
            max_range_m=float(args.far_range_m),
            max_steps=int(args.far_max_steps),
        )
        raised = far_cube > cube
        far_info["cells_raised_pct"] = round(100.0 * float(raised.mean()), 2)
        far_info["mean_raise_deg_where_raised"] = (
            round(float((far_cube - cube)[raised].mean()), 3) if raised.any() else 0.0
        )
        print(
            f"Far field raised the horizon in {far_info['cells_raised_pct']:.1f}% of "
            f"(azimuth, cell) pairs, by {far_info['mean_raise_deg_where_raised']:.2f} deg "
            "on average where it did"
        )
        cube = np.maximum(cube, far_cube).astype(np.float32)
        provenance["far"] = {"used": True, **far_info}
    else:
        provenance["far"] = {
            "used": False,
            "reason": f"far DEM not found at {args.far_dem}",
        }
        print(
            f"No far-field DEM at {args.far_dem}; the horizon stops at "
            f"{args.max_range_m:g} m (see the module docstring for why that "
            "under-reports the far horizon)."
        )

    np.save(out_path, cube)
    (processed / HORIZON_META_FILENAME).write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )
    print(f"Wrote {out_path} ({cube.nbytes / 2**20:.0f} MiB, shape {cube.shape})")
    print(f"Wrote {processed / HORIZON_META_FILENAME}")
    return 0


def far_field_horizon(
    far_dem_path: Path,
    elevation: np.ndarray,
    metadata: dict,
    n_azimuth: int,
    min_range_m: float,
    max_range_m: float,
    max_steps: int,
) -> tuple[np.ndarray, dict]:
    """The horizon of the window's cells beyond *min_range_m*, from a wide DEM.

    Computed on the far DEM's own pixels covering the window, then mapped
    back to the fine grid by nearest pixel -- the far horizon varies over
    kilometres, not metres. Before marching, the far DEM is shifted onto
    the fine DEM's datum by the mean difference over the window; a datum
    gap between the two products would otherwise tilt every far angle.
    """
    heights, info = read_pds_polar_dem(far_dem_path)
    scale = float(info["scale_m"])
    line_offset = float(info["line_offset"])
    sample_offset = float(info["sample_offset"])

    resolution_m = float(metadata["resolution_m"])
    rows, cols = elevation.shape
    origin_x = float(metadata["origin"]["x"])
    origin_y = float(metadata["origin"]["y"])

    # Fine cell centres in map metres, then in far-DEM pixel indices.
    xs = origin_x + np.arange(cols) * resolution_m
    ys = origin_y - np.arange(rows) * resolution_m
    js = np.rint(xs / scale + sample_offset - 0.5).astype(np.int64)
    is_ = np.rint(line_offset - ys / scale - 0.5).astype(np.int64)
    if (
        is_.min() < 0 or js.min() < 0
        or is_.max() >= heights.shape[0] or js.max() >= heights.shape[1]
    ):
        raise ValueError("the processed window lies outside the far DEM")

    # Datum check over the window: the fine DEM against the far DEM at the
    # same cell centres.
    far_at_fine = heights[is_[:, None], js[None, :]]
    finite = np.isfinite(elevation) & np.isfinite(far_at_fine)
    datum_offset = float(np.mean(elevation[finite] - far_at_fine[finite]))
    residual = float(np.std((elevation - far_at_fine)[finite]))
    print(
        f"Far DEM datum: fine - far = {datum_offset:+.1f} m over the window "
        f"(residual std {residual:.1f} m at {resolution_m:g} m vs {scale:g} m)"
    )
    adjusted = heights + datum_offset

    i0, i1 = int(is_.min()) - 1, int(is_.max()) + 2
    j0, j1 = int(js.min()) - 1, int(js.max()) + 2
    print(
        f"Far field: marching {far_dem_path.name} ({scale:g} m/px) from "
        f"{min_range_m / 1000:g} km to {max_range_m / 1000:g} km over ROI "
        f"rows {i0}:{i1}, cols {j0}:{j1}"
    )
    far = horizon_map(
        adjusted,
        resolution_m=scale,
        n_azimuth=n_azimuth,
        max_range_m=max_range_m,
        min_range_m=min_range_m,
        max_steps=max_steps,
        dense_range_m=0.0,
        roi=(i0, i1, j0, j1),
        progress=False,
    )
    # Nearest far pixel for every fine cell.
    far_fine = far[:, (is_ - i0)[:, None], (js - j0)[None, :]].astype(np.float32)
    far_info = {
        "dem": str(far_dem_path),
        "scale_m": scale,
        "min_range_m": float(min_range_m),
        "max_range_m": float(max_range_m),
        "max_steps": int(max_steps),
        "datum_offset_m": round(datum_offset, 2),
        "datum_residual_std_m": round(residual, 2),
        "roi": [i0, i1, j0, j1],
    }
    return far_fine, far_info


if __name__ == "__main__":
    raise SystemExit(main())
