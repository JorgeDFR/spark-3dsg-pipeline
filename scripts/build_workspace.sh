#!/usr/bin/env bash
set -euo pipefail

workspace="${1:-/opt/ros_ws}"
source /opt/ros/jazzy/setup.bash
cd "$workspace"

colcon build \
  --merge-install \
  --event-handlers console_cohesion+ \
  --cmake-args \
    --no-warn-unused-cli \
    -DCMAKE_BUILD_TYPE=Release \
    -DCONFIG_UTILS_ENABLE_ROS=OFF \
    -DGTSAM_USE_SYSTEM_EIGEN=ON \
    -DSPARK_DSG_BUILD_EXAMPLES=OFF \
    -DSPARK_DSG_BUILD_PYTHON=ON
