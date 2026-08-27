# Models

Model weights are external, ignored by Git, and mounted at `/home/spark/models`.

`make models PROFILE=gpu` downloads and verifies `semantic_inference/yoloe-26m-seg.pt`.

Source: Ultralytics Assets release `v8.4.0`. Expected SHA-256: `585f5ec9028fd358035da8d860c27c56be285a795cba2076fba536a4391c2c83`.

Review `THIRD_PARTY_NOTICES.md` before use. Never commit checkpoints or TensorRT engines.
