from __future__ import annotations

from pathlib import Path
from typing import Iterable

from etl.input_manifest import PathLike, list_manifest_paths, verify_manifest_file


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

