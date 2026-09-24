# Hydra and Khronos parameter tuning

This is a focused guide to the parameters that most affect map quality,
scene-graph contents, data association, and runtime cost. It is not an exhaustive
schema. The authoritative schemas are the `declare_config(...)` functions in the
exact upstream revisions recorded in
[`dependencies/locks/v1.lock.repos`](../dependencies/locks/v1.lock.repos).

The paths and behavior below apply to the repository's locked Hydra revision
`1e89319efd59d73bd189664bf8fa6f9c7e56c5ca` and Khronos revision
`a50f3e21967c32d6bc160dafbe5c26c6188c6386`. Re-audit this document when those
locks change.

## Pipeline selection

| Config | Reconstruction and object source | Scene-graph structure |
| --- | --- | --- |
| `classic.yaml` | Hydra semantic TSDF and semantic-mesh clustering | Hierarchical |
| `uhumans2.yaml` | Hydra semantic TSDF and semantic-mesh clustering | Hierarchical |
| `adt4.yaml` | Khronos instance forwarding, tracking, and object reconstruction | Objects and mesh places |

The classic and uHumans2 profiles do not track 2D instance IDs between frames.
They cluster mesh vertices of each semantic class. ADT4 forwards instance
detections to Khronos and explicitly tracks them.

## Sensor geometry and input buffering

Bad poses, extrinsics, timestamps, camera calibration, or depth registration
cannot be repaired by object-association thresholds. Check those inputs before
tuning the mapper.

| Parameter | Effect and tuning direction |
| --- | --- |
| `input.inputs.<sensor>.sensor.min_range` | Rejects depth closer than this distance. Raise it to remove invalid near-field depth. Lowering it admits more close geometry. |
| `input.inputs.<sensor>.sensor.max_range` | Rejects depth beyond this distance. Reduce it when distant depth is noisy. Increasing it expands coverage and computation. |
| `input.inputs.<sensor>.receiver.queue_size` | ROS receiver backlog. Increase only to tolerate bursts. A large queue can turn overload into latency. |
| `input.max_receiver_queue_size` | Limits queued synchronized input packets. Keeping this small favors current data over delayed processing. |
| `map_window.max_radius_m` | Radius of the active volumetric map around the robot. A larger radius retains more local context but costs memory and processing time. |

The sensor range should agree with the valid range of the registered depth
stream. These values are not object-size filters.

## Volumetric reconstruction and mesh quality

These parameters have the largest quality/performance tradeoffs in both Hydra
and Khronos.

| Parameter | Effect and tuning direction |
| --- | --- |
| `active_window.volumetric_map.voxel_size` | Main map resolution in metres. Smaller voxels preserve finer geometry and improve small-object separation, but increase memory and runtime steeply. |
| `active_window.volumetric_map.truncation_distance` | TSDF truncation band in metres. It should span several voxels. Too small is brittle to depth noise. Too large smooths surfaces and increases update work. |
| `active_window.volumetric_map.voxels_per_side` | Voxels per allocation block. This mainly changes allocation granularity and performance, not nominal spatial resolution. |
| `active_window.volumetric_map.with_semantics` | Enables semantic storage for classic Hydra. Keep it enabled when mesh objects are extracted from semantic labels. |
| `active_window.full_update_separation_s` | Classic Hydra's minimum interval between full reconstruction updates. Increase it to reduce frontend load at the cost of update latency. |
| `active_window.min_output_separation` | Khronos minimum interval between active-window outputs. Increase it to reduce downstream load at the cost of graph update rate. |
| Nested projective-integrator `num_threads` | Raises integration parallelism until CPU contention or memory bandwidth becomes limiting. |

`SingleLabelIntegrator` stores a single semantic decision per voxel. Changing
integrator type changes semantic fusion behavior rather than only a threshold,
so treat it as a pipeline-design choice.

## Classic Hydra object extraction and association

The `classic.yaml` and `uhumans2.yaml` profiles Euclidean-cluster mesh vertices
of each semantic class. During active mapping, a cluster updates an existing
same-class object only if its centroid lies inside that object's bounding box.
The backend similarly merges candidates only if either bounding box contains the
other object's centroid.

