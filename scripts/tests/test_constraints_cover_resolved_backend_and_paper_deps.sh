#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - constraints.txt 宣称 pin resolved versions；新增 paper 依赖或关键
#   backend 传递依赖时，必须同步进入 constraints，避免 fresh 安装漂移。
# - 此测试不访问 PyPI，避免代理/TLS 抖动让 scripts-tests 假红。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

python3 - "$REPO_ROOT" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
constraints_path = repo_root / "frontend/backend/constraints.txt"
paper_requirements_path = repo_root / "scripts/paper/requirements.txt"

constraint_names: set[str] = set()
for line in constraints_path.read_text(encoding="utf-8").splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        continue
    match = re.match(r"([A-Za-z0-9_.-]+)==", stripped)
    if match:
        constraint_names.add(match.group(1).lower().replace("_", "-"))

paper_direct_names: set[str] = set()
for line in paper_requirements_path.read_text(encoding="utf-8").splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        continue
    match = re.match(r"([A-Za-z0-9_.-]+)==", stripped)
    if match:
        paper_direct_names.add(match.group(1).lower().replace("_", "-"))

expected_transitive_names = {
    # pydantic/pydantic-settings/FastAPI currently require this; leaving it unpinned
    # lets fresh backend installs drift even when direct backend requirements are constrained.
    "typing-inspection",
    # matplotlib/seaborn paper rendering stack.
    "contourpy",
    "cycler",
    "fonttools",
    "kiwisolver",
}

missing = sorted((paper_direct_names | expected_transitive_names) - constraint_names)
if missing:
    print("constraints.txt is missing required backend/paper dependency pins:", file=sys.stderr)
    for name in missing:
        print(f"- {name}", file=sys.stderr)
    raise SystemExit(1)
PY

echo "OK: constraints include backend/paper dependency pins"
