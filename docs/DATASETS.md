# Dataset adapters and mapping recipes

Dataset adapters and mapping recipes are deliberately independent.

| Dataset adapter | Bag-specific input |
| --- | --- |
| `uhumans2` | TESSE RGB-D/TF topics plus recorded semantic images |
| `spot` | ADT4 Hamilton Spot/ZED RGB-D/TF topics |
| `custom_rgbd` | Generic registered RGB-D/TF template |

| Mapping recipe | Structure | Semantics | Visualizer | Mapper |
| --- | --- | --- | --- | --- |
| `recorded` | hierarchical | recorded class IDs | hierarchical | `uhumans2.yaml` |
| `closed_set` | hierarchical | online ADE20K | hierarchical | `classic.yaml` |
| `open_set` | Khronos | online YOLOE | Khronos | `adt4.yaml` |

The online recipes can be composed with either `spot` or `uhumans2`, for
example:

```bash
make run PROFILE=gpu DATASET=spot MAPPING=closed_set \
  BAG=/home/spark/data/spot
make run PROFILE=gpu DATASET=uhumans2 MAPPING=open_set \
  BAG=/home/spark/data/uhumans2
```

`recorded` requires `topics.semantic` in the selected dataset and a compatible
class-ID taxonomy. The supplied recipe is therefore intended for uHumans2.

The open-set ADT4 labels file is replaceable at runtime:

```bash
make run PROFILE=gpu DATASET=spot MAPPING=open_set \
  BAG=/home/spark/data/spot \
  LABELS_CONFIG=/home/spark/data/labels.yaml
```

Changing that prompt does not modify `adt4.yaml` or `yoloe.yaml`.
