"""Regression tests for the backend review findings.

One test (or small group) per numbered finding in BACKEND_REVIEW.md, named so
a failure points straight back at the finding it protects. These are the
tests whose absence let the findings survive: #1 in particular went unnoticed
because nothing asserted that a weight the API accepts actually changes
anything.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import ROVERS, get_rover
from app.cost_engine import (
    compute_cost_grid,
    f_energy_cell,
    f_slope,
    f_thermal,
)
from app.costmap import PlanContext, default_cost_map
from app.main import app
from app.rover_grids import grids_for_rover
from app.traversability import compute_traversability_bool


# ── #1  f_energy_cell is a real MRU criterion, not an inert term ───────────

def test_energy_penalty_is_zero_on_flat_ground():
    assert f_energy_cell(0.0, get_rover("lpr_1")) == pytest.approx(0.0)


def test_energy_penalty_reaches_one_at_the_slope_limit():
    # The normalisation spans the CHEAPEST cell (flat and fully lit) to the
    # most expensive one (at the slope limit and fully shadowed), because
    # the penalty reads shadow as well as slope now -- without that it was
    # rank-identical to f_slope. So 1.0 lives at the corner, not on the
    # slope axis alone. (Round 3 review, H-4.)
    for rover_id in ROVERS:
        rover = get_rover(rover_id)
        limit = float(rover["slope_max_deg"])
        assert f_energy_cell(limit, rover, 1.0) == pytest.approx(1.0)
        assert f_energy_cell(0.0, rover, 0.0) == pytest.approx(0.0)


def test_energy_penalty_is_monotonic_and_bounded():
    rover = get_rover("lpr_1")
    for shadow in (0.0, 0.5, 1.0):
        values = [f_energy_cell(float(s), rover, shadow) for s in range(0, 26)]
        assert all(0.0 <= v <= 1.0 for v in values)
        assert all(b >= a for a, b in zip(values, values[1:]))


def test_energy_penalty_is_infinite_above_the_slope_limit():
    rover = get_rover("lpr_1")
    assert f_energy_cell(float(rover["slope_max_deg"]) + 1.0, rover) == float("inf")


def test_energy_penalty_is_independent_of_grid_resolution():
    """The old f_energy scaled with edge length, so the same terrain scored
    differently at 5 m and 80 m. A ratio cannot. (Review #1.)"""
    rover = get_rover("lpr_1")
    shape = (12, 12)
    slope = np.full(shape, 12.0)
    thermal = np.full(shape, -60.0)
    shadow = np.full(shape, 0.2)
    trav = np.ones(shape, dtype=bool)

    fine = compute_cost_grid(slope, thermal, shadow, 5.0, traversable=trav, rover=rover)
    coarse = compute_cost_grid(slope, thermal, shadow, 80.0, traversable=trav, rover=rover)
    assert np.allclose(fine, coarse)


def test_energy_contributes_a_meaningful_share_of_cell_cost():
    """The bug was a term worth 0.04% of cost while weighted 25.9%."""
    rover = get_rover("lpr_1")
    weights = {"w_slope": 0.409, "w_energy": 0.259, "w_shadow": 0.142, "w_thermal": 0.190}
    # Evaluated on a cell that is partly shadowed. On a FLAT, FULLY LIT
    # cell the net energy penalty is legitimately zero now -- the array
    # outproduces the drive, so crossing it costs the battery nothing -- and
    # a term that is zero exactly where the rover most wants to be is the
    # correct answer, not the old inert one. (Round 3 review, H-4.)
    energy = weights["w_energy"] * f_energy_cell(10.0, rover, 0.5)
    slope = weights["w_slope"] * f_slope(10.0, rover)
    thermal = weights["w_thermal"] * f_thermal(-100.0, rover)
    assert energy > 0.1 * slope
    assert energy > 0.1 * thermal


def test_energy_weight_changes_the_cost_grid():
    """The end-to-end symptom: sweeping w_energy changed nothing at all."""
    rover = get_rover("lpr_1")
    rng = np.random.default_rng(0)
    shape = (24, 24)
    slope = rng.uniform(0.0, 24.0, shape)
    thermal = np.full(shape, -60.0)
    shadow = np.full(shape, 0.2)
    trav = np.ones(shape, dtype=bool)

    def grid(w_energy: float) -> np.ndarray:
        return compute_cost_grid(
            slope, thermal, shadow, 5.0,
            traversable=trav,
            weights={"w_slope": 0.409, "w_energy": w_energy,
                     "w_shadow": 0.142, "w_thermal": 0.190},
            rover=rover,
        )

    assert not np.allclose(grid(0.0), grid(2.0))


# ── #2  traversability is recomputed, never trusted from a label ───────────

def _fake_grids(shape=(16, 16)) -> dict:
    rng = np.random.default_rng(1)
    slope = rng.uniform(0.0, 30.0, shape)
    thermal = np.full(shape, -60.0)
    return {
        "slope": slope,
        "thermal": thermal,
        "shadow_ratio": np.full(shape, 0.2),
        "elevation": np.zeros(shape),
        "traversable": np.ones(shape, dtype=bool),  # deliberately wrong
        "cost": np.zeros(shape),
        "metadata": {
            "origin": {"x": 0.0, "y": 0.0},
            "resolution_m": 5.0,
            "shape": list(shape),
            "default_rover_id": "nasa_viper",
            "cost_weights": {},
        },
    }


def test_mislabelled_metadata_does_not_yield_an_over_permissive_mask():
    """metadata claiming 'nasa_viper' does not make an all-true mask correct."""
    grids = _fake_grids()
    out = grids_for_rover(grids, "nasa_viper")
    truth = compute_traversability_bool(
        grids["slope"], grids["thermal"], grids["elevation"],
        rover=get_rover("nasa_viper"),
    )
    assert np.array_equal(out["traversable"], truth)
    assert not (out["traversable"] & ~truth).any()


def test_every_rover_gets_its_own_slope_limit_enforced():
    grids = _fake_grids()
    for rover_id in ROVERS:
        rover = get_rover(rover_id)
        out = grids_for_rover(grids, rover_id)
        passable_slopes = np.asarray(grids["slope"])[out["traversable"]]
        assert passable_slopes.max(initial=0.0) <= float(rover["slope_max_deg"])


def test_cost_is_recomputed_when_the_stored_mask_disagrees():
    """A stale cost grid must not survive a mask that no longer matches it."""
    grids = _fake_grids()
    out = grids_for_rover(grids, "nasa_viper")
    assert not np.array_equal(out["cost"], grids["cost"])
    assert np.isinf(out["cost"][~out["traversable"]]).all()


# ── #3  the DEM path cannot escape the DEM directory ──────────────────────

@pytest.mark.parametrize(
    "attack",
    [
        "../../../../etc/passwd",
        "..\\..\\..\\Windows\\win.ini",
        "/etc/shadow",
        "C:\\Windows\\win.ini",
        "../README.md",
    ],
)
def test_load_dem_rejects_paths_outside_the_dem_directory(attack):
    client = TestClient(app)
    response = client.post("/api/load-dem", json={"dem_file": attack})
    assert response.status_code == 422
    assert "DEM directory" in response.json()["detail"]


def test_load_dem_still_reports_a_missing_file_as_404():
    """The guard must not swallow the ordinary not-found case."""
    client = TestClient(app)
    response = client.post("/api/load-dem", json={"dem_file": "no_such_dem.tif"})
    assert response.status_code == 404


# ── #4  triggers report what they could not evaluate ──────────────────────

def test_missing_telemetry_is_reported_not_silently_skipped():
    from app.replan_triggers import evaluate_triggers_detailed

    result = evaluate_triggers_detailed({"actual_soc": 0.01})
    assert result["fired"] == []
    skipped_ids = {entry["trigger_id"] for entry in result["skipped"]}
    assert "soc_deviation" in skipped_ids
    missing = next(
        e["missing"] for e in result["skipped"] if e["trigger_id"] == "soc_deviation"
    )
    assert "planned_soc" in missing


def test_empty_state_skips_every_trigger():
    from app.replan_triggers import _TRIGGER_INPUTS, evaluate_triggers_detailed

    result = evaluate_triggers_detailed({})
    assert result["evaluated"] == []
    assert len(result["skipped"]) == len(_TRIGGER_INPUTS)


def test_complete_telemetry_evaluates_and_fires():
    from app.replan_triggers import evaluate_triggers_detailed

    result = evaluate_triggers_detailed({"actual_soc": 0.2, "planned_soc": 0.9})
    assert "soc_deviation" in result["evaluated"]
    assert [t.trigger_id for t in result["fired"]] == ["soc_deviation"]


def test_evaluate_triggers_keeps_its_fired_only_contract():
    from app.replan_triggers import evaluate_triggers

    fired = evaluate_triggers({"actual_soc": 0.2, "planned_soc": 0.9})
    assert [t.trigger_id for t in fired] == ["soc_deviation"]


# ── #6  the 4-D cube budget bounds bytes, not just slices ─────────────────

def test_cube_budget_rejects_a_multi_gigabyte_request():
    from app.main import _check_cube_budget
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        _check_cube_budget(1000, (500, 500))
    assert excinfo.value.status_code == 422


def test_cube_budget_allows_a_coarsened_horizon():
    from app.main import _check_cube_budget

    _check_cube_budget(1000, (125, 125))  # must not raise


# ── #9 / #10  input validation on the remaining endpoints ─────────────────

@pytest.mark.parametrize("downsample", [0, -1, -2, 51])
def test_layers_rejects_an_out_of_range_downsample(downsample):
    client = TestClient(app)
    response = client.get(f"/api/layers/slope?downsample={downsample}")
    assert response.status_code == 422


@pytest.mark.parametrize("start", [[1, 2, 3], [1], []])
def test_plan_multi_rejects_a_malformed_pixel_pair(start):
    client = TestClient(app)
    response = client.post(
        "/api/plan-multi",
        json={"start": start, "goal": [5, 5], "profiles": ["balanced"]},
    )
    assert response.status_code == 422


# ── #5  the cost grid is reused, not recomputed, when it matches ──────────

def test_reused_and_recomputed_cost_grids_plan_the_same_route():
    """The reuse fast path must be an optimisation, never a behaviour change."""
    from app.pathfinder import astar

    grids = _fake_grids((24, 24))
    grids["slope"] = np.clip(grids["slope"], 0.0, 18.0)  # keep a route open
    adapted = grids_for_rover(grids, "lpr_1")

    reused = astar(adapted, (1, 1), (20, 20), rover=get_rover("lpr_1"))
    stripped = {
        **adapted,
        "metadata": {k: v for k, v in adapted["metadata"].items() if k != "rover_id"},
    }
    recomputed = astar(stripped, (1, 1), (20, 20), rover=get_rover("lpr_1"))

    assert reused["error"] == recomputed["error"]
    assert reused["path_pixels"] == recomputed["path_pixels"]


def test_a_cost_grid_from_an_older_formula_is_not_reused():
    """A P1 .npy predating the review #1 energy change must be recomputed."""
    from app.cost_engine import COST_MODEL_ID

    grids = _fake_grids((16, 16))
    grids["metadata"]["cost_model"] = "weighted_cell_cost_without_barrier"
    adapted = grids_for_rover(grids, "lpr_1")
    assert adapted["metadata"]["cost_model"] == COST_MODEL_ID


# ── #7  app.state is the only grid store ──────────────────────────────────

def test_main_exposes_no_module_level_grid_global():
    import app.main as main_module

    assert not hasattr(main_module, "_grids")


def test_get_grids_and_active_grids_read_the_same_store():
    import app.main as main_module

    saved = getattr(app.state, "grids", None)
    try:
        sentinel = {"metadata": {"shape": [1, 1]}}
        main_module._set_grids(sentinel)
        assert main_module._get_grids() is sentinel
        assert main_module._current_grids() is sentinel
    finally:
        main_module._set_grids(saved)


# ── #8  scalar and vectorised penalties may never drift apart ─────────────

def _sample_slopes() -> np.ndarray:
    rng = np.random.default_rng(7)
    return np.concatenate([rng.uniform(0.0, 40.0, 2000), [0.0, 20.0, 25.0, 90.0, -3.0]])


def _sample_temps() -> np.ndarray:
    rng = np.random.default_rng(8)
    return np.concatenate([rng.uniform(-260.0, 140.0, 2000), [0.0, -1e-4, 1e-4, -150.0]])


@pytest.mark.parametrize("rover_id", sorted(ROVERS))
def test_vectorised_slope_matches_the_scalar_form(rover_id):
    from app.cost_vec import f_slope_grid

    rover = get_rover(rover_id)
    domain = _sample_slopes()
    scalar = np.array([f_slope(float(x), rover) for x in domain])
    assert np.allclose(scalar, f_slope_grid(domain, rover), equal_nan=True)


@pytest.mark.parametrize("rover_id", sorted(ROVERS))
def test_vectorised_energy_matches_the_scalar_form(rover_id):
    from app.cost_vec import f_energy_cell_grid

    rover = get_rover(rover_id)
    domain = _sample_slopes()
    scalar = np.array([f_energy_cell(float(x), rover) for x in domain])
    assert np.allclose(scalar, f_energy_cell_grid(domain, rover), equal_nan=True)


@pytest.mark.parametrize("rover_id", sorted(ROVERS))
def test_vectorised_thermal_matches_the_scalar_form(rover_id):
    from app.cost_vec import f_thermal_grid

    rover = get_rover(rover_id)
    domain = _sample_temps()
    scalar = np.array([f_thermal(float(x), rover) for x in domain])
    assert np.allclose(scalar, f_thermal_grid(domain, rover), equal_nan=True)


def test_vectorised_shadow_matches_the_scalar_form():
    from app.cost_engine import f_shadow_cell
    from app.cost_vec import f_shadow_cell_grid

    rng = np.random.default_rng(9)
    domain = np.concatenate([rng.uniform(-0.2, 1.2, 2000), [0.0, 0.5, 1.0]])
    scalar = np.array([f_shadow_cell(float(x)) for x in domain])
    assert np.allclose(scalar, f_shadow_cell_grid(domain))


def test_the_two_cost_grid_implementations_agree():
    """compute_cost_grid and CostMap.total must never diverge: one plans the
    route, the other explains it. (Review #8.)"""
    rng = np.random.default_rng(3)
    shape = (40, 40)
    slope = rng.uniform(0.0, 30.0, shape)
    thermal = rng.uniform(-160.0, 40.0, shape)
    shadow = rng.uniform(0.0, 1.0, shape)
    trav = (slope <= 25.0) & (thermal >= -150.0)
    rover = get_rover("lpr_1")

    loop = compute_cost_grid(slope, thermal, shadow, 5.0, traversable=trav, rover=rover)
    layered = default_cost_map(rover).total(
        PlanContext(
            slope=slope, thermal=thermal, shadow_ratio=shadow,
            traversable=trav, resolution_m=5.0, rover=rover,
        )
    )
    assert np.array_equal(np.isfinite(loop), np.isfinite(layered))
    finite = np.isfinite(loop)
    assert np.allclose(loop[finite], layered[finite])


def test_nan_inputs_stay_impassable_after_vectorisation():
    rover = get_rover("lpr_1")
    shape = (4, 4)
    slope = np.full(shape, 5.0)
    thermal = np.full(shape, -60.0)
    shadow = np.full(shape, 0.2)
    slope[0, 0] = np.nan
    thermal[1, 1] = np.nan
    shadow[2, 2] = np.nan

    grid = compute_cost_grid(
        slope, thermal, shadow, 5.0,
        traversable=np.ones(shape, dtype=bool), rover=rover,
    )
    assert np.isinf(grid[0, 0]) and np.isinf(grid[1, 1]) and np.isinf(grid[2, 2])
    assert np.isfinite(grid[3, 3])


# ── #11  a non-polar grid is a 422, not an opaque 500 ─────────────────────

def _polar_grids(origin_y: float, shape=(20, 20)) -> dict:
    from app.cost_engine import COST_MODEL_ID

    return {
        "elevation": np.zeros(shape),
        "slope": np.full(shape, 5.0),
        "aspect": np.zeros(shape),
        "thermal": np.full(shape, -50.0),
        "shadow_ratio": np.full(shape, 0.1),
        "cost": np.full(shape, 0.5),
        "traversable": np.ones(shape, dtype=bool),
        "metadata": {
            "resolution_m": 80.0,
            "shape": list(shape),
            "crs": "moon_sp",
            "origin": {"x": 0.0, "y": origin_y},
            "cost_weights": {
                "w_slope": 0.409, "w_energy": 0.259,
                "w_shadow": 0.142, "w_thermal": 0.190,
            },
            "cost_model": COST_MODEL_ID,
            "default_rover_id": "lpr_1",
        },
    }


def test_a_non_polar_grid_reports_422_with_the_real_reason():
    client = TestClient(app)
    saved = getattr(app.state, "grids", None)
    try:
        app.state.grids = _polar_grids(1_000_000.0)
        response = client.post(
            "/api/plan",
            json={"start": {"row": 0, "col": 0}, "goal": {"row": 5, "col": 5}},
        )
        assert response.status_code == 422
        assert "south pole" in response.json()["detail"]
    finally:
        app.state.grids = saved


def test_a_polar_grid_still_plans():
    client = TestClient(app)
    saved = getattr(app.state, "grids", None)
    try:
        app.state.grids = _polar_grids(0.0)
        response = client.post(
            "/api/plan",
            json={"start": {"row": 0, "col": 0}, "goal": {"row": 5, "col": 5}},
        )
        assert response.status_code == 200
    finally:
        app.state.grids = saved


# ── #12  the adjusted summary stays internally consistent ─────────────────

def _sensor_summary() -> dict:
    return {
        "total_energy_consumed_wh": 500.0,
        "total_elapsed_hours": 3.0,
        "final_battery_pct": 70.0,
        "min_battery_pct": 68.0,
        "critical_steps_count": 0,
        "high_or_above_steps_count": 1,
    }


def test_sensor_overhead_keeps_min_at_or_below_final_battery():
    from app.sensor_payload import apply_sensor_overhead_to_summary, with_sensor_payload

    rover = with_sensor_payload(get_rover("lpr_1"), payload_w=12.0, heater_w=8.0)
    adjusted = apply_sensor_overhead_to_summary(_sensor_summary(), rover)
    assert adjusted["min_battery_pct"] < 68.0
    assert adjusted["min_battery_pct"] <= adjusted["final_battery_pct"]


def test_sensor_overhead_invalidates_the_stale_risk_counters():
    from app.sensor_payload import apply_sensor_overhead_to_summary, with_sensor_payload

    rover = with_sensor_payload(get_rover("lpr_1"), payload_w=12.0)
    adjusted = apply_sensor_overhead_to_summary(_sensor_summary(), rover)
    assert adjusted["risk_counts_valid"] is False
    assert adjusted["critical_steps_count"] is None


def test_a_payload_free_rover_leaves_the_summary_untouched():
    from app.sensor_payload import apply_sensor_overhead_to_summary

    adjusted = apply_sensor_overhead_to_summary(_sensor_summary(), get_rover("lpr_1"))
    assert adjusted["final_battery_pct"] == pytest.approx(70.0)
    assert adjusted["min_battery_pct"] == pytest.approx(68.0)
    assert adjusted["critical_steps_count"] == 0


# ── #13  recharging costs time and needs sunlight ─────────────────────────

def _run_simulation(shadow_ratio: float, steps: int = 400) -> dict:
    from app.simulation import simulate_path, summarize_simulation

    shape = (20, 20)
    result = {"error": None, "path_pixels": [[0, i % 20] for i in range(steps)]}
    states = simulate_path(
        result,
        np.full(shape, 0.5), np.full(shape, 20.0),
        np.full(shape, -50.0), np.full(shape, shadow_ratio),
        rover=get_rover("lpr_1"), pixel_size_m=80.0,
    )
    return summarize_simulation(states)


def test_a_rover_in_full_shadow_cannot_recharge():
    dark = _run_simulation(1.0)
    assert dark["total_recharges"] == 0
    # It now stops AT its SOC reserve instead of driving on to a flat zero:
    # soc_min_pct was declared and enforced nowhere. The traverse truncates
    # there and the summary says so. (Round 3 review, H-1 / M-10.)
    assert dark["stranded"] is True
    reserve_pct = float(get_rover("lpr_1")["soc_min_pct"]) * 100.0
    assert 0.0 < dark["final_battery_pct"] <= reserve_pct + 1e-6


def test_recharging_in_sunlight_advances_the_clock():
    # Half shadow rather than full sun: since B5 the simulator credits the
    # array while driving (the planner's move_battery_drain_wh) and a
    # 20-degree climb in full sunlight nets only ~8 Wh per step for LPR-1,
    # so 400 steps never reach the reserve. At 0.5 the drive drains and a
    # stop still charges.
    lit = _run_simulation(0.5)
    dark = _run_simulation(1.0)
    assert lit["total_recharges"] > 0
    assert lit["total_elapsed_hours"] > dark["total_elapsed_hours"]


def test_drive_time_is_still_counted_once_per_step():
    assert _run_simulation(1.0)["total_elapsed_hours"] > 0.0


# ── #14  the thermal shadow proxy is direction-agnostic ───────────────────

def test_a_ridge_east_of_a_cell_now_casts_a_shadow():
    from app.thermal_grid import generate_thermal_grid

    shape = (5, 5)
    elevation = np.zeros(shape)
    elevation[:, 4] = 100.0  # ridge on the EASTERN edge
    grid = generate_thermal_grid(
        elevation, np.zeros(shape), np.zeros(shape), 80.0
    )
    assert grid[2, 3] < grid[2, 0]


def test_row_zero_is_no_longer_structurally_exempt_from_shadow():
    from app.thermal_grid import generate_thermal_grid

    shape = (5, 5)
    elevation = np.zeros(shape)
    elevation[1, :] = 100.0  # ridge immediately SOUTH of row 0
    grid = generate_thermal_grid(
        elevation, np.zeros(shape), np.zeros(shape), 80.0
    )
    assert grid[0, 2] < grid[3, 2]


# ── #16 / #20 / #21  cleanups that must not change behaviour ──────────────

def test_pathfinder_has_no_stale_module_level_offsets():
    import app.pathfinder as pathfinder

    assert not hasattr(pathfinder, "_OFFSETS")
    assert not hasattr(pathfinder, "_CELL_M")


def test_bfs_move_count_still_measures_correctly():
    from app.pathfinder_4d import bfs_move_count

    open_grid = np.ones((10, 10), dtype=bool)
    assert bfs_move_count(open_grid, (0, 0), (9, 9)) == 9
    assert bfs_move_count(open_grid, (0, 0), (0, 5)) == 5
    assert bfs_move_count(open_grid, (3, 3), (3, 3)) == 0

    walled = np.ones((5, 5), dtype=bool)
    walled[:, 2] = False
    assert bfs_move_count(walled, (0, 0), (0, 4)) is None


def test_negative_slope_never_yields_a_discount():
    # The piecewise table this used to check is gone (round 3, M-9); the
    # property it protected -- a negative slope is bad input, not free
    # energy -- now lives in cost_engine's clamp.
    from app.constants import get_rover as _gr
    from app.cost_engine import gross_energy_per_metre_wh

    rover = _gr("lpr_1")
    assert gross_energy_per_metre_wh(-5.0, 0.0, rover) == pytest.approx(
        gross_energy_per_metre_wh(0.0, 0.0, rover)
    )


# ── #17  the DEM cache key identifies the DEM ─────────────────────────────

def test_cache_key_separates_same_named_dems_in_different_directories():
    from app.cost_engine import resolve_weights
    from app.data_loader import _cache_key

    weights = resolve_weights(None)
    assert _cache_key("/a/dem.tif", 80, weights) != _cache_key("/b/dem.tif", 80, weights)


def test_cache_key_does_not_truncate_the_resolution():
    from app.cost_engine import resolve_weights
    from app.data_loader import _cache_key

    weights = resolve_weights(None)
    keys = {_cache_key("/a/dem.tif", r, weights) for r in (80.0, 80.4, 80.9)}
    assert len(keys) == 3


# ── #15 / #19  CORS and the lifespan handler ──────────────────────────────

def test_wildcard_cors_does_not_advertise_credentials():
    client = TestClient(app)
    response = client.get("/api/health", headers={"Origin": "https://example.test"})
    assert response.headers.get("access-control-allow-credentials") is None


def test_startup_runs_through_the_lifespan_handler():
    import app.main as main_module

    assert main_module.app.router.lifespan_context is not None
