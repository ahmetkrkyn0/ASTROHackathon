"""Pure local-control tests: no ROS daemon or motor hardware required."""

from __future__ import annotations

import math

import pytest

from lunapath_ros.local_control import ControlLimits, Pose2D, step_local_route, wrap_angle_rad


def test_wrap_angle_has_a_single_canonical_range():
    assert wrap_angle_rad(3.0 * math.pi) == pytest.approx(-math.pi)
    assert wrap_angle_rad(-3.0 * math.pi) == pytest.approx(-math.pi)


def test_controller_turns_in_place_before_driving_at_a_sharp_heading_error():
    step = step_local_route(Pose2D(0.0, 0.0, 0.0), [(0.0, 2.0)], 0)
    assert step.command.linear_m_s == 0.0
    assert step.command.angular_rad_s > 0.0
    assert not step.complete


def test_controller_advances_close_waypoint_then_drives_toward_the_next_one():
    step = step_local_route(
        Pose2D(0.05, 0.0, 0.0), [(0.0, 0.0), (1.0, 0.0)], 0,
        ControlLimits(waypoint_tolerance_m=0.10),
    )
    assert step.next_waypoint_index == 1
    assert step.command.linear_m_s > 0.0
    assert step.command.angular_rad_s == pytest.approx(0.0)


def test_empty_or_completed_route_commands_an_explicit_stop():
    pose = Pose2D(0.0, 0.0, 0.0)
    for route, index in (([], 0), ([(0.0, 0.0)], 0), ([(1.0, 0.0)], 99)):
        step = step_local_route(pose, route, index)
        assert step.complete
        assert step.command.linear_m_s == 0.0
        assert step.command.angular_rad_s == 0.0
