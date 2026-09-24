# Camera acquisition profiles

These are starting configurations for **recorded data**, not live-camera launch
files or guarantees that a driver version works with every device. Acquisition
settings and actual bag metadata take precedence. Vendor drivers other than ZED
are not installed in the preprocessing image. Run acquisition/conversion in a
suitable container, then follow [the preprocessing workflow](PREPROCESSING.md).

| Model / profile | IMU | Native pose | Depth input used |
| --- | --- | --- | --- |
| ZED 2i / `zed2i_svo` | Yes | SDK tracking | Registered left/RGB, metres |
| ZED X / `zedx_svo` | Yes | SDK tracking | Registered left/RGB, metres |
| Original ZED / `zed_original_svo` | No | SDK visual tracking | Registered left/RGB, metres |
| RealSense / `realsense` | Model-dependent. Omitted | No | Color-aligned, millimetres |
| D455 / `realsense_d455` | Accel + gyro | No | Color-aligned, millimetres |
| L515 / `realsense_l515` | Accel + gyro | No | Color-aligned, millimetres |
| DS77C Pro / `vzense_ds77c_pro` | None documented | No | Depth transformed to color, millimetres |
| NYX660 / `vzense_nyx660` | None documented | No | Depth transformed to color, millimetres |
| Visionary-S AP / `sick_visionary_s_ap` | Optional driver component | No | **Adapted** optical Z in metres |
| Visionary-S CX / `sick_visionary_s_cx` | Not exposed by this driver | No | Legacy Z map. Verify millimetres |

An IMU does not supply a trajectory. Use RTAB-Map, a calibrated OpenVINS setup,
or an external recorded TF/odometry source where native pose is unavailable.
If acquisition did not record IMU, remove the `imu` entries from both `topics`
and `frames` in your copied source profile. Each camera profile is a standalone
YAML under its family directory. No parent configuration is required.

## ZED

`zed_rosbag` uses wrapper 5.1+ naming under `/zed/zed_node`:
`rgb/color/rect/image`, `rgb/color/rect/camera_info`,
`right/color/rect/image`, `depth/depth_registered`, `imu/data`, and `odom`.
Enable the corresponding streams when recording. Right-image publication is
needed for stereo OpenVINS. Older wrappers use different image names, including
`left/image_rect_color`. Edit your source for those recordings.

RGB aliases the left camera. Depth is `32FC1` metres registered to that image.
Verify matching publication dimensions and CameraInfo when downsampling.
Frames are `zed_camera_link`, `zed_left_camera_frame_optical`, and
`zed_imu_link`, with `odom` for incremental tracking. Record `/tf_static`.
Record `/tf` for passthrough or `odom` for recorded-odometry preprocessing.
The generic bag profile works for both 2i and X with `camera_name=zed`.
`zed_original_rosbag` removes the IMU requirement.

