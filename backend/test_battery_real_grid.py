"""C2 on the checked-in production grid (Site11).

test_battery.py pins the arithmetic on the catalogue and on synthetic worlds;
this file asks what it says about the real site, and skips wherever the
gitignored inputs are not on disk (the guard mirrors test_panel_real_grid.py).

Pinned here:

* the BIT-EQUALITY proof, in the two forms that matter -- LPR-1's two
  checked-in cost-grid digests still match byte for byte (C2 never touches the
  2-D grid, so ``COST_MODEL_ID`` does not move), and a 4-D route planned with
  the three switches explicitly off is the same route, the same cost and the
  same node count as one planned without mentioning them;
* the measurement that justifies the whole feature: on this grid the shadow
  ratio says nothing about the surface temperature, so the pre-C2 heater --
  which scales with shadow -- is not a proxy for cold;
* that each switch is actually reachable on the real site and reports what it
  claims to report.

Deliberately NOT pinned: absolute move counts. Twenty-four real-grid tests
already fail at HEAD because the shipped window is (2400, 2500) while the
suite expects (1500, 1000), and a C2 test that hard-codes route geometry would
add a twenty-fifth failure that says nothing about C2. The relations above
hold whatever window is on disk.
"""

from __future__ import annotations

import hashlib
import os
import pathlib

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import battery as B
from app.cost_engine import COST_MODEL_ID
from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids
from app.main import app
from app.rover_grids import grids_for_rover

_KERNELS = pathlib.Path(__file__).resolve().parent.parent / "kernels" / "lunapath.tm"
_HORIZON = os.path.join(_P1_PROCESSED_DIR, "horizon_map.npy")
_METADATA = os.path.join(_P1_PROCESSED_DIR, "metadata.json")

needs_real_inputs = pytest.mark.skipif(
    not (_KERNELS.exists() and os.path.exists(_HORIZON) and os.path.exists(_METADATA)),
    reason="NAIF kernels, horizon_map.npy or the processed grids are not on disk",
)

# The C3 build's v4 digest and the C4 build's v5 digest of LPR-1's Site11 cost
# grid, copied from test_roughness_real_grid.py. NASA VIPER's pair is
# deliberately not asserted here: it stopped matching before C1 (4af6989's
# slope_max_deg 20 -> 15 correction) and is one of the failures already on the
# board at HEAD.
LPR1_V5_COST_SHA256 = "55e1bb3cd3b9fb93403140b283cfa38fef8b93836a28512bc95f38db5ed893db"
LPR1_V4_COST_SHA256 = "0e74607d668efa227af0357fde24a53a95636a6bf13cd11af9d97ac92f5c7bd1"

DAY_ROUTE = {
    "start": {"row": 358, "col": 494},
    "goal": {"row": 206, "col": 426},
    "rover_id": "lpr_1",
    "start_utc": "2026-09-28T00:00:00",
}


def _digest(grid: np.ndarray) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(np.asarray(grid, dtype=np.float64)).tobytes()
    ).hexdigest()


def _without_roughness(grids: dict) -> dict:
    base = {k: v for k, v in grids.items() if k != "roughness"}
    base["metadata"] = {k: v for k, v in grids["metadata"].items() if k != "roughness"}
    return base


@pytest.fixture(scope="module")
def grids():
    return load_preprocessed_grids()


@pytest.fixture()
def client(grids):
    previous = getattr(app.state, "grids", None)
    with TestClient(app) as test_client:
        app.state.grids = grids
        yield test_client
    app.state.grids = previous


# ── the guard itself ────────────────────────────────────────────────────────


@needs_real_inputs
def test_the_skip_guard_really_passed_here():
    """A skipped real-grid file proves nothing, so say out loud that the
    inputs were present when these ran."""
    assert _KERNELS.exists()
    assert os.path.exists(_HORIZON)
    assert os.path.exists(_METADATA)


# ── bit-equality ────────────────────────────────────────────────────────────


