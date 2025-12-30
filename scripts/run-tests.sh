#!/bin/bash
# Human LncRNA Atlas - 测试运行脚本
# 运行所有测试（需要后端和前端服务已启动）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/frontend/backend"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  Human LncRNA Atlas - 测试套件"
echo "=========================================="
echo ""

require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" > /dev/null 2>&1; then
        echo -e "${RED}缺少依赖命令: ${cmd}${NC}"
        return 1
    fi
    return 0
}

resolve_backend_python() {
    # 优先使用后端虚拟环境，避免依赖全局 Python（CI/本地更稳定）
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

ensure_backend_pytest() {
    local python_bin="$1"

    # python_bin 可能是绝对路径或命令名
    if [[ "$python_bin" == /* ]]; then
        if [ ! -x "$python_bin" ]; then
            echo -e "${RED}后端 Python 不可执行: ${python_bin}${NC}"
            return 1
        fi
    else
        require_cmd "$python_bin" || return 1
    fi

    if ! "$python_bin" -c "import pytest" > /dev/null 2>&1; then
        echo -e "${RED}后端 pytest 不可用（请在后端虚拟环境中安装依赖）${NC}"
        echo -e "${YELLOW}建议：cd ${BACKEND_DIR} && pip install -r requirements.txt${NC}"
        return 1
    fi

    return 0
}

# 检查服务状态
check_services() {
    echo -e "${YELLOW}检查服务状态...${NC}"
    require_cmd curl || return 1

    # 检查后端 (-f: fail on HTTP errors, -sS: silent but show errors)
    if curl -fsS http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "  后端 (8000): ${GREEN}运行中${NC}"
    else
        echo -e "  后端 (8000): ${RED}未运行或返回错误${NC}"
        echo -e "  ${YELLOW}请先启动后端: cd frontend/backend && python3 -m uvicorn main:app --port 8000${NC}"
        return 1
    fi

    # 检查前端 (-f: fail on HTTP errors like 502, -sS: silent but show errors)
    if curl -fsS http://localhost:5173 > /dev/null 2>&1; then
        echo -e "  前端 (5173): ${GREEN}运行中${NC}"
    else
        echo -e "  前端 (5173): ${RED}未运行或返回错误${NC}"
        echo -e "  ${YELLOW}请先启动前端: cd frontend/web && npm run dev${NC}"
        return 1
    fi

    echo ""
    return 0
}

# 运行后端 API 合同测试 (需要服务运行)
run_backend_tests() {
    echo -e "${YELLOW}运行后端 API 合同测试...${NC}"
    local python_bin
    python_bin="$(resolve_backend_python)"
    ensure_backend_pytest "$python_bin" || return 1

    cd "$BACKEND_DIR"

    # integration 测试默认是 opt-in（见 frontend/backend/tests/conftest.py）
    if RUN_INTEGRATION_TESTS=1 "$python_bin" -m pytest tests/test_api_contracts.py -v --tb=short; then
        echo -e "${GREEN}后端 API 测试通过!${NC}"
        return 0
    else
        echo -e "${RED}后端 API 测试失败${NC}"
        return 1
    fi
}

# 运行后端单元测试 (无外部依赖)
run_backend_unit_tests() {
    echo -e "${YELLOW}运行后端单元测试 (pytest -m unit)...${NC}"
    local python_bin
    python_bin="$(resolve_backend_python)"
    ensure_backend_pytest "$python_bin" || return 1

    cd "$BACKEND_DIR"

    if "$python_bin" -m pytest -m unit -v --tb=short; then
        echo -e "${GREEN}后端单元测试通过!${NC}"
        return 0
    else
        echo -e "${RED}后端单元测试失败${NC}"
        return 1
    fi
}

# 运行前端单元测试
run_frontend_unit_tests() {
    echo -e "${YELLOW}运行前端单元测试...${NC}"
    require_cmd npm || return 1
    cd "$PROJECT_ROOT/frontend/web"

    if npm run test:run; then
        echo -e "${GREEN}前端单元测试通过!${NC}"
        return 0
    else
        echo -e "${RED}前端单元测试失败${NC}"
        return 1
    fi
}

# 运行 E2E 测试
run_e2e_tests() {
    echo -e "${YELLOW}运行 E2E 测试...${NC}"
    require_cmd npm || return 1
    cd "$PROJECT_ROOT/frontend/web"

    if npm run test:e2e; then
        echo -e "${GREEN}E2E 测试通过!${NC}"
        return 0
    else
        echo -e "${RED}E2E 测试失败${NC}"
        return 1
    fi
}

# 主函数
main() {
    local failed=0

    case "${1:-smoke}" in
        backend)
            check_services || exit 1
            run_backend_tests || failed=1
            ;;
        backend-unit)
            run_backend_unit_tests || failed=1
            ;;
        unit)
            run_frontend_unit_tests || failed=1
            ;;
        e2e)
            check_services || exit 1
            run_e2e_tests || failed=1
            ;;
        smoke)
            # 默认: 运行所有无外部依赖的单元测试
            run_backend_unit_tests || failed=1
            echo ""
            run_frontend_unit_tests || failed=1
            ;;
        all)
            # 完整测试: 需要后端和前端服务运行
            check_services || exit 1
            echo ""
            run_backend_tests || failed=1
            echo ""
            run_frontend_unit_tests || failed=1
            echo ""
            run_e2e_tests || failed=1
            ;;
        *)
            echo "用法: $0 [smoke|unit|backend-unit|backend|e2e|all]"
            echo ""
            echo "  smoke        - 运行所有单元测试（默认，无外部依赖）"
            echo "  unit         - 运行前端单元测试"
            echo "  backend-unit - 运行后端单元测试 (pytest -m unit)"
            echo "  backend      - 运行后端 API 合同测试（需要服务运行）"
            echo "  e2e          - 运行前端 E2E 测试（需要服务运行）"
            echo "  all          - 运行所有测试（需要服务运行）"
            exit 1
            ;;
    esac

    echo ""
    echo "=========================================="
    if [ $failed -eq 0 ]; then
        echo -e "  ${GREEN}所有测试通过!${NC}"
    else
        echo -e "  ${RED}部分测试失败${NC}"
    fi
    echo "=========================================="

    exit $failed
}

main "$@"
