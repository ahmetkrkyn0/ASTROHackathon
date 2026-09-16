"""C5 on the real Site11 grid and the real Diviner PRP cache.

Checks the CONTRACT of the comparison, not its result: the report measures
RMSE, bias and Spearman and publishes whatever they are. What must hold
here is that the cache matches the PDS label, that the facet comparison
actually compares co-registered things at the coarse product's resolution,
that the sample size is reported honestly, and -- the point of a validation
feature -- that NOTHING the planner reads moved.

Skips without the processed grids or the Diviner PRP cache. A skipped test
is not a passing test: if these skip, run
``python scripts/build_diviner_prp_cache.py`` first.
"""

from __future__ import annotations

import hashlib
import json
import os

import numpy as np
import pytest

from app.cost_engine import COST_MODEL_ID
from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids
from app.rover_grids import grids_for_rover
from app.thermal_model import (
    PSR_ANNUAL_MAX_K,
    annual_peak_c,
    shadowed_equilibrium_c,
)
from app.thermal_validation import (
    PRP_QUOTED,
    WILLIAMS_QUOTED,
    aggregate_to_facets,
    assign_cells_to_facets,
    cold_trap_area_check,
    compare_candidates,
    facet_coverage_fraction,
    grid_cell_centres,
    kelvin_to_c,
    triangle_areas_km2,
)

PRP_CACHE_FILENAME = "diviner_prp.npz"
PRP_META_FILENAME = "diviner_prp_meta.json"

_HAS_GRIDS = os.path.exists(os.path.join(_P1_PROCESSED_DIR, "metadata.json"))
_HAS_CACHE = _HAS_GRIDS and all(
    os.path.exists(os.path.join(_P1_PROCESSED_DIR, name))
    for name in (PRP_CACHE_FILENAME, PRP_META_FILENAME)
)
pytestmark = pytest.mark.skipif(
    not _HAS_CACHE, reason="needs lunapath/data/processed and the Diviner PRP cache"
)

# The checked-in v5 cost-grid lock from test_roughness_real_grid.py. C5 is a
# validation feature: it must not move a single cost cell, and the cheapest
# proof is that this digest is still exactly what C4 recorded.
#
# LPR-1 only, deliberately. The nasa_viper digest recorded at C4 has not
# matched since 4af6989 corrected that profile's slope_max_deg from 20 to
# 15 degrees, so it is a stale lock, not a live one -- anchoring C5's
# bit-equality claim to it would mean this test fails for a reason that has
# nothing to do with C5. Measured here: lpr_1 matches, nasa_viper does not,
# and nasa_viper did not match at HEAD before C5 either.
V5_COST_SHA256 = {
    "lpr_1": "55e1bb3cd3b9fb93403140b283cfa38fef8b93836a28512bc95f38db5ed893db",
}


def _digest(array: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(array, dtype=np.float64).tobytes()
    ).hexdigest()


@pytest.fixture(scope="module")
def prp():
    return np.load(os.path.join(_P1_PROCESSED_DIR, PRP_CACHE_FILENAME))