SVO profiles select the SDK camera model. ZED X acquisition requires compatible
GMSL2/ZED Link hardware. An SVO playback profile does not make this desktop
container a Jetson acquisition environment. The original ZED has no IMU.
See [legacy SVO settings](PREPROCESSING.md#older-svo-recordings) for recordings
without usable inertial data.

Sources: [vendor ROS 2 interface](https://docs.stereolabs.com/docs/integrations/ros-2/zed-stereo-node),
[SDK recording formats](https://www.stereolabs.com/docs/development/zed-sdk/modules/camera/recording).
The runtime wrapper itself remains pinned in the repository dependency lock.

## RealSense D455, L515 and generic devices

The ROS 2 defaults `camera_namespace=camera`, `camera_name=camera` produce
`/camera/camera`. Examples select `color/image_raw`, `color/camera_info`, and
`aligned_depth_to_color/image_raw` with its own CameraInfo. Enable
`align_depth.enable:=true`. Raw `depth/image_rect_raw` is in depth-camera
geometry. Use `realsense_unregistered` to register it during preprocessing.
Do not pair aligned depth with raw depth intrinsics.

Frames use `camera_link`, `camera_color_optical_frame`, and
`camera_depth_optical_frame`. Capture factory static TF. D455/L515 profiles
also expect `/camera/camera/imu` in `camera_imu_optical_frame`: enable accel,
gyro and `unite_imu_method` (1 for copying, 2 for interpolation). Separate
`accel/sample` and `gyro/sample` streams are not the combined input expected by
OpenVINS. D455 has an IMU, as does L515. Neither supplies native odometry.
Stereo D455 acquisition can additionally record `infra1/image_rect_raw` and
`infra2/image_rect_raw`, but using them for VIO requires a profile and calibration
for that exact stereo rig, not RGB intrinsics.

L515 is discontinued. Use an acquisition SDK/wrapper version supporting L500.
The shared naming template is not a claim of current SDK hardware support.
The wrapper's ROS depth output is standard `16UC1` millimetres. Do not substitute
raw SDK integer counts without applying the device's depth unit.

Sources: [wrapper interface and defaults](https://github.com/realsenseai/realsense-ros/tree/9a11121700cb4780e273e34141f6402fe184321d),
[L515 datasheet](https://realsenseai.com/wp-content/uploads/2025/06/Intel_RealSense_LiDAR_L515_Datasheet_Rev003.pdf).

## Vzense DS77C Pro and NYX660

The examples use the **ScepterSDK ROS2 plugin**, which supports these families.
Its default camera name is `tof_camera`. Replace `SERIAL` in topic names with
your configured `camera_sn`. Topics are
`/tof_camera/SERIAL/color/image_raw`, `color/camera_info`,
`transformedDepth/image_raw`, and `transformedDepth/camera_info`.
Enable `transformed_depth` (off in the supplied driver defaults).
`transformedDepth` uses color intrinsics. `transformedColor` is the reverse
operation and must not be substituted. Depth is `16UC1` millimetres.

The driver uses frame names without serial numbers: `tof_camera_frame`,
`tof_camera_color_frame`, `tof_camera_depth_frame` and
`tof_camera_transformedDepth_frame`. The registered stream is normalized into
the color optical frame. Verify calibration and TF in your driver revision.
The plugin's frame naming is not a guarantee of REP-103 body axes. Set a unique
camera name for each device. Use the driver's static-TF publication mode
(intra-process communication disabled) and record `/tf_static`. Estimator
playback deliberately omits recorded dynamic `/tf`.

Older **Nebula** integrations use `/Vzense/...` and have different transformed
image headers. They need an edited source. Their topic table is not the current
Scepter interface. Neither family profile declares IMU or odometry.

Sources: [Scepter ROS2 implementation and parameters](https://github.com/ScepterSW/ScepterSDK/tree/2f0ba661d13ee664b20aba1f78c583f10e1d4b72/3rd-PartyPlugin/ROS2),
[older Nebula implementation](https://github.com/Vzense/NebulaSDK/tree/3decf8349aba17d3ac16ce02b337ff60e668184a).

## SICK Visionary-S: AP and CX are different interfaces

### AP (V3S142), GigE Vision ROS 2

The vendor driver requires the Visionary GigE Vision Basic App on the device.
Its namespace is `/visionary_s/cam_SERIAL`, with `rgb`, `depth`, `camera_info`
and optional `imu`. RGB and range share an image grid. The Visionary-S default
component list contains `Intensity` and `Range`. Add `ImuBasic` to enable IMU.
This is measurement data, not odometry, and the example leaves it out until
its frame, timestamps and calibration are verified for the estimator.

**The supplied profile is an export template, not direct support for raw AP
bags.** In the inspected driver, `depth` is `mono16` raw range. The point-cloud
code applies chunk coordinate scale and offset. Relabeling this as `16UC1` or
setting `depth.scale` alone does not apply that conversion. An acquisition/export
adapter must produce `depth_metric` as `32FC1` optical-axis Z in metres, using
the camera's scale, offset, invalid-value handling and optical reference. It
must also provide matching optical CameraInfo and measured TF to
`visionary_s_optical_frame`. That topic/frame are this template's **adapter
contract**, not vendor defaults. This repository does not supply that adapter.

The driver image frame is `camera_frame_SERIAL`. Its default mounting TF can
publish a fixed `map` → camera transform. Disable that (`broadcast_tf: false`)
for a moving-camera estimator, and record the required measured body/optical
static extrinsics separately. Common pixel geometry does not by itself settle
the difference between the housing reference and optical focal point.

Sources: [AP driver](https://github.com/SICKAG/sick_visionary_gev_ros2/tree/3d5fc36bf55b9c7a4860969ff67acb77a93a014a),
[image publication](https://github.com/SICKAG/sick_visionary_gev_ros2/blob/3d5fc36bf55b9c7a4860969ff67acb77a93a014a/sick_publisher/src/SICKPublisher.cpp),
[range conversion](https://github.com/SICKAG/sick_visionary_gev_ros2/blob/3d5fc36bf55b9c7a4860969ff67acb77a93a014a/sick_publisher/src/utils/PointCloudUtils.cpp).

### CX (V3S102), legacy ROS 1

The older driver publishes `/sick_visionary_s/rgba`, `z` and `camera_info`, with
frame `camera` by default. Convert the recording to ROS 2 before ingestion.
The example requires `16UC1` Z in millimetres and a measured recorded
`base_link` → optical `camera` transform. The legacy driver does not generate
a moving-camera trajectory. Verify the device's XML Z decimal exponent and
reference geometry: the driver publishes the raw Z map, so a nonstandard
scale or reference requires conversion before using this template.

Source: [legacy SICK driver](https://github.com/SICKAG/sick_visionary_ros/tree/365f28f80ad6a099f233b2a5554d9a61ff1e67ed).