| Parameter | Effect and tuning direction |
| --- | --- |
| `frontend.objects.cluster_tolerance` | Maximum Euclidean gap within a cluster. Increase it when one object is fragmented. Decrease it when nearby same-class objects are fused. This is normally the first object parameter to tune. |
| `frontend.objects.min_cluster_size` | Minimum mesh vertices per cluster and minimum retained active-object size. Raise it to reject small fragments. Lower it when genuine small or partially observed objects disappear and reappear. |
| `frontend.objects.max_cluster_size` | Rejects clusters larger than the limit. Change it only when legitimate very large objects are discarded. |
| `frontend.objects.bounding_box_type` | Controls geometry and the centroid-in-box association gate. `RAABB` is yaw-adjusted, `AABB` is often more permissive for rotated objects, and `OBB` is tighter. More permissive boxes also increase false merges. |
| `backend.enable_node_merging` | Must be `true` for backend merge proposals to be applied. |
| `backend.update_functors.objects.allow_connection_merging` | Allows accepted object merges to combine their mesh connections. Its default is `true`. |
| `backend.update_functors.objects.merge_proposer.strategy.num_merges_to_consider` | Number of nearest same-class archived candidates checked per object. The default is `1`. A small increase can help when the correct object is not nearest, but it does not relax the bounding-box test. |

An explicit multi-candidate configuration is:

```yaml
backend:
  update_functors:
    objects:
      type: UpdateObjectsFunctor
      merge_proposer:
        strategy:
          type: SemanticNearestNode
          num_merges_to_consider: 3
```

If duplicate copies are spatially displaced by more than the object's extent,
fix trajectory, TF, timestamps, and calibration before loosening association.
If the copies have different semantic labels, fix semantic inference or label
remapping first.

## Khronos detection, tracking, and object reconstruction

These paths apply to `adt4.yaml`. There are three separate association stages:
frame-to-frame tracking in the active window, frontend graph updates, and
backend graph merging. Tune them in that order.

### Detection and frame-to-frame tracking

| Parameter | Effect and tuning direction |
| --- | --- |
| `active_window.object_detector.min_cluster_size` | Minimum detection size. Raise it to reject small noisy detections. Lower it for small or distant objects. |
| `active_window.object_detector.min_range` / `max_range` | Range gate applied to object detections. Keep it within the sensor's valid depth range. |
| `active_window.tracker.track_by` | IoU representation: `pixels`, `voxels`, or `bounding_box`. Pixels depend on image overlap. Voxels depend on reliable 3D pose and `voxel_size`. Bounding boxes are coarser. |
| `active_window.tracker.min_semantic_iou` | Minimum overlap for same-semantic detection/track association. Lower it when viewpoint changes fragment tracks. Raise it when neighboring objects exchange identities. |
| `active_window.tracker.min_cross_iou` | Minimum overlap between semantic and dynamic detections. It is not the primary static-object association threshold. |
| `active_window.tracker.min_cosine_sim` | Optional semantic-feature similarity gate. Increase it to require closer feature agreement. Use only when meaningful features are supplied. |
| `active_window.tracker.max_dynamic_distance` | Maximum inter-frame displacement for dynamic-object association. Increase it for fast objects or low frame rates, with greater false-association risk. |
| `active_window.tracker.min_num_observations` | Controls how quickly track confidence grows. Lower values admit short tracks sooner and increase false positives. Higher values require persistence. |
| `active_window.tracker.voxel_size` | Resolution for `track_by: voxels`. Smaller values are more precise but more sensitive to pose/depth noise and more expensive. |

### Object acceptance and reconstruction

All paths in this table are below `active_window.object_extractor`.

| Parameter | Effect and tuning direction |
| --- | --- |
| `min_object_allocation_confidence` | Minimum track confidence for extraction. Lower it to retain shorter tracks. Raise it to reject unstable tracks. |
| `min_object_volume` / `max_object_volume` | Accepted 3D volume range. Set these from expected physical object sizes. |
| `only_extract_reconstructed_objects` | When `true`, drops objects whose reconstructed mesh is empty. This improves graph cleanliness but can remove weakly observed objects. |
| `min_object_reconstruction_confidence` | Removes object-reconstruction voxels below this confidence. Lower it for completeness. Raise it for cleaner meshes. |
| `min_object_reconstruction_observations` | Minimum observations contributing to reconstructed object voxels. Lower it for short tracks. Raise it to suppress transient geometry. |
| `object_reconstruction_resolution` | Positive values are voxel size in metres. Negative values are a fraction of object extent. Zero disables static reconstruction. Smaller magnitudes give finer meshes at higher cost. |
| `min_reconstruction_resolution` | Lower bound on voxel size when `object_reconstruction_resolution` is negative. It prevents small objects from producing excessively fine grids. |
| `min_dynamic_displacement` | Minimum trajectory length for accepting a dynamic object. Lower it for slow motion. Raise it to reject static/noisy tracks classified as dynamic. |
| `visualize_classification` | Debugging-only reconstruction coloring. It changes pruning for visualization and should normally remain `false`. |

### Frontend and backend graph association

