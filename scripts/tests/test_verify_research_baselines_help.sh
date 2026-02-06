#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 确保 `scripts/verify_research_baselines.py` 存在且 CLI 可用（至少 --help 可运行）。
# - 该测试不依赖 psql/建库权限，避免在 CI 中引入额外环境依赖。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

set +e
out="$(cd "$REPO_ROOT" && python3 scripts/verify_research_baselines.py --help 2>&1)"
status=$?
set -e

if [ "$status" -ne 0 ]; then
  echo "expected verify_research_baselines.py --help to exit 0" >&2
  echo "$out" >&2
  exit 1
fi

echo "$out" | grep -E "Verify.*Research.*baselines|research baselines" >/dev/null || {
  echo "expected help output to mention research baselines" >&2
  echo "$out" >&2
  exit 1
}

echo "OK: verify_research_baselines.py help is available"

