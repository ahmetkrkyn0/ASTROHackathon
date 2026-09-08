"""Turn a real ``PointCloud2`` stream into anonymous observed obstacles.

The node accepts a sensor-frame cloud, transforms it to ``base_frame`` for
range/height filtering, then writes only validated cluster centres in
``map_frame``. Missing TF, malformed fields, or invalid parameter values fail
closed: no obstacle message is emitted and no route is altered.
"""

from __future__ import annotations

import rclpy
from geometry_msgs.msg import Point
from lunapath_msgs.msg import ObservedObstacle, ObservedObstacles
from rclpy.duration import Duration
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2
from tf2_ros import Buffer, TransformListener

from lunapath_ros.lidar_perception import LidarPoint, cluster_obstacle_returns


def _apply_transform(point: LidarPoint, transform) -> LidarPoint:
    """Apply a geometry_msgs Transform without a hidden tf2 plugin registry."""
    translation = transform.translation
    rotation = transform.rotation
    x, y, z = point.x_m, point.y_m, point.z_m
    qx, qy, qz, qw = (
        float(rotation.x),
        float(rotation.y),
        float(rotation.z),
        float(rotation.w),
    )
    # Quaternion vector rotation: p' = p + 2qv×(qv×p + qw p).
    tx = 2.0 * (qy * z - qz * y)
    ty = 2.0 * (qz * x - qx * z)
    tz = 2.0 * (qx * y - qy * x)
    return LidarPoint(
        x + qw * tx + (qy * tz - qz * ty) + float(translation.x),
        y + qw * ty + (qz * tx - qx * tz) + float(translation.y),
        z + qw * tz + (qx * ty - qy * tx) + float(translation.z),
    )


class LidarPerception(Node):
    def __init__(self) -> None:
        super().__init__("lunapath_lidar_perception")
        self.declare_parameter("points_topic", "points")
        self.declare_parameter("observed_obstacles_topic", "observed_obstacles")
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("map_frame", "moon_map")
        self.declare_parameter("min_height_m", 0.12)
        self.declare_parameter("max_range_m", 12.0)
        self.declare_parameter("cluster_radius_m", 0.35)
        self.declare_parameter("min_points", 3)
        self.declare_parameter("min_confidence", 0.65)

        self._base_frame = str(self.get_parameter("base_frame").value)
        self._map_frame = str(self.get_parameter("map_frame").value)
        self._thresholds = {
            "min_height_m": float(self.get_parameter("min_height_m").value),
            "max_range_m": float(self.get_parameter("max_range_m").value),
            "cluster_radius_m": float(self.get_parameter("cluster_radius_m").value),
            "min_points": int(self.get_parameter("min_points").value),
        }
        self._min_confidence = min(1.0, max(0.0, float(self.get_parameter("min_confidence").value)))
        if self._thresholds["max_range_m"] <= 0.0 or self._thresholds["cluster_radius_m"] <= 0.0:
            raise ValueError("max_range_m and cluster_radius_m must be positive")

        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)
        self._publisher = self.create_publisher(
            ObservedObstacles,
            str(self.get_parameter("observed_obstacles_topic").value),
            10,
        )
        self.create_subscription(
            PointCloud2, str(self.get_parameter("points_topic").value), self._on_cloud, 10
        )
        self.get_logger().info(
            f"LiDAR perception: '{self.get_parameter('points_topic').value}' -> "
            f"'{self.get_parameter('observed_obstacles_topic').value}' "
            f"({self._base_frame} -> {self._map_frame})"
        )

    def _lookup(self, target: str, source: str, stamp):
        if target == source:
            return None
        return self._tf_buffer.lookup_transform(target, source, stamp, timeout=Duration(seconds=0.1))

    def _on_cloud(self, message: PointCloud2) -> None:
        source_frame = message.header.frame_id
        if not source_frame:
            self.get_logger().warning("dropping PointCloud2 without a frame_id")
            return
        try:
            base_transform = self._lookup(self._base_frame, source_frame, message.header.stamp)
            raw = point_cloud2.read_points(
                message, field_names=("x", "y", "z"), skip_nans=True
            )
            base_points = []
            for item in raw:
                sensor_point = LidarPoint(float(item[0]), float(item[1]), float(item[2]))
                base_points.append(
                    _apply_transform(sensor_point, base_transform.transform)
                    if base_transform is not None else sensor_point
                )
            clusters = cluster_obstacle_returns(base_points, **self._thresholds)
        except Exception as exc:  # TF/message failures are unsafe to reinterpret.
            self.get_logger().warning(f"dropping LiDAR cloud: {exc}")
            return

        # Cluster centres were computed in base frame. Recompute the world
        # centre from the same source points selected by no identity-bearing
        # information: transform a base-frame centre through map<-base.
        try:
            map_from_base = self._lookup(self._map_frame, self._base_frame, message.header.stamp)
        except Exception as exc:
            self.get_logger().warning(f"dropping LiDAR clusters without map TF: {exc}")
            return

        output = ObservedObstacles()
        output.header.frame_id = self._map_frame
        output.header.stamp = message.header.stamp
        observed_at = self.get_clock().now().to_msg()
        for cluster in clusters:
            if cluster.confidence < self._min_confidence:
                continue
            local_center = LidarPoint(cluster.x_m, cluster.y_m, 0.0)
            centre = (
                _apply_transform(local_center, map_from_base.transform)
                if map_from_base is not None else local_center
            )
            obstacle = ObservedObstacle()
            obstacle.header = output.header
            obstacle.center = Point(x=centre.x_m, y=centre.y_m, z=centre.z_m)
            obstacle.radius_m = float(cluster.radius_m)
            obstacle.confidence = float(cluster.confidence)
            obstacle.observed_at = observed_at
            obstacle.source = "lidar"
            output.obstacles.append(obstacle)
        if output.obstacles:
            self._publisher.publish(output)


def main() -> None:
    rclpy.init()
    node = LidarPerception()
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
