#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 确保 performance 聚合脚本能从多次 run 的 JSON 报告中计算 median
# - 确保遇到坏值（非 number）时会忽略并继续聚合
# - 确保缺少必要参数时能返回非零退出码并打印用法

unset GIT_DIR GIT_WORK_TREE

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_UNDER_TEST="$REPO_ROOT/frontend/web/scripts/aggregate-performance-metrics.js"

if [ ! -f "$SCRIPT_UNDER_TEST" ]; then
  echo "missing script under test: $SCRIPT_UNDER_TEST" >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "missing dependency: node" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "missing dependency: python3" >&2
  exit 1
fi

tmp_root="$(mktemp -d)"
cleanup() {
  if [ -n "${tmp_root:-}" ] && [ -d "${tmp_root:-}" ] && [ "${tmp_root:-}" != "/" ]; then
    rm -rf "$tmp_root"
  fi
}
trap cleanup EXIT

in1="$tmp_root/run-1.json"
in2="$tmp_root/run-2.json"
in3="$tmp_root/run-3.json"
out="$tmp_root/out.json"

cat > "$in1" <<'JSON'
{
  "test_date": "2026-02-02",
  "critical_metrics": { "api_response_time": { "value_ms": 100 } },
  "test_results": { "pass_rate_percent": 100 }
}
JSON

cat > "$in2" <<'JSON'
{
  "test_date": "2026-02-02",
  "critical_metrics": { "api_response_time": { "value_ms": 110 } },
  "test_results": { "pass_rate_percent": 100 }
}
JSON

cat > "$in3" <<'JSON'
{
  "test_date": "2026-02-02",
  "critical_metrics": { "api_response_time": { "value_ms": 90 } },
  "test_results": { "pass_rate_percent": 100 }
}
JSON

node "$SCRIPT_UNDER_TEST" --out "$out" --inputs "$in1" "$in2" "$in3" >/dev/null

python3 - <<PY
import json
with open("$out", "r", encoding="utf-8") as f:
  data = json.load(f)
v = data["critical_metrics"]["api_response_time"]["value_ms"]
assert abs(v - 100.0) < 1e-9, f"expected median=100, got {v}"
PY

# 坏值应被忽略：100 + 110（2 个有效值） => median = (100+110)/2 = 105
cat > "$in3" <<'JSON'
{
  "test_date": "2026-02-02",
  "critical_metrics": { "api_response_time": { "value_ms": "bad" } },
  "test_results": { "pass_rate_percent": 100 }
}
JSON

node "$SCRIPT_UNDER_TEST" --out "$out" --inputs "$in1" "$in2" "$in3" >/dev/null

python3 - <<PY
import json
with open("$out", "r", encoding="utf-8") as f:
  data = json.load(f)
v = data["critical_metrics"]["api_response_time"]["value_ms"]
assert abs(v - 105.0) < 1e-9, f"expected median=105, got {v}"
PY

# 参数校验：缺参数应 exit 2
set +e
node "$SCRIPT_UNDER_TEST" --inputs "$in1" >/dev/null 2>&1
code_missing_out=$?
node "$SCRIPT_UNDER_TEST" --out "$out" >/dev/null 2>&1
code_missing_inputs=$?
set -e

if [ "$code_missing_out" -ne 2 ]; then
  echo "expected exit code 2 for missing --out, got $code_missing_out" >&2
  exit 1
fi

if [ "$code_missing_inputs" -ne 2 ]; then
  echo "expected exit code 2 for missing --inputs, got $code_missing_inputs" >&2
  exit 1
fi

echo "ok"

