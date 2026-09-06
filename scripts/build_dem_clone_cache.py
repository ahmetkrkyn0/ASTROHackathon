#!/usr/bin/env python3
"""Fetch NASA's DEM clones for the planning window and derive their horizons (B3).

NASA GSFC's Planetary Geodesy group publishes, for every 5 m/px south-polar
site DEM, a Z-uncertainty map (``toterr``), a slope-uncertainty map
(``slperr``) and 100 statistical clones (PGDA product 78). Each clone is a
full surface DEM -- ``surface + toterr * xi`` with a spatially correlated
unit field -- so the error realisation is ``clone - surface``. This script
reads, for the shipped planning window only, the two sigma maps and the
first ``--n-clones`` clones (the window plus a ``--near-range-m`` pad), with
rasterio's ``/vsicurl/`` range reads in parallel: the server delivers ~170
KB/s per connection and ~545 KB/s over four (measured 4 Sep 2026), and a
whole clone is 41 MB where the padded window is 3 MB.

Every clone is checked against the surface before it is kept: the error
must be zero-mean (|mean| < 0.1 m) and its RMS must be NASA's own toterr
RMS to within 30 percent -- the proof that the file is a clone of THIS
window. The checks are written to the provenance file.

Horizons. The 4-D planner works on block centres (``coarsen`` 4); for each
clone the near field (samples within ``--near-range-m``) is marched on the
clone's padded window at those centres, and the far field -- the surface
DEM's own 10 km context beyond the near range plus the LOLA 40 m far field
(``scripts/build_horizon_cache.py``) -- is marched once on the surface and
shared. The two sample sets partition the production march, so the surface
DEM's own ``max(near, far)`` is checked to be the production cube at those
cells; the script refuses to write clone cubes that fail that check. What
is held fixed (the far field) and the shift it could hide
(``median(toterr) / near_range``) are written down.

Writes beside the processed grids (all gitignored):
    dem_elevation_sigma.npy, dem_slope_sigma_nasa.npy      NASA's maps, window
    dem_clones.npy + dem_clones_meta.json                    (N, R, C) padded clones
    dem_surf_horizon_far.npy                                 the shared far field
    dem_clone_horizons.npy + dem_clone_horizons_meta.json    (N, A, h, w) cubes

Usage:
    python scripts/build_dem_clone_cache.py                  # Site11, 20 clones, 1 km pad
    python scripts/build_dem_clone_cache.py --n-clones 100   # extends an existing cache
    python scripts/build_dem_clone_cache.py --skip-horizons  # slope / passability only
    python scripts/build_dem_clone_cache.py --synthetic      # offline: toterr must already be cached
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from app.horizon import horizon_map  # noqa: E402
from app.illumination_series import HORIZON_CACHE_FILENAME  # noqa: E402
from app.uncertainty import (  # noqa: E402
    CLONE_HORIZONS_META_FILENAME,
    DEM_CLONES_META_FILENAME,
    ELEVATION_SIGMA_FILENAME,
    PGDA_PRODUCT_URL,
    PGDA_REFERENCE,
    SLOPE_SIGMA_NASA_FILENAME,
    SURF_HORIZON_FAR_FILENAME,
    clone_check,
    clone_url,
    load_clone_horizons,
    load_dem_clones,
    near_far_steps,
    padded_box,
    slperr_url,
    synthetic_clones,
    toterr_url,
    write_clone_horizons,
    write_dem_clones,
)
from build_horizon_cache import (  # noqa: E402
    HORIZON_META_FILENAME,
    _DEFAULT_FAR_DEM,
    _matching_raw_dem,
    far_field_horizon,
)

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_PROCESSED = _REPO / "lunapath" / "data" / "processed"

#: GDAL settings for range reads: no directory listing, only .tif over HTTP.
_VSICURL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    "GDAL_HTTP_MAX_RETRY": "3",
    "GDAL_HTTP_RETRY_DELAY": "5",
}
_READ_ATTEMPTS = 3


def _read_window(source: str, box: dict, attempts: int = _READ_ATTEMPTS) -> tuple[np.ndarray, dict]:
    """Read ``box`` from a local path or a URL (via /vsicurl/) as float32,
    NaN for no-data. Returns the array and the raster's shape/geotransform."""
    import rasterio
    from rasterio.windows import Window

    path = source if not source.startswith("http") else "/vsicurl/" + source
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with rasterio.Env(**_VSICURL_ENV):
                with rasterio.open(path) as src:
                    data = src.read(
                        1, window=Window(box["col0"], box["row0"], box["cols"], box["rows"])
                    ).astype(np.float32)
                    nodata = src.nodata
                    info = {
                        "raster_rows": int(src.height),
                        "raster_cols": int(src.width),
                        "transform": [float(v) for v in src.transform[:6]],
                    }
            data = np.where(data < -1e6, np.nan, data)
            if nodata is not None and np.isfinite(nodata):
                data = np.where(np.isclose(data, float(nodata)), np.nan, data)
            return data, info
        except Exception as exc:  # network hiccups: retry, then give up loudly
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(5.0 * (attempt + 1))
    raise RuntimeError(f"could not read {source}: {last_error}")


