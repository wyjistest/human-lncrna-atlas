#!/usr/bin/env bash
set -euo pipefail

# 目的：
# - 验证前端 bundle size 报告脚本能按“未压缩体积”排序输出 Top chunk 列表。
#
# 说明：
# - 不跑真实构建；仅在临时目录构造 dist/assets 下的最小文件集合。

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

mkdir -p "$tmp_root/dist/assets"

# 构造 3 个不同大小的 chunk（内容用随机字节，避免 gzip 过度压缩导致排序不稳定）。
(cd "$tmp_root" && python3 - <<'PY'
from pathlib import Path
import os

assets = Path("dist/assets")
assets.mkdir(parents=True, exist_ok=True)

def write(name: str, size: int) -> None:
    (assets / name).write_bytes(os.urandom(size))

write("igv-vendor-AAAAAAAA.js", 300_000)
write("antd-vendor-BBBBBBBB.js", 200_000)
write("react-vendor-CCCCCCCC.js", 100_000)

# 额外噪音文件：应被忽略
write("igv-vendor-AAAAAAAA.js.map", 10_000)
PY
)

output="$(cd "$tmp_root" && node "$REPO_ROOT/frontend/web/scripts/report-bundle-sizes.mjs" --dist dist --top 2)"

first="$(echo "$output" | awk '/Top JS chunks by size/{found=1;next} found && /^[0-9]+\./{print; exit}')"
second="$(echo "$output" | awk '/Top JS chunks by size/{found=1;next} found && /^[0-9]+\./{if (n==0){n=1;next}; print; exit}')"

if ! echo "$first" | grep -q "igv-vendor-AAAAAAAA.js"; then
  echo "expected #1 to be igv-vendor-AAAAAAAA.js, got: $first" >&2
  echo "$output" >&2
  exit 1
fi

if ! echo "$second" | grep -q "antd-vendor-BBBBBBBB.js"; then
  echo "expected #2 to be antd-vendor-BBBBBBBB.js, got: $second" >&2
  echo "$output" >&2
  exit 1
fi

echo "OK: bundle size report prints top chunks by size"

