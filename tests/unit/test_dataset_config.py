from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from dataset_config import (
    REQUIRED_TOPIC_KEYS,
    get_value,
    load_config,
    resolve_config,
    validate_config,
    validate_hydra_config,
    validate_runtime_resources,
)


def test_dataset_dimensions_resolve_independently():
    expected = {
        "custom_rgbd": ("hierarchical", "closed_set", "hierarchical", "classic.yaml"),
        "uhumans2": ("hierarchical", "recorded", "hierarchical", "uhumans2.yaml"),
        "spot": ("khronos", "open_set", "khronos", "adt4.yaml"),
    }
    for name, values in expected.items():
        config = load_config(name)
        assert (
            config["scene_structure"],
            config["semantics"]["source"],
            config["visualization"]["profile"],
            config["hydra_config"],
        ) == values


def test_known_dataset_and_dotted_query_resolve():
    assert resolve_config("custom_rgbd").name == "custom_rgbd.yaml"
    config = load_config("custom_rgbd")
    assert get_value(config, "frames.sensor") == "camera_color_optical_frame"
    assert get_value(config, "semantics.labelspace_name") == "ade20k_mit"


def test_dataset_topics_have_normalized_contract():
    for name in ("spot", "custom_rgbd", "uhumans2"):
        assert set(REQUIRED_TOPIC_KEYS).issubset(load_config(name)["topics"])
    assert load_config("uhumans2")["topics"]["semantic"].startswith("/tesse/")
    assert "semantic" not in load_config("spot")["topics"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            {
                "scene_structure": "khronos",
                "visualization": {"profile": "khronos"},
            },
            "incompatible",
        ),
        ({"visualization": {"profile": "khronos"}}, "does not match"),
        ({"semantics": {"source": "closed_set"}}, "is missing"),
    ],
)
def test_invalid_dimension_combinations_fail_early(change, message):
    config = deepcopy(load_config("custom_rgbd"))
    config.update(change)
    with pytest.raises(ValueError, match=message):
        validate_config(config)


def test_recorded_semantics_requires_bag_semantic_topic():
    config = deepcopy(load_config("uhumans2"))
    config["topics"].pop("semantic")
    with pytest.raises(ValueError, match="topics.semantic"):
        validate_config(config)


def test_hydra_override_must_match_explicit_dimensions(tmp_path):
    incompatible = tmp_path / "wrong.yaml"
    incompatible.write_text(
        """
input: {inputs: {camera: {receiver: {type: InstanceImageReceiver}}}}
active_window: {type: ActiveWindow}
backend: {update_functors: {objects: {type: GenericUpdateFunctor}}}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="requires ClosedSetImageReceiver"):
        validate_hydra_config(load_config("custom_rgbd"), incompatible)


def test_dataset_rejects_incomplete_topic_contract(tmp_path):
    config = tmp_path / "incomplete.yaml"
    config.write_text("topics:\n  color: /camera/image_raw\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing topics"):
        load_config(str(config))


def test_runtime_validation_reports_closed_set_components(tmp_path):
    config = load_config("custom_rgbd")
    shares = {
        "spark_3dsg_pipeline": tmp_path / "pipeline",
        "semantic_inference_ros": tmp_path / "semantic",
        "hydra": tmp_path / "hydra",
    }
    with pytest.raises(FileNotFoundError) as caught:
        validate_runtime_resources(config, shares, tmp_path / "models")
    message = str(caught.value)
    assert "closed-set model not found" in message
    assert "semantic-inference model config not found" in message
    assert "semantic-inference grouping not found" in message
    assert "Hydra label-space config not found" in message
    assert "make models PROFILE=gpu" in message


def test_runtime_validation_accepts_complete_open_set_resources(tmp_path):
    config = load_config("spot")
    shares = {
        "spark_3dsg_pipeline": tmp_path / "pipeline",
        "semantic_inference_ros": tmp_path / "semantic",
        "hydra": tmp_path / "hydra",
    }
    paths = [
        shares["spark_3dsg_pipeline"] / "config/hydra/adt4.yaml",
        shares["spark_3dsg_pipeline"] / "config/visualization/khronos.yaml",
        shares["spark_3dsg_pipeline"] / "config/perception/yoloe.yaml",
        shares["spark_3dsg_pipeline"] / "config/perception/labels/adt4.yaml",
        shares["spark_3dsg_pipeline"] / "config/labelspaces/from_message.yaml",
        shares["spark_3dsg_pipeline"] / "config/labelspaces/no_remap.yaml",
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n{}\n", encoding="utf-8")
    resolved = validate_runtime_resources(config, shares, tmp_path / "models")
    assert resolved["open-set labels config"].name == "adt4.yaml"
