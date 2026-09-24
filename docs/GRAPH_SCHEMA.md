# Graph structure and Hydra profiles

The mapping recipe selects the Hydra/Khronos profile, semantic inputs, and
visualizer together. This reference describes the resulting layers and files.
For individual parameters, see [Hydra and Khronos tuning](HYDRA_TUNING.md).

## Profiles

| Recipe | Hydra config | Reconstruction | Structure |
| --- | --- | --- | --- |
| `recorded` | `uhumans2.yaml` | Hydra `ReconstructionModule` | Hierarchical |
| `closed_set` | `classic.yaml` | Hydra `ReconstructionModule` | Hierarchical |
| `open_set` | `adt4.yaml` | Khronos `ActiveWindow` | Objects and mesh places |

`classic.yaml` follows the pinned Hydra uHumans2 architecture. The `closed_set`
recipe supplies its taxonomy through a separate Hydra label-space file.
The `recorded` recipe uses the same graph architecture with a dedicated
uHumans2 class-ID taxonomy and remap overlay.

## Hierarchical graph

Objects belong to places, places belong to rooms, and rooms belong to buildings.
Mesh places form a separate surface representation and are not object parents.

| Layer | Representation | Configuration component |
| --- | --- | --- |
| `OBJECTS` | Semantic objects extracted from the mesh | `UpdateObjectsFunctor` |
| `PLACES` | Freespace places | `freespace_places: gvd` and `UpdatePlacesFunctor` |
| `ROOMS` | Room grouping | `UpdateRoomsFunctor` |
| `BUILDINGS` | Building grouping | `UpdateBuildingsFunctor` |
| `MESH_PLACES` | Decoupled surface places | `surface_places: place_2d` and `Update2dPlacesFunctor` |

The graph can also contain `AGENTS` trajectory data and mesh geometry.
Both `classic.yaml` and `uhumans2.yaml` use semantic TSDF reconstruction and
mesh-object extraction.

## Khronos graph

The ADT4 profile follows the Awesome-DCIST-T4 revision recorded in the
[upstream baseline](../dependencies/UPSTREAM_BASELINE.md). It uses instance
forwarding, IoU tracking, and mesh-object extraction.

| Layer | Representation | Relationship |
| --- | --- | --- |
| `OBJECTS` | Reconstructed objects from tracked instances | Associated with mesh places |
| `MESH_PLACES` | Traversability surface places | Parents of objects through the ADT4 connector |

`AGENTS` trajectory data and mesh geometry may also be present. This profile
does not use the classical place, room, or building update functors.

## Configuration boundaries

| Setting | Configured through |
| --- | --- |
| Topics, frames, depth units | Dataset adapter and launch overlays |
| Sensor extrinsics | Recorded transforms and launch overlays |
| Semantic source and matching resources | Mapping recipe |
| Closed-set taxonomy | Separate Hydra label-space config |
| Open-set vocabulary | Labels overlay selected with `LABELS_CONFIG` |
| Reconstruction and graph update parameters | Selected Hydra profile |

Frames and sensor extrinsics are not embedded in mapper files. Label names are
not embedded in `classic.yaml`, and open-set vocabulary is separate from
`yoloe.yaml`.

## Exported files

Each successful mapping run writes to `/home/spark/output/<run-id>`.

| File | Contents |
| --- | --- |
| `dsg.json` | Spark-DSG graph without embedded mesh data |
| `dsg_with_mesh.json` | Self-contained graph with mesh data |
| `mesh.ply` | Standalone mesh |
| `metadata.json` | Run settings, output paths, and dependency-lock hash |
| `dataset.yaml`, `mapping.yaml` | Selected dataset and mapping configs |

Runs also retain resolved semantic/Hydra inputs and logs. Offline visualization
prefers `dsg_with_mesh.json` when it is a sibling of the selected `dsg.json`.

## Inspect a graph

```bash
make inspect DSG=/home/spark/output/run/dsg.json \
  INSPECT_ARGS=--require-pipeline-output
```

The inspector checks nonempty objects, mesh places, trajectory, mesh vertices,
and at least one meaningful object label. These are graph-content checks.
Dependency versions are recorded separately in run metadata.
