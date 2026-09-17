#!/usr/bin/env bash
set -euo pipefail

dataset=spot
bag=
run_id=
rate=
hydra_config_name=
labels_config_override=
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
    --labels-config) labels_config_override="${2:?missing value for --labels-config}"; shift 2 ;;
    --skip-validation) skip_validation=true; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$bag" ]] || { echo "--bag is required" >&2; exit 2; }
config_path=$(python3 "$dataset_config" "$dataset" --path)
dataset_name=$(python3 "$dataset_config" "$dataset" --get name)
semantics_source=$(python3 "$dataset_config" "$dataset" --get semantics.source)
scene_structure=$(python3 "$dataset_config" "$dataset" --get scene_structure)
visualization_profile=$(python3 "$dataset_config" "$dataset" --get visualization.profile)

if [[ "$skip_validation" != true ]]; then
  python3 "$pipeline_root/scripts/validate_bag.py" --bag "$bag" --dataset "$dataset"
fi

map_frame=$(python3 "$dataset_config" "$dataset" --get frames.map)
odom_frame=$(python3 "$dataset_config" "$dataset" --get frames.odom)
robot_frame=$(python3 "$dataset_config" "$dataset" --get frames.robot)
sensor_frame=$(python3 "$dataset_config" "$dataset" --get frames.sensor)
package_share=$(ros2 pkg prefix --share spark_3dsg_pipeline)
semantic_share=$(ros2 pkg prefix --share semantic_inference_ros)
hydra_share=$(ros2 pkg prefix --share hydra)

