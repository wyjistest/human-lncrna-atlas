import json
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse


@contextmanager
def _mock_api_server() -> Iterator[str]:
    responses = {
        "/health": {"status": "ok"},
        "/api/v1/stats/overview": {"ok": True, "version": 1},
        "/api/v1/genes": {"total": 5, "items": [{"id": 1, "symbol": "GENE1"}]},
        "/api/v1/genes/options": {"genes": [{"gene_id": 1, "gene_name": "GENE1"}]},
        "/api/v1/genes/1": {"gene_id": 1, "gene_name": "GENE1", "orthologs": []},
        "/api/v1/regulations": {"total": 6, "items": [{"id": 1, "lncrna": "LNC1"}]},
        "/api/v1/regulations/1": {"regulation_id": 1, "lncrna_gene_id": 1, "target_gene_id": 2},
        "/api/v1/diseases/options": {"traits": ["T1", "T2", "T3", "T4", "T5"]},
        "/api/v1/stats/top-genes": [{"gene_id": 1, "regulation_count": 10}],
        "/api/v1/stats/top-diseases": [{"trait_id": 1, "gene_count": 10}],
        "/api/v1/analysis/summary": {"high_affinity": {"total_regulations": 1}},
        "/api/v1/features/chipseq/marks": [
            {
                "mark_type_id": 1,
                "mark_name": "H3K4me3",
                "mark_category": "activating",
                "display_name": "H3K4me3",
                "display_color": "#ff0000",
                "description": "mock mark",
                "biological_function": "mock",
                "associated_state": "active",
                "typical_signal_range": {"min": 0, "max": 10},
                "is_active": True,
                "sort_order": 10,
            }
        ],
        "/api/v1/features/chipseq/marks/relationships": [
            {
                "relationship_id": 1,
                "mark_1": "H3K4me3",
                "mark_2": "H3K27me3",
                "relationship_type": "bivalent_pair",
                "description": "mock relationship",
                "biological_significance": "mock",
            }
        ],
        "/api/v1/features/chipseq/marks/1": {
            "species_id": 1,
            "species_code": "human",
            "marks": [
                {
                    "mark_type_id": 1,
                    "mark_name": "H3K4me3",
                    "mark_category": "activating",
                    "display_name": "H3K4me3",
                    "display_color": "#ff0000",
                    "description": "mock mark",
                    "biological_function": "mock",
                    "associated_state": "active",
                    "typical_signal_range": {"min": 0, "max": 10},
                    "is_active": True,
                    "sort_order": 10,
                }
            ],
            "total_experiments": 1,
            "total_peaks": 1,
        },
        "/api/v1/features/chipseq/stats": {
            "total_experiments": 1,
            "total_peaks": 1,
            "marks_available": ["H3K4me3"],
            "species_available": ["human"],
            "stats_by_mark": [
                {
                    "species_code": "human",
                    "mark_name": "H3K4me3",
                    "mark_category": "activating",
                    "display_color": "#ff0000",
                    "experiment_count": 1,
                    "total_peaks": 1,
                    "avg_fold_enrichment": 1.0,
                    "median_fold_enrichment": 1.0,
                    "avg_peak_width": 200.0,
                }
            ],
        },
        "/api/v1/features/chipseq/experiments": {
            "total": 1,
            "page": 1,
            "page_size": 1,
            "items": [
                {
                    "experiment_id": 1,
                    "experiment_name": "mock exp",
                    "species_id": 1,
                    "species_code": "human",
                    "mark_type": "H3K4me3",
                    "mark_category": "activating",
                    "mark_display_color": "#ff0000",
                    "cell_type": "K562",
                    "tissue_type": "blood",
                    "cell_line": None,
                    "treatment": None,
                    "source_database": "mock",
                    "source_accession": "MOCK0001",
                    "peak_caller": "MACS2",
                    "reference_genome": "GRCh38",
                    "total_reads": None,
                    "mapped_reads": None,
                    "frip_score": None,
                    "is_active": True,
                    "created_at": "1970-01-01T00:00:00Z",
                    "peak_count": 1,
                }
            ],
        },
        "/api/v1/features/chipseq/regions/1": {
            "total": 1,
            "page": 1,
            "page_size": 1,
            "items": [
                {
                    "peak_id": 1,
                    "experiment_id": 1,
                    "mark_type": "H3K4me3",
                    "mark_category": "activating",
                    "chromosome": "chr22",
                    "peak_start": 100050,
                    "peak_end": 100150,
                    "summit_position": None,
                    "peak_name": "mock peak",
                    "strand": ".",
                    "fold_enrichment": 10.0,
                    "log2_fold_enrichment": None,
                    "pvalue": None,
                    "neg_log10_pvalue": None,
                    "qvalue": 0.05,
                    "neg_log10_qvalue": None,
                    "signal_value": None,
                    "score": None,
                    "peak_width": 100,
                }
            ],
        },
        "/api/v1/igv/chipseq/marks/1": {
            "success": True,
            "data": {
                "species_id": 1,
                "species_name": "Human",
                "marks": [],
                "chipseq_schema_ready": True,
            },
            "message": "mock",
        },
        "/api/v1/lncrna-chipseq-overlap": {
            "total": 0,
            "page": 1,
            "page_size": 1,
            "total_pages": 0,
            "items": [],
            "default_filter_applied": False,
            "effective_chromosome": "chr22",
            "using_materialized_view": False,
        },
        "/api/v1/lncrna-chipseq-overlap/cursor": {
            "total": 0,
            "page_size": 1,
            "items": [],
            "next_cursor": None,
            "has_more": False,
            "default_filter_applied": False,
            "effective_chromosome": "chr22",
            "using_materialized_view": False,
        },
        "/api/v1/lncrna-chipseq-overlap/statistics": {
            "total_overlaps": 0,
            "unique_lncrnas": 0,
            "unique_target_genes": 0,
            "unique_marks": 0,
            "unique_cell_types": 0,
            "avg_overlap_length": 0.0,
            "avg_binding_affinity": 0.0,
            "avg_peak_strength": 0.0,
            "by_mark_type": [],
            "by_cell_type": [],
            "default_filter_applied": False,
            "effective_chromosome": "chr22",
        },
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler naming)
            path = urlparse(self.path).path
            payload = responses.get(path)
            if payload is None:
                self.send_response(404)
                self.end_headers()
                return

            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)


