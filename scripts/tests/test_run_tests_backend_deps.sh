#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 验证 `scripts/run-tests.sh` 的后端依赖漂移检测逻辑：
#   当 requirements/constraints 发生变化且使用的是后端 venv 时，应触发一次 `pip install` 以对齐依赖。
#
# 说明：
# - 该测试不会真实执行 pip：通过注入 fake python 来记录是否调用过 `python -m pip install`。
# - 测试会在临时目录中复制最小仓库结构，避免影响开发机现有的 `.venv`。

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

# 伪造最小后端依赖文件（用于生成 hash / 漂移检测）
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
cat > "$tmp_root/frontend/backend/.venv/bin/python" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

called_file="${FAKE_PIP_CALLED_FILE:?}"

if [[ "${1:-}" == "-m" && "${2:-}" == "pip" && "${3:-}" == "install" ]]; then
  echo "[fake-python] pip install" >&2
  touch "$called_file"
  exit 0
fi

if [[ "${1:-}" == "-c" ]]; then
  exit 0
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "pytest" ]]; then
  exit 0
fi

if [[ "${1:-}" == "-m" && "${2:-}" == "py_compile" ]]; then
  exit 0
fi

echo "[fake-python] noop: $*" >&2
exit 0
EOF
chmod +x "$tmp_root/frontend/backend/.venv/bin/python"

# 预置一个“过期”标记：模拟 git pull 更新依赖文件但未重装 venv。
echo "deadbeef" > "$tmp_root/frontend/backend/.venv/.hla_requirements.sha256"

export FAKE_PIP_CALLED_FILE="$pip_called"

(cd "$tmp_root" && bash scripts/run-tests.sh backend-unit)

if [ ! -f "$pip_called" ]; then
  echo "expected backend deps drift to trigger python -m pip install (venv requirements out of date)" >&2
  exit 1
fi

echo "OK: ensure_backend_deps triggered pip install on requirements/constraints drift"

