"""Bring up the LunaPath ROS 2 shell."""

from __future__ import annotations

import os

from launch import LaunchDescription
from launch.actions import AppendEnvironmentVariable, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def _find_backend_dir() -> str | None:
    """Locate the repo's ``backend/`` directory so ``app.*`` imports resolve.

    ``grid_publisher.py`` and ``planner_node.py`` import ``app.*`` straight
    from ``backend/`` -- a plain (non-colcon, non-installed) Python package
    -- so it must be on ``PYTHONPATH``. Historically the operator had to run
    `export PYTHONPATH=.../backend:$PYTHONPATH` by hand before `ros2 launch`
    would work (docs/ROS2_SETUP.md); this made the launch file NOT a real
    one-command entry point. (Faz 4 final-review finding M2.)

    The tricky part: this repo's `colcon build` does not use
    `--symlink-install`, so after a build this launch file is a real COPY
    installed at
    ``install/lunapath_ros/share/lunapath_ros/launch/lunapath.launch.py``
    -- five directories below the repo root -- while the source copy at
    ``lunapath_ros/launch/lunapath.launch.py`` is only two directories below
    it. A single hard-coded ``os.path.dirname(__file__)`` offset is
    therefore right for exactly one of those two locations and wrong for
    the other, so it can't be used directly.

    Instead, walk upward from this file's real path (``os.path.realpath``,
    so it still works if some future build DOES use --symlink-install and
    this file is a symlink back into the source tree) looking for a
    ``backend/app`` package. That finds the right directory regardless of
    whether we're running from source or from an installed copy, as long as
    ``lunapath_ros`` and ``backend`` still live in the same checkout --
    true for this repo's actual dev setup (a single Windows repo with a
    WSL2 ROS overlay, not an isolated multi-repo ROS workspace).

    ``LUNAPATH_BACKEND_DIR``, if set, always wins and skips the search --
    an escape hatch for any layout this heuristic doesn't fit.
    """
    override = os.environ.get("LUNAPATH_BACKEND_DIR")
    if override and os.path.isdir(os.path.join(override, "app")):
        return override

    current = os.path.dirname(os.path.realpath(__file__))
    for _ in range(8):
        candidate = os.path.join(current, "backend")
        if os.path.isdir(os.path.join(candidate, "app")):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def generate_launch_description() -> LaunchDescription:
    frame_id = LaunchConfiguration("frame_id")
    processed_dir = LaunchConfiguration("processed_dir")

    actions = [
        DeclareLaunchArgument("frame_id", default_value="moon_map"),
        DeclareLaunchArgument("processed_dir", default_value=""),
        DeclareLaunchArgument("odom_topic", default_value="odom"),
        DeclareLaunchArgument("pose_source", default_value="visual_odometry"),
        DeclareLaunchArgument("local_plan_topic", default_value="local_plan"),
        DeclareLaunchArgument("cmd_vel_topic", default_value="cmd_vel"),
        DeclareLaunchArgument("lidar_points_topic", default_value="points"),
        DeclareLaunchArgument("observed_obstacles_topic", default_value="observed_obstacles"),
        # The local controller is deliberately opt-in: launch cannot make a
        # hardware rover move merely because a local route message appeared.
        DeclareLaunchArgument("enable_local_controller", default_value="false"),
    ]

    backend_dir = _find_backend_dir()
    if backend_dir:
        # AppendEnvironmentVariable, not SetEnvironmentVariable: preserves
        # whatever PYTHONPATH the operator's shell already has instead of
        # clobbering it. (Faz 4 final-review finding M2.)
        actions.append(AppendEnvironmentVariable("PYTHONPATH", backend_dir))
    # else: `backend/` could not be located automatically -- fall back to
    # whatever PYTHONPATH the operator already exported per
    # docs/ROS2_SETUP.md. Both nodes below fail fast with a clear
    # ModuleNotFoundError if that's unset too, rather than us guessing wrong.

    actions += [
        # map -> moon_map is the IDENTITY: moon_map already is a
        # world-fixed metric frame (Moon 2015 South Polar Stereographic),
        # so this only lets RViz use REP-105's `map` as the fixed frame.
        # Named arguments, not positional: the positional form is
        # deprecated on Jazzy. (Faz 4 revision, R13.)
        Node(
            package="tf2_ros",
            executable="static_transform_publisher",
            name="map_to_moon_map",
            arguments=[
                "--x", "0", "--y", "0", "--z", "0",
                "--roll", "0", "--pitch", "0", "--yaw", "0",
                "--frame-id", "map", "--child-frame-id", "moon_map",
            ],
        ),
        Node(
            package="lunapath_ros",
            executable="grid_publisher",
            name="lunapath_grid_publisher",
            parameters=[{"frame_id": frame_id, "processed_dir": processed_dir}],
            output="screen",
        ),
        Node(
            package="lunapath_ros",
            executable="planner_node",
            name="lunapath_planner",
            parameters=[{"frame_id": frame_id, "processed_dir": processed_dir}],
            output="screen",
        ),
        # Faz 7: consumes nav_msgs/Odometry from whatever odometry stack
        # is running (none is launched here -- LunaPath does not produce
        # odometry) and publishes ReplanTrigger when the pose leaves the
        # corridor, uncertainty outgrows it, or slip accumulates.
        Node(
            package="lunapath_ros",
            executable="pose_monitor",
            name="lunapath_pose_monitor",
            parameters=[
                {
                    "odom_topic": LaunchConfiguration("odom_topic"),
                    "pose_source": LaunchConfiguration("pose_source"),
                }
            ],
            output="screen",
        ),
        Node(
            package="lunapath_ros",
            executable="safety_monitor",
            name="lunapath_safety_monitor",
            parameters=[{"odom_topic": LaunchConfiguration("odom_topic")}],
            output="screen",
        ),
        Node(
            package="lunapath_ros",
            executable="local_controller",
            name="lunapath_local_controller",
            parameters=[
                {
                    "enabled": ParameterValue(
                        LaunchConfiguration("enable_local_controller"), value_type=bool
                    ),
                    "odom_topic": LaunchConfiguration("odom_topic"),
                    "local_plan_topic": LaunchConfiguration("local_plan_topic"),
                    "cmd_vel_topic": LaunchConfiguration("cmd_vel_topic"),
                    "map_frame": frame_id,
                }
            ],
            output="screen",
        ),
        Node(
            package="lunapath_ros",
            executable="lidar_perception",
            name="lunapath_lidar_perception",
            parameters=[
                {
                    "points_topic": LaunchConfiguration("lidar_points_topic"),
                    "observed_obstacles_topic": LaunchConfiguration("observed_obstacles_topic"),
                    "map_frame": frame_id,
                }
            ],
            output="screen",
        ),
        Node(
            package="lunapath_ros",
            executable="local_planner",
            name="lunapath_local_planner",
            parameters=[
                {
                    "odom_topic": LaunchConfiguration("odom_topic"),
                    "observed_obstacles_topic": LaunchConfiguration("observed_obstacles_topic"),
                    "local_plan_topic": LaunchConfiguration("local_plan_topic"),
                    "map_frame": frame_id,
                }
            ],
            output="screen",
        ),
        Node(
            package="lunapath_ros",
            executable="replan_coordinator",
            name="lunapath_replan_coordinator",
            parameters=[
                {
                    "odom_topic": LaunchConfiguration("odom_topic"),
                    "observed_obstacles_topic": LaunchConfiguration("observed_obstacles_topic"),
                    "map_frame": frame_id,
                }
            ],
            output="screen",
        ),
        Node(
            package="lunapath_ros",
            executable="execution_monitor",
            name="lunapath_execution_monitor",
            parameters=[
                {"odom_topic": LaunchConfiguration("odom_topic"), "map_frame": frame_id}
            ],
            output="screen",
        ),
    ]

    return LaunchDescription(actions)
