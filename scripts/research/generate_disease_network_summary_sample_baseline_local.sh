#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Generate disease network summary using local PostgreSQL + sample DB
# ==============================================================================
#
# Purpose:
# - Quick smoke test for scripts/research/disease_network_summary.py
# - No need for the full production dataset
#
# What it does:
# - Creates a temporary Postgres database
# - Loads schema/v2.3/{01_core,02_extension,03_sample_data}.sql
# - Runs the disease network summary exporter against that DB
# - Drops the temporary DB (unless KEEP_DB=true)
#
# Output (defaults):
# - docs/baselines/research/disease-network-*.{tsv,md}
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
EVIDENCE_SPECIES_ID="${EVIDENCE_SPECIES_ID:-1}"
TOP_TRAITS="${TOP_TRAITS:-50}"
TOP_LNCRNAS="${TOP_LNCRNAS:-50}"
OUT_DIR="${OUT_DIR:-docs/baselines/research}"
GENERATED_AT="${GENERATED_AT:-sample}"

KEEP_DB="${KEEP_DB:-false}"

createdb_best_effort() {
  psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "CREATE DATABASE \"$DB_NAME\";" >/dev/null
}

dropdb_best_effort() {
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
  "schema/v2.3/03_sample_data.sql"; do
  echo "  - $f"
  psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$f" >/dev/null
done

echo "[research-baseline-local] generating disease network summary (evidence_species_id=$EVIDENCE_SPECIES_ID) ..."
mkdir -p "$OUT_DIR"

DB_HOST="$DB_HOST" \
DB_PORT="$DB_PORT" \
DB_USER="$DB_USER" \
DB_PASSWORD="$DB_PASSWORD" \
DB_NAME="$DB_NAME" \
"$python_bin" "scripts/research/disease_network_summary.py" \
  --evidence-species-id "$EVIDENCE_SPECIES_ID" \
  --top-traits "$TOP_TRAITS" \
  --top-lncrnas "$TOP_LNCRNAS" \
  --generated-at "$GENERATED_AT" \
  --out-dir "$OUT_DIR"

echo "[research-baseline-local] done (out_dir=$OUT_DIR)"

