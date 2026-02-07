import subprocess
import sys
from pathlib import Path


def test_verify_research_baselines_help_mentions_new_groups() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [sys.executable, "scripts/verify_research_baselines.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, f"stdout/stderr:\n{output}"
    assert "epigenetic-summary" in output
    assert "conservation-matrix" in output

