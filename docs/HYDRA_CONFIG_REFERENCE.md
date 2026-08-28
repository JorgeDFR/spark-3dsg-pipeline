# Hydra and Khronos configuration reference

This document explains the Hydra YAML profiles owned by this repository and the
configuration choices that are useful when adapting them. It deliberately does
not cover DAAAM, ROMAN, Hydra-Multi, robot drivers, or every experimental option
available upstream.

The executable source of truth is the workspace imported from
`dependencies/locks/adt4.lock.repos`. Hydra uses `config_utilities`: many YAML
blocks select a registered implementation through a `type` field. A key may be
valid for one implementation and invalid for another even when both occupy the
same position in the YAML tree. Treat upstream C++ declarations and registration
macros at the locked revisions as authoritative when this guide and the code
disagree.

## Repository profiles

Each dataset adapter selects one complete file with `hydra_config`:

```yaml
semantics_source: online
hydra_config: adt4.yaml
```

`scripts/run_pipeline.sh` resolves the file from the installed
`spark_3dsg_pipeline/config/hydra/` directory, passes it to `hydra_ros_node`, and
copies it to the run directory as `hydra.yaml`. Complete profiles avoid unsafe
partial merges between core Hydra and Khronos virtual implementations.

The repository intentionally provides exactly three defaults:

| File | Intended input | Active window | Generated DSG structure |
|---|---|---|---|
| `adt4.yaml` | RGB-D plus online packed YOLOE instances | Khronos `ActiveWindow` | `OBJECTS`, `MESH_PLACES`, `AGENTS`, mesh |
| `classic.yaml` | RGB-D plus online packed YOLOE instances | Khronos `ActiveWindow` with semantic TSDF | `OBJECTS`, `MESH_PLACES`, `PLACES`, `ROOMS`, `AGENTS`, mesh |
| `uhumans2.yaml` | uHumans2 office RGB-D plus recorded class IDs | Hydra `ReconstructionModule` | `OBJECTS`, `PLACES`, `ROOMS`, `BUILDINGS`, `AGENTS`, mesh |

The `spot` and `custom_rgbd` adapters select `adt4.yaml`; the `uhumans2`
adapter selects `uhumans2.yaml`. An explicit compatible profile can be selected
with `HYDRA_CONFIG`, for example:

```bash
make run \
  PROFILE=gpu \
  DATASET=spot \
  HYDRA_CONFIG=classic.yaml \
  BAG=/home/spark/data/spot
```

### Relationship to ADT4 upstream

`adt4.yaml` follows ADT4's pinned `config/default/hydra.yaml` mapping structure.
This repository additionally enables deterministic DSG/mesh output and keeps
headless execution independent of ADT4's launch framework.

`classic.yaml` starts from ADT4's pinned `config/classic/hydra.yaml`: semantic
TSDF integration, `ConnectedSemantics`, voxel-IoU tracking, and 2D surface
places. The pinned ADT4 classic file creates surface `MESH_PLACES`, but does
**not** create GVD `PLACES` or `ROOMS`. To provide the hierarchical classic
profile requested by this project, the local file explicitly adds the pinned
core-Hydra GVD generator plus `UpdatePlacesFunctor` and `UpdateRoomsFunctor`.
That small extension is repository-owned and is not presented as a verbatim
copy of upstream ADT4.

`uhumans2.yaml` is based on the pinned core-Hydra uHumans2 office demo. It does
not load Khronos and does not run YOLOE because the bag already contains
closed-set semantic ground truth.

## Configuration ownership and runtime overrides

Configuration is split by rate of change:

| Owner | Values |
|---|---|
| dataset adapter | input topic names, frames, depth contract, semantic source, playback rate |
| Hydra profile | algorithms, layer generators, thresholds, backend functors, PGMO settings |
| launch file | selected profile, frames, sensor extrinsics, output directory, clock/shutdown behavior |
| run wrapper | readiness, deterministic run directory, logs, metadata, serialization checks |

`pipeline.launch.yaml` always supplies these values through
`--config-utilities-yaml`:

```text
map_frame
odom_frame
robot_frame
sensor_frame
log_path / output directory
exit_after_clock
```

