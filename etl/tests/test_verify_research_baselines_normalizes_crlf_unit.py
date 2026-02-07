import importlib.util
from pathlib import Path
import sys


def _load_verify_module(repo_root: Path):
    script_path = repo_root / "scripts" / "verify_research_baselines.py"
    spec = importlib.util.spec_from_file_location("verify_research_baselines", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_verify_research_baselines_normalizes_crlf(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    mod = _load_verify_module(repo_root)

    expected = tmp_path / "expected.csv"
    actual = tmp_path / "actual.csv"

    expected.write_text("a,b\n1,2\n", encoding="utf-8")
    actual.write_bytes(b"a,b\r\n1,2\r\n")

    rc = mod._compare_text_files(expected, actual, group_artifacts=("expected.csv",))
    assert rc == 0
