"""Contract tests for the 3-D data path, on synthetic grids.

Mirrors the split the repo already uses for the 4-D planner:
test_plan_4d_endpoint.py exercises the contract on an injected fixture and
test_plan_4d_real_grid.py asserts about the checked-in production grid.
The `.npy` artefacts are gitignored, so anything asserting 500x500 belongs
in test_terrain_real_grid.py, not here -- this file must pass on a fresh
clone with no pipeline output.

The fixture is deliberately 8x6, not square: a row/column transposition in
the encoder or the headers produces a plausible-looking square grid and
survives every test written against one.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient  # noqa: E402

from app.cost_engine import COST_MODEL_ID  # noqa: E402
from app.data_loader import derive_thermal_fields  # noqa: E402
from app.main import app  # noqa: E402
from app.terrain import BINARY_DTYPE, BINARY_LAYER_HEADERS  # noqa: E402

ROWS, COLS = 8, 6
SHAPE = (ROWS, COLS)


def _make_grids() -> dict:
    """A small, fully specified grid set with one impassable cell.

    Cell (0, 0) is pitched at 40 deg, past LPR-1's 25 deg limit, so the cost
    grid the endpoint recomputes carries a genuine +inf there. Writing the
    infinity into the fixture's own `cost` array would not survive: every
    request for `cost` or `traversable` goes through `grids_for_rover`,
    which derives both from slope and thermal for the rover being asked
    about. The encoder's infinity handling has to be provoked the way
    production provokes it -- with terrain, not with a planted value.
    """
    rng = np.arange(ROWS * COLS, dtype=np.float64).reshape(SHAPE)
    elevation = 100.0 + rng
    slope = 2.0 + (rng % 7)
    slope[0, 0] = 40.0
    shadow = np.clip(0.2 + (rng % 5) / 10.0, 0.0, 1.0)
    sunlit_peak = np.full(SHAPE, 20.0)
    thermal, thermal_min = derive_thermal_fields(sunlit_peak, shadow)

    cost = 0.4 + (rng % 3) / 10.0
    cost[0, 0] = np.inf
    traversable = np.isfinite(cost)

    return {
        "elevation": elevation,
        "slope": slope,
        "aspect": (rng * 3.0) % 360.0,
        "thermal": np.asarray(thermal, dtype=np.float64),
        "thermal_min": np.asarray(thermal_min, dtype=np.float64),
        "thermal_sunlit_peak": sunlit_peak,
        "shadow_ratio": shadow,
        "cost": cost,
        "traversable": traversable,
        "metadata": {
            "resolution_m": 5.0,
            "shape": list(SHAPE),
            "crs": "moon_sp",
            "source": "synthetic_test",
            "origin": {"x": -100.0, "y": 40.0},
            "window_offset": {"row": 0, "col": 0},
            "cost_weights": {
                "w_slope": 0.409,
                "w_energy": 0.259,
                "w_shadow": 0.142,
                "w_thermal": 0.190,
            },
            "cost_model": COST_MODEL_ID,
            "default_rover_id": "lpr_1",
            "thermal_field": "sunlit_peak",
            "thermal_shadow_coupled": True,
            "layer_validity": {
                "elevation": "MEASURED",
                "slope": "DERIVED",
                "aspect": "DERIVED",
                "shadow_ratio": "DERIVED",
                "thermal": "DERIVED",
                "thermal_min": "DERIVED",
                "traversable": "DERIVED",
                "cost": "DERIVED",
            },
        },
    }


@pytest.fixture(autouse=True)
def _grids():
    """app.state is the single grid store (backend review #7)."""
    app.state.grids = _make_grids()
    yield
    app.state.grids = None


client = TestClient(app, raise_server_exceptions=True)


def _as_array(payload) -> np.ndarray:
    return np.array(
        [[np.nan if v is None else v for v in row] for row in payload["data"]],
        dtype=np.float32,
    )


# -- the additive promise ----------------------------------------------------

def test_json_layer_is_unchanged_without_format():
    """The whole promise of this feature is that it is additive."""
    plain = client.get("/api/layers/slope")
    explicit = client.get("/api/layers/slope?format=json")
    assert plain.status_code == 200
    assert plain.json() == explicit.json()
    assert plain.headers["content-type"].startswith("application/json")


def test_unknown_format_is_rejected():
    assert client.get("/api/layers/slope?format=f64").status_code == 422


# -- the wire format ---------------------------------------------------------

def test_binary_layer_returns_exactly_rows_times_cols_float32():
    response = client.get("/api/layers/elevation?format=f32")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert int(response.headers["X-Layer-Rows"]) == ROWS
    assert int(response.headers["X-Layer-Cols"]) == COLS
    assert len(response.content) == ROWS * COLS * 4
    assert response.headers["X-Layer-Endian"] == "little"
    assert response.headers["X-Layer-Order"] == "row-major"


def test_binary_rows_and_cols_are_not_interchangeable():
    """The fixture is 8x6. A transposed encoder passes on a square grid."""
    response = client.get("/api/layers/elevation?format=f32")
    values = np.frombuffer(response.content, dtype=BINARY_DTYPE).reshape(ROWS, COLS)
    # elevation is 100 + arange, so row-major order is strictly increasing.
    assert values[0, 0] == pytest.approx(100.0)
    assert values[0, COLS - 1] == pytest.approx(100.0 + COLS - 1)
    assert values[1, 0] == pytest.approx(100.0 + COLS)


def test_binary_matches_json_values():
    """Two representations of one grid must agree, or the 3-D view and the
    2-D map are showing different terrain."""
    payload = client.get("/api/layers/slope").json()
    binary = client.get("/api/layers/slope?format=f32")
    values = np.frombuffer(binary.content, dtype=BINARY_DTYPE).reshape(ROWS, COLS)
    np.testing.assert_allclose(values, _as_array(payload), rtol=1e-6, equal_nan=True)


def test_binary_cost_layer_has_no_infinities():
    binary = client.get("/api/layers/cost?format=f32")
    values = np.frombuffer(binary.content, dtype=BINARY_DTYPE)
    assert not np.isinf(values).any()
    assert np.isnan(values).any(), "the fixture's impassable cell must survive"
    assert int(binary.headers["X-Layer-Nodata"]) == int(np.isnan(values).sum())


def test_binary_traversable_is_one_and_zero():
    values = np.frombuffer(
        client.get("/api/layers/traversable?format=f32").content, dtype=BINARY_DTYPE
    )
    assert set(np.unique(values).tolist()) <= {0.0, 1.0}


def test_binary_resolution_header_follows_downsample():
    binary = client.get("/api/layers/elevation?format=f32&downsample=2")
    assert float(binary.headers["X-Layer-Resolution-M"]) == pytest.approx(10.0)
    assert int(binary.headers["X-Layer-Rows"]) == 4
    assert int(binary.headers["X-Layer-Cols"]) == 3
    assert len(binary.content) == 4 * 3 * 4


def test_cors_exposes_every_binary_header():
    """Without Access-Control-Expose-Headers the browser silently reports
    `undefined` for each X-Layer-* header on a cross-origin fetch."""
    response = client.get(
        "/api/layers/elevation?format=f32",
        headers={"Origin": "http://localhost:5173"},
    )
    exposed = {
        name.strip().lower()
        for name in response.headers.get("access-control-expose-headers", "").split(",")
    }
    for name in BINARY_LAYER_HEADERS:
        assert name.lower() in exposed, f"{name} is invisible to the browser"


# -- the manifest ------------------------------------------------------------

def test_terrain_manifest_describes_the_grid():
    manifest = client.get("/api/terrain").json()
    assert manifest["grid"] == {
        "rows": ROWS,
        "cols": COLS,
        "resolution_m": 5.0,
        "span_m": [ROWS * 5.0, COLS * 5.0],
        "cells": ROWS * COLS,
    }
    assert manifest["binary_format"]["dtype"] == "float32"
    assert manifest["binary_format"]["endian"] == "little"
    assert manifest["binary_format"]["bytes_per_layer"] == ROWS * COLS * 4
    assert manifest["georeference"]["row_axis"] == "north-to-south"
    assert manifest["georeference"]["col_axis"] == "west-to-east"
    assert manifest["rover"]["id"] == "lpr_1"
    assert set(manifest["layers"]) == {
        "elevation", "slope", "aspect", "thermal", "thermal_min",
        "shadow_ratio", "cost", "traversable",
    }
    assert manifest["layers"]["elevation"]["units"] == "m"
    assert manifest["layers"]["elevation"]["validity"] == "MEASURED"


def test_manifest_binary_urls_are_fetchable_as_given():
    """The manifest is only useful if its URLs work verbatim -- a client
    should never have to reassemble a query string by hand."""
    manifest = client.get("/api/terrain?rover_id=lpr_1&w_slope=0.5").json()
    for name, entry in manifest["layers"].items():
        response = client.get(entry["binary_url"])
        assert response.status_code == 200, f"{name}: {entry['binary_url']}"
        assert len(response.content) == manifest["binary_format"]["bytes_per_layer"]


def test_manifest_layer_range_matches_the_binary_it_points_at():
    manifest = client.get("/api/terrain").json()
    for name, entry in manifest["layers"].items():
        values = np.frombuffer(
            client.get(entry["binary_url"]).content, dtype=BINARY_DTYPE
        )
        finite = values[np.isfinite(values)]
        assert float(finite.min()) == pytest.approx(entry["min"], rel=1e-5), name
        assert float(finite.max()) == pytest.approx(entry["max"], rel=1e-5), name
        assert int(np.isnan(values).sum()) == entry["nodata"], name
