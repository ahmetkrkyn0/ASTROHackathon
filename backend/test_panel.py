"""The panel incidence model (C1): geometry, catalogue, and bit-equality.

Three things are pinned here. The GEOMETRY -- RoverDevKit's cos i, the
normalisation that stops a published peak power being multiplied by a
cosine twice, and the arithmetic on NASA's own two VIPER numbers. The
CATALOGUE -- every profile's panel geometry is an assumption and says so,
and the MODELLED/DECLARED_ONLY partition stays exact now that five fields
joined it. And BIT-EQUALITY -- with the default gain of 1.0 every energy
function, both cost cubes and the 4-D search return exactly what they
returned before C1, which is the contract the other twelve features set.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from app import panel as P
from app.constants import (
    DECLARED_ONLY_FIELDS,
    MODELLED_FIELDS,
    ROVERS,
    get_rover,
    rover_catalog,
)
from app.cost_cube import build_cost_cube, build_wait_cost_cube, wait_cost
from app.cost_engine import (
    f_energy_cell,
    move_battery_drain_wh,
    net_energy_per_metre_wh,
    wait_battery_drain_wh,
)
from app.cost_vec import _energy_per_metre_wh_grid, f_energy_cell_grid
from app.pathfinder_4d import astar_4d

WEIGHTS = {"w_energy": 0.259, "w_shadow": 0.142}


def _single(tilt_deg: float, mode: str = "sun_tracking", azimuth=None, tilt_mode="fixed"):
    return P.PanelArray(
        faces=(P.PanelFace(tilt_deg=tilt_deg, azimuth_offset_deg=0.0),),
        azimuth_mode=mode,
        azimuth_deg=azimuth,
        kind="assumption",
        source="assumption: test fixture",
        tilt_mode=tilt_mode,
    )


def _track(samples):
    return [
        {"index": i, "elevation_deg": float(e), "azimuth_true_deg": float(a)}
        for i, (e, a) in enumerate(samples)
    ]


# ── cos i itself ────────────────────────────────────────────────────────────


def test_normal_incidence_is_one():
    # A plate tilted to 60 deg with the Sun 30 deg up on the same azimuth is
    # face-on: the normal points straight at it.
    assert P.cos_incidence(30.0, 0.0, 60.0, 0.0) == pytest.approx(1.0, abs=1e-12)


def test_a_horizontal_plate_reduces_to_sin_elevation():
    for elev in (0.0, 1.5, 12.0, 45.0, 89.0):
        assert P.cos_incidence(elev, 137.0, 0.0, 0.0) == pytest.approx(
            math.sin(math.radians(elev)), abs=1e-12
        )


def test_a_vertical_plate_with_the_sun_on_the_horizon_reduces_to_cos_of_the_offset():
    for offset in (0.0, 30.0, 90.0, 150.0):
        assert P.cos_incidence(0.0, offset, 90.0, 0.0) == pytest.approx(
            math.cos(math.radians(offset)), abs=1e-12
        )


def test_the_back_of_the_plate_is_negative_and_the_gain_clamps_it():
    assert P.cos_incidence(0.0, 180.0, 90.0, 0.0) == pytest.approx(-1.0, abs=1e-12)
    array = _single(90.0, "fixed", azimuth=0.0)
    assert P.panel_gain(1.0, 180.0, array) == 0.0


def test_only_the_azimuth_difference_matters_so_the_frame_cancels():
    # The same geometry expressed in a frame rotated by the meridian
    # convergence must give the same cosine -- the trap the Faz-1 finding
    # (also numbered C1) left in the shadow path.
    rotation = 287.32792177719796
    a = P.cos_incidence(1.7, 40.0, 80.0, 15.0)
    b = P.cos_incidence(1.7, (40.0 + rotation) % 360.0, 80.0, (15.0 + rotation) % 360.0)
    assert a == pytest.approx(b, abs=1e-12)


def test_polar_tilt_rule_is_roverdevkits_min_80_abs_latitude():
    assert P.polar_tilt_deg(-88.9204782775053) == 80.0
    assert P.polar_tilt_deg(-45.0) == 45.0
    assert P.polar_tilt_deg(12.5) == 12.5
    assert P.polar_tilt_deg(-90.0) == 80.0


# ── normalisation ───────────────────────────────────────────────────────────


def test_a_single_plate_normalises_to_one_so_the_gain_is_exactly_max_0_cos_i():
    """The research note's formula is the one-face case of this model."""
    array = _single(80.0, "fixed", azimuth=0.0)
    assert array.reference_raw() == pytest.approx(1.0, abs=1e-9)
    for elev, azim in ((1.5, 0.0), (2.4, 37.0), (0.4, 200.0), (30.0, 95.0)):
        expected = max(0.0, P.cos_incidence(elev, azim, 80.0, 0.0))
        assert P.panel_gain(elev, azim, array) == pytest.approx(expected, abs=1e-12)


