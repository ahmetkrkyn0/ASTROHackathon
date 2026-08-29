"""conversions.py tests -- run under `colcon test`, no running ROS graph needed.

These only need the message PACKAGES importable, not a node or a daemon, so
they are cheap. They exist because the previous revision of this plan left
the ROS side with zero automated coverage and verified the publisher by eye
in RViz -- exactly the gap that let Faz 3's real-grid failures hide behind a
toy fixture. (Faz 4 revision, R10.)
"""

from __future__ import annotations

import numpy as np
import pytest

from builtin_interfaces.msg import Time
from geometry_msgs.msg import PoseStamped

from lunapath_ros.conversions import (
    LAYER_NAMES,
    corridor_to_msg,
    grids_to_grid_map,
    pixels_to_path,
    pose_to_pixel,
    weights_msg_to_dict,
)

# Non-square on purpose: a square fixture hides a swapped size_x/size_y.
ROWS, COLS = 4, 6
METADATA = {
    "origin": {"x": 1000.0, "y": 500.0},
    "resolution_m": 10.0,
    "shape": [ROWS, COLS],
    "crs": "test",
}


def _grids() -> dict:
    return {
        "elevation": np.arange(ROWS * COLS, dtype=np.float64).reshape(ROWS, COLS),
        "slope": np.zeros((ROWS, COLS)),
        "aspect": np.zeros((ROWS, COLS)),
        "thermal": np.full((ROWS, COLS), -60.0),
        "shadow_ratio": np.zeros((ROWS, COLS)),
        "traversable": np.ones((ROWS, COLS), dtype=bool),
        "cost": np.full((ROWS, COLS), 0.3),
        "metadata": METADATA,
    }


def _stamp() -> Time:
    return Time(sec=0, nanosec=0)


def test_grid_map_carries_every_layer_with_the_spec_names():
    message = grids_to_grid_map(_grids(), "moon_map", _stamp())
    assert message.layers == list(LAYER_NAMES.values())
    assert len(message.data) == len(message.layers)


def test_grid_map_info_matches_the_metadata_extent():
    message = grids_to_grid_map(_grids(), "moon_map", _stamp())
    assert message.info.resolution == pytest.approx(10.0)
    assert message.info.length_x == pytest.approx(COLS * 10.0)
    assert message.info.length_y == pytest.approx(ROWS * 10.0)


def test_grid_map_layout_sizes_are_not_swapped():
    """size_x/size_y swapped is invisible on a square grid; assert it here."""
    message = grids_to_grid_map(_grids(), "moon_map", _stamp())
    dims = message.data[0].layout.dim
    assert [d.label for d in dims] == ["column_index", "row_index"]
    assert dims[0].size == ROWS
    assert dims[1].size == COLS
    assert len(message.data[0].data) == ROWS * COLS


def test_blocked_cost_cells_become_nan_not_inf():
    grids = _grids()
    grids["cost"] = np.full((ROWS, COLS), np.inf)
    message = grids_to_grid_map(grids, "moon_map", _stamp())
    cost_index = message.layers.index("cost")
    assert all(np.isnan(v) for v in message.data[cost_index].data)


def test_path_poses_are_in_map_metres_and_row_axis_points_south():
    path = pixels_to_path([(0, 0), (1, 0)], METADATA, "moon_map", _stamp())
    assert path.header.frame_id == "moon_map"
    assert path.poses[0].pose.position.x == pytest.approx(1000.0)
    assert path.poses[0].pose.position.y == pytest.approx(500.0)
    assert path.poses[1].pose.position.y < path.poses[0].pose.position.y


def test_pose_to_pixel_round_trips_through_pixels_to_path():
    path = pixels_to_path([(2, 3)], METADATA, "moon_map", _stamp())
    assert pose_to_pixel(path.poses[0], METADATA) == (2, 3)


def test_pose_to_pixel_rejects_an_off_grid_pose():
    pose = PoseStamped()
    pose.pose.position.x = 1.0e9
    pose.pose.position.y = 1.0e9
    with pytest.raises(ValueError):
        pose_to_pixel(pose, METADATA)


def test_weights_msg_to_dict_uses_the_cost_engine_key_names():
    class _W:
        w_slope, w_energy, w_shadow, w_thermal = 0.4, 0.3, 0.2, 0.1

    assert weights_msg_to_dict(_W()) == {
        "w_slope": pytest.approx(0.4),
        "w_energy": pytest.approx(0.3),
        "w_shadow": pytest.approx(0.2),
        "w_thermal": pytest.approx(0.1),
    }


def test_corridor_msg_maps_the_capital_k_field():
    corridor = {
        "crs": "test",
        "waypoints": [(0.0, 0.0), (1.0, 1.0)],
        "fallback_points": [(0.0, 0.0), (1.0, 1.0)],
        "half_width_m": [5.0],
        "max_slope_deg": [3.0],
        "energy_budget_wh": [1.0],
        "thermal_budget_K_s": [2.0],
    }
    message = corridor_to_msg(corridor)
    assert list(message.thermal_budget_k_s) == pytest.approx([2.0])
    assert len(message.waypoints) == 2
    assert len(message.half_width_m) == len(message.waypoints) - 1
