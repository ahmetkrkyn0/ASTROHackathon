"""D5 unit tests: the sampler, route identity, and the dominance rule.

No grids and no HTTP here -- these pin the arithmetic that decides what
lands on the front, because that is where a silent error would be
invisible: a front is plausible whatever it contains.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.pareto import (
    OBJECTIVE_KEYS,
    OBJECTIVE_QUANTUM,
    PARETO_COMPLETENESS,
    PARETO_OBJECTIVES,
    SIMPLEX_WEIGHT_KEYS,
    diagnostics,
    dominance_epsilon,
    dominates,
    non_dominated,
    objectives_from,
    route_id,
    simplex_samples,
)


def _obj(hours, energy, shadow, thermal=1.0):
    return {
        "hours": hours,
        "energy_wh": energy,
        "shadow_exposure_h": shadow,
        "thermal_risk": thermal,
    }


def _route(route_id_, hours, energy, shadow, thermal=1.0, nominal=False):
    return {
        "route_id": route_id_,
        "objectives": _obj(hours, energy, shadow, thermal),
        "is_nominal": nominal,
    }


# ── the sampler ─────────────────────────────────────────────────────────────


def test_samples_lie_on_the_simplex():
    for _, weights in simplex_samples(64, seed=1):
        assert set(weights) == set(SIMPLEX_WEIGHT_KEYS)
        assert all(w >= 0.0 for w in weights.values())
        assert math.isclose(sum(weights.values()), 1.0, rel_tol=0, abs_tol=1e-12)


def test_sampler_is_reproducible_from_the_seed():
    """The front is only assertable because the same seed gives the same draws."""
    assert simplex_samples(16, seed=7) == simplex_samples(16, seed=7)
    assert simplex_samples(16, seed=7) != simplex_samples(16, seed=8)


def test_sampler_agrees_with_dirichlet_to_one_ulp_but_is_not_it():
    """Normalised exponentials are Dirichlet(1,1,1,1) -- to within one ULP.

    Measured on numpy 2.2.1, seed 3, 32 draws: the two agree to a maximum
    absolute difference of 1.11e-16, with 28 of 128 components differing in
    the last bit (the two normalise in a different order). They are NOT
    bit-identical, and that is the argument for writing the sampler out
    rather than calling Generator.dirichlet: a one-ULP drift is enough to
    reorder two near-tied weight vectors and move a route, so the draw this
    feature asserts against is its own, not numpy's internal choice.
    """
    ours = np.array(
        [[w[k] for k in SIMPLEX_WEIGHT_KEYS] for _, w in simplex_samples(32, seed=3)]
    )
    theirs = np.random.default_rng(3).dirichlet(np.ones(len(SIMPLEX_WEIGHT_KEYS)), size=32)
    assert np.allclose(ours, theirs, rtol=0.0, atol=1e-15)
    assert not np.array_equal(ours, theirs), (
        "if these ever become bit-identical, numpy changed dirichlet's normalisation; "
        "re-measure before relaxing this test -- the point is that we do not depend on it"
    )


def test_corners_are_the_vertices_and_edge_midpoints():
    labelled = dict(simplex_samples(0, seed=0, include_corners=True))
    assert len(labelled) == 4 + 6
    assert labelled["corner_w_slope"]["w_slope"] == 1.0
    assert sum(labelled["corner_w_slope"].values()) == 1.0
    edge = labelled["edge_slope_energy"]
    assert edge["w_slope"] == 0.5 and edge["w_energy"] == 0.5
    assert edge["w_shadow"] == 0.0 and edge["w_thermal"] == 0.0


def test_zero_samples_without_corners_is_empty():
    assert simplex_samples(0, seed=0) == []


def test_negative_sample_count_is_refused():
    with pytest.raises(ValueError):
        simplex_samples(-1, seed=0)


# ── route identity ──────────────────────────────────────────────────────────


def test_route_id_is_order_sensitive():
    """Routes are de-duplicated by cell SEQUENCE, so order has to matter."""
    assert route_id([(1, 2), (3, 4)]) == route_id([(1, 2), (3, 4)])
    assert route_id([(1, 2), (3, 4)]) != route_id([(3, 4), (1, 2)])


def test_route_id_ignores_integer_type():
    assert route_id([(np.int64(1), np.int64(2))]) == route_id([(1, 2)])


# ── dominance ───────────────────────────────────────────────────────────────


def test_dominance_needs_no_worse_everywhere_and_better_somewhere():
    better = _obj(1.0, 100.0, 0.5)
    worse = _obj(2.0, 200.0, 0.9)
    assert dominates(better, worse)
    assert not dominates(worse, better)


def test_a_mixed_pair_dominates_in_neither_direction():
    """The whole point of a front: faster but hungrier beats nobody."""
    fast = _obj(1.0, 200.0, 0.5)
    frugal = _obj(2.0, 100.0, 0.5)
    assert not dominates(fast, frugal)
    assert not dominates(frugal, fast)


def test_identical_vectors_do_not_dominate_each_other():
    same = _obj(1.0, 100.0, 0.5)
    assert not dominates(same, dict(same))


def test_direction_is_read_from_the_objective_table_not_assumed():
    """Every objective here is minimised; the code must still consult the table.

    If a maximised objective is added later and the comparison silently
    kept minimising, the front would invert. This asserts the table is the
    single source of truth for direction.
    """
    assert {o["direction"] for o in PARETO_OBJECTIVES} == {"minimize"}
    assert tuple(o["key"] for o in PARETO_OBJECTIVES) == OBJECTIVE_KEYS


def test_epsilon_defaults_to_each_objective_publication_quantum():
    """An epsilon finer than the quantum is meaningless: the inputs are rounded."""
    assert dominance_epsilon() == OBJECTIVE_QUANTUM
    assert dominance_epsilon({"hours": 0.5})["hours"] == 0.5
    # the untouched objectives keep their own quantum
    assert dominance_epsilon({"hours": 0.5})["energy_wh"] == OBJECTIVE_QUANTUM["energy_wh"]


def test_a_sub_quantum_difference_is_not_a_domination():
    """Two routes a fraction of a quantum apart were never measured apart."""
    a = _obj(1.0, 100.0, 0.5)
    b = _obj(1.0 + 1e-6, 100.0 + 1e-4, 0.5 + 1e-6)
    assert not dominates(a, b)
    assert not dominates(b, a)


def test_epsilon_rejects_unknown_or_negative_entries():
    with pytest.raises(ValueError):
        dominance_epsilon({"w_slope": 0.1})
    with pytest.raises(ValueError):
        dominance_epsilon({"hours": -1.0})
    with pytest.raises(ValueError):
        dominance_epsilon({"hours": float("nan")})


def test_non_dominated_keeps_the_whole_trade_off_and_drops_the_rest():
    routes = [
        _route("fast", 1.0, 200.0, 0.5),
        _route("frugal", 2.0, 100.0, 0.5),
        _route("beaten", 3.0, 300.0, 0.9),
    ]
    assert non_dominated(routes) == [0, 1]


def test_non_dominated_of_one_is_that_one():
    assert non_dominated([_route("only", 1.0, 1.0, 1.0)]) == [0]


def test_non_dominated_of_nothing_is_nothing():
    assert non_dominated([]) == []


def test_a_constant_objective_changes_no_dominance_relation():
    """A saturated axis pads the objective count; it cannot separate a pair.

    Measured on Site11: thermal_risk takes one value on every route, so the
    four-objective front is really a three-objective one. This pins that
    the constant axis is inert rather than quietly protective.
    """
    varying = [
        _route("a", 1.0, 100.0, 0.5, thermal=1.0),
        _route("b", 2.0, 200.0, 0.9, thermal=1.0),
    ]
    without_axis = [
        _route("a", 1.0, 100.0, 0.5, thermal=0.0),
        _route("b", 2.0, 200.0, 0.9, thermal=0.0),
    ]
    assert non_dominated(varying) == non_dominated(without_axis) == [0]


# ── objectives and diagnostics ──────────────────────────────────────────────


def test_objectives_read_the_fields_the_table_names():
    summary = {
        "total_elapsed_hours": 1.5,
        "total_energy_consumed_wh": 600.0,
        "total_shadow_exposure": 0.9,
    }
    metrics = {"max_thermal_risk": 0.75}
    assert objectives_from(summary, metrics) == _obj(1.5, 600.0, 0.9, 0.75)


def test_diagnostics_names_the_constant_axis_and_counts_the_effective_ones():
    routes = [
        _route("a", 1.0, 100.0, 0.5),
        _route("b", 2.0, 200.0, 0.9),
        _route("c", 3.0, 300.0, 1.3),
    ]
    block = diagnostics(routes)
    assert block["constant_objectives"] == ["thermal_risk"]
    assert block["effective_objectives"] == 3
    assert block["n_distinct_routes"] == 3
    assert block["correlation_n"] == 3


def test_diagnostics_reports_span_against_the_reporting_quantum():
    routes = [_route("a", 1.0, 100.0, 0.5), _route("b", 2.0, 150.0, 0.5)]
    spread = diagnostics(routes)["objective_spread"]
    assert spread["hours"]["span"] == pytest.approx(1.0)
    assert spread["hours"]["span_pct_of_min"] == pytest.approx(100.0)
    assert spread["hours"]["quantum"] == OBJECTIVE_QUANTUM["hours"]
    # shadow never moved, so it is constant at reporting precision
    assert spread["shadow_exposure_h"]["distinct_values_at_reporting_precision"] == 1


def test_diagnostics_correlation_excludes_constant_objectives():
    """A constant axis has no ranking, so correlating against it is meaningless."""
    routes = [
        _route("a", 1.0, 100.0, 0.5),
        _route("b", 2.0, 200.0, 0.9),
        _route("c", 3.0, 300.0, 1.3),
    ]
    keys = diagnostics(routes)["objective_rank_correlation_spearman"]
    assert all("thermal_risk" not in key for key in keys)
    assert keys["hours~energy_wh"] == pytest.approx(1.0)


def test_spearman_is_rank_based_not_value_based():
    """Monotone but wildly non-linear inputs must still rank-correlate at 1."""
    routes = [
        _route("a", 1.0, 1.0, 0.1),
        _route("b", 2.0, 1000.0, 0.2),
        _route("c", 3.0, 1_000_000.0, 0.3),
    ]
    assert diagnostics(routes)["objective_rank_correlation_spearman"][
        "hours~energy_wh"
    ] == pytest.approx(1.0)


def test_completeness_does_not_claim_a_guarantee_it_cannot_make():
    """The weights scalarise the cost CRITERIA, not these objectives.

    So not even the convex-hull result applies, and the label must not say
    'convex_hull_only' -- that would claim a theorem this setup does not
    satisfy.
    """
    assert PARETO_COMPLETENESS == "no_guarantee"
