"""GET /api/safe-haven: the Safe Haven map as a manifest plus binary layers."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app
from app.terrain import BINARY_DTYPE

SHAPE = (16, 16)
ROWS, COLS = SHAPE

_client = TestClient(app)


@pytest.fixture()
def client():
    rover = get_rover()
    app.state.grids = {
        "elevation": np.zeros(SHAPE),
        "slope": np.full(SHAPE, 3.0),
        "aspect": np.zeros(SHAPE),
        "thermal": np.full(SHAPE, -60.0),
        "shadow_ratio": np.full(SHAPE, 0.3),
        "traversable": np.ones(SHAPE, dtype=bool),
        "cost": np.full(SHAPE, 0.3),
        "metadata": {
            "origin": {"x": 156000.0, "y": 28000.0},
            "resolution_m": 80.0,
            "shape": list(SHAPE),
            "crs": "test",
            "default_rover_id": rover["id"],
            "cost_weights": {
                "w_slope": 0.409,
                "w_energy": 0.259,
                "w_shadow": 0.142,
                "w_thermal": 0.19,
            },
        },
    }
    yield _client
    app.state.grids = None


EPOCH = "2026-09-07T00:00:00"


def _fake_map(rover_id: str = "lpr_1"):
    """A map with havens on the top-left quarter, one unreachable cell, and
    the endurance of the requested rover."""
    safe = np.zeros(SHAPE, dtype=bool)
    safe[:8, :8] = True
    max_dark = np.where(safe, 12.0, 80.0)
    earth_below = np.full(SHAPE, 300.0)
    tts = np.where(safe, 0.0, 2.5)
    tts[15, 15] = np.inf
    layers = {
        "safe_haven": safe,
        "max_dark_hours_without_dte": max_dark,
        "earth_below_hours": earth_below,
        "ever_lit": np.ones(SHAPE, dtype=bool),
    }
    endurance = float(get_rover(rover_id)["h_max_shadow_h"])
    info = {
        "model": "spice_horizon",
        "start_utc": EPOCH + "Z",
        "span_hours": 708.7,
        "step_hours": 2.0,
        "n_steps": 355,
        "rover_id": rover_id,
        "h_max_shadow_h": endurance,
        "safe_haven_cells": int(safe.sum()),
        "traversable_cells": int(SHAPE[0] * SHAPE[1]),
        "safe_haven_fraction": float(safe.mean()),
        "earth_below_fraction": 300.0 / 708.7,
    }
    return layers, tts, info


def _patch_map(monkeypatch):
    import app.main as main_module

    def _fake(grids, rover_id, start_utc, span_hours=708.7, step_hours=2.0):
        return _fake_map(rover_id)

    monkeypatch.setattr(main_module, "safe_haven_for_grids", _fake)


def test_safe_haven_requires_an_epoch(client):
    response = client.get("/api/safe-haven")
    assert response.status_code == 422


def test_safe_haven_is_unavailable_without_a_horizon_cube_and_says_so(client):
    """The fixture has no processed_dir, so no horizon cube: the manifest
    says unavailable with the reason, offers no fields, and the binary
    request is a 404 rather than a grid of zeros."""
    payload = client.get(f"/api/safe-haven?start_utc={EPOCH}").json()
    assert payload["safe_haven_model"]["model"] == "unavailable"
    assert "horizon_map.npy" in payload["safe_haven_model"]["reason"]
    assert payload["fields"] == {}
    assert payload["safe_haven_fraction"] is None

    binary = client.get(f"/api/safe-haven?start_utc={EPOCH}&format=f32&field=safe_haven")
    assert binary.status_code == 404


def test_safe_haven_manifest_describes_the_window_the_rover_and_the_fields(client, monkeypatch):
    _patch_map(monkeypatch)
    payload = client.get(f"/api/safe-haven?start_utc={EPOCH}").json()

    assert payload["rover_id"] == "lpr_1"
    assert payload["h_max_shadow_h"] == 50.0
    assert payload["start_utc"] == EPOCH + "Z"
    assert payload["span_hours"] == 708.7
    assert payload["step_hours"] == 2.0
    assert payload["n_steps"] == 355
    assert payload["safe_haven_model"]["model"] == "spice_horizon"
    assert payload["safe_haven_cells"] == 64
    assert payload["traversable_cells"] == 256
    assert payload["safe_haven_fraction"] == pytest.approx(0.25)
    assert payload["earth_below_fraction"] == pytest.approx(300.0 / 708.7)
    assert payload["grid"] == {"rows": ROWS, "cols": COLS, "resolution_m": 80.0, "downsample": 1}

    fields = payload["fields"]
    assert set(fields) == {
        "safe_haven", "max_dark_hours_without_dte", "earth_below_hours", "time_to_safe_haven",
    }
    assert fields["safe_haven"]["units"] == "bool"
    assert fields["max_dark_hours_without_dte"]["units"] == "hours"
    assert fields["time_to_safe_haven"]["units"] == "hours"
    assert fields["time_to_safe_haven"]["max"] == pytest.approx(2.5)
    assert fields["time_to_safe_haven"]["nodata"] == 1
    for entry in fields.values():
        assert entry["binary_url"].startswith("/api/safe-haven?")
        assert "format=f32" in entry["binary_url"]
    assert payload["binary_format"]["nodata"] == "NaN"


def test_safe_haven_binary_fields_round_trip_as_float32(client, monkeypatch):
    _patch_map(monkeypatch)
    manifest = client.get(f"/api/safe-haven?start_utc={EPOCH}").json()

    for name, entry in manifest["fields"].items():
        response = client.get(entry["binary_url"])
        assert response.status_code == 200, name
        assert response.headers["X-Layer-Name"] == name
        assert int(response.headers["X-Layer-Rows"]) == ROWS
        assert int(response.headers["X-Layer-Cols"]) == COLS
        values = np.frombuffer(response.content, dtype=BINARY_DTYPE).reshape(SHAPE)
        if name == "safe_haven":
            assert set(np.unique(values).tolist()) == {0.0, 1.0}
            assert values[:8, :8].all() and not values[8:, 8:].any()
        if name == "time_to_safe_haven":
            assert np.isnan(values[15, 15])
            assert values[0, 0] == 0.0 and values[10, 10] == pytest.approx(2.5)


def test_safe_haven_binary_honours_downsample_and_the_rover(client, monkeypatch):
    _patch_map(monkeypatch)
    response = client.get(
        f"/api/safe-haven?start_utc={EPOCH}&format=f32&field=safe_haven&downsample=2&rover_id=luvmi_m"
    )
    assert response.status_code == 200
    assert int(response.headers["X-Layer-Rows"]) == 8
    assert float(response.headers["X-Layer-Resolution-M"]) == pytest.approx(160.0)
    values = np.frombuffer(response.content, dtype=BINARY_DTYPE)
    assert values.size == 64

    manifest = client.get(f"/api/safe-haven?start_utc={EPOCH}&rover_id=luvmi_m").json()
    assert manifest["rover_id"] == "luvmi_m"
    assert manifest["h_max_shadow_h"] == 4.0


def test_safe_haven_rejects_an_unknown_field_and_rover(client, monkeypatch):
    _patch_map(monkeypatch)
    assert client.get(f"/api/safe-haven?start_utc={EPOCH}&format=f32&field=nope").status_code == 422
    assert client.get(f"/api/safe-haven?start_utc={EPOCH}&rover_id=nope").status_code == 422
