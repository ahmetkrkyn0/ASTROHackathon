"""Recovery policies and the chance constraint (B1), kernel-free.

Small hand-made grids pin the dynamic programme against closed forms; the
planner section checks that ``astar_4d`` without a survival field is the
pre-B1 planner and that ``max_failure_probability`` binds when a field is
given. Nothing here needs the horizon cube or the NAIF kernels.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app import survival as S
from app.constants import get_rover


def _rover(**overrides) -> dict:
    """LPR-1 with a physics that can be worked by hand: no slip curve, no
    solar income, 100 W housekeeping in light and dark alike, 200 W
    traction on the flat, 1 000 Wh, 1 m/s, no slope gates, no reserve."""
    rover = dict(get_rover("lpr_1"))
    rover.update(
        p_solar_w=0.0,
        p_idle_w=100.0,
        p_heater_w=0.0,
        p_shadow_w=100.0,
        p_base_w=200.0,
        mu_coeff=0.0,
        e_cap_wh=1000.0,
        soc_min_pct=0.0,
        v_max_ms=1.0,
        slope_max_deg=90.0,
        slope_lateral_max_deg=90.0,
        slip_curve=None,
        h_max_shadow_h=1e9,
    )
    rover.update(overrides)
    return rover


# ── Task 0: constants and layer labels ───────────────────────────────────────


def test_failure_model_constants_are_labelled_assumptions():
    from app import constants as C

    assert C.FAILURE_RATE_PER_KM_ASSUMED == 0.2
    assert C.FAULT_RECOVERY_HOURS_ASSUMED == 10.0
    assert C.FAILURE_MODEL_SOURCE.startswith("assumption:")
    for rover in C.ROVERS.values():
        assert "failure_rate_per_km" not in rover


def test_survival_layers_are_described_but_not_in_the_manifest():
    from app.terrain import LAYER_DESCRIPTIONS, LAYER_UNITS, TERRAIN_LAYERS

    assert LAYER_UNITS["survival_probability"] == "fraction"
    assert LAYER_UNITS["best_action"] == "code"
    assert "survival_probability" in LAYER_DESCRIPTIONS
    assert "best_action" in LAYER_DESCRIPTIONS
    assert "survival_probability" not in TERRAIN_LAYERS


# ── Task 1: fault model, safe set, direction tables, shadow bins ─────────────


def test_fault_outcomes_are_lamarre_eq_2_to_4_and_sum_to_one():
    p0, p1, p2 = S.fault_outcome_probabilities(0.2, 320.0)  # 1 per 5 km, one 320 m block
    rho = 0.2 / 1000.0 * 320.0
    assert p0 == pytest.approx(math.exp(-rho))
    assert p1 == pytest.approx(1.0 - math.exp(-rho / 2.0))
    assert p2 == pytest.approx(math.exp(-rho / 2.0) - math.exp(-rho))
    assert p0 + p1 + p2 == pytest.approx(1.0)
    assert S.fault_outcome_probabilities(0.0, 320.0) == (1.0, 0.0, 0.0)


def test_haven_hibernation_soc_is_reserve_plus_dark_housekeeping_over_endurance():
    rover = get_rover("lpr_1")  # 5 420 Wh, reserve 20 %, 65 W in shadow, 50 h
    assert S.haven_hibernation_soc_wh(rover) == pytest.approx(min(5420.0, 0.2 * 5420.0 + 65.0 * 50.0))


def test_safe_soc_requirement_leg_and_haven_sets():
    rover = get_rover("lpr_1")
    trav = np.ones((3, 3), dtype=bool)
    haven = np.zeros((3, 3), dtype=bool)
    haven[0, 0] = True
    leg = S.safe_soc_requirement(trav, haven, (2, 2), rover, "leg")
    assert leg[2, 2] == pytest.approx(0.2 * 5420.0)
    assert leg[0, 0] == pytest.approx(S.haven_hibernation_soc_wh(rover))
    assert np.isinf(leg[1, 1])
    only = S.safe_soc_requirement(trav, haven, (2, 2), rover, "haven")
    assert np.isinf(only[2, 2]) and np.isfinite(only[0, 0])
    with pytest.raises(ValueError):
        S.safe_soc_requirement(trav, None, None, rover, "leg")  # leg needs a goal
    with pytest.raises(ValueError):
        S.safe_soc_requirement(trav, haven, (2, 2), rover, "goal")


def test_safe_soc_requirement_ignores_impassable_cells():
    rover = get_rover("lpr_1")
    trav = np.ones((2, 2), dtype=bool)
    trav[1, 1] = False
    haven = np.ones((2, 2), dtype=bool)
    req = S.safe_soc_requirement(trav, haven, (1, 1), rover, "leg")
    assert np.isinf(req[1, 1]) and np.isfinite(req[0, 0])


def test_direction_tables_match_the_gated_edge_graph():
    from app.safe_haven import _gated_edges

    rng = np.random.default_rng(3)
    rover = get_rover("lpr_1")
    trav = rng.random((12, 12)) > 0.2
    elev = rng.random((12, 12)) * 40.0
    slope = rng.random((12, 12)) * 20.0
    tables = S.direction_tables(trav, elev, slope, 80.0, rover)
    src, dst, hours = _gated_edges(trav, elev, slope, 80.0, rover)
    expected = {(int(a), int(b)): float(h) for a, b, h in zip(src, dst, hours)}
    expected.update({(b, a): h for (a, b), h in list(expected.items())})  # symmetric graph
    got: dict[tuple[int, int], float] = {}
    for d, (dr, dc, _diag) in enumerate(S.OFFSETS):
        for r, c in zip(*np.nonzero(tables.allowed[d])):
            got[(int(r * 12 + c), int((r + dr) * 12 + c + dc))] = float(tables.travel_h[d, r, c])
    assert got.keys() == expected.keys()
    for key, value in got.items():
        assert value == pytest.approx(expected[key])
    assert tables.distance_m[4] == pytest.approx(80.0 * math.sqrt(2.0))
    assert tables.distance_m[0] == 80.0
    assert tables.allowed.shape == (8, 12, 12) and tables.traction_w.shape == (8, 12, 12)


def test_direction_tables_traction_follows_the_edge_slope():
    rover = _rover(mu_coeff=2.0)
    trav = np.ones((1, 2), dtype=bool)
    slope = np.array([[0.0, 30.0]])
    tables = S.direction_tables(trav, None, slope, 10.0, rover)
    # E from (0, 0): mean slope 15 deg -> 200 * (1 + 2 sin 15)
    assert tables.traction_w[3, 0, 0] == pytest.approx(200.0 * (1.0 + 2.0 * math.sin(math.radians(15.0))))
    assert not tables.allowed[3, 0, 1]  # nothing east of the last column


def test_bin_shadow_series_is_the_block_mean_over_slices():
    series = [np.full((2, 2), v) for v in (0.0, 1.0, 1.0, 0.5, 0.2)]
    binned = S.bin_shadow_series(series, 2)
    assert binned.shape == (3, 2, 2)
    assert binned[0, 0, 0] == 0.5 and binned[1, 0, 0] == 0.75 and binned[2, 0, 0] == 0.2
    assert S.bin_shadow_series(series, 1).shape == (5, 2, 2)


def test_auto_slices_per_bin_respects_the_state_cap():
    assert S.auto_slices_per_bin(100, 15625, 20, 40_000_000) == 1
    assert S.auto_slices_per_bin(460, 15625, 20, 40_000_000) == 4
    assert S.auto_slices_per_bin(0, 15625, 20, 40_000_000) == 1


# ── Task 2: the value iteration and SurvivalField ────────────────────────────


def _field(trav, safe_req, rover, n_bins=3, step=1.0, K=4, rate=0.0, recovery=1.0, shadow=None, res=3600.0):
    """A field on a toy grid: one cardinal move of *res* metres at 1 m/s is
    ``res / 3600`` hours, so 3 600 m is exactly one 1 h bin."""
    height, width = trav.shape
    shadow_bins = np.zeros((n_bins, height, width)) if shadow is None else shadow
    return S.build_survival_field(
        trav, None, None, res, rover, shadow_bins, step, 1, safe_req, K, rate, recovery
    )


def _strip(n: int, goal: int):
    trav = np.ones((1, n), dtype=bool)
    req = np.full((1, n), np.inf)
    req[0, goal] = 0.0
    return trav, req


def test_a_safe_cell_has_p_safe_one_and_the_safe_action():
    trav, req = _strip(3, 2)
    f = _field(trav, req, _rover())
    assert f.p_safe.shape == (4, 1, 3, 4)  # n_bins + 1: the last entry is the terminal boundary
    assert f.p_safe[:, 0, 2, :].min() == 1.0
    assert (f.policy[:, 0, 2, :] == S.ACTION_SAFE).all()


def test_deterministic_reach_within_horizon_is_one_and_zero_beyond():
    rover = _rover(p_base_w=0.0, p_idle_w=0.0, p_shadow_w=0.0)  # no drain at all
    trav, req = _strip(3, 2)
    f = _field(trav, req, rover, n_bins=3)
    assert f.p_safe[0, 0, 0, 3] == 1.0 and f.policy[0, 0, 0, 3] == 3  # E, E: arrive at bin 2
    assert f.p_safe[1, 0, 0, 3] == 1.0  # E, E: arrive at bin 3 = the boundary, safe there
    assert f.p_safe[2, 0, 0, 3] == 0.0  # one bin left, two moves needed
    assert f.p_safe[2, 0, 1, 3] == 1.0
    assert f.policy[2, 0, 0, 3] == S.ACTION_NONE


def test_battery_bins_under_the_reserve_fail_and_drain_interpolates_between_bin_centres():
    """Reserve 500 of 1 000 Wh, K = 4 (centres 125, 375, 625, 875): the two
    lower bins are failures. A 1 h move drains (100 + 100) W = 200 Wh = 0.8
    bins, so from bin 3 the value is 0.8 V[2] + 0.2 V[3] (both safe at the
    goal) and from bin 2 it is 0.8 V[1] (failed) + 0.2 V[2]: P_safe 0.2.
    Lamarre's lower-bin map would have made bin 2 hopeless and bin 3 as
    well once the drain is under a bin -- see the spec's probe."""
    rover = _rover(soc_min_pct=0.5, p_base_w=100.0)
    trav, req = _strip(2, 1)
    req[0, 1] = 500.0
    f = _field(trav, req, rover, n_bins=2, K=4)
    assert (f.p_safe[0, 0, 0, :2] == 0.0).all()
    assert f.p_safe[0, 0, 0, 3] == pytest.approx(1.0, abs=1e-6)
    assert f.p_safe[0, 0, 0, 2] == pytest.approx(0.2, abs=1e-6)
    assert (f.policy[0, 0, 0, :2] == S.ACTION_NONE).all()
    assert f.policy[0, 0, 0, 3] == 3


