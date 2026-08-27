#!/usr/bin/env bash
set -euo pipefail

cd "${PIPELINE_ROOT:-/home/spark/spark-3dsg-pipeline}"
python3 -m compileall -q scripts tests

while IFS= read -r script; do
  bash -n "$script"
done < <(find docker scripts -type f -name '*.sh' -print | sort)

python3 - <<'PY'
from pathlib import Path
import re
import yaml

for path in sorted(Path('.').rglob('*.yaml')) + sorted(Path('.').rglob('*.repos')):
    with path.open(encoding='utf-8') as stream:
        yaml.safe_load(stream)

sha = re.compile(r'^[0-9a-f]{40}$')
for path in Path('dependencies/locks').glob('*.repos'):
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    for name, entry in data['repositories'].items():
        assert entry['url'].startswith('https://'), f'{path}:{name}: non-HTTPS URL'
        assert sha.fullmatch(entry['version']), f'{path}:{name}: floating revision'
PY

ros2 launch spark_3dsg_pipeline pipeline.launch.yaml --show-args >/dev/null
echo "Lint checks passed"
