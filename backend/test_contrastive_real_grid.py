"""D4 on the real Site11 grid.

Checks the CONTRACT of the contrast, not its result: which outcome a given
foil lands in is a measurement the report publishes, and it moves with the
window on disk. What must hold here is that the affine identity really IS the
planner's g-score on real terrain, that the gate replay agrees with
``_astar_core``, that the counterfactual arithmetic ties the routes it says it
ties -- and, the point of a presentation feature, that NOTHING the planner
reads moved.

Absolute counts are deliberately NOT asserted. The window on disk is
(2400, 2500) while much of the suite still expects (1500, 1000), so a test
that pinned "3 criteria found a threshold" would fail for a reason that has
nothing to do with D4. The report script is where the numbers live.

Skips without the processed grids. A skipped test is not a passing test: if
these skip, run the P1 pipeline first.
"""

from __future__ import annotations

import hashlib
import json
import math
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.contrastive import (
    CRITERION_WEIGHT_KEY,
    OUTCOME_DOMINATED,
    OUTCOME_FOUND_VS_FACT,
    OUTCOME_HARD_GATE,
    OUTCOME_OUTSIDE_BOUNDS,
    WEIGHT_MAX,
    WEIGHT_MIN,
    EdgeModel,
    explain_contrast,
    route_terms,
)
from app.cost_engine import COST_MODEL_ID, resolve_weights
from app.data_loader import load_preprocessed_grids
from app.main import app
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

# The three standard pairs this repo measures every routing feature on.
DAYTIME = ("lpr_1", (358, 494), (206, 426))
LUNAR_NIGHT = ("lpr_1", (186, 34), (494, 450))
VIPER_SHORT = ("nasa_viper", (358, 494), (346, 462))

# The checked-in v5 cost-grid lock from test_roughness_real_grid.py. D4 is a
# pure EXPLANATION feature: it must not move a single cost cell, and the
# cheapest proof is that this digest is still exactly what C4 recorded and C5
# and D5 left alone.
#
# LPR-1 only, deliberately. The nasa_viper digest recorded at C4 has not
# matched since 4af6989 corrected that profile's slope_max_deg from 20 to 15
# degrees, so it is a stale lock rather than a live one -- anchoring D4's
# bit-equality claim to it would mean this test fails for a reason that has
# nothing to do with D4.
LPR1_V5_COST_SHA256 = "55e1bb3cd3b9fb93403140b283cfa38fef8b93836a28512bc95f38db5ed893db"


def _digest(array: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(array, dtype=np.float64).tobytes()
    ).hexdigest()


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


def _plan(grids, rover_id, start, goal, weights=None):
    rover = get_rover(rover_id)
    adapted = grids_for_rover(grids, rover_id, weights)
    result = astar(adapted, start, goal, weights=weights, rover=rover)
    return adapted, rover, result


def _bresenham(a, b):
    (r0, c0), (r1, c1) = a, b
    out = []
    dr, dc = abs(r1 - r0), abs(c1 - c0)
    sr = 1 if r1 > r0 else -1
    sc = 1 if c1 > c0 else -1
    err = dr - dc
    r, c = r0, c0
    while True:
        out.append((r, c))
        if (r, c) == (r1, c1):
            break
        e2 = 2 * err
        if e2 > -dc:
            err -= dc
            r += sr
        if e2 < dr:
            err += dr
            c += sc
    return out


# ── bit-equality: the house contract ────────────────────────────────────────


def test_the_cost_grid_did_not_move(grids):
    """D4 adds an endpoint and touches no physics.

    The proof is the lock C4 left behind: if the checked-in v5 digest still
    matches, no route the planner produces can have changed, because the grid
    it searches is byte-for-byte the one it searched before.
    """
    assert _digest(grids_for_rover(grids, "lpr_1")["cost"]) == LPR1_V5_COST_SHA256


def test_the_cost_model_id_is_still_v5():
    assert COST_MODEL_ID.endswith("_v5")


def test_importing_the_module_does_not_perturb_a_plan(grids):
    """The endpoint is pure addition: not calling it changes nothing."""
    adapted, rover, before = _plan(grids, "lpr_1", *DAYTIME[1:])
    import app.contrastive  # noqa: F401  - the import itself is the test

    after = astar(adapted, DAYTIME[1], DAYTIME[2], rover=rover)
    assert before["path_pixels"] == after["path_pixels"]
    assert (
        before["metrics"]["total_weighted_cost"]
        == after["metrics"]["total_weighted_cost"]
    )


# ── the identity, on real terrain ───────────────────────────────────────────


