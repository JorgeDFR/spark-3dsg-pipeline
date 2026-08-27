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

model_dir=/models/semantic_inference
filename=yoloe-26m-seg.pt
url=https://github.com/ultralytics/assets/releases/download/v8.4.0/yoloe-26m-seg.pt
sha256=585f5ec9028fd358035da8d860c27c56be285a795cba2076fba536a4391c2c83

mkdir -p "$model_dir"
destination="$model_dir/$filename"

echo "Source: $url"
echo "License notice: review THIRD_PARTY_NOTICES.md and the upstream model terms."

if [[ -f "$destination" ]] && echo "$sha256  $destination" | sha256sum --check --status; then
  echo "Already present and verified: $destination"
  exit 0
fi

partial="$destination.partial"
curl --fail --location --retry 3 --output "$partial" "$url"
echo "$sha256  $partial" | sha256sum --check --status || {
  echo "Checksum mismatch; leaving partial download at $partial" >&2
  exit 1
}
mv "$partial" "$destination"
echo "Downloaded and verified: $destination"