Consequently, `map_frame`, `odom_frame`, and `robot_frame` are deliberately
absent from all three profile files. There must be only one source of truth for
dataset-specific frames. The sensor frame is similarly attached to the camera's
ROS extrinsics at launch time.

The normalized ROS boundary is:

```text
/input/color/image_raw
/input/depth/image_rect
/input/color/camera_info
/input/semantic/instances
/input/semantic/labelspace
/tf
/tf_static
```

The shared semantic topic name does not imply a shared encoding:

- `InstanceImageReceiver` consumes semantic-inference's packed `32SC1`
  class/instance observations.
- `ClosedSetImageReceiver` consumes a class-ID image and uses a configured
  label space.

## How Hydra configuration composition works

Hydra configuration has four conceptual levels:

```text
root pipeline/context
  input and sensors
  active_window
  frontend (GraphBuilder)
  backend (BackendModule)
```

`paths: [khronos, khronos_ros]` asks `config_utilities` to load Khronos config
namespaces and plugin registrations. It is required by `adt4.yaml` and
`classic.yaml`; it is intentionally absent from `uhumans2.yaml`.

Common root fields include:

- `robot_id`: numeric robot prefix used in graph symbols.
- `config_verbosity`: controls config parsing diagnostics.
- `enable_zmq_interface`: enables the optional streaming interface; disabled
  here because output and inspection do not depend on it.
- `map_window`: bounds the globally retained map, independently of any
  Khronos-local temporal window.
- `labelspace`: defines semantic IDs from a message or local config.
- `mesh`: controls stored mesh attributes where a profile needs explicit
  semantic/color allocation.

Hydra also has pipeline-wide timing, logging, LCD, thread-count, and
visualization-detail settings. They are omitted here when defaults are adequate.
Do not add such fields by memory: confirm their names against the locked
`PipelineConfig` declaration.

### Spatial and temporal windows

A global spatial window such as:

```yaml
map_window: {type: spatial, max_radius_m: 14.0}
```

bounds the retained map around the robot. Khronos classic also uses a local
temporal active window:

```yaml
active_window:
  map_window: {type: temporal, window_sec: 3.0}
```

These are not duplicates: the first is pipeline/map retention policy; the
second controls what remains active for Khronos reconstruction and tracking.

## Scene-graph layers

The relevant Spark-DSG layers are:

| Layer | Meaning in these profiles |
|---|---|
| `OBJECTS` | reconstructed semantic object instances |
| `PLACES` | sparse free-space topology extracted from a GVD |
| `MESH_PLACES` | mesh-associated surface or traversability regions |
| `ROOMS` | clusters inferred from the `PLACES` topology |
| `BUILDINGS` | building-level parents used by the uHumans2 demo |
| `AGENTS` | robot trajectory/state |

`PLACES` and `MESH_PLACES` are not aliases. Room inference consumes classical
GVD `PLACES`; it cannot infer rooms merely because a graph has
`MESH_PLACES`. This is why `classic.yaml` retains ADT4 surface places and also
adds a GVD generator.

Expected hierarchies are:

```text
adt4.yaml
MESH_PLACES
    └── OBJECTS

classic.yaml
ROOMS
    └── PLACES

MESH_PLACES
    └── OBJECTS

uhumans2.yaml
BUILDINGS
    └── ROOMS
        └── PLACES
            └── OBJECTS
```

The actual set and parentage must be checked with `make inspect`; having a YAML
block present does not prove that the input generated viable nodes.

## Input and sensor configuration

All profiles use `RosInput` with one named camera. Important fields are:

- `max_receiver_queue_size`: bounds messages waiting for receiver processing.
- receiver `queue_size`: synchronization/subscription queue for camera streams.
- sensor `type: camera_info`: derives intrinsics from `CameraInfo`.
- `min_range`, `max_range`: valid integration depth interval.
- `extrinsics: {type: ros}`: resolves sensor-to-robot transform through TF; the
  concrete `sensor_frame` comes from launch.

Receiver selection is part of the semantic contract:

