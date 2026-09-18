# spark-3dsg-pipeline

Docker/ROS integration for building Spark-DSG scene graphs with the public
MIT-SPARK stack. The repository owns launch, configuration, validation, and
reproducibility glue; Hydra, Khronos, Spark-DSG, and semantic inference remain
upstream components.

Dataset adapters describe only the bag interface (topics, frames, depth, and
playback). An independent mapping recipe selects the graph structure, semantic
source, models, and matching visualizer:

| `MAPPING` | Scene structure | Semantic source | RViz profile |
| --- | --- | --- | --- |
| `recorded` | hierarchical Hydra | recorded uHumans2 class IDs | hierarchical |
| `closed_set` | hierarchical Hydra (`classic.yaml`) | ADE20K closed-set inference | hierarchical |
| `open_set` | Khronos (`adt4.yaml`) | YOLOE open-set inference | Khronos |

This separation lets both the Spot and uHumans2 RGB-D bags run with either
online semantic pipeline. Recorded mode additionally requires a semantic image
in the bag, which the uHumans2 adapter provides.

## Before running a demo

Host requirements are Docker and, for GPU demos, an NVIDIA driver plus NVIDIA
Container Toolkit. Do not install ROS, CUDA, or runtime Python packages on the
host.

```bash
cp .env.example .env
```

Download and prepare a demo bag as described in [data setup](data/README.md).
All paths in the commands below are container paths.

## uHumans2 recorded-semantics demo

This CPU demo uses the semantic class-ID images already stored in uHumans2. It
builds the classic hierarchical graph and does not start an inference node.

Build the core image:

```bash
make build PROFILE=core
```

Validate the bag contract:

```bash
make validate-bag PROFILE=core DATASET=uhumans2 MAPPING=recorded \
  BAG=/home/spark/data/uhumans2
```

Start mapping:

```bash
make run PROFILE=core DATASET=uhumans2 MAPPING=recorded \
  BAG=/home/spark/data/uhumans2
```

To view the live graph with the hierarchical visualizer, run this in a second
terminal while the pipeline is active:

```bash
make rviz DATASET=uhumans2 MAPPING=recorded
```

## Closed-set demo

This GPU demo runs ADE20K segmentation and the classic hierarchical mapper.
The same mapping recipe works with either example bag.

Build the GPU image:

```bash
make build PROFILE=gpu
```

Download the model weights:

```bash
make models PROFILE=gpu
```

Choose the dataset below. uHumans2 is expanded by default.

<details>
<summary><strong>Spot</strong></summary>

Start mapping:

```bash
make run PROFILE=gpu DATASET=spot MAPPING=closed_set \
  BAG=/home/spark/data/spot
```

To view the live graph, run this in a second terminal:

```bash
make rviz DATASET=spot MAPPING=closed_set
```

</details>

<details open>
<summary><strong>uHumans2</strong></summary>

Its recorded semantic topic is ignored in this mode. Start mapping with:

```bash
make run PROFILE=gpu DATASET=uhumans2 MAPPING=closed_set \
  BAG=/home/spark/data/uhumans2
```

To view the live graph, run this in a second terminal:

```bash
make rviz DATASET=uhumans2 MAPPING=closed_set
```

</details>

<p></p>

`make run` validates the selected bag and mapping before starting inference.
Use `make validate-bag` with the same `PROFILE`, `DATASET`, `MAPPING`, and `BAG`
when you want to run that check separately.

## Open-set demo

This GPU demo runs YOLOE with the default ADT4 prompt and the ADT4/Khronos
mapper. It also accepts either example bag.

Build the GPU image:

```bash
make build PROFILE=gpu
```

Download the model weights:

```bash
make models PROFILE=gpu
```

Choose the dataset below. uHumans2 is expanded by default.

<details>
<summary><strong>Spot</strong></summary>

Start mapping:

```bash
make run PROFILE=gpu DATASET=spot MAPPING=open_set \
  BAG=/home/spark/data/spot
```

To view the live graph, run this in a second terminal:

```bash
make rviz DATASET=spot MAPPING=open_set
```

</details open>

<details>
<summary><strong>uHumans2</strong></summary>

