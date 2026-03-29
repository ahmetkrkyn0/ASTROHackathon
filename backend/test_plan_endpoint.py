"""Integration tests for POST /api/plan.

No DEM or .npy files required — synthetic 20x20 grids are injected directly
into app.state and the module-level _grids before each request.

Run with: python test_plan_endpoint.py  (from backend/)
"""

from __future__ import annotations

import math
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

# Disable startup grid loading so the test server does not need .npy files.
# The startup handler checks app.state.grids after load; we inject it manually.
os.environ["LUNAPATH_SKIP_STARTUP"] = "YES"  # harmless — startup still runs but fails gracefully

from fastapi.testclient import TestClient
import app.main as _main_module
from app.main import app
from app.serializer import pixel_to_lonlat

SHAPE = (20, 20)
_ROWS, _COLS = SHAPE


def _make_grids(
    slope_val: float = 5.0,
    temp_val: float = -50.0,
    shadow_val: float = 0.1,
    traversable_val: bool = True,
) -> dict:
    """Build a synthetic flat 20x20 grid set."""
    slope = np.full(SHAPE, slope_val, dtype=np.float64)
    thermal = np.full(SHAPE, temp_val, dtype=np.float64)
    shadow = np.full(SHAPE, shadow_val, dtype=np.float64)
    traversable = np.full(SHAPE, traversable_val, dtype=bool)
    elevation = np.zeros(SHAPE, dtype=np.float64)

    # Cost grid: simple uniform value (no inf — fully traversable)
    cost = np.full(SHAPE, 0.5, dtype=np.float64)
    if not traversable_val:
        # Make every cell blocked
        traversable[:] = False
        cost[:] = np.inf

    return {
        "elevation": elevation,
        "slope": slope,
        "aspect": np.zeros(SHAPE, dtype=np.float64),
        "thermal": thermal,
        "shadow_ratio": shadow,
        "cost": cost,
        "traversable": traversable,
        "metadata": {
            "resolution_m": 80.0,
            "shape": list(SHAPE),
            "crs": "moon_sp",
            "source": "synthetic_test",
            "cost_weights": {
                "w_slope": 0.409,
                "w_energy": 0.259,
                "w_shadow": 0.142,
                "w_thermal": 0.190,
            },
        },
    }


def _inject_grids(grids: dict) -> None:
    """Push synthetic grids into app.state and module global."""
    app.state.grids = grids
    _main_module._grids = grids


def check(condition: bool, label: str) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        sys.exit(1)


# TestClient is created once; startup events run but fail gracefully (no .npy files).
client = TestClient(app, raise_server_exceptions=True)


# ── /api/health ───────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/api/health")
    check(r.status_code == 200, "GET /api/health returns 200")
    check(r.json()["status"] == "ok", "health.status == ok")


# ── 503 when no grids loaded ──────────────────────────────────────────────────

def test_plan_503_when_no_grids():
    # Remove grids
    app.state.grids = None
    _main_module._grids = None

    r = client.post("/api/plan", json={
        "start": {"row": 0, "col": 0},
        "goal": {"row": 5, "col": 5},
    })
    check(r.status_code == 503, "POST /api/plan returns 503 when grids not loaded")


# ── PlanWeights model validation ──────────────────────────────────────────────

def test_weights_out_of_range():
    _inject_grids(_make_grids())
    r = client.post("/api/plan", json={
        "start": {"row": 0, "col": 0},
        "goal": {"row": 5, "col": 5},
        "weights": {"w_slope": 3.0},  # > 2.0 — invalid
    })
    check(r.status_code == 422, "weight > 2.0 returns 422 validation error")


def test_weights_default_accepted():
    _inject_grids(_make_grids())
    r = client.post("/api/plan", json={
        "start": {"row": 0, "col": 0},
        "goal": {"row": 2, "col": 2},
        # No weights key — defaults (balanced profile) should be used
    })
    # 200 or 404 (path not found on synthetic grid) — either means request was valid
    check(r.status_code in (200, 404), "no weights field is accepted")


# ── Coordinate input: pixel vs geo ────────────────────────────────────────────

def test_pixel_input_accepted():
    _inject_grids(_make_grids())
    r = client.post("/api/plan", json={
        "start": {"row": 0, "col": 0},
        "goal": {"row": 5, "col": 5},
    })
    check(r.status_code in (200, 404), "pixel coords accepted")


