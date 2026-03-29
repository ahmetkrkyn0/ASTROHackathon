"""Unit tests for backend/app/serializer.py.

No DEM file required — synthetic RoverState objects only.
Run with: python test_serializer.py  (from backend/)
"""

from __future__ import annotations

import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from app.serializer import (
    GRID_COLS,
    GRID_ROWS,
    ORIGIN_X_M,
    ORIGIN_Y_M,
    RESOLUTION_M,
    lonlat_to_pixel,
    pixel_to_lonlat,
    states_to_geojson,
    states_to_waypoints,
    build_plan_response,
)
from app.simulation import RoverState, BATTERY_CAPACITY_WH


def check(condition: bool, label: str) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        sys.exit(1)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_state(step=0, row=250, col=250, battery_pct=80.0,
                slope_deg=5.0, temp=-50.0, shadow=0.2,
                distance_m=0.0, elapsed_hours=0.0,
                step_energy_wh=0.0, cumulative_cost=0.5) -> RoverState:
    return RoverState(
        step=step,
        row=row,
        col=col,
        distance_m=distance_m,
        elapsed_hours=elapsed_hours,
        battery_wh=BATTERY_CAPACITY_WH * battery_pct / 100.0,
        battery_pct=battery_pct,
        risk_level="LOW",
        slope_deg=slope_deg,
        surface_temp_c=temp,
        shadow_ratio=shadow,
        node_cost=0.5,
        step_energy_wh=step_energy_wh,
        cumulative_cost=cumulative_cost,
        recharge_count=0,
        recharged_this_step=False,
    )


def _dummy_astar_result(path: list | None = None) -> dict:
    return {
        "path_pixels": path or [[250, 250], [250, 251]],
        "metrics": {
            "total_distance_m": 80.0,
            "total_weighted_cost": 100.0,
            "max_slope_deg": 5.0,
            "max_thermal_risk": 0.4,
            "min_surface_temp_c": -50.0,
            "path_length_nodes": 2,
            "computation_time_ms": 12.5,
            "nodes_expanded": 1200,
        },
        "error": None,
    }


# ── pixel_to_lonlat ───────────────────────────────────────────────────────────

def test_pixel_to_lonlat_center():
    lon, lat = pixel_to_lonlat(250, 250)
    check(isinstance(lon, float), "center: lon is float")
    check(isinstance(lat, float), "center: lat is float")
    check(lat < -80.0, f"center: lat {lat:.4f} is south of -80")
    check(-180.0 <= lon <= 180.0, f"center: lon {lon:.4f} is in [-180, 180]")


def test_metadata_geometry_round_trip():
    metadata = {
        "origin": {"x": 176000.0, "y": 48000.0},
        "resolution_m": 80.0,
        "shape": [500, 500],
    }
    lon, lat = pixel_to_lonlat(250, 250, metadata)
    check(abs(lon - 70.8664) < 0.01, f"metadata lon {lon:.4f} matches expected window")
    check(abs(lat - (-83.1665)) < 0.01, f"metadata lat {lat:.4f} matches expected window")
    row, col = lonlat_to_pixel(lon, lat, metadata)
    check((row, col) == (250, 250), "metadata round-trip recovers original pixel")


def test_pixel_to_lonlat_corners():
    for r, c in [(0, 0), (0, 499), (499, 0), (499, 499)]:
        lon, lat = pixel_to_lonlat(r, c)
        check(lat < -80.0, f"corner ({r},{c}): lat {lat:.4f} < -80")


def test_pixel_to_lonlat_sanity_check():
    """Force a bad pixel (very large col) to trigger the sanity check."""
    raised = False
    try:
        # x_m = 156000 + 50000 * 80 = 4_156_000 m — far from south pole
        pixel_to_lonlat(0, 50000)
    except ValueError:
        raised = True
    check(raised, "sanity check raises ValueError for far-off pixel")


# ── lonlat_to_pixel ───────────────────────────────────────────────────────────

def test_round_trip():
    """pixel -> lonlat -> pixel should recover the original coordinates."""
    for r, c in [(0, 0), (250, 250), (499, 499), (100, 400)]:
        lon, lat = pixel_to_lonlat(r, c)
        r2, c2 = lonlat_to_pixel(lon, lat)
        check(r2 == r, f"round-trip row: ({r},{c}) -> lon/lat -> ({r2},{c2})")
        check(c2 == c, f"round-trip col: ({r},{c}) -> lon/lat -> ({r2},{c2})")


def test_lonlat_to_pixel_out_of_bounds():
    """A point near the equator is far outside the grid."""
    raised = False
    try:
        lonlat_to_pixel(0.0, -10.0)   # -10 lat is not near the south pole
    except ValueError:
        raised = True
    check(raised, "lonlat_to_pixel raises ValueError for out-of-grid point")


# ── states_to_geojson ─────────────────────────────────────────────────────────

def test_geojson_structure():
    states = [_make_state(step=i, col=250 + i, cumulative_cost=0.5 * (i + 1))
              for i in range(3)]
    gj = states_to_geojson(states)

    check(gj["type"] == "Feature", "geojson type is Feature")
    check(gj["geometry"]["type"] == "LineString", "geometry type is LineString")
    check(len(gj["geometry"]["coordinates"]) == 3, "3 coordinates for 3 states")
    check("total_cost" in gj["properties"], "properties has total_cost")
    check(gj["properties"]["waypoint_count"] == 3, "waypoint_count is 3")


