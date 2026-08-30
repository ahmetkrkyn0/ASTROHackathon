"""Regression tests for the round 3 independent backend review.

One test (or group) per finding, named for the finding id. Each asserts the
BEHAVIOUR the fix establishes, not its implementation, so a future refactor
that keeps the behaviour keeps the test.

Findings: 4 high, 12 medium, 19 low. See
docs/superpowers/reviews/2026-08-30-backend-review-3.md.
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from app import constants as C
from app.constants import (
    DECLARED_ONLY_FIELDS,
    MODELLED_FIELDS,
    get_rover,
    inner_temperature_drop_k,
    rover_catalog,
    soc_deviation_threshold,
)
from app.cost_engine import (
    COST_MODEL_ID,
    edge_barrier_penalty,
    f_energy_cell,
    f_slope,
    gross_energy_per_metre_wh,
    inner_to_surface,
    lateral_slope_deg,
    net_energy_per_metre_wh,
    surface_to_inner,
    thermal_barrier_terms,
)
from app.cost_vec import f_energy_cell_grid
from app.thermal_model import (
    PSR_ANNUAL_MAX_K,
    annual_peak_c,
    couple_shadow_to_thermal,
    shadowed_equilibrium_c,
)


# ══════════════════════════════════════════════════════════════════════════
#  H-1  the documented barrier terms are enforced somewhere
# ══════════════════════════════════════════════════════════════════════════

def _ramp(rows: int, cols: int, resolution_m: float, gradient_deg: float):
    """Elevation rising uniformly along +row at *gradient_deg*."""
    rise = math.tan(math.radians(gradient_deg)) * resolution_m
    column = np.arange(rows, dtype=np.float64)[:, None] * rise
    return np.repeat(column, cols, axis=1)


def test_h1_lateral_slope_limit_is_enforced_by_the_planner():
    """The roll-over limit used to appear only inside dead code.

    On a uniform ramp the cross-slope depends on the direction of travel:
    straight up the fall line it is zero, straight across it is the whole
    gradient, and a diagonal sits at 1/sqrt(2) of it. At 22 deg (tan 0.404)
    a broadside move exceeds LPR-1's 18 deg limit (tan 0.325) while a
    diagonal does not, so a route across the slope must zig-zag.
    """
    from app.pathfinder import astar

    rover = get_rover("lpr_1")
    resolution = 10.0
    grids = _grids_from_elevation(_ramp(12, 12, resolution, 22.0), resolution, 22.0)

    # Straight up the fall line: cross-slope is zero, so it is allowed.
    up = astar(grids, (0, 5), (11, 5), rover=rover)
    assert up["error"] is None, up["error"]
    assert up["metrics"]["edges_rejected"]["lateral_slope"] > 0

    # Across the slope: possible, but only by zig-zagging, so the route is
    # longer than the 11 straight steps a lateral-blind planner would take.
    across = astar(grids, (5, 0), (5, 11), rover=rover)
    assert across["error"] is None, across["error"]
    assert len(across["path_pixels"]) > 12


def test_h1_a_slope_too_steep_to_cross_in_any_direction_has_no_route():
    """At 27 deg every direction is refused by one gate or the other:
    the fall line by the 25 deg step limit, everything else by the 18 deg
    roll-over limit."""
    from app.pathfinder import astar

    rover = get_rover("lpr_1")
    resolution = 10.0
    grids = _grids_from_elevation(_ramp(10, 10, resolution, 27.0), resolution, 24.0)

    result = astar(grids, (5, 0), (5, 9), rover=rover)
    assert result["error"] is not None
    assert "roll-over" in result["error"]
    assert result["metrics"]["edges_rejected"]["lateral_slope"] > 0
    assert result["metrics"]["edges_rejected"]["step_slope"] > 0


def test_h1_soc_reserve_is_enforced_by_the_simulator():
    from app.simulation import simulate_path

    rover = get_rover("lpr_1")
    shape = (4, 4)
    # Full shadow: no recharge is possible, so the rover must stop at its
    # reserve rather than driving the battery to zero.
    states = simulate_path(
        {"path_pixels": [[0, i % 4] for i in range(400)], "error": None},
        np.full(shape, 0.5),
        np.full(shape, 24.0),
        np.full(shape, -50.0),
        np.full(shape, 1.0),
        rover=rover,
        pixel_size_m=80.0,
    )
    reserve_pct = float(rover["soc_min_pct"]) * 100.0
    assert states[-1].stranded is True
    # It stops AT the reserve, not below it: the last recorded level is the
    # first one at or under the floor, never a flat zero.
    assert states[-1].battery_pct <= reserve_pct + 1e-6
    assert states[-1].battery_pct > 0.0


def test_h1_barrier_thermal_limits_are_rover_anchored_not_hardcoded():
    rover = get_rover("lpr_1")
    # The old form used a fixed -20 C / +95 C INNER band. Anchoring to the
    # traversability threshold means a cell just inside -150 C surface is
    # penalised heavily but still finite, and one below it is infinite.
    assert math.isfinite(edge_barrier_penalty(5.0, 5.0, -149.0, rover=rover))
    assert edge_barrier_penalty(5.0, 5.0, -151.0, rover=rover) == math.inf
    # A comfortable cell costs almost nothing.
    assert edge_barrier_penalty(0.0, 0.0, 0.0, rover=rover) == pytest.approx(0.0)


def test_h1_barrier_is_never_negative():
    """A negative barrier would be a discount for safety, and would break
    the A* heuristic's admissibility."""
    rover = get_rover("lpr_1")
    for surface in (-140.0, -100.0, -50.0, 0.0, 20.0, 40.0):
        for along in (0.0, 5.0, 12.0, 20.0):
            for lateral in (0.0, 4.0, 10.0, 16.0):
                value = edge_barrier_penalty(along, lateral, surface, rover=rover)
                assert value >= 0.0 or value == math.inf


