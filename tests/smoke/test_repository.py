from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_lock_is_https_and_exact():
    sha = re.compile(r"^[0-9a-f]{40}$")
    lock = yaml.safe_load((ROOT / "dependencies/locks/adt4.lock.repos").read_text())
    for entry in lock["repositories"].values():
        assert entry["url"].startswith("https://")
        assert sha.fullmatch(entry["version"])


def test_mapper_config_contains_v1_architecture():
    config = yaml.safe_load(
        (ROOT / "src/spark_3dsg_pipeline/config/hydra/default.yaml").read_text()
    )
    assert config["active_window"]["type"] == "ActiveWindow"
    assert config["active_window"]["tracker"]["type"] == "MaxIouTracker"
    assert config["active_window"]["object_extractor"]["type"] == "MeshObjectExtractor"
    assert config["frontend"]["traversability_places"]["layer"] == "MESH_PLACES"
    assert "OBJECTS" in config["frontend"]["graph_updater"]["layer_updates"]


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
    assert common["volumes"] == [
        "${DATA_DIR:-./data}:/home/spark/data:ro",
        "${MODEL_DIR:-./models}:/home/spark/models",
        "${OUTPUT_DIR:-./output}:/home/spark/output",
        "${PACKAGE_SOURCE_DIR:-./src/spark_3dsg_pipeline}:/home/spark/ros_ws/src/spark_3dsg_pipeline:ro",
        "spark-cache:/home/spark/.cache",
    ]

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
