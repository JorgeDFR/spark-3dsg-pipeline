from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[2]


def assert_yaml_has_unique_keys(path):
    def visit(node):
        if isinstance(node, yaml.MappingNode):
            keys = set()
            for key, value in node.value:
                assert isinstance(key, yaml.ScalarNode), f"{path}: non-scalar YAML key"
                assert key.value not in keys, f"{path}: duplicate YAML key {key.value!r}"
                keys.add(key.value)
                visit(value)
        elif isinstance(node, yaml.SequenceNode):
            for value in node.value:
                visit(value)

    visit(yaml.compose(path.read_text()))


def test_lock_is_https_and_exact():
    sha = re.compile(r"^[0-9a-f]{40}$")
    lock = yaml.safe_load((ROOT / "dependencies/locks/adt4.lock.repos").read_text())
    for entry in lock["repositories"].values():
        assert entry["url"].startswith("https://")
        assert sha.fullmatch(entry["version"])


def test_mapper_config_contains_v1_architecture():
    config = yaml.safe_load(
        (
            ROOT
            / "src/spark_3dsg_pipeline/config/hydra/adt4.yaml"
        ).read_text()
    )
    assert config["active_window"]["type"] == "ActiveWindow"
    assert config["active_window"]["tracker"]["type"] == "MaxIouTracker"
    assert config["active_window"]["object_extractor"]["type"] == "MeshObjectExtractor"
    assert config["frontend"]["traversability_places"]["layer"] == "MESH_PLACES"
    assert "freespace_places" not in config["frontend"]
    assert "OBJECTS" in config["frontend"]["graph_updater"]["layer_updates"]
    assert "places" not in config["backend"]["update_functors"]
    assert "rooms" not in config["backend"]["update_functors"]
    for frame_key in ("map_frame", "odom_frame", "robot_frame"):
        assert frame_key not in config


def test_classic_profile_adds_places_and_rooms_to_adt4_classic():
    config = yaml.safe_load(
        (
            ROOT / "src/spark_3dsg_pipeline/config/hydra/classic.yaml"
        ).read_text()
    )
    assert config["paths"] == ["khronos", "khronos_ros"]
    assert config["active_window"]["type"] == "ActiveWindow"
    assert config["active_window"]["object_detector"]["type"] == "ConnectedSemantics"
    assert config["active_window"]["tracker"]["track_by"] == "voxels"
    assert config["frontend"]["surface_places"]["type"] == "place_2d"
    assert config["frontend"]["freespace_places"]["type"] == "gvd"
    functors = config["backend"]["update_functors"]
    assert functors["surface_places"]["type"] == "Update2dPlacesFunctor"
    assert functors["places"]["type"] == "UpdatePlacesFunctor"
    assert functors["rooms"]["type"] == "UpdateRoomsFunctor"
    assert "buildings" not in functors


def test_uhumans2_profile_uses_core_hydra_hierarchy():
    config = yaml.safe_load(
        (
            ROOT
            / "src/spark_3dsg_pipeline/config/hydra/uhumans2.yaml"
        ).read_text()
    )
    assert "paths" not in config
    assert config["active_window"]["type"] == "ReconstructionModule"
    assert config["input"]["inputs"]["camera"]["receiver"]["type"] == "ClosedSetImageReceiver"
    assert config["frontend"]["enable_mesh_objects"] is True
    assert config["frontend"]["freespace_places"]["type"] == "gvd"
    functors = config["backend"]["update_functors"]
    assert functors["objects"]["type"] == "UpdateObjectsFunctor"
    assert functors["places"]["type"] == "UpdatePlacesFunctor"
    assert functors["rooms"]["type"] == "UpdateRoomsFunctor"
    assert functors["buildings"]["type"] == "UpdateBuildingsFunctor"


def test_every_dataset_selects_an_installed_complete_hydra_profile():
    package = ROOT / "src/spark_3dsg_pipeline"
    hydra_dir = package / "config/hydra"
    for dataset_path in (package / "config/datasets").glob("*.yaml"):
        dataset = yaml.safe_load(dataset_path.read_text())
        profile = hydra_dir / dataset["hydra_config"]
        assert profile.is_file(), f"{dataset_path.name}: missing {profile.name}"

    assert not (hydra_dir / "empty.yaml").exists()
    assert sorted(path.name for path in hydra_dir.glob("*.yaml")) == [
        "adt4.yaml",
        "classic.yaml",
        "uhumans2.yaml",
    ]
    for profile in hydra_dir.glob("*.yaml"):
        assert_yaml_has_unique_keys(profile)
        config = yaml.safe_load(profile.read_text())
        for frame_key in ("map_frame", "odom_frame", "robot_frame"):
            assert frame_key not in config, f"{profile.name}: {frame_key} belongs to launch"


