from conftest import fixture_config
from pathlib import Path

import pytest
import yaml

from preprocess_bag import (
    backend_nodes,
    generated_dataset,
    input_fingerprint,
    playback_topics,
)
from preprocessing_config import resolve_config
from spark_3dsg_preprocessing.config import (
    load_preprocessing,
    load_source,
    static_transforms_for_backend,
    validate_openvins_calibration,
    validate_pair,
)


def test_generic_rtabmap_pair_is_valid():
    source = load_source(resolve_config("generic_rgbd", "sources"))
    profile = load_preprocessing(resolve_config("rtabmap_rgbd", "preprocessing"))
    validate_pair(source, profile)
    assert profile["pose"]["backend"] == "rtabmap_rgbd"


def test_unregistered_depth_requires_depth_camera_info(tmp_path: Path):
    config = yaml.safe_load(
        resolve_config("generic_rgbd_unregistered", "sources").read_text()
    )
    del config["topics"]["depth_camera_info"]
    path = tmp_path / "source.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError, match="depth registration requires"):
        load_source(path)


def test_pose_provider_requirements_are_fail_fast():
    source = load_source(resolve_config("generic_rgbd", "sources"))
    recorded = load_preprocessing(
        resolve_config("recorded_odometry", "preprocessing")
    )
    with pytest.raises(ValueError, match="topics.odometry"):
        validate_pair(source, recorded)


def test_zed_tracking_is_only_valid_for_svo():
    bag = load_source(resolve_config("zed_rosbag", "sources"))
    svo = load_source(resolve_config("zed2i_svo", "sources"))
    tracking = load_preprocessing(resolve_config("zed_tracking", "preprocessing"))
    with pytest.raises(ValueError, match="zed_svo"):
        validate_pair(bag, tracking)
    validate_pair(svo, tracking)


def test_svo_rejects_recorded_pose_profiles():
    svo = load_source(resolve_config("zed2i_svo", "sources"))
    passthrough = load_preprocessing(resolve_config("passthrough", "preprocessing"))
    with pytest.raises(ValueError, match="cannot provide pose"):
        validate_pair(svo, passthrough)


def test_validation_sources_cover_public_sensor_variants():
    zed2 = load_source(resolve_config("zed2_svo", "sources"))
    zed2i = load_source(resolve_config("zed2i_svo", "sources"))
    d435i = load_source(fixture_config("validation_d435i"))
    tum = load_source(fixture_config("validation_tum_fr1"))
    assert zed2["zed"]["camera_model"] == "zed2"
    assert zed2i["zed"]["camera_model"] == "zed2i"
    assert d435i["depth"]["mode"] == "registered"
    assert d435i["topics"]["color_right"].endswith("infra2/image_rect_raw")
    assert d435i["static_transforms"]
    assert {
        transform["parent"]
        for transform in static_transforms_for_backend(d435i, "rtabmap_rgbd")
    } == set()
    assert {
        transform["parent"]
        for transform in static_transforms_for_backend(d435i, "openvins")
    } == {"mavros_imu_frame"}
    assert tum["depth"]["accepted_encodings"] == ["32FC1"]
    assert tum["static_transforms"]


def test_static_transform_shape_is_validated(tmp_path: Path):
    config = yaml.safe_load(
        fixture_config("validation_d435i").read_text()
    )
    config["static_transforms"][0]["rotation"] = [0.0, 1.0]
    path = tmp_path / "source.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError, match="rotation must have 4 numbers"):
        load_source(path)


def test_static_transform_backend_is_validated(tmp_path: Path):
    config = yaml.safe_load(
        fixture_config("validation_d435i").read_text()
    )
    config["static_transforms"][0]["backends"] = ["not_a_backend"]
    path = tmp_path / "source.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError, match="supported pose backends"):
        load_source(path)


