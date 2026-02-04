#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

try:
    import pyBigWig  # type: ignore
except Exception as e:  # pragma: no cover
    pyBigWig = None
    _PYBIGWIG_IMPORT_ERROR = e
else:  # pragma: no cover
    _PYBIGWIG_IMPORT_ERROR = None


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


def _infer_assembly(
    filename: str,
    *,
    known_assemblies: list[str],
    default_assembly: str,
) -> str:
    for assembly in sorted(known_assemblies, key=len, reverse=True):
        if filename.startswith(f"{assembly}.") or filename.startswith(f"{assembly}_"):
            return assembly

        pattern = re.compile(rf"(^|[^A-Za-z0-9]){re.escape(assembly)}([^A-Za-z0-9]|$)")
        if pattern.search(filename):
            return assembly

    return default_assembly


def _iter_tracks(genomes_dir: Path, *, files: list[str]) -> list[Path]:
    if files:
        return [Path(p).expanduser().resolve() for p in files]

    candidates: list[Path] = []
    for suffix in (".bw", ".bb"):
        candidates.extend(sorted(genomes_dir.glob(f"*{suffix}")))
    return candidates


def _validate_one_track(
    track_path: Path,
    *,
    expected_chrom_sizes: dict[str, int],
    allow_extra_chroms: bool,
) -> tuple[bool, list[str]]:
    if pyBigWig is None:  # pragma: no cover
        raise RuntimeError(
            "missing_dependency: pyBigWig (install via `python3 -m pip install pyBigWig`)"
        )

    warnings: list[str] = []
    ok = True

    bw = pyBigWig.open(str(track_path))
    try:
        chroms: dict[str, int] = bw.chroms() or {}
    finally:
        bw.close()

    if not chroms:
        return False, ["empty_chrom_table"]

    mismatches: list[str] = []
    unknown_chroms: list[str] = []
    checked = 0

    for chrom, size in chroms.items():
        exp = expected_chrom_sizes.get(chrom)
        if exp is None:
            unknown_chroms.append(chrom)
            continue
        checked += 1
        if int(size) != int(exp):
            mismatches.append(f"{chrom}: track={size} expected={exp}")

    if mismatches:
        ok = False
        warnings.append(f"mismatch_count={len(mismatches)}")
        warnings.extend(mismatches[:10])
        if len(mismatches) > 10:
            warnings.append("mismatch_truncated=true")

    if unknown_chroms:
        msg = f"unknown_chroms={len(unknown_chroms)}"
        if allow_extra_chroms:
            warnings.append(msg)
        else:
            ok = False
            warnings.append(msg)

    # Sentinel chromosomes: quick smoke checks that can catch hg19/hg38 混用等问题。
    for sentinel in ("chr1", "chr2", "chrX", "chrM"):
        if sentinel in chroms and sentinel in expected_chrom_sizes:
            if int(chroms[sentinel]) != int(expected_chrom_sizes[sentinel]):
                ok = False
                warnings.append(
                    f"sentinel_mismatch={sentinel}: "
                    f"track={chroms[sentinel]} expected={expected_chrom_sizes[sentinel]}"
                )

    if checked < 10:
        warnings.append(f"checked_chroms_low={checked}")

    return ok, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "校验 BigWig/BigBed 轨道文件的坐标组装是否与 <assembly>.chrom.sizes 一致。"
            "（用于快速发现 hg19/hg38 等组装混用问题）"
        )
    )
    parser.add_argument(
        "--genomes-dir",
        default=None,
        help="GENOMES_DIR（默认读取环境变量 GENOMES_DIR；仍为空则使用当前目录）",
    )
    parser.add_argument(
        "--default-assembly",
        default="hg19",
        help="当轨道文件名无法推断组装时使用的默认 assembly（默认: hg19）",
    )
    parser.add_argument(
        "--known-assemblies",
        default="hg19,panTro5,rheMac10,calJac3,hg38,panTro6,calJac4",
        help="用于从文件名推断组装的候选列表（逗号分隔）",
    )
    parser.add_argument(
        "--allow-extra-chroms",
        action="store_true",
        help="允许轨道中的染色体不在 chrom.sizes 中（仅 warning，不 fail）",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="可选：要校验的 .bw/.bb 文件（不提供则扫描 genomes-dir 下所有 .bw/.bb）",
    )

    args = parser.parse_args(argv)

    genomes_dir = (
        Path(args.genomes_dir).expanduser()
        if args.genomes_dir
        else Path((os.environ.get("GENOMES_DIR") or "."))
    ).resolve()

    known = [s.strip() for s in str(args.known_assemblies).split(",") if s.strip()]
    default_assembly = str(args.default_assembly).strip()
    if not default_assembly:
        print("invalid --default-assembly: empty", file=sys.stderr)
        return 2

    tracks = _iter_tracks(genomes_dir, files=list(args.files))
    if not tracks:
        print(f"no tracks found under {genomes_dir}", file=sys.stderr)
        return 1

    exit_code = 0

    for track_path in tracks:
        if track_path.suffix not in (".bw", ".bb"):
            continue

        assembly = _infer_assembly(
            track_path.name, known_assemblies=known, default_assembly=default_assembly
        )
        chrom_sizes_path = genomes_dir / f"{assembly}.chrom.sizes"
        if not chrom_sizes_path.exists():
            print(
                f"ERROR assembly={assembly} missing_chrom_sizes={chrom_sizes_path} track={track_path}",
                file=sys.stderr,
            )
            exit_code = 1
            continue

        expected = _load_chrom_sizes(chrom_sizes_path)
        try:
            ok, warnings = _validate_one_track(
                track_path,
                expected_chrom_sizes=expected,
                allow_extra_chroms=bool(args.allow_extra_chroms),
            )
        except Exception as e:
            print(
                f"ERROR assembly={assembly} track={track_path} error={e}",
                file=sys.stderr,
            )
            exit_code = 1
            continue

        if ok:
            print(f"OK   assembly={assembly} track={track_path}")
            for w in warnings:
                print(f"     WARN {w}")
        else:
            print(f"FAIL assembly={assembly} track={track_path}", file=sys.stderr)
            for w in warnings:
                print(f"     {w}", file=sys.stderr)
            exit_code = 1

    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
