#!/usr/bin/env bash
set -euo pipefail

dataset=spot
bag=
run_id=
rate=
hydra_config_name=
skip_validation=false
spark_home="${HOME:-/home/spark}"
pipeline_root="${PIPELINE_ROOT:-$spark_home/spark-3dsg-pipeline}"
dataset_config="$pipeline_root/scripts/dataset_config.py"

while (($#)); do
  case "$1" in
    --dataset) dataset="${2:?missing value for --dataset}"; shift 2 ;;
    --bag) bag="${2:?missing value for --bag}"; shift 2 ;;
    --run-id) run_id="${2:?missing value for --run-id}"; shift 2 ;;
    --rate) rate="${2:?missing value for --rate}"; shift 2 ;;
    --hydra-config) hydra_config_name="${2:?missing value for --hydra-config}"; shift 2 ;;
    --skip-validation) skip_validation=true; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$bag" ]] || { echo "--bag is required" >&2; exit 2; }
config_path=$(python3 "$dataset_config" "$dataset" --path)
dataset_name=$(python3 "$dataset_config" "$dataset" --get name)
semantics_source=$(python3 "$dataset_config" "$dataset" --get semantics_source)

if [[ "$skip_validation" != true ]]; then
  python3 "$pipeline_root/scripts/validate_bag.py" --bag "$bag" --dataset "$dataset"
fi

if [[ "$semantics_source" == online ]]; then
  model="$spark_home/models/semantic_inference/yoloe-26m-seg.pt"
  [[ -f "$model" ]] || {
    echo "online semantics requires $model; run make models PROFILE=gpu" >&2
    exit 2
  }
  start_perception=true
else
  start_perception=false
fi

map_frame=$(python3 "$dataset_config" "$dataset" --get frames.map)
odom_frame=$(python3 "$dataset_config" "$dataset" --get frames.odom)
robot_frame=$(python3 "$dataset_config" "$dataset" --get frames.robot)
sensor_frame=$(python3 "$dataset_config" "$dataset" --get frames.sensor)
package_share=$(ros2 pkg prefix --share spark_3dsg_pipeline)
if [[ -z "$hydra_config_name" ]]; then
  hydra_config_name=$(python3 "$dataset_config" "$dataset" --get hydra_config)
fi
if [[ "$hydra_config_name" = /* ]]; then
  hydra_config="$hydra_config_name"
else
  hydra_config="$package_share/config/hydra/$hydra_config_name"
fi
[[ -f "$hydra_config" ]] || {
  echo "Hydra config not found: $hydra_config" >&2
  exit 2
}

if [[ -z "$run_id" ]]; then
  run_id="$(date -u +%Y%m%dT%H%M%SZ)-${dataset_name}"
fi
[[ "$run_id" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "unsafe run id: $run_id" >&2; exit 2; }

run_dir="$spark_home/output/$run_id"
if [[ -e "$run_dir" ]]; then
  echo "output already exists: $run_dir (choose --run-id)" >&2
  exit 2
fi
mkdir -p "$run_dir/logs" "$run_dir/upstream"
cp "$config_path" "$run_dir/dataset.yaml"
cp "$hydra_config" "$run_dir/hydra.yaml"
cp "$pipeline_root/dependencies/locks/adt4.lock.repos" "$run_dir/adt4.lock.repos"

pipeline_pid=
cleanup() {
  if [[ -n "${pipeline_pid:-}" ]] && kill -0 "$pipeline_pid" 2>/dev/null; then
    kill -INT "$pipeline_pid" 2>/dev/null || true
    wait "$pipeline_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

ros2 launch spark_3dsg_pipeline pipeline.launch.yaml \
  use_sim_time:=true \
  start_perception:="$start_perception" \
  output_dir:="$run_dir/upstream" \
  map_frame:="$map_frame" \
  odom_frame:="$odom_frame" \
  robot_frame:="$robot_frame" \
  sensor_frame:="$sensor_frame" \
  hydra_config_path:="$hydra_config" \
  exit_after_clock:=true \
  >"$run_dir/logs/pipeline.log" 2>&1 &
pipeline_pid=$!

ready=false
readiness_topic=/input/color/camera_info
for _ in $(seq 1 120); do
  if ! kill -0 "$pipeline_pid" 2>/dev/null; then
    echo "pipeline exited during startup; see $run_dir/logs/pipeline.log" >&2
    exit 1
  fi
  subscription_count=$(
    { ros2 topic info "$readiness_topic" 2>/dev/null || true; } \
      | awk '/Subscription count:/ {print $3; exit}'
  )
  if [[ "${subscription_count:-0}" =~ ^[0-9]+$ ]] \
      && ((subscription_count > 0)); then
    ready=true
    break
  fi
  sleep 1
done
[[ "$ready" == true ]] || {
  echo "pipeline did not subscribe to $readiness_topic within 120 seconds; see $run_dir/logs/pipeline.log" >&2
  exit 1
}

bag_args=("$bag" "$dataset")
[[ -n "$rate" ]] && bag_args+=("$rate")
"$pipeline_root/scripts/run_bag.sh" "${bag_args[@]}" 2>&1 | tee "$run_dir/logs/bag.log"

# exit_after_clock normally stops the pipeline. Bound the final flush, then ask
# for a clean interrupt so experiment serializers run.
for _ in $(seq 1 120); do
  kill -0 "$pipeline_pid" 2>/dev/null || break
  sleep 1
done
cleanup
pipeline_pid=

"$pipeline_root/scripts/save_dsg.sh" "$run_dir"

PIPELINE_RUN_DIR="$run_dir" PIPELINE_DATASET="$dataset_name" PIPELINE_BAG="$bag" \
PIPELINE_HYDRA_CONFIG="$hydra_config_name" \
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
    "hydra_config": os.environ["PIPELINE_HYDRA_CONFIG"],
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