resource_path() {
  local resource="$1"
  local package="${resource%%:*}"
  local relative="${resource#*:}"
  if [[ "$resource" != *:* || "$resource" = /* ]]; then
    printf '%s\n' "$resource"
  elif [[ "$package" == spark_3dsg_pipeline ]]; then
    printf '%s/%s\n' "$package_share" "$relative"
  elif [[ "$package" == semantic_inference_ros ]]; then
    printf '%s/%s\n' "$semantic_share" "$relative"
  elif [[ "$package" == hydra ]]; then
    printf '%s/%s\n' "$hydra_share" "$relative"
  else
    echo "unsupported package resource: $resource" >&2
    return 2
  fi
}

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
python3 "$dataset_config" "$dataset" --validate-hydra "$hydra_config"

if [[ -n "$labels_config_override" && "$semantics_source" != open_set ]]; then
  echo "--labels-config is valid only for open_set semantics" >&2
  exit 2
fi

labelspace_spec=$(python3 "$dataset_config" "$dataset" --get semantics.labelspace_config)
labelspace_config=$(resource_path "$labelspace_spec")
[[ -f "$labelspace_config" ]] || {
  echo "Hydra label-space config not found: $labelspace_config" >&2
  exit 2
}
semantic_pipeline_spec=$(python3 "$dataset_config" "$dataset" --get semantics.pipeline_config)
semantic_pipeline_config=$(resource_path "$semantic_pipeline_spec")
[[ -f "$semantic_pipeline_config" ]] || {
  echo "semantic pipeline config not found: $semantic_pipeline_config" >&2
  exit 2
}

start_closed_set=false
start_open_set=false
model_file=
model_config=
grouping_config=
labelspace_name=
perception_config=
labels_config=
if [[ "$semantics_source" == closed_set ]]; then
  start_closed_set=true
  model_name=$(python3 "$dataset_config" "$dataset" --get semantics.model_file)
  if [[ "$model_name" = /* ]]; then
    model_file="$model_name"
  else
    model_file="$spark_home/models/semantic_inference/$model_name"
  fi
  model_config=$(resource_path "$(python3 "$dataset_config" "$dataset" --get semantics.model_config)")
  grouping_config=$(resource_path "$(python3 "$dataset_config" "$dataset" --get semantics.grouping_config)")
  labelspace_name=$(python3 "$dataset_config" "$dataset" --get semantics.labelspace_name)
  for requirement in "$model_file" "$model_config" "$grouping_config"; do
    [[ -f "$requirement" ]] || {
      echo "closed-set resource not found: $requirement; run make models PROFILE=gpu and verify the v1 dependency snapshot" >&2
      exit 2
    }
  done
elif [[ "$semantics_source" == open_set ]]; then
  start_open_set=true
  perception_config=$(resource_path "$(python3 "$dataset_config" "$dataset" --get semantics.perception_config)")
  if [[ -n "$labels_config_override" ]]; then
    labels_config="$labels_config_override"
  else
    labels_config=$(resource_path "$(python3 "$dataset_config" "$dataset" --get semantics.labels_config)")
  fi
  for requirement in "$perception_config" "$labels_config" "$spark_home/models/semantic_inference/yoloe-26m-seg.pt"; do
    [[ -f "$requirement" ]] || {
      echo "open-set resource not found: $requirement; run make models PROFILE=gpu or fix --labels-config" >&2
      exit 2
    }
  done
fi

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
cp "$labelspace_config" "$run_dir/labelspace.yaml"
cp "$semantic_pipeline_config" "$run_dir/semantic_pipeline.yaml"
cp "$pipeline_root/dependencies/locks/v1.lock.repos" "$run_dir/v1.lock.repos"
if [[ "$semantics_source" == open_set ]]; then
  python3 "$pipeline_root/scripts/merge_yaml.py" \
    "$perception_config" "$labels_config" --output "$run_dir/perception.yaml"
  perception_config="$run_dir/perception.yaml"
  cp "$labels_config" "$run_dir/open_set_labels.yaml"
elif [[ "$semantics_source" == closed_set ]]; then
  cp "$model_config" "$run_dir/closed_set_model.yaml"
  cp "$grouping_config" "$run_dir/closed_set_grouping.yaml"
fi

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
  start_closed_set:="$start_closed_set" \
  start_open_set:="$start_open_set" \
  output_dir:="$run_dir/upstream" \
  map_frame:="$map_frame" \
  odom_frame:="$odom_frame" \
  robot_frame:="$robot_frame" \
  sensor_frame:="$sensor_frame" \
  hydra_config_path:="$hydra_config" \
  labelspace_config_path:="$labelspace_config" \
  semantic_pipeline_config_path:="$semantic_pipeline_config" \
  perception_config_path:="$perception_config" \
  model_file:="$model_file" \
  model_config_path:="$model_config" \
  grouping_config_path:="$grouping_config" \
  labelspace_name:="$labelspace_name" \
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
PIPELINE_SCENE_STRUCTURE="$scene_structure" \
PIPELINE_SEMANTICS_SOURCE="$semantics_source" \
PIPELINE_VISUALIZATION_PROFILE="$visualization_profile" \
python3 - <<'PY'
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

run_dir = Path(os.environ["PIPELINE_RUN_DIR"])
lock = run_dir / "v1.lock.repos"
metadata = {
    "schema_version": 1,
    "pipeline_version": "v1",
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "dataset": os.environ["PIPELINE_DATASET"],
    "bag": os.environ["PIPELINE_BAG"],
    "hydra_config": os.environ["PIPELINE_HYDRA_CONFIG"],
    "scene_structure": os.environ["PIPELINE_SCENE_STRUCTURE"],
    "semantics_source": os.environ["PIPELINE_SEMANTICS_SOURCE"],
    "visualization_profile": os.environ["PIPELINE_VISUALIZATION_PROFILE"],
    "dependency_lock_hash": hashlib.sha256(lock.read_bytes()).hexdigest(),
    "outputs": {
        "dsg": "dsg.json",
        "mesh": "mesh.ply" if (run_dir / "mesh.ply").is_file() else None,
        "logs": "logs",
    },
}
(run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
PY

echo "Mapping output: $run_dir"
