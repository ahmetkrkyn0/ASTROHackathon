"""app.safety_monitor: the STL AST, the two robustness engines, the trace
converters, the requirement catalogue and the online session -- all on
synthetic traces, no grids, no kernels.

Every expected robustness here is worked out by hand from the discrete-time
space-robustness semantics in the D3 spec (Donze & Maler 2010, RTAMT's
offline semantics as measured on 2026-09-04)."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from app import safety_monitor as sm
from app.safety_monitor import (
    Always,
    And,
    Atom,
    Eventually,
    Implies,
    Not,
    Or,
    Until,
    robustness_builtin,
    signals_of,
    to_rtamt,
)


# ── 1. AST → RTAMT text ─────────────────────────────────────────────────


def test_unbounded_always_renders_without_an_interval():
    assert to_rtamt(Always(Atom("soc_pct", ">=", 20.0))) == "always (soc_pct >= 20)"


def test_bounded_window_is_converted_from_hours_to_samples():
    formula = Eventually(Atom("charging", ">=", 0.5), 0.0, 6.0)
    assert to_rtamt(formula, dt_h=0.1) == "eventually[0,60] (charging >= 0.5)"


def test_bounded_window_without_a_sampling_step_is_refused():
    with pytest.raises(ValueError):
        to_rtamt(Always(Atom("x", "<=", 1.0), 0.0, 3.0))


def test_boolean_connectives_render_with_rtamt_keywords():
    formula = Always(Implies(Atom("soc_pct", "<", 20.0), Eventually(Atom("charging", ">=", 0.5), 0.0, 2.0)))
    assert (
        to_rtamt(formula, dt_h=1.0)
        == "always ((soc_pct < 20) -> (eventually[0,2] (charging >= 0.5)))"
    )
    assert to_rtamt(And(Atom("t", ">=", -20.0), Atom("t", "<=", 50.0))) == "((t >= -20) and (t <= 50))"
    assert to_rtamt(Or(Not(Atom("x", ">=", 0.0)), Atom("y", ">=", 0.0))) == "((not (x >= 0)) or (y >= 0))"
    assert to_rtamt(Until(Atom("x", ">=", 0.0), Atom("y", ">=", 0.0), 0.0, 2.0), dt_h=1.0) == (
        "((x >= 0) until[0,2] (y >= 0))"
    )


def test_signals_of_collects_every_atom():
    formula = Always(Implies(Atom("a", "<", 1.0), Or(Atom("b", ">=", 0.0), Atom("a", ">=", 3.0))))
    assert signals_of(formula) == {"a", "b"}


# ── 2. Built-in engine, hand-computed ───────────────────────────────────


def _rho(formula, dt_h=None, **signals):
    return robustness_builtin(formula, {k: np.asarray(v, dtype=float) for k, v in signals.items()}, dt_h=dt_h)


def test_atom_robustness_is_the_signed_distance_to_the_threshold():
    np.testing.assert_allclose(_rho(Atom("x", ">=", 0.0), x=[3, 1, 2]), [3, 1, 2])
    np.testing.assert_allclose(_rho(Atom("x", "<=", 5.0), x=[3, 1, 7]), [2, 4, -2])
    # Strict and non-strict comparisons share the same robustness.
    np.testing.assert_allclose(_rho(Atom("x", ">", 0.0), x=[3, -1]), [3, -1])
    np.testing.assert_allclose(_rho(Atom("x", "<", 5.0), x=[3, 7]), [2, -2])


def test_negation_conjunction_disjunction_implication():
    np.testing.assert_allclose(_rho(Not(Atom("x", ">=", 0.0)), x=[3, -1]), [-3, 1])
    np.testing.assert_allclose(_rho(And(Atom("x", ">=", 0.0), Atom("y", ">=", 0.0)), x=[3, -1], y=[1, 4]), [1, -1])
    np.testing.assert_allclose(_rho(Or(Atom("x", ">=", 0.0), Atom("y", ">=", 0.0)), x=[3, -1], y=[1, 4]), [3, 4])
    # (x >= 0) -> (y >= 0) == max(-rho_x, rho_y)
    np.testing.assert_allclose(
        _rho(Implies(Atom("x", ">=", 0.0), Atom("y", ">=", 0.0)), x=[3, -1, 2], y=[1, -4, -5]),
        [1, 1, -2],
    )
    # RTAMT's precedence, measured: `not a or b and c` == (not a) or (b and c).
    np.testing.assert_allclose(
        _rho(Or(Not(Atom("x", ">=", 0.0)), And(Atom("y", ">=", 0.0), Atom("x", "<=", 10.0))), x=[1, -2], y=[3, -4]),
        [3, 2],
    )


def test_unbounded_always_is_the_suffix_minimum():
    np.testing.assert_allclose(_rho(Always(Atom("x", ">=", 0.0)), x=[3, 1, 2]), [1, 1, 2])


def test_unbounded_eventually_is_the_suffix_maximum():
    np.testing.assert_allclose(_rho(Eventually(Atom("x", "<=", 0.0)), x=[5, 3, 1]), [-1, -1, -1])


def test_bounded_windows_are_clipped_at_the_end_of_the_trace():
    # Measured on rtamt 0.3.5: always[0,3] over x=[1,2,3,4,5] -> [1,2,3,4,5].
    np.testing.assert_allclose(_rho(Always(Atom("x", ">=", 0.0), 0.0, 3.0), dt_h=1.0, x=[1, 2, 3, 4, 5]), [1, 2, 3, 4, 5])
    np.testing.assert_allclose(
        _rho(Eventually(Atom("x", ">=", 0.0), 0.0, 3.0), dt_h=1.0, x=[-1, -2, -3, -4, -5]),
        [-1, -2, -3, -4, -5],
    )
    # A window starting later than the trace's first sample; an EMPTY window
    # is vacuous: +inf for always, -inf for eventually (measured on rtamt).
    np.testing.assert_allclose(_rho(Always(Atom("x", ">=", 0.0), 1.0, 2.0), dt_h=1.0, x=[9, 1, 5, 2]), [1, 2, 2, math.inf])
    np.testing.assert_allclose(
        _rho(Eventually(Atom("x", ">=", 0.0), 1.0, 2.0), dt_h=1.0, x=[9, 1, 5, 2]), [5, 5, 2, -math.inf]
    )
    np.testing.assert_allclose(_rho(Always(Atom("x", ">=", 0.0), 2.0, 2.0), dt_h=1.0, x=[1, 2, 3]), [3, math.inf, math.inf])


def test_bounded_window_in_hours_uses_the_sampling_step():
    # 0.5 h step: eventually[0, 1 h] spans three samples.
    np.testing.assert_allclose(
        _rho(Eventually(Atom("x", ">=", 0.0), 0.0, 1.0), dt_h=0.5, x=[-3, -2, 4, -1]),
        [4, 4, 4, -1],
    )


def test_response_pattern_matches_the_rtamt_measurement():
    # always ((x < 20) -> eventually[0,2] (y >= 0.5)), x=[30,10,10,10,30], y=[0,0,1,0,0]
    # measured on rtamt 0.3.5 -> [-0.5, -0.5, -0.5, -0.5, 10].
    formula = Always(Implies(Atom("x", "<", 20.0), Eventually(Atom("y", ">=", 0.5), 0.0, 2.0)))
    np.testing.assert_allclose(_rho(formula, dt_h=1.0, x=[30, 10, 10, 10, 30], y=[0, 0, 1, 0, 0]), [-0.5] * 4 + [10])


def test_until_matches_the_rtamt_measurement():
    # (x >= 0) until[0,2] (y >= 0), x=[1,2,3,-1], y=[-5,-4,2,3] -> [1,2,3,3]
    formula = Until(Atom("x", ">=", 0.0), Atom("y", ">=", 0.0), 0.0, 2.0)
    np.testing.assert_allclose(_rho(formula, dt_h=1.0, x=[1, 2, 3, -1], y=[-5, -4, 2, 3]), [1, 2, 3, 3])


def test_bounded_operator_without_a_step_is_refused_by_the_engine():
    with pytest.raises(ValueError):
        _rho(Always(Atom("x", ">=", 0.0), 0.0, 3.0), x=[1, 2, 3])


def test_missing_signal_is_a_key_error():
    with pytest.raises(KeyError):
        _rho(Atom("nope", ">=", 0.0), x=[1.0])


# ── 3. RTAMT cross-check (skipped without the package) ──────────────────


def _families(dt_h: float):
    return [
        Always(Atom("a", ">=", 0.0)),
        Eventually(Atom("a", "<=", 0.5)),
        Always(Implies(Atom("a", "<", 0.2), Eventually(Atom("b", ">=", 0.5), 0.0, 3.0 * dt_h))),
        Always(And(Atom("a", ">=", -0.5), Atom("a", "<=", 0.7)), 0.0, 4.0 * dt_h),
        Until(Atom("a", ">=", 0.0), Atom("b", ">=", 0.0), 0.0, 2.0 * dt_h),
        Or(Not(Always(Atom("b", ">=", 0.3), 1.0 * dt_h, 3.0 * dt_h)), Eventually(Atom("a", ">=", 0.9))),
    ]


def test_builtin_and_rtamt_agree_on_random_traces():
    pytest.importorskip("rtamt")
    rng = np.random.default_rng(7)
    dt_h = 0.25
    for trial in range(20):
        n = int(rng.integers(3, 30))
        signals = {"a": rng.normal(size=n), "b": rng.normal(size=n)}
        for formula in _families(dt_h):
            ours = robustness_builtin(formula, signals, dt_h=dt_h)
            theirs = sm.robustness_rtamt(formula, signals, dt_h=dt_h)
            np.testing.assert_allclose(ours, theirs, atol=1e-9, err_msg=f"trial {trial}: {to_rtamt(formula, dt_h)}")


def test_engines_agree_on_infinite_signal_values():
    pytest.importorskip("rtamt")
    signals = {"a": np.array([math.inf, 3.0, math.inf]), "b": np.array([1.0, -1.0, 2.0])}
    for formula in (Always(Atom("a", ">=", 0.0)), Always(Or(Atom("b", ">=", 0.0), Atom("a", ">=", 5.0)))):
        ours = robustness_builtin(formula, signals)
        theirs = sm.robustness_rtamt(formula, signals)
        assert list(ours) == list(theirs)


def test_auto_engine_reports_which_engine_ran():
    rho, engine = sm.robustness(Always(Atom("a", ">=", 0.0)), {"a": np.array([2.0, 1.0])})
    assert engine == ("rtamt" if sm.rtamt_available() else "builtin")
    np.testing.assert_allclose(rho, [1.0, 1.0])


def test_requesting_rtamt_without_the_package_raises(monkeypatch):
    monkeypatch.setattr(sm, "_import_rtamt", lambda: None)
    assert sm.rtamt_available() is False
    with pytest.raises(ImportError):
        sm.robustness(Always(Atom("a", ">=", 0.0)), {"a": np.array([1.0])}, engine="rtamt")
    rho, engine = sm.robustness(Always(Atom("a", ">=", 0.0)), {"a": np.array([1.0])}, engine="auto")
    assert engine == "builtin"


def test_unknown_engine_is_rejected():
    with pytest.raises(ValueError):
        sm.robustness(Always(Atom("a", ">=", 0.0)), {"a": np.array([1.0])}, engine="z3")


# ── 4. Derived signals ─────────────────────────────────────────────────


def test_continuous_shadow_hours_counts_step_durations_and_resets_when_lit():
    t = np.array([0.0, 1.0, 3.0, 4.0, 6.0])
    in_shadow = np.array([0, 1, 1, 0, 1], dtype=bool)
    np.testing.assert_allclose(sm.continuous_shadow_hours(t, in_shadow), [0, 1, 3, 0, 2])


def test_hours_below_reserve_is_causal_and_resets_on_charging_or_recovery():
    t = np.array([0.0, 1.0, 2.0, 4.0, 5.0, 7.0])
    soc = np.array([30.0, 15.0, 15.0, 15.0, 25.0, 10.0])
    charging = np.array([0, 0, 1, 0, 0, 0], dtype=bool)
    np.testing.assert_allclose(sm.hours_below_reserve(t, soc, 20.0, charging), [0, 1, 0, 2, 0, 2])


def test_hours_below_reserve_counts_from_the_trace_start_when_never_above():
    t = np.array([0.0, 0.5, 2.0])
    soc = np.array([10.0, 10.0, 10.0])
    charging = np.zeros(3, dtype=bool)
    np.testing.assert_allclose(sm.hours_below_reserve(t, soc, 20.0, charging), [0, 0.5, 2.0])


def _ramp(rows: int, cols: int, resolution_m: float, tan_slope: float) -> np.ndarray:
    return np.fromfunction(lambda r, c: tan_slope * resolution_m * c, (rows, cols), dtype=float)


def test_path_lateral_slopes_follow_the_planners_gradient_rule():
    # z rises 0.2 m per metre along the columns: an edge along a ROW rolls
    # on the full cross-slope, an edge along a COLUMN on none, a diagonal
    # on 0.2 / sqrt(2).
    elevation = _ramp(5, 5, 80.0, 0.2)
    cells = [(0, 0), (1, 0), (1, 1), (2, 2)]
    lateral = sm.path_lateral_slopes(cells, elevation, 80.0)
    expected = [0.0, math.degrees(math.atan(0.2)), 0.0, math.degrees(math.atan(0.2 / math.sqrt(2)))]
    np.testing.assert_allclose(lateral, expected, atol=1e-9)


def test_path_step_slopes_are_the_grade_of_each_step():
    elevation = _ramp(5, 5, 80.0, 0.2)
    cells = [(0, 0), (0, 1), (1, 2), (2, 2)]
    steps = sm.path_step_slopes(cells, elevation, 80.0)
    expected = [0.0, math.degrees(math.atan(0.2)), math.degrees(math.atan(16.0 / (80.0 * math.sqrt(2)))), 0.0]
    np.testing.assert_allclose(steps, expected, atol=1e-9)


# ── 5. Trace converters ────────────────────────────────────────────────

from app.constants import get_rover  # noqa: E402
from app.simulation import MAX_RECHARGE_HOURS, RoverState  # noqa: E402


def _state(step, row, col, dist, t, soc_low, slope, seg, temp, shadow, energy, solar, recharged=False, stranded=False):
    return RoverState(
        step=step, row=row, col=col, distance_m=dist, elapsed_hours=t, battery_wh=0.0,
        battery_pct=100.0 if recharged else soc_low, risk_level="LOW", slope_deg=slope,
        surface_temp_c=temp, shadow_ratio=shadow, node_cost=1.0, step_energy_wh=energy,
        cumulative_cost=1.0, recharge_count=int(recharged), recharged_this_step=recharged,
        segment_slope_deg=seg, battery_low_pct=soc_low, stranded=stranded, step_solar_wh=solar,
    )


_PLANNED = [(0, 0), (0, 1), (0, 2), (0, 3)]


def _two_d_states():
    return [
        _state(0, 0, 0, 0.0, 0.0, 100.0, 3.0, 0.0, -60.0, 0.1, 0.0, 0.0),
        _state(1, 0, 1, 80.0, 0.2, 60.0, 5.0, 8.0, -60.0, 0.5, 30.0, 5.0),
        _state(2, 0, 2, 160.0, 0.5, 15.0, 4.0, 2.0, 10.0, 0.5, 30.0, 40.0),
        _state(3, 0, 3, 240.0, 0.9, 25.0, 6.0, 1.0, -60.0, 0.1, 20.0, 0.0, recharged=True),
    ]


def test_trace_from_states_names_every_signal():
    rover = get_rover("lpr_1")
    trace = sm.trace_from_states(_two_d_states(), _PLANNED, np.zeros((4, 4)), 80.0, rover)
    assert trace.kind == "2d" and trace.complete and not trace.stranded and trace.extended_h is None
    np.testing.assert_allclose(trace.t_h, [0.0, 0.2, 0.5, 0.9])
    s = trace.signals
    np.testing.assert_allclose(s["soc_pct"], [100, 60, 15, 25])
    np.testing.assert_allclose(s["charging"], [0, 0, 1, 1])
    np.testing.assert_allclose(s["shadow_continuous_h"], [0.0, 0.2, 0.5, 0.0])
    np.testing.assert_allclose(s["hours_below_reserve_h"], [0.0, 0.0, 0.0, 0.0])
    np.testing.assert_allclose(s["inner_temp_c"], [0.0, 0.0, -30.0, 0.0])  # lpr_1 offsets +60 / -40
    np.testing.assert_allclose(s["drive_slope_deg"], [3, 8, 4, 6])
    np.testing.assert_allclose(s["lateral_slope_deg"], [0, 0, 0, 0])
    np.testing.assert_allclose(s["moving"], [0, 1, 1, 1])
    np.testing.assert_allclose(s["dist_to_goal_m"], [240, 160, 80, 0])
    np.testing.assert_allclose(s["at_goal"], [0, 0, 0, 1])
    assert "earth_link_h" not in s and "haven_margin_h" not in s
    assert list(trace.index) == [0, 1, 2, 3]
    assert trace.cells == _PLANNED


def test_trace_from_states_extends_a_stranded_trace_by_one_lunar_day():
    rover = get_rover("lpr_1")
    states = _two_d_states()[:2] + [
        _state(2, 0, 2, 160.0, 0.5, 15.0, 4.0, 2.0, 10.0, 0.5, 30.0, 0.0, stranded=True)
    ]
    trace = sm.trace_from_states(states, _PLANNED, np.zeros((4, 4)), 80.0, rover)
    assert trace.stranded and trace.complete
    extension = MAX_RECHARGE_HOURS - 0.3
    assert trace.extended_h == pytest.approx(extension)
    assert trace.t_h.shape == (4,)
    assert trace.t_h[-1] == pytest.approx(0.5 + extension)
    s = trace.signals
    assert s["soc_pct"][-1] == 15.0 and s["charging"][-1] == 0 and s["moving"][-1] == 0
    assert s["shadow_continuous_h"][-1] == pytest.approx(0.5 + extension)
    assert s["hours_below_reserve_h"][-2] == pytest.approx(0.3)
    assert s["hours_below_reserve_h"][-1] == pytest.approx(0.3 + extension)
    assert s["dist_to_goal_m"][-1] == 80.0 and s["at_goal"][-1] == 0
    assert list(trace.index) == [0, 1, 2, 2]


def _plan4d_inputs():
    res = 320.0
    return dict(
        path_states=[[0, 0, 0], [0, 1, 1], [0, 1, 2], [1, 2, 3]],
        path_battery_pct=[100.0, 90.0, 95.0, 80.0],
        path_dark_hours=[0.0, 1.0, 2.0, 0.0],
        path_earth_visible=[True, True, False, True],
        path_hours_until_earthset=[10.0, 9.0, None, None],
        path_haven_margin_h=[5.0, 4.0, None, 3.0],
        path_time_to_haven_h=[5.0, 5.0, None, 4.0],
        slice_hours=1.0,
        coarse_slope=np.arange(3, 12, dtype=float).reshape(3, 3),
        coarse_elevation=_ramp(3, 3, res, 0.1),
        coarse_thermal=np.full((3, 3), -60.0),
        resolution_m=res,
        rover=get_rover("lpr_1"),
    )


def test_trace_from_plan4d_names_every_signal():
    trace = sm.trace_from_plan4d(**_plan4d_inputs())
    assert trace.kind == "4d" and trace.complete and not trace.stranded
    np.testing.assert_allclose(trace.t_h, [0, 1, 2, 3])
    s = trace.signals
    np.testing.assert_allclose(s["soc_pct"], [100, 90, 95, 80])
    np.testing.assert_allclose(s["charging"], [0, 0, 1, 0])
    np.testing.assert_allclose(s["shadow_continuous_h"], [0, 1, 2, 0])
    np.testing.assert_allclose(s["moving"], [0, 1, 0, 1])
    np.testing.assert_allclose(s["earth_link_h"], [10, 9, -1, math.inf])
    np.testing.assert_allclose(s["haven_margin_h"], [5, 4, math.inf, 3])
    step_row = math.degrees(math.atan(0.1))
    np.testing.assert_allclose(s["drive_slope_deg"], [3, max(4, step_row), 4, 8])
    diag = math.degrees(math.atan(0.1 / math.sqrt(2)))
    np.testing.assert_allclose(s["lateral_slope_deg"], [0, 0, 0, diag], atol=1e-9)
    np.testing.assert_allclose(s["inner_temp_c"], [0, 0, 0, 0])
    total = 320.0 + 320.0 * math.sqrt(2)
    np.testing.assert_allclose(s["dist_to_goal_m"], [total, total - 320.0, total - 320.0, 0.0])
    np.testing.assert_allclose(s["at_goal"], [0, 0, 0, 1])
    assert trace.cells == [(0, 0), (0, 1), (0, 1), (1, 2)]
    assert trace.notes["thermal_source"] == "static_layer"


def test_trace_from_plan4d_without_earth_or_haven_fields_omits_those_signals():
    inputs = _plan4d_inputs()
    inputs.update(path_earth_visible=None, path_hours_until_earthset=None, path_haven_margin_h=None, path_time_to_haven_h=None)
    trace = sm.trace_from_plan4d(**inputs)
    assert "earth_link_h" not in trace.signals and "haven_margin_h" not in trace.signals


def test_trace_from_plan4d_treats_a_finite_deadline_with_no_haven_as_an_unbounded_violation():
    # The planner reports None for the margin both when the Earth never
    # sets (+inf) and when no haven is reachable before a FINITE Earthset
    # (-inf). LPR-1 on 2026-09-28 is the second case (B5): the link ends in
    # 184 h and no haven exists on that lunar day.
    inputs = _plan4d_inputs()
    inputs.update(
        path_hours_until_earthset=[10.0, 9.0, 8.0, 7.0],
        path_haven_margin_h=[None, None, None, None],
        path_time_to_haven_h=[None, None, None, None],
    )
    trace = sm.trace_from_plan4d(**inputs)
    assert list(trace.signals["haven_margin_h"]) == [-math.inf] * 4
    assert trace.notes["haven_unreachable_states"] == 4
    block = sm.evaluate_catalogue(trace, get_rover("lpr_1"))
    entry = {e["id"]: e for e in block["requirements"]}["LP-R09"]
    assert entry["satisfied"] is False and entry["rho"] is None and "unbounded" in entry["reason"]
    assert "LP-R09" in block["violated"] and block["verdict"] == "violated"
    json.dumps(block, allow_nan=False)
    # Open-ended link with no haven is not a violation of the leg rule.
    inputs.update(path_hours_until_earthset=[None] * 4)
    trace = sm.trace_from_plan4d(**inputs)
    assert list(trace.signals["haven_margin_h"]) == [math.inf] * 4


def test_trace_from_samples_keeps_only_the_signals_given():
    rover = get_rover("lpr_1")
    samples = [
        {"t_h": 0.0, "soc_pct": 50.0, "surface_temp_c": -60.0, "shadow_ratio": 0.1, "bogus": 1},
        {"t_h": 1.0, "soc_pct": 15.0, "surface_temp_c": -60.0, "shadow_ratio": 0.9},
        {"t_h": 2.5, "soc_pct": 18.0, "surface_temp_c": 5.0, "shadow_ratio": 0.9, "charging": True},
    ]
    trace = sm.trace_from_samples(samples, rover)
    assert trace.kind == "telemetry"
    s = trace.signals
    np.testing.assert_allclose(s["soc_pct"], [50, 15, 18])
    np.testing.assert_allclose(s["inner_temp_c"], [0.0, 0.0, -35.0])
    np.testing.assert_allclose(s["shadow_continuous_h"], [0.0, 1.0, 2.5])
    np.testing.assert_allclose(s["charging"], [0, 0, 1])
    np.testing.assert_allclose(s["hours_below_reserve_h"], [0.0, 1.0, 0.0])
    for absent in ("drive_slope_deg", "lateral_slope_deg", "moving", "earth_link_h", "haven_margin_h", "dist_to_goal_m", "at_goal"):
        assert absent not in s
    assert trace.notes["ignored_keys"] == ["bogus"]


def test_trace_from_samples_accepts_direct_signals_and_derives_at_goal():
    rover = get_rover("nasa_viper")
    samples = [
        {"t_h": 0.0, "inner_temp_c": 5.0, "in_shadow": True, "slope_deg": 4.0, "lateral_slope_deg": 2.0,
         "moving": True, "earth_link_h": 3.0, "haven_margin_h": 1.5, "dist_to_goal_m": 100.0},
        {"t_h": 0.5, "inner_temp_c": 6.0, "in_shadow": False, "slope_deg": 9.0, "lateral_slope_deg": 1.0,
         "moving": False, "earth_link_h": 2.5, "haven_margin_h": 1.0, "dist_to_goal_m": 0.0},
    ]
    s = sm.trace_from_samples(samples, rover).signals
    np.testing.assert_allclose(s["inner_temp_c"], [5, 6])
    np.testing.assert_allclose(s["shadow_continuous_h"], [0.0, 0.0])
    np.testing.assert_allclose(s["drive_slope_deg"], [4, 9])
    np.testing.assert_allclose(s["lateral_slope_deg"], [2, 1])
    np.testing.assert_allclose(s["moving"], [1, 0])
    np.testing.assert_allclose(s["earth_link_h"], [3, 2.5])
    np.testing.assert_allclose(s["haven_margin_h"], [1.5, 1.0])
    np.testing.assert_allclose(s["at_goal"], [0, 1])
    assert "soc_pct" not in s


@pytest.mark.parametrize(
    "samples",
    [
        [],
        [{"t_h": 1.0, "soc_pct": 50.0}, {"t_h": 0.5, "soc_pct": 50.0}],
        [{"t_h": 0.0, "soc_pct": float("nan")}],
        [{"soc_pct": 50.0}],
        [{"t_h": 0.0, "soc_pct": "high"}],
    ],
)
def test_trace_from_samples_rejects_malformed_input(samples):
    with pytest.raises(ValueError):
        sm.trace_from_samples(samples, get_rover("lpr_1"))


# ── 6. Catalogue ───────────────────────────────────────────────────────


def _bound(rover_id: str, **kwargs):
    return {b.requirement.id: b for b in sm.bind_catalogue(get_rover(rover_id), **kwargs)}


def test_catalogue_thresholds_come_from_the_rover():
    viper = _bound("nasa_viper")
    assert [rid for rid in viper] == [f"LP-R{i:02d}" for i in range(1, 12)]
    assert viper["LP-R01"].threshold == 96.0 and viper["LP-R01"].requirement.rover_parameter == "h_max_shadow_h"
    assert viper["LP-R02"].threshold == 20.0
    assert viper["LP-R03"].threshold == 6.0 and viper["LP-R03"].threshold_source == "catalogue"
    assert viper["LP-R04"].threshold == (-20.0, 50.0)
    assert viper["LP-R05"].threshold == (0.0, 35.0)
    assert viper["LP-R06"].threshold == 20.0
    assert viper["LP-R07"].threshold == 15.0
    assert viper["LP-R11"].threshold == 20.0
    assert all(viper[rid].applicable for rid in viper)
    assert _bound("cnsa_yutu_2")["LP-R02"].threshold == 30.0
    assert _bound("lpr_1", recharge_deadline_h=3.0)["LP-R03"].threshold == 3.0


def test_a_rover_without_an_envelope_makes_that_requirement_inapplicable():
    luvmi = _bound("luvmi_m")
    assert luvmi["LP-R04"].applicable is False and "elec_op" in luvmi["LP-R04"].reason
    assert luvmi["LP-R04"].formula is None
    assert luvmi["LP-R05"].threshold == (-100.0, 0.0)


def test_every_catalogue_formula_renders_and_names_its_signal():
    for bound in sm.bind_catalogue(get_rover("nasa_viper")):
        text = to_rtamt(bound.formula)
        assert bound.requirement.signal in text
        assert signals_of(bound.formula) == {bound.requirement.signal}
        assert bound.requirement.fretish.endswith(("satisfy " + bound.requirement.response, bound.requirement.response))


# ── 7. evaluate_catalogue on a hand-built trace ────────────────────────

_SAMPLES = [
    {"t_h": 0.0, "soc_pct": 100.0, "inner_temp_c": 10.0, "in_shadow": False, "slope_deg": 5.0, "lateral_slope_deg": 3.0,
     "moving": False, "earth_link_h": 30.0, "haven_margin_h": 12.0, "dist_to_goal_m": 400.0},
    {"t_h": 1.0, "soc_pct": 60.0, "inner_temp_c": 20.0, "in_shadow": True, "slope_deg": 12.0, "lateral_slope_deg": 6.0,
     "moving": True, "earth_link_h": 25.0, "haven_margin_h": 10.0, "dist_to_goal_m": 300.0},
    {"t_h": 3.0, "soc_pct": 30.0, "inner_temp_c": 33.0, "in_shadow": True, "slope_deg": 18.0, "lateral_slope_deg": 14.0,
     "moving": True, "earth_link_h": 20.0, "haven_margin_h": 7.0, "dist_to_goal_m": 100.0},
    {"t_h": 4.0, "soc_pct": 25.0, "inner_temp_c": 5.0, "in_shadow": False, "slope_deg": 3.0, "lateral_slope_deg": 1.0,
     "moving": True, "earth_link_h": 19.0, "haven_margin_h": 9.0, "dist_to_goal_m": 0.0},
]


def _by_id(block):
    return {entry["id"]: entry for entry in block["requirements"]}


def test_evaluate_catalogue_reports_hand_computed_margins():
    rover = get_rover("nasa_viper")
    block = sm.evaluate_catalogue(sm.trace_from_samples(_SAMPLES, rover), rover)
    r = _by_id(block)
    expected = {
        "LP-R01": (93.0, "h", 2), "LP-R02": (5.0, "pct", 3), "LP-R03": (6.0, "h", 0),
        "LP-R04": (17.0, "degC", 2), "LP-R05": (2.0, "degC", 2), "LP-R06": (2.0, "deg", 2),
        "LP-R07": (1.0, "deg", 2), "LP-R08": (19.0, "h", 3), "LP-R09": (7.0, "h", 2),
        "LP-R10": (0.0, "m", 3), "LP-R11": (5.0, "pct", 3),
    }
    for rid, (rho, unit, worst) in expected.items():
        entry = r[rid]
        assert entry["applicable"] is True, rid
        assert entry["rho"] == pytest.approx(rho), rid
        assert entry["unit"] == unit, rid
        assert entry["satisfied"] is True, rid
        assert entry["worst_at"]["index"] == worst, rid
        assert entry["worst_at"]["hours"] == pytest.approx(_SAMPLES[worst]["t_h"]), rid
    assert r["LP-R10"]["boundary"] is True and r["LP-R02"]["boundary"] is False
    assert r["LP-R01"]["rho_normalized"] == pytest.approx(93.0 / 96.0)
    assert r["LP-R04"]["rho_normalized"] == pytest.approx(17.0 / 35.0)
    assert r["LP-R08"]["rho_normalized"] == pytest.approx(19.0 / 24.0)
    assert r["LP-R10"]["rho_normalized"] == pytest.approx(0.0)
    assert r["LP-R03"]["threshold_source"] == "catalogue" and r["LP-R01"]["threshold_source"] == "rover"
    assert block["min_margin"] == {
        "id": "LP-R07", "rho": pytest.approx(1.0), "unit": "deg", "rho_normalized": pytest.approx(1.0 / 15.0, abs=1e-6)
    }
    assert block["n_applicable"] == 11 and block["n_violated"] == 0 and block["violated"] == []
    assert block["verdict"] == "satisfied"
    monitor = block["monitor"]
    assert monitor["engine"] in ("rtamt", "builtin")
    assert monitor["trace"]["kind"] == "telemetry" and monitor["trace"]["n_samples"] == 4
    assert monitor["trace"]["duration_h"] == pytest.approx(4.0)
    assert "not proven" in monitor["claim"] and "runtime monitoring" in monitor["claim"]
    if sm.rtamt_available():
        assert monitor["cross_check"]["engine"] == "builtin"
        assert monitor["cross_check"]["max_abs_diff"] == pytest.approx(0.0, abs=1e-9)
    else:
        assert monitor["cross_check"] is None
    json.dumps(block, allow_nan=False)


def test_a_violation_is_negative_and_named():
    rover = get_rover("nasa_viper")
    samples = [dict(s) for s in _SAMPLES]
    samples[2]["lateral_slope_deg"] = 16.0
    block = sm.evaluate_catalogue(sm.trace_from_samples(samples, rover), rover)
    entry = _by_id(block)["LP-R07"]
    assert entry["rho"] == pytest.approx(-1.0) and entry["satisfied"] is False
    assert block["violated"] == ["LP-R07"] and block["n_violated"] == 1
    assert block["verdict"] == "violated"
    assert block["min_margin"]["id"] == "LP-R07" and block["min_margin"]["rho"] == pytest.approx(-1.0)


def test_an_open_ended_margin_is_null_not_infinite():
    rover = get_rover("nasa_viper")
    trace = sm.Trace(
        kind="telemetry",
        t_h=np.array([0.0, 1.0]),
        signals={"haven_margin_h": np.array([math.inf, math.inf]), "moving": np.array([1.0, 1.0]),
                 "earth_link_h": np.array([math.inf, 4.0])},
        index=np.array([0, 1]),
        cells=None,
    )
    r = _by_id(sm.evaluate_catalogue(trace, rover))
    assert r["LP-R09"]["rho"] is None and r["LP-R09"]["open_ended"] is True and r["LP-R09"]["satisfied"] is True
    assert r["LP-R09"]["worst_at"] is None and r["LP-R09"]["rho_normalized"] is None
    assert r["LP-R08"]["rho"] == pytest.approx(4.0) and r["LP-R08"]["open_ended"] is False


def test_an_empty_scope_is_inapplicable_and_a_missed_goal_is_a_violation():
    rover = get_rover("nasa_viper")
    samples = [dict(s) for s in _SAMPLES[:3]]  # never reaches dist 0
    block = sm.evaluate_catalogue(sm.trace_from_samples(samples, rover), rover)
    r = _by_id(block)
    assert r["LP-R11"]["applicable"] is False and "scope" in r["LP-R11"]["reason"]
    assert r["LP-R10"]["rho"] == pytest.approx(-100.0) and r["LP-R10"]["satisfied"] is False
    assert block["violated"] == ["LP-R10"] and block["verdict"] == "violated"
    # A mission-class requirement never drives min_margin.
    assert block["min_margin"]["id"] != "LP-R10"


def test_missing_signals_make_requirements_inapplicable_not_satisfied():
    rover = get_rover("lpr_1")
    block = sm.evaluate_catalogue(sm.trace_from_samples([{"t_h": 0.0, "soc_pct": 50.0}, {"t_h": 1.0, "soc_pct": 40.0}], rover), rover)
    r = _by_id(block)
    assert r["LP-R01"]["applicable"] is False and "shadow_continuous_h" in r["LP-R01"]["reason"]
    assert r["LP-R01"]["rho"] is None and r["LP-R01"]["satisfied"] is None
    assert block["n_applicable"] == 2 and {rid for rid, e in r.items() if e["applicable"]} == {"LP-R02", "LP-R03"}
    assert block["verdict"] == "satisfied"


def test_a_rover_without_an_envelope_reports_the_reason_in_the_block():
    rover = get_rover("luvmi_m")
    r = _by_id(sm.evaluate_catalogue(sm.trace_from_samples(_SAMPLES, rover), rover))
    assert r["LP-R04"]["applicable"] is False and "elec_op" in r["LP-R04"]["reason"]


def test_an_incomplete_trace_leaves_liveness_pending():
    rover = get_rover("nasa_viper")
    trace = sm.trace_from_samples(_SAMPLES[:2], rover, complete=False)
    block = sm.evaluate_catalogue(trace, rover)
    r = _by_id(block)
    assert r["LP-R10"]["satisfied"] is None and r["LP-R10"]["pending"] is True
    assert r["LP-R02"]["satisfied"] is True and r["LP-R02"]["pending"] is False
    assert block["verdict"] == "pending"


def test_nothing_applicable_is_not_evaluated():
    rover = get_rover("nasa_viper")
    trace = sm.Trace(kind="telemetry", t_h=np.array([0.0]), signals={}, index=np.array([0]), cells=None)
    block = sm.evaluate_catalogue(trace, rover)
    assert block["n_applicable"] == 0 and block["verdict"] == "not_evaluated" and block["min_margin"] is None


def test_builtin_engine_can_be_forced():
    rover = get_rover("nasa_viper")
    block = sm.evaluate_catalogue(sm.trace_from_samples(_SAMPLES, rover), rover, engine="builtin")
    assert block["monitor"]["engine"] == "builtin" and block["monitor"]["cross_check"] is None


def test_rank_by_margin_orders_safest_first_and_unevaluated_last():
    def block(verdict, normalized=None, n_violated=0):
        return {
            "verdict": verdict,
            "n_violated": n_violated,
            "min_margin": None if normalized is None else {"id": "LP-R02", "rho": normalized * 20, "unit": "pct", "rho_normalized": normalized},
        }

    ranking = sm.rank_by_margin([
        ("a", block("satisfied", 0.3)),
        ("b", block("satisfied", 0.5)),
        ("c", block("violated", -0.2, 1)),
        ("d", block("not_evaluated")),
        ("e", block("violated", -0.1, 2)),
    ])
    assert [entry["label"] for entry in ranking] == ["b", "a", "c", "e", "d"]
    assert ranking[0]["min_margin"]["rho_normalized"] == 0.5 and ranking[0]["verdict"] == "satisfied"


# ── 8. FRET export ─────────────────────────────────────────────────────

from pathlib import Path  # noqa: E402

_FRET_JSON = Path(__file__).resolve().parent.parent / "docs" / "requirements" / "lunapath.fret.json"


def test_fret_export_carries_every_requirement_with_fret_like_fields():
    doc = sm.fret_export()
    assert doc["project"] == "LunaPath"
    assert "not exported from the FRET tool" in doc["provenance"]["method"]
    reqs = doc["requirements"]
    assert [r["reqid"] for r in reqs] == [f"LP-R{i:02d}" for i in range(1, 12)]
    for r in reqs:
        assert r["fulltext"].startswith(("The rover shall", "In ", "Upon "))
        assert r["rationale"]
        sem = r["semantics"]
        for key in ("scope", "condition", "component", "timing", "response", "ftLTL", "stl", "monitored_stl"):
            assert key in sem, (r["reqid"], key)
        mon = r["monitor"]
        for key in ("signal", "unit", "rover_parameter", "threshold_source", "thresholds_by_rover", "formula_by_rover", "trace_kinds", "class"):
            assert key in mon, (r["reqid"], key)
        assert set(mon["thresholds_by_rover"]) == {"lpr_1", "luvmi_m", "nasa_viper", "cnsa_yutu_2"}
    r4 = next(r for r in reqs if r["reqid"] == "LP-R04")
    assert r4["monitor"]["thresholds_by_rover"]["luvmi_m"] is None
    assert r4["monitor"]["thresholds_by_rover"]["nasa_viper"] == [-20.0, 50.0]
    assert r4["monitor"]["formula_by_rover"]["luvmi_m"] is None
    r3 = next(r for r in reqs if r["reqid"] == "LP-R03")
    assert r3["fulltext"] == "Upon soc_pct < soc_min the rover shall within 6 hours satisfy charging"
    assert r3["monitor"]["threshold_source"] == "catalogue"
    assert r3["monitor"]["formula_by_rover"]["lpr_1"] == "always (hours_below_reserve_h <= 6)"
    r8 = next(r for r in reqs if r["reqid"] == "LP-R08")
    assert r8["fulltext"] == "In moving mode the rover shall always satisfy earth_visible"
    assert r8["semantics"]["scope"] == "moving"
    json.dumps(doc, allow_nan=False)


def test_checked_in_fret_file_matches_the_catalogue():
    assert _FRET_JSON.exists(), "run scripts/export_fret_requirements.py"
    on_disk = json.loads(_FRET_JSON.read_text(encoding="utf-8"))
    assert on_disk == json.loads(json.dumps(sm.fret_export()))


# ── 9. Online session (the ROS node's brain) ───────────────────────────


def test_session_verdicts_are_monotone_and_new_violations_fire_once():
    session = sm.SafetyMonitorSession(get_rover("nasa_viper"), engine="builtin")
    first = session.push({"t_h": 0.0, "soc_pct": 50.0, "inner_temp_c": 10.0, "in_shadow": True})
    assert first["n_samples"] == 1
    assert first["newly_violated"] == [] and first["violated"] == []
    assert first["safety_margins"]["verdict"] == "satisfied"
    assert first["safety_margins"]["monitor"]["trace"]["complete"] is False
    second = session.push({"t_h": 1.0, "soc_pct": 15.0, "inner_temp_c": 10.0, "in_shadow": True})
    assert second["newly_violated"] == ["LP-R02"] and second["violated"] == ["LP-R02"]
    assert second["safety_margins"]["verdict"] == "violated"
    # The battery recovers, but "always" over the flown prefix stays violated
    # and the violation is not announced a second time.
    third = session.push({"t_h": 2.0, "soc_pct": 25.0, "inner_temp_c": 10.0, "in_shadow": True})
    assert third["newly_violated"] == [] and third["violated"] == ["LP-R02"]
    assert _by_id(third["safety_margins"])["LP-R02"]["rho"] == pytest.approx(-5.0)
    assert _by_id(third["safety_margins"])["LP-R02"]["worst_at"]["index"] == 1


def test_session_liveness_is_pending_until_the_goal_is_seen():
    session = sm.SafetyMonitorSession(get_rover("lpr_1"), engine="builtin")
    first = session.push({"t_h": 0.0, "dist_to_goal_m": 100.0})
    r = _by_id(first["safety_margins"])
    assert r["LP-R10"]["pending"] is True and first["safety_margins"]["verdict"] == "pending"
    assert first["newly_violated"] == []
    second = session.push({"t_h": 1.0, "dist_to_goal_m": 0.0})
    assert _by_id(second["safety_margins"])["LP-R10"]["satisfied"] is True
    assert second["safety_margins"]["verdict"] == "satisfied"


def test_session_finish_evaluates_the_complete_trace():
    session = sm.SafetyMonitorSession(get_rover("lpr_1"), engine="builtin")
    session.push({"t_h": 0.0, "dist_to_goal_m": 100.0, "soc_pct": 50.0})
    block = session.finish()
    assert block["monitor"]["trace"]["complete"] is True
    assert _by_id(block)["LP-R10"]["satisfied"] is False and block["verdict"] == "violated"


def test_session_rejects_time_going_backwards_and_keeps_its_state():
    session = sm.SafetyMonitorSession(get_rover("lpr_1"), engine="builtin")
    session.push({"t_h": 1.0, "soc_pct": 50.0})
    with pytest.raises(ValueError):
        session.push({"t_h": 0.5, "soc_pct": 50.0})
    assert session.n_samples == 1


def test_session_uses_the_requested_deadline():
    session = sm.SafetyMonitorSession(get_rover("lpr_1"), engine="builtin", recharge_deadline_h=2.0)
    session.push({"t_h": 0.0, "soc_pct": 10.0})
    result = session.push({"t_h": 3.0, "soc_pct": 10.0})
    assert "LP-R03" in result["newly_violated"]
    assert _by_id(result["safety_margins"])["LP-R03"]["rho"] == pytest.approx(-1.0)
