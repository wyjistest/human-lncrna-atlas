#!/usr/bin/env bash
# ==============================================================================
# 外部数据组装一致性审计（hg19 / 防 hg38 混入）
# ==============================================================================
# 目标：
# - 一键串联仓库内置校验器，检查：
#   1) BigWig/BigBed 轨道文件：header 染色体表是否与 <assembly>.chrom.sizes 一致
#   2) 文本 peaks（.bed/.broadPeak/.narrowPeak/.gz）：坐标是否越界、是否出现未知染色体
# - 只读、可审计：不修改任何数据；输出落盘到 audits 目录，便于回溯
#
# 默认数据根目录：
#   /data/wenyujianData/humanLncAtlas
#
# 可通过环境变量覆盖：
#   HUMAN_LNC_ATLAS_DATA_DIR=/path/to/humanLncAtlas
#
# 输出：
#   $HUMAN_LNC_ATLAS_DATA_DIR/audits/<timestamp>_external_assembly_audit/
# ==============================================================================

set -euo pipefail

HUMAN_LNC_ATLAS_DATA_DIR="${HUMAN_LNC_ATLAS_DATA_DIR:-/data/wenyujianData/humanLncAtlas}"
ASSEMBLY="${ASSEMBLY:-hg19}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[audit] ERROR: 需要命令: $1" >&2
    exit 1
  }
}

need_cmd date
need_cmd mkdir
need_cmd python3

if [ ! -d "${HUMAN_LNC_ATLAS_DATA_DIR}" ]; then
  echo "[audit] ERROR: 数据根目录不存在: ${HUMAN_LNC_ATLAS_DATA_DIR}" >&2
  exit 1
fi

AUDIT_ROOT="${HUMAN_LNC_ATLAS_DATA_DIR}/audits"
TS="$(date +"%Y-%m-%d_%H-%M-%S")"
AUDIT_DIR="${AUDIT_ROOT}/${TS}_external_assembly_audit"

mkdir -p "${AUDIT_DIR}"

# GitHub Actions step output support
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "audit_dir=${AUDIT_DIR}" >> "${GITHUB_OUTPUT}"
fi

GENOMES_DIR="${GENOMES_DIR:-${HUMAN_LNC_ATLAS_DATA_DIR}/genomes}"
CHROM_SIZES="${CHROM_SIZES:-${GENOMES_DIR}/${ASSEMBLY}.chrom.sizes}"

CHIPSEQ_BED_DIR="${CHIPSEQ_BED_DIR:-${HUMAN_LNC_ATLAS_DATA_DIR}/chipseq_bed}"
ENCODE_DATA_DIR="${ENCODE_DATA_DIR:-${HUMAN_LNC_ATLAS_DATA_DIR}/encode_data}"
ENCODE_PEAKS_DIR="${ENCODE_PEAKS_DIR:-${HUMAN_LNC_ATLAS_DATA_DIR}/chipseq_data/encode_peaks}"

write_meta() {
  {
    echo "timestamp=${TS}"
    echo "assembly=${ASSEMBLY}"
    echo "data_dir=${HUMAN_LNC_ATLAS_DATA_DIR}"
    echo "genomes_dir=${GENOMES_DIR}"
    echo "chrom_sizes=${CHROM_SIZES}"
    echo "chipseq_bed_dir=${CHIPSEQ_BED_DIR}"
    echo "encode_data_dir=${ENCODE_DATA_DIR}"
    echo "encode_peaks_dir=${ENCODE_PEAKS_DIR}"
    echo "repo_root=${REPO_ROOT}"
    if command -v hostname >/dev/null 2>&1; then
      echo "host=$(hostname)"
    fi
    if command -v git >/dev/null 2>&1 && git -C "${REPO_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      echo "git_head=$(git -C "${REPO_ROOT}" rev-parse HEAD 2>/dev/null || true)"
      echo "git_branch=$(git -C "${REPO_ROOT}" branch --show-current 2>/dev/null || true)"
    fi
    echo "python=$(python3 --version 2>/dev/null || true)"
  } > "${AUDIT_DIR}/meta.env"
}

