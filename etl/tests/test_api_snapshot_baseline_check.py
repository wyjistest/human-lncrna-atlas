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
        "/api/v1/regulations": {"total": 6, "items": [{"id": 1, "lncrna": "LNC1"}]},
        "/api/v1/diseases/options": {"traits": ["T1", "T2", "T3", "T4", "T5"]},
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