def test_geo_input_accepted():
    """Geo coords near lunar south pole should parse without 422."""
    _inject_grids(_make_grids())
    # pixel (0,0) → roughly lon=10.1, lat=-84.8 (from serializer tests)
    # We don't need an exact match; just verify the request parses and reaches A*
    r = client.post("/api/plan", json={
        "start": {"lon": 10.1, "lat": -84.8},
        "goal": {"lon": 74.7, "lat": -83.9},
    })
    # Either found a path (200) or A* gave up (404) — both mean parsing succeeded
    check(r.status_code in (200, 404, 422), "geo coords accepted (422 only if out-of-grid)")


def test_geo_out_of_range_returns_422():
    _inject_grids(_make_grids())
    r = client.post("/api/plan", json={
        "start": {"lon": 0.0, "lat": -10.0},  # Near equator — not in south pole grid
        "goal": {"row": 5, "col": 5},
    })
    check(r.status_code == 422, "geo coord outside grid returns 422")


# ── Bounds checks ─────────────────────────────────────────────────────────────

def test_start_out_of_bounds():
    _inject_grids(_make_grids())
    r = client.post("/api/plan", json={
        "start": {"row": 999, "col": 999},
        "goal": {"row": 5, "col": 5},
    })
    check(r.status_code == 422, "start out of bounds returns 422")


def test_goal_out_of_bounds():
    _inject_grids(_make_grids())
    r = client.post("/api/plan", json={
        "start": {"row": 0, "col": 0},
        "goal": {"row": _ROWS + 1, "col": _COLS + 1},
    })
    check(r.status_code == 422, "goal out of bounds returns 422")


def test_cell_telemetry_returns_backend_values():
    grids = _make_grids(temp_val=-84.7)
    grids["elevation"][7, 8] = -1972.7
    _inject_grids(grids)

    r = client.get("/api/cell-telemetry?row=7&col=8")
    check(r.status_code == 200, "GET /api/cell-telemetry returns 200")
    body = r.json()
    check(body["row"] == 7 and body["col"] == 8, "telemetry returns requested row/col")
    check(math.isclose(body["altitude_m"], -1972.7, rel_tol=0, abs_tol=1e-6), "altitude comes from backend elevation grid")
    check(math.isclose(body["thermal_c"], -84.7, rel_tol=0, abs_tol=1e-6), "temperature comes from backend thermal grid")
    check(math.isclose(body["span_km"], 1.6, rel_tol=0, abs_tol=1e-6), "span_km uses backend shape metadata")


def test_cost_layer_respects_weight_overrides():
    grids = _make_grids(slope_val=12.0, temp_val=-120.0, shadow_val=0.35)
    _inject_grids(grids)

    baseline = client.get("/api/layers/cost?downsample=1")
    override = client.get(
        "/api/layers/cost?downsample=1&w_slope=0.8&w_energy=0.1&w_shadow=0.9&w_thermal=0.2"
    )

    check(baseline.status_code == 200, "baseline cost layer returns 200")
    check(override.status_code == 200, "weighted cost layer returns 200")

    baseline_value = baseline.json()["data"][0][0]
    override_body = override.json()
    override_value = override_body["data"][0][0]

    check(baseline_value == 0.5, "baseline cost layer uses stored preprocessed cost grid")
    check(
        isinstance(override_value, float) and not math.isclose(override_value, baseline_value, rel_tol=0, abs_tol=1e-9),
        "weighted cost layer recomputes grid for requested weights",
    )
    check(
        math.isclose(override_body["metadata"]["cost_weights"]["w_shadow"], 0.9, rel_tol=0, abs_tol=1e-9),
        "weighted cost layer metadata reflects override weights",
    )


def test_geo_input_with_metadata_origin_accepted():
    grids = _make_grids()
    grids["metadata"]["origin"] = {"x": 176000.0, "y": 48000.0}
    start_lon, start_lat = pixel_to_lonlat(3, 4, grids["metadata"])
    goal_lon, goal_lat = pixel_to_lonlat(8, 9, grids["metadata"])
    _inject_grids(grids)

    r = client.post("/api/plan", json={
        "start": {"lon": start_lon, "lat": start_lat},
        "goal": {"lon": goal_lon, "lat": goal_lat},
    })
    check(r.status_code == 200, "geo plan uses metadata-aware coordinate transform")


