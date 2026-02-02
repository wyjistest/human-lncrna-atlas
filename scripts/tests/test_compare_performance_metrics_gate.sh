#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 确保 performance compare 脚本在启用门禁参数时能正确返回非零退出码
#   （否则 CI/本地的“性能门禁”不会真正拦截回归）。
#
# 覆盖：
# - 回归超过阈值时：exit 1
# - 回归不超过阈值时：exit 0

unset GIT_DIR GIT_WORK_TREE

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_UNDER_TEST="$REPO_ROOT/frontend/web/scripts/compare-performance-metrics.js"

if [ ! -f "$SCRIPT_UNDER_TEST" ]; then
  echo "missing script under test: $SCRIPT_UNDER_TEST" >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "missing dependency: node" >&2
  exit 1
fi

tmp_root="$(mktemp -d)"
cleanup() {
  if [ -n "${tmp_root:-}" ] && [ -d "${tmp_root:-}" ] && [ "${tmp_root:-}" != "/" ]; then
    rm -rf "$tmp_root"
  fi
}
trap cleanup EXIT

baseline="$tmp_root/baseline.json"
current_regress="$tmp_root/current-regress.json"
current_ok="$tmp_root/current-ok.json"

cat > "$baseline" <<'JSON'
{
  "test_date": "2026-02-02",
  "critical_metrics": {
    "api_response_time": { "value_ms": 1000 },
    "cache_performance": {
      "cold_cache_time_ms": 100,
      "warm_cache_time_ms": 100,
      "cache_hit_rate_percent": 90,
      "average_hit_time_ms": 10,
      "average_miss_time_ms": 100
    }
  },
  "test_results": { "pass_rate_percent": 100 }
}
JSON

# 回归：api_response_time 从 1000ms → 1060ms（+6%），阈值 5% 时应判定为 REGRESSION 并 exit 1。
cat > "$current_regress" <<'JSON'
{
  "test_date": "2026-02-02",
  "critical_metrics": {
    "api_response_time": { "value_ms": 1060 },
    "cache_performance": {
      "cold_cache_time_ms": 100,
      "warm_cache_time_ms": 100,
      "cache_hit_rate_percent": 90,
      "average_hit_time_ms": 10,
      "average_miss_time_ms": 100
    }
  },
  "test_results": { "pass_rate_percent": 100 }
}
JSON

set +e
node "$SCRIPT_UNDER_TEST" \
  --baseline "$baseline" \
  --current "$current_regress" \
  --fail-on-regression \
  --regression-threshold 5 \
  >/dev/null 2>&1
code_regress=$?
set -e

if [ "$code_regress" -eq 0 ]; then
  echo "expected non-zero exit code when regressions exceed threshold" >&2
  exit 1
fi

# 非回归：1000ms → 1040ms（+4%），阈值 5% 时应 exit 0。
cat > "$current_ok" <<'JSON'
{
  "test_date": "2026-02-02",
  "critical_metrics": {
    "api_response_time": { "value_ms": 1040 },
    "cache_performance": {
      "cold_cache_time_ms": 100,
      "warm_cache_time_ms": 100,
      "cache_hit_rate_percent": 90,
      "average_hit_time_ms": 10,
      "average_miss_time_ms": 100
    }
  },
  "test_results": { "pass_rate_percent": 100 }
}
JSON

node "$SCRIPT_UNDER_TEST" \
  --baseline "$baseline" \
  --current "$current_ok" \
  --fail-on-regression \
  --regression-threshold 5 \
  >/dev/null

echo "ok"

