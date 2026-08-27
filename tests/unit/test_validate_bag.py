from validate_bag import connected


def test_tf_connectivity_is_bidirectional():
    edges = {("map", "odom"), ("odom", "base_link"), ("base_link", "camera")}
    assert connected(edges, "map", "camera")
    assert connected(edges, "camera", "map")
    assert not connected(edges, "map", "missing")
