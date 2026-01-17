#!/usr/bin/env bash
# ==============================================================================
# 下载 IGV/hg19 离线资源（2bit / cytoband / alias / chrom.sizes）
# ==============================================================================
# 目标：
# - 为 IGV.js 的 hg19 参考基因组提供“纯本地”依赖，避免运行时访问 UCSC/igv.org/GitHub
# - 文件放入后端 GENOMES_DIR（由 /genomes 静态服务暴露），前端会自动优先使用本地资源
#
# 说明：
# - hg19.2bit 体积较大（~GB），脚本默认启用断点续传（curl -C -）
# - 保守性 BigWig（phastCons/phyloP）同样很大，默认不下载，需显式加 --with-conservation
#
# 用法：
#   GENOMES_DIR=<repo-root>/genomes ./scripts/genomes/download_hg19_igv_assets.sh
#   ./scripts/genomes/download_hg19_igv_assets.sh <repo-root>/genomes
#   ./scripts/genomes/download_hg19_igv_assets.sh --with-conservation <repo-root>/genomes
# ==============================================================================

set -euo pipefail

WITH_CONSERVATION="false"
WRITE_MANIFEST="false"
HASH_LARGE_FILES="false"

usage() {
  cat <<'EOF'
用法：
  download_hg19_igv_assets.sh [--with-conservation] [--write-manifest] [--hash-large-files] [GENOMES_DIR]

参数：
  --with-conservation   同时下载 hg19 的 phastCons/phyloP BigWig（文件很大）
  --write-manifest      写入下载清单（文件大小 + 可选 SHA256）
  --hash-large-files    在写 manifest 时也计算大文件的 SHA256（很慢）

环境变量（可选校验）：
  HG19_2BIT_SHA256          校验 hg19.2bit 的 SHA256（64 hex）
  HG19_CYTOBAND_SHA256      校验 cytoBand.hg19.txt.gz 的 SHA256（64 hex）
  HG19_CHROMSIZES_SHA256    校验 hg19.chrom.sizes 的 SHA256（64 hex）
  HG19_ALIAS_SHA256         校验 hg19_alias.tab 的 SHA256（64 hex）
  HG19_PHASTCONS_SHA256     校验 hg19.100way.phastCons.bw 的 SHA256（64 hex）
  HG19_PHYLOP_SHA256        校验 hg19.100way.phyloP100way.bw 的 SHA256（64 hex）

示例：
  GENOMES_DIR=<repo-root>/genomes ./scripts/genomes/download_hg19_igv_assets.sh
  ./scripts/genomes/download_hg19_igv_assets.sh <repo-root>/genomes
  ./scripts/genomes/download_hg19_igv_assets.sh --write-manifest <repo-root>/genomes
EOF
}

while [ $# -gt 0 ]; do
  case "${1:-}" in
    --help|-h)
      usage
      exit 0
      ;;
    --with-conservation)
      WITH_CONSERVATION="true"
      shift
      ;;
    --write-manifest)
      WRITE_MANIFEST="true"
      shift
      ;;
    --hash-large-files)
      HASH_LARGE_FILES="true"
      shift
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "[hg19] ERROR: 未知参数: ${1:-}"
      usage
      exit 1
      ;;
    *)
      break
      ;;
  esac
done

TARGET_DIR="${1:-${GENOMES_DIR:-}}"
if [ -z "${TARGET_DIR:-}" ]; then
  echo "[hg19] ERROR: 未指定 GENOMES_DIR（参数或环境变量）"
  usage
  exit 1
fi

mkdir -p "$TARGET_DIR"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[hg19] ERROR: 需要命令 $1"
    exit 1
  }
}

need_cmd curl

cmd_exists() {
  command -v "$1" >/dev/null 2>&1
}

file_size_bytes() {
  # Portable file size (bytes) without relying on GNU/BSD stat flags.
  wc -c < "$1" | tr -d '[:space:]'
}

ensure_min_size() {
  local path="$1"
  local min_bytes="$2"

  if [ -z "${min_bytes:-}" ] || [ "$min_bytes" -le 0 ]; then
    return 0
  fi
  if [ ! -f "$path" ]; then
    echo "[hg19] ERROR: 下载后文件不存在: $path"
    exit 1
  fi

  local size
  size="$(file_size_bytes "$path")"
  if [ "$size" -lt "$min_bytes" ]; then
    echo "[hg19] ERROR: 下载文件体积异常（可能下载中断或拿到错误页面）"
    echo "[hg19]        file=$path size=${size}B min=${min_bytes}B"
    exit 1
  fi
}

sha256_hex_file() {
  local path="$1"

  if cmd_exists sha256sum; then
    sha256sum "$path" | awk '{print $1}'
    return 0
  fi
  if cmd_exists shasum; then
    shasum -a 256 "$path" | awk '{print $1}'
    return 0
  fi
  if cmd_exists python3; then
    python3 - "$path" <<'PY'
import hashlib
import sys

path = sys.argv[1]
h = hashlib.sha256()
with open(path, "rb") as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b""):
        h.update(chunk)
