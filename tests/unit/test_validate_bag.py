from validate_bag import Report, connected, connected_component, tf_paths_connected


def test_tf_connectivity_is_bidirectional():
    edges = {("map", "odom"), ("odom", "base_link"), ("base_link", "camera")}
    assert connected(edges, "map", "camera")
    assert connected(edges, "camera", "map")
    assert not connected(edges, "map", "missing")


def test_tf_component_reports_reachable_frames():
    edges = {
        ("map", "robot/map"),
        ("robot/map", "robot/odom"),
        ("robot/body", "robot/base_link"),
    }
    assert connected_component(edges, "map") == {"map", "robot/map", "robot/odom"}
    assert not connected(edges, "robot/map", "robot/base_link")


def test_sampling_requires_odometry_and_sensor_tf_paths_not_map():
    paths = (("robot/odom", "robot/base_link"), ("robot/base_link", "camera"))
    early_edges = {
        ("robot/body", "robot/base_link"),
        ("robot/base_link", "camera"),
        ("camera", "camera_optical"),
    }
    assert not tf_paths_connected(early_edges, paths)

    complete_edges = early_edges | {
        ("robot/odom", "robot/body"),
    }
    assert tf_paths_connected(complete_edges, paths)


def test_informational_messages_do_not_increment_warning_count(capsys):
    report = Report()
    report.info("optional transform is absent")
    assert report.warnings == 0
    assert "optional transform is absent" in capsys.readouterr().out
