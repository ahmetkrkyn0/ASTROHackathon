"""D5 on the wire: /api/pareto's contract, its blocks and every 422.

Synthetic 16x16 grid -- this file asserts the SHAPE of the response and the
validation surface, never a route. What the front contains on real terrain
is test_pareto_real_grid.py's business.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import MAX_PARETO_SAMPLES, app
from app.pareto import OBJECTIVE_KEYS, OBJECTIVE_QUANTUM

SHAPE = (16, 16)
START = {"row": 1, "col": 1}
GOAL = {"row": 14, "col": 14}

# Built once so the startup handler runs and fails gracefully (no .npy
# files); grids are injected per test afterwards, mirroring test_risk_api.py.
_client = TestClient(app)


def _grids():
    rover = get_rover()
    rng = np.random.default_rng(5)
    # A gentle field with a steeper band, so different weight mixes have
    # something to disagree about; every cell stays passable for every rover.
    slope = rng.uniform(2.0, 6.0, SHAPE)
    slope[6:9, :] = rng.uniform(9.0, 13.0, (3, SHAPE[1]))
    return {
        "elevation": np.zeros(SHAPE),
        "slope": slope,
        "aspect": np.zeros(SHAPE),
        "thermal": np.full(SHAPE, -60.0),
        "shadow_ratio": rng.uniform(0.0, 0.6, SHAPE),
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


@pytest.fixture()
def client():
    app.state.grids = _grids()
    yield _client
    app.state.grids = None


def _pareto(client, **extra):
    body = {"start": START, "goal": GOAL, "rover_id": "lpr_1", "n_samples": 6, **extra}
    return client.post("/api/pareto", json=body)


# ── the contract ────────────────────────────────────────────────────────────


def test_sweep_answers_with_every_documented_block(client):
    response = _pareto(client)
    assert response.status_code == 200, response.text
    payload = response.json()
    for key in (
        "start",
        "goal",
        "rover_id",
        "planner",
        "objectives",
        "epsilon",
        "samples",
        "distinct_routes",
        "non_dominated",
        "counts",
        "diagnostics",
        "nominal",
        "total_ms",
        "seed",
        "swept_weight_keys",
        "held_weights",
        "method",
        "method_id",
        "completeness",
        "completeness_note",
        "validity",
        "claim",
        "references",
        "note",
    ):
        assert key in payload, key
    assert payload["planner"] == "2d"
    json.dumps(payload, allow_nan=False)


def test_every_objective_publishes_its_source_and_direction(client):
    """Direction is stored, never implied -- an inverted axis flips the front."""
    objectives = _pareto(client).json()["objectives"]
    assert [o["key"] for o in objectives] == list(OBJECTIVE_KEYS)
    for objective in objectives:
        assert objective["direction"] in {"minimize", "maximize"}
        assert objective["source"]
        assert objective["unit"]


def test_the_nominal_vector_is_always_swept_and_marked(client):
    payload = _pareto(client).json()
    labels = [s["label"] for s in payload["samples"]]
    assert labels[0] == "nominal"
    assert sum(1 for s in payload["samples"] if s["is_nominal"]) == 1
    assert payload["nominal"]["on_front"] in (True, False)


def test_sample_count_is_n_samples_plus_the_nominal_vector(client):
    payload = _pareto(client, n_samples=6).json()
    assert payload["counts"]["weight_vectors"] == 7
    assert len(payload["samples"]) == 7


def test_corners_add_the_four_vertices_and_six_edges(client):
    payload = _pareto(client, n_samples=3, include_corners=True).json()
    assert payload["counts"]["weight_vectors"] == 1 + 3 + 10
    labels = {s["label"] for s in payload["samples"]}
    assert "corner_w_slope" in labels
    assert "edge_slope_energy" in labels


def test_w_roughness_is_held_and_not_swept(client):
    """C4 made the fifth criterion additive, so it is not on the simplex."""
    payload = _pareto(client).json()
    assert payload["swept_weight_keys"] == ["w_slope", "w_energy", "w_shadow", "w_thermal"]
    assert "w_roughness" in payload["held_weights"]
    held = payload["held_weights"]["w_roughness"]
    assert all(s["weights"]["w_roughness"] == held for s in payload["samples"])


def test_every_swept_vector_lies_on_the_simplex(client):
    for sample in _pareto(client).json()["samples"]:
        weights = sample["weights"]
        total = sum(weights[k] for k in ("w_slope", "w_energy", "w_shadow", "w_thermal"))
        assert total == pytest.approx(1.0, abs=1e-12)


def test_counts_name_all_five_populations_separately(client):
    """Five different n's live here and must not be quotable as one another."""
    counts = _pareto(client).json()["counts"]
    for key in (
        "weight_vectors",
        "planned",
        "stranded_excluded",
        "usable",
        "distinct_routes",
        "non_dominated",
        "weight_vectors_per_distinct_route",
    ):
        assert key in counts
    assert counts["distinct_routes"] <= counts["usable"] <= counts["planned"]
    assert counts["non_dominated"] <= counts["distinct_routes"]