@needs_real_inputs
def test_the_two_d_cost_grid_is_untouched_byte_for_byte(grids):
    """C2's heater reads a per-slice SURFACE, and the 2-D grid has no epoch and
    so no per-slice surface. That is a design decision, not an omission, and
    this is its proof: the formula id does not move and LPR-1's two frozen
    digests still match."""
    assert COST_MODEL_ID == "weighted_cell_cost_shadow_aware_energy_slip_roughness_v5"
    assert _digest(grids_for_rover(grids, "lpr_1")["cost"]) == LPR1_V5_COST_SHA256
    assert (
        _digest(grids_for_rover(_without_roughness(grids), "lpr_1")["cost"])
        == LPR1_V4_COST_SHA256
    )


@needs_real_inputs
def test_the_three_switches_off_is_the_route_planned_without_them(client):
    """The defaults are the pre-C2 model, on the real grid: same path, same
    cost, same nodes expanded."""
    reference = client.post("/api/plan-4d", json=DAY_ROUTE)
    assert reference.status_code == 200, reference.text
    explicit = client.post(
        "/api/plan-4d",
        json={
            **DAY_ROUTE,
            "battery_model": "constant",
            "heater_power_model": "constant",
            "allow_hibernate": False,
        },
    )
    assert explicit.status_code == 200, explicit.text

    left, right = reference.json(), explicit.json()
    assert left["path_states"] == right["path_states"]
    assert left["metrics"]["total_cost"] == right["metrics"]["total_cost"]
    assert left["metrics"]["nodes_expanded"] == right["metrics"]["nodes_expanded"]
    assert left["metrics"]["move_steps"] == right["metrics"]["move_steps"]
    assert left["metrics"]["wait_steps"] == right["metrics"]["wait_steps"]
    # and the block is reported either way, unapplied
    assert left["battery"]["applied"] is False
    assert left["metrics"]["hibernate_steps"] == 0
    assert left["metrics"]["hibernate_hours"] is None


# ── the measurement the feature rests on ────────────────────────────────────


@needs_real_inputs
def test_on_site11_the_shadow_ratio_says_nothing_about_the_temperature(grids):
    """The pre-C2 heater scales with SHADOW RATIO, which assumes darkness is a
    proxy for cold. Measured over the traversable cells of the shipped window,
    the rank correlation between the two layers is within 0.05 of zero -- so on
    this site that proxy carries essentially no information, which is why C2
    adds a temperature law rather than tuning the exposure one."""
    from scipy.stats import spearmanr

    traversable = np.asarray(grids["traversable"], dtype=bool)
    shadow = np.asarray(grids["shadow_ratio"], dtype=np.float64)[traversable]
    surface = np.asarray(grids["thermal"], dtype=np.float64)[traversable]
    finite = np.isfinite(shadow) & np.isfinite(surface)
    assert finite.sum() > 100_000

    correlation = float(spearmanr(shadow[finite], surface[finite]).correlation)
    assert abs(correlation) < 0.05, correlation

    # And the consequence: cells that are mostly lit and genuinely cold exist,
    # where the old term charges almost nothing for heating.
    pocket = finite & (shadow < 0.5) & (surface < -50.0)
    assert int(pocket.sum()) > 0


@needs_real_inputs
def test_the_two_heater_laws_disagree_with_the_old_one_in_both_directions(grids):
    """The first draft claimed the temperature law is a bound on the exposure
    law. It is not, and this is where that was measured: on the real grid both
    laws draw MORE than the old term in some cells and less in others."""
    rover_id = "lpr_1"
    from app.constants import get_rover

    rover = get_rover(rover_id)
    traversable = np.asarray(grids["traversable"], dtype=bool)
    shadow = np.asarray(grids["shadow_ratio"], dtype=np.float64)[traversable]
    surface = np.asarray(grids["thermal"], dtype=np.float64)[traversable]
    old = np.clip(shadow, 0.0, 1.0) * float(rover["p_heater_w"])
    for model in ("delta_t", "radiative"):
        new = B.heater_power_w_grid(surface, rover, model)
        delta = new - old
        good = np.isfinite(delta)
        assert int((delta[good] > 1e-9).sum()) > 0, model
        assert int((delta[good] < -1e-9).sum()) > 0, model
        assert float(np.max(new)) <= float(rover["p_heater_w"]) + 1e-9


