# Input contract

All adapters normalize bag or perception topics to:

| Topic | Type | Purpose |
| --- | --- | --- |
| `/input/color/image_raw` | `sensor_msgs/msg/Image` | RGB image |
| `/input/color/camera_info` | `sensor_msgs/msg/CameraInfo` | intrinsics |
| `/input/depth/image_rect` | `sensor_msgs/msg/Image` | registered depth |
| `/input/semantic/image_raw` | `sensor_msgs/msg/Image` | class IDs or packed instances |
| `/input/semantic/labelspace` | `semantic_inference_msgs/msg/Labelspace` | open-set names/metadata |
| `/input/imu` | `sensor_msgs/msg/Imu` | optional normalized IMU stream |
| `/input/odometry` | `nav_msgs/msg/Odometry` | optional odometry diagnostics |
| `/tf`, `/tf_static` | `tf2_msgs/msg/TFMessage` | odom/robot/sensor transforms |

The dataset adapter always declares RGB-D, camera info, and TF. The selected
mapping recipe determines whether a semantic image is also required: recorded
mode requires `topics.semantic`, while online modes supply semantics through
perception. Depth encoding and scale are adapter fields. The required transform
paths are `odom -> robot` and `robot -> sensor`. `map -> odom` is optional
input: Hydra's backend can publish this correction, and preprocessing must not
create a competing broadcaster.

`scripts/python/validate_bag.py` checks this contract before starting expensive GPU
work and therefore accepts both `--dataset` and `--mapping`. Closed-set class
IDs deliberately use the generic semantic topic rather than an
instance-specific name.