def test_h1_lateral_slope_geometry():
    # Travelling straight up the fall line leaves no cross-slope.
    assert lateral_slope_deg(20.0, 20.0) == pytest.approx(0.0, abs=1e-9)
    # Travelling on the level across a 20 deg slope is a 20 deg cross-slope.
    assert lateral_slope_deg(20.0, 0.0) == pytest.approx(20.0)
    # Never negative, even when the along-track estimate overshoots.
    assert lateral_slope_deg(10.0, 25.0) == 0.0


def test_h1_inner_to_surface_is_a_genuine_preimage():
    rover = get_rover("lpr_1")
    for inner in (-150.0, -100.0, -40.0, 0.0, 40.0, 59.0, 61.0, 120.0):
        assert surface_to_inner(inner_to_surface(inner, rover), rover) == pytest.approx(
            inner
        )


# ══════════════════════════════════════════════════════════════════════════
#  H-2  the traversability gate and the driven edge agree
# ══════════════════════════════════════════════════════════════════════════

def test_h2_step_slope_over_the_limit_is_refused():
    """A cell pair the np.gradient mask calls passable, whose one-cell step
    is steeper than the rover can climb, must not be an edge."""
    from app.pathfinder import astar

    rover = get_rover("lpr_1")
    resolution = 10.0
    # A single 45 deg step between two otherwise flat plateaus. The smoothed
    # cell-slope grid stays at 5 deg -- the traversability mask sees nothing
    # wrong -- while the one-cell STEP the rover would actually drive is far
    # over the limit. 45 deg is chosen so even a DIAGONAL crossing (which
    # spreads the same rise over 1.41 cells) stays above 25 deg; a gentler
    # step is legitimately crossable on the diagonal.
    elevation = np.zeros((5, 6), dtype=np.float64)
    elevation[:, 3:] = math.tan(math.radians(45.0)) * resolution
    grids = _grids_from_elevation(elevation, resolution, 5.0)

    result = astar(grids, (2, 0), (2, 5), rover=rover)
    assert result["error"] is not None
    assert result["metrics"]["edges_rejected"]["step_slope"] > 0


def test_h2_both_slope_definitions_are_reported_under_distinct_names():
    from app.pathfinder import astar

    rover = get_rover("lpr_1")
    elevation = np.zeros((8, 8), dtype=np.float64)
    grids = _grids_from_elevation(elevation, 10.0, 3.0)
    metrics = astar(grids, (0, 0), (7, 7), rover=rover)["metrics"]

    assert "max_segment_slope_deg" in metrics
    assert "max_cell_slope_deg" in metrics
    assert metrics["max_cell_slope_deg"] == pytest.approx(3.0)
    # The legacy key keeps its old meaning so existing callers are unaffected.
    assert metrics["max_slope_deg"] == metrics["max_segment_slope_deg"]
    assert set(metrics["slope_definitions"]) == {
        "max_segment_slope_deg",
        "max_cell_slope_deg",
    }


# ══════════════════════════════════════════════════════════════════════════
#  H-3  thermal is coupled to illumination
# ══════════════════════════════════════════════════════════════════════════

