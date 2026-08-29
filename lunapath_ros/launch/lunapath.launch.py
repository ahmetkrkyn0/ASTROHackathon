"""Bring up the LunaPath ROS 2 shell."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    frame_id = LaunchConfiguration("frame_id")
    processed_dir = LaunchConfiguration("processed_dir")

    return LaunchDescription(
        [
            DeclareLaunchArgument("frame_id", default_value="moon_map"),
            DeclareLaunchArgument("processed_dir", default_value=""),
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
        ]
    )
