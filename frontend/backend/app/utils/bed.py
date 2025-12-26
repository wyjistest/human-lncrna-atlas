"""
BED/Track 输出安全工具

用于对 BED 字段、track line 属性做最小必要的清理，避免：
- 控制字符（\\t/\\r/\\n/\\0）破坏 TSV/BED 结构
- track header 中的引号破坏属性解析

注意：
- 不尝试做“内容语义级”的校验（例如染色体命名规则），只做输出层防护。
- 该清理不会影响数据库查询，只影响导出/IGV webservice track 的输出文本。
"""

from __future__ import annotations

import re

_CONTROL_CHARS_RE = re.compile(r"[\x00\t\r\n]")


def sanitize_bed_field(value: str, *, max_len: int = 200, replacement: str = " ") -> str:
    """
    清理 BED/TSV 字段中的控制字符，避免破坏列分隔与行结构。

    - 将 \\t/\\r/\\n/\\0 替换为 replacement（默认空格）
    - strip() 去除首尾空白
    - 超长截断（默认 200）
    - 结果为空时返回 "unknown"
    """
    if not isinstance(value, str):
        value = str(value)

    cleaned = _CONTROL_CHARS_RE.sub(replacement, value).strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned or "unknown"


def sanitize_bed_track_attr(value: str, *, max_len: int = 200) -> str:
    """
    清理 BED track header 属性值（name/description）。

    track line 形如：
        track name="..." description="..."

    因此需要额外处理双引号，避免破坏属性解析。
    """
    cleaned = sanitize_bed_field(value, max_len=max_len, replacement=" ")
    return cleaned.replace('"', "'")


__all__ = ["sanitize_bed_field", "sanitize_bed_track_attr"]

