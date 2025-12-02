#!/bin/bash
# Human LncRNA Atlas - 测试运行脚本
# 运行所有测试（需要后端和前端服务已启动）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  Human LncRNA Atlas - 测试套件"
echo "=========================================="
echo ""

# 检查服务状态
check_services() {
    echo -e "${YELLOW}检查服务状态...${NC}"

    # 检查后端
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "  后端 (8000): ${GREEN}运行中${NC}"
    else
        echo -e "  后端 (8000): ${RED}未运行${NC}"
        echo -e "  ${YELLOW}请先启动后端: cd frontend/backend && python3 -m uvicorn main:app --port 8000${NC}"
        return 1
    fi

    # 检查前端
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        echo -e "  前端 (5173): ${GREEN}运行中${NC}"
    else
        echo -e "  前端 (5173): ${RED}未运行${NC}"
        echo -e "  ${YELLOW}请先启动前端: cd frontend/web && npm run dev${NC}"
        return 1
    fi

    echo ""
    return 0
}

# 运行后端测试
run_backend_tests() {
    echo -e "${YELLOW}运行后端 API 测试...${NC}"
    cd "$PROJECT_ROOT/frontend/backend"

    if python3 -m pytest tests/test_api_contracts.py -v --tb=short; then
        echo -e "${GREEN}后端测试通过!${NC}"
        return 0
    else
        echo -e "${RED}后端测试失败${NC}"
        return 1
    fi
}

# 运行前端单元测试
run_frontend_unit_tests() {
    echo -e "${YELLOW}运行前端单元测试...${NC}"
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

    case "${1:-all}" in
        backend)
            check_services || exit 1
            run_backend_tests || failed=1
            ;;
        unit)
            run_frontend_unit_tests || failed=1
            ;;
        e2e)
            check_services || exit 1
            run_e2e_tests || failed=1
            ;;
        all)
            check_services || exit 1
            echo ""
            run_backend_tests || failed=1
            echo ""
            run_frontend_unit_tests || failed=1
            echo ""
            run_e2e_tests || failed=1
            ;;
        *)
            echo "用法: $0 [backend|unit|e2e|all]"
            echo ""
            echo "  backend  - 运行后端 API 合同测试"
            echo "  unit     - 运行前端单元测试"
            echo "  e2e      - 运行前端 E2E 测试"
            echo "  all      - 运行所有测试（默认）"
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
