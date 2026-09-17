# Graph schema

Hierarchical output contains `OBJECTS`, `PLACES`, `ROOMS`, `BUILDINGS`, and
decoupled `MESH_PLACES`, plus `AGENTS` and a mesh when available. The semantic
hierarchy is `OBJECTS -> PLACES -> ROOMS -> BUILDINGS`; surface places are not
object parents.

Khronos output contains `OBJECTS` and `MESH_PLACES`, plus optional `AGENTS` and
mesh data. The ADT4 connector associates objects with mesh places.

`scripts/inspect_dsg.py --require-pipeline-output` checks nonempty objects,
mesh places, trajectory, mesh vertices, and at least one meaningful object
label. It checks output contents, not dependency versions.

Each mapping run exports both `dsg.json` without embedded mesh data and a
self-contained `dsg_with_mesh.json`, as well as a standalone `mesh.ply`.
Offline visualization automatically prefers the mesh-bearing JSON sibling.
