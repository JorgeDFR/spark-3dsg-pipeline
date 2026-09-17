#!/usr/bin/env bash
set -euo pipefail

profile="${1:-gpu}"
if [[ "$profile" == "core" ]]; then
  echo "The core profile uses recorded semantics and requires no model weights."
  exit 0
fi
if [[ "$profile" != "gpu" ]]; then
  echo "Unsupported model profile: $profile" >&2
  exit 2
fi

model_dir="${SEMANTIC_INFERENCE_MODEL_DIR:-${HOME:-/home/spark}/models/semantic_inference}"
mkdir -p "$model_dir"
echo "License notice: review THIRD_PARTY_NOTICES.md and the upstream model terms."

download() {
  local filename="$1"
  local url="$2"
  local sha256="$3"
  local destination="$model_dir/$filename"
  local partial="$destination.partial"
  echo "Source: $url"
  if [[ -f "$destination" ]] && echo "$sha256  $destination" | sha256sum --check --status; then
    echo "Already present and verified: $destination"
    return
  fi
  curl --fail --location --retry 3 --output "$partial" "$url"
  echo "$sha256  $partial" | sha256sum --check --status || {
    echo "Checksum mismatch; leaving partial download at $partial" >&2
    return 1
  }
  mv "$partial" "$destination"
  echo "Downloaded and verified: $destination"
}

download \
  yoloe-26m-seg.pt \
  https://github.com/ultralytics/assets/releases/download/v8.4.0/yoloe-26m-seg.pt \
  585f5ec9028fd358035da8d860c27c56be285a795cba2076fba536a4391c2c83
download \
  ade20k-efficientvit_seg_l2.onnx \
  'https://www.dropbox.com/scl/fi/qtaqm3htsdjlnoyqjvrol/ade20k-efficientvit_seg_l2.onnx?rlkey=3evg4gfeybd0wie0gom8535zo&st=1ocu1vl7&dl=1' \
  bce5de3bf3707258e7a2eff36b2f705595e6efcaeaab8e052f341057853a0072
