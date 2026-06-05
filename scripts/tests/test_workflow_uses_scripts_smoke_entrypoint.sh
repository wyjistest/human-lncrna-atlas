#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - CI scripts smoke 阶段必须调用 `scripts/run-tests.sh scripts-smoke`。
# - 避免 workflow 手写单个 smoke 脚本后遗漏 research 语法检查。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
workflow="$REPO_ROOT/.github/workflows/test.yml"

grep -F "bash scripts/run-tests.sh scripts-smoke" "$workflow" >/dev/null || {
  echo "expected .github/workflows/test.yml to use scripts/run-tests.sh scripts-smoke" >&2
  exit 1
}

python3 - "$workflow" <<'PY'
from pathlib import Path
import sys

workflow = Path(sys.argv[1]).read_text(encoding="utf-8")
start = workflow.find("\n  backend-checks:")
if start < 0:
    raise SystemExit("missing backend-checks job")
end = workflow.find("\n  lint:", start)
if end < 0:
    raise SystemExit("missing lint job after backend-checks")
backend_checks = workflow[start:end]
smoke_step = backend_checks.find("bash scripts/run-tests.sh scripts-smoke")
unit_step = backend_checks.find("bash scripts/run-tests.sh scripts-tests")
if smoke_step < 0:
    raise SystemExit("expected backend-checks to run scripts-smoke")
if unit_step < 0:
    raise SystemExit("expected backend-checks to run scripts-tests")
if smoke_step > unit_step:
    raise SystemExit("expected scripts-smoke to run before scripts-tests")
if "bash scripts/genomes/tests/test_download_igv_assets.sh" in backend_checks:
    raise SystemExit("expected workflow to avoid hand-written scripts smoke list")
PY

echo "OK: workflow uses scripts-smoke entrypoint"