def test_large_artifacts_are_ignored():
    ignore = (ROOT / ".gitignore").read_text()
    dockerignore = (ROOT / ".dockerignore").read_text()
    for suffix in ("*.pt", "*.bag", "*.db3", "*.mcap", "*.ply"):
        assert suffix in ignore
        assert suffix in dockerignore


def test_containers_use_host_matched_non_root_user():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())
    build_args = compose["services"]["core"]["build"]["args"]
    assert build_args == {
        "USER_UID": "${HOST_UID:-1000}",
        "USER_GID": "${HOST_GID:-1000}",
    }
    common = compose["x-common"]
    assert common["working_dir"] == "/home/spark/spark-3dsg-pipeline"
    required_volumes = {
        "${DATA_DIR:-./data}:/home/spark/data:ro",
        "${MODEL_DIR:-./models}:/home/spark/models",
        "${OUTPUT_DIR:-./output}:/home/spark/output",
        "${PACKAGE_SOURCE_DIR:-./src/spark_3dsg_pipeline}:/home/spark/ros_ws/src/spark_3dsg_pipeline",
        "spark-cache:/home/spark/.cache",
    }
    assert required_volumes.issubset(common["volumes"])

    env_example = (ROOT / ".env.example").read_text()
    assert "HOST_UID=1000" in env_example
    assert "HOST_GID=1000" in env_example
    assert "PACKAGE_SOURCE_DIR=./src/spark_3dsg_pipeline" in env_example

    core = (ROOT / "docker/Dockerfile.core").read_text()
    gpu = (ROOT / "docker/Dockerfile.gpu").read_text()
    assert "ARG USER_UID=1000" in core
    assert "ARG USER_GID=1000" in core
    assert "ROS_WS=/home/spark/ros_ws" in core
    assert "PIPELINE_ROOT=/home/spark/spark-3dsg-pipeline" in core
    assert "/opt/ros_ws" not in core
    assert "/opt/spark_pipeline" not in core
    assert "USER spark" in core
    assert gpu.rstrip().endswith('CMD ["bash"]')
    assert "USER spark" in gpu

    build_script = (ROOT / "scripts/build_workspace.sh").read_text()
    assert "--symlink-install" in build_script

    data_setup = compose["services"]["data-setup"]
    assert data_setup["volumes"] == [
        "${DATA_DIR:-./data}:/home/spark/data"
    ]
    assert data_setup["working_dir"] == "/home/spark/spark-3dsg-pipeline"


def test_spot_is_the_default_dataset_adapter():
    makefile = (ROOT / "Makefile").read_text()
    assert "DATASET ?= spot" in makefile


def test_integration_package_name_and_flat_source_layout():
    package_root = ROOT / "src/spark_3dsg_pipeline"
    assert package_root.is_dir()
    assert not (ROOT / "ros_ws").exists()
    assert "<name>spark_3dsg_pipeline</name>" in (
        package_root / "package.xml"
    ).read_text()
    assert "project(spark_3dsg_pipeline)" in (
        package_root / "CMakeLists.txt"
    ).read_text()


def test_ros_setup_is_sourced_without_nounset():
    script = (ROOT / "scripts/build_workspace.sh").read_text()
    disable_nounset = script.index("set +u")
    source_ros = script.index("source /opt/ros/jazzy/setup.bash")
    restore_nounset = script.index("set -u", source_ros)
    assert disable_nounset < source_ros < restore_nounset


def test_docker_uses_canonical_bootstrap_and_ros_entrypoint():
    core = (ROOT / "docker/Dockerfile.core").read_text()
    gpu = (ROOT / "docker/Dockerfile.gpu").read_text()

    assert "scripts/bootstrap_dependencies.sh" in core
    assert "vcs import src" not in core
    assert "docker/ros_entrypoint.sh" in core
    assert "docker/ros_entrypoint.sh" in gpu
    assert not (ROOT / "docker/entrypoint.sh").exists()


def test_launch_configs_keep_hydra_and_perception_paths_isolated():
    package = ROOT / "src/spark_3dsg_pipeline"
    pipeline = (package / "launch/pipeline.launch.yaml").read_text()
    perception = (package / "launch/perception.launch.yaml").read_text()

    assert "name: hydra_config_path" in pipeline
    assert "name: hydra_overlay_path" not in pipeline
    assert "name: perception_config_path" in pipeline
    assert "--config-utilities-file $(var hydra_config_path)" in pipeline
    assert pipeline.count("--config-utilities-file") == 1
    assert "value: $(var perception_config_path)" in perception


