#!/bin/bash
#
# ChIP-seq Test Runner Script
# Runs both backend API tests and frontend E2E tests for ChIP-seq functionality
#
# Usage:
#   ./run_chipseq_tests.sh           # Run all tests
#   ./run_chipseq_tests.sh backend   # Run only backend tests
#   ./run_chipseq_tests.sh e2e       # Run only E2E tests
#   ./run_chipseq_tests.sh --help    # Show help
#

set -euo pipefail  # Exit on error (incl. undefined vars and pipe failures)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project directories (support overrides via env vars)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}[ERROR]${NC} Missing required command: $cmd"
        return 1
    fi
    return 0
}

require_cmd curl || exit 1
require_cmd grep || exit 1

GITHUB_REPO="${GITHUB_REPO:-${REPO_DIR}}"
BACKEND_DIR="${BACKEND_DIR:-${GITHUB_REPO}/frontend/backend}"

if [ -z "${FRONTEND_DIR:-}" ]; then
    if [ -n "${LOCAL_DEV:-}" ]; then
        FRONTEND_DIR="${LOCAL_DEV}/frontend/web"
    else
        FRONTEND_DIR="${GITHUB_REPO}/frontend/web"
    fi
fi

# Functions
print_header() {
    echo -e "\n${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

show_help() {
    echo "ChIP-seq Test Runner"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  backend    Run backend API tests only"
    echo "  e2e        Run frontend E2E tests only"
    echo "  all        Run all tests (default)"
    echo "  --help     Show this help message"
    echo ""
    echo "Prerequisites:"
    echo "  - Backend server running on http://localhost:8000"
    echo "  - Frontend dev server running on http://localhost:5173 (for E2E)"
    echo "  - Backend venv (.venv/venv) with pytest installed"
    echo "  - Node.js with Playwright installed"
}

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

check_backend_server() {
    print_header "Checking Backend Server"

    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/stats/overview | grep -q "200"; then
        print_success "Backend server is running at http://localhost:8000"
        return 0
    else
        print_warning "Backend server may not be running at http://localhost:8000"
        print_warning "API tests may fail if server is not available"
        return 1
    fi
}

check_frontend_server() {
    print_header "Checking Frontend Server"

    if curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 | grep -q "200"; then
        print_success "Frontend server is running at http://localhost:5173"
        return 0
    else
        print_warning "Frontend server may not be running at http://localhost:5173"
        print_warning "E2E tests may fail if server is not available"
        return 1
    fi
}

run_backend_tests() {
    print_header "Running Backend ChIP-seq API Tests"

    if [ ! -d "${BACKEND_DIR}" ]; then
        print_error "Backend directory not found: ${BACKEND_DIR}"
        return 1
    fi

    cd "${BACKEND_DIR}"

    echo "Test directory: ${BACKEND_DIR}/tests"
    echo "Test file: test_chipseq_api.py"
    echo ""

    local python_bin
    python_bin="$(resolve_backend_python)"
    if ! "$python_bin" -c "import pytest" > /dev/null 2>&1; then
        print_error "pytest not available in backend python: ${python_bin}"
        print_error "Hint: cd ${BACKEND_DIR} && pip install -r requirements-dev.txt -c constraints.txt"
        return 1
    fi

    if "$python_bin" -m pytest tests/test_chipseq_api.py -v --tb=short 2>&1; then
        print_success "Backend tests passed!"
        return 0
    else
        local exit_code=$?
        print_error "Backend tests failed with exit code ${exit_code}"
        return ${exit_code}
    fi
}

run_e2e_tests() {
    print_header "Running Frontend E2E ChIP-seq Tests"

    require_cmd npx || return 1

    if [ ! -d "${FRONTEND_DIR}" ]; then
        print_error "Frontend directory not found: ${FRONTEND_DIR}"
        return 1
    fi

    cd "${FRONTEND_DIR}"

    echo "Test directory: ${FRONTEND_DIR}/e2e"
    echo "Test file: chipseq-flow.spec.ts"
    echo ""

    local exit_code=0
    if npx playwright test e2e/chipseq-flow.spec.ts --reporter=html 2>&1; then
        print_success "E2E tests passed!"
    else
        exit_code=$?
        print_error "E2E tests failed with exit code ${exit_code}"
    fi

    echo ""
    echo "HTML report available at: ${FRONTEND_DIR}/playwright-report/index.html"

    return ${exit_code}
}

run_all_tests() {
    OVERALL_EXIT_CODE=0

    # Check servers
    check_backend_server || true
    check_frontend_server || true

    # Run backend tests
    run_backend_tests || OVERALL_EXIT_CODE=1

    # Run E2E tests
    run_e2e_tests || OVERALL_EXIT_CODE=1

    # Summary
    print_header "Test Summary"

    if [ $OVERALL_EXIT_CODE -eq 0 ]; then
        print_success "All tests passed!"
    else
        print_error "Some tests failed. Please check the output above."
    fi

    return $OVERALL_EXIT_CODE
}

# Main script
case "${1:-all}" in
    backend)
        check_backend_server || true
        run_backend_tests
        ;;
    e2e)
        check_frontend_server || true
        run_e2e_tests
        ;;
    all)
        run_all_tests
        ;;
    --help|-h)
        show_help
        exit 0
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
