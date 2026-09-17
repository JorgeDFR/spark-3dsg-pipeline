# Dataset adapters

| Adapter | Structure | Semantics | Visualizer | Mapper |
| --- | --- | --- | --- | --- |
| `uhumans2` | hierarchical | recorded | hierarchical | `uhumans2.yaml` |
| `custom_rgbd` | hierarchical | closed-set | hierarchical | `classic.yaml` |
| `spot` | Khronos | open-set | Khronos | `adt4.yaml` |

uHumans2 plays its recorded class-ID image directly. `custom_rgbd` is the
generic online closed-set example. `spot` is the concrete public ADT4/DCIST-T4
example with Khronos and the default ADT4 prompt.

The ADT4 labels file is replaceable at runtime:

```bash
make run PROFILE=gpu DATASET=spot BAG=/home/spark/data/spot \
  LABELS_CONFIG=/home/spark/data/labels.yaml
```

Changing that prompt does not modify `adt4.yaml` or `yoloe.yaml`.
