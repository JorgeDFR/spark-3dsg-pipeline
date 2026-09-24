# Preprocess an RGB-D recording

Preprocessing produces a ROS 2 bag and `dataset.yaml` for the
[mapping input contract](INPUT_CONTRACT.md). Describe your camera with a
**source profile**, then select **one pose provider**. Depth must be registered
into the image camera, either by the acquisition driver or during preprocessing.

## Build the toolbox

Configure `.env` following the [README](../README.md), then run:

```bash
make build-preprocess
```

All bag processing and ROS execution run as `spark` in the optional `preprocess`
Docker service. This image currently requires Linux/amd64, an NVIDIA driver and
NVIDIA Container Toolkit, including for non-ZED recordings. It includes the ZED
SDK/wrapper, RTAB-Map odometry, OpenVINS and depth-image processing. Other camera
acquisition drivers are not bundled. See the
[locked dependencies](../dependencies/PREPROCESSING_BASELINE.md).

## Choose and adapt a source

Profiles live in
[`config/sources`](../src/spark_3dsg_preprocessing/config/sources).
See [camera profiles and driver settings](CAMERA_PROFILES.md) for topics,
frames, IMU availability and acquisition requirements for each model.

| Recording | Starting profile |
| --- | --- |
| Registered RGB-D ROS 2 bag | `generic_rgbd` |
| RGB-D with recorded odometry | `generic_rgbd_odometry` |
| Raw, unregistered depth | `generic_rgbd_unregistered` |
| ZED wrapper ROS 2 bag | `zed_rosbag`, `zed_original_rosbag` |
| ZED SVO/SVO2 | `zed2i_svo`, `zed2_svo`, `zedx_svo`, `zed_original_svo` |
| RealSense | `realsense`, `realsense_d455`, `realsense_l515`, `realsense_unregistered` |
| Vzense/Scepter | `vzense_scepter`, `vzense_ds77c_pro`, `vzense_nyx660` |
| SICK Visionary-S | `sick_visionary_s_ap` (adapted export), `sick_visionary_s_cx` |

Names are examples, not automatic device detection. Copy a profile into your
`data/custom-configs` directory and edit topic names, frames and calibration to match
the recording. Replace `SERIAL` placeholders. Each YAML is self-contained.
Copy just the file you need. Profiles are grouped under `generic/`, `zed/`,
`intel-realsense/`, `vzense/` and `sick/`. Both short names such as
`realsense_d455` and family-qualified names such as
`intel-realsense/realsense_d455` work. Preprocessing saves the source settings
and their fingerprint alongside the output.

For example, copy and edit both the source and pose-provider settings on the host:

```bash
cp src/spark_3dsg_preprocessing/config/sources/generic/generic_rgbd.yaml data/custom-configs/source.yaml
```

```bash
cp src/spark_3dsg_preprocessing/config/preprocessing/rtabmap_rgbd.yaml data/custom-configs/preprocessor.yaml
```

For an external `DATA_DIR`, use that root instead of `data`. Inspect the example
fields before editing: source configs describe recorded topics, frames and depth.
Preprocessor configs select the pose backend and its parameters. Pass the edited
files to both commands:

```bash
make validate-source INPUT=/home/spark/data/raw/session \
  SOURCE=/home/spark/data/custom-configs/source.yaml \
  PREPROCESSOR=/home/spark/data/custom-configs/preprocessor.yaml
```

```bash
make preprocess INPUT=/home/spark/data/raw/session \
  PREPROCESS_OUTPUT=/home/spark/data/normalized/session \
  SOURCE=/home/spark/data/custom-configs/source.yaml \
  PREPROCESSOR=/home/spark/data/custom-configs/preprocessor.yaml
```

The `sensor` frame must be the image camera's optical frame (X right, Y down,
Z forward). `robot` is the tracked body frame. Record the measured static TF
between them. A changed frame name is not a substitute for an extrinsic
transform. Cameras with an IMU do not necessarily provide odometry.

For `depth.mode: registered`, depth pixels must already use color-image
geometry. For `register`, supply both CameraInfo streams and a recorded static
TF path from the depth optical frame to the image optical frame. Offline
projection assumes rectified camera geometry. Use `16UC1` millimetres
(`scale: 1000.0`) or `32FC1` metres (`scale: 1.0`). The scale field does not
perform arbitrary raw-unit conversion in the relay. Convert proprietary
range encodings, scale/offset and coordinate conventions before ingestion.

## Select the pose provider

| Preprocessor | Required input |
| --- | --- |
| `passthrough` | Recorded TF connecting odom → robot → sensor |
| `recorded_odometry` | `nav_msgs/Odometry` plus sensor extrinsics |
| `rtabmap_rgbd` | RGB-D, CameraInfo and sensor extrinsics |
| `openvins_mono` / `openvins_stereo` | Image(s), IMU, calibrated camera/IMU rig |
| `zed_tracking` | ZED SVO/SVO2 |

Passthrough and recorded odometry rewrite ROS 2 bags offline, including depth
registration when requested. RTAB-Map runs RGB-D odometry, not mapping.
RTAB-Map/OpenVINS use ROS playback and `depth_image_proc` for registration.
Only the selected provider writes the odom → robot trajectory.

