#!/usr/bin/env python3
"""Resolve, compose, validate, and query dataset and mapping configs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import yaml


REQUIRED_TOPIC_KEYS = ("color", "depth", "camera_info", "tf", "tf_static")
REQUIRED_FRAME_KEYS = ("map", "odom", "robot", "sensor")
REQUIRED_DATASET_KEYS = (
    "name",
    "frames",
    "depth_scale",
    "depth_encodings",
    "use_sim_time",
    "playback_rate",
)
REQUIRED_MAPPING_KEYS = (
    "name",
    "scene_structure",
    "semantics",
    "visualization",
    "hydra_config",
)
SCENE_STRUCTURES = {"hierarchical", "khronos"}
SEMANTIC_SOURCES = {"recorded", "closed_set", "open_set"}
VISUALIZATION_PROFILES = {"hierarchical", "khronos"}
MAPPING_ONLY_KEYS = {"scene_structure", "semantics", "visualization", "hydra_config"}


def config_directory(kind: str = "datasets") -> Path:
    if kind not in {"datasets", "mappings"}:
        raise ValueError(f"unknown config kind: {kind}")
    explicit = os.environ.get(
        "PIPELINE_DATASET_CONFIG_DIR"
        if kind == "datasets"
        else "PIPELINE_MAPPING_CONFIG_DIR"
    )
    candidates = [
        Path(explicit) if explicit else None,
        Path(f"/home/spark/ros_ws/install/share/spark_3dsg_pipeline/config/{kind}"),
        Path(f"/home/spark/ros_ws/src/spark_3dsg_pipeline/config/{kind}"),
        Path(__file__).resolve().parents[2]
        / f"src/spark_3dsg_pipeline/config/{kind}",
    ]
    for candidate in candidates:
        if candidate and candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"could not locate spark_3dsg_pipeline {kind} configs")


def resolve_config(name_or_path: str, kind: str = "datasets") -> Path:
    requested = Path(name_or_path)
    if requested.is_file():
        return requested.resolve()
    if requested.is_absolute() or len(requested.parts) > 1:
        raise FileNotFoundError(f"config file not found: {requested}")
    name = requested.name
    if not name.endswith(".yaml"):
        name += ".yaml"
    candidate = config_directory(kind) / name
    if not candidate.is_file():
        available = ", ".join(
            path.stem for path in sorted(config_directory(kind).glob("*.yaml"))
        )
        label = "dataset" if kind == "datasets" else "mapping"
        raise FileNotFoundError(
            f"unknown {label} '{name_or_path}'; available: {available}"
        )
    return candidate


def load_yaml_config(name_or_path: str, kind: str) -> tuple[dict[str, Any], Path]:
    path = resolve_config(name_or_path, kind)
    with path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError(f"config is not a mapping: {path}")
    return config, path


def load_dataset_config(name_or_path: str) -> dict[str, Any]:
    config, path = load_yaml_config(name_or_path, "datasets")
    misplaced = sorted(MAPPING_ONLY_KEYS.intersection(config))
    if misplaced:
        raise ValueError(
            f"dataset config contains mapping settings: {', '.join(misplaced)}; "
            "move them to config/mappings"
        )
    topics = config.get("topics")
    if not isinstance(topics, dict):
        raise ValueError(f"dataset config has no topics mapping: {path}")
    missing = [key for key in REQUIRED_TOPIC_KEYS if not topics.get(key)]
    if missing:
        raise ValueError(f"dataset config is missing topics: {', '.join(missing)}")
    missing = [
        key
        for key in REQUIRED_DATASET_KEYS
        if key not in config or config[key] is None
    ]
    if missing:
        raise ValueError(f"dataset config is missing settings: {', '.join(missing)}")
    frames = config["frames"]
    if not isinstance(frames, dict):
        raise ValueError(f"dataset config frames is not a mapping: {path}")
    missing = [key for key in REQUIRED_FRAME_KEYS if not frames.get(key)]
    if missing:
        raise ValueError(f"dataset config is missing frames: {', '.join(missing)}")
    if not isinstance(config["depth_scale"], (int, float)) or config["depth_scale"] <= 0:
        raise ValueError(f"dataset config depth_scale must be positive: {path}")
    encodings = config["depth_encodings"]
    if not isinstance(encodings, list) or not encodings or not all(
        isinstance(value, str) and value for value in encodings
    ):
        raise ValueError(
            f"dataset config depth_encodings must be a non-empty list: {path}"
        )
    if not isinstance(config["use_sim_time"], bool):
        raise ValueError(f"dataset config use_sim_time must be boolean: {path}")
    if (
        not isinstance(config["playback_rate"], (int, float))
        or config["playback_rate"] <= 0
    ):
        raise ValueError(f"dataset config playback_rate must be positive: {path}")
    return config


def load_mapping_config(name_or_path: str) -> dict[str, Any]:
    config, path = load_yaml_config(name_or_path, "mappings")
    missing = [key for key in REQUIRED_MAPPING_KEYS if not config.get(key)]
    if missing:
        raise ValueError(f"mapping config is missing settings: {', '.join(missing)}")
    validate_config(config, path)
    return config


def compose_config(
    dataset: dict[str, Any], mapping: dict[str, Any]
) -> dict[str, Any]:
    """Compose acquisition settings with an independently selected mapper."""
    config = dict(dataset)
    config.update({key: value for key, value in mapping.items() if key != "name"})
    config["mapping"] = mapping["name"]
    validate_config(config)
    return config


def load_config(
    dataset_name_or_path: str, mapping_name_or_path: str | None = None
) -> dict[str, Any]:
    """Load a dataset, optionally composed with a mapping recipe."""
    dataset = load_dataset_config(dataset_name_or_path)
    if mapping_name_or_path is None:
        return dataset
    return compose_config(dataset, load_mapping_config(mapping_name_or_path))


def validate_config(config: dict[str, Any], path: Path | str = "mapping config") -> None:
    """Reject contradictory mapping dimensions before ROS is started."""
    structure = config.get("scene_structure")
    semantics = config.get("semantics")
    visualization = config.get("visualization")
    if structure not in SCENE_STRUCTURES:
        raise ValueError(f"{path}: invalid scene_structure {structure!r}")
    if not isinstance(semantics, dict):
        raise ValueError(f"{path}: semantics must be a mapping")
    source = semantics.get("source")
    if source not in SEMANTIC_SOURCES:
        raise ValueError(f"{path}: invalid semantics.source {source!r}")
    if not isinstance(visualization, dict):
        raise ValueError(f"{path}: visualization must be a mapping")
    profile = visualization.get("profile")
    if profile not in VISUALIZATION_PROFILES:
        raise ValueError(f"{path}: invalid visualization.profile {profile!r}")
    if profile != structure:
        raise ValueError(
            f"{path}: visualization profile {profile!r} does not match "
            f"scene structure {structure!r}"
        )

    allowed_sources = {
        "hierarchical": {"recorded", "closed_set"},
        "khronos": {"open_set"},
    }
    if source not in allowed_sources[structure]:
        raise ValueError(
            f"{path}: semantics source {source!r} is incompatible with "
            f"scene structure {structure!r}"
        )

    required_by_source = {
        "recorded": ("labelspace_config", "pipeline_config"),
        "closed_set": (
            "model_file",
            "model_config",
            "labelspace_name",
            "grouping_config",
            "labelspace_config",
            "pipeline_config",
        ),
        "open_set": (
            "perception_config",
            "labels_config",
            "labelspace_config",
            "pipeline_config",
        ),
    }
    missing = [key for key in required_by_source[source] if not semantics.get(key)]
    if missing:
        raise ValueError(
            f"{path}: {source} semantics is missing: {', '.join(missing)}"
        )
    if (
        source == "recorded"
        and "topics" in config
        and not config["topics"].get("semantic")
    ):
        raise ValueError(f"{path}: recorded semantics requires topics.semantic")


def resolve_resource(
    resource: str,
    package_shares: dict[str, Path],
    *,
    model_directory: Path | None = None,
) -> Path:
    """Resolve ``package:path`` resources and model filenames."""
    if ":" in resource and not resource.startswith("/"):
        package, relative = resource.split(":", 1)
        if package not in package_shares:
            raise FileNotFoundError(f"package share is unavailable: {package}")
        return package_shares[package] / relative
    path = Path(resource).expanduser()
    if path.is_absolute() or model_directory is None:
        return path
    return model_directory / path


def validate_runtime_resources(
    config: dict[str, Any],
    package_shares: dict[str, Path],
    model_directory: Path,
) -> dict[str, Path]:
    """Resolve every selected local/upstream resource and report all omissions."""
    resources = {
        "Hydra config": f"spark_3dsg_pipeline:config/hydra/{config['hydra_config']}",
        "visualizer config": (
            "spark_3dsg_pipeline:config/visualization/"
            f"{config['visualization']['profile']}.yaml"
        ),
        "semantic pipeline config": config["semantics"]["pipeline_config"],
    }
    semantics = config["semantics"]
    source = semantics["source"]
    if source == "closed_set":
        resources.update(
            {
                "closed-set model": semantics["model_file"],
                "semantic-inference model config": semantics["model_config"],
                "semantic-inference grouping": semantics["grouping_config"],
                "Hydra label-space config": semantics["labelspace_config"],
            }
        )
    elif source == "open_set":
        resources.update(
            {
                "open-set perception config": semantics["perception_config"],
                "open-set labels config": semantics["labels_config"],
                "open-set Hydra label-space config": semantics["labelspace_config"],
            }
        )
    else:
        resources["recorded label-space config"] = semantics["labelspace_config"]

    resolved: dict[str, Path] = {}
    missing: list[str] = []
    for label, resource in resources.items():
        try:
            path = resolve_resource(
                resource,
                package_shares,
                model_directory=model_directory if label == "closed-set model" else None,
            )
        except FileNotFoundError as error:
            missing.append(f"{label}: {error}")
            continue
        resolved[label] = path
        if not path.is_file():
            missing.append(f"{label} not found: {path}")
    if missing:
        raise FileNotFoundError(
            "pipeline resources are incomplete:\n  - "
            + "\n  - ".join(missing)
            + "\nRun 'make models PROFILE=gpu' for model weights and verify the v1 dependency snapshot is built."
        )
    return resolved


def validate_hydra_config(config: dict[str, Any], hydra_path: Path) -> None:
    """Ensure an override implements the mapping's declared structure/semantics."""
    try:
        hydra = yaml.safe_load(hydra_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"cannot load Hydra config {hydra_path}: {error}") from error
    if not isinstance(hydra, dict):
        raise ValueError(f"Hydra config is not a mapping: {hydra_path}")
    try:
        receiver = hydra["input"]["inputs"]["camera"]["receiver"]["type"]
        active_window = hydra["active_window"]["type"]
        functors = hydra["backend"]["update_functors"]
    except (KeyError, TypeError) as error:
        raise ValueError(f"Hydra config is incomplete: {hydra_path} ({error})") from error

    source = config["semantics"]["source"]
    expected_receiver = (
        "InstanceImageReceiver" if source == "open_set" else "ClosedSetImageReceiver"
    )
    if receiver != expected_receiver:
        raise ValueError(
            f"{hydra_path}: {source} semantics requires {expected_receiver}, got {receiver}"
        )

    if config["scene_structure"] == "hierarchical":
        if active_window != "ReconstructionModule":
            raise ValueError(
                f"{hydra_path}: hierarchical structure requires ReconstructionModule"
            )
        required = {"objects", "surface_places", "places", "rooms", "buildings"}
        missing = sorted(required - set(functors))
        if missing:
            raise ValueError(
                f"{hydra_path}: hierarchical structure is missing update functors: "
                + ", ".join(missing)
            )
        connector = hydra.get("frontend", {}).get("graph_connector", {}).get(
            "layers", []
        )
        if any(layer.get("parent_layer") == "MESH_PLACES" for layer in connector):
            raise ValueError(
                f"{hydra_path}: hierarchical objects must not use MESH_PLACES as parent"
            )
    else:
        if active_window != "ActiveWindow":
            raise ValueError(f"{hydra_path}: khronos structure requires ActiveWindow")
        forbidden = sorted({"places", "rooms", "buildings"}.intersection(functors))
        if forbidden:
            raise ValueError(
                f"{hydra_path}: khronos structure has hierarchical functors: "
                + ", ".join(forbidden)
            )