@pytest.mark.parametrize("pair", [DAYTIME, LUNAR_NIGHT, VIPER_SHORT])
def test_the_decomposition_is_the_planners_own_g_score(grids, pair):
    """D + sum_k w_k I_k + B must equal total_weighted_cost, not approximate it.

    The tolerance is the rounding of the PUBLISHED field (round(., 4)), not a
    fudge factor: this module computes in float64 and the planner publishes
    four decimals.
    """
    rover_id, start, goal = pair
    adapted, rover, result = _plan(grids, rover_id, start, goal)
    assert result["error"] is None, result["error"]
    cells = [(int(r), int(c)) for r, c in result["path_pixels"]]
    weights = resolve_weights(None, rover)
    terms = route_terms(adapted, rover, cells, EdgeModel(adapted, rover))
    assert terms.affine_cost(weights) == pytest.approx(
        result["metrics"]["total_weighted_cost"], abs=1e-3
    )
    assert terms.affine_cost(weights) - terms.B == pytest.approx(
        result["metrics"]["total_weighted_cost_cells_only"], abs=1e-3
    )


@pytest.mark.parametrize("pair", [DAYTIME, LUNAR_NIGHT, VIPER_SHORT])
def test_the_gate_replay_clears_the_planners_own_route(grids, pair):
    """A TRANSCRIPTION check, not evidence the route is safe.

    It replays the same rules from the same functions over the same grid that
    produced the route, so it can only fail if the replay is mis-transcribed.
    That is worth locking; it says nothing about the terrain, and the clone
    test below shows the same route gating on other realisations of it.
    """
    rover_id, start, goal = pair
    adapted, rover, result = _plan(grids, rover_id, start, goal)
    assert result["error"] is None
    cells = [(int(r), int(c)) for r, c in result["path_pixels"]]
    terms = route_terms(adapted, rover, cells, EdgeModel(adapted, rover))
    assert terms.gates["clean"], terms.gates["by_rule"]


def test_the_clamp_stays_clear_on_a_real_route_at_nominal_weights(grids):
    """The identity's precondition, measured rather than assumed."""
    adapted, rover, result = _plan(grids, *DAYTIME)
    cells = [(int(r), int(c)) for r, c in result["path_pixels"]]
    weights = resolve_weights(None, rover)
    terms = route_terms(adapted, rover, cells, EdgeModel(adapted, rover))
    assert terms.clamped_cells(weights) == 0
    assert terms.clamp_margin(weights) > 1.0


# ── the outcomes ────────────────────────────────────────────────────────────


def _foil_from_weights(grids, rover_id, start, goal, weights):
    adapted = grids_for_rover(grids, rover_id, weights)
    result = astar(adapted, start, goal, weights=weights, rover=get_rover(rover_id))
    assert result["error"] is None
    return [(int(r), int(c)) for r, c in result["path_pixels"]]


def test_a_straight_line_foil_is_a_hard_gate_not_a_weight_question(grids):
    """The route a user actually draws, and the answer that must never be a number."""
    rover_id, start, goal = DAYTIME
    rover = get_rover(rover_id)
    out = explain_contrast(
        grids, start, goal, rover_id, rover, _bresenham(start, goal),
        scan_points=2, max_replans=0, clone_band=False,
    )
    assert out["outcome"] == OUTCOME_HARD_GATE
    assert out["counterfactual"] is None
    assert out["criterion_gap"] is None
    assert out["foil"]["gate_violations"]["n_violations"] > 0
    json.dumps(out, allow_nan=False)


def test_a_reweighted_foil_gets_a_real_criterion_decomposition(grids):
    rover_id, start, goal = DAYTIME
    rover = get_rover(rover_id)
    heavy = {"w_slope": 0.10, "w_energy": 0.10, "w_shadow": 0.10,
             "w_thermal": 0.70, "w_roughness": 0.15}
    foil = _foil_from_weights(grids, rover_id, start, goal, heavy)
    out = explain_contrast(
        grids, start, goal, rover_id, rover, foil,
        scan_points=2, max_replans=2, clone_band=False,
    )
    block = out["criterion_gap"]
    rebuilt = (
        block["delta_distance"]
        + block["delta_barrier"]
        + sum(t["delta_weighted"] for t in block["criteria"])
    )
    assert rebuilt == pytest.approx(block["delta_total"], rel=1e-9)
    # The fact is A*-optimal, so it is never dearer than the foil.
    assert block["delta_total"] >= -1e-6
    assert block["basis"] == "total_weighted_cost"
    json.dumps(out, allow_nan=False)


