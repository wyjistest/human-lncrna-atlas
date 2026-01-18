#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

assembly="panTro5"

# 1) 预置文件，避免脚本触发大文件下载（脚本应在文件存在时跳过下载）
python3 - "$tmp_dir" "$assembly" <<'PY'
import gzip
import pathlib
import sys

tmp = pathlib.Path(sys.argv[1])
assembly = sys.argv[2]

# 2bit：为测试创建一个小文件（真实文件很大；脚本应对非 hg19 使用较小 min-size 阈值）
(tmp / f"{assembly}.2bit").write_bytes(b"0" * (2 * 1024 * 1024))

# cytoband.gz：创建一个有效 gzip 文件，并写入足够行数
with gzip.open(tmp / f"cytoBand.{assembly}.txt.gz", "wt", encoding="utf-8") as f:
    for i in range(200):
        f.write(f"chr1\t{i}\t{i+1}\tq{i}\tstain\n")

# chrom.sizes：至少 20 行，且以 chr 开头 + 整数长度
with (tmp / f"{assembly}.chrom.sizes").open("w", encoding="utf-8") as f:
    for i in range(1, 51):
        f.write(f"chr{i}\t1000\n")

# alias：至少 10 行即可
with (tmp / f"{assembly}_alias.tab").open("w", encoding="utf-8") as f:
    for i in range(1, 21):
        f.write(f"{i}\tchr{i}\tChr{i}\n")
PY

# 2) 期望：支持 --assembly 并生成对应 manifest
"$REPO_ROOT/scripts/genomes/download_hg19_igv_assets.sh" \
  --assembly "$assembly" \
  --write-manifest \
  "$tmp_dir"

manifest="$tmp_dir/${assembly}_igv_assets.manifest.tsv"
if [ ! -f "$manifest" ]; then
  echo "expected manifest not found: $manifest" >&2
  exit 1
fi

grep -q "^${assembly}\\.2bit" "$manifest"

