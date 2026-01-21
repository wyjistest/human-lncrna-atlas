import os
import subprocess
from pathlib import Path


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True, check=False)


def test_db_migrate_verify_passes_for_paired_migrations(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir(parents=True, exist_ok=True)

    (migrations_dir / "0001_example.up.sql").write_text("-- up\n", encoding="utf-8")
    (migrations_dir / "0001_example.down.sql").write_text("-- down\n", encoding="utf-8")

    env = os.environ.copy()
    env["MIGRATIONS_DIR"] = str(migrations_dir)
    env["LOG_DIR"] = str(tmp_path / "logs")

    result = _run(
        ["bash", str(repo_root / "frontend/backend/scripts/db_migrate.sh"), "verify"],
        cwd=repo_root,
        env=env,
    )

    assert result.returncode == 0, result.stderr + result.stdout


def test_db_migrate_verify_fails_when_down_missing(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir(parents=True, exist_ok=True)

    (migrations_dir / "0001_example.up.sql").write_text("-- up\n", encoding="utf-8")

    env = os.environ.copy()
    env["MIGRATIONS_DIR"] = str(migrations_dir)
    env["LOG_DIR"] = str(tmp_path / "logs")

    result = _run(
        ["bash", str(repo_root / "frontend/backend/scripts/db_migrate.sh"), "verify"],
        cwd=repo_root,
        env=env,
    )

    assert result.returncode != 0

