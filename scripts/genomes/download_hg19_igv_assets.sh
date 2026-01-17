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

usage() {
  cat <<'EOF'
用法：
  download_hg19_igv_assets.sh [--with-conservation] [GENOMES_DIR]

参数：
  --with-conservation   同时下载 hg19 的 phastCons/phyloP BigWig（文件很大）

示例：
  GENOMES_DIR=<repo-root>/genomes ./scripts/genomes/download_hg19_igv_assets.sh
  ./scripts/genomes/download_hg19_igv_assets.sh <repo-root>/genomes
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

if [ "${1:-}" = "--with-conservation" ]; then
  WITH_CONSERVATION="true"
  shift
fi

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

echo "[hg19] OK    离线资源已就绪（/genomes 将暴露这些文件）"

# ------------------------------------------------------------------------------
# 可选：multiz 保守性 BigWig（体积很大）
# ------------------------------------------------------------------------------
if [ "$WITH_CONSERVATION" = "true" ]; then
  HG19_PHASTCONS_URL="https://hgdownload.soe.ucsc.edu/goldenPath/hg19/phastCons100way/hg19.100way.phastCons.bw"
  HG19_PHYLOP_URL="https://hgdownload.soe.ucsc.edu/goldenPath/hg19/phyloP100way/hg19.100way.phyloP100way.bw"

  download "$HG19_PHASTCONS_URL" "$TARGET_DIR/hg19.100way.phastCons.bw" 100000000
  download "$HG19_PHYLOP_URL"    "$TARGET_DIR/hg19.100way.phyloP100way.bw" 100000000
  echo "[hg19] OK    保守性 BigWig 已下载"
fi
