"""Model-vs-reference statistics for a visibility fraction grid.

Pure function, synthetic grids: the real comparison against NASA's LOLA
average-Earth-visibility product runs in scripts/earth_visibility_validation.py
and writes its numbers to docs/research; this pins what those numbers mean.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.visibility_validation import visibility_comparison


def test_identical_grids_score_zero_error_and_unit_correlation():
    grid = np.linspace(0.0, 1.0, 16).reshape(4, 4)
    result = visibility_comparison(grid, grid)
    assert result["rmse"] == 0.0
    assert result["mae"] == 0.0
    assert result["bias"] == 0.0
    assert result["pearson_r"] == pytest.approx(1.0)
    assert result["n_compared"] == 16
    assert result["disagreement_pct"] == 0.0


def test_a_constant_offset_is_reported_as_bias_and_rmse():
    reference = np.linspace(0.0, 0.8, 16).reshape(4, 4)
    model = reference + 0.1
    result = visibility_comparison(model, reference)
    assert result["bias"] == pytest.approx(0.1)
    assert result["rmse"] == pytest.approx(0.1)
    assert result["mae"] == pytest.approx(0.1)
    assert result["pearson_r"] == pytest.approx(1.0)


def test_nan_cells_on_either_side_are_excluded():
    model = np.full((3, 3), 0.5)
    reference = np.full((3, 3), 0.5)
    model[0, 0] = np.nan
    reference[2, 2] = np.nan
    result = visibility_comparison(model, reference)
    assert result["n_compared"] == 7


def test_disagreement_counts_cells_on_opposite_sides_of_the_threshold():
    """The number that matters for planning: where one grid says "mostly
    linked" and the other says "mostly not"."""
    model = np.array([[0.9, 0.6], [0.4, 0.1]])
    reference = np.array([[0.9, 0.4], [0.6, 0.1]])
    result = visibility_comparison(model, reference, threshold=0.5)
    assert result["disagreement_pct"] == pytest.approx(50.0)
    assert result["model_mean"] == pytest.approx(0.5)
    assert result["reference_mean"] == pytest.approx(0.5)


def test_constant_grids_have_no_correlation_not_a_crash():
    result = visibility_comparison(np.full((2, 2), 0.3), np.full((2, 2), 0.3))
    assert result["pearson_r"] is None
    assert result["rmse"] == 0.0


def test_nothing_to_compare_is_reported_as_such():
    result = visibility_comparison(np.full((2, 2), np.nan), np.zeros((2, 2)))
    assert result["n_compared"] == 0
    assert result["rmse"] is None and result["pearson_r"] is None


def test_shape_mismatch_is_an_error():
    with pytest.raises(ValueError):
        visibility_comparison(np.zeros((2, 2)), np.zeros((3, 3)))


# ── block_mean: 5 m model cells -> the reference's 60 m pixels ─────────────


def test_block_mean_averages_full_blocks_and_drops_the_remainder():
    from app.visibility_validation import block_mean

    grid = np.arange(7 * 5, dtype=np.float64).reshape(7, 5)
    out = block_mean(grid, 3)
    assert out.shape == (2, 1)
    assert out[0, 0] == pytest.approx(grid[0:3, 0:3].mean())
    assert out[1, 0] == pytest.approx(grid[3:6, 0:3].mean())


def test_block_mean_ignores_nan_inside_a_block_but_keeps_an_all_nan_block_nan():
    from app.visibility_validation import block_mean

    grid = np.ones((4, 4))
    grid[0, 0] = np.nan
    grid[2:4, 2:4] = np.nan
    out = block_mean(grid, 2)
    assert out[0, 0] == pytest.approx(1.0)
    assert np.isnan(out[1, 1])


def test_block_mean_of_one_is_the_grid_itself():
    from app.visibility_validation import block_mean

    grid = np.random.default_rng(0).random((3, 4))
    np.testing.assert_array_equal(block_mean(grid, 1), grid)
