#!/usr/bin/env bash
set -euo pipefail

dataset=custom_rgbd
bag=
run_id=
rate=
skip_validation=false

while (($#)); do
  case "$1" in
    --dataset) dataset="${2:?missing value for --dataset}"; shift 2 ;;
    --bag) bag="${2:?missing value for --bag}"; shift 2 ;;
    --run-id) run_id="${2:?missing value for --run-id}"; shift 2 ;;
    --rate) rate="${2:?missing value for --rate}"; shift 2 ;;
    --skip-validation) skip_validation=true; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$bag" ]] || { echo "--bag is required" >&2; exit 2; }
config_path=$(python3 /opt/spark_pipeline/scripts/dataset_config.py "$dataset" --path)
dataset_name=$(python3 /opt/spark_pipeline/scripts/dataset_config.py "$dataset" --get name)
semantics_source=$(python3 /opt/spark_pipeline/scripts/dataset_config.py "$dataset" --get semantics_source)

if [[ "$skip_validation" != true ]]; then
  python3 /opt/spark_pipeline/scripts/validate_bag.py --bag "$bag" --dataset "$dataset"
fi

if [[ "$semantics_source" == online ]]; then
  model=/models/semantic_inference/yoloe-26m-seg.pt
  [[ -f "$model" ]] || {
    echo "online semantics requires $model; run make models PROFILE=gpu" >&2
    exit 2
  }
  start_perception=true
else
  start_perception=false
fi

if [[ -z "$run_id" ]]; then
  run_id="$(date -u +%Y%m%dT%H%M%SZ)-${dataset_name}"
fi
[[ "$run_id" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "unsafe run id: $run_id" >&2; exit 2; }

run_dir="/output/$run_id"
if [[ -e "$run_dir" ]]; then
  echo "output already exists: $run_dir (choose --run-id)" >&2
  exit 2
fi
mkdir -p "$run_dir/logs" "$run_dir/upstream"
cp "$config_path" "$run_dir/dataset.yaml"
cp /opt/spark_pipeline/dependencies/locks/adt4.lock.repos "$run_dir/adt4.lock.repos"

map_frame=$(python3 /opt/spark_pipeline/scripts/dataset_config.py "$dataset" --get frames.map)
odom_frame=$(python3 /opt/spark_pipeline/scripts/dataset_config.py "$dataset" --get frames.odom)
robot_frame=$(python3 /opt/spark_pipeline/scripts/dataset_config.py "$dataset" --get frames.robot)
sensor_frame=$(python3 /opt/spark_pipeline/scripts/dataset_config.py "$dataset" --get frames.sensor)
mapper_overlay=$(python3 /opt/spark_pipeline/scripts/dataset_config.py "$dataset" --get mapper_overlay)

pipeline_pid=
cleanup() {
  if [[ -n "${pipeline_pid:-}" ]] && kill -0 "$pipeline_pid" 2>/dev/null; then
    kill -INT "$pipeline_pid" 2>/dev/null || true
    wait "$pipeline_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

ros2 launch spark_dsg_pipeline pipeline.launch.yaml \
  use_sim_time:=true \
  start_perception:="$start_perception" \
  output_dir:="$run_dir/upstream" \
  map_frame:="$map_frame" \
  odom_frame:="$odom_frame" \
  robot_frame:="$robot_frame" \
  sensor_frame:="$sensor_frame" \
  overlay_path:="/opt/ros_ws/install/spark_dsg_pipeline/share/spark_dsg_pipeline/config/hydra/$mapper_overlay" \
  exit_after_clock:=true \
  >"$run_dir/logs/pipeline.log" 2>&1 &
pipeline_pid=$!

ready=false
for _ in $(seq 1 60); do
  if ! kill -0 "$pipeline_pid" 2>/dev/null; then
    echo "pipeline exited during startup; see $run_dir/logs/pipeline.log" >&2
    exit 1
  fi
  if ros2 node list 2>/dev/null | grep -q '/hydra'; then
    ready=true
    break
  fi
  sleep 1
done
[[ "$ready" == true ]] || { echo "pipeline did not become ready in 60 seconds" >&2; exit 1; }

bag_args=("$bag" "$dataset")
[[ -n "$rate" ]] && bag_args+=("$rate")
/opt/spark_pipeline/scripts/run_bag.sh "${bag_args[@]}" 2>&1 | tee "$run_dir/logs/bag.log"

# exit_after_clock normally stops the pipeline. Bound the final flush, then ask
# for a clean interrupt so experiment serializers run.
for _ in $(seq 1 120); do
  kill -0 "$pipeline_pid" 2>/dev/null || break
  sleep 1
done
cleanup
pipeline_pid=

/opt/spark_pipeline/scripts/save_dsg.sh "$run_dir"

PIPELINE_RUN_DIR="$run_dir" PIPELINE_DATASET="$dataset_name" PIPELINE_BAG="$bag" \
python3 - <<'PY'
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

run_dir = Path(os.environ["PIPELINE_RUN_DIR"])
lock = run_dir / "adt4.lock.repos"
metadata = {
    "schema_version": 1,
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "dataset": os.environ["PIPELINE_DATASET"],
    "bag": os.environ["PIPELINE_BAG"],
    "dependency_lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
    "outputs": {
        "dsg": "dsg.json",
        "mesh": "mesh.ply" if (run_dir / "mesh.ply").is_file() else None,
        "logs": "logs",
    },
}
(run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
PY

echo "Mapping output: $run_dir"
