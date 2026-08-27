# Changelog

## Unreleased

- Add Docker-first core and GPU profiles.
- Add exact public dependency locks and upstream provenance.
- Add the `spark_3dsg_pipeline` ROS 2 integration package and dataset adapters.
- Add model download, bag validation, deterministic run output, and DSG inspection tools.
- Run containers with a host-matched non-root UID and GID.
- Add automatic preparation of the public Spot and uHumans2 example bags.
- Rename the integration package to `spark_3dsg_pipeline` and move it to the
  repository-level `src/` directory.
- Bind-mount the integration package into a symlink-installed container
  workspace so launch and configuration edits do not require image rebuilds.
- Wait for the configured TF paths during bag validation instead of stopping
  after an arbitrary initial set of transforms.
