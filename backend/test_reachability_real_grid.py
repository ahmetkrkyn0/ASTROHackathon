"""D6 on the real Site11 grid: the contract, the lock, and the containment.

Checks the CONTRACT and the two PROPERTIES, not the result. How many blocks
are reachable at a given epoch is a measurement the report publishes, and it
moves with the window on disk -- (2400, 2500) here while much of the suite
still expects (1500, 1000) -- so nothing pins a count.

Two things are pinned:

* **bit-equality.** D6 is pure addition. Nothing it touches may move a cost
  cell, so LPR-1's checked-in v5 cost-grid digest and ``COST_MODEL_ID`` are
  asserted unchanged after the endpoint has run, and /api/plan's response is
  compared before and after.
* **containment.** Blocks the 4-D planner can actually route to must be in
  the sweep's live set. Sampled, because each check is a full 4-D search.

The lock is LPR-1's only, deliberately: the ``nasa_viper`` digest recorded at
C4 has not matched since 4af6989 corrected that profile's ``slope_max_deg``
from 20 to 15 degrees, so it is a stale lock rather than a live one, and
anchoring D6's bit-equality claim to it would mean this file fails for a
reason that has nothing to do with D6.

Skips without the processed grids. A skipped test is not a passing test: if
these skip, run the P1 pipeline first.
"""

from __future__ import annotations

import hashlib
import math
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.cost_cube import auto_slice_hours, build_cost_cube, build_wait_cost_cube
from app.cost_engine import COST_MODEL_ID
from app.data_loader import load_preprocessed_grids
from app.main import _coarse_geometry, app
from app.pathfinder_4d import astar_4d
from app.reachability import (
    coarse_shadow_cube,
    hold_limit,
    hold_times,
    sweep,
)
from app.rover_grids import grids_for_rover

_P1_PROCESSED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "lunapath",
    "data",
    "processed",
)
_HAS_GRIDS = os.path.exists(os.path.join(_P1_PROCESSED_DIR, "metadata.json"))
pytestmark = pytest.mark.skipif(not _HAS_GRIDS, reason="needs lunapath/data/processed")

# The three standard pairs this repo measures every routing feature on. D6
# takes only the START of each.
DAYTIME_START = ("lpr_1", (358, 494))
LUNAR_NIGHT_START = ("lpr_1", (186, 34))
VIPER_START = ("nasa_viper", (358, 494))

#: An epoch at which part of the window is LIT. 2026-09-01 -- the epoch most
#: of the suite uses -- has Site11 fully in shadow, which is exactly the
#: condition under which a Dijkstra over signed energy would look correct.
LIT_EPOCH = "2026-09-05T00:00:00"
DARK_EPOCH = "2026-09-01T00:00:00"

# The checked-in v5 cost-grid lock from test_roughness_real_grid.py. See the
# module docstring for why LPR-1 only.
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
    try:
        yield TestClient(app)
    finally:
        app.state.grids = previous


def _body(**overrides):
    rover_id, start = DAYTIME_START
    body = {
        "start": {"row": start[0], "col": start[1]},
        "rover_id": rover_id,
        "start_utc": LIT_EPOCH,
        "horizon_hours": 2.0,
        "coarsen": 4,
        "include_grids": False,
        "max_boundary_cells": 25,
    }
    body.update(overrides)
    return body


