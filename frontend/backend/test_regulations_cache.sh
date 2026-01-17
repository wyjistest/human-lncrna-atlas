#!/bin/bash
# Regulations API 缓存测试脚本
# Usage: ./test_regulations_cache.sh

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000/api/v1}"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: Missing required command: $cmd"
    exit 1
  fi
}

require_cmd curl
require_cmd redis-cli
require_cmd jq

REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_DB="${REDIS_DB:-0}"

redis_cli() {
  redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -n "$REDIS_DB" "$@"
}

confirm_redis_delete() {
  local target="${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}"
  echo ""
  echo "WARNING: 即将对 Redis (${target}) 删除缓存键（DEL/KEYS）。"
  echo "如确认是本地/测试环境，请继续；否则请 Ctrl+C 退出。"
  echo ""

  if [ "${ALLOW_REDIS_DELETE:-}" = "true" ]; then
    return 0
  fi

  if [ -t 0 ]; then
    read -r -p "输入 DELETE 以确认继续: " confirm
    if [ "$confirm" != "DELETE" ]; then
      echo "已取消。若要跳过交互确认，请设置 ALLOW_REDIS_DELETE=true。"
      exit 1
    fi
    return 0
  fi

  echo "非交互环境下默认拒绝执行。请设置 ALLOW_REDIS_DELETE=true 以继续。"
  exit 1
}

delete_keys_by_pattern() {
  local pattern="$1"
  mapfile -t keys < <(redis_cli KEYS "$pattern")
  if [ "${#keys[@]}" -eq 0 ]; then
    return 0
  fi
  for key in "${keys[@]}"; do
    redis_cli DEL "$key" > /dev/null
  done
}

echo "========================================="
echo "Regulations API 缓存测试"
echo "========================================="
echo ""

if ! redis_cli PING > /dev/null 2>&1; then
  echo "ERROR: Redis 未运行或不可达（目标: ${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}）"
  exit 1
fi

confirm_redis_delete

# Test 1: lncRNA options
echo "1. 测试 lncRNA Options API"
echo "----------------------------------------"
echo "清除缓存..."
redis_cli DEL "lncrna:regulations:lncrna-options:all" > /dev/null

echo "首次查询（无缓存）..."
time curl -s "${BASE_URL}/regulations/lncrna-options" > /dev/null
echo ""

echo "第二次查询（缓存命中）..."
time curl -s "${BASE_URL}/regulations/lncrna-options" > /dev/null
echo ""

# Test 2: target options
echo "2. 测试 Target Options API"
echo "----------------------------------------"
echo "清除缓存..."
redis_cli DEL "lncrna:regulations:target-options:all" > /dev/null

echo "首次查询（无缓存）..."
time curl -s "${BASE_URL}/regulations/target-options" > /dev/null
echo ""

echo "第二次查询（缓存命中）..."
time curl -s "${BASE_URL}/regulations/target-options" > /dev/null
echo ""

# Test 3: list regulations
echo "3. 测试 List Regulations API"
echo "----------------------------------------"
echo "清除缓存..."
delete_keys_by_pattern "lncrna:regulations:list:*"

echo "首次查询（无缓存）..."
time curl -s "${BASE_URL}/regulations?page=1&page_size=10" > /dev/null
echo ""

echo "第二次查询（缓存命中）..."
time curl -s "${BASE_URL}/regulations?page=1&page_size=10" > /dev/null
echo ""

# Statistics
echo "4. 数据统计"
echo "----------------------------------------"
LNCRNA_COUNT=$(curl -s "${BASE_URL}/regulations/lncrna-options" | jq '.lncrnas | length')
TARGET_COUNT=$(curl -s "${BASE_URL}/regulations/target-options" | jq '.targets | length')
TOTAL_REGS=$(curl -s "${BASE_URL}/regulations?page=1&page_size=1" | jq '.total')

echo "lncRNA 数量: ${LNCRNA_COUNT}"
echo "靶基因数量: ${TARGET_COUNT}"
echo "调控关系总数: ${TOTAL_REGS}"
echo ""

# Cache keys
echo "5. Redis 缓存键"
echo "----------------------------------------"
redis_cli KEYS "lncrna:regulations:*"
echo ""

echo "========================================="
echo "测试完成！"
echo "========================================="
