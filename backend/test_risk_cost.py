"""B2 on the cost path: alpha and the slope sigma through cost_engine's
scalar references, cost_vec's array twins, compute_cost_grid, the layered
cost map, the 4-D cube and the rover-grid cache -- and the guarantee that
risk_alpha=None is the v4 build bit for bit."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app import constants as C
from app.constants import get_rover
from app.cost_engine import (
    COST_MODEL_ID,
    compute_cost_grid,
    edge_travel_time_s,
    edge_travel_time_s_array,
    f_energy_cell,
    f_slope,
    net_energy_per_metre_wh,
)
from app.cost_vec import f_energy_cell_grid, f_slope_grid
from app.risk import slip_cvar, slope_cvar
from app.slip_model import slip_ratio

ROVER_IDS = list(C.ROVERS)
ALPHAS = (0.5, 0.9, 0.99)
SIGMAS = (0.0, 1.5, 3.0)


def _viper() -> dict:
    return dict(get_rover("nasa_viper"))


# ── the one binding point takes an explicit slip ────────────────────────────


def test_edge_travel_time_default_and_slip_none_are_the_same_operations():
    rover = _viper()
    for theta in (0.0, 7.5, 15.0, 19.9):
        assert edge_travel_time_s(theta, 320.0, rover) == edge_travel_time_s(theta, 320.0, rover, slip=None)
    thetas = np.linspace(0.0, 25.0, 101)
    assert np.array_equal(
        edge_travel_time_s_array(thetas, 320.0, rover),
        edge_travel_time_s_array(thetas, 320.0, rover, slip=None),
    )


def test_edge_travel_time_with_an_explicit_slip():
    rover = _viper()
    theta, d, s = 10.0, 320.0, 0.5
    cos_t = math.cos(math.radians(theta))
    expected = (d / cos_t) / (1.0 - s) / (float(rover["v_max_ms"]) * cos_t)
    assert edge_travel_time_s(theta, d, rover, slip=s) == pytest.approx(expected, rel=1e-12)
    assert edge_travel_time_s(theta, d, rover, slip=slip_ratio(theta, rover)) == edge_travel_time_s(theta, d, rover)
    thetas = np.linspace(0.0, 25.0, 51)
    slips = np.linspace(0.0, 0.8, 51)
    vector = edge_travel_time_s_array(thetas, d, rover, slip=slips)
    scalar = np.array([edge_travel_time_s(float(t), d, rover, slip=float(sl)) for t, sl in zip(thetas, slips)])
    assert np.array_equal(vector, scalar)
    assert net_energy_per_metre_wh(theta, 0.5, rover) == net_energy_per_metre_wh(theta, 0.5, rover, slip=None)
    assert net_energy_per_metre_wh(theta, 0.5, rover, slip=0.5) > net_energy_per_metre_wh(theta, 0.5, rover)


# ── scalar references vs array twins, with alpha ────────────────────────────


@pytest.mark.parametrize("rover_id", ROVER_IDS)
def test_slope_and_energy_criteria_agree_scalar_vs_grid_under_alpha(rover_id):
    rover = get_rover(rover_id)
    slopes = np.linspace(0.0, float(rover["slope_max_deg"]), 17)
    shadows = np.linspace(0.0, 1.0, 5)
    for alpha in ALPHAS:
        for sigma in SIGMAS:
            for slope in slopes:
                scalar = f_slope(float(slope), rover, risk_alpha=alpha, slope_sigma=sigma)
                vector = float(f_slope_grid(np.array([slope]), rover, risk_alpha=alpha, slope_sigma=np.array([sigma]))[0])
                assert scalar == pytest.approx(vector, abs=1e-12)
                for shadow in shadows:
                    scalar = f_energy_cell(float(slope), rover, float(shadow), risk_alpha=alpha, slope_sigma=sigma)
                    vector = float(
                        f_energy_cell_grid(
                            np.array([slope]), rover, np.array([shadow]), risk_alpha=alpha, slope_sigma=np.array([sigma])
                        )[0]
                    )
                    assert scalar == pytest.approx(vector, abs=1e-12)


def test_alpha_none_is_the_v4_path_bit_for_bit():
    rover = _viper()
    rng = np.random.default_rng(3)
    slopes = rng.uniform(0.0, 25.0, (30, 30))
    shadows = rng.uniform(0.0, 1.0, (30, 30))
    sigmas = rng.uniform(0.0, 3.0, (30, 30))
    assert np.array_equal(
        f_energy_cell_grid(slopes, rover, shadows),
        f_energy_cell_grid(slopes, rover, shadows, risk_alpha=None, slope_sigma=sigmas),
    )
    assert np.array_equal(f_slope_grid(slopes, rover), f_slope_grid(slopes, rover, risk_alpha=None, slope_sigma=sigmas))
    for slope in (0.0, 9.0, 19.0, 21.0):
        assert f_slope(slope, rover) == f_slope(slope, rover, risk_alpha=None, slope_sigma=1.5)
        assert f_energy_cell(slope, rover, 0.4) == f_energy_cell(slope, rover, 0.4, risk_alpha=None, slope_sigma=1.5)


def test_the_slope_criterion_reads_the_tail_but_gates_on_the_nominal_slope():
    rover = _viper()  # slope_max 20
    assert f_slope(10.0, rover, risk_alpha=0.9, slope_sigma=1.5) == pytest.approx(
        f_slope(slope_cvar(10.0, 0.9, 1.5, rover), rover)
    )
    assert f_slope(10.0, rover, risk_alpha=0.9, slope_sigma=1.5) > f_slope(10.0, rover)
    # Capped at the limit: the same finite penalty as a cell AT the limit.
    assert f_slope(19.5, rover, risk_alpha=0.99, slope_sigma=1.5) == pytest.approx(f_slope(20.0, rover))
    assert math.isfinite(f_slope(19.5, rover, risk_alpha=0.99, slope_sigma=3.0))
    # Above the limit stays impassable regardless of alpha; no sigma, no tail.
    assert math.isinf(f_slope(20.5, rover, risk_alpha=0.99, slope_sigma=0.0))
    assert f_slope(10.0, rover, risk_alpha=0.9, slope_sigma=None) == f_slope(10.0, rover)


def test_the_energy_criterion_prices_the_slip_tail_and_never_gets_cheaper_with_alpha():
    rover = _viper()
    for slope, shadow in ((5.0, 0.2), (10.0, 0.7), (15.0, 1.0)):
        nominal = f_energy_cell(slope, rover, shadow)
        values = [f_energy_cell(slope, rover, shadow, risk_alpha=a, slope_sigma=1.5) for a in ALPHAS]
        assert nominal <= values[0] <= values[1] <= values[2] <= 1.0
        assert f_energy_cell(slope, rover, shadow, risk_alpha=0.9, slope_sigma=1.5) >= f_energy_cell(
            slope, rover, shadow, risk_alpha=0.9, slope_sigma=None
        )
    # Exactly the reference formula with the tail slip in place of mu.
    slope, shadow, alpha = 10.0, 0.7, 0.9
    tail = slip_cvar(slope, alpha, rover, 1.5)
    reference = dict(rover)
    reference["slip_curve"] = None
    best = net_energy_per_metre_wh(0.0, 0.0, reference)
    worst = net_energy_per_metre_wh(float(rover["slope_max_deg"]), 1.0, reference)
    here = net_energy_per_metre_wh(slope, shadow, rover, slip=tail)
    expected = min(1.0, max(0.0, (here - best) / (worst - best)))
    assert f_energy_cell(slope, rover, shadow, risk_alpha=alpha, slope_sigma=1.5) == pytest.approx(expected, rel=1e-12)


# ── compute_cost_grid ───────────────────────────────────────────────────────


def _grid_inputs(rover: dict, shape=(40, 40)):
    rng = np.random.default_rng(5)
    slope = rng.uniform(0.0, float(rover["slope_max_deg"]) + 4.0, shape)
    thermal = np.full(shape, -60.0)
    thermal_min = np.full(shape, -95.0)
    shadow = rng.uniform(0.0, 1.0, shape)
    sigma = rng.uniform(0.0, 3.0, shape)
    sigma[0, 0] = np.nan
    traversable = slope <= float(rover["slope_max_deg"])
    return slope, thermal, thermal_min, shadow, sigma, traversable


def test_compute_cost_grid_without_alpha_is_unchanged_by_the_new_arguments():
    rover = _viper()
    slope, thermal, thermal_min, shadow, sigma, traversable = _grid_inputs(rover)
    nominal = compute_cost_grid(slope, thermal, shadow, 5.0, traversable=traversable, rover=rover, thermal_min_grid=thermal_min)
    again = compute_cost_grid(
        slope, thermal, shadow, 5.0, traversable=traversable, rover=rover, thermal_min_grid=thermal_min,
        risk_alpha=None, slope_sigma_grid=sigma,
    )
    assert np.array_equal(nominal, again)
    assert COST_MODEL_ID.endswith("_v4")


def test_compute_cost_grid_never_gets_cheaper_as_alpha_rises():
    rover = _viper()
    slope, thermal, thermal_min, shadow, sigma, traversable = _grid_inputs(rover)
    kwargs = dict(traversable=traversable, rover=rover, thermal_min_grid=thermal_min)
    grids = [compute_cost_grid(slope, thermal, shadow, 5.0, **kwargs)]
    for alpha in ALPHAS:
        grids.append(compute_cost_grid(slope, thermal, shadow, 5.0, risk_alpha=alpha, slope_sigma_grid=sigma, **kwargs))
    finite = np.isfinite(grids[0])
    for lower, higher in zip(grids[:-1], grids[1:]):
        assert np.array_equal(np.isinf(lower), np.isinf(higher))
        assert np.all(higher[finite] >= lower[finite])
        assert np.any(higher[finite] > lower[finite])
    # The slope sigma alone must matter: without it only the slip spread widens.
    without_sigma = compute_cost_grid(slope, thermal, shadow, 5.0, risk_alpha=0.9, **kwargs)
    assert np.all(grids[2][finite] >= without_sigma[finite]) and np.any(grids[2][finite] > without_sigma[finite])
    assert np.all(without_sigma[finite] >= grids[0][finite])


def test_compute_cost_grid_rejects_a_mismatched_sigma():
    rover = _viper()
    slope, thermal, thermal_min, shadow, sigma, traversable = _grid_inputs(rover)
    with pytest.raises(ValueError):
        compute_cost_grid(
            slope, thermal, shadow, 5.0, traversable=traversable, rover=rover,
            risk_alpha=0.9, slope_sigma_grid=sigma[:-1],
        )


# ── the layered cost map ────────────────────────────────────────────────────


def test_cost_map_layers_take_alpha_and_explain_under_the_same_names():
    from app.costmap import PlanContext, default_cost_map

    rover = _viper()
    slope, thermal, thermal_min, shadow, sigma, traversable = _grid_inputs(rover, (12, 12))
    ctx = PlanContext(slope, thermal, shadow, traversable, 5.0, rover, thermal_min)
    ctx_sigma = PlanContext(slope, thermal, shadow, traversable, 5.0, rover, thermal_min, slope_sigma=sigma)
    nominal_map = default_cost_map(rover)
    alpha_map = default_cost_map(rover, risk_alpha=0.9)
    assert alpha_map.layer_names() == nominal_map.layer_names()

    nominal = nominal_map.total(ctx)
    # A nominal map ignores a sigma in the context.
    assert np.array_equal(nominal_map.total(ctx_sigma), nominal)
    tail = alpha_map.total(ctx_sigma)
    finite = np.isfinite(nominal)
    assert np.array_equal(np.isinf(nominal), np.isinf(tail))
    assert np.all(tail[finite] >= nominal[finite]) and np.any(tail[finite] > nominal[finite])
    # The same numbers compute_cost_grid produces with the same alpha and sigma.
    grid = compute_cost_grid(
        slope, thermal, shadow, 5.0, traversable=traversable, rover=rover, thermal_min_grid=thermal_min,
        risk_alpha=0.9, slope_sigma_grid=sigma,
    )
    np.testing.assert_allclose(tail[finite], grid[finite], rtol=1e-12)

    r, c = np.argwhere(traversable & (slope > 8.0) & np.isfinite(sigma) & (sigma > 0.5))[0]
    before = nominal_map.explain(int(r), int(c), ctx)
    after = alpha_map.explain(int(r), int(c), ctx_sigma)
    assert set(after) == set(before) == {"slope", "energy", "shadow", "thermal", "total"}
    assert after["slope"] > before["slope"] and after["energy"] >= before["energy"]
    assert after["shadow"] == before["shadow"] and after["thermal"] == before["thermal"]
    assert after["total"] > before["total"]
    assert alpha_map.layers[0].risk_alpha == 0.9 and nominal_map.layers[0].risk_alpha is None


# ── the 4-D cube ────────────────────────────────────────────────────────────


def _cube_grids(rover: dict, shape=(16, 16)) -> tuple[dict, np.ndarray, list]:
    _slope, thermal, thermal_min, shadow, sigma, traversable = _grid_inputs(rover, shape)
    # Moderate slopes: the cube coarsens with the block MAXIMUM, and a block
    # at the rover's limit has an energy term saturated at 1.0 already, which
    # would hide the tail.
    slope = np.random.default_rng(9).uniform(2.0, 12.0, shape)
    grids = {
        "slope": slope,
        "thermal": thermal,
        "shadow_ratio": shadow,
        "traversable": np.ones(shape, dtype=bool),
        "metadata": {"resolution_m": 80.0, "shape": list(shape), "thermal_field": "sunlit_peak"},
    }
    return grids, sigma, [shadow, np.clip(shadow + 0.2, 0.0, 1.0), shadow]


def test_cost_cube_takes_alpha_and_keeps_the_none_path_bit_for_bit():
    from app.cost_cube import build_cost_cube

    rover = _viper()
    grids, sigma, series = _cube_grids(rover)
    nominal = build_cost_cube(grids, series, rover, None, coarsen=4)
    again = build_cost_cube(grids, series, rover, None, coarsen=4, risk_alpha=None, slope_sigma=sigma)
    assert np.array_equal(nominal, again)

    without_sigma = build_cost_cube(grids, series, rover, None, coarsen=4, risk_alpha=0.9)
    with_sigma = build_cost_cube(grids, series, rover, None, coarsen=4, risk_alpha=0.9, slope_sigma=sigma)
    assert nominal.shape == with_sigma.shape == (3, 4, 4)
    finite = np.isfinite(nominal)
    assert np.array_equal(np.isinf(nominal), np.isinf(with_sigma))
    assert np.all(without_sigma[finite] >= nominal[finite]) and np.any(without_sigma[finite] > nominal[finite])
    assert np.all(with_sigma[finite] >= without_sigma[finite]) and np.any(with_sigma[finite] > without_sigma[finite])
    with pytest.raises(ValueError):
        build_cost_cube(grids, series, rover, None, coarsen=4, risk_alpha=0.9, slope_sigma=sigma[:8, :8])


# ── the rover-grid cache ────────────────────────────────────────────────────


def _base_for_cache(rover_id: str = "lpr_1", shape=(10, 10)) -> dict:
    from app.rover_grids import grids_for_rover

    rover = get_rover(rover_id)
    slope, thermal, thermal_min, shadow, _sigma, _trav = _grid_inputs(dict(rover), shape)
    base = {
        "elevation": np.zeros(shape),
        "slope": slope,
        "thermal": thermal,
        "thermal_min": thermal_min,
        "shadow_ratio": shadow,
        "traversable": np.ones(shape, dtype=bool),
        "metadata": {
            "resolution_m": 5.0,
            "shape": list(shape),
            "default_rover_id": rover_id,
            "cost_weights": {},
            "cost_model": "older",
        },
    }
    # A stored nominal grid this build recognises, so the None path can reuse it.
    adapted = grids_for_rover(base, rover_id)
    base["cost"] = adapted["cost"]
    base["traversable"] = adapted["traversable"]
    base["metadata"]["cost_weights"] = adapted["metadata"]["cost_weights"]
    base["metadata"]["cost_model"] = adapted["metadata"]["cost_model"]
    return base


def test_grids_for_rover_keys_the_cost_grid_by_alpha():
    from app.rover_grids import grids_for_rover

    base = _base_for_cache()
    nominal = grids_for_rover(base, "lpr_1")
    again = grids_for_rover(base, "lpr_1", None, risk_alpha=None)
    assert nominal["cost"] is base["cost"] and again["cost"] is base["cost"]  # reused, not recomputed
    assert "risk_alpha" not in nominal["metadata"] and "risk" not in nominal["metadata"]
    assert "slope_sigma" not in nominal

    tail = grids_for_rover(base, "lpr_1", None, risk_alpha=0.9)
    assert tail["metadata"]["risk_alpha"] == 0.9
    assert tail["metadata"]["cost_model"] == COST_MODEL_ID
    assert tail["metadata"]["risk"]["slope_sigma_source"] == "none"  # no clone cache here
    assert tail["metadata"]["risk"]["measure"] == "cvar_normal_closed_form_v1"
    assert "slope_sigma" not in tail
    finite = np.isfinite(nominal["cost"])
    assert np.all(tail["cost"][finite] >= nominal["cost"][finite]) and np.any(tail["cost"][finite] > nominal["cost"][finite])
    assert base["metadata"].get("risk_alpha") is None  # the input is not mutated

    # Same alpha on the alpha-stamped grids: reused. A different alpha: recomputed.
    same = grids_for_rover(tail, "lpr_1", None, risk_alpha=0.9)
    assert same["cost"] is tail["cost"]
    higher = grids_for_rover(tail, "lpr_1", None, risk_alpha=0.99)
    assert higher["metadata"]["risk_alpha"] == 0.99
    assert np.all(higher["cost"][finite] >= tail["cost"][finite]) and np.any(higher["cost"][finite] > tail["cost"][finite])

    # A nominal request on alpha-stamped grids recomputes and drops the stamp.
    back = grids_for_rover(tail, "lpr_1", None)
    assert np.array_equal(back["cost"], nominal["cost"])
    assert "risk_alpha" not in back["metadata"] and "risk" not in back["metadata"]


def test_grids_for_rover_reads_the_clone_slope_sigma_when_cached(monkeypatch):
    from app import rover_grids

    base = _base_for_cache()
    shape = tuple(base["slope"].shape)
    sigma = np.full(shape, 1.5)

    def fake_layers(grids, rover_id):
        return {"slope_sigma": sigma.astype(np.float32)}, {"model": "pgda_clones", "n_clones": 100}

    monkeypatch.setattr(rover_grids, "uncertainty_layers_for_grids", fake_layers)
    without = rover_grids.grids_for_rover(base, "lpr_1", None, risk_alpha=0.9)
    assert without["metadata"]["risk"]["slope_sigma_source"] == "dem_clones"
    assert without["metadata"]["risk"]["n_clones"] == 100
    assert np.array_equal(without["slope_sigma"], sigma.astype(np.float32))

    monkeypatch.setattr(rover_grids, "uncertainty_layers_for_grids", lambda g, r: (None, {"model": "unavailable"}))
    plain = rover_grids.grids_for_rover(base, "lpr_1", None, risk_alpha=0.9)
    finite = np.isfinite(plain["cost"])
    assert np.all(without["cost"][finite] >= plain["cost"][finite]) and np.any(without["cost"][finite] > plain["cost"][finite])
    # The nominal path never consults the clone cache.
    calls = []
    monkeypatch.setattr(rover_grids, "uncertainty_layers_for_grids", lambda g, r: calls.append(r) or (None, {}))
    rover_grids.grids_for_rover(base, "lpr_1")
    assert calls == []
