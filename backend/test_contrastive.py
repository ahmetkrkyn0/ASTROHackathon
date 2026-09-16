"""D4 on synthetic grids: the contract, the identity and the gate order.

Nothing here needs the Site11 cache. What is checked is that the foil's
contract refuses what it says it refuses, that the affine identity really
reproduces the planner's own g-score, that the gate replay agrees with
``_astar_core`` about WHICH rule an edge breaks, and that the counterfactual
arithmetic is what it claims to be.

The gate-order tests are the ones that earn their keep. A replay that checks
the same rules in a different order still returns "this edge is illegal" --
it just returns the wrong REASON, and the whole selling point of the block is
that the reason is the planner's own.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.constants import get_rover
from app.contrastive import (
    CRITERION_WEIGHT_KEY,
    GATE_RULES,
    OUTCOME_CLAMP_BINDS,
    OUTCOME_FOUND_VS_FACT,
    OUTCOME_NO_LEVERAGE,
    OUTCOME_OUTSIDE_BOUNDS,
    WEIGHT_MAX,
    WEIGHT_MIN,
    ContrastInputError,
    EdgeModel,
    criterion_gap,
    flip_threshold_vs_fact,
    l2_minimal_joint_move,
    resolution_report,
    route_terms,
    validate_foil,
)
from app.cost_engine import resolve_weights
from app.pathfinder import astar
from app.traversability import compute_traversability_bool

ROVER = get_rover("lpr_1")


def make_grids(
    rows: int = 24,
    cols: int = 24,
    resolution: float = 5.0,
    elevation: np.ndarray | None = None,
    thermal_c: float = -40.0,
) -> dict:
    """A small, benign grid the planner can cross in any direction."""
    if elevation is None:
        elevation = np.zeros((rows, cols), dtype=np.float64)
    elevation = np.asarray(elevation, dtype=np.float64)
    rows, cols = elevation.shape
    thermal = np.full((rows, cols), thermal_c, dtype=np.float64)
    shadow = np.full((rows, cols), 0.25, dtype=np.float64)
    slope = np.zeros((rows, cols), dtype=np.float64)
    grad_r, grad_c = np.gradient(elevation, resolution)
    slope = np.degrees(np.arctan(np.hypot(grad_r, grad_c)))
    traversable = compute_traversability_bool(slope, thermal, elevation, rover=ROVER)
    return {
        "elevation": elevation,
        "slope": slope,
        "thermal": thermal,
        "shadow_ratio": shadow,
        "traversable": traversable,
        "metadata": {
            "resolution_m": resolution,
            "shape": [rows, cols],
            "cost_criteria": ["slope", "energy", "shadow", "thermal"],
        },
    }


def with_cost(grids: dict, weights: dict) -> dict:
    from app.cost_engine import compute_cost_grid

    out = dict(grids)
    out["cost"] = compute_cost_grid(
        grids["slope"],
        grids["thermal"],
        grids["shadow_ratio"],
        float(grids["metadata"]["resolution_m"]),
        traversable=grids["traversable"],
        weights=weights,
        rover=ROVER,
    )
    meta = dict(grids["metadata"])
    meta["cost_weights"] = dict(weights)
    meta["rover_id"] = ROVER["id"]
    out["metadata"] = meta
    return out


# ── the foil's contract ─────────────────────────────────────────────────────


class TestValidateFoil:
    shape = (24, 24)
    start = (2, 2)
    goal = (2, 5)

    def _ok(self) -> list[list[int]]:
        return [[2, 2], [2, 3], [2, 4], [2, 5]]

    def test_a_clean_foil_is_returned_as_tuples(self):
        out = validate_foil(self._ok(), self.start, self.goal, self.shape, 100)
        assert out == [(2, 2), (2, 3), (2, 4), (2, 5)]

    @pytest.mark.parametrize("foil", [[], [[2, 2]]])
    def test_a_foil_without_an_edge_is_refused(self, foil):
        with pytest.raises(ContrastInputError) as exc:
            validate_foil(foil, self.start, self.goal, self.shape, 100)
        assert exc.value.reason == "foil_too_short"

    def test_the_length_cap_names_the_cap_and_the_grid(self):
        long_foil = [[2, 2]] * 200
        with pytest.raises(ContrastInputError) as exc:
            validate_foil(long_foil, self.start, self.goal, self.shape, 100)
        assert exc.value.reason == "foil_too_long"
        assert exc.value.detail["max_cells"] == 100
        assert exc.value.detail["grid_shape"] == [24, 24]

    def test_out_of_bounds_is_refused_before_any_indexing(self):
        with pytest.raises(ContrastInputError) as exc:
            validate_foil(
                [[2, 2], [-1, 3], [2, 5]], self.start, self.goal, self.shape, 100
            )
        assert exc.value.reason == "foil_out_of_bounds"

    def test_a_mismatched_start_names_both_cells(self):
        """The resolved endpoint goes in the message, not just the caller's.

        A geo start can resolve a cell away from where the caller clicked, and
        that off-by-one is the server's convention; a bare "must share the
        start" would blame the caller for it.
        """
        with pytest.raises(ContrastInputError) as exc:
            validate_foil(
                [[9, 9], [2, 3], [2, 4], [2, 5]], self.start, self.goal, self.shape, 100
            )
        assert exc.value.reason == "foil_start_mismatch"
        assert exc.value.detail["foil_endpoint"] == [9, 9]
        assert exc.value.detail["resolved_endpoint"] == [2, 2]

    def test_a_mismatched_goal_is_refused(self):
        with pytest.raises(ContrastInputError) as exc:
            validate_foil(
                [[2, 2], [2, 3], [2, 4], [2, 9]], self.start, self.goal, self.shape, 100
            )
        assert exc.value.reason == "foil_goal_mismatch"

    def test_a_non_adjacent_step_is_refused(self):
        with pytest.raises(ContrastInputError) as exc:
            validate_foil(
                [[2, 2], [2, 4], [2, 5]], self.start, self.goal, self.shape, 100
            )
        assert exc.value.reason == "foil_not_8_adjacent"
        assert exc.value.detail["index"] == 1

    def test_a_repeated_cell_names_both_indices(self):
        foil = [[2, 2], [2, 3], [2, 2], [2, 3], [2, 4], [2, 5]]
        with pytest.raises(ContrastInputError) as exc:
            validate_foil(foil, self.start, self.goal, self.shape, 100)
        assert exc.value.reason == "foil_repeats_a_cell"
        assert exc.value.detail["first_index"] == 0

    def test_diagonal_steps_are_adjacent(self):
        out = validate_foil(
            [[2, 2], [3, 3], [4, 4]], (2, 2), (4, 4), self.shape, 100
        )
        assert len(out) == 3


# ── the identity ────────────────────────────────────────────────────────────


class TestAffineIdentity:
    """D + sum_k w_k I_k + B must BE the g-score, not approximate it."""

    def _setup(self):
        rng = np.random.default_rng(20260916)
        elevation = rng.normal(0.0, 1.2, size=(24, 24))
        grids = make_grids(elevation=elevation)
        weights = resolve_weights(None, ROVER)
        grids = with_cost(grids, weights)
        result = astar(grids, (2, 2), (20, 20), weights=weights, rover=ROVER)
        assert result["error"] is None
        cells = [(int(r), int(c)) for r, c in result["path_pixels"]]
        model = EdgeModel(grids, ROVER)
        terms = route_terms(grids, ROVER, cells, model)
        return grids, weights, result, terms

    def test_the_decomposition_reproduces_the_planners_g_score(self):
        _, weights, result, terms = self._setup()
        published = result["metrics"]["total_weighted_cost"]
        assert terms.affine_cost(weights) == pytest.approx(published, abs=1e-3)

    def test_the_cell_only_total_is_the_decomposition_without_the_barrier(self):
        _, weights, result, terms = self._setup()
        cells_only = result["metrics"]["total_weighted_cost_cells_only"]
        assert terms.affine_cost(weights) - terms.B == pytest.approx(cells_only, abs=1e-3)

    def test_the_exact_and_affine_forms_agree_while_the_clamp_is_clear(self):
        _, weights, _, terms = self._setup()
        assert terms.clamp_margin(weights) > 1.0
        assert terms.exact_cost(weights) == pytest.approx(terms.affine_cost(weights), rel=1e-12)

    def test_the_cost_is_affine_in_every_weight(self):
        """Two points define the line; a third must lie on it exactly."""
        _, weights, _, terms = self._setup()
        for key in CRITERION_WEIGHT_KEY.values():
            if key not in weights:
                continue
            low, high = dict(weights), dict(weights)
            low[key], high[key] = 0.2, 1.2
            mid = dict(weights)
            mid[key] = 0.7
            predicted = 0.5 * (terms.affine_cost(low) + terms.affine_cost(high))
            assert terms.affine_cost(mid) == pytest.approx(predicted, rel=1e-12)

    def test_the_barrier_does_not_move_with_the_weights(self):
        _, weights, _, terms = self._setup()
        before = terms.B
        heavy = {k: 1.9 for k in weights}
        terms.affine_cost(heavy)
        assert terms.B == before

    def test_an_all_zero_weight_vector_binds_the_clamp(self):
        """PlanWeights permits it, and it is outside the identity's domain."""
        _, weights, _, terms = self._setup()
        zeros = {key: 0.0 for key in weights}
        assert terms.clamp_margin(zeros) < 1.0
        assert terms.clamped_cells(zeros) > 0