def test_every_published_threshold_actually_ties_the_two_routes(grids):
    """The closed form is exact or it is nothing."""
    rover_id, start, goal = DAYTIME
    rover = get_rover(rover_id)
    heavy = {"w_slope": 0.10, "w_energy": 0.10, "w_shadow": 0.10,
             "w_thermal": 0.70, "w_roughness": 0.15}
    foil_cells = _foil_from_weights(grids, rover_id, start, goal, heavy)
    adapted = grids_for_rover(grids, rover_id)
    weights = resolve_weights(None, rover)
    model = EdgeModel(adapted, rover)
    fact_result = astar(adapted, start, goal, rover=rover)
    fact = route_terms(
        adapted, rover, [(int(r), int(c)) for r, c in fact_result["path_pixels"]], model
    )
    foil = route_terms(adapted, rover, foil_cells, model)

    out = explain_contrast(
        grids, start, goal, rover_id, rover, foil_cells,
        scan_points=2, max_replans=0, clone_band=False,
    )
    checked = 0
    for entry in out["counterfactual"]["per_criterion"]:
        if entry["threshold"] is None:
            continue
        trial = dict(weights)
        trial[CRITERION_WEIGHT_KEY[entry["criterion"]]] = entry["threshold"]
        assert foil.affine_cost(trial) - fact.affine_cost(trial) == pytest.approx(
            0.0, abs=1e-6
        )
        checked += 1
    assert checked > 0, "no threshold was produced to check"


def test_the_direction_never_points_into_the_provably_empty_half(grids):
    """delta0 >= 0, so the sign of delta_I_k fixes which way the weight moves.

    Getting this backwards sends the vs_replanned scan into the interval where
    delta_vs_fact > 0 everywhere -- which, since delta_vs_replanned >=
    delta_vs_fact, is provably empty.
    """
    rover_id, start, goal = DAYTIME
    rover = get_rover(rover_id)
    heavy = {"w_slope": 0.10, "w_energy": 0.10, "w_shadow": 0.10,
             "w_thermal": 0.70, "w_roughness": 0.15}
    foil = _foil_from_weights(grids, rover_id, start, goal, heavy)
    out = explain_contrast(
        grids, start, goal, rover_id, rover, foil,
        scan_points=2, max_replans=0, clone_band=False,
    )
    for entry in out["counterfactual"]["per_criterion"]:
        if entry["direction"] is None:
            continue
        if entry["delta_integral"] > 0:
            assert entry["direction"] == "decrease"
        else:
            assert entry["direction"] == "increase"


def test_an_out_of_bounds_threshold_proves_the_replanned_regime_empty(grids):
    """No scan is spent where the bound already settles it."""
    rover_id, start, goal = DAYTIME
    rover = get_rover(rover_id)
    heavy = {"w_slope": 0.10, "w_energy": 0.10, "w_shadow": 0.10,
             "w_thermal": 0.70, "w_roughness": 0.15}
    foil = _foil_from_weights(grids, rover_id, start, goal, heavy)
    out = explain_contrast(
        grids, start, goal, rover_id, rover, foil,
        scan_points=3, max_replans=6, clone_band=False,
    )
    for entry in out["counterfactual"]["per_criterion"]:
        if entry["outcome"] != OUTCOME_OUTSIDE_BOUNDS:
            continue
        assert entry["vs_replanned"]["outcome"] is None
        assert "zero re-plans" in entry["vs_replanned"]["skipped_because"]
        assert not (WEIGHT_MIN <= entry["threshold"] <= WEIGHT_MAX)


