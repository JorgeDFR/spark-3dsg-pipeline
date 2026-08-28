#!/usr/bin/env python3
"""Resolve and query the repository's small dataset adapter files."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import yaml


REQUIRED_TOPIC_KEYS = (
    "color",
    "depth",
    "camera_info",
    "instances",
    "labelspace",
    "tf",
    "tf_static",
)


def config_directory() -> Path:
    explicit = os.environ.get("PIPELINE_DATASET_CONFIG_DIR")
    candidates = [
        Path(explicit) if explicit else None,
        Path("/home/spark/ros_ws/src/spark_3dsg_pipeline/config/datasets"),
        Path("/home/spark/ros_ws/install/share/spark_3dsg_pipeline/config/datasets"),
        Path(__file__).resolve().parents[1]
        / "src/spark_3dsg_pipeline/config/datasets",
    ]
    for candidate in candidates:
        if candidate and candidate.is_dir():
            return candidate
    raise FileNotFoundError("could not locate spark_3dsg_pipeline dataset configs")


def resolve_config(name_or_path: str) -> Path:
    requested = Path(name_or_path)
    if requested.is_file():
        return requested.resolve()
    name = requested.name
    if not name.endswith(".yaml"):
        name += ".yaml"
    candidate = config_directory() / name
    if not candidate.is_file():
        available = ", ".join(path.stem for path in sorted(config_directory().glob("*.yaml")))
        raise FileNotFoundError(f"unknown dataset '{name_or_path}'; available: {available}")
    return candidate


def load_config(name_or_path: str) -> dict[str, Any]:
    path = resolve_config(name_or_path)
    with path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError(f"dataset config is not a mapping: {path}")
    topics = config.get("topics")
    if not isinstance(topics, dict):
        raise ValueError(f"dataset config has no topics mapping: {path}")
    missing = [key for key in REQUIRED_TOPIC_KEYS if not topics.get(key)]
    if missing:
        raise ValueError(f"dataset config is missing topics: {', '.join(missing)}")
    return config


def get_value(config: dict[str, Any], dotted_key: str) -> Any:
    value: Any = config
    for key in dotted_key.split("."):
        if not isinstance(value, dict) or key not in value:
            raise KeyError(f"missing dataset key: {dotted_key}")
        value = value[key]
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", help="dataset name or YAML path")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--get", metavar="KEY", help="print a dotted key")
    mode.add_argument("--json", action="store_true", help="print resolved JSON")
    mode.add_argument("--path", action="store_true", help="print resolved path")
    args = parser.parse_args()

    if args.path:
        print(resolve_config(args.dataset))
        return 0

    config = load_config(args.dataset)
    if args.json:
        print(json.dumps(config, indent=2, sort_keys=True))
    else:
        value = get_value(config, args.get)
        if isinstance(value, bool):
            print(str(value).lower())
        elif isinstance(value, (dict, list)):
            print(json.dumps(value))
        else:
            print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
