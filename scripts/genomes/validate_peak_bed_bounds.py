#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import os
import sys
from pathlib import Path


def _load_chrom_sizes(path: Path) -> dict[str, int]:
    chrom_sizes: dict[str, int] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            chrom, size_str, *_ = raw.split("\t")
            chrom_sizes[chrom] = int(size_str)
    return chrom_sizes


def _open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def validate_peak_file(
    path: Path,
    *,
    chrom_sizes: dict[str, int],
    allow_unknown_chroms: bool,
    max_examples: int,
) -> tuple[bool, dict[str, int], list[str]]:
    """
    校验 BED/broadPeak/narrowPeak 文件中坐标是否落在 chrom.sizes 定义范围内。

    规则：
    - start >= 0
    - end > start
    - end <= chrom_sizes[chrom]
    - 染色体不在 chrom.sizes 中默认视为错误（可通过 allow_unknown_chroms 放宽为 warning）
    """
    records = 0
    bad_records = 0
    unknown_chrom_records = 0
    examples: list[str] = []

    def _add_example(lineno: int, reason: str, line: str) -> None:
        nonlocal examples
        if len(examples) >= max_examples:
            return
        examples.append(f"line={lineno} reason={reason} record={line.strip()[:200]}")

    with _open_text(path) as fh:
        for lineno, line in enumerate(fh, 1):
            raw = line.rstrip("\n")
            stripped = raw.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            if stripped.startswith("track") or stripped.startswith("browser"):
                continue

            parts = raw.split("\t")
            if len(parts) < 3:
                bad_records += 1
                _add_example(lineno, "too_few_columns", raw)
                continue

            chrom = parts[0]
            try:
                start = int(parts[1])
                end = int(parts[2])
            except ValueError:
                bad_records += 1
                _add_example(lineno, "invalid_int", raw)
                continue

            records += 1

            chrom_len = chrom_sizes.get(chrom)
            if chrom_len is None:
                unknown_chrom_records += 1
                if not allow_unknown_chroms:
                    bad_records += 1
                _add_example(lineno, "unknown_chrom", raw)
                continue

            if start < 0:
                bad_records += 1
                _add_example(lineno, "start_negative", raw)
                continue

            if end <= start:
                bad_records += 1
                _add_example(lineno, "end_le_start", raw)
                continue

            if end > chrom_len:
                bad_records += 1
                _add_example(lineno, f"end_gt_chrom_len({chrom_len})", raw)
                continue

    ok = bad_records == 0
    stats = {
        "records": records,
        "bad_records": bad_records,
        "unknown_chrom_records": unknown_chrom_records,
    }
    return ok, stats, examples


def _iter_peak_files(paths: list[Path]) -> list[Path]:
    suffixes = (
        ".bed",
        ".broadPeak",
        ".narrowPeak",
        ".bed.gz",
        ".broadPeak.gz",
        ".narrowPeak.gz",
    )

    files: list[Path] = []
    for p in paths:
        if p.is_file():
            if str(p).endswith(suffixes):
                files.append(p)
            continue
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file() and str(child).endswith(suffixes):
                    files.append(child)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "校验 peak 注释轨道（BED/broadPeak/narrowPeak）坐标是否符合指定 assembly 的 chrom.sizes。"
            "（用于快速发现 hg19/hg38 等组装混用问题）"
        )
    )
    parser.add_argument(
        "--chrom-sizes",
        default=None,
        help=(
            "chrom.sizes 文件路径（优先）。"
            "未提供时，将尝试使用 GENOMES_DIR/<assembly>.chrom.sizes"
        ),
    )
    parser.add_argument(
        "--genomes-dir",
        default=None,
        help="GENOMES_DIR（默认读取环境变量 GENOMES_DIR；仍为空则使用当前目录）",
    )
    parser.add_argument(
        "--assembly",
        default="hg19",
        help="当未显式提供 --chrom-sizes 时使用的 assembly（默认: hg19）",
    )
    parser.add_argument(
        "--allow-unknown-chroms",
        action="store_true",
        help="允许 peak 文件中存在 chrom.sizes 未定义的染色体（仅 warning，不 fail）",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=5,
        help="每个文件最多输出多少条示例错误（默认: 5）",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="要校验的文件或目录（目录会递归扫描 .bed/.broadPeak/.narrowPeak 及其 .gz）",
    )

    args = parser.parse_args(argv)

    if args.chrom_sizes:
        chrom_sizes_path = Path(args.chrom_sizes).expanduser().resolve()
    else:
        genomes_dir = (
            Path(args.genomes_dir).expanduser()
            if args.genomes_dir
            else Path((os.environ.get("GENOMES_DIR") or "."))
        ).resolve()
        chrom_sizes_path = genomes_dir / f"{args.assembly}.chrom.sizes"

    if not chrom_sizes_path.exists():
        print(f"missing chrom.sizes: {chrom_sizes_path}", file=sys.stderr)
        return 2

    chrom_sizes = _load_chrom_sizes(chrom_sizes_path)
    if not chrom_sizes:
        print(f"empty chrom.sizes: {chrom_sizes_path}", file=sys.stderr)
        return 2

    input_paths = [Path(p).expanduser().resolve() for p in args.paths]
    files = _iter_peak_files(input_paths)
    if not files:
        print("no peak files found (supported: .bed/.broadPeak/.narrowPeak[.gz])", file=sys.stderr)
        return 1

    exit_code = 0
    for f in files:
        ok, stats, examples = validate_peak_file(
            f,
            chrom_sizes=chrom_sizes,
            allow_unknown_chroms=bool(args.allow_unknown_chroms),
            max_examples=int(args.max_examples),
        )

        if ok:
            print(
                "OK   file=%s records=%s unknown_chrom_records=%s"
                % (f, stats["records"], stats["unknown_chrom_records"])
            )
            if stats["unknown_chrom_records"] > 0:
                print("     WARN unknown_chrom_records=%s" % stats["unknown_chrom_records"])
        else:
            exit_code = 1
            print(
                "FAIL file=%s records=%s bad_records=%s unknown_chrom_records=%s"
                % (f, stats["records"], stats["bad_records"], stats["unknown_chrom_records"]),
                file=sys.stderr,
            )
            for ex in examples:
                print(f"     {ex}", file=sys.stderr)

    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