# ── the gate replay ─────────────────────────────────────────────────────────


class TestGateReplay:
    def test_the_planners_own_route_trips_nothing(self):
        """A transcription check, and labelled as one.

        This cannot fail unless the replay is mis-transcribed -- it runs the
        same rules from the same functions over the same grid that produced
        the route. It is not evidence that the route is safe.
        """
        rng = np.random.default_rng(0)
        grids = make_grids(elevation=rng.normal(0.0, 1.0, size=(24, 24)))
        weights = resolve_weights(None, ROVER)
        grids = with_cost(grids, weights)
        result = astar(grids, (2, 2), (20, 20), weights=weights, rover=ROVER)
        assert result["error"] is None
        cells = [(int(r), int(c)) for r, c in result["path_pixels"]]
        model = EdgeModel(grids, ROVER)
        terms = route_terms(grids, ROVER, cells, model)
        assert terms.gates["clean"]
        assert terms.gates["n_violations"] == 0

    def test_a_corner_cut_outranks_the_step_slope_it_also_breaks(self):
        """The order is the planner's, and the planner checks the corner FIRST.

        ``_astar_core`` tests the diagonal corner-cut before it computes any
        slope, so an edge guilty of both is a ``diagonal_corner_cut`` to the
        planner. A replay that checked the slopes first would answer
        ``step_slope`` -- the same verdict for the wrong reason.
        """
        elevation = np.zeros((10, 10))
        elevation[3, 3] = 40.0  # a step far over lpr_1's 25 deg limit
        grids = make_grids(elevation=elevation)
        traversable = np.asarray(grids["traversable"], dtype=bool).copy()
        traversable[2, 3] = False
        traversable[3, 2] = False
        traversable[3, 3] = True
        grids["traversable"] = traversable
        model = EdgeModel(grids, ROVER)
        edge = model.edge((2, 2), (3, 3))
        assert edge["violated"] == "diagonal_corner_cut"

    def test_an_untraversable_destination_outranks_everything(self):
        elevation = np.zeros((10, 10))
        elevation[2, 3] = 40.0
        grids = make_grids(elevation=elevation)
        traversable = np.asarray(grids["traversable"], dtype=bool).copy()
        traversable[2, 3] = False
        grids["traversable"] = traversable
        model = EdgeModel(grids, ROVER)
        assert model.edge((2, 2), (2, 3))["violated"] == "destination_not_traversable"

    def test_a_steep_cardinal_step_is_named_step_slope_with_its_exceedance(self):
        elevation = np.zeros((10, 10))
        # 5 m step over a 5 m cell is 45 deg, well over lpr_1's 25 deg.
        elevation[2, 3] = 5.0
        grids = make_grids(elevation=elevation)
        traversable = np.ones((10, 10), dtype=bool)
        grids["traversable"] = traversable
        model = EdgeModel(grids, ROVER)
        edge = model.edge((2, 2), (2, 3))
        assert edge["violated"] == "step_slope"
        assert edge["grid_value"] == pytest.approx(45.0, abs=1e-6)
        assert edge["limit"] == pytest.approx(float(ROVER["slope_max_deg"]))
        assert edge["exceedance"] == pytest.approx(45.0 - float(ROVER["slope_max_deg"]), abs=1e-6)

    def test_the_replay_covers_every_rule_it_advertises(self):
        assert set(GATE_RULES) == {
            "destination_not_traversable",
            "diagonal_corner_cut",
            "nan_elevation",
            "step_slope",
            "lateral_slope",
            "thermal_barrier",
            "slope_barrier",
            "lateral_barrier",
        }

    def test_nan_elevation_is_refused(self):
        elevation = np.zeros((10, 10))
        elevation[2, 3] = np.nan
        grids = make_grids(elevation=elevation)
        grids["traversable"] = np.ones((10, 10), dtype=bool)
        model = EdgeModel(grids, ROVER)
        assert model.edge((2, 2), (2, 3))["violated"] == "nan_elevation"


