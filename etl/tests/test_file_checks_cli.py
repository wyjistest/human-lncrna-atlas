import json
import subprocess
import sys
from pathlib import Path


def _run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "etl.file_checks", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def test_file_checks_cli_verify_outputs_json(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    path = tmp_path / "input.tsv"
    path.write_text("col1\tcol2\n1\t2\n", encoding="utf-8")

    proc = _run(["verify", str(path)], cwd=repo_root)
    assert proc.returncode == 0, proc.stderr

    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["path"] == str(path)
    assert obj["bytes"] == path.stat().st_size
    assert obj["lines"] is None
    assert obj["sha256"] is None


def test_file_checks_cli_verify_enforces_min_bytes(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    path = tmp_path / "small.txt"
    path.write_text("x\ny\n", encoding="utf-8")

    proc = _run(["verify", "--min-bytes", "10000", str(path)], cwd=repo_root)
    assert proc.returncode == 1
    assert "min_bytes" in proc.stderr


def test_file_checks_cli_verify_enforces_sha256(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    path = tmp_path / "input.tsv"
    path.write_text("a\tb\n", encoding="utf-8")

    proc = _run(["verify", "--sha256", "0" * 64, str(path)], cwd=repo_root)
    assert proc.returncode == 1
    assert "SHA256" in proc.stderr