```yaml
# ADT4 / classic
receiver: {type: InstanceImageReceiver, queue_size: 30}

# uHumans2
receiver: {type: ClosedSetImageReceiver, queue_size: 30}
```

Hydra also supports point-cloud receivers, but none of the default profiles do.
A point-cloud adapter would be a new coherent input/profile combination, not a
topic-only edit to these RGB-D files.

### Label spaces

The online profiles use:

```yaml
labelspace: {type: from_msg}
```

The perception node publishes label names and ID roles. If the labelspace
message never arrives, objects may be absent or unlabeled even when packed
instance images are present.

uHumans2 uses `type: from_config`, an explicit office label table, and Hydra's
pinned `uhumans2_office.yaml` remap. `semantic_layers: [OBJECTS]` identifies
which closed-set labels are eligible for semantic object extraction. A
different uHumans2 scene or label taxonomy requires a separate matching label
space/remap.

## Active-window implementations

### Core Hydra `ReconstructionModule`

`uhumans2.yaml` uses the core TSDF reconstruction module:

```yaml
active_window:
  type: ReconstructionModule
  volumetric_map: {with_semantics: true}
  tsdf:
    semantic_integrator: {type: SingleLabelIntegrator}
```

Semantic mesh vertices are later clustered by `GraphBuilder.objects`; no
Khronos detector, tracker, or mesh object extractor is involved.

### Khronos `ActiveWindow`

The two online profiles use:

```yaml
paths: [khronos, khronos_ros]
active_window:
  type: ActiveWindow
```

Khronos combines reconstruction with object detection, association/tracking,
object extraction, and optional active-window sinks. Its important blocks are:

```text
volumetric_map
projective_integrator
object_detector
tracker
object_extractor
khronos_sinks
map_window                 # classic only
```

`min_output_separation` throttles output updates; lowering it increases update
frequency and cost.

### Volumetric map and integration

The main resolution controls are:

- `voxel_size`: geometry resolution and dominant memory/compute trade-off.
- `voxels_per_side`: allocation block size.
- `truncation_distance`: TSDF truncation band.
- `with_semantics`: whether dense semantic values are stored in voxels.

Smaller voxels preserve detail but increase memory and processing sharply.
Tune range/depth correctness before reducing voxel size.

`SingleLabelIntegrator` stores one semantic label estimate per voxel. Other
locked Hydra implementations include alternative MLE, binary, and first-K
semantic integration strategies; these change the voxel representation and
should only be selected after checking the exact registered fields and
downstream compatibility.

Projective integration also has interpolation choices such as nearest,
bilinear, and adaptive interpolation in relevant Hydra components. They trade
speed, edge behavior, and robustness to missing depth. The defaults here are
inherited unless the pinned ADT4 configuration specifies a field.

## Khronos object pipeline

The default online profile is instance-centric:

```text
InstanceImageReceiver
  -> InstanceForwarding
  -> MaxIouTracker(track_by: pixels)
  -> MeshObjectExtractor
```

The classic profile also integrates semantic voxels and uses:

```text
InstanceImageReceiver
  -> ConnectedSemantics
  -> MaxIouTracker(track_by: voxels)
  -> MeshObjectExtractor
```

### `InstanceForwarding`

This detector forwards received instance masks into the Khronos observation
pipeline. Relevant tuning includes minimum cluster size and valid range. It is
appropriate when upstream perception has already separated object instances.

Khronos can apply instance filters, including category/background filtering in
compatible revisions. If adding a filter, check whether it operates on numeric
label roles, names, or open-vocabulary metadata; an incorrect background policy
can silently remove every object.

### `ConnectedSemantics`

This detector groups connected semantic voxels. Its resolution, connectivity,
2D/3D mode, range, and minimum cluster size jointly determine whether a class
becomes a candidate object. It requires `with_semantics: true`; using it with a
geometry-only volume is internally inconsistent.

### `MaxIouTracker`

The tracker associates observations with object tracks. Important fields are:

- `track_by`: `pixels` for forwarded image instances or `voxels` for connected
  semantic reconstruction.
