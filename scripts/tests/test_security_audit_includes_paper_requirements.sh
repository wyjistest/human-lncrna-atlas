#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - scripts/paper/requirements.txt 会在 CI 中安装，也必须进入 Python 依赖安全审计。
# - 避免新增论文脚本依赖后 security-audit workflow 或本地入口只审计后端依赖。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
workflow="$REPO_ROOT/.github/workflows/security-audit.yml"
run_tests="$REPO_ROOT/scripts/run-tests.sh"

grep -F 'scripts/paper/requirements.txt' "$workflow" >/dev/null || {
  echo "expected security-audit workflow paths/cache to include scripts/paper/requirements.txt" >&2
  exit 1
}

grep -F 'frontend/backend/constraints.txt' "$workflow" >/dev/null || {
  echo "expected security-audit workflow paths/cache to include frontend/backend/constraints.txt" >&2
  exit 1
}

grep -F 'pip "${pip_args[@]}" install pip-audit -c constraints.txt' "$workflow" >/dev/null || {
  echo "expected security-audit workflow to install pip-audit under backend constraints" >&2
  exit 1
}

python3 - "$workflow" <<'PY'
import sys
from pathlib import Path

workflow = Path(sys.argv[1]).read_text(encoding="utf-8")
start = workflow.find("cache-dependency-path:")
if start < 0:
    raise SystemExit("expected security-audit workflow to configure setup-python cache-dependency-path")
end = workflow.find("\n\n", start)
cache_block = workflow[start:] if end < 0 else workflow[start:end]
if "frontend/backend/constraints.txt" not in cache_block:
    raise SystemExit("expected setup-python cache key to include frontend/backend/constraints.txt")
PY

grep -F 'pip-audit -s osv -r constraints.txt --no-deps --disable-pip' "$workflow" >/dev/null || {
  echo "expected security-audit workflow to audit locked backend constraints" >&2
  exit 1
}

grep -F 'pip-audit -s osv -r ../../scripts/paper/requirements.txt --no-deps --disable-pip' "$workflow" >/dev/null || {
  echo "expected security-audit workflow to audit paper requirements" >&2
  exit 1
}

grep -F 'HTTP_PROXY="${HTTP_PROXY:-${PIP_PROXY:-}}"' "$workflow" >/dev/null || {
  echo "expected security-audit workflow to map PIP_PROXY to HTTP_PROXY before pip-audit" >&2
  exit 1
}

grep -F 'HTTPS_PROXY="${HTTPS_PROXY:-${PIP_PROXY:-}}"' "$workflow" >/dev/null || {
  echo "expected security-audit workflow to map PIP_PROXY to HTTPS_PROXY before pip-audit" >&2
  exit 1
}

grep -F 'run_pip_audit_with_retry "$python_bin" -s osv -r constraints.txt --no-deps --disable-pip' "$run_tests" >/dev/null || {
  echo "expected scripts/run-tests.sh security-audit mode to audit locked backend constraints" >&2
  exit 1
}

grep -F 'run_pip_audit_with_retry "$python_bin" -s osv -r ../../scripts/paper/requirements.txt --no-deps --disable-pip' "$run_tests" >/dev/null || {
  echo "expected scripts/run-tests.sh security-audit mode to audit paper requirements" >&2
  exit 1
}

grep -F 'run_pip_audit_with_retry pip-audit -s osv -r constraints.txt --no-deps --disable-pip' "$workflow" >/dev/null || {
  echo "expected security-audit workflow to retry locked backend constraints audit" >&2
  exit 1
}

grep -F 'run_pip_audit_with_retry pip-audit -s osv -r ../../scripts/paper/requirements.txt --no-deps --disable-pip' "$workflow" >/dev/null || {
  echo "expected security-audit workflow to retry paper requirements audit" >&2
  exit 1
}

grep -F 'PIP_AUDIT_TIMEOUT' "$run_tests" >/dev/null || {
  echo "expected scripts/run-tests.sh security-audit mode to set an explicit pip-audit socket timeout" >&2
  exit 1
}

grep -F 'PIP_AUDIT_TIMEOUT' "$workflow" >/dev/null || {
  echo "expected security-audit workflow to set an explicit pip-audit socket timeout" >&2
  exit 1
}

echo "OK: security audit includes paper Python requirements"