def test_geojson_coordinate_order():
    """GeoJSON / Leaflet expects [lon, lat] — lon index 0 should be longitude."""
    states = [_make_state()]
    gj = states_to_geojson(states)
    coord = gj["geometry"]["coordinates"][0]
    check(len(coord) == 2, "coordinate has 2 elements")
    lon, lat = coord
    check(-180.0 <= lon <= 180.0, f"coord[0] is longitude ({lon:.4f})")
    check(lat < -80.0, f"coord[1] is latitude ({lat:.4f})")


def test_geojson_total_cost():
    states = [_make_state(step=i, cumulative_cost=float(i + 1)) for i in range(4)]
    gj = states_to_geojson(states)
    check(abs(gj["properties"]["total_cost"] - 4.0) < 1e-4, "total_cost = last cumulative_cost")


# ── states_to_waypoints ───────────────────────────────────────────────────────

def test_waypoints_fields():
    states = [_make_state()]
    wps = states_to_waypoints(states)
    check(len(wps) == 1, "one waypoint for one state")
    wp = wps[0]
    required_keys = (
        "step", "lon", "lat", "battery_pct", "risk_level",
        "slope_deg", "surface_temp_c", "shadow_ratio", "node_cost",
        "elapsed_hours", "distance_m", "step_energy_wh", "altitude_m",
        "recharge_count", "recharged_this_step",
    )
    for key in required_keys:
        check(key in wp, f"waypoint has key '{key}'")


def test_waypoints_step_index():
    states = [_make_state(step=i) for i in range(5)]
    wps = states_to_waypoints(states)
    for i, wp in enumerate(wps):
        check(wp["step"] == i, f"waypoints[{i}].step == {i}")


def test_waypoints_coord_is_valid():
    states = [_make_state(row=250, col=250)]
    wp = states_to_waypoints(states)[0]
    check(-180.0 <= wp["lon"] <= 180.0, "waypoint lon in valid range")
    check(wp["lat"] < -80.0, "waypoint lat in south pole region")


def test_waypoints_include_altitude_from_elevation_grid():
    states = [_make_state(row=4, col=7)]
    elevation = np.zeros((20, 20), dtype=np.float64)
    elevation[4, 7] = -1972.7

    wp = states_to_waypoints(states, elevation_grid=elevation)[0]
    check(wp["altitude_m"] == -1972.7, "waypoint altitude comes from elevation grid")


# ── build_plan_response ───────────────────────────────────────────────────────

def test_build_plan_response_with_simulation():
    states = [_make_state(step=i, col=250 + i) for i in range(3)]
    summary = {"waypoint_count": 3, "total_distance_km": 0.16}
    astar = _dummy_astar_result()
    elevation = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.float64)
    elevation[250, 250] = -123.45
    resp = build_plan_response(astar, states, summary, include_simulation=True, elevation_grid=elevation)

    check(resp["status"] == "success", "status is success")
    check("astar_metrics" in resp, "response has astar_metrics")
    check("summary" in resp, "response has summary")
    check("geojson" in resp, "response has geojson")
    check("waypoints" in resp, "response has waypoints (include_simulation=True)")
    check(resp["astar_metrics"] is astar["metrics"], "astar_metrics is the metrics dict")
    check(resp["summary"] is summary, "summary is passed through")
    check(resp["waypoints"][0]["altitude_m"] == -123.45, "plan response waypoint includes altitude")


def test_build_plan_response_without_simulation():
    states = [_make_state()]
    summary = {"waypoint_count": 1}
    astar = _dummy_astar_result()
    resp = build_plan_response(astar, states, summary, include_simulation=False)

    check("waypoints" not in resp, "waypoints omitted when include_simulation=False")
    check("geojson" in resp, "geojson still present when include_simulation=False")


def test_build_plan_response_astar_metrics_separate():
    """astar_metrics and summary must be distinct top-level keys."""
    states = [_make_state()]
    summary = {"waypoint_count": 1, "final_battery_pct": 80.0}
    astar = _dummy_astar_result()
    resp = build_plan_response(astar, states, summary)
    check("nodes_expanded" in resp["astar_metrics"], "astar_metrics has nodes_expanded")
    check("final_battery_pct" in resp["summary"], "summary has final_battery_pct")
    check("final_battery_pct" not in resp["astar_metrics"], "battery_pct not leaked into astar_metrics")


if __name__ == "__main__":
    tests = [
        test_pixel_to_lonlat_center,
        test_metadata_geometry_round_trip,
        test_pixel_to_lonlat_corners,
        test_pixel_to_lonlat_sanity_check,
        test_round_trip,
        test_lonlat_to_pixel_out_of_bounds,
        test_geojson_structure,
        test_geojson_coordinate_order,
        test_geojson_total_cost,
        test_waypoints_fields,
        test_waypoints_step_index,
        test_waypoints_coord_is_valid,
        test_waypoints_include_altitude_from_elevation_grid,
        test_build_plan_response_with_simulation,
        test_build_plan_response_without_simulation,
        test_build_plan_response_astar_metrics_separate,
    ]

    print(f"Running {len(tests)} serializer tests...\n")
    for fn in tests:
        print(f"{fn.__name__}:")
        fn()
    print("\nAll tests passed.")
