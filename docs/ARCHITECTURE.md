# Architecture

This repository is an integration layer, not a mapper fork.

```text
bag/dataset adapter
  -> /input/color/image_raw
  -> /input/depth/image_rect
  -> /input/color/camera_info
  -> /tf + /tf_static
            |
            +-> online YOLOE instances
            |       -> Khronos ActiveWindow
            |       -> OBJECTS + MESH_PLACES
            |
            +-> recorded ground-truth semantics
                    -> Hydra ReconstructionModule
                    -> OBJECTS + MESH_PLACES
                    -> PLACES + ROOMS + BUILDINGS
                                      |
                                      v
                              Hydra backend + Spark-DSG
                                      |
                           dsg.json + mesh + metadata
```

Owned here: Docker, exact locks, launch composition, complete mapper profiles,
dataset topic/frame adapters, preflight checks, deterministic output,
inspection, tests, and documentation.

Owned upstream: SLAM/TSDF, object detection/tracking algorithms, graph construction, optimization, the DSG data structure, YOLOE implementation, and DAAAM.

The integration package is the canonical ROS execution layer. The runtime
wrappers resolve dataset YAML and manage readiness, logs, shutdown, and output;
they delegate ROS processes to these launch files:

- `pipeline.launch.yaml`: selected Hydra profile and optional perception composition.
- `perception.launch.yaml`: semantic-inference/YOLOE composition.
- `bag.launch.yaml`: rosbag2 playback, QoS, and normalized topic remapping.
- `visualization.launch.yaml`: upstream Hydra streaming visualizer and RViz.

This separation keeps dataset policy in the repository wrappers without
duplicating ROS node definitions outside the package.

The repository-owned ROS package lives directly under `src/spark_3dsg_pipeline`. Docker retains an internal `/home/spark/ros_ws` only because the pinned upstream ROS packages must be imported and built somewhere. Compose mounts the local integration package into that internal workspace, whose symlink install keeps launch and configuration edits live without rebuilding the image.

The runnable v1 default follows the public ADT4 mapping snapshot through
`config/hydra/adt4.yaml`. `classic.yaml` starts from ADT4's classic mapping
profile and adds the core Hydra GVD place and room hierarchy. The independent
`uhumans2.yaml` office demo uses core Hydra reconstruction and ground-truth
semantics instead of Khronos. Dataset adapters select one complete profile;
profiles are not merged across active-window implementations. The
locked Hydra revision is a public monorepo containing Hydra-ROS, so importing the
separate post-split repository would duplicate ROS packages. No source patch is
applied.

DAAAM is isolated by a separate manifest/lock because it requires project-specific Hydra and Spark-DSG branches. It must never be merged into the standard source workspace.
