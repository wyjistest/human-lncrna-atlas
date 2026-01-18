#!/bin/bash
# Human LncRNA Atlas - 测试运行脚本
# 运行所有测试（需要后端和前端服务已启动）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/frontend/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend/web"

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

ensure_frontend_deps() {
    require_cmd npm || return 1
    if [ ! -f "$FRONTEND_DIR/package-lock.json" ]; then
        echo -e "${RED}未找到前端锁文件: ${FRONTEND_DIR}/package-lock.json${NC}"
        return 1
    fi

    # 仅在 node_modules 缺失时自动安装，避免每次都重装依赖导致本地过慢。
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        echo -e "${YELLOW}前端依赖未安装，执行 npm ci...${NC}"
        (cd "$FRONTEND_DIR" && npm ci)
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

ensure_backend_python() {
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

    return 0
}

ensure_backend_pytest() {
    local python_bin="$1"

    ensure_backend_python "$python_bin" || return 1

    if ! "$python_bin" -c "import pytest" > /dev/null 2>&1; then
        echo -e "${RED}后端 pytest 不可用（请在后端虚拟环境中安装依赖）${NC}"
        echo -e "${YELLOW}建议：cd ${BACKEND_DIR} && pip install -r requirements-dev.txt -c constraints.txt${NC}"
        return 1
    fi

    return 0
}

ensure_backend_ruff() {
    local ruff_bin="$1"

    # ruff_bin 可能是绝对路径或命令名
    if [[ "$ruff_bin" == /* ]]; then
        if [ ! -x "$ruff_bin" ]; then
            echo -e "${RED}后端 ruff 不可执行: ${ruff_bin}${NC}"
            return 1
        fi
    else
        require_cmd "$ruff_bin" || return 1
    fi

    return 0
}

ensure_backend_pip_audit() {
    local python_bin="$1"

    ensure_backend_python "$python_bin" || return 1

    if ! "$python_bin" -c "import pip_audit" > /dev/null 2>&1; then
        echo -e "${RED}后端 pip-audit 不可用（请在后端虚拟环境中安装依赖）${NC}"
        echo -e "${YELLOW}建议：cd ${BACKEND_DIR} && pip install pip-audit${NC}"
        return 1
    fi

    return 0
}

# 运行后端 Lint（ruff）
run_backend_lint() {
    echo -e "${YELLOW}运行后端 Lint (ruff check)...${NC}"
    local python_bin
    python_bin="$(resolve_backend_python)"

    local ruff_bin="ruff"
    if [[ "$python_bin" == /* ]]; then
        ruff_bin="$(dirname "$python_bin")/ruff"
    fi

    ensure_backend_ruff "$ruff_bin" || {
        echo -e "${YELLOW}建议：cd ${BACKEND_DIR} && pip install -r requirements-dev.txt -c constraints.txt${NC}"
        return 1
    }

    cd "$BACKEND_DIR"

    if "$ruff_bin" check .; then
        echo -e "${GREEN}后端 Lint 通过!${NC}"
        return 0
    else
        echo -e "${RED}后端 Lint 失败${NC}"
        return 1
    fi
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

run_backend_security_audit() {
    echo -e "${YELLOW}运行后端依赖安全审计 (pip-audit --strict)...${NC}"
    local python_bin
    python_bin="$(resolve_backend_python)"
    ensure_backend_pip_audit "$python_bin" || return 1

    cd "$BACKEND_DIR"

    if "$python_bin" -m pip_audit -r requirements.txt --strict --progress-spinner off; then
        echo -e "${GREEN}后端依赖安全审计通过!${NC}"
        return 0
    else
        echo -e "${RED}后端依赖安全审计失败（发现漏洞）${NC}"
        return 1
    fi
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

run_backend_checks() {
    echo -e "${YELLOW}运行后端导入与语法检查（对齐 CI）...${NC}"
    local python_bin
    python_bin="$(resolve_backend_python)"
    ensure_backend_python "$python_bin" || return 1

    cd "$BACKEND_DIR"

    "$python_bin" -c "from app.core.config import settings; print('Config loaded')"
    "$python_bin" -c "from app.core.database import engine; print('Database module loaded')"
    "$python_bin" -c "from app.core.cache import cache; print('Cache module loaded')"
    "$python_bin" -c "from app.core.exceptions import sanitize_db_error; print('Exceptions module loaded')"
    "$python_bin" -c "import main; print('Main app loaded')"

    "$python_bin" -m py_compile main.py
    find app -name "*.py" -exec "$python_bin" -m py_compile {} \;

    echo -e "${GREEN}后端导入与语法检查通过!${NC}"
    return 0
}

run_etl_checks() {
    echo -e "${YELLOW}运行 ETL 输入校验单元测试 (pytest etl/tests)...${NC}"
    local python_bin
    python_bin="$(resolve_backend_python)"
    ensure_backend_pytest "$python_bin" || return 1

    cd "$PROJECT_ROOT"

    if "$python_bin" -m pytest -q etl/tests; then
        echo -e "${GREEN}ETL 单元测试通过!${NC}"
        return 0
    else
        echo -e "${RED}ETL 单元测试失败${NC}"
        return 1
    fi
}

run_scripts_smoke_tests() {
    echo -e "${YELLOW}运行脚本冒烟测试（离线资源下载脚本）...${NC}"
    if bash scripts/genomes/tests/test_download_igv_assets.sh; then
        echo -e "${GREEN}脚本冒烟测试通过!${NC}"
        return 0
    else
        echo -e "${RED}脚本冒烟测试失败${NC}"
        return 1
    fi
}

run_docs_checks() {
    echo -e "${YELLOW}运行文档命令漂移检查...${NC}"
    require_cmd python3 || return 1

    cd "$PROJECT_ROOT"
    if python3 scripts/check_docs_commands.py; then
        echo -e "${GREEN}文档命令漂移检查通过!${NC}"
        return 0
    else
        echo -e "${RED}文档命令漂移检查失败${NC}"
        return 1
    fi
}

# 运行前端单元测试
run_frontend_unit_tests() {
    echo -e "${YELLOW}运行前端单元测试...${NC}"
    ensure_frontend_deps || return 1
    cd "$FRONTEND_DIR"

    if npm run test:run; then
        echo -e "${GREEN}前端单元测试通过!${NC}"
        return 0
    else
        echo -e "${RED}前端单元测试失败${NC}"
        return 1
    fi
}

run_frontend_security_audit() {
    echo -e "${YELLOW}运行前端依赖安全审计 (npm audit --audit-level=high)...${NC}"
    ensure_frontend_deps || return 1
    cd "$FRONTEND_DIR"

    if npm audit --registry=https://registry.npmjs.org --audit-level=high; then
        echo -e "${GREEN}前端依赖安全审计通过!${NC}"
        return 0
    else
        echo -e "${RED}前端依赖安全审计失败（发现 high/critical 漏洞）${NC}"
        return 1
    fi
}

run_frontend_lint() {
    echo -e "${YELLOW}运行前端 Lint (ESLint)...${NC}"
    ensure_frontend_deps || return 1
    cd "$FRONTEND_DIR"

    if npm run lint; then
        echo -e "${GREEN}前端 Lint 通过!${NC}"
        return 0
    else
        echo -e "${RED}前端 Lint 失败${NC}"
        return 1
    fi
}

run_frontend_build() {
    echo -e "${YELLOW}运行前端构建 (Vite build)...${NC}"
    ensure_frontend_deps || return 1
    cd "$FRONTEND_DIR"

    if npm run build; then
        echo -e "${GREEN}前端构建通过!${NC}"
        return 0
    else
        echo -e "${RED}前端构建失败${NC}"
        return 1
    fi
}

# 运行 E2E 测试
run_e2e_tests() {
    echo -e "${YELLOW}运行 E2E 测试...${NC}"
    ensure_frontend_deps || return 1
    cd "$FRONTEND_DIR"

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
        security-audit)
            run_backend_security_audit || failed=1
            echo ""
            run_frontend_security_audit || failed=1
            ;;
        backend-lint)
            run_backend_lint || failed=1
            ;;
        backend-checks)
            run_backend_checks || failed=1
            ;;
        etl-checks)
            run_etl_checks || failed=1
            ;;
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
        frontend-lint)
            run_frontend_lint || failed=1
            ;;
        frontend-build)
            run_frontend_build || failed=1
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
        ci)
            # 对齐 GitHub Actions `.github/workflows/test.yml` 的核心质量门禁（不含 secret scan / security-audit）
            run_backend_lint || failed=1
            echo ""
            run_backend_checks || failed=1
            echo ""
            run_etl_checks || failed=1
            echo ""
            run_scripts_smoke_tests || failed=1
            echo ""
            run_docs_checks || failed=1
            echo ""
            run_backend_unit_tests || failed=1
            echo ""
            run_frontend_unit_tests || failed=1
            echo ""
            run_frontend_lint || failed=1
            echo ""
            run_frontend_build || failed=1
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
        docs-check)
            run_docs_checks || failed=1
            ;;
        *)
            echo "用法: $0 [smoke|security-audit|unit|etl-checks|docs-check|backend-unit|backend-checks|backend-lint|frontend-lint|frontend-build|ci|backend|e2e|all]"
            echo ""
            echo "  smoke        - 运行所有单元测试（默认，无外部依赖）"
            echo "  security-audit - 运行依赖安全审计（pip-audit + npm audit）"
            echo "  unit         - 运行前端单元测试"
            echo "  etl-checks   - 运行 ETL 输入校验单元测试 (pytest etl/tests)"
            echo "  docs-check   - 检查文档命令漂移（启动命令示例）"
            echo "  backend-unit - 运行后端单元测试 (pytest -m unit)"
            echo "  backend-checks - 运行后端导入与语法检查（对齐 CI）"
            echo "  backend-lint - 运行后端 Lint (ruff check)"
            echo "  frontend-lint  - 运行前端 Lint (ESLint)"
            echo "  frontend-build - 运行前端构建 (Vite build)"
            echo "  ci           - 对齐 GitHub Actions 的核心检查集合"
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
