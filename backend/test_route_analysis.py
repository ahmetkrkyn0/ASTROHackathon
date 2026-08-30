"""Route statistics (PathAnalysis-inspired) tests."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app
from app.route_analysis import route_statistics
from app.simulation import RoverState

_SHAPE = (30, 30)


def _state(step, slope_deg, risk_level, surface_temp_c=-60.0) -> RoverState:
    return RoverState(
        step=step,
        row=step,
        col=step,
        distance_m=step * 80.0,
        elapsed_hours=step * 0.5,
        battery_wh=5000.0 - step * 10,
        battery_pct=100.0 - step * 2,
        risk_level=risk_level,
        slope_deg=slope_deg,
        surface_temp_c=surface_temp_c,
        shadow_ratio=0.2,
        node_cost=0.3,
        step_energy_wh=10.0,
        cumulative_cost=step * 0.3,
        recharge_count=0,
        recharged_this_step=False,
    )


def test_empty_states_return_zeroed_statistics():
    stats = route_statistics([])
    assert stats["waypoint_count"] == 0
    assert stats["slope_histogram"] == []
    assert stats["risk_breakdown_pct"] == {}


def test_slope_histogram_bins_cover_every_waypoint():
    states = [
        _state(0, slope_deg=2.0, risk_level="LOW"),
        _state(1, slope_deg=7.0, risk_level="LOW"),
        _state(2, slope_deg=22.0, risk_level="MEDIUM"),
    ]
    stats = route_statistics(states)
    total_count = sum(bucket["count"] for bucket in stats["slope_histogram"])
    assert total_count == 3


def test_slope_histogram_bucket_labels_are_ordered():
    states = [_state(0, slope_deg=3.0, risk_level="LOW")]
    stats = route_statistics(states)
    lows = [bucket["bin_low_deg"] for bucket in stats["slope_histogram"]]
    assert lows == sorted(lows)


def test_risk_breakdown_sums_to_one_hundred_percent():
    states = [
        _state(0, slope_deg=2.0, risk_level="LOW"),
        _state(1, slope_deg=3.0, risk_level="LOW"),
        _state(2, slope_deg=4.0, risk_level="HIGH"),
        _state(3, slope_deg=5.0, risk_level="CRITICAL"),
    ]
    stats = route_statistics(states)
    assert stats["risk_breakdown_pct"]["LOW"] == pytest.approx(50.0)
    assert stats["risk_breakdown_pct"]["HIGH"] == pytest.approx(25.0)
    assert stats["risk_breakdown_pct"]["CRITICAL"] == pytest.approx(25.0)
    assert sum(stats["risk_breakdown_pct"].values()) == pytest.approx(100.0)


def test_thermal_extremes_are_reported():
    states = [
        _state(0, slope_deg=1.0, risk_level="LOW", surface_temp_c=-140.0),
        _state(1, slope_deg=1.0, risk_level="LOW", surface_temp_c=-20.0),
    ]
    stats = route_statistics(states)
    assert stats["min_surface_temp_c"] == pytest.approx(-140.0)
    assert stats["max_surface_temp_c"] == pytest.approx(-20.0)


def test_waypoint_count_matches_input_length():
    states = [_state(i, slope_deg=1.0, risk_level="LOW") for i in range(7)]
    stats = route_statistics(states)
    assert stats["waypoint_count"] == 7


def test_custom_slope_bins_are_respected():
    states = [_state(0, slope_deg=12.0, risk_level="LOW")]
    stats = route_statistics(states, slope_bins_deg=(0, 15, 30))
    assert len(stats["slope_histogram"]) == 2
    assert stats["slope_histogram"][0]["count"] == 1


def test_slope_at_the_top_bin_edge_is_counted():
    """25 deg is the default rover's slope_max_deg, so a traversable route
    can legitimately touch the top edge -- it must not vanish."""
    stats = route_statistics([_state(0, slope_deg=25.0, risk_level="MEDIUM")])
    assert sum(b["count"] for b in stats["slope_histogram"]) == 1
    assert stats["slope_histogram"][-1]["count"] == 1


def test_slopes_outside_the_bin_range_land_in_the_edge_bins():
    """Counts must always reconcile with waypoint_count; a slope beyond
    the outermost edge is clamped, never dropped."""
    states = [
        _state(0, slope_deg=-3.0, risk_level="LOW"),
        _state(1, slope_deg=40.0, risk_level="CRITICAL"),
    ]
    stats = route_statistics(states, slope_bins_deg=(0, 10, 20))
    assert sum(b["count"] for b in stats["slope_histogram"]) == stats["waypoint_count"]
    assert stats["slope_histogram"][0]["count"] == 1
    assert stats["slope_histogram"][-1]["count"] == 1


def test_histogram_percentages_sum_to_about_one_hundred():
    """Percentages are rounded to 2dp for display, so a route whose bins
    divide unevenly leaves a small residue (six waypoints give 100.01).
    The counts are the exact figure; this only guards against a bin being
    scaled against the wrong total."""
    states = [_state(i, slope_deg=float(i * 4), risk_level="LOW") for i in range(6)]
    stats = route_statistics(states)
    assert sum(b["pct"] for b in stats["slope_histogram"]) == pytest.approx(100.0, abs=0.1)


def test_degenerate_bin_specification_is_rejected():
    with pytest.raises(ValueError):
        route_statistics([_state(0, slope_deg=1.0, risk_level="LOW")], slope_bins_deg=(5.0,))


def test_plan_endpoint_returns_route_statistics():
    """The grids are injected INSIDE the TestClient context, not before it.

    Entering the context runs the startup lifespan, which loads the real
    500x500 processed grid into app.state and would overwrite anything
    staged beforehand -- the request would then be planned against real
    terrain, where (2, 2) is not traversable and the endpoint answers 422.
    """
    rover = get_rover()
    synthetic_grids = {
        "elevation": np.zeros(_SHAPE),
        "slope": np.full(_SHAPE, 3.0),
        "aspect": np.zeros(_SHAPE),
        "thermal": np.full(_SHAPE, -60.0),
        "shadow_ratio": np.full(_SHAPE, 0.2),
        "traversable": np.ones(_SHAPE, dtype=bool),
        "cost": np.full(_SHAPE, 0.3),
        "metadata": {
            "origin": {"x": 156000.0, "y": 28000.0},
            "resolution_m": 80.0,
            "shape": list(_SHAPE),
            "crs": "test",
            "default_rover_id": rover["id"],
            "cost_weights": {
                "w_slope": 0.409,
                "w_energy": 0.259,
                "w_shadow": 0.142,
                "w_thermal": 0.19,
            },
        },
    }
    previous_grids = getattr(app.state, "grids", None)
    try:
        with TestClient(app) as client:
            app.state.grids = synthetic_grids
            response = client.post(
                "/api/plan",
                json={
                    "start": {"row": 2, "col": 2},
                    "goal": {"row": 25, "col": 25},
                    "include_simulation": True,
                },
            )
    finally:
        app.state.grids = previous_grids

    assert response.status_code == 200, response.text
    stats = response.json()["route_statistics"]
    assert stats["waypoint_count"] > 0
    assert stats["slope_histogram"]
    assert stats["risk_breakdown_pct"]
