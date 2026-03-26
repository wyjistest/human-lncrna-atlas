#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 回归测试：当前端依赖漂移且 `npm ci` 失败时，
#   `scripts/run-tests.sh frontend-lint` 必须立即返回非 0。
#
# 说明：
# - 该测试不会真实执行 npm / node / eslint：通过 PATH 注入 fake npm。
# - fake npm 会在 `ci` 时返回固定错误码，验证 run-tests 不得继续吞掉失败。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

mkdir -p "$tmp_root/scripts" "$tmp_root/frontend/web" "$tmp_root/bin"

cp "$REPO_ROOT/scripts/run-tests.sh" "$tmp_root/scripts/run-tests.sh"
chmod +x "$tmp_root/scripts/run-tests.sh"
cp "$REPO_ROOT/frontend/web/package-lock.json" "$tmp_root/frontend/web/package-lock.json"

mkdir -p "$tmp_root/frontend/web/node_modules"
touch -d "2000-01-01 00:00:00" "$tmp_root/frontend/web/node_modules/.package-lock.json"
touch -d "2000-01-02 00:00:00" "$tmp_root/frontend/web/package-lock.json"

lint_called="$tmp_root/npm-run-lint-called"
cat > "$tmp_root/bin/npm" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

lint_called_file="${FAKE_NPM_RUN_LINT_CALLED_FILE:?}"

if [[ "${1:-}" == "ci" ]]; then
  echo "[fake-npm] ci fails" >&2
  exit 42
fi

if [[ "${1:-}" == "run" && "${2:-}" == "lint" ]]; then
  touch "$lint_called_file"
  echo "[fake-npm] run lint" >&2
  exit 0
fi

echo "[fake-npm] noop: $*" >&2
exit 0
EOF
chmod +x "$tmp_root/bin/npm"

export FAKE_NPM_RUN_LINT_CALLED_FILE="$lint_called"
export PATH="$tmp_root/bin:$PATH"

set +e
(cd "$tmp_root" && bash scripts/run-tests.sh frontend-lint >/dev/null 2>&1)
status=$?
set -e

if [ "$status" -eq 0 ]; then
  echo "expected frontend-lint to fail (non-zero) when npm ci fails during dependency sync" >&2
  exit 1
fi

if [ -f "$lint_called" ]; then
  echo "expected frontend-lint not to continue to npm run lint after npm ci failure" >&2
  exit 1
fi

echo "OK: frontend-lint fails fast when npm ci fails during dependency sync"
