"""Safe Havens (A1) on the checked-in production grid.

test_safe_haven.py pins the rule on scripted skies. This file asks what the
rule says about Site11 with the real horizon cube and NAIF kernels, and
skips wherever the gitignored inputs are not on disk (mirrors
test_earth_visibility_real_grid.py).

Measured 4 Sep 2026 (scripts/safe_haven_report.py, 13 synodic months from
2026-09-07): the two weeks without an Earth link coincide with a lunar
night that darkens the whole site for ~6.5 days, so havens are RARE --
the shortest unlinked darkness ranges 40-186 h by lunar day. LPR-1 (50 h)
gets ~40 cells in Nov 2026 and none otherwise; NASA VIPER (96 h) peaks at
10.7 percent in the lunar day starting 2027-05-30; LUVMI-M (4 h) and
Yutu-2 (2 h) never qualify. These tests pin that shape, not the digits.
"""

from __future__ import annotations

import os
import pathlib

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import ROVERS, get_rover
from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids
from app.main import app
from app.rover_grids import grids_for_rover
from app.safe_haven import safe_haven_for_grids
from app.terrain import BINARY_DTYPE

_KERNELS = pathlib.Path(__file__).resolve().parent.parent / "kernels" / "lunapath.tm"
_HORIZON = os.path.join(_P1_PROCESSED_DIR, "horizon_map.npy")
_METADATA = os.path.join(_P1_PROCESSED_DIR, "metadata.json")

needs_real_inputs = pytest.mark.skipif(
    not (_KERNELS.exists() and os.path.exists(_HORIZON) and os.path.exists(_METADATA)),
    reason="NAIF kernels, horizon_map.npy or the processed grids are not on disk",
)

#: A lunar day with no haven for any profile: the unlinked fortnight holds
#: at least 156 h of continuous darkness in every traversable cell.
_EPOCH_NO_HAVEN = "2026-09-07T00:00:00"
#: The lunar day where NASA VIPER's 96 h endurance buys the most: the
#: shortest unlinked darkness is 62 h and a tenth of the site qualifies.
_EPOCH_VIPER = "2027-05-30T00:00:00"


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


def _traversable(grids, rover_id: str) -> np.ndarray:
    return np.asarray(grids_for_rover(grids, rover_id)["traversable"], dtype=bool)


@needs_real_inputs
def test_a_lunar_night_inside_the_unlinked_fortnight_leaves_no_haven(grids):
    """September 2026: the Earth is down 11-24 Sep and the whole site is
    dark 12-18 Sep, so every cell's unlinked darkness exceeds every
    profile's endurance. The map must say so -- an all-safe grid here
    would be a broken sky, not a good site."""
    for rover_id in ROVERS:
        layers, tts, info = safe_haven_for_grids(grids, rover_id, _EPOCH_NO_HAVEN)
        assert info["model"] == "spice_horizon", info
        traversable = _traversable(grids, rover_id)
        dark = layers["max_dark_hours_without_dte"][traversable]
        assert dark.min() > 96.0, (rover_id, dark.min())
        assert info["safe_haven_fraction"] < 0.001, (rover_id, info)
        assert np.isinf(tts[traversable]).all()
        # The Earth is below the horizon for most of the month at this
        # window (long-run visibility 0.28, A4), yet nearly every cell is
        # lit at some point: the site is dark for lack of a LINK, not Sun.
        assert 0.5 < info["earth_below_fraction"] < 0.9, info
        assert layers["ever_lit"][traversable].mean() > 0.9


@needs_real_inputs
def test_the_map_shrinks_with_the_endurance_on_the_best_lunar_day(grids):
    """Late May 2027: the shortest unlinked darkness drops to ~62 h. VIPER
    (96 h) gets a real haven set; LPR-1 (50 h) still almost nothing;
    LUVMI-M (4 h) and Yutu-2 (2 h) nothing at all. The research doc's demo
    -- change the profile, watch the map shrink -- in numbers."""
    fractions = {}
    for rover_id in ROVERS:
        _layers, _tts, info = safe_haven_for_grids(grids, rover_id, _EPOCH_VIPER)
        assert info["model"] == "spice_horizon", info
        fractions[rover_id] = float(info["safe_haven_fraction"])

    assert fractions["nasa_viper"] > 0.05, fractions
    assert fractions["lpr_1"] < fractions["nasa_viper"]
    assert fractions["luvmi_m"] <= fractions["lpr_1"]
    assert fractions["cnsa_yutu_2"] == 0.0
    assert fractions["luvmi_m"] == 0.0


