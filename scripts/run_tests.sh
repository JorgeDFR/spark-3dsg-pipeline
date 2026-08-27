#!/usr/bin/env bash
set -euo pipefail

cd /opt/spark_pipeline
colcon test --base-paths /opt/ros_ws/src --packages-select spark_dsg_pipeline --event-handlers console_cohesion+
colcon test-result --test-result-base /opt/ros_ws/build/spark_dsg_pipeline --verbose
python3 -m pytest -q tests
