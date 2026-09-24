from types import SimpleNamespace

import numpy as np

from spark_3dsg_preprocessing.offline_normalize import (
    _lookup_transform,
    _static_graph,
    register_depth,
)


def ns(**values):
    return SimpleNamespace(**values)


def test_static_tf_lookup_uses_existing_sensor_tree():
    transform = ns(
        header=ns(frame_id="camera_link"),
        child_frame_id="camera_optical",
        transform=ns(
            translation=ns(x=1.0, y=0.0, z=0.0),
            rotation=ns(x=0.0, y=0.0, z=0.0, w=1.0),
        ),
    )
    rotation, translation = _lookup_transform(
        _static_graph([ns(transforms=[transform])]),
        "camera_optical",
        "camera_link",
    )
    assert np.allclose(rotation, np.eye(3))
    assert np.allclose(translation, [1.0, 0.0, 0.0])


def test_registered_depth_uses_z_buffer_and_color_dimensions():
    projection = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    info = ns(P=projection, width=2, height=1)
    message = ns(
        encoding="16UC1",
        is_bigendian=0,
        data=np.array([1000, 2000], dtype=np.uint16).view(np.uint8),
        height=1,
        width=2,
        step=4,
        header=ns(frame_id="depth"),
    )
    output = register_depth(
        message,
        info,
        info,
        np.eye(3),
        np.zeros(3),
        1000.0,
        "color",
    )
    assert output.header.frame_id == "color"
    assert output.step == 4
    assert np.array_equal(output.data.view(np.uint16), [1000, 2000])


def test_depth_registration_translates_pixels_and_resolves_occlusion():
    projection = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0.]
    info = ns(P=projection, width=4, height=1)
    message = ns(
        encoding="16UC1", is_bigendian=0,
        data=np.array([1000, 2000, 0, 0], dtype=np.uint16).view(np.uint8),
        height=1, width=4, step=8, header=ns(frame_id="depth"),
    )
    # Both input points land at u=2; only the nearer surface should survive.
    output = register_depth(message, info, info, np.eye(3), np.array([2., 0., 0.]), 1000., "right")
    assert output.header.frame_id == "right"
    assert np.array_equal(output.data.view(np.uint16), [0, 0, 1000, 0])
