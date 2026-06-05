#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - weekly-regression 的 ci-plus 会执行 scripts-tests。
# - scripts-tests 会运行 scripts/tests/*.py，依赖 pandoc 与 scripts/paper/requirements.txt。
# - 避免 weekly workflow 只安装 backend deps 后在 scripts-tests 阶段缺依赖。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
workflow="$REPO_ROOT/.github/workflows/weekly-regression.yml"

python3 - "$workflow" <<'PY'
from pathlib import Path
import sys

workflow = Path(sys.argv[1]).read_text(encoding="utf-8")
start = workflow.find("\n  ci-plus:")
if start < 0:
    raise SystemExit("missing weekly ci-plus job")
end = workflow.find("\n  perf-overlap:", start)
if end < 0:
    raise SystemExit("missing perf-overlap job after ci-plus")
ci_plus = workflow[start:end]

run_step = ci_plus.find("bash scripts/run-tests.sh ci-plus")
if run_step < 0:
    raise SystemExit("expected weekly ci-plus to call scripts/run-tests.sh ci-plus")

paper_system_deps_step = ci_plus.find("Install paper script system dependencies")
if paper_system_deps_step < 0 or paper_system_deps_step > run_step:
    raise SystemExit("expected weekly ci-plus to install pandoc before ci-plus")

sudo_fallback = ci_plus.find("command -v sudo")
root_fallback = ci_plus.find("id -u")
if (
    sudo_fallback < paper_system_deps_step
    or root_fallback < paper_system_deps_step
    or sudo_fallback > run_step
    or root_fallback > run_step
):
    raise SystemExit("expected weekly pandoc install to support both sudo and root apt-get runners")

paper_python_install = ci_plus.find("scripts/paper/requirements.txt")
if paper_python_install < 0 or paper_python_install > run_step:
    raise SystemExit("expected weekly ci-plus to install paper Python dependencies before ci-plus")

constraints_install = ci_plus.find("-c constraints.txt")
if constraints_install < 0 or constraints_install > run_step:
    raise SystemExit("expected weekly paper dependency install to use backend constraints")

pip_proxy = ci_plus.find('--proxy "$PIP_PROXY"')
if pip_proxy < 0 or pip_proxy > paper_python_install:
    raise SystemExit("expected weekly PyPI installs to honor optional PIP_PROXY before ci-plus")
PY

echo "OK: weekly ci-plus installs paper script dependencies"
