#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 回归测试：`scripts/run-tests.sh scripts-tests` 必须执行 `scripts/tests/*.py`。
# - 这些 Python 测试覆盖论文图表/稿件脚本，不能只依赖 shell 回归列表。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

mkdir -p "$tmp_root/bin" "$tmp_root/scripts/paper" "$tmp_root/scripts/tests" "$tmp_root/frontend/backend/.venv/bin"
cp "$REPO_ROOT/scripts/run-tests.sh" "$tmp_root/scripts/run-tests.sh"
chmod +x "$tmp_root/scripts/run-tests.sh"

python3 - "$tmp_root/scripts/run-tests.sh" "$tmp_root" <<'PY'
import re
import sys
from pathlib import Path

script = Path(sys.argv[1])
root = Path(sys.argv[2])
for rel in sorted(set(re.findall(r'"(scripts/tests/test_[^"]+\.sh)"', script.read_text()))):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
PY

cat > "$tmp_root/frontend/backend/requirements.txt" <<'EOF'
# stub
EOF
cat > "$tmp_root/frontend/backend/requirements-dev.txt" <<'EOF'
# stub
EOF
cat > "$tmp_root/frontend/backend/constraints.txt" <<'EOF'
# stub
EOF

cat > "$tmp_root/scripts/tests/test_example.py" <<'EOF'
def test_example():
    assert True
EOF

cat > "$tmp_root/scripts/paper/requirements.txt" <<'EOF'
matplotlib>=3.8.0
EOF

pytest_log="$tmp_root/pytest.log"
pip_log="$tmp_root/pip.log"
cat > "$tmp_root/frontend/backend/.venv/bin/python" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-" ]]; then
  echo "fakehash"
  exit 0
fi

if [[ "${1:-}" == "-c" ]]; then
  exit 0
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "pip" && "$*" == *" install "* ]]; then
  printf '%s\n' "$*" >> "${PIP_LOG:?}"
  exit "${FAKE_PIP_EXIT_CODE:-0}"
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "pytest" ]]; then
  printf 'PWD=%s ARGS=%s\n' "$PWD" "$*" >> "${PYTEST_LOG:?}"
  if [ ! -f "scripts/tests/test_example.py" ]; then
    echo "pytest must run from repository root; cwd=$PWD" >&2
    exit 44
  fi
  exit 0
fi

exit 0
EOF
chmod +x "$tmp_root/frontend/backend/.venv/bin/python"

cat > "$tmp_root/bin/pandoc" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF
chmod +x "$tmp_root/bin/pandoc"

(
  cd "$tmp_root"
  PIP_LOG="$pip_log" \
  PYTEST_LOG="$pytest_log" \
  PIP_PROXY="http://localhost:7890" \
  PATH="$tmp_root/bin:$PATH" \
    bash scripts/run-tests.sh scripts-tests >/dev/null
)

if [ ! -f "$pytest_log" ]; then
  echo "expected scripts-tests to invoke pytest for scripts/tests Python tests" >&2
  exit 1
fi

grep -F "scripts/tests" "$pytest_log" >/dev/null || {
  echo "expected pytest invocation to include scripts/tests" >&2
  cat "$pytest_log" >&2
  exit 1
}

grep -F "PWD=$tmp_root" "$pytest_log" >/dev/null || {
  echo "expected scripts-tests Python pytest invocation to run from repository root" >&2
  cat "$pytest_log" >&2
  exit 1
}

grep -F "scripts/paper/requirements.txt" "$pip_log" | grep -F "frontend/backend/constraints.txt" >/dev/null || {
  echo "expected paper dependency install to use backend constraints" >&2
  cat "$pip_log" >&2
  exit 1
}

grep -F -- "--proxy http://localhost:7890" "$pip_log" >/dev/null || {
  echo "expected paper dependency install to include --proxy from PIP_PROXY" >&2
  cat "$pip_log" >&2
  exit 1
}

grep -F "require_cmd pandoc" "$REPO_ROOT/scripts/run-tests.sh" >/dev/null || {
  echo "expected scripts-tests to check for pandoc before running paper Python tests" >&2
  exit 1
}

set +e
usage_output="$(bash "$REPO_ROOT/scripts/run-tests.sh" does-not-exist 2>&1)"
set -e

echo "$usage_output" | grep -F "shell/Python" >/dev/null || {
  echo "expected scripts-tests usage text to mention shell/Python coverage" >&2
  echo "$usage_output" >&2
  exit 1
}

echo "OK: run-tests scripts-tests invokes scripts/tests Python tests"

echo "deadbeef" > "$tmp_root/frontend/backend/.venv/.hla_requirements.sha256"
echo "fakehash" > "$tmp_root/frontend/backend/.venv/.hla_paper_requirements.sha256"
rm -f "$pytest_log"

set +e
(
  cd "$tmp_root"
  PIP_LOG="$pip_log" \
  PYTEST_LOG="$pytest_log" \
  PIP_PROXY="http://localhost:7890" \
  PATH="$tmp_root/bin:$PATH" \
    bash scripts/run-tests.sh scripts-tests >/dev/null 2>&1
)
status=$?
set -e

if [ "$status" -ne 0 ]; then
  echo "expected scripts-tests to keep Python tests rooted after backend dependency drift" >&2
  if [ -f "$pytest_log" ]; then
    cat "$pytest_log" >&2
  fi
  exit 1
fi

grep -F "PWD=$tmp_root" "$pytest_log" >/dev/null || {
  echo "expected dependency drift path to restore repository root before pytest" >&2
  cat "$pytest_log" >&2
  exit 1
}

echo "OK: scripts-tests keeps Python tests rooted after backend dependency drift"

echo "fakehash" > "$tmp_root/frontend/backend/.venv/.hla_requirements.sha256"
echo "deadbeef" > "$tmp_root/frontend/backend/.venv/.hla_paper_requirements.sha256"
rm -f "$pytest_log"

set +e
(
  cd "$tmp_root"
  PIP_LOG="$pip_log" \
  PYTEST_LOG="$pytest_log" \
  PIP_PROXY="http://localhost:7890" \
  FAKE_PIP_EXIT_CODE=43 \
  PATH="$tmp_root/bin:$PATH" \
    bash scripts/run-tests.sh scripts-tests >/dev/null 2>&1
)
status=$?
set -e

if [ "$status" -eq 0 ]; then
  echo "expected paper dependency pip install failure to fail scripts-tests" >&2
  exit 1
fi

if [ "$(cat "$tmp_root/frontend/backend/.venv/.hla_paper_requirements.sha256")" != "deadbeef" ]; then
  echo "expected failed paper dependency install to leave dependency stamp unchanged" >&2
  exit 1
fi

echo "OK: ensure_paper_python_deps propagates pip install failures"
