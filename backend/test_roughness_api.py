"""The roughness / PSR layers on the API (C4): /api/terrain and /api/layers,
the cell card, the `roughness` block on /api/plan and /api/plan-4d,
PlanWeights.w_roughness, /api/psr-validation, profiles and rovers --
on 16x16 synthetic grids, with and without the two layers. No kernels, no
network, no cache."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app
from app.roughness import LDRM_PRODUCT, LPSR_PRODUCT, RoughnessScale
from app.terrain import BINARY_DTYPE

SHAPE = (16, 16)
_client = TestClient(app)


def _scale() -> RoughnessScale:
    knots = np.linspace(0.05, 3.0, 41)
    return RoughnessScale.from_meta({"knots": knots.tolist(), "probs": np.linspace(0.0, 1.0, 41).tolist()})


def _roughness() -> np.ndarray:
    return np.exp(np.random.default_rng(0).normal(-0.3, 0.5, SHAPE))


def _psr() -> np.ndarray:
    psr = np.zeros(SHAPE)
    psr[10:14, 2:6] = 1.0  # a 4x4 block, 16 cells
    return psr


def _grids(with_layers: bool) -> dict:
    rover = get_rover()
    grids = {
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
            "cost_weights": {"w_slope": 0.409, "w_energy": 0.259, "w_shadow": 0.142, "w_thermal": 0.19},
            "layer_validity": {"thermal": "MODEL", "shadow_ratio": "DERIVED"},
        },
    }
    if with_layers:
        grids["roughness"] = _roughness()
        grids["psr"] = _psr()
        grids["metadata"]["roughness"] = {
            "product": LDRM_PRODUCT, "baseline_m": 100, "resolution_m": 50, "scale": _scale().to_meta(),
        }
        grids["metadata"]["psr"] = {"product": LPSR_PRODUCT, "resolution_m": 20}
        grids["metadata"]["layer_validity"].update({"roughness": "MEASURED", "psr": "MEASURED"})
    return grids


@pytest.fixture()
def bare():
    app.state.grids = _grids(with_layers=False)
    yield _client
    app.state.grids = None


@pytest.fixture()
def layered():
    app.state.grids = _grids(with_layers=True)
    yield _client
    app.state.grids = None


PLAN = {"start": {"row": 0, "col": 0}, "goal": {"row": 12, "col": 12}, "rover_id": "lpr_1"}
PLAN_4D = {**PLAN, "n_slices": 24, "slice_hours": 1.0, "coarsen": 4}


# ── without the layers ─────────────────────────────────────────────────────


def test_plan_without_the_layer_says_the_criterion_was_not_applied(bare):
    payload = bare.post("/api/plan", json=PLAN).json()
    block = payload["roughness"]
    assert block["applied"] is False and block["route"] is None
    assert "build_roughness_cache" in block["reason"]
    assert block["validity"] == "MEASURED" and block["scale_validity"] == "MODEL"
    assert "roughness" not in payload["risk"]["sigma_sources"]


def test_plan_4d_without_the_layer_says_so_too(bare):
    payload = bare.post("/api/plan-4d", json=PLAN_4D).json()
    assert payload["roughness"]["applied"] is False and "build_roughness_cache" in payload["roughness"]["reason"]


def test_cell_telemetry_without_the_layer_has_null_fields(bare):
    payload = bare.get("/api/cell-telemetry", params={"row": 3, "col": 3}).json()
    assert payload["roughness_m"] is None and payload["f_roughness"] is None and payload["in_psr"] is None
    assert set(payload["cost_breakdown"]) == {"slope", "energy", "shadow", "thermal", "total"}


@pytest.mark.parametrize("path", ["/api/layers/roughness", "/api/layers/psr", "/api/psr-validation"])
def test_missing_layers_are_404s_that_name_the_script(bare, path):
    response = bare.get(path)
    assert response.status_code == 404
    assert "build_roughness_cache" in response.json()["detail"]


def test_manifest_omits_the_layers_until_they_are_loaded(bare):
    layers = bare.get("/api/terrain").json()["layers"]
    assert "roughness" not in layers and "psr" not in layers


# ── with the layers ────────────────────────────────────────────────────────


def test_manifest_lists_roughness_and_psr_as_measured(layered):
    layers = layered.get("/api/terrain").json()["layers"]
    assert layers["roughness"]["units"] == "m" and layers["roughness"]["validity"] == "MEASURED"
    assert layers["psr"]["units"] == "boolean" and layers["psr"]["validity"] == "MEASURED"
    assert layers["roughness"]["binary_url"].startswith("/api/layers/roughness?format=f32")
    assert layers["psr"]["max"] == 1.0 and layers["psr"]["min"] == 0.0


def test_roughness_layer_round_trips_as_float32(layered):
    response = layered.get("/api/layers/roughness?format=f32")
    assert response.status_code == 200
    assert response.headers["X-Layer-Validity"] == "MEASURED"
    values = np.frombuffer(response.content, dtype=BINARY_DTYPE).reshape(SHAPE)
    np.testing.assert_allclose(values, _roughness().astype(np.float32), rtol=1e-6)
    psr = np.frombuffer(layered.get("/api/layers/psr?format=f32").content, dtype=BINARY_DTYPE).reshape(SHAPE)
    assert psr.sum() == 16.0


def test_cell_telemetry_explains_the_roughness_criterion(layered):
    roughness, scale = _roughness(), _scale()
    payload = layered.get("/api/cell-telemetry", params={"row": 3, "col": 3}).json()
    assert payload["roughness_m"] == pytest.approx(roughness[3, 3])
    assert payload["f_roughness"] == pytest.approx(scale.f(roughness[3, 3]))
    assert payload["in_psr"] is False
    assert payload["cost_breakdown"]["roughness"] == pytest.approx(0.15 * scale.f(roughness[3, 3]), abs=1e-9)
    assert payload["layer_validity"]["roughness"] == "MEASURED"
    inside = layered.get("/api/cell-telemetry", params={"row": 11, "col": 3}).json()
    assert inside["in_psr"] is True


def test_plan_carries_the_roughness_route_block(layered):
    roughness = _roughness()
    payload = layered.post("/api/plan", json=PLAN).json()
    block = payload["roughness"]
    assert block["applied"] is True and block["weight"] == 0.15 and block["reason"] is None
    assert block["product"] == LDRM_PRODUCT and block["baseline_m"] == 100
    route = block["route"]
    assert route["n_cells"] == payload["summary"]["waypoint_count"]
    assert roughness.min() <= route["mean_roughness_m"] <= roughness.max()
    assert route["max_roughness_m"] >= route["mean_roughness_m"]
    assert 0.0 <= route["mean_f_roughness"] <= 1.0
    assert isinstance(route["cells_in_psr"], int)
    assert payload["risk"]["sigma_sources"]["roughness"]["source"] == "none"
    assert "sigma" in payload["risk"]["sigma_sources"]["roughness"]["reason"]


def test_plan_4d_carries_the_roughness_route_block(layered):
    payload = layered.post("/api/plan-4d", json=PLAN_4D).json()
    block = payload["roughness"]
    assert block["applied"] is True
    # WAIT states repeat a cell and are collapsed: positions = moves + 1.
    assert block["route"]["n_cells"] == payload["metrics"]["move_steps"] + 1
    assert block["route"]["max_roughness_m"] > 0.0 and block["route"]["coarsen"] == 4
    assert block["route"]["grid"] == "coarse: block-max roughness, block touches PSR"


def test_w_roughness_outside_the_range_is_a_422(layered):
    response = layered.post("/api/plan", json={**PLAN, "weights": {"w_roughness": 3.0}})
    assert response.status_code == 422


def test_zero_roughness_weight_removes_the_criterion_from_the_cost_layer(layered):
    default = layered.get("/api/layers/cost").json()
    zero = layered.get("/api/layers/cost?w_roughness=0.0").json()
    assert zero["metadata"]["cost_weights"]["w_roughness"] == 0.0
    assert default["metadata"]["cost_weights"]["w_roughness"] == 0.15
    d = np.array(default["data"], dtype=float)
    z = np.array(zero["data"], dtype=float)
    assert np.all(z <= d + 1e-12) and np.any(z < d)
    assert zero["metadata"]["cost_criteria"] == ["slope", "energy", "shadow", "thermal", "roughness"]


def test_psr_validation_reports_the_overlap_with_our_shadow_model(layered):
    payload = layered.get("/api/psr-validation").json()
    assert payload["threshold"] == 0.99
    assert payload["n_psr"] == 16 and payload["n_dark"] == 0
    assert payload["jaccard"] == 0.0 and payload["psr_recall"] == 0.0 and payload["dark_precision"] is None
    assert payload["product"] == LPSR_PRODUCT
    assert payload["validity"] == {"psr": "MEASURED", "shadow_ratio": "DERIVED"}
    assert "not a planning input" in payload["claim"].lower()
    looser = layered.get("/api/psr-validation?threshold=0.2").json()
    assert looser["n_dark"] == 256 and looser["jaccard"] == pytest.approx(16 / 256)


def test_profiles_and_rovers_publish_w_roughness(layered):
    profiles = layered.get("/api/profiles").json()
    assert profiles and all(p["weights"]["w_roughness"] == 0.15 for p in profiles.values())
    rovers = layered.get("/api/rovers").json()["rovers"]
    assert rovers and all(r["default_weights"]["w_roughness"] == 0.15 for r in rovers)