def test_rtabmap_sync_interval_is_bounded():
    profile = load_preprocessing(resolve_config("rtabmap_rgbd", "preprocessing"))
    assert profile["synchronization"]["max_interval"] == 0.05


def test_generated_dataset_uses_normalized_topics_and_source_frames(tmp_path: Path):
    source = load_source(resolve_config("zed_rosbag", "sources"))
    profile = load_preprocessing(resolve_config("rtabmap_rgbd", "preprocessing"))
    path = generated_dataset(source, profile, tmp_path)
    dataset = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert dataset["topics"]["color"] == "/input/color/image_raw"
    assert dataset["topics"]["depth"] == "/input/depth/image_rect"
    assert dataset["frames"]["robot"] == "zed_camera_link"
    assert dataset["frames"]["odom"] == "odom"


def test_d435i_uses_existing_camera_tree_root_as_robot_frame(tmp_path: Path):
    source = load_source(fixture_config("validation_d435i"))
    assert source["frames"]["robot"] == "camera_link"
    assert "rtabmap_robot" not in source["frames"]
    profile = load_preprocessing(resolve_config("rtabmap_rgbd", "preprocessing"))
    path = generated_dataset(source, profile, tmp_path)
    dataset = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert dataset["frames"]["robot"] == "camera_link"
    assert dataset["frames"]["sensor"] == "camera_infra1_optical_frame"


def test_visual_odometry_playback_excludes_recorded_dynamic_tf():
    source = load_source(resolve_config("generic_rgbd", "sources"))
    profile = load_preprocessing(resolve_config("rtabmap_rgbd", "preprocessing"))
    topics = playback_topics(source, profile)
    assert source["topics"]["tf"] not in topics
    assert source["topics"]["tf_static"] in topics
    assert "/camera/imu" not in topics


def test_openvins_calibration_checks_companions_and_camera_count(tmp_path: Path):
    estimator = tmp_path / "estimator_config.yaml"
    estimator.write_text(
        'relative_config_imu: "imu.yaml"\n'
        'relative_config_imucam: "imucam.yaml"\n',
        encoding="utf-8",
    )
    (tmp_path / "imu.yaml").write_text("imu0:\n  rostopic: /imu\n", encoding="utf-8")
    (tmp_path / "imucam.yaml").write_text("cam0:\n  camera_model: pinhole\n", encoding="utf-8")
    validate_openvins_calibration(estimator, 1)
    with pytest.raises(ValueError, match="cam1"):
        validate_openvins_calibration(estimator, 2)


def test_runner_waits_for_selected_backend_before_playback():
    source = load_source(resolve_config("generic_rgbd", "sources"))
    profile = load_preprocessing(resolve_config("rtabmap_rgbd", "preprocessing"))
    assert backend_nodes(source, profile) == [
        "/rgbd_relay",
        "/rtabmap_rgbd_sync",
        "/rgbd_odometry",
    ]


def test_input_fingerprint_covers_names_and_content(tmp_path: Path):
    (tmp_path / "metadata.yaml").write_text("value: 1\n", encoding="utf-8")
    first = input_fingerprint(tmp_path)
    (tmp_path / "data.mcap").write_bytes(b"bag")
    second = input_fingerprint(tmp_path)
    assert first["sha256"] != second["sha256"]
    assert second["files"] == 2
    assert second["bytes"] == len("value: 1\n") + 3


def test_legacy_lake_uses_visual_tracking_but_modern_svo_keeps_defaults():
    from preprocessing_config import resolve_config
    from spark_3dsg_preprocessing.config import zed_parameter_overrides, zed_inline_overrides

    legacy = load_source(fixture_config("validation_zed2_lake"))
    modern = load_source(resolve_config("zed2i_svo", "sources"))
    profile = load_preprocessing(resolve_config("zed_tracking", "preprocessing"))
    parameters = zed_parameter_overrides(legacy, profile)
    assert parameters["pos_tracking.pos_tracking_mode"] == "GEN_1"
    assert parameters["pos_tracking.imu_fusion"] is False
    assert parameters["pos_tracking.set_gravity_as_origin"] is False
    assert parameters["sensors.sensors_image_sync"] is True
    assert parameters["sensors.publish_imu"] is False
    assert "imu" not in legacy["topics"]
    assert "pos_tracking.pos_tracking_enabled" not in parameters
    assert zed_parameter_overrides(modern, profile) == {}
    assert "pos_tracking.imu_fusion:=false" in zed_inline_overrides(legacy, profile)
    assert zed_inline_overrides(modern, profile) == ""


