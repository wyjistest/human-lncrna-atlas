#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Generate API snapshot baseline using Docker Compose + sample DB dataset
# ==============================================================================
#
# Output:
#   docs/baselines/api-snapshot.sample.json
#
# Notes:
# - Uses an isolated docker compose project name (no impact on existing stacks)
# - Loads schema/v2.3 sample dataset into a fresh Postgres container
# - Starts backend container and snapshots a small set of API endpoints
# - Cleans up containers on exit (volumes are kept by default)
#
# Requirements:
# - docker + docker compose
# - python3
#
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

DB_NAME="${DB_NAME:-lncrna_baseline}"
DB_USER="${DB_USER:-lncrna}"
DB_PASSWORD="${DB_PASSWORD:-}"
ADMIN_API_KEY="${ADMIN_API_KEY:-}"

TRUSTED_HOSTS="${TRUSTED_HOSTS:-[\"localhost\",\"127.0.0.1\"]}"
CORS_ORIGINS="${CORS_ORIGINS:-[\"http://localhost:5173\"]}"

BASE_URL="${BASE_URL:-http://localhost:8000}"
OUT_FILE="${OUT_FILE:-docs/baselines/api-snapshot.sample.json}"

KEEP_DOCKER="${KEEP_DOCKER:-false}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

gen_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 16
    return 0
  fi
  python3 -c "import secrets; print(secrets.token_hex(16))"
}

require_cmd docker
require_cmd curl
require_cmd python3

if [ -z "$DB_PASSWORD" ]; then
  DB_PASSWORD="$(gen_secret)"
fi
if [ -z "$ADMIN_API_KEY" ]; then
  ADMIN_API_KEY="$(gen_secret)"
fi

# Isolate compose resources (containers/networks/volumes) under a unique project name.
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-hla-baseline-$(date +%Y%m%d-%H%M%S)}"

compose() {
  COMPOSE_PROJECT_NAME="$PROJECT_NAME" \
  DB_NAME="$DB_NAME" \
  DB_USER="$DB_USER" \
  DB_PASSWORD="$DB_PASSWORD" \
  ADMIN_API_KEY="$ADMIN_API_KEY" \
  TRUSTED_HOSTS="$TRUSTED_HOSTS" \
  CORS_ORIGINS="$CORS_ORIGINS" \
  docker compose -f "$COMPOSE_FILE" "$@"
}

cleanup() {
  if [ "$KEEP_DOCKER" = "true" ]; then
    echo "KEEP_DOCKER=true, skip cleanup. Project: $PROJECT_NAME" >&2
    return 0
  fi
  compose down >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[baseline] compose project: $PROJECT_NAME"
echo "[baseline] target: $OUT_FILE"

# Start DB + Redis first
compose up -d postgres redis

echo "[baseline] waiting for postgres..."
compose exec -T postgres pg_isready -U "$DB_USER" -d "$DB_NAME"

echo "[baseline] loading schema + sample data..."
for f in \
  "schema/v2.3/01_core.sql" \
  "schema/v2.3/02_extension.sql" \
  "schema/v2.3/03_sample_data.sql"; do
  echo "  - $f"
  compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -f /dev/stdin < "$f"
done

echo "[baseline] starting backend..."
compose up -d --build backend

echo "[baseline] waiting for backend health..."
timeout_seconds=60
while ! curl -fsS "$BASE_URL/health" >/dev/null 2>&1; do
  if [ "$timeout_seconds" -le 0 ]; then
    echo "backend not ready: $BASE_URL/health" >&2
    exit 1
  fi
  sleep 2
  timeout_seconds=$((timeout_seconds - 2))
done

mkdir -p "$(dirname "$OUT_FILE")"

echo "[baseline] generating snapshot..."
python3 scripts/api_snapshot.py \
  --base-url "$BASE_URL" \
  --deterministic \
  --no-json \
  --pretty \
  --output "$OUT_FILE"

echo "[baseline] done: $OUT_FILE"
