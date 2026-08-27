# DAAAM profile (post-v1)

DAAAM is deliberately not buildable through the v1 Makefile. Its public installation expects Ubuntu 24.04, ROS 2 Jazzy, CUDA 12.x, and approximately 24 GB or more GPU memory, plus a substantially larger Python/model dependency surface.

The independent `daaam.repos` and reference `daaam.lock.repos` document the branch boundary. They include DAAAM-specific Hydra/Hydra-ROS/Spark-DSG branches and must not affect the working standard profile.

The implementation milestone is:

```text
CODa bag -> DAAAM-ROS segmentation/tracking/grounding -> Hydra/Khronos -> dsg.json
```

Before enabling `make build PROFILE=daaam`, add:

- a complete image built only from `daaam.lock.repos`;
- external FastSAM/ReID/VLM model management and license/checksum records;
- the documented CODa bag/QoS workflow;
- an automatic headless shutdown/output normalizer;
- CODa acceptance checks equivalent to `inspect_dsg.py --require-v1`;
- a manual GPU acceptance test.

The current failing `Dockerfile.daaam` is an intentional guardrail against silently combining incompatible standard and DAAAM workspaces.