def test_three_vertical_faces_reference_is_sqrt_two_on_the_corner():
    array = P.PanelArray(
        faces=P._VIPER_FACES,
        azimuth_mode="free_heading",
        azimuth_deg=None,
        kind="assumption",
        source="assumption: test fixture",
    )
    assert array.reference_raw() == pytest.approx(math.sqrt(2.0), abs=1e-9)
    psi, raw = P.best_reference_azimuth(0.0, 0.0, array)
    assert raw == pytest.approx(math.sqrt(2.0), abs=1e-9)
    # Port (+90) and aft (180) straddle the Sun at 45 deg each.
    assert psi == pytest.approx(135.0, abs=1e-3)


def test_a_two_axis_array_gains_exactly_one_whenever_the_sun_is_up():
    """The pre-C1 model, expressed inside the new one."""
    array = _single(0.0, "sun_tracking", tilt_mode="sun_tracking")
    for elev in (0.1, 1.5, 30.0, 89.0):
        assert P.panel_gain(elev, 213.0, array) == pytest.approx(1.0, abs=1e-12)


def test_a_sun_below_the_horizon_gains_nothing_even_for_a_tilted_plate():
    """cos i alone does not give this: a tilted face sees a below-horizon Sun."""
    array = _single(80.0, "sun_tracking")
    assert P.cos_incidence(-0.9, 0.0, 80.0, 0.0) > 0.9  # the trap
    assert P.panel_gain(-0.9, 0.0, array) == 0.0
    assert P.panel_gain(0.0, 0.0, array) == 0.0


def test_the_gain_never_leaves_the_unit_interval():
    array = P.PanelArray(
        faces=P._VIPER_FACES,
        azimuth_mode="free_heading",
        azimuth_deg=None,
        kind="assumption",
        source="assumption: test fixture",
    )
    for elev in np.linspace(0.01, 89.0, 37):
        for azim in np.linspace(0.0, 359.0, 23):
            assert 0.0 <= P.panel_gain(float(elev), float(azim), array) <= 1.0


# ── NASA's two numbers ──────────────────────────────────────────────────────


def test_the_viper_corner_check_reproduces_nasas_published_ratio():
    """NASA published 320 W per panel and 450 W on corner; the geometry model
    says the second is sqrt(2) times the first. This is OUR arithmetic on
    THEIR numbers -- not a NASA validation of LunaPath."""
    check = P.viper_corner_check()
    assert check["one_face_raw"] == pytest.approx(1.0, abs=1e-9)
    assert check["corner_raw"] == pytest.approx(math.sqrt(2.0), abs=1e-9)
    assert check["model_ratio"] == pytest.approx(math.sqrt(2.0), abs=1e-9)
    assert check["published_ratio"] == pytest.approx(450.0 / 320.0, abs=1e-12)
    assert check["predicted_on_corner_w"] == pytest.approx(452.548, abs=1e-3)
    assert check["published_on_corner_w"] == 450.0
    assert abs(check["difference_pct"]) < 1.0
    assert check["quote"] == "Solar arrays: 320W per panel (450W on corner)"


def test_roverdevkits_own_validation_is_quoted_not_restated():
    """Their result, in their words. The paper writes '+5%' where 52/50 is
    +4%, and 13.3% is a MEDIAN -- so nothing here is recomputed."""
    quoted = P.ROVERDEVKIT_QUOTED
    assert "52 W" in quoted["peak_power"] and "+5%" in quoted["peak_power"]
    assert "median absolute error of 13.3 %" in quoted["mass_model"]
    assert "mean 14.8 %" in quoted["mass_model"]
    assert "default array is horizontal" in quoted["default_array"]


