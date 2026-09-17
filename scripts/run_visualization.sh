#!/usr/bin/env bash
set -euo pipefail

dataset=
dsg=
profile=
pipeline_root="${PIPELINE_ROOT:-/home/spark/spark-3dsg-pipeline}"
dataset_config="$pipeline_root/scripts/dataset_config.py"

while (($#)); do
  case "$1" in
    --dataset) dataset="${2:?missing value for --dataset}"; shift 2 ;;
    --dsg) dsg="${2:?missing value for --dsg}"; shift 2 ;;
    --profile) profile="${2:?missing value for --profile}"; shift 2 ;;
    *) echo "unknown visualization argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -n "$dataset" ]]; then
  map_frame=$(python3 "$dataset_config" "$dataset" --get frames.map)
  use_sim_time=$(python3 "$dataset_config" "$dataset" --get use_sim_time)
  dataset_profile=$(python3 "$dataset_config" "$dataset" --get visualization.profile)
  if [[ -n "$profile" && "$profile" != "$dataset_profile" ]]; then
    echo "visualization profile '$profile' conflicts with dataset '$dataset' profile '$dataset_profile'" >&2
    exit 2
  fi
  profile="$dataset_profile"
else
  map_frame=map
  use_sim_time=false
fi

[[ "$profile" == hierarchical || "$profile" == khronos ]] || {
  echo "choose --dataset or --profile hierarchical|khronos" >&2
  exit 2
}

file_mode=false
if [[ -n "$dsg" ]]; then
  [[ -f "$dsg" ]] || { echo "DSG JSON not found: $dsg" >&2; exit 2; }
  if [[ "$(basename "$dsg")" == dsg.json ]]; then
    mesh_dsg="$(dirname "$dsg")/dsg_with_mesh.json"
    if [[ -f "$mesh_dsg" ]]; then
      echo "Using mesh-bearing DSG for visualization: $mesh_dsg"
      dsg="$mesh_dsg"
    fi
  fi
  python3 - "$dsg" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    with path.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
except (OSError, UnicodeError, json.JSONDecodeError) as error:
    raise SystemExit(f"invalid DSG JSON '{path}': {error}")
mesh = data.get("mesh")
if not isinstance(mesh, dict) or not mesh.get("points") or not mesh.get("faces"):
    print(
        f"warning: DSG JSON '{path}' does not contain a non-empty embedded mesh; "
        "RViz will show the graph without its mesh",
        file=sys.stderr,
    )
PY
  file_mode=true
  use_sim_time=false
fi

package_share=$(ros2 pkg prefix --share spark_3dsg_pipeline)
visualizer_config="$package_share/config/visualization/$profile.yaml"
[[ -f "$visualizer_config" ]] || {
  echo "visualizer config not found: $visualizer_config" >&2
  exit 2
}

launch_args=(
  "map_frame:=$map_frame"
  "use_sim_time:=$use_sim_time"
  "visualizer_config_path:=$visualizer_config"
  "file_mode:=$file_mode"
)
if [[ "$file_mode" == true ]]; then
  launch_args+=("scene_graph:=$dsg")
fi

exec ros2 launch spark_3dsg_pipeline visualization.launch.yaml "${launch_args[@]}"
