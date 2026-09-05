"""C4 on the real Site11 grid: the measured roughness and PSR layers from
NASA PGDA product 90, the criterion's contract (finite, in [0, 1], not a
restatement of slope), the PSR-vs-shadow statistic in range, the standard
2-D pairs planning with the block applied, and the cost-grid locks: the
five-criterion v5 digests WITH the layer and the pre-C4 v4 digests with
the layer removed (the four terms are untouched, bit for bit).

Skips without the processed grids or the roughness/PSR cache. Nothing
here asserts a route or a Jaccard value -- the report measures those --
only the contract.
"""

from __future__ import annotations

import hashlib
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient
from scipy.stats import spearmanr

from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids
from app.main import app
from app.roughness import PSR_CACHE_FILENAME, ROUGHNESS_CACHE_FILENAME, RoughnessScale, psr_shadow_overlap
from app.rover_grids import grids_for_rover

_HAS_GRIDS = os.path.exists(os.path.join(_P1_PROCESSED_DIR, "metadata.json"))
_HAS_CACHE = _HAS_GRIDS and all(
    os.path.exists(os.path.join(_P1_PROCESSED_DIR, name)) for name in (ROUGHNESS_CACHE_FILENAME, PSR_CACHE_FILENAME)
)
pytestmark = pytest.mark.skipif(not _HAS_CACHE, reason="needs lunapath/data/processed and the roughness/PSR cache")

# SHA-256 of the Site11 cost grid (default weights) as computed by the C3
# build on 5 Sept 2026, before C4 -- the four-term formula. With the
# roughness layer removed from the base grids, C4 must reproduce it byte
# for byte: the fifth term is additive and the other four are untouched.
V4_COST_SHA256 = {
    "lpr_1": "0e74607d668efa227af0357fde24a53a95636a6bf13cd11af9d97ac92f5c7bd1",
    "nasa_viper": "8788936cee3f8cde6cff1db5370fd9a09776e62f50c69e59a1a95581375ad3cf",
}
# The same grids WITH the LDRM roughness layer (w_roughness 0.15), as
# computed by the C4 build on 5 Sept 2026 from the cache built that day.
V5_COST_SHA256 = {
    "lpr_1": "55e1bb3cd3b9fb93403140b283cfa38fef8b93836a28512bc95f38db5ed893db",
    "nasa_viper": "593f8e46730ad0e1002bb679229c3bf7ff4ed9f9b2bf7f3d37847d1bd418c56a",
}

PAIRS = [
    ("lpr_1", {"row": 358, "col": 494}, {"row": 206, "col": 426}),
    ("lpr_1", {"row": 186, "col": 34}, {"row": 494, "col": 450}),
    ("nasa_viper", {"row": 358, "col": 494}, {"row": 206, "col": 426}),
    ("nasa_viper", {"row": 358, "col": 494}, {"row": 346, "col": 462}),
]


def _digest(grid: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(np.asarray(grid, dtype=np.float64)).tobytes()).hexdigest()


def _without_roughness(grids: dict) -> dict:
    base = {k: v for k, v in grids.items() if k != "roughness"}
    base["metadata"] = {k: v for k, v in grids["metadata"].items() if k != "roughness"}
    return base


@pytest.fixture(scope="module")
def grids():
    return load_preprocessed_grids()


def test_the_layers_are_measured_finite_and_in_range(grids):
    rough = np.asarray(grids["roughness"])
    psr = np.asarray(grids["psr"])
    assert rough.shape == psr.shape == tuple(grids["metadata"]["shape"])
    assert np.all(np.isfinite(rough)) and np.all(rough >= 0.0)
    assert set(np.unique(psr).tolist()) <= {0.0, 1.0}
    validity = grids["metadata"]["layer_validity"]
    assert validity["roughness"] == "MEASURED" and validity["psr"] == "MEASURED"
    assert validity["cost"] == "DERIVED"  # the weakest input still decides
    assert grids["metadata"]["cost_criteria"] == ["slope", "energy", "shadow", "thermal", "roughness"]
    meta = grids["metadata"]["roughness"]
    assert meta["product"] == "LDRM_80S_50MPP_ADJ_ROUGH_100M" and meta["resampling"] == "nearest"
    assert meta["crs_match"]["same_projection"] is True
    assert meta["registration_check"]["spearman"] >= 0.9


