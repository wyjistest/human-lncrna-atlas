"""
热点 SQL 查询性能基线：EXPLAIN (ANALYZE, BUFFERS)

用途：
- 在本机 PostgreSQL + 真实数据集环境下，快速验证关键查询是否命中索引、耗时是否在可接受范围内
- 为 Phase 4（后端性能热点）提供可重复的“跑法”和结果摘要

运行方式：
    cd frontend/backend
    ./.venv/bin/python scripts/explain_hot_queries.py

可选参数：
    --species-id 1
    --chromosome chr1
    --lncrna-name MALAT1
    --min-ba 100
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import desc, text

# 添加 backend 目录到 Python 路径（允许从任意 cwd 运行）
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.core.utils import escape_like_pattern  # noqa: E402
from app.models import Regulation  # noqa: E402
from app.routers.regulations import _build_regulation_list_query  # noqa: E402


@dataclass(frozen=True)
class ExplainSummary:
    name: str
    execution_ms: float
    planning_ms: float
    actual_rows: int | None
    indexes: tuple[str, ...]


def _collect_indexes(plan_node: dict[str, Any], out: set[str]) -> None:
    index_name = plan_node.get("Index Name")
    if isinstance(index_name, str) and index_name:
        out.add(index_name)

    for child in plan_node.get("Plans", []) or []:
        if isinstance(child, dict):
            _collect_indexes(child, out)


def _explain_json(db, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    payload = db.execute(
        text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}"),
        params,
    ).scalar()
    return payload[0]


def _summarize(db, name: str, sql: str, params: dict[str, Any] | None = None) -> ExplainSummary:
    data = _explain_json(db, sql, params)
    plan = data["Plan"]

    indexes: set[str] = set()
    _collect_indexes(plan, indexes)

    actual_rows = plan.get("Actual Rows")
    if isinstance(actual_rows, (int, float)):
        actual_rows = int(actual_rows)
    else:
        actual_rows = None

    return ExplainSummary(
        name=name,
        execution_ms=float(data.get("Execution Time", 0.0)),
        planning_ms=float(data.get("Planning Time", 0.0)),
        actual_rows=actual_rows,
        indexes=tuple(sorted(indexes)),
    )


def _compile_sql(query) -> str:
    stmt = query.statement
    compiled = stmt.compile(compile_kwargs={"literal_binds": True})
    return str(compiled)


def main() -> int:
    parser = argparse.ArgumentParser(description="EXPLAIN hot queries for Human LncRNA Atlas backend")
    parser.add_argument("--species-id", type=int, default=1, help="Regulations list: species_id filter (default: 1)")
    parser.add_argument("--chromosome", type=str, default="chr1", help="Regulations list: target chromosome (default: chr1)")
    parser.add_argument("--lncrna-name", type=str, default="MALAT1", help="Regulations list: lncRNA gene_name fuzzy match")
    parser.add_argument("--min-ba", type=float, default=100.0, help="Analysis summary: BA threshold (default: 100)")
    args = parser.parse_args()

    high_affinity_sql = """
    WITH high_affinity_regs AS (
        SELECT
            r.regulation_id,
            r.lncrna_gene_id,
            r.target_gene_id,
            r.binding_affinity,
            lnc.gene_name as lncrna_name
        FROM regulations r
        JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
        WHERE r.binding_affinity >= :min_ba
    )
    SELECT
        COUNT(*) as total_regulations,
        COUNT(DISTINCT lncrna_gene_id) as unique_lncrnas,
        COUNT(DISTINCT target_gene_id) as unique_targets,
        AVG(binding_affinity) as avg_ba,
        MAX(binding_affinity) as max_ba
    FROM high_affinity_regs
    """

    top_lncrnas_sql = """
    SELECT
        lnc.gene_name as lncrna_name,
        COUNT(DISTINCT r.target_gene_id) as target_count,
        AVG(r.binding_affinity) as avg_ba
    FROM regulations r
    JOIN genes lnc ON r.lncrna_gene_id = lnc.gene_id
    WHERE r.binding_affinity >= :min_ba
    GROUP BY lnc.gene_name
    ORDER BY target_count DESC, avg_ba DESC
    LIMIT 20
    """

    epigenetic_sql = """
    SELECT
        COUNT(*) as total_overlaps,
        o.mark_name,
        o.mark_category,
        o.cell_type
    FROM mv_lncrna_chipseq_overlaps o
    WHERE o.binding_affinity >= :min_ba
    GROUP BY o.mark_name, o.mark_category, o.cell_type
    """

    epigenetic_summary_sql = """
    SELECT
        o.overlap_count as total_overlaps,
        o.mark_name,
        o.mark_category,
        o.cell_type
    FROM mv_lncrna_chipseq_overlaps_epigenetic_summary_ba100 o
    """

    with SessionLocal() as db:
        base_query, LncRNAGene, _TargetGene = _build_regulation_list_query(db)

        escaped = escape_like_pattern(args.lncrna_name)
        like_pattern = f"%{escaped}%"

        q1 = (
            base_query.filter(Regulation.species_id == args.species_id)
            .order_by(desc(Regulation.binding_affinity), Regulation.regulation_id)
            .limit(100)
            .offset(0)
        )
        q2 = (
            base_query.filter(Regulation.species_id == args.species_id)
            .filter(Regulation.target_chromosome == args.chromosome.lower())
            .order_by(desc(Regulation.binding_affinity), Regulation.regulation_id)
            .limit(100)
            .offset(0)
        )
        q3 = (
            base_query.filter(Regulation.species_id == args.species_id)
            .filter(LncRNAGene.gene_name.ilike(like_pattern, escape="\\"))
            .order_by(desc(Regulation.binding_affinity), Regulation.regulation_id)
            .limit(100)
            .offset(0)
        )

        summaries = [
            _summarize(db, f"regulations list: species_id={args.species_id}", _compile_sql(q1)),
            _summarize(
                db,
                f"regulations list: species_id={args.species_id} chr={args.chromosome}",
                _compile_sql(q2),
            ),
            _summarize(
                db,
                f"regulations list: species_id={args.species_id} lncrna_name~{args.lncrna_name}",
                _compile_sql(q3),
            ),
            _summarize(db, "analysis:high_affinity_stats", high_affinity_sql, {"min_ba": args.min_ba}),
            _summarize(db, "analysis:top_lncrnas", top_lncrnas_sql, {"min_ba": args.min_ba}),
            _summarize(db, "analysis:epigenetic_group_by", epigenetic_sql, {"min_ba": args.min_ba}),
        ]

        try:
            summaries.append(_summarize(db, "analysis:epigenetic_summary_mv", epigenetic_summary_sql))
        except Exception as e:
            print(f"[SKIP] analysis:epigenetic_summary_mv: {e}", file=sys.stderr)

    for s in summaries:
        indexes = ", ".join(s.indexes) if s.indexes else "(none)"
        print(f"\n[{s.name}]")
        print(f"execution_ms={s.execution_ms:.3f} planning_ms={s.planning_ms:.3f} actual_rows={s.actual_rows}")
        print(f"indexes={indexes}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
