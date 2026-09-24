#!/usr/bin/env python3
"""Deterministically normalize ROS 2 bag messages without ROS playback."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from rosbags.highlevel import AnyReader
from rosbags.rosbag2 import Writer
from rosbags.typesys import Stores, get_typestore


DEFAULT_TYPESTORE = get_typestore(Stores.ROS2_JAZZY)
TF_TYPE = "tf2_msgs/msg/TFMessage"


def _transform_from_odometry(message: Any, robot: str, typestore: Any) -> Any:
    types = typestore.types
    vector = types["geometry_msgs/msg/Vector3"]
    transform = types["geometry_msgs/msg/Transform"]
    stamped = types["geometry_msgs/msg/TransformStamped"]
    tf_message = types[TF_TYPE]
    pose = message.pose.pose
    return tf_message(
        [
            stamped(
                message.header,
                robot,
                transform(
                    vector(pose.position.x, pose.position.y, pose.position.z),
                    pose.orientation,
                ),
            )
        ]
    )


def _rewrite_frame(message: Any, frame: str) -> Any:
    message.header.frame_id = frame
    return message


def _rotation(quaternion: Any) -> np.ndarray:
    x, y, z, w = quaternion.x, quaternion.y, quaternion.z, quaternion.w
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def _static_graph(
    messages: list[Any],
) -> dict[str, list[tuple[str, np.ndarray, np.ndarray]]]:
    graph: dict[str, list[tuple[str, np.ndarray, np.ndarray]]] = {}
    for message in messages:
        for stamped in message.transforms:
            parent = stamped.header.frame_id.lstrip("/")
            child = stamped.child_frame_id.lstrip("/")
            rotation = _rotation(stamped.transform.rotation)
            value = stamped.transform.translation
            translation = np.array([value.x, value.y, value.z], dtype=np.float64)
            # A TF parent->child maps child coordinates into the parent frame.
            graph.setdefault(child, []).append((parent, rotation, translation))
            graph.setdefault(parent, []).append(
                (child, rotation.T, -(rotation.T @ translation))
            )
    return graph


def _lookup_transform(
    graph: dict[str, list[tuple[str, np.ndarray, np.ndarray]]],
    source: str,
    target: str,
) -> tuple[np.ndarray, np.ndarray]:
    source, target = source.lstrip("/"), target.lstrip("/")
    queue = deque([(source, np.eye(3), np.zeros(3))])
    visited = {source}
    while queue:
        frame, rotation, translation = queue.popleft()
        if frame == target:
            return rotation, translation
        for neighbor, edge_rotation, edge_translation in graph.get(frame, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append(
                (
                    neighbor,
                    edge_rotation @ rotation,
                    edge_rotation @ translation + edge_translation,
                )
            )
    raise ValueError(f"no static TF path from {source} to {target}")


def register_depth(
    message: Any,
    depth_info: Any,
    color_info: Any,
    rotation: np.ndarray,
    translation: np.ndarray,
    scale: float,
    output_frame: str,
) -> Any:
    """Project a rectified depth image into a rectified color camera."""
    encodings = {"16UC1": (np.uint16, 2), "32FC1": (np.float32, 4)}
    if message.encoding not in encodings:
        raise ValueError(f"offline depth registration does not support {message.encoding}")
    dtype, itemsize = encodings[message.encoding]
    byteorder = ">" if message.is_bigendian else "<"
    source = np.frombuffer(message.data, dtype=np.dtype(dtype).newbyteorder(byteorder))
    source = source.reshape(message.height, message.step // itemsize)[:, : message.width]
    z = (
        source.astype(np.float64) / scale
        if message.encoding == "16UC1"
        else source.astype(np.float64)
    )
    rows, columns = np.indices(z.shape)
    valid = np.isfinite(z) & (z > 0)
    z, rows, columns = z[valid], rows[valid], columns[valid]

    depth_p = np.asarray(depth_info.P, dtype=np.float64).reshape(3, 4)
    color_p = np.asarray(color_info.P, dtype=np.float64).reshape(3, 4)
    points = np.vstack(
        (
            (columns - depth_p[0, 2]) * z / depth_p[0, 0],
            (rows - depth_p[1, 2]) * z / depth_p[1, 1],
            z,
        )
    )
    points = rotation @ points + translation[:, None]
    valid = points[2] > 0
    points = points[:, valid]
    u = np.rint(
        color_p[0, 0] * points[0] / points[2] + color_p[0, 2]
    ).astype(int)
    v = np.rint(
        color_p[1, 1] * points[1] / points[2] + color_p[1, 2]
    ).astype(int)
    valid = (
        (u >= 0)
        & (u < color_info.width)
        & (v >= 0)
        & (v < color_info.height)
    )
    u, v = u[valid], v[valid]
    projected_z = points[2, valid]
    pixels = v * color_info.width + u
    order = np.lexsort((projected_z, pixels))
    pixels, projected_z = pixels[order], projected_z[order]
    output = np.zeros(color_info.width * color_info.height, dtype=dtype)
    if pixels.size:
        first = np.r_[True, pixels[1:] != pixels[:-1]]
        values = (
            projected_z[first] * scale
            if message.encoding == "16UC1"
            else projected_z[first]
        )
        output[pixels[first]] = values.astype(dtype)
    message.header.frame_id = output_frame
    message.height = color_info.height
    message.width = color_info.width
    message.step = color_info.width * itemsize
    message.is_bigendian = 0
    message.data = (
        output.reshape(color_info.height, color_info.width).view(np.uint8).ravel()
    )
    return message


def materialize_rosbag(
    input_path: Path,
    output_path: Path,
    source: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    """Rewrite a bag directly; supported pose data never crosses DDS."""
    backend = profile["pose"]["backend"]
    if backend not in {"existing_tf", "recorded_odometry"}:
        raise ValueError(f"pose backend requires an estimator process: {backend}")

    topics = source["topics"]
    frames = source["frames"]
    routes = {
        topics["color"]: ("/input/color/image_raw", "sensor"),
        topics["color_camera_info"]: ("/input/color/camera_info", "sensor"),
        topics["depth"]: ("/input/depth/image_rect", "sensor"),
    }
    if topics.get("imu"):
        routes[topics["imu"]] = ("/input/imu", None)
    if topics.get("tf_static"):
        routes[topics["tf_static"]] = ("/tf_static", None)
    if backend == "existing_tf" and topics.get("tf"):
        routes[topics["tf"]] = ("/tf", None)
    if backend == "recorded_odometry":
        routes[topics["odometry"]] = ("/input/odometry", "odometry")

    with AnyReader([input_path], default_typestore=DEFAULT_TYPESTORE) as reader, Writer(
        output_path, version=9
    ) as writer:
        typestore = reader.typestore
        registration: tuple[Any, Any, np.ndarray, np.ndarray] | None = None
        if source["depth"]["mode"] == "register":
            preload_topics = {
                topics["depth_camera_info"],
                topics["color_camera_info"],
                topics.get("tf_static", ""),
            }
            preload = [item for item in reader.connections if item.topic in preload_topics]
            depth_info = color_info = None
            static_messages = []
            for item, _, raw in reader.messages(connections=preload):
                value = reader.deserialize(raw, item.msgtype)
                if item.topic == topics["depth_camera_info"] and depth_info is None:
                    depth_info = value
                elif item.topic == topics["color_camera_info"] and color_info is None:
                    color_info = value
                elif item.topic == topics.get("tf_static"):
                    static_messages.append(value)
            if depth_info is None or color_info is None:
                raise ValueError("depth registration requires both CameraInfo streams")
            graph = _static_graph(static_messages)
            rotation, translation = _lookup_transform(
                graph, depth_info.header.frame_id, color_info.header.frame_id
            )
            registration = depth_info, color_info, rotation, translation
        selected = [
            connection
            for connection in reader.connections
            if connection.topic in routes
        ]
        output_connections: dict[tuple[str, str], Any] = {}

        def connection(topic: str, msgtype: str) -> Any:
            key = (topic, msgtype)
            if key not in output_connections:
                output_connections[key] = writer.add_connection(
                    topic, msgtype, typestore=typestore
                )
            return output_connections[key]

        for source_connection, timestamp, raw in reader.messages(connections=selected):
            output_topic, operation = routes[source_connection.topic]
            message = reader.deserialize(raw, source_connection.msgtype)
            if operation == "sensor":
                if source_connection.topic == topics["depth"] and registration:
                    message = register_depth(
                        message,
                        *registration,
                        source["depth"]["scale"],
                        frames["sensor"],
                    )
                else:
                    _rewrite_frame(message, frames["sensor"])
            elif operation == "odometry":
                message.header.frame_id = frames["odom"]
                message.child_frame_id = frames["robot"]

            writer.write(
                connection(output_topic, source_connection.msgtype),
                timestamp,
                typestore.serialize_cdr(message, source_connection.msgtype),
            )
            if operation == "odometry":
                tf = _transform_from_odometry(message, frames["robot"], typestore)
                writer.write(
                    connection("/tf", TF_TYPE),
                    timestamp,
                    typestore.serialize_cdr(tf, TF_TYPE),
                )
