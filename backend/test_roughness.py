"""app.roughness (C4): the regional-ECDF roughness scale, projection equality,
the PSR-vs-shadow overlap statistic, the route summary and the response
block. Pure functions; no grids, no network."""

from __future__ import annotations

import numpy as np
import pytest

from app.roughness import (
    LDRM_BASELINE_M,
    LDRM_PRODUCT,
    LDRM_RESOLUTION_M,
    LPSR_PRODUCT,
    NAN_ROUGHNESS_F,
    PSR_CLAIM,
    ROUGHNESS_CLAIM,
    ROUGHNESS_LAYER_VALIDITY,
    ROUGHNESS_REFERENCES,
    ROUGHNESS_SCALE_VALIDITY,
    RoughnessScale,
    ldrm_url,
    lpsr_url,
    psr_shadow_overlap,
    roughness_block,
    route_roughness_summary,
    same_projection,
)

# The WKT metadata.json carries (P1 pipeline, GDAL "unnamed" names).
OUR_WKT = (
    'PROJCS["unnamed",GEOGCS["unnamed ellipse",DATUM["unknown",SPHEROID["unnamed",1737400,0]],'
    'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]]],'
    'PROJECTION["Polar_Stereographic"],PARAMETER["latitude_of_origin",-90],'
    'PARAMETER["central_meridian",0],PARAMETER["false_easting",0],PARAMETER["false_northing",0],'
    'UNIT["metre",1],AXIS["Easting",NORTH],AXIS["Northing",NORTH]]'
)
# The WKT the PGDA product 90 GeoTIFFs carry (read over /vsicurl/, 5 Sept 2026).
PGDA_WKT = (
    'PROJCS["Moon (2015) - Sphere / Ocentric / South Polar",GEOGCS["Moon (2015) - Sphere / Ocentric",'
    'DATUM["Moon (2015) - Sphere",SPHEROID["Moon (2015) - Sphere",1737400,0]],'
    'PRIMEM["Reference Meridian",0],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]]],'
    'PROJECTION["Polar_Stereographic"],PARAMETER["latitude_of_origin",-90],'
    'PARAMETER["central_meridian",0],PARAMETER["false_easting",0],PARAMETER["false_northing",0],'
    'UNIT["metre",1],AXIS["Easting",NORTH],AXIS["Northing",NORTH]]'
)
NORTH_WKT = PGDA_WKT.replace('PARAMETER["latitude_of_origin",-90]', 'PARAMETER["latitude_of_origin",90]')


def _scale(knots=(0.1, 0.5, 1.0, 2.0), probs=(0.0, 0.25, 0.75, 1.0)) -> RoughnessScale:
    return RoughnessScale.from_meta(
        {"kind": "regional_ecdf", "knots": list(knots), "probs": list(probs), "source": "test", "n_samples": 4}
    )


# ── RoughnessScale ──────────────────────────────────────────────────────────


def test_scale_round_trips_through_meta():
    scale = _scale()
    meta = scale.to_meta()
    assert meta["kind"] == "regional_ecdf"
    assert meta["validity"] == ROUGHNESS_SCALE_VALIDITY == "MODEL"
    assert meta["knots"] == [0.1, 0.5, 1.0, 2.0] and meta["probs"] == [0.0, 0.25, 0.75, 1.0]
    assert meta["n_samples"] == 4 and meta["source"] == "test"
    assert RoughnessScale.from_meta(meta) == scale


@pytest.mark.parametrize(
    "meta",
    [
        {"knots": [1.0], "probs": [0.5]},
        {"knots": [0.5, 1.0], "probs": [0.8, 0.2]},
        {"knots": [0.5, 1.0]},
        {"probs": [0.0, 1.0]},
        {"knots": [0.5, float("nan")], "probs": [0.0, 1.0]},
        {"knots": [0.5, 1.0], "probs": [0.0, 1.5]},
        None,
    ],
)
def test_scale_refuses_a_malformed_meta(meta):
    with pytest.raises(ValueError, match="scale"):
        RoughnessScale.from_meta(meta)


def test_equal_knots_are_merged_and_f_stays_monotone():
    # Quantile tables have ties (many zeros); the ECDF is right-continuous,
    # so an equal knot keeps the LAST probability.
    scale = RoughnessScale.from_meta(
        {"knots": [0.0, 0.0, 0.0, 0.4, 0.8], "probs": [0.0, 0.1, 0.3, 0.6, 1.0]}
    )
    assert scale.knots == (0.0, 0.4, 0.8) and scale.probs == (0.3, 0.6, 1.0)
    xs = np.linspace(-1.0, 2.0, 301)
    values = scale.f_grid(xs)
    assert np.all(np.diff(values) >= 0.0)


