#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Run genes/regulations perf regression using Docker Compose + sample DB dataset
# ==============================================================================
#
# Why:
# - Performance Genes/Regulations workflow can run on a self-hosted runner even
#   when no backend is already running on 127.0.0.1:8000.
# - Uses an isolated docker compose project name (no impact on existing stacks)
# - Loads schema/v2.3 sample dataset into a fresh Postgres container
# - Starts backend container and runs scripts/perf_genes_regulations_regression.py
#
# Outputs (default):
# - docs/reports/perf-genes-regulations-*.md / *.json
# - docs/baselines/performance/genes-regulations-admin-metrics.baseline.json (generate-baseline)
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
WARMUP_ROUNDS="${WARMUP_ROUNDS:-30}"
RESET_METRICS="${RESET_METRICS:-true}"

GENES_SPECIES_ID="${GENES_SPECIES_ID:-1}"
GENES_GENE_TYPE="${GENES_GENE_TYPE:-lncRNA}"
GENES_PAGE_SIZE="${GENES_PAGE_SIZE:-100}"

REGULATIONS_SPECIES_ID="${REGULATIONS_SPECIES_ID:-1}"
REGULATIONS_PAGE_SIZE="${REGULATIONS_PAGE_SIZE:-100}"

MIN_SAMPLES="${MIN_SAMPLES:-20}"
RESPONSE_REGRESSION_PCT="${RESPONSE_REGRESSION_PCT:-8}"
# 与 scripts/perf_genes_regulations_regression.py 的默认值一致（减少 self-hosted 环境噪声误报）
RESPONSE_REGRESSION_ABS_MS="${RESPONSE_REGRESSION_ABS_MS:-20}"
DB_REGRESSION_PCT="${DB_REGRESSION_PCT:-8}"
DB_REGRESSION_ABS_MS="${DB_REGRESSION_ABS_MS:-2}"

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

BASE_URL="${BASE_URL:-http://localhost:8000}"
OUT_DIR="${OUT_DIR:-docs/reports}"
BASELINE_FILE="${BASELINE_FILE:-docs/baselines/performance/genes-regulations-admin-metrics.baseline.json}"
BASELINE_RAW_METRICS_FILE="${BASELINE_RAW_METRICS_FILE:-docs/baselines/performance/genes-regulations-admin-metrics.baseline.raw.json}"

KEEP_DOCKER="${KEEP_DOCKER:-false}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/baselines/run_genes_regulations_perf_regression_docker.sh [options]

Options (env var compatible):
  MODE=check|generate-baseline
  BASE_URL=http://localhost:8000
  WARMUP_ROUNDS=30
  RESET_METRICS=true|false
  GENES_SPECIES_ID=1
  GENES_GENE_TYPE=lncRNA
  GENES_PAGE_SIZE=100
  REGULATIONS_SPECIES_ID=1
  REGULATIONS_PAGE_SIZE=100
  MIN_SAMPLES=20
  RESPONSE_REGRESSION_PCT=8
  RESPONSE_REGRESSION_ABS_MS=20
  DB_REGRESSION_PCT=8
  DB_REGRESSION_ABS_MS=2
  COMPOSE_FILE=docker-compose.yml
  COMPOSE_OVERRIDE_FILE=scripts/baselines/docker-compose.overlap-perf.yml
  BASELINE_FILE=docs/baselines/performance/genes-regulations-admin-metrics.baseline.json
  BASELINE_RAW_METRICS_FILE=docs/baselines/performance/genes-regulations-admin-metrics.baseline.raw.json
  OUT_DIR=docs/reports
  KEEP_DOCKER=false|true

Example:
  MODE=generate-baseline bash scripts/baselines/run_genes_regulations_perf_regression_docker.sh
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
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-hla-genes-regulations-perf-$(date +%Y%m%d-%H%M%S)}"

compose() {
  local -a compose_files
  compose_files=(-f "$COMPOSE_FILE")
  if [ -n "${COMPOSE_OVERRIDE_FILE:-}" ]; then
    compose_files+=(-f "$COMPOSE_OVERRIDE_FILE")
  fi

  COMPOSE_PROJECT_NAME="$PROJECT_NAME" \
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

echo "[genes-regulations-perf] compose project: $PROJECT_NAME"
echo "[genes-regulations-perf] mode: $MODE"
echo "[genes-regulations-perf] base_url: $BASE_URL"
echo "[genes-regulations-perf] reset_metrics: $RESET_METRICS"
echo "[genes-regulations-perf] out_dir: $OUT_DIR"
echo "[genes-regulations-perf] baseline_file: $BASELINE_FILE"
echo "[genes-regulations-perf] baseline_raw_metrics_file: $BASELINE_RAW_METRICS_FILE"

# Start DB + Redis first
compose up -d postgres redis

echo "[genes-regulations-perf] waiting for postgres..."
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

echo "[genes-regulations-perf] loading schema + sample data..."
for f in \
  "schema/v2.3/01_core.sql" \
  "schema/v2.3/02_extension.sql" \
  "frontend/backend/sql/chipseq_schema.sql" \
  "schema/v2.3/03_sample_data.sql"; do
  echo "  - $f"
  compose exec -T postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -f /dev/stdin < "$f"
done

echo "[genes-regulations-perf] starting backend..."
compose up -d --build backend

echo "[genes-regulations-perf] waiting for backend health..."
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

echo "[genes-regulations-perf] running perf gate..."
reset_args=()
if [ "$RESET_METRICS" = "true" ]; then
  reset_args=(--reset-metrics)
fi

python3 scripts/perf_genes_regulations_regression.py "$MODE" \
  --base-url "$BASE_URL" \
  --admin-api-key "$ADMIN_API_KEY" \
  --out-dir "$OUT_DIR" \
  --baseline-file "$BASELINE_FILE" \
  --baseline-raw-metrics-file "$BASELINE_RAW_METRICS_FILE" \
  "${reset_args[@]}" \
  --warmup-rounds "$WARMUP_ROUNDS" \
  --genes-species-id "$GENES_SPECIES_ID" \
  --genes-gene-type "$GENES_GENE_TYPE" \
  --genes-page-size "$GENES_PAGE_SIZE" \
  --regulations-species-id "$REGULATIONS_SPECIES_ID" \
  --regulations-page-size "$REGULATIONS_PAGE_SIZE" \
  --min-samples "$MIN_SAMPLES" \
  --response-regression-pct "$RESPONSE_REGRESSION_PCT" \
  --response-regression-abs-ms "$RESPONSE_REGRESSION_ABS_MS" \
  --db-regression-pct "$DB_REGRESSION_PCT" \
  --db-regression-abs-ms "$DB_REGRESSION_ABS_MS"

echo "[genes-regulations-perf] done"
