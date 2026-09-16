"""Compare a modelled thermal grid to an external reference (e.g. Diviner).

Pure functions only: nothing here fetches, downloads or writes. Getting the
Diviner Polar Resource Product onto disk is ``scripts/build_diviner_prp_cache.py``'s
job and running the comparison is ``scripts/validate_thermal.py``'s, so the
arithmetic stays testable without a 605 MB NASA archive file present.

C5 note -- what is being compared to what
-----------------------------------------
The PRP is *not* a measurement. Its PDS catalogue calls it "thermal model
fits to first mapping year Diviner polar observations", processing level
CODMAC 5 / NASA 4. So this module compares a MODEL (ours) against a MODEL
FITTED TO OBSERVATIONS (theirs). That is worth doing and is not the same
claim as "validated against a measurement", and none of these functions
upgrade any layer's validity label.

Their numbers live in :data:`PRP_QUOTED` and :data:`WILLIAMS_QUOTED` and are
never mixed into a table of ours. RMSE, bias and Spearman are ours, and each
is reported with the field, the resolution, the sample size and the masking
that produced it.
"""

from __future__ import annotations

from typing import Any

import numpy as np

_ABSOLUTE_ZERO_C: float = -273.15


# ── what the sources say, verbatim (theirs, not ours) ───────────────────────

#: The PDS archive's own description of the Polar Resource Product, read
#: from the bundle on 16 September 2026. Quoted so a reader can tell our
#: arithmetic from NASA's product description without leaving this file.
PRP_QUOTED: dict[str, Any] = {
    "data_set_id": "LRO-L-DLRE-5-PRP-V2.0",
    "citation": (
        "Paige et al., LRO DLRE LEVEL 5 PRP V2.0, NASA Planetary Data System, "
        "LRO-L-DLRE-5-PRP-V2.0, 2018."
    ),
    "model_reference": "Paige et al., Science 330, 497 (2010)",
    "nature_quote": (
        "thermal model fits to first mapping year Diviner polar observations"
    ),
    "processing_level_quote": "PRPs are CODMAC Level 5 (NASA Level 4)",
    "coverage_quote": (
        "The mesh consists of 288000 triangles and covers a square region "
        "centered on the pole to 80 degrees latitude"
    ),
    "mesh_source_quote": (
        "a north or south polar digital elevation model derived from the "
        "Kaguya laser altimeter experiment results"
    ),
    "temp_max_definition": (
        "The annual maximum temperature (K), calculated at the surface"
    ),
    "temp_avg_definition": (
        "The annual average temperature (K), calculated at a depth of 2 cm "
        "below the surface"
    ),
    "ice_depth_invalid_constant": -999.0,
    # The label's machine-readable record count, which disagrees with the
    # catalogue prose above by a factor of ten. The file is 604 800 210 bytes
    # at 210 bytes per record = 2 880 001 records = 1 header + 2 880 000 rows,
    # so the label is right and the prose dropped a zero.
    "label_file_records": 2_880_000,
    "record_bytes": 210,
    "a_axis_radius_km": 1737.4,
}

#: Williams et al. (2019), "Seasonal Polar Temperatures on the Moon",
#: JGR Planets, doi 10.1029/2019JE006028. Theirs, not ours. The cold-trap
#: area is the one we re-derive with our own arithmetic in
#: :func:`cold_trap_area_check`.
WILLIAMS_QUOTED: dict[str, Any] = {
    "citation": (
        "Williams, Greenhagen, Paige, Schorghofer, Sefton-Nash, Hayne, "
        "Lucey, Siegler, Aye, Seasonal Polar Temperatures on the Moon, "
        "JGR Planets 124, 2019, doi 10.1029/2019JE006028"
    ),
    "map_resolution_m": 240.0,
    "map_products": "seasonal summer/winter max, avg, min and amplitude, to 80 deg",
    "cold_trap_area_km2": 1.3e4,
    "cold_trap_peak_temperature_k": 110.0,
    "cold_trap_quote": (
        "real cold traps poleward of 80S total 1.3e4 km2 (peak T < 110 K)"
    ),
}


