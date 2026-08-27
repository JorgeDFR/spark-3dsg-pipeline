# Debugging

Start with preflight validation. Most apparent mapping failures are missing topics, incompatible image encodings, incomplete TF, or incorrect depth units.

Useful commands:

```bash
make config
make validate-bag PROFILE=core DATASET=custom_rgbd BAG=/data/example
make shell PROFILE=core
ros2 bag info /data/example
ros2 launch spark_dsg_pipeline pipeline.launch.yaml --show-args
```

Run logs are under `/output/<run-id>/logs/`. A startup exit is normally a configuration registration/version mismatch; compare the image lock with `dependencies/UPSTREAM_BASELINE.md`. Do not edit imported source to bypass it.

For online semantics, verify the model checksum with `make models PROFILE=gpu`, then run `scripts/gpu_smoke_test.sh` in a GPU shell. If CUDA is unavailable, verify the NVIDIA driver/toolkit with a standard NVIDIA container before debugging ROS.

If `/tf_static` is missed during bag playback, ensure the QoS override file is being passed. The wrapper does this automatically.

RViz is never a success criterion. Use `make inspect` and `--require-v1` to diagnose graph contents.
