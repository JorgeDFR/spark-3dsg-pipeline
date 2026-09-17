#!/usr/bin/env python3
"""Resolve, validate, and query the repository's dataset adapter files."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import yaml


REQUIRED_TOPIC_KEYS = ("color", "depth", "camera_info", "tf", "tf_static")
REQUIRED_CONFIG_KEYS = (
    "name",
    "frames",
    "scene_structure",
    "semantics",
    "visualization",
    "hydra_config",
)
SCENE_STRUCTURES = {"hierarchical", "khronos"}
SEMANTIC_SOURCES = {"recorded", "closed_set", "open_set"}
VISUALIZATION_PROFILES = {"hierarchical", "khronos"}


def config_directory() -> Path:
    explicit = os.environ.get("PIPELINE_DATASET_CONFIG_DIR")
    candidates = [
        Path(explicit) if explicit else None,
        Path("/home/spark/ros_ws/install/share/spark_3dsg_pipeline/config/datasets"),
        Path("/home/spark/ros_ws/src/spark_3dsg_pipeline/config/datasets"),
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
    missing = [key for key in REQUIRED_CONFIG_KEYS if not config.get(key)]
    if missing:
        raise ValueError(f"dataset config is missing settings: {', '.join(missing)}")
    validate_config(config, path)
    return config


def validate_config(config: dict[str, Any], path: Path | str = "dataset config") -> None:
    """Reject contradictory pipeline dimensions before ROS is started."""
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
    if source == "recorded" and not config["topics"].get("semantic"):
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
    """Ensure an override implements the adapter's declared structure/semantics."""
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
    mode.add_argument(
        "--validate-hydra",
        type=Path,
        metavar="PATH",
        help="validate a Hydra YAML against the adapter dimensions",
    )
    args = parser.parse_args()

    if args.path:
        print(resolve_config(args.dataset))
        return 0

    config = load_config(args.dataset)
    if args.validate_hydra:
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
