#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 验证前端 bundle size 报告脚本支持输出“可机器读取”的 JSON 快照（包含 entry/modulepreload/assets）。
# - 该快照将用于后续的 baseline/diff（可审计可回滚）。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

mkdir -p "$tmp_root/dist/assets"

# 构造 3 个 js 文件：entry + 2 个 modulepreload（内容用随机字节，避免 gzip 过度压缩导致不稳定）。
(cd "$tmp_root" && python3 - <<'PY'
from pathlib import Path
import os

assets = Path("dist/assets")
assets.mkdir(parents=True, exist_ok=True)

def write(name: str, size: int) -> None:
    (assets / name).write_bytes(os.urandom(size))

write("index-ENTRY123.js", 123_456)
write("react-vendor-AAAAAAA.js", 200_000)
write("antd-vendor-BBBBBBB.js", 300_000)

# 噪音文件：应被忽略
write("react-vendor-AAAAAAA.js.map", 10_000)
PY
)

cat >"$tmp_root/dist/index.html" <<'HTML'
<!doctype html>
<html>
  <head>
    <link rel="modulepreload" crossorigin href="/assets/react-vendor-AAAAAAA.js">
    <link rel="modulepreload" crossorigin href="/assets/antd-vendor-BBBBBBB.js">
  </head>
  <body>
    <script type="module" crossorigin src="/assets/index-ENTRY123.js"></script>
  </body>
</html>
HTML

snapshot_json="$tmp_root/snapshot.json"

(cd "$tmp_root" && node "$REPO_ROOT/frontend/web/scripts/report-bundle-sizes.mjs" --dist dist --top 2 --json "$snapshot_json")

python3 - <<PY
import json
from pathlib import Path

data = json.loads(Path("$snapshot_json").read_text())

assert data["schemaVersion"] == 1

entry = data["entry"]
assert entry["file"] == "index-ENTRY123.js"
assert entry["bytes"] == 123_456

preloads = data["modulePreloads"]
assert len(preloads) == 2
files = {p["file"] for p in preloads}
assert "react-vendor-AAAAAAA.js" in files
assert "antd-vendor-BBBBBBB.js" in files

assets = data["assets"]
asset_files = {a["file"] for a in assets}
assert "index-ENTRY123.js" in asset_files
assert "react-vendor-AAAAAAA.js" in asset_files
assert "antd-vendor-BBBBBBB.js" in asset_files
PY

echo "OK: bundle size report writes JSON snapshot with entry/modulepreload/assets"

