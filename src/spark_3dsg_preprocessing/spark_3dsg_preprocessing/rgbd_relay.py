"""Relay raw sensor messages onto the stable normalized topic names."""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image, Imu


class RgbdRelay(Node):
    def __init__(self) -> None:
        super().__init__("rgbd_relay")
        self.declare_parameter("color_topic", "")
        self.declare_parameter("color_info_topic", "")
        self.declare_parameter("depth_topic", "")
        self.declare_parameter("depth_info_topic", "")
        self.declare_parameter("imu_topic", "")
        self.declare_parameter("output_depth_topic", "/input/depth/image_rect")
        self.declare_parameter("output_depth_info_topic", "/input/depth/camera_info")
        self.declare_parameter("color_frame_id", "")
        self.declare_parameter("depth_frame_id", "")
        self._color_frame_id = self._parameter("color_frame_id")
        self._depth_frame_id = self._parameter("depth_frame_id")

        self._color_pub = self.create_publisher(
            Image, "/input/color/image_raw", 10
        )
        self._color_info_pub = self.create_publisher(
            CameraInfo, "/input/color/camera_info", 10
        )
        self._depth_pub = self.create_publisher(
            Image,
            self._parameter("output_depth_topic"),
            10,
        )
        self._depth_info_pub = self.create_publisher(
            CameraInfo,
            self._parameter("output_depth_info_topic"),
            10,
        )
        self._subscriptions = [
            self.create_subscription(
                Image,
                self._required_parameter("color_topic"),
                self._publish_color,
                qos_profile_sensor_data,
            ),
            self.create_subscription(
                CameraInfo,
                self._required_parameter("color_info_topic"),
                self._publish_color_info,
                qos_profile_sensor_data,
            ),
            self.create_subscription(
                Image,
                self._required_parameter("depth_topic"),
                self._publish_depth,
                qos_profile_sensor_data,
            ),
        ]
        depth_info = self._parameter("depth_info_topic")
        if depth_info:
            self._subscriptions.append(
                self.create_subscription(
                    CameraInfo,
                    depth_info,
                    self._depth_info_pub.publish,
                    qos_profile_sensor_data,
                )
            )
        imu = self._parameter("imu_topic")
        if imu:
            self._imu_pub = self.create_publisher(
                Imu, "/input/imu", qos_profile_sensor_data
            )
            self._subscriptions.append(
                self.create_subscription(
                    Imu, imu, self._imu_pub.publish, qos_profile_sensor_data
                )
            )

    def _publish_color(self, message: Image) -> None:
        if self._color_frame_id:
            message.header.frame_id = self._color_frame_id
        self._color_pub.publish(message)

    def _publish_color_info(self, message: CameraInfo) -> None:
        if self._color_frame_id:
            message.header.frame_id = self._color_frame_id
        self._color_info_pub.publish(message)

    def _publish_depth(self, message: Image) -> None:
        if self._depth_frame_id:
            message.header.frame_id = self._depth_frame_id
        self._depth_pub.publish(message)

    def _parameter(self, name: str) -> str:
        return self.get_parameter(name).get_parameter_value().string_value

    def _required_parameter(self, name: str) -> str:
        value = self._parameter(name)
        if not value:
            raise ValueError(f"parameter {name} must not be empty")
        return value


def main() -> None:
    rclpy.init()
    node = RgbdRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception:
        if rclpy.ok():
            raise
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()