def _raster_shape(source: str) -> tuple[int, int]:
    import rasterio

    with rasterio.Env(**_VSICURL_ENV):
        with rasterio.open(source if not source.startswith("http") else "/vsicurl/" + source) as src:
            return int(src.height), int(src.width)


def _sha256(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array, dtype=np.float32).tobytes()).hexdigest()[:16]


def _stats(values: np.ndarray) -> dict:
    finite = values[np.isfinite(values)]
    return {
        "median": round(float(np.median(finite)), 4),
        "mean": round(float(finite.mean()), 4),
        "p95": round(float(np.percentile(finite, 95)), 4),
        "max": round(float(finite.max()), 4),
    }


def _fetch_sigma_maps(processed: Path, site: str, window_box: dict, force: bool, offline: bool) -> dict:
    """NASA's toterr / slperr over the window, cached as .npy."""
    out = {}
    for filename, url, label in (
        (ELEVATION_SIGMA_FILENAME, toterr_url(site), "toterr"),
        (SLOPE_SIGMA_NASA_FILENAME, slperr_url(site), "slperr"),
    ):
        path = processed / filename
        if path.exists() and not force:
            out[label] = np.load(path)
            print(f"  {label}: cached ({path.name})")
            continue
        if offline:
            out[label] = None
            print(f"  {label}: not cached and --synthetic is offline; skipped")
            continue
        t0 = time.perf_counter()
        data, _ = _read_window(url, window_box)
        np.save(path, data.astype(np.float32))
        out[label] = data
        print(f"  {label}: {url} -> {path.name} [{time.perf_counter() - t0:.0f} s]")
    return out


