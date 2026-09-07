"""Pure LiDAR cluster tests; the ROS/TF shell stays thin."""

from __future__ import annotations

import pytest

from lunapath_ros.lidar_perception import LidarPoint, cluster_obstacle_returns


def test_clusters_only_above_ground_returns_inside_the_sensor_range():
    clusters = cluster_obstacle_returns(
        [
            LidarPoint(1.0, 1.0, 0.30),
            LidarPoint(1.1, 1.0, 0.35),
            LidarPoint(1.0, 1.1, 0.32),
            LidarPoint(1.0, 1.0, 0.01),  # ground: discarded
            LidarPoint(99.0, 0.0, 1.0),  # out of range: discarded
        ],
        min_height_m=0.12,
        cluster_radius_m=0.25,
        min_points=3,
    )
    assert len(clusters) == 1
    assert clusters[0].point_count == 3
    assert clusters[0].x_m == pytest.approx(1.033, abs=0.001)


def test_sparse_or_separate_returns_do_not_become_obstacles():
    clusters = cluster_obstacle_returns(
        [LidarPoint(1.0, 0.0, 0.3), LidarPoint(4.0, 0.0, 0.3)],
        min_points=2,
        cluster_radius_m=0.2,
    )
    assert clusters == []


def test_bad_thresholds_are_rejected_not_silently_normalized():
    with pytest.raises(ValueError):
        cluster_obstacle_returns([], cluster_radius_m=0.0)
