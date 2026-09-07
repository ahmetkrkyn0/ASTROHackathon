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
from app.terrain import BINARY_DTYPE, BINARY_LAYER_HEADERS, SERIES_HEADERS  # noqa: E402

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


def test_cors_exposes_every_series_header():
    """The series binary payload has its own X-Series-* headers (a time axis
    a single layer does not carry) -- CORS_review found these were missing
    from the middleware's allowlist even though the endpoint set them, the
    exact failure the sibling layer test above exists to catch."""
    response = client.get(
        f"{SERIES}?n_slices=2&format=f32&field=shadow",
        headers={"Origin": "http://localhost:5173"},
    )
    exposed = {
        name.strip().lower()
        for name in response.headers.get("access-control-expose-headers", "").split(",")
    }
    for name in SERIES_HEADERS:
        assert name.lower() in exposed, f"{name} is invisible to the browser"
        assert name in response.headers, f"{name} was never set on the response"


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


# -- the time-slice series ---------------------------------------------------

SERIES = "/api/illumination-series"


def test_series_manifest_reports_slices_grid_and_fields():
    manifest = client.get(f"{SERIES}?n_slices=6&slice_hours=4").json()
    assert manifest["slices"] == 6
    assert manifest["slice_hours"] == 4.0
    assert manifest["grid"]["rows"] == ROWS and manifest["grid"]["cols"] == COLS
    assert manifest["binary_format"]["shape"] == [6, ROWS, COLS]
    assert set(manifest["fields"]) == {"shadow", "surface_temp_c"}
    assert manifest["fields"]["surface_temp_c"]["units"] == "degC"
    assert manifest["thermal_model"]["tau_s"] > 0


def test_series_without_an_epoch_says_static_and_says_why():
    """Illumination is a function of time; without an epoch it cannot vary,
    and the response must not let a frozen cube pass as physics."""
    manifest = client.get(f"{SERIES}?n_slices=4").json()
    assert manifest["shadow_model"]["time_varying"] is False
    assert manifest["shadow_model"]["model"] == "static"
    assert "epoch" in manifest["shadow_model"]["reason"]
    assert manifest["sun"] == []


def test_series_binary_is_slice_major_then_row_major():
    response = client.get(f"{SERIES}?n_slices=6&slice_hours=4&format=f32&field=shadow")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert int(response.headers["X-Series-Slices"]) == 6
    assert int(response.headers["X-Series-Rows"]) == ROWS
    assert int(response.headers["X-Series-Cols"]) == COLS
    values = np.frombuffer(response.content, dtype=BINARY_DTYPE)
    assert values.size == 6 * ROWS * COLS
    cube = values.reshape(6, ROWS, COLS)
    assert np.nanmin(cube) >= 0.0 and np.nanmax(cube) <= 1.0


def test_series_binary_preserves_slice_order_when_time_varying(monkeypatch):
    """The test above cannot catch a slice/row axis swap: without an epoch
    the series is static, so every slice is byte-identical and no
    permutation of the T axis is detectable. Monkeypatch a genuinely
    time-varying series -- one snapshot per slice, offset by its own index
    -- so a T/W swap (n_slices=4 vs COLS=6, deliberately different) has
    something to disagree with."""
    import app.main as main_module

    base = np.asarray(_make_grids()["shadow_ratio"], dtype=np.float64)

    def _fake_series(base_shadow, metadata, n_slices, slice_hours, start_utc=None):
        series = [base + float(i) for i in range(int(n_slices))]
        return series, {"model": "spice_horizon", "time_varying": True}

    monkeypatch.setattr(main_module, "build_shadow_series", _fake_series)

    response = client.get(f"{SERIES}?n_slices=4&slice_hours=4&format=f32&field=shadow")
    assert response.status_code == 200
    cube = np.frombuffer(response.content, dtype=BINARY_DTYPE).reshape(4, ROWS, COLS)
    means = cube.reshape(4, -1).mean(axis=1)
    # Slice i was offset by i; a correct slice-major encode keeps that
    # strictly increasing. A swapped axis reshapes the same bytes into a
    # different partition and this monotonicity does not survive it.
    assert np.all(np.diff(means) > 0)


def test_series_temperature_uses_the_planner_recipe():
    """The surface a viewer animates has to be the surface the planner
    costed. build_cost_cube starts every cell at the equilibrium under its
    long-run illumination; with a static series that is also where it
    stays, so slice 0 is exactly that field."""
    from app.thermal_model import shadowed_equilibrium_c

    grids = _make_grids()
    response = client.get(
        f"{SERIES}?n_slices=2&slice_hours=4&format=f32&field=surface_temp_c"
    )
    cube = np.frombuffer(response.content, dtype=BINARY_DTYPE).reshape(2, ROWS, COLS)
    expected = np.asarray(
        shadowed_equilibrium_c(grids["thermal_sunlit_peak"], grids["shadow_ratio"]),
        dtype=np.float64,
    )
    np.testing.assert_allclose(cube[0], expected, rtol=1e-4, equal_nan=True)


