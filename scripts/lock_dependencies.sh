#!/usr/bin/env bash
set -euo pipefail

pipeline_root="${PIPELINE_ROOT:-/home/spark/spark-3dsg-pipeline}"
source_manifest="$pipeline_root/dependencies/upstream-public.repos"
destination="$pipeline_root/dependencies/locks/v1.lock.repos"
lock_workspace=$(mktemp -d)

echo "Importing public branches to resolve exact revisions..."
mkdir -p "$lock_workspace/src"
vcs import "$lock_workspace/src" --workers 1 < "$source_manifest"
{
  echo "# Immutable v1 dependency snapshot generated from ../upstream-public.repos on $(date -u +%F)."
  vcs export --exact "$lock_workspace/src"
} > "$destination"

if grep -Eq 'git@|ssh://|version: (main|master|develop)$' "$destination"; then
  echo "generated lock violates repository policy" >&2
  exit 1
fi
echo "Updated $destination"
