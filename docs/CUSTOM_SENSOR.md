# Custom RGB-D sensor

Copy `config/datasets/custom_rgbd.yaml` and change source topics, frames, depth
scale/encodings, and playback rate. Keep the dimensions explicit:

```yaml
scene_structure: hierarchical
semantics:
  source: closed_set
  model_file: ade20k-efficientvit_seg_l2.onnx
  model_config: semantic_inference_ros:config/models/ade20k-efficientvit_seg_l2.yaml
  labelspace_name: ade20k_mit
  grouping_config: semantic_inference_ros:config/label_groupings/ade20k_mit.yaml
  labelspace_config: hydra:config/label_spaces/ade20k_mit_label_space.yaml
visualization: {profile: hierarchical}
hydra_config: classic.yaml
```

For recorded IDs, set `source: recorded`, provide `topics.semantic`, and point
`labelspace_config` at a matching Hydra taxonomy/remap overlay. For Khronos
open-set mapping, start from `spot.yaml` and set independent `perception_config`
and `labels_config` resources.

Run `make validate-bag` before mapping. New dependencies belong in the Docker
image and exact-SHA lock, never on the host.
