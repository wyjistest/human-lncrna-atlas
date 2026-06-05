#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - `scripts/run-tests.sh scripts-tests` 遇到清单中的 shell 回归缺失时必须失败。
# - 静默跳过整组脚本单测会让 CI 误报绿色。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

mkdir -p "$tmp_root/scripts"
cp "$REPO_ROOT/scripts/run-tests.sh" "$tmp_root/scripts/run-tests.sh"
chmod +x "$tmp_root/scripts/run-tests.sh"

set +e
output="$(cd "$tmp_root" && bash scripts/run-tests.sh scripts-tests 2>&1)"
status=$?
set -e

if [ "$status" -eq 0 ]; then
  echo "expected scripts-tests to fail when listed shell tests are missing" >&2
  echo "$output" >&2
  exit 1
fi

echo "$output" | grep -F "SKIP  未找到:" >/dev/null || {
  echo "expected missing shell test output to name skipped paths" >&2
  echo "$output" >&2
  exit 1
}

echo "OK: scripts-tests fails when listed shell tests are missing"
