#!/bin/bash
# ============================================================================
# Human LncRNA Atlas - Materialized View Refresh Script
# ============================================================================
# Purpose: Refresh materialized views used by the API (optional performance optimizations)
# Usage: ./refresh_materialized_views.sh [options]
#
# Options:
#   -h, --help          Show this help message
#   -c, --concurrent    Use CONCURRENTLY option (default, non-blocking)
#   -f, --full          Use full refresh (blocking but faster)
#   -s, --status        Show status only, don't refresh
#   -v, --verbose       Verbose output
#   -d, --database      Database name (default: lncrna_production)
#   -H, --host          Database host (default: localhost)
#   -p, --port          Database port (default: 5432)
#   -U, --user          Database user (default: postgres)
#   --notify-backend    After refresh, call backend Admin API to reset MV availability cache (best-effort)
#   --backend-url       Backend base URL for Admin API calls (default: http://localhost:8000)
#   --invalidate-cache  After refresh, also invalidate API cache namespaces via Admin API (best-effort)
#   --invalidate-namespaces  Comma-separated namespaces to invalidate (default: all allowed)
#
# Examples:
#   ./refresh_materialized_views.sh              # Concurrent refresh
#   ./refresh_materialized_views.sh -f           # Full blocking refresh
#   ./refresh_materialized_views.sh -s           # Status check only
#   ./refresh_materialized_views.sh -d mydb -U admin  # Custom database/user
#   ADMIN_API_KEY=... ./refresh_materialized_views.sh --notify-backend --invalidate-cache
#
# Cron example (weekly refresh at 3 AM on Sunday):
#   0 3 * * 0 /path/to/refresh_materialized_views.sh >> /var/log/mv_refresh.log 2>&1
# ============================================================================

set -euo pipefail

# Default configuration
DB_NAME="${PGDATABASE:-lncrna_production}"
DB_HOST="${PGHOST:-localhost}"
DB_PORT="${PGPORT:-5432}"
DB_USER="${PGUSER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-}"
USE_CONCURRENT=true
STATUS_ONLY=false
VERBOSE=false

# Optional: notify backend after refresh (best-effort; failures do not fail the MV refresh)
NOTIFY_BACKEND=false
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
INVALIDATE_CACHE=false
INVALIDATE_NAMESPACES_DEFAULT="regulations,genes,stats,export,conservation,chipseq,network,diseases,features,igv,analysis,visualization"
INVALIDATE_NAMESPACES="${INVALIDATE_NAMESPACES:-$INVALIDATE_NAMESPACES_DEFAULT}"
# curl timeouts (seconds)
CURL_CONNECT_TIMEOUT="${CURL_CONNECT_TIMEOUT:-5}"
CURL_MAX_TIME="${CURL_MAX_TIME:-10}"

# 若需要密码，请通过环境变量 DB_PASSWORD 或 ~/.pgpass/PGPASSWORD 提供；脚本使用 psql -w 避免非交互卡死。
if [ -n "$DB_PASSWORD" ]; then
    export PGPASSWORD="$DB_PASSWORD"
fi

# Materialized views managed by this script (order matters when dependencies exist).
MV_LIST=(
    # Analysis summary cache-miss acceleration (fast to refresh)
    "mv_analysis_high_affinity_stats_ba100"
    "mv_analysis_top_lncrnas_ba100"

    # ChIP-seq overlap optimization (base MV first, then dependent summary MV)
    "mv_lncrna_chipseq_overlaps"
    "mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    shift
    local message=$*
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    case $level in
        INFO)
            echo -e "${timestamp} [${BLUE}INFO${NC}] $message"
            ;;
        SUCCESS)
            echo -e "${timestamp} [${GREEN}SUCCESS${NC}] $message"
            ;;
        WARN)
            echo -e "${timestamp} [${YELLOW}WARN${NC}] $message"
            ;;
        ERROR)
            echo -e "${timestamp} [${RED}ERROR${NC}] $message" >&2
            ;;
        DEBUG)
            if [ "$VERBOSE" = true ]; then
                echo -e "${timestamp} [DEBUG] $message"
            fi
            ;;
    esac
}