def test_a_chain_of_small_drains_is_unbiased_in_expectation():
    """Ten 1 h moves of 200 Wh each = 2 000 Wh from a 5 000 Wh battery with
    a 1 000 Wh reserve, K = 10 (500 Wh bins): the rover ends at 3 000 Wh,
    comfortably safe. The lower-bin map charged a whole bin per move and
    killed it after eight; the centre interpolation keeps P_safe high."""
    rover = _rover(soc_min_pct=0.2, p_base_w=100.0, e_cap_wh=5000.0)
    trav, req = _strip(11, 10)
    req[0, 10] = 1000.0
    f = _field(trav, req, rover, n_bins=11, K=10)
    assert f.p_safe[0, 0, 0, 9] > 0.95
    assert f.p_safe[0, 0, 0, 3] < 0.5  # 1 750 Wh centre - 2 000 Wh: under the reserve


def test_more_soc_never_lowers_p_safe_and_more_faults_never_raise_it():
    rng = np.random.default_rng(0)
    rover = _rover()
    trav = rng.random((6, 6)) > 0.15
    trav[5, 5] = True
    req = np.full((6, 6), np.inf)
    req[5, 5] = 0.0
    shadow = rng.random((6, 6, 6))
    lo = _field(trav, req, rover, n_bins=6, K=8, rate=0.5, recovery=1.0, shadow=shadow)
    hi = _field(trav, req, rover, n_bins=6, K=8, rate=2.0, recovery=1.0, shadow=shadow)
    assert (np.diff(lo.p_safe, axis=3) >= -1e-6).all()
    assert (hi.p_safe <= lo.p_safe + 1e-6).all()
    assert lo.p_safe[0, 0, 0, 7] < 1.0 or not trav[0, 0]


