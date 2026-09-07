#!/usr/bin/env python3
"""Fetch NASA's measured roughness and PSR products for the planning window (C4).

NASA GSFC's Planetary Geodesy group publishes, for the lunar south pole
(PGDA product 90; Barker et al. 2023, PSJ 4:183; DOI
10.60903/gsfcpgda-lola-spole), multi-baseline roughness maps computed from
the LOLA spots -- "the spread of height residuals of individual LOLA spots
around a plane fit to the LDEM within a circular window whose diameter is
equal to a baseline of *M meters" -- at 50 m/px, and a 20 m/px map of the
permanently shadowed regions (506 349 features). Both are cloud-optimised
GeoTIFFs in the same south-polar stereographic frame as the planning grid.

This script reads, for the shipped planning window only, the 100 m-baseline
roughness (the grid criterion) plus the other baselines, the Hurst exponent
and the 100 m plane-fit slope (report only), and the PSR mask, with
rasterio's ``/vsicurl/`` range reads: the window is 50 x 50 pixels at 50 m
and 125 x 125 at 20 m, one 512-pixel COG tile each, ~1 MB per product
instead of 150-650 MB. Everything is co-registered to the 5 m grid with
NEAREST resampling -- every 5 m cell carries the value of the product pixel
that contains it, a block statistic, not an interpolated guess -- onto the
grid's own transform (origin = upper-left corner, as the Site11 TIF says).

Before anything is written, two checks:

* the products' projection parameters must equal the grid's
  (``same_projection``; names such as "unnamed" vs "Moon (2015) - Sphere"
  are ignored), and
* NASA's own 100 m plane-fit slope must rank like the block mean of our 5 m
  slope grid (Spearman >= ``--min-registration-spearman``, default 0.9;
  measured 0.989 on Site11) -- the proof the window landed where it should.

The criterion's [0, 1] scale is the empirical CDF of the roughness product
over the 80-90 S region, sampled from every ``--regional-every``-th COG tile
along each axis (36 tiles, ~9.4 M finite pixels by default) and stored as
201 quantile knots in ``roughness_meta.json["scale"]``: a cell's criterion
value is its percentile rank among the region's 50 m pixels. That is a
statistical scale (MODEL) on a MEASURED layer; no rover tolerance is
implied or invented.

Writes beside the processed grids (all gitignored):
    roughness_grid.npy + roughness_meta.json    100 m-baseline roughness, metres, 5 m grid
    psr_grid.npy + psr_meta.json                PSR mask 1.0/0.0, 5 m grid
    roughness_baselines.npz                     raw 50 m windows for the report

Usage:
    python scripts/build_roughness_cache.py                     # Site11, all baselines
    python scripts/build_roughness_cache.py --baselines 100     # the criterion only
    python scripts/build_roughness_cache.py --skip-regional     # keep the cached scale
    python scripts/build_roughness_cache.py --force
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np  # noqa: E402

from app.roughness import (  # noqa: E402
    LDRM_BASELINE_M,
    LDRM_BASELINES_M,
    LDRM_PRODUCT,
    LDRM_RESOLUTION_M,
    LPSR_FEATURE_COUNT,
    LPSR_PRODUCT,
    LPSR_RESOLUTION_M,
    PGDA_DATA_DOI,
    PGDA_PRODUCT_URL,
    PSR_CACHE_FILENAME,
    PSR_CLAIM,
    PSR_LAYER_VALIDITY,
    PSR_META_FILENAME,
    ROUGHNESS_BASELINES_FILENAME,
    ROUGHNESS_CACHE_FILENAME,
    ROUGHNESS_CLAIM,
    ROUGHNESS_LAYER_VALIDITY,
    ROUGHNESS_META_FILENAME,
    ROUGHNESS_REFERENCES,
    ROUGHNESS_SCALE_VALIDITY,
    ecdf_scale_from_sample,
    ldrm_url,
    lpsr_url,
    same_projection,
)

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_PROCESSED = _REPO / "lunapath" / "data" / "processed"

#: GDAL settings for range reads: no directory listing, only .TIF over HTTP.
_VSICURL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".TIF,.tif",
    "GDAL_HTTP_MAX_RETRY": "3",
    "GDAL_HTTP_RETRY_DELAY": "5",
}
_READ_ATTEMPTS = 3

LDRM_DEFINITION = (
    "LOLA Digital Roughness Map (LDRM, in meters). This is the spread of height "
    "residuals of individual LOLA spots around a plane fit to the LDEM within a "
    "circular window whose diameter is equal to a baseline of *M meters."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _window_bounds(metadata: dict) -> tuple[float, float, float, float]:
    """(x0, x1, y_bottom, y_top) of the grid in map metres. ``origin`` is the
    UPPER-LEFT CORNER of cell (0, 0): verified against the Site11 TIF's own
    transform (t * (col 2500, row 2400) = (-32 500, 11 000))."""
    res = float(metadata["resolution_m"])
    rows, cols = int(metadata["shape"][0]), int(metadata["shape"][1])
    ox, oy = float(metadata["origin"]["x"]), float(metadata["origin"]["y"])
    return ox, ox + cols * res, oy - rows * res, oy


def _open(url: str):
    import rasterio

    return rasterio.open("/vsicurl/" + url)


def read_header(url: str) -> dict:
    import rasterio

    with rasterio.Env(**_VSICURL_ENV):
        with _open(url) as ds:
            return {
                "url": url,
                "crs_wkt": ds.crs.to_wkt() if ds.crs else None,
                "transform": list(ds.transform)[:6],
                "resolution_m": float(ds.transform.a),
                "shape": [int(ds.height), int(ds.width)],
                "dtype": str(ds.dtypes[0]),
                "nodata": None if ds.nodata is None else (None if np.isnan(ds.nodata) else float(ds.nodata)),
                "tiled": bool(ds.is_tiled),
                "block_shape": [int(b) for b in ds.block_shapes[0]],
                "compression": None if ds.compression is None else str(ds.compression.value),
                "tags": {k: v for k, v in ds.tags().items() if not k.startswith("NC_GLOBAL#history")},
            }


def read_window(url: str, bounds: tuple[float, float, float, float], pad_px: int, attempts: int = _READ_ATTEMPTS) -> dict:
    """The product pixels covering ``bounds`` plus ``pad_px`` on every side,
    as float32 with NaN for no-data, with the window's own transform."""
    import rasterio
    from rasterio.windows import Window

    x0, x1, y_bottom, y_top = bounds
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            started = time.perf_counter()
            with rasterio.Env(**_VSICURL_ENV):
                with _open(url) as ds:
                    r0, c0 = ds.index(x0, y_top)
                    r1, c1 = ds.index(x1, y_bottom)
                    r0, c0 = max(0, r0 - pad_px), max(0, c0 - pad_px)
                    r1, c1 = min(ds.height, r1 + pad_px), min(ds.width, c1 + pad_px)
                    window = Window(c0, r0, c1 - c0, r1 - r0)
                    data = ds.read(1, window=window).astype(np.float32)
                    if ds.nodata is not None and not np.isnan(ds.nodata):
                        data = np.where(data == ds.nodata, np.nan, data)
                    transform = ds.window_transform(window)
                    crs_wkt = ds.crs.to_wkt()
            return {
                "url": url,
                "data": data,
                "transform": list(transform)[:6],
                "crs_wkt": crs_wkt,
                "row0": int(r0),
                "col0": int(c0),
                "rows": int(r1 - r0),
                "cols": int(c1 - c0),
                "pad_px": int(pad_px),
                "seconds": round(time.perf_counter() - started, 1),
                "fetched_utc": _utc_now(),
            }
        except Exception as exc:  # network hiccups: retry, then give up loudly
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(5.0 * (attempt + 1))
    raise RuntimeError(f"could not read {url}: {last_error}")


