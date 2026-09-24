#!/usr/bin/env python3
"""Resolve preprocessing source/profile files from source or install trees."""

from __future__ import annotations

import os
from pathlib import Path


KINDS = {"sources", "preprocessing"}


def config_directory(kind: str) -> Path:
    if kind not in KINDS:
        raise ValueError(f"unknown preprocessing config kind: {kind}")
    explicit = os.environ.get("PREPROCESSING_CONFIG_DIR")
    candidates = [
        Path(explicit) / kind if explicit else None,
        Path(
            f"/home/spark/ros_ws/src/spark_3dsg_preprocessing/config/{kind}"
        ),
        Path(
            f"/home/spark/ros_ws/install/share/spark_3dsg_preprocessing/config/{kind}"
        ),
        Path(__file__).resolve().parents[2]
        / "src"
        / "spark_3dsg_preprocessing"
        / "config"
        / kind,
    ]
    for candidate in candidates:
        if candidate and candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"could not locate {kind} preprocessing configs")


def resolve_config(name_or_path: str, kind: str) -> Path:
    requested = Path(name_or_path)
    if requested.is_file():
        return requested.resolve()
    directory = config_directory(kind)
    relative = requested if requested.suffix == ".yaml" else requested.with_name(requested.name + ".yaml")
    candidate = directory / relative
    if not requested.is_absolute() and candidate.is_file():
        return candidate.resolve()
    # Preserve short profile names while allowing explicit family/name selection.
    if len(requested.parts) == 1:
        matches = sorted(directory.rglob(relative.name))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            choices = ", ".join(str(path.relative_to(directory)) for path in matches)
            raise ValueError(f"ambiguous {kind} config {name_or_path!r}; choose: {choices}")
    available = ", ".join(
        str(path.relative_to(directory).with_suffix(""))
        for path in sorted(directory.rglob("*.yaml"))
    )
    raise FileNotFoundError(f"unknown {kind} config {name_or_path!r}; available: {available}")
