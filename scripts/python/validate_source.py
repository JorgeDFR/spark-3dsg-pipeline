#!/usr/bin/env python3
"""Validate the discoverable contract of a raw preprocessing source."""

from __future__ import annotations

import argparse
import ctypes
import subprocess
import sys
from pathlib import Path

from preprocessing_config import resolve_config


PACKAGE_MODULE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "spark_3dsg_preprocessing"
)
if str(PACKAGE_MODULE) not in sys.path:
    sys.path.insert(0, str(PACKAGE_MODULE))

from spark_3dsg_preprocessing.config import (  # noqa: E402
    SOURCE_TOPIC_TYPES,
    load_preprocessing,
    load_source,
    validate_openvins_calibration,
    validate_pair,
)
from validate_bag import sample_messages, topics_from_metadata  # noqa: E402


def validate_rosbag(bag: Path, source: dict, profile: dict) -> list[str]:
    errors: list[str] = []
    if not bag.exists():
        return [f"input does not exist: {bag}"]
    topics = topics_from_metadata(bag)
    if not topics:
        return [f"ROS 2 metadata.yaml is missing or contains no topics: {bag}"]
    required = {"color", "color_camera_info", "depth"}
    backend_topics = source["topics"]
    if source["depth"]["mode"] == "register":
        required.add("depth_camera_info")
    backend = profile["pose"]["backend"]
    if backend == "existing_tf":
        required.update(("tf", "tf_static"))
    elif backend == "recorded_odometry":
        required.update(("odometry", "tf_static"))
    elif backend == "rtabmap_rgbd":
        required.add("tf_static")
    elif backend == "openvins":
        required.update(("imu", "tf_static"))
        if profile["pose"].get("max_cameras", 1) == 2:
            required.add("color_right")
    for key in sorted(required):
        name = backend_topics.get(key)
        if key == "tf_static" and not name and source.get("static_transforms"):
            continue
        if not name:
            errors.append(f"{key} topic is not configured")
            continue
        if name not in topics:
            errors.append(f"{key} topic missing: {name}")
        elif topics[name] != SOURCE_TOPIC_TYPES[key]:
            errors.append(
                f"{key} has type {topics[name]}, expected {SOURCE_TOPIC_TYPES[key]}"
            )
    depth_topic = backend_topics["depth"]
    samples, _, _, reader_error = sample_messages(bag, {depth_topic}, 20000)
    if reader_error:
        errors.append(f"cannot sample depth messages: {reader_error}")
    elif depth_topic not in samples:
        errors.append(f"depth topic contains no sampled messages: {depth_topic}")
    else:
        encoding = samples[depth_topic].encoding
        accepted = source["depth"]["accepted_encodings"]
        if encoding not in accepted:
            errors.append(
                f"depth encoding {encoding} is not accepted; expected one of {accepted}"
            )
    return errors


ZED_LIBRARY = Path("/usr/local/zed/lib/libsl_zed.so")


def validate_svo(path: Path) -> list[str]:
    if not path.is_file():
        return [f"SVO file does not exist: {path}"]
    # ldconfig indexes SONAMEs, which may differ from this unversioned filename.
    # Load the known SDK file directly so a name lookup cannot reject an
    # otherwise working installation, and preserve errors from dependencies.
    library = ZED_LIBRARY
    try:
        if not library.is_file():
            return [f"ZED SDK file missing or broken symlink: {library}; rebuild with make build-preprocess"]
        # stat alone does not prove that the library can be read by spark.
        with library.open("rb") as stream:
            stream.read(1)
    except OSError as error:
        return [
            f"cannot access ZED SDK at {library}: {error}. "
            "The runtime spark user needs read access to the SDK files and "
            "traversal access to their parent directories. Rebuild with "
            "make build-preprocess to apply the SDK permissions fix."
        ]
    try:
        ctypes.CDLL(str(library))
    except OSError as error:
        diagnostics = ""
        try:
            result = subprocess.run(
                ["ldd", str(library)], capture_output=True, text=True, check=False,
                timeout=10,
            )
            diagnostics = "\nSDK dependencies:\n" + result.stdout + result.stderr
        except (OSError, subprocess.TimeoutExpired) as diagnostic_error:
            diagnostics = f"\nCould not inspect SDK dependencies: {diagnostic_error}"
        return [
            f"cannot load ZED SDK at {library}: {error}. "
            "If a dependency is missing, see the ldd output below. "
            "libcuda/libnvcuvid are supplied by the NVIDIA Container Toolkit "
            "with compute,video driver capabilities."
            + diagnostics
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--preprocessor", required=True)
    args = parser.parse_args()

    try:
        source_path = resolve_config(args.source, "sources")
        profile_path = resolve_config(args.preprocessor, "preprocessing")
        source = load_source(source_path)
        profile = load_preprocessing(profile_path)
        validate_pair(source, profile)
        if profile["pose"]["backend"] == "openvins":
            validate_openvins_calibration(
                Path(profile["pose"]["calibration"]).expanduser(),
                profile["pose"].get("max_cameras", 1),
            )
        errors = (
            validate_rosbag(args.input, source, profile)
            if source["input_kind"] == "rosbag2"
            else validate_svo(args.input)
        )
    except (FileNotFoundError, ValueError) as error:
        print(f"source validation failed: {error}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"✗ {error}")
        return 1
    print(f"✓ source: {source['name']}")
    print(f"✓ pose backend: {profile['pose']['backend']}")
    print(f"✓ input: {args.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
