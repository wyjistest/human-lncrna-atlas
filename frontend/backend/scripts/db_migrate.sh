#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# DB migrations runner (auditable + rollbackable)
# ==============================================================================
#
# Features:
# - Executes versioned *.up.sql / *.down.sql migrations via psql
# - Records every successful apply/rollback into schema_migration_events (audit trail)
# - Supports status/list/up/down/up-all
#
# Connection:
# - Uses standard psql env vars (PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE)
# - Or project-style vars: DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME
#
# Examples:
#   bash frontend/backend/scripts/db_migrate.sh list
#   DB_HOST=127.0.0.1 DB_PORT=5432 DB_USER=lncrna DB_PASSWORD=... DB_NAME=lncrna \
#     bash frontend/backend/scripts/db_migrate.sh status
#   bash frontend/backend/scripts/db_migrate.sh up 0002_pg_trgm_search_indexes
#   bash frontend/backend/scripts/db_migrate.sh down 0002_pg_trgm_search_indexes
#
# Logs:
# - Default: docs/reports/db-migrations/<ts>_<migration>_<direction>.log
# - Override: LOG_DIR=/path/to/logs
#
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

MIGRATIONS_DIR="${MIGRATIONS_DIR:-$SCRIPT_DIR/db_migrations}"
LOG_DIR="${LOG_DIR:-$REPO_ROOT/docs/reports/db-migrations}"

LOCK_KEY_1=20260121
LOCK_KEY_2=42

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

usage() {
  cat <<'USAGE'
Usage:
  db_migrate.sh list
  db_migrate.sh verify
  db_migrate.sh status
  db_migrate.sh up <migration_name>
  db_migrate.sh down <migration_name>
  db_migrate.sh up-all

Env (either set PG* or DB_*):
  PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE
  DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME

Optional:
  MIGRATIONS_DIR=...   # default: frontend/backend/scripts/db_migrations
  LOG_DIR=...          # default: docs/reports/db-migrations
USAGE
}

require_cmd "psql"
require_cmd "python3"

psql_args=(-v "ON_ERROR_STOP=1")

if [ -n "${DB_HOST:-}" ]; then psql_args+=(-h "$DB_HOST"); fi
if [ -n "${DB_PORT:-}" ]; then psql_args+=(-p "$DB_PORT"); fi
if [ -n "${DB_USER:-}" ]; then psql_args+=(-U "$DB_USER"); fi
if [ -n "${DB_NAME:-}" ]; then psql_args+=(-d "$DB_NAME"); fi

if [ -n "${DB_PASSWORD:-}" ]; then
  export PGPASSWORD="$DB_PASSWORD"
fi

run_psql() {
  psql "${psql_args[@]}" "$@"
}

ensure_audit_table() {
  run_psql <<'SQL' >/dev/null
CREATE TABLE IF NOT EXISTS schema_migration_events (
  event_id BIGSERIAL PRIMARY KEY,
  migration_id TEXT NOT NULL,
  migration_name TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('up', 'down')),
  checksum TEXT NOT NULL,
  git_sha TEXT,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  applied_by TEXT NOT NULL DEFAULT current_user,
  applied_from TEXT
);

CREATE INDEX IF NOT EXISTS idx_schema_migration_events_migration_id_applied_at
  ON schema_migration_events (migration_id, applied_at DESC, event_id DESC);
SQL
}

acquire_lock() {
  run_psql -c "SELECT pg_advisory_lock($LOCK_KEY_1, $LOCK_KEY_2);" >/dev/null
}

release_lock() {
  run_psql -c "SELECT pg_advisory_unlock($LOCK_KEY_1, $LOCK_KEY_2);" >/dev/null 2>&1 || true
}

sha256_file() {
  python3 - <<'PY' "$1"
import hashlib
import sys
from pathlib import Path

p = Path(sys.argv[1])
h = hashlib.sha256()
h.update(p.read_bytes())
print(h.hexdigest())
PY
}

git_sha() {
  if command -v git >/dev/null 2>&1 && git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || true
    return 0
  fi
  echo ""
}

timestamp_utc() {
  date -u +"%Y-%m-%dT%H-%M-%SZ"
}

latest_direction() {
  local migration_name="$1"
  run_psql -tA -v "migration_name=$migration_name" -c \
    "SELECT direction FROM schema_migration_events WHERE migration_name = :'migration_name' ORDER BY applied_at DESC, event_id DESC LIMIT 1;" \
    | tr -d '[:space:]'
}

record_event() {
  local migration_id="$1"
  local migration_name="$2"
  local direction="$3"
  local checksum="$4"
  local git_sha_value="$5"
  local applied_from="$6"

  run_psql \
    -v "migration_id=$migration_id" \
    -v "migration_name=$migration_name" \
    -v "direction=$direction" \
    -v "checksum=$checksum" \
    -v "git_sha=$git_sha_value" \
    -v "applied_from=$applied_from" \
    -c "
      INSERT INTO schema_migration_events (migration_id, migration_name, direction, checksum, git_sha, applied_from)
      VALUES (
        :'migration_id',
        :'migration_name',
        :'direction',
        :'checksum',
        NULLIF(:'git_sha', ''),
        NULLIF(:'applied_from', '')
      );
    " >/dev/null
}

run_migration_file() {
  local direction="$1"
  local migration_name="$2"
  local migration_file="$3"

  mkdir -p "$LOG_DIR"
  local ts
  ts="$(timestamp_utc)"
  local log_file="$LOG_DIR/${ts}_${migration_name}_${direction}.log"

  echo "[db-migrate] running: $migration_file"
  echo "[db-migrate] log: $log_file"

  # Keep both stdout/stderr for postmortem auditing (file is not committed by default).
  run_psql -f "$migration_file" 2>&1 | tee "$log_file"
}

