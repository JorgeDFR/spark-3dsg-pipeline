# Preprocessing dependency baseline

The preprocessing image is an optional toolbox and does not change the mapping
snapshot in `locks/v1.lock.repos`. Its upstream source is locked independently
in `locks/preprocess.lock.repos`.

The single build/runtime image uses the immutable ZED SDK 5.4.1 base
`stereolabs/zed:5.4.1-devel-cuda12.8-ubuntu24.04` at
`sha256:c12a20237f55958e878853d1e112927de71f7756433e5dec7078e5f6885fbb60`.
There is no separate runtime stage. The image registers `/usr/local/zed/lib`
with `ldconfig` and includes it in runtime `LD_LIBRARY_PATH` for unversioned
SDK library lookups. SDK files/directories are made readable/traversable during
image construction, with a final library-read check as the runtime `spark` user.
Only SDK `settings` and `resources` caches are spark-owned and writable. Compose
persists them in named volumes for calibration and model downloads.
NVIDIA driver libraries are injected at container runtime.

The source lock contains ZED ROS 2 wrapper 5.4.1, RTAB-Map's Jazzy branches,
and the exact head of upstream OpenVINS Jazzy support pull request
[#500](https://github.com/rpng/open_vins/pull/500). The
commit is fetched from the pull-request author's public fork because GitHub's
pull-request ref is not part of a normal clone. OpenVINS is exposed as an
experimental backend because this is not yet a released upstream compatibility
promise. The image proves that the locked source builds. Promotion additionally
requires sensor-specific timing and calibration validation. Replace the
fork URL and revision with the released upstream commit when the pull request
is merged.

RTAB-Map is built as an RGB-D odometry dependency only. Its desktop app and
direct ZED/ZED Open Capture drivers are disabled. Its Qt-backed `gui` library
is retained because the upstream `rtabmap_util` ROS package requires that CMake
component even for headless odometry. ZED acquisition and SDK tracking remain
provided by the separately locked `zed_wrapper`. Disabling the duplicate
RTAB-Map camera driver also avoids build-time linkage against the host-only
CUDA driver library.

Original Kalibr is intentionally absent. It requires a ROS 1 bag/toolchain and
cannot share the Jazzy dependency environment safely. The first calibration
contract accepts existing estimator YAML and factory calibration. A future
ROS-2-native calibration tool must receive its own exact-SHA lock entry and
feature-parity validation before it enters this image.

The legacy Lake SVO validation source opts into `GEN_1` visual-only tracking
without IMU fusion. The SVO2 validation source keeps the SDK defaults. ZED
acquisition for external pose estimators disables both SDK tracking and depth
stabilization. The integration passes these through the locked wrapper's inline
`param_overrides` launch argument. See the pinned
[parameter definitions](https://github.com/stereolabs/zed-ros2-wrapper/blob/86171bccda22de6e83ccc69b3c0e67af99dece7c/zed_wrapper/config/common_stereo.yaml).
