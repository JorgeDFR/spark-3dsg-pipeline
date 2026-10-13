import numpy as np
import pytest
from rosbags.highlevel import AnyReader
from rosbags.rosbag2 import Writer
import yaml

from spark_3dsg_preprocessing.config import load_preprocessing
from spark_3dsg_preprocessing.offline_normalize import (
    DEFAULT_TYPESTORE, _rotation, materialize_rosbag,
)
from spark_3dsg_preprocessing.trajectory import load_trajectory, quaternion_from_rotation


def settings(tmp_path, text, **kwargs):
    path = tmp_path / "poses.txt"
    path.write_text(text)
    return {"path": str(path), "frame": "lidar", "max_gap": 2.0, **kwargs}


def test_interpolation_uses_nanoseconds_linear_translation_and_shortest_slerp(tmp_path):
    cfg = settings(tmp_path,
                   "1700000000.000000001 0 0 0 0 0 0 2\n"
                   "1700000002.000000001 2 0 0 0 0 -1 -1\n")
    poses = load_trajectory(cfg)
    assert poses.timestamps[0] == 1700000000000000001
    position, quaternion = poses.sample(1700000001000000001)
    assert np.allclose(position, [1, 0, 0])
    assert np.allclose(quaternion, [0, 0, np.sin(np.pi / 8), np.cos(np.pi / 8)])


@pytest.mark.parametrize("text,match", [
    ("1 0 0 0 0 0 0 0\n2 0 0 0 0 0 0 1", "quaternion"),
    ("1 nan 0 0 0 0 0 1\n2 0 0 0 0 0 0 1", "finite"),
    ("1 0 0 0 0 0 0 1\n1 0 0 0 0 0 0 1", "strictly increasing"),
    ("2 0 0 0 0 0 0 1\n1 0 0 0 0 0 0 1", "strictly increasing"),
    ("1 0 0 0\n2 0 0 0", "expected timestamp"),
    ("1 0 0 0 0 0 0 1", "at least two"),
    ("nan 0 0 0 0 0 0 1\n2 0 0 0 0 0 0 1", "finite"),
])
def test_invalid_trajectory_is_rejected(tmp_path, text, match):
    with pytest.raises(ValueError, match=match):
        load_trajectory(settings(tmp_path, text))


def test_no_extrapolation_or_interpolation_across_large_gaps(tmp_path):
    cfg = settings(tmp_path, "1 0 0 0 0 0 0 1\n5 4 0 0 0 0 0 1", time_offset=1)
    poses = load_trajectory(cfg)
    with pytest.raises(ValueError, match="outside"):
        poses.sample(1_000_000_000)
    with pytest.raises(ValueError, match="gap"):
        poses.sample(3_000_000_000)
    cfg["missing"] = "drop"
    poses = load_trajectory(cfg)
    assert poses.sample(7_000_000_000) is None
    assert poses.sample(3_000_000_000) is None
    assert np.allclose(poses.sample(2_000_000_000)[0], [0, 0, 0])


@pytest.mark.parametrize("angle", [0., np.pi / 2, np.pi, -np.pi / 2])
def test_static_rotation_conversion_handles_half_turns(angle):
    from types import SimpleNamespace

    rotation = np.array([[np.cos(angle), -np.sin(angle), 0],
                         [np.sin(angle), np.cos(angle), 0], [0, 0, 1]])
    quaternion = quaternion_from_rotation(rotation)
    result = _rotation(SimpleNamespace(**dict(zip(("x", "y", "z", "w"), quaternion))))
    assert np.allclose(result, rotation, atol=1e-12)


@pytest.mark.parametrize("change,match", [
    ({"frame": None}, "explicit frame"),
    ({"max_gap": 0}, "positive"),
    ({"max_gap": float("nan")}, "finite"),
    ({"time_offset": float("inf")}, "finite"),
    ({"format": "kitti"}, "format"),
    ({"missing": "extrapolate"}, "missing"),
])
def test_config_requires_explicit_frame_and_valid_policies(tmp_path, change, match):
    cfg = {"name": "external", "pose": {"backend": "external_trajectory",
           "trajectory": {"path": "/poses.txt", "frame": "lidar", "max_gap": 1, **change}},
           "synchronization": {"approximate": False}}
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ValueError, match=match):
        load_preprocessing(path)


