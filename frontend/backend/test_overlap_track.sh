#!/usr/bin/env bash
set -euo pipefail

# IGV Overlap Track API - Smoke Test
#
# 目标：
# - 快速验证 /api/v1/igv/overlap-track 可用性、参数校验与 BED6 输出形态
# - 便于在本地/CI/部署环境快速定位问题
#
# 可选环境变量：
# - API_BASE_URL：默认 http://localhost:8000
# - CHR：默认 chr1
# - START：默认 1000000
# - END：默认 2000000
# - CURL_MAX_TIME：默认 30
#
# 依赖：
# - curl
# - python3

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
CHR="${CHR:-chr1}"
START="${START:-1000000}"
END="${END:-2000000}"
CURL_MAX_TIME="${CURL_MAX_TIME:-30}"

PASS_COUNT=0
FAIL_COUNT=0

log() { printf '%s\n' "$*"; }

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
  curl -sS --connect-timeout 5 --max-time "$CURL_MAX_TIME" -o /dev/null -w "%{http_code}" "$1"
}

http_body() {
  curl -sS --connect-timeout 5 --max-time "$CURL_MAX_TIME" "$1"
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

assert_bed6_non_empty() {
  local name="$1"
  local body="$2"
  local output
  output="$(python3 -c $'import sys\nraw=sys.stdin.read().strip()\nif not raw:\n    print(\"EMPTY\")\n    raise SystemExit(0)\nlines=[ln for ln in raw.splitlines() if ln.strip()]\nfor i,ln in enumerate(lines[:50]):\n    fields=ln.split(\"\\t\")\n    if len(fields)!=6:\n        print(\"BAD_FIELDS\", i, len(fields))\n        raise SystemExit(0)\n    chr_=fields[0]\n    try:\n        s=int(fields[1]); e=int(fields[2])\n    except Exception:\n        print(\"BAD_COORD\", i)\n        raise SystemExit(0)\n    if not chr_.startswith(\"chr\"):\n        print(\"BAD_CHR\", i, chr_)\n        raise SystemExit(0)\n    if s>=e:\n        print(\"BAD_RANGE\", i, s, e)\n        raise SystemExit(0)\nprint(\"OK\")' <<<"$body" 2>&1 || true)"

  if [ "$output" = "OK" ]; then
    pass "$name (bed6 shape ok)"
  else
    fail "$name (bed6 shape invalid) detail=$output"
  fi
}

assert_body_contains() {
  local name="$1"
  local body="$2"
  local needle="$3"
  if printf '%s' "$body" | grep -Fq -- "$needle"; then
    pass "$name (contains '$needle')"
  else
    fail "$name (missing '$needle')"
  fi
}

log "============================================================"
log "🔎 IGV overlap-track smoke tests"
log "API_BASE_URL=$API_BASE_URL"
log "REGION=$CHR:$START-$END"
log "============================================================"

BASE_URL="$API_BASE_URL/api/v1/igv/overlap-track"

assert_status "Health" "$API_BASE_URL/health" "200"

# Validation
assert_status "Validation (missing chr -> 400)" "$BASE_URL?start=$START&end=$END" "400"
assert_status "Validation (start>=end -> 400)" "$BASE_URL?chr=$CHR&start=10&end=10" "400"
assert_status "Validation (region too large -> 400)" "$BASE_URL?chr=$CHR&start=0&end=10000001" "400"

# Basic
basic_body="$(http_body "$BASE_URL?chr=$CHR&start=$START&end=$END" || true)"
assert_status "Basic query" "$BASE_URL?chr=$CHR&start=$START&end=$END" "200"
assert_bed6_non_empty "Basic query" "$basic_body"

# chromosome alias (chr=1 should normalize to chr1)
alias_body="$(http_body "$BASE_URL?chromosome=1&start=$START&end=$END&limit=1" || true)"
assert_status "Chromosome alias" "$BASE_URL?chromosome=1&start=$START&end=$END&limit=1" "200"
if [ -n "$alias_body" ]; then
  first_chr="$(printf '%s\n' "$alias_body" | head -n 1 | cut -f1)"
  if [ "$first_chr" = "chr1" ]; then
    pass "Chromosome alias (normalized chr1)"
  else
    fail "Chromosome alias (expected chr1, got $first_chr)"
  fi
else
  fail "Chromosome alias (empty response)"
fi

# Filters
mark_body="$(http_body "$BASE_URL?chr=$CHR&start=$START&end=$END&mark_type=H3K27me3&limit=50" || true)"
assert_status "Filter (mark_type)" "$BASE_URL?chr=$CHR&start=$START&end=$END&mark_type=H3K27me3&limit=50" "200"
assert_bed6_non_empty "Filter (mark_type)" "$mark_body"
assert_body_contains "Filter (mark_type)" "$mark_body" "H3K27me3"

cell_body="$(http_body "$BASE_URL?chr=$CHR&start=$START&end=$END&cell_line=K562&limit=50" || true)"
assert_status "Filter (cell_line)" "$BASE_URL?chr=$CHR&start=$START&end=$END&cell_line=K562&limit=50" "200"
assert_bed6_non_empty "Filter (cell_line)" "$cell_body"
assert_body_contains "Filter (cell_line)" "$cell_body" "K562"

# min_ba (canonical)
min_ba_body="$(http_body "$BASE_URL?chr=$CHR&start=$START&end=$END&min_ba=80&limit=50" || true)"
assert_status "Filter (min_ba)" "$BASE_URL?chr=$CHR&start=$START&end=$END&min_ba=80&limit=50" "200"
assert_bed6_non_empty "Filter (min_ba)" "$min_ba_body"

# min_binding_affinity (alias)
alias_ba_body="$(http_body "$BASE_URL?chr=$CHR&start=$START&end=$END&min_binding_affinity=80&limit=50" || true)"
assert_status "Filter (min_binding_affinity alias)" "$BASE_URL?chr=$CHR&start=$START&end=$END&min_binding_affinity=80&limit=50" "200"
assert_bed6_non_empty "Filter (min_binding_affinity alias)" "$alias_ba_body"

log "------------------------------------------------------------"
log "✅ PASS: $PASS_COUNT"
log "❌ FAIL: $FAIL_COUNT"

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