@pytest.fixture(scope="module")
def prp_meta():
    with open(os.path.join(_P1_PROCESSED_DIR, PRP_META_FILENAME), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def grids():
    return load_preprocessed_grids()


# ── the cache matches the archive's own label ───────────────────────────────


def test_cache_holds_exactly_the_rows_the_pds_label_promises(prp, prp_meta):
    assert prp_meta["data_set_id"] == PRP_QUOTED["data_set_id"]
    assert prp_meta["n_triangles"] == PRP_QUOTED["label_file_records"]
    assert prp["lat_deg"].size == PRP_QUOTED["label_file_records"]
    # 1 header record + N data records, at the label's fixed record length.
    expected = PRP_QUOTED["record_bytes"] * (PRP_QUOTED["label_file_records"] + 1)
    assert prp_meta["raw_bytes"] == expected
    assert len(prp_meta["raw_sha256"]) == 64


def test_the_product_is_labelled_derived_not_measured(prp_meta):
    """A validation feature must not quietly promote its reference.

    The PDS catalogue calls the PRP "thermal model fits" at CODMAC level 5,
    so it is DERIVED. Calling it MEASURED would make every RMSE in the
    report a stronger claim than the archive supports.
    """
    assert prp_meta["validity"] == "DERIVED"
    assert "thermal model fits" in prp_meta["validity_note"]


def test_the_mesh_covers_everything_poleward_of_80_south(prp):
    lat = prp["lat_deg"]
    # The catalogue says a SQUARE region to 80 deg, so the corners reach
    # equatorward of 80 -- the cold-trap sum below needs full coverage
    # poleward of it, which a square guarantees and a disc would not.
    assert lat.max() > -80.0
    assert lat.min() < -89.9
    assert np.sum(lat <= -80.0) > 2_000_000


def test_facet_size_is_the_coarse_resolution_the_report_claims(prp, prp_meta):
    area = prp["area_km2"].astype(np.float64)
    assert np.all(area > 0.0)
    edge_m = np.sqrt(4.0 * np.median(area) / np.sqrt(3.0)) * 1000.0
    # Roughly half a kilometre: two orders of magnitude coarser than our 5 m
    # grid, which is why the comparison is done at the facet's resolution.
    assert 400.0 < edge_m < 700.0
    assert prp_meta["equivalent_edge_m"] == pytest.approx(edge_m, rel=1e-3)


def test_triangle_areas_recompute_from_the_stored_vertices(prp):
    """The cached areas are not taken on trust: they come back from the
    vertices, which is also what makes the cold-trap sum a re-derivation."""
    index = prp["polar_vertex_index"]
    assert index.size > 10_000
    recomputed = triangle_areas_km2(prp["polar_vertices_km"].astype(np.float64))
    cached = prp["area_km2"].astype(np.float64)[index]
    assert np.allclose(recomputed, cached, rtol=1e-4)


def test_temperature_columns_are_kelvin_and_carry_no_fill_values(prp):
    for name in ("temp_max_k", "temp_avg_k"):
        values = prp[name].astype(np.float64)
        assert np.all(np.isfinite(values))
        assert values.min() > 0.0, f"{name} went below absolute zero"
        assert values.max() < 450.0, f"{name} is implausible for the Moon"
        assert not np.any(values == PRP_QUOTED["ice_depth_invalid_constant"])
    # temp_max is a maximum and temp_avg is 2 cm down, so the ordering holds
    # everywhere; if it ever did not, the two columns would be swapped.
    assert np.all(prp["temp_max_k"] >= prp["temp_avg_k"])


# ── the published-number re-derivation ──────────────────────────────────────


def test_cold_trap_area_lands_in_the_same_order_as_williams(prp):
    """Re-derive their 1.3e4 km^2 from the mesh's own vertices.

    The assertion is deliberately loose: the two sides are DIFFERENT
    published products (Williams' 240 m seasonal maps vs PRP v2 on a ~544 m
    Kaguya mesh), so pinning an exact agreement would be asserting that two
    NASA products are identical, which they are not. What is worth failing
    on is the arithmetic breaking -- a unit slip, a lost mask, a wrong
    latitude sign -- which would miss by orders of magnitude, not percent.
    """
    result = cold_trap_area_check(
        prp["lat_deg"].astype(np.float64),
        prp["temp_max_k"].astype(np.float64),
        prp["area_km2"].astype(np.float64),
    )
    quoted = WILLIAMS_QUOTED["cold_trap_area_km2"]
    assert 0.5 * quoted < result["derived_area_km2"] < 2.0 * quoted
    assert result["n_cold_triangles"] > 10_000
    assert result["difference_pct"] is not None
    # The spherical cap poleward of 80 S is ~288 000 km^2; a mesh draped on
    # real topography is slightly larger, never smaller.
    assert 285_000 < result["poleward_area_km2"] < 320_000


def test_cold_trap_area_is_monotone_in_the_temperature_threshold(prp):
    lat = prp["lat_deg"].astype(np.float64)
    peak = prp["temp_max_k"].astype(np.float64)
    area = prp["area_km2"].astype(np.float64)
    areas = [
        cold_trap_area_check(lat, peak, area, peak_temperature_k=t)["derived_area_km2"]
        for t in (100.0, 110.0, 120.0)
    ]
    assert areas[0] < areas[1] < areas[2]


# ── the window comparison ───────────────────────────────────────────────────


@pytest.fixture(scope="module")
def window_facets(prp, grids):
    from pyproj import CRS, Transformer

    metadata = grids["metadata"]
    index = prp["polar_vertex_index"]
    lat = prp["lat_deg"].astype(np.float64)[index]
    lon = prp["lon_deg"].astype(np.float64)[index]
    geographic = CRS.from_proj4(
        f"+proj=lonlat +R={PRP_QUOTED['a_axis_radius_km'] * 1000.0:.1f} +no_defs"
    )
    to_grid = Transformer.from_crs(
        geographic, CRS.from_wkt(metadata["crs"]), always_xy=True
    )
    x, y = grid_cell_centres(metadata)
    centre_x, centre_y = to_grid.transform(lon, lat)
    near = np.flatnonzero(
        (centre_x >= x.min() - 600.0)
        & (centre_x <= x.max() + 600.0)
        & (centre_y >= y.min() - 600.0)
        & (centre_y <= y.max() + 600.0)
    )
    vertices = prp["polar_vertices_km"].astype(np.float64)[near]
    norm = np.linalg.norm(vertices, axis=2)
    v_lat = np.degrees(np.arcsin(np.clip(vertices[:, :, 2] / norm, -1.0, 1.0)))
    v_lon = np.degrees(np.arctan2(vertices[:, :, 1], vertices[:, :, 0]))
    vx, vy = to_grid.transform(v_lon.ravel(), v_lat.ravel())
    vertices_xy = np.stack(
        [np.asarray(vx).reshape(v_lat.shape), np.asarray(vy).reshape(v_lat.shape)],
        axis=2,
    )
    return {
        "near": near,
        "area_km2": prp["area_km2"].astype(np.float64)[index][near],
        "assignment": assign_cells_to_facets(vertices_xy, x, y),
        # index first, THEN near: `near` addresses the polar subset, not the
        # full 2.88 M-row mesh. Indexing the full array with subset positions
        # silently reads the wrong triangles.
        "reference_c": kelvin_to_c(
            prp["temp_max_k"].astype(np.float64)[index][near]
        ),
    }


def test_the_window_holds_only_a_few_dozen_facets_and_the_test_says_so(window_facets):
    """The small-n limit is an assertion, not a footnote.

    A 2.5 km window against a ~544 m product cannot yield a large sample.
    If this ever passes with thousands of facets, someone has interpolated
    the coarse product onto our 5 m grid and manufactured sample size.
    """
    counts = np.bincount(
        window_facets["assignment"][window_facets["assignment"] >= 0].ravel(),
        minlength=window_facets["near"].size,
    )
    covered = int(np.sum(counts > 0))
    assert 20 < covered < 200, f"{covered} facets cover the window"


def test_every_grid_cell_lands_in_exactly_one_facet(window_facets, grids):
    assignment = window_facets["assignment"]
    assert assignment.shape == grids["thermal"].shape
    # The mesh tiles the surface, so with a one-facet margin every cell is
    # covered; an uncovered cell means the projection or the margin is wrong.
    assert np.all(assignment >= 0)


def test_each_facet_aggregates_hundreds_of_our_cells(window_facets, grids):
    _, counts = aggregate_to_facets(
        grids["thermal"],
        window_facets["assignment"],
        window_facets["near"].size,
        how="mean",
    )
    used = counts[counts > 0]
    # (544 m / 5 m)^2 / 2 is of order 5 000 cells per triangle.
    assert np.median(used) > 500


def test_all_three_candidates_are_measured_against_the_same_reference(
    window_facets, grids
):
    """C5 publishes three RMSEs, not one. This pins that all three are
    computed, against the same facets, with the sample size reported."""
    sunlit = np.asarray(grids["thermal_sunlit_peak"], dtype=np.float64)
    shadow = np.asarray(grids["shadow_ratio"], dtype=np.float64)
    candidates = {
        "A": sunlit,
        "B": np.asarray(annual_peak_c(sunlit, shadow), dtype=np.float64),
        "C": np.asarray(shadowed_equilibrium_c(sunlit, shadow), dtype=np.float64),
    }
    aggregated = {}
    for name, field in candidates.items():
        values, _ = aggregate_to_facets(
            field, window_facets["assignment"], window_facets["near"].size, how="mean"
        )
        aggregated[name] = values
    results = compare_candidates(aggregated, window_facets["reference_c"])

    assert set(results) == {"A", "B", "C"}
    counts = {r["n_compared"] for r in results.values()}
    assert len(counts) == 1, "candidates compared against different samples"
    for name, stats in results.items():
        assert stats["rmse_c"] is not None and np.isfinite(stats["rmse_c"]), name
        low, high = stats["rmse_ci95_c"]
        assert low <= stats["rmse_c"] <= high, name
    # The cold-end equilibrium is not an annual maximum, so it must be the
    # worst match of the three. If it ever wins, the statistics have been
    # mixed up somewhere upstream.
    assert results["C"]["rmse_c"] > results["A"]["rmse_c"]
    assert results["C"]["rmse_c"] > results["B"]["rmse_c"]


def test_our_psr_floor_is_colder_than_anything_diviner_reports_in_the_window(
    window_facets,
):
    """The C5 finding, pinned so it cannot quietly stop being true.

    ``annual_peak_c`` pins every never-lit cell to PSR_ANNUAL_MAX_K. In the
    Site11 window Diviner's coldest facet is far warmer than that, which is
    what drives candidate B's extra cold bias. Recorded here as a fact about
    the two products; C5 does NOT move the constant.
    """
    # Only the facets that actually cover our cells -- the ones the report
    # compares. Facets in the one-facet margin whose footprint misses the
    # window are not part of any statistic and must not be part of this one.
    counts = np.bincount(
        window_facets["assignment"][window_facets["assignment"] >= 0].ravel(),
        minlength=window_facets["near"].size,
    )
    compared = window_facets["reference_c"][counts > 0]
    coldest_k = float(compared.min()) + 273.15
    assert coldest_k > PSR_ANNUAL_MAX_K
    assert coldest_k - PSR_ANNUAL_MAX_K > 40.0


def test_diviner_does_report_facets_below_our_floor_further_poleward(prp):
    """...and the same floor is too WARM elsewhere, which is the other half
    of the finding. A single constant cannot be both, and saying only one
    would be a selective reading of the same product."""
    lat = prp["lat_deg"].astype(np.float64)
    peak = prp["temp_max_k"].astype(np.float64)
    deep = lat <= -88.0
    assert np.any(peak[deep] < PSR_ANNUAL_MAX_K)
    assert peak[deep].min() < 50.0


# ── the bit-equality claim ──────────────────────────────────────────────────


@pytest.mark.parametrize("rover_id", list(V5_COST_SHA256))
def test_c5_moved_no_cost_cell_at_all(grids, rover_id):
    """C5 is a validation feature: it reads, it never writes.

    The proof is the same lock C4 left behind -- if the checked-in v5 cost
    digest still matches, no route number can have changed, because the
    planner's entire input is this grid.
    """
    assert _digest(grids_for_rover(grids, rover_id)["cost"]) == V5_COST_SHA256[rover_id]


def test_c5_did_not_bump_the_cost_model_id():
    assert COST_MODEL_ID.endswith("_v5")


def test_c5_did_not_promote_any_layer_validity(grids):
    """Adding a measured/derived NASA reference must not upgrade our labels.

    C4 settled this: the weakest input still governs. A good RMSE buys the
    thermal layer a stated error band, not a better validity label.
    """
    validity = grids["metadata"]["layer_validity"]
    assert validity["thermal"] == "DERIVED"
    assert validity["cost"] == "DERIVED"
    assert "MEASURED" not in (validity["thermal"], validity["thermal_min"])


def test_edge_clipped_facets_exist_and_are_excluded_from_the_headline(
    window_facets, grids
):
    """The window edge really does clip facets, and it really does matter.

    A facet's Diviner value describes its whole ~0.128 km^2 triangle. The
    ones the window cuts through are only partly visible to us, and including
    them makes the agreement look BETTER than it is -- the flattering
    direction, which is exactly the direction C5 must not drift in.
    """
    _, counts = aggregate_to_facets(
        grids["thermal"],
        window_facets["assignment"],
        window_facets["near"].size,
        how="mean",
    )
    coverage = facet_coverage_fraction(
        counts, window_facets["area_km2"], grids["metadata"]["resolution_m"]
    )
    touched = counts > 0
    assert coverage[touched].min() < 0.1, "expected at least one thin sliver facet"
    assert np.sum(touched & (coverage < 0.5)) >= 10

    sunlit = np.asarray(grids["thermal_sunlit_peak"], dtype=np.float64)
    shadow = np.asarray(grids["shadow_ratio"], dtype=np.float64)
    modelled, _ = aggregate_to_facets(
        np.asarray(annual_peak_c(sunlit, shadow), dtype=np.float64),
        window_facets["assignment"],
        window_facets["near"].size,
        how="mean",
    )
    reference = window_facets["reference_c"]

    def rmse(mask):
        stats = compare_candidates(
            {"B": np.where(mask, modelled, np.nan)}, np.where(mask, reference, np.nan)
        )
        return stats["B"]["rmse_c"], stats["B"]["n_compared"]

    loose_rmse, loose_n = rmse(touched)
    strict_rmse, strict_n = rmse(touched & (coverage >= 0.5))
    assert strict_n < loose_n, "the filter must actually drop facets"
    assert strict_rmse > loose_rmse, (
        "including sliver facets flattered the RMSE; if this ever reverses, "
        "re-derive which subset is the honest one before changing the threshold"
    )
