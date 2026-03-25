#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$REPO_ROOT"
python3 scripts/tests/test_sync_backlog_issues.py

echo "OK: sync_backlog_issues.py unit tests passed"
