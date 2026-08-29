"""Grid <-> map-frame conversion tests.

Two things are pinned here and nothing else in the repo pins them:

1. The row-sign convention (K1). Faz 2's C2 finding was three copies of one
   formula drifting apart; these tests compare against corridor's live
   implementation rather than asserting a literal sign, so a future flip in
   either place fails here instead of silently diverging. (Faz 4 revision, R2.)
2. The grid_map orientation (K3). grid_map counts indices AGAINST the axes,
   so a correct message needs a transpose + flip, not just column-major
   flattening. The round-trip test alone cannot catch that -- it is
   self-inverse by construction -- so the orientation is asserted against an
   explicit expected matrix. (Faz 4 revision, R3.)
"""

from __future__ import annotations

import numpy as np
import pytest

from app.corridor import _pixel_to_metres
from app.grid_frame import (
    from_grid_map_matrix,
    from_multiarray_layout,
    grid_map_info,
    map_xy_to_pixel,
    pixel_to_map_xy,
    to_grid_map_matrix,
    to_multiarray_layout,
)

# Deliberately NON-SQUARE and not the production grid: a square fixture makes
# a swapped size_x/size_y invisible, and Global Constraints allow synthetic
# fixtures. rows=4, cols=6.
METADATA = {
    "origin": {"x": 1000.0, "y": 500.0},
    "resolution_m": 10.0,
    "shape": [4, 6],
}


# ── K1: the row-sign convention, pinned against corridor ────────────────────

def test_row_axis_points_south():
    """Increasing row must DECREASE northing (Faz 2 C2)."""
    _, y0 = pixel_to_map_xy(0, 0, METADATA)
    _, y1 = pixel_to_map_xy(1, 0, METADATA)
    assert y1 < y0


def test_column_axis_points_east():
    x0, _ = pixel_to_map_xy(0, 0, METADATA)
    x1, _ = pixel_to_map_xy(0, 1, METADATA)
    assert x1 > x0


def test_corridor_delegates_to_grid_frame():
    """After Step 4 corridor calls grid_frame, so this cannot fail by
    coincidence -- it fails if someone re-inlines a private copy of the
    formula in corridor.py, which is exactly how C2 happened."""
    for row, col in ((0, 0), (1, 3), (3, 5)):
        assert pixel_to_map_xy(row, col, METADATA) == pytest.approx(
            _pixel_to_metres(row, col, 1000.0, 500.0, 10.0)
        )


def test_matches_the_serializer_projection_independently():
    """The real anti-divergence check.

    serializer.pixel_to_lonlat keeps its OWN copy of the row-sign formula and
    then projects to WGS84 -- it does not delegate. Projecting its answer back
    to metres must land on grid_frame's answer. A sign flip in EITHER module
    fails here, which the corridor comparison above can no longer detect once
    corridor delegates. (Faz 4 revision, R2.)
    """
    from app.serializer import _inv, pixel_to_lonlat

    for row, col in ((0, 0), (1, 3), (3, 5)):
        lon, lat = pixel_to_lonlat(row, col, METADATA)
        x_back, y_back = _inv.transform(lon, lat)
        assert (x_back, y_back) == pytest.approx(
            pixel_to_map_xy(row, col, METADATA), abs=1e-3
        )


def test_origin_pixel_maps_to_the_metadata_origin():
    assert pixel_to_map_xy(0, 0, METADATA) == pytest.approx((1000.0, 500.0))


def test_pixel_round_trip():
    for row, col in ((0, 0), (2, 4), (3, 5)):
        x, y = pixel_to_map_xy(row, col, METADATA)
        assert map_xy_to_pixel(x, y, METADATA) == (row, col)


def test_map_xy_outside_the_grid_is_rejected():
    with pytest.raises(ValueError):
        map_xy_to_pixel(1.0e9, 1.0e9, METADATA)


def test_map_xy_north_of_the_origin_is_rejected():
    """Row 0 is the northernmost cell; anything north of it is off-grid.
    With the pre-C2 '+' sign this point would have mapped to a valid row."""
    x, y = pixel_to_map_xy(0, 0, METADATA)
    with pytest.raises(ValueError):
        map_xy_to_pixel(x, y + 5 * 10.0, METADATA)


# ── K4: grid_map geometry ───────────────────────────────────────────────────