# Show help
show_help() {
    # Print the initial comment block (after shebang) as help text.
    awk 'NR==1 {next} /^#/ {sub(/^# ?/, "", $0); print; next} {exit}' "$0"
}

require_arg_value() {
    local opt=$1
    local value=${2:-}

    if [[ -z "$value" || "$value" == -* ]]; then
        log ERROR "Option $opt requires a value"
        show_help
        exit 1
    fi
}

check_prereqs() {
    if ! command -v psql >/dev/null 2>&1; then
        log ERROR "psql not found. Please install the PostgreSQL client tools (psql)."
        exit 1
    fi
    if [ "$NOTIFY_BACKEND" = true ] || [ "$INVALIDATE_CACHE" = true ]; then
        if ! command -v curl >/dev/null 2>&1; then
            log ERROR "curl not found. Please install curl to use --notify-backend / --invalidate-cache."
            exit 1
        fi
    fi
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -c|--concurrent)
                USE_CONCURRENT=true
                shift
                ;;
            -f|--full)
                USE_CONCURRENT=false
                shift
                ;;
            -s|--status)
                STATUS_ONLY=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -d|--database)
                require_arg_value "$1" "${2:-}"
                DB_NAME="$2"
                shift 2
                ;;
            -H|--host)
                require_arg_value "$1" "${2:-}"
                DB_HOST="$2"
                shift 2
                ;;
            -p|--port)
                require_arg_value "$1" "${2:-}"
                DB_PORT="$2"
                shift 2
                ;;
            -U|--user)
                require_arg_value "$1" "${2:-}"
                DB_USER="$2"
                shift 2
                ;;
            --notify-backend)
                NOTIFY_BACKEND=true
                shift
                ;;
            --backend-url)
                require_arg_value "$1" "${2:-}"
                BACKEND_URL="$2"
                shift 2
                ;;
            --invalidate-cache)
                INVALIDATE_CACHE=true
                shift
                ;;
            --invalidate-namespaces)
                require_arg_value "$1" "${2:-}"
                INVALIDATE_NAMESPACES="$2"
                shift 2
                ;;
            *)
                log ERROR "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Execute SQL and return result
execute_sql() {
    local sql=$1
    psql -w -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -c "$sql" 2>/dev/null
}

# Execute SQL with full output
execute_sql_verbose() {
    local sql=$1
    psql -w -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "$sql"
}

normalize_backend_url() {
    local raw="$1"
    # Strip trailing slashes to avoid double "//" in endpoint joins
    echo "${raw%/}"
}

get_admin_api_key() {
    # SECURITY: Prefer env var to avoid leaking keys into shell history.
    # Supported variables:
    # - ADMIN_API_KEY (project standard)
    # - HLA_ADMIN_API_KEY (explicit, avoids clobbering other shells)
    if [ -n "${HLA_ADMIN_API_KEY:-}" ]; then
        echo "$HLA_ADMIN_API_KEY"
        return 0
    fi
    if [ -n "${ADMIN_API_KEY:-}" ]; then
        echo "$ADMIN_API_KEY"
        return 0
    fi
    echo ""
}

admin_post() {
    local endpoint="$1"
    local base
    base="$(normalize_backend_url "$BACKEND_URL")"
    local url="${base}${endpoint}"
    local key
    key="$(get_admin_api_key)"
    if [ -z "$key" ]; then
        log WARN "Admin API key not set (ADMIN_API_KEY/HLA_ADMIN_API_KEY). Skip backend notification: $endpoint"
        return 0
    fi

    log DEBUG "Calling Admin API: $url"
    if ! curl -sS --fail \
        --connect-timeout "$CURL_CONNECT_TIMEOUT" \
        --max-time "$CURL_MAX_TIME" \
        -X POST \
        -H "X-Admin-API-Key: $key" \
        -H "Content-Type: application/json" \
        "$url" >/dev/null; then
        log WARN "Admin API call failed (best-effort): $endpoint"
        return 0
    fi
    return 0
}