def test_two_cell_fault_dp_matches_the_closed_form():
    """A -> B (goal), two 1 h bins, a 1 h move, rho = 0.5 expected faults, R = 1 h.
    No fault: B at bin 1, safe. Fault in the first half: A at 1.5 h -> bins 1 and 2;
    from A at bin 1 the move ends at the boundary (safe), at bin 2 = boundary A is not
    safe -> the worse of the two is failure. Fault in the second half: B at 2 h =
    the boundary, safe. V = p1."""
    rover = _rover(p_base_w=0.0, p_idle_w=0.0, p_shadow_w=0.0)
    trav, req = _strip(2, 1)
    rate = 0.5 / 3.6  # per km: 0.5 faults over 3 600 m
    f = _field(trav, req, rover, n_bins=2, K=2, rate=rate, recovery=1.0)
    _p0, p1, _p2 = S.fault_outcome_probabilities(rate, 3600.0)
    assert f.p_safe[0, 0, 0, 1] == pytest.approx(1.0 - p1, abs=1e-6)
    assert f.policy[0, 0, 0, 1] == 3
    factor, q1, q2, ps1, ps2 = f.move_survival_factor(0, 0, 0, 0, 1, 1000.0, 1.0, 3600.0, 0.0)
    assert (q1, q2) == pytest.approx((p1, _p2)) and ps1 == 0.0 and ps2 == 1.0
    assert factor == pytest.approx(1.0 - p1, abs=1e-6)


