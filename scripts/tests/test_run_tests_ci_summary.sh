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

set +e
(
  cd "$tmp_root"
  PATH="$tmp_root/bin:$PATH" RUN_TESTS_SUMMARY_ACTIVE=0 RUN_TESTS_SUMMARY_PATH="$summary_path" \
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

grep -F "| Backend lint | PASS |" "$summary_path" >/dev/null
grep -F "| Frontend lint | FAIL |" "$summary_path" >/dev/null
grep -F "| Frontend build | PASS |" "$summary_path" >/dev/null
grep -F -- "- Result: **failed**" "$summary_path" >/dev/null

echo "OK: ci summary markdown is generated and captures failed stages"
