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
    --gene-id 18917
    --diseases-search diabetes
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


def _normalize_optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def main() -> int:
    parser = argparse.ArgumentParser(description="EXPLAIN hot queries for Human LncRNA Atlas backend")
    parser.add_argument("--species-id", type=int, default=1, help="Regulations list: species_id filter (default: 1)")
    parser.add_argument("--chromosome", type=str, default="chr1", help="Regulations list: target chromosome (default: chr1)")
    parser.add_argument("--lncrna-name", type=str, default="MALAT1", help="Regulations list: lncRNA gene_name fuzzy match")
    parser.add_argument("--gene-id", type=int, default=None, help="Network queries: gene_id (default: auto by --lncrna-name)")
    parser.add_argument("--diseases-search", type=str, default=None, help="Diseases list: search keyword (default: none)")
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

    high_affinity_stats_mv_sql = """
    SELECT
        total_regulations,
        unique_lncrnas,
        unique_targets,
        avg_ba,
        max_ba
    FROM mv_analysis_high_affinity_stats_ba100
    """

    top_lncrnas_mv_sql = """
    SELECT
        lncrna_name,
        target_count,
        avg_ba
    FROM mv_analysis_top_lncrnas_ba100
    ORDER BY row_num
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

    network_gene_stats_sql = """
    SELECT
        COUNT(*) FILTER (WHERE lncrna_gene_id = :gene_id) as as_source_count,
        COUNT(*) FILTER (WHERE target_gene_id = :gene_id) as as_target_count,
        SUM(binding_affinity) as total_ba
    FROM regulations
    WHERE lncrna_gene_id = :gene_id OR target_gene_id = :gene_id
    """

    network_gene_edges_sql = """
    SELECT
        regulation_id,
        lncrna_gene_id,
        target_gene_id,
        binding_affinity
    FROM regulations
    WHERE lncrna_gene_id = :gene_id OR target_gene_id = :gene_id
    ORDER BY binding_affinity DESC, regulation_id
    LIMIT :limit
    """

    genes_name_ilike_sql = """
    SELECT gene_id
    FROM genes
    WHERE gene_name ILIKE :pattern
    ORDER BY gene_id
    LIMIT 20
    """

    diseases_count_sql = """
    SELECT COUNT(*)
    FROM (
        SELECT DISTINCT
            t.trait_id,
            o.ontology_id,
            tga.evidence_species_id
        FROM traits t
        JOIN trait_gene_associations tga ON t.trait_id = tga.trait_id
        JOIN ontologies o ON tga.ontology_id = o.ontology_id
        JOIN core_genes cg ON tga.core_id = cg.core_id
        WHERE (
            :search_pattern IS NULL
            OR t.trait_name ILIKE :search_pattern
            OR o.ontology_name ILIKE :search_pattern
        )
    ) combos
    """

    diseases_page_sql = """
    SELECT
        t.trait_id,
        t.trait_name,
        t.trait_category,
        t.trait_doid,
        o.ontology_id,
        o.ontology_name,
        o.ontology_cl_id,
        tga.evidence_species_id,
        s.display_name AS species_name,
        COUNT(DISTINCT tga.core_id) AS gene_count,
        COUNT(DISTINCT CASE WHEN cg.gene_type = 'lncRNA' THEN tga.core_id END) AS lncrna_count
    FROM traits t
    JOIN trait_gene_associations tga ON t.trait_id = tga.trait_id
    JOIN ontologies o ON tga.ontology_id = o.ontology_id
    JOIN core_genes cg ON tga.core_id = cg.core_id
    LEFT JOIN species s ON tga.evidence_species_id = s.species_id
    WHERE (
        :search_pattern IS NULL
        OR t.trait_name ILIKE :search_pattern
        OR o.ontology_name ILIKE :search_pattern
    )
    GROUP BY
        t.trait_id,
        t.trait_name,
        t.trait_category,
        t.trait_doid,
        o.ontology_id,
        o.ontology_name,
        o.ontology_cl_id,
        tga.evidence_species_id,
        s.display_name
    ORDER BY t.trait_id, o.ontology_id
    LIMIT :limit
    OFFSET :offset
    """

    export_chipseq_overlaps_sql = """
    SELECT
        o.regulation_id,
        o.lncrna_name as lncrna_name,
        o.target_gene_name as target_name,
        o.binding_affinity,
        o.mark_name,
        o.fold_enrichment as peak_score,
        o.chromosome as peak_chr,
        o.peak_start,
        o.peak_end,
        o.cell_type
    FROM mv_lncrna_chipseq_overlaps o
    WHERE o.mark_name = ANY(:mark_names)
      AND o.binding_affinity >= :min_ba
    ORDER BY o.binding_affinity DESC, o.fold_enrichment DESC
    LIMIT :limit
    """

    with SessionLocal() as db:
        base_query, LncRNAGene, _TargetGene = _build_regulation_list_query(db)

        escaped = escape_like_pattern(args.lncrna_name)
        like_pattern = f"%{escaped}%"
        diseases_search = _normalize_optional_str(args.diseases_search)
        diseases_search_pattern = f"%{escape_like_pattern(diseases_search)}%" if diseases_search else None

        # Pick a representative gene_id for network queries.
        gene_id = args.gene_id
        if gene_id is None:
            gene_id = db.execute(
                text(
                    """
                    SELECT gene_id
                    FROM genes
                    WHERE gene_name = :gene_name AND species_id = :species_id
                    ORDER BY gene_id
                    LIMIT 1
                    """
                ),
                {"gene_name": args.lncrna_name, "species_id": args.species_id},
            ).scalar()

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

        summaries: list[ExplainSummary] = []

        def add_summary(
            name: str,
            sql: str,
            params: dict[str, Any] | None = None,
            *,
            required: bool = False,
        ) -> None:
            try:
                summaries.append(_summarize(db, name, sql, params))
            except Exception as e:
                db.rollback()
                if required:
                    raise
                print(f"[SKIP] {name}: {e}", file=sys.stderr)

        add_summary(f"regulations list: species_id={args.species_id}", _compile_sql(q1), required=True)
        add_summary(
            f"regulations list: species_id={args.species_id} chr={args.chromosome}",
            _compile_sql(q2),
            required=True,
        )
        add_summary(
            f"regulations list: species_id={args.species_id} lncrna_name~{args.lncrna_name}",
            _compile_sql(q3),
            required=True,
        )
        add_summary("analysis:high_affinity_stats", high_affinity_sql, {"min_ba": args.min_ba}, required=True)
        add_summary("analysis:top_lncrnas", top_lncrnas_sql, {"min_ba": args.min_ba}, required=True)

        add_summary("analysis:high_affinity_stats_mv", high_affinity_stats_mv_sql)
        add_summary("analysis:top_lncrnas_mv", top_lncrnas_mv_sql)

        add_summary("analysis:epigenetic_group_by", epigenetic_sql, {"min_ba": args.min_ba})
        add_summary("analysis:epigenetic_summary_mv", epigenetic_summary_sql)
        add_summary("genes:gene_name_ilike", genes_name_ilike_sql, {"pattern": like_pattern})

        if gene_id:
            add_summary(f"network:gene_stats gene_id={gene_id}", network_gene_stats_sql, {"gene_id": gene_id})
            add_summary(
                f"network:gene_edges_top500 gene_id={gene_id}",
                network_gene_edges_sql,
                {"gene_id": gene_id, "limit": 500},
            )
        else:
            print("[SKIP] network:* (no gene_id found)", file=sys.stderr)

        add_summary("diseases:list_count_distinct", diseases_count_sql, {"search_pattern": diseases_search_pattern})
        add_summary(
            "diseases:list_page_group_by",
            diseases_page_sql,
            {"search_pattern": diseases_search_pattern, "limit": 100, "offset": 0},
        )

        try:
            mark_names = (
                db.execute(text("SELECT DISTINCT mark_name FROM mv_lncrna_chipseq_overlaps LIMIT 2"))
                .scalars()
                .all()
            )
        except Exception as e:
            db.rollback()
            mark_names = []
            print(f"[SKIP] export:chipseq_overlaps_mv (mark_name discovery failed): {e}", file=sys.stderr)

        if mark_names:
            add_summary(
                "export:chipseq_overlaps_mv",
                export_chipseq_overlaps_sql,
                {"mark_names": mark_names, "min_ba": args.min_ba, "limit": 10000},
            )

    for s in summaries:
        indexes = ", ".join(s.indexes) if s.indexes else "(none)"
        print(f"\n[{s.name}]")
        print(f"execution_ms={s.execution_ms:.3f} planning_ms={s.planning_ms:.3f} actual_rows={s.actual_rows}")
        print(f"indexes={indexes}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