def synthetic_bag(path):
    store = DEFAULT_TYPESTORE
    types = store.types
    def header(second, frame):
        return types["std_msgs/msg/Header"](types["builtin_interfaces/msg/Time"](second, 0), frame)
    transforms = []
    for child, translation in [("lidar", [1., 0., 0.]), ("camera", [0., 0., 0.])]:
        transforms.append(types["geometry_msgs/msg/TransformStamped"](
            header(0, "robot"), child, types["geometry_msgs/msg/Transform"](
                types["geometry_msgs/msg/Vector3"](*translation),
                types["geometry_msgs/msg/Quaternion"](0., 0., 0., 1.),
            )))
    with Writer(path, version=9) as writer:
        tf_conn = writer.add_connection("/tf_static", "tf2_msgs/msg/TFMessage", typestore=store)
        tf = types["tf2_msgs/msg/TFMessage"](transforms)
        writer.write(tf_conn, 0, store.serialize_cdr(tf, tf.__msgtype__))
        color_conn = writer.add_connection("/rgb", "sensor_msgs/msg/Image", typestore=store)
        depth_conn = writer.add_connection("/depth", "sensor_msgs/msg/Image", typestore=store)
        for second in [1, 2, 3]:
            for conn, encoding, step in [(color_conn, "rgb8", 3), (depth_conn, "16UC1", 2)]:
                message = types["sensor_msgs/msg/Image"](
                    header(second, "camera"), 1, 1, encoding, 0, step, np.zeros(step, dtype=np.uint8)
                )
                # Deliberately differ from image timestamps to detect wrong clock use.
                writer.write(conn, (second + 10) * 1_000_000_000,
                             store.serialize_cdr(message, message.__msgtype__))
    return {"topics": {"color": "/rgb", "depth": "/depth", "color_camera_info": "/info",
                       "tf_static": "/tf_static"},
            "frames": {"odom": "odom", "robot": "robot", "sensor": "camera"},
            "depth": {"mode": "registered"}}


def test_offline_external_trajectory_converts_sensor_pose_and_drops_uncovered_images(tmp_path):
    raw = tmp_path / "raw"
    source = synthetic_bag(raw)
    cfg = settings(tmp_path, "0 10 0 0 0 0 0 1\n2 10 0 0 0 0 1 0", missing="drop")
    output = tmp_path / "out"
    materialize_rosbag(raw, output, source,
                       {"pose": {"backend": "external_trajectory", "trajectory": cfg}})
    with AnyReader([output]) as reader:
        messages = [(c.topic, t, reader.deserialize(v, c.msgtype)) for c, t, v in reader.messages()]
    odom = [(t, m) for topic, t, m in messages if topic == "/input/odometry"]
    assert len(odom) == 2
    timestamp, message = odom[0]
    assert timestamp == 11_000_000_000
    assert message.header.stamp.sec == 1
    assert message.header.frame_id == "odom" and message.child_frame_id == "robot"
    # World->lidar has yaw=90deg, robot->lidar has +1m along robot X.
    assert np.allclose([message.pose.pose.position.x, message.pose.pose.position.y,
                        message.pose.pose.position.z], [10, -1, 0])
    assert np.allclose(_rotation(message.pose.pose.orientation),
                       [[0, -1, 0], [1, 0, 0], [0, 0, 1]], atol=1e-12)
    assert len([1 for topic, _, _ in messages if topic == "/tf"]) == 2
    report = yaml.safe_load((output / "trajectory_usage.yaml").read_text())
    assert report["dropped_messages"] == {"/input/color/image_raw": 1, "/input/depth/image_rect": 1}


def test_disconnected_trajectory_frame_fails_before_writing_images(tmp_path):
    raw = tmp_path / "raw"
    source = synthetic_bag(raw)
    cfg = settings(tmp_path, "0 0 0 0 0 0 0 1\n2 0 0 0 0 0 0 1", frame="unknown")
    with pytest.raises(ValueError, match="no static TF path"):
        materialize_rosbag(raw, tmp_path / "out", source,
                           {"pose": {"backend": "external_trajectory", "trajectory": cfg}})