| Parameter | Effect and tuning direction |
| --- | --- |
| `frontend.graph_updater.layer_updates.OBJECTS.matcher.min_same_iou` | Minimum 3D bounding-box IoU for adding a same-class observation to an active frontend object. Lower it cautiously when good tracks still create frontend duplicates. |
| `frontend.graph_updater.layer_updates.OBJECTS.matcher.min_cross_iou` | IoU threshold for objects with different labels. Lowering it permits more cross-label merges and is risky. |
| `backend.update_functors.objects.node_matcher.min_same_iou` | Minimum IoU for backend same-class merges. Lower it only after tracker and frontend association work correctly. |
| `backend.update_functors.objects.node_matcher.min_cross_iou` | Backend cross-label merge threshold. Keep it stricter than the same-label threshold unless label flicker is understood. |
| `backend.update_functors.objects.merge_proposer.strategy.type` | `Pairwise` checks all eligible pairs. This is exhaustive but can be expensive for large object layers. |

## Places, connectivity, and rooms

### Surface places (`MESH_PLACES`)

| Parameter | Effect and tuning direction |
| --- | --- |
| `frontend.surface_places.cluster_tolerance` | Spatial tolerance for clustering same-label surface vertices. Larger values connect gaps but may fuse surfaces. |
| `min_cluster_size` / `max_cluster_size` under `surface_places` | Accepted initial surface-cluster size in mesh vertices. |
| `pure_final_place_size` | Target size used while recursively decomposing a surface region. Smaller values produce more, smaller places. |
| `min_final_place_points` | Rejects final places with too few supporting points. Raise it to suppress small regions. |
| `place_overlap_threshold` | Required planar overlap for connecting neighboring surface places. Raising it makes connectivity stricter. |
| `place_max_neighbor_z_diff` | Maximum vertical difference for a surface-place edge. Lower it to prevent connections across levels. Raise it for ramps or uneven surfaces. |

There is no relative-height filter in the locked `place_2d` extractor.

### Freespace places (`PLACES`)

| Parameter | Effect and tuning direction |
| --- | --- |
| `frontend.freespace_places.gvd.min_distance_m` | Minimum obstacle clearance represented by the GVD. Raise it to suppress narrow free-space structure. |
| `frontend.freespace_places.gvd.max_distance_m` | Caps represented obstacle distance. Larger values preserve wider-space distance information at additional cost. |
| `frontend.freespace_places.gvd.min_diff_m` | GVD basis-point distance-difference threshold. Increase it to make skeleton extraction more selective. |
| `frontend.freespace_places.graph.min_node_distance_m` | Minimum spacing between extracted place nodes. Increase it for a sparser graph. |
| `compression_distance_m` | Distance scale for graph compression. Increase it to compress more aggressively. |
| `merge_nearby_nodes` / `node_merge_distance_m` | Enables and sets distance-based merging. Larger distances reduce graph size but can collapse narrow topology. |
| `tsdf_interpolator.ratio` | Downsampling ratio used while reading the TSDF. Larger ratios reduce cost and detail. |

### Traversability places (`MESH_PLACES` in ADT4)

| Parameter | Effect and tuning direction |
| --- | --- |
| `estimator.height_below` / `height_above` | Vertical band evaluated by the height estimator. Match it to robot clearance and obstacle height. |
| `estimator.min_confidence` | Required evidence before a region is traversable. Raise it for conservative maps. |
| `estimator.min_traversability` | Minimum traversability score. Raise it to reject marginal terrain. |
| `estimator.pessimistic` | Treats insufficient or unknown evidence conservatively when enabled. |
| `clustering.max_radius` | Maximum spatial extent considered during region growth. Larger values form larger places and cost more. |
| `clustering.num_orientation_bins` | Surface-orientation discretization. More bins distinguish slopes more finely but fragment regions more easily. |

### Rooms

All paths in this table are below
`backend.update_functors.rooms.room_finder`.

| Parameter | Effect and tuning direction |
| --- | --- |
| `min_dilation_m` / `max_dilation_m` | Search range for room separation by freespace-graph dilation. Set it relative to doorway and corridor widths. |
| `min_component_size` | Rejects small candidate room components. Raise it to suppress tiny rooms. |
| `min_room_size` | Minimum accepted room size in graph nodes. Raise it when closets or noise become rooms. |
| `plateau_ratio` | Sensitivity of plateau-based dilation selection. Treat it as an advanced dataset-specific threshold. |
| `min_lifetime_length_m` | Minimum persistence across the dilation filtration. Raise it to require more stable room candidates. |

## Deformation, optimization, and loop closures

