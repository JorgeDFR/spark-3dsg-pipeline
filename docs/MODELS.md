# Model setup

Models are external artifacts mounted at `/home/spark/models`; they are never
committed. Run:

```bash
make models PROFILE=gpu
```

The model runtime is the pinned compatibility set in
[`dependencies/GPU_BASELINE.md`](../dependencies/GPU_BASELINE.md). Do not
independently update PyTorch, CUDA, TensorRT, or cuDNN.

The downloader verifies fixed SHA-256 hashes for:

- `yoloe-26m-seg.pt`, used by open-set instance segmentation;
- `ade20k-efficientvit_seg_l2.onnx`, used by closed-set dense segmentation.

`SEMANTIC_INFERENCE_MODEL_DIR` is `/home/spark/models/semantic_inference` in the
GPU image, matching upstream model lookup conventions. The `closed_set` mapping
recipe separately selects the ONNX filename, upstream model preprocessing
config, semantic-inference grouping, and Hydra label-space config. Startup
fails with an actionable list if any one is absent.

On the first closed-set run, TensorRT compiles the ONNX model and caches
`ade20k-efficientvit_seg_l2.trt` beside it in the mounted model directory.
Compilation can take longer than the example bags. The pipeline waits for the
closed-set node to finish initialization and subscribe to RGB before starting
bag playback; later runs reuse the cached engine.

Review `THIRD_PARTY_NOTICES.md` and upstream model terms before use.
