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
        ],
    },
)