# ── the original comparison, unchanged ──────────────────────────────────────


def thermal_comparison(
    model_c: np.ndarray,
    reference_c: np.ndarray,
    traversable_threshold_c: float = -150.0,
) -> dict[str, float | int | None]:
    """RMSE/MAE/bias between a modelled and a reference thermal grid.

    Cells where either grid is NaN are excluded. ``misclassified_traversable_pct``
    is the share of compared cells where the two grids disagree about
    whether ``value >= traversable_threshold_c`` -- the number that
    matters for LunaPath, since that threshold gates traversability.
    """
    model = np.asarray(model_c, dtype=np.float64)
    reference = np.asarray(reference_c, dtype=np.float64)
    if model.shape != reference.shape:
        raise ValueError(
            f"shape mismatch: model {model.shape} vs reference {reference.shape}"
        )

    valid = np.isfinite(model) & np.isfinite(reference)
    n_compared = int(np.sum(valid))
    if n_compared == 0:
        return {
            "rmse_c": None,
            "mae_c": None,
            "bias_c": None,
            "n_compared": 0,
            "misclassified_traversable_pct": None,
        }

    error = model[valid] - reference[valid]
    rmse = float(np.sqrt(np.mean(error**2)))
    mae = float(np.mean(np.abs(error)))
    bias = float(np.mean(error))

    model_ok = model[valid] >= traversable_threshold_c
    reference_ok = reference[valid] >= traversable_threshold_c
    misclassified_pct = float(100.0 * np.mean(model_ok != reference_ok))

    return {
        "rmse_c": round(rmse, 3),
        "mae_c": round(mae, 3),
        "bias_c": round(bias, 3),
        "n_compared": n_compared,
        "misclassified_traversable_pct": round(misclassified_pct, 3),
    }


# ── georeferencing ──────────────────────────────────────────────────────────


def destination_transform(metadata: dict) -> Any:
    """Affine transform of the processed grid, for reprojecting into it.

    ``metadata["origin"]["y"]`` is the window's TOP edge -- the P1
    pipeline records ``win_transform.f``, and ``grid_frame.pixel_to_map_xy``
    reads row 0 back at exactly that y, descending with increasing row.
    ``from_origin(west, north, ...)`` wants that same top edge.

    An earlier revision added ``rows * resolution`` here, treating the
    origin as the bottom edge. That displaced the sampling window one
    full window height north (2.5 km on the shipped 500 x 5 m grid), so
    every statistic would have been computed against the wrong terrain
    with entirely plausible-looking magnitudes. The synthetic end-to-end
    check missed it because it built its reference raster with the same
    wrong transform -- two errors cancelling into a passing test -- which
    is why test_review2_fixes.py pins this against grid_frame instead.
    (Round 2 review, H-3.)

    Half-cell registration: ``pixel_to_map_xy`` returns ``origin.y`` for
    row 0, i.e. it treats the recorded origin as that row's CENTRE, while
    ``from_origin`` names the raster's outer edge. Offsetting by half a
    cell here makes reprojected cell centres land on the coordinates the
    rest of the app assigns to those same cells; without it every sample
    is drawn half a pixel north of the model value it is compared with.

    Lives here rather than in a script because it is pure georeferencing
    that both the raster path and the mesh path need. (C5 moved it out of
    the deleted ``scripts/diviner_validation.py``; the H-3 assertions came
    with it unchanged.)
    """
    import rasterio  # imported lazily: the pure comparisons do not need it

    resolution_m = float(metadata["resolution_m"])
    origin = metadata["origin"]
    return rasterio.transform.from_origin(
        float(origin["x"]) - resolution_m / 2.0,
        float(origin["y"]) + resolution_m / 2.0,
        resolution_m,
        resolution_m,
    )


def grid_cell_centres(metadata: dict) -> tuple[np.ndarray, np.ndarray]:
    """(x, y) map coordinates of every cell centre, shaped like the grid.

    Uses the same convention ``grid_frame.pixel_to_map_xy`` does -- the
    recorded origin is row 0 / column 0's CENTRE and y descends with row --
    so a value sampled here lands on the coordinate the rest of the app
    assigns to that same cell.
    """
    rows, cols = (int(v) for v in metadata["shape"])
    resolution_m = float(metadata["resolution_m"])
    origin = metadata["origin"]
    x = float(origin["x"]) + np.arange(cols, dtype=np.float64) * resolution_m
    y = float(origin["y"]) - np.arange(rows, dtype=np.float64) * resolution_m
    return np.meshgrid(x, y)


