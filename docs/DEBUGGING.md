# Debugging

Start with preflight validation. Most apparent mapping failures are missing topics, incompatible image encodings, incomplete TF, or incorrect depth units.

Useful commands:

```bash
make config
make validate-bag PROFILE=core DATASET=custom_rgbd BAG=/home/spark/data/example
make shell PROFILE=core
ros2 bag info /home/spark/data/example
ros2 launch spark_3dsg_pipeline pipeline.launch.yaml --show-args
ros2 launch spark_3dsg_pipeline bag.launch.yaml --show-args
ros2 launch spark_3dsg_pipeline visualization.launch.yaml --show-args
```

For a downloaded public example whose archive or extracted directory still has its upstream name, create the documented canonical bag path first:

```bash
make prepare-data
```

Use `PREPARE_ARGS="--dataset spot"` or `PREPARE_ARGS="--dataset uhumans2"` to limit detection to one example. The command refuses to overwrite an existing canonical path that is not a valid ROS 2 bag.

Run logs are under `/home/spark/output/<run-id>/logs/`. A startup exit is normally a configuration registration/version mismatch; compare the image lock with `dependencies/UPSTREAM_BASELINE.md`. Do not edit imported source to bypass it.

The Spot bag records `map -> hamilton/map -> hamilton/odom -> hamilton/body -> hamilton/base_link`. The adapter intentionally uses `hamilton/map` as Hydra's local map frame. Validation waits for both configured TF paths instead of accepting the first arbitrary TF edges; on a genuine failure it prints the sampled connected component.

Online perception publishes the labelspace before Hydra constructs its camera input. The run wrapper therefore waits for Hydra's `/input/color/camera_info` subscription before starting bag playback. The `/tf_static` playback profile retains 100 samples because the Spot example stores its static tree in several messages; reducing this to depth 1 makes late subscribers receive only the final camera-transform batch.

For online semantics, verify the model checksum with `make models PROFILE=gpu`, then run `scripts/gpu_smoke_test.sh` in a GPU shell. If CUDA is unavailable, verify the NVIDIA driver/toolkit with a standard NVIDIA container before debugging ROS.

## Mounted-directory permissions

The images run as `spark`, using the `HOST_UID` and `HOST_GID` configured in `.env`. Confirm them with `id -u` and `id -g`, then rebuild after changing either value. The host user must already be able to write the configured model and output directories.

An existing `spark-cache` volume created by an older root-running image keeps its old ownership. Repair it once with:

```bash
docker compose --profile core run --rm --user root core \
  chown -R "$(id -u):$(id -g)" /home/spark/.cache
```

If `/tf_static` is missed during bag playback, ensure the QoS override file is being passed. The wrapper does this automatically.

`make rviz DATASET=spot` starts `visualization.launch.yaml`, which resolves the
Spot adapter to the `hamilton/map` fixed frame and connects the upstream Hydra
streaming visualizer to `/hydra/backend/dsg`. RViz is never a success criterion.
Use `make inspect` and `--require-v1` to diagnose graph contents.
