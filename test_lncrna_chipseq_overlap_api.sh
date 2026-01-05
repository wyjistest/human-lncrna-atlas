#!/usr/bin/env bash
set -euo pipefail

# lncRNA-ChIP-seq Overlap API - Minimal Smoke Test Suite
#
# 目标：
# - 快速验证关键端点可用性与响应结构（不依赖固定数据量）
# - 便于在本地/CI/部署环境快速诊断
#
# 可选环境变量：
# - API_BASE_URL：默认 http://localhost:8000
#
# 依赖：
# - curl
# - python3

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"

PASS_COUNT=0
FAIL_COUNT=0

log() {
  printf '%s\n' "$*"
}

fail() {
  log "❌ $*"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

pass() {
  log "✅ $*"
  PASS_COUNT=$((PASS_COUNT + 1))
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "缺少依赖命令: $1"
    exit 1
  fi
}

require_cmd curl
require_cmd python3

http_status() {
  curl -sS -o /dev/null -w "%{http_code}" "$1"
}

http_body() {
  curl -sS "$1"
}

assert_status() {
  local name="$1"
  local url="$2"
  local expected="$3"
  local actual
  actual="$(http_status "$url" || true)"
  if [ "$actual" = "$expected" ]; then
    pass "$name (status=$actual)"
  else
    fail "$name (expected=$expected, got=$actual) url=$url"
  fi
}

assert_json_shape_overlap_list() {
  local name="$1"
  local url="$2"
  local body
  body="$(http_body "$url" || true)"
  local output
  output="$(python3 -c $'import json,sys\nraw=sys.stdin.read()\ntry:\n    data=json.loads(raw)\nexcept Exception as e:\n    print(\"INVALID_JSON:\", e)\n    raise SystemExit(0)\nrequired=[\"total\",\"page\",\"page_size\",\"total_pages\",\"items\"]\nmissing=[k for k in required if k not in data]\nif missing:\n    print(\"MISSING_KEYS:\", \",\".join(missing))\n    raise SystemExit(0)\nif not isinstance(data.get(\"items\"), list):\n    print(\"INVALID_ITEMS_TYPE\")\n    raise SystemExit(0)\nprint(\"OK\")' <<<"$body" 2>&1 || true)"

  if [ "$output" = "OK" ]; then
    pass "$name (json shape ok)"
  else
    fail "$name (json shape invalid) url=$url; detail=$output"
  fi
}

assert_json_shape_statistics() {
  local name="$1"
  local url="$2"
  local body
  body="$(http_body "$url" || true)"
  local output
  output="$(python3 -c $'import json,sys\nraw=sys.stdin.read()\ntry:\n    data=json.loads(raw)\nexcept Exception as e:\n    print(\"INVALID_JSON:\", e)\n    raise SystemExit(0)\nrequired=[\"total_overlaps\",\"unique_lncrnas\",\"unique_targets\",\"unique_marks\"]\nmissing=[k for k in required if k not in data]\nif missing:\n    print(\"MISSING_KEYS:\", \",\".join(missing))\n    raise SystemExit(0)\nfor k in required:\n    if not isinstance(data.get(k), (int,float)):\n        print(\"INVALID_TYPE:\", k)\n        raise SystemExit(0)\nprint(\"OK\")' <<<"$body" 2>&1 || true)"

  if [ "$output" = "OK" ]; then
    pass "$name (json shape ok)"
  else
    fail "$name (json shape invalid) url=$url; detail=$output"
  fi
}

log "============================================================"
log "🔎 Overlap API smoke tests"
log "API_BASE_URL=$API_BASE_URL"
log "============================================================"

assert_status "Health" "$API_BASE_URL/health" "200"

assert_status "Overlap list (basic)" "$API_BASE_URL/api/v1/lncrna-chipseq-overlap?page=1&page_size=5" "200"
assert_json_shape_overlap_list "Overlap list (basic)" "$API_BASE_URL/api/v1/lncrna-chipseq-overlap?page=1&page_size=5"

assert_status "Overlap list (chr1)" "$API_BASE_URL/api/v1/lncrna-chipseq-overlap?chromosome=chr1&page=1&page_size=5" "200"
assert_json_shape_overlap_list "Overlap list (chr1)" "$API_BASE_URL/api/v1/lncrna-chipseq-overlap?chromosome=chr1&page=1&page_size=5"

assert_status "Overlap list (mark_type=H3K27me3)" "$API_BASE_URL/api/v1/lncrna-chipseq-overlap?mark_type=H3K27me3&page=1&page_size=5" "200"
assert_json_shape_overlap_list "Overlap list (mark_type=H3K27me3)" "$API_BASE_URL/api/v1/lncrna-chipseq-overlap?mark_type=H3K27me3&page=1&page_size=5"

assert_status "Overlap statistics" "$API_BASE_URL/api/v1/lncrna-chipseq-overlap/statistics" "200"
assert_json_shape_statistics "Overlap statistics" "$API_BASE_URL/api/v1/lncrna-chipseq-overlap/statistics"

# 422 validation
assert_status "Validation (page=-1 -> 422)" "$API_BASE_URL/api/v1/lncrna-chipseq-overlap?page=-1&page_size=5" "422"
assert_status "Validation (page_size=0 -> 422)" "$API_BASE_URL/api/v1/lncrna-chipseq-overlap?page=1&page_size=0" "422"

log "------------------------------------------------------------"
log "✅ PASS: $PASS_COUNT"
log "❌ FAIL: $FAIL_COUNT"

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
