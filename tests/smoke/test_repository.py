from pathlib import Path
import hashlib
import re

import yaml


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src/spark_3dsg_pipeline"


def assert_yaml_has_unique_keys(path: Path) -> None:
    def visit(node):
        if isinstance(node, yaml.MappingNode):
            keys = set()
            for key, value in node.value:
                assert isinstance(key, yaml.ScalarNode), f"{path}: non-scalar key"
                assert key.value not in keys, f"{path}: duplicate key {key.value!r}"
                keys.add(key.value)
                visit(value)
        elif isinstance(node, yaml.SequenceNode):
            for value in node.value:
                visit(value)

    visit(yaml.compose(path.read_text(encoding="utf-8")))


def load(relative: str):
    path = PACKAGE / relative
    assert_yaml_has_unique_keys(path)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_all_yaml_and_repo_manifests_parse_with_unique_keys():
    for path in sorted(ROOT.rglob("*.yaml")) + sorted(ROOT.rglob("*.repos")):
        relative = path.relative_to(ROOT)
        if any(part in {".git", ".venv"} for part in relative.parts) or (
            relative.parts and relative.parts[0] in {"data", "models", "output"}
        ):
            continue
        assert_yaml_has_unique_keys(path)
        yaml.safe_load(path.read_text(encoding="utf-8"))


def test_v1_lock_is_exact_https_and_consumed_by_build():
    lock_path = ROOT / "dependencies/locks/v1.lock.repos"
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    sha = re.compile(r"^[0-9a-f]{40}$")
    assert {"hydra", "khronos", "spark_dsg", "semantic_inference"}.issubset(
        lock["repositories"]
    )
    for entry in lock["repositories"].values():
        assert entry["url"].startswith("https://")
        assert sha.fullmatch(entry["version"])
    dockerfile = (ROOT / "docker/Dockerfile.core").read_text(encoding="utf-8")
    assert "dependencies/locks/v1.lock.repos" in dockerfile
    assert "adt4.lock.repos" not in dockerfile


def test_gpu_source_lock_is_exact_and_consumed_by_gpu_build():
    lock_path = ROOT / "dependencies/locks/gpu.lock.repos"
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    entry = lock["repositories"]["ultralytics_clip"]
    assert entry["url"] == "https://github.com/ultralytics/CLIP.git"
    assert re.fullmatch(r"[0-9a-f]{40}", entry["version"])

    gpu = (ROOT / "docker/Dockerfile.gpu").read_text(encoding="utf-8")
    assert "dependencies/locks/gpu.lock.repos" in gpu
    assert "/tmp/bootstrap_dependencies.sh ${ROS_WS}/src /tmp/gpu.lock.repos" in gpu
    assert "${ROS_WS}/src/ultralytics_clip" in gpu


def test_preprocessing_lock_is_exact_and_consumed_by_single_image():
    lock_path = ROOT / "dependencies/locks/preprocess.lock.repos"
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    assert {
        "open_vins",
        "rtabmap",
        "rtabmap_ros",
        "zed_ros2_description",
        "zed_ros2_interfaces",
        "zed_ros2_wrapper",
    } == set(lock["repositories"])
    for entry in lock["repositories"].values():
        assert entry["url"].startswith("https://")
        assert re.fullmatch(r"[0-9a-f]{40}", entry["version"])

    dockerfile = (ROOT / "docker/Dockerfile.preprocess").read_text(
        encoding="utf-8"
    )
    assert "dependencies/locks/preprocess.lock.repos" in dockerfile
    assert "stereolabs/zed:5.4.1-devel-cuda12.8-ubuntu24.04@sha256:" in dockerfile
    assert "-DBUILD_APP=OFF" in dockerfile
    assert "-DWITH_QT=OFF" not in dockerfile
    assert "-DWITH_ZED=OFF" in dockerfile
    assert "-DWITH_ZEDOC=OFF" in dockerfile
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    assert compose["services"]["preprocess"]["image"] == "spark-3dsg-preprocess:local"
    assert compose["services"]["preprocess"]["gpus"] == "all"
    assert (
        compose["services"]["preprocess"]["environment"][
            "NVIDIA_DRIVER_CAPABILITIES"
        ]
        == "all"
    )
    assert [
        name
        for name, service in compose["services"].items()
        if service.get("image") == "spark-3dsg-preprocess:local"
    ] == ["preprocess"]
    data_mounts = [
        volume
        for volume in compose["services"]["preprocess"]["volumes"]
        if "/home/spark/data" in volume
    ]
    assert data_mounts == ["${DATA_DIR:-./data}:/home/spark/data"]
    assert "rosbags-convert --help" in dockerfile
    assert dockerfile.count("ros2 pkg prefix rtabmap_sync") == 2
    assert not {
        "preprocess-generic",
        "preprocess-zed",
        "preprocess-openvins",
        "preprocess-gpu",
        "preprocess-data-setup",
    }.intersection(compose["services"])


