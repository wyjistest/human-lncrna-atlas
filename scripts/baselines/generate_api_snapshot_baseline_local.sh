#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Generate API snapshot baseline using local PostgreSQL + local backend venv
# ==============================================================================
#
# Output:
#   docs/baselines/api-snapshot.sample.json
#
# What it does:
# - Creates a temporary Postgres database
# - Loads schema/v2.3/{01_core,02_extension,03_sample_data}.sql
# - Starts the backend (uvicorn) pointing at that DB
# - Runs scripts/api_snapshot.py with --deterministic --no-json
# - Cleans up backend process and drops the temporary DB
#
# Requirements:
# - psql (and permissions to create/drop a local database)
# - python3 + backend dependencies installed (prefer frontend/backend/.venv)
# - curl
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
require_cmd curl
require_cmd python3

BACKEND_DIR="${BACKEND_DIR:-$REPO_ROOT/frontend/backend}"

gen_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 16
    return 0
  fi
  python3 -c "import secrets; print(secrets.token_hex(16))"
}

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
DB_NAME="${DB_NAME:-lncrna_api_snapshot_baseline_$(date +%Y%m%d_%H%M%S)}"
DB_USER="${DB_USER:-$(whoami)}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
ADMIN_API_KEY="${ADMIN_API_KEY:-}"

PORT="${PORT:-18000}"
BASE_URL="${BASE_URL:-http://127.0.0.1:${PORT}}"
OUT_FILE="${OUT_FILE:-docs/baselines/api-snapshot.sample.json}"

KEEP_DB="${KEEP_DB:-false}"

createdb_best_effort() {
  psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "CREATE DATABASE \"$DB_NAME\";" >/dev/null
}

dropdb_best_effort() {
  # Terminate connections then drop. Best-effort cleanup only.
  psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME';" >/dev/null || true
  psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$DB_NAME\";" >/dev/null || true
}

backend_pid=""

cleanup() {
  if [ -n "${backend_pid:-}" ]; then
    kill "$backend_pid" >/dev/null 2>&1 || true
    wait "$backend_pid" >/dev/null 2>&1 || true
  fi
  if [ "$KEEP_DB" != "true" ]; then
    dropdb_best_effort
  else
    echo "KEEP_DB=true, keeping database: $DB_NAME" >&2
  fi
}
trap cleanup EXIT

echo "[baseline-local] creating db: $DB_NAME"
createdb_best_effort

echo "[baseline-local] loading schema + sample data..."
for f in \
  "schema/v2.3/01_core.sql" \
  "schema/v2.3/02_extension.sql" \
  "schema/v2.3/03_sample_data.sql"; do
  echo "  - $f"
  psql -v ON_ERROR_STOP=1 -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$f" >/dev/null
done

if [ -z "$ADMIN_API_KEY" ]; then
  ADMIN_API_KEY="$(gen_secret)"
fi

echo "[baseline-local] starting backend on $BASE_URL ..."
(
  cd "$BACKEND_DIR"
  ENV=development \
  ENABLE_CACHE=false \
  DB_HOST="$DB_HOST" \
  DB_PORT="$DB_PORT" \
  DB_USER="$DB_USER" \
  DB_NAME="$DB_NAME" \
  ADMIN_REQUIRE_API_KEY=true \
  ADMIN_API_KEY="$ADMIN_API_KEY" \
  "$python_bin" -m uvicorn main:app --host 127.0.0.1 --port "$PORT" --log-level warning
) &
backend_pid="$!"

echo "[baseline-local] waiting for backend health..."
timeout_seconds=60
while ! curl -fsS --noproxy "*" "$BASE_URL/health" >/dev/null 2>&1; do
  if [ "$timeout_seconds" -le 0 ]; then
    echo "backend not ready: $BASE_URL/health" >&2
    exit 1
  fi
  sleep 2
  timeout_seconds=$((timeout_seconds - 2))
done

mkdir -p "$(dirname "$OUT_FILE")"

echo "[baseline-local] generating snapshot..."
python3 scripts/api_snapshot.py \
  --base-url "$BASE_URL" \
  --deterministic \
  --no-json \
  --pretty \
  --output "$OUT_FILE" >/dev/null

echo "[baseline-local] done: $OUT_FILE"