# ── the counterfactual ──────────────────────────────────────────────────────


class TestCounterfactual:
    def _pair(self):
        rng = np.random.default_rng(0)
        grids = make_grids(elevation=rng.normal(0.0, 1.0, size=(24, 24)))
        weights = resolve_weights(None, ROVER)
        grids = with_cost(grids, weights)
        fact_result = astar(grids, (2, 2), (20, 20), weights=weights, rover=ROVER)
        assert fact_result["error"] is None
        fact_cells = [(int(r), int(c)) for r, c in fact_result["path_pixels"]]
        # w_slope, not w_thermal: this grid's thermal and shadow fields are
        # constant, so only the slope-derived criteria can steer it anywhere
        # and a thermal-heavy vector would hand back the fact itself.
        heavy = dict(weights)
        heavy["w_slope"] = 1.9
        grids_heavy = with_cost(grids, heavy)
        foil_result = astar(grids_heavy, (2, 2), (20, 20), weights=heavy, rover=ROVER)
        assert foil_result["error"] is None
        foil_cells = [(int(r), int(c)) for r, c in foil_result["path_pixels"]]
        assert foil_cells != fact_cells
        model = EdgeModel(grids, ROVER)
        fact = route_terms(grids, ROVER, fact_cells, model)
        foil = route_terms(grids, ROVER, foil_cells, model)
        return grids, weights, fact, foil

    def test_the_gap_decomposition_has_no_residual(self):
        _, weights, fact, foil = self._pair()
        block = criterion_gap(fact, foil, weights)
        rebuilt = (
            block["delta_distance"]
            + block["delta_barrier"]
            + sum(t["delta_weighted"] for t in block["criteria"])
        )
        assert rebuilt == pytest.approx(block["delta_total"], rel=1e-12)
        assert block["delta_total"] == pytest.approx(
            foil.affine_cost(weights) - fact.affine_cost(weights), rel=1e-12
        )

    def test_the_fact_is_never_dearer_than_the_foil(self):
        """A* optimality, restated as an invariant the module depends on."""
        _, weights, fact, foil = self._pair()
        assert foil.affine_cost(weights) >= fact.affine_cost(weights) - 1e-9

    def test_the_threshold_actually_ties_the_two_routes(self):
        _, weights, fact, foil = self._pair()
        for name in fact.criteria:
            entry = flip_threshold_vs_fact(fact, foil, weights, name, 1e-9)
            if entry["threshold"] is None:
                continue
            trial = dict(weights)
            trial[CRITERION_WEIGHT_KEY[name]] = entry["threshold"]
            gap = foil.affine_cost(trial) - fact.affine_cost(trial)
            assert gap == pytest.approx(0.0, abs=1e-6)

    def test_the_direction_follows_the_sign_of_the_integral_difference(self):
        """Getting this backwards sends the scan into a provably empty half."""
        _, weights, fact, foil = self._pair()
        for name in fact.criteria:
            entry = flip_threshold_vs_fact(fact, foil, weights, name, 1e-9)
            if entry["direction"] is None:
                continue
            if entry["delta_integral"] > 0:
                assert entry["direction"] == "decrease"
                assert entry["threshold"] <= entry["current_weight"] + 1e-9
            else:
                assert entry["direction"] == "increase"
                assert entry["threshold"] >= entry["current_weight"] - 1e-9

    def test_a_criterion_with_no_leverage_gets_a_label_not_a_number(self):
        """A bare division here is a ZeroDivisionError or a NaN, and a NaN in
        the response is a 500 rather than an answer."""
        _, weights, fact, _ = self._pair()
        entry = flip_threshold_vs_fact(fact, fact, weights, fact.criteria[0], 1e-9)
        assert entry["outcome"] == OUTCOME_NO_LEVERAGE
        assert entry["threshold"] is None

    def test_an_out_of_bounds_threshold_is_labelled_not_clipped(self):
        _, weights, fact, foil = self._pair()
        entries = [
            flip_threshold_vs_fact(fact, foil, weights, name, 1e-9)
            for name in fact.criteria
        ]
        for entry in entries:
            if entry["threshold"] is None:
                continue
            inside = WEIGHT_MIN <= entry["threshold"] <= WEIGHT_MAX
            assert entry["outcome"] == (
                OUTCOME_FOUND_VS_FACT if inside else OUTCOME_OUTSIDE_BOUNDS
            )

    def test_a_threshold_inside_the_clamp_is_refused_not_published(self):
        """The closed form describes the AFFINE branch, so it is only an answer
        where that branch still applies.

        Verifying the clamp at w0 and then publishing a root somewhere else in
        the box would mean publishing a number produced by a formula that had
        stopped holding at the very weight it points to.
        """
        _, weights, fact, foil = self._pair()
        for name in fact.criteria:
            entry = flip_threshold_vs_fact(fact, foil, weights, name, 1e-9)
            if entry["outcome"] != OUTCOME_FOUND_VS_FACT:
                continue
            # Whenever a threshold IS published, the clamp must be clear there.
            assert entry["clamp_margin_at_threshold"] >= 1.0
            trial = dict(weights)
            trial[CRITERION_WEIGHT_KEY[name]] = entry["threshold"]
            assert fact.clamped_cells(trial) == 0
            assert foil.clamped_cells(trial) == 0

    def test_a_clamped_threshold_is_labelled_clamp_binds(self):
        """Forced: drive the other four weights to zero so the root lands in
        the region where sum_k w_k f_k falls under MIN_CELL_COST."""
        _, weights, fact, foil = self._pair()
        starved = {key: 0.0 for key in weights}
        outcomes = set()
        for name in fact.criteria:
            entry = flip_threshold_vs_fact(fact, foil, starved, name, 1e-12)
            outcomes.add(entry["outcome"])
            if entry["outcome"] == OUTCOME_CLAMP_BINDS:
                assert entry["threshold"] is not None
                assert entry["clamp_margin_at_threshold"] < 1.0
        # With every weight at zero the clamp binds everywhere, so no criterion
        # may come back with a publishable threshold.
        assert OUTCOME_FOUND_VS_FACT not in outcomes

    def test_the_l2_move_ties_the_routes_and_beats_every_single_axis_move(self):
        """The per-criterion thresholds are sections, not minima."""
        _, weights, fact, foil = self._pair()
        move = l2_minimal_joint_move(fact, foil, weights)
        assert move["available"]
        shifted = dict(weights)
        for key, offset in move["move"].items():
            shifted[key] = weights[key] + offset
        assert foil.affine_cost(shifted) - fact.affine_cost(shifted) == pytest.approx(
            0.0, abs=1e-6
        )
        for name in fact.criteria:
            entry = flip_threshold_vs_fact(fact, foil, weights, name, 1e-9)
            if entry["threshold"] is None:
                continue
            single = abs(entry["threshold"] - entry["current_weight"])
            assert move["l2_distance"] <= single + 1e-9


