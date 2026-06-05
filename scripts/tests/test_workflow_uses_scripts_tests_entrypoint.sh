#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - CI scripts 单元测试阶段必须调用 `scripts/run-tests.sh scripts-tests`。
# - 避免 workflow 手写一份 scripts/tests 列表后与本地统一入口漂移。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
workflow="$REPO_ROOT/.github/workflows/test.yml"

grep -F "bash scripts/run-tests.sh scripts-tests" "$workflow" >/dev/null || {
  echo "expected .github/workflows/test.yml to use scripts/run-tests.sh scripts-tests" >&2
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
scripts_step = backend_checks.find("bash scripts/run-tests.sh scripts-tests")
node_setup = backend_checks.find("actions/setup-node")
if node_setup < 0 or node_setup > scripts_step:
    raise SystemExit("expected backend-checks to set up Node before scripts-tests")
paper_system_deps_step = backend_checks.find("Install paper script system dependencies")
if paper_system_deps_step < 0 or paper_system_deps_step > scripts_step:
    raise SystemExit("expected backend-checks to install pandoc before scripts-tests")
sudo_fallback = backend_checks.find("command -v sudo")
root_fallback = backend_checks.find("id -u")
if (
    sudo_fallback < paper_system_deps_step
    or root_fallback < paper_system_deps_step
    or sudo_fallback > scripts_step
    or root_fallback > scripts_step
):
    raise SystemExit("expected backend-checks pandoc install to support both sudo and root apt-get runners")
backend_python = backend_checks.find("BACKEND_PYTHON: python")
if backend_python < 0 or backend_python > scripts_step:
    raise SystemExit("expected backend-checks scripts-tests to reuse the setup-python interpreter via BACKEND_PYTHON=python")
install_step = backend_checks.find("../../scripts/paper/requirements.txt")
if install_step < 0 or install_step > scripts_step:
    raise SystemExit("expected backend-checks to install paper Python dependencies before scripts-tests")
pip_proxy = backend_checks.find('--proxy "$PIP_PROXY"')
if pip_proxy < 0 or pip_proxy > install_step:
    raise SystemExit("expected backend-checks dependency installs to honor optional PIP_PROXY before scripts-tests")
PY

echo "OK: workflow uses scripts-tests entrypoint"
