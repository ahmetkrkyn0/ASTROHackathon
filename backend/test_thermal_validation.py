"""Thermal model vs. reference comparison tests (pure function, no data file)."""

from __future__ import annotations

import numpy as np
import pytest

from app.thermal_validation import thermal_comparison


def test_identical_grids_have_zero_error():
    grid = np.array([[-60.0, -80.0], [-40.0, -120.0]])
    result = thermal_comparison(grid, grid)
    assert result["rmse_c"] == pytest.approx(0.0, abs=1e-9)
    assert result["mae_c"] == pytest.approx(0.0, abs=1e-9)
    assert result["bias_c"] == pytest.approx(0.0, abs=1e-9)


def test_constant_offset_is_captured_as_bias_and_rmse():
    model = np.full((3, 3), -60.0)
    reference = np.full((3, 3), -50.0)
    result = thermal_comparison(model, reference)
    assert result["bias_c"] == pytest.approx(-10.0)
    assert result["rmse_c"] == pytest.approx(10.0)


def test_nan_cells_are_excluded_from_the_comparison():
    model = np.array([[-60.0, np.nan], [-40.0, -120.0]])
    reference = np.array([[-55.0, -70.0], [-40.0, np.nan]])
    result = thermal_comparison(model, reference)
    assert result["n_compared"] == 2


def test_shape_mismatch_is_rejected():
    with pytest.raises(ValueError):
        thermal_comparison(np.zeros((2, 2)), np.zeros((3, 3)))


def test_all_nan_grids_report_zero_compared_and_no_crash():
    model = np.full((2, 2), np.nan)
    reference = np.full((2, 2), np.nan)
    result = thermal_comparison(model, reference)
    assert result["n_compared"] == 0
    assert result["rmse_c"] is None


def test_misclassification_counts_only_disagreements_at_the_threshold():
    """Model says traversable (-140 > -150), reference says blocked (-160)."""
    model = np.array([[-140.0]])
    reference = np.array([[-160.0]])
    result = thermal_comparison(model, reference, traversable_threshold_c=-150.0)
    assert result["misclassified_traversable_pct"] == pytest.approx(100.0)


def test_misclassification_is_zero_when_thresholds_agree():
    model = np.array([[-140.0, -160.0]])
    reference = np.array([[-135.0, -170.0]])
    result = thermal_comparison(model, reference, traversable_threshold_c=-150.0)
    assert result["misclassified_traversable_pct"] == pytest.approx(0.0)


# ── C5: the Diviner PRP comparison helpers ─────────────────────────────────


