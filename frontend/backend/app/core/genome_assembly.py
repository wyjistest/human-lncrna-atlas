from __future__ import annotations

import re
from typing import Optional


_REF_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def reference_genome_aliases(expected_assembly: str) -> set[str]:
    """
    返回用于匹配 chipseq_experiments.reference_genome 的“允许别名集合”（小写）。

    说明：
    - 我们在 DB 中同时看到 'hg19' 和 'GRCh38' 等写法；对外 IGV 参考使用 hg19。
    - 为了“可回滚 + 向后兼容”，NULL/空值视为未知（兼容），仅排除明确不匹配的记录。
    """
    expected = (expected_assembly or "").strip().lower()
    if not expected:
        return set()

    aliases = {expected}
    if expected == "hg19":
        aliases.add("grch37")
    elif expected == "hg38":
        aliases.add("grch38")

    return aliases


def is_reference_genome_compatible(
    reference_genome: Optional[str],
    *,
    expected_assembly: str,
) -> bool:
    """
    判断单条实验的 reference_genome 是否与当前物种对外宣称的 assembly 兼容。

    规则：
    - None/空字符串：视为“未知”，默认为兼容（避免因历史数据缺少元信息而全量丢数据）
    - 非空：若 tokens 与 expected_assembly 的别名集合有交集则兼容，否则不兼容
    """
    if reference_genome is None or not str(reference_genome).strip():
        return True

    aliases = reference_genome_aliases(expected_assembly)
    if not aliases:
        return True

    tokens = {t.lower() for t in _REF_TOKEN_RE.findall(str(reference_genome))}
    return bool(tokens & aliases)
