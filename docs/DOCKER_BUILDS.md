# Docker builds and validation

The three images build independently with Docker BuildKit. The existing Compose
services and Make commands are unchanged. Core remains a complete development,
test, mapping, and RViz image. GPU and preprocessing assemble runtime images
from independently cached build artifacts.

## Caching and size

- Upstream compilation is cached separately from local package installation.
  Editing a local launch/config/Python file should not rebuild upstream C++.
- Requirements and locked Python source packages determine virtual-environment
  rebuilds. Editing README, scripts, or tests does not reinstall dependencies.
- APT and pip caches persist in the Docker builder, not in the final image.
  APT cache mounts use exclusive locking and separate image/architecture IDs.
- Host UID/GID changes affect final ownership and assembly, not compilation.
- Core copies its full workspace with final ownership once. GPU copies only the
  installed workspace and inference environment. Preprocessing uses the exact
  matching ZED 5.4.1 / CUDA 12.8 / Ubuntu 24.04 runtime base and copies only the
  installed workspace and data-tools environment. Both ZED bases are digest-pinned.

Keep the BuildKit cache for fast rebuilds. Multi-stage builds can reduce final
image size while retaining substantial builder disk usage. A clean preprocessing
build also pulls both ZED bases and installs the runtime dependency set, so it
can take longer than a cached build despite producing a smaller final image.
No measured size or timing improvement is claimed until Docker validation.

ROS desktop packages, upstream feature flags, exact-SHA locks, and the qualified
GPU inference stack are preserved. Further package pruning requires separate
runtime qualification. Core's development workflow is intentionally retained.

## Validate the images

Run from the repository root on a Docker host, with `HOST_UID` and `HOST_GID`
configured as usual in `.env`:

```bash
make check-compose
BUILDKIT_PROGRESS=plain make build PROFILE=all
make test PROFILE=core
make lint PROFILE=core
```

Build-time checks verify ROS package discovery, copied install trees, inference
imports, and SDK access. GPU and preprocessing also scan installed ELF files
for unresolved shared libraries. Only explicit NVIDIA driver library names may
be missing at build time. Those are injected when GPU containers start.

With the demo models and fixture data available, run:

```bash
make check-gpu
make test-preprocess PREPROCESS_TEST_ARGS='--force'
```

`--force` reruns preprocessing even if previous outputs exist. Missing fixtures
are downloaded by the fixture runner. Include the ZED cases, not only the stable
CPU suite, and verify that SDK settings/resources remain writable as `spark`.

Run the README recorded, closed-set, and open-set mapping demos and RViz. Confirm
that each mapper saves a Spark-DSG JSON under `/home/spark/output` and validate it:

```bash
make inspect DSG=/home/spark/output/run/dsg.json \
  INSPECT_ARGS=--require-pipeline-output
```

Launch-argument and linkage checks do not exercise GPU inference, SDK decoding,
or dynamically loaded plugins. Execution of the demos is the acceptance check.

## Compare builds

Record baseline sizes/timings before replacing old image tags if available.
Measure a cold build on a separate empty builder, an unchanged rebuild, and a
rebuild after a local configuration edit separately. Keep the same machine,
platform, build arguments, and base images for comparisons. `--no-cache` alone
does not empty persistent download caches and is not a fully cold measurement.

```bash
BUILDKIT_PROGRESS=plain make build PROFILE=all
docker image ls spark-3dsg-core:local
docker image ls spark-3dsg-gpu:local
docker image ls spark-3dsg-preprocess:local
docker image history spark-3dsg-core:local
docker image history spark-3dsg-gpu:local
docker image history spark-3dsg-preprocess:local
docker system df -v
docker buildx du
```

Compare per-image sizes separately from shared layers and builder cache usage.
For a configuration-only rebuild, the log should show cached upstream compile,
APT, and Python dependency steps. Rebuilding with a different host UID/GID should
also reuse those steps. Build checks do not replace these cache/timing observations.