def test_rtabmap_disables_zed_tracker_and_its_depth_stabilization_trigger():
    from preprocessing_config import resolve_config
    from spark_3dsg_preprocessing.config import zed_parameter_overrides

    profile = load_preprocessing(resolve_config("rtabmap_rgbd", "preprocessing"))
    for name in (str(fixture_config("validation_zed2_lake")), "zed2_svo", "zed2i_svo"):
        source = load_source(resolve_config(name, "sources"))
        parameters = zed_parameter_overrides(source, profile)
        assert parameters["pos_tracking.pos_tracking_enabled"] is False
        assert parameters["depth.depth_stabilization"] == 0


def test_legacy_svo_flag_rejects_string_false(tmp_path):
    from preprocessing_config import resolve_config

    config = load_source(resolve_config("zed2_svo", "sources"))
    config["zed"]["legacy_svo"] = "false"
    path = tmp_path / "source.yaml"
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match="legacy_svo must be boolean"):
        load_source(path)


def test_all_camera_profiles_resolve_without_validation_data():
    directory = resolve_config("generic_rgbd", "sources").parent.parent
    paths = list(directory.rglob("*.yaml"))
    assert paths
    for path in paths:
        assert "extends" not in yaml.safe_load(path.read_text())
        source = load_source(path)
        assert source["name"] == path.stem
        assert "validation" not in str(source)
        validate_pair(source, load_preprocessing(resolve_config("rtabmap_rgbd", "preprocessing")))
    assert not (directory / "zed_svo.yaml").exists()


def test_family_and_short_profile_names_select_same_file():
    short = resolve_config("realsense_d455", "sources")
    assert short == resolve_config("intel-realsense/realsense_d455", "sources")
    assert short == resolve_config("intel-realsense/realsense_d455.yaml", "sources")


def test_profile_lookup_rejects_ambiguous_names_and_missing_paths(tmp_path, monkeypatch):
    import preprocessing_config

    for family in ("first", "second"):
        directory = tmp_path / family
        directory.mkdir()
        (directory / "camera.yaml").write_text("name: camera\n")
    monkeypatch.setattr(preprocessing_config, "config_directory", lambda kind: tmp_path)
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_config("camera", "sources")
    assert resolve_config("first/camera", "sources") == tmp_path / "first/camera.yaml"
    # A typo in a qualified path must not silently select another camera profile.
    with pytest.raises(FileNotFoundError):
        resolve_config("missing/camera", "sources")


def test_package_installs_all_camera_family_profiles(monkeypatch):
    import runpy
    import sys
    from types import SimpleNamespace

    package = resolve_config("generic_rgbd", "sources").parents[3]
    captured = {}
    monkeypatch.chdir(package)
    monkeypatch.setitem(sys.modules, "setuptools", SimpleNamespace(
        find_packages=lambda: [], setup=lambda **kwargs: captured.update(kwargs),
    ))
    runpy.run_path(str(package / "setup.py"))
    installed = {
        source: destination
        for destination, sources in captured["data_files"]
        for source in sources
        if source.startswith("config/sources/")
    }
    expected = {str(path) for path in Path("config/sources").rglob("*.yaml")}
    assert expected
    assert set(installed) == expected
    for source, destination in installed.items():
        assert destination == f"share/spark_3dsg_preprocessing/{Path(source).parent}"
