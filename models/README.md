# Model setup

Model weights and TensorRT engines are external artifacts, ignored by Git.
Docker mounts the model directory at `/home/spark/models`.

## Download models

Build the GPU image using the [README instructions](../README.md#open-set-demo),
then download and verify both models:

```bash
make models PROFILE=gpu
```

The downloader verifies fixed SHA-256 hashes and reuses files that already
match. Recorded-semantics mapping with `PROFILE=core` requires no model weights.

## Model files

Files live in `models/semantic_inference` on the host (or under `MODEL_DIR`
when customized). In the GPU image, `SEMANTIC_INFERENCE_MODEL_DIR` points to
`/home/spark/models/semantic_inference`.

| File | Recipe | Purpose |
| --- | --- | --- |
| `yoloe-26m-seg.pt` | `open_set` | YOLOE instance segmentation |
| `ade20k-efficientvit_seg_l2.onnx` | `closed_set` | ADE20K dense segmentation |
| `ade20k-efficientvit_seg_l2.trt` | `closed_set` | TensorRT engine generated on first use |

## Sources and checksums

The download URLs and expected hashes are pinned in
[`download_models.sh`](../scripts/shell/download_models.sh).
YOLOE comes from the Ultralytics Assets `v8.4.0` release. The ADE20K ONNX URL
is the fixed Dropbox download recorded in that script.

| Download | Expected SHA-256 |
| --- | --- |
| `yoloe-26m-seg.pt` | `585f5ec9028fd358035da8d860c27c56be285a795cba2076fba536a4391c2c83` |
| `ade20k-efficientvit_seg_l2.onnx` | `bce5de3bf3707258e7a2eff36b2f705595e6efcaeaab8e052f341057853a0072` |

Review [third-party notices](../THIRD_PARTY_NOTICES.md) and upstream model terms
before use. Do not commit checkpoints or generated engines.

## Closed-set initialization

The `closed_set` recipe selects four resources independently:

| Resource | Role |
| --- | --- |
| ONNX model | Network weights |
| Upstream model config | Image preprocessing and inference settings |
| Semantic grouping | Class grouping for semantic inference |
| Hydra label-space config | Mapper taxonomy |

Startup reports missing resources before mapping. On the first run, TensorRT
compiles the ONNX model and saves the `.trt` engine beside it in the writable
model mount. Compilation can take longer than a short demo bag.

The pipeline waits for the inference node to initialize and subscribe to RGB
before starting playback. Later runs reuse the cached engine.

## Runtime compatibility

CUDA, TensorRT, PyTorch, torchvision, and cuDNN use the qualified compatibility
set in [the GPU baseline](../dependencies/GPU_BASELINE.md). Update them as a
compatible set inside Docker.

For open-set vocabulary changes, use a labels overlay as described in the
[custom dataset guide](../docs/CUSTOM_DATASET.md#customize-open-set-labels).