# ── the array's own validation ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "kwargs",
    [
        {"faces": ()},
        {"azimuth_mode": "sideways"},
        {"azimuth_mode": "fixed", "azimuth_deg": None},
        {"tilt_mode": "wobbling"},
    ],
)
def test_a_malformed_array_is_refused_at_construction(kwargs):
    base = {
        "faces": (P.PanelFace(tilt_deg=80.0, azimuth_offset_deg=0.0),),
        "azimuth_mode": "sun_tracking",
        "azimuth_deg": None,
        "kind": "assumption",
        "source": "assumption: test fixture",
    }
    with pytest.raises(ValueError):
        P.PanelArray(**{**base, **kwargs})


def test_a_two_axis_array_with_several_faces_is_refused():
    with pytest.raises(ValueError, match="single face"):
        P.PanelArray(
            faces=P._VIPER_FACES,
            azimuth_mode="sun_tracking",
            azimuth_deg=None,
            kind="assumption",
            source="assumption: test fixture",
            tilt_mode="sun_tracking",
        )


def test_a_face_outside_zero_to_ninety_degrees_is_refused():
    with pytest.raises(ValueError, match="tilt"):
        _single(120.0)


def test_heading_locked_without_a_heading_is_an_error():
    array = _single(90.0, "heading_locked")
    with pytest.raises(ValueError, match="heading_deg"):
        P.panel_gain(1.5, 30.0, array)


# ── the series ──────────────────────────────────────────────────────────────


def test_gain_series_follows_the_track_slice_for_slice():
    array = _single(80.0, "sun_tracking")
    track = _track([(1.5, 10.0), (-0.5, 100.0), (2.0, 200.0)])
    gains = P.gain_series(track, array)
    assert gains.shape == (3,)
    assert gains[1] == 0.0
    assert gains[0] == pytest.approx(P.panel_gain(1.5, 10.0, array), abs=1e-12)
    assert gains[2] == pytest.approx(P.panel_gain(2.0, 200.0, array), abs=1e-12)


def test_a_heading_series_of_the_wrong_length_is_refused():
    array = _single(90.0, "heading_locked")
    with pytest.raises(ValueError, match="same length"):
        P.gain_series(_track([(1.0, 0.0), (1.0, 10.0)]), array, headings_deg=[0.0])


def test_a_heading_locked_body_array_loses_everything_driving_at_the_sun():
    """VIPER has no forward-facing array -- the front carries the drill and
    the navigation cameras -- so a heading straight at the Sun lights no face.
    This is why NASA names a driving mode 'sun on corner'."""
    array = P.PanelArray(
        faces=P._VIPER_FACES,
        azimuth_mode="heading_locked",
        azimuth_deg=None,
        kind="assumption",
        source="assumption: test fixture",
    )
    track = _track([(1.0, 0.0)] * 3)
    at_sun, on_corner, away = P.gain_series(track, array, headings_deg=[0.0, 135.0, 180.0])
    assert at_sun == pytest.approx(0.0, abs=1e-9)
    assert on_corner == pytest.approx(1.0, abs=1e-3)
    assert away == pytest.approx(1.0 / math.sqrt(2.0), abs=1e-3)


def test_counterfactuals_rank_the_way_the_geometry_says_they_must():
    # A polar-latitude Sun: 1.5 deg up, sweeping in azimuth.
    track = _track([(1.5, float(a)) for a in range(0, 360, 5)])
    cf = P.counterfactual_gains(track, tilt_deg=80.0)
    # "When lit" is the SUN being up, not the panel facing it: a fixed panel
    # averaged only over its good hours would look far better than it is.
    assert cf["polar_fixed_north"]["sun_up_fraction"] == 1.0
    assert cf["polar_fixed_north"]["positive_fraction"] < 1.0
    assert cf["polar_tracking"]["positive_fraction"] == 1.0
    assert cf["polar_fixed_north"]["mean_when_sun_up"] == pytest.approx(
        cf["polar_fixed_north"]["mean"], abs=1e-12
    )
    assert cf["sun_pointed"]["mean"] == pytest.approx(1.0, abs=1e-12)
    assert cf["body_three_face"]["mean"] > cf["polar_tracking"]["mean"]
    assert cf["polar_tracking"]["mean"] > cf["polar_fixed_north"]["mean"]
    assert cf["polar_fixed_north"]["mean"] > cf["horizontal"]["mean"]
    # A horizontal plate at 1.5 deg collects sin(1.5 deg) of its rating.
    assert cf["horizontal"]["mean"] == pytest.approx(math.sin(math.radians(1.5)), abs=1e-9)