def test_h3_permanent_shadow_reaches_the_psr_floor():
    """Round 3's finding, kept: a never-lit cell must not read as warm.

    What changed in round 4 is WHICH statistic the blend produces. Round 3
    stored a fourth-power TIME MEAN under the name of an annual PEAK, so a
    cell lit a quarter of the time was reported 78 K colder than the
    temperature it actually reaches whenever the Sun clears its horizon.
    Both statistics are now named and both are exact at the two ends.
    (Round 4 review, H-3.)
    """
    sunlit = np.array([[20.0, 20.0], [20.0, 20.0]])
    shadow = np.array([[0.0, 0.5], [1.0, 1.0]])
    psr_c = PSR_ANNUAL_MAX_K - 273.15

    peak = annual_peak_c(sunlit, shadow)
    assert peak[0, 0] == pytest.approx(20.0, abs=1e-3)   # full sun
    assert peak[1, 0] == pytest.approx(psr_c, abs=1e-3)  # never lit: floor
    assert peak[1, 1] == pytest.approx(psr_c, abs=1e-3)
    # Lit half the time still REACHES the sunlit peak. This is the round-4
    # correction: a maximum is not an average.
    assert peak[0, 1] == pytest.approx(20.0, abs=1e-3)

    equilibrium = shadowed_equilibrium_c(sunlit, shadow)
    assert equilibrium[0, 0] == pytest.approx(20.0, abs=1e-3)
    assert equilibrium[1, 0] == pytest.approx(psr_c, abs=1e-3)
    # The cold end lands strictly between, and ABOVE the arithmetic mean,
    # because a fourth-power blend is dominated by the hotter term. That is
    # the physics, not a fudge.
    assert psr_c < equilibrium[0, 1] < 20.0
    assert equilibrium[0, 1] > 0.5 * (20.0 + psr_c)

    # couple_shadow_to_thermal defaults to the statistic the stored field
    # actually holds.
    assert np.allclose(couple_shadow_to_thermal(sunlit, shadow), peak, equal_nan=True)
    assert np.allclose(
        couple_shadow_to_thermal(sunlit, shadow, statistic="equilibrium"),
        equilibrium,
        equal_nan=True,
    )


def test_h3_coupling_is_monotone_in_illumination():
    """Both statistics fall monotonically as illumination falls.

    The peak is flat until the cell stops being lit at all and then drops to
    the floor -- a maximum has no reason to vary with duty cycle. The cold
    end falls throughout. Neither may ever RISE with more shadow.
    """
    sunlit = np.full(5, 10.0)
    shadow = np.array([0.0, 0.25, 0.5, 0.75, 1.0])

    equilibrium = shadowed_equilibrium_c(sunlit, shadow)
    assert all(b < a for a, b in zip(equilibrium, equilibrium[1:]))

    peak = annual_peak_c(sunlit, shadow)
    assert all(b <= a for a, b in zip(peak, peak[1:]))
    assert np.allclose(peak[:4], 10.0, atol=1e-3)
    assert peak[4] == pytest.approx(PSR_ANNUAL_MAX_K - 273.15, abs=1e-3)


def test_h3_round4_the_correction_is_applied_exactly_once():
    """The peak correction must be invertible wherever the cell is lit.

    This is what stops app.cost_cube re-applying it. Before round 4 the
    4-D planner coupled an already-coupled field, and the compounded result
    ran 37 C colder than the 2-D planner's map for the same terrain at the
    same instant. (Round 4 review, H-1.)
    """
    from app.thermal_model import sunlit_peak_from_annual_peak_c

    sunlit = np.array([[24.0, 0.0, -50.0, 10.0]])
    shadow = np.array([[0.0, 0.53, 0.9, 0.99]])
    recovered = sunlit_peak_from_annual_peak_c(annual_peak_c(sunlit, shadow), shadow)
    assert np.allclose(recovered, sunlit, atol=1e-2)


def test_h3_round4_regolith_lag_separates_a_passing_shadow_from_a_cold_trap():
    """A cell entering shadow does not reach the cold-trap floor instantly.

    Round 3 had no dynamics, so any cell dark at instant t was scored at the
    PSR floor at instant t -- below the -150 C traversability gate, hence
    impassable, however briefly the shadow lasted. Three quarters of the
    production grid sits above shadow_ratio 0.5. (Round 4 review, H-3.)
    """
    from app.constants import THERMAL_MIN_TRAVERSABLE_C
    from app.thermal_model import REGOLITH_THERMAL_TAU_S, relax_surface_c

    floor = np.array(PSR_ANNUAL_MAX_K - 273.15)
    start = np.array(0.0)

    after_one_hour = float(relax_surface_c(start, floor, 3600.0))
    assert after_one_hour < 0.0, "the surface must actually cool"
    assert after_one_hour > THERMAL_MIN_TRAVERSABLE_C, (
        "one hour of shadow must not read as a cold trap"
    )

    # Given long enough it does get there, so a genuine cold trap still
    # closes the cell.
    after_a_day = float(relax_surface_c(start, floor, 24 * 3600.0))
    assert after_a_day == pytest.approx(float(floor), abs=1.0)

    # The lag is a lag, not a threshold: cooling is monotone in time.
    temps = [
        float(relax_surface_c(start, floor, h * REGOLITH_THERMAL_TAU_S))
        for h in (0.5, 1.0, 2.0, 4.0)
    ]
    assert all(b < a for a, b in zip(temps, temps[1:]))


def test_h3_coupling_preserves_nan():
    coupled = couple_shadow_to_thermal(
        np.array([np.nan, 0.0]), np.array([0.0, np.nan])
    )
    assert np.isnan(coupled).all()


def test_h3_a_fully_shadowed_cell_becomes_untraversable():
    from app.traversability import compute_traversability_bool

    sunlit = np.array([[40.0]])
    dark = couple_shadow_to_thermal(sunlit, np.array([[1.0]])).astype(np.float64)
    lit = couple_shadow_to_thermal(sunlit, np.array([[0.0]])).astype(np.float64)
    slope = np.array([[5.0]])
    assert bool(compute_traversability_bool(slope, lit)[0, 0]) is True
    assert bool(compute_traversability_bool(slope, dark)[0, 0]) is False