def coregister_nearest(window: dict, dst_transform, dst_crs: str, shape: tuple[int, int]) -> np.ndarray:
    """Nearest-neighbour reprojection of a fetched window onto the grid."""
    import rasterio
    from rasterio.warp import Resampling, reproject

    out = np.full(shape, np.nan, dtype=np.float64)
    reproject(
        source=np.asarray(window["data"], dtype=np.float64),
        destination=out,
        src_transform=rasterio.Affine(*window["transform"]),
        src_crs=window["crs_wkt"],
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        resampling=Resampling.nearest,
        src_nodata=np.nan,
        dst_nodata=np.nan,
    )
    return out


def block_mean(grid: np.ndarray, factor: int) -> np.ndarray:
    rows, cols = grid.shape
    rows_c, cols_c = rows // factor, cols // factor
    trimmed = np.asarray(grid[: rows_c * factor, : cols_c * factor], dtype=np.float64)
    return np.nanmean(trimmed.reshape(rows_c, factor, cols_c, factor), axis=(1, 3))


def registration_check(slope_grid: np.ndarray, slp_on_grid: np.ndarray, factor: int) -> dict:
    """Spearman between NASA's 100 m plane-fit slope and the block mean of
    our 5 m slope at the product's posting: the co-registration proof."""
    from scipy.stats import spearmanr

    ours = block_mean(slope_grid, factor)
    theirs = np.asarray(slp_on_grid, dtype=np.float64)[::factor, ::factor][: ours.shape[0], : ours.shape[1]]
    ok = np.isfinite(ours) & np.isfinite(theirs)
    rho = float(spearmanr(ours[ok], theirs[ok]).statistic) if ok.sum() > 2 else float("nan")
    return {
        "product": f"LDRM_80S_{LDRM_RESOLUTION_M}MPP_ADJ_SLP_{LDRM_BASELINE_M}M",
        "against": f"block mean of slope_grid.npy over {factor}x{factor} cells ({LDRM_RESOLUTION_M} m)",
        "spearman": rho,
        "n_blocks": int(ok.sum()),
        "ours_median_deg": float(np.nanmedian(ours[ok])) if ok.any() else None,
        "theirs_median_deg": float(np.nanmedian(theirs[ok])) if ok.any() else None,
    }


