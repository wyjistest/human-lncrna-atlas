#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - scripts/run-tests.sh security-audit 使用 `python -m pip_audit`。
# - 后端 venv 自举只安装 requirements-dev.txt；因此 pip-audit 必须是显式
#   dev 依赖，避免 fresh venv 下 security-audit/ci-full 缺工具。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

python3 - "$REPO_ROOT" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
run_tests = (repo_root / "scripts/run-tests.sh").read_text(encoding="utf-8")
requirements_dev = (repo_root / "frontend/backend/requirements-dev.txt").read_text(encoding="utf-8")
constraints = (repo_root / "frontend/backend/constraints.txt").read_text(encoding="utf-8")


def requirement_names(text: str) -> set[str]:
    names: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-r "):
            continue
        match = re.match(r"([A-Za-z0-9_.-]+)", stripped)
        if match:
            names.add(match.group(1).lower().replace("_", "-"))
    return names


if "python_bin\" -m pip_audit" not in run_tests:
    raise SystemExit("expected run-tests security-audit to invoke python -m pip_audit")

dev_names = requirement_names(requirements_dev)
if "pip-audit" not in dev_names:
    raise SystemExit("requirements-dev.txt must declare pip-audit for security-audit mode")

constraint_names = requirement_names(constraints)
if "pip-audit" not in constraint_names:
    raise SystemExit("constraints.txt must pin pip-audit for reproducible security-audit installs")
PY

echo "OK: security-audit declares pip-audit as a reproducible dev dependency"