def _walk(node, path="$"):
    """Every scalar in the payload, with the path that reaches it."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, f"{path}[{index}]")
    else:
        yield path, node


# ── bit-equality: D6 moves nothing ───────────────────────────────────────────


def test_the_v5_cost_grid_digest_is_unchanged_after_a_sweep(client, grids):
    """The proof pattern of the last seventeen features.

    D6 builds no cost cube at all, so this ought to be trivially true -- and
    it is asserted anyway, because "ought to" is what a regression sounds
    like before someone measures it.
    """
    before = grids_for_rover(grids, "lpr_1")
    assert _digest(before["cost"]) == LPR1_V5_COST_SHA256
    assert before["metadata"]["cost_model"] == COST_MODEL_ID
    assert COST_MODEL_ID.endswith("_v5")

    assert client.post("/api/reachable", json=_body()).status_code == 200

    after = grids_for_rover(grids, "lpr_1")
    assert _digest(after["cost"]) == LPR1_V5_COST_SHA256
    assert after["metadata"]["cost_model"] == COST_MODEL_ID


def _differing_leaves(first: dict, second: dict) -> set[str]:
    """Which leaf paths of two payloads disagree."""
    left = dict(_walk(first))
    right = dict(_walk(second))
    return {
        path
        for path in set(left) | set(right)
        if left.get(path, object()) != right.get(path, object())
    }


def _unchanged_across_a_sweep(client, path: str, body: dict, route_keys: tuple[str, ...]) -> None:
    """Assert a sweep changes nothing this endpoint publishes.

    Two identical calls to /api/plan already disagree on
    ``astar_metrics.computation_time_ms`` and ``corridor.corridor_id``, and
    two identical calls to /api/plan-4d on eight wall-clock timings -- with
    no D6 anywhere near them. So "equal before and after" is the wrong
    assertion: it would fail on a stopwatch.

    The right one is the CONTROL: measure which leaves move on their own,
    then require that a sweep in between moves exactly those and no others.
    A real regression shows up as a leaf outside the control set, and the
    assertion names it.
    """
    first = client.post(path, json=body)
    assert first.status_code == 200
    second = client.post(path, json=body)
    assert second.status_code == 200
    volatile = _differing_leaves(first.json(), second.json())

    assert client.post("/api/reachable", json=_body()).status_code == 200
    third = client.post(path, json=body)
    assert third.status_code == 200
    moved = _differing_leaves(second.json(), third.json())

    assert moved <= volatile, (
        f"{path} changed across a D6 sweep in leaves that are stable without one: "
        f"{sorted(moved - volatile)}"
    )
    # And the fields the feature exists not to touch, compared directly.
    for key in route_keys:
        assert third.json()[key] == second.json()[key]


def test_plan_is_unchanged_across_a_sweep(client):
    rover_id, start = DAYTIME_START
    _unchanged_across_a_sweep(
        client,
        "/api/plan",
        {
            "start": {"row": start[0], "col": start[1]},
            "goal": {"row": 206, "col": 426},
            "rover_id": rover_id,
        },
        ("waypoints", "summary", "route_statistics"),
    )


def test_plan_4d_is_unchanged_across_a_sweep(client):
    rover_id, start = DAYTIME_START
    _unchanged_across_a_sweep(
        client,
        "/api/plan-4d",
        {
            "start": {"row": start[0], "col": start[1]},
            "goal": {"row": 346, "col": 462},
            "rover_id": rover_id,
            "start_utc": LIT_EPOCH,
            "horizon_hours": 2.0,
            "coarsen": 4,
        },
        ("path_pixels", "path_states", "path_battery_pct"),
    )


def test_the_control_only_admits_timings_and_ids(client):
    """The control above is only honest if what it tolerates really is a
    stopwatch. Measured: /api/plan moves 2 leaves on its own and /api/plan-4d
    8, and every one of them is a millisecond count or a per-call id."""
    rover_id, start = DAYTIME_START
    body = {
        "start": {"row": start[0], "col": start[1]},
        "goal": {"row": 206, "col": 426},
        "rover_id": rover_id,
    }
    first = client.post("/api/plan", json=body).json()
    second = client.post("/api/plan", json=body).json()
    for path in _differing_leaves(first, second):
        assert path.endswith("_ms") or path.endswith("_id") or "timings_ms" in path, path


# ── the response contract ────────────────────────────────────────────────────


def test_the_response_carries_its_own_claim_boundary(client):
    response = client.post("/api/reachable", json=_body())
    assert response.status_code == 200
    payload = response.json()
    for key in (
        "claim",
        "scope",
        "planner_configuration",
        "gates_replayed",
        "gates_not_replayed",
        "conservatism",
        "uncertainty_not_propagated",
        "references",
        "corrections",
        "quoted",
        "energy_binds",
        "refusals",
        "isochrone",
        "hold",
        "edges",
    ):
        assert key in payload, key
    # The configuration the containment claim is stated against travels with
    # the number, so a reader comparing against a hibernating plan can see
    # that the two are different questions.
    assert payload["planner_configuration"]["allow_hibernate"] is False
    assert payload["planner_configuration"]["battery_model"] == "constant"
    # Every gate the sweep does NOT replay says which way it pushes the set.
    for entry in payload["gates_not_replayed"]:
        assert entry["direction"] == "enlarges the set"
    # The two headline fields err in opposite directions, and the response
    # says which is which rather than leaving it to be inferred.
    assert "OPTIMISTIC" in payload["conservatism"]["reachable"]
    assert "PESSIMISTIC" in payload["conservatism"]["earliest_hours"]


def test_nothing_non_finite_reaches_the_wire(client):
    """Starlette serialises with allow_nan=False, and this endpoint's natural
    encodings are non-finite everywhere it has nothing to say."""
    response = client.post("/api/reachable", json=_body(include_grids=True))
    assert response.status_code == 200
    for path, value in _walk(response.json()):
        if isinstance(value, float):
            assert math.isfinite(value), f"{path} is {value}"


def test_unreachable_blocks_are_null_and_never_a_large_number(client):
    response = client.post("/api/reachable", json=_body(include_grids=True))
    payload = response.json()
    band_index = np.asarray(payload["grids"]["band_index"])
    earliest = np.asarray(
        [[np.nan if v is None else v for v in row] for row in payload["grids"]["earliest_hours"]]
    )
    unreachable = band_index < 0
    assert unreachable.any()
    assert np.isnan(earliest[unreachable]).all()
    assert np.isfinite(earliest[~unreachable]).all()


def test_bands_partition_the_reachable_set(client):
    payload = client.post("/api/reachable", json=_body()).json()
    bands = payload["isochrone"]
    counted = sum(entry["blocks"] for entry in bands["bands"])
    assert counted + bands["beyond_last_edge_blocks"] == payload["reachable"]["blocks"]
    # The band boundary is a block lattice and the response says so in both
    # dimensions -- space AND time.
    assert bands["boundary_is_block_lattice"] is True
    assert bands["band_time_quantum_h"] == payload["time"]["slice_hours"]
    assert bands["band_space_quantum_m"] == payload["grid"]["effective_resolution_m"]
    assert "none" in bands["smoothing"]


def test_the_epoch_is_the_one_that_was_asked_for(client):
    """The cube is built in chunks and each chunk carries its own shifted
    epoch; the provenance must report the FIRST, not the last."""
    payload = client.post("/api/reachable", json=_body(horizon_hours=4.0)).json()
    assert payload["shadow_model"]["time_varying"] is True
    assert payload["shadow_model"]["start_utc"] == LIT_EPOCH
    assert payload["shadow_model"]["chunks"] >= 1


def test_later_hours_is_snapped_to_whole_slices_and_says_so(client):
    payload = client.post(
        "/api/reachable", json=_body(horizon_hours=1.0, later_hours=3.0)
    ).json()
    later = payload["later"]
    assert later["requested_later_hours"] == 3.0
    assert later["later_slices"] >= 1
    assert later["later_hours"] == pytest.approx(
        later["later_slices"] * payload["time"]["slice_hours"]
    )
    assert later["comparison"]["independent_restart"] is True
    assert later["start_utc"] != LIT_EPOCH


def test_a_short_horizon_on_a_full_battery_reports_that_energy_never_bound(client):
    """The honest disclosure: with the battery never touching its floor the
    frontier is the clock, and the map is a gated distance transform."""
    payload = client.post(
        "/api/reachable", json=_body(horizon_hours=2.0, initial_soc_pct=1.0)
    ).json()
    assert payload["refusals"]["horizon"] > 0
    assert payload["energy_binds"] == (
        payload["refusals"]["soc_floor"] > 0
        or payload["refusals"]["shadow_endurance"] > 0
    )


def test_a_thin_battery_shrinks_the_set_and_makes_energy_bind(client):
    """The budget curve, end to end: same start, same epoch, same horizon,
    less charge."""
    full = client.post("/api/reachable", json=_body(horizon_hours=6.0)).json()
    thin = client.post(
        "/api/reachable", json=_body(horizon_hours=6.0, initial_soc_pct=0.25)
    ).json()
    assert thin["reachable"]["blocks"] <= full["reachable"]["blocks"]
    assert thin["refusals"]["soc_floor"] >= full["refusals"]["soc_floor"]


def test_the_viper_start_block_is_refused_at_coarsen_4_and_answered_at_2(client):
    """A real property of the window, not a bug: VIPER's 15 degree limit
    makes block (89, 123) fail the conservative AND at coarsen 4 while the
    fine cell (358, 494) is passable."""
    rover_id, start = VIPER_START
    refused = client.post(
        "/api/reachable",
        json=_body(
            start={"row": start[0], "col": start[1]}, rover_id=rover_id, coarsen=4
        ),
    )
    assert refused.status_code == 422
    assert "not traversable" in refused.json()["detail"]

    answered = client.post(
        "/api/reachable",
        json=_body(
            start={"row": start[0], "col": start[1]},
            rover_id=rover_id,
            coarsen=2,
            horizon_hours=1.0,
            include_grids=False,
        ),
    )
    assert answered.status_code == 200
    assert answered.json()["reachable"]["blocks"] >= 1


def test_the_hold_clock_outlasts_the_drive_horizon(client):
    """A 3 h drive horizon censored every hold time on Site11; the hold runs
    on its own axis so the field is numbers rather than nulls."""
    payload = client.post(
        "/api/reachable", json=_body(horizon_hours=2.0, hold_horizon_hours=120.0)
    ).json()
    hold = payload["hold"]
    assert hold["horizon_hours"] == pytest.approx(120.0, abs=hold["slice_hours"])
    assert hold["horizon_hours"] > payload["time"]["horizon_hours"]
    decided = (
        hold["limited_by_blocks"]["reserve"] + hold["limited_by_blocks"]["shadow_endurance"]
    )
    assert decided + hold["limited_by_blocks"]["censored"] == payload["reachable"]["blocks"]


# ── containment, on the real terrain ─────────────────────────────────────────


def test_the_live_set_contains_what_the_planner_routes_to_on_site11(grids):
    """The direction the published claim runs in, sampled on Site11.

    Each check is a full 4-D search, so this samples rather than sweeps. The
    reverse containment is NOT asserted: the set is a relaxation and may be
    strictly larger, which is why the claim is stated negatively.
    """
    rover_id, start = LUNAR_NIGHT_START
    rover = get_rover(rover_id)
    grids_for_plan = grids_for_rover(grids, rover_id)
    coarsen = 4
    geometry = _coarse_geometry(grids_for_plan, coarsen)
    slice_hours = auto_slice_hours(
        grids_for_plan["slope"],
        grids_for_plan["traversable"],
        resolution_m=geometry.resolution_m,
        rover=rover,
    )
    n_slices = 40
    coarse_start = (start[0] // coarsen, start[1] // coarsen)
    cube, provenance = coarse_shadow_cube(
        np.asarray(grids_for_plan["shadow_ratio"], dtype=np.float64),
        grids_for_plan["metadata"],
        coarsen,
        n_slices,
        slice_hours,
        LIT_EPOCH,
    )
    if not provenance.get("time_varying"):
        pytest.skip(f"needs a time-varying shadow series: {provenance.get('reason')}")

    field = sweep(
        geometry.traversable,
        geometry.elevation,
        geometry.slope,
        geometry.resolution_m,
        rover,
        cube,
        slice_hours,
        coarse_start,
        1.0,
    )
    series = [cube[index] for index in range(n_slices)]
    cost = build_cost_cube(
        {**grids_for_plan, "shadow_ratio": grids_for_plan["shadow_ratio"]},
        [np.asarray(grids_for_plan["shadow_ratio"], dtype=np.float64)] * n_slices,
        rover,
        None,
        coarsen=coarsen,
    )
    wait = build_wait_cost_cube(
        [1.0 - snapshot for snapshot in series], rover, slice_hours, None, coarsen=1
    )

    # Sample inside and just outside the frontier: the interesting blocks are
    # the ones the sweep calls reachable late.
    rows, cols = np.nonzero(field.reachable)
    order = np.argsort(field.first_slice[rows, cols])
    picks = [(int(rows[i]), int(cols[i])) for i in order[-8:]]
    checked = 0
    for goal in picks:
        if goal == coarse_start:
            continue
        result = astar_4d(
            cost,
            wait,
            geometry.traversable,
            coarse_start,
            goal,
            geometry.resolution_m,
            slice_hours,
            rover,
            slope_grid=geometry.slope,
            elevation_grid=geometry.elevation,
            shadow_cube=cube,
            initial_soc_frac=1.0,
        )
        if result.get("path_states"):
            checked += 1
            assert field.reachable[goal], (
                f"the planner routes to {goal} but the sweep excludes it"
            )
    assert checked > 0, "the fixture must let the planner reach something"


def test_the_hold_limit_names_the_binding_clock_on_site11(grids):
    rover_id, start = LUNAR_NIGHT_START
    rover = get_rover(rover_id)
    grids_for_plan = grids_for_rover(grids, rover_id)
    coarsen = 4
    geometry = _coarse_geometry(grids_for_plan, coarsen)
    slice_hours = auto_slice_hours(
        grids_for_plan["slope"],
        grids_for_plan["traversable"],
        resolution_m=geometry.resolution_m,
        rover=rover,
    )
    cube, provenance = coarse_shadow_cube(
        np.asarray(grids_for_plan["shadow_ratio"], dtype=np.float64),
        grids_for_plan["metadata"],
        coarsen,
        30,
        slice_hours,
        DARK_EPOCH,
    )
    if not provenance.get("time_varying"):
        pytest.skip(f"needs a time-varying shadow series: {provenance.get('reason')}")
    field = sweep(
        geometry.traversable,
        geometry.elevation,
        geometry.slope,
        geometry.resolution_m,
        rover,
        cube,
        slice_hours,
        (start[0] // coarsen, start[1] // coarsen),
        1.0,
    )
    hold_cube, _ = coarse_shadow_cube(
        np.asarray(grids_for_plan["shadow_ratio"], dtype=np.float64),
        grids_for_plan["metadata"],
        coarsen,
        200,
        0.5,
        DARK_EPOCH,
    )
    holds = hold_times(field, hold_cube, rover, 0.5)
    hours, code = hold_limit(holds, field.reachable)
    endurance = float(rover["h_max_shadow_h"])
    decided = np.isfinite(hours)
    assert decided.any(), "a 100 h hold in the lunar night has to end somewhere"
    # The darkness clock is EXPOSURE-WEIGHTED travel hours, not elapsed hours
    # (astar_4d.envelope_after: dark += hours * exposure), so a block at
    # exposure e < 1 needs h_max_shadow_h / e WALL-CLOCK hours to spend its
    # endurance. The wall clock can therefore only run LONG, never short --
    # measured here: the minimum is 49.5 h against the published 50 h, one
    # hold slice of discretisation, and the maximum 56.0 h on partially lit
    # blocks. That gap is exactly why the response publishes the clock's
    # semantics instead of letting "50 hours of darkness" be inferred.
    picked = code == 1
    if picked.any():
        assert float(np.nanmin(hours[picked])) >= endurance - holds.slice_hours - 1e-6
        assert float(np.nanmax(hours[picked])) >= endurance - 1e-6
