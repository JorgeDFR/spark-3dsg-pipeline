#!/usr/bin/env bash
set -euo pipefail

dataset=spot
mapping=
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
    --mapping) mapping="${2:?missing value for --mapping}"; shift 2 ;;
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
[[ -n "$mapping" ]] || {
  echo "--mapping is required (recorded, closed_set, or open_set)" >&2
  exit 2
}
config_path=$(python3 "$dataset_config" "$dataset" --path)
mapping_config_path=$(python3 "$dataset_config" "$dataset" --mapping "$mapping" --mapping-path)

config_query() {
  python3 "$dataset_config" "$dataset" --mapping "$mapping" --get "$1"
}

dataset_name=$(config_query name)
mapping_name=$(config_query mapping)
semantics_source=$(config_query semantics.source)
scene_structure=$(config_query scene_structure)
visualization_profile=$(config_query visualization.profile)

if [[ "$skip_validation" != true ]]; then
  python3 "$pipeline_root/scripts/validate_bag.py" \
    --bag "$bag" --dataset "$dataset" --mapping "$mapping"
fi

map_frame=$(config_query frames.map)
odom_frame=$(config_query frames.odom)
robot_frame=$(config_query frames.robot)
sensor_frame=$(config_query frames.sensor)
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
  hydra_config_name=$(config_query hydra_config)
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
python3 "$dataset_config" "$dataset" --mapping "$mapping" \
  --validate-hydra "$hydra_config"

if [[ -n "$labels_config_override" && "$semantics_source" != open_set ]]; then
  echo "--labels-config is valid only for open_set semantics" >&2
  exit 2
fi