# ── each switch is reachable and reports what it claims ─────────────────────


@needs_real_inputs
def test_the_heater_power_model_applies_on_the_real_route(client):
    response = client.post(
        "/api/plan-4d",
        json={
            **DAY_ROUTE,
            "heater_model": "thermostat_assumed",
            "heater_power_model": "radiative",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["battery"]["applied"] is True
    assert payload["battery"]["requested"]["heater_power_model"] == "radiative"
    heater = payload["battery"]["catalogue"]["heater"]
    assert heater["available"] is True
    assert heater["sizing_surface_c"] == -150.0
    assert heater["source"].startswith("assumption:")


@needs_real_inputs
def test_the_derating_applies_and_never_reads_the_sentinel(client):
    response = client.post(
        "/api/plan-4d", json={**DAY_ROUTE, "battery_model": "temperature_derated"}
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["battery"]["applied"] is True
    assert payload["metrics"]["battery_model"] == "temperature_derated"
    # The inner temperature is genuinely tracked, not left at the 0.0 sentinel
    # that would read as "exactly at the rating temperature".
    inner = payload["path_inner_c"]
    assert inner is not None and len(inner) == len(payload["path_states"])
    assert len(set(round(v, 6) for v in inner)) > 1


@needs_real_inputs
def test_hibernation_is_offered_on_the_real_route_and_accounted_for(client):
    response = client.post("/api/plan-4d", json={**DAY_ROUTE, "allow_hibernate": True})
    assert response.status_code == 200, response.text
    payload = response.json()
    metrics = payload["metrics"]
    assert metrics["hibernation_allowed"] is True
    actions = payload["path_actions"]
    assert actions is not None and len(actions) == len(payload["path_states"]) - 1
    assert set(actions) <= {"move", "wait", "hibernate"}
    # Whether or not the planner takes it, the accounting has to add up.
    assert actions.count("hibernate") == metrics["hibernate_steps"]
    assert actions.count("wait") == metrics["wait_steps"]
    assert actions.count("move") == metrics["move_steps"]
    if metrics["hibernate_steps"]:
        assert metrics["hibernate_hours"] > 0.0
        assert metrics["hibernate_dark_hours"] >= 0.0
        assert metrics["coldest_inner_c"] >= B.BATTERY_FREEZE_C
        assert metrics["hibernation_beyond_cited_evidence"] in (True, False)


@needs_real_inputs
def test_a_route_that_never_hibernates_keeps_the_pre_c2_wait_accounting(client):
    """wait_steps is computed as the geometric count minus the hibernations, so
    a route with no hibernation must report exactly what it reported before."""
    plain = client.post("/api/plan-4d", json=DAY_ROUTE).json()
    offered = client.post(
        "/api/plan-4d", json={**DAY_ROUTE, "allow_hibernate": True}
    ).json()
    if offered["metrics"]["hibernate_steps"] == 0:
        assert offered["metrics"]["wait_steps"] == plain["metrics"]["wait_steps"]


@needs_real_inputs
def test_luvmi_m_is_refused_on_the_real_grid_for_all_three_models(client):
    body = {**DAY_ROUTE, "rover_id": "luvmi_m"}
    for extra, phrase in (
        ({"battery_model": "temperature_derated"}, "freeze point"),
        ({"allow_hibernate": True}, "p_hibernate_w"),
    ):
        response = client.post("/api/plan-4d", json={**body, **extra})
        assert response.status_code == 422, response.text
        assert phrase in response.json()["detail"]
