# Changelog

## Unreleased

- Add one optional ZED SDK preprocessing toolbox image with exact-SHA RTAB-Map,
  experimental OpenVINS, ZED tracking, depth registration, normalized bag
  materialization, provenance, source profiles, and corrected odometry TF
  validation.
- Base the preprocessing toolbox directly on the pinned ZED development image
  so build and runtime use the same SDK installation without a second stage.
- Add a compact public-data validation manifest and Docker-orchestrated
  downloader, ROS 1 conversion, backend execution, output validation, and
  resumable per-case workflow for ZED2, ZED2i, D435i, and TUM RGB-D data.
- Materialize ROS-bag topic/frame rewrites, recorded odometry, existing TF, and
  rectified depth registration directly with `rosbags`, avoiding ROS playback
  and recording for deterministic preprocessing steps.
- Derive the D435i validation frame model from its recorded TF: use
  `camera_link` as the sensor-tree root, leave the unrelated MAVROS `base_link`
  disconnected, recognize depth/infra1 as already registered, and attach the
  OpenVINS bridge only at `camera_link`.
- Reuse the preprocessing image for validation data preparation without an
  implicit image build, and create missing ROS 2 conversion directories before
  checking their free space.
- Fix ZED SDK runtime-library discovery, normalize leading-slash sensor frame
  IDs before RTAB-Map, select backend-specific D435i extrinsics, bound RGB-D
  approximate synchronization, use the camera pose for handheld D435i visual
  odometry, and keep optional map/odom absence informational.
- Add an image revision and GPU-container runtime preflight so validation
  reports a stale preprocessing image or unloadable ZED component before
  starting any cases.
- Standardize data into `raw` and `normalized`: keep validation downloads
  and storage-only conversions under `raw/validation`, put Spot and
  uHumans2 directly under `normalized`, and group final validation outputs
  under `normalized/validation`.
- Invoke bind-mounted Python tools through `python3` so host executable-bit
  differences cannot break Docker preparation or validation commands.
- Use one GPU-enabled Compose preprocessing service with a read/write mount of
  the complete data root, complete the D435i validation TF tree, and harden
  RTAB-Map replay startup and dependency failure handling.
- Build the GPU image in separate CUDA development and runtime stages, retain
  only TensorRT runtime libraries and installed artifacts, and avoid the
  multi-gigabyte recursive-ownership layer.
- Install the exact-SHA Ultralytics CLIP dependency during the GPU build and
  exercise YOLOE text prompt encoding in the GPU smoke test.
- Keep independently buildable core and GPU images, with the GPU build based
  directly on CUDA 12.8.1/Ubuntu 24.04 for Blackwell support.
- Keep source and build tooling in the core image, reuse it for CPU, tests, and
  RViz, and retain bind-mounted integration-resource development in both images.
- Separate bag-specific dataset adapters from reusable recorded, closed-set,
  and open-set mapping recipes, with fail-fast compatibility checks.
- Rebuild `classic.yaml` as hierarchical Hydra reconstruction with online
  closed-set semantics and externalize uHumans2 taxonomy/remapping.
- Split YOLOE model settings from replaceable ADT4 prompts and add independent
  closed-set/open-set perception launches.
- Add hierarchical and Khronos renderer profiles plus native saved-DSG JSON
  visualization.
- Export both compact and mesh-bearing DSG JSONs, warn on mesh-free offline
  visualization, and add two mesh-bearing reference scene graphs.
- Define `v1` solely as the immutable exact-SHA upstream snapshot, rename the
  output acceptance flag, and remove unavailable pipeline placeholders.
- Add Docker-first core and GPU profiles.
- Add exact public dependency locks and upstream provenance.
- Add the `spark_3dsg_pipeline` ROS 2 integration package and dataset adapters.
- Add model download, bag validation, deterministic run output, and DSG inspection tools.
- Run containers with a host-matched non-root UID and GID.
- Add automatic preparation of the public Spot and uHumans2 example bags.
- Rename the integration package to `spark_3dsg_pipeline` and move it to the
  repository-level `src/` directory.
- Bind-mount the integration package into a symlink-installed container
  workspace so launch and configuration edits do not require image rebuilds.
- Wait for the configured TF paths during bag validation instead of stopping
  after an arbitrary initial set of transforms.
- Isolate Hydra and perception launch arguments and resolve package resources
  through the ament package share instead of assuming an install layout.
- Delay bag playback until Hydra creates its camera input subscription and retain
  all static-transform batches for late DDS discovery.
- Pass all dataset topic remaps through one rosbag2 `--remap` option so RGB,
  depth, and CameraInfo are normalized together.
- Make `bag.launch.yaml` and `visualization.launch.yaml` the canonical playback
  and RViz entry points, including dataset TF remaps and fixed-frame selection.
- Configure RViz displays for the DSG mesh, graph markers, and agent trajectory,
  and syntax-check every installed launch file.
- Remove the unused no-op Docker entrypoint and use the repository dependency
  bootstrap script as the single `vcstool` import implementation.