OpenVINS profiles expect `/home/spark/data/calibration/openvins/estimator_config.yaml`.
Supply your estimator YAML and its referenced camera/IMU calibration files:
intrinsics, extrinsics, time offsets and noise parameters must match your rig.
Having an IMU topic alone does not make a sensor calibrated for VIO. The toolbox
includes ROS 2 camera calibration for intrinsics. It does not include Kalibr.

## ROS 1 bags

Convert ROS 1 storage to ROS 2 in the toolbox before running `validate-source`
or `preprocess`. Keep the converted bag in `raw`: conversion preserves the
recorded topics and does not generate missing odometry or register depth.
The destination must not already exist.

```bash
docker compose --profile preprocess run --rm preprocess \
  rosbags-convert --src /home/spark/data/raw/session.bag \
  --dst /home/spark/data/raw/session_ros2
```

Adapt a ROS 2 source example to the converted topics and frames, then use
`INPUT=/home/spark/data/raw/session_ros2` in the validation and preprocessing
commands below. Conversion cannot supply measurements absent from the recording.

## Validate and preprocess

`${DATA_DIR:-./data}` is mounted at `/home/spark/data`. Commands accept a supplied
profile name or a container-visible YAML path. The destination must not exist.

```bash
make validate-source \
  INPUT=/home/spark/data/raw/session \
  SOURCE=realsense_d455 PREPROCESSOR=rtabmap_rgbd
```

```bash
make preprocess \
  INPUT=/home/spark/data/raw/session \
  PREPROCESS_OUTPUT=/home/spark/data/normalized/session \
  SOURCE=realsense_d455 PREPROCESSOR=rtabmap_rgbd
```

`validate-source` checks input requirements. It does not execute an estimator.
`preprocess` validates the input, creates a temporary bag, checks the normalized
contract, then publishes the destination. Failed temporary outputs and logs are
retained for diagnosis.

For SVO playback specify a capture duration:

```bash
make preprocess \
  INPUT=/home/spark/data/raw/session.svo2 \
  PREPROCESS_OUTPUT=/home/spark/data/normalized/session \
  SOURCE=zed2i_svo PREPROCESSOR=zed_tracking \
  PREPROCESS_ARGS='--duration 120 --startup-timeout 300'
```

Duration starts after normalized color, depth and CameraInfo arrive. The
startup timeout allows SDK initialization and initial model downloads.

### Older SVO recordings

`zed.legacy_svo: true` selects visual-only GEN_1 tracking, disables IMU fusion
and gravity initialization, and uses image-synchronized reads without publishing
IMU. `zed_original_svo` enables it because the original ZED has no IMU.
`zed2_legacy_svo` demonstrates the same setting for older ZED 2 recordings.
Do not infer this setting from the camera generation or file suffix alone:
it depends on usable sensor data and SDK playback compatibility. SVO2 supports
high-frequency sensor recording where the camera provides it. Renaming or
converting a file cannot create missing IMU measurements.

When RTAB-Map or OpenVINS provides pose for SVO, preprocessing disables SDK
positional tracking and depth stabilization to avoid running a second tracker.
The obsolete duplicate `zed_svo` source name is removed. Use `zed2i_svo` for
its previous behavior. `zed_svo` remains the YAML **input kind**.

## Use the result for mapping

Outputs include the bag, `dataset.yaml`, resolved `source.yaml`,
`preprocessing.yaml`, dependency lock, `preprocessing_manifest.yaml`,
`validation.txt` and process logs. The manifest fingerprints inputs and configs.

```bash
make run PROFILE=gpu \
  BAG=/home/spark/data/normalized/session \
  DATASET=/home/spark/data/normalized/session/dataset.yaml \
  MAPPING=closed_set
```

## Troubleshooting

Repository scripts, packages, example profiles and test fixtures are baked into
the image. Rebuild after changing them. Custom profiles under
`data/custom-configs` are read through the data mount and need no rebuild.
For SDK errors, inspect the full
launch log: the image exposes `/usr/local/zed/lib` and checks SDK permissions
as `spark`. Running `ldconfig` or the service as root at startup is unnecessary.
Missing CUDA/video driver libraries require working NVIDIA container injection.

The SDK needs serial-specific calibration and may download neural models.
Writable `zed-settings` and `zed-resources` Docker volumes persist these caches.
First use needs network access. A missing calibration prevents image output.
See [Stereolabs cache guidance](https://support.stereolabs.com/articles/3140266139-how-can-i-use-the-zed-with-docker-on-a-robot-with-no-internet-connection).

For TF errors, inspect the recording's actual frame names and transforms.
ZED examples use `zed_left_camera_frame_optical`. Do not add identity transforms
to hide mismatched optical/body frames or disconnected trees.

## Optional toolbox tests

`make test-preprocess` downloads about 1.25 GiB: ZED2 Lake SVO, UoSM ZED2i
SVO2, D435i run009 and TUM Freiburg 1 xyz. It exercises all pose providers and
both registration paths. Data lives in `data/raw/test-preprocess`. Reports and logs
live in `data/normalized/test-preprocess` (under `DATA_DIR` if customized).
This is a standalone developer check, not a mapping pipeline step. See the
[test fixture guide](../tests/fixtures/preprocessing/README.md) for cases,
licenses, cached-data migration and rerun options.