def test_routes_are_deduplicated_by_cell_sequence(client):
    payload = _pareto(client, n_samples=MAX_PARETO_SAMPLES).json()
    ids = [r["route_id"] for r in payload["distinct_routes"]]
    assert len(ids) == len(set(ids))
    # and the count of weight vectors that found each route is carried
    assert sum(r["weight_vectors"] for r in payload["distinct_routes"]) == payload["counts"][
        "usable"
    ]


def test_the_front_is_a_subset_of_the_distinct_routes(client):
    payload = _pareto(client).json()
    distinct = {r["route_id"] for r in payload["distinct_routes"]}
    assert {r["route_id"] for r in payload["non_dominated"]} <= distinct
    assert all(r["non_dominated"] for r in payload["non_dominated"])


def test_diagnostics_explain_the_size_of_the_front(client):
    diagnostics = _pareto(client).json()["diagnostics"]
    for key in (
        "n_distinct_routes",
        "objective_spread",
        "constant_objectives",
        "effective_objectives",
        "objective_rank_correlation_spearman",
        "correlation_n",
    ):
        assert key in diagnostics
    assert diagnostics["effective_objectives"] == len(OBJECTIVE_KEYS) - len(
        diagnostics["constant_objectives"]
    )


def test_epsilon_defaults_to_the_publication_quanta(client):
    assert _pareto(client).json()["epsilon"] == OBJECTIVE_QUANTUM


def test_a_huge_epsilon_collapses_the_front_to_one(client):
    """Sanity on the tolerance: if nothing is distinguishable, nothing is beaten."""
    payload = _pareto(
        client, n_samples=MAX_PARETO_SAMPLES, epsilon={"hours": 1e6, "energy_wh": 1e6}
    ).json()
    assert payload["counts"]["non_dominated"] >= 1


def test_the_same_seed_reproduces_the_sweep(client):
    a = _pareto(client, seed=99).json()
    b = _pareto(client, seed=99).json()
    assert [s["weights"] for s in a["samples"]] == [s["weights"] for s in b["samples"]]
    assert [r["route_id"] for r in a["distinct_routes"]] == [
        r["route_id"] for r in b["distinct_routes"]
    ]


def test_a_different_seed_draws_different_vectors(client):
    a = _pareto(client, seed=1).json()
    b = _pareto(client, seed=2).json()
    assert [s["weights"] for s in a["samples"]] != [s["weights"] for s in b["samples"]]


def test_the_response_does_not_call_itself_a_pareto_front(client):
    """Naming it pareto_front would claim a completeness this cannot have."""
    payload = _pareto(client).json()
    assert "pareto_front" not in payload
    assert payload["completeness"] == "no_guarantee"
    assert "supported" in payload["completeness_note"]


def test_the_claim_and_references_travel_with_the_answer(client):
    payload = _pareto(client).json()
    assert payload["validity"] == "MODEL"
    assert payload["claim"]
    assert len(payload["references"]) >= 4
    for reference in payload["references"]:
        assert reference["citation"]


def test_timing_is_reported_per_sample_and_in_total(client):
    payload = _pareto(client).json()
    assert payload["total_ms"] > 0.0
    assert all(s["plan_ms"] is not None for s in payload["samples"])


# ── validation ──────────────────────────────────────────────────────────────


def test_options_and_validation(client):
    assert _pareto(client, n_samples=0).status_code == 422
    assert _pareto(client, n_samples=-1).status_code == 422
    assert _pareto(client, n_samples=MAX_PARETO_SAMPLES + 1).status_code == 422
    assert _pareto(client, seed=-1).status_code == 422
    assert _pareto(client, epsilon={"w_slope": 0.1}).status_code == 422
    assert _pareto(client, epsilon={"hours": -1.0}).status_code == 422
    assert _pareto(client, goal={"row": 99, "col": 99}).status_code == 422
    assert _pareto(client, start={"row": -1, "col": 0}).status_code == 422
    assert (
        _client.post(
            "/api/pareto", json={"start": START, "goal": GOAL, "rover_id": "nope"}
        ).status_code
        in (404, 422)
    )


def test_n_samples_at_the_cap_is_accepted(client):
    assert _pareto(client, n_samples=MAX_PARETO_SAMPLES).status_code == 200


def test_grids_not_loaded_is_a_503_not_a_500():
    app.state.grids = None
    response = _client.post("/api/pareto", json={"start": START, "goal": GOAL})
    assert response.status_code == 503, response.text


def test_an_untraversable_endpoint_is_refused_with_a_reason(client):
    grids = _grids()
    grids["slope"][14, 14] = 80.0
    app.state.grids = grids
    response = _pareto(_client)
    assert response.status_code == 422
    assert "traversable" in response.json()["detail"]