def test_a_detour_is_dominated_and_the_proof_is_structural(grids):
    """A strictly longer route through the same corridor can never win.

    Constructed deliberately: a foil the PLANNER produced can never land in
    this outcome, because it is optimal at some weight vector by construction.
    """
    rover_id, start, goal = DAYTIME
    rover = get_rover(rover_id)
    adapted = grids_for_rover(grids, rover_id)
    fact_result = astar(adapted, start, goal, rover=rover)
    fact_cells = [(int(r), int(c)) for r, c in fact_result["path_pixels"]]
    on_route = set(fact_cells)
    traversable = np.asarray(adapted["traversable"], dtype=bool)
    middle = fact_cells[len(fact_cells) // 2]
    detour = None
    for distance in range(6, 40, 2):
        for offset in ((distance, 0), (0, distance), (-distance, 0), (0, -distance)):
            point = (middle[0] + offset[0], middle[1] + offset[1])
            if not (0 <= point[0] < traversable.shape[0] and 0 <= point[1] < traversable.shape[1]):
                continue
            if point in on_route or not traversable[point]:
                continue
            first = astar(adapted, start, point, rover=rover)
            second = astar(adapted, point, goal, rover=rover)
            if first["error"] or second["error"]:
                continue
            candidate = [(int(r), int(c)) for r, c in first["path_pixels"]]
            candidate += [(int(r), int(c)) for r, c in second["path_pixels"]][1:]
            if len(candidate) == len(set(candidate)) and candidate != fact_cells:
                detour = candidate
                break
        if detour:
            break
    if detour is None:
        pytest.skip("no simple detour found on this window")

    out = explain_contrast(
        grids, start, goal, rover_id, rover, detour,
        scan_points=2, max_replans=0, clone_band=False,
    )
    if out["outcome"] != OUTCOME_DOMINATED:
        pytest.skip(f"this detour is not dominated ({out['outcome']})")
    dominance = out["dominance"]
    assert dominance["criteria_none_better"] is True
    assert dominance["weight_independent_term"] >= 0.0
    # The proof's own claim: every criterion threshold must be out of bounds,
    # because no weight in [0, inf)^5 can make this foil cheaper.
    for entry in out["counterfactual"]["per_criterion"]:
        assert entry["outcome"] != OUTCOME_FOUND_VS_FACT


# ── the terrain the numbers sit on ──────────────────────────────────────────


def test_the_clone_band_moves_the_gap_and_reports_gate_failures(grids):
    """The band that decides whether a threshold is worth printing.

    Not an assertion on the numbers -- they move with the window -- but on the
    SHAPE of the honesty: the band must say how many clones it used, what it
    does not cover, and how often each route trips a gate on terrain NASA
    considers equally consistent with its own data.
    """
    rover_id, start, goal = DAYTIME
    rover = get_rover(rover_id)
    heavy = {"w_slope": 0.10, "w_energy": 0.10, "w_shadow": 0.10,
             "w_thermal": 0.70, "w_roughness": 0.15}
    foil = _foil_from_weights(grids, rover_id, start, goal, heavy)
    out = explain_contrast(
        grids, start, goal, rover_id, rover, foil,
        scan_points=2, max_replans=0, clone_band=True, max_clones=6,
    )
    band = out["terrain_band"]
    if not band.get("available"):
        pytest.skip(f"no clone cache: {band.get('reason')}")
    assert band["n_clones"] >= 2
    assert band["does_not_cover"] == ["thermal", "shadow", "roughness"]
    assert band["validity"] == "MODEL"
    assert isinstance(band["fact_gate_failures"], int)
    assert isinstance(band["foil_gate_failures"], int)
    assert band["provenance"] == "nasa_pgda_clones"


def test_the_resolution_block_names_a_level_for_every_verdict(grids):
    rover_id, start, goal = DAYTIME
    rover = get_rover(rover_id)
    heavy = {"w_slope": 0.10, "w_energy": 0.10, "w_shadow": 0.10,
             "w_thermal": 0.70, "w_roughness": 0.15}
    foil = _foil_from_weights(grids, rover_id, start, goal, heavy)
    out = explain_contrast(
        grids, start, goal, rover_id, rover, foil,
        scan_points=2, max_replans=0, clone_band=True, max_clones=6,
    )
    levels = {entry["level"]: entry for entry in out["resolution"]["levels"]}
    assert set(levels) == {
        "arithmetic", "publication", "model_discretisation", "terrain_ensemble"
    }
    # The barrier table's own discretisation is measured per pair, never
    # assumed: it is the difference between the tabulated and closed-form
    # barriers on these two routes.
    assert levels["model_discretisation"]["floor"] is not None
    assert math.isfinite(levels["model_discretisation"]["floor"])
    assert out["resolution"]["headline"]
    assert isinstance(out["resolution"]["actionable"], bool)


# ── the wire ────────────────────────────────────────────────────────────────


def test_the_endpoint_answers_on_the_real_grid(client, grids):
    rover_id, start, goal = DAYTIME
    heavy = {"w_slope": 0.10, "w_energy": 0.10, "w_shadow": 0.10,
             "w_thermal": 0.70, "w_roughness": 0.15}
    foil = _foil_from_weights(grids, rover_id, start, goal, heavy)
    response = client.post(
        "/api/explain-contrast",
        json={
            "start": {"row": start[0], "col": start[1]},
            "goal": {"row": goal[0], "col": goal[1]},
            "foil": [[r, c] for r, c in foil],
            "rover_id": rover_id,
            "scan_points": 2,
            "max_replans": 2,
            "terrain_band": False,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cost_units"] == "weighted_metres"
    assert body["criteria"] == ["slope", "energy", "shadow", "thermal", "roughness"]
    json.dumps(body, allow_nan=False)


def test_the_roughness_criterion_is_priced_because_the_cache_is_here(grids):
    """Five criteria is a property of THIS DISK, and the module reads it off
    the same stamp the cost grid carries rather than hardcoding it."""
    adapted = grids_for_rover(grids, "lpr_1")
    assert adapted["metadata"]["cost_criteria"] == [
        "slope", "energy", "shadow", "thermal", "roughness"
    ]
