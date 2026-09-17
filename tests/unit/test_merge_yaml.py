import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_open_set_labels_overlay_does_not_modify_model_settings(tmp_path):
    output = tmp_path / "resolved.yaml"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/merge_yaml.py"),
            str(ROOT / "src/spark_3dsg_pipeline/config/perception/yoloe.yaml"),
            str(ROOT / "src/spark_3dsg_pipeline/config/perception/labels/adt4.yaml"),
            "--output",
            str(output),
        ],
        check=True,
    )
    config = yaml.safe_load(output.read_text(encoding="utf-8"))
    model = config["model"]["instance_model"]
    assert model["type"] == "yoloe"
    assert model["model_name"] == "yoloe-26m-seg.pt"
    assert model["text_prompt"][0] == "ignore"


def test_arbitrary_labels_overlay_replaces_only_prompt(tmp_path):
    labels = tmp_path / "labels.yaml"
    labels.write_text(
        "model:\n  instance_model:\n    text_prompt: [ignore, mug]\n",
        encoding="utf-8",
    )
    output = tmp_path / "resolved.yaml"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/merge_yaml.py"),
            str(ROOT / "src/spark_3dsg_pipeline/config/perception/yoloe.yaml"),
            str(labels),
            "--output",
            str(output),
        ],
        check=True,
    )
    model = yaml.safe_load(output.read_text())["model"]["instance_model"]
    assert model["text_prompt"] == ["ignore", "mug"]
    assert model["confidence_threshold"] == 0.3
