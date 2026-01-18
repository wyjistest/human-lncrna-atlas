from __future__ import annotations

import gzip
import hashlib
from pathlib import Path
from typing import Any, Optional, Union

PathLike = Union[str, Path]


def _to_path(path: PathLike) -> Path:
    if isinstance(path, Path):
        return path
    return Path(path)


def sha256_hex_file(path: PathLike, *, chunk_size: int = 1024 * 1024) -> str:
    """
    计算文件的 SHA256（hex）。

    说明：
    - 返回值为小写 64 位十六进制字符串
    - 以流式方式读取，避免大文件占用过多内存
    """

    file_path = _to_path(path)
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def count_lines(path: PathLike, *, gz: Optional[bool] = None) -> int:
    """
    统计文本文件行数（支持 .gz）。

    Args:
        path: 文件路径
        gz: 是否按 gzip 解压读取；None 时根据后缀 `.gz` 自动判断
    """

    file_path = _to_path(path)
    is_gz = file_path.suffix == ".gz" if gz is None else gz

    if is_gz:
        opener: Any = gzip.open
    else:
        opener = Path.open

    with opener(file_path, "rt", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def validate_file(
    path: PathLike,
    *,
    min_bytes: int = 0,
    min_lines: int = 0,
    max_lines: int = 0,
    expected_sha256: Optional[str] = None,
    gz: Optional[bool] = None,
) -> dict[str, Any]:
    """
    对输入文件做可选 fail-fast 校验（size/line-count/checksum）。

    返回一个指纹 dict，便于上层记录/输出：
    - path: str
    - bytes: int
    - lines: Optional[int]（当未触发行数校验时为 None）
    - sha256: Optional[str]（当未提供 expected_sha256 时为 None）
    """

    file_path = _to_path(path)
    if not file_path.exists():
        raise ValueError(f"file_not_found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"not_a_file: {file_path}")

    size = file_path.stat().st_size
    if min_bytes and size < min_bytes:
        raise ValueError(f"min_bytes: size={size} min_bytes={min_bytes} path={file_path}")

    lines: Optional[int] = None
    if min_lines or max_lines:
        lines = count_lines(file_path, gz=gz)
        if min_lines and lines < min_lines:
            raise ValueError(f"min_lines: lines={lines} min_lines={min_lines} path={file_path}")
        if max_lines and lines > max_lines:
            raise ValueError(f"max_lines: lines={lines} max_lines={max_lines} path={file_path}")

    actual_sha: Optional[str] = None
    if expected_sha256:
        expected = expected_sha256.strip().lower()
        actual_sha = sha256_hex_file(file_path)
        if actual_sha != expected:
            raise ValueError(
                "SHA256 mismatch: "
                f"expected={expected} actual={actual_sha} path={file_path}"
            )

    return {
        "path": str(file_path),
        "bytes": size,
        "lines": lines,
        "sha256": actual_sha,
    }

