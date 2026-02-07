#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 回归测试：`scripts/run-tests.sh` 的 usage 必须包含 `frontend-baselines` 子命令，
#   方便把 bundle baseline 校验作为“本地可选”入口（不进入默认 CI 门禁）。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

set +e
out="$(cd "$REPO_ROOT" && bash scripts/run-tests.sh __unknown__ 2>&1)"
status=$?
set -e

if [ "$status" -eq 0 ]; then
  echo "expected run-tests.sh to exit non-zero on unknown command" >&2
  exit 1
fi

echo "$out" | grep -F "frontend-baselines" >/dev/null || {
  echo "expected usage to include frontend-baselines" >&2
  echo "$out" >&2
  exit 1
}

echo "OK: run-tests usage includes frontend-baselines"

