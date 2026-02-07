import subprocess
import sys
from pathlib import Path


def test_conservation_matrix_help_mentions_no_plots_flag() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [sys.executable, "scripts/research/conservation_matrix_by_binding_affinity.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, f"stdout/stderr:\n{output}"
    assert "--no-plots" in output

