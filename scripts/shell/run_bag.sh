#!/usr/bin/env bash
set -euo pipefail

bag="${1:?usage: run_bag.sh BAG DATASET MAPPING [RATE]}"
dataset="${2:?usage: run_bag.sh BAG DATASET MAPPING [RATE]}"
mapping="${3:?usage: run_bag.sh BAG DATASET MAPPING [RATE]}"
pipeline_root="${PIPELINE_ROOT:-/home/spark/spark-3dsg-pipeline}"
rate="${4:-$(python3 "$pipeline_root/scripts/python/dataset_config.py" "$dataset" --get playback_rate)}"

[[ -e "$bag" ]] || { echo "bag not found: $bag" >&2; exit 2; }

topic() {
  python3 "$pipeline_root/scripts/python/dataset_config.py" "$dataset" --get "topics.$1"
}

color_topic=$(topic color)
depth_topic=$(topic depth)
camera_info_topic=$(topic camera_info)
semantics_source=$(python3 "$pipeline_root/scripts/python/dataset_config.py" \
  "$dataset" --mapping "$mapping" --get semantics.source)
if [[ "$semantics_source" == recorded ]]; then
  semantic_topic=$(topic semantic)
else
  semantic_topic=/input/semantic/image_raw
fi
tf_topic=$(topic tf)
tf_static_topic=$(topic tf_static)

exec ros2 launch spark_3dsg_pipeline bag.launch.yaml \
  bag:="$bag" \
  rate:="$rate" \
  color_topic:="$color_topic" \
  depth_topic:="$depth_topic" \
  camera_info_topic:="$camera_info_topic" \
  semantic_topic:="$semantic_topic" \
  tf_topic:="$tf_topic" \
  tf_static_topic:="$tf_static_topic"
