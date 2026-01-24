#!/bin/bash
# ChIP-seq API Tests Script
# Run all ChIP-seq related tests including cell line comparison

set -euo pipefail  # Exit on error (incl. undefined vars and pipe failures)

require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: Missing required command: $cmd"
        exit 1
    fi
}

require_cmd curl
require_cmd grep
require_cmd wc

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

resolve_backend_python() {
    # Prefer backend virtualenv for stable deps
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

PYTHON_BIN="$(resolve_backend_python)"
if ! "$PYTHON_BIN" -c "import pytest" > /dev/null 2>&1; then
    echo "ERROR: pytest is not available in backend python: ${PYTHON_BIN}"
    echo "Hint: cd ${BACKEND_DIR} && pip install -r requirements-dev.txt -c constraints.txt"
    exit 1
fi

# Proxy-friendly defaults (avoid curl hanging via http_proxy)
DEFAULT_NO_PROXY="127.0.0.1,localhost,::1"
export NO_PROXY="${NO_PROXY:-$DEFAULT_NO_PROXY}"
export no_proxy="${no_proxy:-$DEFAULT_NO_PROXY}"

# Optional: override backend service URL
# - API_BASE_URL preferred (can be http://host:port or http://host:port/api/v1)
# - HLA_BACKEND_URL / BACKEND_URL supported as aliases
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

echo "=================================="
echo "ChIP-seq API Tests"
echo "=================================="
echo ""

# Check if the backend service is running
echo "Checking service status..."
if ! curl -fsS --connect-timeout 2 --max-time 5 "${BACKEND_ORIGIN_URL}/health" > /dev/null; then
    echo "ERROR: Backend service is not running!"
    echo "Please start the service first:"
    echo "   uvicorn main:app --host 0.0.0.0 --port 8000"
    echo "   (or set API_BASE_URL/HLA_BACKEND_URL/BACKEND_URL to your backend origin URL)"
    exit 1
fi
echo "Service is running"
echo ""

# Navigate to the backend directory
cd "$BACKEND_DIR"

# Run ChIP-seq API tests
echo "Running ChIP-seq API tests..."
echo ""

# Run all ChIP-seq tests
"$PYTHON_BIN" -m pytest tests/test_chipseq_api.py -v --tb=short -x

echo ""
echo "=================================="
echo "Test Summary"
echo "=================================="

# Count test results
TOTAL_TESTS=$("$PYTHON_BIN" -m pytest tests/test_chipseq_api.py --collect-only -q 2>/dev/null | grep "test" | wc -l || true)
echo "Total ChIP-seq tests: $TOTAL_TESTS"

# Run with more verbose output for cell line comparison tests specifically
echo ""
echo "Running Cell Line Comparison Tests..."
echo ""
"$PYTHON_BIN" -m pytest tests/test_chipseq_api.py::TestChIPSeqCellLineComparison -v --tb=short

echo ""
echo "=================================="
echo "ChIP-seq Tests Complete"
echo "=================================="
