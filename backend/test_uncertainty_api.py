"""The DEM-uncertainty API (B3) on a synthetic grid with a synthetic clone
cache in a temporary processed_dir: the four ensemble layers in the terrain
manifest and the binary layer endpoint, ``GET /api/uncertainty-series``,
``POST /api/dem-uncertainty`` and the ``uncertainty`` block the plan
endpoints add when -- and only when -- a clone cache exists. No kernels, no
horizon cube: every sky here is static and labelled so.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.terrain import BINARY_DTYPE  # noqa: E402
from app.uncertainty import clear_uncertainty_cache  # noqa: E402
from test_uncertainty import _synthetic_grids, _write_synthetic_cache  # noqa: E402

_client = TestClient(app)


@pytest.fixture()
def grids(tmp_path):
    clear_uncertainty_cache()
    grids = _synthetic_grids(str(tmp_path))
    app.state.grids = grids
    yield grids
    app.state.grids = None
    clear_uncertainty_cache()


@pytest.fixture()
def cached(grids, tmp_path):
    """The same grids with a clone cache labelled as NASA's, so the
    published labels are the production ones (DERIVED / MODEL)."""
    _write_synthetic_cache(str(tmp_path), grids, provenance="nasa_pgda_clones")
    return grids


# ── Task 5: layers and the manifest ────────────────────────────────────────


def test_manifest_lists_the_ensemble_layers_and_their_pedigree(cached):
    manifest = _client.get("/api/terrain", params={"rover_id": "lpr_1"}).json()
    layers = manifest["layers"]
    for name, units, validity in (
        ("p_traversable", "fraction", "DERIVED"),
        ("slope_sigma", "deg", "DERIVED"),
        ("elevation_sigma", "m", "MODEL"),
        ("slope_sigma_nasa", "deg", "MODEL"),
    ):
        assert name in layers, name
        assert layers[name]["units"] == units
        assert layers[name]["validity"] == validity
        assert layers[name]["binary_url"].startswith(f"/api/layers/{name}?format=f32")
        assert "rover_id=lpr_1" in layers[name]["binary_url"]
    assert 0.0 <= layers["p_traversable"]["min"] <= layers["p_traversable"]["max"] <= 1.0
    pedigree = manifest["dem_uncertainty"]
    assert pedigree["model"] == "nasa_pgda_clones"
    assert pedigree["n_clones"] == 6
    assert pedigree["product_url"] == "https://pgda.gsfc.nasa.gov/products/78"
    assert pedigree["thermal_field_held_fixed"] is True


def test_manifest_is_unchanged_without_a_clone_cache(grids):
    manifest = _client.get("/api/terrain").json()
    assert "p_traversable" not in manifest["layers"]
    assert "dem_uncertainty" not in manifest


def test_binary_layer_serves_p_traversable_with_its_validity(cached):
    response = _client.get("/api/layers/p_traversable", params={"format": "f32", "rover_id": "lpr_1"})
    assert response.status_code == 200, response.text
    assert response.headers["X-Layer-Validity"] == "DERIVED"
    assert response.headers["X-Layer-Rows"] == "8" and response.headers["X-Layer-Cols"] == "8"
    values = np.frombuffer(response.content, dtype=BINARY_DTYPE)
    assert values.size == 64
    assert float(values.min()) >= 0.0 and float(values.max()) <= 1.0

    sigma = _client.get("/api/layers/elevation_sigma", params={"format": "f32"})
    assert sigma.status_code == 200
    assert sigma.headers["X-Layer-Validity"] == "MODEL"
    assert np.frombuffer(sigma.content, dtype=BINARY_DTYPE)[0] == pytest.approx(0.4)

    as_json = _client.get("/api/layers/slope_sigma").json()
    assert as_json["layer"] == "slope_sigma" and len(as_json["data"]) == 8
    assert as_json["metadata"]["dem_uncertainty"]["n_clones"] == 6


def test_binary_layer_404s_without_a_clone_cache_and_names_the_script(grids):
    response = _client.get("/api/layers/p_traversable", params={"format": "f32"})
    assert response.status_code == 404
    assert "build_dem_clone_cache" in response.json()["detail"]


def test_p_traversable_follows_the_rovers_slope_limit(cached):
    lpr = np.frombuffer(
        _client.get("/api/layers/p_traversable", params={"format": "f32", "rover_id": "lpr_1"}).content,
        dtype=BINARY_DTYPE,
    )
    viper = np.frombuffer(
        _client.get("/api/layers/p_traversable", params={"format": "f32", "rover_id": "nasa_viper"}).content,
        dtype=BINARY_DTYPE,
    )
    # A 20 deg limit can only close cells a 25 deg limit keeps open.
    assert np.all(viper <= lpr + 1e-6)
    assert float(viper.sum()) < float(lpr.sum())


# ── Task 6: GET /api/uncertainty-series ────────────────────────────────────


def _write_clone_horizons(processed_dir, n=6, stride=4, shape=(2, 2), n_azimuth=4):
    """Per-clone cubes on the 8x8 grid's 2x2 block centres: clone k sees a
    northern ridge of 5 + 5k deg at cell (0, 0) and a flat horizon elsewhere."""
    from app.uncertainty import write_clone_horizons

    cubes = np.zeros((n, n_azimuth) + shape, dtype=np.float32)
    for k in range(n):
        cubes[k, 0, 0, 0] = 5.0 + 5.0 * k
    write_clone_horizons(
        processed_dir,
        cubes,
        {
            "stride": stride,
            "row_offset": stride // 2,
            "col_offset": stride // 2,
            "n_azimuth": n_azimuth,
            "near_range_m": 1000.0,
            "far_field_held_fixed": True,
            "neglected_horizon_shift_deg_max": 0.0214,
            "clone_indices": list(range(1, n + 1)),
        },
    )
    return cubes


def _script_sun(monkeypatch, elevations):
    """The Sun due north (grid azimuth 0) at the scripted elevation per slice."""
    import app.main as main_module

    def fake_track(metadata, n_slices, slice_hours, start_utc, body="SUN"):
        return [
            {"index": i, "utc": start_utc, "azimuth_true_deg": 0.0, "azimuth_grid_deg": 0.0,
             "elevation_deg": float(elevations[i])}
            for i in range(int(n_slices))
        ]

    monkeypatch.setattr(main_module, "body_track_for_series", fake_track)


def test_uncertainty_series_is_unavailable_without_clone_horizons(cached):
    response = _client.get(
        "/api/uncertainty-series",
        params={"start_utc": "2027-05-30T00:00:00", "n_slices": 3, "slice_hours": 1.0},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["model"] == "unavailable"
    assert "build_dem_clone_cache" in payload["reason"]
    assert "fields" not in payload
    binary = _client.get(
        "/api/uncertainty-series",
        params={"start_utc": "2027-05-30T00:00:00", "n_slices": 3, "slice_hours": 1.0, "format": "f32"},
    )
    assert binary.status_code == 404


def test_uncertainty_series_needs_an_epoch(cached, tmp_path):
    _write_clone_horizons(str(tmp_path))
    payload = _client.get("/api/uncertainty-series", params={"n_slices": 3}).json()
    assert payload["model"] == "unavailable" and "epoch" in payload["reason"]


def test_uncertainty_series_reports_p_illuminated_per_slice(cached, tmp_path, monkeypatch):
    _write_clone_horizons(str(tmp_path))
    # 2, 12, 22, 32 deg: cell (0, 0) is lit in 0/6, 2/6, 4/6, 6/6 clones.
    _script_sun(monkeypatch, [2.0, 12.0, 22.0, 32.0])
    response = _client.get(
        "/api/uncertainty-series",
        params={"start_utc": "2027-05-30T00:00:00", "n_slices": 4, "slice_hours": 1.0},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["model"] == "clone_horizon"
    assert payload["n_clones"] == 6
    assert payload["grid"] == {
        "rows": 2, "cols": 2, "resolution_m": 20.0, "stride": 4, "row_offset": 2, "col_offset": 2,
    }
    assert payload["fields"]["p_illuminated"]["units"] == "fraction"
    assert payload["binary_format"]["shape"] == [4, 2, 2]
    assert payload["per_slice"]["mean"] == pytest.approx([0.75, 0.75 + 2 / 24, 0.75 + 4 / 24, 1.0], abs=1e-6)
    assert payload["per_slice"]["uncertain_fraction"] == pytest.approx([0.0, 0.25, 0.25, 0.0])
    assert payload["far_field_held_fixed"] is True
    assert len(payload["sun"]) == 4

    binary = _client.get(
        "/api/uncertainty-series",
        params={"start_utc": "2027-05-30T00:00:00", "n_slices": 4, "slice_hours": 1.0, "format": "f32"},
    )
    assert binary.status_code == 200
    assert binary.headers["X-Series-Field"] == "p_illuminated"
    assert binary.headers["X-Series-Slices"] == "4"
    assert binary.headers["X-Series-Rows"] == "2" and binary.headers["X-Series-Cols"] == "2"
    assert binary.headers["X-Series-Resolution-M"] == "20.0"
    cube = np.frombuffer(binary.content, dtype=BINARY_DTYPE).reshape(4, 2, 2)
    np.testing.assert_allclose(cube[:, 0, 0], [0.0, 2 / 6, 4 / 6, 1.0], atol=1e-6)
    np.testing.assert_allclose(cube[:, 1, 1], 1.0)


def test_uncertainty_series_degrades_when_the_sun_track_fails(cached, tmp_path, monkeypatch):
    import app.main as main_module

    _write_clone_horizons(str(tmp_path))

    def broken(*args, **kwargs):
        raise RuntimeError("SPICE(NOLOADEDFILES)")

    monkeypatch.setattr(main_module, "body_track_for_series", broken)
    payload = _client.get(
        "/api/uncertainty-series",
        params={"start_utc": "2027-05-30T00:00:00", "n_slices": 2},
    ).json()
    assert payload["model"] == "unavailable" and "NOLOADEDFILES" in payload["reason"]


# ── Task 7: POST /api/dem-uncertainty and the plan endpoints' block ────────

# Coarse cells at coarsen 4 on the 8x8 grid: two moves, then a planned wait.
_COARSE_ROUTE = [[0, 0, 0], [0, 1, 1], [1, 1, 2], [1, 1, 3]]


def _band_body(**overrides) -> dict:
    body = {
        "path_states": _COARSE_ROUTE,
        "rover_id": "lpr_1",
        "coarsen": 4,
        "slice_hours": 1.0,
    }
    body.update(overrides)
    return body


@pytest.fixture()
def flat(tmp_path):
    """A gentle grid (slopes well under 25 deg) so every clone keeps the
    route passable and the plan endpoints find a path."""
    clear_uncertainty_cache()
    grids = _synthetic_grids(str(tmp_path), amplitude=0.4)
    _write_synthetic_cache(str(tmp_path), grids, provenance="nasa_pgda_clones")
    app.state.grids = grids
    yield grids
    app.state.grids = None
    clear_uncertainty_cache()


def test_dem_uncertainty_band_on_a_static_sky(flat):
    response = _client.post("/api/dem-uncertainty", json=_band_body(label="band"))
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["label"] == "band"
    assert out["n_clones"] == 6 and out["clones_priced"] == 6 and out["unpriceable"] == []
    assert out["route"]["n_states"] == 4 and out["route"]["move_steps"] == 2 and out["route"]["wait_steps"] == 1
    assert out["route_feasible"]["count"] == 6 and out["route_feasible"]["fraction"] == 1.0
    assert len(out["route_feasible"]["ci95"]) == 2
    assert len(out["p_traversable"]["per_state"]) == 4
    assert out["p_traversable"]["min"] == 1.0
    for key in ("duration_h", "drive_hours", "gross_drive_wh", "battery_used_wh",
                "min_battery_pct", "final_battery_pct", "max_continuous_shadow_h"):
        assert out["metrics"][key]["n"] == 6, key
        assert key in out["nominal"], key
    assert out["nominal"]["reached"] is True
    assert out["sky_model"]["model"] == "static" and out["sky_model"]["reason"]
    assert out["sky_model"]["far_field_held_fixed"] is True
    assert out["sherpa"] is None
    assert out["provenance"]["model"] == "nasa_pgda_clones"
    assert out["provenance"]["n_clones_available"] == 6
    assert set(out["timing_ms"]) == {"sky", "runs", "total"}


def test_dem_uncertainty_can_add_sherpas_runs_and_limit_the_clones(flat):
    out = _client.post(
        "/api/dem-uncertainty",
        json=_band_body(with_sherpa=True, n_runs=20, seed=1, n_clones=4),
    ).json()
    assert out["n_clones"] == 4 and out["metrics"]["drive_hours"]["n"] == 4
    assert out["sherpa"]["n_runs_per_clone"] == 20 and out["sherpa"]["n_runs_total"] == 80
    assert out["sherpa"]["completion"]["count"] <= 80
    again = _client.post(
        "/api/dem-uncertainty",
        json=_band_body(with_sherpa=True, n_runs=20, seed=1, n_clones=4),
    ).json()
    assert again["sherpa"] == out["sherpa"]


def test_dem_uncertainty_rejects_bad_routes_and_too_many_clones(flat):
    broken = _client.post("/api/dem-uncertainty", json=_band_body(path_states=[[0, 0, 0], [1, 0, 0]]))
    assert broken.status_code == 422 and "path_states" in broken.json()["detail"]
    apart = _client.post("/api/dem-uncertainty", json=_band_body(path_states=[[0, 0, 0], [1, 1, 1], [0, 0, 2]]))
    assert apart.status_code == 200  # diagonal moves are legal
    too_many = _client.post("/api/dem-uncertainty", json=_band_body(n_clones=50))
    assert too_many.status_code == 422 and "6" in too_many.json()["detail"]


def test_dem_uncertainty_404s_without_a_clone_cache(grids):
    response = _client.post("/api/dem-uncertainty", json=_band_body())
    assert response.status_code == 404
    assert "build_dem_clone_cache" in response.json()["detail"]


def test_plan_endpoints_carry_an_uncertainty_block_only_with_the_cache(flat, tmp_path):
    plan = _client.post(
        "/api/plan",
        json={"start": {"row": 0, "col": 0}, "goal": {"row": 7, "col": 7}, "rover_id": "lpr_1"},
    )
    assert plan.status_code == 200, plan.text
    block = plan.json()["uncertainty"]
    assert block["n_clones"] == 6
    assert block["model"] == "nasa_pgda_clones"
    assert 0.0 <= block["p_traversable_min"] <= block["p_traversable_mean"] <= 1.0
    assert 0.0 <= block["route_feasible_fraction"] <= 1.0
    assert block["band_url"] == "/api/dem-uncertainty"

    plan_4d = _client.post(
        "/api/plan-4d",
        json={
            "start": {"row": 0, "col": 0}, "goal": {"row": 7, "col": 7}, "rover_id": "lpr_1",
            "coarsen": 4, "n_slices": 8, "slice_hours": 1.0,
        },
    )
    assert plan_4d.status_code == 200, plan_4d.text
    block = plan_4d.json()["uncertainty"]
    assert block["n_clones"] == 6 and block["coarsen"] == 4
    assert block["route_feasible_fraction"] == 1.0
    assert block["band_url"] == "/api/dem-uncertainty"

    # Without the cache the field is absent -- not null, absent.
    clear_uncertainty_cache()
    bare = _synthetic_grids(str(tmp_path / "bare"), amplitude=0.4)
    app.state.grids = bare
    assert "uncertainty" not in _client.post(
        "/api/plan",
        json={"start": {"row": 0, "col": 0}, "goal": {"row": 7, "col": 7}, "rover_id": "lpr_1"},
    ).json()
    assert "uncertainty" not in _client.post(
        "/api/plan-4d",
        json={
            "start": {"row": 0, "col": 0}, "goal": {"row": 7, "col": 7}, "rover_id": "lpr_1",
            "coarsen": 4, "n_slices": 8, "slice_hours": 1.0,
        },
    ).json()


def test_uncertainty_series_can_use_the_first_n_clones(cached, tmp_path, monkeypatch):
    """One clone cube is 4.5 MB at the production stride; a viewer asking
    for a quick look takes the first n rather than all hundred."""
    _write_clone_horizons(str(tmp_path))
    _script_sun(monkeypatch, [12.0])
    payload = _client.get(
        "/api/uncertainty-series",
        params={"start_utc": "2027-05-30T00:00:00", "n_slices": 1, "n_clones": 3},
    ).json()
    assert payload["n_clones"] == 3 and payload["clone_indices"] == [1, 2, 3]
    # Clones 1-3 see a 5 / 10 / 15 deg ridge at (0, 0): two of three are lit at 12 deg.
    assert payload["per_slice"]["mean"] == pytest.approx([(2 / 3 + 3.0) / 4.0], abs=1e-6)
    too_many = _client.get(
        "/api/uncertainty-series",
        params={"start_utc": "2027-05-30T00:00:00", "n_slices": 1, "n_clones": 50},
    )
    assert too_many.status_code == 422 and "6" in too_many.json()["detail"]
