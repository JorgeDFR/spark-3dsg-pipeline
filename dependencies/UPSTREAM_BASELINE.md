# Upstream baseline

Captured: 2026-08-27 UTC

Reference project: [MIT-SPARK/Awesome-DCIST-T4](https://github.com/MIT-SPARK/Awesome-DCIST-T4)

Reference commit: `10263e7b9cce9ae215d69264fcd224dabfb51406`

Mapping submodules at that reference:

- Hydra: `1e89319efd59d73bd189664bf8fa6f9c7e56c5ca`
- Khronos: `a50f3e21967c32d6bc160dafbe5c26c6188c6386`
- Spark-DSG: `6d678d5ab72dd5a19a03b16cbf1107d100fbb01b`
- semantic_inference: `00b05c1f4867ab0466e78154a781d1114e488a2b`

The v1 executable lock uses these ADT4 mapping submodule revisions plus exact public auxiliary dependencies captured on the same date. At this snapshot, `MIT-SPARK/Hydra` is a monorepo containing the `hydra`, `hydra_ros`, `hydra_msgs`, and `hydra_visualizer` packages. The separately split Hydra-ROS repository is therefore not imported into the standard workspace, which would create duplicate ROS packages.

Mapping architecture copied conceptually (not as a runtime dependency):

```text
semantic_inference YOLOE
  -> InstanceImageReceiver
  -> Khronos ActiveWindow + MaxIouTracker + MeshObjectExtractor
  -> Hydra GraphBuilder
  -> OBJECTS + MESH_PLACES/traversability
  -> Spark-DSG
```

Intentionally excluded: Hydra-Multi, ROMAN, Spot hardware/SDK, Phoenix, planners, Heracles, speech/NLU, networking/base-station infrastructure, robot executors, and private deploy keys.
