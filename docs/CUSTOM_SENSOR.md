# Dataset adapter reference

A dataset adapter describes a bag's topics, frames, depth units, and playback.
Use the [custom dataset guide](CUSTOM_DATASET.md) for the complete workflow.
Mapping recipes independently select semantics, graph structure, and visualization.

## Create an adapter

Copy the normalized RGB-D example into `data/custom-configs`:

```bash
cp src/spark_3dsg_pipeline/config/datasets/custom_rgbd.yaml data/custom-configs/my_sensor.yaml
```

With an external `DATA_DIR`, copy to that root's `custom-configs` directory.
Pass the edited file as
`DATASET=/home/spark/data/custom-configs/my_sensor.yaml`.

The example uses normalized `/input/...` topics. Change its fields to match
the actual recording, including frames and depth units.

## Topics

| Field | Required data |
| --- | --- |
| `topics.color` | RGB `sensor_msgs/msg/Image` |
| `topics.depth` | Depth image registered to the color image |
| `topics.camera_info` | Intrinsics for the color image |
| `topics.tf` | Dynamic transforms, normally `/tf` |
| `topics.tf_static` | Static transforms, normally `/tf_static` |
| `topics.semantic` | Class-ID image (only required for recorded semantics) |

Color, depth, and camera information must be synchronized closely enough for
RGB-D reconstruction. CameraInfo must contain positive image dimensions and
focal lengths. See the [input contract](INPUT_CONTRACT.md) for normalized names
and message types.

## Frames

| Field | Meaning |
| --- | --- |
| `frames.map` | Global mapping frame |
| `frames.odom` | Odometry frame |
| `frames.robot` | Tracked body frame |
| `frames.sensor` | Color camera optical frame |

The bag must provide connected `odom → robot → sensor` transform paths.
A recorded `map → odom` transform is optional and must not compete with another
broadcaster. Frame names must match the recorded transforms. Renaming a frame
in YAML does not create an extrinsic transform.

## Depth and playback

| Field | Meaning |
| --- | --- |
| `depth_encodings` | Accepted image encodings, usually `16UC1`, `32FC1`, or both |
| `depth_scale` | Units per meter (`1000.0` for millimeters, `1.0` for meters) |
| `playback_rate` | Bag playback speed |
| `use_sim_time` | Simulation-time behavior |

Timestamps must increase monotonically. Depth must already use color-image
geometry. An adapter cannot register depth or generate missing poses.

## Validate the adapter

```bash
make validate-bag PROFILE=core MAPPING=closed_set \
  DATASET=/home/spark/data/custom-configs/my_sensor.yaml \
  BAG=/home/spark/data/normalized/my_sensor
```

If the bag lacks required inputs, follow [preprocessing](PREPROCESSING.md).
Select a [mapping recipe](DATASETS.md#mapping-recipes) independently.
The supplied `recorded` recipe expects uHumans2 class IDs and matching remap
files. Other datasets normally use `closed_set` or `open_set`.
