#!/usr/bin/env bash
set -euo pipefail

run_dir="${1:?usage: save_dsg.sh RUN_DIR}"
upstream="$run_dir/upstream"
[[ -d "$upstream" ]] || { echo "missing upstream output directory: $upstream" >&2; exit 1; }

source_dsg=$(find "$upstream" -type f -path '*/backend/dsg.json' -print | sort | tail -n 1)
if [[ -z "$source_dsg" ]]; then
  source_dsg=$(find "$upstream" -type f -name 'backend.json' -print | sort | tail -n 1)
fi
if [[ -z "$source_dsg" ]]; then
  source_dsg=$(find "$upstream" -type f -path '*/backend/*' -name '*dsg*.json' -print | sort | tail -n 1)
fi
[[ -n "$source_dsg" ]] || {
  echo "mapping finished without a backend DSG JSON under $upstream" >&2
  exit 1
}

# Normalize the selected backend graph and keep mesh data in mesh.ply. This
# makes the public dsg.json small and consistently loadable by Spark-DSG.
python3 - "$source_dsg" "$run_dir/dsg.json" <<'PY'
import sys
import spark_dsg

graph = spark_dsg.DynamicSceneGraph.load(sys.argv[1])
graph.save(sys.argv[2], include_mesh=False)
PY
echo "Mesh-free backend DSG saved: $run_dir/dsg.json"

source_mesh_dsg=$(
  find "$(dirname "$source_dsg")" -maxdepth 1 -type f \
    -name '*dsg*mesh*.json' -print | sort | tail -n 1
)
[[ -n "$source_mesh_dsg" ]] || source_mesh_dsg="$source_dsg"

if [[ ! -f "$run_dir/mesh.ply" ]]; then
  source_mesh=$(find "$upstream" -type f -path '*/backend/*.ply' -print | sort | tail -n 1)
  if [[ -z "$source_mesh" ]]; then
    source_mesh=$(find "$upstream" -type f -name '*.ply' -print | sort | tail -n 1)
  fi
  [[ -z "$source_mesh" ]] || cp "$source_mesh" "$run_dir/mesh.ply"
fi

if [[ ! -f "$run_dir/mesh.ply" ]]; then
  python3 - "$source_mesh_dsg" "$run_dir/mesh.ply" <<'PY'
import sys
import spark_dsg

graph = spark_dsg.DynamicSceneGraph.load(sys.argv[1])
if graph.has_mesh() and graph.mesh.num_vertices() > 0:
    vertices = graph.mesh.get_vertices()
    faces = graph.mesh.get_faces()
    with open(sys.argv[2], "w", encoding="ascii") as stream:
        stream.write("ply\nformat ascii 1.0\n")
        stream.write(f"element vertex {vertices.shape[1]}\n")
        stream.write("property float x\nproperty float y\nproperty float z\n")
        stream.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
        stream.write(f"element face {faces.shape[1]}\n")
        stream.write("property list uchar int vertex_indices\nend_header\n")
        for i in range(vertices.shape[1]):
            xyz = vertices[:3, i]
            rgb = vertices[3:6, i]
            stream.write(
                f"{xyz[0]} {xyz[1]} {xyz[2]} "
                f"{int(rgb[0])} {int(rgb[1])} {int(rgb[2])}\n"
            )
        for i in range(faces.shape[1]):
            face = faces[:, i]
            stream.write(f"3 {int(face[0])} {int(face[1])} {int(face[2])}\n")
PY
fi

test -s "$run_dir/dsg.json"
echo "3D Scene Graph saved: $run_dir/dsg.json"