def test_preprocessing_dataset_manifest_is_small_exact_and_https():
    path = ROOT / "tests/fixtures/preprocessing/datasets.yaml"
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert manifest["version"] == 2
    datasets = manifest["datasets"]
    assert {
        "zed2_lake_h265",
        "uosm_zed2i_svo2",
        "d435i_run009",
        "tum_fr1_xyz",
    } == set(datasets)
    assert sum(entry["bytes"] for entry in datasets.values()) < 2 * 2**30
    for entry in datasets.values():
        assert entry["url"].startswith("https://")
        assert entry["bytes"] > 0
        assert Path(entry["relative_path"]).parts[0] == "raw"
        if "converted_path" in entry:
            assert Path(entry["converted_path"]).parts[:2] == (
                "raw",
                "test-preprocess",
            )
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "prepare-preprocess-data:" in makefile
    assert "test-preprocess:" in makefile
    preprocessing_target = makefile.split(
        "prepare-preprocess-data: ##", 1
    )[1].split("test-preprocess: ##", 1)[0]
    assert "preprocess" in preprocessing_target
    assert "--build" not in preprocessing_target


def test_data_root_has_raw_and_normalized_directories():
    data = ROOT / "data"
    assert {path.name for path in data.iterdir() if path.is_dir()} == {
        "raw",
        "normalized",
        "custom-configs",
    }
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    environment = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "NORMALIZED_DATA_DIR" not in compose + environment
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    for path in (
        "data/raw/.gitkeep",
        "data/normalized/.gitkeep",
        "data/custom-configs/.gitkeep",
    ):
        assert f"!{path}" in dockerignore


def test_preprocessing_package_is_integration_glue_only():
    package = ROOT / "src/spark_3dsg_preprocessing"
    setup = (package / "setup.py").read_text(encoding="utf-8")
    launch = (package / "launch/preprocess.launch.py").read_text(encoding="utf-8")
    assert "rgbd_relay" in setup
    assert "odometry_to_tf" in setup
    assert 'package="rtabmap_odom"' in launch
    assert 'package="ov_msckf"' in launch
    assert 'get_package_share_directory("zed_wrapper")' in launch
    assert not list(package.rglob("*.cpp"))


def test_hierarchical_configs_have_full_classic_hierarchy():
    for name in ("classic", "uhumans2"):
        config = load(f"config/hydra/{name}.yaml")
        assert config["active_window"]["type"] == "ReconstructionModule"
        assert config["input"]["inputs"]["camera"]["receiver"]["type"] == "ClosedSetImageReceiver"
        assert config["frontend"]["enable_mesh_objects"] is True
        assert config["frontend"]["surface_places"]["type"] == "place_2d"
        assert config["frontend"]["freespace_places"]["type"] == "gvd"
        functors = config["backend"]["update_functors"]
        expected = {
            "objects": "UpdateObjectsFunctor",
            "surface_places": "Update2dPlacesFunctor",
            "places": "UpdatePlacesFunctor",
            "rooms": "UpdateRoomsFunctor",
            "buildings": "UpdateBuildingsFunctor",
        }
        assert {key: functors[key]["type"] for key in expected} == expected
        assert "graph_connector" not in config["frontend"]
        assert "paths" not in config


def test_classic_is_online_closed_set_and_taxonomy_is_an_overlay():
    classic = load("config/hydra/classic.yaml")
    assert classic["active_window"]["volumetric_map"]["with_semantics"] is True
    assert "labelspace" not in classic
    assert "semantic_label_remap_filepath" not in classic
    uhumans = load("config/hydra/uhumans2.yaml")
    assert "labelspace" not in uhumans
    labels = load("config/labelspaces/uhumans2_office.yaml")
    assert labels["type"] == "from_config"
    assert labels["label_names"]
    pipeline = (PACKAGE / "launch/pipeline.launch.yaml").read_text()
    assert "$(var labelspace_config_path)@labelspace" in pipeline