def test_runtime_resources_use_ament_package_share():
    script = (ROOT / "scripts/run_pipeline.sh").read_text()
    assert "ros2 pkg prefix --share spark_3dsg_pipeline" in script
    assert "install/spark_3dsg_pipeline/share" not in script
    assert "--get hydra_config" in script
    assert 'hydra_config_path:="$hydra_config"' in script
    assert 'cp "$hydra_config" "$run_dir/hydra.yaml"' in script

    bag_launch = (
        ROOT / "src/spark_3dsg_pipeline/launch/bag.launch.yaml"
    ).read_text()
    assert "$(find-pkg-share spark_3dsg_pipeline)/config/tf_qos.yaml" in bag_launch


def test_bag_playback_waits_for_hydra_input_subscription():
    script = (ROOT / "scripts/run_pipeline.sh").read_text()
    readiness = script.index('readiness_topic=/input/color/camera_info')
    subscription = script.index('ros2 topic info "$readiness_topic"', readiness)
    playback = script.index('"$pipeline_root/scripts/run_bag.sh"', subscription)
    assert readiness < subscription < playback
    assert "ros2 node list" not in script


def test_bag_playback_uses_package_launch_and_normalizes_all_inputs():
    script = (ROOT / "scripts/run_bag.sh").read_text()
    launch = (
        ROOT / "src/spark_3dsg_pipeline/launch/bag.launch.yaml"
    ).read_text()

    assert "exec ros2 launch spark_3dsg_pipeline bag.launch.yaml" in script
    assert "ros2 bag play" not in script
    for key in (
        "color",
        "depth",
        "camera_info",
        "instances",
        "labelspace",
        "tf",
        "tf_static",
    ):
        assert f"topic {key}" in script

    assert "- executable:" in launch
    assert "ros2 bag play $(var bag)" in launch
    assert "pkg: rosbag2_transport" not in launch
    assert launch.count("--remap") == 1
    for target in (
        "/input/color/image_raw",
        "/input/depth/image_rect",
        "/input/color/camera_info",
        "/input/semantic/instances",
        "/input/semantic/labelspace",
        "/tf",
        "/tf_static",
    ):
        assert f":={target}" in launch


def test_rviz_uses_package_visualization_launch_and_dataset_frame():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())
    makefile = (ROOT / "Makefile").read_text()
    wrapper = (ROOT / "scripts/run_visualization.sh").read_text()
    launch = (
        ROOT / "src/spark_3dsg_pipeline/launch/visualization.launch.yaml"
    ).read_text()
    rviz = (ROOT / "src/spark_3dsg_pipeline/rviz/scene_graph.rviz").read_text()

    assert compose["services"]["rviz"]["command"] == [
        "/home/spark/spark-3dsg-pipeline/scripts/run_visualization.sh",
        "spot",
    ]
    assert 'run_visualization.sh "$(DATASET)"' in makefile
    assert "ros2 launch spark_3dsg_pipeline visualization.launch.yaml" in wrapper
    assert "--get frames.map" in wrapper
    assert "hydra_visualizer)/launch/streaming_visualizer.launch.yaml" in launch
    assert "visualizer_frame, value: $(var map_frame)" in launch
    assert "external_plugins_path, value: $(var visualizer_overlay_path)" in launch
    assert "--fixed-frame $(var map_frame)" in launch
    for topic in (
        "/hydra_visualizer/mesh",
        "/hydra_visualizer/graph",
        "/hydra_visualizer/agent_poses",
    ):
        assert topic in rviz


def test_visualization_uses_rgb_mesh_colors_and_displayable_semantic_overlay():
    package = ROOT / "src/spark_3dsg_pipeline"
    perception_config = yaml.safe_load(
        (package / "config/perception/yoloe.yaml").read_text()
    )
    visualizer_config = yaml.safe_load(
        (package / "config/visualization/adt4.yaml").read_text()
    )
    perception_launch = (package / "launch/perception.launch.yaml").read_text()
    rviz = (package / "rviz/scene_graph.rviz").read_text()

    assert perception_config["visualize_semantic_img"] is True
    assert (
        "from: semantic_overlay/image_raw, to: /input/semantic/overlay"
        in perception_launch
    )
    assert "/input/semantic/overlay" in rviz
    assert "/input/semantic/instances" not in rviz
    assert visualizer_config["plugins"]["mesh"]["coloring"]["type"] == ""


def test_lint_validates_every_installed_launch_file():
    script = (ROOT / "scripts/run_lint.sh").read_text()
    launch_dir = ROOT / "src/spark_3dsg_pipeline/launch"
    for launch_file in launch_dir.glob("*.launch.yaml"):
        assert launch_file.name in script


def test_tf_static_qos_retains_every_example_batch():
    config = yaml.safe_load(
        (ROOT / "src/spark_3dsg_pipeline/config/tf_qos.yaml").read_text()
    )
    profile = config["/tf_static"]
    assert profile["history"] == "keep_last"
    assert profile["depth"] >= 5
    assert profile["durability"] == "transient_local"
    assert profile["reliability"] == "reliable"
