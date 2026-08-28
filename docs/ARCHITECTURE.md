# Architecture

This repository is an integration layer, not a mapper fork.

```text
bag/dataset adapter
  -> /input/color/image_raw
  -> /input/depth/image_rect
  -> /input/color/camera_info
  -> /tf + /tf_static
            |
            +-> online YOLOE --------+
            +-> recorded instances --+-> /input/semantic/*
                                      |
                              Khronos ActiveWindow
                         InstanceForwarding + MaxIoU
                              MeshObjectExtractor
                                      |
                              Hydra GraphBuilder
                         OBJECTS + traversability places
                                      |
                                  Spark-DSG
                                      |
                           dsg.json + mesh + metadata
```

Owned here: Docker, exact locks, launch composition, mapper parameter overlays, dataset topic/frame adapters, preflight checks, deterministic output, inspection, tests, and documentation.

Owned upstream: SLAM/TSDF, object detection/tracking algorithms, graph construction, optimization, the DSG data structure, YOLOE implementation, and DAAAM.

The integration package is the canonical ROS execution layer. The runtime
wrappers resolve dataset YAML and manage readiness, logs, shutdown, and output;
they delegate ROS processes to these launch files:

- `pipeline.launch.yaml`: Hydra/Khronos and optional perception composition.
- `perception.launch.yaml`: semantic-inference/YOLOE composition.
- `bag.launch.yaml`: rosbag2 playback, QoS, and normalized topic remapping.
- `visualization.launch.yaml`: upstream Hydra streaming visualizer and RViz.

This separation keeps dataset policy in the repository wrappers without
duplicating ROS node definitions outside the package.

The repository-owned ROS package lives directly under `src/spark_3dsg_pipeline`. Docker retains an internal `/home/spark/ros_ws` only because the pinned upstream ROS packages must be imported and built somewhere. Compose mounts the local integration package into that internal workspace, whose symlink install keeps launch and configuration edits live without rebuilding the image.

The runnable v1 default follows the exact public ADT4 mapping snapshot. That Hydra revision is a public monorepo containing Hydra-ROS; importing the separate post-split repository would duplicate ROS packages. `config/hydra/adt4.yaml` is a compact provenance view and `default.yaml` is the runnable configuration. No source patch is applied.

DAAAM is isolated by a separate manifest/lock because it requires project-specific Hydra and Spark-DSG branches. It must never be merged into the standard source workspace.