# ── statistics ──────────────────────────────────────────────────────────────


def spearman_rho(a: np.ndarray, b: np.ndarray) -> float | None:
    """Spearman rank correlation over pairs where both inputs are finite.

    ``None`` when fewer than three pairs survive or either side is constant
    (the coefficient is undefined, and reporting 0.0 there would read as
    "measured no relationship" rather than "could not measure").
    """
    from scipy.stats import spearmanr

    left = np.asarray(a, dtype=np.float64).ravel()
    right = np.asarray(b, dtype=np.float64).ravel()
    valid = np.isfinite(left) & np.isfinite(right)
    if int(valid.sum()) < 3:
        return None
    left, right = left[valid], right[valid]
    if np.ptp(left) == 0.0 or np.ptp(right) == 0.0:
        return None
    rho = float(spearmanr(left, right).statistic)
    return None if not np.isfinite(rho) else rho


def rmse_ci95(errors: np.ndarray) -> tuple[float, float] | None:
    """Approximate 95% confidence interval for an RMSE, from chi-square.

    With ``n`` residuals, ``n * RMSE^2 / sigma^2`` is chi-square with ``n``
    degrees of freedom, so the interval is
    ``RMSE * sqrt(n / chi2_{0.975,n})`` to ``RMSE * sqrt(n / chi2_{0.025,n})``.

    This exists because C5's Site11 window holds about fifty Diviner facets.
    An RMSE from fifty samples has a visibly wide interval, and publishing
    the point estimate alone would overstate what a 2.5 km window can say.
    """
    from scipy.stats import chi2

    residuals = np.asarray(errors, dtype=np.float64).ravel()
    residuals = residuals[np.isfinite(residuals)]
    n = residuals.size
    if n < 2:
        return None
    rmse = float(np.sqrt(np.mean(residuals**2)))
    lower = rmse * float(np.sqrt(n / chi2.ppf(0.975, n)))
    upper = rmse * float(np.sqrt(n / chi2.ppf(0.025, n)))
    return lower, upper


def error_statistics(
    model_c: np.ndarray,
    reference_c: np.ndarray,
    traversable_threshold_c: float = -150.0,
) -> dict[str, Any]:
    """:func:`thermal_comparison` plus Spearman and an RMSE interval.

    Same masking and the same ``model - reference`` sign convention, so the
    shared keys agree with :func:`thermal_comparison` exactly.
    """
    base = thermal_comparison(model_c, reference_c, traversable_threshold_c)
    model = np.asarray(model_c, dtype=np.float64).ravel()
    reference = np.asarray(reference_c, dtype=np.float64).ravel()
    valid = np.isfinite(model) & np.isfinite(reference)
    out: dict[str, Any] = dict(base)
    out["spearman"] = spearman_rho(model[valid], reference[valid])
    interval = rmse_ci95(model[valid] - reference[valid]) if valid.any() else None
    out["rmse_ci95_c"] = (
        None if interval is None else [round(interval[0], 3), round(interval[1], 3)]
    )
    return out


# ── the Diviner mesh ────────────────────────────────────────────────────────


def triangle_areas_km2(vertices_km: np.ndarray) -> np.ndarray:
    """Area of each triangle from its own three vertices, ``0.5*|(b-a)x(c-a)|``.

    *vertices_km* is ``(n, 3, 3)``: triangle, vertex, xyz. The PRP carries
    the vertices, so its areas are computed rather than assumed from a
    nominal cell size -- which is what makes :func:`cold_trap_area_check`
    a re-derivation instead of a restatement.
    """
    v = np.asarray(vertices_km, dtype=np.float64)
    if v.ndim != 3 or v.shape[1:] != (3, 3):
        raise ValueError(f"expected (n, 3, 3) vertices, got {v.shape}")
    return 0.5 * np.linalg.norm(np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]), axis=1)


