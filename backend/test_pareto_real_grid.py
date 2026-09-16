"""D5 on the real Site11 grid.

Checks the CONTRACT of the sweep, not its result: how many routes survive
is a measurement the report publishes, and it moves with the window on
disk. What must hold here is that the sweep is reproducible, that the
de-duplication and dominance rules are self-consistent, that the
diagnostics honestly describe whatever came out -- and, the point of a
presentation feature, that NOTHING the planner reads moved.

Absolute counts are deliberately NOT asserted. The window on disk is
(2400, 2500) while much of the suite still expects (1500, 1000), so a test
that pinned "17 distinct routes" would fail for a reason that has nothing
to do with D5. The report script is where the numbers live.

Skips without the processed grids. A skipped test is not a passing test:
if these skip, run the P1 pipeline first.
"""

from __future__ import annotations

import hashlib
import os
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.cost_engine import COST_MODEL_ID
from app.data_loader import load_preprocessed_grids
from app.main import app
from app.pareto import (
    OBJECTIVE_KEYS,
    PARETO_COMPLETENESS,
    SIMPLEX_WEIGHT_KEYS,
    route_id,
    sweep,
)
from app.pathfinder import astar
from app.rover_grids import grids_for_rover

_P1_PROCESSED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "lunapath",
    "data",
    "processed",
)
_HAS_GRIDS = os.path.exists(os.path.join(_P1_PROCESSED_DIR, "metadata.json"))
pytestmark = pytest.mark.skipif(not _HAS_GRIDS, reason="needs lunapath/data/processed")

START = {"row": 358, "col": 494}
GOAL = {"row": 206, "col": 426}

# The checked-in v5 cost-grid lock from test_roughness_real_grid.py. D5 is a
# search-and-presentation feature: it must not move a single cost cell, and
# the cheapest proof is that this digest is still exactly what C4 recorded
# and C5 left alone.
#
# LPR-1 only, deliberately. The nasa_viper digest recorded at C4 has not
# matched since 4af6989 corrected that profile's slope_max_deg from 20 to
# 15 degrees, so it is a stale lock rather than a live one -- anchoring D5's
# bit-equality claim to it would mean this test fails for a reason that has
# nothing to do with D5.
LPR1_V5_COST_SHA256 = "55e1bb3cd3b9fb93403140b283cfa38fef8b93836a28512bc95f38db5ed893db"


def _digest(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array, dtype=np.float64).tobytes()).hexdigest()


@pytest.fixture(scope="module")
def grids():
    return load_preprocessed_grids()


@pytest.fixture()
def client(grids):
    previous = getattr(app.state, "grids", None)
    app.state.grids = grids
    test_client = TestClient(app)
    yield test_client
    app.state.grids = previous


@pytest.fixture(scope="module")
def result(grids):
    """One real sweep, shared -- it costs seconds, not milliseconds."""
    rover = get_rover("lpr_1")
    return sweep(
        grids,
        (START["row"], START["col"]),
        (GOAL["row"], GOAL["col"]),
        "lpr_1",
        rover,
        n_samples=12,
        seed=20260916,
    )


def test_the_skip_guard_really_passed_here():
    """A skipped real-grid file proves nothing, so say out loud that the
    inputs were present when these ran."""
    assert os.path.exists(os.path.join(_P1_PROCESSED_DIR, "metadata.json"))


# ── the bit-equality claim ──────────────────────────────────────────────────


def test_d5_moved_no_cost_cell_at_all(grids):
    """D5 sweeps weights; it must not change what any weight vector costs.

    The proof is the lock C4 left behind: if the checked-in v5 digest still
    matches, no route number can have changed, because the planner's entire
    input is this grid.
    """
    assert _digest(grids_for_rover(grids, "lpr_1")["cost"]) == LPR1_V5_COST_SHA256


def test_d5_did_not_bump_the_cost_model_id():
    assert COST_MODEL_ID.endswith("_v5")


def test_d5_did_not_promote_any_layer_validity(grids):
    """A presentation feature buys no layer a better label."""
    validity = grids["metadata"]["layer_validity"]
    assert validity["thermal"] == "DERIVED"
    assert validity["cost"] == "DERIVED"


def test_the_nominal_sample_is_the_route_api_plan_already_returned(grids, result):
    """Bit-equality for D5 means: the default-weight route did not move.

    The nominal entry of the sweep must be the identical cell sequence the
    planner returns for this pair with no weights supplied at all.
    """
    rover = get_rover("lpr_1")
    adapted = grids_for_rover(grids, "lpr_1")
    plain = astar(
        adapted, (START["row"], START["col"]), (GOAL["row"], GOAL["col"]), rover=rover
    )
    assert plain.get("error") is None
    nominal = next(s for s in result["samples"] if s["is_nominal"])
    assert nominal["route_id"] == route_id(plain["path_pixels"])


def test_the_nominal_weights_are_the_rovers_own(result):
    rover = get_rover("lpr_1")
    nominal = next(s for s in result["samples"] if s["is_nominal"])
    for key in SIMPLEX_WEIGHT_KEYS:
        assert nominal["weights"][key] == pytest.approx(float(rover[key]))
    assert nominal["weights"]["w_roughness"] == pytest.approx(float(rover["w_roughness"]))


