from setuptools import find_packages, setup

package_name = "lunapath_ros"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", ["launch/lunapath.launch.py"]),
        (f"share/{package_name}/config", ["config/lunapath.rviz"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="LunaPath Team",
    maintainer_email="berkekusseng@gmail.com",
    description="ROS 2 shell for the LunaPath lunar traverse planner.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "planner_node = lunapath_ros.planner_node:main",
            "grid_publisher = lunapath_ros.grid_publisher:main",
            "pose_monitor = lunapath_ros.pose_monitor:main",
            "safety_monitor = lunapath_ros.safety_monitor_node:main",
            "local_controller = lunapath_ros.local_controller_node:main",
            "lidar_perception = lunapath_ros.lidar_perception_node:main",
            "local_planner = lunapath_ros.local_planner_node:main",
            "replan_coordinator = lunapath_ros.replan_coordinator_node:main",
            "execution_monitor = lunapath_ros.execution_monitor_node:main",
        ],
    },
)
