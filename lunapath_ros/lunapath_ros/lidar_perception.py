"""ROS-independent clustering for candidate LiDAR obstacle returns.

Input points must already be expressed in the rover base frame. The caller is
responsible for transforming the point cloud and must not pass a simulator's
object identifiers through this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class LidarPoint:
    x_m: float
    y_m: float
    z_m: float


@dataclass(frozen=True)
class ObstacleCluster:
    x_m: float
    y_m: float
    radius_m: float
    confidence: float
    point_count: int


def cluster_obstacle_returns(
    points: Iterable[LidarPoint],
    *,
    min_height_m: float = 0.12,
    max_range_m: float = 12.0,
    cluster_radius_m: float = 0.35,
    min_points: int = 3,
) -> list[ObstacleCluster]:
    """Cluster finite, above-ground LiDAR points into anonymous obstacles.

    A deliberately small O(n²) flood fill is used because this node operates
    on the sparse, range-limited obstacle candidates of one rover, not a map
    reconstruction cloud. It avoids a scipy/PCL dependency in the flight
    boundary and makes the exact confidence policy easy to audit.
    """
    if min_points < 1 or max_range_m <= 0.0 or cluster_radius_m <= 0.0:
        raise ValueError("invalid LiDAR clustering thresholds")

    candidates = [
        point
        for point in points
        if all(math.isfinite(value) for value in (point.x_m, point.y_m, point.z_m))
        and point.z_m >= min_height_m
        and math.hypot(point.x_m, point.y_m) <= max_range_m
    ]
    visited = [False] * len(candidates)
    clusters: list[ObstacleCluster] = []

    for seed in range(len(candidates)):
        if visited[seed]:
            continue
        visited[seed] = True
        members = [seed]
        queue = [seed]
        while queue:
            current = queue.pop()
            point = candidates[current]
            for other_index, other in enumerate(candidates):
                if visited[other_index]:
                    continue
                if math.hypot(point.x_m - other.x_m, point.y_m - other.y_m) <= cluster_radius_m:
                    visited[other_index] = True
                    queue.append(other_index)
                    members.append(other_index)

        if len(members) < min_points:
            continue
        group = [candidates[index] for index in members]
        x = sum(point.x_m for point in group) / len(group)
        y = sum(point.y_m for point in group) / len(group)
        radius = max(math.hypot(point.x_m - x, point.y_m - y) for point in group)
        # More mutually-consistent returns raise confidence; a compact group
        # reaches 1 sooner than a diffuse cluster of the same cardinality.
        compactness = 1.0 / (1.0 + radius / cluster_radius_m)
        density = min(1.0, len(group) / float(min_points * 3))
        clusters.append(
            ObstacleCluster(x, y, radius, density * compactness, len(group))
        )
    return clusters
