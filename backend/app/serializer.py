"""Coordinate transforms and response serialization for LunaPath.

Converts (row, col) grid pixels to WGS84 (lon, lat) via Lunar South Polar
Stereographic projection, and builds API-ready response structures.

No web-framework dependencies — fully standalone and testable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

import os

# PROJ enforces celestial-body matching by default; override for Moon→WGS84.
os.environ.setdefault("PROJ_IGNORE_CELESTIAL_BODY", "YES")

from pyproj import Transformer

if TYPE_CHECKING:
    from .simulation import RoverState

# ── Grid geometry constants ───────────────────────────────────────────────────
# Origin: top-left corner of the 500x500 window in Polar Stereo metres.
# Derived from window selection in process_lunar_data.py:
#   centre pixel (250, 250) maps to (176000, 48000) m.
ORIGIN_X_M: float = 176000.0 - 250 * 80.0   # = 156000.0
ORIGIN_Y_M: float = 48000.0  - 250 * 80.0   # = 28000.0
RESOLUTION_M: float = 80.0
GRID_ROWS: int = 500
GRID_COLS: int = 500

# ── Lunar South Polar Stereographic → WGS84 ──────────────────────────────────
_PROJ_MOON_SP: str = (
    "+proj=stere +lat_0=-90 +lon_0=0 +k=1 +R=1737400 +units=m"
)

# Module-level singletons — created once at import time.
_fwd: Transformer = Transformer.from_crs(_PROJ_MOON_SP, "EPSG:4326", always_xy=True)
_inv: Transformer = Transformer.from_crs("EPSG:4326", _PROJ_MOON_SP, always_xy=True)

# Sanity-check threshold: all valid grid pixels should be south of -80° lat.
_LAT_SOUTH_THRESHOLD: float = -80.0


# ── Coordinate transforms ─────────────────────────────────────────────────────

def pixel_to_lonlat(row: int, col: int) -> tuple[float, float]:
    """Convert grid (row, col) to WGS84 (lon, lat).

    Returns
    -------
    tuple[float, float]
        (longitude, latitude) in decimal degrees.

    Raises
    ------
    ValueError
        If the resulting latitude is north of -80° (not in the lunar south
        pole region), indicating a bad origin constant or out-of-range pixel.
    """
    x_m = ORIGIN_X_M + col * RESOLUTION_M
    y_m = ORIGIN_Y_M + row * RESOLUTION_M
    lon, lat = _fwd.transform(x_m, y_m)
    if lat > _LAT_SOUTH_THRESHOLD:
        raise ValueError(
            f"Projection sanity check failed: lat={lat:.4f} is not in the "
            f"lunar south pole region (expected < {_LAT_SOUTH_THRESHOLD}). "
            f"Pixel ({row}, {col}) may be out of the valid grid window."
        )
    return float(lon), float(lat)


def lonlat_to_pixel(lon: float, lat: float) -> tuple[int, int]:
    """Convert WGS84 (lon, lat) to the nearest grid (row, col).

    Used to map a Leaflet map click to grid coordinates.

    Raises
    ------
    ValueError
        If the point falls outside the 500x500 grid boundary.
    """
    x_m, y_m = _inv.transform(lon, lat)
    col_f = (x_m - ORIGIN_X_M) / RESOLUTION_M
    row_f = (y_m - ORIGIN_Y_M) / RESOLUTION_M
    row_i = int(round(row_f))
    col_i = int(round(col_f))
    if not (0 <= row_i < GRID_ROWS and 0 <= col_i < GRID_COLS):
        raise ValueError(
            f"({lon:.6f}, {lat:.6f}) maps to ({row_i}, {col_i}), "
            f"which is outside the {GRID_ROWS}x{GRID_COLS} grid."
        )
    return row_i, col_i


# ── Simulation serializers ────────────────────────────────────────────────────

def states_to_geojson(states: "List[RoverState]") -> dict:
    """Serialize a simulated path to a GeoJSON Feature (LineString).

    Coordinates follow the Leaflet/GeoJSON standard: [longitude, latitude].

    Returns
    -------
    dict
        GeoJSON Feature with LineString geometry and summary properties.
    """
    coordinates = []
    for s in states:
        lon, lat = pixel_to_lonlat(s.row, s.col)
        coordinates.append([round(lon, 6), round(lat, 6)])

    total_cost = round(states[-1].cumulative_cost, 4) if states else 0.0

    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates,
        },
        "properties": {
            "total_cost": total_cost,
            "waypoint_count": len(states),
        },
    }


def states_to_waypoints(states: "List[RoverState]") -> list[dict]:
    """Serialize each RoverState to a flat dict for frontend animation.

    The returned list is index-aligned with the path: ``waypoints[i]``
    corresponds to path step ``i``.

    Returns
    -------
    list[dict]
        One dict per waypoint with coordinates and telemetry fields.
    """
    waypoints: list[dict] = []
    for s in states:
        lon, lat = pixel_to_lonlat(s.row, s.col)
        waypoints.append({
            "step": s.step,
            "row": s.row,
            "col": s.col,
            "lon": round(lon, 6),
            "lat": round(lat, 6),
            "battery_pct": round(s.battery_pct, 2),
            "risk_level": s.risk_level,
            "slope_deg": round(s.slope_deg, 2),
            "surface_temp_c": round(s.surface_temp_c, 2),
            "shadow_ratio": round(s.shadow_ratio, 3),
            "node_cost": round(s.node_cost, 4),
            "elapsed_hours": round(s.elapsed_hours, 4),
            "distance_m": round(s.distance_m, 2),
            "step_energy_wh": round(s.step_energy_wh, 4),
        })
    return waypoints


def build_plan_response(
    astar_result: dict,
    states: "List[RoverState]",
    summary: dict,
    include_simulation: bool = True,
) -> dict:
    """Assemble the final API response for a single plan request.

    Keeps A* algorithm metrics and physics simulation summary separate
    because they measure different concerns.

    Parameters
    ----------
    astar_result : dict
        Raw output from ``pathfinder.astar()``.
    states : List[RoverState]
        Output from ``simulation.simulate_path()``.
    summary : dict
        Output from ``simulation.summarize_simulation()``.
    include_simulation : bool
        When False, the ``waypoints`` array is omitted for a lighter response.

    Returns
    -------
    dict
        ``{status, astar_metrics, summary, geojson[, waypoints]}``
    """
    response: dict = {
        "status": "success",
        "astar_metrics": astar_result.get("metrics", {}),
        "summary": summary,
        "geojson": states_to_geojson(states),
    }
    if include_simulation:
        response["waypoints"] = states_to_waypoints(states)
    return response
