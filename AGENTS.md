# Project rules

## Purpose

This repository integrates public MIT-SPARK software to create 3D Dynamic Scene Graphs. It does not implement its own SLAM, TSDF, tracking, or DSG framework.

## Environment

Compilation, ROS execution, integration tests, and runtime dependency installation must happen inside Docker. Repository-only Python tests may also be validated in an ignored local `.venv`. Do not instruct users to install ROS, CUDA libraries, Python runtime dependencies, CMake packages, or colcon dependencies on the host. Host requirements are limited to Docker and, for GPU execution, an NVIDIA driver plus NVIDIA Container Toolkit.

Runtime containers must default to the non-root `spark` user created from `HOST_UID` and `HOST_GID`. Root is limited to image-build steps and explicit maintenance operations.

## Upstream source policy

- Do not modify vendored or imported upstream projects directly.
- Fetch dependencies with vcstool over HTTPS.
- Builds must use exact SHA locks from `dependencies/locks/`.
- Never put `main`, `master`, `develop`, or another floating ref in a lock file.
- The v1 dependency lock uses a Hydra public monorepo snapshot that already contains the
  `hydra_ros` packages. Do not also import the split Hydra-ROS repository into
  that workspace. Migrate the entire compatible dependency set together.
- Prefer launch/configuration composition over upstream source changes.
- Any unavoidable upstream change must be an explicit patch under `patches/`, with its reason, applicable upstream commit, upstream issue/PR, and removal condition documented.

## Scope

The v1 name refers only to the immutable exact-SHA dependency snapshot in
`dependencies/locks/v1.lock.repos`. It does not identify a graph topology or
validation mode. Required upstreams are Hydra/Hydra-ROS, Khronos, Spark-DSG,
and semantic_inference.

## Testing and outputs

Every change must leave the Docker definitions buildable, tests passing, README commands accurate, and model/bag files untracked. A successful mapping run must produce a Spark-DSG JSON file under `/home/spark/output`.
