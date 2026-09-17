# Upstream baseline

Captured: 2026-08-27 UTC

`v1` means only this immutable, mutually compatible set of upstream repository
commits. It does not identify a scene-graph structure, semantic mode, or output
acceptance contract. `locks/v1.lock.repos` is the machine-consumed source of
truth; this file records its provenance for reviewers.

Reference project: [MIT-SPARK/Awesome-DCIST-T4](https://github.com/MIT-SPARK/Awesome-DCIST-T4)

Reference commit: `10263e7b9cce9ae215d69264fcd224dabfb51406`

| Repository | Exact commit |
| --- | --- |
| Hydra (monorepo including Hydra-ROS) | `1e89319efd59d73bd189664bf8fa6f9c7e56c5ca` |
| Khronos | `a50f3e21967c32d6bc160dafbe5c26c6188c6386` |
| Spark-DSG | `6d678d5ab72dd5a19a03b16cbf1107d100fbb01b` |
| semantic_inference | `00b05c1f4867ab0466e78154a781d1114e488a2b` |
| Spark-Config | `81a97a1106ad3852e280ac9e200bc6c8f36e1357` |
| config_utilities | `291ab68087e00cbb7d9609f5e1caf8cf16436145` |
| Ianvs | `29cd77d9649c348dfaf40d5fffa9c7f8c9dfbbcf` |
| Kimera-PGMO | `fb45b27543813f314df513e7b8c90e28dce7de8b` |
| Kimera-RPGO | `f1fee0900ef6825bf76304685668235cf5dd008d` |
| pose_graph_tools | `965dfe864487be9040195c598fd89718563c348c` |
| Spatial-Hash | `8045892f34978d78870d806a50f8e5aefdbe52fc` |
| TEASER-plusplus | `52a9c52ee7d4c838c5e8a75458c33178be5bfb70` |

The four mapping commits come from the Awesome-DCIST-T4 reference above. Exact
public auxiliary commits were captured with that compatible set on the same
date. At this snapshot, `MIT-SPARK/Hydra` is a monorepo containing the `hydra`,
`hydra_ros`, `hydra_msgs`, and `hydra_visualizer` packages. The separately split
Hydra-ROS repository is therefore not imported, which would create duplicate ROS
packages.

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