| Parameter | Effect and tuning direction |
| --- | --- |
| `frontend.pgmo.time_horizon` | Time horizon retained for frontend deformation-graph construction. A longer horizon supplies more context at higher cost. |
| `frontend.pgmo.d_graph_resolution` | Deformation-graph sampling resolution. Smaller values create denser deformation graphs and increase optimization cost. |
| `frontend.pgmo.mesh_resolution` | Mesh sampling resolution used by PGMO. Smaller values retain more mesh constraints and cost more. |
| `backend.optimize_on_lc` | Runs optimization when a loop closure is received. It does not detect loop closures. |
| `backend.pgmo.embed_trajectory_delta_t` | Temporal spacing of embedded trajectory states. Smaller spacing adds more states and cost. |
| `backend.pgmo.num_interp_pts` / `interp_horizon` | Controls deformation interpolation support. More support produces smoother, more global deformation at higher cost. |
| `backend.pgmo.covariance.*` | Relative uncertainty of odometry, loop-closure, mesh, place, and merge factors. Lower covariance gives that factor more influence. Change these only with measured residuals and a sensor-noise model. |
| `backend.pgmo.optimizer.gnc.*` | Robust optimization settings. They affect rejection of inconsistent constraints, not initial data association. |

The repository's mapper profiles do not set `enable_lcd`. Hydra's locked default
is `false`. Consequently, `optimize_on_lc: true` alone does not provide internal
loop-closure detection. Enabling Hydra LCD also requires composing its detector,
descriptor, registration, and model configuration. Those parameters are outside
the current profiles.

`backend.pgmo.covariance.object_merge` is an optimization weight after an object
merge has been accepted. It is not an object-matching distance or IoU threshold.

## Publication and serialization

These affect bandwidth, latency, or output size rather than reconstruction or
association quality:

| Parameter | Effect |
| --- | --- |
| `frontend.serialize_dsg_mesh` / `backend.serialize_dsg_mesh` | Includes mesh data in streamed DSG messages. |
| `backend.publish_mesh` | Enables separate mesh publication. |
| `backend.min_dsg_separation_s` | Minimum interval between published DSG messages. |
| `backend.min_mesh_separation_s` | Minimum interval between published mesh messages. |
| `backend.publish_backend_tf` | Publishes the optimized map-to-odometry transform. |
| `config_verbosity` and nested `verbosity` | Logging detail. High values can add runtime overhead but do not change algorithm thresholds. |

## Symptom-first tuning order

| Symptom | Check or tune first | Then consider |
| --- | --- | --- |
| Duplicate object is displaced in 3D | TF, timestamps, depth registration, odometry | Loop closure and trajectory optimization |
| Classic Hydra splits one object into nearby fragments | `frontend.objects.cluster_tolerance` | `min_cluster_size`, bounding-box type, merge candidates |
| Classic Hydra fuses adjacent same-class objects | Lower `cluster_tolerance` | Tighter bounding boxes, finer `voxel_size` |
| Khronos creates a new track each frame | `tracker.min_semantic_iou`, `track_by` | Tracker voxel size and pose quality |
| Khronos tracks correctly but graph has duplicates | Frontend `min_same_iou` | Backend `min_same_iou` |
| Small objects are absent | Sensor range, map `voxel_size`, minimum cluster size | Allocation confidence, volume and observation thresholds |
| Mesh is noisy or doubled | Calibration, synchronization, odometry | Truncation distance and voxel size |
| Place graph is too dense | Place node spacing and compression | TSDF downsampling ratio |
| Rooms are fragmented | Place connectivity first | Room dilation range and component thresholds |

Change one parameter group at a time and compare the generated Spark-DSG JSON,
object counts, object bounding boxes, mesh statistics, and runtime. Thresholds
cannot compensate reliably for invalid geometry or inconsistent semantic IDs.

## Locked upstream source anchors

- [Hydra surface-place schema](https://github.com/MIT-SPARK/Hydra/blob/1e89319efd59d73bd189664bf8fa6f9c7e56c5ca/hydra/src/frontend/surface_place_extractor.cpp)
- [Hydra mesh-object clustering and active association](https://github.com/MIT-SPARK/Hydra/blob/1e89319efd59d73bd189664bf8fa6f9c7e56c5ca/hydra/src/frontend/mesh_segmenter.cpp)
- [Hydra backend object merging](https://github.com/MIT-SPARK/Hydra/blob/1e89319efd59d73bd189664bf8fa6f9c7e56c5ca/hydra/src/backend/updates/update_objects_functor.cpp)
- [Khronos IoU tracker schema](https://github.com/MIT-SPARK/Khronos/blob/a50f3e21967c32d6bc160dafbe5c26c6188c6386/khronos/src/active_window/tracking/max_iou_tracker.cpp)
- [Khronos object-extractor schema](https://github.com/MIT-SPARK/Khronos/blob/a50f3e21967c32d6bc160dafbe5c26c6188c6386/khronos/src/active_window/object_extraction/mesh_object_extractor.cpp)
