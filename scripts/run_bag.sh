#!/usr/bin/env bash
set -euo pipefail

bag="${1:?usage: run_bag.sh BAG DATASET [RATE]}"
dataset="${2:?usage: run_bag.sh BAG DATASET [RATE]}"
pipeline_root="${PIPELINE_ROOT:-/home/spark/spark-3dsg-pipeline}"
ros_ws="${ROS_WS:-/home/spark/ros_ws}"
rate="${3:-$(python3 "$pipeline_root/scripts/dataset_config.py" "$dataset" --get playback_rate)}"

[[ -e "$bag" ]] || { echo "bag not found: $bag" >&2; exit 2; }

remap_args=()
while IFS= read -r remap; do
  [[ -n "$remap" ]] && remap_args+=(--remap "$remap")
done < <(python3 "$pipeline_root/scripts/dataset_config.py" "$dataset" --remaps)

exec ros2 bag play "$bag" \
  --clock \
  --rate "$rate" \
  --qos-profile-overrides-path "$ros_ws/install/spark_3dsg_pipeline/share/spark_3dsg_pipeline/config/tf_qos.yaml" \
  "${remap_args[@]}"
