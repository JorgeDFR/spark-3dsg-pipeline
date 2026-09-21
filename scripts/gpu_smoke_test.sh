#!/usr/bin/env bash
set -euo pipefail

model="${HOME:-/home/spark}/models/semantic_inference/yoloe-26m-seg.pt"
[[ -f "$model" ]] || { echo "missing model: $model (run make models PROFILE=gpu)" >&2; exit 2; }

python3 - "$model" <<'PY'
import sys
import PIL
import torch
import torchvision
import ultralytics
from ultralytics import YOLOE

assert torch.__version__.split("+")[0] == "2.7.0", torch.__version__
assert torchvision.__version__.split("+")[0] == "0.22.0", torchvision.__version__
assert torch.version.cuda == "12.8", torch.version.cuda
assert torch.cuda.is_available(), "CUDA is not available in this container"
model = YOLOE(sys.argv[1])
model.set_classes(["chair", "table"])
print(f"PyTorch: {torch.__version__}; torchvision: {torchvision.__version__}")
print(f"PyTorch CUDA: {torch.version.cuda}; cuDNN: {torch.backends.cudnn.version()}")
print(f"Pillow: {PIL.__version__}; Ultralytics: {ultralytics.__version__}")
print(
    f"GPU: {torch.cuda.get_device_name(0)}; "
    f"compute capability: {torch.cuda.get_device_capability(0)}"
)
print("YOLOE model load OK")
print("YOLOE text prompt encoding OK")
PY
