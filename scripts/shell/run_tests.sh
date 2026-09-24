#!/usr/bin/env bash
set -euo pipefail

pipeline_root="${PIPELINE_ROOT:-/home/spark/spark-3dsg-pipeline}"
ros_ws="${ROS_WS:-/home/spark/ros_ws}"
cd "$pipeline_root"
colcon test --base-paths "$ros_ws/src" --packages-select spark_3dsg_pipeline --event-handlers console_cohesion+
colcon test-result --test-result-base "$ros_ws/build/spark_3dsg_pipeline" --verbose
python3 -m pytest -q tests