- `min_semantic_iou`: semantic-consistency threshold.
- `min_cross_iou`: cross-observation association threshold.
- `min_num_observations`: maturity requirement before extraction.
- `voxel_size`: association resolution in voxel mode.
- `temporal_window`: retained association horizon in the pinned classic ADT4
  configuration.

If objects never appear, reduce maturity/cluster thresholds only after proving
that synchronized semantic observations reach Hydra.

### `MeshObjectExtractor`

This stage turns mature tracks into mesh-backed object nodes. Its main gates are:

- object allocation confidence;
- minimum/maximum volume;
- reconstruction confidence and observation count;
- dynamic displacement threshold;
- `only_extract_reconstructed_objects`;
- reconstruction resolution.

`object_reconstruction_resolution` uses the semantics defined by the pinned
Khronos version; do not assume its sign/units from another branch. The
`visualizer_classification` spelling is also version-specific and is retained
from the pinned ADT4 snapshot.

`ActiveWindowVisualizer` is an optional sink that publishes debugging markers.
It must not be required for headless graph generation.

## `GraphBuilder` frontend

The frontend consumes active-window output and creates/updates the DSG. Common
controls include:

- `enable_mesh_objects`: cluster semantic mesh labels into objects in core
  Hydra; false for Khronos-provided object tracks.
- `serialize_dsg_mesh`: retain the mesh with serialized DSG output.
- `clear_object_meshes`: remove temporary per-object mesh storage after graph
  integration where supported.
- `pgmo`: mesh/deformation graph resolution and time horizon.
- `graph_connector`: declares allowed inter-layer parent/child connections.
- `graph_updater`: declares per-layer prefix and matching strategy.

The online profiles connect `OBJECTS` below `MESH_PLACES` and use an
`IoUNodeMatcher`. Matcher thresholds trade duplicate nodes against incorrect
merges. `matcher` in `GraphBuilder.graph_updater` and `node_matcher` inside
`GenericUpdateFunctor` belong to different config types and must not be renamed
to look consistent.

### Object generation in core Hydra

The uHumans2 frontend enables mesh object clustering:

```yaml
enable_mesh_objects: true
objects:
  min_cluster_size: 40
  cluster_tolerance: 0.25
  bounding_box_type: RAABB
```

These fields apply to semantic mesh clustering, not Khronos tracking. Increasing
cluster tolerance joins nearby vertices; decreasing it fragments objects.

## Place-generation modes

Hydra/Khronos exposes three place concepts relevant here.

### Traversability `MESH_PLACES`

`adt4.yaml` uses a `HeightTraversabilityEstimator` followed by
`RegionGrowingTraversabilityClustering`:

```text
mesh geometry
  -> height/traversability classification
  -> region growing
  -> MESH_PLACES
```

Important estimator fields are height below/above, confidence,
traversability threshold, and pessimistic handling. Important clustering fields
are maximum region radius and number of orientation bins. These settings are
sensitive to gravity alignment and floor geometry.

### Surface/2D `MESH_PLACES`

ADT4 classic's `place_2d` generator clusters compatible surface mesh points.
Relevant controls include cluster tolerance and size limits, minimum final place
points, maximum neighbor height difference, overlap threshold, and the pinned
purity fields. Its backend partner is `Update2dPlacesFunctor`.

This representation is mesh-associated and does not substitute for GVD
`PLACES` in room inference.

### Free-space GVD `PLACES`

The GVD generator derives a sparse free-space topology from the TSDF. Key
controls are:

- `max_distance_m`: maximum retained obstacle distance.
- `min_distance_m`: clearance floor.
- `min_diff_m`: GVD parent-distance separation.
- Voronoi angle/L1 separation parameters.
- `compression_distance_m`: graph simplification scale.
- `min_node_distance_m`: minimum new-node spacing.
- `node_merge_distance_m`: nearby-node merge threshold.
- overlap and free-space edge policies.
- TSDF interpolation/downsampling.

Over-compression or aggressive merging can erase bottlenecks needed by the room
finder. Tune GVD topology before room dilation thresholds.

Frontier generation is available in Hydra configurations but is not enabled by
the three defaults because it is not required for offline DSG construction.

