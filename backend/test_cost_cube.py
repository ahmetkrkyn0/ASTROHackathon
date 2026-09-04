"""Time-sliced cost cube tests."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.constants import get_rover
from app.cost_cube import build_cost_cube, coarsen_grid, coarsen_traversable

SHAPE = (8, 8)


def _base_grids() -> dict:
    return {
        "slope": np.full(SHAPE, 4.0),
        # The stored field is the SUNLIT PEAK; the illumination-dependent
        # statistics are derived from it exactly once. (Round 4 review, H-1.)
        "thermal": np.full(SHAPE, -60.0),
        "shadow_ratio": np.zeros(SHAPE),
        "traversable": np.ones(SHAPE, dtype=bool),
        "metadata": {
            "resolution_m": 80.0,
            "shape": list(SHAPE),
            "thermal_field": "sunlit_peak",
        },
    }


def _reference_states(grids, series, coarsen=1, slice_hours=1.0):
    """Per-slice surface temperature, integrated the way the builder does.

    The builder no longer recomputes an instantaneous coupling per slice --
    it INTEGRATES a first-order lag from the long-run equilibrium, because a
    cell crossing into shadow does not reach the cold-trap floor within one
    slice. Mirroring that here keeps the cube checked against an independent
    implementation of the same physics rather than against a constant.
    (Round 4 review, H-1 and H-3.)
    """
    from app.thermal_model import (
        REGOLITH_THERMAL_TAU_S,
        relax_surface_c,
        shadowed_equilibrium_c,
    )

    sunlit = coarsen_grid(np.asarray(grids["thermal"], float), coarsen)
    base_shadow = coarsen_grid(
        np.asarray(grids.get("shadow_ratio", series[0]), float), coarsen
    )
    state = np.asarray(shadowed_equilibrium_c(sunlit, base_shadow), dtype=np.float64)
    dt_s = slice_hours * 3600.0
    out = []
    for snapshot in series:
        shadow_c = coarsen_grid(np.asarray(snapshot, float), coarsen)
        target = np.asarray(shadowed_equilibrium_c(sunlit, shadow_c), dtype=np.float64)
        state = np.asarray(
            relax_surface_c(state, target, dt_s, REGOLITH_THERMAL_TAU_S),
            dtype=np.float64,
        )
        out.append(state.copy())
    return out


def test_coarsen_grid_averages_blocks():
    grid = np.arange(16, dtype=np.float64).reshape(4, 4)
    out = coarsen_grid(grid, factor=2)
    assert out.shape == (2, 2)
    assert out[0, 0] == pytest.approx(np.mean([0, 1, 4, 5]))


def test_coarsen_grid_factor_one_is_identity():
    grid = np.arange(9, dtype=np.float64).reshape(3, 3)
    assert np.array_equal(coarsen_grid(grid, factor=1), grid)


def test_coarsen_grid_rejects_non_divisible_shape():
    with pytest.raises(ValueError):
        coarsen_grid(np.zeros((5, 4)), factor=2)


def test_coarsen_traversable_is_conservative():
    """A coarse cell is passable only if every fine cell inside it is."""
    fine = np.ones((4, 4), dtype=bool)
    fine[0, 0] = False
    out = coarsen_traversable(fine, factor=2)
    assert out.shape == (2, 2)
    assert not out[0, 0]
    assert out[1, 1]


def test_cost_cube_has_one_slice_per_shadow_series_entry():
    series = [np.full(SHAPE, r) for r in (0.0, 0.5, 1.0)]
    cube = build_cost_cube(_base_grids(), series, get_rover())
    assert cube.shape == (3, *SHAPE)


def test_cost_cube_is_monotonic_in_shadow():
    """More shadow at a given cell must never make it cheaper."""
    series = [np.full(SHAPE, r) for r in (0.0, 0.5, 1.0)]
    cube = build_cost_cube(_base_grids(), series, get_rover())
    assert cube[0, 4, 4] < cube[1, 4, 4] < cube[2, 4, 4]


def test_cost_cube_applies_coarsening():
    series = [np.zeros(SHAPE), np.ones(SHAPE)]
    cube = build_cost_cube(_base_grids(), series, get_rover(), coarsen=2)
    assert cube.shape == (2, 4, 4)


def test_cost_cube_rejects_empty_series():
    with pytest.raises(ValueError):
        build_cost_cube(_base_grids(), [], get_rover())


def test_cost_cube_rejects_shape_mismatch():
    with pytest.raises(ValueError):
        build_cost_cube(_base_grids(), [np.zeros((4, 4))], get_rover())


from app.cost_cube import build_wait_cost_cube, wait_cost
from app.cost_engine import resolve_weights


def test_waiting_in_full_sun_costs_only_time():
    """Solar input exceeds idle+heater draw -> no energy penalty."""
    rover = get_rover()
    weights = resolve_weights(None, rover)
    # Waiting in full sun costs nothing on the ENERGY or SHADOW axes -- but
    # it still costs the time it takes. A free WAIT gave the planner no
    # reason to prefer arriving sooner and made "go now" and "wait, then go"
    # tie on cost. (Round 3 review, M-2.)
    assert wait_cost(1.0, 1.0, rover, weights) == pytest.approx(1.0, abs=1e-12)
    assert wait_cost(1.0, 2.0, rover, weights) == pytest.approx(2.0, abs=1e-12)


def test_waiting_in_full_shadow_costs_more_than_in_sun():
    rover = get_rover()
    weights = resolve_weights(None, rover)
    assert wait_cost(0.0, 1.0, rover, weights) > wait_cost(1.0, 1.0, rover, weights)


def test_wait_cost_grows_with_duration():
    rover = get_rover()
    weights = resolve_weights(None, rover)
    assert wait_cost(0.0, 2.0, rover, weights) > wait_cost(0.0, 1.0, rover, weights)


def test_wait_cost_is_never_negative():
    rover = get_rover()
    weights = resolve_weights(None, rover)
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert wait_cost(frac, 1.0, rover, weights) >= 0.0


def test_wait_cost_cube_shape_matches_series_and_coarsening():
    series = [np.ones(SHAPE), np.zeros(SHAPE)]
    cube = build_wait_cost_cube(series, get_rover(), dt_hours=1.0, coarsen=2)
    assert cube.shape == (2, 4, 4)
    assert (cube[1] > cube[0]).all()


# ── Review finding M3: time-invariant layers must not be recomputed ───────────


def _coupled(thermal, shadow):
    """The per-slice thermal field build_cost_cube now derives.

    A cell that is dark in THIS slice is colder in this slice: the cube
    recomputes surface temperature from each snapshot's illumination rather
    than freezing the annual field, which is what makes a WAIT edge able to
    unlock a route instead of only making one marginally cheaper.
    (Round 3 review, H-3 / M-2.)
    """
    from app.thermal_model import couple_shadow_to_thermal

    return np.asarray(
        couple_shadow_to_thermal(
            np.asarray(thermal, dtype=np.float64),
            np.asarray(shadow, dtype=np.float64),
        ),
        dtype=np.float64,
    )


def _passable(traversable, coupled_thermal):
    """The slice's own traversable mask.

    This used to AND the base mask with ``coupled_thermal >= -150 C`` -- the
    regolith skin temperature at that instant. On the production grid that
    gate closed every cell within ~1.3 h of darkness and made the whole map
    impassable for the entire lunar night, although the rover catalogue says
    LPR-1 survives 50 h of shadow. Whether the rover can be in a dark cell
    is now decided by the ROVER'S envelope (battery and shadow endurance,
    carried in the planner's state), not by the ground's skin temperature;
    the static cold-trap gate lives in the base ``traversable`` mask.
    """
    del coupled_thermal
    return np.asarray(traversable, dtype=bool)


def test_cost_cube_matches_a_per_slice_reference():
    """The optimised builder must agree with the naive one, bit for bit."""
    from app.costmap import PlanContext, default_cost_map

    grids = _base_grids()
    rover = get_rover()
    series = [np.full(SHAPE, r) for r in (0.0, 0.35, 0.8, 1.0)]

    cube = build_cost_cube(grids, series, rover, slice_hours=1.0)
    states = _reference_states(grids, series, slice_hours=1.0)

    cost_map = default_cost_map(rover)
    for index, snapshot in enumerate(series):
        reference = cost_map.total(
            PlanContext(
                slope=np.asarray(grids["slope"], dtype=np.float64),
                thermal=states[index],
                shadow_ratio=np.asarray(snapshot, dtype=np.float64),
                traversable=_passable(grids["traversable"], states[index]),
                resolution_m=80.0,
                rover=rover,
            )
        )
        assert np.allclose(cube[index], reference, equal_nan=True)


def test_cost_cube_matches_reference_with_coarsening_and_blocked_cells():
    from app.costmap import PlanContext, default_cost_map

    grids = _base_grids()
    traversable = np.ones(SHAPE, dtype=bool)
    traversable[0, 0] = False          # kills coarse block (0, 0)
    grids["traversable"] = traversable
    slope = np.asarray(grids["slope"], dtype=np.float64).copy()
    slope[4, 4] = 30.0                 # non-uniform: exercises how="max"
    grids["slope"] = slope

    rover = get_rover()
    series = [np.full(SHAPE, 0.2), np.full(SHAPE, 0.9)]
    cube = build_cost_cube(grids, series, rover, coarsen=2, slice_hours=1.0)
    states = _reference_states(grids, series, coarsen=2, slice_hours=1.0)

    from app.cost_cube import coarsen_grid, coarsen_traversable

    cost_map = default_cost_map(rover)
    for index, snapshot in enumerate(series):
        reference = cost_map.total(
            PlanContext(
                slope=coarsen_grid(slope, 2, how="max"),
                thermal=states[index],
                shadow_ratio=coarsen_grid(np.asarray(snapshot, float), 2),
                traversable=_passable(
                    coarsen_traversable(traversable, 2), states[index]
                ),
                resolution_m=160.0,
                rover=rover,
            )
        )
        assert np.allclose(cube[index], reference, equal_nan=True)
    assert np.isinf(cube[0, 0, 0])     # blocked block stays impassable


def test_cost_cube_evaluates_every_layer_per_slice_and_stays_fast():
    """Every layer is evaluated per slice now, and that is not a regression.

    The old builder evaluated "invariant" layers once, on the premise that
    only the shadow layer varies with time. That premise died when thermal
    became a function of illumination (round 3, H-3): freezing the thermal
    layer at its annual value hid the very state change the 4-D planner
    exists to reason about, and made a WAIT edge unable to unlock anything.

    The optimisation existed because np.vectorize made each layer a Python
    loop (~22 s for a 168-slice cube). Review #8 replaced those with true
    array forms, so the reason is gone: this asserts the cost is still small
    at production scale rather than asserting the shortcut.
    """
    import time

    shape = (128, 128)
    grids = {
        "slope": np.full(shape, 5.0),
        "thermal": np.full(shape, -60.0),
        "traversable": np.ones(shape, dtype=bool),
        "metadata": {"resolution_m": 20.0, "shape": list(shape)},
    }
    series = [np.full(shape, 0.3)] * 168

    started = time.perf_counter()
    cube = build_cost_cube(grids, series, get_rover())
    elapsed = time.perf_counter() - started

    assert cube.shape == (168, *shape)
    assert elapsed < 5.0, f"168-slice cube took {elapsed:.1f} s"


def test_wait_cost_cube_matches_scalar_wait_cost():
    """The vectorised/cached cube must agree with the scalar formula."""
    rover = get_rover()
    weights = resolve_weights(None, rover)
    series = [
        np.array([[0.0, 0.25], [0.5, 1.0]]),
        np.array([[1.0, 0.75], [0.1, 0.0]]),
    ]
    cube = build_wait_cost_cube(series, rover, dt_hours=1.5)
    for t, snapshot in enumerate(series):
        for r in range(2):
            for c in range(2):
                expected = wait_cost(snapshot[r, c], 1.5, rover, weights)
                assert cube[t, r, c] == pytest.approx(expected)


def test_wait_cost_cube_evaluates_each_distinct_value_once():
    """Cost scales with DISTINCT illumination values, not with cube size.

    A 168-slice cube used to evaluate wait_cost per cell per slice (~5 s);
    illumination grids repeat heavily, so solving each distinct value once
    makes the slice count almost free. (Faz 3 review, M3.)
    """
    import app.cost_cube as module

    calls = {"n": 0}
    original = module.wait_cost

    def counting(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    module.wait_cost = counting
    try:
        # 40 slices x 15625 cells, but only 3 distinct illumination values.
        grid = np.full((125, 125), 0.3)
        grid[:10] = 0.8
        grid[10:20] = 0.0
        module.build_wait_cost_cube([grid] * 40, get_rover(), dt_hours=1.0)
    finally:
        module.wait_cost = original

    assert calls["n"] == 3, f"wait_cost ran {calls['n']}x for 3 distinct values"


def test_cost_cube_honours_shadow_reading_layers_regardless_of_name():
    """A layer that reads shadow_ratio must stay time-varying even if it is
    not called "shadow". Keying the optimisation off the layer name froze
    such a layer at one value and produced a constant cube. (Faz 3 review, M3.)
    """
    import app.cost_cube as module
    from app.costmap import CostMap

    class _ShadowReadingLayer:
        name = "custom_illumination"
        validity = "MODEL"
        weight = 1.0

        def contribution(self, ctx):
            return np.asarray(ctx.shadow_ratio, dtype=np.float64)

    original = module.default_cost_map
    module.default_cost_map = lambda *a, **k: CostMap([_ShadowReadingLayer()])
    try:
        # couple_thermal=False isolates what this test is about: whether the
        # builder re-evaluates a shadow-reading layer per slice. With the
        # coupling on, a fully shadowed cell is impassable on thermal
        # grounds and the layer's value never gets to be compared.
        cube = module.build_cost_cube(
            _base_grids(),
            [np.zeros(SHAPE), np.ones(SHAPE)],
            get_rover(),
            couple_thermal=False,
        )
        # Long enough in the dark for the surface to actually get there.
        coupled = module.build_cost_cube(
            _base_grids(),
            [np.zeros(SHAPE)] + [np.ones(SHAPE)] * 12,
            get_rover(),
            slice_hours=1.0,
        )
    finally:
        module.default_cost_map = original

    assert cube[1, 0, 0] > cube[0, 0, 0], "cube must vary with shadow"
    assert cube[1, 0, 0] == pytest.approx(1.0)
    # With the dynamics on, sustained shadow makes a cell steadily MORE
    # EXPENSIVE as the surface cools -- but never impassable on its own.
    # Round 4 closed the cell once the skin fell below -150 C, which on the
    # production grid closed the entire map for the whole lunar night
    # (measured: 0 percent passable 2.5 h into 2026-09-07). Whether the
    # rover may be there is the rover's envelope to decide, in the planner's
    # state; the ground's skin temperature is a cost, not a veto.
    assert np.isfinite(coupled[0, 0, 0])
    assert np.isfinite(coupled[1, 0, 0]), "one slice of shadow is not a cold trap"
    assert np.isfinite(coupled[-1, 0, 0]), "sustained shadow must not close the cell"
    # (This test swaps the cost map for a single shadow-reading layer, so
    # the cooling itself is invisible here; the real map's rise is asserted
    # in test_lunar_night_leaves_statically_passable_cells_finite.)
    dark = [coupled[i, 0, 0] for i in range(1, len(coupled))]
    assert dark == sorted(dark), "cost must never fall as the surface cools"


def test_lunar_night_leaves_statically_passable_cells_finite():
    """The user-facing failure: a 4-D plan at a night epoch found the whole
    cube infinite. A cell the static mask calls passable must stay finite
    however long it sits in full shadow; darkness is priced, not banned."""
    grids = _base_grids()
    hours_of_night = 48
    series = [np.ones(SHAPE)] * hours_of_night
    cube = build_cost_cube(grids, series, get_rover(), slice_hours=1.0)
    assert np.isfinite(cube).all()
    assert cube[-1, 0, 0] > cube[0, 0, 0]


# ── Battery physics shared by the planner and the simulator ──────────────────


def test_wait_battery_drain_charges_in_sun_and_drains_in_shadow():
    from app.cost_engine import wait_battery_drain_wh

    rover = get_rover()
    in_sun = wait_battery_drain_wh(0.0, 1.0, rover)
    in_shadow = wait_battery_drain_wh(1.0, 1.0, rover)
    assert in_sun == pytest.approx(rover["p_idle_w"] - rover["p_solar_w"])
    assert in_sun < 0.0, "sunlight charges: a negative drain"
    assert in_shadow == pytest.approx(rover["p_shadow_w"])


def test_move_battery_drain_is_gross_draw_minus_solar_income():
    from app.cost_engine import (
        edge_travel_time_s,
        gross_energy_per_metre_wh,
        move_battery_drain_wh,
    )

    rover = get_rover()
    theta, distance = 3.0, 80.0
    hours = edge_travel_time_s(theta, distance, rover) / 3600.0
    dark = move_battery_drain_wh(theta, distance, 1.0, rover)
    lit = move_battery_drain_wh(theta, distance, 0.0, rover)
    assert dark == pytest.approx(gross_energy_per_metre_wh(theta, 1.0, rover) * distance)
    assert lit == pytest.approx(
        gross_energy_per_metre_wh(theta, 0.0, rover) * distance
        - rover["p_solar_w"] * hours
    )
    assert lit < dark



# ── Review finding C1: the time axis must advance in real hours ───────────────


def test_auto_slice_hours_matches_a_typical_edge_traversal():
    """A slice should be about as long as crossing one cell takes.

    With slice_hours=1.0 every move on any realistic grid rounded up to
    exactly one slice, so arrival_slice counted STEPS, not hours, and the
    slope-dependent travel time was invisible. (Faz 3 review, C1.)
    """
    from app.cost_cube import auto_slice_hours

    rover = get_rover()
    slope = np.full((8, 8), 19.0)
    traversable = np.ones((8, 8), dtype=bool)

    hours = auto_slice_hours(slope, traversable, resolution_m=20.0, rover=rover)

    from app.cost_engine import edge_travel_time_s

    expected = edge_travel_time_s(19.0, 20.0, rover) / 3600.0
    assert hours == pytest.approx(expected, rel=0.1)


def test_auto_slice_hours_scales_with_cell_size():
    from app.cost_cube import auto_slice_hours

    rover = get_rover()
    slope = np.full((8, 8), 10.0)
    traversable = np.ones((8, 8), dtype=bool)

    small = auto_slice_hours(slope, traversable, resolution_m=20.0, rover=rover)
    large = auto_slice_hours(slope, traversable, resolution_m=80.0, rover=rover)
    assert large == pytest.approx(small * 4, rel=0.05)


def test_auto_slice_hours_ignores_impassable_cells():
    """Blocked cells often carry extreme slopes; they must not set the clock."""
    from app.cost_cube import auto_slice_hours

    rover = get_rover()
    slope = np.full((8, 8), 10.0)
    slope[0, :] = 89.0                       # near-vertical, and blocked
    traversable = np.ones((8, 8), dtype=bool)
    traversable[0, :] = False

    hours = auto_slice_hours(slope, traversable, resolution_m=20.0, rover=rover)
    reference = auto_slice_hours(
        np.full((8, 8), 10.0), np.ones((8, 8), dtype=bool), 20.0, rover
    )
    assert hours == pytest.approx(reference)


def test_auto_slice_hours_is_positive_when_nothing_is_traversable():
    from app.cost_cube import auto_slice_hours

    rover = get_rover()
    hours = auto_slice_hours(
        np.full((4, 4), 10.0), np.zeros((4, 4), dtype=bool), 20.0, rover
    )
    assert hours > 0.0
    assert math.isfinite(hours)



# ── C3: the auto slice follows the slip-lengthened crossing ─────────────────


def test_auto_slice_hours_grows_with_the_profiles_slip():
    """The slice is one cell crossing at the median slope; that crossing now
    includes the rover's slip, so a slip-free view of the same profile
    yields a shorter slice by exactly 1 / (1 - slip(median))."""
    import pytest

    from app.constants import get_rover
    from app.cost_cube import auto_slice_hours
    from app.cost_engine import slip_free_view
    from app.slip_model import slip_ratio

    slope = np.full((6, 6), 10.0)
    traversable = np.ones((6, 6), dtype=bool)
    rover = get_rover("nasa_viper")

    with_slip = auto_slice_hours(slope, traversable, 320.0, rover)
    without = auto_slice_hours(slope, traversable, 320.0, slip_free_view(rover))

    assert with_slip > without
    assert with_slip / without == pytest.approx(1.0 / (1.0 - slip_ratio(10.0, rover)))
