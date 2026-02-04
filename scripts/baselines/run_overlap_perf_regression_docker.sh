#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Run overlap perf regression using Docker Compose + sample DB dataset
# ==============================================================================
#
# Why:
# - Performance Overlap workflow can run on a self-hosted runner even when no
#   backend is already running on 127.0.0.1:8000.
# - Uses an isolated docker compose project name (no impact on existing stacks)
# - Loads schema/v2.3 sample dataset into a fresh Postgres container
# - Starts backend container and runs scripts/perf_overlap_regression.py
#
# Outputs (default):
# - docs/reports/perf-overlap-*.md / *.json
# - docs/baselines/performance/overlap-admin-metrics.baseline.json (generate-baseline)
#
# Requirements:
# - docker + docker compose
# - python3
#
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT"

MODE="${MODE:-check}" # check | generate-baseline
WARMUP_ROUNDS="${WARMUP_ROUNDS:-60}"
PRE_WARMUP_ROUNDS="${PRE_WARMUP_ROUNDS:-$WARMUP_ROUNDS}"
LNCRNA_GENE_ID="${LNCRNA_GENE_ID:-17276}"
SPECIES_IDS="${SPECIES_IDS:-1,3}"
RESET_METRICS="${RESET_METRICS:-true}"

# Host port for published backend (0 = random free port; avoids collisions on self-hosted runners).
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-0}"

MIN_SAMPLES="${MIN_SAMPLES:-40}"
RESPONSE_REGRESSION_PCT="${RESPONSE_REGRESSION_PCT:-8}"
RESPONSE_REGRESSION_ABS_MS="${RESPONSE_REGRESSION_ABS_MS:-2}"
DB_REGRESSION_PCT="${DB_REGRESSION_PCT:-8}"
DB_REGRESSION_ABS_MS="${DB_REGRESSION_ABS_MS:-1}"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
COMPOSE_OVERRIDE_FILE="${COMPOSE_OVERRIDE_FILE:-scripts/baselines/docker-compose.overlap-perf.yml}"

DB_NAME="${DB_NAME:-lncrna_baseline}"
DB_USER="${DB_USER:-lncrna}"
DB_PASSWORD="${DB_PASSWORD:-}"

ADMIN_API_KEY="${ADMIN_API_KEY:-}"

TRUSTED_HOSTS="${TRUSTED_HOSTS:-[\"localhost\",\"127.0.0.1\"]}"
CORS_ORIGINS="${CORS_ORIGINS:-[\"http://localhost:5173\"]}"

APP_ENV="${APP_ENV:-development}"
ENABLE_CACHE="${ENABLE_CACHE:-false}"
# Perf regression should not be blocked by rate limiting (docker bridge IP is private, not loopback).
RATE_LIMIT_BYPASS_PRIVATE="${RATE_LIMIT_BYPASS_PRIVATE:-true}"

BASE_URL="${BASE_URL:-}"
OUT_DIR="${OUT_DIR:-docs/reports}"
BASELINE_FILE="${BASELINE_FILE:-docs/baselines/performance/overlap-admin-metrics.baseline.json}"
BASELINE_RAW_METRICS_FILE="${BASELINE_RAW_METRICS_FILE:-docs/baselines/performance/overlap-admin-metrics.baseline.raw.json}"

KEEP_DOCKER="${KEEP_DOCKER:-false}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/baselines/run_overlap_perf_regression_docker.sh [options]

Options (env var compatible):
  MODE=check|generate-baseline
  BACKEND_HOST=127.0.0.1
  BACKEND_PORT=0
  BASE_URL=http://127.0.0.1:8000  # optional override (recommended to leave empty when BACKEND_PORT=0)
  WARMUP_ROUNDS=60
  PRE_WARMUP_ROUNDS=60
  LNCRNA_GENE_ID=17276
  SPECIES_IDS=1,3
  RESET_METRICS=true|false
  MIN_SAMPLES=40
  RESPONSE_REGRESSION_PCT=8
  RESPONSE_REGRESSION_ABS_MS=2
  DB_REGRESSION_PCT=8
  DB_REGRESSION_ABS_MS=1
  COMPOSE_FILE=docker-compose.yml
  COMPOSE_OVERRIDE_FILE=scripts/baselines/docker-compose.overlap-perf.yml
  BASELINE_FILE=docs/baselines/performance/overlap-admin-metrics.baseline.json
  BASELINE_RAW_METRICS_FILE=docs/baselines/performance/overlap-admin-metrics.baseline.raw.json
  OUT_DIR=docs/reports
  KEEP_DOCKER=false|true

Example:
  MODE=generate-baseline bash scripts/baselines/run_overlap_perf_regression_docker.sh
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

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

case "$MODE" in
  check|generate-baseline) ;;
  *)
    echo "invalid MODE: $MODE (expected: check|generate-baseline)" >&2
    exit 2
    ;;
esac

# Isolate compose resources (containers/networks/volumes) under a unique project name.
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-hla-overlap-perf-$(date +%Y%m%d-%H%M%S)}"

