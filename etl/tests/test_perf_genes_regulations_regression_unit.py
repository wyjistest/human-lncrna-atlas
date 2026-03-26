import json
import os
import subprocess
import sys
import threading
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


def _start_mock_server(state: dict[str, Any]) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)

            if parsed.path == "/api/v1/genes":
                hit_counts = state.setdefault("request_hits", {})
                if isinstance(hit_counts, dict):
                    hit_counts["/api/v1/genes"] = int(hit_counts.get("/api/v1/genes", 0)) + 1
                qs = parse_qs(parsed.query)
                if "page" not in qs or "page_size" not in qs:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"missing paging\n")
                    return
                status_seq_by_path = state.get("status_sequence_by_path")
                if isinstance(status_seq_by_path, dict):
                    seq = status_seq_by_path.get("/api/v1/genes")
                    if isinstance(seq, list) and seq:
                        code = seq.pop(0)
                        if isinstance(code, int) and code != 200:
                            self.send_response(code)
                            self.end_headers()
                            self.wfile.write(b"forced status (sequence)\n")
                            return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}\n')
                return

            if parsed.path == "/api/v1/regulations":
                hit_counts = state.setdefault("request_hits", {})
                if isinstance(hit_counts, dict):
                    hit_counts["/api/v1/regulations"] = int(hit_counts.get("/api/v1/regulations", 0)) + 1
                qs = parse_qs(parsed.query)
                if "page" not in qs or "page_size" not in qs:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"missing paging\n")
                    return
                status_seq_by_path = state.get("status_sequence_by_path")
                if isinstance(status_seq_by_path, dict):
                    seq = status_seq_by_path.get("/api/v1/regulations")
                    if isinstance(seq, list) and seq:
                        code = seq.pop(0)
                        if isinstance(code, int) and code != 200:
                            self.send_response(code)
                            self.end_headers()
                            self.wfile.write(b"forced status (sequence)\n")
                            return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}\n')
                return

            if parsed.path == "/api/v1/admin/metrics":
                metrics_from_hits = state.get("metrics_from_hits")
                if metrics_from_hits:
                    payload = _base_metrics_payload(
                        response_p95=1000.0,
                        response_p99=1200.0,
                        db_p95=200.0,
                        db_p99=250.0,
                    )
                    hit_counts = state.get("request_hits")
                    if isinstance(hit_counts, dict):
                        for endpoint in payload["endpoints"]:
                            path = endpoint["path"]
                            endpoint["requests"] = int(hit_counts.get(path, 0))
                else:
                    payload = state.get("metrics_payload")
                if not isinstance(payload, dict):
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b"missing metrics_payload\n")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write((json.dumps(payload) + "\n").encode("utf-8"))
                return

            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found\n")

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _run_script(repo_root: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/perf_genes_regulations_regression.py", *args],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _base_metrics_payload(*, response_p95: float, response_p99: float, db_p95: float, db_p99: float) -> dict[str, Any]:
    return {
        "request": {"total": 100},
        "errors": {"total": 0},
        "endpoints": [
            {
                "path": "/api/v1/genes",
                "requests": 60,
                "percentiles": {"p95_ms": response_p95, "p99_ms": response_p99},
                "db_percentiles": {"p95_ms": db_p95, "p99_ms": db_p99},
            },
            {
                "path": "/api/v1/regulations",
                "requests": 60,
                "percentiles": {"p95_ms": response_p95, "p99_ms": response_p99},
                "db_percentiles": {"p95_ms": db_p95, "p99_ms": db_p99},
            },
        ],
    }


def _latest_report_paths(out_dir: Path) -> tuple[Path, Path]:
    markdown_reports = sorted(out_dir.glob("perf-genes-regulations-*.md"))
    json_reports = sorted(
        path
        for path in out_dir.glob("perf-genes-regulations-*.json")
        if "raw-metrics" not in path.name
    )
    assert markdown_reports, "missing markdown reports"
    assert json_reports, "missing compact json reports"
    return markdown_reports[-1], json_reports[-1]


def _load_perf_module():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "perf_genes_regulations_regression.py"
    spec = importlib.util.spec_from_file_location("perf_genes_regulations_regression", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_perf_genes_regulations_generate_baseline_and_check_passes(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]

    state: dict[str, Any] = {
        "metrics_payload": _base_metrics_payload(response_p95=1000.0, response_p99=1200.0, db_p95=200.0, db_p99=250.0),
    }
    server = _start_mock_server(state)
    try:
        port = server.server_address[1]
        base_url = f"http://127.0.0.1:{port}"

        env = os.environ.copy()

        # Simulate global proxy enabled but no explicit bypass configured.
        env["http_proxy"] = "http://127.0.0.1:1"
        env["https_proxy"] = "http://127.0.0.1:1"
        env.pop("NO_PROXY", None)
        env.pop("no_proxy", None)

        baseline_file = tmp_path / "baseline.json"
        out_dir = tmp_path / "out"

        gen = _run_script(
            repo_root,
            env,
            "generate-baseline",
            "--base-url",
            base_url,
            "--baseline-file",
            str(baseline_file),
            "--out-dir",
            str(out_dir),
            "--warmup-rounds",
            "2",
            "--timeout-seconds",
            "1",
        )
        output = f"{gen.stdout}\n{gen.stderr}"
        assert gen.returncode == 0, f"generate-baseline failed:\n{output}"
        assert baseline_file.exists(), f"baseline file not created. Output:\n{output}"
        assert list(out_dir.glob("perf-genes-regulations-*.md")), f"missing markdown report. Output:\n{output}"

        chk = _run_script(
            repo_root,
            env,
            "check",
            "--base-url",
            base_url,
            "--baseline-file",
            str(baseline_file),
            "--out-dir",
            str(out_dir),
            "--warmup-rounds",
            "2",
            "--timeout-seconds",
            "1",
        )
        output = f"{chk.stdout}\n{chk.stderr}"
        assert chk.returncode == 0, f"check should pass:\n{output}"
    finally:
        server.shutdown()


def test_perf_genes_regulations_check_fails_on_large_regression(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]

    state: dict[str, Any] = {
        "metrics_payload": _base_metrics_payload(response_p95=1000.0, response_p99=1200.0, db_p95=200.0, db_p99=250.0),
    }
    server = _start_mock_server(state)
    try:
        port = server.server_address[1]
        base_url = f"http://127.0.0.1:{port}"

        env = os.environ.copy()
        env.pop("NO_PROXY", None)
        env.pop("no_proxy", None)

        baseline_file = tmp_path / "baseline.json"
        out_dir = tmp_path / "out"

        gen = _run_script(
            repo_root,
            env,
            "generate-baseline",
            "--base-url",
            base_url,
            "--baseline-file",
            str(baseline_file),
            "--out-dir",
            str(out_dir),
            "--warmup-rounds",
            "1",
            "--timeout-seconds",
            "1",
        )
        output = f"{gen.stdout}\n{gen.stderr}"
        assert gen.returncode == 0, f"generate-baseline failed:\n{output}"

        # Simulate a clear regression that exceeds both pct and abs thresholds.
        state["metrics_payload"] = _base_metrics_payload(response_p95=2000.0, response_p99=2400.0, db_p95=500.0, db_p99=650.0)

        chk = _run_script(
            repo_root,
            env,
            "check",
            "--base-url",
            base_url,
            "--baseline-file",
            str(baseline_file),
            "--out-dir",
            str(out_dir),
            "--warmup-rounds",
            "1",
            "--timeout-seconds",
            "1",
        )
        output = f"{chk.stdout}\n{chk.stderr}"
        assert chk.returncode != 0, f"check should fail on regression:\n{output}"
        assert "REGRESSION" in output
    finally:
        server.shutdown()


def test_perf_genes_regulations_warmup_retries_on_503_then_succeeds(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]

    state: dict[str, Any] = {
        "metrics_payload": _base_metrics_payload(response_p95=1000.0, response_p99=1200.0, db_p95=200.0, db_p99=250.0),
        "status_sequence_by_path": {"/api/v1/genes": [503, 200]},
    }
    server = _start_mock_server(state)
    try:
        port = server.server_address[1]
        base_url = f"http://127.0.0.1:{port}"

        env = os.environ.copy()
        env.pop("NO_PROXY", None)
        env.pop("no_proxy", None)

        baseline_file = tmp_path / "baseline.json"
        out_dir = tmp_path / "out"

        gen = _run_script(
            repo_root,
            env,
            "generate-baseline",
            "--base-url",
            base_url,
            "--baseline-file",
            str(baseline_file),
            "--out-dir",
            str(out_dir),
            "--warmup-rounds",
            "1",
            "--warmup-max-retries",
            "1",
            "--warmup-retry-base-sleep-ms",
            "0",
            "--timeout-seconds",
            "1",
        )
        output = f"{gen.stdout}\n{gen.stderr}"
        assert gen.returncode == 0, f"generate-baseline should succeed after retrying warmup:\n{output}"
    finally:
        server.shutdown()


def test_perf_genes_regulations_backfills_samples_to_minimum() -> None:
    perf = _load_perf_module()

    seeded_metrics = _base_metrics_payload(response_p95=1000.0, response_p99=1200.0, db_p95=200.0, db_p99=250.0)
    seeded_metrics["endpoints"][0]["requests"] = 2
    seeded_metrics["endpoints"][1]["requests"] = 1

    filled_metrics = _base_metrics_payload(response_p95=1000.0, response_p99=1200.0, db_p95=200.0, db_p99=250.0)
    filled_metrics["endpoints"][0]["requests"] = 3
    filled_metrics["endpoints"][1]["requests"] = 3

    metrics_sequence = [filled_metrics]
    warmup_urls: list[str] = []

    def fetch_metrics() -> dict[str, Any]:
        assert metrics_sequence, "metrics sequence exhausted"
        return metrics_sequence.pop(0)

    diagnostics = perf._empty_run_diagnostics()
    result_metrics = perf._backfill_min_samples(
        raw_metrics=seeded_metrics,
        base_url="http://example.test",
        genes_species_id=1,
        genes_gene_type="lncRNA",
        genes_page_size=100,
        regulations_species_id=1,
        regulations_page_size=100,
        min_samples=3,
        warmup_max_retries=2,
        warmup_retry_base_sleep_ms=0,
        timeout_seconds=1.0,
        diagnostics=diagnostics,
        fetch_metrics=fetch_metrics,
        warmup_get=lambda url, **_: warmup_urls.append(url),
    )

    assert result_metrics["endpoints"][0]["requests"] == 3
    assert result_metrics["endpoints"][1]["requests"] == 3
    assert diagnostics["sample_fill_rounds"] == 1
    assert diagnostics["sample_fill_requests"]["/api/v1/genes"] == 1
    assert diagnostics["sample_fill_requests"]["/api/v1/regulations"] == 2
    assert len(warmup_urls) == 3


def test_perf_genes_regulations_build_markdown_includes_response_only_triage_hint() -> None:
    perf = _load_perf_module()

    baseline = perf._build_compact_snapshot(
        raw_metrics=_base_metrics_payload(response_p95=1000.0, response_p99=1200.0, db_p95=200.0, db_p99=250.0),
        base_url="http://example.test",
        mode="generate-baseline",
        baseline_file=Path("docs/baselines/performance/test.json"),
        baseline_raw_metrics_file=None,
        admin_metrics_reset=None,
        genes_species_id=1,
        genes_gene_type="lncRNA",
        genes_page_size=100,
        regulations_species_id=1,
        regulations_page_size=100,
        pre_warmup_rounds=0,
        warmup_rounds=1,
        warmup_max_retries=2,
        warmup_retry_base_sleep_ms=200,
        min_samples=1,
        response_regression_pct=4.0,
        response_regression_abs_ms=2.0,
        db_regression_pct=4.0,
        db_regression_abs_ms=1.0,
        generated_at="2026-03-26T00-00-00Z",
        diagnostics=perf._empty_run_diagnostics(),
    )
    current_diagnostics = perf._empty_run_diagnostics()
    current_diagnostics["response_only_regressions"] = [perf.GENES_LIST_PATH, perf.REGULATIONS_LIST_PATH]
    current = perf._build_compact_snapshot(
        raw_metrics=_base_metrics_payload(response_p95=1200.0, response_p99=1400.0, db_p95=200.0, db_p99=250.0),
        base_url="http://example.test",
        mode="check",
        baseline_file=Path("docs/baselines/performance/test.json"),
        baseline_raw_metrics_file=None,
        admin_metrics_reset=None,
        genes_species_id=1,
        genes_gene_type="lncRNA",
        genes_page_size=100,
        regulations_species_id=1,
        regulations_page_size=100,
        pre_warmup_rounds=0,
        warmup_rounds=1,
        warmup_max_retries=2,
        warmup_retry_base_sleep_ms=200,
        min_samples=1,
        response_regression_pct=4.0,
        response_regression_abs_ms=2.0,
        db_regression_pct=4.0,
        db_regression_abs_ms=1.0,
        generated_at="2026-03-26T00-00-01Z",
        diagnostics=current_diagnostics,
    )

    ok, failures = perf._gate_regressions(
        baseline,
        current,
        response_pct_th=4.0,
        response_abs_th=2.0,
        db_pct_th=4.0,
        db_abs_th=1.0,
    )
    assert not ok

    markdown = perf._build_markdown(
        mode="check",
        base_url="http://example.test",
        generated_at="2026-03-26T00-00-01Z",
        baseline_file=Path("docs/baselines/performance/test.json"),
        baseline=baseline,
        current=current,
        ok=ok,
        failures=failures,
        admin_metrics_diff_path=None,
        min_samples=1,
        response_regression_pct=4.0,
        response_regression_abs_ms=2.0,
        db_regression_pct=4.0,
        db_regression_abs_ms=1.0,
    )

    assert "response regressed but db metrics stayed flat" in markdown
