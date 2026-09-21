# Hydra configuration reference

For the high-impact parameter guide, tuning directions, and the locked-source
audit of unsupported keys, see [Hydra and Khronos parameter
tuning](HYDRA_TUNING.md).

## Profiles

| Config | Reconstruction | Receiver | Layers |
| --- | --- | --- | --- |
| `uhumans2.yaml` | Hydra `ReconstructionModule` | `ClosedSetImageReceiver` | OBJECTS, PLACES, ROOMS, BUILDINGS, MESH_PLACES |
| `classic.yaml` | Hydra `ReconstructionModule` | `ClosedSetImageReceiver` | OBJECTS, PLACES, ROOMS, BUILDINGS, MESH_PLACES |
| `adt4.yaml` | Khronos `ActiveWindow` | `InstanceImageReceiver` | OBJECTS, MESH_PLACES |

`classic.yaml` is structurally based on the pinned Hydra uHumans2 architecture,
not on ADT4. Its taxonomy is supplied by the `closed_set` mapping recipe as a
separate Hydra label-space file. The `recorded` recipe uses the same graph
architecture but has a dedicated uHumans2 class-ID taxonomy/remap overlay.

For hierarchical configs, `surface_places: place_2d` creates decoupled
`MESH_PLACES`; `freespace_places: gvd` creates hierarchical `PLACES`.
`UpdateObjectsFunctor`, `UpdatePlacesFunctor`, `UpdateRoomsFunctor`, and
`UpdateBuildingsFunctor` form `OBJECTS -> PLACES -> ROOMS -> BUILDINGS`.
`Update2dPlacesFunctor` updates the separate surface representation.

ADT4 follows the Awesome-DCIST-T4 commit recorded in
`dependencies/UPSTREAM_BASELINE.md`. It uses instance forwarding, IoU tracking,
mesh-object extraction, traversability mesh places, and no unused classical
place/room/building functors.

Frames and sensor extrinsics are launch overlays, not embedded in mapper files.
Label names are not embedded in `classic.yaml`; open-set labels are not embedded
in `yoloe.yaml`.