# ── the catalogue ───────────────────────────────────────────────────────────


def test_every_profile_declares_panel_geometry_as_an_assumption():
    for rover_id in ROVERS:
        rover = get_rover(rover_id)
        array = P.array_for_rover(rover)
        assert array is not None, rover_id
        assert array.kind == "assumption"
        assert array.source.startswith("assumption:"), rover_id
        assert array.reference_raw() > 0.0


def test_a_profile_without_panel_geometry_gets_none_rather_than_an_invented_one():
    bare = {k: v for k, v in get_rover().items() if not k.startswith("panel_")}
    assert P.array_for_rover(bare) is None
    assert P.array_for_rover(None) is None
    block = P.rover_panel_block(bare)
    assert block["declared"] is False
    assert "no panel geometry" in block["reason"]


def test_the_modelled_declared_partition_is_exact_now_that_five_fields_joined_it():
    """Disjointness was already asserted elsewhere; this pins EXHAUSTIVENESS,
    which nothing did -- a field in neither set would have passed the whole
    suite while falsifying the catalogue's own docstring."""
    assert not (MODELLED_FIELDS & set(DECLARED_ONLY_FIELDS))
    for rover_id, cfg in ROVERS.items():
        leftover = set(cfg) - MODELLED_FIELDS - set(DECLARED_ONLY_FIELDS) - {"name"}
        assert leftover == set(), f"{rover_id} has unclassified fields {leftover}"


def test_the_catalogue_publishes_the_panel_block_and_stays_json_safe():
    catalog = rover_catalog()
    text = json.dumps(catalog, allow_nan=False)
    assert "panel_model" in text
    for entry in catalog:
        block = entry["panel_model"]
        assert block["declared"] is True
        assert block["validity"] == "MODEL"
        assert block["source"].startswith("assumption:")
        assert block["n_faces"] in (1, 3)


def test_the_viper_and_lpr1_sources_carry_nasas_own_words():
    for rover_id in ("lpr_1", "nasa_viper"):
        source = get_rover(rover_id)["panel_geometry_source"]
        assert "port, starboard, and aft surfaces" in source
        assert "Radiators (on top)" in source
        assert "sun on corner" in source
        # The tilt is an inference and the source says so.
        assert "inference" in source and "never calls" in source


# ── bit-equality: the whole point of the default ────────────────────────────


def test_every_energy_function_is_bit_identical_at_gain_one():
    for rover_id in sorted(ROVERS):
        rover = get_rover(rover_id)
        for theta in (0.0, 4.0, 9.5, 14.0):
            for shadow in (0.0, 0.25, 0.5, 1.0):
                assert net_energy_per_metre_wh(
                    theta, shadow, rover
                ) == net_energy_per_metre_wh(theta, shadow, rover, solar_gain=1.0)
                assert move_battery_drain_wh(
                    theta, 20.0, shadow, rover
                ) == move_battery_drain_wh(theta, 20.0, shadow, rover, solar_gain=1.0)
                assert wait_battery_drain_wh(
                    shadow, 1.5, rover
                ) == wait_battery_drain_wh(shadow, 1.5, rover, solar_gain=1.0)
                assert f_energy_cell(theta, rover, shadow) == f_energy_cell(
                    theta, rover, shadow, solar_gain=1.0
                )
                assert wait_cost(1.0 - shadow, 1.0, rover, WEIGHTS) == wait_cost(
                    1.0 - shadow, 1.0, rover, WEIGHTS, solar_gain=1.0
                )