def test_grid_map_info_extent_follows_rows_and_columns():
    info = grid_map_info(METADATA)
    assert info["resolution"] == pytest.approx(10.0)
    assert info["length_x"] == pytest.approx(6 * 10.0)   # cols -> easting
    assert info["length_y"] == pytest.approx(4 * 10.0)   # rows -> northing


def test_grid_map_centre_puts_cell_centres_on_pixel_positions():
    """Derived in K4: the grid_map cell centre for our pixel (r, c) must be
    exactly pixel_to_map_xy(r, c), otherwise the published Path sits half a
    cell off the published terrain."""
    info = grid_map_info(METADATA)
    rows, cols = METADATA["shape"]
    resolution = METADATA["resolution_m"]
    for row, col in ((0, 0), (3, 5), (2, 1)):
        i = cols - 1 - col
        j = row
        x = info["pose_x"] + info["length_x"] / 2.0 - (i + 0.5) * resolution
        y = info["pose_y"] + info["length_y"] / 2.0 - (j + 0.5) * resolution
        assert (x, y) == pytest.approx(pixel_to_map_xy(row, col, METADATA))


# ── K3: orientation ─────────────────────────────────────────────────────────

def test_grid_map_matrix_is_transposed_and_flipped():
    """The core of K3, asserted against an explicit expectation.

    A round-trip test cannot catch a wrong orientation (it is self-inverse),
    and a square fixture cannot catch a swapped axis (shapes still match).
    Both holes are closed here.
    """
    array = np.arange(12, dtype=np.float32).reshape(3, 4)  # rows=3, cols=4
    matrix = to_grid_map_matrix(array)
    assert matrix.shape == (4, 3)  # (cols, rows) -- NOT (3, 4)
    assert np.array_equal(matrix, np.flipud(array.T))
    # Spot-check the corner semantics: grid_map index (0, 0) is the cell with
    # the LARGEST x and LARGEST y, i.e. our north-east corner = array[0, -1].
    assert matrix[0, 0] == array[0, -1]


def test_grid_map_matrix_round_trip():
    array = np.arange(12, dtype=np.float32).reshape(3, 4)
    assert np.array_equal(from_grid_map_matrix(to_grid_map_matrix(array)), array)


def test_multiarray_layout_is_column_major_with_grid_map_labels():
    array = np.arange(12, dtype=np.float32).reshape(3, 4)  # rows=3, cols=4
    dims, flat = to_multiarray_layout(array)
    labels = [label for label, _size, _stride in dims]
    assert labels == ["column_index", "row_index"]
    # dim[0] is the Eigen OUTER size = grid_map matrix columns = our rows.
    assert dims[0] == ("column_index", 3, 12)
    assert dims[1] == ("row_index", 4, 4)


def test_multiarray_data_matches_the_documented_short_form():
    """K3 states two equivalent formulations; if they ever disagree the
    derivation is wrong."""
    array = np.arange(12, dtype=np.float32).reshape(3, 4)
    _dims, flat = to_multiarray_layout(array)
    assert np.array_equal(flat, np.flipud(array.T).flatten(order="F"))
    assert np.array_equal(flat, np.fliplr(array).flatten(order="C"))


def test_multiarray_round_trip_preserves_an_asymmetric_pattern():
    array = np.zeros((4, 6), dtype=np.float32)
    array[0, :] = 1.0    # a single lit north row
    array[:, 0] = 2.0    # a single lit west column
    dims, flat = to_multiarray_layout(array)
    assert np.array_equal(from_multiarray_layout(dims, flat), array)


def test_north_row_lands_on_the_high_y_edge_of_the_message():
    """The rotation test with teeth: a lit NORTH row must come back as the
    grid_map cells with the largest y, not the largest x."""
    rows, cols = 4, 6
    array = np.zeros((rows, cols), dtype=np.float32)
    array[0, :] = 1.0  # north row
    matrix = to_grid_map_matrix(array)
    # j = row, so the north row is j = 0 -> the whole first COLUMN of the
    # grid_map matrix, across every i.
    assert np.all(matrix[:, 0] == 1.0)
    assert np.all(matrix[:, 1:] == 0.0)


def test_non_square_grid_does_not_silently_swap_axes():
    array = np.zeros((4, 6), dtype=np.float32)
    dims, flat = to_multiarray_layout(array)
    assert dims[0][1] == 4   # column_index size == our rows
    assert dims[1][1] == 6   # row_index size    == our cols
    assert flat.size == 24