invalidate_cache_namespaces() {
    local csv="$1"
    # Empty list => nothing to do.
    if [ -z "${csv//[[:space:]]/}" ]; then
        return 0
    fi
    local base
    base="$(normalize_backend_url "$BACKEND_URL")"
    local key
    key="$(get_admin_api_key)"
    if [ -z "$key" ]; then
        log WARN "Admin API key not set (ADMIN_API_KEY/HLA_ADMIN_API_KEY). Skip cache invalidation"
        return 0
    fi

    local IFS=','
    # shellcheck disable=SC2206
    read -r -a namespaces <<<"$csv"
    for ns in "${namespaces[@]}"; do
        # Trim whitespace
        ns="$(echo "$ns" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
        if [ -z "$ns" ]; then
            continue
        fi
        local url="${base}/api/v1/admin/cache/invalidate/${ns}"
        log DEBUG "Invalidating cache namespace: $ns"
        if ! curl -sS --fail \
            --connect-timeout "$CURL_CONNECT_TIMEOUT" \
            --max-time "$CURL_MAX_TIME" \
            -X POST \
            -H "X-Admin-API-Key: $key" \
            "$url" >/dev/null; then
            log WARN "Cache invalidation failed (best-effort): namespace=$ns"
        fi
    done
    return 0
}

notify_backend_after_refresh() {
    if [ "$NOTIFY_BACKEND" != true ] && [ "$INVALIDATE_CACHE" != true ]; then
        return 0
    fi

    local base
    base="$(normalize_backend_url "$BACKEND_URL")"
    log INFO "Notifying backend (best-effort): $base"

    if [ "$NOTIFY_BACKEND" = true ]; then
        # Reset process-level MV availability caches in backend workers.
        admin_post "/api/v1/admin/mv-cache/reset"
    fi

    if [ "$INVALIDATE_CACHE" = true ]; then
        invalidate_cache_namespaces "$INVALIDATE_NAMESPACES"
    fi

    return 0
}

# Check if materialized view exists
check_mv_exists() {
    local mv_name=$1
    local result=$(execute_sql "SELECT EXISTS(SELECT 1 FROM pg_matviews WHERE matviewname = '$mv_name')")
    [ "$result" = "t" ]
}

# Check if materialized view is populated
check_mv_populated() {
    local mv_name=$1
    local result=$(execute_sql "SELECT relispopulated FROM pg_class WHERE relname = '$mv_name' AND relkind = 'm'")
    [ "$result" = "t" ]
}

# Get materialized view row count
get_mv_row_count() {
    local mv_name=$1
    execute_sql "SELECT COUNT(*) FROM $mv_name" 2>/dev/null || echo "0"
}

# Get materialized view size
get_mv_size() {
    local mv_name=$1
    execute_sql "SELECT pg_size_pretty(pg_total_relation_size('$mv_name'))" 2>/dev/null || echo "N/A"
}

