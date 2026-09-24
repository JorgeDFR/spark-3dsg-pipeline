"""Compose sensor normalization with one upstream pose provider."""

from __future__ import annotations

from pathlib import Path

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

from spark_3dsg_preprocessing.config import (
    load_preprocessing,
    load_source,
    static_transforms_for_backend,
    validate_openvins_calibration,
    validate_pair,
    zed_inline_overrides,
)


def _setup(context):
    source_path = Path(LaunchConfiguration("source_config").perform(context))
    profile_path = Path(LaunchConfiguration("preprocessing_config").perform(context))
    source = load_source(source_path)
    profile = load_preprocessing(profile_path)
    validate_pair(source, profile)
    topics = source["topics"]
    frames = source["frames"]
    pose = profile["pose"]
    backend = pose["backend"]
    actions = []
    source_action = None

    for index, transform in enumerate(
        static_transforms_for_backend(source, backend)
    ):
        translation = transform.get("translation", [0.0, 0.0, 0.0])
        rotation = transform.get("rotation", [0.0, 0.0, 0.0, 1.0])
        actions.append(
            Node(
                package="tf2_ros",
                executable="static_transform_publisher",
                name=f"source_static_transform_{index}",
                output="screen",
                arguments=[
                    "--x", str(translation[0]),
                    "--y", str(translation[1]),
                    "--z", str(translation[2]),
                    "--qx", str(rotation[0]),
                    "--qy", str(rotation[1]),
                    "--qz", str(rotation[2]),
                    "--qw", str(rotation[3]),
                    "--frame-id", transform["parent"],
                    "--child-frame-id", transform["child"],
                ],
                parameters=[
                    {"use_sim_time": LaunchConfiguration("use_sim_time")}
                ],
            )
        )

    if source["input_kind"] == "zed_svo":
        zed_share = get_package_share_directory("zed_wrapper")
        source_action = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                str(Path(zed_share) / "launch" / "zed_camera.launch.py")
            ),
            launch_arguments={
                "camera_model": source.get("zed", {}).get("camera_model", "zed2i"),
                "camera_name": source.get("zed", {}).get("camera_name", "zed"),
                "svo_path": LaunchConfiguration("input_path"),
                # The SVO source produces /clock; it must not wait on its own
                # clock. Relays and estimators still consume simulation time.
                "use_sim_time": "false",
                "publish_svo_clock": "true",
                "publish_tf": "true" if backend == "zed_tracking" else "false",
                "publish_map_tf": "false",
                "param_overrides": zed_inline_overrides(source, profile),
            }.items(),
        )

    registering = source["depth"]["mode"] == "register"
    relay_parameters = {
        "color_topic": topics["color"],
        "color_info_topic": topics["color_camera_info"],
        "depth_topic": topics["depth"],
        "depth_info_topic": topics.get("depth_camera_info", ""),
        "imu_topic": topics.get("imu", ""),
        "output_depth_topic": (
            "/preprocess/depth/image_rect"
            if registering
            else "/input/depth/image_rect"
        ),
        "output_depth_info_topic": "/preprocess/depth/camera_info",
        "color_frame_id": frames["sensor"],
        "depth_frame_id": "" if registering else frames["sensor"],
        "use_sim_time": LaunchConfiguration("use_sim_time"),
    }
    actions.append(
        Node(
            package="spark_3dsg_preprocessing",
            executable="rgbd_relay",
            name="rgbd_relay",
            output="screen",
            parameters=[relay_parameters],
        )
    )

    if registering:
        actions.append(
            Node(
                package="depth_image_proc",
                executable="register_node",
                name="depth_register",
                output="screen",
                parameters=[{"use_sim_time": LaunchConfiguration("use_sim_time")}],
                remappings=[
                    ("depth/image_rect", "/preprocess/depth/image_rect"),
                    ("depth/camera_info", "/preprocess/depth/camera_info"),
                    ("rgb/camera_info", "/input/color/camera_info"),
                    ("depth_registered/image_rect", "/input/depth/image_rect"),
                ],
            )
        )

    common_parameters = {"use_sim_time": LaunchConfiguration("use_sim_time")}
    if backend == "recorded_odometry":
        actions.append(
            Node(
                package="spark_3dsg_preprocessing",
                executable="odometry_to_tf",
                name="recorded_odometry_to_tf",
                output="screen",
                parameters=[
                    common_parameters,
                    {
                        "input_topic": topics["odometry"],
                        "odom_frame": frames["odom"],
                        "robot_frame": frames["robot"],
                    },
                ],
            )
        )
    elif backend == "rtabmap_rgbd":
        actions.extend(
            [
                Node(
                    package="rtabmap_sync",
                    executable="rgbd_sync",
                    name="rtabmap_rgbd_sync",
                    output="screen",
                    parameters=[
                        common_parameters,
                        {
                            "approx_sync": profile["synchronization"]["approximate"],
                            "approx_sync_max_interval": profile["synchronization"].get(
                                "max_interval", 0.0
                            ),
                            "topic_queue_size": profile["synchronization"].get(
                                "queue_size", 20
                            ),
                            "sync_queue_size": profile["synchronization"].get(
                                "queue_size", 20
                            ),
                            "qos": 1,
                            "qos_camera_info": 1,
                        },
                    ],
                    remappings=[
                        ("rgb/image", "/input/color/image_raw"),
                        ("depth/image", "/input/depth/image_rect"),
                        ("rgb/camera_info", "/input/color/camera_info"),
                        ("rgbd_image", "/preprocess/rgbd_image"),
                    ],
                ),
                Node(
                    package="rtabmap_odom",
                    executable="rgbd_odometry",
                    name="rgbd_odometry",
                    output="screen",
                    parameters=[
                        common_parameters,
                        {
                            "frame_id": frames["robot"],
                            "odom_frame_id": frames["odom"],
                            "publish_tf": True,
                            "subscribe_depth": False,
                            "subscribe_rgb": False,
                            "subscribe_rgbd": True,
                            "wait_for_transform": 1.0,
                            "always_process_most_recent_frame": False,
                            "approx_sync": profile["synchronization"]["approximate"],
                            "approx_sync_max_interval": profile["synchronization"].get(
                                "max_interval", 0.0
                            ),
                            "topic_queue_size": profile["synchronization"].get(
                                "queue_size", 20
                            ),
                            "sync_queue_size": profile["synchronization"].get(
                                "queue_size", 20
                            ),
                            "qos": 1,
                            "qos_camera_info": 1,
                            "qos_imu": 2,
                        },
                        pose.get("parameters", {}),
                    ],
                    remappings=[
                        ("rgbd_image", "/preprocess/rgbd_image"),
                        ("odom", "/input/odometry"),
                    ],
                ),
            ]
        )
    elif backend == "openvins":
        calibration_path = Path(pose["calibration"]).expanduser()
        validate_openvins_calibration(
            calibration_path, pose.get("max_cameras", 1)
        )
        calibration = str(calibration_path)
        actions.extend(
            [
                Node(
                    package="ov_msckf",
                    executable="run_subscribe_msckf",
                    namespace="openvins",
                    name="estimator",
                    output="screen",
                    parameters=[
                        common_parameters,
                        {
                            "config_path": calibration,
                            "verbosity": pose.get("verbosity", "INFO"),
                            "use_stereo": pose.get("max_cameras", 1) == 2,
                            "max_cameras": pose.get("max_cameras", 1),
                        },
                    ],
                    remappings=[
                        ("/imu0", topics["imu"]),
                        ("/cam0/image_raw", topics["color"]),
                        (
                            "/cam1/image_raw",
                            topics.get("color_right", "/input/color_right/image_raw"),
                        ),
                    ],
                ),
                Node(
                    package="spark_3dsg_preprocessing",
                    executable="odometry_to_tf",
                    name="openvins_odometry_to_tf",
                    output="screen",
                    parameters=[
                        common_parameters,
                        {
                            "input_topic": "/openvins/odomimu",
                            "odom_frame": frames["odom"],
                            "robot_frame": frames["imu"],
                        },
                    ],
                ),
            ]
        )
    # existing_tf and zed_tracking already publish odom -> robot. Delay SVO
    # replay until relays and estimators have created their subscriptions.
    if source_action is not None:
        actions.append(TimerAction(period=2.0, actions=[source_action]))
    return actions


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("source_config"),
            DeclareLaunchArgument("preprocessing_config"),
            DeclareLaunchArgument("input_path", default_value=""),
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            OpaqueFunction(function=_setup),
        ]
    )
