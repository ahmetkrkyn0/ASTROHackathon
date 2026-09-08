FROM osrf/ros:jazzy-desktop

RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-jazzy-grid-map \
        ros-jazzy-navigation2 \
        ros-jazzy-nav2-bringup \
        ros-jazzy-rosbag2 \
        ros-jazzy-sensor-msgs-py \
        build-essential cmake \
        python3-colcon-common-extensions \
        python3-pytest python3-numpy python3-scipy \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
CMD ["bash"]