def test_min_max_takes_the_worse_time_bin():
    """A move of 1.5 bins with one bin of horizon: the lower mapping lands on the
    boundary (safe), the upper one beyond it (failure) -> the worse wins."""
    rover = _rover(p_base_w=0.0, p_idle_w=0.0, p_shadow_w=0.0)
    trav, req = _strip(2, 1)
    long = _field(trav, req, rover, n_bins=1, res=5400.0)
    exact = _field(trav, req, rover, n_bins=1, res=3600.0)
    assert long.p_safe[0, 0, 0, 3] == 0.0
    assert exact.p_safe[0, 0, 0, 3] == 1.0


def test_a_fault_hold_longer_than_the_endurance_in_a_dark_block_is_fatal():
    rover = _rover(p_base_w=0.0, p_idle_w=0.0, p_shadow_w=0.0)
    trav, req = _strip(2, 1)
    shadow = np.zeros((3, 1, 2))
    shadow[:, 0, 0] = 1.0  # A is dark throughout, B lit
    rate = 0.5 / 3.6
    tolerant = _field(trav, req, rover, n_bins=3, rate=rate, recovery=1.0, shadow=shadow)
    fragile = _field(trav, req, dict(rover, h_max_shadow_h=0.5), n_bins=3, rate=rate, recovery=1.0, shadow=shadow)
    p0, p1, _p2 = S.fault_outcome_probabilities(rate, 3600.0)
    # Tolerant: a first-half fault leaves A at 1.5 h, whose worse bin (2) can
    # still drive but not survive a second fault: V = p1 * (1 - p0).
    assert tolerant.p_safe[0, 0, 0, 3] == pytest.approx(1.0 - p1 * (1.0 - p0), abs=1e-6)
    # Fragile: the hold in dark A outlasts the endurance -> that branch fails.
    assert fragile.p_safe[0, 0, 0, 3] == pytest.approx(1.0 - p1, abs=1e-6)


