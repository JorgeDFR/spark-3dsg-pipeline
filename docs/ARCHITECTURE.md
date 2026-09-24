# Architecture

This repository connects public MIT-SPARK packages through Docker images,
configuration files, and ROS launch files. Reconstruction, tracking, and graph
algorithms remain in the upstream projects.

## Processing flow

| Stage | Input | Output | Responsibility |
| --- | --- | --- | --- |
| Preprocessing (optional) | Raw recording and source/pose profiles | Normalized ROS 2 bag and dataset adapter | Register depth and provide the required pose/TF streams |
| Input validation | ROS 2 bag, dataset adapter, and mapping recipe | Contract check | Check topics, calibration, depth, and transforms |
| Mapping | Validated bag and selected recipe | Spark-DSG graph and mesh | Run Hydra or Khronos with the selected semantics |
| Inspection and visualization | Saved graph or live mapping output | Content checks or RViz display | Inspect results without requiring another mapping run |

Preprocessing is a separate materialization step. Mapping consumes the saved bag
and does not run camera SDKs or odometry estimators. See the
[custom dataset workflow](CUSTOM_DATASET.md) and
[preprocessing guide](PREPROCESSING.md).

## Configuration

Dataset adapters describe acquisition. Mapping recipes select processing.
This lets Spot and uHumans2 use either online semantic pipeline.

| Configuration | Controls | Example |
| --- | --- | --- |
| Dataset adapter | Topics, frames, depth units, playback | `spot`, `uhumans2`, `custom_rgbd` |
| Mapping recipe | Scene structure, semantic resources, Hydra config, visualizer | `recorded`, `closed_set`, `open_set` |
| Open-set labels | YOLOE text vocabulary | Custom `LABELS_CONFIG` YAML |
| Preprocessing profiles | Recorded sensor interface and pose provider | `generic_rgbd` with `rtabmap_rgbd` |

`scripts/python/dataset_config.py` checks the composed dataset and mapping
configuration before launch. Visualization follows the recipe's explicit
metadata. See [datasets and mappings](DATASETS.md) for supported combinations.

## Semantic processing

| Recipe | Semantic input | Processing | Mapper input |
| --- | --- | --- | --- |
| `recorded` | Class-ID images in the bag | Topic normalization, no perception node | Class-ID image |
| `closed_set` | RGB images | Upstream C++ ADE20K inference | Class-ID image |
| `open_set` | RGB images | Upstream Python YOLOE inference | Packed instance IDs and latched labelspace |

Closed-set inference uses separate model, preprocessing, grouping, and Hydra
label-space resources. Open-set inference combines model/worker settings with
a labels overlay. Model setup is documented in [models](../models/README.md).

## Scene graphs

| Recipe | Reconstruction | Graph structure |
| --- | --- | --- |
| `recorded`, `closed_set` | Hydra semantic TSDF and mesh-object extraction | Objects → places → rooms → buildings, with separate mesh places |
| `open_set` | Khronos active window and instance tracking | Objects associated with mesh places |

The [graph reference](GRAPH_SCHEMA.md) describes layers, profile configuration,
and exported files.

## Docker images

### Image roles

| Image | Base | Used for |
| --- | --- | --- |
| `spark-3dsg-core:local` | `osrf/ros:jazzy-desktop-full` | CPU recorded mapping, RViz, repository tests, development |
| `spark-3dsg-gpu:local` | NVIDIA CUDA 12.8.1 on Ubuntu 24.04 | TensorRT and PyTorch semantic inference with mapping |
| `spark-3dsg-preprocess:local` | `stereolabs/zed:5.4.1-devel-cuda12.8-ubuntu24.04` | Passthrough, recorded odometry, RTAB-Map, OpenVINS, ZED tracking |

All three images build independently. The preprocessing image is optional and
selects one pose provider at runtime. Its output follows the same mapping input
contract for every source.

### GPU build and runtime

The GPU image uses two stages and does not inherit from the local core image.

| Stage | Contents |
| --- | --- |
| Builder | CUDA compiler, TensorRT headers, exact-SHA upstream source, colcon build tree |
| Runtime | Installed ROS workspace, semantic-inference virtual environment, TensorRT libraries, ROS execution dependencies |

Both stages use Ubuntu 24.04 for ROS 2 Jazzy compatibility. Official PyTorch
`cu128` wheels are installed in one virtual environment. The qualified versions
are recorded in [the GPU baseline](../dependencies/GPU_BASELINE.md).

### Runtime files and identity

Every service runs as the non-root `spark` user matched to `HOST_UID` and
`HOST_GID`. Core mapping, RViz, tests, maintenance, and development reuse the
core image.

| Files | Delivery | How to update |
| --- | --- | --- |
| Packages, scripts, bundled examples | Baked into the image | Rebuild the affected image |
| Custom YAML configs | `data/custom-configs` mount | Edit the file and pass its container path |
| Bags, models, outputs | Data, model, and output mounts | Manage independently of image builds |

The core workspace uses symlink installation within the image. The GPU
workspace uses a self-contained install tree.

## Dependency locks

| File | Purpose |
| --- | --- |
| `dependencies/locks/v1.lock.repos` | Exact-SHA mapping dependency snapshot |
| `dependencies/locks/gpu.lock.repos` | Additional source dependencies for GPU perception |
| `dependencies/locks/preprocess.lock.repos` | Exact-SHA preprocessing toolbox snapshot |
| `dependencies/upstream-public.repos` | Updateable manifest for maintainers |

`v1` identifies the immutable dependency snapshot. It does not select a graph
structure or validation mode. Builds use the exact-SHA locks, and mapping
outputs record the lock hash for reproducibility.
