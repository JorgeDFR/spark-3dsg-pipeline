# Custom sensor or bag

1. Copy `src/spark_3dsg_pipeline/config/datasets/custom_rgbd.yaml` to a descriptive dataset name.
2. Set the original bag topics and exact TF frame IDs.
3. Set `depth_scale` and permitted encodings.
4. Choose `semantics_source: online` or `precomputed`.
5. Build the appropriate image and validate the bag.

```bash
make validate-bag PROFILE=core DATASET=my_robot BAG=/home/spark/data/my_robot
```

Resolve every error before mapping. Warnings mean bounded sampling could not prove a property and should be checked with `ros2 bag info`/`ros2 bag play` inside `make shell`.

Then run the same core launch:

```bash
make run PROFILE=gpu DATASET=my_robot BAG=/home/spark/data/my_robot
```

Do not add dataset conditions to `pipeline.launch.yaml`. Topic normalization belongs in the adapter/bag remaps. Image registration, calibration, odometry generation, and missing TF publication are upstream sensor-pipeline responsibilities.
