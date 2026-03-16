#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 保护首屏体积：当 dist/index.html 的 entry bundle 过大时，`check-entry-preloads.mjs` 应失败（非 0 退出码）。
#
# 说明：
# - 这里不跑真实构建，只在临时目录构造最小 dist/ 结构。
# - 该测试用来确保“体积预算”逻辑存在且可回归（可审计/可回滚）。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

mkdir -p "$tmp_root/dist/assets"

# 构造一个“modulepreload 合规，但 entry chunk 超预算”的场景。
cat > "$tmp_root/dist/index.html" <<'EOF'
<!doctype html>
<html lang="en">
  <head>
    <script type="module" crossorigin src="/assets/index-ENTRYHASH.js"></script>
    <link rel="modulepreload" crossorigin href="/assets/react-vendor-AAA.js">
    <link rel="modulepreload" crossorigin href="/assets/query-vendor-BBB.js">
    <link rel="modulepreload" crossorigin href="/assets/i18n-vendor-CCC.js">
  </head>
  <body><div id="root"></div></body>
</html>
EOF

# 小体积 vendor（不触发 vendor budget）
echo "react" > "$tmp_root/dist/assets/react-vendor-AAA.js"
echo "query" > "$tmp_root/dist/assets/query-vendor-BBB.js"
echo "i18n" > "$tmp_root/dist/assets/i18n-vendor-CCC.js"
# 让 entry bundle 超预算（> 200KB）。
(cd "$tmp_root" && python3 - <<'PY'
from pathlib import Path

path = Path("dist/assets/index-ENTRYHASH.js")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_bytes(b"0" * (210 * 1024))
PY
)

set +e
output="$(cd "$tmp_root" && node "$REPO_ROOT/frontend/web/scripts/check-entry-preloads.mjs" 2>&1)"
status=$?
set -e

if [[ $status -eq 0 ]]; then
  echo "expected check-entry-preloads.mjs to fail when entry bundle exceeds budget" >&2
  echo "$output" >&2
  exit 1
fi

if ! echo "$output" | grep -q "Entry bundle exceeds budget"; then
  echo "expected budget failure message, got:" >&2
  echo "$output" >&2
  exit 1
fi

echo "OK: entry bundle budget check rejects oversized entry chunk"

