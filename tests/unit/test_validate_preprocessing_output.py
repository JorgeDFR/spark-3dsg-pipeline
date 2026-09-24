from pathlib import Path

import yaml

from validate_preprocessing_output import topic_counts


def test_topic_counts_reads_rosbag2_metadata(tmp_path: Path):
    metadata = {
        "rosbag2_bagfile_information": {
            "topics_with_message_count": [
                {
                    "topic_metadata": {
                        "name": "/input/imu",
                        "type": "sensor_msgs/msg/Imu",
                    },
                    "message_count": 42,
                }
            ]
        }
    }
    (tmp_path / "metadata.yaml").write_text(
        yaml.safe_dump(metadata), encoding="utf-8"
    )
    assert topic_counts(tmp_path) == {"/input/imu": 42}


def test_validation_rejects_advertised_but_empty_rgbd(tmp_path, monkeypatch, capsys):
    import sys
    import validate_preprocessing_output as validator

    (tmp_path / "metadata.yaml").write_text(yaml.safe_dump({
        "rosbag2_bagfile_information": {
            "topics_with_message_count": [
                {"topic_metadata": {"name": topic}, "message_count": 0}
                for topic in validator.REQUIRED_TOPICS
            ],
        },
    }))
    for name in ("dataset.yaml", "source.yaml", "preprocessing.yaml", "preprocess.lock.repos",
                 "preprocessing_manifest.yaml", "validation.txt"):
        (tmp_path / name).touch()
    monkeypatch.setattr(sys, "argv", ["validate_preprocessing_output.py", "--bag", str(tmp_path)])
    assert validator.main() == 1
    assert "required topic has no messages: /input/depth/image_rect" in capsys.readouterr().out