def test_recovery_drain_integrates_housekeeping_minus_solar_over_the_hold():
    rover = _rover(p_solar_w=50.0)  # 100 W housekeeping; 50 W solar at full light
    trav, req = _strip(2, 1)
    shadow = np.full((4, 1, 2), 0.5)
    f = _field(trav, req, rover, n_bins=4, recovery=2.0, shadow=shadow)
    assert f.recovery_drain_wh(0, 0, 0.0) == pytest.approx((100.0 - 50.0 * 0.5) * 2.0)
    assert f.recovery_drain_wh(0, 0, 0.5) == pytest.approx((100.0 - 50.0 * 0.5) * 2.0)


def test_p_safe_at_reads_the_worse_of_the_neighbouring_bins_and_the_floor_soc():
    rover = _rover(p_base_w=0.0, p_idle_w=0.0, p_shadow_w=0.0)
    trav, req = _strip(3, 2)
    f = _field(trav, req, rover, n_bins=3)
    f.slices_per_bin = 2  # planner slices are half a bin
    assert f.p_safe_at(1, 0, 0, 999.0) == min(f.p_safe[0, 0, 0, 3], f.p_safe[1, 0, 0, 3])
    assert f.p_safe_at(5, 0, 0, 999.0) == min(f.p_safe[2, 0, 0, 3], f.p_safe[3, 0, 0, 3])
    assert f.p_safe_at(99, 0, 0, 999.0) == 0.0  # beyond the horizon
    assert f.soc_bin(999.0) == 3 and f.soc_bin(1000.0) == 3 and f.soc_bin(-5.0) == 0
    assert f.soc_bin(374.0) == 1 and f.soc_bin(376.0) == 1 and f.soc_bin(500.0) == 2  # nearest centre


def test_p_safe_hours_interpolates_between_soc_bin_centres():
    rover = _rover(p_base_w=0.0, p_idle_w=0.0, p_shadow_w=0.0)
    trav, req = _strip(2, 1)
    f = _field(trav, req, rover, n_bins=1, K=4)
    f.p_safe[0, 0, 0, :] = np.array([0.0, 0.0, 0.4, 0.8], dtype=np.float32)
    f.p_safe[1, 0, 0, :] = 1.0
    # 750 Wh sits exactly on bin 3's centre - 0.5 bin: halfway between bins 2 and 3.
    assert f.p_safe_hours(0.0, 0, 0, 750.0) == pytest.approx(0.6, abs=1e-6)
    assert f.p_safe_hours(0.0, 0, 0, 875.0) == pytest.approx(0.8, abs=1e-6)
    assert f.p_safe_hours(0.0, 0, 0, 1000.0) == pytest.approx(0.8, abs=1e-6)  # clamped at the top
    assert f.p_safe_hours(0.0, 0, 0, 50.0) == pytest.approx(0.0, abs=1e-6)


def test_best_action_names_the_policy_move_and_its_target():
    rover = _rover(p_base_w=0.0, p_idle_w=0.0, p_shadow_w=0.0)
    trav, req = _strip(3, 2)
    f = _field(trav, req, rover)
    best = f.best_action(0, 0, 0, 1000.0)
    assert best["action"] == 3 and best["name"] == "E" and best["target"] == (0, 1)
    assert best["p_safe_now"] == 1.0 and best["p_safe_next"] == 1.0
    safe = f.best_action(0, 0, 2, 1000.0)
    assert safe["action"] == S.ACTION_SAFE and safe["name"] == "safe" and safe["target"] is None
    info = f.info()
    assert info["n_states"] == 3 * 3 * 4 and info["validity"] == "MODEL"
    assert info["n_bins"] == 3 and info["horizon_hours"] == 3.0 and info["safe_cells"] == 1
    assert info["failure_model"]["source"].startswith("assumption:")


# ── Task 3: rollout, API blocks, suggestion ──────────────────────────────────


def test_rollout_with_no_faults_agrees_with_the_deterministic_dp():
    rover = _rover(p_base_w=0.0, p_idle_w=0.0, p_shadow_w=0.0)
    trav, req = _strip(3, 2)
    f = _field(trav, req, rover, n_bins=3)
    out = S.rollout(f, (0, 0), 1000.0, n_runs=50, seed=1)
    assert out["failure_rate"] == 0.0 and out["predicted_failure"] == 0.0 and out["safe"] == 50
    assert out["n_runs"] == 50 and out["mean_faults"] == 0.0 and out["followed_plan"] is False
    late = S.rollout(f, (0, 0), 1000.0, n_runs=50, seed=1, start_slice=2)
    assert late["failure_rate"] == 1.0 and late["predicted_failure"] == 1.0 and late["failed"] == 50


