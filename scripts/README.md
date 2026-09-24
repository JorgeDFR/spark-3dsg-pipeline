# Repository scripts

The scripts are grouped by interpreter:

- `python/` contains configuration, validation, dataset preparation, and
  preprocessing command-line utilities.
- `shell/` contains Docker build, launch, test, and pipeline orchestration
  entry points.

Reusable preprocessing implementation belongs in the
`spark_3dsg_preprocessing` Python package. In particular, deterministic bag
normalization and offline depth projection live in
`spark_3dsg_preprocessing.offline_normalize`. `python/preprocess_bag.py` is its
repository-level command-line orchestrator.
