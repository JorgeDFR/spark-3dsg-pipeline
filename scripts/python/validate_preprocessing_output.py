#!/usr/bin/env python3
"""Validate validation-specific normalized topics and provenance files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


REQUIRED_TOPICS = (
    "/input/color/image_raw",
    "/input/color/camera_info",
    "/input/depth/image_rect",
    "/tf",
    "/tf_static",
)


def topic_counts(bag: Path) -> dict[str, int]:
    metadata = bag / "metadata.yaml"
    if not metadata.is_file():
        raise ValueError(f"ROS 2 metadata is missing: {metadata}")
    root = yaml.safe_load(metadata.read_text(encoding="utf-8")) or {}
    info = root.get("rosbag2_bagfile_information", root)
    result: dict[str, int] = {}
    for entry in info.get("topics_with_message_count", []):
        topic = entry.get("topic_metadata", {}).get("name")
        if topic:
            result[topic] = int(entry.get("message_count", 0))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bag", required=True, type=Path)
    parser.add_argument("--require-topic", action="append", default=[])
    args = parser.parse_args()
    failures: list[str] = []
    try:
        counts = topic_counts(args.bag)
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"validation output validation failed: {error}", file=sys.stderr)
        return 1
    for topic in dict.fromkeys((*REQUIRED_TOPICS, *args.require_topic)):
        count = counts.get(topic, 0)
        if count <= 0:
            failures.append(f"required topic has no messages: {topic}")
        else:
            print(f"✓ {topic}: {count} messages")
    for name in (
        "dataset.yaml",
        "source.yaml",
        "preprocessing.yaml",
        "preprocess.lock.repos",
        "preprocessing_manifest.yaml",
        "validation.txt",
    ):
        path = args.bag / name
        if not path.is_file():
            failures.append(f"provenance file missing: {path}")
        else:
            print(f"✓ provenance: {name}")
    for failure in failures:
        print(f"✗ {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
