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
        if any(part in {".git", ".venv"} for part in path.parts):
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
    adapter = load("config/datasets/spot.yaml")
    assert adapter["semantics"]["labels_config"].endswith("labels/adt4.yaml")
    assert "adt4.yaml" not in (PACKAGE / "config/perception/yoloe.yaml").read_text()
    runner = (ROOT / "scripts/run_pipeline.sh").read_text(encoding="utf-8")
    assert "--labels-config" in runner
    assert "merge_yaml.py" in runner


def test_all_referenced_package_local_files_exist():
    for adapter_path in (PACKAGE / "config/datasets").glob("*.yaml"):
        adapter = yaml.safe_load(adapter_path.read_text(encoding="utf-8"))
        assert (PACKAGE / "config/hydra" / adapter["hydra_config"]).is_file()
        for value in adapter["semantics"].values():
            if isinstance(value, str) and value.startswith("spark_3dsg_pipeline:"):
                relative = value.split(":", 1)[1]
                assert (PACKAGE / relative).is_file(), f"{adapter_path}: {relative}"
        profile = adapter["visualization"]["profile"]
        assert (PACKAGE / "config/visualization" / f"{profile}.yaml").is_file()


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
    wrapper = (ROOT / "scripts/run_visualization.sh").read_text(encoding="utf-8")
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
    runner = (ROOT / "scripts/run_pipeline.sh").read_text(encoding="utf-8")
    assert '"pipeline_version": "v1"' in runner
    assert '"dependency_lock_hash"' in runner
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
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    assert compose["x-common"]["working_dir"] == "/home/spark/spark-3dsg-pipeline"
    for suffix in ("*.pt", "*.bag", "*.db3", "*.mcap", "*.ply"):
        assert suffix in (ROOT / ".gitignore").read_text()
        assert suffix in (ROOT / ".dockerignore").read_text()


def test_release_images_use_separate_builder_and_runtime_stages():
    core = (ROOT / "docker/Dockerfile.core").read_text(encoding="utf-8")
    gpu = (ROOT / "docker/Dockerfile.gpu").read_text(encoding="utf-8")
    build_script = (ROOT / "scripts/build_workspace.sh").read_text(
        encoding="utf-8"
    )

    assert "AS core-builder" in core
    assert "AS core-runtime" in core
    assert "AS core-development" in core
    assert "AS rviz-runtime" in core
    assert "osrf/ros:jazzy-ros-base" in core
    assert "--from=core-builder" in core
    assert "${ROS_WS}/install ${ROS_WS}/install" in core
    assert "COPY --chown=${USER_UID}:${USER_GID}" in core
    assert "--dependency-types exec" in core
    assert "apt-get purge -y --no-auto-remove" in core
    assert "SPARK_SYMLINK_INSTALL=OFF" in core
    assert "-DBUILD_TESTING=${SPARK_BUILD_TESTING:-OFF}" in build_script
    assert "--symlink-install" not in build_script.split("colcon_args=(", 1)[1].split(")", 1)[0]

    assert "AS gpu-builder" in gpu
    assert "AS gpu-runtime" in gpu
    assert "COPY --chown=spark:spark --from=gpu-builder" in gpu
    assert "/home/spark/ros_ws/install /home/spark/ros_ws/install" in gpu
    assert "/home/spark/.venvs/semantic_inference /home/spark/.venvs/semantic_inference" in gpu
    assert "chown -R spark:spark" not in gpu
    runtime = gpu.split("AS gpu-runtime", 1)[1]
    assert "cuda-nvcc" not in runtime
    assert "libnvinfer-dev" not in runtime


def test_compose_uses_slim_runtime_dev_and_rviz_targets():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    targets = {
        "core-builder": "core-builder",
        "core": "core-runtime",
        "core-dev": "core-development",
        "pipeline": "gpu-runtime",
        "data-setup": "core-runtime",
        "rviz": "rviz-runtime",
    }
    for service, target in targets.items():
        assert compose["services"][service]["build"]["target"] == target

    assert compose["services"]["rviz"]["image"] == "spark-3dsg-rviz:local"
    assert "gpus" not in compose["services"]["rviz"]
    assert compose["services"]["pipeline"]["gpus"] == "all"

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "--profile dev run --rm --build core-dev" in makefile
    assert "--profile rviz run --rm --build rviz" in makefile