run_step() {
  local step_id="$1"
  shift

  local log_path="${AUDIT_DIR}/${step_id}.log"
  echo "[audit] ===== ${step_id} =====" | tee "${log_path}"
  echo "[audit] CMD: $*" | tee -a "${log_path}"
  echo "" | tee -a "${log_path}"

  # Run and tee output. If command fails, propagate non-zero exit code (fail-fast).
  "$@" 2>&1 | tee -a "${log_path}"

  echo "" | tee -a "${log_path}"
  echo "[audit] OK: ${step_id}" | tee -a "${log_path}"
}

write_meta

if [ ! -d "${GENOMES_DIR}" ]; then
  echo "[audit] ERROR: GENOMES_DIR 不存在: ${GENOMES_DIR}" >&2
  exit 1
fi
if [ ! -f "${CHROM_SIZES}" ]; then
  echo "[audit] ERROR: chrom.sizes 不存在: ${CHROM_SIZES}" >&2
  exit 1
fi

# ------------------------------------------------------------------------------
# Step 1: BigWig/BigBed header vs chrom.sizes（最强信号：能直接发现 hg19/hg38 混用）
# ------------------------------------------------------------------------------
run_step "01_validate_track_assemblies" \
  python3 "${REPO_ROOT}/scripts/genomes/validate_track_assemblies.py" \
    --genomes-dir "${GENOMES_DIR}" \
    --default-assembly "${ASSEMBLY}"

# ------------------------------------------------------------------------------
# Step 2-5: 文本 peaks 越界/未知染色体（对 .bed/.broadPeak/.narrowPeak/.gz）
# ------------------------------------------------------------------------------
if [ ! -d "${CHIPSEQ_BED_DIR}" ]; then
  echo "[audit] ERROR: chipseq_bed 目录不存在: ${CHIPSEQ_BED_DIR}" >&2
  exit 1
fi
run_step "02_validate_peak_bounds_chipseq_bed" \
  python3 "${REPO_ROOT}/scripts/genomes/validate_peak_bed_bounds.py" \
    --chrom-sizes "${CHROM_SIZES}" \
    "${CHIPSEQ_BED_DIR}"

if [ ! -d "${ENCODE_DATA_DIR}" ]; then
  echo "[audit] ERROR: encode_data 目录不存在: ${ENCODE_DATA_DIR}" >&2
  exit 1
fi
run_step "03_validate_peak_bounds_encode_data" \
  python3 "${REPO_ROOT}/scripts/genomes/validate_peak_bed_bounds.py" \
    --chrom-sizes "${CHROM_SIZES}" \
    "${ENCODE_DATA_DIR}"

if [ -d "${ENCODE_PEAKS_DIR}" ]; then
  run_step "04_validate_peak_bounds_encode_peaks" \
    python3 "${REPO_ROOT}/scripts/genomes/validate_peak_bed_bounds.py" \
      --chrom-sizes "${CHROM_SIZES}" \
      "${ENCODE_PEAKS_DIR}"
else
  echo "[audit] WARN: encode_peaks 目录不存在，跳过: ${ENCODE_PEAKS_DIR}" | tee "${AUDIT_DIR}/04_validate_peak_bounds_encode_peaks.log"
fi

# genomes/ 下偶尔会放一些 peaks（例如从 UCSC 下载的临时 broadPeak/narrowPeak）
run_step "05_validate_peak_bounds_genomes_text" \
  python3 "${REPO_ROOT}/scripts/genomes/validate_peak_bed_bounds.py" \
    --chrom-sizes "${CHROM_SIZES}" \
    "${GENOMES_DIR}"

{
  echo "OK"
  echo "audit_dir=${AUDIT_DIR}"
} > "${AUDIT_DIR}/summary.txt"

echo "[audit] ✅ 完成"
echo "[audit] 审计输出: ${AUDIT_DIR}"
