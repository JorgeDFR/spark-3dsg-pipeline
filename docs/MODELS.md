# Model setup

Models are external artifacts mounted at `/home/spark/models`; they are never
committed. Run:

```bash
make models PROFILE=gpu
```

The downloader verifies fixed SHA-256 hashes for:

- `yoloe-26m-seg.pt`, used by open-set instance segmentation;
- `ade20k-efficientvit_seg_l2.onnx`, used by closed-set dense segmentation.

`SEMANTIC_INFERENCE_MODEL_DIR` is `/home/spark/models/semantic_inference` in the
GPU image, matching upstream model lookup conventions. The closed-set adapter
separately selects the ONNX filename, upstream model preprocessing config,
semantic-inference grouping, and Hydra label-space config. Startup fails with an
actionable list if any one is absent.

Review `THIRD_PARTY_NOTICES.md` and upstream model terms before use.
