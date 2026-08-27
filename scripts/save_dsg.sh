#!/usr/bin/env bash
set -euo pipefail

run_dir="${1:?usage: save_dsg.sh RUN_DIR}"
upstream="$run_dir/upstream"
[[ -d "$upstream" ]] || { echo "missing upstream output directory: $upstream" >&2; exit 1; }

if [[ ! -f "$run_dir/dsg.json" ]]; then
  source_dsg=$(find "$upstream" -type f \( -name 'dsg.json' -o -name '*dsg*.json' -o -name 'backend.json' \) -print | sort | tail -n 1)
  [[ -n "$source_dsg" ]] || { echo "mapping finished without a DSG JSON under $upstream" >&2; exit 1; }
  cp "$source_dsg" "$run_dir/dsg.json"
fi

if [[ ! -f "$run_dir/mesh.ply" ]]; then
  source_mesh=$(find "$upstream" -type f -name '*.ply' -print | sort | tail -n 1)
  [[ -z "$source_mesh" ]] || cp "$source_mesh" "$run_dir/mesh.ply"
fi

if [[ ! -f "$run_dir/mesh.ply" ]]; then
  python3 - "$run_dir/dsg.json" "$run_dir/mesh.ply" <<'PY'
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
echo "DSG saved: $run_dir/dsg.json"
