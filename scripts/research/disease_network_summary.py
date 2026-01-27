#!/usr/bin/env python3
"""
导出疾病（traits）关联网络的统计汇总（TSV + Markdown）。

目标：
- Phase 6.0「方向 4：疾病关联网络分析」最小可复现入口
- 基于 trait_gene_associations（core_id 口径）输出：
  - 全局统计：疾病数/基因数/lncRNA 数/平均连接数
  - Top diseases（按关联 lncRNA 数排序）
  - Top lncRNAs（按关联疾病数排序）

依赖：
- 复用后端 SQLAlchemy DB 配置（同 `frontend/backend`）
- 需要可访问 PostgreSQL（环境变量与后端一致：DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD）

示例：
  python3 scripts/research/disease_network_summary.py --evidence-species-id 1 --top-traits 50 --top-lncrnas 50
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


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
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
class TraitTopRow:
    trait_id: int
    trait_name: str
    trait_category: str
    lncrna_count: int
    gene_count: int
    ontology_count: int


@dataclass(frozen=True)
class LncrnaTopRow:
    core_id: int
    canonical_symbol: str
    human_ensembl_id: str
    trait_count: int
    ontology_count: int


def _write_tsv(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def _fmt_pct(part: int, total: int) -> str:
    if total <= 0:
        return "0.00%"
    return f"{(100.0 * float(part) / float(total)):.2f}%"


def _evidence_filter_sql(evidence_species_id: Optional[int]) -> tuple[str, dict[str, Any]]:
    if evidence_species_id is None:
        return ("", {})
    return ("WHERE tga.evidence_species_id = :evidence_species_id", {"evidence_species_id": evidence_species_id})


def _query_summary(db, *, evidence_species_id: Optional[int]) -> tuple[dict[str, Any], Optional[str]]:
    from sqlalchemy import text

    where_sql, params = _evidence_filter_sql(evidence_species_id)

    stats_sql = text(
        f"""
        SELECT
          COUNT(*) AS total_associations,
          COUNT(DISTINCT tga.trait_id) AS total_diseases,
          COUNT(DISTINCT tga.core_id) AS total_genes,
          COUNT(DISTINCT tga.core_id) FILTER (WHERE cg.gene_type = 'lncRNA') AS total_lncrnas
        FROM trait_gene_associations tga
        JOIN core_genes cg ON tga.core_id = cg.core_id
        {where_sql}
        """
    )

    avg_connections_sql = text(
        f"""
        SELECT AVG(connection_count) AS avg_connections
        FROM (
            SELECT
              tga.trait_id,
              COUNT(DISTINCT tga.core_id) AS connection_count
            FROM trait_gene_associations tga
            {where_sql}
            GROUP BY tga.trait_id
        ) per_trait
        """
    )

    try:
        stats_row = db.execute(stats_sql, params).mappings().first()
        avg_row = db.execute(avg_connections_sql, params).mappings().first()
    except Exception as e:
        return ({}, _safe_error(e))

    avg_connections = _to_float(avg_row.get("avg_connections")) if avg_row else None
    out = {
        "total_associations": _to_int(stats_row.get("total_associations")) if stats_row else 0,
        "total_diseases": _to_int(stats_row.get("total_diseases")) if stats_row else 0,
        "total_genes": _to_int(stats_row.get("total_genes")) if stats_row else 0,
        "total_lncrnas": _to_int(stats_row.get("total_lncrnas")) if stats_row else 0,
        "avg_connections": float(avg_connections) if avg_connections is not None else 0.0,
    }
    return (out, None)


def _query_top_traits(
    db,
    *,
    evidence_species_id: Optional[int],
    limit: int,
) -> tuple[list[TraitTopRow], Optional[str]]:
    from sqlalchemy import text

    where_sql, params = _evidence_filter_sql(evidence_species_id)
    params["limit"] = limit

    sql = text(
        f"""
        SELECT
          t.trait_id,
          t.trait_name,
          COALESCE(NULLIF(TRIM(t.trait_category), ''), '') AS trait_category,
          COUNT(DISTINCT tga.core_id) FILTER (WHERE cg.gene_type = 'lncRNA') AS lncrna_count,
          COUNT(DISTINCT tga.core_id) AS gene_count,
          COUNT(DISTINCT tga.ontology_id) AS ontology_count
        FROM trait_gene_associations tga
        JOIN traits t ON tga.trait_id = t.trait_id
        JOIN core_genes cg ON tga.core_id = cg.core_id
        {where_sql}
        GROUP BY t.trait_id, t.trait_name, t.trait_category
        ORDER BY lncrna_count DESC, gene_count DESC, t.trait_id ASC
        LIMIT :limit
        """
    )

    try:
        rows = db.execute(sql, params).mappings().all()
    except Exception as e:
        return ([], _safe_error(e))

    out: list[TraitTopRow] = []
    for r in rows:
        out.append(
            TraitTopRow(
                trait_id=_to_int(r.get("trait_id")) or 0,
                trait_name=str(r.get("trait_name") or "").strip(),
                trait_category=str(r.get("trait_category") or "").strip(),
                lncrna_count=_to_int(r.get("lncrna_count")) or 0,
                gene_count=_to_int(r.get("gene_count")) or 0,
                ontology_count=_to_int(r.get("ontology_count")) or 0,
            )
        )
    return (out, None)


def _query_top_lncrnas(
    db,
    *,
    evidence_species_id: Optional[int],
    limit: int,
) -> tuple[list[LncrnaTopRow], Optional[str]]:
    from sqlalchemy import text

    where_sql, params = _evidence_filter_sql(evidence_species_id)
    params["limit"] = limit

    sql = text(
        f"""
        SELECT
          cg.core_id,
          COALESCE(NULLIF(TRIM(cg.canonical_symbol), ''), '') AS canonical_symbol,
          COALESCE(NULLIF(TRIM(cg.human_ensembl_id), ''), '') AS human_ensembl_id,
          COUNT(DISTINCT tga.trait_id) AS trait_count,
          COUNT(DISTINCT tga.ontology_id) AS ontology_count
        FROM trait_gene_associations tga
        JOIN core_genes cg ON tga.core_id = cg.core_id
        {where_sql}
          {"AND" if where_sql else "WHERE"} cg.gene_type = 'lncRNA'
        GROUP BY cg.core_id, cg.canonical_symbol, cg.human_ensembl_id
        ORDER BY trait_count DESC, ontology_count DESC, cg.core_id ASC
        LIMIT :limit
        """
    )

    try:
        rows = db.execute(sql, params).mappings().all()
    except Exception as e:
        return ([], _safe_error(e))

    out: list[LncrnaTopRow] = []
    for r in rows:
        out.append(
            LncrnaTopRow(
                core_id=_to_int(r.get("core_id")) or 0,
                canonical_symbol=str(r.get("canonical_symbol") or "").strip(),
                human_ensembl_id=str(r.get("human_ensembl_id") or "").strip(),
                trait_count=_to_int(r.get("trait_count")) or 0,
                ontology_count=_to_int(r.get("ontology_count")) or 0,
            )
        )
    return (out, None)


def _write_markdown(
    path: Path,
    *,
    evidence_species_id: Optional[int],
    summary: dict[str, Any],
    warning: Optional[str],
    traits_tsv: Path,
    lncrnas_tsv: Path,
    top_traits: list[TraitTopRow],
    top_lncrnas: list[LncrnaTopRow],
    generated_at_utc: str,
    preview_limit: int,
) -> None:
    evidence_token = str(evidence_species_id) if evidence_species_id is not None else "all"
    total_diseases = int(summary.get("total_diseases") or 0)
    total_lncrnas = int(summary.get("total_lncrnas") or 0)
    total_genes = int(summary.get("total_genes") or 0)
    total_associations = int(summary.get("total_associations") or 0)
    avg_connections = float(summary.get("avg_connections") or 0.0)

    lines: list[str] = []
    lines.append("# Disease Network Summary (traits × genes)")
    lines.append("")
    lines.append(f"- Generated (UTC): `{generated_at_utc}`")
    lines.append(f"- evidence_species_id: `{evidence_token}`")
    if warning:
        lines.append(f"- Warning: `{warning}`")
    lines.append(f"- Total diseases: `{total_diseases}`")
    lines.append(f"- Total genes: `{total_genes}`")
    lines.append(f"- Total lncRNAs: `{total_lncrnas}`")
    lines.append(f"- Total associations: `{total_associations}`")
    lines.append(f"- Avg connections per disease: `{avg_connections:.2f}`")
    lines.append("")
    lines.append(f"- Top diseases TSV: `{traits_tsv}`")
    lines.append(f"- Top lncRNAs TSV: `{lncrnas_tsv}`")

    traits_preview = top_traits[: max(0, preview_limit)]
    lncrnas_preview = top_lncrnas[: max(0, preview_limit)]

    lines.append("")
    lines.append(f"## Top diseases (Top {len(traits_preview)})")
    lines.append("")
    lines.append("| Rank | Trait | Category | lncRNAs | Genes | Ontologies |")
    lines.append("|---:|---|---|---:|---:|---:|")
    for i, r in enumerate(traits_preview, start=1):
        name = _md_escape(r.trait_name or f"trait_id={r.trait_id}")
        category = _md_escape(r.trait_category or "")
        lines.append(f"| {i} | {name} | {category} | {r.lncrna_count} | {r.gene_count} | {r.ontology_count} |")

    lines.append("")
    lines.append(f"## Top lncRNAs (Top {len(lncrnas_preview)})")
    lines.append("")
    lines.append("| Rank | lncRNA (core) | Human Ensembl | Diseases | Ontologies |")
    lines.append("|---:|---|---|---:|---:|")
    for i, r in enumerate(lncrnas_preview, start=1):
        symbol = _md_escape(r.canonical_symbol or f"core_id={r.core_id}")
        human = _md_escape(r.human_ensembl_id or "")
        lines.append(f"| {i} | {symbol} | {human} | {r.trait_count} | {r.ontology_count} |")

    if total_associations == 0:
        lines.append("")
        lines.append("## Notes")
        lines.append("")
        lines.append("- 若你期望看到非空结果：请确认已导入 trait/ontology/trait_gene_associations 数据。")
        lines.append("- 参考：`schema/v2.3/01_core.sql`（traits/ontologies/trait_gene_associations）")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export disease network summary from trait_gene_associations.")
    parser.add_argument(
        "--evidence-species-id",
        type=int,
        default=1,
        help="Filter by trait_gene_associations.evidence_species_id. 0 = all (no filter). Default: 1.",
    )
    parser.add_argument(
        "--top-traits",
        type=int,
        default=50,
        help="Top traits rows in TSV/Markdown (default: 50).",
    )
    parser.add_argument(
        "--top-lncrnas",
        type=int,
        default=50,
        help="Top lncRNAs rows in TSV/Markdown (default: 50).",
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=20,
        help="Preview rows in Markdown tables (default: 20).",
    )
    parser.add_argument(
        "--generated-at",
        type=str,
        default="",
        help="Override 'Generated (UTC)' in Markdown outputs. Empty = use current UTC time.",
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

    evidence_species_id = int(args.evidence_species_id)
    evidence_filter: Optional[int] = None if evidence_species_id <= 0 else evidence_species_id
    evidence_token = str(evidence_filter) if evidence_filter is not None else "all"

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_at_utc = (args.generated_at or "").strip() or _iso_ts()

    traits_limit = max(0, int(args.top_traits))
    lncrnas_limit = max(0, int(args.top_lncrnas))
    preview_limit = max(0, int(args.preview_limit))

    traits_tsv = out_dir / f"disease-network-traits-evidence-{evidence_token}.tsv"
    lncrnas_tsv = out_dir / f"disease-network-lncrnas-evidence-{evidence_token}.tsv"
    md_path = out_dir / f"disease-network-summary-evidence-{evidence_token}.md"

    db = SessionLocal()
    try:
        summary, warn1 = _query_summary(db, evidence_species_id=evidence_filter)
        top_traits, warn2 = _query_top_traits(db, evidence_species_id=evidence_filter, limit=traits_limit)
        top_lncrnas, warn3 = _query_top_lncrnas(db, evidence_species_id=evidence_filter, limit=lncrnas_limit)

        warning = next((w for w in [warn1, warn2, warn3] if w), None)

        _write_tsv(
            traits_tsv,
            ["trait_id", "trait_name", "trait_category", "lncrna_count", "gene_count", "ontology_count"],
            [
                [r.trait_id, r.trait_name, r.trait_category, r.lncrna_count, r.gene_count, r.ontology_count]
                for r in top_traits
            ],
        )
        _write_tsv(
            lncrnas_tsv,
            ["core_id", "canonical_symbol", "human_ensembl_id", "trait_count", "ontology_count"],
            [[r.core_id, r.canonical_symbol, r.human_ensembl_id, r.trait_count, r.ontology_count] for r in top_lncrnas],
        )
        _write_markdown(
            md_path,
            evidence_species_id=evidence_filter,
            summary=summary,
            warning=warning,
            traits_tsv=traits_tsv,
            lncrnas_tsv=lncrnas_tsv,
            top_traits=top_traits,
            top_lncrnas=top_lncrnas,
            generated_at_utc=generated_at_utc,
            preview_limit=preview_limit,
        )
    finally:
        db.close()

    print(f"Wrote: {traits_tsv}")
    print(f"Wrote: {lncrnas_tsv}")
    print(f"Wrote: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

