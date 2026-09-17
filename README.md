# spark-3dsg-pipeline

Docker/ROS integration for building Spark-DSG scene graphs with the public
MIT-SPARK stack. The repository owns launch, configuration, validation, and
reproducibility glue; Hydra, Khronos, Spark-DSG, and semantic inference remain
upstream components.

The pipeline has three independent dimensions: graph structure, semantic
source/taxonomy, and visualization profile. Dataset adapters select compatible
defaults without deriving one dimension from a Hydra filename.

| Example/config | Scene structure | Semantic source | Perception |
| --- | --- | --- | --- |
| `uhumans2.yaml` | hierarchical | recorded class IDs | none |
| `classic.yaml` | hierarchical | online closed-set | `semantic_inference` closed-set |
| `adt4.yaml` | Khronos | online open-set | YOLOE |

The hierarchical graph is `OBJECTS -> PLACES -> ROOMS -> BUILDINGS`.
`MESH_PLACES` is a decoupled 2D/surface representation. The Khronos graph has
`OBJECTS` and `MESH_PLACES`, with the ADT4 object-to-mesh-place connection.

## Setup

Host requirements are Docker and, for GPU execution, an NVIDIA driver plus
NVIDIA Container Toolkit. Do not install ROS, CUDA, or runtime Python packages
on the host.

```bash
cp .env.example .env
make build PROFILE=core
make build PROFILE=gpu
make models PROFILE=gpu
```

`make models` downloads and checksums both the closed-set ONNX model and YOLOE
weights into the mounted model directory. See [model setup](docs/MODELS.md).

## Mapping examples

```bash
# Recorded uHumans2 semantics; no inference node.
make run PROFILE=core DATASET=uhumans2 BAG=/home/spark/data/uhumans2

# Generic hierarchical mapping with ADE20K closed-set inference.
make run PROFILE=gpu DATASET=custom_rgbd BAG=/home/spark/data/my_rgbd

# ADT4/Spot Khronos example with the default open-set taxonomy.
make run PROFILE=gpu DATASET=spot BAG=/home/spark/data/spot

# Same mapper and model settings, different YOLOE taxonomy.
make run PROFILE=gpu DATASET=spot BAG=/home/spark/data/spot \
  LABELS_CONFIG=/home/spark/data/my_labels.yaml
```

An open-set labels file is a small overlay:

```yaml
model:
  instance_model:
    text_prompt: [ignore, chair, mug]
```

Outputs are written below `/home/spark/output`. Each run records
`pipeline_version: v1` and a `dependency_lock_hash`; here `v1` means only the
immutable upstream snapshot in `dependencies/locks/v1.lock.repos`.

## Visualization and inspection

```bash
# Live graph, profile selected by the dataset adapter.
make rviz DATASET=spot

# Saved graph, profile selected by the adapter.
make rviz DATASET=spot DSG=/home/spark/output/run/dsg.json

# Saved graph without a dataset adapter.
make rviz DSG=/home/spark/output/run/dsg.json \
  VISUALIZATION_PROFILE=hierarchical

make inspect DSG=/home/spark/output/run/dsg.json \
  INSPECT_ARGS=--require-pipeline-output
```

The pinned visualizer loads saved JSON directly through `GraphFromFile`; Hydra
or Khronos need not be running in file mode.

## Tests

```bash
make test PROFILE=core
make lint PROFILE=core
```

Repository-only tests may also run from the ignored `.venv`. GPU/runtime smoke
tests are described in [debugging](docs/DEBUGGING.md). Model, bag, mesh, and
output artifacts remain untracked.

Further detail: [architecture](docs/ARCHITECTURE.md), [datasets](docs/DATASETS.md),
[input contract](docs/INPUT_CONTRACT.md), and
[Hydra configuration reference](docs/HYDRA_CONFIG_REFERENCE.md).
