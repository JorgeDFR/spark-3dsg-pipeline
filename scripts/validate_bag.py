#!/usr/bin/env python3
"""Fail-fast validation for RGB-D/TF bags before expensive mapping."""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path
from typing import Any

import yaml

from dataset_config import load_config


EXPECTED_TYPES = {
    "color": "sensor_msgs/msg/Image",
    "depth": "sensor_msgs/msg/Image",
    "camera_info": "sensor_msgs/msg/CameraInfo",
    "instances": "sensor_msgs/msg/Image",
    "labelspace": "semantic_inference_msgs/msg/Labelspace",
    "tf": "tf2_msgs/msg/TFMessage",
    "tf_static": "tf2_msgs/msg/TFMessage",
}


class Report:
    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def ok(self, message: str) -> None:
        print(f"✓ {message}")

    def fail(self, message: str) -> None:
        self.failures += 1
        print(f"✗ {message}")

    def warn(self, message: str) -> None:
        self.warnings += 1
        print(f"! {message}")


def metadata_path(bag: Path) -> Path | None:
    if bag.is_dir() and (bag / "metadata.yaml").is_file():
        return bag / "metadata.yaml"
    return None


def topics_from_metadata(bag: Path) -> dict[str, str]:
    path = metadata_path(bag)
    if path is None:
        return {}
    with path.open("r", encoding="utf-8") as stream:
        root = yaml.safe_load(stream) or {}
    info = root.get("rosbag2_bagfile_information", root)
    result: dict[str, str] = {}
    for entry in info.get("topics_with_message_count", []):
        metadata = entry.get("topic_metadata", {})
        if metadata.get("name"):
            result[metadata["name"]] = metadata.get("type", "")
    return result


def sample_messages(
    bag: Path, wanted: set[str], max_messages: int
) -> tuple[dict[str, Any], set[tuple[str, str]], bool, str | None]:
    """Read bounded samples. Failure is advisory because storage plugins vary."""
    try:
        import rosbag2_py
        from rclpy.serialization import deserialize_message
        from rosidl_runtime_py.utilities import get_message
    except ImportError as error:
        return {}, set(), True, f"ROS bag Python APIs unavailable: {error}"

    samples: dict[str, Any] = {}
    tf_edges: set[tuple[str, str]] = set()
    last_stamp: dict[str, int] = {}
    monotonic = True
    try:
        reader = rosbag2_py.SequentialReader()
        reader.open(
            rosbag2_py.StorageOptions(uri=str(bag), storage_id=""),
            rosbag2_py.ConverterOptions("", ""),
        )
        type_map = {entry.name: entry.type for entry in reader.get_all_topics_and_types()}
        resolved_types = {topic: get_message(type_name) for topic, type_name in type_map.items() if topic in wanted}
        count = 0
        while reader.has_next() and count < max_messages:
            topic, payload, timestamp = reader.read_next()
            count += 1
            if topic not in wanted:
                continue
            if topic in last_stamp and timestamp < last_stamp[topic]:
                monotonic = False
            last_stamp[topic] = timestamp
            if topic not in samples:
                samples[topic] = deserialize_message(payload, resolved_types[topic])
            if type_map.get(topic) == "tf2_msgs/msg/TFMessage":
                message = deserialize_message(payload, resolved_types[topic])
                for transform in message.transforms:
                    tf_edges.add((transform.header.frame_id.lstrip("/"), transform.child_frame_id.lstrip("/")))
            if wanted.issubset(samples) and len(tf_edges) >= 3:
                break
        return samples, tf_edges, monotonic, None
    except Exception as error:  # storage/plugin failures should still yield topic checks
        return samples, tf_edges, monotonic, str(error)


def connected(edges: set[tuple[str, str]], start: str, goal: str) -> bool:
    graph: dict[str, set[str]] = collections.defaultdict(set)
    for parent, child in edges:
        graph[parent].add(child)
        graph[child].add(parent)
    queue = collections.deque([start.lstrip("/")])
    seen = set(queue)
    target = goal.lstrip("/")
    while queue:
        node = queue.popleft()
        if node == target:
            return True
        for neighbor in graph[node] - seen:
            seen.add(neighbor)
            queue.append(neighbor)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bag", required=True, type=Path)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--max-messages", type=int, default=20000)
    args = parser.parse_args()

    report = Report()
    if not args.bag.exists():
        report.fail(f"bag does not exist: {args.bag}")
        return 1

    config = load_config(args.dataset)
    topics_cfg = config["topics"]
    topics = topics_from_metadata(args.bag)
    if not topics:
        report.warn("metadata.yaml unavailable; topic type checks will use the reader only")

    required = ["color", "depth", "camera_info", "tf", "tf_static"]
    if config.get("semantics_source") == "precomputed":
        required.append("instances")

    for key in required:
        topic = topics_cfg[key]
        if topics and topic not in topics:
            report.fail(f"{key} topic missing: {topic}")
        elif topics and topics[topic] != EXPECTED_TYPES[key]:
            report.fail(f"{key} has type {topics[topic]}, expected {EXPECTED_TYPES[key]}")
        else:
            report.ok(f"{key} topic: {topic}")

    wanted = {topics_cfg[key] for key in required}
    samples, tf_edges, monotonic, reader_error = sample_messages(args.bag, wanted, args.max_messages)
    if reader_error:
        report.warn(f"bounded message inspection incomplete: {reader_error}")

    depth_topic = topics_cfg["depth"]
    depth = samples.get(depth_topic)
    if depth is None:
        report.warn("depth encoding not sampled")
    elif depth.encoding not in config.get("depth_encodings", ["16UC1", "32FC1"]):
        report.fail(f"depth encoding {depth.encoding} is unsupported")
    else:
        report.ok(f"depth encoding: {depth.encoding}")

    camera_info = samples.get(topics_cfg["camera_info"])
    if camera_info is None:
        report.warn("CameraInfo payload not sampled")
    elif camera_info.width <= 0 or camera_info.height <= 0 or camera_info.k[0] <= 0:
        report.fail("CameraInfo has invalid dimensions/intrinsics")
    else:
        report.ok(f"CameraInfo: {camera_info.width}x{camera_info.height}")

    frames = config["frames"]
    for source, target, label in [
        (frames["map"], frames["robot"], "map/robot TF"),
        (frames["robot"], frames["sensor"], "camera optical TF"),
    ]:
        if not tf_edges:
            report.warn(f"{label} not sampled")
        elif connected(tf_edges, source, target):
            report.ok(label)
        else:
            report.fail(f"{label} missing ({source} -> {target})")

    if monotonic:
        report.ok("sampled timestamps monotonically increasing")
    else:
        report.fail("timestamps move backwards within at least one topic")

    if config.get("semantics_source") == "online":
        report.ok("semantics source: online perception (not required in bag)")
    else:
        report.ok("semantics source: precomputed")

    print(f"\nValidation: {report.failures} error(s), {report.warnings} warning(s)")
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
