"""Coordinate transforms and response serialization for LunaPath.

Converts (row, col) grid pixels to WGS84 (lon, lat) via Lunar South Polar
Stereographic projection, and builds API-ready response structures.

No web-framework dependencies — fully standalone and testable.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, List

# PROJ enforces celestial-body matching by default; override for Moon→WGS84.
os.environ.setdefault("PROJ_IGNORE_CELESTIAL_BODY", "YES")

from pyproj import Transformer

if TYPE_CHECKING:
    from .simulation import RoverState

# ── Grid geometry fallback ────────────────────────────────────────────────────
# These are the LAST RESORT, used only when a caller passes no metadata.
# Every production path carries a real origin from metadata.json, and
# _resolve_grid_geometry prefers it.
#
# They used to be hardcoded to a window that no longer exists: a comment
# derived them from "centre pixel (250, 250) maps to (176000, 48000) m" at
# 80 m/px, while the shipped grid at the time was origin (-15500, -4000) at
# 5 m/px. The numbers were wrong AND the comment presented the derivation as
# current, so anyone reading it to understand the grid was reading about a
# different site. They are now READ from the shipped metadata at import
# time, so they cannot drift from the grids again, with the literals below
# as the fallback's own fallback. (Round 3 review, L-7.)
#
# That drift is exactly why these are read, not trusted: the shipped window
# has since moved again, from Site01 (-15500, -4000) to the current Site11
# working window (-40000, 15500). The literals track the current window so a metadata-less caller
# lands on the right site, but nothing in production depends on them.
#
# The y term is subtracted per row because rows increase southward, so the
# origin (row 0) is the window's NORTH edge -- the convention grid_frame
# defines and process_lunar_data writes. (Round 2 review, L-1.)
_FALLBACK_ORIGIN_X_M: float = -40000.0
_FALLBACK_ORIGIN_Y_M: float = 15500.0
_FALLBACK_RESOLUTION_M: float = 5.0
_FALLBACK_ROWS: int = 500
_FALLBACK_COLS: int = 500


def _shipped_geometry() -> tuple[float, float, float, int, int]:
    """Grid geometry from the shipped metadata.json, or the literals above.

    Read once at import. A missing or malformed file is not an error here --
    it only means the no-metadata fallback uses the literals instead.
    """
    import json

    candidate = (
        Path(__file__).resolve().parent.parent.parent
        / "lunapath"
        / "data"
        / "processed"
        / "metadata.json"
    )
    try:
        meta = json.loads(candidate.read_text(encoding="utf-8"))
        origin = meta["origin"]
        shape = meta["shape"]
        return (
            float(origin["x"]),
            float(origin["y"]),
            float(meta["resolution_m"]),
            int(shape[0]),
            int(shape[1]),
        )
    except Exception:
        return (
            _FALLBACK_ORIGIN_X_M,
            _FALLBACK_ORIGIN_Y_M,
            _FALLBACK_RESOLUTION_M,
            _FALLBACK_ROWS,
            _FALLBACK_COLS,
        )


(
    ORIGIN_X_M,
    ORIGIN_Y_M,
    RESOLUTION_M,
    GRID_ROWS,
    GRID_COLS,
) = _shipped_geometry()

# ── Lunar South Polar Stereographic → WGS84 ──────────────────────────────────
_PROJ_MOON_SP: str = (
    "+proj=stere +lat_0=-90 +lon_0=0 +k=1 +R=1737400 +units=m"
)

# Module-level singletons — created once at import time.
_fwd: Transformer = Transformer.from_crs(_PROJ_MOON_SP, "EPSG:4326", always_xy=True)
_inv: Transformer = Transformer.from_crs("EPSG:4326", _PROJ_MOON_SP, always_xy=True)

# Sanity-check threshold: all valid grid pixels should be south of -80° lat.
_LAT_SOUTH_THRESHOLD: float = -80.0


def _resolve_grid_geometry(metadata: dict[str, Any] | None = None) -> tuple[float, float, float, int, int]:
    origin = metadata.get("origin") if metadata else None
    origin_x = float(origin.get("x", ORIGIN_X_M)) if isinstance(origin, dict) else ORIGIN_X_M
    origin_y = float(origin.get("y", ORIGIN_Y_M)) if isinstance(origin, dict) else ORIGIN_Y_M
    resolution_m = float(metadata.get("resolution_m", RESOLUTION_M)) if metadata else RESOLUTION_M

    shape = metadata.get("shape") if metadata else None
    if (
        isinstance(shape, (list, tuple))
        and len(shape) >= 2
        and all(isinstance(value, (int, float)) for value in shape[:2])
    ):
        rows = int(shape[0])
        cols = int(shape[1])
    else:
        rows = GRID_ROWS
        cols = GRID_COLS

    return origin_x, origin_y, resolution_m, rows, cols


# ── Coordinate transforms ─────────────────────────────────────────────────────

def pixel_to_lonlat(
    row: int,
    col: int,
    metadata: dict[str, Any] | None = None,
) -> tuple[float, float]:
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
    origin_x, origin_y, resolution_m, _, _ = _resolve_grid_geometry(metadata)
    x_m = origin_x + col * resolution_m
    # origin_y is the top edge of the window and rows increase southward, so
    # the row term is subtracted -- the same convention as
    # process_lunar_data.window_center_latlon and corridor._pixel_to_metres.
    # (Faz 2 review, C2. Faz 1 had flagged this line as a known-unfixed bug.)
    y_m = origin_y - row * resolution_m
    lon, lat = _fwd.transform(x_m, y_m)
    if lat > _LAT_SOUTH_THRESHOLD:
        raise ValueError(
            f"Projection sanity check failed: lat={lat:.4f} is not in the "
            f"lunar south pole region (expected < {_LAT_SOUTH_THRESHOLD}). "
            f"Pixel ({row}, {col}) may be out of the valid grid window."
        )
    return float(lon), float(lat)


def lonlat_to_pixel(
    lon: float,
    lat: float,
    metadata: dict[str, Any] | None = None,
) -> tuple[int, int]:
    """Convert WGS84 (lon, lat) to the nearest grid (row, col).

    Used to map a Leaflet map click to grid coordinates.

    Raises
    ------
    ValueError
        If the point falls outside the 500x500 grid boundary.
    """
    origin_x, origin_y, resolution_m, rows, cols = _resolve_grid_geometry(metadata)
    x_m, y_m = _inv.transform(lon, lat)
    col_f = (x_m - origin_x) / resolution_m
    # Inverse of pixel_to_lonlat's y_m = origin_y - row * resolution_m.
    row_f = (origin_y - y_m) / resolution_m
    row_i = int(round(row_f))
    col_i = int(round(col_f))
    if not (0 <= row_i < rows and 0 <= col_i < cols):
        raise ValueError(
            f"({lon:.6f}, {lat:.6f}) maps to ({row_i}, {col_i}), "
            f"which is outside the {rows}x{cols} grid."
        )
    return row_i, col_i


# ── Simulation serializers ────────────────────────────────────────────────────

def states_to_geojson(
    states: "List[RoverState]",
    metadata: dict[str, Any] | None = None,
) -> dict:
    """Serialize a simulated path to a GeoJSON Feature (LineString).

    Coordinates follow the Leaflet/GeoJSON standard: [longitude, latitude].

    Returns
    -------
    dict
        GeoJSON Feature with LineString geometry and summary properties.
    """
    coordinates = []
    for s in states:
        lon, lat = pixel_to_lonlat(s.row, s.col, metadata)
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


def states_to_waypoints(
    states: "List[RoverState]",
    metadata: dict[str, Any] | None = None,
    elevation_grid: Any | None = None,
) -> list[dict]:
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
        lon, lat = pixel_to_lonlat(s.row, s.col, metadata)
        altitude_m = None
        if elevation_grid is not None:
            altitude_value = float(elevation_grid[s.row, s.col])
            if math.isfinite(altitude_value):
                altitude_m = round(altitude_value, 2)
        waypoints.append({
            "step": s.step,
            "row": s.row,
            "col": s.col,
            "lon": round(lon, 6),
            "lat": round(lat, 6),
            "altitude_m": altitude_m,
            "battery_pct": round(s.battery_pct, 2),
            "recharge_count": s.recharge_count,
            "recharged_this_step": s.recharged_this_step,
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
    metadata: dict[str, Any] | None = None,
    elevation_grid: Any | None = None,
    rover_id: str | None = None,
    rover_name: str | None = None,
    corridor: dict[str, Any] | None = None,
    route_statistics: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
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
        "geojson": states_to_geojson(states, metadata),
        "corridor": corridor,
        "route_statistics": route_statistics,
        # How much of the planned route the rover can actually execute.
        # `astar_metrics` describes what the PLANNER found; `summary` and
        # `geojson` describe what the SIMULATION could drive, and when a
        # traverse strands those are different journeys. Nothing said so
        # except a `stranded` flag three levels down. (Round 4 review, M-3.)
        "execution": execution,
    }
    if rover_id is not None:
        response["rover"] = {
            "id": rover_id,
            "name": rover_name or rover_id,
        }
    if include_simulation:
        response["waypoints"] = states_to_waypoints(states, metadata, elevation_grid)
    return response