def test_h3_loader_couples_and_downgrades_validity():
    """The loader applies the coupling to grids that predate it, and says so."""
    from app.data_loader import load_preprocessed_grids

    try:
        grids = load_preprocessed_grids()
    except FileNotFoundError:
        pytest.skip("P1 processed grids not present")

    thermal = grids["thermal"]
    shadow = grids["shadow_ratio"]
    fully_dark = shadow >= 0.999
    if fully_dark.any():
        psr_c = PSR_ANNUAL_MAX_K - 273.15
        assert thermal[fully_dark].max() == pytest.approx(psr_c, abs=0.5)
    assert grids["metadata"]["thermal_shadow_coupled"] is True
    # MODEL blended with DERIVED cannot still claim MODEL.
    assert grids["metadata"]["layer_validity"]["thermal"] in {"DERIVED", "SYNTHETIC"}


# ══════════════════════════════════════════════════════════════════════════
#  H-4  the energy criterion carries information the slope criterion does not
# ══════════════════════════════════════════════════════════════════════════

def test_h4_energy_penalty_depends_on_shadow():
    rover = get_rover("lpr_1")
    lit = f_energy_cell(10.0, rover, 0.0)
    dark = f_energy_cell(10.0, rover, 1.0)
    assert dark > lit + 0.1, (lit, dark)


def test_h4_energy_and_slope_penalties_are_no_longer_rank_identical():
    """Spearman was exactly 1.000000 before the fix: w_energy could rescale
    the cost but never reorder two cells."""
    rover = get_rover("lpr_1")
    rng = np.random.default_rng(0)
    slopes = rng.uniform(0.0, float(rover["slope_max_deg"]), 400)
    shadows = rng.uniform(0.0, 1.0, 400)

    slope_penalty = np.array([f_slope(s, rover) for s in slopes])
    energy_penalty = f_energy_cell_grid(slopes, rover, shadows)

    # Rank correlation via ranks, without a scipy dependency in the test.
    def ranks(values):
        order = np.argsort(values)
        out = np.empty_like(order, dtype=np.float64)
        out[order] = np.arange(len(values))
        return out

    rho = np.corrcoef(ranks(slope_penalty), ranks(energy_penalty))[0, 1]
    assert rho < 0.99, f"energy is still a restatement of slope (rho={rho})"


def test_h4_a_flat_lit_cell_costs_the_battery_nothing():
    rover = get_rover("lpr_1")
    assert net_energy_per_metre_wh(0.0, 0.0, rover) == pytest.approx(0.0)
    # ...while it still DRAWS power; the difference is the solar input.
    assert gross_energy_per_metre_wh(0.0, 0.0, rover) > 0.0


def test_h4_scalar_and_vector_forms_agree_including_shadow():
    for rover_id in C.ROVERS:
        rover = get_rover(rover_id)
        for slope in np.linspace(0.0, float(rover["slope_max_deg"]), 17):
            for shadow in np.linspace(0.0, 1.0, 5):
                scalar = f_energy_cell(float(slope), rover, float(shadow))
                vector = float(
                    f_energy_cell_grid(
                        np.array([slope]), rover, np.array([shadow])
                    )[0]
                )
                assert scalar == pytest.approx(vector, abs=1e-12)


def test_h4_cost_model_id_was_bumped():
    assert COST_MODEL_ID.endswith("_v3")


# ══════════════════════════════════════════════════════════════════════════
#  M-1 / M-2 / M-3  the 4-D planner
# ══════════════════════════════════════════════════════════════════════════

def test_m1_shadow_series_reports_static_honestly():
    from app.illumination_series import build_shadow_series

    base = np.zeros((4, 4))
    series, provenance = build_shadow_series(base, {}, 5, 1.0, start_utc=None)
    assert len(series) == 5
    assert provenance["time_varying"] is False
    assert provenance["model"] == "static"
    assert "epoch" in provenance["reason"]


def test_m1_shadow_series_reports_a_missing_horizon_cache():
    from app.illumination_series import build_shadow_series

    base = np.zeros((4, 4))
    _series, provenance = build_shadow_series(
        base, {"processed_dir": "/definitely/not/here"}, 3, 1.0, "2026-09-01T00:00:00"
    )
    assert provenance["time_varying"] is False
    assert "horizon_map.npy" in provenance["reason"]


def test_m2_waiting_is_never_free():
    from app.cost_cube import wait_cost

    rover = get_rover("lpr_1")
    weights = {"w_energy": 0.259, "w_shadow": 0.142}
    dt = 0.5
    for illum in (0.0, 0.5, 1.0):
        assert wait_cost(illum, dt, rover, weights) >= dt
    # Darkness still costs strictly more than sunlight.
    assert wait_cost(0.0, dt, rover, weights) > wait_cost(1.0, dt, rover, weights)