print(h.hexdigest())
PY
    return 0
  fi

  return 1
}

normalize_sha256() {
  local raw="${1:-}"
  printf '%s' "$raw" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]'
}

verify_sha256_if_set() {
  local path="$1"
  local expected_raw="${2:-}"
  local expected
  expected="$(normalize_sha256 "$expected_raw")"

  if [ -z "${expected:-}" ]; then
    return 0
  fi

  local actual
  if ! actual="$(sha256_hex_file "$path")"; then
    echo "[hg19] WARN  缺少 sha256 工具（sha256sum/shasum/python3），跳过 SHA256 校验: $path" >&2
    return 0
  fi

  actual="$(normalize_sha256 "$actual")"
  if [ "$actual" != "$expected" ]; then
    echo "[hg19] ERROR: SHA256 校验失败: $path" >&2
    echo "[hg19]        expected=$expected" >&2
    echo "[hg19]        actual  =$actual" >&2
    exit 1
  fi
}

ensure_gzip_ok_if_possible() {
  local path="$1"
  if ! cmd_exists gzip; then
    echo "[hg19] WARN  未找到 gzip，跳过 gzip 完整性校验: $path" >&2
    return 0
  fi
  gzip -t "$path"
}

ensure_lines_between_plain() {
  local path="$1"
  local min_lines="${2:-0}"
  local max_lines="${3:-0}"

  if [ -z "${min_lines:-}" ] || [ "$min_lines" -le 0 ]; then
    return 0
  fi
  if [ ! -f "$path" ]; then
    echo "[hg19] ERROR: 文件不存在: $path" >&2
    exit 1
  fi

  local lines
  lines="$(wc -l < "$path" | tr -d '[:space:]')"
  if [ "$lines" -lt "$min_lines" ]; then
    echo "[hg19] ERROR: 文件行数异常（过少）: $path lines=$lines min=$min_lines" >&2
    exit 1
  fi
  if [ -n "${max_lines:-}" ] && [ "$max_lines" -gt 0 ] && [ "$lines" -gt "$max_lines" ]; then
    echo "[hg19] ERROR: 文件行数异常（过多）: $path lines=$lines max=$max_lines" >&2
    exit 1
  fi
}

ensure_lines_between_gz() {
  local path="$1"
  local min_lines="${2:-0}"
  local max_lines="${3:-0}"

  if [ -z "${min_lines:-}" ] || [ "$min_lines" -le 0 ]; then
    return 0
  fi
  if ! cmd_exists gzip; then
    echo "[hg19] WARN  未找到 gzip，跳过行数范围校验: $path" >&2
    return 0
  fi

  local lines
  lines="$(gzip -cd "$path" | wc -l | tr -d '[:space:]')"
  if [ "$lines" -lt "$min_lines" ]; then
    echo "[hg19] ERROR: 文件行数异常（过少）: $path lines=$lines min=$min_lines" >&2
    exit 1
  fi
  if [ -n "${max_lines:-}" ] && [ "$max_lines" -gt 0 ] && [ "$lines" -gt "$max_lines" ]; then
    echo "[hg19] ERROR: 文件行数异常（过多）: $path lines=$lines max=$max_lines" >&2
    exit 1
  fi
}

verify_chrom_sizes_format() {
  local path="$1"

  # Basic sanity: "chr*" + integer size, no empty lines.
  # Intentionally loose to avoid breaking when UCSC adds contigs.
  awk '
    NF < 2 { bad=1; exit }
    $1 !~ /^chr/ { bad=1; exit }
    $2 !~ /^[0-9]+$/ { bad=1; exit }
    { ok++ }
    END { if (bad || ok < 20) exit 1 }
  ' "$path"
}

download() {
  local url="$1"
  local dest="$2"
  local min_bytes="${3:-0}"

  if [ -f "$dest" ]; then
    echo "[hg19] SKIP  已存在: $dest"
    return 0
  fi

  local tmp="${dest}.part"
  echo "[hg19] GET   $url"
  echo "[hg19] INTO  $dest"
  # 兼容不同版本 curl：部分版本不支持 --retry-all-errors
  local curl_args=(-L --fail --retry 5 --connect-timeout 15)
  if curl --help 2>/dev/null | grep -q -- '--retry-all-errors'; then
    curl_args+=(--retry-all-errors)
  fi
  curl "${curl_args[@]}" -C - -o "$tmp" "$url"
  mv "$tmp" "$dest"
  ensure_min_size "$dest" "$min_bytes"
}

