# Input contract

All adapters normalize bag or perception topics to:

| Topic | Type | Purpose |
| --- | --- | --- |
| `/input/color/image_raw` | `sensor_msgs/msg/Image` | RGB image |
| `/input/color/camera_info` | `sensor_msgs/msg/CameraInfo` | intrinsics |
| `/input/depth/image_rect` | `sensor_msgs/msg/Image` | registered depth |
| `/input/semantic/image_raw` | `sensor_msgs/msg/Image` | class IDs or packed instances |
| `/input/semantic/labelspace` | `semantic_inference_msgs/msg/Labelspace` | open-set names/metadata |
| `/tf`, `/tf_static` | `tf2_msgs/msg/TFMessage` | map/robot/sensor transforms |

Recorded mode requires the semantic image in the bag. Online modes require only
RGB-D, camera info, and TF; perception supplies semantics. Depth encoding and
scale are adapter fields. The required transform paths are map-to-robot and
robot-to-sensor.

`scripts/validate_bag.py` checks this contract before starting expensive GPU
work. Closed-set class IDs deliberately use the generic semantic topic rather
than an instance-specific name.