def test_f_is_bounded_and_clamps_outside_the_knots():
    scale = _scale()
    assert scale.f(0.05) == 0.0
    assert scale.f(5.0) == 1.0
    assert scale.f(0.5) == pytest.approx(0.25)
    assert scale.f(0.75) == pytest.approx(0.5)  # midway 0.5..1.0 -> 0.25..0.75
    values = scale.f_grid(np.linspace(-3.0, 30.0, 500))
    assert values.min() >= 0.0 and values.max() <= 1.0


def test_nan_roughness_reads_as_the_regional_median():
    scale = _scale()
    assert NAN_ROUGHNESS_F == 0.5
    assert scale.f(float("nan")) == 0.5
    assert scale.f(None) == 0.5
    grid = np.array([[0.5, np.nan], [np.inf, 2.0]])
    out = scale.f_grid(grid)
    assert out[0, 1] == 0.5 and out[1, 0] == 0.5
    assert out[0, 0] == pytest.approx(0.25) and out[1, 1] == 1.0


def test_grid_form_is_bit_equal_to_the_scalar_form():
    scale = RoughnessScale.from_meta(
        {"knots": list(np.linspace(0.05, 3.0, 201)), "probs": list(np.linspace(0.0, 1.0, 201) ** 0.7)}
    )
    rng = np.random.default_rng(4)
    values = rng.uniform(-0.5, 4.0, size=20_000)
    values[::97] = np.nan
    grid = scale.f_grid(values)
    scalar = np.array([scale.f(float(v)) for v in values])
    assert np.array_equal(grid, scalar)
    assert grid.dtype == np.float64


# ── projection equality ────────────────────────────────────────────────────


def test_same_projection_ignores_names_and_compares_parameters():
    assert same_projection(OUR_WKT, PGDA_WKT) is True
    assert same_projection(PGDA_WKT, PGDA_WKT) is True


def test_same_projection_rejects_a_different_pole():
    assert same_projection(OUR_WKT, NORTH_WKT) is False


def test_same_projection_rejects_a_different_radius():
    other = PGDA_WKT.replace("1737400", "1737000")
    assert same_projection(OUR_WKT, other) is False


# ── PSR vs shadow overlap ──────────────────────────────────────────────────


def _hand_made():
    psr = np.zeros((4, 4))
    psr[0, 0] = psr[0, 1] = psr[1, 0] = psr[3, 3] = 1.0  # 4 PSR cells
    shadow = np.full((4, 4), 0.3)
    shadow[0, 0] = shadow[0, 1] = shadow[1, 0] = 1.0  # 3 inside PSR
    shadow[2, 2] = 0.995  # dark outside PSR
    shadow[2, 3] = 0.99  # dark outside PSR (threshold inclusive)
    shadow[3, 3] = 0.8  # PSR cell our model calls lit-ish
    thermal_min = np.full((4, 4), -100.0)
    thermal_min[psr == 1.0] = -183.15
    return psr, shadow, thermal_min


def test_psr_shadow_overlap_by_hand():
    psr, shadow, thermal_min = _hand_made()
    stats = psr_shadow_overlap(psr, shadow, thermal_min=thermal_min, threshold=0.99)
    assert stats["threshold"] == 0.99
    assert stats["n_cells"] == 16 and stats["n_psr"] == 4 and stats["n_dark"] == 5
    assert stats["psr_fraction"] == pytest.approx(0.25)
    assert stats["n_intersection"] == 3 and stats["n_union"] == 6
    assert stats["jaccard"] == pytest.approx(0.5)
    assert stats["psr_recall"] == pytest.approx(0.75)
    assert stats["dark_precision"] == pytest.approx(0.6)
    assert stats["false_positive_fraction"] == pytest.approx(0.4)
    assert stats["mean_shadow_inside_psr"] == pytest.approx((1.0 + 1.0 + 1.0 + 0.8) / 4)
    assert stats["mean_shadow_outside_psr"] == pytest.approx((0.3 * 10 + 0.995 + 0.99) / 12)
    assert stats["thermal_min_median_inside_psr"] == pytest.approx(-183.15)
    assert stats["thermal_min_median_outside_psr"] == pytest.approx(-100.0)


def test_psr_shadow_overlap_without_thermal_and_with_empty_sets():
    psr = np.zeros((3, 3))
    shadow = np.zeros((3, 3))
    stats = psr_shadow_overlap(psr, shadow)
    assert stats["jaccard"] == 0.0
    assert stats["psr_recall"] is None and stats["dark_precision"] is None
    assert stats["false_positive_fraction"] is None
    assert stats["thermal_min_median_inside_psr"] is None
    assert stats["mean_shadow_inside_psr"] is None
    assert stats["n_psr"] == 0 and stats["n_dark"] == 0


def test_psr_shadow_overlap_rejects_a_shape_mismatch():
    with pytest.raises(ValueError, match="shape"):
        psr_shadow_overlap(np.zeros((2, 2)), np.zeros((3, 3)))


