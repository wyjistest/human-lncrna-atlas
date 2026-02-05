#!/usr/bin/env bash
# ==============================================================================
# ChIP-seq reference_genome 审计与回填（DB）
# ==============================================================================
# 目标：
# - 审计 DB 中 active 的 ChIP-seq 实验（chipseq_experiments.reference_genome IS NULL）
# - 通过 peaks 坐标边界校验（peak_end <= <assembly>.chrom.sizes）判断是否与目标组装一致
# - 生成可审计输出 + 可回滚 SQL（默认只生成，不写 DB；--apply 才执行回填）
#
# 默认基准：
# - 组装：hg19
# - 数据根目录：/data/wenyujianData/humanLncAtlas
# - chrom.sizes：$HUMAN_LNC_ATLAS_DATA_DIR/genomes/<assembly>.chrom.sizes
# - 数据库：lncrna_production@localhost:5432（用户/密码走 PG* 或 ~/.pgpass）
#
# 用法：
#   # 只读审计（推荐）
#   bash scripts/genomes/audit_chipseq_reference_genome_db.sh
#
#   # 指定 DB / 组装 / 数据目录
#   DB_USER=amax DB_NAME=lncrna_production HUMAN_LNC_ATLAS_DATA_DIR="/data/wenyujianData/humanLncAtlas" \
#     bash scripts/genomes/audit_chipseq_reference_genome_db.sh --assembly hg19
#
#   # 生成 SQL 并执行回填（会写 DB；请先确认审计结果与回滚脚本）
#   bash scripts/genomes/audit_chipseq_reference_genome_db.sh --apply
#
# 输出：
#   $HUMAN_LNC_ATLAS_DATA_DIR/audits/<timestamp>_chipseq_reference_genome_db_audit/
#     - chipseq_reference_genome_audit.tsv           # 每个 experiment 的校验统计
#     - pass_experiment_ids.txt / fail_experiment_ids.txt
#     - update_reference_genome_<assembly>.sql       # 回填 SQL（仅 PASS 集合）
#     - rollback_reference_genome_<assembly>.sql     # 回滚 SQL
#     - meta.env / summary.txt / psql_audit.log
# ==============================================================================

set -euo pipefail

show_help() {
  awk 'NR==1 {next} /^#/ {sub(/^# ?/, "", $0); print; next} {exit}' "$0"
}

require_arg_value() {
  local opt="$1"
  local value="${2:-}"
  if [[ -z "${value:-}" || "${value:-}" == -* ]]; then
    echo "[audit] ERROR: Option ${opt} requires a value" >&2
    show_help >&2
    exit 2
  fi
}

if ! command -v psql >/dev/null 2>&1; then
  echo "[audit] ERROR: psql not found. Please install PostgreSQL client tools." >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"

HUMAN_LNC_ATLAS_DATA_DIR="${HUMAN_LNC_ATLAS_DATA_DIR:-/data/wenyujianData/humanLncAtlas}"
ASSEMBLY="${ASSEMBLY:-hg19}"
SPECIES_ID="${SPECIES_ID:-1}" # Human

DB_HOST="${DB_HOST:-${PGHOST:-localhost}}"
DB_PORT="${DB_PORT:-${PGPORT:-5432}}"
DB_NAME="${DB_NAME:-${PGDATABASE:-lncrna_production}}"
DB_USER="${DB_USER:-${PGUSER:-postgres}}"
DB_PASSWORD="${DB_PASSWORD:-}"

CHROM_SIZES="${CHROM_SIZES:-${HUMAN_LNC_ATLAS_DATA_DIR}/genomes/${ASSEMBLY}.chrom.sizes}"

APPLY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      exit 0
      ;;
    --apply)
      APPLY=true
      shift
      ;;
    --data-dir)
      require_arg_value "$1" "${2:-}"
      HUMAN_LNC_ATLAS_DATA_DIR="$2"
      shift 2
      ;;
    --assembly)
      require_arg_value "$1" "${2:-}"
      ASSEMBLY="$2"
      shift 2
      ;;
    --chrom-sizes)
      require_arg_value "$1" "${2:-}"
      CHROM_SIZES="$2"
      shift 2
      ;;
    --species-id)
      require_arg_value "$1" "${2:-}"
      SPECIES_ID="$2"
      shift 2
      ;;
    --db-host)
      require_arg_value "$1" "${2:-}"
      DB_HOST="$2"
      shift 2
      ;;
    --db-port)
      require_arg_value "$1" "${2:-}"
      DB_PORT="$2"
      shift 2
      ;;
    --db-name)
      require_arg_value "$1" "${2:-}"
      DB_NAME="$2"
      shift 2
      ;;
    --db-user)
      require_arg_value "$1" "${2:-}"
      DB_USER="$2"
      shift 2
      ;;
    *)
      echo "[audit] ERROR: Unknown option: $1" >&2
      show_help >&2
      exit 2
      ;;
  esac