## Rooms and buildings

Rooms require both a populated `PLACES` layer and a backend room updater:

```yaml
frontend:
  freespace_places: {type: gvd, ...}
backend:
  update_functors:
    places: {type: UpdatePlacesFunctor}
    rooms:
      type: UpdateRoomsFunctor
      room_finder: {...}
```

The room finder examines changes in connectivity as the place graph is dilated.
Important fields include:

- minimum/maximum dilation;
- component and room size thresholds;
- dilation threshold mode;
- minimum lifetime length;
- plateau ratio;
- clustering mode;
- dilation-difference threshold.

Common clustering modes in compatible Hydra revisions include neighbor-based,
modularity variants, ground-truth, and none. The default profiles use
`NEIGHBORS`. Enum names and available fields are revision-specific.

Tune rooms in this order:

1. verify dense enough, connected `PLACES`;
2. verify place edges and bottlenecks;
3. adjust dilation range;
4. adjust component/room size;
5. adjust plateau/lifetime behavior;
6. only then compare clustering modes.

uHumans2 adds `UpdateBuildingsFunctor` above rooms. `classic.yaml` intentionally
stops at rooms.

## Backend and PGMO

`BackendModule` maintains the persistent graph and deformation/pose graph.
Relevant controls are:

- `optimize_on_lc`: run optimization after loop closure.
- `add_places_to_deformation_graph`: include GVD places in deformation
  constraints; true in hierarchical profiles.
- `enable_node_merging`: permits compatible persistent-node merging where used.
- DSG/mesh publication and serialization intervals.
- `update_functors`: one updater for each generated semantic layer family.
- `pgmo`: optimizer, interpolation, priors, and covariances.

Updater responsibilities in this repository are:

| Functor | Layer/purpose |
|---|---|
| `UpdateAgentsFunctor` | trajectory/agent state |
| `UpdateObjectsFunctor` | standard persistent objects |
| `GenericUpdateFunctor` | ADT4 object matching/merge policy |
| `UpdatePlacesFunctor` | classical GVD `PLACES` |
| `Update2dPlacesFunctor` | surface `MESH_PLACES` |
| `UpdateRegionGrowingTraversabilityFunctor` | traversability `MESH_PLACES` |
| `UpdateRoomsFunctor` | `ROOMS` from `PLACES` |
| `UpdateBuildingsFunctor` | building parent layer |

Frontend generation and backend updater configuration must change together. A
frontend block without its updater may create transient nodes that never become
the expected persistent graph; an updater without source nodes has nothing to
process.

PGMO fields used here include `run_mode`, trajectory embedding interval,
interpolation points/horizon, initial prior, robust optimizer, and covariance
terms for odometry, loop closures, mesh/pose constraints, places, and merges.
Covariances are information-model choices, not generic “accuracy” sliders.
Change them only after TF, timestamps, odometry, and geometry are correct.

## Profile walkthroughs

### `adt4.yaml`

```text
YOLOE packed instances
  -> InstanceImageReceiver
  -> InstanceForwarding
  -> pixel MaxIoU tracking
  -> MeshObjectExtractor
  -> OBJECTS

mesh
  -> HeightTraversabilityEstimator
  -> region-growing MESH_PLACES
  -> GenericUpdateFunctor + traversability updater
```

Dense TSDF semantics are disabled. This is why the mesh should be visualized
with RGB/geometry coloring rather than expecting semantic vertex colors.

### `classic.yaml`

```text
packed instances + semantic TSDF
  -> ConnectedSemantics
  -> voxel MaxIoU tracking
  -> MeshObjectExtractor
  -> OBJECTS

mesh -> ADT4 place_2d -> MESH_PLACES
TSDF -> core-Hydra GVD -> PLACES -> ROOMS
```

It deliberately generates both place representations. `MESH_PLACES` retain the
ADT4 classic surface structure; `PLACES` support the room hierarchy.

### `uhumans2.yaml`

```text
recorded class IDs
  -> ClosedSetImageReceiver
  -> semantic ReconstructionModule
  -> semantic mesh object clustering -> OBJECTS
  -> GVD -> PLACES -> ROOMS -> BUILDINGS
```

