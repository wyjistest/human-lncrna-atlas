#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render manuscript markdown through Pandoc and the repository-local citation filter.",
    )
    parser.add_argument(
        "--source",
        default="docs/paper/manuscript.md",
        help="Source manuscript markdown path",
    )
    parser.add_argument(
        "--output",
        default="docs/paper/build/manuscript_rendered.md",
        help="Rendered markdown output path",
    )
    parser.add_argument(
        "--pandoc",
        default="pandoc",
        help="Pandoc executable to invoke",
    )
    return parser.parse_args()


def run_step(command: list[str], *, cwd: Path, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / args.source
    output_path = repo_root / args.output
    filter_path = repo_root / "scripts/paper/pandoc_citation_filter.py"

    if not source_path.exists():
        sys.stderr.write(f"Source manuscript missing: {source_path}\n")
        return 1
    if not filter_path.exists():
        sys.stderr.write(f"Pandoc citation filter missing: {filter_path}\n")
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)

    parse_result = run_step(
        [args.pandoc, "--from=markdown+yaml_metadata_block+citations", "--to=json", str(source_path)],
        cwd=repo_root,
    )
    if parse_result.returncode != 0:
        sys.stderr.write(parse_result.stderr or parse_result.stdout)
        return parse_result.returncode

    filter_result = run_step(
        [sys.executable, str(filter_path)],
        cwd=repo_root,
        input_text=parse_result.stdout,
    )
    if filter_result.returncode != 0:
        sys.stderr.write(filter_result.stderr or filter_result.stdout)
        return filter_result.returncode

    render_result = run_step(
        [args.pandoc, "--from=json", "--to=gfm", "--wrap=preserve"],
        cwd=repo_root,
        input_text=filter_result.stdout,
    )
    if render_result.returncode != 0:
        sys.stderr.write(render_result.stderr or render_result.stdout)
        return render_result.returncode

    output_path.write_text(render_result.stdout, encoding="utf-8")
    sys.stdout.write(f"Rendered manuscript written to {output_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
