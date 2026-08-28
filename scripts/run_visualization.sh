#!/usr/bin/env bash
set -euo pipefail

dataset="${1:-spot}"
pipeline_root="${PIPELINE_ROOT:-/home/spark/spark-3dsg-pipeline}"
dataset_config="$pipeline_root/scripts/dataset_config.py"
map_frame=$(python3 "$dataset_config" "$dataset" --get frames.map)
use_sim_time=$(python3 "$dataset_config" "$dataset" --get use_sim_time)

exec ros2 launch spark_3dsg_pipeline visualization.launch.yaml \
  map_frame:="$map_frame" \
  use_sim_time:="$use_sim_time"