def test_series_temperature_relaxes_toward_a_new_target_across_slices(monkeypatch):
    """The test above only proves slice 0 -- the initial equilibrium -- is
    right. With a static series ``target == state`` at every step, so
    relax_surface_c is a no-op and that test cannot tell whether the
    slice-to-slice integration (the actual "same recipe as build_cost_cube"
    claim) works at all. Feed a genuinely time-varying shadow series and
    check slice 1 moved from slice 0's state toward slice 1's own target --
    not jumped straight to it (relax_surface_c is a first-order lag, not an
    instant reset) and not stayed put (that would mean the series was never
    threaded through the temperature branch)."""
    from app.thermal_model import shadowed_equilibrium_c
    import app.main as main_module

    grids = _make_grids()
    base = np.asarray(grids["shadow_ratio"], dtype=np.float64)
    shaded = np.clip(base + 0.5, 0.0, 1.0)  # a distinctly different illumination

    def _fake_series(base_shadow, metadata, n_slices, slice_hours, start_utc=None):
        return [base, shaded], {"model": "spice_horizon", "time_varying": True}

    monkeypatch.setattr(main_module, "build_shadow_series", _fake_series)

    response = client.get(
        f"{SERIES}?n_slices=2&slice_hours=4&format=f32&field=surface_temp_c"
    )
    cube = np.frombuffer(response.content, dtype=BINARY_DTYPE).reshape(2, ROWS, COLS)

    sunlit = grids["thermal_sunlit_peak"]
    slice0_target = np.asarray(shadowed_equilibrium_c(sunlit, base), dtype=np.float64)
    slice1_target = np.asarray(
        shadowed_equilibrium_c(sunlit, shaded), dtype=np.float64
    )
    np.testing.assert_allclose(cube[0], slice0_target, rtol=1e-4, equal_nan=True)

    finite = np.isfinite(cube[0]) & np.isfinite(slice1_target)
    moved_toward_target = np.abs(cube[1][finite] - slice1_target[finite]) < np.abs(
        cube[0][finite] - slice1_target[finite]
    )
    assert moved_toward_target.all()
    assert not np.allclose(cube[1][finite], cube[0][finite])
    assert not np.allclose(cube[1][finite], slice1_target[finite])


def test_series_downsample_decimates_both_axes():
    manifest = client.get(f"{SERIES}?n_slices=2&downsample=2").json()
    assert manifest["grid"]["rows"] == 4 and manifest["grid"]["cols"] == 3
    assert manifest["grid"]["resolution_m"] == pytest.approx(10.0)
    binary = client.get(f"{SERIES}?n_slices=2&downsample=2&format=f32&field=shadow")
    assert len(binary.content) == 2 * 4 * 3 * 4


def test_series_rejects_an_unknown_field():
    assert client.get(f"{SERIES}?n_slices=2&format=f32&field=albedo").status_code == 422


def test_series_manifest_urls_are_fetchable_as_given():
    manifest = client.get(f"{SERIES}?n_slices=3&slice_hours=2&downsample=2").json()
    for name, entry in manifest["fields"].items():
        response = client.get(entry["binary_url"])
        assert response.status_code == 200, f"{name}: {entry['binary_url']}"
        assert len(response.content) == 3 * 4 * 3 * 4, name


# -- A4: the Earth-visibility layer ------------------------------------------


def _with_earth_layer(value: float = 0.5) -> np.ndarray:
    rng = np.arange(ROWS * COLS, dtype=np.float64).reshape(SHAPE)
    layer = np.clip(value + (rng % 4) / 10.0, 0.0, 1.0)
    app.state.grids["earth_visibility"] = layer
    app.state.grids["metadata"]["layer_validity"]["earth_visibility"] = "DERIVED"
    return layer


def test_manifest_omits_earth_visibility_until_the_layer_is_loaded():
    manifest = client.get("/api/terrain").json()
    assert "earth_visibility" not in manifest["layers"]


def test_manifest_lists_earth_visibility_when_the_layer_is_loaded():
    layer = _with_earth_layer()
    manifest = client.get("/api/terrain").json()
    entry = manifest["layers"]["earth_visibility"]
    assert entry["units"] == "fraction"
    assert entry["validity"] == "DERIVED"
    assert entry["min"] == pytest.approx(float(layer.min()))
    assert entry["max"] == pytest.approx(float(layer.max()))
    assert entry["binary_url"].startswith("/api/layers/earth_visibility?format=f32")
    assert "Earth" in entry["description"]


def test_earth_visibility_layer_round_trips_as_float32():
    layer = _with_earth_layer()
    response = client.get("/api/layers/earth_visibility?format=f32")
    assert response.status_code == 200
    assert response.headers["X-Layer-Validity"] == "DERIVED"
    values = np.frombuffer(response.content, dtype=BINARY_DTYPE).reshape(SHAPE)
    np.testing.assert_allclose(values, layer.astype(np.float32))
    payload = client.get("/api/layers/earth_visibility").json()
    assert payload["layer"] == "earth_visibility"
    assert payload["shape"] == [ROWS, COLS]