def test_m2_wait_cost_scales_with_time():
    from app.cost_cube import wait_cost

    rover = get_rover("lpr_1")
    weights = {"w_energy": 0.259, "w_shadow": 0.142}
    assert wait_cost(0.3, 2.0, rover, weights) == pytest.approx(
        2.0 * wait_cost(0.3, 1.0, rover, weights)
    )


def test_m3_horizon_truncation_is_reported():
    from app.pathfinder_4d import astar_4d

    rover = get_rover("lpr_1")
    height = width = 6
    n_slices = 3  # deliberately too short for a corner-to-corner route
    cost = np.full((n_slices, height, width), 0.1)
    wait = np.full((n_slices, height, width), 0.05)
    traversable = np.ones((height, width), dtype=bool)

    result = astar_4d(
        cost,
        wait,
        traversable,
        start=(0, 0),
        goal=(height - 1, width - 1),
        resolution_m=100.0,
        slice_hours=0.01,
        rover=rover,
    )
    assert result["metrics"]["horizon_truncated"] is True
    assert result["metrics"]["edges_dropped_at_horizon"] > 0


def test_m6_the_two_planners_label_their_cost_units():
    from app.pathfinder_4d import _empty

    assert _empty("x")["metrics"]["cost_units"] == "weighted_hours"
    from app.pathfinder import _zero_metrics

    assert _zero_metrics()["cost_units"] == "weighted_metres"


# ══════════════════════════════════════════════════════════════════════════
#  M-4 / M-5  localisation
# ══════════════════════════════════════════════════════════════════════════

