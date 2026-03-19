#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

cat > "$tmp_root/failed.json" <<'EOF'
{
  "result": "failed",
  "passed_stages": 5,
  "failed_stages": 1,
  "first_failed_stage": "frontend-lint"
}
EOF

cat > "$tmp_root/passed.json" <<'EOF'
{
  "result": "passed",
  "passed_stages": 6,
  "failed_stages": 0,
  "first_failed_stage": null
}
EOF

failed_out="$(python3 "$REPO_ROOT/scripts/render_run_tests_summary_overview.py" "$tmp_root/failed.json")"
passed_out="$(python3 "$REPO_ROOT/scripts/render_run_tests_summary_overview.py" "$tmp_root/passed.json")"

echo "$failed_out" | grep -F "## Self-hosted fast CI overview" >/dev/null
echo "$failed_out" | grep -F -- "- Result: **failed**" >/dev/null
echo "$failed_out" | grep -F -- "- Passed stages: 5" >/dev/null
echo "$failed_out" | grep -F -- "- Failed stages: 1" >/dev/null
echo "$failed_out" | grep -F -- "- First failed stage: \`frontend-lint\`" >/dev/null

echo "$passed_out" | grep -F -- "- Result: **passed**" >/dev/null
echo "$passed_out" | grep -F -- "- Passed stages: 6" >/dev/null
echo "$passed_out" | grep -F -- "- Failed stages: 0" >/dev/null
echo "$passed_out" | grep -F -- "- First failed stage: \`none\`" >/dev/null

echo "OK: run-tests summary overview renderer prints expected markdown"