def test_missing_earth_visibility_layer_is_a_404_that_names_the_script():
    response = client.get("/api/layers/earth_visibility")
    assert response.status_code == 404
    assert "build_earth_visibility_cache" in response.json()["detail"]


# -- A4: the Earth-visibility series -----------------------------------------

EARTH_SERIES = "/api/earth-series"


def test_earth_series_with_nothing_to_compute_from_is_unavailable_and_says_so():
    """No epoch, no horizon cube, no long-run layer: the manifest must not
    paint a field it does not have."""
    manifest = client.get(f"{EARTH_SERIES}?n_slices=4").json()
    assert manifest["slices"] == 4
    assert manifest["earth_model"]["model"] == "unavailable"
    assert manifest["earth_model"]["time_varying"] is False
    assert manifest["earth_model"]["reason"]
    assert manifest["earth"] == []
    assert manifest["fields"] == {}
    assert manifest["binary_format"]["shape"] == [4, ROWS, COLS]

    binary = client.get(f"{EARTH_SERIES}?n_slices=4&format=f32&field=earth_visible")
    assert binary.status_code == 404
    assert "unavailable" in binary.json()["detail"].lower()


def test_earth_series_falls_back_to_the_long_run_layer_and_labels_it_static():
    layer = _with_earth_layer()
    manifest = client.get(f"{EARTH_SERIES}?n_slices=3&slice_hours=4").json()
    assert manifest["earth_model"]["model"] == "static"
    assert manifest["earth_model"]["time_varying"] is False
    assert "epoch" in manifest["earth_model"]["reason"]
    entry = manifest["fields"]["earth_visible"]
    assert entry["units"] == "fraction"
    assert entry["min"] == pytest.approx(float(layer.min()))
    assert entry["max"] == pytest.approx(float(layer.max()))

    binary = client.get(entry["binary_url"])
    assert binary.status_code == 200
    assert binary.headers["X-Series-Field"] == "earth_visible"
    assert int(binary.headers["X-Series-Slices"]) == 3
    cube = np.frombuffer(binary.content, dtype=BINARY_DTYPE).reshape(3, ROWS, COLS)
    for index in range(3):
        np.testing.assert_allclose(cube[index], layer.astype(np.float32))


def test_earth_series_binary_preserves_slice_order_when_time_varying(monkeypatch):
    """Same axis-swap guard as the illumination series: n_slices=4 against
    COLS=6, each slice offset by its own index."""
    import app.main as main_module

    def _fake_series(base, metadata, n_slices, slice_hours, start_utc=None):
        series = [np.full(SHAPE, 0.1 * i) for i in range(int(n_slices))]
        return series, {"model": "spice_horizon", "time_varying": True}

    def _fake_track(metadata, n_slices, slice_hours, start_utc):
        return [
            {
                "index": i,
                "utc": f"2026-09-0{i + 1}T00:00:00Z",
                "azimuth_true_deg": 100.0,
                "azimuth_grid_deg": 350.0,
                "elevation_deg": 6.0 - i,
            }
            for i in range(int(n_slices))
        ]

    monkeypatch.setattr(main_module, "build_earth_visibility_series", _fake_series)
    monkeypatch.setattr(main_module, "earth_track_for_series", _fake_track)

    query = f"{EARTH_SERIES}?start_utc=2026-09-01T00:00:00&n_slices=4&slice_hours=24"
    manifest = client.get(query).json()
    assert manifest["earth_model"]["model"] == "spice_horizon"
    assert manifest["start_utc"] == "2026-09-01T00:00:00"
    assert [entry["elevation_deg"] for entry in manifest["earth"]] == [6.0, 5.0, 4.0, 3.0]
    # The share of the grid with a link, per slice: what a timeline widget
    # needs, straight from the slices the binary carries.
    assert [entry["visible_fraction"] for entry in manifest["earth"]] == pytest.approx(
        [0.0, 0.1, 0.2, 0.3]
    )

    binary = client.get(f"{query}&format=f32&field=earth_visible")
    assert binary.status_code == 200
    cube = np.frombuffer(binary.content, dtype=BINARY_DTYPE).reshape(4, ROWS, COLS)
    means = cube.reshape(4, -1).mean(axis=1)
    assert np.all(np.diff(means) > 0)


def test_earth_series_shares_the_illumination_series_budget(monkeypatch):
    """One budget, two endpoints: the refusal has to name a downsample that
    fits, exactly as /api/illumination-series does. The fixture is far too
    small to hit the real ceiling, so the ceiling is lowered to meet it."""
    import app.main as main_module

    monkeypatch.setattr(main_module, "MAX_SERIES_BYTES", 100)
    for endpoint in (EARTH_SERIES, SERIES):
        response = client.get(f"{endpoint}?n_slices=4&downsample=1")
        assert response.status_code == 422, endpoint
        assert "downsample=" in response.json()["detail"], endpoint


def test_earth_series_rejects_an_unknown_field():
    response = client.get(f"{EARTH_SERIES}?n_slices=2&format=f32&field=shadow")
    assert response.status_code == 422
