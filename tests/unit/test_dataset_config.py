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
    assert config["topics"]["color"] == "/hamilton/hamilton_zed/rgb/image_rect_color"
    assert config["topics"]["depth"] == "/hamilton/hamilton_zed/depth/depth_registered"
    assert config["frames"]["map"] == "hamilton/map"
    assert config["frames"]["robot"] == "hamilton/base_link"
    assert config["depth_scale"] == 1.0
    assert config["depth_encodings"] == ["32FC1"]
