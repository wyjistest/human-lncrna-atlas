from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterable, Optional, Union

from etl.file_checks import count_lines, sha256_hex_file

PathLike = Union[str, Path]


def _to_path(path: PathLike) -> Path:
    if isinstance(path, Path):
        return path
    return Path(path)


def build_manifest_entries(
    paths: Iterable[PathLike],
    *,
    include_lines: bool = False,
    include_sha256: bool = False,
) -> list[dict[str, Any]]:
    """
    为一组文件生成 manifest entries（bytes + 可选 lines/sha256）。
    """

    entries: list[dict[str, Any]] = []
    for p in paths:
        file_path = _to_path(p)
        if not file_path.exists():
            raise FileNotFoundError(str(file_path))
        if not file_path.is_file():
            raise ValueError(f"not_a_file: {file_path}")

        size = file_path.stat().st_size
        lines: Optional[int] = None
        digest: Optional[str] = None

        if include_lines:
            lines = count_lines(file_path)
        if include_sha256:
            digest = sha256_hex_file(file_path)

        entries.append(
            {
                "path": str(file_path),
                "bytes": size,
                "lines": lines,
                "sha256": digest,
            }
        )

    return entries


def write_manifest_tsv(entries: list[dict[str, Any]], output_path: PathLike) -> None:
    """
    将 entries 写入 TSV 文件。

    格式：
      path  bytes  lines  sha256

    约定：
    - 空字段表示“未记录/不校验”（例如 lines/sha256）
    """

    out = _to_path(output_path)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write("path\tbytes\tlines\tsha256\n")
        for e in entries:
            path = str(e.get("path", ""))
            size = e.get("bytes", "")
            lines = e.get("lines", "")
            sha = e.get("sha256", "")

            f.write(
                f"{path}\t{size}\t{'' if lines is None else lines}\t{'' if sha is None else sha}\n"
            )


def _parse_manifest_tsv(path: Path) -> list[dict[str, str]]:
    raw = path.read_text(encoding="utf-8").splitlines()
    if not raw:
        return []

    # Very small TSV parser (no quoting). Skip blank/comment lines.
    rows = [line for line in raw if line.strip() and not line.lstrip().startswith("#")]
    if not rows:
        return []

    header = rows[0].split("\t")
    expected = ["path", "bytes", "lines", "sha256"]
    if header[:4] != expected:
        raise ValueError(f"invalid_manifest_header: {header!r}")

    entries: list[dict[str, str]] = []
    for line in rows[1:]:
        parts = line.split("\t")
        # Pad to 4 columns
        parts += [""] * (4 - len(parts))
        entries.append(
            {
                "path": parts[0],
                "bytes": parts[1],
                "lines": parts[2],
                "sha256": parts[3],
            }
        )
    return entries


def verify_manifest_file(manifest_path: PathLike) -> list[str]:
    """
    校验 manifest 中列出的文件（存在性/bytes/lines/sha256）。

    规则：
    - bytes 字段为空：跳过 size 校验
    - lines 字段为空：跳过行数校验
    - sha256 字段为空：跳过 sha256 校验
    - 相对路径按 manifest 所在目录解析
    """

    manifest = _to_path(manifest_path)
    base_dir = manifest.parent
    entries = _parse_manifest_tsv(manifest)

    errors: list[str] = []
    for e in entries:
        raw_path = (e.get("path") or "").strip()
        if not raw_path:
            errors.append("path missing in manifest entry")
            continue

        p = Path(raw_path)
        if not p.is_absolute():
            p = base_dir / p

        if not p.exists():
            errors.append(f"missing file: {p}")
            continue
        if not p.is_file():
            errors.append(f"not a file: {p}")
            continue

        expected_bytes = (e.get("bytes") or "").strip()
        if expected_bytes:
            try:
                exp = int(expected_bytes)
            except ValueError:
                errors.append(f"invalid bytes value: {expected_bytes!r} path={p}")
            else:
                actual = p.stat().st_size
                if actual != exp:
                    errors.append(f"bytes mismatch: expected={exp} actual={actual} path={p}")

        expected_lines = (e.get("lines") or "").strip()
        if expected_lines:
            try:
                exp_lines = int(expected_lines)
            except ValueError:
                errors.append(f"invalid lines value: {expected_lines!r} path={p}")
            else:
                actual_lines = count_lines(p)
                if actual_lines != exp_lines:
                    errors.append(
                        f"lines mismatch: expected={exp_lines} actual={actual_lines} path={p}"
                    )

        expected_sha = (e.get("sha256") or "").strip()
        if expected_sha:
            actual_sha = sha256_hex_file(p)
            if actual_sha.lower() != expected_sha.lower():
                errors.append(
                    f"sha256 mismatch: expected={expected_sha.lower()} actual={actual_sha.lower()} path={p}"
                )

    return errors


def list_manifest_paths(manifest_path: PathLike) -> list[Path]:
    """
    读取 manifest 并返回解析后的文件路径列表。

    规则：
    - 相对路径按 manifest 所在目录解析
    - 不验证文件存在性（这由 verify_manifest_file() 负责）
    """

    manifest = _to_path(manifest_path)
    base_dir = manifest.parent
    entries = _parse_manifest_tsv(manifest)

    paths: list[Path] = []
    for e in entries:
        raw_path = (e.get("path") or "").strip()
        if not raw_path:
            continue

        p = Path(raw_path)
        if not p.is_absolute():
            p = base_dir / p
        paths.append(p)

    return paths


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="生成/校验 ETL 输入文件 manifest（bytes/lines/sha256）"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    build = sub.add_parser("build", help="生成 manifest")
    build.add_argument("--output", required=True, help="输出 manifest 路径（TSV）")
    build.add_argument("--lines", action="store_true", help="记录行数（对大文件可能较慢）")
    build.add_argument("--sha256", action="store_true", help="记录 SHA256（对大文件可能较慢）")
    build.add_argument("files", nargs="+", help="输入文件列表")

    verify = sub.add_parser("verify", help="校验 manifest")
    verify.add_argument("manifest", help="manifest TSV 路径")

    args = parser.parse_args(argv)

    if args.cmd == "build":
        entries = build_manifest_entries(
            args.files, include_lines=bool(args.lines), include_sha256=bool(args.sha256)
        )
        write_manifest_tsv(entries, args.output)
        return 0

    if args.cmd == "verify":
        errors = verify_manifest_file(args.manifest)
        if errors:
            for e in errors:
                print(e, file=sys.stderr)
            return 1
        return 0

    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
