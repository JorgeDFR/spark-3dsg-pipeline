# Debugging and runtime validation

Start with `make validate-bag` and pass the same `DATASET` and `MAPPING` planned
for the run. Pipeline startup then checks the selected Hydra config,
labelspace/grouping, model config, weights, visualization config, and open-set
labels before launching ROS. Missing components are reported together by the
Python resolver and individually by the runtime wrapper.

Use:

```bash
make inspect DSG=/home/spark/output/run/dsg.json \
  INSPECT_ARGS=--require-pipeline-output
```

Use `make dev-shell` for the complete compiler environment, pytest, or upstream
source access. The core image retains its source and build tree. The GPU runtime
image deliberately omits compilers, upstream source, and build objects; use the
Docker builder-stage output or rebuild with progress enabled when diagnosing a
GPU compilation failure. Use `docker image ls` and `docker image history` to
confirm the runtime image contains only the expected final-stage layers.

For file visualization, a missing path fails before launch and malformed JSON
returns nonzero with a parse explanation. When given `dsg.json`, the wrapper
prefers a sibling `dsg_with_mesh.json`. It warns before launch if the selected
file has no non-empty embedded mesh. A valid file uses the same renderer as live
streaming and does not require a mapper process.

GPU smoke tests must run in Docker:

1. uHumans2 recorded semantics.
2. classic closed-set semantics with both Spot and uHumans2 input.
3. ADT4 open-set semantics with both Spot and uHumans2 input.
4. ADT4 with a small alternate labels overlay.
5. live RViz for both scene structures.
6. stop each mapper and load both saved JSON files.

Inspect actual layer sets and hierarchy edges in every output. This repository's
host environment is suitable only for static/CPU tests.
