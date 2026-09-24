# Dataset adapters and mapping recipes

A dataset adapter describes the recorded inputs. A mapping recipe selects how
those inputs become a scene graph. Choose them independently with `DATASET`
and `MAPPING`.

## Dataset adapters

| Adapter | Recorded input |
| --- | --- |
| `uhumans2` | TESSE RGB-D/TF topics and recorded semantic images |
| `spot` | ADT4 Hamilton Spot/ZED RGB-D/TF topics |
| `custom_rgbd` | Normalized registered RGB-D/TF example |

Original recordings belong in `data/raw`. Prepared demo bags and preprocessing
outputs belong in `data/normalized`. See [data setup](../data/README.md) for
download and preparation commands.

`DATASET` accepts an example name or a container-visible YAML path. For another
recording, follow the [custom dataset guide](CUSTOM_DATASET.md) and
[adapter reference](CUSTOM_SENSOR.md).

## Mapping recipes

| Recipe | Structure | Semantics | Visualizer | Hydra config |
| --- | --- | --- | --- | --- |
| `recorded` | Hierarchical | Recorded class IDs | Hierarchical | `uhumans2.yaml` |
| `closed_set` | Hierarchical | Online ADE20K | Hierarchical | `classic.yaml` |
| `open_set` | Khronos | Online YOLOE | Khronos | `adt4.yaml` |

Both online recipes work with Spot and uHumans2. They do not consume recorded
semantic images. The `recorded` recipe requires `topics.semantic` and a
compatible class-ID taxonomy. The supplied recipe targets uHumans2.

See the [graph reference](GRAPH_SCHEMA.md) for output layers and profile details.

## Run a demo bag

Complete the image and model setup in the [README demos](../README.md) first.
The commands below use the prepared ROS 2 bags and validate them before mapping.

Run Spot with ADE20K inference:

```bash
make run PROFILE=gpu DATASET=spot MAPPING=closed_set \
  BAG=/home/spark/data/normalized/spot
```

Run uHumans2 with YOLOE inference:

```bash
make run PROFILE=gpu DATASET=uhumans2 MAPPING=open_set \
  BAG=/home/spark/data/normalized/uhumans2
```

## Customize open-set labels

Prepare a labels YAML as described in the
[custom dataset guide](CUSTOM_DATASET.md#customize-open-set-labels).
Pass it with `LABELS_CONFIG`:

```bash
make run PROFILE=gpu DATASET=spot MAPPING=open_set \
  BAG=/home/spark/data/normalized/spot \
  LABELS_CONFIG=/home/spark/data/custom-configs/labels.yaml
```

The labels overlay changes the text vocabulary while retaining the supplied
`adt4.yaml` mapper and `yoloe.yaml` model settings.
