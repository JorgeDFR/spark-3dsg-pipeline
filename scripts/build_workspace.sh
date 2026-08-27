#!/usr/bin/env bash
set -euo pipefail

workspace="${1:-${ROS_WS:-/home/spark/ros_ws}}"

# ROS-generated environment hooks probe optional variables such as
# AMENT_TRACE_SETUP_FILES and are not safe to source while nounset is enabled.
set +u
source /opt/ros/jazzy/setup.bash
set -u
cd "$workspace"

colcon build \
  --merge-install \
  --symlink-install \
  --event-handlers console_cohesion+ \
  --cmake-args \
    --no-warn-unused-cli \
    -DCMAKE_BUILD_TYPE=Release \
    -DCONFIG_UTILS_ENABLE_ROS=OFF \
    -DGTSAM_USE_SYSTEM_EIGEN=ON \
    -DSPARK_DSG_BUILD_EXAMPLES=OFF \
    -DSPARK_DSG_BUILD_PYTHON=ON