list_migrations() {
  find "$MIGRATIONS_DIR" -maxdepth 1 -type f -name "*.up.sql" -print \
    | while IFS= read -r f; do
      b="$(basename "$f")"
      echo "${b%.up.sql}"
    done \
    | sort
}

verify_migrations() {
  if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo "missing migrations dir: $MIGRATIONS_DIR" >&2
    return 2
  fi

  local failed=0

  # 1) Check every up has matching down, and naming is sane.
  mapfile -t migrations < <(list_migrations)
  if [ "${#migrations[@]}" -eq 0 ]; then
    echo "[db-migrate] no migrations found in: $MIGRATIONS_DIR" >&2
    return 1
  fi

  for name in "${migrations[@]}"; do
    if [[ ! "$name" =~ ^[0-9]{4}_[a-z0-9][a-z0-9_-]*$ ]]; then
      echo "[db-migrate][verify] invalid migration name: $name (expected: 0001_slug)" >&2
      failed=1
      continue
    fi

    if [ ! -f "$MIGRATIONS_DIR/${name}.down.sql" ]; then
      echo "[db-migrate][verify] missing down.sql for: $name" >&2
      failed=1
    fi
  done

  # 2) Check no orphan down.sql exists without matching up.sql.
  while IFS= read -r down_file; do
    down_base="$(basename "$down_file")"
    name="${down_base%.down.sql}"
    if [ ! -f "$MIGRATIONS_DIR/${name}.up.sql" ]; then
      echo "[db-migrate][verify] orphan down.sql without up.sql: $down_base" >&2
      failed=1
    fi
  done < <(find "$MIGRATIONS_DIR" -maxdepth 1 -type f -name "*.down.sql" -print | sort)

  if [ "$failed" -ne 0 ]; then
    return 1
  fi

  echo "[db-migrate][verify] OK (${#migrations[@]} migrations)"
  return 0
}

cmd="${1:-}"
case "$cmd" in
  list)
    if [ ! -d "$MIGRATIONS_DIR" ]; then
      echo "missing migrations dir: $MIGRATIONS_DIR" >&2
      exit 1
    fi
    echo "[db-migrate] migrations dir: $MIGRATIONS_DIR"
    list_migrations
    ;;
  verify)
    verify_migrations
    ;;
  status)
    ensure_audit_table
    echo "[db-migrate] latest migration events (top 50):"
    run_psql -P pager=off -c \
      "SELECT event_id, migration_name, direction, applied_at, applied_by, applied_from, git_sha, checksum FROM schema_migration_events ORDER BY applied_at DESC, event_id DESC LIMIT 50;"
    ;;
  up|down)
    migration_name="${2:-}"
    if [ -z "$migration_name" ]; then
      usage >&2
      exit 2
    fi
    if [ ! -d "$MIGRATIONS_DIR" ]; then
      echo "missing migrations dir: $MIGRATIONS_DIR" >&2
      exit 1
    fi
    migration_file="$MIGRATIONS_DIR/${migration_name}.${cmd}.sql"
    if [ ! -f "$migration_file" ]; then
      echo "missing migration file: $migration_file" >&2
      exit 1
    fi

    ensure_audit_table
    acquire_lock
    trap release_lock EXIT

    current="$(latest_direction "$migration_name")"
    if [ "$cmd" = "up" ] && [ "$current" = "up" ]; then
      echo "[db-migrate] already applied: $migration_name"
      exit 0
    fi
    if [ "$cmd" = "down" ] && [ "$current" != "up" ]; then
      echo "[db-migrate] not applied (skip rollback): $migration_name"
      exit 0
    fi

    checksum="$(sha256_file "$migration_file")"
    git_sha_value="$(git_sha)"
    applied_from="$(hostname 2>/dev/null || true)"
    migration_id="${migration_name%%_*}"

    run_migration_file "$cmd" "$migration_name" "$migration_file"
    record_event "$migration_id" "$migration_name" "$cmd" "$checksum" "$git_sha_value" "$applied_from"
    echo "[db-migrate] recorded event: $migration_name ($cmd)"
    ;;
  up-all)
    if [ ! -d "$MIGRATIONS_DIR" ]; then
      echo "missing migrations dir: $MIGRATIONS_DIR" >&2
      exit 1
    fi
    ensure_audit_table
    acquire_lock
    trap release_lock EXIT

    mapfile -t migrations < <(list_migrations)
    if [ "${#migrations[@]}" -eq 0 ]; then
      echo "[db-migrate] no migrations found in: $MIGRATIONS_DIR" >&2
      exit 1
    fi

    for migration_name in "${migrations[@]}"; do
      current="$(latest_direction "$migration_name")"
      if [ "$current" = "up" ]; then
        echo "[db-migrate] already applied: $migration_name"
        continue
      fi
      migration_file="$MIGRATIONS_DIR/${migration_name}.up.sql"
      checksum="$(sha256_file "$migration_file")"
      git_sha_value="$(git_sha)"
      applied_from="$(hostname 2>/dev/null || true)"
      migration_id="${migration_name%%_*}"

      run_migration_file "up" "$migration_name" "$migration_file"
      record_event "$migration_id" "$migration_name" "up" "$checksum" "$git_sha_value" "$applied_from"
      echo "[db-migrate] recorded event: $migration_name (up)"
    done
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    echo "unknown command: $cmd" >&2
    usage >&2
    exit 2
    ;;
esac
