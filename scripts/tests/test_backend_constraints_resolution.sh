#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 验证 backend requirements + constraints 在 fresh venv 中至少可以被 pip 解析。
# - 该测试使用 `pip install --dry-run`，只做解析/求解，不真实安装依赖。
# - 代理/网络抖动可通过 PIP_PROXY、PIP_RESOLVE_ATTEMPTS、
#   PIP_RESOLVE_PIP_RETRIES、PIP_RESOLVE_TIMEOUT 控制。

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

pip_global_args=()
if [ -n "${PIP_PROXY:-}" ]; then
  pip_global_args+=(--proxy "$PIP_PROXY")
fi
if [[ ! "${PIP_RESOLVE_PIP_RETRIES:-0}" =~ ^[0-9]+$ ]]; then
  echo "PIP_RESOLVE_PIP_RETRIES must be a non-negative integer, got: ${PIP_RESOLVE_PIP_RETRIES}" >&2
  exit 2
fi
if [[ ! "${PIP_RESOLVE_TIMEOUT:-15}" =~ ^[1-9][0-9]*$ ]]; then
  echo "PIP_RESOLVE_TIMEOUT must be a positive integer, got: ${PIP_RESOLVE_TIMEOUT}" >&2
  exit 2
fi
pip_global_args+=(--retries "${PIP_RESOLVE_PIP_RETRIES:-0}" --timeout "${PIP_RESOLVE_TIMEOUT:-15}")

run_pip_with_retries() {
  local attempt
  local status=0
  local max_attempts="${PIP_RESOLVE_ATTEMPTS:-3}"

  if [[ ! "$max_attempts" =~ ^[1-9][0-9]*$ ]]; then
    echo "PIP_RESOLVE_ATTEMPTS must be a positive integer, got: ${max_attempts}" >&2
    return 2
  fi

  for ((attempt = 1; attempt <= max_attempts; attempt += 1)); do
    if "$@"; then
      return 0
    fi
    status=$?
    if [ "$attempt" -lt "$max_attempts" ]; then
      echo "pip command failed (attempt ${attempt}/${max_attempts}); retrying..." >&2
      sleep 2
    fi
  done

  return "$status"
}

log_file="$tmp_root/pip-dry-run.log"
if ! (
  cd "$REPO_ROOT/frontend/backend"
  run_pip_with_retries pip "${pip_global_args[@]}" install --dry-run -r requirements-dev.txt -c constraints.txt
) >"$log_file" 2>&1; then
  cat "$log_file" >&2
  echo "expected backend requirements-dev.txt + constraints.txt to resolve cleanly" >&2
  exit 1
fi

echo "OK: backend requirements-dev.txt + constraints.txt resolve in a fresh venv"