def regional_sample(url: str, every: int, workers: int) -> tuple[np.ndarray, dict]:
    """Every ``every``-th COG tile along each axis, finite pixels only."""
    import rasterio
    from rasterio.windows import Window

    with rasterio.Env(**_VSICURL_ENV):
        with _open(url) as ds:
            bh, bw = ds.block_shapes[0]
            height, width = ds.height, ds.width
    nby, nbx = -(-height // bh), -(-width // bw)
    tiles = [(by, bx) for by in range(every // 2, nby, every) for bx in range(every // 2, nbx, every)]

    def read_tile(tile):
        by, bx = tile
        with rasterio.Env(**_VSICURL_ENV):
            with _open(url) as ds:
                window = Window(bx * bw, by * bh, min(bw, width - bx * bw), min(bh, height - by * bh))
                arr = ds.read(1, window=window).astype(np.float64)
        return arr[np.isfinite(arr)]

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        parts = list(pool.map(read_tile, tiles))
    sample = np.concatenate(parts) if parts else np.array([])
    info = {
        "url": url,
        "tile_shape": [int(bh), int(bw)],
        "every": int(every),
        "n_tiles": len(tiles),
        "n_finite": int(sample.size),
        "seconds": round(time.perf_counter() - started, 1),
        "quantiles_m": {
            f"p{p}": float(np.percentile(sample, p)) for p in (1, 5, 25, 50, 75, 95, 99)
        } if sample.size else {},
        "fetched_utc": _utc_now(),
    }
    return sample, info


def _stats(grid: np.ndarray) -> dict:
    finite = grid[np.isfinite(grid)]
    return {
        "n_nan": int(grid.size - finite.size),
        "min": float(finite.min()) if finite.size else None,
        "p5": float(np.percentile(finite, 5)) if finite.size else None,
        "median": float(np.median(finite)) if finite.size else None,
        "p95": float(np.percentile(finite, 95)) if finite.size else None,
        "max": float(finite.max()) if finite.size else None,
        "n_unique": int(np.unique(finite).size),
    }


def _crs_name(wkt: str | None) -> str | None:
    if not wkt:
        return None
    start = wkt.find('"')
    end = wkt.find('"', start + 1)
    return wkt[start + 1 : end] if start >= 0 and end > start else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--processed-dir", type=Path, default=_DEFAULT_PROCESSED)
    parser.add_argument(
        "--baselines",
        default=",".join(str(b) for b in LDRM_BASELINES_M),
        help="LDRM baselines (m) to fetch; the first is the grid criterion (must be 100)",
    )
    parser.add_argument("--n-workers", type=int, default=4)
    parser.add_argument("--pad-px", type=int, default=2, help="edge padding in 50 m product pixels")
    parser.add_argument("--psr-pad-px", type=int, default=5, help="edge padding in 20 m PSR pixels")
    parser.add_argument("--regional-every", type=int, default=4, help="sample every N-th COG tile per axis")
    parser.add_argument("--skip-regional", action="store_true", help="reuse the scale in the existing meta")
    parser.add_argument("--min-registration-spearman", type=float, default=0.9)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    processed: Path = args.processed_dir
    meta_path = processed / "metadata.json"
    slope_path = processed / "slope_grid.npy"
    if not meta_path.exists() or not slope_path.exists():
        print(f"{processed} has no metadata.json / slope_grid.npy; run the P1 pipeline first.", file=sys.stderr)
        return 1
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))

    outputs = [processed / name for name in (ROUGHNESS_CACHE_FILENAME, ROUGHNESS_META_FILENAME, PSR_CACHE_FILENAME, PSR_META_FILENAME, ROUGHNESS_BASELINES_FILENAME)]
    if all(path.exists() for path in outputs) and not args.force:
        print("roughness/PSR cache already present; pass --force to rebuild.")
        return 0

    baselines = [int(b) for b in args.baselines.split(",") if b.strip()]
    if not baselines or baselines[0] != LDRM_BASELINE_M:
        print(f"--baselines must start with {LDRM_BASELINE_M} (the grid criterion)", file=sys.stderr)
        return 1

    import rasterio

    res = float(metadata["resolution_m"])
    rows, cols = int(metadata["shape"][0]), int(metadata["shape"][1])
    grid_crs = metadata["crs"]
    bounds = _window_bounds(metadata)
    dst_transform = rasterio.transform.from_origin(bounds[0], bounds[3], res, res)
    print(f"grid {rows}x{cols} @ {res:g} m, x {bounds[0]:.0f}..{bounds[1]:.0f}, y {bounds[2]:.0f}..{bounds[3]:.0f}")

    # 1. headers and the projection check
    rough_url = ldrm_url(LDRM_BASELINE_M)
    psr_url = lpsr_url()
    headers = {name: read_header(url) for name, url in (("roughness", rough_url), ("psr", psr_url))}
    for name, header in headers.items():
        if not same_projection(header["crs_wkt"], grid_crs):
            print(f"{name}: projection differs from the grid's; refusing to co-register.\n  product: {header['crs_wkt']}\n  grid:    {grid_crs}", file=sys.stderr)
            return 1
        print(f"{name}: {header['shape'][0]}x{header['shape'][1]} @ {header['resolution_m']:g} m, same projection as the grid")

    # 2. windows, in parallel
    jobs = {f"rough_{b}m": (ldrm_url(b), args.pad_px) for b in baselines}
    jobs["hurst"] = (ldrm_url(kind="H"), args.pad_px)
    jobs["slp_100m"] = (ldrm_url(LDRM_BASELINE_M, kind="SLP"), args.pad_px)
    jobs["psr"] = (psr_url, args.psr_pad_px)
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, args.n_workers)) as pool:
        futures = {name: pool.submit(read_window, url, bounds, pad) for name, (url, pad) in jobs.items()}
        windows = {name: future.result() for name, future in futures.items()}
    for name, window in windows.items():
        print(f"  {name}: {window['rows']}x{window['cols']} px in {window['seconds']} s, nan {int(np.isnan(window['data']).sum())}")
    print(f"windows fetched in {time.perf_counter() - started:.0f} s")

    # 3. co-registration (nearest) to the 5 m grid
    rough_5m = coregister_nearest(windows["rough_100m"], dst_transform, grid_crs, (rows, cols))
    slp_5m = coregister_nearest(windows["slp_100m"], dst_transform, grid_crs, (rows, cols))
    psr_5m = coregister_nearest(windows["psr"], dst_transform, grid_crs, (rows, cols))
    if np.isnan(psr_5m).any():
        print(f"warning: {int(np.isnan(psr_5m).sum())} PSR cells have no data; they are written as NaN", file=sys.stderr)

    # 4. registration check against our own slope grid
    factor = int(round(LDRM_RESOLUTION_M / res))
    if factor < 1 or abs(factor * res - LDRM_RESOLUTION_M) > 1e-6:
        print(f"grid resolution {res} m does not divide the product's {LDRM_RESOLUTION_M} m; cannot run the registration check", file=sys.stderr)
        return 1
    slope_grid = np.load(slope_path).astype(np.float64)
    check = registration_check(slope_grid, slp_5m, factor)
    check["threshold"] = float(args.min_registration_spearman)
    print(f"registration check: Spearman(LDRM SLP_100M, block-mean slope) = {check['spearman']:.4f} over {check['n_blocks']} blocks")
    if not np.isfinite(check["spearman"]) or check["spearman"] < args.min_registration_spearman:
        print("registration check FAILED; nothing written.", file=sys.stderr)
        return 1

    # 5. the criterion's scale: regional ECDF
    existing_meta = None
    rough_meta_path = processed / ROUGHNESS_META_FILENAME
    if rough_meta_path.exists():
        existing_meta = json.loads(rough_meta_path.read_text(encoding="utf-8"))
    if args.skip_regional and existing_meta and existing_meta.get("scale"):
        scale_meta = existing_meta["scale"]
        regional_info = existing_meta.get("regional_sample")
        print("regional sample skipped; scale reused from the existing meta")
    else:
        sample, regional_info = regional_sample(rough_url, args.regional_every, max(1, args.n_workers))
        print(f"regional sample: {regional_info['n_tiles']} tiles, {regional_info['n_finite']} finite px, {regional_info['seconds']} s")
        scale = ecdf_scale_from_sample(
            sample,
            n_knots=201,
            source=(
                f"empirical CDF of {LDRM_PRODUCT} over 80-90 S: every {args.regional_every}th 512-px COG tile "
                f"per axis ({regional_info['n_tiles']} tiles, {regional_info['n_finite']} finite pixels)"
            ),
        )
        scale_meta = scale.to_meta()

    # 6. write
    fetched = windows["rough_100m"]["fetched_utc"]
    roughness_meta = {
        "layer": "roughness",
        "validity": ROUGHNESS_LAYER_VALIDITY,
        "scale_validity": ROUGHNESS_SCALE_VALIDITY,
        "product": LDRM_PRODUCT,
        "product_url": PGDA_PRODUCT_URL,
        "data_doi": PGDA_DATA_DOI,
        "file_url": rough_url,
        "definition": LDRM_DEFINITION,
        "baseline_m": LDRM_BASELINE_M,
        "resolution_m": LDRM_RESOLUTION_M,
        "units": "m",
        "fetched_utc": fetched,
        "raster": headers["roughness"],
        "window": {k: windows["rough_100m"][k] for k in ("row0", "col0", "rows", "cols", "pad_px", "transform", "seconds")},
        "crs_match": {
            "same_projection": True,
            "grid_crs_name": _crs_name(grid_crs),
            "product_crs_name": _crs_name(headers["roughness"]["crs_wkt"]),
            "rule": "projection parameters compared (proj, lat_0, lon_0, x_0, y_0, sphere radius); names ignored",
        },
        "destination": {
            "transform": list(dst_transform)[:6],
            "resolution_m": res,
            "shape": [rows, cols],
            "origin_rule": "metadata origin is the upper-left CORNER of cell (0, 0), as the Site11 TIF transform gives it",
        },
        "resampling": "nearest",
        "resampling_note": (
            f"each {res:g} m cell carries the value of the {LDRM_RESOLUTION_M} m pixel that contains it "
            f"({factor}x{factor} cells per pixel); a block statistic, not an interpolation"
        ),
        "stats_on_grid_m": _stats(rough_5m),
        "registration_check": check,
        "scale": scale_meta,
        "regional_sample": regional_info,
        "claim": ROUGHNESS_CLAIM,
        "references": list(ROUGHNESS_REFERENCES),
        "built_by": "scripts/build_roughness_cache.py",
    }
    psr_count = int(np.nansum(psr_5m >= 0.5))
    psr_factor = int(round(LPSR_RESOLUTION_M / res))
    psr_blocks = (psr_5m >= 0.5)[::psr_factor, ::psr_factor] if psr_factor >= 1 else (psr_5m >= 0.5)
    psr_meta = {
        "layer": "psr",
        "validity": PSR_LAYER_VALIDITY,
        "product": LPSR_PRODUCT,
        "product_url": PGDA_PRODUCT_URL,
        "data_doi": PGDA_DATA_DOI,
        "file_url": psr_url,
        "resolution_m": LPSR_RESOLUTION_M,
        "product_feature_count": LPSR_FEATURE_COUNT,
        "units": "boolean (1.0 inside a PSR)",
        "fetched_utc": windows["psr"]["fetched_utc"],
        "raster": headers["psr"],
        "window": {k: windows["psr"][k] for k in ("row0", "col0", "rows", "cols", "pad_px", "transform", "seconds")},
        "crs_match": roughness_meta["crs_match"] | {"product_crs_name": _crs_name(headers["psr"]["crs_wkt"])},
        "destination": roughness_meta["destination"],
        "resampling": "nearest",
        "n_psr_cells": psr_count,
        "psr_fraction": psr_count / float(rows * cols),
        "n_psr_pixels_product": int(psr_blocks.sum()),
        "n_nan_cells": int(np.isnan(psr_5m).sum()),
        "claim": PSR_CLAIM,
        "references": list(ROUGHNESS_REFERENCES),
        "built_by": "scripts/build_roughness_cache.py",
    }

    np.save(processed / ROUGHNESS_CACHE_FILENAME, rough_5m.astype(np.float32))
    np.save(processed / PSR_CACHE_FILENAME, psr_5m.astype(np.float32))
    rough_meta_path.write_text(json.dumps(roughness_meta, indent=2), encoding="utf-8")
    (processed / PSR_META_FILENAME).write_text(json.dumps(psr_meta, indent=2), encoding="utf-8")
    np.savez(
        processed / ROUGHNESS_BASELINES_FILENAME,
        baselines_m=np.array(baselines),
        **{f"rough_{b}m": windows[f"rough_{b}m"]["data"] for b in baselines},
        hurst=windows["hurst"]["data"],
        slp_100m=windows["slp_100m"]["data"],
        transform_50m=np.array(windows["rough_100m"]["transform"], dtype=np.float64),
        rough_100m_on_grid=rough_5m.astype(np.float32),
        slp_100m_on_grid=slp_5m.astype(np.float32),
    )
    s = roughness_meta["stats_on_grid_m"]
    print(
        f"wrote {ROUGHNESS_CACHE_FILENAME} (median {s['median']:.3f} m, p95 {s['p95']:.3f}, max {s['max']:.3f}, "
        f"{s['n_unique']} blocks), {PSR_CACHE_FILENAME} ({psr_count} PSR cells, {psr_meta['psr_fraction']:.2%}), "
        f"{ROUGHNESS_BASELINES_FILENAME} ({len(baselines)} baselines)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