done

if [ ! -f "${CHROM_SIZES}" ]; then
  echo "[audit] ERROR: chrom.sizes not found: ${CHROM_SIZES}" >&2
  exit 1
fi

if [ -n "${DB_PASSWORD}" ]; then
  export PGPASSWORD="${DB_PASSWORD}"
fi

AUDIT_ROOT="${HUMAN_LNC_ATLAS_DATA_DIR}/audits"
TS="$(date +"%Y-%m-%d_%H-%M-%S")"
AUDIT_DIR="${AUDIT_ROOT}/${TS}_chipseq_reference_genome_db_audit"
mkdir -p "${AUDIT_DIR}"

AUDIT_TSV="${AUDIT_DIR}/chipseq_reference_genome_audit.tsv"
PASS_IDS="${AUDIT_DIR}/pass_experiment_ids.txt"
FAIL_IDS="${AUDIT_DIR}/fail_experiment_ids.txt"
PSQL_LOG="${AUDIT_DIR}/psql_audit.log"
SUMMARY="${AUDIT_DIR}/summary.txt"

UPDATE_SQL="${AUDIT_DIR}/update_reference_genome_${ASSEMBLY}.sql"
ROLLBACK_SQL="${AUDIT_DIR}/rollback_reference_genome_${ASSEMBLY}.sql"

{
  echo "timestamp=${TS}"
  echo "host=$(hostname || true)"
  echo "repo_root=${REPO_ROOT}"
  echo "repo_sha=$(git -C \"${REPO_ROOT}\" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "data_dir=${HUMAN_LNC_ATLAS_DATA_DIR}"
  echo "assembly=${ASSEMBLY}"
  echo "chrom_sizes=${CHROM_SIZES}"
  echo "species_id=${SPECIES_ID}"
  echo "db_host=${DB_HOST}"
  echo "db_port=${DB_PORT}"
  echo "db_name=${DB_NAME}"
  echo "db_user=${DB_USER}"
  echo "apply=${APPLY}"
} > "${AUDIT_DIR}/meta.env"

echo "[audit] Running DB audit (read-only) ..."
psql -w -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
  >"${PSQL_LOG}" 2>&1 <<SQL
\set ON_ERROR_STOP on

CREATE TEMP TABLE tmp_chrom_sizes (
  chrom TEXT PRIMARY KEY,
  chrom_len BIGINT NOT NULL
);

-- Client-side copy: reads chrom.sizes from this machine (psql client).
\copy tmp_chrom_sizes (chrom, chrom_len) FROM '${CHROM_SIZES}' WITH (FORMAT csv, DELIMITER E'\t')

CREATE TEMP TABLE tmp_audit_results AS
WITH exp AS (
  SELECT experiment_id, experiment_name
  FROM chipseq_experiments
  WHERE is_active = TRUE
    AND species_id = ${SPECIES_ID}
    AND reference_genome IS NULL
),
peak_stats AS (
  SELECT
    p.experiment_id,
    COUNT(*) AS peak_count,
    SUM(CASE WHEN cs.chrom IS NULL THEN 1 ELSE 0 END) AS unknown_chrom_records,
    SUM(CASE WHEN cs.chrom IS NOT NULL AND p.peak_end > cs.chrom_len THEN 1 ELSE 0 END) AS end_gt_chrom_len_records
  FROM chipseq_peaks p
  LEFT JOIN tmp_chrom_sizes cs ON cs.chrom = p.chromosome
  WHERE p.species_id = ${SPECIES_ID}
    AND p.experiment_id IN (SELECT experiment_id FROM exp)
  GROUP BY p.experiment_id
)
SELECT
  e.experiment_id,
  e.experiment_name,
  COALESCE(s.peak_count, 0) AS peak_count,
  COALESCE(s.unknown_chrom_records, 0) AS unknown_chrom_records,
  COALESCE(s.end_gt_chrom_len_records, 0) AS end_gt_chrom_len_records,
  (COALESCE(s.unknown_chrom_records, 0) = 0 AND COALESCE(s.end_gt_chrom_len_records, 0) = 0) AS pass_hg19
