"""Pure bounded local-detour decisions for the ROS execution bridge."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence


@dataclass(frozen=True)
class MapPoint:
    x_m: float
    y_m: float


@dataclass(frozen=True)
class LocalObstacle:
    center: MapPoint
    radius_m: float
    confidence: float


@dataclass(frozen=True)
class LocalDecision:
    decision: str
    waypoints: tuple[MapPoint, ...]
    reason: str
    nearest_obstacle_m: float | None
    corridor_deviation_m: float


def _distance_to_segment(point: MapPoint, start: MapPoint, end: MapPoint) -> float:
    dx, dy = end.x_m - start.x_m, end.y_m - start.y_m
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return math.hypot(point.x_m - start.x_m, point.y_m - start.y_m)
    t = max(0.0, min(1.0, ((point.x_m - start.x_m) * dx + (point.y_m - start.y_m) * dy) / length_sq))
    return math.hypot(point.x_m - (start.x_m + t * dx), point.y_m - (start.y_m + t * dy))


def _nearest_segment(point: MapPoint, corridor: Sequence[MapPoint]) -> int:
    return min(
        range(len(corridor) - 1),
        key=lambda index: _distance_to_segment(point, corridor[index], corridor[index + 1]),
    )


def plan_local_detour(
    pose: MapPoint,
    corridor: Sequence[MapPoint],
    half_width_m: Sequence[float],
    obstacles: Sequence[LocalObstacle],
    *,
    rover_radius_m: float = 0.35,
    safety_margin_m: float = 0.25,
    min_confidence: float = 0.65,
) -> LocalDecision:
    """Make one bounded detour around observed obstacles on the active segment.

    The result only rejoins the next global-corridor waypoint. It is not a new
    global path search. When the corridor cannot contain a verified clearance,
    callers receive ``STOP_AND_REPLAN`` rather than a geometrically hopeful
    route through an obstacle.
    """
    if len(corridor) < 2 or len(half_width_m) != len(corridor) - 1:
        return LocalDecision("STOP_AND_REPLAN", (), "invalid or missing corridor", None, 0.0)
    if rover_radius_m < 0.0 or safety_margin_m < 0.0:
        raise ValueError("rover_radius_m and safety_margin_m must be non-negative")

    segment_index = _nearest_segment(pose, corridor)
    target = corridor[segment_index + 1]
    start = corridor[segment_index]
    clearance = rover_radius_m + safety_margin_m
    accepted = [obstacle for obstacle in obstacles if obstacle.confidence >= min_confidence]
    relevant = [
        obstacle
        for obstacle in accepted
        if _distance_to_segment(obstacle.center, pose, target) <= obstacle.radius_m + clearance
    ]
    if not relevant:
        return LocalDecision("FOLLOW", (), "no observed obstacle blocks active corridor", None, 0.0)

    blocking = min(relevant, key=lambda obstacle: _distance_to_segment(obstacle.center, pose, target))
    distance = _distance_to_segment(blocking.center, pose, target)
    available_lateral = float(half_width_m[segment_index]) - rover_radius_m - safety_margin_m
    required_lateral = blocking.radius_m + clearance
    if available_lateral <= 0.0 or required_lateral > available_lateral:
        return LocalDecision(
            "STOP_AND_REPLAN", (), "observed obstacle exceeds local corridor clearance", distance, 0.0
        )

    dx, dy = target.x_m - start.x_m, target.y_m - start.y_m
    length = math.hypot(dx, dy)
    if length == 0.0:
        return LocalDecision("STOP_AND_REPLAN", (), "zero-length active corridor segment", distance, 0.0)
    normal = (-dy / length, dx / length)
    # Start at the clearance boundary and grow the offset until both legs are
    # clear of every accepted observation; never leave the corridor budget.
    increments = 8
    for side in (-1.0, 1.0):
        for index in range(increments + 1):
            lateral = required_lateral + (available_lateral - required_lateral) * index / increments
            candidate = MapPoint(
                blocking.center.x_m + side * normal[0] * lateral,
                blocking.center.y_m + side * normal[1] * lateral,
            )
            if all(
                _distance_to_segment(obstacle.center, pose, candidate) > obstacle.radius_m + clearance
                and _distance_to_segment(obstacle.center, candidate, target) > obstacle.radius_m + clearance
                for obstacle in accepted
            ):
                return LocalDecision(
                    "LOCAL_DETOUR", (candidate, target), "bounded detour around LiDAR observation",
                    distance, lateral,
                )
    return LocalDecision(
        "STOP_AND_REPLAN", (), "no collision-free local detour within corridor", distance, 0.0
    )
