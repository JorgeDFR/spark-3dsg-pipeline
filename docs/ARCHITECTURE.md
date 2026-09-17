# Architecture

The integration resolves three orthogonal choices before ROS starts:

```text
dataset adapter
  +-- scene_structure: hierarchical | khronos
  +-- semantics.source: recorded | closed_set | open_set
  +-- visualization.profile: hierarchical | khronos
```

Invalid combinations fail in `scripts/dataset_config.py`. Visualization is
selected from explicit adapter metadata, never from a Hydra YAML filename.

## Scene structures

The `classic` and uHumans2 pipelines use core Hydra reconstruction:

```text
BUILDINGS
   |
 ROOMS        MESH_PLACES (decoupled surface places)
   |
 PLACES
   |
OBJECTS
```

They use semantic TSDF reconstruction, mesh object extraction, GVD places,
room/building functors, and a separate 2D surface-place updater.

The ADT4 example uses the pinned Khronos active window and contains `OBJECTS`
plus `MESH_PLACES`. Its connector makes mesh places parents of objects.

## Semantic paths

- `recorded`: the bag class-ID image is normalized to
  `/input/semantic/image_raw`; no perception node runs.
- `closed_set`: the upstream C++ closed-set node consumes RGB and publishes a
  class-ID image. Model config, ONNX model, semantic grouping, and matching
  Hydra label space are separate resources.
- `open_set`: the upstream Python YOLOE instance node publishes packed instance
  IDs and a latched labelspace. Model/worker settings and prompt labels are
  composed from separate YAML files.

The repository does not implement reconstruction, tracking, or DSG algorithms.
It does not modify upstream source.

## Container architecture

Release builds use independent builder and runtime stages:

```text
core-builder (desktop + toolchain + exact-SHA source)
  |-- core-development (tests and maintenance only)
  `-- self-contained ROS install --> core-runtime (ROS Base)
                                      |-- gpu-runtime
                                      `-- rviz-runtime
```

The release ROS workspace is built without `--symlink-install`, allowing only
its install space to be copied into runtime images. Runtime apt dependencies are
resolved from the builder source through a temporary BuildKit mount. The GPU
builder adds NVCC and TensorRT headers, but the final image receives only the
TensorRT runtime packages, rebuilt ROS install, and semantic-inference virtual
environment. CUDA, TensorRT, PyTorch, torchvision, and cuDNN form the qualified
set documented in [`dependencies/GPU_BASELINE.md`](../dependencies/GPU_BASELINE.md).
RViz is kept separate from GPU inference.

`core-runtime`, `gpu-runtime`, and `rviz-runtime` run as the non-root `spark`
user. `core-development` retains the complete upstream source and workspace
build trees and is used by `make test`, `make lint`, `make lock-dependencies`,
and `make dev-shell`.

## Reproducibility

`dependencies/locks/v1.lock.repos` is the machine-consumed exact-SHA snapshot.
`dependencies/upstream-public.repos` is the updateable maintainer manifest.
The name `v1` has no topology or validation meaning.