labelspace_spec=$(config_query semantics.labelspace_config)
labelspace_config=$(resource_path "$labelspace_spec")
[[ -f "$labelspace_config" ]] || {
  echo "Hydra label-space config not found: $labelspace_config" >&2
  exit 2
}
semantic_pipeline_spec=$(config_query semantics.pipeline_config)
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
  model_name=$(config_query semantics.model_file)
  if [[ "$model_name" = /* ]]; then
    model_file="$model_name"
  else
    model_file="$spark_home/models/semantic_inference/$model_name"
  fi
  model_config=$(resource_path "$(config_query semantics.model_config)")
  grouping_config=$(resource_path "$(config_query semantics.grouping_config)")
  labelspace_name=$(config_query semantics.labelspace_name)
  for requirement in "$model_file" "$model_config" "$grouping_config"; do
    [[ -f "$requirement" ]] || {
      echo "closed-set resource not found: $requirement; run make models PROFILE=gpu and verify the v1 dependency snapshot" >&2
      exit 2
    }
  done
elif [[ "$semantics_source" == open_set ]]; then
  start_open_set=true
  perception_config=$(resource_path "$(config_query semantics.perception_config)")
  if [[ -n "$labels_config_override" ]]; then
    labels_config="$labels_config_override"
  else
    labels_config=$(resource_path "$(config_query semantics.labels_config)")
  fi
  for requirement in "$perception_config" "$labels_config" "$spark_home/models/semantic_inference/yoloe-26m-seg.pt"; do
    [[ -f "$requirement" ]] || {
      echo "open-set resource not found: $requirement; run make models PROFILE=gpu or fix --labels-config" >&2
      exit 2
    }
  done
fi

if [[ -z "$run_id" ]]; then
  run_id="$(date -u +%Y%m%dT%H%M%SZ)-${dataset_name}-${mapping_name}"
fi
[[ "$run_id" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "unsafe run id: $run_id" >&2; exit 2; }

run_dir="$spark_home/output/$run_id"
if [[ -e "$run_dir" ]]; then
  echo "output already exists: $run_dir (choose --run-id)" >&2
  exit 2
fi
mkdir -p "$run_dir/logs" "$run_dir/upstream"
cp "$config_path" "$run_dir/dataset.yaml"
cp "$mapping_config_path" "$run_dir/mapping.yaml"
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

launch_args=(
  "use_sim_time:=true"
  "start_closed_set:=$start_closed_set"
  "start_open_set:=$start_open_set"
  "output_dir:=$run_dir/upstream"
  "map_frame:=$map_frame"
  "odom_frame:=$odom_frame"
  "robot_frame:=$robot_frame"
  "sensor_frame:=$sensor_frame"
  "hydra_config_path:=$hydra_config"
  "labelspace_config_path:=$labelspace_config"
  "semantic_pipeline_config_path:=$semantic_pipeline_config"
  "exit_after_clock:=true"
)
if [[ "$semantics_source" == closed_set ]]; then
  launch_args+=(
    "model_file:=$model_file"
    "model_config_path:=$model_config"
    "grouping_config_path:=$grouping_config"
    "labelspace_name:=$labelspace_name"
  )
elif [[ "$semantics_source" == open_set ]]; then
  launch_args+=("perception_config_path:=$perception_config")
fi

ros2 launch spark_3dsg_pipeline pipeline.launch.yaml "${launch_args[@]}" \
  >"$run_dir/logs/pipeline.log" 2>&1 &
pipeline_pid=$!

ready=false
camera_info_topic=/input/color/camera_info
color_topic=/input/color/image_raw
perception_node=
if [[ "$semantics_source" == closed_set ]]; then
  perception_node=/semantic_inference_closed_set
elif [[ "$semantics_source" == open_set ]]; then
  perception_node=/semantic_inference
fi

# Hydra can announce its CameraInfo subscription before online perception has
# finished loading a model. In particular, the first closed-set run compiles a
# TensorRT engine before creating its RGB subscription. Do not consume a short
# bag while that blocking initialization is still in progress.
for _ in $(seq 1 300); do
  if ! kill -0 "$pipeline_pid" 2>/dev/null; then
    echo "pipeline exited during startup; see $run_dir/logs/pipeline.log" >&2
    exit 1
  fi
  camera_info_subscriptions=$(
    { ros2 topic info "$camera_info_topic" 2>/dev/null || true; } \
      | awk '/Subscription count:/ {print $3; exit}'
  )
  hydra_ready=false
  if [[ "${camera_info_subscriptions:-0}" =~ ^[0-9]+$ ]] \
      && ((camera_info_subscriptions > 0)); then
    hydra_ready=true
  fi

  perception_ready=true
  if [[ -n "$perception_node" ]]; then
    perception_ready=false
    node_info=$(ros2 node info "$perception_node" 2>/dev/null || true)
    if grep -Fq "$color_topic:" <<<"$node_info"; then
      perception_ready=true
    fi
  fi

  if [[ "$hydra_ready" == true && "$perception_ready" == true ]]; then
    ready=true
    break
  fi
  sleep 1
done
[[ "$ready" == true ]] || {
  if [[ -n "$perception_node" ]]; then
    echo "pipeline was not ready within 300 seconds; waiting for Hydra on $camera_info_topic and $perception_node on $color_topic; see $run_dir/logs/pipeline.log" >&2
  else
    echo "pipeline did not subscribe to $camera_info_topic within 300 seconds; see $run_dir/logs/pipeline.log" >&2
  fi
  exit 1
}

bag_args=("$bag" "$dataset" "$mapping")
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
PIPELINE_MAPPING="$mapping_name" \
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
    "mapping": os.environ["PIPELINE_MAPPING"],
    "bag": os.environ["PIPELINE_BAG"],
    "hydra_config": os.environ["PIPELINE_HYDRA_CONFIG"],
    "scene_structure": os.environ["PIPELINE_SCENE_STRUCTURE"],
    "semantics_source": os.environ["PIPELINE_SEMANTICS_SOURCE"],
    "visualization_profile": os.environ["PIPELINE_VISUALIZATION_PROFILE"],
    "dependency_lock_hash": hashlib.sha256(lock.read_bytes()).hexdigest(),
    "outputs": {
        "dsg": "dsg.json",
        "dsg_with_mesh": "dsg_with_mesh.json",
        "mesh": "mesh.ply" if (run_dir / "mesh.ply").is_file() else None,
        "logs": "logs",
    },
}
(run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
PY

echo "Mapping output: $run_dir"
