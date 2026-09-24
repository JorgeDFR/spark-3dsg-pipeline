#!/usr/bin/env python3
"""Materialize one raw RGB-D source as a validated normalized ROS 2 bag."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import yaml

PACKAGE_MODULE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "spark_3dsg_preprocessing"
)
if str(PACKAGE_MODULE) not in sys.path:
    sys.path.insert(0, str(PACKAGE_MODULE))

from preprocessing_config import resolve_config  # noqa: E402
from spark_3dsg_preprocessing.config import (  # noqa: E402
    load_preprocessing,
    load_source,
    validate_openvins_calibration,
    validate_pair,
)
from spark_3dsg_preprocessing.offline_normalize import materialize_rosbag  # noqa: E402


NORMALIZED_TOPICS = [
    "/input/color/image_raw",
    "/input/color/camera_info",
    "/input/depth/image_rect",
    "/input/imu",
    "/input/odometry",
    "/tf",
    "/tf_static",
]


def playback_topics(source: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    """Select raw topics and prevent a recorded pose from competing with VO/VIO."""
    topics = source["topics"]
    keys = {"color", "color_camera_info", "depth", "tf_static"}
    if source["depth"]["mode"] == "register":
        keys.add("depth_camera_info")
    backend = profile["pose"]["backend"]
    if backend == "existing_tf":
        keys.add("tf")
    elif backend == "recorded_odometry":
        keys.add("odometry")
    elif backend == "openvins":
        keys.add("imu")
        if profile["pose"].get("max_cameras", 1) == 2:
            keys.add("color_right")
    return sorted({topics[key] for key in keys if topics.get(key)})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_fingerprint(path: Path) -> dict[str, Any]:
    files = (
        [path]
        if path.is_file()
        else sorted(item for item in path.rglob("*") if item.is_file())
    )
    digest = hashlib.sha256()
    total = 0
    for item in files:
        relative = item.name if path.is_file() else item.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with item.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                total += len(chunk)
                digest.update(chunk)
    return {"sha256": digest.hexdigest(), "bytes": total, "files": len(files)}


def stop(process: subprocess.Popen[Any] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def check_launch(process: subprocess.Popen[Any], log_path: Path | None = None) -> None:
    # ros2 launch can remain alive after a component container has crashed.
    if log_path is not None and log_path.is_file():
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for index, line in enumerate(lines):
            if "process has died" in line:
                # Sensor warnings can bury the fatal initialization error long
                # before the process exits. Retain that cause as well as the tail.
                causes = [
                    item for item in lines[:index]
                    if "[FATAL]" in item or "[ZED][ERROR]" in item
                ][-3:]
                context = "\n".join(dict.fromkeys(
                    causes + lines[max(0, index - 6):index + 1]
                ))
                raise RuntimeError(f"preprocessing child process failed; log: {log_path}\n{context}")
    if process.poll() is not None:
        raise RuntimeError(f"preprocessing launch exited with {process.returncode}; log: {log_path}")


def wait_for_node(
    process: subprocess.Popen[Any], name: str, timeout: float,
    log_path: Path | None = None,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        check_launch(process, log_path)
        result = subprocess.run(
            ["ros2", "node", "list"], capture_output=True, text=True, check=False
        )
        if name in result.stdout.splitlines():
            return
        time.sleep(0.25)
    raise RuntimeError(f"timed out waiting for ROS node {name}")


def wait_for_svo_data(
    process: subprocess.Popen[Any], timeout: float, log_path: Path,
) -> None:
    """Wait for real RGB-D messages, not just discovery of an initializing node."""
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import CameraInfo, Image

    rclpy.init()
    node = rclpy.create_node("preprocessing_readiness")
    pending = {
        "/input/color/image_raw": Image,
        "/input/color/camera_info": CameraInfo,
        "/input/depth/image_rect": Image,
    }
    try:
        # Keep subscriptions alive for the whole wait; use wall time because
        # the SVO clock itself may not exist during camera initialization.
        subscriptions = [
            node.create_subscription(
                kind, topic, lambda message, topic=topic: pending.pop(topic, None),
                qos_profile_sensor_data,
            )
            for topic, kind in list(pending.items())
        ]
        deadline = time.monotonic() + timeout
        while pending:
            check_launch(process, log_path)
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"SVO did not publish RGB-D within {timeout}s; "
                    f"waiting for {', '.join(sorted(pending))}; log: {log_path}"
                )
            rclpy.spin_once(node, timeout_sec=0.25)
        print("SVO RGB-D stream ready; starting capture duration", flush=True)
    finally:
        node.destroy_node()
        rclpy.shutdown()


def monitor_capture(
    launch: subprocess.Popen[Any], record: subprocess.Popen[Any],
    duration: float, log_path: Path,
) -> None:
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        check_launch(launch, log_path)
        if record.poll() is not None:
            raise RuntimeError(f"bag recorder exited with {record.returncode}; logs: {log_path.parent}")
        time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))


def backend_nodes(source: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    nodes = ["/rgbd_relay"]
    if source["depth"]["mode"] == "register":
        nodes.append("/depth_register")
    backend = profile["pose"]["backend"]
    if backend == "recorded_odometry":
        nodes.append("/recorded_odometry_to_tf")
    elif backend == "rtabmap_rgbd":
        nodes.extend(("/rtabmap_rgbd_sync", "/rgbd_odometry"))
    elif backend == "openvins":
        nodes.extend(("/openvins/estimator", "/openvins_odometry_to_tf"))
    if source["input_kind"] == "zed_svo":
        camera_name = source.get("zed", {}).get("camera_name", "zed")
        nodes.append(f"/{camera_name}/zed_node")
    return nodes


def normalized_frames(
    source: dict[str, Any], profile: dict[str, Any]
) -> dict[str, str]:
    frames = source["frames"]
    backend = profile["pose"]["backend"]
    if backend == "openvins":
        robot = frames["imu"]
    else:
        robot = frames["robot"]
    return {
        "map": frames.get("map", "map"),
        "odom": frames["odom"],
        "robot": robot,
        "sensor": frames["sensor"],
    }


def generated_dataset(
    source: dict[str, Any], profile: dict[str, Any], output: Path
) -> Path:
    config = {
        "name": f"normalized_{source['name']}",
        "description": "Generated normalized RGB-D preprocessing output",
        "topics": {
            "color": "/input/color/image_raw",
            "depth": "/input/depth/image_rect",
            "camera_info": "/input/color/camera_info",
            "tf": "/tf",
            "tf_static": "/tf_static",
        },
        "frames": normalized_frames(source, profile),
        "depth_scale": source["depth"].get("scale", 1.0),
        "depth_encodings": source["depth"].get(
            "accepted_encodings", ["16UC1", "32FC1"]
        ),
        "use_sim_time": True,
        "playback_rate": 1.0,
    }
    path = output / "dataset.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return path


def write_manifest(
    output: Path,
    input_path: Path,
    source_path: Path,
    profile_path: Path,
    source: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    root = Path(__file__).resolve().parents[2]
    lock = root / "dependencies" / "locks" / "preprocess.lock.repos"
    manifest = {
        "schema_version": 1,
        "source": source["name"],
        "preprocessor": profile["name"],
        "pose_backend": profile["pose"]["backend"],
        "input": str(input_path),
        "input_fingerprint": input_fingerprint(input_path),
        "source_config_sha256": sha256(source_path),
        "resolved_source_config_sha256": hashlib.sha256(
            yaml.safe_dump(source, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "preprocessing_config_sha256": sha256(profile_path),
        "dependency_lock_sha256": sha256(lock),
        "normalized_topics": NORMALIZED_TOPICS,
        "frames": normalized_frames(source, profile),
        "validation": "passed",
    }
    (output / "preprocessing_manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    (output / "source.yaml").write_text(
        yaml.safe_dump(source, sort_keys=False), encoding="utf-8"
    )
    shutil.copy2(profile_path, output / "preprocessing.yaml")
    shutil.copy2(lock, output / "preprocess.lock.repos")


def finalize_output(
    temporary: Path,
    output: Path,
    input_path: Path,
    source_path: Path,
    profile_path: Path,
    source: dict[str, Any],
    profile: dict[str, Any],
) -> None:
    root = Path(__file__).resolve().parents[2]
    dataset = generated_dataset(source, profile, temporary)
    validation = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "python" / "validate_bag.py"),
            "--bag",
            str(temporary),
            "--dataset",
            str(dataset),
            "--mapping",
            "closed_set",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    report_text = validation.stdout
    if validation.stderr:
        report_text += "\n[stderr]\n" + validation.stderr
    report_path = temporary / "validation.txt"
    report_path.write_text(report_text, encoding="utf-8")
    print(validation.stdout, end="")
    if validation.returncode:
        raise RuntimeError(
            "normalized bag validation failed; "
            f"report: {report_path}; logs: {temporary / 'logs'}"
        )
    write_manifest(
        temporary, input_path, source_path, profile_path, source, profile
    )
    temporary.rename(output)
    print(f"normalized bag: {output}")


def run(args: argparse.Namespace) -> None:
    root = Path(__file__).resolve().parents[2]
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
    input_path = args.input.resolve()
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    if source["input_kind"] == "zed_svo" and args.duration is None:
        raise ValueError("--duration is required for SVO input")

    validation = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "python" / "validate_source.py"),
            "--input",
            str(input_path),
            "--source",
            str(source_path),
            "--preprocessor",
            str(profile_path),
        ],
        check=True,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
    backend = profile["pose"]["backend"]
    if source["input_kind"] == "rosbag2" and backend in {
        "existing_tf",
        "recorded_odometry",
    }:
        materialize_rosbag(input_path, temporary, source, profile)
        logs = temporary / "logs"
        logs.mkdir()
        (logs / "offline.log").write_text(
            "normalized directly with rosbags; no ROS graph, playback, or recorder\n",
            encoding="utf-8",
        )
        finalize_output(
            temporary,
            output,
            input_path,
            source_path,
            profile_path,
            source,
            profile,
        )
        return

    record: subprocess.Popen[Any] | None = None
    launch: subprocess.Popen[Any] | None = None
    log_dir = temporary.parent / f".{output.name}.logs-{uuid.uuid4().hex}"
    log_dir.mkdir()
    try:
        record_log = (log_dir / "record.log").open("w", encoding="utf-8")
        launch_log = (log_dir / "launch.log").open("w", encoding="utf-8")
        record = subprocess.Popen(
            [
                "ros2",
                "bag",
                "record",
                "-o",
                str(temporary),
                "--topics",
                *NORMALIZED_TOPICS,
            ],
            stdout=record_log,
            stderr=subprocess.STDOUT,
        )
        launch = subprocess.Popen(
            [
                "ros2",
                "launch",
                "spark_3dsg_preprocessing",
                "preprocess.launch.py",
                f"source_config:={source_path}",
                f"preprocessing_config:={profile_path}",
                f"input_path:={input_path}",
                "use_sim_time:=true",
            ],
            stdout=launch_log,
            stderr=subprocess.STDOUT,
        )
        try:
            for node_name in backend_nodes(source, profile):
                wait_for_node(launch, node_name, args.startup_timeout, log_dir / "launch.log")
        except RuntimeError as error:
            raise RuntimeError(f"{error}; logs: {log_dir}") from error

        if source["input_kind"] == "rosbag2":
            # Node discovery precedes DDS endpoint matching. Give relays,
            # synchronizers, TF listeners, and the recorder time to match
            # before a short bag starts publishing.
            time.sleep(args.settle_seconds)
            play = [
                "ros2",
                "bag",
                "play",
                str(input_path),
                "--clock",
                "--disable-keyboard-controls",
                "--qos-profile-overrides-path",
                str(root / "src/spark_3dsg_pipeline/config/tf_qos.yaml"),
                "--topics",
                *playback_topics(source, profile),
            ]
            topics = source["topics"]
            remaps = []
            if topics.get("tf") and topics["tf"] != "/tf":
                remaps.append(f"{topics['tf']}:=/tf")
            if topics.get("tf_static") and topics["tf_static"] != "/tf_static":
                remaps.append(f"{topics['tf_static']}:=/tf_static")
            if remaps:
                play.extend(["--remap", *remaps])
            subprocess.run(play, check=True)
        else:
            wait_for_svo_data(launch, args.startup_timeout, log_dir / "launch.log")
            monitor_capture(launch, record, args.duration, log_dir / "launch.log")
        time.sleep(args.drain_seconds)
        check_launch(launch, log_dir / "launch.log")
        if record.poll() is not None:
            raise RuntimeError(f"bag recorder exited with {record.returncode}; logs: {log_dir}")
    finally:
        stop(launch)
        stop(record)
        for stream in (locals().get("record_log"), locals().get("launch_log")):
            if stream:
                stream.close()

    if not temporary.is_dir() or not (temporary / "metadata.yaml").is_file():
        raise RuntimeError(f"recorder did not create a complete bag; logs: {log_dir}")
    shutil.copytree(log_dir, temporary / "logs")
    finalize_output(
        temporary,
        output,
        input_path,
        source_path,
        profile_path,
        source,
        profile,
    )
    shutil.rmtree(log_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source", required=True)
    parser.add_argument("--preprocessor", required=True)
    parser.add_argument("--duration", type=float, help="SVO recording duration in seconds")
    parser.add_argument("--startup-timeout", type=float, default=30.0)
    parser.add_argument("--settle-seconds", type=float, default=2.0)
    parser.add_argument("--drain-seconds", type=float, default=2.0)
    args = parser.parse_args()
    try:
        run(args)
    except (FileNotFoundError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"preprocessing failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