def test_the_scalar_and_vectorised_energy_twins_agree_at_every_gain():
    """They are asserted equal cell for cell elsewhere; a gain inserted in a
    different position in one of them would break that silently."""
    rover = get_rover()
    theta = np.array([0.0, 3.0, 7.5, 13.0])
    shadow = np.array([0.0, 0.3, 0.7, 1.0])
    for gain in (1.0, 0.98, 0.5, 0.019, 0.0):
        scalar = np.array(
            [
                net_energy_per_metre_wh(float(t), float(s), rover, solar_gain=gain)
                for t, s in zip(theta, shadow)
            ]
        )
        vector = _energy_per_metre_wh_grid(theta, shadow, rover, solar_gain=gain)
        assert np.array_equal(scalar, vector)
        cells = np.array(
            [
                f_energy_cell(float(t), rover, float(s), solar_gain=gain)
                for t, s in zip(theta, shadow)
            ]
        )
        assert f_energy_cell_grid(theta, rover, shadow, solar_gain=gain) == pytest.approx(
            cells, abs=1e-12
        )


def test_a_lower_gain_never_makes_a_cell_cheaper():
    rover = get_rover()
    for theta in (0.0, 8.0):
        previous = -1.0
        for gain in (1.0, 0.9, 0.5, 0.1, 0.0):
            value = f_energy_cell(theta, rover, 0.0, solar_gain=gain)
            assert value >= previous
            previous = value


def test_the_reference_scale_does_not_move_with_the_gain():
    """Only the cell being priced reads the gain. If the [0, 1] reference
    moved too, "the cheapest possible cell" would follow the Sun's azimuth."""
    rover = get_rover()
    # The worst admissible cell is fully shadowed, so it collects nothing at
    # any gain and must stay pinned at 1.0.
    slope_max = float(rover["slope_max_deg"])
    for gain in (1.0, 0.3, 0.0):
        assert f_energy_cell(slope_max, rover, 1.0, solar_gain=gain) == pytest.approx(
            1.0, abs=1e-12
        )


def test_the_wait_cube_is_bit_identical_without_a_gain_series():
    rover = get_rover()
    series = [np.full((4, 4), 0.3), np.full((4, 4), 0.9), np.full((4, 4), 0.0)]
    base = build_wait_cost_cube(series, rover, 1.0, WEIGHTS)
    ones = build_wait_cost_cube(series, rover, 1.0, WEIGHTS, solar_gain_series=[1.0] * 3)
    assert np.array_equal(base, ones)


def test_the_wait_cube_prices_the_same_illumination_differently_at_different_gains():
    """The pre-C1 cube deduplicated values across the WHOLE cube. With a
    per-slice gain that would collapse exactly the distinction C1 adds."""
    rover = get_rover()
    series = [np.full((2, 2), 0.2)] * 3
    cube = build_wait_cost_cube(
        series, rover, 1.0, WEIGHTS, solar_gain_series=[1.0, 0.5, 0.0]
    )
    assert cube[0, 0, 0] < cube[1, 0, 0] < cube[2, 0, 0]


def test_a_gain_series_of_the_wrong_length_is_refused_by_both_cubes():
    rover = get_rover()
    series = [np.full((3, 3), 0.4)] * 2
    with pytest.raises(ValueError, match="solar_gain_series"):
        build_wait_cost_cube(series, rover, 1.0, WEIGHTS, solar_gain_series=[1.0])
    grids = {
        "slope": np.zeros((3, 3)),
        "thermal": np.full((3, 3), -20.0),
        "traversable": np.ones((3, 3), dtype=bool),
        "metadata": {"resolution_m": 20.0},
    }
    with pytest.raises(ValueError, match="solar_gain_series"):
        build_cost_cube(grids, series, rover, solar_gain_series=[1.0, 1.0, 1.0])


def test_the_cost_cube_is_bit_identical_without_a_gain_series():
    rover = get_rover()
    grids = {
        "slope": np.array([[0.0, 5.0], [10.0, 2.0]]),
        "thermal": np.full((2, 2), -40.0),
        "traversable": np.ones((2, 2), dtype=bool),
        "metadata": {"resolution_m": 20.0},
    }
    series = [np.full((2, 2), 0.1), np.full((2, 2), 0.8)]
    base = build_cost_cube(grids, series, rover)
    ones = build_cost_cube(grids, series, rover, solar_gain_series=[1.0, 1.0])
    assert np.array_equal(base, ones)
    gained = build_cost_cube(grids, series, rover, solar_gain_series=[0.02, 0.02])
    assert not np.array_equal(base, gained)