def cold_trap_area_check(
    lat_deg: np.ndarray,
    temp_max_k: np.ndarray,
    area_km2: np.ndarray,
    latitude_limit_deg: float = -80.0,
    peak_temperature_k: float = 110.0,
) -> dict[str, Any]:
    """Re-derive Williams et al.'s published cold-trap area from the PRP mesh.

    Williams et al. (2019) report that real cold traps poleward of 80S --
    those whose peak temperature stays below 110 K -- total 1.3e4 km^2.
    Every ingredient is in the PRP file: each triangle carries its own three
    vertices (hence its area) and its own annual maximum surface temperature.
    So the sum is ours even though the target number is theirs.

    This is C5's counterpart of C1's ``panel.viper_corner_check`` and C2's
    ``battery.jsc_survival_temperature_check``: a published number reproduced
    with our own arithmetic, with the difference stated rather than tuned away.

    The two sides are NOT the same product, and the result is reported with
    that said out loud: Williams computed from their own 240 m/px seasonal
    maps, while this sums PRP v2 (the Paige 2010 model on a ~544 m Kaguya
    mesh). Agreement is evidence the two products describe the same Moon;
    disagreement is a real difference between two published products, not an
    error in either. Neither outcome licenses changing anything of ours.
    """
    lat = np.asarray(lat_deg, dtype=np.float64).ravel()
    peak = np.asarray(temp_max_k, dtype=np.float64).ravel()
    area = np.asarray(area_km2, dtype=np.float64).ravel()
    if not (lat.shape == peak.shape == area.shape):
        raise ValueError(
            f"shape mismatch: lat {lat.shape}, temp_max {peak.shape}, "
            f"area {area.shape}"
        )

    poleward = lat <= float(latitude_limit_deg)
    cold = poleward & (peak < float(peak_temperature_k))
    derived = float(area[cold].sum())
    quoted = float(WILLIAMS_QUOTED["cold_trap_area_km2"])

    return {
        "quoted_area_km2": quoted,
        "quoted_text": WILLIAMS_QUOTED["cold_trap_quote"],
        "quoted_source": WILLIAMS_QUOTED["citation"],
        "derived_area_km2": round(derived, 1),
        "derived_from": PRP_QUOTED["data_set_id"],
        "difference_pct": (
            None if quoted == 0.0 else round(100.0 * (derived / quoted - 1.0), 2)
        ),
        "n_cold_triangles": int(cold.sum()),
        "n_poleward_triangles": int(poleward.sum()),
        "poleward_area_km2": round(float(area[poleward].sum()), 1),
        "latitude_limit_deg": float(latitude_limit_deg),
        "peak_temperature_k": float(peak_temperature_k),
        "note": (
            "Williams' figure is theirs, from their 240 m/px seasonal maps. The "
            "derived figure sums PRP v2 triangle areas (Paige 2010 model on a "
            "~544 m Kaguya mesh). Two different published products, so a "
            "difference is informative about the products, not an error of ours."
        ),
    }


def assign_cells_to_facets(
    vertices_xy: np.ndarray, x: np.ndarray, y: np.ndarray
) -> np.ndarray:
    """Index of the triangle covering each grid cell, or -1 where none does.

    *vertices_xy* is ``(n, 3, 2)`` in the grid's own map coordinates; *x*
    and *y* are cell-centre coordinates of the same shape as the grid.
    Membership is an exact barycentric point-in-triangle test, not a
    nearest-centre approximation: the mesh is irregular and a cell nearer
    one centroid can still lie inside its neighbour.
    """
    tri = np.asarray(vertices_xy, dtype=np.float64)
    if tri.ndim != 3 or tri.shape[1:] != (3, 2):
        raise ValueError(f"expected (n, 3, 2) vertices, got {tri.shape}")
    px = np.asarray(x, dtype=np.float64)
    py = np.asarray(y, dtype=np.float64)
    out = np.full(px.shape, -1, dtype=np.int64)

    for index in range(tri.shape[0]):
        (ax, ay), (bx, by), (cx, cy) = tri[index]
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if det == 0.0:
            continue
        lam1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / det
        lam2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / det
        inside = (lam1 >= 0.0) & (lam2 >= 0.0) & (lam1 + lam2 <= 1.0)
        out = np.where(inside & (out < 0), index, out)
    return out


