"""D4 on the wire: /api/explain-contrast's contract, its blocks and every 422.

Synthetic 20x20 grid -- this file asserts the SHAPE of the response and the
validation surface, never a real route. What the contrast says about Site11
is test_contrastive_real_grid.py's business.

The serialisation tests are not decoration. Part (a) and the barrier produce
infinities BY DESIGN -- that is how impassability is expressed -- and
Starlette renders with ``allow_nan=False``, so an ``inf`` that reaches the
response is not a wrong number, it is a 500.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.contrastive import CONTRAST_OUTCOMES
from app.main import MAX_CONTRAST_REPLANS, MAX_CONTRAST_ROUTE_CELLS, app
from app.pathfinder import astar
from app.rover_grids import grids_for_rover

SHAPE = (20, 20)
START = {"row": 2, "col": 2}
GOAL = {"row": 17, "col": 17}

_client = TestClient(app)


def _grids():
    """A gentle ridged field: every cell passable for every rover, but with
    enough structure that different weight vectors pick different routes.

    The parameters are not arbitrary. Plain Gaussian noise at this resolution
    puts single-cell steps over lpr_1's 25 deg limit, which makes the goal
    itself untraversable and turns every test in this file into a 422 about
    the fixture rather than about the endpoint. Measured here: max cell slope
    10.8 deg, 400/400 cells passable.
    """
    rover = get_rover()
    rng = np.random.default_rng(5)
    rows, cols = np.mgrid[0:SHAPE[0], 0:SHAPE[1]]
    elevation = 1.2 * np.sin(cols / 3.0) * np.cos(rows / 4.0) + rng.normal(0.0, 0.2, SHAPE)
    grad_r, grad_c = np.gradient(elevation, 5.0)
    slope = np.degrees(np.arctan(np.hypot(grad_r, grad_c)))
    return {
        "elevation": elevation,
        "slope": slope,
        "aspect": np.zeros(SHAPE),
        "thermal": np.full(SHAPE, -60.0),
        "shadow_ratio": rng.uniform(0.0, 0.6, SHAPE),
        "traversable": np.ones(SHAPE, dtype=bool),
        "cost": np.full(SHAPE, 0.3),
        "metadata": {
            "origin": {"x": 156000.0, "y": 28000.0},
            "resolution_m": 5.0,
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


def _fact_cells(rover_id: str = "lpr_1") -> list[list[int]]:
    grids = grids_for_rover(_grids(), rover_id)
    result = astar(
        grids, (START["row"], START["col"]), (GOAL["row"], GOAL["col"]),
        rover=get_rover(rover_id),
    )
    assert result["error"] is None, result["error"]
    return [[int(r), int(c)] for r, c in result["path_pixels"]]


def _post(client, foil, **extra):
    body = {
        "start": START,
        "goal": GOAL,
        "foil": foil,
        "rover_id": "lpr_1",
        "scan_points": 2,
        "max_replans": 2,
        "terrain_band": False,
        **extra,
    }
    return client.post("/api/explain-contrast", json=body)


# ── the happy path ──────────────────────────────────────────────────────────


class TestContract:
    def test_the_fact_itself_is_recognised_rather_than_called_dominated(self, client):
        """Drawing the route we chose is not "your route can never win"."""
        response = _post(client, _fact_cells())
        assert response.status_code == 200
        body = response.json()
        assert body["outcome"] == "foil_is_the_fact"
        assert body["foil"]["is_the_fact"] is True
        assert body["counterfactual"] is None
        assert body["criterion_gap"]["delta_total"] == pytest.approx(0.0, abs=1e-9)

    def test_the_response_names_its_method_units_and_claim(self, client):
        body = _post(client, _fact_cells()).json()
        assert body["cost_units"] == "weighted_metres"
        assert body["planner"] == "2d"
        assert body["method_id"].startswith("affine_criterion_decomposition")
        assert "weighted_metres" in body["claim"]
        assert body["validity"] == "MODEL"
        assert body["outcome"] in CONTRAST_OUTCOMES
        assert set(body["outcome_vocabulary"]) == set(CONTRAST_OUTCOMES)

    def test_the_response_publishes_the_facts_own_pixels(self, client):
        """/api/plan publishes no path_pixels, so a caller cannot otherwise
        obtain the route it is being asked to contrast against."""
        body = _post(client, _fact_cells()).json()
        assert body["fact"]["path_pixels"][0] == [START["row"], START["col"]]
        assert body["fact"]["path_pixels"][-1] == [GOAL["row"], GOAL["col"]]
        assert body["start"] == [START["row"], START["col"]]
        assert body["goal"] == [GOAL["row"], GOAL["col"]]

    def test_the_weight_vector_actually_used_is_echoed_in_full(self, client):
        """A typo'd weight is refused, but the caller still gets to see the
        five numbers the answer was computed with."""
        body = _post(client, _fact_cells()).json()
        for key in ("w_slope", "w_energy", "w_shadow", "w_thermal", "w_roughness"):
            assert key in body["weights"]

    def test_the_vocabulary_block_says_a_whole_route_foil_is_atypical(self, client):
        body = _post(client, _fact_cells()).json()
        assert "TOTAL foil" in body["vocabulary"]["foil"]

    def test_every_outcome_carries_the_same_key_set(self, client):
        """A response whose shape depends on its outcome forces the client to
        guess which keys exist -- and the outcomes with the fewest keys are
        exactly the ones it most needs to handle."""
        expected = {
            "criterion_gap", "counterfactual", "dominance", "clamp", "terrain_band",
            "objective_gap", "objective_dominance", "resolution", "suppressed_because",
            "inconsistency", "outcome", "fact", "foil", "weights", "criteria",
            "cost_units", "claim", "validity", "references", "vocabulary",
        }
        bodies = [_post(client, _fact_cells()).json()]
        grids = _grids()
        thermal = np.asarray(grids["thermal"]).copy()
        thermal[9, 9] = -200.0
        grids["thermal"] = thermal
        app.state.grids = grids
        bodies.append(_post(client, [[2, 2]] + [[r, r] for r in range(3, 18)]).json())
        for body in bodies:
            missing = expected - set(body)
            assert not missing, f"{body['outcome']} is missing {sorted(missing)}"

    def test_every_block_survives_allow_nan_false(self, client):
        """Exactly how Starlette serialises; an inf here is a 500, not a number."""
        body = _post(client, _fact_cells()).json()
        json.dumps(body, allow_nan=False)


class TestHardGate:
    def _gated_foil(self, client):
        """A foil pushed through a cell no rover may enter.

        The cell is made impassable through the THERMAL field, not by
        injecting a traversable mask: ``grids_for_rover`` recomputes the mask
        from slope and temperature on every call precisely so a stale or
        hand-edited mask cannot steer the planner, so an injected one is a
        no-op and the test would silently assert nothing.
        """
        grids = _grids()
        thermal = np.asarray(grids["thermal"]).copy()
        thermal[9, 9] = -200.0  # below THERMAL_MIN_TRAVERSABLE_C
        grids["thermal"] = thermal
        app.state.grids = grids
        return [[2, 2]] + [[r, r] for r in range(3, 18)]

    def test_a_gated_foil_suppresses_the_cost_blocks_rather_than_filling_them(
        self, client
    ):
        foil = self._gated_foil(client)
        body = _post(client, foil).json()
        assert body["outcome"] == "hard_gate"
        assert body["criterion_gap"] is None
        assert body["counterfactual"] is None
        assert "suppressed_because" in body
        json.dumps(body, allow_nan=False)

    def test_the_violation_names_the_cell_the_rule_and_the_source(self, client):
        foil = self._gated_foil(client)
        gates = _post(client, foil).json()["foil"]["gate_violations"]
        assert gates["clean"] is False
        assert gates["n_violations"] >= 1
        entry = gates["violations"][0]
        for key in ("edge_index", "from_cell", "to_cell", "rule", "source"):
            assert key in entry
        assert gates["claim"].startswith("These are the planner's own gates")

    def test_the_rule_tally_is_complete_even_when_the_detail_is_truncated(self, client):
        foil = self._gated_foil(client)
        gates = _post(client, foil).json()["foil"]["gate_violations"]
        assert sum(gates["by_rule"].values()) == gates["n_violations"]
        assert gates["violations_truncated"] == (
            gates["n_violations"] > len(gates["violations"])
        )


# ── the refusals ────────────────────────────────────────────────────────────


class TestRefusals:
    def test_a_foil_that_does_not_share_the_start_is_422(self, client):
        foil = _fact_cells()
        response = _post(client, [[0, 0], [1, 1]] + foil[2:])
        assert response.status_code == 422
        assert response.json()["detail"]["reason"] == "foil_start_mismatch"

    def test_a_foil_that_does_not_share_the_goal_is_422(self, client):
        foil = _fact_cells()[:-1] + [[16, 16]]
        response = _post(client, foil)
        assert response.status_code == 422
        assert response.json()["detail"]["reason"] in (
            "foil_goal_mismatch",
            "foil_not_8_adjacent",
        )

    def test_a_jump_between_cells_is_422(self, client):
        foil = _fact_cells()
        response = _post(client, [foil[0], [10, 10]] + foil[1:])
        assert response.status_code == 422

    def test_a_repeated_cell_is_422(self, client):
        foil = _fact_cells()
        response = _post(client, [foil[0], foil[1], foil[0]] + foil[1:])
        assert response.status_code == 422
        assert response.json()["detail"]["reason"] == "foil_repeats_a_cell"

    def test_a_one_cell_foil_is_refused_by_the_schema(self, client):
        assert _post(client, [[2, 2]]).status_code == 422

    def test_an_over_long_foil_is_refused_by_the_schema(self, client):
        assert _post(client, [[2, 2]] * (MAX_CONTRAST_ROUTE_CELLS + 1)).status_code == 422

    def test_an_identical_start_and_goal_is_refused_with_its_own_message(self, client):
        response = _post(
            client, [[2, 2], [2, 3]], goal={"row": 2, "col": 2}
        )
        assert response.status_code == 422
        assert "nothing to compare" in str(response.json()["detail"])

    def test_a_typo_in_a_field_name_is_refused_rather_than_silently_dropped(
        self, client
    ):
        """The worst possible silent failure for THIS endpoint: the answer
        would be about a different weight vector than the caller asked."""
        response = _post(client, _fact_cells(), wieghts={"w_slope": 0.4})
        assert response.status_code == 422

    def test_an_out_of_range_weight_is_refused(self, client):
        response = _post(client, _fact_cells(), weights={"w_slope": 5.0})
        assert response.status_code == 422

    def test_a_non_traversable_start_is_refused_like_api_plan_does(self, client):
        """Same helper, same 422, same wording as /api/plan.

        The start is made impassable through the thermal field because
        ``grids_for_rover`` rebuilds the traversable mask from slope and
        temperature on every call.
        """
        grids = _grids()
        thermal = np.asarray(grids["thermal"]).copy()
        thermal[2, 2] = -200.0
        grids["thermal"] = thermal
        app.state.grids = grids
        response = _post(client, [[2, 2], [3, 3]])
        assert response.status_code == 422
        assert "not traversable" in str(response.json()["detail"])

    def test_an_out_of_grid_cell_is_refused(self, client):
        response = _post(client, [[2, 2], [-1, 1]])
        assert response.status_code == 422

    def test_a_scan_budget_above_the_cap_is_refused(self, client):
        response = _post(
            client, _fact_cells(), max_replans=MAX_CONTRAST_REPLANS + 1
        )
        assert response.status_code == 422

    def test_without_grids_the_answer_is_503(self):
        app.state.grids = None
        response = _client.post(
            "/api/explain-contrast",
            json={"start": START, "goal": GOAL, "foil": [[2, 2], [3, 3]]},
        )
        assert response.status_code == 503


# ── the budget ──────────────────────────────────────────────────────────────


class TestBudget:
    def test_zero_replans_leaves_the_exact_regime_intact(self, client):
        """vs_fact costs nothing; a caller in a hurry still gets a real answer."""
        grids = _grids()
        app.state.grids = grids
        foil = _fact_cells()
        # perturb the foil into a genuinely different route by re-planning heavy
        heavy = {"w_slope": 1.9, "w_energy": 0.259, "w_shadow": 0.142,
                 "w_thermal": 0.19, "w_roughness": 0.15}
        other = astar(
            grids_for_rover(grids, "lpr_1", heavy),
            (START["row"], START["col"]), (GOAL["row"], GOAL["col"]),
            weights=heavy, rover=get_rover("lpr_1"),
        )
        if other["error"] or list(other["path_pixels"]) == foil:
            pytest.skip("this synthetic grid has only one route")
        alt = [[int(r), int(c)] for r, c in other["path_pixels"]]
        body = _post(client, alt, max_replans=0).json()
        assert body["counterfactual"]["replans_used"] == 0
        assert body["counterfactual"]["per_criterion"]

    def test_the_replans_used_never_exceeds_the_budget(self, client):
        body = _post(client, _fact_cells(), max_replans=2).json()
        if body.get("counterfactual"):
            assert body["counterfactual"]["replans_used"] <= 2
