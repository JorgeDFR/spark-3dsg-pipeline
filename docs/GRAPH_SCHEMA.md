# Graph and output schema

A successful run directory contains:

```text
<run-id>/
  dsg.json              backend Spark-DSG without an embedded mesh (required)
  mesh.ply              separate mesh when available upstream (optional)
  metadata.json         run/output schema and dependency-lock digest
  dataset.yaml          exact resolved adapter
  hydra.yaml            exact complete Hydra profile selected for the run
  adt4.lock.repos       exact source revisions used by the image
  logs/
  upstream/             unmodified Hydra/Khronos experiment output
```

The v1 semantic contract is:

- `OBJECTS`: tracked/extracted object nodes with at least one meaningful semantic label
- `MESH_PLACES`: traversability regions produced from the mesh
- `AGENTS`: robot trajectory nodes
- mesh: present as `mesh.ply`

The uHumans2 core-Hydra demo expects surface `MESH_PLACES` plus classical GVD
`PLACES`, `ROOMS`, and `BUILDINGS` in addition to `OBJECTS`, `AGENTS`, and the
mesh.

The classic profile retains ADT4 surface `MESH_PLACES` and additionally creates
GVD `PLACES` and structural `ROOMS`; it does not add a `BUILDINGS` layer.

Run `inspect_dsg.py --json` for a stable summary of both `PLACES` and
`MESH_PLACES` structures and edges grouped by endpoint layer type. Inspection
omits the agent trajectory and mesh statistics; `--require-v1` still checks
those components as part of the Spot/ADT4 acceptance contract.
