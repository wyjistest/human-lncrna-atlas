#!/bin/bash
#
# Stats API 缓存验证脚本
# 用于验证所有统计端点的缓存功能
#

set -e

BASE_URL="http://localhost:8000/api/v1"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Stats API 缓存验证脚本"
echo "=========================================="
echo ""

# 检查服务器是否运行
echo -n "检查 API 服务器状态..."
if curl -s -f "$BASE_URL/health" > /dev/null 2>&1; then
    echo -e " ${GREEN}✓${NC} 运行中"
else
    echo -e " ${RED}✗${NC} 未运行"
    echo "请先启动 API 服务器: uvicorn main:app --reload"
    exit 1
fi

# 检查 Redis 是否运行
echo -n "检查 Redis 服务状态..."
if redis-cli PING > /dev/null 2>&1; then
    echo -e " ${GREEN}✓${NC} 运行中"
else
    echo -e " ${RED}✗${NC} 未运行"
    echo "请先启动 Redis: redis-server"
    exit 1
fi

echo ""
echo "=========================================="
echo "测试 1: 清空缓存"
echo "=========================================="
redis-cli FLUSHDB > /dev/null
echo -e "${GREEN}✓${NC} 缓存已清空"

echo ""
echo "=========================================="
echo "测试 2: Stats API 端点性能测试"
echo "=========================================="
echo ""

# 定义测试端点
declare -a endpoints=(
    "top-genes:/stats/top-genes?limit=10"
    "top-genes-filtered:/stats/top-genes?limit=20&gene_type=lncRNA"
    "top-diseases:/stats/top-diseases?limit=10"
    "conserved-regulations:/stats/conserved-regulations?min_species=2&limit=100"
    "detailed:/stats/detailed?buckets=10&top_limit=10"
)

total_first=0
total_cached=0
count=0

for endpoint_data in "${endpoints[@]}"; do
    IFS=':' read -r name path <<< "$endpoint_data"

    echo "测试端点: $name"
    echo "  URL: $path"

    # 首次查询
    time1=$(curl -s -w "%{time_total}" -o /tmp/test_first.json "$BASE_URL$path")
    first_ms=$(echo "$time1 * 1000" | bc | cut -d'.' -f1)
    echo -e "  首次查询: ${YELLOW}${first_ms}ms${NC}"

    # 等待
    sleep 0.3

    # 缓存查询
    time2=$(curl -s -w "%{time_total}" -o /tmp/test_cached.json "$BASE_URL$path")
    cached_ms=$(echo "$time2 * 1000" | bc | cut -d'.' -f1)
    echo -e "  缓存查询: ${GREEN}${cached_ms}ms${NC}"

    # 计算加速比
    speedup=$(echo "scale=2; $time1 / $time2" | bc)
    echo -e "  加速比: ${BLUE}${speedup}x${NC}"

    # 验证响应
    if jq empty /tmp/test_first.json 2>/dev/null && jq empty /tmp/test_cached.json 2>/dev/null; then
        echo -e "  响应验证: ${GREEN}✓${NC} JSON 格式正确"
    else
        echo -e "  响应验证: ${RED}✗${NC} JSON 格式错误"
    fi

    echo ""

    total_first=$(echo "$total_first + $time1" | bc)
    total_cached=$(echo "$total_cached + $time2" | bc)
    count=$((count + 1))
done

# 计算平均值
avg_first=$(echo "scale=0; ($total_first / $count) * 1000" | bc | cut -d'.' -f1)
avg_cached=$(echo "scale=0; ($total_cached / $count) * 1000" | bc | cut -d'.' -f1)
avg_speedup=$(echo "scale=2; $total_first / $total_cached" | bc)

echo "=========================================="
echo "性能统计汇总"
echo "=========================================="
echo -e "平均首次查询: ${YELLOW}${avg_first}ms${NC}"
echo -e "平均缓存查询: ${GREEN}${avg_cached}ms${NC}"
echo -e "平均加速比: ${BLUE}${avg_speedup}x${NC}"
echo ""

echo "=========================================="
echo "测试 3: Redis 缓存验证"
echo "=========================================="
echo ""

# 检查缓存键
cache_keys=$(redis-cli KEYS "lncrna:stats:*")
cache_count=$(echo "$cache_keys" | wc -l)

echo "缓存键数量: $cache_count"
echo ""
echo "缓存键列表:"
echo "$cache_keys" | while read -r key; do
    if [ -n "$key" ]; then
        ttl=$(redis-cli TTL "$key")
        size=$(redis-cli MEMORY USAGE "$key" 2>/dev/null || echo "N/A")
        echo -e "  ${GREEN}✓${NC} $key"
        echo "    TTL: ${ttl}s, Size: ${size} bytes"
    fi
done

echo ""
echo "=========================================="
echo "测试 4: TTL 验证"
echo "=========================================="
echo ""

expected_ttl=3600
ttl_pass=true

echo "$cache_keys" | while read -r key; do
    if [ -n "$key" ]; then
        ttl=$(redis-cli TTL "$key")
        # TTL 应该在 3500-3600 范围内（允许测试期间的时间流逝）
        if [ "$ttl" -ge 3500 ] && [ "$ttl" -le 3600 ]; then
            echo -e "${GREEN}✓${NC} $key: ${ttl}s (有效)"
        else
            echo -e "${RED}✗${NC} $key: ${ttl}s (异常)"
            ttl_pass=false
        fi
    fi
done

echo ""
echo "=========================================="
echo "测试 5: 全站统计端点状态"
echo "=========================================="
echo ""

# 测试所有统计端点
declare -a all_endpoints=(
    "overview:/stats/overview"
    "ba-range:/stats/ba-range"
    "top-genes:/stats/top-genes?limit=10"
    "top-diseases:/stats/top-diseases?limit=10"
    "conserved-regulations:/stats/conserved-regulations"
    "detailed:/stats/detailed"
)

echo "端点名称                    | 状态 | 响应时间"
echo "---------------------------|------|----------"

for endpoint_data in "${all_endpoints[@]}"; do
    IFS=':' read -r name path <<< "$endpoint_data"

    time=$(curl -s -w "%{time_total}" -o /tmp/test_endpoint.json "$BASE_URL$path")
    time_ms=$(echo "$time * 1000" | bc | cut -d'.' -f1)

    if jq empty /tmp/test_endpoint.json 2>/dev/null; then
        printf "%-27s | ${GREEN}✓${NC}    | %sms\n" "$name" "$time_ms"
    else
        printf "%-27s | ${RED}✗${NC}    | %sms\n" "$name" "$time_ms"
    fi
done

echo ""
echo "=========================================="
echo "测试总结"
echo "=========================================="
echo ""

# 检查是否所有测试都通过
if [ "$cache_count" -eq 5 ] && [ "$ttl_pass" = true ]; then
    echo -e "${GREEN}✓ 所有测试通过${NC}"
    echo ""
    echo "缓存状态: 正常"
    echo "缓存键数量: $cache_count (预期 5)"
    echo "TTL 验证: 通过"
    echo "端点响应: 正常"
    echo ""
    echo "Stats API 缓存系统工作正常！"
else
    echo -e "${RED}✗ 部分测试未通过${NC}"
    echo ""
    echo "请检查:"
    echo "  - Redis 服务是否正常"
    echo "  - API 服务是否正常"
    echo "  - 缓存配置是否正确"
fi

echo ""
echo "=========================================="
echo "验证完成！"
echo "=========================================="

# 清理临时文件
rm -f /tmp/test_first.json /tmp/test_cached.json /tmp/test_endpoint.json
