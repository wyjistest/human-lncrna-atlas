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

# 检查服务是否运行
echo "📡 检查服务状态..."
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ 服务未运行！请先启动服务："
    echo "   uvicorn main:app --host 0.0.0.0 --port 8000"
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
HEALTH=$(curl -s http://localhost:8000/health | "$PYTHON_BIN" -c "import sys, json; print(json.load(sys.stdin)['status'])")
if [ "$HEALTH" = "healthy" ]; then
    echo "✅ /health - OK"
else
    echo "❌ /health - FAILED"
    exit 1
fi

# 监控指标
METRICS=$(curl -s http://localhost:8000/metrics | "$PYTHON_BIN" -c "import sys, json; print(json.load(sys.stdin)['total_requests'])")
if [ -n "$METRICS" ]; then
    echo "✅ /metrics - OK (${METRICS} requests)"
else
    echo "❌ /metrics - FAILED"
    exit 1
fi

# 基因列表
GENES=$(curl -s "http://localhost:8000/api/v1/genes?page=1&page_size=1" | "$PYTHON_BIN" -c "import sys, json; print(json.load(sys.stdin)['total'])")
if [ "$GENES" = "17248" ]; then
    echo "✅ /api/v1/genes - OK (total: ${GENES})"
else
    echo "❌ /api/v1/genes - FAILED (expected 17248, got ${GENES})"
    exit 1
fi

# 调控关系
REGS=$(curl -s "http://localhost:8000/api/v1/regulations?page=1&page_size=1" | "$PYTHON_BIN" -c "import sys, json; print(json.load(sys.stdin)['total'])")
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