def test_rollout_failure_rate_is_near_the_closed_form():
    rover = _rover(p_base_w=0.0, p_idle_w=0.0, p_shadow_w=0.0)
    trav, req = _strip(2, 1)
    rate = 0.5 / 3.6
    f = _field(trav, req, rover, n_bins=2, K=2, rate=rate, recovery=1.0)
    out = S.rollout(f, (0, 0), 1000.0, n_runs=4000, seed=7)
    _p0, p1, _p2 = S.fault_outcome_probabilities(rate, 3600.0)
    assert out["wilson_low"] <= p1 <= out["wilson_high"]
    assert out["predicted_failure"] == pytest.approx(p1, abs=1e-6)
    assert out["mean_faults"] > 0.0


def test_rollout_can_follow_a_plan_first():
    rover = _rover(p_base_w=0.0, p_idle_w=0.0, p_shadow_w=0.0)
    trav, req = _strip(3, 2)
    f = _field(trav, req, rover, n_bins=3)
    out = S.rollout(f, (0, 0), 1000.0, n_runs=10, seed=1, plan_states=[(0, 0, 0), (0, 1, 1), (0, 2, 2)])
    assert out["safe"] == 10 and out["followed_plan"] is True
    with pytest.raises(ValueError):
        S.rollout(f, (0, 0), 1000.0, n_runs=1, seed=1, plan_states=[(0, 0, 0), (0, 2, 1)])  # not adjacent


def test_recovery_suggestion_and_block_shapes():
    rover = _rover(p_base_w=0.0, p_idle_w=0.0, p_shadow_w=0.0)
    trav, req = _strip(3, 2)
    f = _field(trav, req, rover)
    s = S.recovery_suggestion(f, 0, 0, 1000.0, coarsen=4)
    assert s["action_name"] == "E" and s["target_block"] == [0, 1] and s["target_pixel"] == [2, 6]
    assert s["validity"] == "MODEL" and s["p_safe_now"] == 1.0 and s["soc_frac"] == 1.0
    block = S.survival_block(None, None, None, requested=False, reason="not requested")
    assert block == {
        "requested": False,
        "applied": False,
        "reason": "not requested",
        "validity": "MODEL",
        "model": S.SURVIVAL_MODEL_ID,
    }
    result = {
        "metrics": {
            "execution_failure_probability": 0.01,
            "min_recovery_prob": 0.99,
            "start_recovery_prob": 1.0,
            "edges_rejected": {"failure_probability": 0},
        },
        "path_recovery_prob": [1.0, 0.99, 1.0],
    }
    block = S.survival_block(f, result, 0.05, requested=True, shadow_model={"model": "static"})
    assert block["applied"] is True and block["beta"] == 0.05
    assert block["route"]["execution_failure_probability"] == 0.01 and block["route"]["mean_recovery_prob"] == pytest.approx(0.9966667)
    assert block["field"]["n_states"] == f.n_states and block["failure_model"]["source"].startswith("assumption:")
    assert "claim" in block and block["shadow_model"] == {"model": "static"} and block["references"][0]["id"] == "lamarre_acta_2023"


def test_field_cache_holds_two_entries():
    S.clear_survival_cache()
    calls = []

    def build(tag):
        def _builder():
            calls.append(tag)
            return tag
        return _builder

    assert S.cached_survival_field(("a",), build("a")) == "a"
    assert S.cached_survival_field(("a",), build("a2")) == "a"   # hit
    assert S.cached_survival_field(("b",), build("b")) == "b"
    assert S.cached_survival_field(("c",), build("c")) == "c"   # evicts "a"
    assert S.cached_survival_field(("a",), build("a3")) == "a3"
    assert calls == ["a", "b", "c", "a3"]
    S.clear_survival_cache()