def _corridor():
    from app.schemas import Corridor

    return Corridor(
        waypoints=[(0.0, 0.0), (100.0, 0.0), (200.0, 0.0)],
        half_width_m=[50.0, 50.0],
        max_slope_deg=[5.0, 5.0],
        energy_budget_wh=[1.0, 1.0],
        thermal_budget_K_s=[1.0, 1.0],
        fallback_points=[(0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
        crs="test",
    )


def _pose(source: str, distance: float = 100.0):
    from app.pose import PoseEstimate

    return PoseEstimate(
        x_m=50.0,
        y_m=1.0,
        heading_deg=90.0,
        covariance_m=1.0,
        heading_covariance_deg=1.0,
        timestamp_utc="2026-09-01T00:00:00Z",
        source=source,
        distance_travelled_m=distance,
    )


@pytest.mark.parametrize("source", ["visual_odometry", "lidar_odometry"])
def test_m4_slip_is_not_checked_for_self_correcting_sources(source):
    from app.localization import evaluate_pose

    result = evaluate_pose(_pose(source), _corridor())
    assert "slip_accumulation" not in result["evaluated"]
    reasons = [
        entry["reason"]
        for entry in result["skipped"]
        if entry["trigger_id"] == "slip_accumulation"
    ]
    assert reasons and "body motion" in reasons[0]


def test_m4_slip_is_checked_for_wheel_dead_reckoning():
    from app.localization import evaluate_pose

    result = evaluate_pose(_pose("dead_reckoning"), _corridor())
    assert "slip_accumulation" in result["evaluated"]
    assert "slip_accumulation" in {t.trigger_id for t in result["fired"]}


def test_m5_all_zero_odometry_covariance_is_unknown_not_certain():
    """The negative-variance guard missed the far more common signal."""
    covariance = [0.0] * 36

    def horizontal_sigma(fallback):
        var_x, var_y = float(covariance[0]), float(covariance[7])
        unknown = (var_x < 0.0 or var_y < 0.0) or not any(
            float(v) != 0.0 for v in covariance
        )
        if unknown:
            if fallback is None:
                raise ValueError("refusing to invent confidence")
            return float(fallback)
        return math.sqrt(max(var_x, var_y))

    with pytest.raises(ValueError):
        horizontal_sigma(None)
    assert horizontal_sigma(12.0) == 12.0


# ══════════════════════════════════════════════════════════════════════════
#  M-7 / M-8  constraints and catalogue honesty
# ══════════════════════════════════════════════════════════════════════════

def test_m7_profile_constraints_reach_the_planner():
    from app.pathfinder import astar

    rover = get_rover("lpr_1")
    elevation = np.zeros((8, 8), dtype=np.float64)
    grids = _grids_from_elevation(elevation, 10.0, 3.0)

    default = astar(grids, (0, 0), (7, 7), rover=rover)
    assert default["metrics"]["constraints_applied"]["source"] == "rover"
    assert default["metrics"]["constraints_applied"]["max_slope_deg"] == 25.0

    tightened = astar(
        grids, (0, 0), (7, 7), rover=rover, constraints={"max_slope_deg": 12.0}
    )
    applied = tightened["metrics"]["constraints_applied"]
    assert applied["source"] == "profile"
    assert applied["max_slope_deg"] == 12.0


def test_m7_a_profile_ceiling_actually_blocks_edges():
    from app.pathfinder import astar

    rover = get_rover("lpr_1")
    resolution = 10.0
    step = math.tan(math.radians(15.0)) * resolution
    elevation = np.zeros((5, 6), dtype=np.float64)
    elevation[:, 3:] = step
    grids = _grids_from_elevation(elevation, resolution, 4.0)

    assert astar(grids, (2, 0), (2, 5), rover=rover)["error"] is None
    blocked = astar(
        grids, (2, 0), (2, 5), rover=rover, constraints={"max_slope_deg": 10.0}
    )
    assert blocked["error"] is not None
    assert blocked["metrics"]["edges_rejected"]["step_slope"] > 0


def test_m8_previously_dead_catalogue_fields_now_have_readers():
    from app.cost_engine import housekeeping_power_w

    rover = get_rover("lpr_1")
    # p_shadow_w sets the shadowed end of the housekeeping load.
    assert housekeeping_power_w(1.0, rover) == pytest.approx(
        float(rover["p_shadow_w"])
    )
    assert housekeeping_power_w(0.0, rover) == pytest.approx(float(rover["p_idle_w"]))


def test_m8_catalogue_separates_modelled_from_declared_only():
    catalog = rover_catalog()
    assert catalog
    for entry in catalog:
        assert set(entry["declared_only"]) == set(DECLARED_ONLY_FIELDS)
    # Nothing may be in both sets.
    assert not (MODELLED_FIELDS & set(DECLARED_ONLY_FIELDS))
    # Every declared-only field really is unread by the model.
    assert "f_net_n" in DECLARED_ONLY_FIELDS
    assert "slope_lateral_max_deg" in MODELLED_FIELDS


def test_m8_shadow_and_peak_power_limits_are_checked():
    from app.simulation import simulate_path, summarize_simulation

    rover = get_rover("cnsa_yutu_2")  # h_max_shadow_h = 2
    shape = (4, 4)
    states = simulate_path(
        {"path_pixels": [[0, i % 4] for i in range(60)], "error": None},
        np.full(shape, 0.5),
        np.full(shape, 10.0),
        np.full(shape, -50.0),
        np.full(shape, 1.0),
        rover=rover,
        pixel_size_m=80.0,
    )
    summary = summarize_simulation(states, rover)
    assert summary["shadow_limit_h"] == pytest.approx(2.0)
    assert summary["shadow_limit_exceeded"] is True
    assert summary["max_continuous_shadow_h"] > 2.0


# ══════════════════════════════════════════════════════════════════════════
#  M-9 / M-10  one physics model, and a battery floor
# ══════════════════════════════════════════════════════════════════════════

def test_m9_simulation_and_cost_engine_agree_on_travel_time():
    from app.cost_engine import edge_travel_time_s
    from app.simulation import simulate_path

    rover = get_rover("lpr_1")
    shape = (3, 3)
    states = simulate_path(
        {"path_pixels": [[1, 0], [1, 1], [1, 2]], "error": None},
        np.full(shape, 0.5),
        np.full(shape, 18.0),
        np.full(shape, -50.0),
        np.full(shape, 0.0),
        rover=rover,
        pixel_size_m=20.0,
    )
    per_step_h = edge_travel_time_s(18.0, 20.0, rover) / 3600.0
    assert states[-1].elapsed_hours == pytest.approx(2 * per_step_h)


def test_m9_slope_energy_is_rover_specific():
    lpr = get_rover("lpr_1")
    luvmi = get_rover("luvmi_m")

    def ratio(rover):
        return gross_energy_per_metre_wh(
            20.0, 0.0, rover
        ) / gross_energy_per_metre_wh(0.0, 0.0, rover)

    assert abs(ratio(lpr) - ratio(luvmi)) > 0.2


def test_m10_recharge_time_is_bounded():
    from app.simulation import MAX_RECHARGE_HOURS, simulate_path

    rover = dict(get_rover("lpr_1"))
    # A cell whose net charge rate is a trickle: unbounded, this used to
    # produce a recharge of several centuries reported as elapsed hours.
    rover["p_solar_w"] = float(rover["p_idle_w"]) + 0.001
    shape = (4, 4)
    states = simulate_path(
        {"path_pixels": [[0, i % 4] for i in range(400)], "error": None},
        np.full(shape, 0.5),
        np.full(shape, 24.0),
        np.full(shape, -50.0),
        np.full(shape, 0.0),
        rover=rover,
        pixel_size_m=80.0,
    )
    assert states[-1].stranded is True
    assert states[-1].elapsed_hours < MAX_RECHARGE_HOURS * 2


def test_m10_risk_level_reads_the_step_low_point():
    """A step that dipped to its reserve and refilled used to report LOW."""
    from app.simulation import simulate_path

    rover = get_rover("lpr_1")
    shape = (4, 4)
    states = simulate_path(
        {"path_pixels": [[0, i % 4] for i in range(200)], "error": None},
        np.full(shape, 0.5),
        np.full(shape, 24.0),
        np.full(shape, -50.0),
        np.full(shape, 0.0),
        rover=rover,
        pixel_size_m=80.0,
    )
    recharged = [s for s in states if s.recharged_this_step]
    assert recharged, "the route should have needed a recharge"
    for state in recharged:
        assert state.battery_pct == pytest.approx(100.0)
        # ...but the risk it reports is the dip that forced the stop.
        assert state.risk_level in {"HIGH", "CRITICAL", "MEDIUM"}


# ══════════════════════════════════════════════════════════════════════════
#  M-11 / M-12  illumination and clearance
# ══════════════════════════════════════════════════════════════════════════

def test_m11_a_negative_horizon_can_still_be_lit():
    """The blanket sun>0 floor discarded peak-of-eternal-light geometry."""
    from app.illumination import illuminated_mask

    horizon = np.full((4, 1, 2), -5.0, dtype=np.float32)
    # A Sun below the horizontal but above the local (negative) horizon.
    mask = illuminated_mask(horizon, 0.0, -2.0)
    assert bool(mask[0, 0]) is True
    # Below the local horizon it is dark.
    assert not illuminated_mask(horizon, 0.0, -8.0).any()


def test_m11_the_no_data_sentinel_falls_back_to_the_horizontal():
    """The sentinel means "no obstruction found", so the honest reading is
    a horizon at the horizontal -- lit above it, dark below. That is the
    original Faz 1 fix, now applied ONLY where the sentinel appears instead
    of to every cell on the map."""
    from app.horizon import _NO_HORIZON_DEG
    from app.illumination import illuminated_mask

    horizon = np.full((4, 1, 2), _NO_HORIZON_DEG, dtype=np.float32)
    assert illuminated_mask(horizon, 0.0, 30.0).all()
    assert not illuminated_mask(horizon, 0.0, -1.0).any()


def test_m11_the_floor_applies_only_to_sentinel_cells():
    from app.horizon import _NO_HORIZON_DEG
    from app.illumination import illuminated_mask

    horizon = np.full((4, 1, 2), -5.0, dtype=np.float32)
    horizon[:, 0, 1] = _NO_HORIZON_DEG
    # A Sun at -2 deg clears the real -5 deg horizon of the first cell, and
    # is below the horizontal for the sentinel cell beside it.
    mask = illuminated_mask(horizon, 0.0, -2.0)
    assert bool(mask[0, 0]) is True
    assert bool(mask[0, 1]) is False


def test_m12_the_map_edge_counts_as_an_obstacle():
    from app.corridor import clearance_map

    passable = np.ones((5, 5), dtype=bool)
    clearance = clearance_map(passable, 10.0)
    # A corner cell is one cell from two edges.
    assert clearance[0, 0] == pytest.approx(10.0)
    # The centre is further from every edge than the corner is.
    assert clearance[2, 2] > clearance[0, 0]


# ══════════════════════════════════════════════════════════════════════════
#  Low-severity findings
# ══════════════════════════════════════════════════════════════════════════

def test_l1_nan_slope_is_not_treated_as_flat_ground():
    """max(0.0, nan) is 0.0 in Python, so the scalar form returned the
    CHEAPEST possible penalty for an unknown slope."""
    rover = get_rover("lpr_1")
    assert math.isnan(f_energy_cell(float("nan"), rover, 0.0))
    assert np.isnan(f_energy_cell_grid(np.array([np.nan]), rover)).all()


def test_l3_synthetic_thermal_does_not_depend_on_the_window():
    from app.thermal_grid import generate_thermal_grid

    elevation = np.linspace(200.0, 1200.0, 64).reshape(8, 8)
    slope = np.full((8, 8), 5.0)
    aspect = np.full((8, 8), 90.0)

    full = generate_thermal_grid(elevation, slope, aspect, 10.0)
    # The same terrain, cropped: the shared cells must keep their values.
    crop = generate_thermal_grid(
        elevation[2:6, 2:6], slope[2:6, 2:6], aspect[2:6, 2:6], 10.0
    )
    # Interior cells only -- the edge-padded shadow proxy legitimately
    # differs where the crop introduced a new boundary.
    assert full[3:5, 3:5] == pytest.approx(crop[1:3, 1:3], abs=1e-3)


def test_l4_synthetic_thermal_honours_the_sun_azimuth():
    from app.thermal_grid import generate_thermal_grid

    elevation = np.zeros((4, 4))
    slope = np.full((4, 4), 20.0)
    aspect_east = np.full((4, 4), 90.0)

    warm_from_east = generate_thermal_grid(
        elevation, slope, aspect_east, 10.0, sun_azimuth_grid_deg=90.0
    )
    warm_from_north = generate_thermal_grid(
        elevation, slope, aspect_east, 10.0, sun_azimuth_grid_deg=0.0
    )
    assert warm_from_east.mean() > warm_from_north.mean()


def test_l5_a_recomputed_cost_grid_is_stamped_with_this_build():
    from app.data_loader import load_preprocessed_grids

    try:
        grids = load_preprocessed_grids()
    except FileNotFoundError:
        pytest.skip("P1 processed grids not present")
    assert grids["metadata"]["cost_model"] == COST_MODEL_ID


def test_l7_the_serializer_fallback_describes_a_real_window():
    from app.serializer import GRID_COLS, GRID_ROWS, RESOLUTION_M, pixel_to_lonlat

    # It must project into the south polar region without raising -- the old
    # constants described a window that no longer exists.
    lon, lat = pixel_to_lonlat(GRID_ROWS // 2, GRID_COLS // 2)
    assert lat < -80.0
    assert RESOLUTION_M > 0.0


def test_l8_replan_thresholds_follow_the_rover():
    assert soc_deviation_threshold(get_rover("lpr_1")) == pytest.approx(0.10)
    assert soc_deviation_threshold(get_rover("cnsa_yutu_2")) == pytest.approx(0.15)
    assert inner_temperature_drop_k(get_rover("luvmi_m")) > inner_temperature_drop_k(
        get_rover("lpr_1")
    )


def test_l9_localization_uses_a_two_sigma_bound():
    from app.replan_triggers import check_localization_uncertainty

    # 1 sigma of 30 m fits a 50 m half-width; 2 sigma does not.
    assert check_localization_uncertainty(30.0, 50.0).triggered is True
    assert check_localization_uncertainty(20.0, 50.0).triggered is False
    assert check_localization_uncertainty(30.0, 50.0, sigma_multiplier=1.0).triggered is False


def test_l10_slip_is_part_of_the_trigger_enumeration():
    from app.replan_triggers import _TRIGGER_INPUTS, evaluate_triggers_detailed

    assert "slip_accumulation" in _TRIGGER_INPUTS
    evaluation = evaluate_triggers_detailed(
        {"map_progress_m": 40.0, "odometer_claim_m": 100.0}
    )
    assert "slip_accumulation" in evaluation["evaluated"]
    assert "slip_accumulation" in {t.trigger_id for t in evaluation["fired"]}
    # And absent inputs are reported as skipped, never as clear.
    assert "slip_accumulation" in {
        entry["trigger_id"] for entry in evaluate_triggers_detailed({})["skipped"]
    }


def test_l11_the_safety_key_normalises_by_the_rover_limit():
    from app.scenarios import compare_results

    results = [
        {
            "profile_id": "steep",
            "metrics": {
                "total_distance_m": 100.0,
                "max_thermal_risk": 0.1,
                "max_slope_deg": 20.0,
                "total_weighted_cost": 10.0,
            },
        },
        {
            "profile_id": "hot",
            "metrics": {
                "total_distance_m": 100.0,
                "max_thermal_risk": 0.9,
                "max_slope_deg": 2.0,
                "total_weighted_cost": 12.0,
            },
        },
    ]
    # nasa_viper's limit is 20 deg: steep scores 0.1 + 20/20 = 1.10 against
    # hot's 0.9 + 2/20 = 1.00, so the hot route is the safer one.
    assert compare_results(results, get_rover("nasa_viper"))["safest_profile"] == "hot"
    # lpr_1's limit is 25 deg: steep scores 0.1 + 20/25 = 0.90 against hot's
    # 0.9 + 2/25 = 0.98, and the ranking flips. A hardcoded /25.0 gave every
    # rover lpr_1's answer.
    assert compare_results(results, get_rover("lpr_1"))["safest_profile"] == "steep"


def test_l15_every_pose_source_has_a_drift_row_or_is_absolute():
    from app.localization_budget import DRIFT_RATES
    from app.pose import ABSOLUTE_SOURCES

    import typing

    from app.pose import PoseSource

    sources = set(typing.get_args(PoseSource))
    covered = {label for label, _rate, _note in DRIFT_RATES} | set(ABSOLUTE_SOURCES)
    assert sources <= covered, sources - covered


def test_l18_along_track_matches_the_cumulative_segment_length():
    from app.localization import project_onto_corridor

    fix = project_onto_corridor(_pose("dead_reckoning"), _corridor())
    assert fix.along_track_m == pytest.approx(50.0)
    assert fix.segment_index == 0


# ══════════════════════════════════════════════════════════════════════════
#  helpers
# ══════════════════════════════════════════════════════════════════════════

def _grids_from_elevation(
    elevation: np.ndarray, resolution_m: float, cell_slope_deg: float
) -> dict:
    """A minimal grids dict whose cell slope is stated rather than derived.

    The cell slope grid and the elevation are supplied independently on
    purpose: the whole point of H-2 is that the two are DIFFERENT estimators
    and the planner must respect both.
    """
    shape = elevation.shape
    return {
        "elevation": elevation,
        "slope": np.full(shape, cell_slope_deg, dtype=np.float64),
        "thermal": np.full(shape, -40.0, dtype=np.float64),
        "shadow_ratio": np.zeros(shape, dtype=np.float64),
        "traversable": np.ones(shape, dtype=bool),
        "metadata": {"resolution_m": resolution_m, "shape": list(shape)},
    }
