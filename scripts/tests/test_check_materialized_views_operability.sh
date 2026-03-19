#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

tmp_root="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_root"
}
trap cleanup EXIT

cat > "$tmp_root/healthy.json" <<'EOF'
{
  "status": "success",
  "supported": true,
  "attention_summary": {
    "status": "healthy",
    "severity": "info",
    "message": "All materialized views are healthy.",
    "recommended_action": null,
    "attention_count": 0,
    "total_count": 4,
    "attention_view_names": []
  }
}
EOF

cat > "$tmp_root/warning.json" <<'EOF'
{
  "status": "success",
  "supported": true,
  "attention_summary": {
    "status": "degraded",
    "severity": "warning",
    "message": "1/4 materialized view(s) need attention.",
    "recommended_action": "Run ANALYZE for top-lncRNA stats.",
    "attention_count": 1,
    "total_count": 4,
    "attention_view_names": ["mv_analysis_top_lncrnas_ba100"]
  }
}
EOF

cat > "$tmp_root/critical.json" <<'EOF'
{
  "status": "success",
  "supported": true,
  "attention_summary": {
    "status": "critical",
    "severity": "critical",
    "message": "1 critical materialized view issue detected.",
    "recommended_action": "Recreate overlap MV before serving compare traffic.",
    "attention_count": 1,
    "total_count": 4,
    "attention_view_names": ["mv_lncrna_chipseq_overlaps"]
  }
}
EOF

cat > "$tmp_root/unsupported.json" <<'EOF'
{
  "status": "unsupported",
  "supported": false,
  "attention_summary": {
    "status": "degraded",
    "severity": "warning",
    "message": "Materialized view operations are unavailable on sqlite.",
    "recommended_action": "Switch the admin backend to PostgreSQL to refresh or inspect materialized views.",
    "attention_count": 4,
    "total_count": 4,
    "attention_view_names": [
      "mv_analysis_high_affinity_stats_ba100",
      "mv_analysis_top_lncrnas_ba100",
      "mv_lncrna_chipseq_overlaps",
      "mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100"
    ]
  }
}
EOF

run_and_expect() {
  local expected_status="$1"
  local json_path="$2"

  set +e
  output="$(python3 "$REPO_ROOT/scripts/check_materialized_views_operability.py" --status-json "$json_path" 2>&1)"
  status=$?
  set -e

  if [ "$status" -ne "$expected_status" ]; then
    echo "expected exit code $expected_status for $json_path, got $status" >&2
    echo "$output" >&2
    exit 1
  fi
}

run_and_expect 0 "$tmp_root/healthy.json"
run_and_expect 1 "$tmp_root/warning.json"
run_and_expect 2 "$tmp_root/critical.json"
run_and_expect 1 "$tmp_root/unsupported.json"

echo "OK: materialized view operability CLI maps summary severity to exit codes"
