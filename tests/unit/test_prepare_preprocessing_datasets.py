from pathlib import Path

import prepare_preprocessing_datasets


def test_convert_ros1_creates_missing_destination_parent(tmp_path, monkeypatch):
    source = tmp_path / "input.bag"
    source.write_bytes(b"ros1 fixture")
    destination = tmp_path / "missing" / "nested" / "output"
    calls = []

    def fake_run(command, check):
        calls.append((command, check))
        temporary = Path(command[command.index("--dst") + 1])
        temporary.mkdir()
        (temporary / "metadata.yaml").write_text(
            "rosbag2_bagfile_information: {}\n", encoding="utf-8"
        )
        (temporary / "output.mcap").write_bytes(b"ros2 fixture")

    monkeypatch.setattr(prepare_preprocessing_datasets.subprocess, "run", fake_run)

    prepare_preprocessing_datasets.convert_ros1(
        source, destination, ["/camera/image"]
    )

    assert prepare_preprocessing_datasets.is_ros2_bag(destination)
    command, check = calls[0]
    assert command[-2:] == ["--include-topic", "/camera/image"]
    assert check is True


def test_openvins_calibration_is_written_under_raw_test_preprocess(
    tmp_path, monkeypatch
):
    def fake_download(url, destination, expected_bytes):
        destination.write_text("estimator\n", encoding="utf-8")

    monkeypatch.setattr(prepare_preprocessing_datasets, "download", fake_download)

    prepare_preprocessing_datasets.write_openvins_calibration(tmp_path)

    calibration = (
        tmp_path / "raw" / "test-preprocess" / "calibration" / "openvins"
    )
    assert (calibration / "estimator_config.yaml").is_file()
    assert (calibration / "kalibr_imu_chain.yaml").is_file()
    assert (calibration / "kalibr_imucam_chain.yaml").is_file()
    assert not (tmp_path / "normalized" / "calibration").exists()


def test_legacy_conversion_is_moved_without_copying(tmp_path):
    legacy = tmp_path / "normalized" / "d435i_run009"
    legacy.mkdir(parents=True)
    (legacy / "metadata.yaml").write_text("metadata\n", encoding="utf-8")
    destination = (
        tmp_path / "raw" / "test-preprocess" / "d435i_run009_ros2"
    )

    prepare_preprocessing_datasets.migrate_legacy([legacy], destination)

    assert not legacy.exists()
    assert (destination / "metadata.yaml").is_file()


def test_empty_legacy_prepared_tree_is_removed(tmp_path):
    legacy = tmp_path / "prepared" / "validation" / "calibration"
    legacy.mkdir(parents=True)

    prepare_preprocessing_datasets.prune_legacy_prepared_directories(tmp_path)

    assert not (tmp_path / "prepared").exists()
