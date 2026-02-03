from __future__ import annotations

from pathlib import Path


def resolve_out_dir(repo_root: Path, raw_out_dir: str) -> Path:
    """
    将 --out-dir 解析为真实输出目录：
    - 相对路径：以 repo_root 为基准（避免依赖调用者的 cwd）
    - 绝对路径：保持不变
    """
    out_dir = Path(raw_out_dir)
    if not out_dir.is_absolute():
        out_dir = repo_root / out_dir
    return out_dir.resolve()


def display_path(repo_root: Path, path: Path) -> str:
    """
    用于 Markdown/日志展示：尽量输出 repo-relative 路径，
    避免把机器绝对路径写进产物。
    """
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return str(path)

