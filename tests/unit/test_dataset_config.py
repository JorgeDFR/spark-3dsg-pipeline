from dataset_config import NORMALIZED_TOPICS, get_value, load_config, resolve_config


def test_known_dataset_resolves():
    path = resolve_config("custom_rgbd")
    assert path.name == "custom_rgbd.yaml"
    config = load_config("custom_rgbd")
    assert get_value(config, "frames.sensor") == "camera_color_optical_frame"
    assert config["semantics_source"] == "online"


def test_dataset_topics_have_normalized_targets():
    config = load_config("spot")
    assert set(NORMALIZED_TOPICS).issubset(config["topics"])
    assert config["depth_scale"] > 0
