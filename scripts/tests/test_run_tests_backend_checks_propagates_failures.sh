#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 回归测试：`scripts/run-tests.sh backend-checks` 必须在导入检查失败时返回非 0。
#
# 背景：
# - `scripts/run-tests.sh` 的 main() 使用 `run_backend_checks || failed=1` 汇总失败；
#   在 Bash 的 `set -e` 语义下，函数在 `||` 上下文中可能“吞掉”内部失败命令。
# - 该测试确保 backend-checks 不会在出现 Python import traceback 时误报 PASS。
#
# 说明：
# - 测试会在临时目录里复制最小仓库结构，并注入 fake backend python，
#   让 `-c`（导入检查）固定返回 1，模拟缺失依赖（例如 psycopg2）。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

mkdir -p \
  "$tmp_root/scripts" \
  "$tmp_root/frontend/backend/.venv/bin" \
  "$tmp_root/frontend/backend/app"

cp "$REPO_ROOT/scripts/run-tests.sh" "$tmp_root/scripts/run-tests.sh"
chmod +x "$tmp_root/scripts/run-tests.sh"

# 最小占位文件，避免 backend-checks 的 py_compile/find 失败。
cat > "$tmp_root/frontend/backend/main.py" <<'EOF'
print("hello")
EOF
cat > "$tmp_root/frontend/backend/app/__init__.py" <<'EOF'
# stub
EOF

cat > "$tmp_root/frontend/backend/.venv/bin/python" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

# 模拟导入失败（如缺少 psycopg2）：任何 `-c` 都返回非 0。
if [[ "${1:-}" == "-c" ]]; then
  echo "[fake-python] import failed" >&2
  exit 1
fi

# 其它调用一律当作成功（避免影响测试聚焦）。
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

set +e
(cd "$tmp_root" && bash scripts/run-tests.sh backend-checks >/dev/null 2>&1)
status=$?
set -e

if [ "$status" -eq 0 ]; then
  echo "expected backend-checks to fail (non-zero) when python import checks fail" >&2
  exit 1
fi

echo "OK: backend-checks propagates import-check failures"