# ── the 4-D search ──────────────────────────────────────────────────────────


def _search(gain_series=None, n_slices=8, shape=(1, 5)):
    cost_cube = np.full((n_slices, *shape), 0.02, dtype=np.float64)
    wait_cube = np.full((n_slices, *shape), 0.02, dtype=np.float64)
    shadow_cube = np.full((n_slices, *shape), 0.4, dtype=np.float64)
    return astar_4d(
        cost_cube,
        wait_cube,
        np.ones(shape, dtype=bool),
        start=(0, 0),
        goal=(0, 4),
        resolution_m=80.0,
        slice_hours=1.0,
        rover=get_rover(),
        slope_grid=np.zeros(shape),
        shadow_cube=shadow_cube,
        solar_gain_series=gain_series,
    )


def test_the_search_is_bit_identical_without_a_gain_series():
    """C6's contract: same path, same nodes expanded, same total cost."""
    base = _search()
    ones = _search(gain_series=[1.0] * 8)
    assert base["error"] is None and ones["error"] is None
    assert base["path_states"] == ones["path_states"]
    assert base["metrics"]["nodes_expanded"] == ones["metrics"]["nodes_expanded"]
    assert base["metrics"]["total_cost"] == ones["metrics"]["total_cost"]
    assert base["path_battery_pct"] == ones["path_battery_pct"]


def test_a_low_gain_drains_the_battery_faster_along_the_same_route():
    base = _search()
    dark = _search(gain_series=[0.02] * 8)
    assert dark["error"] is None
    assert dark["path_states"] == base["path_states"]
    assert dark["path_battery_pct"][-1] < base["path_battery_pct"][-1]


def test_a_short_gain_series_is_refused_rather_than_silently_padded():
    result = _search(gain_series=[1.0, 1.0])
    assert result["error"] is not None
    assert "solar_gain_series" in result["error"]


# ── the two defects an adversarial review found ─────────────────────────────


def test_a_multislice_move_averages_the_slice_INCOMES_not_the_two_means():
    """The solar term is BILINEAR in (exposure, gain) once the gain varies.
    Charging ``(1 - mean exposure) * mean gain`` is not the trapezoid the cost
    cube prices -- on an edge that crosses the terminator the two differ by a
    factor of two -- and the Monte Carlo replay integrates the product, so the
    plan and its stress test would disagree on the same edge."""
    rover = get_rover()
    p_solar = float(rover["p_solar_w"])
    shape = (1, 3)
    n_slices = 6
    # Depart a LIT cell in a slice with FULL gain, arrive in a DARK cell in a
    # slice where the Sun has set. Both terms of the bilinear product move,
    # which is exactly when the two conventions diverge.
    shadow_cube = np.zeros((n_slices, *shape))
    shadow_cube[:, 0, 1:] = 1.0
    gains = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    result = astar_4d(
        np.full((n_slices, *shape), 0.02),
        np.full((n_slices, *shape), 0.02),
        np.ones(shape, dtype=bool),
        start=(0, 0),
        goal=(0, 1),
        resolution_m=80.0,
        slice_hours=1.0,
        rover=rover,
        slope_grid=np.zeros(shape),
        shadow_cube=shadow_cube,
        solar_gain_series=gains,
    )
    assert result["error"] is None
    e_cap = float(rover["e_cap_wh"])
    drained = (1.0 - result["path_battery_pct"][1] / 100.0) * e_cap

    departure, arrival = result["path_states"][0][2], result["path_states"][1][2]
    hours = _edge_hours(result, rover, 80.0)
    mean_exposure = 0.5 * (
        shadow_cube[departure, 0, 0] + shadow_cube[arrival, 0, 1]
    )
    trapezoid = 0.5 * (
        (1.0 - shadow_cube[departure, 0, 0]) * gains[departure]
        + (1.0 - shadow_cube[arrival, 0, 1]) * gains[arrival]
    )
    product_of_means = (1.0 - mean_exposure) * 0.5 * (gains[departure] + gains[arrival])
    # The two candidate conventions really do differ here, and by a lot: the
    # gap is p_solar * 0.25 * hours, three orders of magnitude more than the
    # rounding in the reported battery percentage.
    assert trapezoid != pytest.approx(product_of_means, abs=1e-9)
    drawn = _drawn_wh(rover, mean_exposure, hours)
    as_trapezoid = drawn - p_solar * trapezoid * hours
    as_product_of_means = drawn - p_solar * product_of_means * hours
    assert abs(as_trapezoid - as_product_of_means) > 5.0
    # The planner charged the trapezoid.
    assert abs(drained - as_trapezoid) < abs(drained - as_product_of_means)
    assert drained == pytest.approx(as_trapezoid, abs=0.05)


