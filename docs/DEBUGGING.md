# Debugging and runtime validation

Start with `make validate-bag`. Pipeline startup then checks the selected Hydra
config, labelspace/grouping, model config, weights, visualization config, and
open-set labels before launching ROS. Missing components are reported together
by the Python resolver and individually by the runtime wrapper.

Use:

```bash
make inspect DSG=/home/spark/output/run/dsg.json \
  INSPECT_ARGS=--require-pipeline-output
```

For file visualization, a missing path fails before launch and malformed JSON
returns nonzero with a parse explanation. A valid file uses the same renderer as
live streaming and does not require a mapper process.

GPU smoke tests must run in Docker:

1. uHumans2 recorded semantics.
2. generic classic closed-set semantics.
3. ADT4 with default labels.
4. ADT4 with a small alternate labels overlay.
5. live RViz for both scene structures.
6. stop each mapper and load both saved JSON files.

Inspect actual layer sets and hierarchy edges in every output. This repository's
host environment is suitable only for static/CPU tests.
