"""Pure-function tests for the binary terrain transport."""

import numpy as np
import pytest

from app.terrain import (
    BINARY_DTYPE,
    BINARY_LAYER_HEADERS,
    binary_layer_headers,
    encode_layer_f32,
    layer_stats,
    suggested_vertical_exaggeration,
    terrain_manifest,
)


def _grids():
    """A 4x3 stand-in grid set with both flavours of absent value."""
    elevation = np.array(
        [[100.0, 101.0, 102.0],
         [103.0, 104.0, 105.0],
         [106.0, 107.0, 108.0],
         [109.0, 110.0, 120.0]]
    )
    cost = np.array(
        [[0.5, 0.6, np.inf],
         [0.7, np.nan, 0.8],
         [0.9, 1.0, 1.1],
         [1.2, 1.3, 1.4]]
    )
    return {
        "elevation": elevation,
        "cost": cost,
        "traversable": np.isfinite(cost),
        "metadata": {
            "shape": [4, 3],
            "resolution_m": 5.0,
            "origin": {"x": -1.0, "y": 2.0},
            "crs": "PROJCS[...]",
            "window_offset": {"row": 0, "col": 700},
            "layer_validity": {"elevation": "MEASURED", "cost": "DERIVED"},
        },
    }


def test_encode_is_little_endian_float32_row_major():
    grid = np.arange(6, dtype=np.float64).reshape(2, 3)
    raw = encode_layer_f32(grid)
    assert len(raw) == 6 * 4
    back = np.frombuffer(raw, dtype=BINARY_DTYPE)
    # Row-major: the flat order is the row order, not the column order.
    assert back.tolist() == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]


def test_encode_collapses_infinity_to_nan():
    """+inf in `cost` marks an impassable cell. float32 would carry the
    infinity into a colour ramp or a vertex, which renders as a silent
    artefact rather than a visible hole."""
    grid = np.array([[1.0, np.inf], [-np.inf, np.nan]])
    back = np.frombuffer(encode_layer_f32(grid), dtype=BINARY_DTYPE)
    assert back[0] == 1.0
    assert np.isnan(back[1]) and np.isnan(back[2]) and np.isnan(back[3])


def test_encode_maps_bool_to_one_and_zero():
    back = np.frombuffer(
        encode_layer_f32(np.array([[True, False]])), dtype=BINARY_DTYPE
    )
    assert back.tolist() == [1.0, 0.0]


def test_layer_stats_ignores_non_finite():
    stats = layer_stats(np.array([[1.0, np.inf], [np.nan, 5.0]]))
    assert stats == {"min": 1.0, "max": 5.0, "nodata": 2, "cells": 4}


def test_layer_stats_all_nodata():
    stats = layer_stats(np.array([[np.nan, np.inf]]))
    assert stats["min"] is None and stats["max"] is None and stats["nodata"] == 2


def test_vertical_exaggeration_is_one_when_relief_already_reads():
    # The production site: 1063.8 m over 2500 m.
    assert suggested_vertical_exaggeration(1063.8, 2500.0) == 1.0


def test_vertical_exaggeration_snaps_up_a_readable_ladder():
    # 25 m over 2500 m is 1:100; reaching the 0.2 target needs 20x.
    assert suggested_vertical_exaggeration(25.0, 2500.0) == 20.0
    assert suggested_vertical_exaggeration(0.0, 2500.0) == 1.0


def test_headers_report_effective_resolution_not_source_resolution():
    grid = np.zeros((4, 3))
    headers = binary_layer_headers("elevation", grid, 4, 5.0, "MEASURED")
    assert headers["X-Layer-Resolution-M"] == repr(20.0)
    assert headers["X-Layer-Rows"] == "4" and headers["X-Layer-Cols"] == "3"
    assert headers["X-Layer-Validity"] == "MEASURED"


def test_every_header_the_encoder_sets_is_in_the_cors_allowlist():
    """A header the CORS middleware does not expose is invisible to the
    browser -- no error, just undefined. Keep the two lists in lockstep."""
    headers = binary_layer_headers(
        "cost", np.array([[np.inf, 1.0]]), 1, 5.0, "DERIVED"
    )
    for name in headers:
        assert name in BINARY_LAYER_HEADERS


def test_manifest_reports_grid_georeference_and_layers():
    manifest = terrain_manifest(_grids(), "lpr_1", "LPR-1")
    assert manifest["grid"] == {
        "rows": 4, "cols": 3, "resolution_m": 5.0,
        "span_m": [20.0, 15.0], "cells": 12,
    }
    assert manifest["georeference"]["row_axis"] == "north-to-south"
    assert manifest["georeference"]["window_offset"] == {"row": 0, "col": 700}
    assert manifest["elevation"]["relief_m"] == pytest.approx(20.0)
    assert manifest["binary_format"]["bytes_per_layer"] == 12 * 4
    assert manifest["layers"]["elevation"]["validity"] == "MEASURED"
    assert manifest["layers"]["elevation"]["units"] == "m"
    assert manifest["layers"]["cost"]["nodata"] == 2
    assert manifest["layers"]["cost"]["max"] == pytest.approx(1.4)


def test_manifest_binary_url_carries_the_caller_query():
    manifest = terrain_manifest(
        _grids(), "lpr_1", "LPR-1", binary_query="rover_id=lpr_1&w_slope=0.5"
    )
    assert manifest["layers"]["cost"]["binary_url"] == (
        "/api/layers/cost?format=f32&rover_id=lpr_1&w_slope=0.5"
    )


def test_sun_track_for_series_returns_one_entry_per_slice():
    """The shadow raster says WHERE it is dark; the Sun angle says WHY.

    A directional light placed from anything other than this series will
    disagree with the shadows it is supposed to be casting.
    """
    from app.illumination_series import sun_track_for_series

    metadata = {
        "shape": [500, 500],
        "resolution_m": 5.0,
        "origin": {"x": -15500.0, "y": -4000.0},
        "crs": "unknown",
    }
    try:
        track = sun_track_for_series(metadata, 4, 6.0, "2026-09-01T00:00:00")
    except Exception as exc:            # no NAIF kernels in this environment
        pytest.skip(f"SPICE unavailable: {exc}")

    assert len(track) == 4
    assert [entry["index"] for entry in track] == [0, 1, 2, 3]
    assert track[0]["utc"].startswith("2026-09-01T00:00:00")
    assert track[1]["utc"].startswith("2026-09-01T06:00:00")
    for entry in track:
        assert 0.0 <= entry["azimuth_grid_deg"] < 360.0
        assert 0.0 <= entry["azimuth_true_deg"] < 360.0
        # A polar site: the Sun grazes the horizon, it never climbs.
        assert -10.0 < entry["elevation_deg"] < 10.0

    # The Sun moves. A track that reports the same azimuth for every slice
    # would satisfy every assertion above and be useless.
    assert len({round(e["azimuth_true_deg"], 3) for e in track}) == 4