def _edge_hours(result, rover, resolution_m: float) -> float:
    from app.cost_engine import edge_travel_time_s

    return edge_travel_time_s(0.0, resolution_m, rover) / 3600.0


def _drawn_wh(rover, exposure: float, hours: float) -> float:
    from app.cost_engine import housekeeping_power_w

    traction_w = float(rover["p_base_w"])
    return (traction_w + housekeeping_power_w(exposure, rover)) * hours


def test_a_safety_bound_takes_the_worst_gain_WITH_LIGHT_not_the_worst_number():
    """A horizon that runs into the night contains zeros, and a plain minimum
    would make one scalar say "this array never produces anything" -- which
    double-counts darkness the consumer's exposure term already carries."""
    assert P.conservative_gain(np.array([0.99, 0.0, 0.98, 0.0])) == pytest.approx(0.98)
    assert P.conservative_gain(np.array([0.0, 0.0, 0.0])) == 1.0
    assert P.conservative_gain(np.array([0.4, 0.9])) == pytest.approx(0.4)
    # The trap, stated: np.min would have said 0.0 for the first case.
    assert float(np.min(np.array([0.99, 0.0, 0.98, 0.0]))) == 0.0


def test_the_claim_names_the_heading_assumption_as_the_largest_optimism():
    """The applied gain for a body array is the maximum over heading, which a
    rover driving somewhere cannot hold. The block the jury reads has to say
    so, not just the research document."""
    assert "free_heading" in P.PANEL_CLAIM
    assert "3.3" in P.PANEL_CLAIM
    assert "0.305" in P.PANEL_CLAIM and "0.9996" in P.PANEL_CLAIM


# ── the response block ──────────────────────────────────────────────────────


def test_the_block_reports_without_applying_when_nothing_was_requested():
    block = P.panel_block(get_rover(), None, requested=False, reason="no epoch")
    assert block["applied"] is False
    assert block["model"] == "sun_pointed"
    assert block["reason"] == "no epoch"
    assert block["geometry"]["n_faces"] == 3
    assert block["validity"] == "MODEL"
    assert block["gain"]["n_slices"] == 0
    json.dumps(block, allow_nan=False)


def test_the_block_applies_only_when_a_gain_series_actually_exists():
    rover = get_rover()
    array = P.array_for_rover(rover)
    track = _track([(1.5, 10.0), (1.6, 20.0)])
    gains = P.gain_series(track, array)
    block = P.panel_block(rover, gains, requested=True, sun_track=track)
    assert block["applied"] is True
    assert block["model"] == "cos_incidence"
    assert block["gain"]["n_slices"] == 2
    assert block["counterfactuals"]["horizontal"]["mean"] < block["gain"]["mean"]
    json.dumps(block, allow_nan=False)
    # Requested but unbuildable is NOT applied.
    assert P.panel_block(rover, None, requested=True, reason="no kernels")["applied"] is False


def test_the_claim_never_promises_more_than_geometry():
    for text in (P.PANEL_CLAIM, P.PANEL_SCOPE):
        assert isinstance(text, str) and text
    assert "MODEL" in P.PANEL_CLAIM
    assert "ASSUMPTION" in P.PANEL_CLAIM
    assert "efficiency" in P.PANEL_CLAIM
    assert "NOT RoverDevKit's default" in P.PANEL_CLAIM
    ids = {ref["id"] for ref in P.PANEL_REFERENCES}
    assert {"roverdevkit_2026", "viper_pip_2021", "otten_icra_2015"} <= ids
