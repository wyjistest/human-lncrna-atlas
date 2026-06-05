#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 论文图表/稿件脚本依赖会在 CI 中安装，必须避免 PyPI 新版本导致结果漂移。
# - requirements 的有效依赖行应使用精确 `==` pin。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
requirements="$REPO_ROOT/scripts/paper/requirements.txt"

if [ ! -f "$requirements" ]; then
  echo "missing paper requirements file: $requirements" >&2
  exit 1
fi

python3 - "$requirements" <<'PY'
import re
import sys
from pathlib import Path

requirements = Path(sys.argv[1])
unpinned: list[tuple[int, str]] = []
package_pin = re.compile(r"^[A-Za-z0-9_.-]+==[A-Za-z0-9_.!+:-]+$")

for line_number, raw_line in enumerate(requirements.read_text(encoding="utf-8").splitlines(), start=1):
    line = raw_line.strip()
    if not line or line.startswith("#"):
        continue
    if not package_pin.fullmatch(line):
        unpinned.append((line_number, line))

if unpinned:
    print("scripts/paper/requirements.txt must pin direct dependencies with ==:", file=sys.stderr)
    for line_number, line in unpinned:
        print(f"- line {line_number}: {line}", file=sys.stderr)
    raise SystemExit(1)
PY

echo "OK: paper requirements direct dependencies are pinned"