class TestResolutionReport:
    def test_a_gap_below_a_floor_is_not_resolved_there(self):
        report = resolution_report(gap=0.05, model_floor=0.002, terrain_sd=10.0)
        levels = {entry["level"]: entry for entry in report["levels"]}
        assert levels["publication"]["resolved"] is True
        assert levels["model_discretisation"]["resolved"] is True
        assert levels["terrain_ensemble"]["resolved"] is False
        assert report["headline"].startswith("closer_than_the_model_resolves")
        assert report["actionable"] is False

    def test_a_gap_above_every_floor_is_actionable(self):
        report = resolution_report(gap=500.0, model_floor=0.002, terrain_sd=10.0)
        assert report["headline"] == "resolved_at_every_level"
        assert report["actionable"] is True

    def test_an_unmeasured_terrain_floor_is_null_not_zero(self):
        """No clone cache must not silently read as "the terrain is certain"."""
        report = resolution_report(gap=0.05, model_floor=0.002, terrain_sd=None)
        levels = {entry["level"]: entry for entry in report["levels"]}
        assert levels["terrain_ensemble"]["floor"] is None
        assert levels["terrain_ensemble"]["resolved"] is None


def test_the_weight_box_matches_the_api_model():
    """WEIGHT_MIN/MAX restate PlanWeights' rule; they must not drift from it."""
    from app.main import PlanWeights

    with pytest.raises(ValueError):
        PlanWeights(w_slope=WEIGHT_MAX + 0.01)
    with pytest.raises(ValueError):
        PlanWeights(w_slope=WEIGHT_MIN - 0.01)
    assert PlanWeights(w_slope=WEIGHT_MAX).w_slope == WEIGHT_MAX
    assert PlanWeights(w_slope=WEIGHT_MIN).w_slope == WEIGHT_MIN


def test_every_criterion_has_a_weight_key():
    from app.cost_engine import cost_criteria_for

    for name in cost_criteria_for(True):
        assert name in CRITERION_WEIGHT_KEY
    assert math.isfinite(WEIGHT_MAX)
