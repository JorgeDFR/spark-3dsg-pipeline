#!/usr/bin/env bash
set -euo pipefail

pipeline_root="${PIPELINE_ROOT:-/home/spark/spark-3dsg-pipeline}"
ros_ws="${ROS_WS:-/home/spark/ros_ws}"
cd "$pipeline_root"
# Source discovery does not set colcon's build/install directories. Match the
# merged workspace built into the image while keeping pytest in the repository.
colcon --log-base "$ros_ws/log" test \
  --base-paths "$ros_ws/src" \
  --build-base "$ros_ws/build" --install-base "$ros_ws/install" --merge-install \
  --packages-select spark_3dsg_pipeline --event-handlers console_cohesion+ \
  --return-code-on-test-failure
colcon test-result --test-result-base "$ros_ws/build/spark_3dsg_pipeline" --verbose
# Large example graphs are excluded from the image and supplied by Compose.
PIPELINE_EXAMPLES_DIR="${PIPELINE_EXAMPLES_DIR:-/home/spark/examples}" \
  python3 -m pytest -q tests
