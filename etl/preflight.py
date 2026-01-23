from __future__ import annotations

from pathlib import Path
from typing import Iterable

from etl.input_manifest import PathLike, list_manifest_paths, verify_manifest_file
from etl.file_checks import validate_file


def _normalize_path(p: PathLike) -> Path:
    if isinstance(p, Path):
        return p.resolve(strict=False)
    return Path(p).resolve(strict=False)


def verify_manifest_for_paths(manifest_path: PathLike, required_paths: Iterable[PathLike]) -> list[str]:
    """
    导入前的 fail-fast 校验：
    1) 先执行 verify_manifest_file()（存在性/bytes/lines/sha256）
    2) 再确保 required_paths 均在 manifest 中出现（避免“传了 manifest 但没覆盖到本次导入文件”）
    """

    try:
        errors = verify_manifest_file(manifest_path)
    except Exception as e:
        return [f"manifest verification error: {e}"]

    try:
        manifest_set = {_normalize_path(p) for p in list_manifest_paths(manifest_path)}
    except Exception as e:
        return errors + [f"manifest parse error: {e}"]

    for rp in required_paths:
        try:
            required = _normalize_path(rp)
        except Exception as e:
            errors.append(f"invalid required path: {rp!r} ({e})")
            continue

        if required not in manifest_set:
            errors.append(f"required file not listed in manifest: {required}")

    return errors


def verify_file_checks_for_paths(
    required_paths: Iterable[PathLike],
    *,
    min_bytes: int = 0,
    min_lines: int = 0,
    max_lines: int = 0,
    expected_sha256: Iterable[str] | None = None,
) -> list[str]:
    """
    对指定输入文件执行阈值校验（size/line-count/checksum）。

    规则：
    - expected_sha256 为空：不做 checksum 校验
    - 仅提供 1 个 SHA256：对所有文件使用同一值
    - 提供 N 个 SHA256：与文件一一对应
    """

    paths = list(required_paths)
    sha_list = list(expected_sha256 or [])
    expected_per_file: list[str | None] = []
    if not sha_list:
        expected_per_file = [None] * len(paths)
    elif len(sha_list) == 1:
        expected_per_file = [sha_list[0]] * len(paths)
    elif len(sha_list) == len(paths):
        expected_per_file = sha_list
    else:
        return [
            "invalid --sha256 usage: provide 0 values, 1 value, or N values matching files"
        ]

    errors: list[str] = []
    for file_path, expected_sha in zip(paths, expected_per_file, strict=True):
        try:
            validate_file(
                file_path,
                min_bytes=min_bytes,
                min_lines=min_lines,
                max_lines=max_lines,
                expected_sha256=expected_sha,
            )
        except Exception as e:
            errors.append(str(e))

    return errors