The adapter uses bag frame `world` for map and odometry. Backend TF publication
is disabled to avoid a self-transform. This profile is specifically for the
office demo taxonomy.

## Configuration audit pitfalls

The older reference contained several useful warnings from auditing generated
ADT4 files. They remain important when updating profiles:

1. **Duplicate YAML keys:** a generated file may repeat a block such as
   `projective_integrator`. Standard YAML loaders often keep only the last
   occurrence. Never rely on that; consolidate the intended fields.
2. **Namespace/context fields:** values such as `enable_zmq_interface`, ROS
   publication intervals, and serialization flags may be consumed by different
   ROS context/publisher layers rather than the nearest C++ config struct.
   Preserve known-good placement from the pinned source and verify parser output.
3. **Frontend serialization:** `serialize_dsg_mesh` under `frontend` controls
   graph mesh retention; backend mesh publication is a separate concern.
4. **Object mesh clearing:** `clear_object_meshes` affects temporary object mesh
   data, not whether the final DSG has object nodes.
5. **`matcher` vs `node_matcher`:** these names belong to distinct registered
   config types. Do not mechanically normalize them.
6. **Version-specific spelling:** fields such as
   `visualizer_classification`, tracker `temporal_window`, older surface-place
   purity controls, and `Update2dPlacesFunctor.min_size` must be checked against
   the locked revision before carrying them to another branch.
7. **Virtual type replacement:** changing `type: ActiveWindow` to
   `ReconstructionModule` does not make Khronos-only child fields valid. Use a
   complete profile.

Hydra config logs with increased `config_verbosity` are often more useful than
guessing. Watch for unknown fields, missing required fields, and unregistered
types.

## Auditing against the Docker workspace

Run source/config inspection inside the built container so searches use the
same revisions as the executable:

```bash
make shell PROFILE=core

source /opt/ros/jazzy/setup.bash
source /home/spark/ros_ws/install/setup.bash

rg 'DECLARE_CONFIG|Config::Config|Config\{' /home/spark/ros_ws/src/hydra
rg 'InstanceForwarding|ConnectedSemantics|MaxIouTracker' /home/spark/ros_ws/src/khronos
rg 'UpdateRoomsFunctor|RoomFinder' /home/spark/ros_ws/src/hydra
rg 'visualizer_classification|temporal_window|min_size' /home/spark/ros_ws/src
```

Useful searches are:

- registered implementations of the virtual base in question;
- the exact config struct constructor/visitor that parses YAML;
- defaults and required fields;
- plugin registration translation units;
- upstream example YAML at the same commit.

Do not validate a locked workspace against documentation from floating `main`.

## Debugging by missing output

### No `OBJECTS`

Check, in order:

1. color, depth, semantic image, and `CameraInfo` publishers/subscribers;
2. semantic image encoding and timestamp synchronization;
3. labelspace publication or configured label roles;
4. camera intrinsics and sensor TF;
5. detector candidates/visualizer markers;
6. tracker maturity and IoU thresholds;
7. object extractor confidence, volume, observation, and reconstruction gates;
8. frontend/backend object updater logs.

### No `MESH_PLACES`

For traversability mode, verify gravity/frame alignment, mesh existence,
height bounds, confidence threshold, and clustering radius. For surface mode,
verify labeled/usable mesh points, cluster tolerance, neighbor height, minimum
cluster/final sizes, and `Update2dPlacesFunctor`.

### No classical `PLACES`

Verify TSDF allocation, GVD distance thresholds, interpolator/downsampling,
component size, graph compression, and `UpdatePlacesFunctor`. Confirm inspection
is reading `PLACES`, not `MESH_PLACES`.

### No `ROOMS`

First require non-empty, connected `PLACES`. Then verify
`UpdateRoomsFunctor`, dilation bounds, component/room sizes, and clustering mode.
Room thresholds cannot recover topology that the GVD generator removed.

### Rooms exist but lack semantic categories

Room topology and room semantic naming are separate problems. These defaults
create structural `ROOMS`; they do not promise labels such as office or kitchen.
Semantic region classification is a future optional layer.

