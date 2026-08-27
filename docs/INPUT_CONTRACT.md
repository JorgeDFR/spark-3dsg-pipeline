# Input contract

Dataset-specific names end at the bag adapter. The mapper always sees:

| Topic | Type | Requirement |
| --- | --- | --- |
| `/input/color/image_raw` | `sensor_msgs/msg/Image` | RGB8/BGR8 image |
| `/input/depth/image_rect` | `sensor_msgs/msg/Image` | registered to color; `16UC1` or `32FC1` |
| `/input/color/camera_info` | `sensor_msgs/msg/CameraInfo` | intrinsics for the color geometry |
| `/input/semantic/instances` | `sensor_msgs/msg/Image` | `32SC1`; high 16 bits semantic ID, low 16 bits instance ID |
| `/input/semantic/labelspace` | `semantic_inference_msgs/msg/Labelspace` | label names and object-label metadata |
| `/tf`, `/tf_static` | `tf2_msgs/msg/TFMessage` | connected pose/extrinsics tree |

Online profiles produce the semantic topics from the normalized color image. Precomputed profiles require them in the bag.

Frames are declared per dataset:

- `map`: stable graph/backend frame
- `odom`: locally continuous odometry frame
- `robot`: body frame whose trajectory becomes the agent layer
- `sensor`: optical camera frame

Required connectivity is `map -> ... -> robot -> ... -> sensor`. Color, depth, and semantics must share timestamps closely enough for approximate synchronization. Depth must already be registered to RGB; the integration layer does not perform calibration or registration.

`depth_scale` records/validates the dataset convention. The pinned Hydra converts `16UC1` millimetres by `0.001` and treats `32FC1` as metres. A sensor using another convention must normalize depth before this boundary.
