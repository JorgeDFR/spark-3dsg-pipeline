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

The runnable v1 default follows the exact public ADT4 mapping snapshot. That Hydra revision is a public monorepo containing Hydra-ROS; importing the separate post-split repository would duplicate ROS packages. `config/hydra/adt4.yaml` is a compact provenance view and `default.yaml` is the runnable configuration. No source patch is applied.

DAAAM is isolated by a separate manifest/lock because it requires project-specific Hydra and Spark-DSG branches. It must never be merged into the standard source workspace.