# ── route summary and block ────────────────────────────────────────────────


def test_route_roughness_summary_by_hand():
    summary = route_roughness_summary([0.5, 1.5, np.nan, 1.0], [0.2, 0.9, 0.5, 0.6], [0, 1, 1, 0])
    assert summary["n_cells"] == 4
    assert summary["mean_roughness_m"] == pytest.approx(1.0)  # NaN skipped
    assert summary["max_roughness_m"] == pytest.approx(1.5)
    assert summary["mean_f_roughness"] == pytest.approx(0.55)
    assert summary["cells_in_psr"] == 2
    assert summary["nan_cells"] == 1


def test_route_roughness_summary_of_an_empty_route_and_without_psr():
    summary = route_roughness_summary([], [], None)
    assert summary["n_cells"] == 0
    assert summary["mean_roughness_m"] is None and summary["max_roughness_m"] is None
    assert summary["mean_f_roughness"] is None and summary["cells_in_psr"] is None


def test_roughness_block_when_the_layer_is_absent():
    block = roughness_block(applied=False, weight=0.15, reason="no roughness_grid.npy")
    assert block["applied"] is False and block["route"] is None
    assert block["reason"] == "no roughness_grid.npy"
    assert block["validity"] == ROUGHNESS_LAYER_VALIDITY == "MEASURED"
    assert block["scale_validity"] == "MODEL"
    assert block["product"] == LDRM_PRODUCT and block["baseline_m"] == LDRM_BASELINE_M == 100
    assert block["resolution_m"] == LDRM_RESOLUTION_M == 50
    assert block["claim"] == ROUGHNESS_CLAIM


def test_roughness_block_when_applied_carries_the_route():
    route = route_roughness_summary([1.0], [0.8], [0])
    block = roughness_block(applied=True, weight=0.15, route=route)
    assert block["applied"] is True and block["weight"] == 0.15
    assert block["route"] == route and block["reason"] is None
    assert block["references"] == list(ROUGHNESS_REFERENCES)


# ── constants and claim limits ─────────────────────────────────────────────


def test_product_urls_follow_the_pgda_filename_format():
    assert ldrm_url() == "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDRM_80S_50MPP_ADJ_ROUGH_100M.TIF"
    assert ldrm_url(baseline_m=400) .endswith("LDRM_80S_50MPP_ADJ_ROUGH_400M.TIF")
    assert ldrm_url(kind="SLP", baseline_m=100).endswith("LDRM_80S_50MPP_ADJ_SLP_100M.TIF")
    assert ldrm_url(kind="H").endswith("LDRM_80S_50MPP_ADJ_H.TIF")
    assert lpsr_url() == f"https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/{LPSR_PRODUCT}.TIF"


def test_claims_state_the_limits():
    lowered = ROUGHNESS_CLAIM.lower()
    assert "not the roughness of the cell" in lowered
    assert "percentile" in lowered and "not a rover tolerance" in lowered
    assert "rock abundance" in lowered  # Diviner explicitly excluded
    assert "measured" in PSR_CLAIM.lower() and "not" in PSR_CLAIM.lower()
    assert any("10.3847/PSJ/acf3e1" in ref for ref in ROUGHNESS_REFERENCES)
    assert any("pgda.gsfc.nasa.gov/products/90" in ref for ref in ROUGHNESS_REFERENCES)


# ── the scale from a regional sample ───────────────────────────────────────


def test_ecdf_scale_from_sample_is_the_empirical_cdf():
    from app.roughness import ecdf_scale_from_sample

    rng = np.random.default_rng(7)
    sample = rng.uniform(0.0, 2.0, 200_000)
    sample[:100] = np.nan  # non-finite values are dropped, not counted
    scale = ecdf_scale_from_sample(sample, n_knots=201, source="test tiles")
    assert scale.kind == "regional_ecdf" and scale.source == "test tiles"
    assert scale.n_samples == 200_000 - 100
    assert 2 <= len(scale.knots) <= 201
    assert scale.f(float(np.nanmin(sample))) == 0.0 and scale.f(float(np.nanmax(sample))) == 1.0
    assert scale.f(1.0) == pytest.approx(0.5, abs=0.01)
    assert scale.f(0.5) == pytest.approx(0.25, abs=0.01)
    assert scale.f(-1.0) == 0.0 and scale.f(5.0) == 1.0


def test_ecdf_scale_from_sample_refuses_a_degenerate_sample():
    from app.roughness import ecdf_scale_from_sample

    with pytest.raises(ValueError, match="sample"):
        ecdf_scale_from_sample(np.array([np.nan, np.nan]))
    with pytest.raises(ValueError, match="sample"):
        ecdf_scale_from_sample(np.full(50, 0.7))  # one distinct value: no scale
