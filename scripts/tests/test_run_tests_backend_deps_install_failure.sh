#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 回归测试：当后端依赖漂移且 `python -m pip install` 失败时，
#   `scripts/run-tests.sh backend-unit` 必须立即返回非 0。
#
# 说明：
# - 该测试不会真实执行 pip / pytest：通过 fake backend python 模拟失败。
# - fake python 会在 `-m pip install` 时返回固定错误码，验证 run-tests 不得继续吞掉失败。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

mkdir -p \
  "$tmp_root/scripts" \
  "$tmp_root/frontend/backend/.venv/bin" \
  "$tmp_root/bin"

cp "$REPO_ROOT/scripts/run-tests.sh" "$tmp_root/scripts/run-tests.sh"
chmod +x "$tmp_root/scripts/run-tests.sh"

cat > "$tmp_root/frontend/backend/requirements.txt" <<'EOF'
fastapi==0.0.0
EOF

cat > "$tmp_root/frontend/backend/requirements-dev.txt" <<'EOF'
pytest==0.0.0
EOF

cat > "$tmp_root/frontend/backend/constraints.txt" <<'EOF'
starlette==0.0.0
EOF

pytest_called="$tmp_root/pytest-called"
cat > "$tmp_root/frontend/backend/.venv/bin/python" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

pytest_called_file="${FAKE_PYTEST_CALLED_FILE:?}"

if [[ "${1:-}" == "-m" && "${2:-}" == "pip" && "${3:-}" == "install" ]]; then
  echo "[fake-python] pip install fails" >&2
  exit 17
fi

if [[ "${1:-}" == "-c" ]]; then
  exit 0
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "pytest" ]]; then
  touch "$pytest_called_file"
  echo "[fake-python] pytest should not run" >&2
  exit 0
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "py_compile" ]]; then
  exit 0
fi

echo "[fake-python] noop: $*" >&2
exit 0
EOF
chmod +x "$tmp_root/frontend/backend/.venv/bin/python"

echo "deadbeef" > "$tmp_root/frontend/backend/.venv/.hla_requirements.sha256"

export FAKE_PYTEST_CALLED_FILE="$pytest_called"

set +e
(cd "$tmp_root" && bash scripts/run-tests.sh backend-unit >/dev/null 2>&1)
status=$?
set -e

if [ "$status" -eq 0 ]; then
  echo "expected backend-unit to fail (non-zero) when pip install fails during dependency sync" >&2
  exit 1
fi

if [ -f "$pytest_called" ]; then
  echo "expected backend-unit not to continue to pytest after pip install failure" >&2
  exit 1
fi

echo "OK: backend-unit fails fast when pip install fails during dependency sync"
