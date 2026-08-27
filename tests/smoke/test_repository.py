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
        (ROOT / "ros_ws/src/spark_dsg_pipeline/config/hydra/default.yaml").read_text()
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
