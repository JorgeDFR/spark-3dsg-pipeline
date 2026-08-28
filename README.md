# spark-3dsg-pipeline

An unofficial, reproducible integration environment for constructing 3D Dynamic Scene Graphs with public MIT-SPARK software. This repository owns Docker images, exact dependency locks, ROS 2 launch composition, dataset adapters, validation, output handling, and tests. Hydra, Khronos, Spark-DSG, and semantic inference remain upstream projects.

The v1 pipeline is headless by default:

```text
RGB-D + TF/odometry -> YOLOE or recorded instances -> Khronos/Hydra -> Spark-DSG
                                                                      |
                                           dsg.json + mesh.ply + metadata.json
```

## Status

The repository provides the Docker/ROS integration and CPU-testable tooling. A full Spot run requires an NVIDIA GPU, external YOLOE weights, and the public Spot bag; those assets are deliberately not committed. DAAAM is documented as a follow-on profile and is not part of the v1 dependency set.

## Host requirements

- Linux, Git, GNU Make, Docker Engine, and Docker Compose v2
- For `PROFILE=gpu`: an NVIDIA driver and NVIDIA Container Toolkit

Do not install ROS, CUDA Toolkit, colcon, GTSAM, or Python ML packages on the host.

## Example ROS bags

Download and preparation instructions for the public Spot and uHumans2 examples are maintained in [data/README.md](data/README.md). Prepare an example before following the quick start below.

## Quick start

```bash
cp .env.example .env
make build PROFILE=gpu
make models PROFILE=gpu
make validate-bag PROFILE=gpu BAG=/home/spark/data/spot
make run PROFILE=gpu BAG=/home/spark/data/spot
make inspect DSG=/home/spark/output/<run-id>/dsg.json
```

`BAG` and `DSG` are container paths. The defaults mount `./data` read-only at `/home/spark/data`, `./models` at `/home/spark/models`, `./output` at `/home/spark/output`, and the persistent cache volume at `/home/spark/.cache`. The project is installed at `/home/spark/spark-3dsg-pipeline`; the image's internal upstream workspace is `/home/spark/ros_ws`. Change the host-side paths in `.env` for external storage.

Containers run as the non-root `spark` user. Its UID and GID are set at image build time from `HOST_UID` and `HOST_GID` in `.env`, so files written under the bind-mounted model and output directories belong to the host user. The example values are `1000`; if your account differs, use `id -u` and `id -g` to set the correct values before building. Rebuild the images after changing either value.

## Editing the integration package

The repository-owned ROS package is [src/spark_3dsg_pipeline](src/spark_3dsg_pipeline); the repository itself does not imitate a complete ROS workspace. Compose mounts this package at `/home/spark/ros_ws/src/spark_3dsg_pipeline` over the copy used during the image build. The workspace is built with `colcon --symlink-install`, so edits to existing launch, configuration, and RViz files are visible in newly started containers without rebuilding the image. Rebuild after changing `package.xml`, `CMakeLists.txt`, or compiled dependencies.

Every run creates `/home/spark/output/<UTC timestamp>-<dataset>/`. The run wrapper records the resolved dataset configuration, upstream lock hash, command, and logs. Hydra/Khronos are asked to stop when simulated time ends; the wrapper then normalizes upstream output names to the output contract where possible and fails if no DSG JSON was produced.

## Commands

Run `make help` for the complete interface. Common commands are:

```bash
make build PROFILE=core|gpu
make models PROFILE=gpu
make prepare-data
make shell PROFILE=core|gpu
make validate-bag PROFILE=gpu DATASET=spot BAG=/home/spark/data/spot
make run PROFILE=gpu DATASET=spot BAG=/home/spark/data/spot
make inspect DSG=/home/spark/output/run/dsg.json
make test
make lint
```

RViz is optional and requires host display forwarding:

```bash
make rviz PROFILE=gpu DATASET=spot
```

The visualization command resolves the adapter's map frame, starts the Hydra
streaming visualizer, and then starts RViz with the DSG mesh, graph-marker, and
agent-trajectory displays. Run it while the headless pipeline is active.

## Inputs and outputs

The normalized interface and frame requirements are in [docs/INPUT_CONTRACT.md](docs/INPUT_CONTRACT.md). Add a robot by creating one dataset YAML file; do not fork the core launch. See [docs/CUSTOM_SENSOR.md](docs/CUSTOM_SENSOR.md).

The graph inspection command supports human-readable and machine-readable output:

```bash
make inspect DSG=/home/spark/output/run/dsg.json
make inspect DSG=/home/spark/output/run/dsg.json INSPECT_ARGS=--json
```

The three supported graph profiles (`adt4.yaml`, `classic.yaml`, and
`uhumans2.yaml`) and their tuning surfaces are described in
[docs/HYDRA_CONFIG_REFERENCE.md](docs/HYDRA_CONFIG_REFERENCE.md). See also
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
[docs/DATASETS.md](docs/DATASETS.md), and
[docs/DEBUGGING.md](docs/DEBUGGING.md) before running a large bag.

## Reproducibility

Docker builds import [dependencies/locks/adt4.lock.repos](dependencies/locks/adt4.lock.repos), which contains exact commit SHAs and only HTTPS URLs. [dependencies/adt4-public.repos](dependencies/adt4-public.repos) is the human-updatable branch manifest and is never consumed by an image build. The architectural reference point and the Hydra/Hydra-ROS monorepo transition are recorded in [dependencies/UPSTREAM_BASELINE.md](dependencies/UPSTREAM_BASELINE.md).

This project is not affiliated with or endorsed by MIT or MIT-SPARK. Upstream projects and model weights retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
