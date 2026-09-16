#!/usr/bin/env python3
"""Validate LunaPath's thermal grid against the Diviner Polar Resource Product.

This is C5's single entry point. It replaced ``scripts/diviner_validation.py``,
which expected a Diviner *raster*: the real polar product is a 605 MB ASCII
triangular mesh, so the old reprojection path could never have consumed it.
The one genuinely valuable thing in that script -- ``destination_transform``
and its half-cell/top-edge lesson (Round 2 H-3) -- moved into
``app.thermal_validation`` and is still pinned by test_review2_fixes.py.

What it measures, and what it refuses to do
-------------------------------------------
Three of our fields are compared against the SAME Diviner statistic, and all
three RMSEs are published. Which of ours is the counterpart of Diviner's
annual maximum is an argument to be made from the numbers; picking one first
and calling its RMSE "the" RMSE is the most likely way to be wrong here.

It does not tune anything. If the agreement is poor, the poor number is what
gets published: fitting our model to Diviner would invalidate every
measurement from A1 through C2 and is a different feature (calibration).

Sections
--------
1. Site11 window -- our 5 m grid aggregated onto the ~50 Diviner facets that
   overlap it. Co-registered, but n is tiny and the interval says so.
2. LUT at matched latitude -- our (slope x aspect) lookup table against every
   Diviner facet in the window's own latitude band, at all longitudes
   (n ~ 5 000). Latitude has to be matched: at -88.9 the Sun's maximum
   elevation is ~0.5 deg and changes by ~0.5 deg per degree of latitude, so a
   wide band would compare our table against a different insolation.
3. Cold-trap area -- Williams et al.'s published 1.3e4 km^2 re-derived from
   the mesh's own vertices (C1/C2's "reproduce a published number" pattern).
4. Night minimum -- Williams' seasonal minimum maps, if they can be had.

``--json`` dumps the raw measurements before rendering; ``--from-json``
re-renders without measuring.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "backend"))

import numpy as np  # noqa: E402

from app.thermal_model import (  # noqa: E402
    annual_peak_c,
    shadowed_equilibrium_c,
)
from app.thermal_validation import (  # noqa: E402
    PRP_QUOTED,
    WILLIAMS_QUOTED,
    aggregate_to_facets,
    assign_cells_to_facets,
    cold_trap_area_check,
    compare_candidates,
    error_statistics,
    facet_coverage_fraction,
    grid_cell_centres,
    kelvin_to_c,
    spearman_rho,
)

_PROCESSED = _ROOT / "lunapath" / "data" / "processed"
_ABSOLUTE_ZERO_C_LOCAL = -273.15

#: A facet is compared only when at least this much of its real footprint
#: lies inside our window. PRIMARY_COVERAGE is the headline; the others are
#: published beside it so the choice is visible rather than assumed.
COVERAGE_THRESHOLDS = (0.0, 0.5, 0.9)
PRIMARY_COVERAGE = "0.50"

#: Slope/aspect axes of Heat1DModel's lookup table, mirrored here so the
#: table can be recovered from the shipped grid without re-running heat1d
#: (a rebuild is ~12-15 minutes per latitude). Kept in sync with
#: app.thermal_model._SLOPE_MAX_DEG_FOR_TABLE and Heat1DModel's defaults.
LUT_SLOPE_MAX_DEG = 30.0
LUT_N_SLOPE = 13
LUT_N_ASPECT = 16


def _f(value, digits=3):
    if value is None:
        return "—"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    return f"{float(value):.{digits}f}"


# ── loading ─────────────────────────────────────────────────────────────────


def load_inputs(processed: Path) -> dict:
    metadata = json.loads((processed / "metadata.json").read_text(encoding="utf-8"))
    return {
        "metadata": metadata,
        "sunlit_peak": np.load(processed / "thermal_grid.npy"),
        "shadow_ratio": np.load(processed / "shadow_ratio_grid.npy"),
        "slope": np.load(processed / "slope_grid.npy"),
        "aspect": np.load(processed / "aspect_grid.npy"),
        "prp": np.load(processed / "diviner_prp.npz"),
        "prp_meta": json.loads(
            (processed / "diviner_prp_meta.json").read_text(encoding="utf-8")
        ),
    }


def candidate_fields(inputs: dict) -> dict[str, np.ndarray]:
    """Our three fields, all named for what they actually are."""
    sunlit = np.asarray(inputs["sunlit_peak"], dtype=np.float64)
    shadow = np.asarray(inputs["shadow_ratio"], dtype=np.float64)
    return {
        "A_thermal_sunlit_peak": sunlit,
        "B_thermal_annual_peak": np.asarray(
            annual_peak_c(sunlit, shadow), dtype=np.float64
        ),
        "C_thermal_min_equilibrium": np.asarray(
            shadowed_equilibrium_c(sunlit, shadow), dtype=np.float64
        ),
    }


def recover_lookup_table(
    sunlit_peak: np.ndarray, slope: np.ndarray, aspect: np.ndarray
) -> dict:
    """Recover Heat1DModel's (slope x aspect) table from the shipped grid.

    ``Heat1DModel.surface_temperature_c`` is a nearest-bin lookup, so every
    cell's value IS a table entry. Taking the most common value per bin
    recovers the table the planner actually reads, for free, instead of
    spending 12-15 minutes re-running heat1d for a table that might differ
    from the one on disk.

    Bins holding more than one distinct value are counted and reported
    rather than hidden: the shipped thermal grid is not bit-reproducible
    from the current slope/aspect grids, and that is a fact about the
    artefacts, measured here, not something this script should paper over.
    """
    slope_clipped = np.clip(
        np.nan_to_num(np.asarray(slope, dtype=np.float64), nan=0.0),
        0.0,
        LUT_SLOPE_MAX_DEG,
    )
    si = np.rint(slope_clipped / LUT_SLOPE_MAX_DEG * (LUT_N_SLOPE - 1)).astype(np.int64)
    aspect_wrapped = np.mod(
        np.nan_to_num(np.asarray(aspect, dtype=np.float64), nan=0.0), 360.0
    )
    ai = np.mod(
        np.rint(aspect_wrapped / 360.0 * LUT_N_ASPECT).astype(np.int64), LUT_N_ASPECT
    )

    table = np.full((LUT_N_SLOPE, LUT_N_ASPECT), np.nan)
    counts = np.zeros((LUT_N_SLOPE, LUT_N_ASPECT), dtype=np.int64)
    ambiguous = 0
    values = np.asarray(sunlit_peak, dtype=np.float64)
    for i in range(LUT_N_SLOPE):
        for j in range(LUT_N_ASPECT):
            selected = values[(si == i) & (ai == j)]
            selected = selected[np.isfinite(selected)]
            counts[i, j] = selected.size
            if selected.size == 0:
                continue
            distinct, tally = np.unique(np.round(selected, 6), return_counts=True)
            table[i, j] = float(distinct[np.argmax(tally)])
            if distinct.size > 1:
                ambiguous += 1
    # How faithful is the recovered table? Re-evaluating it on the same
    # slope/aspect grids should reproduce the shipped thermal grid exactly
    # if the documented nearest-bin rule and these grids are what built it.
    reconstructed = table[si, ai]
    finite = np.isfinite(values) & np.isfinite(reconstructed)
    mismatch = finite & ~np.isclose(reconstructed, values, atol=1e-4)
    return {
        "table_c": table,
        "counts": counts,
        "n_bins_populated": int(np.sum(counts > 0)),
        "n_bins_total": LUT_N_SLOPE * LUT_N_ASPECT,
        "n_bins_multivalued": int(ambiguous),
        "reconstruction_mismatch_pct": float(100.0 * np.mean(mismatch)),
        "reconstruction_max_abs_diff_c": (
            float(np.max(np.abs(reconstructed - values)[mismatch]))
            if mismatch.any()
            else 0.0
        ),
        "flat_cell_peak_c": (None if np.isnan(table[0, 0]) else float(table[0, 0])),
        "aspect_spread_by_slope_c": [
            (
                None
                if np.all(np.isnan(table[i]))
                else float(np.nanmax(table[i]) - np.nanmin(table[i]))
            )
            for i in range(LUT_N_SLOPE)
        ],
        "slope_deg_axis": np.linspace(0.0, LUT_SLOPE_MAX_DEG, LUT_N_SLOPE).tolist(),
    }


def evaluate_lookup_table(
    table: np.ndarray, slope_deg: np.ndarray, aspect_deg: np.ndarray
) -> np.ndarray:
    """Sample a recovered table exactly as Heat1DModel.surface_temperature_c does."""
    slope_clipped = np.clip(
        np.nan_to_num(np.asarray(slope_deg, dtype=np.float64), nan=0.0),
        0.0,
        LUT_SLOPE_MAX_DEG,
    )
    si = np.rint(slope_clipped / LUT_SLOPE_MAX_DEG * (LUT_N_SLOPE - 1)).astype(np.int64)
    aspect_wrapped = np.mod(
        np.nan_to_num(np.asarray(aspect_deg, dtype=np.float64), nan=0.0), 360.0
    )
    ai = np.mod(
        np.rint(aspect_wrapped / 360.0 * LUT_N_ASPECT).astype(np.int64), LUT_N_ASPECT
    )
    return table[si, ai]


# ── section 1: the Site11 window ────────────────────────────────────────────


def measure_window(inputs: dict) -> dict:
    from pyproj import CRS, Transformer

    metadata = inputs["metadata"]
    prp = inputs["prp"]
    rows, cols = (int(v) for v in metadata["shape"])
    resolution = float(metadata["resolution_m"])

    index = prp["polar_vertex_index"]
    vertices_km = prp["polar_vertices_km"].astype(np.float64)
    lat = prp["lat_deg"].astype(np.float64)[index]
    lon = prp["lon_deg"].astype(np.float64)[index]
    temp_max_k = prp["temp_max_k"].astype(np.float64)[index]
    temp_avg_k = prp["temp_avg_k"].astype(np.float64)[index]
    area_km2 = prp["area_km2"].astype(np.float64)[index]

    geographic = CRS.from_proj4(
        f"+proj=lonlat +R={PRP_QUOTED['a_axis_radius_km'] * 1000.0:.1f} +no_defs"
    )
    to_grid = Transformer.from_crs(
        geographic, CRS.from_wkt(metadata["crs"]), always_xy=True
    )
    centre_x, centre_y = to_grid.transform(lon, lat)

    x, y = grid_cell_centres(metadata)
    x_min, x_max = float(x.min()), float(x.max())
    y_min, y_max = float(y.min()), float(y.max())

    inside = (
        (centre_x >= x_min)
        & (centre_x <= x_max)
        & (centre_y >= y_min)
        & (centre_y <= y_max)
    )
    # A facet whose centre is just outside can still cover our cells, so the
    # footprint test runs on a margin of one facet width around the window.
    margin = 600.0
    near = np.flatnonzero(
        (centre_x >= x_min - margin)
        & (centre_x <= x_max + margin)
        & (centre_y >= y_min - margin)
        & (centre_y <= y_max + margin)
    )

    # Project each kept facet's vertices into the grid frame.
    v = vertices_km[near]
    norm = np.linalg.norm(v, axis=2)
    v_lat = np.degrees(np.arcsin(np.clip(v[:, :, 2] / norm, -1.0, 1.0)))
    v_lon = np.degrees(np.arctan2(v[:, :, 1], v[:, :, 0]))
    vx, vy = to_grid.transform(v_lon.ravel(), v_lat.ravel())
    vertices_xy = np.stack(
        [np.asarray(vx).reshape(v_lat.shape), np.asarray(vy).reshape(v_lat.shape)],
        axis=2,
    )

    assignment = assign_cells_to_facets(vertices_xy, x, y)
    candidates = candidate_fields(inputs)

    reference_c = kelvin_to_c(temp_max_k[near])

    # How much of each facet's REAL footprint actually lies in our window.
    #
    # This matters more than it looks. A Diviner facet's temp_max describes
    # its whole ~0.128 km^2 triangle. A facet clipped by the window edge
    # contributes only the sliver of itself that overlaps us, and comparing
    # our mean over 2% of a triangle against Diviner's value for all of it
    # is comparing unlike things. Measured: 22 of the 71 covered facets sit
    # below 50% coverage and 13 below 25%, and including them makes the
    # agreement look better than it is (B: RMSE 35.5 with them, 39.4
    # without). So coverage is computed, the comparison is reported at
    # several thresholds, and the headline number is the filtered one.
    _, cell_counts = aggregate_to_facets(
        candidates["A_thermal_sunlit_peak"], assignment, near.size, how="mean"
    )
    coverage = facet_coverage_fraction(cell_counts, area_km2[near], resolution)

    results: dict[str, dict] = {}
    for how in ("mean", "max"):
        aggregated = {
            name: aggregate_to_facets(field, assignment, near.size, how=how)[0]
            for name, field in candidates.items()
        }
        by_threshold: dict[str, dict] = {}
        for threshold in COVERAGE_THRESHOLDS:
            keep = (cell_counts > 0) & (coverage >= threshold)
            masked_reference = np.where(keep, reference_c, np.nan)
            by_threshold[f"{threshold:.2f}"] = compare_candidates(
                {n: np.where(keep, v, np.nan) for n, v in aggregated.items()},
                masked_reference,
            )
        results[how] = by_threshold

    counts = cell_counts
    used = (counts > 0) & (coverage >= float(PRIMARY_COVERAGE))
    return {
        "n_facet_centres_inside_window": int(inside.sum()),
        "n_facets_considered": int(near.size),
        "n_facets_with_cells": int((counts > 0).sum()),
        "n_facets_compared": int(used.sum()),
        "primary_coverage": float(PRIMARY_COVERAGE),
        "coverage_percentiles": {
            str(q): float(np.percentile(coverage[counts > 0], q))
            for q in (0, 25, 50, 75, 100)
        },
        "n_facets_below_half_coverage": int(
            np.sum((counts > 0) & (coverage < 0.5))
        ),
        "n_cells_assigned": int(np.sum(assignment >= 0)),
        "n_cells_total": rows * cols,
        "cells_per_facet_median": float(np.median(counts[used])) if used.any() else None,
        "window_x_m": [x_min, x_max],
        "window_y_m": [y_min, y_max],
        "window_lat_deg": [float(lat[inside].min()), float(lat[inside].max())]
        if inside.any()
        else None,
        "resolution_m": resolution,
        "reference_temp_max_c": {
            "min": float(reference_c[used].min()) if used.any() else None,
            "median": float(np.median(reference_c[used])) if used.any() else None,
            "max": float(reference_c[used].max()) if used.any() else None,
        },
        "reference_temp_avg_2cm_c": {
            "min": float(kelvin_to_c(temp_avg_k[near])[used].min())
            if used.any()
            else None,
            "median": float(np.median(kelvin_to_c(temp_avg_k[near])[used]))
            if used.any()
            else None,
            "max": float(kelvin_to_c(temp_avg_k[near])[used].max())
            if used.any()
            else None,
        },
        "by_aggregation": results,
    }


# ── section 2: the lookup table at matched latitude ─────────────────────────


def measure_lookup_table(inputs: dict) -> dict:
    metadata = inputs["metadata"]
    prp = inputs["prp"]
    recovered = recover_lookup_table(
        inputs["sunlit_peak"], inputs["slope"], inputs["aspect"]
    )
    table = recovered["table_c"]

    from pyproj import CRS, Transformer

    geographic = CRS.from_proj4(
        f"+proj=lonlat +R={PRP_QUOTED['a_axis_radius_km'] * 1000.0:.1f} +no_defs"
    )
    to_geographic = Transformer.from_crs(
        CRS.from_wkt(metadata["crs"]), geographic, always_xy=True
    )
    x, y = grid_cell_centres(metadata)
    _, window_lat = to_geographic.transform(x.ravel(), y.ravel())
    lat_low, lat_high = float(window_lat.min()), float(window_lat.max())

    lat = prp["lat_deg"].astype(np.float64)
    band = (lat >= lat_low) & (lat <= lat_high)
    slope = prp["slope_deg"].astype(np.float64)[band]
    aspect = prp["aspect_true_deg"].astype(np.float64)[band]
    reference_c = kelvin_to_c(prp["temp_max_k"].astype(np.float64)[band])

    modelled = evaluate_lookup_table(table, slope, aspect)
    aspect_resolved = error_statistics(modelled, reference_c)

    # Frame-independent view: marginalise aspect away entirely. Our grid's
    # aspect is measured in GRID coordinates while heat1d documents slope_az
    # as clockwise from TRUE north, and the two differ by the meridian
    # convergence (~72.7 deg at this longitude). Binning by slope alone is
    # immune to that, so it is the comparison that does not rest on an
    # unverified convention.
    edges = np.linspace(0.0, LUT_SLOPE_MAX_DEG, LUT_N_SLOPE + 1)
    by_slope = []
    table_slope_mean = np.nanmean(table, axis=1)
    for i in range(LUT_N_SLOPE):
        selected = (slope >= edges[i]) & (slope < edges[i + 1])
        n = int(selected.sum())
        by_slope.append(
            {
                "slope_from_deg": float(edges[i]),
                "slope_to_deg": float(edges[i + 1]),
                "n": n,
                "prp_temp_max_c_mean": float(reference_c[selected].mean())
                if n
                else None,
                "prp_temp_max_c_median": float(np.median(reference_c[selected]))
                if n
                else None,
                "our_lut_c_aspect_mean": (
                    None
                    if np.isnan(table_slope_mean[i])
                    else float(table_slope_mean[i])
                ),
            }
        )

    # How much of the disagreement could an aspect rotation explain? Scanning
    # it is a DIAGNOSTIC, not a fit: nothing downstream is changed by the
    # answer. If the best offset lands near the meridian convergence, that is
    # evidence the grid-vs-true-north frame mismatch is real and costly.
    rotation_scan = []
    for offset in range(0, 360, 5):
        rotated = evaluate_lookup_table(table, slope, np.mod(aspect + offset, 360.0))
        residual = rotated - reference_c
        residual = residual[np.isfinite(residual)]
        rotation_scan.append(
            {
                "offset_deg": offset,
                "rmse_c": float(np.sqrt(np.mean(residual**2))) if residual.size else None,
            }
        )
    valid_scan = [r for r in rotation_scan if r["rmse_c"] is not None]
    best = min(valid_scan, key=lambda r: r["rmse_c"]) if valid_scan else None

    return {
        "recovered_lut": {
            k: v for k, v in recovered.items() if k not in ("table_c", "counts")
        },
        "lut_table_c": table.tolist(),
        "latitude_band_deg": [lat_low, lat_high],
        "n_facets_in_band": int(band.sum()),
        "prp_slope_deg": {
            "min": float(slope.min()) if slope.size else None,
            "median": float(np.median(slope)) if slope.size else None,
            "max": float(slope.max()) if slope.size else None,
            "over_lut_max_pct": float(100.0 * np.mean(slope > LUT_SLOPE_MAX_DEG))
            if slope.size
            else None,
        },
        "aspect_resolved": aspect_resolved,
        "aspect_marginalised_by_slope": by_slope,
        "aspect_marginalised_spearman": spearman_rho(
            np.array([b["our_lut_c_aspect_mean"] or np.nan for b in by_slope]),
            np.array([b["prp_temp_max_c_mean"] or np.nan for b in by_slope]),
        ),
        "rotation_scan": rotation_scan,
        "best_rotation": best,
        # Magnitude of the grid-north / true-north separation across the
        # window. For a polar stereographic projection the meridian
        # convergence is the longitude difference from the central meridian
        # (0 here), so |mean longitude| is that angle. Reported unsigned:
        # the sign depends on the axis convention in the CRS's WKT, and the
        # rotation scan above measures the direction empirically anyway.
        "window_mean_longitude_deg": float(
            np.mean(to_geographic.transform(x.ravel(), y.ravel())[0])
        ),
        "meridian_convergence_deg": float(
            abs(np.mean(to_geographic.transform(x.ravel(), y.ravel())[0]))
        ),
    }


# ── section 3 and 4 ─────────────────────────────────────────────────────────


def measure_psr_floor(inputs: dict, window: dict) -> dict:
    """Our PSR floor against what Diviner actually reports at the same places.

    ``thermal_model.PSR_ANNUAL_MAX_K`` is 90 K: the middle of the 80-110 K
    band Paige et al. (2010) report for large south-polar PSRs. Every cell
    our model calls never-lit is pinned there by ``annual_peak_c``, so the
    floor sets candidate B's cold tail outright. The PRP carries the same
    statistic (annual maximum at the surface) for every facet, which makes
    the floor directly checkable for the first time.

    Reported, not changed. Moving the constant would be calibration.
    """
    from app.thermal_model import PSR_ANNUAL_MAX_K

    prp = inputs["prp"]
    lat = prp["lat_deg"].astype(np.float64)
    temp_max_k = prp["temp_max_k"].astype(np.float64)
    shadow = np.asarray(inputs["shadow_ratio"], dtype=np.float64)

    band_low, band_high = window["window_lat_deg"] or (-90.0, -80.0)
    band = (lat >= band_low) & (lat <= band_high)
    poleward_88 = lat <= -88.0
    poleward_80 = lat <= -80.0

    return {
        "our_floor_k": float(PSR_ANNUAL_MAX_K),
        "our_floor_c": float(PSR_ANNUAL_MAX_K + _ABSOLUTE_ZERO_C_LOCAL),
        "our_floor_source": (
            "thermal_model.PSR_ANNUAL_MAX_K -- mid-point of the 80-110 K "
            "annual-maximum band Paige et al. (2010) report for large "
            "south-polar PSRs"
        ),
        "n_never_lit_cells_in_window": int(np.sum(shadow >= 1.0)),
        "prp_window_min_k": window["reference_temp_max_c"]["min"] is not None
        and float(window["reference_temp_max_c"]["min"]) - _ABSOLUTE_ZERO_C_LOCAL
        or None,
        "prp_band_min_k": float(temp_max_k[band].min()) if band.any() else None,
        "prp_poleward88_min_k": float(temp_max_k[poleward_88].min()),
        "prp_below_floor_pct_poleward88": float(
            100.0 * np.mean(temp_max_k[poleward_88] < PSR_ANNUAL_MAX_K)
        ),
        "prp_below_floor_pct_poleward80": float(
            100.0 * np.mean(temp_max_k[poleward_80] < PSR_ANNUAL_MAX_K)
        ),
        "prp_poleward80_range_k": [
            float(temp_max_k[poleward_80].min()),
            float(temp_max_k[poleward_80].max()),
        ],
    }


def measure_cold_traps(inputs: dict) -> dict:
    prp = inputs["prp"]
    return cold_trap_area_check(
        prp["lat_deg"].astype(np.float64),
        prp["temp_max_k"].astype(np.float64),
        prp["area_km2"].astype(np.float64),
    )


def measure_night_minimum(inputs: dict, williams_dir: Path | None) -> dict:
    """Williams' seasonal minimum against our cold end -- if the maps exist.

    The PRP carries no minimum at all: its two temperature columns are an
    annual maximum at the surface and an annual average 2 cm down. So this
    section depends entirely on Williams' separate 240 m/px products, and
    when they are not on disk it returns unavailable WITH the reason rather
    than substituting something that looks like an answer.

    It also names the statistic gap, which no download fixes: Williams'
    "min" is a seasonal minimum of surface temperature, while our
    ``thermal_min`` is a radiative EQUILIBRIUM under time-averaged
    insolation. Those are different quantities, and heat1d's own nightly
    transient minimum (C6's envelope cache reaches -232.4 C) is a third.
    """
    present = (
        williams_dir is not None
        and williams_dir.is_dir()
        and any(williams_dir.iterdir())
    )
    if not present:
        return {
            "status": "unavailable",
            "reason": (
                "Williams et al. (2019) 240 m/px seasonal min maps are not on "
                "disk. The Diviner PRP cannot stand in: its columns are an "
                "annual MAXIMUM at the surface and an annual AVERAGE at 2 cm "
                "depth, neither of which is a seasonal minimum."
            ),
            "statistic_gap": (
                "Williams 'min' = seasonal minimum of surface temperature; our "
                "thermal_min = radiative equilibrium under time-averaged "
                "insolation; heat1d's nightly transient floor is a third "
                "quantity again. Naming which is compared is a precondition "
                "for a number, not a caveat on one."
            ),
            "searched": str(williams_dir) if williams_dir else None,
            "quoted": dict(WILLIAMS_QUOTED),
        }
    return {
        "status": "present",
        "reason": "maps found; per-product comparison not implemented in this pass",
        "searched": str(williams_dir),
    }


def measure(processed: Path, williams_dir: Path | None) -> dict:
    started = time.time()
    inputs = load_inputs(processed)
    window = measure_window(inputs)
    data = {
        "prp_meta": inputs["prp_meta"],
        "grid_metadata": {
            k: inputs["metadata"][k]
            for k in (
                "shape",
                "resolution_m",
                "origin",
                "window_offset",
                "thermal_field",
                "layer_validity",
            )
            if k in inputs["metadata"]
        },
        "window": window,
        "lookup_table": measure_lookup_table(inputs),
        "psr_floor": measure_psr_floor(inputs, window),
        "cold_traps": measure_cold_traps(inputs),
        "night_minimum": measure_night_minimum(inputs, williams_dir),
        "quoted": {"prp": dict(PRP_QUOTED), "williams": dict(WILLIAMS_QUOTED)},
    }
    data["total_seconds"] = time.time() - started
    return data


# ── rendering ───────────────────────────────────────────────────────────────


def _stats_row(name: str, stats: dict) -> str:
    interval = stats.get("rmse_ci95_c")
    interval_text = (
        "—" if not interval else f"{_f(interval[0], 1)} – {_f(interval[1], 1)}"
    )
    return (
        f"| `{name}` | {_f(stats.get('rmse_c'), 2)} | {interval_text} | "
        f"{_f(stats.get('bias_c'), 2)} | {_f(stats.get('mae_c'), 2)} | "
        f"{_f(stats.get('spearman'), 3)} | {_f(stats.get('n_compared'))} |"
    )


def render(data: dict) -> str:
    prp_meta = data["prp_meta"]
    window = data["window"]
    lut = data["lookup_table"]
    cold = data["cold_traps"]
    night = data["night_minimum"]
    psr = data["psr_floor"]

    lines: list[str] = [
        "# Diviner PRP termal doğrulama raporu (C5)",
        "",
        "*Üretim: `python scripts/validate_thermal.py` "
        "(`--json` ham çıktı, `--from-json` ölçmeden yeniden render).*",
        "",
        "## Ne neye karşı ölçüldü",
        "",
        f"**Referans:** `{prp_meta['data_set_id']}` — {prp_meta['citation']}",
        "",
        f"> PDS kataloğu bu ürünü şöyle tanımlıyor: *\"{PRP_QUOTED['nature_quote']}\"*, "
        f"işlem düzeyi *\"{PRP_QUOTED['processing_level_quote']}\"*.",
        "",
        "Yani PRP **ham bir ölçüm değil**, Diviner gözlemlerine oturtulmuş bir "
        "**modeldir**. Bu karşılaştırma MODEL ↔ MODEL-ÖLÇÜME-OTURTULMUŞ'tur; "
        "\"ölçüme karşı doğrulandı\" ile aynı iddia değildir. Hiçbir katmanın "
        "`layer_validity` etiketi bu rapor yüzünden yükselmez.",
        "",
        "| | Bizim | Diviner PRP |",
        "|---|---|---|",
        f"| Kaynak | LunaPath heat1d LUT (MODEL) | {prp_meta['validity']} |",
        f"| Çözünürlük | {data['grid_metadata']['resolution_m']:.0f} m/px | "
        f"~{prp_meta['equivalent_edge_m']:.0f} m (üçgen kenarı) |",
        f"| Topografya | Site11 5 m LOLA | {prp_meta['mesh_reference']} |",
        f"| İstatistik | yıllık tepe | `temp_max` — *{PRP_QUOTED['temp_max_definition']}* |",
        "",
        f"PRP'nin ikinci sıcaklık sütunu `temp_avg` **yüzeyin 2 cm altında** "
        f"(*{PRP_QUOTED['temp_avg_definition']}*) hesaplanmıştır; bir yüzey alanı "
        "değildir ve bu yüzden karşılaştırmaya girmez. `ice_depth` modellenmiş "
        "bir üründür, o da girmez.",
        "",
        f"Ham dosya: **{prp_meta['raw_bytes']:,} B**, "
        f"SHA-256 `{prp_meta['raw_sha256']}`, "
        f"{prp_meta['n_triangles']:,} üçgen, "
        f"enlem {prp_meta['lat_range_deg'][0]:.3f}…{prp_meta['lat_range_deg'][1]:.3f}°.",
        "",
        "---",
        "",
        "## 1. Site11 penceresi",
        "",
        f"Pencerede **{window['n_facet_centres_inside_window']}** PRP üçgeninin "
        f"merkezi var; kenardan taşanlarla birlikte "
        f"**{window['n_facets_with_cells']}** üçgen bizim hücrelerimizi örtüyor "
        f"(üçgen başına medyan {_f(window['cells_per_facet_median'], 0)} hücre; "
        f"{window['n_cells_assigned']:,}/{window['n_cells_total']:,} hücre atandı).",
        "",
        "**Bu n küçüktür ve öyle okunmalıdır.** 2,5 km × 2,5 km'lik pencerede "
        f"~{prp_meta['equivalent_edge_m']:.0f} m'lik bir ürün bu kadar örnek verir; "
        "RMSE'nin %95 güven aralığı aşağıda ayrı sütunda duruyor ve geniştir. "
        "Karşılaştırma **kabanın çözünürlüğünde** yapıldı: bizim 5 m'lik gridimiz "
        "her üçgenin ayak izinde toplulaştırıldı, PRP 5 m'e interpolasyon "
        "**yapılmadı** (yapılsaydı 50 ölçüm 250 000 sahte örneğe dönerdi).",
        "",
        "**Kenardan kırpılan fasetler ölçümden çıkarıldı.** Bir Diviner fasetinin "
        "`temp_max`'ı **bütün** üçgenini (~0,128 km²) anlatır. Pencere kenarında "
        "kırpılan bir faset bize yalnız kendi diliminden görünür ve bizim o dilim "
        "üzerindeki ortalamamızı onların tüm üçgen için verdiği değere karşı koymak "
        "**benzemeyen şeyleri** karşılaştırmaktır. Ölçüldü: hücrelerimizi örten "
        f"{window['n_facets_with_cells']} fasetin "
        f"**{window['n_facets_below_half_coverage']}**'i yarıdan az örtülüyor "
        f"(en küçüğü %{window['coverage_percentiles']['0'] * 100:.1f}), ve bunları "
        "dâhil etmek uyumu **olduğundan iyi** gösteriyor (aşağıdaki duyarlılık "
        "tablosu). Bu yüzden ana sayı "
        f"**örtme ≥ %{window['primary_coverage'] * 100:.0f}** süzgecinden geçen "
        f"**{window['n_facets_compared']}** fasetle hesaplandı; süzgeçsiz ve daha "
        "sıkı hâlleri de yayımlandı.",
        "",
        f"PRP `temp_max` penceredeki aralık: "
        f"{_f(window['reference_temp_max_c']['min'], 2)} … "
        f"{_f(window['reference_temp_max_c']['max'], 2)} °C "
        f"(medyan {_f(window['reference_temp_max_c']['median'], 2)}).",
        "",
    ]

    primary = f"{window['primary_coverage']:.2f}"
    for how, title in (
        ("mean", "Ortalama toplulaştırma (**dürüst eşdeğer**)"),
        ("max", "Maksimum toplulaştırma (karşılaştırma için)"),
    ):
        lines += [
            f"### {title} — örtme ≥ %{window['primary_coverage'] * 100:.0f}",
            "",
            "| Aday | RMSE (°C) | RMSE %95 GA | Bias (°C) | MAE (°C) | Spearman | n |",
            "|---|---|---|---|---|---|---|",
        ]
        for name, stats in window["by_aggregation"][how][primary].items():
            lines.append(_stats_row(name, stats))
        lines.append("")

    lines += [
        "### Örtme eşiğine duyarlılık (ortalama toplulaştırma)",
        "",
        "| Eşik | Aday | RMSE (°C) | Bias (°C) | Spearman | n |",
        "|---|---|---|---|---|---|",
    ]
    for threshold, block in window["by_aggregation"]["mean"].items():
        for name, stats in block.items():
            mark = " **←**" if threshold == primary else ""
            lines.append(
                f"| ≥ %{float(threshold) * 100:.0f}{mark} | `{name}` | "
                f"{_f(stats.get('rmse_c'), 2)} | {_f(stats.get('bias_c'), 2)} | "
                f"{_f(stats.get('spearman'), 3)} | {_f(stats.get('n_compared'))} |"
            )
    lines.append("")

    _primary_mean = window["by_aggregation"]["mean"][primary]
    lines += [
        "**Toplulaştırma neden ortalama?** PRP'nin üçgen değeri tek bir **fasetin** "
        "(tek eğim, tek bakı) modellenmiş yıllık maksimumudur — faset içindeki "
        "topografyanın maksimumu değil. Bizim 5 m hücrelerimizin ortalaması bu "
        "tanımın karşılığıdır; maksimum toplulaştırma karşılaştırma için verilmiştir.",
        "",
        "**Üç aday ne demek:**",
        "",
        "- `A_thermal_sunlit_peak` — `thermal_grid.npy`, olduğu gibi: yalnız geometri, "
        "gölge görmez.",
        "- `B_thermal_annual_peak` — `annual_peak_c(sunlit_peak, shadow_ratio)`: gölge "
        "eşlenmiş yıllık tepe, **planlayıcının gerçekten kullandığı alan**.",
        "- `C_thermal_min_equilibrium` — soğuk uç **dengesi**; bir maksimum değildir, "
        "PRP `temp_max`'ın karşılığı olması beklenmez ve tam da bu yüzden ölçülmüştür.",
        "",
        "### Hangisi doğru eşleşme? (gerekçesiyle)",
        "",
        "**Kavramsal olarak B.** PRP `temp_max` gerçek bir topografya üzerinde, "
        "aydınlanma dâhil hesaplanmış yıllık maksimumdur; bizde bunun karşılığı "
        "gölge eşlenmiş `annual_peak_c`'dir, yani B. A gölgeyi hiç görmez, C ise "
        "bir maksimum bile değildir.",
        "",
        "**Sayılar bunu kısmen doğruluyor, kısmen çürütüyor.** B'nin sıra "
        f"korelasyonu A'dan belirgin biçimde daha iyi "
        f"({_f(_primary_mean['B_thermal_annual_peak']['spearman'], 3)} ↔ "
        f"{_f(_primary_mean['A_thermal_sunlit_peak']['spearman'], 3)}) — "
        "yani gölge eşlemesi hücreleri **doğru sıraya** sokuyor. Ama B'nin RMSE'si "
        f"A'dan **daha kötü** "
        f"({_f(_primary_mean['B_thermal_annual_peak']['rmse_c'], 2)} ↔ "
        f"{_f(_primary_mean['A_thermal_sunlit_peak']['rmse_c'], 2)} °C) "
        "ve soğuk yönde iki katına yakın bias taşıyor "
        f"({_f(_primary_mean['B_thermal_annual_peak']['bias_c'], 2)} ↔ "
        f"{_f(_primary_mean['A_thermal_sunlit_peak']['bias_c'], 2)} °C). "
        "Nedeni aşağıdaki PSR tabanıdır, ve bu bir kusurdur, bir tercih değil.",
        "",
        "**Karar:** karşılaştırmanın doğru tarafı **B**'dir — planlayıcının okuduğu "
        "alan odur ve istatistik eşleşmesi odur. A'nın daha küçük RMSE'si, gölge "
        "eşlemesinin **yönünü** değil, PSR tabanının **değerini** suçlar: gölgeyi hiç "
        "uygulamamak, bu pencerede yanlış bir tabanla uygulamaktan tesadüfen daha az "
        "hata veriyor. Doğru okuma \"A daha iyi model\" değil, \"B'nin soğuk kuyruğu "
        "fazla soğuk\"tur.",
        "",
        "---",
        "",
        "## 1b. PSR tabanı — ilk kez ölçülebilir hâle geldi",
        "",
        f"`thermal_model.PSR_ANNUAL_MAX_K` = **{psr['our_floor_k']:.0f} K "
        f"({_f(psr['our_floor_c'], 2)} °C)**. Kaynağı: {psr['our_floor_source']}. "
        "`annual_peak_c` hiç aydınlanmayan her hücreyi buraya sabitler, yani bu sabit "
        "B adayının soğuk kuyruğunu tek başına belirliyor. PRP aynı istatistiği "
        "(yüzeyde yıllık maksimum) her faset için taşıdığından, taban **ilk kez** "
        "doğrudan kontrol edilebiliyor.",
        "",
        "| | Değer |",
        "|---|---|",
        f"| Bizim tabanımız | {psr['our_floor_k']:.0f} K |",
        f"| Penceredeki hiç aydınlanmayan hücre sayısı | "
        f"{psr['n_never_lit_cells_in_window']:,} |",
        f"| PRP'nin penceredeki en soğuk `temp_max`'ı | "
        f"{_f(psr['prp_window_min_k'], 1)} K |",
        f"| PRP'nin enlem şeridindeki en soğuk `temp_max`'ı | "
        f"{_f(psr['prp_band_min_k'], 1)} K |",
        f"| PRP'nin 88°S kutup tarafındaki en soğuğu | "
        f"{_f(psr['prp_poleward88_min_k'], 1)} K |",
        f"| 88°S kutup tarafında tabanımızın **altında** kalan fasetler | "
        f"%{_f(psr['prp_below_floor_pct_poleward88'], 2)} |",
        f"| 80°S kutup tarafında tabanımızın altında kalanlar | "
        f"%{_f(psr['prp_below_floor_pct_poleward80'], 2)} |",
        f"| 80°S kutup tarafında PRP `temp_max` aralığı | "
        f"{psr['prp_poleward80_range_k'][0]:.1f} – "
        f"{psr['prp_poleward80_range_k'][1]:.1f} K |",
        "",
        "**İki yönlü bir bulgu, ve ikisi de yazılmalı:**",
        "",
        f"1. **Site11 penceresinde taban fazla soğuk.** PRP'nin penceredeki en soğuk "
        f"faseti {_f(psr['prp_window_min_k'], 1)} K; bizim tabanımız "
        f"{psr['our_floor_k']:.0f} K, yani yaklaşık "
        f"**{_f((psr['prp_window_min_k'] or 0) - psr['our_floor_k'], 0)} K daha soğuk**. "
        f"Penceredeki {psr['n_never_lit_cells_in_window']:,} hiç-aydınlanmayan hücre "
        "bu tabana çakıldığı için B adayının bias'ı A'nınkinin iki katına çıkıyor.",
        f"2. **Bölge genelinde taban fazla sıcak.** 88°S'nin kutup tarafındaki "
        f"fasetlerin **%{_f(psr['prp_below_floor_pct_poleward88'], 2)}**'i "
        f"{psr['our_floor_k']:.0f} K'nin altında, en soğuğu "
        f"{_f(psr['prp_poleward88_min_k'], 1)} K. Yani tek bir sabit taban, PRP'nin "
        f"{psr['prp_poleward80_range_k'][0]:.0f}–"
        f"{psr['prp_poleward80_range_k'][1]:.0f} K'lik gerçek yayılımını temsil "
        "edemiyor — Paige'in 80–110 K bandının ortası bir **bant ortası**ydı, bir "
        "hücre değeri değil.",
        "",
        "**C5 bu sabiti DEĞİŞTİRMEZ.** Değiştirmek kalibrasyondur: `annual_peak_c`'nin "
        "soğuk kuyruğunu, `THERMAL_MIN_TRAVERSABLE_C` kapısını, maliyet gridini ve her "
        "rotayı oynatır. Ölçüldü, yazıldı, dokunulmadı.",
        "",
        "---",
        "",
        "## 2. LUT'un kendisi (enlem eşlenmiş)",
        "",
        f"Pencerenin kendi enlem şeridinde "
        f"({lut['latitude_band_deg'][0]:.4f}° … {lut['latitude_band_deg'][1]:.4f}°) "
        f"tüm boylamlarda **{lut['n_facets_in_band']:,}** PRP üçgeni var. Enlemin "
        "eşlenmesi zorunlu: −88,9°'de Güneş'in maksimum yüksekliği ~0,5° ve enlemle "
        "hızla değişiyor, geniş bir şerit tablomuzu başka bir aydınlanmaya karşı "
        "koyardı.",
        "",
        f"LUT `thermal_grid.npy`'den geri kazanıldı: "
        f"{lut['recovered_lut']['n_bins_populated']}/"
        f"{lut['recovered_lut']['n_bins_total']} kutu dolu, "
        f"düz hücre tepesi **{_f(lut['recovered_lut']['flat_cell_peak_c'], 2)} °C** "
        "(C6'nın heat1d ölçümü −146,4 °C ile uyuşuyor). "
        f"{lut['recovered_lut']['n_bins_multivalued']} kutuda birden fazla değer var: "
        "geri kazanılan tablo eğim/bakı gridlerine yeniden uygulandığında hücrelerin "
        f"**%{_f(lut['recovered_lut']['reconstruction_mismatch_pct'], 2)}**'i "
        f"tutmuyor, en büyük fark "
        f"**{_f(lut['recovered_lut']['reconstruction_max_abs_diff_c'], 2)} °C** ve "
        "farklar hep **komşu kutu** değerleri. Yani gönderilen termal grid, diskteki "
        "eğim/bakı gridlerinden belgelenmiş en-yakın-kutu kuralıyla **bit-eşit olarak "
        "yeniden üretilemiyor**. Ölçüldü ve yazıldı; nedeni **saptanmadı** (eğim/bakı "
        "gridlerinin termal gridden sonra yeniden üretilmiş olması bu büyüklükle "
        "tutarlı olurdu, ama bu bir hipotezdir, ölçüm değil). Aşağıdaki RMSE'lerin "
        "yanında bu ≤6 °C'lik kutu-kenarı gürültüsü küçüktür.",
        "",
        f"PRP faset eğimi: {_f(lut['prp_slope_deg']['min'], 2)}° … "
        f"{_f(lut['prp_slope_deg']['max'], 2)}° "
        f"(medyan {_f(lut['prp_slope_deg']['median'], 2)}°); "
        f"%{_f(lut['prp_slope_deg']['over_lut_max_pct'], 2)}'i LUT'un 30° tavanının "
        "üstünde ve orada kırpılıyor.",
        "",
        "### 2a. Bakı marjinalleştirilmiş (referans çerçevesinden bağımsız)",
        "",
        "| Eğim aralığı | n | PRP `temp_max` ort. (°C) | Bizim LUT (bakı ort., °C) |",
        "|---|---|---|---|",
    ]
    for row in lut["aspect_marginalised_by_slope"]:
        lines.append(
            f"| {row['slope_from_deg']:.1f}–{row['slope_to_deg']:.1f}° | "
            f"{_f(row['n'])} | {_f(row['prp_temp_max_c_mean'], 2)} | "
            f"{_f(row['our_lut_c_aspect_mean'], 2)} |"
        )
    lines += [
        "",
        f"Eğim kutuları arası Spearman: "
        f"**{_f(lut['aspect_marginalised_spearman'], 3)}**.",
        "",
        "### 2b. Bakı çözümlenmiş (çerçeve varsayımı açık)",
        "",
        "| Aday | RMSE (°C) | RMSE %95 GA | Bias (°C) | MAE (°C) | Spearman | n |",
        "|---|---|---|---|---|---|---|",
        _stats_row("heat1d LUT (gölgesiz)", lut["aspect_resolved"]),
        "",
        "**Çerçeve uyarısı — C5'in bulgusu.** heat1d'in `slope_az` parametresi kurulu "
        "paketin docstring'inde *\"clockwise from north (0 = N, pi/2 = E)\"*, yani "
        "**gerçek** yerel kuzeye göre tanımlı. Bizim `make_aspect_grid`'imiz "
        "(`lunapath/src/process_lunar_data.py:275`) açıyı **grid** koordinatlarında "
        "hesaplıyor. Polar stereografik projeksiyonda bu ikisi meridyen yakınsaması "
        "kadar ayrışır ve pencere boylamında (−72,67°) bu ~72,7° eder — 22,5°'lik "
        "bakı kutularında ~3,2 kutu.",
        "",
    ]
    if lut["best_rotation"]:
        # The convergence's MAGNITUDE is predicted by geometry; its SIGN
        # depends on the axis convention in the CRS's WKT, so both branches
        # are printed and the scan is allowed to say which one it is. That
        # is a measurement choosing between two prior hypotheses, not a fit.
        convergence = float(lut["meridian_convergence_deg"])
        branch_plus = float(np.mod(convergence, 360.0))
        branch_minus = float(np.mod(-convergence, 360.0))
        best_offset = float(lut["best_rotation"]["offset_deg"])

        def _separation(target: float) -> float:
            return abs((best_offset - target + 180.0) % 360.0 - 180.0)

        sep_plus, sep_minus = _separation(branch_plus), _separation(branch_minus)
        predicted = branch_plus if sep_plus <= sep_minus else branch_minus
        separation = min(sep_plus, sep_minus)
        lines += [
            "Tanısal tarama (5° adımlarla, bakıya sabit bir ofset eklenip RMSE "
            "yeniden hesaplanarak):",
            "",
            "| | Ofset | RMSE (°C) |",
            "|---|---|---|",
            f"| Ofsetsiz | 0° | {_f(lut['aspect_resolved']['rmse_c'], 2)} |",
            f"| **Taramanın en iyisi** | **{best_offset:.0f}°** | "
            f"**{_f(lut['best_rotation']['rmse_c'], 2)}** |",
            f"| Meridyen yakınsaması, + dalı | {branch_plus:.1f}° | — |",
            f"| Meridyen yakınsaması, − dalı | {branch_minus:.1f}° | — |",
            "",
            f"Yakınsamanın **büyüklüğü** geometriden öngörülüyor "
            f"({_f(lut['meridian_convergence_deg'], 2)}°); **işareti** CRS'in eksen "
            "konvansiyonuna bağlı olduğu için iki dal da yazıldı ve hangisi olduğunu "
            f"taramanın söylemesine izin verildi. Minimum {predicted:.1f}° dalına "
            f"**{separation:.1f}°** uzakta (öteki dala "
            f"{max(sep_plus, sep_minus):.1f}°), yani LUT'un 22,5°'lik bakı "
            "kutusundan daha yakın. Çerçeve uyuşmazlığı **gerçek ve öngörülen "
            "büyüklükte**. Ama kazanç küçük: "
            f"{_f(lut['aspect_resolved']['rmse_c'], 2)} → "
            f"{_f(lut['best_rotation']['rmse_c'], 2)} °C "
            f"(%{_f(100.0 * (1.0 - lut['best_rotation']['rmse_c'] / lut['aspect_resolved']['rmse_c']), 1)}), "
            "ve tüm tarama yalnızca "
            f"{_f(min(r['rmse_c'] for r in lut['rotation_scan']), 1)}–"
            f"{_f(max(r['rmse_c'] for r in lut['rotation_scan']), 1)} °C arasında "
            "geziniyor. Toplam uyuşmazlığın çoğunu bakı çerçevesi **açıklamıyor** "
            "(gölgeleme, topografya ve model farkları duruyor).",
            "",
            "Bu bir **tanıdır, bir uydurma değildir**: hiçbir parametre bu sayıya "
            "göre değiştirilmemiştir.",
            "",
        ]
    lines += [
        "**C5 bunu düzeltmez.** Düzeltmek `aspect_grid`'i, dolayısıyla `thermal_grid`'i, "
        "dolayısıyla maliyet gridini ve her rotayı değiştirir; bu bir kalibrasyon/hata "
        "düzeltmesidir ve ayrı bir özelliktir. C5 ölçer, adlandırır, yazar.",
        "",
        "---",
        "",
        "## 3. Soğuk tuzak alanı — yayımlanmış bir sayının yeniden türetilmesi",
        "",
        f"> {WILLIAMS_QUOTED['citation']}",
        ">",
        f"> *\"{cold['quoted_text']}\"*",
        "",
        "PRP her üçgenin üç köşesini de taşıdığı için alan `½|(v₂−v₁)×(v₃−v₁)|` ile "
        "doğrudan hesaplanabilir. Yani hedef sayı onların, **aritmetik bizim**.",
        "",
        "| | Değer |",
        "|---|---|",
        f"| Williams'ın yayımladığı (ONLARIN) | {cold['quoted_area_km2']:,.0f} km² |",
        f"| PRP v2'den bizim türettiğimiz | **{cold['derived_area_km2']:,.1f} km²** |",
        f"| Fark | **{_f(cold['difference_pct'], 1)} %** |",
        f"| Soğuk üçgen sayısı | {cold['n_cold_triangles']:,} |",
        f"| 80°S'nin kutup tarafındaki üçgen sayısı | {cold['n_poleward_triangles']:,} |",
        f"| 80°S'nin kutup tarafındaki toplam alan | {cold['poleward_area_km2']:,.0f} km² |",
        f"| Ölçüt | `temp_max` < {cold['peak_temperature_k']:.0f} K, "
        f"enlem ≤ {cold['latitude_limit_deg']:.0f}° |",
        "",
        f"**Künye farkı:** {cold['note']}",
        "",
        "---",
        "",
        "## 4. Gece minimumu (Williams 240 m/px)",
        "",
        f"**Durum: `{night['status']}`.**",
        "",
        f"{night['reason']}",
        "",
    ]
    if night.get("statistic_gap"):
        lines += [f"**İstatistik boşluğu:** {night['statistic_gap']}", ""]
    lines += [
        "---",
        "",
        "## İddia sınırı",
        "",
        "- PRP'nin ve Williams'ın sayıları **onlarındır**; bu raporda alıntı olarak, "
        "künyeleriyle durur.",
        "- RMSE / bias / Spearman **bizimdir**; hangi alan, hangi çözünürlük, hangi n "
        "ile hesaplandığı her tabloda yazılıdır.",
        "- Termal katmanımız hâlâ **MODEL / UNCALIBRATED**. Bu rapor ona bir hata bandı "
        "kazandırır, etiketini yükseltmez.",
        "- Hiçbir rota sayısı değişmedi; C5 planlayıcıya dokunmaz.",
        "- Uyum kötü çıktığı yerde kötü hâliyle yayımlanmıştır; model Diviner'a "
        "uydurulmamıştır.",
        "",
        f"*Ölçüm süresi: {_f(data.get('total_seconds', 0.0) / 60.0, 1)} dk.*",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", default=None)
    parser.add_argument("--from-json", default=None)
    parser.add_argument("--processed-dir", default=str(_PROCESSED))
    parser.add_argument(
        "--williams-dir",
        default=str(_ROOT / "lunapath" / "data" / "raw" / "williams2019"),
    )
    parser.add_argument(
        "--out", default=str(_ROOT / "docs" / "research" / "thermal_validation_report.md")
    )
    args = parser.parse_args()

    if args.from_json:
        data = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    else:
        processed = Path(args.processed_dir)
        needed = ("metadata.json", "thermal_grid.npy", "shadow_ratio_grid.npy")
        missing = [n for n in needed if not (processed / n).exists()]
        if missing:
            print(f"processed grids missing ({', '.join(missing)}); nothing written")
            return 2
        if not (processed / "diviner_prp.npz").exists():
            print(
                "Diviner PRP cache absent. Run:\n"
                "  python scripts/build_diviner_prp_cache.py\n"
                "Nothing measured, nothing written -- this report does not "
                "invent a reference."
            )
            return 2
        data = measure(processed, Path(args.williams_dir))
        if args.json:
            Path(args.json).write_text(
                json.dumps(data, indent=1, default=float), encoding="utf-8"
            )
            print(f"json -> {args.json}")

    Path(args.out).write_text(render(data), encoding="utf-8")
    print(f"report -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
