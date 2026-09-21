# Architecture

The integration composes bag acquisition with a mapping recipe before ROS
starts:

```text
dataset adapter                 mapping recipe
  +-- topics                      +-- scene_structure
  +-- frames                      +-- semantics.source/resources
  +-- depth/playback              +-- Hydra + visualization profiles
```

Thus Spot and uHumans2 do not imply a semantic source or scene structure.
Invalid composed configurations fail in `scripts/dataset_config.py`.
Visualization is selected from explicit mapping metadata, never from a dataset
name or Hydra YAML filename.

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

The repository builds two independent final images:

```text
osrf/ros:jazzy-desktop-full              nvidia/cuda:12.8.1-devel-ubuntu24.04
             |                                      | build
     core (CPU + RViz + tests)               installed ROS workspace + venv
                                                    |
                                  nvidia/cuda:12.8.1-runtime-ubuntu24.04
                                                    |
                                      gpu (ROS + TensorRT + PyTorch)
```

The core image remains a complete development environment. The independently
buildable GPU image uses a builder stage for the CUDA compiler, TensorRT headers,
exact-SHA upstream source, and colcon build tree. Its final stage retains only a
non-symlinked ROS install tree, the semantic-inference virtual environment,
TensorRT shared runtime libraries, and declared ROS execution dependencies. It
does not inherit from `spark-3dsg-core:local` or require another locally tagged
image.

The official PyTorch 2.7/CUDA 12.8 images use Ubuntu 22.04 and Conda, which are
not compatible base assumptions for ROS 2 Jazzy's Ubuntu 24.04 binary packages.
The GPU builder therefore starts from NVIDIA's Ubuntu 24.04 CUDA development
image and the final stage starts from its matching runtime image. The official
PyTorch `cu128` wheels are installed in one virtual environment. CUDA, TensorRT,
PyTorch, torchvision, and cuDNN form the qualified set documented in
[`dependencies/GPU_BASELINE.md`](../dependencies/GPU_BASELINE.md).

Every service runs as the host-matched, non-root `spark` user. Core mapping,
RViz, tests, maintenance, and the development shell reuse the same core image.
The core integration package is symlink-installed. The GPU stage uses a
self-contained install tree, but its resource files point at the bind-mounted
integration source, so launch/configuration/RViz edits remain visible without
rebuilding either image.

## Reproducibility

`dependencies/locks/v1.lock.repos` is the machine-consumed exact-SHA snapshot.
`dependencies/upstream-public.repos` is the updateable maintainer manifest.
The GPU build additionally consumes `dependencies/locks/gpu.lock.repos` for
source-only perception dependencies that are not part of the mapping snapshot.
The name `v1` has no topology or validation meaning.
