#!/usr/bin/env python3
"""
导出表观遗传标记重叠汇总（TSV + Markdown）。

目标：
- Phase 6.0「方向 3：表观遗传标记关联分析」最小可复现入口
- 在给定 binding_affinity 阈值下，统计 ChIP-seq overlaps 的：
  - mark_name × mark_category × cell_type 的重叠条数（overlap_count）
  - Top marks / Top cell types / category 汇总（用于快速解读）

依赖：
- 复用后端 SQLAlchemy DB 配置（同 `frontend/backend`）
- 需要可访问 PostgreSQL（环境变量与后端一致：DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD）

示例：
  python3 scripts/research/epigenetic_summary_by_binding_affinity.py --min-ba 100
  python3 scripts/research/epigenetic_summary_by_binding_affinity.py --min-ba 50 --out-dir docs/reports
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "frontend" / "backend"
sys.path.insert(0, str(BACKEND_DIR))


def _iso_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _to_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _md_escape(text_value: str) -> str:
    return text_value.replace("|", "\\|")


def _safe_error(e: Exception, *, max_len: int = 500) -> str:
    msg = f"{type(e).__name__}: {e}"
    msg = " ".join(str(msg).split())
    if len(msg) > max_len:
        return msg[: max_len - 3] + "..."
    return msg


@dataclass(frozen=True)
class SummaryRow:
    mark_name: str
    mark_category: str
    cell_type: str
    overlap_count: int


def _query_summary_rows(db, *, min_ba: float) -> tuple[list[SummaryRow], str, Optional[str]]:
    from sqlalchemy import text

    # Fast path（Phase 9.21）：只有 BA>=100 的预聚合 MV。
    if float(min_ba) == 100.0:
        try:
            result = db.execute(
                text(
                    """
                    SELECT
                      o.mark_name,
                      o.mark_category,
                      o.cell_type,
                      o.overlap_count
                    FROM mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100 o
                    """
                ).execution_options(stream_results=True)
            )
            rows: list[SummaryRow] = []
            with result as rs:
                for r in rs.mappings():
                    rows.append(
                        SummaryRow(
                            mark_name=str(r.get("mark_name") or "").strip(),
                            mark_category=str(r.get("mark_category") or "").strip(),
                            cell_type=str(r.get("cell_type") or "").strip(),
                            overlap_count=_to_int(r.get("overlap_count")) or 0,
                        )
                    )
            return (rows, "mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100", None)
        except Exception as e:
            # MV 缺失会让事务进入 aborted；fallback 前必须 rollback。
            try:
                db.rollback()
            except Exception:
                pass
            warning = _safe_error(e)
    else:
        warning = None

    # Fallback：从 base MV 聚合（支持任意 min_ba）。
    try:
        result = db.execute(
            text(
                """
                SELECT
                  o.mark_name,
                  o.mark_category,
                  o.cell_type,
                  COUNT(*) AS overlap_count
                FROM mv_lncrna_chipseq_overlaps o
                WHERE o.binding_affinity >= :min_ba
                GROUP BY o.mark_name, o.mark_category, o.cell_type
                ORDER BY overlap_count DESC, o.mark_name ASC, o.cell_type ASC
                """
            ).execution_options(stream_results=True),
            {"min_ba": min_ba},
        )
        rows = []
        with result as rs:
            for r in rs.mappings():
                rows.append(
                    SummaryRow(
                        mark_name=str(r.get("mark_name") or "").strip(),
                        mark_category=str(r.get("mark_category") or "").strip(),
                        cell_type=str(r.get("cell_type") or "").strip(),
                        overlap_count=_to_int(r.get("overlap_count")) or 0,
                    )
                )
        return (rows, "mv_lncrna_chipseq_overlaps (GROUP BY)", warning)
    except Exception as e:
        return ([], "mv_lncrna_chipseq_overlaps (GROUP BY)", _safe_error(e))


def _write_tsv(path: Path, rows: list[SummaryRow]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["mark_name", "mark_category", "cell_type", "overlap_count"])
        for r in rows:
            w.writerow([r.mark_name, r.mark_category, r.cell_type, r.overlap_count])


def _fmt_pct(part: int, total: int) -> str:
    if total <= 0:
        return "0.00%"
    return f"{(100.0 * float(part) / float(total)):.2f}%"


def _write_markdown(
    path: Path,
    *,
    min_ba: float,
    source: str,
    warning: Optional[str],
    rows: list[SummaryRow],
    tsv_path: Path,
    generated_at_utc: str,
    preview_limit: int,
) -> None:
    total_overlaps = sum(r.overlap_count for r in rows)

    by_mark: dict[str, int] = {}
    by_cell: dict[str, int] = {}
    by_category: dict[str, int] = {}

    for r in rows:
        by_mark[r.mark_name] = by_mark.get(r.mark_name, 0) + r.overlap_count
        by_cell[r.cell_type] = by_cell.get(r.cell_type, 0) + r.overlap_count
        by_category[r.mark_category] = by_category.get(r.mark_category, 0) + r.overlap_count

    top_marks = sorted(by_mark.items(), key=lambda kv: (-kv[1], kv[0]))[: max(0, preview_limit)]
    top_cells = sorted(by_cell.items(), key=lambda kv: (-kv[1], kv[0]))[: max(0, preview_limit)]
    category_rows = sorted(by_category.items(), key=lambda kv: (-kv[1], kv[0]))

    lines: list[str] = []
    lines.append("# Epigenetic Summary (ChIP-seq overlaps)")
    lines.append("")
    lines.append(f"- Generated (UTC): `{generated_at_utc}`")
    lines.append(f"- min_ba: `{min_ba}`")
    lines.append(f"- Source: `{source}`")
    if warning:
        lines.append(f"- Warning: `{warning}`")
    lines.append(f"- Total overlaps: `{total_overlaps}`")
    lines.append(f"- Unique marks: `{len(by_mark)}`")
    lines.append(f"- Unique cell types: `{len(by_cell)}`")
    lines.append("")
    lines.append(f"- TSV: `{tsv_path}`")

    lines.append("")
    lines.append("## Category breakdown")
    lines.append("")
    lines.append("| Category | Overlaps | % |")
    lines.append("|---|---:|---:|")
    for cat, cnt in category_rows:
        cat_label = _md_escape(cat or "(empty)")
        lines.append(f"| {cat_label} | {cnt} | {_fmt_pct(cnt, total_overlaps)} |")

    lines.append("")
    lines.append(f"## Top marks (Top {len(top_marks)})")
    lines.append("")
    lines.append("| Rank | Mark | Overlaps | % |")
    lines.append("|---:|---|---:|---:|")
    for i, (mark, cnt) in enumerate(top_marks, start=1):
        mark_label = _md_escape(mark or "(empty)")
        lines.append(f"| {i} | {mark_label} | {cnt} | {_fmt_pct(cnt, total_overlaps)} |")

    lines.append("")
    lines.append(f"## Top cell types (Top {len(top_cells)})")
    lines.append("")
    lines.append("| Rank | Cell type | Overlaps | % |")
    lines.append("|---:|---|---:|---:|")
    for i, (cell, cnt) in enumerate(top_cells, start=1):
        cell_label = _md_escape(cell or "(empty)")
        lines.append(f"| {i} | {cell_label} | {cnt} | {_fmt_pct(cnt, total_overlaps)} |")

    if total_overlaps == 0:
        lines.append("")
        lines.append("## Notes")
        lines.append("")
        lines.append(
            "- 若你期望看到非空结果：请确认已安装并填充 `mv_lncrna_chipseq_overlaps`（以及可选的 "
            "`mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100`）。"
        )
        lines.append("- 参考：`schema/v2.3/05_mv_lncrna_chipseq_overlaps.sql` / `schema/v2.3/06_mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100.sql`")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export epigenetic overlap summary by binding affinity threshold.")
    parser.add_argument("--min-ba", type=float, default=100.0, help="Minimum binding affinity (default: 100).")
    parser.add_argument(
        "--generated-at",
        type=str,
        default="",
        help="Override 'Generated (UTC)' in Markdown outputs. Empty = use current UTC time.",
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=20,
        help="Top marks/cell types rows in Markdown (default: 20).",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=str(REPO_ROOT / "docs" / "reports"),
        help="Output directory (default: docs/reports).",
    )
    args = parser.parse_args()

    try:
        from app.core.database import SessionLocal
    except ModuleNotFoundError as e:
        print(
            "Missing Python dependencies for DB access.\n"
            "- Please run this script with the backend venv Python (e.g. `frontend/backend/.venv/bin/python ...`)\n"
            "- Or install backend requirements so `sqlalchemy` and `app.*` are importable.",
            file=sys.stderr,
        )
        raise SystemExit(2) from e

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    generated_at_utc = (args.generated_at or "").strip() or _iso_ts()
    min_ba = float(args.min_ba)
    preview_limit = max(0, int(args.preview_limit))

    tsv_path = out_dir / f"epigenetic-summary-ba{int(min_ba)}.tsv"
    md_path = out_dir / f"epigenetic-summary-ba{int(min_ba)}.md"

    db = SessionLocal()
    try:
        rows, source, warning = _query_summary_rows(db, min_ba=min_ba)
        _write_tsv(tsv_path, rows)
        _write_markdown(
            md_path,
            min_ba=min_ba,
            source=source,
            warning=warning,
            rows=rows,
            tsv_path=tsv_path,
            generated_at_utc=generated_at_utc,
            preview_limit=preview_limit,
        )
    finally:
        db.close()

    print(f"Wrote: {tsv_path}")
    print(f"Wrote: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

