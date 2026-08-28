# Datasets

Adapters live in `src/spark_3dsg_pipeline/config/datasets/` and contain topic
names, frame names, depth units, playback policy, semantics source, and the
default complete Hydra profile for that input contract.

## Spot

`spot.yaml` is the default adapter. It matches the Hamilton hardware-free bag linked from the Awesome-DCIST-T4 README: `/hamilton/hamilton_zed/...` RGB-D topics and the `hamilton/map`, `hamilton/odom`, and `hamilton/base_link` frame tree. No Spot SDK or driver is required for playback.

It selects `adt4.yaml`. Use `HYDRA_CONFIG=classic.yaml` with the same online
semantic contract when the run should additionally generate GVD `PLACES` and
structural `ROOMS`.

## uHumans2

`uhumans2.yaml` supplies the inexpensive CPU demo with recorded ground-truth
semantic images. Its core-Hydra profile produces classical `OBJECTS`, GVD
`PLACES`, `ROOMS`, and `BUILDINGS` without loading Khronos. It catches ROS, TF,
startup, serialization, dependency, and DSG parsing regressions; it is not the
default modern perception architecture.

## Custom RGB-D

Copy `custom_rgbd.yaml`, change its topics/frames/depth scale, then follow `CUSTOM_SENSOR.md`.

Datasets and bags are never committed. Set `DATA_DIR` in `.env` and use `/home/spark/data/...` in Make commands. Public example download, preparation, validation, and execution instructions are centralized in [data/README.md](../data/README.md).
