#!/usr/bin/env bash
set -euo pipefail

root="${1:-${ROS_WS:-/home/spark/ros_ws}/src}"
manifest="${2:-${PIPELINE_ROOT:-/home/spark/spark-3dsg-pipeline}/dependencies/locks/adt4.lock.repos}"

mkdir -p "$root"
vcs import "$root" --workers 1 < "$manifest"