def test_spearman_is_none_when_undefined():
    from app.thermal_validation import spearman_rho

    assert spearman_rho([1.0, 2.0], [1.0, 2.0]) is None  # fewer than 3 pairs
    assert spearman_rho([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None  # constant side
    assert spearman_rho([1.0, 2.0, 3.0], [np.nan, np.nan, 1.0]) is None


def test_spearman_is_rank_based_not_value_based():
    from app.thermal_validation import spearman_rho

    a = np.array([1.0, 2.0, 3.0, 4.0])
    assert spearman_rho(a, a**3) == pytest.approx(1.0)
    assert spearman_rho(a, -(a**3)) == pytest.approx(-1.0)


def test_spearman_ignores_pairs_with_a_nan_on_either_side():
    from app.thermal_validation import spearman_rho

    a = np.array([1.0, 2.0, 3.0, 4.0, np.nan])
    b = np.array([1.0, 2.0, 3.0, 4.0, 99.0])
    assert spearman_rho(a, b) == pytest.approx(1.0)


def test_error_statistics_agrees_with_thermal_comparison_on_shared_keys():
    from app.thermal_validation import error_statistics

    model = np.array([[-60.0, -80.0], [-40.0, -120.0]])
    reference = np.array([[-62.0, -75.0], [-44.0, -118.0]])
    base = thermal_comparison(model, reference)
    rich = error_statistics(model, reference)
    for key in base:
        assert rich[key] == base[key], key
    assert rich["spearman"] is not None
    assert rich["rmse_ci95_c"][0] <= rich["rmse_c"] <= rich["rmse_ci95_c"][1]


def test_rmse_interval_narrows_as_the_sample_grows():
    from app.thermal_validation import rmse_ci95

    rng = np.random.default_rng(0)
    small = rmse_ci95(rng.normal(0.0, 10.0, 20))
    large = rmse_ci95(rng.normal(0.0, 10.0, 20000))
    assert (small[1] - small[0]) > (large[1] - large[0])
    assert rmse_ci95(np.array([1.0])) is None


def test_triangle_area_of_a_known_right_triangle():
    from app.thermal_validation import triangle_areas_km2

    tri = np.array([[[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [0.0, 4.0, 0.0]]])
    assert triangle_areas_km2(tri)[0] == pytest.approx(6.0)
    with pytest.raises(ValueError):
        triangle_areas_km2(np.zeros((2, 3)))


def test_triangle_area_is_independent_of_vertex_order():
    from app.thermal_validation import triangle_areas_km2

    a = np.array([[[1.0, 0.0, 2.0], [0.0, 3.0, 1.0], [2.0, 2.0, 0.0]]])
    b = a[:, [2, 0, 1], :]
    assert triangle_areas_km2(a)[0] == pytest.approx(triangle_areas_km2(b)[0])


def test_cold_trap_area_sums_only_cold_poleward_triangles():
    from app.thermal_validation import cold_trap_area_check

    lat = np.array([-85.0, -85.0, -75.0, -81.0])
    temp_max = np.array([100.0, 200.0, 50.0, 109.9])
    area = np.array([1000.0, 5000.0, 9000.0, 2000.0])
    result = cold_trap_area_check(lat, temp_max, area)
    # Only rows 0 and 3 qualify: cold AND poleward. Row 2 is cold but equatorward.
    assert result["derived_area_km2"] == pytest.approx(3000.0)
    assert result["n_cold_triangles"] == 2
    assert result["n_poleward_triangles"] == 3
    assert result["poleward_area_km2"] == pytest.approx(8000.0)
    assert result["quoted_area_km2"] == 1.3e4


def test_cold_trap_check_reports_the_difference_without_hiding_it():
    from app.thermal_validation import cold_trap_area_check

    lat = np.array([-85.0])
    result = cold_trap_area_check(lat, np.array([50.0]), np.array([1.3e4]))
    assert result["difference_pct"] == pytest.approx(0.0)
    doubled = cold_trap_area_check(lat, np.array([50.0]), np.array([2.6e4]))
    assert doubled["difference_pct"] == pytest.approx(100.0)


def test_cold_trap_check_rejects_mismatched_shapes():
    from app.thermal_validation import cold_trap_area_check

    with pytest.raises(ValueError):
        cold_trap_area_check(np.zeros(3), np.zeros(2), np.zeros(3))


def test_point_in_triangle_assignment_is_exact_not_nearest_centre():
    from app.thermal_validation import assign_cells_to_facets

    # Two triangles splitting the unit square along its diagonal.
    tri = np.array(
        [
            [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
            [[1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        ]
    )
    x, y = np.meshgrid(np.array([0.1, 0.9]), np.array([0.1, 0.9]))
    out = assign_cells_to_facets(tri, x, y)
    assert out[0, 0] == 0  # (0.1, 0.1) lower-left triangle
    assert out[1, 1] == 1  # (0.9, 0.9) upper-right triangle
    # A point outside both belongs to neither.
    far = assign_cells_to_facets(tri, np.array([[5.0]]), np.array([[5.0]]))
    assert far[0, 0] == -1


def test_aggregation_mean_and_max_differ_and_empty_facets_stay_nan():
    from app.thermal_validation import aggregate_to_facets

    values = np.array([10.0, 20.0, 30.0, np.nan])
    assignment = np.array([0, 0, 0, 1])
    mean, counts = aggregate_to_facets(values, assignment, 3, how="mean")
    top, _ = aggregate_to_facets(values, assignment, 3, how="max")
    assert mean[0] == pytest.approx(20.0)
    assert top[0] == pytest.approx(30.0)
    assert counts[0] == 3
    # Facet 1's only cell is NaN and facet 2 has none: both drop out.
    assert np.isnan(mean[1]) and counts[1] == 0
    assert np.isnan(mean[2]) and counts[2] == 0
    with pytest.raises(ValueError):
        aggregate_to_facets(values, assignment, 3, how="median")


def test_unassigned_cells_never_reach_a_facet():
    from app.thermal_validation import aggregate_to_facets

    values = np.array([10.0, 999.0])
    assignment = np.array([0, -1])
    mean, counts = aggregate_to_facets(values, assignment, 1, how="mean")
    assert mean[0] == pytest.approx(10.0) and counts[0] == 1


def test_compare_candidates_runs_every_candidate_against_one_reference():
    from app.thermal_validation import compare_candidates

    reference = np.array([-50.0, -60.0, -70.0])
    results = compare_candidates(
        {
            "exact": reference.copy(),
            "offset": reference + 5.0,
        },
        reference,
    )
    assert results["exact"]["rmse_c"] == pytest.approx(0.0)
    assert results["offset"]["bias_c"] == pytest.approx(5.0)
    assert set(results) == {"exact", "offset"}


def test_kelvin_to_c_matches_the_prp_label_units():
    from app.thermal_validation import kelvin_to_c

    assert kelvin_to_c(np.array([273.15]))[0] == pytest.approx(0.0)
    assert kelvin_to_c(np.array([110.0]))[0] == pytest.approx(-163.15)


def test_quoted_dictionaries_stay_separate_from_our_measurements():
    from app.thermal_validation import PRP_QUOTED, WILLIAMS_QUOTED

    # Their numbers, carried verbatim with a citation, never recomputed.
    assert PRP_QUOTED["data_set_id"] == "LRO-L-DLRE-5-PRP-V2.0"
    assert "thermal model fits" in PRP_QUOTED["nature_quote"]
    assert PRP_QUOTED["record_bytes"] == 210
    assert PRP_QUOTED["label_file_records"] == 2_880_000
    assert WILLIAMS_QUOTED["cold_trap_area_km2"] == 1.3e4
    assert WILLIAMS_QUOTED["cold_trap_peak_temperature_k"] == 110.0
    assert "2019JE006028" in WILLIAMS_QUOTED["citation"]


def test_grid_cell_centres_agree_with_grid_frame():
    from app.grid_frame import pixel_to_map_xy
    from app.thermal_validation import grid_cell_centres

    metadata = {
        "origin": {"x": 500.0, "y": 2000.0},
        "resolution_m": 5.0,
        "shape": [40, 40],
        "crs": "test",
    }
    x, y = grid_cell_centres(metadata)
    for row, col in ((0, 0), (17, 3), (39, 39)):
        expected_x, expected_y = pixel_to_map_xy(row, col, metadata)
        assert x[row, col] == pytest.approx(expected_x)
        assert y[row, col] == pytest.approx(expected_y)


def test_coverage_fraction_flags_facets_clipped_by_the_window_edge():
    from app.thermal_validation import facet_coverage_fraction

    # A 0.1 km^2 facet is 100 000 m^2 = 4 000 cells at 5 m.
    counts = np.array([4000, 2000, 80, 0])
    area = np.full(4, 0.1)
    coverage = facet_coverage_fraction(counts, area, 5.0)
    assert coverage[0] == pytest.approx(1.0)
    assert coverage[1] == pytest.approx(0.5)
    assert coverage[2] == pytest.approx(0.02)
    assert coverage[3] == pytest.approx(0.0)


def test_coverage_fraction_survives_a_zero_area_facet():
    from app.thermal_validation import facet_coverage_fraction

    coverage = facet_coverage_fraction(np.array([10, 10]), np.array([0.1, 0.0]), 5.0)
    assert np.all(np.isfinite(coverage))
    assert coverage[1] == 0.0
    with pytest.raises(ValueError):
        facet_coverage_fraction(np.zeros(3), np.zeros(2), 5.0)


def test_filtering_sliver_facets_actually_changes_the_comparison():
    """The reason the coverage filter exists, as an executable statement.

    Two well-covered facets our model matches badly, plus a sliver our model
    happens to match well. Including the sliver flatters the RMSE. The filter
    is what stops that from becoming the headline number.
    """
    from app.thermal_validation import error_statistics, facet_coverage_fraction

    model = np.array([-50.0, -50.0, -30.0])
    reference = np.array([-30.0, -30.0, -30.0])
    counts = np.array([4000, 4000, 80])
    coverage = facet_coverage_fraction(counts, np.full(3, 0.1), 5.0)

    unfiltered = error_statistics(model, reference)
    keep = coverage >= 0.5
    filtered = error_statistics(
        np.where(keep, model, np.nan), np.where(keep, reference, np.nan)
    )
    assert unfiltered["n_compared"] == 3
    assert filtered["n_compared"] == 2
    assert filtered["rmse_c"] > unfiltered["rmse_c"]


# ── the chi-square interval's precondition, and what to use instead ──────────


def test_block_bootstrap_widens_on_correlated_residuals_and_not_on_shuffled():
    """The control is the point: blocking must not widen an iid sample.

    A moving-block bootstrap that reported a wide interval for independent
    residuals would prove nothing about the band. So the same call is run on
    a correlated series and on a permuted copy of THAT SERIES -- same values,
    same blocking, dependence destroyed -- and only the first may widen.
    """
    from app.thermal_validation import rmse_ci95, rmse_ci95_block_bootstrap

    rng = np.random.default_rng(0)
    noise = rng.normal(0.0, 10.0, 4000)
    correlated = np.convolve(noise, np.ones(200) / 200.0, mode="same") * 14.0

    chi_square = rmse_ci95(correlated)
    blocked = rmse_ci95_block_bootstrap(correlated, n_blocks=50)
    shuffled = rmse_ci95_block_bootstrap(rng.permutation(correlated), n_blocks=50)

    assert (blocked[1] - blocked[0]) > 4.0 * (chi_square[1] - chi_square[0])
    assert (shuffled[1] - shuffled[0]) < 0.5 * (blocked[1] - blocked[0])


def test_block_bootstrap_is_deterministic_and_guards_degenerate_shapes():
    from app.thermal_validation import rmse_ci95_block_bootstrap

    rng = np.random.default_rng(1)
    sample = rng.normal(0.0, 5.0, 500)
    assert rmse_ci95_block_bootstrap(sample, n_blocks=25) == (
        rmse_ci95_block_bootstrap(sample, n_blocks=25)
    )
    assert rmse_ci95_block_bootstrap(np.array([1.0, 2.0])) is None
    assert rmse_ci95_block_bootstrap(sample, n_blocks=1) is None
    assert rmse_ci95_block_bootstrap(sample, n_blocks=501) is None


def test_lag_autocorrelation_separates_a_smooth_series_from_white_noise():
    from app.thermal_validation import lag_autocorrelation

    rng = np.random.default_rng(2)
    white = lag_autocorrelation(rng.normal(0.0, 1.0, 5000), lags=(1, 20))
    smooth = lag_autocorrelation(
        np.convolve(rng.normal(0.0, 1.0, 5000), np.ones(100) / 100.0, mode="same"),
        lags=(1, 20),
    )
    assert abs(white[1]) < 0.1 and abs(white[20]) < 0.1
    assert smooth[1] > 0.9 and smooth[20] > 0.5
    assert lag_autocorrelation(np.array([1.0, 2.0]), lags=(50,))[50] is None


# ── two RMSEs over one shared sample are paired ─────────────────────────────


def test_paired_difference_calls_a_real_gap_real_and_a_noise_gap_noise():
    from app.thermal_validation import paired_rmse_difference

    rng = np.random.default_rng(3)
    a = rng.normal(0.0, 10.0, 400)
    clear = paired_rmse_difference(a, a * 3.0)
    assert clear["difference_c"] > 0.0
    assert clear["interval_excludes_zero"]
    assert clear["share_b_worse"] > 0.99

    noise = paired_rmse_difference(a, rng.normal(0.0, 10.0, 400))
    assert not noise["interval_excludes_zero"]
    assert noise["difference_ci95_c"][0] < 0.0 < noise["difference_ci95_c"][1]


def test_paired_difference_refuses_unpaired_inputs():
    from app.thermal_validation import paired_rmse_difference

    with pytest.raises(ValueError, match="paired inputs must match"):
        paired_rmse_difference(np.zeros(5), np.zeros(6))
    assert paired_rmse_difference(np.zeros(2), np.zeros(2)) is None


# ── the model floor splits the comparison in two ────────────────────────────


def test_split_at_model_floor_separates_a_cancelling_pool():
    """Two opposite-signed populations must not average into 'near unbiased'."""
    from app.thermal_validation import split_at_model_floor

    floor = -140.0
    reference = np.concatenate([np.full(10, -200.0), np.full(90, -50.0)])
    model = np.concatenate([np.full(10, floor), np.full(90, -56.0)])

    split = split_at_model_floor(model, reference, floor)
    assert split["n_below_floor"] == 10
    assert split["pct_below_floor"] == pytest.approx(10.0)
    assert split["below_floor"]["bias_c"] == pytest.approx(60.0)
    assert split["at_or_above_floor"]["bias_c"] == pytest.approx(-6.0)
    # the pooled bias sits between the two and resembles neither
    assert abs(split["pooled"]["bias_c"]) < abs(split["below_floor"]["bias_c"])
    # and the unreachable tenth carries most of the squared error
    assert split["sse_share_below_floor_pct"] > 90.0


def test_split_at_model_floor_reports_no_split_when_nothing_is_below():
    from app.thermal_validation import split_at_model_floor

    reference = np.full(20, -50.0)
    split = split_at_model_floor(np.full(20, -60.0), reference, -140.0)
    assert split["n_below_floor"] == 0
    assert split["below_floor"] is None
    assert split["sse_share_below_floor_pct"] == pytest.approx(0.0)
    assert split["at_or_above_floor"]["n_compared"] == 20


# ── the provenance block must describe the cache it is printed beside ───────


def test_provenance_check_catches_a_meta_that_describes_another_build():
    from app.thermal_validation import check_prp_provenance

    lat = np.linspace(-90.0, -76.0, 1000)
    good = {"n_triangles": 1000, "lat_range_deg": [-90.0, -76.0]}
    assert check_prp_provenance(good, lat) == []

    stale = {"n_triangles": 7, "lat_range_deg": [11.0, 22.0]}
    problems = check_prp_provenance(stale, lat)
    assert len(problems) == 2
    assert "n_triangles" in problems[0] and "1,000" in problems[0]
    assert "lat_range_deg" in problems[1]


def test_provenance_check_names_missing_keys_rather_than_raising():
    from app.thermal_validation import check_prp_provenance

    problems = check_prp_provenance({}, np.linspace(-90.0, -80.0, 10))
    assert any("n_triangles" in p for p in problems)
    assert any("lat_range_deg" in p for p in problems)
