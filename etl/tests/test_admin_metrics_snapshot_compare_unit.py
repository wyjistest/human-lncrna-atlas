import json
import subprocess
import sys
from pathlib import Path


def test_admin_metrics_snapshot_compare_generates_markdown_diff(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]

    old_metrics = {
        "request": {"total": 100, "last_minute": 10},
        "errors": {"total": 1, "rate": 1.0},
        "response_time": {"avg_ms": 20.0},
        "percentiles": {"p50_ms": 10.0, "p95_ms": 100.0, "p99_ms": 200.0},
        "cache_stats": {"hit_rate_pct": 80.0, "hits": 800, "misses": 200},
        "endpoints": [
            {
                "path": "/api/v1/genes",
                "requests": 50,
                "percentiles": {"p95_ms": 100.0, "p99_ms": 150.0},
                "db_percentiles": {"p95_ms": 20.0, "p99_ms": 40.0},
            },
            {
                "path": "/api/v1/regulations",
                "requests": 30,
                "percentiles": {"p95_ms": 50.0, "p99_ms": 70.0},
                "db_percentiles": {"p95_ms": 10.0, "p99_ms": 15.0},
            },
        ],
        "cache_breakdown": {
            "namespaces": {
                "top": [
                    {
                        "namespace": "aaa",
                        "requests": 3,
                        "hits": 2,
                        "misses": 1,
                        "hit_rate_pct": 66.67,
                        "compute_avg_ms": 0.5,
                        "compute_max_ms": 1.0,
                    },
                    {
                        "namespace": "genes:list",
                        "requests": 10,
                        "hits": 8,
                        "misses": 2,
                        "hit_rate_pct": 80.0,
                        "compute_avg_ms": 3.0,
                        "compute_max_ms": 8.0,
                    },
                ]
            },
            "keys": {
                "top": [
                    {
                        "key": "aaa-key",
                        "namespace": "aaa",
                        "requests": 3,
                        "hits": 2,
                        "misses": 1,
                        "hit_rate_pct": 66.67,
                        "compute_count": 1,
                        "compute_avg_ms": 1.0,
                        "compute_max_ms": 2.0,
                    },
                    {
                        "key": "genes:list:species_id=1:page=1",
                        "namespace": "genes:list",
                        "requests": 10,
                        "hits": 8,
                        "misses": 2,
                        "hit_rate_pct": 80.0,
                        "compute_count": 2,
                        "compute_avg_ms": 4.0,
                        "compute_max_ms": 9.0,
                    },
                ]
            },
            "routes": {
                "top": [
                    {
                        "route": "/api/v1/aaa",
                        "requests": 3,
                        "hits": 2,
                        "misses": 1,
                        "hit_rate_pct": 66.67,
                        "compute_count": 1,
                        "compute_avg_ms": 1.0,
                        "compute_max_ms": 2.0,
                    },
                    {
                        "route": "/api/v1/genes",
                        "requests": 10,
                        "hits": 8,
                        "misses": 2,
                        "hit_rate_pct": 80.0,
                        "compute_count": 2,
                        "compute_avg_ms": 4.0,
                        "compute_max_ms": 9.0,
                    },
                ]
            },
        },
        "cache_get_latency": {
            "hits_samples": 10,
            "misses_samples": 5,
            "hits": {"p95_ms": 1.0, "p99_ms": 2.0},
            "misses": {"p95_ms": 5.0, "p99_ms": 10.0},
        },
        "database": {
            "slow_queries": [
                {
                    "fingerprint": "fp-genes",
                    "route": "/api/v1/genes",
                    "statement": "select 1",
                    "count": 2,
                    "avg_ms": 10.0,
                    "max_ms": 20.0,
                    "total_time_ms": 20.0,
                }
            ]
        },
    }
    new_metrics = {
        "request": {"total": 120, "last_minute": 12},
        "errors": {"total": 0, "rate": 0.0},
        "response_time": {"avg_ms": 18.0},
        "percentiles": {"p50_ms": 9.0, "p95_ms": 90.0, "p99_ms": 210.0},
        "cache_stats": {"hit_rate_pct": 90.0, "hits": 900, "misses": 100},
        "endpoints": [
            {
                "path": "/api/v1/genes",
                "requests": 60,
                "percentiles": {"p95_ms": 80.0, "p99_ms": 140.0},
                "db_percentiles": {"p95_ms": 25.0, "p99_ms": 50.0},
            },
            {
                "path": "/api/v1/regulations",
                "requests": 40,
                "percentiles": {"p95_ms": 120.0, "p99_ms": 160.0},
                "db_percentiles": {"p95_ms": 12.0, "p99_ms": 18.0},
            },
        ],
        "cache_breakdown": {
            "namespaces": {
                "top": [
                    {
                        "namespace": "aaa",
                        "requests": 4,
                        "hits": 3,
                        "misses": 1,
                        "hit_rate_pct": 75.0,
                        "compute_avg_ms": 0.6,
                        "compute_max_ms": 1.2,
                    },
                    {
                        "namespace": "genes:list",
                        "requests": 12,
                        "hits": 10,
                        "misses": 2,
                        "hit_rate_pct": 83.33,
                        "compute_avg_ms": 4.5,
                        "compute_max_ms": 9.0,
                    },
                ]
            },
            "keys": {
                "top": [
                    {
                        "key": "aaa-key",
                        "namespace": "aaa",
                        "requests": 4,
                        "hits": 3,
                        "misses": 1,
                        "hit_rate_pct": 75.0,
                        "compute_count": 2,
                        "compute_avg_ms": 1.1,
                        "compute_max_ms": 2.2,
                    },
                    {
                        "key": "genes:list:species_id=1:page=1",
                        "namespace": "genes:list",
                        "requests": 12,
                        "hits": 10,
                        "misses": 2,
                        "hit_rate_pct": 83.33,
                        "compute_count": 4,
                        "compute_avg_ms": 6.0,
                        "compute_max_ms": 12.0,
                    },
                ]
            },
            "routes": {
                "top": [
                    {
                        "route": "/api/v1/aaa",
                        "requests": 4,
                        "hits": 3,
                        "misses": 1,
                        "hit_rate_pct": 75.0,
                        "compute_count": 2,
                        "compute_avg_ms": 1.1,
                        "compute_max_ms": 2.2,
                    },
                    {
                        "route": "/api/v1/genes",
                        "requests": 12,
                        "hits": 10,
                        "misses": 2,
                        "hit_rate_pct": 83.33,
                        "compute_count": 4,
                        "compute_avg_ms": 6.0,
                        "compute_max_ms": 12.0,
                    },
                ]
            },
        },
        "cache_get_latency": {
            "hits_samples": 12,
            "misses_samples": 6,
            "hits": {"p95_ms": 1.5, "p99_ms": 2.5},
            "misses": {"p95_ms": 6.0, "p99_ms": 12.0},
        },
        "database": {
            "slow_queries": [
                {
                    "fingerprint": "fp-genes",
                    "route": "/api/v1/genes",
                    "statement": "select 1",
                    "count": 4,
                    "avg_ms": 12.0,
                    "max_ms": 30.0,
                    "total_time_ms": 48.0,
                }
            ]
        },
    }

    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text(json.dumps(old_metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    new_path.write_text(json.dumps(new_metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts/admin_metrics_snapshot.py"),
            "--compare",
            str(old_path),
            str(new_path),
            "--out-dir",
            str(tmp_path),
            "--prefix",
            "admin-metrics-diff-test",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr

    md_files = sorted(tmp_path.glob("admin-metrics-diff-test-*.md"))
    assert md_files, "expected diff Markdown output file"

    md = md_files[0].read_text(encoding="utf-8")
    assert "Snapshot Diff" in md
    assert "`/api/v1/regulations`" in md
    assert "50.00ms" in md and "120.00ms" in md
    assert "hit rate" in md
    assert "80.00%" in md and "90.00%" in md
    assert "Cache get() 延迟（变化）" in md
    assert "1.00ms" in md and "1.50ms" in md
    assert "Cache routes（Compute 变化）" in md
    assert "`/api/v1/genes`" in md
    assert "4.00ms" in md and "6.00ms" in md
    assert md.index("- `/api/v1/genes`") < md.index("- `/api/v1/aaa`")
    assert "Cache keys（变化）" in md
    assert "`genes:list:species_id=1:page=1`" in md
    assert md.index("- `genes:list:species_id=1:page=1`") < md.index("- `aaa-key`")
    assert "Cache namespaces（变化）" in md
    assert md.index("- `genes:list`") < md.index("- `aaa`")
    assert "Top endpoint changes by Response P99" in md
    assert "150.00ms" in md and "140.00ms" in md
    assert "Top endpoint changes by DB P99" in md
    assert "40.00ms" in md and "15.00ms" in md
    assert "`fp-genes`" in md
