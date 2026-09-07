"""The ROS action may learn only LiDAR observations, never scene truth."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from app.grid_frame import pixel_to_map_xy
from lunapath_ros.observed_obstacle_grid import with_observed_obstacles


def _grids():
    return {
        "traversable": np.ones((5, 5), dtype=bool),
        "metadata": {
            "origin": {"x": 0.0, "y": 0.0},
            "resolution_m": 1.0,
            "shape": [5, 5],
        },
    }


def _obstacle(x, y, radius=1.0, confidence=0.9, source="lidar"):
    return SimpleNamespace(
        center=SimpleNamespace(x=x, y=y), radius_m=radius,
        confidence=confidence, source=source,
    )


def test_confirmed_lidar_obstacle_blocks_its_map_cell_but_not_live_start():
    base = _grids()
    x, y = pixel_to_map_xy(2, 2, base["metadata"])
    grids, count = with_observed_obstacles(base, [_obstacle(x, y)], (2, 2))
    assert count == 1
    assert grids["traversable"][2, 2]
    assert not grids["traversable"][2, 1]


def test_unconfirmed_or_non_lidar_input_cannot_change_the_global_replan_grid():
    base = _grids()
    x, y = pixel_to_map_xy(2, 2, base["metadata"])
    grids, count = with_observed_obstacles(
        base, [_obstacle(x, y, confidence=0.2), _obstacle(x, y, source="mesh")], (0, 0)
    )
    assert count == 0
    assert grids["traversable"].all()