Its recorded semantic topic is ignored in this mode. Start mapping with:

```bash
make run PROFILE=gpu DATASET=uhumans2 MAPPING=open_set \
  BAG=/home/spark/data/uhumans2
```

To view the live graph, run this in a second terminal:

```bash
make rviz DATASET=uhumans2 MAPPING=open_set
```

</details>

<p></p>

To replace the open-set prompt without changing the mapper or model settings,
provide a labels overlay:

```yaml
model:
  instance_model:
    text_prompt: [ignore, chair, mug]
```

```bash
make run PROFILE=gpu DATASET=spot MAPPING=open_set \
  BAG=/home/spark/data/spot \
  LABELS_CONFIG=/home/spark/data/my_labels.yaml
```

See [model setup](docs/MODELS.md) for model locations, checksums, and the
qualified CUDA/TensorRT/PyTorch stack.

## Scene graph outputs and tools

### Visualize a saved DSG JSON file

The repository examples are both hierarchical graphs. Open the uHumans2
example with:

```bash
make rviz \
  DSG=/home/spark/examples/dsg/uhumans2_office_ade20k_full_dsg_with_mesh.json \
  VISUALIZATION_PROFILE=hierarchical
```

Open the MIT courtyard example with:

```bash
make rviz \
  DSG=/home/spark/examples/dsg/mit_courtyard_ade20k_full_dsg_with_mesh.json \
  VISUALIZATION_PROFILE=hierarchical
```

For a saved ADT4/Khronos graph, select
`VISUALIZATION_PROFILE=khronos` instead. If `dsg.json` is supplied, the wrapper
automatically uses its `dsg_with_mesh.json` sibling when present. The pinned
visualizer loads JSON directly; Hydra or Khronos need not be running.

### Inspect pipeline output

```bash
make inspect DSG=/home/spark/output/run/dsg.json \
  INSPECT_ARGS=--require-pipeline-output
```

Each run is written under `/home/spark/output` with `dataset.yaml`,
`mapping.yaml`, the resolved semantic/Hydra inputs, logs, `dsg.json`,
`dsg_with_mesh.json`, and `mesh.ply`. Metadata records
`pipeline_version: v1` and the exact dependency-lock hash; `v1` names only the
immutable upstream snapshot in `dependencies/locks/v1.lock.repos`.

## Additional dataset and mapping configuration

`custom_rgbd` is the starting adapter for another registered RGB-D bag. Copy
`src/spark_3dsg_pipeline/config/datasets/custom_rgbd.yaml`, then set the bag's
color, registered-depth, camera-info, `/tf`, and `/tf_static` topics; its map,
robot, and camera optical frames; accepted depth encoding/scale; and playback
rate. The bag must provide valid camera intrinsics and connected map-to-robot
and robot-to-sensor transforms. Online mappings do not require semantic images.

The exact field-by-field procedure and validation command are in
[Custom RGB-D sensor](docs/CUSTOM_SENSOR.md); the normalized topics and TF
requirements are in the [input contract](docs/INPUT_CONTRACT.md). Keeping those
details there avoids maintaining a second, diverging checklist in this README.

Mapping recipes live separately under
`src/spark_3dsg_pipeline/config/mappings`. Choose `MAPPING=closed_set` or
`MAPPING=open_set` for a custom adapter. Recorded mode is appropriate only when
the adapter names a compatible class-ID semantic topic and the mapping's Hydra
label-space/remap files match those IDs. Mapper internals and safe overrides are
documented in the [Hydra configuration reference](docs/HYDRA_CONFIG_REFERENCE.md).

## Tests

Run the repository test suite:

```bash
make test PROFILE=core
```

Run static and launch-file checks:

```bash
make lint PROFILE=core
```

These targets use the complete core Docker image. Repository-only tests may
also run from the ignored `.venv`. GPU/runtime smoke tests are described in
[debugging](docs/DEBUGGING.md). Model, bag, mesh, and output artifacts remain
untracked.

Further detail: [architecture](docs/ARCHITECTURE.md),
[datasets and mappings](docs/DATASETS.md), and
[graph schema](docs/GRAPH_SCHEMA.md).