@needs_real_inputs
def test_time_to_haven_covers_the_site_when_havens_exist(grids):
    """With a tenth of the site a haven, almost every passable cell can
    drive to one, and the typical drive is hours, not days: the gated
    graph is connected enough and the edge times are physical."""
    layers, tts, info = safe_haven_for_grids(grids, "nasa_viper", _EPOCH_VIPER)
    traversable = _traversable(grids, "nasa_viper")
    finite = np.isfinite(tts) & traversable
    assert finite.sum() / traversable.sum() > 0.9
    assert (tts[layers["safe_haven"]] == 0.0).all()
    median = float(np.median(tts[finite]))
    assert 0.2 < median < 10.0, median
    assert info["time_to_haven_finite_fraction"] == pytest.approx(
        finite.sum() / traversable.sum(), abs=1e-6
    )


@needs_real_inputs
def test_safe_haven_endpoint_publishes_the_real_map(client, grids):
    manifest = client.get(
        f"/api/safe-haven?start_utc={_EPOCH_VIPER}&rover_id=nasa_viper"
    ).json()
    assert manifest["safe_haven_model"]["model"] == "spice_horizon"
    assert manifest["h_max_shadow_h"] == 96.0
    assert manifest["safe_haven_fraction"] > 0.05
    assert manifest["n_steps"] == 355

    mask = client.get(manifest["fields"]["safe_haven"]["binary_url"])
    values = np.frombuffer(mask.content, dtype=BINARY_DTYPE)
    assert values.size == manifest["grid"]["rows"] * manifest["grid"]["cols"]
    assert int(values.sum()) == manifest["safe_haven_cells"]

    hours = client.get(manifest["fields"]["time_to_safe_haven"]["binary_url"])
    tts = np.frombuffer(hours.content, dtype=BINARY_DTYPE)
    assert int(np.isnan(tts).sum()) == manifest["fields"]["time_to_safe_haven"]["nodata"]
    assert int(hours.headers["X-Layer-Nodata"]) == int(np.isnan(tts).sum())


