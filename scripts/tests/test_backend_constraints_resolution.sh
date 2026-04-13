#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 验证 backend requirements + constraints 在 fresh venv 中至少可以被 pip 解析。
# - 该测试使用 `pip install --dry-run`，只做解析/求解，不真实安装依赖。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

python3 -m venv "$tmp_root/venv"
# shellcheck disable=SC1091
. "$tmp_root/venv/bin/activate"
python -m pip install --upgrade pip >/dev/null

log_file="$tmp_root/pip-dry-run.log"
if ! (
  cd "$REPO_ROOT/frontend/backend"
  pip install --dry-run -r requirements-dev.txt -c constraints.txt
) >"$log_file" 2>&1; then
  cat "$log_file" >&2
  echo "expected backend requirements-dev.txt + constraints.txt to resolve cleanly" >&2
  exit 1
fi

echo "OK: backend requirements-dev.txt + constraints.txt resolve in a fresh venv"
