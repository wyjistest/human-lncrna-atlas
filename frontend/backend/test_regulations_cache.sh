#!/bin/bash
# Regulations API 缓存测试脚本
# Usage: ./test_regulations_cache.sh

BASE_URL="http://localhost:8000/api/v1"

echo "========================================="
echo "Regulations API 缓存测试"
echo "========================================="
echo ""

# Test 1: lncRNA options
echo "1. 测试 lncRNA Options API"
echo "----------------------------------------"
echo "清除缓存..."
redis-cli DEL "lncrna:regulations:lncrna-options:all" > /dev/null

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
redis-cli DEL "lncrna:regulations:target-options:all" > /dev/null

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
redis-cli KEYS "lncrna:regulations:list:*" | xargs redis-cli DEL > /dev/null

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
redis-cli KEYS "lncrna:regulations:*"
echo ""

echo "========================================="
echo "测试完成！"
echo "========================================="
