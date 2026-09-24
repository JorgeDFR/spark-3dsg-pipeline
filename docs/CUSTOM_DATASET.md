# Run your own dataset

Use this workflow to take a recording from `data/raw` to a mapping run.
The pipeline needs registered RGB-D images, camera intrinsics, and connected
odometry/body/camera transforms. Online semantic inference supplies its own
labels. See the [input contract](INPUT_CONTRACT.md) for the exact requirements.

## Setup

Configure `.env` and build the images as described in the
[demo setup](../README.md#before-running-a-demo). Bag processing and mapping
run inside Docker.

Run the commands below from the repository root. File-copy commands use host
paths. Arguments passed to pipeline commands use container paths:

| Purpose | Host path | Container path |
| --- | --- | --- |
| Original recordings | `data/raw/` | `/home/spark/data/raw/` |
| Mapping-ready bags | `data/normalized/` | `/home/spark/data/normalized/` |
| Editable YAML configs | `data/custom-configs/` | `/home/spark/data/custom-configs/` |

If `.env` sets an external `DATA_DIR`, use that root instead of `data` in host
commands. Container paths stay the same.

## 1. Add recording

Keep a ROS 2 bag's complete directory, including `metadata.yaml` and its storage
files. Choose the next step based on the recording format:

| Recording | Next step |
| --- | --- |
| ROS 2 bag, for example `data/raw/session/` | Check the mapping inputs in step 2. |
| ROS 1 bag, for example `data/raw/session.bag` | Follow [ROS 1 conversion](PREPROCESSING.md#ros-1-bags), then check the converted ROS 2 bag in step 2. |
| ZED SVO/SVO2 file | Follow [preprocessing](PREPROCESSING.md) to select a matching ZED source profile and produce a ROS 2 bag, then continue at step 4. |

Storage conversion alone does not supply missing measurements or register depth.

## 2. Validate ROS 2 bag

The `custom_rgbd` example uses normalized `/input/...` topics. If its topics,
frames, and depth units match your bag, validate with:

```bash
make validate-bag PROFILE=core DATASET=custom_rgbd MAPPING=open_set \
  BAG=/home/spark/data/raw/session
```

If your recording uses different topic names, frames, or depth units, copy the
example into the data directory:

```bash
cp src/spark_3dsg_pipeline/config/datasets/custom_rgbd.yaml data/custom-configs/session.yaml
```

Edit `session.yaml` to match the recording. The
[dataset adapter reference](CUSTOM_SENSOR.md) explains each field. Repeat the
check using the edited file:

```bash
make validate-bag PROFILE=core MAPPING=open_set \
  DATASET=/home/spark/data/custom-configs/session.yaml \
  BAG=/home/spark/data/raw/session
```

A dataset config describes existing data. Changing it cannot create missing
odometry or align depth images.

- **Validation passes:** move the complete bag directory to
  `data/normalized/session`, then continue at step 4. Keep the dataset config
  that passed validation.
- **Required inputs or depth registration are missing:** continue at step 3.
- **The config does not match the recording:** correct it and repeat validation.

## 3. Preprocess recording

Follow the [preprocessing guide](PREPROCESSING.md) to:

1. Choose an example source profile for your recording and a pose provider.
2. Copy source and preprocessor YAMLs into `data/custom-configs` if they need edits.
3. Run `make validate-source` to check the selected preprocessor's input requirements.
4. Run `make preprocess` with an output such as
   `/home/spark/data/normalized/session`.

That guide includes custom-config commands, ROS 1 conversion, and SVO/SVO2
playback. Preprocessing produces a checked ROS 2 bag and a matching
`dataset.yaml`. Use that generated adapter for mapping so frames and depth
settings remain consistent with the output.

`validate-bag` checks mapping inputs. `validate-source` checks preprocessing
inputs. `test-preprocess` runs the toolbox's public-data integration tests and
is not a step in processing your recording.

## 4. Run mapping

Build the GPU image and download model weights if you have not already done so:

```bash
make build PROFILE=gpu
```

```bash
make models PROFILE=gpu
```

Choose a supplied mapping recipe:

| Setting | Semantic inference | Scene graph |
| --- | --- | --- |
| `MAPPING=open_set` | YOLOE with configurable labels | Khronos |
| `MAPPING=closed_set` | ADE20K classes | Hierarchical Hydra |

Both recipes use their bundled Hydra configurations.

### Validated bag

Use the dataset adapter from step 2:

```bash
make run PROFILE=gpu MAPPING=open_set \
  BAG=/home/spark/data/normalized/session \
  DATASET=/home/spark/data/custom-configs/session.yaml
```

Use `DATASET=custom_rgbd` instead if the unchanged example passed validation.

### Preprocessed bag

Use the generated adapter:

```bash
make run PROFILE=gpu MAPPING=open_set \
  BAG=/home/spark/data/normalized/session \
  DATASET=/home/spark/data/normalized/session/dataset.yaml
```

`make run` validates the selected bag before starting mapping. Results are
written under `/home/spark/output`. See
[scene graph outputs and tools](../README.md#scene-graph-outputs-and-tools)
for inspection and visualization commands.

## Customize open-set labels

Copy the example vocabulary:

```bash
cp src/spark_3dsg_pipeline/config/perception/labels/adt4.yaml data/custom-configs/labels.yaml
```

Edit `model.instance_model.text_prompt` in `labels.yaml`, then supply the file
with `LABELS_CONFIG`. For a preprocessed bag:

```bash
make run PROFILE=gpu MAPPING=open_set \
  BAG=/home/spark/data/normalized/session \
  DATASET=/home/spark/data/normalized/session/dataset.yaml \
  LABELS_CONFIG=/home/spark/data/custom-configs/labels.yaml
```

For an already mapping-ready bag, substitute the dataset adapter from step 2.
`LABELS_CONFIG` applies only to `MAPPING=open_set`.

## Configuration files

The ROS package configs are bundled examples. `DATASET`, `SOURCE`, and
`PREPROCESSOR` accept example names or explicit container-visible YAML paths.
`LABELS_CONFIG` accepts a YAML path.

Files in `data/custom-configs` are ignored by Git and available through the
data mount. Editing them needs no image rebuild. Source, scripts, and bundled
examples are baked into the images. Rebuild the relevant image after changing
those repository files.
