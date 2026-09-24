import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts/shell/run_visualization.sh"


def fake_ros_environment(tmp_path):
    binary = tmp_path / "ros2"
    binary.write_text(
        """#!/usr/bin/env bash
if [[ "$1" == pkg ]]; then
  printf '%s\\n' "$FAKE_PACKAGE_SHARE"
else
  printf 'ros2 args: %s\\n' "$*"
fi
""",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{Path(sys.executable).parent}:{env['PATH']}"
    env["FAKE_PACKAGE_SHARE"] = str(ROOT / "src/spark_3dsg_pipeline")
    env["PIPELINE_ROOT"] = str(ROOT)
    return env


def test_saved_visualization_reports_missing_json_before_ros(tmp_path):
    result = subprocess.run(
        [str(WRAPPER), "--profile", "hierarchical", "--dsg", str(tmp_path / "missing.json")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "DSG JSON not found" in result.stderr


def test_live_visualization_omits_empty_scene_graph_argument(tmp_path):
    result = subprocess.run(
        [str(WRAPPER), "--dataset", "spot", "--mapping", "open_set"],
        capture_output=True,
        text=True,
        env=fake_ros_environment(tmp_path),
    )
    assert result.returncode == 0
    assert "file_mode:=false" in result.stdout
    assert "scene_graph:=" not in result.stdout


def test_saved_visualization_reports_invalid_json_before_ros(tmp_path):
    invalid = tmp_path / "invalid.json"
    invalid.write_text("not json\n", encoding="utf-8")
    result = subprocess.run(
        [str(WRAPPER), "--profile", "khronos", "--dsg", str(invalid)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "invalid DSG JSON" in result.stderr


def test_saved_visualization_warns_when_mesh_is_absent(tmp_path):
    graph = tmp_path / "graph.json"
    graph.write_text('{"nodes": []}\n', encoding="utf-8")
    result = subprocess.run(
        [str(WRAPPER), "--profile", "hierarchical", "--dsg", str(graph)],
        capture_output=True,
        text=True,
        env=fake_ros_environment(tmp_path),
    )
    assert result.returncode == 0
    assert "does not contain a non-empty embedded mesh" in result.stderr


def test_saved_visualization_prefers_mesh_bearing_sibling(tmp_path):
    graph = tmp_path / "dsg.json"
    graph.write_text('{"nodes": []}\n', encoding="utf-8")
    graph_with_mesh = tmp_path / "dsg_with_mesh.json"
    graph_with_mesh.write_text(
        '{"mesh": {"points": [[0, 0, 0]], "faces": [[0, 0, 0]]}}\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(WRAPPER), "--profile", "khronos", "--dsg", str(graph)],
        capture_output=True,
        text=True,
        env=fake_ros_environment(tmp_path),
    )
    assert result.returncode == 0
    assert f"Using mesh-bearing DSG for visualization: {graph_with_mesh}" in result.stdout
    assert f"scene_graph:={graph_with_mesh}" in result.stdout
    assert "does not contain" not in result.stderr
