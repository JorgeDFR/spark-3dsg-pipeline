# Third-party notices

This integration fetches source at image-build time. It does not vendor upstream
code or redistribute model weights. The authoritative license is always the
`LICENSE` file at the exact revision in `dependencies/locks/`.

| Project | Purpose | Upstream license (repository metadata/file) |
| --- | --- | --- |
| MIT-SPARK/Hydra | 3D scene-graph construction | BSD |
| MIT-SPARK/Hydra-ROS | ROS 2 integration | BSD |
| MIT-SPARK/Khronos | spatio-temporal mapping | BSD-3-Clause |
| MIT-SPARK/Spark-DSG | DSG data structure and Python bindings | BSD |
| MIT-SPARK/semantic_inference | perception frontend | BSD-3-Clause |
| MIT-SPARK/Spark-Config | Python configuration helpers | BSD-3-Clause |
| MIT-SPARK/config_utilities | configuration | BSD-3-Clause |
| MIT-SPARK/Ianvs | ROS/SPARK utilities | BSD-3-Clause |
| MIT-SPARK/Kimera-PGMO | mesh/pose-graph optimization | BSD |
| MIT-SPARK/Kimera-RPGO | robust pose-graph optimization | BSD |
| MIT-SPARK/pose_graph_tools | pose-graph messages/tools | BSD |
| MIT-SPARK/Spatial-Hash | spatial indexing | BSD-3-Clause |
| MIT-SPARK/TEASER-plusplus | registration | MIT |
| Ultralytics/CLIP | YOLOE text prompt encoding | AGPL-3.0 |
| Ternaris/rosbags | ROS 1 to ROS 2 example-bag conversion | Apache-2.0 |
| introlab/RTAB-Map | RGB-D visual odometry | BSD-3-Clause |
| introlab/rtabmap_ros | ROS 2 RTAB-Map integration | BSD-3-Clause |
| rpng/OpenVINS | visual-inertial odometry | GPL-3.0 |
| Stereolabs ZED ROS 2 packages | ZED camera integration | Apache-2.0 |

YOLOE weights are downloaded separately from Ultralytics Assets. Code, weights, and datasets may have terms independent of this repository. Review the [Ultralytics licensing documentation](https://www.ultralytics.com/license) and the terms applicable to your use before downloading or deploying a model.

The public Spot, uHumans2, TUM RGB-D, UoSM-Campus, and D435i validation
datasets are not redistributed here. The downloader only retrieves them from
their publishers. Users are responsible for the source terms, including the
CC-BY-NC-4.0 restriction published with the D435i odometry dataset.

The optional preprocessing image derives from a Stereolabs ZED SDK container.
The SDK is not open-source software and is governed by Stereolabs' separate SDK
license terms. Building or using that image requires accepting the terms
applicable to the selected official base image.