# Show status of all materialized views
show_status() {
    log INFO "Checking materialized view status..."
    echo ""
    echo "=============================================="
    echo "Materialized View Status"
    echo "=============================================="
    echo ""

    for mv_name in "${MV_LIST[@]}"; do
        if check_mv_exists "$mv_name"; then
            local populated="No"
            if check_mv_populated "$mv_name"; then
                populated="Yes"
            fi

            local row_count=$(get_mv_row_count "$mv_name")
            local size=$(get_mv_size "$mv_name")

            echo "View: $mv_name"
            echo "  Exists: Yes"
            echo "  Populated: $populated"
            echo "  Row Count: $row_count"
            echo "  Total Size: $size"

            # Show distribution by chromosome for the base MV only.
            if [ "$mv_name" = "mv_lncrna_chipseq_overlaps" ] && [ "$populated" = "Yes" ] && [ "$VERBOSE" = true ]; then
                echo ""
                echo "Distribution by Chromosome (Top 5):"
                execute_sql_verbose "
                    SELECT
                        chromosome,
                        COUNT(*) as overlap_count,
                        ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 2) as percentage
                    FROM $mv_name
                    GROUP BY chromosome
                    ORDER BY overlap_count DESC
                    LIMIT 5;
                "
            fi
        else
            echo "View: $mv_name"
            echo "  Exists: No"
            echo "  Status: Not created yet"
            echo ""
            echo "To create the materialized view, run:"
            case "$mv_name" in
                mv_lncrna_chipseq_overlaps)
                    echo "  psql -d $DB_NAME -f schema/v2.3/05_mv_lncrna_chipseq_overlaps.sql"
                    ;;
                mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100)
                    echo "  psql -d $DB_NAME -f schema/v2.3/06_mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100.sql"
                    ;;
                mv_analysis_high_affinity_stats_ba100|mv_analysis_top_lncrnas_ba100)
                    echo "  psql -d $DB_NAME -f schema/v2.3/07_mv_analysis_summary_high_affinity_ba100.sql"
                    ;;
                *)
                    echo "  (unknown - please check schema scripts)"
                    ;;
            esac
        fi

        echo ""
    done

    echo "=============================================="
}

# Refresh a single materialized view
refresh_mv() {
    local mv_name=$1
    local start_time=$(date +%s)

    log INFO "Starting refresh of $mv_name..."

    if ! check_mv_exists "$mv_name"; then
        log ERROR "Materialized view $mv_name does not exist"
        return 1
    fi

    local rows_before=$(get_mv_row_count "$mv_name")
    log DEBUG "Rows before refresh: $rows_before"

    # Build refresh command
    local refresh_cmd="REFRESH MATERIALIZED VIEW"
    if [ "$USE_CONCURRENT" = true ]; then
        refresh_cmd="$refresh_cmd CONCURRENTLY"
        log INFO "Using CONCURRENTLY option (non-blocking)"
    else
        log INFO "Using full refresh (blocking)"
    fi
    refresh_cmd="$refresh_cmd $mv_name"

    # Execute refresh
    log DEBUG "Executing: $refresh_cmd"

    if execute_sql "$refresh_cmd"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        local rows_after=$(get_mv_row_count "$mv_name")

        log SUCCESS "Refresh completed in ${duration}s"
        log INFO "Rows: $rows_before -> $rows_after"

        # Run ANALYZE
        log DEBUG "Running ANALYZE..."
        execute_sql "ANALYZE $mv_name"

        return 0
    else
        log ERROR "Refresh failed for $mv_name"
        return 1
    fi
}

# Main function
main() {
    parse_args "$@"
    check_prereqs

    log INFO "Human LncRNA Atlas - Materialized View Manager"
    log DEBUG "Database: $DB_NAME @ $DB_HOST:$DB_PORT (user: $DB_USER)"

    # Test database connection
    if ! execute_sql "SELECT 1" > /dev/null 2>&1; then
        log ERROR "Cannot connect to database $DB_NAME at $DB_HOST:$DB_PORT"
        log ERROR "Please check your database credentials or set PGPASSWORD environment variable"
        exit 1
    fi
    log DEBUG "Database connection successful"

    if [ "$STATUS_ONLY" = true ]; then
        show_status
        exit 0
    fi

    # Refresh materialized views
    log INFO "Starting materialized view refresh..."

    local success=true

    for mv_name in "${MV_LIST[@]}"; do
        if ! refresh_mv "$mv_name"; then
            success=false
        fi
    done

    echo ""
    show_status

    if [ "$success" = true ]; then
        log SUCCESS "All materialized views refreshed successfully"
        notify_backend_after_refresh
        exit 0
    else
        log ERROR "Some materialized views failed to refresh"
        exit 1
    fi
}

# Run main function
main "$@"