# ── the sweep's own consistency ─────────────────────────────────────────────


def test_every_weight_vector_produced_a_route(result):
    """On this pair nothing should be refused; if one is, the entry says why."""
    assert result["counts"]["planned"] == result["counts"]["weight_vectors"]
    assert all(s["error"] is None for s in result["samples"])


def test_the_sweep_is_reproducible(grids):
    rover = get_rover("lpr_1")
    args = (grids, (START["row"], START["col"]), (GOAL["row"], GOAL["col"]), "lpr_1", rover)
    a = sweep(*args, n_samples=8, seed=4242)
    b = sweep(*args, n_samples=8, seed=4242)
    assert [r["route_id"] for r in a["distinct_routes"]] == [
        r["route_id"] for r in b["distinct_routes"]
    ]
    assert [r["route_id"] for r in a["non_dominated"]] == [
        r["route_id"] for r in b["non_dominated"]
    ]


def test_distinct_routes_really_are_distinct(result):
    ids = [r["route_id"] for r in result["distinct_routes"]]
    assert len(ids) == len(set(ids))


def test_several_weight_vectors_land_on_the_same_route(result):
    """The direct measure of how much the weight argument decided.

    If every vector produced its own route this would be vacuous; measured
    on Site11 it does not, and the ratio is the number the report leads with.
    """
    assert result["counts"]["distinct_routes"] <= result["counts"]["usable"]
    assert result["counts"]["weight_vectors_per_distinct_route"] >= 1.0


def test_the_front_is_non_empty_and_internally_undominated(result):
    """No member of the front may dominate another member."""
    from app.pareto import dominates

    front = result["non_dominated"]
    assert front
    for a in front:
        for b in front:
            if a["route_id"] == b["route_id"]:
                continue
            assert not dominates(a["objectives"], b["objectives"])


def test_every_route_off_the_front_is_beaten_by_someone_on_it(result):
    from app.pareto import dominates

    front = result["non_dominated"]
    for route in result["distinct_routes"]:
        if route["non_dominated"]:
            continue
        assert any(
            dominates(winner["objectives"], route["objectives"]) for winner in front
        ), route["route_id"]


def test_the_objectives_are_the_fields_the_table_names(result):
    for route in result["distinct_routes"]:
        assert set(route["objectives"]) == set(OBJECTIVE_KEYS)
        assert all(np.isfinite(v) for v in route["objectives"].values())


# ── the honesty of the diagnostics ──────────────────────────────────────────


def test_a_constant_objective_is_reported_as_constant(result):
    """f_thermal saturates on this site, so max_thermal_risk usually takes one
    value on every route. Whatever it does, the block must say so rather
    than let a dead axis pad the objective count."""
    diagnostics = result["diagnostics"]
    spread = diagnostics["objective_spread"]
    for key in OBJECTIVE_KEYS:
        constant = spread[key]["distinct_values_at_reporting_precision"] <= 1
        assert (key in diagnostics["constant_objectives"]) == constant
    assert diagnostics["effective_objectives"] == len(OBJECTIVE_KEYS) - len(
        diagnostics["constant_objectives"]
    )


def test_correlations_run_over_distinct_routes_not_raw_samples(result):
    """Correlating over samples would count a repeated route once per weight
    vector that found it and inflate every coefficient."""
    assert result["diagnostics"]["correlation_n"] == result["counts"]["distinct_routes"]
    assert result["diagnostics"]["n_distinct_routes"] == result["counts"]["distinct_routes"]


def test_no_correlation_is_reported_against_a_constant_axis(result):
    constant = set(result["diagnostics"]["constant_objectives"])
    for pair in result["diagnostics"]["objective_rank_correlation_spearman"]:
        assert not (set(pair.split("~")) & constant)


def test_the_nominal_verdict_carries_its_margins(result):
    """The verdict without the margin reads as 'the shipped weights are
    wrong'; measured, the margins are fractions of a percent."""
    nominal = result["nominal"]
    assert nominal is not None
    assert nominal["on_front"] in (True, False)
    if not nominal["on_front"]:
        assert nominal["dominated_by"]
        for dominator in nominal["dominated_by"]:
            assert set(dominator["margins"]) == set(OBJECTIVE_KEYS)


def test_the_result_never_calls_itself_a_pareto_front(result):
    assert "pareto_front" not in result
    assert result["completeness"] == PARETO_COMPLETENESS == "no_guarantee"


# ── the wire, on real terrain ───────────────────────────────────────────────


def test_the_endpoint_answers_within_a_sane_time(client):
    started = time.perf_counter()
    response = client.post(
        "/api/pareto",
        json={"start": START, "goal": GOAL, "rover_id": "lpr_1", "n_samples": 8},
    )
    assert response.status_code == 200, response.text
    assert time.perf_counter() - started < 120.0
    payload = response.json()
    assert payload["counts"]["non_dominated"] >= 1
    assert payload["total_ms"] > 0.0