def get_value(config: dict[str, Any], dotted_key: str) -> Any:
    value: Any = config
    for key in dotted_key.split("."):
        if not isinstance(value, dict) or key not in value:
            raise KeyError(f"missing config key: {dotted_key}")
        value = value[key]
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", help="dataset name or YAML path")
    parser.add_argument(
        "--mapping", help="independent mapping recipe name or YAML path"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--get", metavar="KEY", help="print a dotted key")
    mode.add_argument("--json", action="store_true", help="print resolved JSON")
    mode.add_argument("--path", action="store_true", help="print dataset path")
    mode.add_argument(
        "--mapping-path", action="store_true", help="print mapping recipe path"
    )
    mode.add_argument(
        "--validate-hydra",
        type=Path,
        metavar="PATH",
        help="validate a Hydra YAML against the mapping dimensions",
    )
    args = parser.parse_args()

    if args.path:
        print(resolve_config(args.dataset))
        return 0
    if args.mapping_path:
        if not args.mapping:
            parser.error("--mapping-path requires --mapping")
        print(resolve_config(args.mapping, "mappings"))
        return 0

    config = load_config(args.dataset, args.mapping)
    if args.validate_hydra:
        if not args.mapping:
            parser.error("--validate-hydra requires --mapping")
        validate_hydra_config(config, args.validate_hydra)
    elif args.json:
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