def test_adt4_is_khronos_object_mesh_place_graph():
    config = load("config/hydra/adt4.yaml")
    assert config["paths"] == ["khronos", "khronos_ros"]
    assert config["active_window"]["type"] == "ActiveWindow"
    assert config["input"]["inputs"]["camera"]["receiver"]["type"] == "InstanceImageReceiver"
    assert config["frontend"]["traversability_places"]["layer"] == "MESH_PLACES"
    connector = config["frontend"]["graph_connector"]["layers"]
    assert connector == [
        {"parent_layer": "MESH_PLACES", "child_layers": [{"layer": "OBJECTS"}]}
    ]
    assert "freespace_places" not in config["frontend"]
    assert not {"places", "rooms", "buildings"}.intersection(
        config["backend"]["update_functors"]
    )


def test_perception_modes_are_separate_and_use_normalized_topic():
    pipeline = (PACKAGE / "launch/pipeline.launch.yaml").read_text(encoding="utf-8")
    closed = (PACKAGE / "launch/perception_closed_set.launch.yaml").read_text(
        encoding="utf-8"
    )
    opened = (PACKAGE / "launch/perception_open_set.launch.yaml").read_text(
        encoding="utf-8"
    )
    assert "start_closed_set" in pipeline and "start_open_set" in pipeline
    assert "perception_closed_set.launch.yaml" in pipeline
    assert "perception_open_set.launch.yaml" in pipeline
    assert "closed_set_node" in closed
    assert "model_config_path" in closed and "grouping_config_path" in closed
    assert "instance_segmentation.launch.yaml" in opened
    assert "/input/semantic/image_raw" in closed
    assert "/input/semantic/image_raw" in opened
    assert "/input/semantic/instances" not in pipeline + closed + opened


def test_yoloe_model_settings_and_adt4_labels_are_independent():
    generic = load("config/perception/yoloe.yaml")
    labels = load("config/perception/labels/adt4.yaml")
    assert "text_prompt" not in generic["model"]["instance_model"]
    assert labels["model"]["instance_model"]["text_prompt"]
    mapping = load("config/mappings/open_set.yaml")
    assert mapping["semantics"]["labels_config"].endswith("labels/adt4.yaml")
    assert "adt4.yaml" not in (PACKAGE / "config/perception/yoloe.yaml").read_text()
    runner = (ROOT / "scripts/shell/run_pipeline.sh").read_text(encoding="utf-8")
    assert "--labels-config" in runner
    assert "merge_yaml.py" in runner


def test_all_referenced_package_local_files_exist():
    for mapping_path in (PACKAGE / "config/mappings").glob("*.yaml"):
        mapping = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
        assert (PACKAGE / "config/hydra" / mapping["hydra_config"]).is_file()
        for value in mapping["semantics"].values():
            if isinstance(value, str) and value.startswith("spark_3dsg_pipeline:"):
                relative = value.split(":", 1)[1]
                assert (PACKAGE / relative).is_file(), f"{mapping_path}: {relative}"
        profile = mapping["visualization"]["profile"]
        assert (PACKAGE / "config/visualization" / f"{profile}.yaml").is_file()


def test_datasets_do_not_select_mapping_or_semantics():
    forbidden = {"scene_structure", "semantics", "visualization", "hydra_config"}
    for dataset_path in (PACKAGE / "config/datasets").glob("*.yaml"):
        dataset = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
        assert not forbidden.intersection(dataset), dataset_path


def test_exactly_two_structure_specific_visualizer_configs():
    config_dir = PACKAGE / "config/visualization"
    assert sorted(path.name for path in config_dir.glob("*.yaml")) == [
        "hierarchical.yaml",
        "khronos.yaml",
    ]
    hierarchical = load("config/visualization/hierarchical.yaml")
    khronos = load("config/visualization/khronos.yaml")
    assert {str(key) for key in hierarchical["renderer"]["layers"]}.issuperset(
        {"2", "3", "4", "5", "2p*", "3p1"}
    )
    assert {str(key) for key in khronos["renderer"]["layers"]} == {
        "2",
        "2p*",
        "3p1",
        "3p2",
    }
    assert "khronos_objects" not in hierarchical["plugins"]
    assert "khronos_objects" in khronos["plugins"]
    assert not {"3", "4", "5"}.intersection(
        {str(key) for key in khronos["renderer"]["layers"]}
    )
    edges = hierarchical["renderer"]["interlayer_edges"]
    assert any(edge["from"] == 3 and edge["to"] == 2 for edge in edges)
    assert not any(edge["from"] == "3*" and edge["to"] == 2 for edge in edges)


