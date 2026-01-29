#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Generate Top lncRNA target genes (for enrichment) using local PostgreSQL + sample DB
# ==============================================================================
#
# Purpose:
# - Quick smoke test for scripts/research/top_lncrna_target_genes_for_enrichment.py
# - No need for the full production dataset
#
# What it does:
# - Creates a temporary Postgres database
# - Loads schema/v2.3/{01_core,02_extension,03_sample_data}.sql (+ chipseq_schema)
# - Runs the target genes exporter against that DB
# - Drops the temporary DB (unless KEEP_DB=true)
#
# Notes:
# - The v2.3 sample dataset uses BA values around ~55-82, so MIN_BA defaults to 50.
#   If you set MIN_BA=100 on the sample DB, you will likely get an empty output.
#
# Output (defaults):
# - docs/baselines/research/top-lncrna-target-genes-ba${MIN_BA}-top${TOP_N}-species${SPECIES_ID}.(tsv|txt|md)
#
# Requirements:
# - psql (and permissions to create/drop a local database)
# - python3 + backend dependencies installed (prefer frontend/backend/.venv)
#
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

require_cmd psql
require_cmd python3

BACKEND_DIR="${BACKEND_DIR:-$REPO_ROOT/frontend/backend}"

resolve_backend_python() {
  if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
    echo "$BACKEND_DIR/.venv/bin/python"
    return 0
  fi
  if [ -x "$BACKEND_DIR/venv/bin/python" ]; then
    echo "$BACKEND_DIR/venv/bin/python"
    return 0
  fi
  echo "python3"
}

python_bin="$(resolve_backend_python)"

# Use a random, isolated DB name to avoid touching existing databases.
DB_NAME="${DB_NAME:-lncrna_research_baseline_$(date +%Y%m%d_%H%M%S)}"
DB_USER="${DB_USER:-$(whoami)}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_PASSWORD="${DB_PASSWORD:-}"

# Report parameters (sample DB defaults)
SPECIES_ID="${SPECIES_ID:-1}"
MIN_BA="${MIN_BA:-50}"
TOP_N="${TOP_N:-50}"
OUT_DIR="${OUT_DIR:-docs/baselines/research}"
GENERATED_AT="${GENERATED_AT:-sample}"
TARGET_PROTEIN_CODING_ONLY="${TARGET_PROTEIN_CODING_ONLY:-false}"

KEEP_DB="${KEEP_DB:-false}"

createdb_best_effort() {
  psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "CREATE DATABASE \"$DB_NAME\";" >/dev/null
}

dropdb_best_effort() {
  # Terminate connections then drop. Best-effort cleanup only.
  psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME';" >/dev/null || true
  psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$DB_NAME\";" >/dev/null || true
}

cleanup() {
  if [ "$KEEP_DB" != "true" ]; then
    dropdb_best_effort
  else
    echo "KEEP_DB=true, keeping database: $DB_NAME" >&2
  fi
}
trap cleanup EXIT

echo "[research-baseline-local] creating db: $DB_NAME"
createdb_best_effort

echo "[research-baseline-local] loading schema + sample data..."
for f in \
  "schema/v2.3/01_core.sql" \
  "schema/v2.3/02_extension.sql" \
  "frontend/backend/sql/chipseq_schema.sql" \
  "schema/v2.3/03_sample_data.sql"; do
  echo "  - $f"
  psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$f" >/dev/null
done

echo "[research-baseline-local] generating targets (species_id=$SPECIES_ID, min_ba=$MIN_BA, top_n=$TOP_N) ..."
mkdir -p "$OUT_DIR"

cmd=(
  "$python_bin"
  "scripts/research/top_lncrna_target_genes_for_enrichment.py"
  --species-id "$SPECIES_ID"
  --min-ba "$MIN_BA"
  --top-n "$TOP_N"
  --generated-at "$GENERATED_AT"
  --out-dir "$OUT_DIR"
)

if [ "$TARGET_PROTEIN_CODING_ONLY" = "true" ]; then
  cmd+=(--target-protein-coding-only)
fi

DB_HOST="$DB_HOST" \
DB_PORT="$DB_PORT" \
DB_USER="$DB_USER" \
DB_PASSWORD="$DB_PASSWORD" \
DB_NAME="$DB_NAME" \
"${cmd[@]}"

echo "[research-baseline-local] done (out_dir=$OUT_DIR)"