## Tuning order for a new dataset

1. **Geometry:** depth scale/encoding, timestamps, intrinsics, TF, range,
   voxel size, truncation distance, and non-empty mesh.
2. **Objects:** semantic contract and label roles, candidates, tracking, then
   extraction thresholds.
3. **Places:** choose the intended representation, then tune its geometry and
   topology.
4. **Rooms:** tune only after GVD `PLACES` are stable.
5. **Backend:** loop closure, merging, PGMO, and covariances last.

Changing several stages simultaneously makes failures hard to localize. Keep
the copied `hydra.yaml`, dataset adapter, metadata, and logs from every run used
for comparison.

## Adding or updating a profile

Add a profile only for a coherent graph/input architecture:

1. choose the receiver and labelspace for the semantic payload;
2. choose exactly one active-window implementation;
3. configure object and place generators compatible with its output;
4. add corresponding backend functors;
5. omit dataset-specific frame keys because launch owns them;
6. assert the structure in repository tests;
7. parse/start it in the built Docker image;
8. inspect every expected DSG layer programmatically.

Do not modify imported upstream repositories. Do not merge fields from ADT4,
DAAAM, and a different Hydra branch into one file merely because their YAML keys
look similar.

## Quick key index

| Goal | Primary configuration area |
|---|---|
| load Khronos plugins | root `paths` |
| receive online packed instances | `input...receiver: InstanceImageReceiver` |
| receive closed-set class IDs | `input...receiver: ClosedSetImageReceiver` |
| configure semantic roles/names | root `labelspace` and remap |
| set reconstruction resolution | `active_window.volumetric_map.voxel_size` |
| enable dense semantics | `active_window.volumetric_map.with_semantics` |
| forward supplied instances | `active_window.object_detector: InstanceForwarding` |
| cluster semantic voxels | `active_window.object_detector: ConnectedSemantics` |
| tune association | `active_window.tracker` |
| tune object mesh extraction | `active_window.object_extractor` |
| create core semantic-mesh objects | `frontend.enable_mesh_objects` and `objects` |
| create traversability regions | `frontend.traversability_places` |
| create surface regions | `frontend.surface_places` |
| create free-space topology | `frontend.freespace_places` |
| connect layer hierarchy | `frontend.graph_connector` |
| match transient graph nodes | `frontend.graph_updater` |
| maintain persistent layers | `backend.update_functors` |
| infer rooms | `UpdateRoomsFunctor.room_finder` |
| include places in deformation | `backend.add_places_to_deformation_graph` |
| tune graph optimization | `backend.pgmo` |
| set dataset frames | dataset YAML plus `pipeline.launch.yaml`, never profile |

## Pinned sources

- [ADT4 default configuration](https://github.com/MIT-SPARK/Awesome-DCIST-T4/blob/10263e7b9cce9ae215d69264fcd224dabfb51406/dcist_launch_system/config/default/hydra.yaml)
- [ADT4 classic configuration](https://github.com/MIT-SPARK/Awesome-DCIST-T4/blob/10263e7b9cce9ae215d69264fcd224dabfb51406/dcist_launch_system/config/classic/hydra.yaml)
- [Hydra uHumans2 configuration](https://github.com/MIT-SPARK/Hydra/blob/1e89319efd59d73bd189664bf8fa6f9c7e56c5ca/hydra/config/datasets/uhumans2.yaml)
- [Hydra-ROS uHumans2 input configuration](https://github.com/MIT-SPARK/Hydra/blob/1e89319efd59d73bd189664bf8fa6f9c7e56c5ca/hydra_ros/config/datasets/uhumans2.yaml)
- [Hydra uHumans2 office label space](https://github.com/MIT-SPARK/Hydra/blob/1e89319efd59d73bd189664bf8fa6f9c7e56c5ca/hydra/config/label_spaces/uhumans2_office_label_space.yaml)

The ADT4 baseline is recorded in `dependencies/UPSTREAM_BASELINE.md`. Update
this document and profile tests when the entire compatible lock is deliberately
migrated; never silently copy fields from a floating branch.
