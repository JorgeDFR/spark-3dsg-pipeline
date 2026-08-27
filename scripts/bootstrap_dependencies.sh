#!/usr/bin/env bash
set -euo pipefail

root="${1:-/opt/ros_ws/src}"
manifest="${2:-/opt/spark_pipeline/dependencies/locks/adt4.lock.repos}"

mkdir -p "$root"
vcs import "$root" --workers 1 < "$manifest"
