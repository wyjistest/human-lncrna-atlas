#!/usr/bin/env bash
set -euo pipefail

re_q() {
  local pattern="$1"
  if command -v rg >/dev/null 2>&1; then
    rg -q "$pattern"
  else
    grep -Eq "$pattern"
  fi
}

# 目的：
# - 验证 bundle size compare 脚本能对比两份 JSON 快照，输出稳定且可读的差异摘要（用于定位回归）。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

baseline="$tmp_root/baseline.json"
current="$tmp_root/current.json"

# 说明：
# - 文件名刻意使用不同 hash（更贴近真实 Vite 输出），compare 需按 vendor 前缀做“逻辑匹配”。
cat >"$baseline" <<'JSON'
{
  "schemaVersion": 1,
  "generatedAt": "2026-01-31T00:00:00Z",
  "dist": "dist",
  "entry": { "file": "index-OLDHASH.js", "bytes": 102400, "gzipBytes": 40960 },
  "modulePreloads": [
    { "href": "/assets/react-vendor-OLDHASH.js", "file": "react-vendor-OLDHASH.js", "bytes": 40960, "gzipBytes": 20480 },
    { "href": "/assets/antd-vendor-OLDHASH.js", "file": "antd-vendor-OLDHASH.js", "bytes": 1024000, "gzipBytes": 409600 }
  ],
  "assets": [
    { "file": "react-vendor-OLDHASH.js", "bytes": 40960, "gzipBytes": 20480 },
    { "file": "antd-vendor-OLDHASH.js", "bytes": 1024000, "gzipBytes": 409600 }
  ]
}
JSON

cat >"$current" <<'JSON'
{
  "schemaVersion": 1,
  "generatedAt": "2026-01-31T01:00:00Z",
  "dist": "dist",
  "entry": { "file": "index-NEWHASH.js", "bytes": 122880, "gzipBytes": 49152 },
  "modulePreloads": [
    { "href": "/assets/react-vendor-NEWHASH.js", "file": "react-vendor-NEWHASH.js", "bytes": 51200, "gzipBytes": 25600 },
    { "href": "/assets/antd-vendor-NEWHASH.js", "file": "antd-vendor-NEWHASH.js", "bytes": 921600, "gzipBytes": 368640 }
  ],
  "assets": [
    { "file": "react-vendor-NEWHASH.js", "bytes": 51200, "gzipBytes": 25600 },
    { "file": "antd-vendor-NEWHASH.js", "bytes": 921600, "gzipBytes": 368640 }
  ]
}
JSON

# 说明：本测试关注“差异输出的稳定性”，不关注回归门禁；因此把阈值设得足够大避免因门禁导致 exit!=0。
output="$(node "$REPO_ROOT/frontend/web/scripts/compare-bundle-sizes.mjs" "$baseline" "$current" --top 5 --max-entry-regression-pct 999 --max-preloads-regression-pct 999)"

echo "$output" | re_q "\\[bundle-size-diff\\]" || { echo "missing header" >&2; echo "$output" >&2; exit 1; }
echo "$output" | re_q "Entry:.*delta \\+20\\.0 kB" || { echo "missing entry delta" >&2; echo "$output" >&2; exit 1; }
echo "$output" | re_q "Modulepreload total:.*delta -90\\.0 kB" || { echo "missing modulepreload delta" >&2; echo "$output" >&2; exit 1; }
echo "$output" | re_q "react-vendor:.*delta \\+10\\.0 kB" || { echo "missing react-vendor delta" >&2; echo "$output" >&2; exit 1; }
echo "$output" | re_q "antd-vendor:.*delta -100\\.0 kB" || { echo "missing antd-vendor delta" >&2; echo "$output" >&2; exit 1; }

echo "OK: bundle size compare report prints stable deltas"
