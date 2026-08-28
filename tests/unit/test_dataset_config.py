import pytest

from dataset_config import REQUIRED_TOPIC_KEYS, get_value, load_config, resolve_config


def test_known_dataset_resolves():
    path = resolve_config("custom_rgbd")
    assert path.name == "custom_rgbd.yaml"
    config = load_config("custom_rgbd")
    assert get_value(config, "frames.sensor") == "camera_color_optical_frame"
    assert config["semantics_source"] == "online"
    assert config["hydra_config"] == "adt4.yaml"


def test_dataset_topics_have_normalized_targets():
    config = load_config("spot")
    assert set(REQUIRED_TOPIC_KEYS).issubset(config["topics"])
    assert config["topics"]["color"] == "/hamilton/hamilton_zed/rgb/image_rect_color"
    assert config["topics"]["depth"] == "/hamilton/hamilton_zed/depth/depth_registered"
    assert config["frames"]["map"] == "hamilton/map"
    assert config["frames"]["robot"] == "hamilton/base_link"
    assert config["depth_scale"] == 1.0
    assert config["depth_encodings"] == ["32FC1"]

    uhumans2 = load_config("uhumans2")
    assert uhumans2["frames"]["map"] == "world"
    assert uhumans2["frames"]["odom"] == "world"
    assert uhumans2["hydra_config"] == "uhumans2.yaml"


def test_dataset_rejects_incomplete_topic_contract(tmp_path):
    config = tmp_path / "incomplete.yaml"
    config.write_text("topics:\n  color: /camera/image_raw\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing topics"):
        load_config(str(config))


def test_dataset_rejects_missing_hydra_profile(tmp_path):
    config = load_config("spot")
    config.pop("hydra_config")
    path = tmp_path / "missing_profile.yaml"
    import yaml

    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(ValueError, match="missing settings: hydra_config"):
        load_config(str(path))