def aggregate_to_facets(
    values: np.ndarray, assignment: np.ndarray, n_facets: int, how: str = "mean"
) -> tuple[np.ndarray, np.ndarray]:
    """Reduce our fine grid onto the reference's facets. Returns (value, count).

    *how* is ``"mean"`` or ``"max"``. The choice is a real decision, not a
    detail: a PRP triangle's value is the modelled annual maximum of ONE
    facet -- a single slope and azimuth -- not the maximum over the
    sub-facet topography our 5 m grid resolves. So ``"mean"`` is the honest
    counterpart and ``"max"`` is reported alongside it to show what the
    choice is worth.

    Facets covering no finite cell come back NaN with count 0, so they drop
    out of the comparison instead of contributing a fabricated value.
    """
    if how not in ("mean", "max"):
        raise ValueError(f"unknown aggregation {how!r}; expected 'mean' or 'max'")
    flat_values = np.asarray(values, dtype=np.float64).ravel()
    flat_assignment = np.asarray(assignment, dtype=np.int64).ravel()
    out = np.full(int(n_facets), np.nan, dtype=np.float64)
    counts = np.zeros(int(n_facets), dtype=np.int64)

    finite = np.isfinite(flat_values) & (flat_assignment >= 0)
    for index in range(int(n_facets)):
        selected = flat_values[finite & (flat_assignment == index)]
        counts[index] = selected.size
        if selected.size:
            out[index] = selected.mean() if how == "mean" else selected.max()
    return out, counts


def facet_coverage_fraction(
    cell_counts: np.ndarray, area_km2: np.ndarray, resolution_m: float
) -> np.ndarray:
    """What fraction of each facet's real footprint our grid actually covers.

    A reference facet's value describes its WHOLE triangle. A facet clipped
    by the edge of our window is only partly visible to us, and comparing our
    mean over a sliver of it against the reference's value for all of it is
    comparing unlike things -- with a bias, not just noise.

    Measured on the Site11 window: 22 of the 71 facets covering any of our
    cells fall below 50 percent coverage and the smallest is 2 percent, and
    including them moved the headline RMSE from 39.4 to 35.5 C. That is the
    wrong direction to accept silently: the unfiltered number is the
    flattering one. So coverage is computed, the comparison is reported at
    several thresholds, and the filtered number is the headline.

    Values can exceed 1 slightly: cell centres are counted against a
    spherical triangle's area, so discretisation cuts both ways.
    """
    counts = np.asarray(cell_counts, dtype=np.float64)
    area = np.asarray(area_km2, dtype=np.float64)
    if counts.shape != area.shape:
        raise ValueError(
            f"shape mismatch: counts {counts.shape} vs area {area.shape}"
        )
    covered_m2 = counts * float(resolution_m) ** 2
    true_m2 = area * 1e6
    return np.divide(
        covered_m2, true_m2, out=np.zeros_like(covered_m2), where=true_m2 > 0.0
    )


def kelvin_to_c(kelvin: np.ndarray) -> np.ndarray:
    """Kelvin to Celsius. PRP temperatures are in K; our grids are in C."""
    return np.asarray(kelvin, dtype=np.float64) + _ABSOLUTE_ZERO_C


def compare_candidates(
    candidates: dict[str, np.ndarray],
    reference_c: np.ndarray,
    traversable_threshold_c: float = -150.0,
) -> dict[str, dict[str, Any]]:
    """Run :func:`error_statistics` for every candidate field against one reference.

    C5 publishes all of them rather than picking one first. Which of our
    fields is the counterpart of Diviner's annual maximum is an argument to
    be made from the numbers, and a single RMSE presented as "the" RMSE is
    the most likely sentence in this feature to be wrong.
    """
    return {
        name: error_statistics(values, reference_c, traversable_threshold_c)
        for name, values in candidates.items()
    }
