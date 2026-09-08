"""Publish LunaPath layers as a latched grid_map topic."""

from __future__ import annotations

import rclpy
from grid_map_msgs.msg import GridMap
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from app.data_loader import load_preprocessed_grids
from lunapath_ros.conversions import grids_to_grid_map

# TRANSIENT_LOCAL so a subscriber that starts late (RViz, rosbag2) still gets
# the map without waiting for the next timer tick.
LATCHED_QOS = QoSProfile(
    depth=1,
    history=HistoryPolicy.KEEP_LAST,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)


class GridPublisher(Node):
    def __init__(self) -> None:
        super().__init__("lunapath_grid_publisher")
        self.declare_parameter("frame_id", "moon_map")
        self.declare_parameter("processed_dir", "")
        self.declare_parameter("period_s", 5.0)

        processed_dir = self.get_parameter("processed_dir").value or None
        self._grids = load_preprocessed_grids(processed_dir=processed_dir)
        self._frame_id = self.get_parameter("frame_id").value

        self._publisher = self.create_publisher(
            GridMap, "/lunapath/grid_map", LATCHED_QOS
        )
        self.create_timer(float(self.get_parameter("period_s").value), self._publish)
        self._publish()

        metadata = self._grids["metadata"]
        rows, cols = metadata["shape"][0], metadata["shape"][1]
        self.get_logger().info(
            f"Publishing {rows}x{cols} @ {metadata['resolution_m']} m/px "
            f"grid_map on /lunapath/grid_map in frame '{self._frame_id}'"
        )

    def _publish(self) -> None:
        message = grids_to_grid_map(
            self._grids, self._frame_id, self.get_clock().now().to_msg()
        )
        self._publisher.publish(message)


def main() -> None:
    rclpy.init()
    node = GridPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.destroy_node()
        except KeyboardInterrupt:
            pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
