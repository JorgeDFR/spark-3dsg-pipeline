# Data

Place downloaded archives/bags here or set `DATA_DIR` in `.env` to an external dataset root. Runtime services mount the directory read-only at `/home/spark/data`; the dedicated preparation service mounts it read-write. Bags and datasets are ignored by Git.

## Public Spot example

Download the hardware-free Spot mapping bag referenced by Awesome-DCIST-T4 from [Google Drive](https://drive.google.com/file/d/155iqaDarCb7-KN8P_rBOqmAnIBj08TmH/view). Leave `2025-09-04-heracles-eval-3-bag.zip`, `adt4_spot_example_bag.zip`, or the extracted `2025-09-04-heracles-eval-3-bag/` directory here, then run:

```bash
make prepare-data PREPARE_ARGS="--dataset spot"
```

The command creates the canonical `data/spot` bag path.

Validate and run it with:

```bash
make validate-bag PROFILE=gpu DATASET=spot MAPPING=open_set \
  BAG=/home/spark/data/spot
make run PROFILE=gpu DATASET=spot MAPPING=open_set \
  BAG=/home/spark/data/spot
```

## Public uHumans2 example

Download `uHumans2_office_s1_00h_v2.bag` from [Google Drive](https://drive.google.com/file/d/1awAzQ7R1hdS5O1Z2zOcpYjK7F4_APq_p/view?usp=drive_link), then run:

```bash
make prepare-data PREPARE_ARGS="--dataset uhumans2"
```

The preparation container uses `rosbags-convert` when the input is a ROS 1 bag and writes the canonical ROS 2 bag to `data/uhumans2`. It also recognizes a ZIP containing that hard-coded filename and already-converted directories named `uHumans2_office_s1_00h_v2_ros2`.

For a CPU run using recorded ground-truth semantics:

```bash
make build PROFILE=core
make validate-bag PROFILE=core DATASET=uhumans2 MAPPING=recorded \
  BAG=/home/spark/data/uhumans2
make run PROFILE=core DATASET=uhumans2 MAPPING=recorded \
  BAG=/home/spark/data/uhumans2
```

Preparation only normalizes storage and converts bag format; it does not
synthesize semantic topics. A recording without the adapter's precomputed
semantic image topic cannot use `MAPPING=recorded`, so always validate the
converted bag first. Either online mapping can use the uHumans2 RGB-D input
without consuming its recorded semantic topic.

Downloads are intentionally manual: this repository does not redistribute bags or place large dataset files under version control.

Always run `make validate-bag ...` before a long mapping run.