def test_visualization_supports_live_and_native_json_file_modes():
    launch = (PACKAGE / "launch/visualization.launch.yaml").read_text(
        encoding="utf-8"
    )
    wrapper = (ROOT / "scripts/shell/run_visualization.sh").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "streaming_visualizer.launch.yaml" in launch
    assert "GraphFromFile" in launch
    assert "file_mode" in launch
    assert "DSG JSON not found" in wrapper
    assert "invalid DSG JSON" in wrapper
    assert "VISUALIZATION_PROFILE" in makefile and "DSG ?=" in makefile


def test_runtime_paths_use_installed_package_shares():
    pipeline = (PACKAGE / "launch/pipeline.launch.yaml").read_text(encoding="utf-8")
    visualization = (PACKAGE / "launch/visualization.launch.yaml").read_text(
        encoding="utf-8"
    )
    assert "/home/spark/ros_ws/src" not in pipeline + visualization
    assert "$(find-pkg-share spark_3dsg_pipeline)" in pipeline
    assert "$(find-pkg-share spark_3dsg_pipeline)" in visualization


def test_no_removed_pipeline_references_or_files_remain():
    removed_name = "d" + "aaam"
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(
            part in {".git", ".venv", ".pytest_cache", "data", "models", "output"}
            for part in path.parts
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue
        assert removed_name not in text, path


def test_v1_is_only_dependency_snapshot_terminology():
    forbidden = (
        "require-" + "v1",
        "spot " + "v1",
        "runnable " + "v1",
        "v1 " + "semantic",
    )
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(
            part in {".git", ".venv", ".pytest_cache", "data", "models", "output"}
            for part in path.parts
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue
        for phrase in forbidden:
            assert phrase not in text, f"{path}: misleading version terminology"


def test_output_metadata_records_version_and_lock_hash():
    runner = (ROOT / "scripts/shell/run_pipeline.sh").read_text(encoding="utf-8")
    assert '"pipeline_version": "v1"' in runner
    assert '"dependency_lock_hash"' in runner
    assert '"mapping": os.environ["PIPELINE_MAPPING"]' in runner
    assert 'cp "$mapping_config_path" "$run_dir/mapping.yaml"' in runner
    assert 'run_dir / "v1.lock.repos"' in runner
    assert '"dsg_with_mesh": "dsg_with_mesh.json"' in runner


def test_mesh_bearing_example_graphs_are_tracked_outside_docker_context():
    expected = {
        "mit_courtyard_ade20k_full_dsg_with_mesh.json":
            "cf00e8fc98ab3b0c616aba5fc12e347da8ffe8c9dcda58b162718f37970564ad",
        "uhumans2_office_ade20k_full_dsg_with_mesh.json":
            "25aa1328301bbd2abddb86275e152b5404fa0ee53912839018febbffbd45fb7e",
    }
    example_dir = ROOT / "examples/dsg"
    for name, checksum in expected.items():
        path = example_dir / name
        assert path.is_file()
        with path.open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == checksum
    assert "examples/dsg/*.json" in (ROOT / ".dockerignore").read_text()
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())
    assert "./examples:/home/spark/examples:ro" in compose["x-common"]["volumes"]


def test_non_root_runtime_and_artifact_ignores_remain():
    core = (ROOT / "docker/Dockerfile.core").read_text(encoding="utf-8")
    gpu = (ROOT / "docker/Dockerfile.gpu").read_text(encoding="utf-8")
    assert "USER spark" in core
    assert gpu.count("USER spark") >= 1
    for dockerfile in (core, gpu):
        assert "/home/spark /home/spark/.cache /home/spark/.ros" in dockerfile
        assert "ENV HOME=/home/spark" in dockerfile
        assert 'test -w "${HOME}" && test -w "${HOME}/.ros"' in dockerfile
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    assert compose["x-common"]["working_dir"] == "/home/spark/spark-3dsg-pipeline"
    for suffix in ("*.pt", "*.bag", "*.db3", "*.mcap", "*.ply"):
        assert suffix in (ROOT / ".gitignore").read_text()
        assert suffix in (ROOT / ".dockerignore").read_text()


def test_pipeline_omits_unused_perception_launch_arguments():
    script = (ROOT / "scripts/shell/run_pipeline.sh").read_text(encoding="utf-8")
    common, selected = script.split(
        'if [[ "$semantics_source" == closed_set ]]; then\n  launch_args+=(', 1
    )
    closed_set, open_set = selected.split(
        'elif [[ "$semantics_source" == open_set ]]; then', 1
    )

    assert "launch_args=(" in common
    assert "perception_config_path" not in common.split("launch_args=(", 1)[1]
    for name in (
        "model_file",
        "model_config_path",
        "grouping_config_path",
        "labelspace_name",
    ):
        assert f'"{name}:=$' in closed_set
    assert "perception_config_path:=$perception_config" in open_set
    assert 'pipeline.launch.yaml "${launch_args[@]}"' in open_set


def test_pipeline_waits_for_online_perception_before_bag_playback():
    script = (ROOT / "scripts/shell/run_pipeline.sh").read_text(encoding="utf-8")
    readiness = script.index("perception_node=")
    playback = script.index('"$pipeline_root/scripts/shell/run_bag.sh"')

    assert readiness < playback
    assert "perception_node=/semantic_inference_closed_set" in script
    assert "perception_node=/semantic_inference" in script
    assert 'ros2 node info "$perception_node"' in script
    assert 'grep -Fq "$color_topic:"' in script
    assert '"$hydra_ready" == true && "$perception_ready" == true' in script


def test_core_is_complete_and_gpu_has_an_independent_runtime_stage():
    core = (ROOT / "docker/Dockerfile.core").read_text(encoding="utf-8")
    gpu = (ROOT / "docker/Dockerfile.gpu").read_text(encoding="utf-8")
    build_script = (ROOT / "scripts/shell/build_workspace.sh").read_text(
        encoding="utf-8"
    )

    assert "ARG ROS_IMAGE=osrf/ros:jazzy-desktop-full" in core
    assert sum(line.startswith("FROM ") for line in core.splitlines()) == 1
    assert sum(line.startswith("FROM ") for line in gpu.splitlines()) == 2
    assert "--from=" not in core
    assert "FROM ${CUDA_IMAGE} AS builder" in gpu
    assert "FROM ${CUDA_RUNTIME_IMAGE} AS runtime" in gpu
    assert "COPY --from=builder --chown=${USER_UID}:${USER_GID}" in gpu
    assert "spark-3dsg-core" not in gpu
    assert "ARG CUDA_IMAGE=nvidia/cuda:12.8.1-devel-ubuntu24.04" in gpu
    assert (
        "ARG CUDA_RUNTIME_IMAGE=nvidia/cuda:12.8.1-runtime-ubuntu24.04" in gpu
    )
    assert "ros-jazzy-desktop" in gpu
    assert "python3-vcstool" in core
    assert "python3-vcstool" in gpu
    assert "COPY . ${PIPELINE_ROOT}" in core
    assert "COPY --chown=${USER_UID}:${USER_GID} . ${PIPELINE_ROOT}" in gpu
    assert "SPARK_SYMLINK_INSTALL=ON" in core
    assert "SPARK_SYMLINK_INSTALL=OFF" in gpu
    assert 'chown -R "${USER_UID}:${USER_GID}"' not in gpu
    assert "-DBUILD_TESTING=${SPARK_BUILD_TESTING:-OFF}" in build_script
    assert (
        '"-DSEMANTIC_INFERENCE_USE_TRT='
        '${SPARK_SEMANTIC_INFERENCE_USE_TRT:-OFF}"'
    ) in build_script


def test_gpu_stack_is_exact_and_python_is_self_contained():
    gpu = (ROOT / "docker/Dockerfile.gpu").read_text(encoding="utf-8")
    requirements = (ROOT / "dependencies/gpu.requirements.txt").read_text(
        encoding="utf-8"
    )
    baseline = (ROOT / "dependencies/GPU_BASELINE.md").read_text(encoding="utf-8")

    expected = {
        "ARG CUDA_IMAGE=nvidia/cuda:12.8.1-devel-ubuntu24.04",
        "ARG CUDA_RUNTIME_IMAGE=nvidia/cuda:12.8.1-runtime-ubuntu24.04",
        "ARG TENSORRT_VERSION=10.9.0.34-1+cuda12.8",
        "ARG TORCH_VERSION=2.7.0",
        "ARG TORCHVISION_VERSION=0.22.0",
        "ARG PYTORCH_INDEX=https://download.pytorch.org/whl/cu128",
    }
    assert expected <= set(gpu.splitlines())
    for package in (
        "libnvinfer-headers-dev",
        "libnvinfer-headers-plugin-dev",
        "libnvinfer10",
        "libnvinfer-dev",
        "libnvinfer-plugin10",
        "libnvinfer-plugin-dev",
        "libnvonnxparsers10",
        "libnvonnxparsers-dev",
    ):
        assert f'"{package}=${{TENSORRT_VERSION}}"' in gpu
    assert 'python3 -m venv "${SEMANTIC_ENV}"' in gpu
    assert 'venv --system-site-packages "${SEMANTIC_ENV}"' not in gpu
    assert "import clip, PIL, rclpy, semantic_inference, spark_dsg" in gpu
    assert "SPARK_SEMANTIC_INFERENCE_USE_TRT=ON" in gpu
    assert "nvcc --version | grep -F 'release 12.8'" in gpu
    assert "grep -F 'libnvinfer.so.10 =>'" in gpu
    assert "grep -F 'not found'" in gpu
    runtime = gpu.split("FROM ${CUDA_RUNTIME_IMAGE} AS runtime", 1)[1]
    assert '"libnvinfer10=${TENSORRT_VERSION}"' in runtime
    assert '"libnvinfer-plugin10=${TENSORRT_VERSION}"' in runtime
    assert '"libnvonnxparsers10=${TENSORRT_VERSION}"' in runtime
    assert '"libnvinfer-dev=${TENSORRT_VERSION}"' not in runtime
    assert '"libnvinfer-plugin-dev=${TENSORRT_VERSION}"' not in runtime
    assert '"libnvonnxparsers-dev=${TENSORRT_VERSION}"' not in runtime
    assert "--dependency-types exec" in runtime
    assert "! command -v nvcc" in runtime
    assert "! dpkg-query -W libnvinfer-dev" in runtime
    assert "ros2 launch spark_3dsg_pipeline pipeline.launch.yaml" in runtime
    assert "--show-args >/dev/null" in runtime
    validation = gpu.split("SPARK_SEMANTIC_INFERENCE_USE_TRT=ON", 1)[1].split(
        "WORKDIR ${PIPELINE_ROOT}", 1
    )[0]
    assert validation.index("source ${ROS_WS}/install/setup.bash") < validation.index(
        "ldd ${ROS_WS}/install/lib/libsemantic_inference.so"
    )
    assert "pillow==11.3.0" in requirements
    assert "driver 580.173.02" in baseline
    assert "CUDA 13.0" in baseline
    assert "pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime" in baseline
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "gpu-smoke:" in makefile
    assert "scripts/shell/gpu_smoke_test.sh" in makefile
    smoke = (ROOT / "scripts/shell/gpu_smoke_test.sh").read_text(encoding="utf-8")
    assert 'model.set_classes(["chair", "table"])' in smoke


def test_compose_reuses_core_image_and_builds_gpu_independently():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    assert "core-builder" not in compose["services"]
    for service in ("core", "core-dev", "data-setup", "rviz"):
        assert compose["services"][service]["image"] == "spark-3dsg-core:local"
        assert "target" not in compose["services"][service]["build"]
    assert compose["services"]["pipeline"]["image"] == "spark-3dsg-gpu:local"
    assert compose["services"]["pipeline"]["build"]["dockerfile"] == (
        "docker/Dockerfile.gpu"
    )
    assert "target" not in compose["services"]["pipeline"]["build"]
    assert "gpus" not in compose["services"]["rviz"]
    assert compose["services"]["pipeline"]["gpus"] == "all"
    for service in compose["services"].values():
        for volume in service.get("volumes", []):
            assert "/ros_ws/src/" not in volume
            assert "/spark-3dsg-pipeline/scripts" not in volume

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "--profile dev run --rm --build core-dev" in makefile
    assert "--profile rviz run --rm rviz" in makefile
    build_target = makefile.split("build: ##", 1)[1].split("models: ##", 1)[0]
    gpu_build = build_target.split("else ifeq ($(PROFILE),gpu)", 1)[1].split(
        "endif", 1
    )[0]
    assert "build pipeline" in gpu_build
    assert "build core" not in gpu_build
