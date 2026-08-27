#!/usr/bin/env bash
set -euo pipefail

model="/models/semantic_inference/yoloe-26m-seg.pt"
[[ -f "$model" ]] || { echo "missing model: $model (run make models PROFILE=gpu)" >&2; exit 2; }

python3 - "$model" <<'PY'
import sys
import torch
from ultralytics import YOLOE

assert torch.cuda.is_available(), "CUDA is not available in this container"
YOLOE(sys.argv[1])
print(f"CUDA OK: {torch.cuda.get_device_name(0)}")
print("YOLOE model load OK")
PY
