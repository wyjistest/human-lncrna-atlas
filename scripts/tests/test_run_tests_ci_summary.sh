#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

mkdir -p \
  "$tmp_root/bin" \
  "$tmp_root/scripts" \
  "$tmp_root/scripts/genomes/tests" \
  "$tmp_root/scripts/research" \
  "$tmp_root/frontend/backend/.venv/bin" \
  "$tmp_root/frontend/backend/app" \
  "$tmp_root/frontend/backend/scripts" \
  "$tmp_root/frontend/web/node_modules"

cp "$REPO_ROOT/scripts/run-tests.sh" "$tmp_root/scripts/run-tests.sh"
chmod +x "$tmp_root/scripts/run-tests.sh"

cat > "$tmp_root/frontend/backend/main.py" <<'EOF'
print("backend ok")
EOF

cat > "$tmp_root/frontend/backend/app/__init__.py" <<'EOF'
# stub
EOF

cat > "$tmp_root/frontend/backend/requirements.txt" <<'EOF'
# stub
EOF

cat > "$tmp_root/frontend/backend/requirements-dev.txt" <<'EOF'
# stub
EOF

cat > "$tmp_root/frontend/backend/constraints.txt" <<'EOF'
# stub
EOF

cat > "$tmp_root/frontend/backend/scripts/db_migrate.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "verify" ]]; then
  exit 0
fi
exit 1
EOF
chmod +x "$tmp_root/frontend/backend/scripts/db_migrate.sh"

cat > "$tmp_root/scripts/genomes/tests/test_download_igv_assets.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "download igv assets ok"
exit 0
EOF
chmod +x "$tmp_root/scripts/genomes/tests/test_download_igv_assets.sh"

cat > "$tmp_root/scripts/research/example_report.py" <<'EOF'
print("research syntax ok")
EOF

cat > "$tmp_root/scripts/research/generate_example_sample_baseline_local.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "research sample baseline ok"
EOF
chmod +x "$tmp_root/scripts/research/generate_example_sample_baseline_local.sh"

cat > "$tmp_root/scripts/check_docs_commands.py" <<'EOF'
print("docs commands ok")
EOF

cat > "$tmp_root/scripts/check_docs_heading_artifacts.py" <<'EOF'
print("docs headings ok")
EOF

cat > "$tmp_root/scripts/check_docs_status_markers.py" <<'EOF'
print("docs status markers ok")
EOF

cat > "$tmp_root/frontend/backend/.venv/bin/python" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-c" ]]; then
  exit 0
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "py_compile" ]]; then
  exit 0
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "pip" && "${3:-}" == "install" ]]; then
  exit 0
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "pytest" ]]; then
  exit 0
fi

exit 0
EOF
chmod +x "$tmp_root/frontend/backend/.venv/bin/python"

cat > "$tmp_root/frontend/backend/.venv/bin/ruff" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF
chmod +x "$tmp_root/frontend/backend/.venv/bin/ruff"

cat > "$tmp_root/bin/python3" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF
chmod +x "$tmp_root/bin/python3"

cat > "$tmp_root/bin/npm" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "run" && "${2:-}" == "lint" ]]; then
  echo "frontend lint failed" >&2
  exit 1
fi

if [[ "${1:-}" == "run" && "${2:-}" == "build" ]]; then
  mkdir -p dist
  echo "<html></html>" > dist/index.html
  exit 0
fi

exit 0
EOF
chmod +x "$tmp_root/bin/npm"

cat > "$tmp_root/frontend/web/package-lock.json" <<'EOF'
{}
EOF
cat > "$tmp_root/frontend/web/node_modules/.package-lock.json" <<'EOF'
{}
EOF

summary_path="$tmp_root/test-results/run-tests-summary.md"
json_path="$tmp_root/test-results/run-tests-summary.json"
artifact_dir="$tmp_root/test-results/artifacts"

set +e
(
  cd "$tmp_root"
  PATH="$tmp_root/bin:$PATH" \
    RUN_TESTS_SUMMARY_ACTIVE=0 \
    RUN_TESTS_SUMMARY_PATH="$summary_path" \
    RUN_TESTS_SUMMARY_JSON_PATH="$json_path" \
    RUN_TESTS_ARTIFACT_DIR="$artifact_dir" \
    bash scripts/run-tests.sh ci >/dev/null 2>&1
)
status=$?
set -e

if [ "$status" -eq 0 ]; then
  echo "expected ci mode to fail when frontend lint fails" >&2
  exit 1
fi

if [ ! -f "$summary_path" ]; then
  echo "expected summary file to be generated: $summary_path" >&2
  exit 1
fi

if [ ! -f "$json_path" ]; then
  echo "expected summary json to be generated: $json_path" >&2
  exit 1
fi

frontend_lint_log="$artifact_dir/run-tests-stage-logs/frontend-lint.log"
if [ ! -f "$frontend_lint_log" ]; then
  echo "expected frontend lint log to be generated: $frontend_lint_log" >&2
  exit 1
fi

grep -F "| Backend lint | PASS |" "$summary_path" >/dev/null
grep -F "| Frontend lint | FAIL |" "$summary_path" >/dev/null
grep -F "| Frontend build | PASS |" "$summary_path" >/dev/null
grep -F -- "- Result: **failed**" "$summary_path" >/dev/null

grep -F "frontend lint failed" "$frontend_lint_log" >/dev/null

python3 - "$json_path" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as fh:
    data = json.load(fh)

assert data["result"] == "failed", data
assert data["schema_version"] == 1, data
assert data["coverage"] == "core checks only", data
assert data["first_failed_stage"] == "frontend-lint", data
assert data["first_failed_log_relpath"] == "run-tests-stage-logs/frontend-lint.log", data

stages = {stage["stage_id"]: stage for stage in data["stages"]}
assert stages["backend-lint"]["status"] == "PASS", stages
assert stages["frontend-lint"]["status"] == "FAIL", stages
assert stages["frontend-lint"]["log_relpath"] == "run-tests-stage-logs/frontend-lint.log", stages
assert stages["frontend-build"]["status"] == "PASS", stages
PY

echo "OK: ci summary markdown is generated and captures failed stages"
