# Custom RGB-D sensor

Copy `src/spark_3dsg_pipeline/config/datasets/custom_rgbd.yaml` to a new YAML
file in the same directory. A dataset adapter describes acquisition only; it
must not select semantics, graph structure, Hydra config, or visualization.

Set these fields to match the rosbag:

- `topics.color`: RGB `sensor_msgs/msg/Image`.
- `topics.depth`: depth registered to the color image.
- `topics.camera_info`: intrinsics for the color image.
- `topics.tf` and `topics.tf_static`: normally `/tf` and `/tf_static`.
- `frames.map`, `frames.robot`, and `frames.sensor`: a connected transform path
  from the fixed frame to the robot and then the camera optical frame.
- `frames.odom`: the odometry frame used by the mapper.
- `depth_encodings`: encodings present in the bag, normally `16UC1`, `32FC1`,
  or both.
- `depth_scale`: units per meter (`1000.0` for millimeters, `1.0` for meters).
- `playback_rate` and `use_sim_time`: rosbag playback behavior.

The color, depth, and camera-info streams must be calibrated and synchronized
tightly enough for registered RGB-D reconstruction. `CameraInfo` must contain
positive image dimensions and focal lengths. The bag also needs monotonically
increasing timestamps and the configured TF paths. The complete normalized
topic contract is documented in [INPUT_CONTRACT.md](INPUT_CONTRACT.md).

Validate before starting a long run:

```bash
make validate-bag PROFILE=gpu DATASET=my_sensor MAPPING=closed_set \
  BAG=/home/spark/data/my_sensor
```

Choose the processing independently:

- `MAPPING=closed_set` uses ADE20K inference and the classic hierarchical
  graph.
- `MAPPING=open_set` uses the configurable YOLOE prompt and Khronos graph.
- `MAPPING=recorded` requires an additional `topics.semantic` image containing
  class IDs, plus a mapping recipe whose label-space and remap configs exactly
  match those IDs. Copy `config/mappings/recorded.yaml` only when that contract
  applies.

Custom mapping recipes belong in `config/mappings`; do not add model or mapper
settings to a dataset adapter. New runtime dependencies belong in the Docker
image and exact-SHA lock, never on the host.
