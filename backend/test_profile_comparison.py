"""Parity between /api/compare and the shared comparison it now delegates to.

The comparison arithmetic was lifted out of the route body so the AI tool
layer could reuse it. That is only worth doing if the two callers cannot
drift: if the assistant quoted numbers from a second implementation, its
answer would stop matching the route the map draws.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ["LUNAPATH_SKIP_STARTUP"] = "YES"

import numpy as np

from fastapi.testclient import TestClient

from app.constants import get_rover
from app.cost_engine import COST_MODEL_ID
from app.main import app
from app.profile_comparison import compare_all_profiles, solve_named_profiles

SHAPE = (20, 20)

client = TestClient(app, raise_server_exceptions=True)


def _make_grids() -> dict:
    return {
        "elevation": np.zeros(SHAPE, dtype=np.float64),
        "slope": np.full(SHAPE, 5.0, dtype=np.float64),
        "aspect": np.zeros(SHAPE, dtype=np.float64),
        "thermal": np.full(SHAPE, -50.0, dtype=np.float64),
        "shadow_ratio": np.full(SHAPE, 0.1, dtype=np.float64),
        "cost": np.full(SHAPE, 0.5, dtype=np.float64),
        "traversable": np.full(SHAPE, True, dtype=bool),
        "metadata": {
            "resolution_m": 80.0,
            "shape": list(SHAPE),
            "crs": "moon_sp",
            "source": "synthetic_test",
            "cost_weights": {
                "w_slope": 0.409,
                "w_energy": 0.259,
                "w_shadow": 0.142,
                "w_thermal": 0.190,
            },
            "cost_model": COST_MODEL_ID,
            "default_rover_id": "lpr_1",
        },
    }


def _inject() -> dict:
    grids = _make_grids()
    app.state.grids = grids
    return grids


def _comparable(results: list[dict]) -> list[dict]:
    """Drop the two fields that differ between identical runs by design."""
    trimmed = []
    for result in results:
        metrics = {
            key: value
            for key, value in (result.get("metrics") or {}).items()
            if key != "computation_time_ms"
        }
        trimmed.append(
            {
                "profile_id": result.get("profile_id"),
                "path_pixels": result.get("path_pixels"),
                "metrics": metrics,
                "constraint_check": result.get("constraint_check"),
                "simulation_summary": result.get("simulation_summary"),
            }
        )
    return trimmed


def test_endpoint_and_shared_helper_produce_identical_comparisons():
    grids = _inject()
    rover = get_rover("lpr_1")

    direct = compare_all_profiles(grids, [2, 2], [8, 8], "lpr_1", rover)

    response = client.post(
        "/api/compare", json={"start": [2, 2], "goal": [8, 8], "rover_id": "lpr_1"}
    )
    assert response.status_code == 200

    assert _comparable(direct) == _comparable(response.json()["results"])


def test_compare_endpoint_still_returns_all_four_profiles():
    _inject()
    response = client.post(
        "/api/compare", json={"start": [2, 2], "goal": [8, 8], "rover_id": "lpr_1"}
    )
    body = response.json()
    ids = {result["profile_id"] for result in body["results"]}
    assert ids == {"balanced", "energy_saver", "fast_recon", "shadow_traverse"}


def test_compare_endpoint_still_publishes_its_comparison_block():
    # The AI layer drops this block; the HTTP contract keeps it.
    _inject()
    response = client.post(
        "/api/compare", json={"start": [2, 2], "goal": [8, 8], "rover_id": "lpr_1"}
    )
    comparison = response.json()["comparison"]
    assert "recommendation" in comparison
    assert "most_efficient_profile" in comparison


def test_compare_endpoint_still_attaches_constraint_check_and_simulation():
    _inject()
    response = client.post(
        "/api/compare", json={"start": [2, 2], "goal": [8, 8], "rover_id": "lpr_1"}
    )
    first = response.json()["results"][0]
    assert "constraint_check" in first
    assert first["simulation_summary"]["total_energy_consumed_wh"] > 0


def test_compare_endpoint_still_validates_endpoints_with_422():
    _inject()
    response = client.post(
        "/api/compare", json={"start": [2, 2], "goal": [99, 99], "rover_id": "lpr_1"}
    )
    assert response.status_code == 422


def test_plan_multi_matches_the_shared_helper():
    grids = _inject()
    rover = get_rover("lpr_1")

    direct = solve_named_profiles(
        grids, [2, 2], [8, 8], "lpr_1", rover, ["balanced", "fast_recon"]
    )
    response = client.post(
        "/api/plan-multi",
        json={
            "start": [2, 2],
            "goal": [8, 8],
            "rover_id": "lpr_1",
            "profiles": ["balanced", "fast_recon"],
        },
    )
    assert response.status_code == 200
    assert _comparable(direct) == _comparable(response.json()["results"])


def test_plan_multi_still_reports_an_unknown_profile_in_place():
    _inject()
    response = client.post(
        "/api/plan-multi",
        json={
            "start": [2, 2],
            "goal": [8, 8],
            "rover_id": "lpr_1",
            "profiles": ["balanced", "no_such_profile"],
        },
    )
    results = response.json()["results"]
    assert results[1]["error"] == "Unknown profile: no_such_profile"
    assert results[0]["profile_id"] == "balanced"


def test_comparison_does_not_mutate_the_grid_store():
    grids = _inject()
    rover = get_rover("lpr_1")
    before_weights = dict(grids["metadata"]["cost_weights"])
    before_cost = np.array(grids["cost"], copy=True)

    compare_all_profiles(grids, [2, 2], [8, 8], "lpr_1", rover)

    assert grids["metadata"]["cost_weights"] == before_weights
    assert np.array_equal(grids["cost"], before_cost)


def test_comparison_does_not_publish_a_corridor():
    grids = _inject()
    rover = get_rover("lpr_1")
    app.state.active_corridor = None

    compare_all_profiles(grids, [2, 2], [8, 8], "lpr_1", rover)

    assert getattr(app.state, "active_corridor", None) is None
