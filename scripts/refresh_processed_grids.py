#!/usr/bin/env python3
"""Bring the shipped .npy grids back in sync with the current cost model.

The artefacts in ``lunapath/data/processed/`` drift from the code every time
a penalty formula, a traversability rule or a layer's DEFINITION changes,
because regenerating them normally means re-running the whole P1 pipeline --
which rebuilds the heat1d lookup table (12-15 minutes) and re-selects the
window. This script recomputes everything derivable from the layers already
on disk and leaves the expensive, unchanged ones alone.

Round 4 makes two changes it can apply in place:

* ``thermal_grid.npy`` now stores the UNCORRECTED sunlit peak, stamped
  ``thermal_field: "sunlit_peak"``. Round 3 stored a shadow-corrected field
  under the same name, which gave a consumer wanting a different
  illumination -- the 4-D cost cube, one slice at a time -- no way back, so
  it corrected again and produced a map 37 C colder than the 2-D planner's
  for the same terrain. The stored field is inverted once, here, where the
  metadata still says what was done to it. (H-1.)

* ``--rebuild-shadow`` recomputes ``shadow_ratio_grid.npy`` with the fixed
  horizon: marched to its full range, and over the terrain SURROUNDING the
  planning window rather than the 2.5 km crop. Needs the raw DEM and the
  NAIF kernels. (H-4.)

Usage:
    python scripts/refresh_processed_grids.py
    python scripts/refresh_processed_grids.py --rebuild-shadow
    python scripts/refresh_processed_grids.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "backend"))

import numpy as np  # noqa: E402

from app.constants import DEFAULT_ROVER_ID, get_rover  # noqa: E402
from app.cost_engine import (  # noqa: E402
    COST_MODEL_ID,
    compute_cost_grid,
    resolve_weights,
)
from app.data_loader import (  # noqa: E402
    THERMAL_FIELD_SUNLIT_PEAK,
    derive_thermal_fields,
)
from app.thermal_model import sunlit_peak_from_equilibrium_c  # noqa: E402
from app.traversability import (  # noqa: E402
    compute_traversability_bool,
    weakest_validity,
)

_DEFAULT_PROCESSED = _ROOT / "lunapath" / "data" / "processed"
_DEFAULT_RAW_DEM = _ROOT / "lunapath" / "data" / "raw" / "Site11_final_adj_5mpp_surf.tif"

# Same sun track the P1 pipeline samples, so a rebuilt shadow layer is
# comparable with the one it replaces.
SUN_TRACK_START_UTC = "2026-11-15T00:00:00"
SUN_TRACK_END_UTC = "2026-12-13T00:00:00"
SUN_TRACK_SAMPLES = 168
HORIZON_N_AZIMUTH = 72
HORIZON_MAX_RANGE_M = 10000.0
HORIZON_MAX_STEPS = 200


def rebuild_shadow_ratio(
    metadata: dict, dem_path: Path, shape: tuple[int, int]
) -> np.ndarray:
    """Recompute shadow_ratio from the DEM, with the window's real context.

    Two things were wrong with the shipped layer, and only the second is
    visible in its own output. First, ``horizon_map``'s step cap truncated
    the search to 1 km at 5 m/px against a nominal 10 km. Second -- and
    larger -- the horizon was computed from the 2.5 km planning crop alone,
    so every ray left the DEM within a few hundred metres of the crop edge
    and reported no obstruction, which is a different statement from "no
    obstruction exists". The raw DEM is 16 km across. (Round 4 review, H-4.)
    """
    import rasterio
    from rasterio.windows import Window

    from app.ephemeris import (
        sun_track,
        true_azimuth_to_grid_azimuth,
        true_north_grid_azimuth,
    )
    from app.horizon import horizon_map
    from app.illumination import illumination_fraction, shadow_ratio_from_illumination
    from app.serializer import pixel_to_lonlat

    offset = metadata.get("window_offset") or {}
    row_off = int(offset.get("row", 0))
    col_off = int(offset.get("col", 0))
    resolution_m = float(metadata["resolution_m"])
    rows, cols = shape

    with rasterio.open(dem_path) as src:
        pad = int(round(HORIZON_MAX_RANGE_M / resolution_m))
        r0 = max(0, row_off - pad)
        c0 = max(0, col_off - pad)
        r1 = min(src.height, row_off + rows + pad)
        c1 = min(src.width, col_off + cols + pad)
        context = src.read(
            1, window=Window(c0, r0, c1 - c0, r1 - r0)
        ).astype(np.float64)
        context = np.where(context < -1e6, np.nan, context)
        if src.nodata is not None and np.isfinite(src.nodata):
            context = np.where(
                np.isclose(context, float(src.nodata)), np.nan, context
            )
        crs_wkt = src.crs.to_wkt()

    roi = (row_off - r0, row_off - r0 + rows, col_off - c0, col_off - c0 + cols)
    print(
        f"  horizon context {context.shape} at {resolution_m:g} m/px, "
        f"ROI {roi}, range {HORIZON_MAX_RANGE_M:g} m"
    )

    lon, lat = pixel_to_lonlat(rows // 2, cols // 2, metadata)
    samples = sun_track(
        SUN_TRACK_START_UTC, SUN_TRACK_END_UTC, SUN_TRACK_SAMPLES, lat, lon
    )
    grid_north = true_north_grid_azimuth(lat, lon, crs_wkt)
    grid_samples = [
        (true_azimuth_to_grid_azimuth(az, grid_north), elev) for az, elev in samples
    ]

    horizon = horizon_map(
        context,
        resolution_m,
        n_azimuth=HORIZON_N_AZIMUTH,
        max_range_m=HORIZON_MAX_RANGE_M,
        max_steps=HORIZON_MAX_STEPS,
        roi=roi,
        progress=True,
    )
    fraction = illumination_fraction(horizon, grid_samples)
    return shadow_ratio_from_illumination(fraction).astype(np.float64)


def _describe(name: str, arr: np.ndarray, unit: str = "") -> None:
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        print(f"  {name:22s} all non-finite")
        return
    print(
        f"  {name:22s} [{finite.min():8.3f}, {finite.max():8.3f}]{unit}  "
        f"mean {finite.mean():8.3f}  std {finite.std():.4f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=_DEFAULT_PROCESSED)
    parser.add_argument("--raw-dem", type=Path, default=_DEFAULT_RAW_DEM)
    parser.add_argument(
        "--rebuild-shadow",
        action="store_true",
        help="recompute shadow_ratio_grid.npy from the DEM with the fixed horizon",
    )
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
    stored_thermal = load("thermal_grid")
    shadow = load("shadow_ratio_grid")
    old_traversable = np.load(processed / "traversability_grid.npy")

    thermal_validity = str(validity.get("thermal", "UNKNOWN"))
    shadow_validity = str(validity.get("shadow_ratio", "UNKNOWN"))

    # ── the stored thermal field becomes the sunlit peak, once ─────────────
    stored_field = metadata.get("thermal_field")
    if stored_field == THERMAL_FIELD_SUNLIT_PEAK:
        print("thermal_grid already stores the sunlit peak; leaving it alone")
        sunlit_peak = stored_thermal
    else:
        sunlit_peak = np.asarray(
            sunlit_peak_from_equilibrium_c(stored_thermal, shadow), dtype=np.float64
        )
        print("thermal_grid: shadow-corrected field -> sunlit peak")
        _describe("  stored (corrected)", stored_thermal, " C")
        _describe("  recovered (sunlit)", sunlit_peak, " C")

    # ── the shadow layer, optionally rebuilt with the fixed horizon ────────
    if args.rebuild_shadow:
        if not args.raw_dem.exists():
            print(f"raw DEM not found: {args.raw_dem}", file=sys.stderr)
            return 1
        print("\nrebuilding shadow_ratio from the DEM with the window's context")
        before = shadow
        shape = (int(metadata["shape"][0]), int(metadata["shape"][1]))
        shadow = rebuild_shadow_ratio(metadata, args.raw_dem, shape)
        _describe("  before", before)
        _describe("  after", shadow)
        print(
            f"  fully dark cells: {int((before >= 0.999).sum())} -> "
            f"{int((shadow >= 0.999).sum())}"
        )
        shadow_validity = "DERIVED"

    # ── everything else follows ───────────────────────────────────────────
    thermal_peak, thermal_min = derive_thermal_fields(sunlit_peak, shadow)
    thermal_validity = weakest_validity(thermal_validity, shadow_validity)
    print("\nderived thermal statistics")
    _describe("  annual peak", thermal_peak, " C")
    _describe("  cold-end equilibrium", thermal_min, " C")

    rover_id = str(metadata.get("default_rover_id", DEFAULT_ROVER_ID))
    rover = get_rover(rover_id)
    weights = resolve_weights(metadata.get("cost_weights"), rover)

    traversable = compute_traversability_bool(
        slope, thermal_peak, elevation, rover=rover, thermal_min=thermal_min
    )
    changed = int(np.count_nonzero(traversable != old_traversable.astype(bool)))
    print(
        f"\ntraversability for {rover_id}: {int(traversable.sum())} passable "
        f"({100.0 * traversable.mean():.1f}%), {changed} cells differ from disk"
    )

    cost = compute_cost_grid(
        slope,
        thermal_peak,
        shadow,
        float(metadata["resolution_m"]),
        traversable=traversable,
        weights=weights,
        rover=rover,
        thermal_min_grid=thermal_min,
    )
    _describe("cost", cost)

    metadata["cost_model"] = COST_MODEL_ID
    metadata["cost_weights"] = weights
    metadata["thermal_field"] = THERMAL_FIELD_SUNLIT_PEAK
    metadata["thermal_shadow_coupled"] = True  # legacy alias
    validity["thermal"] = thermal_validity
    validity["thermal_min"] = thermal_validity
    validity["shadow_ratio"] = shadow_validity
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

    np.save(processed / "thermal_grid.npy", sunlit_peak)
    np.save(processed / "shadow_ratio_grid.npy", shadow)
    np.save(processed / "traversability_grid.npy", traversable.astype(np.float64))
    np.save(processed / "cost_grid.npy", cost)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        "\nwrote thermal_grid (sunlit peak), shadow_ratio_grid, "
        "traversability_grid, cost_grid and metadata.json"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
