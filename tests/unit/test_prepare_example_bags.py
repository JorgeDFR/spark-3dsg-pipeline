from pathlib import Path
import zipfile

import pytest

import prepare_example_bags


def write_ros2_bag(path: Path, storage_name: str = "bag_0.mcap") -> Path:
    path.mkdir(parents=True)
    (path / "metadata.yaml").write_text("rosbag2_bagfile_information: {}\n")
    (path / storage_name).write_bytes(b"bag fixture")
    return path


def data_layout(root: Path) -> tuple[Path, Path]:
    raw = root / "raw"
    normalized = root / "normalized"
    raw.mkdir()
    normalized.mkdir()
    return raw, normalized


def test_spot_extracted_directory_gets_canonical_link(tmp_path):
    raw, normalized = data_layout(tmp_path)
    source = write_ros2_bag(raw / "2025-09-04-heracles-eval-3-bag")

    assert prepare_example_bags.prepare_spot(raw, normalized)

    canonical = normalized / "spot"
    assert canonical.is_symlink()
    assert canonical.resolve() == source
    assert prepare_example_bags.is_ros2_bag(canonical)


def test_spot_known_zip_is_extracted_to_canonical_directory(tmp_path):
    raw, normalized = data_layout(tmp_path)
    archive_path = raw / "adt4_spot_example_bag.zip"
    prefix = "2025-09-04-heracles-eval-3-bag"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(f"{prefix}/metadata.yaml", "bag metadata")
        archive.writestr(f"{prefix}/{prefix}_0.mcap", b"bag fixture")
        archive.writestr(f"{prefix}/ignored.txt", "not copied")

    assert prepare_example_bags.prepare_spot(raw, normalized)

    canonical = normalized / "spot"
    assert canonical.is_dir()
    assert not canonical.is_symlink()
    assert (canonical / "metadata.yaml").is_file()
    assert (canonical / f"{prefix}_0.mcap").is_file()
    assert not (canonical / "ignored.txt").exists()


def test_uhumans2_converted_directory_gets_canonical_link(tmp_path):
    raw, normalized = data_layout(tmp_path)
    source = write_ros2_bag(
        raw / "uHumans2_office_s1_00h_v2_ros2", "office.db3"
    )

    assert prepare_example_bags.prepare_uhumans2(raw, normalized, "unused")

    canonical = normalized / "uhumans2"
    assert canonical.is_symlink()
    assert canonical.resolve() == source


def test_uhumans2_ros1_file_is_converted(tmp_path, monkeypatch):
    raw, normalized = data_layout(tmp_path)
    source = raw / "uHumans2_office_s1_00h_v2.bag"
    source.write_bytes(b"ros1 fixture")
    calls = []

    def fake_run(command, check):
        calls.append((command, check))
        destination = Path(command[command.index("--dst") + 1])
        write_ros2_bag(destination, "office.db3")

    monkeypatch.setattr(prepare_example_bags.subprocess, "run", fake_run)

    assert prepare_example_bags.prepare_uhumans2(
        raw, normalized, "rosbags-convert"
    )

    canonical = normalized / "uhumans2"
    assert prepare_example_bags.is_ros2_bag(canonical)
    assert len(calls) == 1
    command, check = calls[0]
    assert command[:3] == ["rosbags-convert", "--src", str(source)]
    assert command[3] == "--dst"
    assert check is True


def test_uhumans2_zip_containing_ros1_file_is_converted(tmp_path, monkeypatch):
    raw, normalized = data_layout(tmp_path)
    archive_path = raw / "uHumans2_office_s1_00h_v2.bag.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "download/uHumans2_office_s1_00h_v2.bag", b"ros1 fixture"
        )

    sources = []

    def fake_run(command, check):
        assert check is True
        source = Path(command[command.index("--src") + 1])
        assert source.read_bytes() == b"ros1 fixture"
        sources.append(source)
        destination = Path(command[command.index("--dst") + 1])
        write_ros2_bag(destination, "office.db3")

    monkeypatch.setattr(prepare_example_bags.subprocess, "run", fake_run)

    assert prepare_example_bags.prepare_uhumans2(
        raw, normalized, "rosbags-convert"
    )
    assert len(sources) == 1
    assert prepare_example_bags.is_ros2_bag(normalized / "uhumans2")


def test_invalid_existing_canonical_directory_is_not_replaced(tmp_path):
    raw, normalized = data_layout(tmp_path)
    (normalized / "spot").mkdir()

    with pytest.raises(RuntimeError, match="refusing to replace"):
        prepare_example_bags.prepare_spot(raw, normalized)


def test_legacy_prepared_demo_is_migrated_to_normalized(tmp_path):
    raw, normalized = data_layout(tmp_path)
    legacy = write_ros2_bag(tmp_path / "prepared" / "demos" / "spot")

    assert prepare_example_bags.prepare_spot(raw, normalized)

    assert not legacy.exists()
    assert prepare_example_bags.is_ros2_bag(normalized / "spot")
    assert not (tmp_path / "prepared").exists()
