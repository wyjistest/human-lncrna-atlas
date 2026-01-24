#!/bin/bash
# 快速回归测试脚本
# 用途：部署前验证所有核心功能

set -euo pipefail  # 遇到错误立即退出（含未定义变量与管道失败）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

resolve_backend_python() {
    # 优先使用后端虚拟环境，避免依赖全局 Python（更稳定）
    if [ -n "${BACKEND_PYTHON:-}" ]; then
        echo "$BACKEND_PYTHON"
        return 0
    fi

    if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
        echo "$BACKEND_DIR/.venv/bin/python"
        return 0
    fi
    if [ -x "$BACKEND_DIR/venv/bin/python" ]; then
        echo "$BACKEND_DIR/venv/bin/python"
        return 0
    fi

    echo "python3"
}

cd "$BACKEND_DIR"

echo "=================================="
echo "🧪 Human LncRNA Atlas - 回归测试"
echo "=================================="
echo ""

# 兼容本地代理环境：默认绕过 localhost/127.0.0.1，避免 curl 走 http_proxy 导致卡住。
DEFAULT_NO_PROXY="127.0.0.1,localhost,::1"
export NO_PROXY="${NO_PROXY:-$DEFAULT_NO_PROXY}"
export no_proxy="${no_proxy:-$DEFAULT_NO_PROXY}"

# 可选：为受保护端点（例如 /metrics）提供 Admin API Key
# - 生产环境通常启用 ADMIN_REQUIRE_API_KEY=true，此时需要提供 X-Admin-API-Key 才能访问 /metrics
# - 本脚本默认从环境变量 ADMIN_API_KEY 读取（与后端配置一致）
ADMIN_HEADER_ARGS=()
if [ -n "${ADMIN_API_KEY:-}" ]; then
    ADMIN_HEADER_ARGS=(-H "X-Admin-API-Key: ${ADMIN_API_KEY}")
fi

# 可选：覆盖后端服务地址（默认本地开发端口）
# - 推荐使用 API_BASE_URL（可为 http://host:port 或 http://host:port/api/v1）
# - 兼容：HLA_BACKEND_URL / BACKEND_URL（同义，优先级低于 API_BASE_URL）
normalize_backend_origin_url() {
    local raw="${1:-}"
    raw="${raw%/}"
    if [[ "$raw" == */api/v1 ]]; then
        raw="${raw%/api/v1}"
    fi
    echo "$raw"
}

BACKEND_ORIGIN_URL_RAW="${API_BASE_URL:-${HLA_BACKEND_URL:-${BACKEND_URL:-http://localhost:8000}}}"
BACKEND_ORIGIN_URL="$(normalize_backend_origin_url "$BACKEND_ORIGIN_URL_RAW")"
API_V1_BASE_URL="${BACKEND_ORIGIN_URL%/}/api/v1"

# 检查服务是否运行
echo "📡 检查服务状态..."
if ! curl -fsS --connect-timeout 2 --max-time 5 "${BACKEND_ORIGIN_URL}/health" > /dev/null; then
    echo "❌ 服务未运行！请先启动服务："
    echo "   uvicorn main:app --host 0.0.0.0 --port 8000"
    echo "   (或设置 API_BASE_URL/HLA_BACKEND_URL/BACKEND_URL 指向实际后端地址)"
    exit 1
fi
echo "✅ 服务正常运行"
echo ""

PYTHON_BIN="$(resolve_backend_python)"
if ! "$PYTHON_BIN" -c "import pytest" > /dev/null 2>&1; then
    echo "❌ pytest 不可用（请先安装后端依赖）"
    echo "   cd ${BACKEND_DIR} && pip install -r requirements-dev.txt -c constraints.txt"
    exit 1
fi

# 运行集成测试
echo "🔍 运行集成测试（13个测试）..."
"$PYTHON_BIN" -m pytest tests/test_api_smoke.py -v --tb=short
echo ""

# 运行性能测试
echo "⚡ 运行性能测试（7个测试）..."
"$PYTHON_BIN" -m pytest tests/test_performance.py -v -s --tb=short
echo ""

# 验证关键端点
echo "🎯 验证关键端点..."

# 健康检查
HEALTH=$(curl -fsS --connect-timeout 2 --max-time 10 "${BACKEND_ORIGIN_URL}/health" | "$PYTHON_BIN" -c "import sys, json; print(json.load(sys.stdin)['status'])")
if [ "$HEALTH" = "healthy" ]; then
    echo "✅ /health - OK"
else
    echo "❌ /health - FAILED"
    exit 1
fi

# 监控指标
METRICS_LINES=$(curl -fsS --connect-timeout 2 --max-time 10 "${ADMIN_HEADER_ARGS[@]}" "${BACKEND_ORIGIN_URL}/metrics" | wc -l | tr -d '[:space:]')
if [ "${METRICS_LINES:-0}" -gt 0 ]; then
    echo "✅ /metrics - OK (${METRICS_LINES} lines, Prometheus text format)"
else
    echo "❌ /metrics - FAILED (empty response)"
    exit 1
fi

# 基因列表
GENES=$(curl -fsS --connect-timeout 2 --max-time 10 "${API_V1_BASE_URL}/genes?page=1&page_size=1" | "$PYTHON_BIN" -c "import sys, json; print(json.load(sys.stdin)['total'])")
if [ "$GENES" = "17248" ]; then
    echo "✅ /api/v1/genes - OK (total: ${GENES})"
else
    echo "❌ /api/v1/genes - FAILED (expected 17248, got ${GENES})"
    exit 1
fi

# 调控关系
REGS=$(curl -fsS --connect-timeout 2 --max-time 10 "${API_V1_BASE_URL}/regulations?page=1&page_size=1" | "$PYTHON_BIN" -c "import sys, json; print(json.load(sys.stdin)['total'])")
if [ "$REGS" = "804630" ]; then
    echo "✅ /api/v1/regulations - OK (total: ${REGS})"
else
    echo "❌ /api/v1/regulations - FAILED (expected 804630, got ${REGS})"
    exit 1
fi

echo ""
echo "=================================="
echo "🎉 所有测试通过！"
echo "=================================="
echo ""
echo "📊 测试总结："
echo "  - 集成测试: 13/13 通过"
echo "  - 性能测试: 7/7 通过"
echo "  - 端点验证: 4/4 通过"
echo ""
echo "✅ 代码可以部署到生产环境"