FROM exp e
LEFT JOIN peak_stats s ON s.experiment_id = e.experiment_id;

\copy (SELECT * FROM tmp_audit_results ORDER BY experiment_id) TO '${AUDIT_TSV}' WITH (FORMAT csv, DELIMITER E'\t', HEADER true)
\copy (SELECT experiment_id FROM tmp_audit_results WHERE pass_hg19 ORDER BY experiment_id) TO '${PASS_IDS}' WITH (FORMAT csv, DELIMITER E'\t')
\copy (SELECT experiment_id FROM tmp_audit_results WHERE NOT pass_hg19 ORDER BY experiment_id) TO '${FAIL_IDS}' WITH (FORMAT csv, DELIMITER E'\t')

\echo OK
SQL

last_line="$(tail -n 1 "${PSQL_LOG}" 2>/dev/null || true)"
if [ "${last_line}" != "OK" ]; then
  echo "[audit] ERROR: DB audit failed. See log: ${PSQL_LOG}" >&2
  echo "FAIL" > "${SUMMARY}"
  echo "audit_dir=${AUDIT_DIR}" >> "${SUMMARY}"
  exit 1
fi

ids_csv="$(paste -sd, "${PASS_IDS}" 2>/dev/null || true)"

cat > "${UPDATE_SQL}" <<EOF
-- Auto-generated by scripts/genomes/audit_chipseq_reference_genome_db.sh
-- Purpose: backfill chipseq_experiments.reference_genome for PASS experiments (reference_genome IS NULL).
-- Assembly: ${ASSEMBLY}
-- Audit dir: ${AUDIT_DIR}

BEGIN;
EOF

if [ -n "${ids_csv:-}" ]; then
  cat >> "${UPDATE_SQL}" <<EOF
UPDATE chipseq_experiments
SET reference_genome = '${ASSEMBLY}'
WHERE reference_genome IS NULL
  AND species_id = ${SPECIES_ID}
  AND is_active = TRUE
  AND experiment_id IN (${ids_csv});
EOF
else
  echo "-- No PASS experiments detected; no-op." >> "${UPDATE_SQL}"
fi

echo "COMMIT;" >> "${UPDATE_SQL}"

cat > "${ROLLBACK_SQL}" <<EOF
-- Auto-generated by scripts/genomes/audit_chipseq_reference_genome_db.sh
-- Purpose: rollback reference_genome backfill for the same experiment_id list.
-- NOTE: This reverts only the IDs that this audit would update.
-- Audit dir: ${AUDIT_DIR}

BEGIN;
EOF

if [ -n "${ids_csv:-}" ]; then
  cat >> "${ROLLBACK_SQL}" <<EOF
UPDATE chipseq_experiments
SET reference_genome = NULL
WHERE reference_genome = '${ASSEMBLY}'
  AND species_id = ${SPECIES_ID}
  AND experiment_id IN (${ids_csv});
EOF
else
  echo "-- No PASS experiments detected; no-op." >> "${ROLLBACK_SQL}"
fi

echo "COMMIT;" >> "${ROLLBACK_SQL}"

pass_count="$(wc -l < "${PASS_IDS}" | tr -d '[:space:]' || echo 0)"
fail_count="$(wc -l < "${FAIL_IDS}" | tr -d '[:space:]' || echo 0)"

{
  echo "OK"
  echo "audit_dir=${AUDIT_DIR}"
  echo "pass_experiments=${pass_count}"
  echo "fail_experiments=${fail_count}"
  echo "update_sql=${UPDATE_SQL}"
  echo "rollback_sql=${ROLLBACK_SQL}"
} > "${SUMMARY}"

echo "[audit] ✅ 完成"
echo "[audit] 审计输出: ${AUDIT_DIR}"

if [ "${APPLY}" = true ]; then
  if [ -z "${ids_csv:-}" ]; then
    echo "[audit] WARN: No PASS experiments to apply; skipping DB update." | tee -a "${AUDIT_DIR}/apply.log"
    exit 0
  fi

echo "[audit] Applying backfill SQL (writes DB) ..."
  psql -w -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
    -v ON_ERROR_STOP=1 -f "${UPDATE_SQL}" | tee "${AUDIT_DIR}/apply.log"

  echo "[audit] Verify updated rows ..."
  psql -w -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
    -c "SELECT COUNT(*) AS updated FROM chipseq_experiments WHERE is_active = TRUE AND species_id = ${SPECIES_ID} AND reference_genome = '${ASSEMBLY}';" \
    | tee -a "${AUDIT_DIR}/apply.log"
fi