def test_the_criterion_is_in_unit_range_and_not_a_restatement_of_slope(grids):
    scale = RoughnessScale.from_meta(grids["metadata"]["roughness"]["scale"])
    f = scale.f_grid(grids["roughness"])
    assert f.min() >= 0.0 and f.max() <= 1.0
    assert np.std(f) > 0.05  # it ranks, it does not sit on one value
    rho = spearmanr(np.asarray(grids["roughness"]).ravel(), np.asarray(grids["slope"]).ravel()).statistic
    assert np.isfinite(rho) and abs(rho) < 0.9


def test_psr_overlap_statistics_are_in_range(grids):
    stats = psr_shadow_overlap(grids["psr"], grids["shadow_ratio"], grids.get("thermal_min"), 0.99)
    assert stats["n_psr"] > 0 and stats["n_dark"] > 0
    for key in ("jaccard", "psr_recall", "dark_precision", "false_positive_fraction", "psr_fraction"):
        assert 0.0 <= stats[key] <= 1.0, key
    assert stats["thermal_min_median_inside_psr"] < stats["thermal_min_median_outside_psr"]


@pytest.mark.parametrize("rover_id", list(V5_COST_SHA256))
def test_the_cost_grid_with_the_layer_is_the_v5_grid_and_without_it_the_v4_grid(grids, rover_id):
    with_layer = grids_for_rover(grids, rover_id)
    assert with_layer["metadata"]["cost_criteria"][-1] == "roughness"
    assert _digest(with_layer["cost"]) == V5_COST_SHA256[rover_id]
    without = grids_for_rover(_without_roughness(grids), rover_id)
    assert without["metadata"]["cost_criteria"] == ["slope", "energy", "shadow", "thermal"]
    assert _digest(without["cost"]) == V4_COST_SHA256[rover_id]
    # w_roughness = 0 with the layer present is the v4 grid too: the term is purely additive.
    assert _digest(grids_for_rover(grids, rover_id, {"w_roughness": 0.0})["cost"]) == V4_COST_SHA256[rover_id]


@pytest.fixture()
def client(grids):
    app.state.grids = grids
    c = TestClient(app)
    yield c
    app.state.grids = None


@pytest.mark.parametrize("rover_id, start, goal", PAIRS)
def test_the_standard_pairs_plan_with_the_criterion_applied(client, rover_id, start, goal):
    response = client.post("/api/plan", json={"start": start, "goal": goal, "rover_id": rover_id})
    assert response.status_code == 200, response.text
    payload = response.json()
    block = payload["roughness"]
    assert block["applied"] is True and block["weight"] == 0.15
    route = block["route"]
    assert route["n_cells"] == payload["summary"]["waypoint_count"]
    assert 0.0 < route["mean_roughness_m"] <= route["max_roughness_m"]
    assert 0.0 <= route["mean_f_roughness"] <= 1.0
    assert payload["risk"]["sigma_sources"]["roughness"]["source"] == "none"


def test_psr_validation_endpoint_reports_on_the_real_window(client):
    payload = client.get("/api/psr-validation").json()
    assert payload["n_psr"] == int(np.asarray(load_preprocessed_grids()["psr"]).sum())
    assert 0.0 <= payload["jaccard"] <= 1.0 and payload["validity"]["psr"] == "MEASURED"
    manifest = client.get("/api/terrain").json()["layers"]
    assert manifest["roughness"]["validity"] == "MEASURED" and manifest["psr"]["validity"] == "MEASURED"
