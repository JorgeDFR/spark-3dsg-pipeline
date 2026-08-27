#!/usr/bin/env bash
set -e

source /opt/ros/jazzy/setup.bash
if [[ -f /home/spark/ros_ws/install/setup.bash ]]; then
  source /home/spark/ros_ws/install/setup.bash
fi
if [[ -n "${SEMANTIC_ENV:-}" && -f "${SEMANTIC_ENV}/bin/activate" ]]; then
  source "${SEMANTIC_ENV}/bin/activate"
fi

exec "$@"
