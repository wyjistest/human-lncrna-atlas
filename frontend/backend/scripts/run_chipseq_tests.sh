#!/bin/bash
# ChIP-seq API Tests Script
# Run all ChIP-seq related tests including cell line comparison

set -e  # Exit on error

echo "=================================="
echo "ChIP-seq API Tests"
echo "=================================="
echo ""

# Check if the backend service is running
echo "Checking service status..."
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "ERROR: Backend service is not running!"
    echo "Please start the service first:"
    echo "   uvicorn main:app --host 0.0.0.0 --port 8000"
    exit 1
fi
echo "Service is running"
echo ""

# Navigate to the backend directory
cd "$(dirname "$0")/.."

# Run ChIP-seq API tests
echo "Running ChIP-seq API tests..."
echo ""

# Run all ChIP-seq tests
pytest tests/test_chipseq_api.py -v --tb=short -x

echo ""
echo "=================================="
echo "Test Summary"
echo "=================================="

# Count test results
TOTAL_TESTS=$(pytest tests/test_chipseq_api.py --collect-only -q 2>/dev/null | grep "test" | wc -l)
echo "Total ChIP-seq tests: $TOTAL_TESTS"

# Run with more verbose output for cell line comparison tests specifically
echo ""
echo "Running Cell Line Comparison Tests..."
echo ""
pytest tests/test_chipseq_api.py::TestChIPSeqCellLineComparison -v --tb=short

echo ""
echo "=================================="
echo "ChIP-seq Tests Complete"
echo "=================================="
