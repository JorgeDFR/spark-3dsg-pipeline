"""Normalize nav_msgs/Odometry to an odom-to-robot TF edge."""

from __future__ import annotations

import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from tf2_ros import TransformBroadcaster


class OdometryToTf(Node):
    def __init__(self) -> None:
        super().__init__("odometry_to_tf")
        self.declare_parameter("input_topic", "/odom")
        self.declare_parameter("odom_frame", "odom")
        self.declare_parameter("robot_frame", "base_link")
        self._odom_frame = self.get_parameter("odom_frame").value
        self._robot_frame = self.get_parameter("robot_frame").value
        topic = self.get_parameter("input_topic").value
        self._broadcaster = TransformBroadcaster(self)
        self._publisher = self.create_publisher(
            Odometry, "/input/odometry", qos_profile_sensor_data
        )
        self._subscription = self.create_subscription(
            Odometry, topic, self._callback, qos_profile_sensor_data
        )

    def _callback(self, message: Odometry) -> None:
        normalized = Odometry()
        normalized.header = message.header
        normalized.header.frame_id = self._odom_frame
        normalized.child_frame_id = self._robot_frame
        normalized.pose = message.pose
        normalized.twist = message.twist
        self._publisher.publish(normalized)

        transform = TransformStamped()
        transform.header = normalized.header
        transform.child_frame_id = self._robot_frame
        transform.transform.translation.x = message.pose.pose.position.x
        transform.transform.translation.y = message.pose.pose.position.y
        transform.transform.translation.z = message.pose.pose.position.z
        transform.transform.rotation = message.pose.pose.orientation
        self._broadcaster.sendTransform(transform)


def main() -> None:
    rclpy.init()
    node = OdometryToTf()
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