def test_api_snapshot_check_baseline_matches(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    baseline = tmp_path / "api-snapshot.baseline.json"

    with _mock_api_server() as base_url:
        gen = _run(
            [
                sys.executable,
                str(repo_root / "scripts/api_snapshot.py"),
                "--base-url",
                base_url,
                "--deterministic",
                "--no-json",
                "--output",
                str(baseline),
            ],
            cwd=repo_root,
        )
        assert gen.returncode == 0, gen.stderr
        generated = json.loads(baseline.read_text(encoding="utf-8"))
        summaries = generated.get("summaries") or {}

        # 回归锚点：overlap 端点应输出可 diff 的统计摘要（即使为 0 也应存在 key）。
        assert summaries.get("overlap_total") == 0
        assert summaries.get("overlap_items_len") == 0
        assert summaries.get("overlap_cursor_total") == 0
        assert summaries.get("overlap_cursor_items_len") == 0
        assert summaries.get("overlap_stats_total_overlaps") == 0

        expected_keys = {
            "health",
            "stats_overview",
            "genes_page_1",
            "genes_options_species_1_limit_5",
            "genes_detail_first",
            "regulations_page_1",
            "regulation_detail_first",
            "diseases_options",
            "stats_top_genes_lncrna_limit_3",
            "stats_top_diseases_limit_3",
            "analysis_summary",
            "chipseq_marks",
            "chipseq_mark_relationships",
            "chipseq_available_marks_species_1",
            "chipseq_global_stats",
            "chipseq_experiments_page_1_species_1_page_size_1",
            "chipseq_regions_species_1_chr22_100000_100200_page_size_1",
            "igv_chipseq_marks_species_1",
            "lncrna_chipseq_overlap_page_chr22_page_size_1_sort_peak_qvalue_asc",
            "lncrna_chipseq_overlap_cursor_chr22_page_size_1_sort_peak_qvalue_asc",
            "lncrna_chipseq_overlap_statistics_chr22",
        }
        assert expected_keys.issubset(set(generated["endpoints"].keys()))

        check = _run(
            [
                sys.executable,
                str(repo_root / "scripts/api_snapshot.py"),
                "--base-url",
                base_url,
                "--check-baseline",
                str(baseline),
            ],
            cwd=repo_root,
        )
        assert check.returncode == 0, check.stderr


def test_api_snapshot_check_baseline_detects_mismatch(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    baseline = tmp_path / "api-snapshot.baseline.json"

    with _mock_api_server() as base_url:
        gen = _run(
            [
                sys.executable,
                str(repo_root / "scripts/api_snapshot.py"),
                "--base-url",
                base_url,
                "--deterministic",
                "--no-json",
                "--output",
                str(baseline),
            ],
            cwd=repo_root,
        )
        assert gen.returncode == 0, gen.stderr

        obj = json.loads(baseline.read_text(encoding="utf-8"))
        obj["summaries"]["genes_total"] = 999
        baseline.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        check = _run(
            [
                sys.executable,
                str(repo_root / "scripts/api_snapshot.py"),
                "--base-url",
                base_url,
                "--check-baseline",
                str(baseline),
            ],
            cwd=repo_root,
        )
        assert check.returncode == 3


def test_verify_baselines_api_snapshot_running_mode(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    baseline = tmp_path / "api-snapshot.baseline.json"

    with _mock_api_server() as base_url:
        gen = _run(
            [
                sys.executable,
                str(repo_root / "scripts/api_snapshot.py"),
                "--base-url",
                base_url,
                "--deterministic",
                "--no-json",
                "--output",
                str(baseline),
            ],
            cwd=repo_root,
        )
        assert gen.returncode == 0, gen.stderr

        verify = _run(
            [
                sys.executable,
                str(repo_root / "scripts/verify_baselines.py"),
                "--mode",
                "running",
                "--base-url",
                base_url,
                "--baseline-file",
                str(baseline),
            ],
            cwd=repo_root,
        )
        assert verify.returncode == 0, verify.stderr
