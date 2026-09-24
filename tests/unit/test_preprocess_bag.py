from conftest import fixture_config
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import preprocess_bag
from preprocessing_config import resolve_config
from spark_3dsg_preprocessing.config import load_preprocessing, load_source


def test_offline_command_runs_both_relocated_validators(monkeypatch, tmp_path):
    """Exercise orchestration without ROS; validate actual subprocess entry paths."""
    calls = []

    def run(command, **kwargs):
        script = Path(command[1])
        assert script.is_file()
        assert script.parent.name == "python"
        calls.append(script.name)
        return SimpleNamespace(returncode=0, stdout="passed\n", stderr="")

    def materialize(input_path, output_path, source, profile):
        output_path.mkdir()

    monkeypatch.setattr(preprocess_bag.subprocess, "run", run)
    monkeypatch.setattr(preprocess_bag, "materialize_rosbag", materialize)
    raw = tmp_path / "raw"
    raw.mkdir()
    output = tmp_path / "normalized"
    preprocess_bag.run(Namespace(
        source=str(fixture_config("validation_d435i")), preprocessor="recorded_odometry",
        input=raw, output=output, duration=None,
    ))
    assert calls == ["validate_source.py", "validate_bag.py"]
    assert (output / "preprocessing_manifest.yaml").is_file()


def test_registration_backend_waits_and_plays_depth_calibration():
    source = load_source(fixture_config("validation_d435i_register"))
    profile = load_preprocessing(resolve_config("rtabmap_rgbd", "preprocessing"))
    assert "/depth_register" in preprocess_bag.backend_nodes(source, profile)
    topics = preprocess_bag.playback_topics(source, profile)
    assert source["topics"]["depth_camera_info"] in topics
    assert source["topics"]["odometry"] not in topics


def test_detects_component_death_while_launch_parent_stays_alive(tmp_path):
    import pytest

    log = tmp_path / "launch.log"
    log.write_text(
        "[ZED][ERROR] CALIBRATION FILE NOT AVAILABLE\n"
        "[ERROR] [component_container-3]: process has died [exit code 1]\n"
    )
    launch = SimpleNamespace(poll=lambda: None)
    with pytest.raises(RuntimeError, match="CALIBRATION FILE NOT AVAILABLE"):
        preprocess_bag.check_launch(launch, log)


def fake_ros(monkeypatch, spin):
    import sys

    callbacks = {}
    events = []
    node = SimpleNamespace(
        create_subscription=lambda kind, topic, callback, qos: callbacks.setdefault(topic, callback),
        destroy_node=lambda: events.append("destroy"),
    )
    monkeypatch.setitem(sys.modules, "rclpy", SimpleNamespace(
        init=lambda: events.append("init"), create_node=lambda name: node,
        spin_once=lambda node, timeout_sec: spin(callbacks),
        shutdown=lambda: events.append("shutdown"),
    ))
    monkeypatch.setitem(sys.modules, "rclpy.qos", SimpleNamespace(qos_profile_sensor_data=object()))
    monkeypatch.setitem(sys.modules, "sensor_msgs", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "sensor_msgs.msg", SimpleNamespace(CameraInfo=object, Image=object))
    return events


def test_svo_readiness_requires_all_three_streams(monkeypatch, tmp_path):
    received = []

    def spin(callbacks):
        topic = list(callbacks)[len(received)]
        callbacks[topic](object())
        received.append(topic)

    events = fake_ros(monkeypatch, spin)
    preprocess_bag.wait_for_svo_data(SimpleNamespace(poll=lambda: None), 5, tmp_path / "launch.log")
    assert set(received) == {
        "/input/color/image_raw", "/input/color/camera_info", "/input/depth/image_rect",
    }
    assert events == ["init", "destroy", "shutdown"]


def test_svo_readiness_timeout_cleans_up_and_names_missing_streams(monkeypatch, tmp_path):
    import pytest

    events = fake_ros(monkeypatch, lambda callbacks: None)
    with pytest.raises(RuntimeError, match="SVO did not publish RGB-D") as error:
        preprocess_bag.wait_for_svo_data(SimpleNamespace(poll=lambda: None), 0, tmp_path / "launch.log")
    assert "/input/depth/image_rect" in str(error.value)
    assert events == ["init", "destroy", "shutdown"]


def test_zed_profiles_match_recorded_wrapper_optical_frame():
    for name in ("zed2_svo", "zed2i_svo", "zed_rosbag"):
        source = load_source(resolve_config(name, "sources"))
        assert source["frames"]["sensor"] == "zed_left_camera_frame_optical"


def test_child_failure_keeps_fatal_cause_before_warning_spam(tmp_path):
    import pytest

    log = tmp_path / "launch.log"
    log.write_text(
        "[ZED][ERROR] HIGH FREQUENCY SENSORS DATA REQUIRED\n"
        "[FATAL] It's not possible to enable the required Positional Tracking module.\n"
        + "[WARN] invalid sensor data\n" * 50
        + "[ERROR] [component_container]: process has died [exit code -11]\n"
    )
    with pytest.raises(RuntimeError, match="HIGH FREQUENCY SENSORS DATA REQUIRED"):
        preprocess_bag.check_launch(SimpleNamespace(poll=lambda: None), log)


def test_manifest_preserves_source_settings(tmp_path):
    import hashlib
    import yaml

    source_path = resolve_config("zed2i_svo", "sources")
    source = load_source(source_path)
    profile_path = resolve_config("zed_tracking", "preprocessing")
    profile = load_preprocessing(profile_path)
    raw = tmp_path / "recording.svo2"
    raw.write_bytes(b"synthetic fingerprint input")
    output = tmp_path / "output"
    output.mkdir()
    preprocess_bag.write_manifest(output, raw, source_path, profile_path, source, profile)
    # The archived config must remain loadable without any parent files.
    assert load_source(output / "source.yaml") == source
    manifest = yaml.safe_load((output / "preprocessing_manifest.yaml").read_text())
    assert manifest["resolved_source_config_sha256"] == hashlib.sha256(
        yaml.safe_dump(source, sort_keys=True).encode("utf-8")
    ).hexdigest()