@needs_real_inputs
def test_cell_telemetry_reports_the_verdict_for_a_haven_and_a_plain_cell(client, grids):
    layers, tts, _info = safe_haven_for_grids(grids, "nasa_viper", _EPOCH_VIPER)
    haven_row, haven_col = (int(v) for v in np.argwhere(layers["safe_haven"])[0])
    plain = np.argwhere(~layers["safe_haven"] & np.isfinite(tts) & (tts > 0.0))
    plain_row, plain_col = (int(v) for v in plain[len(plain) // 2])
    params = {"rover_id": "nasa_viper", "start_utc": _EPOCH_VIPER}

    haven = client.get(
        "/api/cell-telemetry", params={"row": haven_row, "col": haven_col, **params}
    ).json()
    assert haven["safe_haven_model"]["model"] == "spice_horizon"
    assert haven["safe_haven"]["is_safe_haven"] is True
    assert haven["safe_haven"]["time_to_safe_haven_h"] == 0.0
    assert haven["safe_haven"]["max_dark_hours_without_dte_h"] <= 96.0
    assert haven["safe_haven"]["h_max_shadow_h"] == 96.0

    plain_cell = client.get(
        "/api/cell-telemetry", params={"row": plain_row, "col": plain_col, **params}
    ).json()
    assert plain_cell["safe_haven"]["is_safe_haven"] is False
    assert plain_cell["safe_haven"]["time_to_safe_haven_h"] == pytest.approx(
        float(tts[plain_row, plain_col]), abs=1e-3
    )


def _coarse_setup(grids, rover_id: str, epoch: str, coarsen: int = 4):
    from app.cost_cube import coarsen_grid, coarsen_traversable

    layers, _tts, _info = safe_haven_for_grids(grids, rover_id, epoch)
    passable = coarsen_traversable(_traversable(grids, rover_id), coarsen)
    havens = coarsen_traversable(layers["safe_haven"], coarsen) & passable
    elevation = coarsen_grid(grids["elevation"], coarsen, how="center")
    resolution_m = float(grids["metadata"]["resolution_m"]) * coarsen
    return passable, havens, elevation, resolution_m


def _pair(
    passable, sources, targets, elevation, resolution_m, rover, seed: int,
    min_moves: int = 15, max_moves: int = 40,
):
    """A (start, goal) pair in coarse cells, start drawn from *sources* and
    goal from *targets*, joined by a gated route of min_moves-max_moves
    moves (the longest such pair among 200 draws)."""
    from app.pathfinder_4d import gated_move_count

    rng = np.random.default_rng(seed)
    source_cells = np.argwhere(sources)
    target_cells = np.argwhere(targets)
    best = None
    for _ in range(200):
        a = tuple(int(v) for v in source_cells[rng.integers(len(source_cells))])
        b = tuple(int(v) for v in target_cells[rng.integers(len(target_cells))])
        moves = gated_move_count(passable, a, b, elevation, resolution_m, rover)
        if moves is not None and min_moves <= moves <= max_moves and (best is None or moves > best[2]):
            best = (a, b, moves)
    assert best is not None, "no suitable pair on this grid"
    return best


def _fine(cell, coarsen: int = 4) -> dict:
    return {"row": cell[0] * coarsen + coarsen // 2, "col": cell[1] * coarsen + coarsen // 2}


@needs_real_inputs
def test_plan_4d_between_two_havens_satisfies_the_leg_rule_on_the_real_grid(client, grids):
    """VIPER's leg: start at a haven, end at a haven, with the Earth up for
    another ~250 h. The constrained plan must exist, end parked at a
    haven, and carry a margin far wider than the plan itself."""
    rover = get_rover("nasa_viper")
    passable, havens, elevation, resolution_m = _coarse_setup(grids, "nasa_viper", _EPOCH_VIPER)
    assert havens.sum() > 100
    # A shorter leg than the other pairs in this file: under the slip curve
    # (C3) a 40-move VIPER leg on this terrain breaches the 20 percent
    # reserve (test_slip_calibration_real_grid), and the rule under test is
    # the leg rule, not the battery.
    start, goal, moves = _pair(
        passable, havens, havens, elevation, resolution_m, rover, seed=5, min_moves=8, max_moves=16
    )

    response = client.post(
        "/api/plan-4d",
        json={
            "start": _fine(start), "goal": _fine(goal), "rover_id": "nasa_viper",
            "coarsen": 4, "n_slices": 256, "start_utc": _EPOCH_VIPER,
            "require_safe_haven": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["safe_haven_model"]["model"] == "spice_horizon"
    assert payload["safe_haven_model"]["earthset_lookahead"]["model"] == "spice_horizon"
    assert payload["safe_haven_model"]["coarse_safe_haven_cells"] == int(havens.sum())
    metrics = payload["metrics"]
    assert metrics["safe_haven_enforced"] is True
    assert metrics["states_past_haven_deadline"] == 0
    assert metrics["ends_at_safe_haven"] is True
    assert metrics["move_steps"] >= moves
    assert payload["path_time_to_haven_h"][0] == 0.0
    assert payload["path_time_to_haven_h"][-1] == 0.0
    # The Earth stays up for days: every deadline is finite (the lookahead
    # found the Earthset) and the tightest margin dwarfs the 24 h horizon.
    assert all(value is not None for value in payload["path_hours_until_earthset"])
    assert metrics["min_haven_margin_h"] > 48.0
    assert metrics["time_to_dsn_shadow_min_h"] > 48.0
    assert metrics["time_to_zero_soc_min_h"] > 1.0


@needs_real_inputs
def test_plan_4d_refuses_a_goal_that_has_no_link_and_is_no_haven(client, grids):
    """A goal already out of Earth view that is not a haven can never be
    ended at under the rule; the refusal is immediate and names the goal,
    rather than a search through every state of the horizon."""
    from app.cost_cube import coarsen_traversable
    from app.earth_visibility import build_earth_visibility_series

    rover = get_rover("nasa_viper")
    passable, havens, elevation, resolution_m = _coarse_setup(grids, "nasa_viper", _EPOCH_VIPER)
    series, provenance = build_earth_visibility_series(
        None, grids["metadata"], 1, 1.0, _EPOCH_VIPER
    )
    assert provenance["model"] == "spice_horizon"
    linked = coarsen_traversable(np.asarray(series[0]) > 0.5, 4)
    unlinked_targets = passable & ~linked & ~havens
    assert unlinked_targets.sum() > 0
    start, goal, _moves = _pair(passable, havens, unlinked_targets, elevation, resolution_m, rover, seed=3)

    response = client.post(
        "/api/plan-4d",
        json={
            "start": _fine(start), "goal": _fine(goal), "rover_id": "nasa_viper",
            "coarsen": 4, "n_slices": 256, "start_utc": _EPOCH_VIPER,
            "require_safe_haven": True,
        },
    )
    assert response.status_code == 404, response.text
    detail = response.json()["detail"]
    assert "Goal" in detail and "safe haven" in detail
    assert "coarse cells are havens" in detail
