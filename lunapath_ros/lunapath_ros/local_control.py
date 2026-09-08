"""Pure, conservative waypoint-following primitives for the ROS bridge.

This module deliberately knows nothing about ROS messages or motors. It is
therefore unit-testable without a robot, and the ROS node is only responsible
for converting messages at its boundary. It never commands reverse motion:
if the rover is not pointing sufficiently near the target, it turns in place.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence


@dataclass(frozen=True)
class ControlLimits:
    max_linear_m_s: float = 0.15
    max_angular_rad_s: float = 0.45
    heading_gain: float = 1.2
    position_gain: float = 0.4
    align_before_drive_rad: float = 0.35
    waypoint_tolerance_m: float = 0.20


@dataclass(frozen=True)
class Pose2D:
    x_m: float
    y_m: float
    heading_rad: float


@dataclass(frozen=True)
class TwistCommand:
    linear_m_s: float
    angular_rad_s: float


@dataclass(frozen=True)
class ControlStep:
    command: TwistCommand
    next_waypoint_index: int
    complete: bool


def wrap_angle_rad(angle: float) -> float:
    """Return *angle* in [-pi, pi)."""
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def _clamp(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def step_local_route(
    pose: Pose2D,
    waypoints: Sequence[tuple[float, float]],
    next_waypoint_index: int,
    limits: ControlLimits = ControlLimits(),
) -> ControlStep:
    """Advance passed targets and calculate the next conservative command.

    ``next_waypoint_index`` is carried by the caller so an explicit new local
    plan cannot accidentally continue an old route. Empty, exhausted, or
    malformed indices always yield a zero command.
    """
    index = max(0, int(next_waypoint_index))
    while index < len(waypoints):
        target_x, target_y = waypoints[index]
        if math.hypot(target_x - pose.x_m, target_y - pose.y_m) > limits.waypoint_tolerance_m:
            break
        index += 1

    if index >= len(waypoints):
        return ControlStep(TwistCommand(0.0, 0.0), index, True)

    target_x, target_y = waypoints[index]
    distance = math.hypot(target_x - pose.x_m, target_y - pose.y_m)
    bearing = math.atan2(target_y - pose.y_m, target_x - pose.x_m)
    heading_error = wrap_angle_rad(bearing - pose.heading_rad)
    angular = _clamp(limits.heading_gain * heading_error, limits.max_angular_rad_s)

    # Turning in place makes the controller fail closed for a route that is
    # behind the rover, and avoids cutting a local-obstacle clearance corner.
    linear = 0.0
    if abs(heading_error) <= limits.align_before_drive_rad:
        linear = min(limits.max_linear_m_s, limits.position_gain * distance)
    return ControlStep(TwistCommand(linear, angular), index, False)
