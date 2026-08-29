"""``/api/plan-4d`` against the real production grid, not a toy fixture.

test_plan_4d_endpoint.py exercises the endpoint against a 16x16, fully
open, obstacle-free fixture, where the default horizon and coarsening
never come close to their real-grid limits. Every earlier report of
"/api/plan-4d works" was true only on that fixture: on the checked-in
production grid (lunapath/data/processed/), the pre-fix default failed
10 of 12 random traversable pairs with "No path found within the time
horizon", and a further chunk of pairs land in coarse blocks that
coarsening itself disqualifies. Neither failure mode exists on the open
fixture, so neither was ever caught by test_plan_4d_endpoint.py.
(Faz 1-2-3 review, H2 -- the finding that H1 and H3 went unnoticed
because no test ran against real terrain.)

Skips entirely when the P1 pipeline has not been run (no
lunapath/data/processed/metadata.json) -- this file asserts about THIS
repository's checked-in grid, not about the pipeline's ability to
produce one.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids
from app.main import app

pytestmark = pytest.mark.skipif(
    not os.path.exists(os.path.join(_P1_PROCESSED_DIR, "metadata.json")),
    reason="lunapath/data/processed/metadata.json not present -- run the P1 pipeline first",
)

_ROVER = "lpr_1"
_COARSEN = 4  # Plan4DRequest's default


@pytest.fixture(scope="module")
def real_grids() -> dict:
    return load_preprocessed_grids()


@pytest.fixture()
def client(real_grids):
    app.state.grids = real_grids
    c = TestClient(app)
    yield c
    app.state.grids = None


def _random_traversable_pairs(traversable: np.ndarray, n: int, seed: int = 11):
    rng = np.random.default_rng(seed)
    idx = np.argwhere(traversable)
    pairs = []
    for _ in range(n):
        s = tuple(int(x) for x in idx[rng.integers(len(idx))])
        g = tuple(int(x) for x in idx[rng.integers(len(idx))])
        pairs.append((s, g))
    return pairs


def _same_coarse_cell(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] // _COARSEN == b[0] // _COARSEN and a[1] // _COARSEN == b[1] // _COARSEN


def test_default_horizon_solves_a_route_the_old_fixed_default_starved(client):
    """Locked-in regression for H1.

    This start/goal pair needs 33 coarse moves at coarsen=4 (measured
    against the checked-in grid). The old DEFAULT_PLAN_4D_SLICES=24
    covered at most ~24 coarse moves at the auto-derived slice length, so
    this pair failed with "No path found within the time horizon" even
    though a route existed. The fix sizes the default from the actual
    shortest-route distance, so this must now succeed with no
    n_slices/horizon_hours given at all.
    """
    body = {
        "start": {"row": 415, "col": 274},
        "goal": {"row": 283, "col": 341},
        "rover_id": _ROVER,
    }
    response = client.post("/api/plan-4d", json=body)
    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["path_pixels"]
    assert payload["metrics"]["arrival_slice"] is not None


def test_default_horizon_never_fails_with_the_old_generic_timeout_message(
    client, real_grids
):
    """Across a batch of random traversable pairs, a 4-D plan may
    legitimately fail because coarsening disconnects start from goal (a
    real, honestly-reported terrain property -- see the 422 test below).
    It must never fail with "No path found within the time horizon" at
    the DEFAULT horizon: that message means the horizon was too short for
    a route that exists, which the default is now sized to rule out.
    """
    traversable = np.asarray(real_grids["traversable"])
    pairs = _random_traversable_pairs(traversable, n=12)

    horizon_failures = []
    successes = 0
    for start, goal in pairs:
        if _same_coarse_cell(start, goal):
            continue  # a different, unrelated 422 path
        body = {
            "start": {"row": start[0], "col": start[1]},
            "goal": {"row": goal[0], "col": goal[1]},
            "rover_id": _ROVER,
        }
        response = client.post("/api/plan-4d", json=body)
        if response.status_code == 200:
            successes += 1
        elif response.status_code == 404:
            horizon_failures.append((start, goal, response.json()["detail"]))

    assert horizon_failures == [], (
        f"default horizon still starved {len(horizon_failures)} reachable "
        f"route(s): {horizon_failures}"
    )
    assert successes >= 1, "no pair succeeded at all -- likely a real regression"


def test_start_in_a_coarsening_disqualified_block_gets_a_specific_422(
    client, real_grids
):
    """A start whose coarse block coarsening itself disqualifies (any fine
    cell inside it over the slope/thermal limit) must be reported as a
    parameter problem the caller can act on (422, naming the reason), not
    surfaced as the planner's generic "not traversable" 404."""
    traversable = np.asarray(real_grids["traversable"])
    blocked = np.argwhere(~traversable)
    assert blocked.size, "fixture assumption: the real grid has blocked cells"
    row, col = (int(x) for x in blocked[0])
    goal = tuple(int(x) for x in np.argwhere(traversable)[-1])

    response = client.post(
        "/api/plan-4d",
        json={
            "start": {"row": row, "col": col},
            "goal": {"row": goal[0], "col": goal[1]},
            "rover_id": _ROVER,
        },
    )
    assert response.status_code == 422
    assert "time horizon" not in response.json()["detail"]