# ── Task 4: the planner's execution-survival label and beta ──────────────────


def _toy_cubes(n_slices: int = 6, width: int = 4):
    cost = np.full((n_slices, 1, width), 0.2)
    wait = np.full((n_slices, 1, width), 0.1)
    trav = np.ones((1, width), dtype=bool)
    return cost, wait, trav


def test_planner_without_a_field_is_unchanged_and_reports_none():
    from app.pathfinder_4d import REJECTION_KEYS, astar_4d

    cost, wait, trav = _toy_cubes()
    rover = _rover(v_max_ms=1.0)
    out = astar_4d(cost, wait, trav, (0, 0), (0, 3), 3600.0, 1.0, rover)
    assert out["error"] is None
    assert out["path_survival_prob"] is None and out["path_recovery_prob"] is None
    assert out["metrics"]["survival_enforced"] is False
    assert out["metrics"]["execution_failure_probability"] is None
    assert "failure_probability" in REJECTION_KEYS
    assert out["metrics"]["edges_rejected"]["failure_probability"] == 0


def test_beta_without_a_field_is_refused():
    from app.pathfinder_4d import astar_4d

    cost, wait, trav = _toy_cubes()
    out = astar_4d(cost, wait, trav, (0, 0), (0, 3), 3600.0, 1.0, _rover(v_max_ms=1.0), max_failure_probability=0.05)
    assert out["error"] and "survival_field" in out["error"]
    assert out["metrics"]["survival_enforced"] is True


def test_field_without_beta_reports_execution_risk_and_beta_enforces_it():
    from app.pathfinder_4d import astar_4d

    cost, wait, trav = _toy_cubes()
    rover = _rover(p_base_w=0.0, p_idle_w=0.0, p_shadow_w=0.0, v_max_ms=1.0)
    req = np.full((1, 4), np.inf)
    req[0, 3] = 0.0
    rate = 0.5 / 3.6
    fieldf = S.build_survival_field(trav, None, None, 3600.0, rover, np.zeros((8, 1, 4)), 1.0, 1, req, 4, rate, 1.0)
    shadow = np.zeros((6, 1, 4))
    reported = astar_4d(
        cost, wait, trav, (0, 0), (0, 3), 3600.0, 1.0, rover, shadow_cube=shadow, survival_field=fieldf
    )
    assert reported["error"] is None
    assert len(reported["path_survival_prob"]) == len(reported["path_states"])
    assert len(reported["path_recovery_prob"]) == len(reported["path_states"])
    assert reported["path_survival_prob"][0] == 1.0
    assert 0.0 < reported["metrics"]["execution_failure_probability"] < 1.0
    assert reported["metrics"]["survival_enforced"] is False
    assert reported["metrics"]["start_recovery_prob"] == pytest.approx(fieldf.p_safe_at(0, 0, 0, 1000.0))
    # Three 1 h moves with rho = 0.5 each: every fault branch that keeps the
    # rover alive is closed with P_safe of the state it leaves it in.
    p0, p1, p2 = S.fault_outcome_probabilities(rate, 3600.0)
    factors = []
    for r_c, t in ((0, 0), (1, 1), (2, 2)):
        f, _q1, _q2, _ps1, _ps2 = fieldf.move_survival_factor(t, 0, r_c, 0, r_c + 1, 1000.0, 1.0, 3600.0, 0.0)
        factors.append(f)
    assert reported["metrics"]["execution_failure_probability"] == pytest.approx(1.0 - float(np.prod(factors)), abs=1e-6)

    tight = astar_4d(
        cost, wait, trav, (0, 0), (0, 3), 3600.0, 1.0, rover,
        shadow_cube=shadow, survival_field=fieldf, max_failure_probability=1e-6,
    )
    assert tight["error"] and "max_failure_probability" in tight["error"]
    assert tight["metrics"]["survival_enforced"] is True
    loose = astar_4d(
        cost, wait, trav, (0, 0), (0, 3), 3600.0, 1.0, rover,
        shadow_cube=shadow, survival_field=fieldf, max_failure_probability=0.9,
    )
    assert loose["error"] is None and loose["metrics"]["survival_enforced"] is True
    assert loose["metrics"]["execution_failure_probability"] <= 0.9


