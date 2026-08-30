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
