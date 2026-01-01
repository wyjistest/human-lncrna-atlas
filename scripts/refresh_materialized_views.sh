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
#
# Examples:
#   ./refresh_materialized_views.sh              # Concurrent refresh
#   ./refresh_materialized_views.sh -f           # Full blocking refresh
#   ./refresh_materialized_views.sh -s           # Status check only
#   ./refresh_materialized_views.sh -d mydb -U admin  # Custom database/user
#
# Cron example (weekly refresh at 3 AM on Sunday):
#   0 3 * * 0 /path/to/refresh_materialized_views.sh >> /var/log/mv_refresh.log 2>&1
# ============================================================================

set -e

# Default configuration
DB_NAME="${PGDATABASE:-lncrna_production}"
DB_HOST="${PGHOST:-localhost}"
DB_PORT="${PGPORT:-5432}"
DB_USER="${PGUSER:-postgres}"
USE_CONCURRENT=true
STATUS_ONLY=false
VERBOSE=false

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
    head -37 "$0" | tail -35 | sed 's/^# //' | sed 's/^#//'
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
                DB_NAME="$2"
                shift 2
                ;;
            -H|--host)
                DB_HOST="$2"
                shift 2
                ;;
            -p|--port)
                DB_PORT="$2"
                shift 2
                ;;
            -U|--user)
                DB_USER="$2"
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
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -c "$sql" 2>/dev/null
}

# Execute SQL with full output
execute_sql_verbose() {
    local sql=$1
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "$sql"
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
        exit 0
    else
        log ERROR "Some materialized views failed to refresh"
        exit 1
    fi
}

# Run main function
main "$@"
