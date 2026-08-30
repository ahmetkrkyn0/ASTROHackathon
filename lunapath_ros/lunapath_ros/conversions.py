"""ROS message assembly. All geometry lives in app.grid_frame.

This module needs a ROS installation (it imports message packages), so it is
tested under `colcon test`, not by backend/pytest. The geometry it depends on
is tested without ROS in backend/test_grid_frame.py.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from geometry_msgs.msg import Point, PoseStamped
from grid_map_msgs.msg import GridMap, GridMapInfo
from nav_msgs.msg import Path
from std_msgs.msg import Float32MultiArray, MultiArrayDimension, MultiArrayLayout

from app.grid_frame import (
    grid_map_info,
    map_xy_to_pixel,
    pixel_to_map_xy,
    to_multiarray_layout,
)

# LunaPath grid key -> grid_map layer name (spec §4.4 table)
LAYER_NAMES: dict[str, str] = {
    "elevation": "elevation",
    "slope": "slope",
    "aspect": "aspect",
    "thermal": "temperature",
    "shadow_ratio": "illumination",
    "traversable": "traversability",
    "cost": "cost",
}


def _float32_multiarray(array: np.ndarray) -> Float32MultiArray:
    dims, flat = to_multiarray_layout(array)
    message = Float32MultiArray()
    message.layout = MultiArrayLayout(
        dim=[
            MultiArrayDimension(label=label, size=size, stride=stride)
            for label, size, stride in dims
        ],
        data_offset=0,
    )
    message.data = flat.tolist()
    return message


def grids_to_grid_map(
    grids: dict[str, Any],
    frame_id: str,
    stamp,
    layers: dict[str, str] | None = None,
) -> GridMap:
    """Pack LunaPath layers into one grid_map_msgs/GridMap."""
    metadata = grids["metadata"]
    geometry = grid_map_info(metadata)
    selected = layers or LAYER_NAMES

    message = GridMap()
    message.header.frame_id = frame_id
    message.header.stamp = stamp

    info = GridMapInfo()
    info.resolution = float(geometry["resolution"])
    info.length_x = float(geometry["length_x"])
    info.length_y = float(geometry["length_y"])
    info.pose.position.x = float(geometry["pose_x"])
    info.pose.position.y = float(geometry["pose_y"])
    info.pose.orientation.w = 1.0
    message.info = info

    for grid_key, layer_name in selected.items():
        if grid_key not in grids:
            continue
        array = np.asarray(grids[grid_key], dtype=np.float32)
        # grid_map's no-data value is NaN. The cost layer is +inf on blocked
        # cells and RViz renders inf as a solid spike, so map every
        # non-finite value on to NaN.
        array = np.where(np.isfinite(array), array, np.nan)
        message.layers.append(layer_name)
        message.data.append(_float32_multiarray(array))

    message.basic_layers = [
        name for name in ("elevation", "traversability") if name in message.layers
    ]
    message.outer_start_index = 0
    message.inner_start_index = 0
    return message


def pixels_to_path(
    path_pixels: list[tuple[int, int]],
    metadata: dict[str, Any],
    frame_id: str,
    stamp,
) -> Path:
    """LunaPath pixel path -> nav_msgs/Path in the map frame."""
    path = Path()
    path.header.frame_id = frame_id
    path.header.stamp = stamp
    for row, col in path_pixels:
        x, y = pixel_to_map_xy(int(row), int(col), metadata)
        pose = PoseStamped()
        pose.header = path.header
        pose.pose.position.x = float(x)
        pose.pose.position.y = float(y)
        pose.pose.orientation.w = 1.0
        path.poses.append(pose)
    return path


def pose_to_pixel(pose: PoseStamped, metadata: dict[str, Any]) -> tuple[int, int]:
    """map-frame pose -> (row, col). Raises ValueError when off-grid."""
    return map_xy_to_pixel(pose.pose.position.x, pose.pose.position.y, metadata)


def weights_msg_to_dict(weights) -> dict[str, float]:
    """lunapath_msgs/MissionWeights -> the dict app.cost_engine expects."""
    return {
        "w_slope": float(weights.w_slope),
        "w_energy": float(weights.w_energy),
        "w_shadow": float(weights.w_shadow),
        "w_thermal": float(weights.w_thermal),
    }


def corridor_to_msg(corridor: dict[str, Any]):
    """backend Corridor dict -> lunapath_msgs/Corridor.

    Note the one field-name change: the core calls it ``thermal_budget_K_s``
    (capital K, a unit symbol) but ROS IDL requires lower snake_case.
    """
    from lunapath_msgs.msg import Corridor as CorridorMsg

    message = CorridorMsg()
    message.crs = str(corridor.get("crs", "unknown"))
    message.waypoints = [
        Point(x=float(x), y=float(y), z=0.0) for x, y in corridor["waypoints"]
    ]
    message.fallback_points = [
        Point(x=float(x), y=float(y), z=0.0) for x, y in corridor["fallback_points"]
    ]
    message.half_width_m = [float(v) for v in corridor["half_width_m"]]
    message.max_slope_deg = [float(v) for v in corridor["max_slope_deg"]]
    message.energy_budget_wh = [float(v) for v in corridor["energy_budget_wh"]]
    message.thermal_budget_k_s = [float(v) for v in corridor["thermal_budget_K_s"]]
    return message


def msg_to_corridor(message) -> dict[str, Any]:
    """lunapath_msgs/Corridor -> the dict app.schemas.Corridor validates.

    Inverse of :func:`corridor_to_msg`, including the one field-name
    mapping back (``thermal_budget_k_s`` -> ``thermal_budget_K_s``).
    Returned as a plain dict so this module stays importable without
    pydantic; the caller validates with ``Corridor(**result)``.
    """
    return {
        "crs": str(message.crs),
        "waypoints": [(float(p.x), float(p.y)) for p in message.waypoints],
        "fallback_points": [
            (float(p.x), float(p.y)) for p in message.fallback_points
        ],
        "half_width_m": [float(v) for v in message.half_width_m],
        "max_slope_deg": [float(v) for v in message.max_slope_deg],
        "energy_budget_wh": [float(v) for v in message.energy_budget_wh],
        "thermal_budget_K_s": [float(v) for v in message.thermal_budget_k_s],
    }


def odometry_to_pose_estimate(
    message,
    source: str,
    distance_travelled_m: float,
    fallback_covariance_m: float | None = None,
) -> dict[str, Any]:
    """nav_msgs/Odometry -> the dict app.pose.PoseEstimate validates.

    The heading comes from ``app.pose.quaternion_to_grid_heading_deg`` --
    the single tested home of the REP-103-yaw-to-grid-compass conversion;
    nothing here re-derives it.

    ``distance_travelled_m`` is supplied by the caller because Odometry
    carries pose and twist but no cumulative distance; the subscribing
    node integrates displacement between messages and passes the total.

    Covariance: ``pose.covariance`` is the 6x6 row-major matrix, so
    var_x = [0], var_y = [7], var_yaw = [35]. The horizontal 1-sigma is
    the sqrt of the LARGER of var_x and var_y -- the conservative axis --
    because check_localization_uncertainty compares a single number
    against the corridor half-width and the ellipse's long axis is what
    leaves the corridor first. A negative variance is the ROS convention
    for "unknown"; unknown is not zero, so it maps to
    *fallback_covariance_m* when given and raises otherwise, rather than
    laundering ignorance into confidence.
    """
    from app.pose import quaternion_to_grid_heading_deg

    position = message.pose.pose.position
    orientation = message.pose.pose.orientation
    covariance = message.pose.covariance

    var_x, var_y, var_yaw = (
        float(covariance[0]),
        float(covariance[7]),
        float(covariance[35]),
    )
    if var_x < 0.0 or var_y < 0.0:
        if fallback_covariance_m is None:
            raise ValueError(
                "odometry reports unknown position covariance (negative "
                "variance) and no fallback_covariance_m is configured; "
                "refusing to invent confidence"
            )
        covariance_m = float(fallback_covariance_m)
    else:
        covariance_m = float(np.sqrt(max(var_x, var_y)))

    heading_covariance_deg = (
        float(np.degrees(np.sqrt(var_yaw))) if var_yaw >= 0.0 else 180.0
    )

    stamp = message.header.stamp
    timestamp_s = float(stamp.sec) + float(stamp.nanosec) * 1e-9
    from datetime import datetime, timezone

    timestamp_utc = datetime.fromtimestamp(timestamp_s, tz=timezone.utc).isoformat()

    return {
        "x_m": float(position.x),
        "y_m": float(position.y),
        "heading_deg": quaternion_to_grid_heading_deg(
            float(orientation.x),
            float(orientation.y),
            float(orientation.z),
            float(orientation.w),
        ),
        "covariance_m": covariance_m,
        "heading_covariance_deg": heading_covariance_deg,
        "timestamp_utc": timestamp_utc,
        "source": str(source),
        "distance_travelled_m": float(distance_travelled_m),
    }
