# Changelog

## Unreleased

- Separate scene structure, semantic source/taxonomy, and visualization profile
  in dataset adapters, with fail-fast compatibility checks.
- Rebuild `classic.yaml` as hierarchical Hydra reconstruction with online
  closed-set semantics and externalize uHumans2 taxonomy/remapping.
- Split YOLOE model settings from replaceable ADT4 prompts and add independent
  closed-set/open-set perception launches.
- Add hierarchical and Khronos renderer profiles plus native saved-DSG JSON
  visualization.
- Define `v1` solely as the immutable exact-SHA upstream snapshot, rename the
  output acceptance flag, and remove unavailable pipeline placeholders.
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
- Isolate Hydra and perception launch arguments and resolve package resources
  through the ament package share instead of assuming an install layout.
- Delay bag playback until Hydra creates its camera input subscription and retain
  all static-transform batches for late DDS discovery.
- Pass all dataset topic remaps through one rosbag2 `--remap` option so RGB,
  depth, and CameraInfo are normalized together.
- Make `bag.launch.yaml` and `visualization.launch.yaml` the canonical playback
  and RViz entry points, including dataset TF remaps and fixed-frame selection.
- Configure RViz displays for the DSG mesh, graph markers, and agent trajectory,
  and syntax-check every installed launch file.
- Remove the unused no-op Docker entrypoint and use the repository dependency
  bootstrap script as the single `vcstool` import implementation.
