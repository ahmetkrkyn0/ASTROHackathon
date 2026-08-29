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