write_manifest_if_enabled() {
  if [ "$WRITE_MANIFEST" != "true" ]; then
    return 0
  fi

  local out="$TARGET_DIR/hg19_igv_assets.manifest.tsv"
  local now
  now="$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date)"

  {
    printf '# generated_at=%s\n' "$now"
    printf '# target_dir=%s\n' "$TARGET_DIR"
    printf 'file\tbytes\tsha256\n'

    local f path size sha
    for f in \
      hg19.2bit \
      cytoBand.hg19.txt.gz \
      hg19.chrom.sizes \
      hg19_alias.tab \
      hg19.100way.phastCons.bw \
      hg19.100way.phyloP100way.bw \
      ; do
      path="$TARGET_DIR/$f"
      if [ ! -f "$path" ]; then
        continue
      fi
      size="$(file_size_bytes "$path")"
      sha=""

      if [ "$f" = "hg19.2bit" ] || [[ "$f" == *.bw ]]; then
        if [ "$HASH_LARGE_FILES" = "true" ]; then
          sha="$(sha256_hex_file "$path" 2>/dev/null || true)"
        fi
      else
        sha="$(sha256_hex_file "$path" 2>/dev/null || true)"
      fi

      printf '%s\t%s\t%s\n' "$f" "$size" "${sha:-}"
    done
  } > "$out"

  echo "[hg19] OK    已写入下载清单: $out"
}

# ------------------------------------------------------------------------------
# 核心离线资源
# ------------------------------------------------------------------------------
HG19_TWOBIT_URL="https://hgdownload.soe.ucsc.edu/goldenPath/hg19/bigZips/hg19.2bit"
HG19_CYTOBAND_URL="https://hgdownload.soe.ucsc.edu/goldenPath/hg19/database/cytoBand.txt.gz"
HG19_CHROMSIZES_URL="https://hgdownload.soe.ucsc.edu/goldenPath/hg19/bigZips/hg19.chrom.sizes"

# 染色体别名表（IGV 官方数据仓库）
HG19_ALIAS_URL="https://raw.githubusercontent.com/igvteam/igv-data/refs/heads/main/data/hg19/hg19_alias.tab"

download "$HG19_TWOBIT_URL"      "$TARGET_DIR/hg19.2bit"
download "$HG19_CYTOBAND_URL"    "$TARGET_DIR/cytoBand.hg19.txt.gz" 10000
download "$HG19_CHROMSIZES_URL"  "$TARGET_DIR/hg19.chrom.sizes" 1000
download "$HG19_ALIAS_URL"       "$TARGET_DIR/hg19_alias.tab" 100

# hg19.2bit / bigWig files are large; use a conservative minimum size guard.
if [ -f "$TARGET_DIR/hg19.2bit" ]; then
  ensure_min_size "$TARGET_DIR/hg19.2bit" 100000000
fi

verify_sha256_if_set "$TARGET_DIR/hg19.2bit" "${HG19_2BIT_SHA256-}"
verify_sha256_if_set "$TARGET_DIR/cytoBand.hg19.txt.gz" "${HG19_CYTOBAND_SHA256-}"
verify_sha256_if_set "$TARGET_DIR/hg19.chrom.sizes" "${HG19_CHROMSIZES_SHA256-}"
verify_sha256_if_set "$TARGET_DIR/hg19_alias.tab" "${HG19_ALIAS_SHA256-}"

ensure_gzip_ok_if_possible "$TARGET_DIR/cytoBand.hg19.txt.gz"
ensure_lines_between_gz "$TARGET_DIR/cytoBand.hg19.txt.gz" 100 100000

ensure_lines_between_plain "$TARGET_DIR/hg19.chrom.sizes" 20 10000
verify_chrom_sizes_format "$TARGET_DIR/hg19.chrom.sizes"

ensure_lines_between_plain "$TARGET_DIR/hg19_alias.tab" 10 200000

echo "[hg19] OK    离线资源已就绪（/genomes 将暴露这些文件）"

# ------------------------------------------------------------------------------
# 可选：multiz 保守性 BigWig（体积很大）
# ------------------------------------------------------------------------------
if [ "$WITH_CONSERVATION" = "true" ]; then
  HG19_PHASTCONS_URL="https://hgdownload.soe.ucsc.edu/goldenPath/hg19/phastCons100way/hg19.100way.phastCons.bw"
  HG19_PHYLOP_URL="https://hgdownload.soe.ucsc.edu/goldenPath/hg19/phyloP100way/hg19.100way.phyloP100way.bw"

  download "$HG19_PHASTCONS_URL" "$TARGET_DIR/hg19.100way.phastCons.bw" 100000000
  download "$HG19_PHYLOP_URL"    "$TARGET_DIR/hg19.100way.phyloP100way.bw" 100000000

  verify_sha256_if_set "$TARGET_DIR/hg19.100way.phastCons.bw" "${HG19_PHASTCONS_SHA256-}"
  verify_sha256_if_set "$TARGET_DIR/hg19.100way.phyloP100way.bw" "${HG19_PHYLOP_SHA256-}"

  echo "[hg19] OK    保守性 BigWig 已下载"
fi

write_manifest_if_enabled
