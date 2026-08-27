# Datasets

Adapters live in `ros_ws/src/spark_dsg_pipeline/config/datasets/` and contain only topic names, frame names, depth units, playback policy, and semantics source.

## Spot

`spot.yaml` is intended for the hardware-free bag linked from the Awesome-DCIST-T4 README and follows its recorded `/<robot>/<robot>_zed/...` RGB-D topics. Spot payload/bag conventions have changed over time; run validation and adjust only this YAML if the downloaded snapshot differs. No Spot SDK or driver is required for playback.

## uHumans2

`uhumans2.yaml` supplies the inexpensive CPU smoke path with recorded ground-truth semantic images. It catches ROS, TF, startup, serialization, dependency, and DSG parsing regressions; it is not the default modern perception architecture.

## Custom RGB-D

Copy `custom_rgbd.yaml`, change its topics/frames/depth scale, then follow `CUSTOM_SENSOR.md`.

Datasets and bags are never committed. Set `DATA_DIR` in `.env` and use `/data/...` in Make commands.
