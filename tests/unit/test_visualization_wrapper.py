import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts/run_visualization.sh"


def test_saved_visualization_reports_missing_json_before_ros(tmp_path):
    result = subprocess.run(
        [str(WRAPPER), "--profile", "hierarchical", "--dsg", str(tmp_path / "missing.json")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "DSG JSON not found" in result.stderr


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