def _fetch_clones(
    site: str,
    indices: list[int],
    box: dict,
    workers: int,
) -> dict[int, np.ndarray]:
    """The padded windows of the requested clones, read in parallel."""
    results: dict[int, np.ndarray] = {}
    started = time.perf_counter()

    def _one(index: int) -> tuple[int, np.ndarray, float]:
        t0 = time.perf_counter()
        data, _ = _read_window(clone_url(site, index), box)
        return index, data, time.perf_counter() - t0

    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        for index, data, seconds in pool.map(_one, indices):
            results[index] = data
            elapsed = time.perf_counter() - started
            print(
                f"  clone {index:04d}: {data.shape} in {seconds:.0f} s "
                f"({len(results)}/{len(indices)}, {elapsed:.0f} s elapsed)",
                flush=True,
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--processed-dir", type=Path, default=_DEFAULT_PROCESSED)
    parser.add_argument("--site", default="Site11")
    parser.add_argument("--n-clones", type=int, default=20)
    parser.add_argument(
        "--near-range-m",
        type=float,
        default=1000.0,
        help="near-field pad around the window that is read from every clone and re-marched",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--stride", type=int, default=4, help="the planner's coarsen factor")
    parser.add_argument("--raw-dem", type=Path, default=None)
    parser.add_argument("--far-dem", type=Path, default=_DEFAULT_FAR_DEM)
    parser.add_argument("--skip-horizons", action="store_true")
    parser.add_argument("--synthetic", action="store_true", help="offline fallback; labelled synthetic")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--force", action="store_true", help="discard the existing cache")
    args = parser.parse_args()

    processed: Path = args.processed_dir
    metadata_path = processed / "metadata.json"
    elevation_path = processed / "elevation_grid.npy"
    if not metadata_path.exists() or not elevation_path.exists():
        print(f"Processed grids not found in {processed}. Run the P1 pipeline first.", file=sys.stderr)
        return 1
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    elevation = np.load(elevation_path).astype(np.float64)
    rows, cols = elevation.shape
    resolution_m = float(metadata["resolution_m"])
    offset = metadata.get("window_offset") or {}
    if not offset:
        print("metadata.json has no window_offset; the clones cannot be placed.", file=sys.stderr)
        return 1
    row_off, col_off = int(offset["row"]), int(offset["col"])

    raw_dem = _matching_raw_dem(elevation, offset, args.raw_dem)
    if raw_dem is None:
        print("No raw site DEM contains the processed window at window_offset; refusing to guess.", file=sys.stderr)
        return 1
    raster_rows, raster_cols = _raster_shape(str(raw_dem))
    if not args.synthetic:
        try:
            remote_rows, remote_cols = _raster_shape(clone_url(args.site, 1))
        except Exception as exc:
            print(f"Cannot reach NASA PGDA ({exc}); use --synthetic for the offline fallback.", file=sys.stderr)
            return 1
        if (remote_rows, remote_cols) != (raster_rows, raster_cols):
            print(
                f"{args.site} clones are {remote_rows}x{remote_cols} but the local surface DEM is "
                f"{raster_rows}x{raster_cols}; they are not the same product.",
                file=sys.stderr,
            )
            return 1

    pad = 0 if args.synthetic else int(round(args.near_range_m / resolution_m))
    box = padded_box(row_off, col_off, rows, cols, pad, raster_rows, raster_cols)
    window_box = {"row0": row_off, "col0": col_off, "rows": rows, "cols": cols}
    print(
        f"{args.site}: window {rows}x{cols} at ({row_off}, {col_off}) of {raster_rows}x{raster_cols}, "
        f"pad {pad} px ({0.0 if args.synthetic else args.near_range_m:g} m) -> box {box['rows']}x{box['cols']} at "
        f"({box['row0']}, {box['col0']}){' [pad clipped]' if box['pad_clipped'] else ''}"
    )

    # ── NASA's sigma maps ──────────────────────────────────────────────────
    print("Sigma maps:")
    sigma = _fetch_sigma_maps(processed, args.site, window_box, args.force, args.synthetic)
    toterr = sigma["toterr"]
    if toterr is None:
        print("toterr is required (the synthetic fallback will not invent an error magnitude).", file=sys.stderr)
        return 1

    # ── The clones ─────────────────────────────────────────────────────────
    existing = None if args.force else load_dem_clones(str(processed))
    if existing is not None:
        same = (
            existing.meta.get("site") == args.site
            and existing.meta.get("window") == box["window"]
            and tuple(existing.elevation.shape[1:]) == (box["rows"], box["cols"])
            and existing.meta.get("provenance") == ("synthetic" if args.synthetic else "nasa_pgda_clones")
        )
        if not same:
            print("Existing clone cache was built for a different window/pad/provenance; rebuilding it.")
            existing = None
    # Copied out of the memmap and the memmap dropped: on Windows an open
    # memmap locks the file this script is about to rewrite.
    have = {} if existing is None else {i: np.array(existing.elevation[k]) for k, i in enumerate(existing.clone_indices)}
    have_meta = {} if existing is None else {c["index"]: c for c in existing.meta.get("clones", [])}
    existing_meta_full = None if existing is None else dict(existing.meta)
    del existing
    wanted = list(range(1, int(args.n_clones) + 1))
    missing = [i for i in wanted if i not in have]
    fetch_seconds = 0.0
    if missing:
        print(f"Clones: {len(have)} cached, fetching {len(missing)} with {args.workers} workers")
        t0 = time.perf_counter()
        if args.synthetic:
            stack = synthetic_clones(elevation, toterr, len(missing), args.seed)
            fetched = {index: stack[k] for k, index in enumerate(missing)}
        else:
            fetched = _fetch_clones(args.site, missing, box, args.workers)
        fetch_seconds = time.perf_counter() - t0
        w = box["window"]
        for index in missing:
            window = fetched[index][w["row0"] : w["row0"] + rows, w["col0"] : w["col0"] + cols]
            check = clone_check(window, elevation, toterr)
            if not check["ok"]:
                print(
                    f"Clone {index:04d} failed the window check {check}; not a clone of this window. "
                    "Nothing written.",
                    file=sys.stderr,
                )
                return 1
            have[index] = fetched[index]
            have_meta[index] = {
                "index": index,
                "url": None if args.synthetic else clone_url(args.site, index),
                "check": check,
                "sha256_16": _sha256(fetched[index]),
            }
    else:
        print(f"Clones: all {len(wanted)} cached")

    indices = sorted(i for i in have if i in wanted)
    stack = np.stack([np.asarray(have[i], dtype=np.float32) for i in indices])
    w = box["window"]
    if not missing and existing_meta_full is not None and existing_meta_full.get("clone_indices") == indices:
        print(f"Clone cache unchanged ({len(indices)} clones); not rewritten")
        clones_meta = existing_meta_full
        if args.skip_horizons or args.synthetic:
            return 0
        return _build_horizons(args, processed, metadata, elevation, raw_dem, box, stack, indices, toterr)
    errors = stack[:, w["row0"] : w["row0"] + rows, w["col0"] : w["col0"] + cols].astype(np.float64) - elevation[None]
    clones_meta = {
        "site": args.site,
        "product_url": PGDA_PRODUCT_URL,
        "reference": PGDA_REFERENCE,
        "provenance": "synthetic" if args.synthetic else "nasa_pgda_clones",
        "clone_kind": "full surface DEM (surface + error realisation); error = clone - surface",
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "surface_dem": raw_dem.name,
        "raster_shape": [raster_rows, raster_cols],
        "resolution_m": resolution_m,
        "window_offset": {"row": row_off, "col": col_off},
        "near_range_m": float(args.near_range_m) if not args.synthetic else 0.0,
        "pad_px": pad,
        "pad_clipped": box["pad_clipped"],
        "box": {k: box[k] for k in ("row0", "col0", "rows", "cols")},
        "window": box["window"],
        "clone_indices": indices,
        "clones": [have_meta[i] for i in indices],
        "sigma": {
            "toterr_url": toterr_url(args.site),
            "slperr_url": slperr_url(args.site),
            "toterr_m": _stats(toterr),
            "slperr_deg": None if sigma["slperr"] is None else _stats(sigma["slperr"]),
        },
        "error_across_clones": {
            "mean_m": round(float(np.nanmean(errors)), 4),
            "rms_m": round(float(np.sqrt(np.nanmean(errors**2))), 4),
            "rms_toterr_m": round(float(np.sqrt(np.nanmean(toterr.astype(np.float64) ** 2))), 4),
        },
        "fetch_seconds": round(fetch_seconds, 1),
        "workers": int(args.workers),
    }
    if args.synthetic:
        clones_meta["synthetic"] = {
            "recipe": "surface + toterr * xi, xi = gaussian_filter(white noise, 2 cells) / std",
            "seed": int(args.seed),
        }
    write_dem_clones(str(processed), stack, clones_meta)
    print(
        f"Wrote {processed / 'dem_clones.npy'} ({stack.nbytes / 2**20:.0f} MiB, {len(indices)} clones); "
        f"error across clones mean {clones_meta['error_across_clones']['mean_m']:+.3f} m, "
        f"RMS {clones_meta['error_across_clones']['rms_m']:.3f} m vs toterr RMS "
        f"{clones_meta['error_across_clones']['rms_toterr_m']:.3f} m"
    )

    if args.skip_horizons or args.synthetic:
        print("Horizons skipped" + (" (synthetic clones carry no context)." if args.synthetic else "."))
        return 0
    return _build_horizons(args, processed, metadata, elevation, raw_dem, box, stack, indices, toterr)


def _build_horizons(args, processed, metadata, elevation, raw_dem, box, stack, indices, toterr) -> int:
    """Per-clone horizon cubes at the planner's block centres."""
    rows, cols = elevation.shape
    resolution_m = float(metadata["resolution_m"])
    stride = int(args.stride)
    if rows % stride or cols % stride:
        print(f"grid {rows}x{cols} is not divisible by stride {stride}", file=sys.stderr)
        return 1
    centre = stride // 2
    base_meta_path = processed / HORIZON_META_FILENAME
    base_meta = json.loads(base_meta_path.read_text(encoding="utf-8")) if base_meta_path.exists() else {}
    n_azimuth = int(base_meta.get("n_azimuth", 72))
    max_range_m = float((base_meta.get("fine") or {}).get("max_range_m", 10000.0))
    far_meta = base_meta.get("far") or {}
    near_steps, far_steps = near_far_steps(resolution_m, args.near_range_m, max_range_m, 200)
    print(
        f"Horizons: stride {stride} (offset {centre}), {n_azimuth} azimuths, near {near_steps.size} samples "
        f"<= {args.near_range_m:g} m, far {far_steps.size} samples to {max_range_m:g} m"
    )

    import rasterio
    from rasterio.windows import Window

    # The production cube's context: the window padded by the full fine
    # range, clipped at the raster. Every pass below -- the far pass on the
    # surface and the NEAR pass on every clone -- addresses cells in THIS
    # frame. The near pass could run on the padded clone alone, but the ray
    # marcher rounds sample positions with np.rint, and a .5 tie breaks
    # differently at index 203.5 than at 2003.5 (the excess a float carries
    # at small magnitudes is lost at large ones): measured, 0.1 percent of
    # (azimuth, cell) pairs moved by up to 0.27 deg. Embedding the padded
    # clone in a NaN canvas with the context's indexing reproduces the
    # production cube exactly (max difference 0).
    row_off = box["row0"] + box["window"]["row0"]
    col_off = box["col0"] + box["window"]["col0"]
    pad_ctx = int(round(max_range_m / resolution_m))
    with rasterio.open(raw_dem) as src:
        raster_rows, raster_cols = src.height, src.width
    r0, c0 = max(0, row_off - pad_ctx), max(0, col_off - pad_ctx)
    r1, c1 = min(raster_rows, row_off + rows + pad_ctx), min(raster_cols, col_off + cols + pad_ctx)
    roi = (row_off - r0 + centre, row_off - r0 + rows, col_off - c0 + centre, col_off - c0 + cols)

    def _canvas(padded: np.ndarray) -> np.ndarray:
        canvas = np.full((r1 - r0, c1 - c0), np.nan)
        canvas[box["row0"] - r0 : box["row0"] - r0 + box["rows"], box["col0"] - c0 : box["col0"] - c0 + box["cols"]] = padded
        return canvas

    # ── The shared far field, once, on the surface ─────────────────────────
    far_path = processed / SURF_HORIZON_FAR_FILENAME
    existing_cubes, existing_meta = load_clone_horizons(str(processed))
    reuse = (
        not args.force
        and existing_cubes is not None
        and far_path.exists()
        and existing_meta.get("stride") == stride
        and float(existing_meta.get("near_range_m", -1)) == float(args.near_range_m)
        and existing_meta.get("n_azimuth") == n_azimuth
    )
    if reuse:
        far_cube = np.load(far_path)
        surf_check = existing_meta.get("surf_check_max_abs_deg")
        far_info = existing_meta.get("far", {})
        print(f"  far field: cached ({far_path.name})")
    cached = {}
    if reuse:
        cached = {i: np.array(existing_cubes[k]) for k, i in enumerate(existing_meta.get("clone_indices", []))}
    del existing_cubes  # a memmap would lock the file about to be rewritten
    if reuse and set(indices) <= set(cached):
        print("  clone horizons: all cached; nothing to do")
        return 0
    if not reuse:
        t0 = time.perf_counter()
        with rasterio.open(raw_dem) as src:
            context = src.read(1, window=Window(c0, r0, c1 - c0, r1 - r0)).astype(np.float64)
            context = np.where(context < -1e6, np.nan, context)
            if src.nodata is not None and np.isfinite(src.nodata):
                context = np.where(np.isclose(context, float(src.nodata)), np.nan, context)
        far_surface = horizon_map(
            context, resolution_m, n_azimuth=n_azimuth, roi=roi, stride=stride, steps_cells=far_steps
        )
        far_info = {"surface_context": str(raw_dem), "max_range_m": max_range_m, "lola": {"used": False}}
        if args.far_dem is not None and Path(args.far_dem).exists() and far_meta.get("used", True):
            lola, lola_info = far_field_horizon(
                Path(args.far_dem),
                elevation,
                metadata,
                n_azimuth=n_azimuth,
                min_range_m=float(far_meta.get("min_range_m", max_range_m)),
                max_range_m=float(far_meta.get("max_range_m", 150000.0)),
                max_steps=int(far_meta.get("max_steps", 400)),
            )
            far_surface = np.maximum(far_surface, lola[:, centre::stride, centre::stride])
            far_info["lola"] = {"used": True, **lola_info}
        far_cube = far_surface.astype(np.float32)
        np.save(far_path, far_cube)
        far_seconds = time.perf_counter() - t0
        print(f"  far field: {far_cube.shape} in {far_seconds:.0f} s -> {far_path.name}")

        # ── The surface's own near field: max(near, far) must BE the production cube
        with rasterio.open(raw_dem) as src:
            surf_padded = src.read(
                1, window=Window(box["col0"], box["row0"], box["cols"], box["rows"])
            ).astype(np.float64)
            surf_padded = np.where(surf_padded < -1e6, np.nan, surf_padded)
        near_surf = horizon_map(
            _canvas(surf_padded), resolution_m, n_azimuth=n_azimuth, roi=roi, stride=stride, steps_cells=near_steps
        )
        surf_cube = np.maximum(near_surf, far_cube)
        base_path = processed / HORIZON_CACHE_FILENAME
        surf_check = None
        if base_path.exists():
            base = np.load(base_path, mmap_mode="r")
            if base.shape[0] == n_azimuth:
                sampled = np.asarray(base[:, centre::stride, centre::stride], dtype=np.float32)
                surf_check = float(np.max(np.abs(surf_cube - sampled)))
                print(f"  surface check: max |max(near, far) - production cube| = {surf_check:.2e} deg")
                if surf_check > 1e-3:
                    print(
                        "  The surface's two-pass horizon does not reproduce the production cube; "
                        "the clone cubes would not be comparable. Rebuild horizon_map.npy with "
                        "scripts/build_horizon_cache.py (same range/azimuths) and retry.",
                        file=sys.stderr,
                    )
                    return 1
        else:
            print(f"  no {HORIZON_CACHE_FILENAME} to check against; continuing")

    # ── Per clone ──────────────────────────────────────────────────────────
    cubes = []
    per_clone_s = []
    for k, index in enumerate(indices):
        if index in cached:
            cubes.append(np.asarray(cached[index], dtype=np.float32))
            continue
        t0 = time.perf_counter()
        near = horizon_map(
            _canvas(stack[k].astype(np.float64)), resolution_m, n_azimuth=n_azimuth, roi=roi, stride=stride, steps_cells=near_steps
        )
        cubes.append(np.maximum(near, far_cube).astype(np.float32))
        per_clone_s.append(time.perf_counter() - t0)
        print(f"  clone {index:04d}: horizon {cubes[-1].shape} in {per_clone_s[-1]:.1f} s", flush=True)
    stack_cubes = np.stack(cubes)
    finite_toterr = toterr[np.isfinite(toterr)]
    horizons_meta = {
        "stride": stride,
        "row_offset": centre,
        "col_offset": centre,
        "n_azimuth": n_azimuth,
        "near_range_m": float(args.near_range_m),
        "near_samples": int(near_steps.size),
        "far_samples": int(far_steps.size),
        "max_range_m": max_range_m,
        "far": far_info,
        "far_field_held_fixed": True,
        "neglected_horizon_shift_deg_max": round(
            float(np.degrees(np.median(finite_toterr) / float(args.near_range_m))), 4
        ),
        "surf_check_max_abs_deg": surf_check,
        "clone_indices": indices,
        "seconds_per_clone": round(float(np.mean(per_clone_s)), 2) if per_clone_s else existing_meta.get("seconds_per_clone"),
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    write_clone_horizons(str(processed), stack_cubes, horizons_meta)
    print(
        f"Wrote {processed / 'dem_clone_horizons.npy'} ({stack_cubes.nbytes / 2**20:.0f} MiB, "
        f"{stack_cubes.shape}); neglected far-field shift <= "
        f"{horizons_meta['neglected_horizon_shift_deg_max']:.4f} deg"
    )
    print(f"Wrote {processed / CLONE_HORIZONS_META_FILENAME} and {processed / DEM_CLONES_META_FILENAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
