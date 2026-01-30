import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


def _start_mock_server(state: dict[str, Any]) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)

            if parsed.path == "/api/v1/genes/options":
                payload = state.get("genes_options_payload")
                if not isinstance(payload, dict):
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b"missing genes_options_payload\n")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write((json.dumps(payload) + "\n").encode("utf-8"))
                return

            if parsed.path.startswith("/api/v1/genes/"):
                gene_id_s = parsed.path.rsplit("/", 1)[-1]
                try:
                    gene_id = int(gene_id_s)
                except Exception:
                    gene_id = -1
                details = state.get("gene_detail_by_id")
                if not isinstance(details, dict):
                    details = {}
                payload = details.get(gene_id)
                if not isinstance(payload, dict):
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"gene not found\n")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write((json.dumps(payload) + "\n").encode("utf-8"))
                return

            if parsed.path == "/api/v1/lncrna-chipseq-overlap":
                qs = parse_qs(parsed.query)
                if "lncrna_gene_id" not in qs or "species_id" not in qs:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"missing query\n")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}\n')
                return

            if parsed.path == "/api/v1/lncrna-chipseq-overlap/compare":
                qs = parse_qs(parsed.query)
                if "lncrna_gene_id" not in qs or "species_ids" not in qs:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"missing query\n")
                    return
                lncrna_gene_id = int((qs.get("lncrna_gene_id") or ["0"])[0])
                status_by_gene = state.get("compare_status_by_gene_id")
                if isinstance(status_by_gene, dict):
                    code = status_by_gene.get(lncrna_gene_id)
                    if isinstance(code, int) and code != 200:
                        self.send_response(code)
                        self.end_headers()
                        self.wfile.write(b"forced status\n")
                        return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}\n')
                return

            if parsed.path == "/api/v1/admin/metrics":
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

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _run_script(repo_root: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/perf_overlap_regression.py", *args],
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
                "path": "/api/v1/lncrna-chipseq-overlap",
                "requests": 20,
                "percentiles": {"p95_ms": response_p95, "p99_ms": response_p99},
                "db_percentiles": {"p95_ms": db_p95, "p99_ms": db_p99},
            },
            {
                "path": "/api/v1/lncrna-chipseq-overlap/compare",
                "requests": 20,
                "percentiles": {"p95_ms": response_p95, "p99_ms": response_p99},
                "db_percentiles": {"p95_ms": db_p95, "p99_ms": db_p99},
            },
        ],
    }


def test_perf_overlap_generate_baseline_and_check_passes(tmp_path: Path) -> None:
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
        assert list(out_dir.glob("perf-overlap-*.md")), f"missing markdown report. Output:\n{output}"

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


def test_perf_overlap_check_fails_on_large_regression(tmp_path: Path) -> None:
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

        # Simulate a large regression:
        # - Response P95 +1000ms (100%) => should fail (>% +>ms)
        # - DB P95 +500ms (250%) => should fail (>% +>ms)
        state["metrics_payload"] = _base_metrics_payload(response_p95=2000.0, response_p99=2400.0, db_p95=700.0, db_p99=900.0)

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
        assert "REGRESSION" in output or "regression" in output, f"missing regression hint:\n{output}"
    finally:
        server.shutdown()


def test_perf_overlap_falls_back_to_auto_gene_id_when_default_compare_404(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]

    state: dict[str, Any] = {
        "metrics_payload": _base_metrics_payload(response_p95=1000.0, response_p99=1200.0, db_p95=200.0, db_p99=250.0),
        "genes_options_payload": {
            "genes": [
                {"gene_id": 101},
                {"gene_id": 102},
            ]
        },
        "gene_detail_by_id": {
            # 101 intentionally lacks core_id to simulate an invalid candidate.
            101: {"gene_id": 101, "core_id": None},
            102: {"gene_id": 102, "core_id": 999},
        },
        # Default gene id used by the perf script should fail compare warmup (sample DB may not contain it).
        "compare_status_by_gene_id": {17276: 404},
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
        assert gen.returncode == 0, f"generate-baseline should auto-pick a valid gene_id:\n{output}"

        baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
        scenario = baseline.get("meta", {}).get("scenario", {})
        assert scenario.get("lncrna_gene_id") == 102, f"expected auto gene_id=102, got:\n{json.dumps(scenario, indent=2)}"
    finally:
        server.shutdown()


def test_perf_overlap_auto_gene_pick_is_deterministic_by_smallest_gene_id(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]

    state: dict[str, Any] = {
        "metrics_payload": _base_metrics_payload(response_p95=1000.0, response_p99=1200.0, db_p95=200.0, db_p99=250.0),
        "genes_options_payload": {
            "genes": [
                {"gene_id": 200},
                {"gene_id": 100},
            ]
        },
        "gene_detail_by_id": {
            100: {"gene_id": 100, "core_id": 999},
            200: {"gene_id": 200, "core_id": 888},
        },
        "compare_status_by_gene_id": {17276: 404},
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
        assert gen.returncode == 0, f"generate-baseline should succeed:\n{output}"

        baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
        scenario = baseline.get("meta", {}).get("scenario", {})
        assert scenario.get("lncrna_gene_id") == 100, f"expected deterministic smallest gene_id=100, got:\n{json.dumps(scenario, indent=2)}"
    finally:
        server.shutdown()


def test_perf_overlap_baseline_file_in_snapshot_is_repo_relative_when_under_repo(tmp_path: Path) -> None:
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

        # Use a repo-local baseline path to ensure snapshots don't embed machine-specific absolute paths.
        rel_baseline = Path(".tmp-tests") / tmp_path.name / "baseline.json"
        abs_baseline = repo_root / rel_baseline
        abs_baseline.parent.mkdir(parents=True, exist_ok=True)

        out_dir = tmp_path / "out"

        try:
            gen = _run_script(
                repo_root,
                env,
                "generate-baseline",
                "--base-url",
                base_url,
                "--baseline-file",
                str(rel_baseline),
                "--out-dir",
                str(out_dir),
                "--warmup-rounds",
                "1",
                "--timeout-seconds",
                "1",
            )
            output = f"{gen.stdout}\n{gen.stderr}"
            assert gen.returncode == 0, f"generate-baseline should succeed:\n{output}"

            baseline = json.loads(abs_baseline.read_text(encoding="utf-8"))
            meta = baseline.get("meta", {})
            assert isinstance(meta, dict)
            assert meta.get("baseline_file") == str(rel_baseline).replace("\\", "/")
        finally:
            if abs_baseline.parent.exists():
                for p in sorted(abs_baseline.parent.glob("*"), reverse=True):
                    try:
                        p.unlink()
                    except IsADirectoryError:
                        pass
                try:
                    abs_baseline.parent.rmdir()
                except OSError:
                    pass
    finally:
        server.shutdown()
