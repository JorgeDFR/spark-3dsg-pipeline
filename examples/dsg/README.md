# Example scene graphs

These mesh-bearing Spark-DSG JSON files are small reference outputs for offline
visualization and inspection. Both use the ADE20K full taxonomy and the
hierarchical visualization profile.

| Scene | File |
| --- | --- |
| MIT courtyard | `mit_courtyard_ade20k_full_dsg_with_mesh.json` |
| uHumans2 office | `uhumans2_office_ade20k_full_dsg_with_mesh.json` |

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
