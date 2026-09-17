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

The repository builds two independent images:

```text
osrf/ros:jazzy-desktop-full                 nvidia/cuda:12.8.1-devel-ubuntu24.04
             |                                              |
     core (CPU + RViz + tests)                  gpu (ROS + TensorRT + PyTorch)
```

Both are single-stage, complete environments. They retain the compiler,
exact-SHA upstream source, build tree, and merged/symlinked install space. This
uses more disk than a minimal deployment image, but removes cross-stage artifact
copying, runtime dependency reconstruction, and the requirement to prebuild
locally tagged parent images. The GPU image is independently buildable and does
not inherit from `spark-3dsg-core:local`.

The official PyTorch 2.7/CUDA 12.8 images use Ubuntu 22.04 and Conda, which are
not compatible base assumptions for ROS 2 Jazzy's Ubuntu 24.04 binary packages.
The GPU image therefore starts from NVIDIA's Ubuntu 24.04 CUDA development image
and installs the official PyTorch `cu128` wheels in one virtual environment.
CUDA, TensorRT, PyTorch, torchvision, and cuDNN form the qualified set documented
in [`dependencies/GPU_BASELINE.md`](../dependencies/GPU_BASELINE.md).

Every service runs as the host-matched, non-root `spark` user. Core mapping,
RViz, tests, maintenance, and the development shell reuse the same core image.
The integration package is symlink-installed and bind-mounted so resource and
Python edits are visible without an image rebuild.

## Reproducibility

`dependencies/locks/v1.lock.repos` is the machine-consumed exact-SHA snapshot.
`dependencies/upstream-public.repos` is the updateable maintainer manifest.
The name `v1` has no topology or validation meaning.
