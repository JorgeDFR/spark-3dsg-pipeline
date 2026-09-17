# Example scene graphs

These mesh-bearing Spark-DSG JSON files are small reference outputs for offline
visualization and inspection. Both use the ADE20K full taxonomy and the
hierarchical visualization profile.

| File | Scene | SHA-256 |
| --- | --- | --- |
| `mit_courtyard_ade20k_full_dsg_with_mesh.json` | MIT courtyard | `cf00e8fc98ab3b0c616aba5fc12e347da8ffe8c9dcda58b162718f37970564ad` |
| `uhumans2_office_ade20k_full_dsg_with_mesh.json` | uHumans2 office | `25aa1328301bbd2abddb86275e152b5404fa0ee53912839018febbffbd45fb7e` |

The examples are mounted read-only at `/home/spark/examples` by Compose and are
not copied into Docker images. For example:

```bash
make rviz \
  DSG=/home/spark/examples/dsg/uhumans2_office_ade20k_full_dsg_with_mesh.json \
  VISUALIZATION_PROFILE=hierarchical
```

Each file is below GitHub's 100 MiB per-file limit, but together they add about
107 MiB to a clone. They are marked `-diff` in `.gitattributes` to keep reviews
usable.
