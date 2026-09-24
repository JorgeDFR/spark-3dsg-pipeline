"""Load and validate raw-source and preprocessing profiles."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


SOURCE_TOPIC_TYPES = {
    "color": "sensor_msgs/msg/Image",
    "color_camera_info": "sensor_msgs/msg/CameraInfo",
    "color_right": "sensor_msgs/msg/Image",
    "depth": "sensor_msgs/msg/Image",
    "depth_camera_info": "sensor_msgs/msg/CameraInfo",
    "imu": "sensor_msgs/msg/Imu",
    "odometry": "nav_msgs/msg/Odometry",
    "tf": "tf2_msgs/msg/TFMessage",
    "tf_static": "tf2_msgs/msg/TFMessage",
}
POSE_BACKENDS = {
    "existing_tf",
    "recorded_odometry",
    "rtabmap_rgbd",
    "openvins",
    "zed_tracking",
}
DEPTH_MODES = {"registered", "register"}
INPUT_KINDS = {"rosbag2", "zed_svo"}


def _load(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"cannot load configuration {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"configuration is not a mapping: {path}")
    return value


def load_source(path: Path) -> dict[str, Any]:
    config = _load(path)
    if "extends" in config:
        raise ValueError(f"source profiles must be self-contained; extends is unsupported: {path}")
    for key in ("name", "input_kind", "topics", "frames", "depth"):
        if not config.get(key):
            raise ValueError(f"source config is missing {key}: {path}")
    if config["input_kind"] not in INPUT_KINDS:
        raise ValueError(f"unsupported input_kind {config['input_kind']!r}: {path}")
    zed = config.get("zed", {})
    if not isinstance(zed, dict):
        raise ValueError(f"source zed must be a mapping: {path}")
    if "legacy_svo" in zed and not isinstance(zed["legacy_svo"], bool):
        raise ValueError(f"zed.legacy_svo must be boolean: {path}")
    if zed.get("legacy_svo") and config["input_kind"] != "zed_svo":
        raise ValueError(f"zed.legacy_svo requires zed_svo input: {path}")
    topics = config["topics"]
    if not isinstance(topics, dict):
        raise ValueError(f"source topics must be a mapping: {path}")
    required_topics = ("color", "color_camera_info", "depth")
    missing = [key for key in required_topics if not topics.get(key)]
    if missing:
        raise ValueError(f"source config is missing topics: {', '.join(missing)}")
    frames = config["frames"]
    if not isinstance(frames, dict):
        raise ValueError(f"source frames must be a mapping: {path}")
    missing = [key for key in ("odom", "robot", "sensor") if not frames.get(key)]
    if missing:
        raise ValueError(f"source config is missing frames: {', '.join(missing)}")
    depth = config["depth"]
    if not isinstance(depth, dict) or depth.get("mode") not in DEPTH_MODES:
        raise ValueError(f"source depth.mode must be registered or register: {path}")
    if not isinstance(depth.get("scale"), (int, float)) or depth["scale"] <= 0:
        raise ValueError(f"source depth.scale must be positive: {path}")
    encodings = depth.get("accepted_encodings")
    if not isinstance(encodings, list) or not encodings or not all(
        isinstance(value, str) and value for value in encodings
    ):
        raise ValueError(f"source depth.accepted_encodings must be a list: {path}")
    if depth["mode"] == "register" and not topics.get("depth_camera_info"):
        raise ValueError(f"depth registration requires topics.depth_camera_info: {path}")
    for index, transform in enumerate(config.get("static_transforms", [])):
        if not isinstance(transform, dict):
            raise ValueError(f"static_transforms[{index}] must be a mapping: {path}")
        if not transform.get("parent") or not transform.get("child"):
            raise ValueError(
                f"static_transforms[{index}] requires parent and child: {path}"
            )
        translation = transform.get("translation", [0.0, 0.0, 0.0])
        rotation = transform.get("rotation", [0.0, 0.0, 0.0, 1.0])
        if (
            not isinstance(translation, list)
            or len(translation) != 3
            or not all(isinstance(value, (int, float)) for value in translation)
        ):
            raise ValueError(
                f"static_transforms[{index}].translation must have 3 numbers: {path}"
            )
        if (
            not isinstance(rotation, list)
            or len(rotation) != 4
            or not all(isinstance(value, (int, float)) for value in rotation)
        ):
            raise ValueError(
                f"static_transforms[{index}].rotation must have 4 numbers: {path}"
            )
        backends = transform.get("backends")
        if backends is not None and (
            not isinstance(backends, list)
            or not backends
            or not all(
                isinstance(backend, str) and backend in POSE_BACKENDS
                for backend in backends
            )
        ):
            raise ValueError(
                f"static_transforms[{index}].backends must contain supported "
                f"pose backends: {path}"
            )
    return config


def static_transforms_for_backend(
    source: dict[str, Any], backend: str
) -> list[dict[str, Any]]:
    return [
        transform
        for transform in source.get("static_transforms", [])
        if not transform.get("backends") or backend in transform["backends"]
    ]


def load_preprocessing(path: Path) -> dict[str, Any]:
    config = _load(path)
    for key in ("name", "pose", "synchronization"):
        if not config.get(key):
            raise ValueError(f"preprocessing config is missing {key}: {path}")
    pose = config["pose"]
    if not isinstance(pose, dict) or pose.get("backend") not in POSE_BACKENDS:
        raise ValueError(f"invalid pose.backend: {path}")
    if pose.get("backend") == "openvins":
        max_cameras = pose.get("max_cameras", 1)
        if (
            not isinstance(max_cameras, int)
            or isinstance(max_cameras, bool)
            or max_cameras not in {1, 2}
        ):
            raise ValueError(f"OpenVINS max_cameras must be 1 or 2: {path}")
    if pose.get("backend") == "rtabmap_rgbd":
        parameters = pose.get("parameters", {})
        if not isinstance(parameters, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in parameters.items()
        ):
            raise ValueError(f"RTAB-Map parameters must be string pairs: {path}")
    approximate = config["synchronization"].get("approximate")
    if not isinstance(approximate, bool):
        raise ValueError(f"synchronization.approximate must be boolean: {path}")
    max_interval = config["synchronization"].get("max_interval", 0.0)
    if (
        not isinstance(max_interval, (int, float))
        or isinstance(max_interval, bool)
        or max_interval < 0
    ):
        raise ValueError(f"synchronization.max_interval must be non-negative: {path}")
    return config


def validate_pair(source: dict[str, Any], profile: dict[str, Any]) -> None:
    topics = source["topics"]
    backend = profile["pose"]["backend"]
    if backend == "recorded_odometry" and not topics.get("odometry"):
        raise ValueError("recorded_odometry requires topics.odometry")
    if backend == "existing_tf" and not topics.get("tf"):
        raise ValueError("existing_tf requires topics.tf")
    if backend == "openvins":
        pose = profile["pose"]
        if not topics.get("imu"):
            raise ValueError("openvins requires topics.imu")
        if not source["frames"].get("imu"):
            raise ValueError("openvins requires frames.imu")
        calibration = profile["pose"].get("calibration")
        if not calibration:
            raise ValueError("openvins requires pose.calibration")
        if pose.get("max_cameras", 1) == 2 and not topics.get("color_right"):
            raise ValueError("stereo OpenVINS requires topics.color_right")
    if backend == "zed_tracking" and source["input_kind"] != "zed_svo":
        raise ValueError("zed_tracking currently requires a zed_svo source")
    if source["input_kind"] == "zed_svo" and backend in {
        "existing_tf",
        "recorded_odometry",
    }:
        raise ValueError(f"{backend} cannot provide pose for a zed_svo source")


def validate_openvins_calibration(path: Path, max_cameras: int) -> None:
    """Check the OpenVINS estimator file and its referenced calibration chains."""
    if not path.is_file():
        raise ValueError(f"OpenVINS calibration not found: {path}")
    text = path.read_text(encoding="utf-8")
    companions: dict[str, Path] = {}
    for key in ("relative_config_imu", "relative_config_imucam"):
        match = re.search(
            rf"^\s*{key}\s*:\s*[\"']?([^#\"']+?)[\"']?\s*(?:#.*)?$",
            text,
            flags=re.MULTILINE,
        )
        if not match:
            raise ValueError(f"OpenVINS calibration is missing {key}: {path}")
        referenced = Path(match.group(1).strip()).expanduser()
        companion = referenced if referenced.is_absolute() else path.parent / referenced
        if not companion.is_file():
            raise ValueError(f"OpenVINS calibration dependency not found: {companion}")
        companions[key] = companion
    camera_chain = companions["relative_config_imucam"].read_text(encoding="utf-8")
    for index in range(max_cameras):
        if not re.search(rf"^\s*cam{index}\s*:", camera_chain, flags=re.MULTILINE):
            raise ValueError(
                f"OpenVINS camera chain has no cam{index}: "
                f"{companions['relative_config_imucam']}"
            )


def zed_parameter_overrides(source: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Compose pinned-wrapper options without activating a second estimator."""
    parameters: dict[str, Any] = {}
    if profile["pose"]["backend"] != "zed_tracking":
        # isPosTrackingRequired() in the pinned wrapper also checks stabilization;
        # disabling publish_tf alone leaves its SDK tracker running.
        parameters.update({
            "pos_tracking.pos_tracking_enabled": False,
            "depth.depth_stabilization": 0,
        })
    if source.get("zed", {}).get("legacy_svo", False):
        parameters.update({
            "pos_tracking.pos_tracking_mode": "GEN_1",
            "pos_tracking.imu_fusion": False,
            "pos_tracking.set_gravity_as_origin": False,
            "sensors.sensors_image_sync": True,
            "sensors.publish_imu": False,
            "sensors.publish_imu_raw": False,
            "sensors.publish_imu_tf": False,
            "sensors.publish_cam_imu_transf": False,
        })
    return parameters


def zed_inline_overrides(source: dict[str, Any], profile: dict[str, Any]) -> str:
    # The locked zed_camera.launch.py accepts key:=value pairs and converts
    # lowercase booleans/numbers to ROS parameter types.
    return ";".join(
        f"{key}:={str(value).lower() if isinstance(value, bool) else value}"
        for key, value in zed_parameter_overrides(source, profile).items()
    )
