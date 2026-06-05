#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - CI workflow 中访问 PyPI 的安装命令必须支持 PIP_PROXY。
# - 避免 self-hosted runner 或本地代理环境下新增裸 `pip install`。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

python3 - "$REPO_ROOT" <<'PY'
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
violations: list[str] = []
checked_installs = 0
workflows = sorted(
    set((repo_root / ".github/workflows").glob("*.yml"))
    | set((repo_root / ".github/workflows").glob("*.yaml"))
)

for workflow in workflows:
    lines = workflow.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if " install" not in stripped:
            continue
        if not (
            stripped.startswith("pip ")
            or stripped.startswith("pip3 ")
            or stripped.startswith("python -m pip ")
            or stripped.startswith("python3 -m pip ")
        ):
            continue
        checked_installs += 1
        context = "\n".join(lines[max(0, line_number - 8) : line_number])
        if (
            '"${pip_args[@]}"' not in stripped
            or "pip_args=()" not in context
            or '--proxy "$PIP_PROXY"' not in context
        ):
            violations.append(f"{workflow.relative_to(repo_root)}:{line_number}: {stripped}")
        if " install --upgrade pip" not in stripped and " -c " not in stripped:
            violations.append(f"{workflow.relative_to(repo_root)}:{line_number}: missing constraints: {stripped}")

if violations:
    print("workflow PyPI installs must pass optional PIP_PROXY and use constraints:", file=sys.stderr)
    for violation in violations:
        print(f"- {violation}", file=sys.stderr)
    raise SystemExit(1)
if checked_installs == 0:
    print("expected at least one workflow PyPI install to check", file=sys.stderr)
    raise SystemExit(1)
PY

echo "OK: workflow PyPI installs honor optional PIP_PROXY and constraints"
