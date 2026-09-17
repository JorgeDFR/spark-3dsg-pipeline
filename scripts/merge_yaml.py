#!/usr/bin/env python3
"""Deep-merge YAML mappings from left to right for runtime config composition."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge(base[key], value)
        else:
            base[key] = value
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result: dict[str, Any] = {}
    for path in args.inputs:
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as error:
            parser.error(f"cannot load {path}: {error}")
        if not isinstance(value, dict):
            parser.error(f"{path} must contain a YAML mapping")
        merge(result, value)
    args.output.write_text(
        yaml.safe_dump(result, sort_keys=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
