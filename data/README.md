# Data

The data root has two lifecycle stages:

```text
data/
├── custom-configs/ # editable dataset, source, preprocessor and labels YAMLs
├── raw/         # source data, including storage-format conversions
│   └── test-preprocess/  # test downloads, ROS 2 conversions, calibration
└── normalized/  # canonical demos and contract-valid preprocessing outputs
    ├── spot/
    ├── uhumans2/
    └── test-preprocess/
```

Set `DATA_DIR` in `.env` to use an external root with the same layout. Mapping
services mount the root read-only at `/home/spark/data`. The single
GPU-enabled preprocessing service mounts the whole root read/write. Bag and
dataset contents are ignored by Git.

Preparation scripts automatically migrate demo bags from the old
`prepared/demos/` layout to `normalized/`. Test downloads are grouped
under `raw/test-preprocess/`. Their ROS 1-to-ROS 2 conversions remain raw because
their topics and TF tree are not normalized. Old test cache paths are
migrated when unambiguous. Remove `NORMALIZED_DATA_DIR` from an existing
`.env`. Normalized outputs are always under `${DATA_DIR}/normalized`.

## Public Spot example

Download the hardware-free Spot mapping bag referenced by Awesome-DCIST-T4
from [Google Drive](https://drive.google.com/file/d/155iqaDarCb7-KN8P_rBOqmAnIBj08TmH/view).
Place `2025-09-04-heracles-eval-3-bag.zip`,
`adt4_spot_example_bag.zip`, or the extracted
`2025-09-04-heracles-eval-3-bag/` directory in `data/raw/`, then run:

```bash
make prepare-data PREPARE_ARGS="--dataset spot"
```

The command creates the canonical `data/normalized/spot` bag path.

Validate and run it with:

```bash
make validate-bag PROFILE=gpu DATASET=spot MAPPING=open_set \
  BAG=/home/spark/data/normalized/spot
```

```bash
make run PROFILE=gpu DATASET=spot MAPPING=open_set \
  BAG=/home/spark/data/normalized/spot
```

## Public uHumans2 example

Download `uHumans2_office_s1_00h_v2.bag` from
[Google Drive](https://drive.google.com/file/d/1awAzQ7R1hdS5O1Z2zOcpYjK7F4_APq_p/view?usp=drive_link),
place it in `data/raw/`, then run:

```bash
make prepare-data PREPARE_ARGS="--dataset uhumans2"
```

The preparation container uses `rosbags-convert` when the input is a ROS 1 bag
and writes the canonical ROS 2 bag to `data/normalized/uhumans2`. It also
recognizes a ZIP containing that hard-coded filename and already-converted
directories named `uHumans2_office_s1_00h_v2_ros2` under `data/raw/`.

For a CPU run using recorded ground-truth semantics:

```bash
make build PROFILE=core
```

```bash
make validate-bag PROFILE=core DATASET=uhumans2 MAPPING=recorded \
  BAG=/home/spark/data/normalized/uhumans2
```

```bash
make run PROFILE=core DATASET=uhumans2 MAPPING=recorded \
  BAG=/home/spark/data/normalized/uhumans2
```

Preparation only normalizes storage and converts bag format. It does not
synthesize semantic topics. A recording without the adapter's precomputed
semantic image topic cannot use `MAPPING=recorded`, so always validate the
converted bag first. Either online mapping can use the uHumans2 RGB-D input
without consuming its recorded semantic topic.

Downloads are intentionally manual: this repository does not redistribute bags or place large dataset files under version control.

Always run `make validate-bag ...` before a long mapping run.

## Optional preprocessing tests

`make build-preprocess` followed by `make test-preprocess` downloads and
checks approximately 1.25 GiB of ZED2 Lake, UoSM ZED2i, D435i and TUM RGB-D data.
These fixtures are separate from the mapping examples. See the
[test fixture guide](../tests/fixtures/preprocessing/README.md) for cache paths,
licenses and rerun options. Downloaded files remain ignored by Git.
