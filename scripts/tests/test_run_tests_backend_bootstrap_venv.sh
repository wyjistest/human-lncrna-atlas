#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 当开发机没有后端 venv（frontend/backend/.venv）且全局 python 缺少依赖时，
#   `scripts/run-tests.sh backend-unit` 应能自动创建 venv 并触发一次依赖安装，使本地 CI 可跑。
#
# 说明：
# - 本测试通过注入 fake python3 来模拟：
#   - 全局 python 缺少 pytest（`python3 -c "import pytest"` 失败）
#   - 但 `python3 -m venv` 可用（创建一个 fake venv python）
# - fake venv python 会在 hash 计算时输出固定值，并在 `-m pip install` 时写入标记文件。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

mkdir -p \
  "$tmp_root/scripts" \
  "$tmp_root/frontend/backend" \
  "$tmp_root/bin"

cp "$REPO_ROOT/scripts/run-tests.sh" "$tmp_root/scripts/run-tests.sh"
chmod +x "$tmp_root/scripts/run-tests.sh"

# 最小后端依赖文件（用于 ensure_backend_deps 的 hash 计算）
cat > "$tmp_root/frontend/backend/requirements.txt" <<'EOF'
fastapi==0.0.0
EOF

cat > "$tmp_root/frontend/backend/requirements-dev.txt" <<'EOF'
pytest==0.0.0
EOF

cat > "$tmp_root/frontend/backend/constraints.txt" <<'EOF'
starlette==0.0.0
EOF

pip_called="$tmp_root/pip-install-called"

cat > "$tmp_root/bin/python3" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

# 模拟：全局 python 缺少 pytest
if [[ "${1:-}" == "-c" ]]; then
  exit 1
fi
if [[ "${1:-}" == "-m" && "${2:-}" == "pytest" ]]; then
  exit 1
fi

# 支持：python3 -m venv <path>（创建 fake venv python）
if [[ "${1:-}" == "-m" && "${2:-}" == "venv" ]]; then
  venv_dir="${3:?venv dir required}"
  mkdir -p "${venv_dir}/bin"

  cat > "${venv_dir}/bin/python" <<'PYEOF'
#!/usr/bin/env bash
set -euo pipefail

called_file="${FAKE_PIP_CALLED_FILE:?}"

if [[ "${1:-}" == "-m" && "${2:-}" == "pip" && "$*" == *" install "* ]]; then
  touch "$called_file"
  exit 0
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "pytest" ]]; then
  exit 0
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "py_compile" ]]; then
  exit 0
fi

if [[ "${1:-}" == "-c" ]]; then
  exit 0
fi

# compute_backend_deps_hash 会用 `python -` 执行 stdin；这里输出固定 hash，确保触发一次 pip install。
if [[ "${1:-}" == "-" ]]; then
  echo "fakehash"
  exit 0
fi

exit 0
PYEOF
  chmod +x "${venv_dir}/bin/python"
  exit 0
fi

exit 0
EOF
chmod +x "$tmp_root/bin/python3"

export FAKE_PIP_CALLED_FILE="$pip_called"
export PATH="$tmp_root/bin:$PATH"

output_log="$tmp_root/backend-unit.log"

set +e
# 说明：脚本单测会在 GitHub Actions（CI=true）中运行，但我们这里需要模拟“本地开发机”行为，
# 因此显式覆盖 CI 变量以启用后端 venv 自举逻辑。
(cd "$tmp_root" && CI=0 bash scripts/run-tests.sh backend-unit >"$output_log" 2>&1)
status=$?
set -e

if [ "$status" -ne 0 ]; then
  echo "expected backend-unit to succeed by bootstrapping backend venv" >&2
  echo "----- backend-unit output (tail) -----" >&2
  tail -n 200 "$output_log" >&2 || true
  exit 1
fi

if [ ! -x "$tmp_root/frontend/backend/.venv/bin/python" ]; then
  echo "expected backend venv python to be created at frontend/backend/.venv/bin/python" >&2
  exit 1
fi

if [ ! -f "$pip_called" ]; then
  echo "expected backend venv bootstrap to trigger one pip install" >&2
  exit 1
fi

echo "OK: backend venv auto-bootstrap works when global python lacks deps"
