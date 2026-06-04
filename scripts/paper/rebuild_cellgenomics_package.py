#!/usr/bin/env python3
"""Rebuild the Cell Genomics reviewer-facing paper package."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]


def run_step(command: list[str], *, cwd: Path, dry_run: bool) -> None:
    printable = " ".join(command)
    print(f"[cellgenomics] {printable}")
    if dry_run:
        return
    subprocess.run(command, cwd=cwd, check=True)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Repository root")
    parser.add_argument("--out-dir", default="paper_figures", help="Paper figure output directory")
    parser.add_argument("--generated-at", default=None, help="Fixed UTC timestamp for metadata")
    parser.add_argument("--source-commit", default="HEAD", help="Git ref or SHA recorded in provenance")
    parser.add_argument("--skip-manuscript", action="store_true", help="Only rebuild validation figures/tables")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running them")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    python = sys.executable or "python3"

    validation_cmd = [
        python,
        "scripts/paper/generate_cellgenomics_validation.py",
        "--repo-root",
        str(repo_root),
        "--out-dir",
        str(args.out_dir),
        "--source-commit",
        str(args.source_commit),
    ]
    if args.generated_at:
        validation_cmd.extend(["--generated-at", str(args.generated_at)])
    run_step(validation_cmd, cwd=repo_root, dry_run=bool(args.dry_run))

    if not args.skip_manuscript:
        run_step(
            [
                python,
                "scripts/paper/render_manuscript.py",
                "--repo-root",
                str(repo_root),
            ],
            cwd=repo_root,
            dry_run=bool(args.dry_run),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