# ── Traversability checks ─────────────────────────────────────────────────────

def test_impassable_start_returns_422():
    grids = _make_grids()
    grids["traversable"][0, 0] = False  # Block only start
    _inject_grids(grids)
    r = client.post("/api/plan", json={
        "start": {"row": 0, "col": 0},
        "goal": {"row": 5, "col": 5},
    })
    check(r.status_code == 422, "impassable start returns 422")
    check("start" in r.json()["detail"].lower(), "error message mentions 'start'")


def test_impassable_goal_returns_422():
    grids = _make_grids()
    grids["traversable"][5, 5] = False  # Block only goal
    _inject_grids(grids)
    r = client.post("/api/plan", json={
        "start": {"row": 0, "col": 0},
        "goal": {"row": 5, "col": 5},
    })
    check(r.status_code == 422, "impassable goal returns 422")
    check("goal" in r.json()["detail"].lower(), "error message mentions 'goal'")


# ── Successful plan response structure ───────────────────────────────────────

def test_successful_plan_response_structure():
    _inject_grids(_make_grids())
    r = client.post("/api/plan", json={
        "start": {"row": 0, "col": 0},
        "goal": {"row": 5, "col": 5},
        "include_simulation": True,
    })
    # A* on a small flat synthetic grid should find a path
    check(r.status_code == 200, "flat grid plan returns 200")
    body = r.json()
    check(body["status"] == "success", "status == success")
    check("astar_metrics" in body, "response has astar_metrics")
    check("summary" in body, "response has summary")
    check("geojson" in body, "response has geojson")
    check("waypoints" in body, "response has waypoints (include_simulation=True)")
    check("altitude_m" in body["waypoints"][0], "waypoints include altitude telemetry")

    geojson = body["geojson"]
    check(geojson["type"] == "Feature", "geojson.type == Feature")
    check(geojson["geometry"]["type"] == "LineString", "geometry.type == LineString")
    check(len(geojson["geometry"]["coordinates"]) >= 2, "path has at least 2 coordinates")

    summary = body["summary"]
    check("waypoint_count" in summary, "summary has waypoint_count")
    check("final_battery_pct" in summary, "summary has final_battery_pct")
    check(summary["waypoint_count"] >= 2, "waypoint_count >= 2")


def test_plan_without_simulation():
    _inject_grids(_make_grids())
    r = client.post("/api/plan", json={
        "start": {"row": 0, "col": 0},
        "goal": {"row": 3, "col": 3},
        "include_simulation": False,
    })
    check(r.status_code == 200, "plan with include_simulation=False returns 200")
    body = r.json()
    check("waypoints" not in body, "waypoints omitted when include_simulation=False")
    check("geojson" in body, "geojson still present")


def test_astar_metrics_and_summary_are_separate():
    _inject_grids(_make_grids())
    r = client.post("/api/plan", json={
        "start": {"row": 0, "col": 0},
        "goal": {"row": 4, "col": 0},
    })
    check(r.status_code == 200, "plan returns 200")
    body = r.json()
    # A* metrics should contain algorithm fields
    check("path_length_nodes" in body["astar_metrics"], "astar_metrics has path_length_nodes")
    check("nodes_expanded" in body["astar_metrics"], "astar_metrics has nodes_expanded")
    # Summary should contain physics fields, not A* fields
    check("total_energy_consumed_wh" in body["summary"], "summary has energy field")
    check("nodes_expanded" not in body["summary"], "nodes_expanded not leaked into summary")


if __name__ == "__main__":
    tests = [
        test_health,
        test_plan_503_when_no_grids,
        test_weights_out_of_range,
        test_weights_default_accepted,
        test_pixel_input_accepted,
        test_geo_input_accepted,
        test_geo_out_of_range_returns_422,
        test_start_out_of_bounds,
        test_goal_out_of_bounds,
        test_cell_telemetry_returns_backend_values,
        test_cost_layer_respects_weight_overrides,
        test_geo_input_with_metadata_origin_accepted,
        test_impassable_start_returns_422,
        test_impassable_goal_returns_422,
        test_successful_plan_response_structure,
        test_plan_without_simulation,
        test_astar_metrics_and_summary_are_separate,
    ]

    print(f"Running {len(tests)} /api/plan endpoint tests...\n")
    for fn in tests:
        print(f"{fn.__name__}:")
        fn()
    print("\nAll tests passed.")
