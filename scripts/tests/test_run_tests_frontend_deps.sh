#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 验证 `scripts/run-tests.sh` 的 `ensure_frontend_deps()` 能在检测到依赖漂移时触发 `npm ci`。
# - “依赖漂移”的判定方式（本测试期望）：`package-lock.json` 比 `node_modules/.package-lock.json` 更新。
#
# 说明：
# - 该测试不会真实执行 npm / node / eslint：通过 PATH 注入 fake npm 来记录是否调用过 `npm ci`。
# - 测试会在临时目录中复制最小仓库结构，避免影响开发机现有的 node_modules。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

mkdir -p "$tmp_root/scripts" "$tmp_root/frontend/web" "$tmp_root/bin"

cp "$REPO_ROOT/scripts/run-tests.sh" "$tmp_root/scripts/run-tests.sh"
chmod +x "$tmp_root/scripts/run-tests.sh"

# `ensure_frontend_deps()` 当前只要求 package-lock.json 存在即可。
cp "$REPO_ROOT/frontend/web/package-lock.json" "$tmp_root/frontend/web/package-lock.json"

# 构造“已安装但锁文件已更新”的场景：package-lock 新于 node_modules/.package-lock.json
mkdir -p "$tmp_root/frontend/web/node_modules"
touch -d "2000-01-01 00:00:00" "$tmp_root/frontend/web/node_modules/.package-lock.json"
touch -d "2000-01-02 00:00:00" "$tmp_root/frontend/web/package-lock.json"

fake_called="$tmp_root/npm-ci-called"
cat > "$tmp_root/bin/npm" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

called_file="${FAKE_NPM_CALLED_FILE:?}"

if [[ "${1:-}" == "ci" ]]; then
  echo "[fake-npm] ci" >&2
  touch "$called_file"
  exit 0
fi

if [[ "${1:-}" == "run" ]]; then
  echo "[fake-npm] run ${2:-}" >&2
  exit 0
fi

echo "[fake-npm] noop: $*" >&2
exit 0
EOF
chmod +x "$tmp_root/bin/npm"

export FAKE_NPM_CALLED_FILE="$fake_called"
export PATH="$tmp_root/bin:$PATH"

(cd "$tmp_root" && bash scripts/run-tests.sh frontend-lint)

if [ ! -f "$fake_called" ]; then
  echo "expected npm ci to be called when package-lock.json is newer than node_modules/.package-lock.json" >&2
  exit 1
fi

echo "OK: ensure_frontend_deps triggered npm ci on lock drift"