def test_a_start_the_optimal_policy_cannot_save_is_refused_at_once():
    from app.pathfinder_4d import astar_4d

    cost, wait, trav = _toy_cubes(n_slices=6)
    rover = _rover(p_base_w=0.0, p_idle_w=0.0, p_shadow_w=0.0, v_max_ms=1.0)
    req = np.full((1, 4), np.inf)
    req[0, 3] = 0.0
    # A field with a 2 h horizon cannot reach column 3 (three moves) from column 0.
    fieldf = S.build_survival_field(trav, None, None, 3600.0, rover, np.zeros((2, 1, 4)), 1.0, 1, req, 4, 0.0, 1.0)
    out = astar_4d(
        cost, wait, trav, (0, 0), (0, 3), 3600.0, 1.0, rover,
        shadow_cube=np.zeros((6, 1, 4)), survival_field=fieldf, max_failure_probability=0.05,
    )
    assert out["error"] and "optimal recovery policy" in out["error"]
    assert out["metrics"]["start_recovery_prob"] == 0.0


def test_a_requirement_at_capacity_means_a_full_battery_is_safe():
    """VIPER's hibernation charge (reserve + 96 h of shadow power) exceeds its
    capacity and is capped at e_cap; no bin's LOWER edge reaches e_cap, so
    without a cap at the top bin the haven would never be safe."""
    rover = _rover(p_base_w=0.0, p_idle_w=0.0, p_shadow_w=0.0)
    trav, req = _strip(2, 1)
    req[0, 1] = 1000.0  # the whole battery
    f = _field(trav, req, rover, n_bins=2, K=4)
    assert f.p_safe[0, 0, 1, 3] == 1.0 and f.policy[0, 0, 1, 3] == S.ACTION_SAFE
    assert f.p_safe[0, 0, 1, 2] == 0.0
    assert f.info()["safe_cells"] == 1




def test_report_only_mode_expands_exactly_the_nodes_of_the_plain_planner():
    """Without a beta the survival axis must not split the Pareto front:
    the plan is the cost-optimal one and its risk is reported, so the
    search expands the same nodes and finds the same states as without a
    field. Under a beta the axis is real and the node count may differ."""
    from app.pathfinder_4d import astar_4d

    rng = np.random.default_rng(5)
    n_slices, height, width = 30, 6, 6
    cost = rng.random((n_slices, height, width)) * 0.5
    wait = np.full((n_slices, height, width), 0.1)
    trav = np.ones((height, width), dtype=bool)
    rover = _rover(p_base_w=50.0, v_max_ms=1.0, e_cap_wh=5000.0)
    req = np.full((height, width), np.inf)
    req[5, 5] = 0.0
    shadow = rng.random((n_slices, height, width))
    fieldf = S.build_survival_field(trav, None, None, 3600.0, rover, shadow[:20], 1.0, 1, req, 8, 0.5 / 3.6, 1.0)
    plain = astar_4d(cost, wait, trav, (0, 0), (5, 5), 3600.0, 1.0, rover, shadow_cube=shadow)
    reported = astar_4d(cost, wait, trav, (0, 0), (5, 5), 3600.0, 1.0, rover, shadow_cube=shadow, survival_field=fieldf)
    assert plain["error"] is None and reported["error"] is None
    assert len(plain["path_states"]) > 1
    assert reported["path_states"] == plain["path_states"]
    assert reported["metrics"]["nodes_expanded"] == plain["metrics"]["nodes_expanded"]
    assert reported["metrics"]["total_cost"] == plain["metrics"]["total_cost"]
    assert 0.0 < reported["metrics"]["execution_failure_probability"] < 1.0
    bounded = astar_4d(
        cost, wait, trav, (0, 0), (5, 5), 3600.0, 1.0, rover, shadow_cube=shadow,
        survival_field=fieldf, max_failure_probability=0.9,
    )
    assert bounded["error"] is None and bounded["metrics"]["survival_enforced"] is True
