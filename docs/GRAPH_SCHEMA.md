# Graph and output schema

A successful run directory contains:

```text
<run-id>/
  dsg.json              Spark-DSG serialization (required)
  mesh.ply              separate mesh when emitted upstream (optional if embedded)
  metadata.json         run/output schema and dependency-lock digest
  dataset.yaml          exact resolved adapter
  adt4.lock.repos       exact source revisions used by the image
  logs/
  upstream/             unmodified Hydra/Khronos experiment output
```

The v1 semantic contract is:

- `OBJECTS`: tracked/extracted object nodes with at least one meaningful semantic label
- `MESH_PLACES`: traversability regions produced from the mesh
- `AGENTS`: robot trajectory nodes
- mesh: embedded in the DSG or present as `mesh.ply`

Run `inspect_dsg.py --json` for a stable summary intended for tests and downstream automation. `--require-v1` fails unless every v1 acceptance condition is present.