compose() {
  local -a compose_files
  compose_files=(-f "$COMPOSE_FILE")
  if [ -n "${COMPOSE_OVERRIDE_FILE:-}" ]; then
    compose_files+=(-f "$COMPOSE_OVERRIDE_FILE")
  fi

  COMPOSE_PROJECT_NAME="$PROJECT_NAME" \
  BACKEND_PORT="$BACKEND_PORT" \
  ENV="$APP_ENV" \
  ENABLE_CACHE="$ENABLE_CACHE" \
  RATE_LIMIT_BYPASS_PRIVATE="$RATE_LIMIT_BYPASS_PRIVATE" \
  DB_NAME="$DB_NAME" \
  DB_USER="$DB_USER" \
  DB_PASSWORD="$DB_PASSWORD" \
  ADMIN_API_KEY="$ADMIN_API_KEY" \
  TRUSTED_HOSTS="$TRUSTED_HOSTS" \
  CORS_ORIGINS="$CORS_ORIGINS" \
  docker compose "${compose_files[@]}" "$@"
}

cleanup() {
  if [ "$KEEP_DOCKER" = "true" ]; then
    echo "KEEP_DOCKER=true, skip cleanup. Project: $PROJECT_NAME" >&2
    return 0
  fi
  compose down >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[overlap-perf] compose project: $PROJECT_NAME"
echo "[overlap-perf] mode: $MODE"
echo "[overlap-perf] backend_host: $BACKEND_HOST"
echo "[overlap-perf] backend_port: $BACKEND_PORT"
echo "[overlap-perf] reset_metrics: $RESET_METRICS"
echo "[overlap-perf] pre_warmup_rounds: $PRE_WARMUP_ROUNDS"
echo "[overlap-perf] out_dir: $OUT_DIR"
echo "[overlap-perf] baseline_file: $BASELINE_FILE"
echo "[overlap-perf] baseline_raw_metrics_file: $BASELINE_RAW_METRICS_FILE"

# Start DB + Redis first
compose up -d postgres redis

echo "[overlap-perf] waiting for postgres..."
timeout_seconds=60
while ! compose exec -T postgres pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; do
  if [ "$timeout_seconds" -le 0 ]; then
    echo "postgres not ready" >&2
    compose logs --no-color postgres || true
    exit 1
  fi
  sleep 2
  timeout_seconds=$((timeout_seconds - 2))
done

echo "[overlap-perf] loading schema + sample data..."
for f in \
  "schema/v2.3/01_core.sql" \
  "schema/v2.3/02_extension.sql" \
  "frontend/backend/sql/chipseq_schema.sql" \
  "schema/v2.3/03_sample_data.sql"; do
  echo "  - $f"
  compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -f /dev/stdin < "$f"
done

echo "[overlap-perf] starting backend..."
compose up -d --build backend

resolve_backend_url() {
  local published
  published="$(compose port backend 8000 | head -n 1 | sed -E 's/.*:([0-9]+)$/\1/')"
  if [ -z "$published" ]; then
    echo "failed to resolve published backend port (docker compose port backend 8000)" >&2
    compose ps || true
    compose logs --no-color backend || true
    exit 1
  fi
  if [ -z "$BASE_URL" ]; then
    BASE_URL="http://${BACKEND_HOST}:${published}"
  fi
  echo "[overlap-perf] resolved backend_url: $BASE_URL (published_port=$published)"
}

resolve_backend_url

echo "[overlap-perf] waiting for backend health..."
timeout_seconds=60
while ! curl -fsS --noproxy "*" "$BASE_URL/health" >/dev/null 2>&1; do
  if [ "$timeout_seconds" -le 0 ]; then
    echo "backend not ready: $BASE_URL/health" >&2
    compose logs --no-color backend || true
    exit 1
  fi
  sleep 2
  timeout_seconds=$((timeout_seconds - 2))
done

mkdir -p "$OUT_DIR"
mkdir -p "$(dirname "$BASELINE_FILE")"

echo "[overlap-perf] running perf gate..."
reset_args=()
if [ "$RESET_METRICS" = "true" ]; then
  reset_args=(--reset-metrics)
fi

python3 scripts/perf_overlap_regression.py "$MODE" \
  --base-url "$BASE_URL" \
  --admin-api-key "$ADMIN_API_KEY" \
  --out-dir "$OUT_DIR" \
  --baseline-file "$BASELINE_FILE" \
  --baseline-raw-metrics-file "$BASELINE_RAW_METRICS_FILE" \
  "${reset_args[@]}" \
  --pre-warmup-rounds "$PRE_WARMUP_ROUNDS" \
  --warmup-rounds "$WARMUP_ROUNDS" \
  --lncrna-gene-id "$LNCRNA_GENE_ID" \
  --species-ids "$SPECIES_IDS" \
  --min-samples "$MIN_SAMPLES" \
  --response-regression-pct "$RESPONSE_REGRESSION_PCT" \
  --response-regression-abs-ms "$RESPONSE_REGRESSION_ABS_MS" \
  --db-regression-pct "$DB_REGRESSION_PCT" \
  --db-regression-abs-ms "$DB_REGRESSION_ABS_MS"

echo "[overlap-perf] done"
