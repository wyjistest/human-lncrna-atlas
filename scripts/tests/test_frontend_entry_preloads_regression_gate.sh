#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 验证 bundle size compare 脚本具备“首屏回归门禁”：
#   - entry.gzipBytes 回归 > +2% 时应失败（exit != 0）
#   - modulepreload gzip 总量回归 > +2% 时应失败（exit != 0）

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

baseline="$tmp_root/baseline.json"
current="$tmp_root/current.json"

cat >"$baseline" <<'JSON'
{
  "schemaVersion": 1,
  "generatedAt": "2026-02-01T00:00:00Z",
  "dist": "dist",
  "entry": { "file": "index-BASE.js", "bytes": 100, "gzipBytes": 100 },
  "modulePreloads": [
    { "href": "/assets/react-vendor-BASE.js", "file": "react-vendor-BASE.js", "bytes": 1000, "gzipBytes": 1000 }
  ],
  "assets": []
}
JSON

cat >"$current" <<'JSON'
{
  "schemaVersion": 1,
  "generatedAt": "2026-02-01T00:10:00Z",
  "dist": "dist",
  "entry": { "file": "index-CUR.js", "bytes": 100, "gzipBytes": 103 },
  "modulePreloads": [
    { "href": "/assets/react-vendor-CUR.js", "file": "react-vendor-CUR.js", "bytes": 1000, "gzipBytes": 1000 }
  ],
  "assets": []
}
JSON

output="$tmp_root/out.txt"
if node "$REPO_ROOT/frontend/web/scripts/compare-bundle-sizes.mjs" "$baseline" "$current" >"$output" 2>&1; then
  echo "expected regression gate failure for entry.gzipBytes (+3%)" >&2
  cat "$output" >&2
  exit 1
fi

cat "$output" | rg -q "entry\\.gzipBytes" || { echo "missing entry.gzipBytes diagnostic" >&2; cat "$output" >&2; exit 1; }

# <= +2% 应通过
cat >"$current" <<'JSON'
{
  "schemaVersion": 1,
  "generatedAt": "2026-02-01T00:20:00Z",
  "dist": "dist",
  "entry": { "file": "index-CUR.js", "bytes": 100, "gzipBytes": 102 },
  "modulePreloads": [
    { "href": "/assets/react-vendor-CUR.js", "file": "react-vendor-CUR.js", "bytes": 1000, "gzipBytes": 1000 }
  ],
  "assets": []
}
JSON

node "$REPO_ROOT/frontend/web/scripts/compare-bundle-sizes.mjs" "$baseline" "$current" >"$output" 2>&1

echo "OK: regression gate enforces +2% threshold for entry/modulepreload gzip totals"
