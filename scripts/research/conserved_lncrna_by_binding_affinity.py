#!/usr/bin/env python3
"""
导出跨物种保守 lncRNA 统计（基于 binding_affinity 阈值，按 core_id 聚合）。

目标：
- Phase 6.0「方向 2：跨物种保守性模式分析」最小可复现入口
- 输出保守等级分层统计（species_count 分布）+ Top lncRNA 列表（CSV + Markdown）

依赖：
- 复用后端 SQLAlchemy DB 配置（同 `frontend/backend`）
- 需要可访问 PostgreSQL（环境变量与后端一致：DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD）

示例：
  python3 scripts/research/conserved_lncrna_by_binding_affinity.py --species-ids all --min-ba 100 --limit 50
  python3 scripts/research/conserved_lncrna_by_binding_affinity.py --species-ids 1,3 --min-ba 100 --limit 50
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


def _parse_species_ids(raw_value: str) -> list[int]:
    out: list[int] = []
    for part in raw_value.split(","):
        part = part.strip()
        if not part:
            continue
        sid = _to_int(part)
        if sid is None:
            raise ValueError(f"Invalid species id: {part!r}")
        out.append(sid)
    if not out:
        raise ValueError("species-ids is empty after parsing")
    return out


def _query_all_species_ids(db) -> list[int]:
    from sqlalchemy import text

    rows = (
        db.execute(
            text(
                """
                SELECT species_id
                FROM species
                ORDER BY species_id
                """
            )
        )
        .mappings()
        .all()
    )
    out: list[int] = []
    for r in rows:
        sid = _to_int(r.get("species_id"))
        if sid is None:
            continue
        out.append(sid)
    return out


def _query_species_label(db, species_id: int) -> str:
    from sqlalchemy import text

    row = (
        db.execute(
            text(
                """
                SELECT species_id, display_name, species_code
                FROM species
                WHERE species_id = :species_id
                """
            ),
            {"species_id": species_id},
        )
        .mappings()
        .first()
    )
    if not row:
        return f"species_id={species_id}"
    display = str(row.get("display_name") or row.get("species_code") or "").strip()
    if display:
        return f"{display} (species_id={species_id})"
    return f"species_id={species_id}"


def _query_species_id_by_code(db, species_code: str) -> Optional[int]:
    from sqlalchemy import text

    row = (
        db.execute(
            text(
                """
                SELECT species_id
                FROM species
                WHERE species_code = :species_code
                """
            ),
            {"species_code": species_code},
        )
        .mappings()
        .first()
    )
    return _to_int(row.get("species_id")) if row else None


@dataclass(frozen=True)
class DistributionRow:
    species_count: int
    lncrna_count: int
    total_regulations: int


@dataclass(frozen=True)
class TopRow:
    lncrna_core_id: int
    lncrna_name: str
    human_ensembl_id: str
    species_count: int
    regulations_count: int
    target_genes_distinct: int
    avg_ba: float
    max_ba: float


def _query_distribution(db, *, species_ids: list[int], min_ba: float) -> list[DistributionRow]:
    if not species_ids:
        return []

    from sqlalchemy import bindparam, text

    stmt = (
        text(
            """
            WITH per_species AS (
              SELECT
                g.core_id AS lncrna_core_id,
                r.species_id,
                COUNT(*) AS regulations_count
              FROM regulations r
              JOIN genes g ON g.gene_id = r.lncrna_gene_id
              JOIN core_genes cg ON cg.core_id = g.core_id
              WHERE g.core_id IS NOT NULL
                AND cg.gene_type = 'lncRNA'
                AND r.binding_affinity >= :min_ba
                AND r.species_id IN :species_ids
              GROUP BY g.core_id, r.species_id
            ),
            per_lncrna AS (
              SELECT
                lncrna_core_id,
                COUNT(*) AS species_count,
                SUM(regulations_count) AS regulations_count
              FROM per_species
              GROUP BY lncrna_core_id
            )
            SELECT
              species_count,
              COUNT(*) AS lncrna_count,
              SUM(regulations_count) AS total_regulations
            FROM per_lncrna
            GROUP BY species_count
            ORDER BY species_count DESC
            """
        )
        .bindparams(bindparam("species_ids", expanding=True))
    )

    rows = (
        db.execute(stmt, {"min_ba": min_ba, "species_ids": species_ids})
        .mappings()
        .all()
    )

    out: list[DistributionRow] = []
    for r in rows:
        species_count = _to_int(r.get("species_count"))
        lncrna_count = _to_int(r.get("lncrna_count"))
        total_regulations = _to_int(r.get("total_regulations"))
        if species_count is None:
            continue
        out.append(
            DistributionRow(
                species_count=species_count,
                lncrna_count=lncrna_count or 0,
                total_regulations=total_regulations or 0,
            )
        )
    return out


def _query_top_lncrna(
    db,
    *,
    species_ids: list[int],
    min_ba: float,
    limit: int,
    human_species_id: Optional[int],
) -> list[TopRow]:
    if not species_ids:
        return []

    from sqlalchemy import bindparam, text

    human_sid = human_species_id if human_species_id is not None else -1

    stmt = (
        text(
            """
            SELECT
              g.core_id AS lncrna_core_id,
              COALESCE(NULLIF(TRIM(cg.canonical_symbol), ''), '') AS canonical_symbol,
              COALESCE(NULLIF(TRIM(hg.gene_name), ''), '') AS human_gene_name,
              COALESCE(NULLIF(TRIM(hg.gene_ensembl_id), ''), '') AS human_ensembl_id,
              COUNT(DISTINCT r.species_id) AS species_count,
              COUNT(*) AS regulations_count,
              COUNT(DISTINCT r.target_gene_id) AS target_genes_distinct,
              AVG(r.binding_affinity) AS avg_ba,
              MAX(r.binding_affinity) AS max_ba
            FROM regulations r
            JOIN genes g ON g.gene_id = r.lncrna_gene_id
            JOIN core_genes cg ON cg.core_id = g.core_id
            LEFT JOIN LATERAL (
              SELECT gene_name, gene_ensembl_id
              FROM genes
              WHERE species_id = :human_species_id AND core_id = g.core_id
              ORDER BY gene_id ASC
              LIMIT 1
            ) hg ON TRUE
            WHERE g.core_id IS NOT NULL
              AND cg.gene_type = 'lncRNA'
              AND r.binding_affinity >= :min_ba
              AND r.species_id IN :species_ids
            GROUP BY g.core_id, cg.canonical_symbol, hg.gene_name, hg.gene_ensembl_id
            ORDER BY
              species_count DESC,
              regulations_count DESC,
              max_ba DESC,
              avg_ba DESC,
              g.core_id ASC
            LIMIT :limit
            """
        )
        .bindparams(bindparam("species_ids", expanding=True))
    )

    rows = (
        db.execute(
            stmt,
            {"min_ba": min_ba, "species_ids": species_ids, "limit": limit, "human_species_id": human_sid},
        )
        .mappings()
        .all()
    )

    out: list[TopRow] = []
    for r in rows:
        core_id = _to_int(r.get("lncrna_core_id"))
        if core_id is None:
            continue

        canonical = str(r.get("canonical_symbol") or "").strip()
        human_name = str(r.get("human_gene_name") or "").strip()
        human_ens = str(r.get("human_ensembl_id") or "").strip()

        name = canonical or human_name or human_ens or str(core_id)
        species_count = _to_int(r.get("species_count")) or 0
        regulations_count = _to_int(r.get("regulations_count")) or 0
        target_distinct = _to_int(r.get("target_genes_distinct")) or 0
        avg_ba = _to_float(r.get("avg_ba")) or 0.0
        max_ba = _to_float(r.get("max_ba")) or 0.0

        out.append(
            TopRow(
                lncrna_core_id=core_id,
                lncrna_name=name,
                human_ensembl_id=human_ens,
                species_count=species_count,
                regulations_count=regulations_count,
                target_genes_distinct=target_distinct,
                avg_ba=avg_ba,
                max_ba=max_ba,
            )
        )
    return out


def _write_csv(path: Path, rows: list[TopRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "rank",
                "lncrna_core_id",
                "lncrna_name",
                "human_ensembl_id",
                "species_count",
                "regulations_count",
                "target_genes_distinct",
                "avg_ba",
                "max_ba",
            ]
        )
        for idx, row in enumerate(rows, start=1):
            writer.writerow(
                [
                    idx,
                    row.lncrna_core_id,
                    row.lncrna_name,
                    row.human_ensembl_id,
                    row.species_count,
                    row.regulations_count,
                    row.target_genes_distinct,
                    f"{row.avg_ba:.4f}",
                    f"{row.max_ba:.4f}",
                ]
            )


def _write_markdown(
    path: Path,
    *,
    species_labels: list[str],
    species_ids: list[int],
    min_ba: float,
    limit: int,
    csv_path: Path,
    distribution: list[DistributionRow],
    top_rows: list[TopRow],
    generated_at_utc: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Conserved lncRNAs (by Binding Affinity)")
    lines.append("")
    lines.append(f"- Species IDs: **{', '.join(str(s) for s in species_ids)}**")
    if species_labels:
        lines.append(f"- Species labels: **{_md_escape(', '.join(species_labels))}**")
    lines.append(f"- Filter: **binding_affinity >= {min_ba}**")
    lines.append(f"- Top limit: **{limit}**")
    lines.append(f"- Generated (UTC): **{_md_escape(generated_at_utc)}**")
    lines.append("")
    lines.append(f"- Top list CSV: `{csv_path}`")
    lines.append("")

    lines.append("## Conservation Level Distribution")
    lines.append("")
    if not distribution:
        lines.append("_No rows returned (check DB connection / filters)._")
        lines.append("")
    else:
        total_lncrnas = sum(r.lncrna_count for r in distribution) or 0
        lines.append("| species_count | lncrna_count | share | total_regulations |")
        lines.append("|---:|---:|---:|---:|")
        for r in distribution:
            share = (r.lncrna_count / total_lncrnas) if total_lncrnas else 0.0
            lines.append(
                "| {sc} | {cnt} | {share} | {regs} |".format(
                    sc=r.species_count,
                    cnt=r.lncrna_count,
                    share=f"{share:.2%}",
                    regs=r.total_regulations,
                )
            )
        lines.append("")

    lines.append("## Top lncRNAs")
    lines.append("")
    if not top_rows:
        lines.append("_No rows returned (check DB connection / filters)._")
        lines.append("")
    else:
        lines.append("| rank | lncRNA | core_id | species_count | regulations | target_genes | avg_ba | max_ba |")
        lines.append("|---:|---|---:|---:|---:|---:|---:|---:|")
        for idx, row in enumerate(top_rows, start=1):
            lines.append(
                "| {rank} | `{name}` | {cid} | {sc} | {rc} | {tg} | {avg} | {mx} |".format(
                    rank=idx,
                    name=_md_escape(row.lncrna_name),
                    cid=row.lncrna_core_id,
                    sc=row.species_count,
                    rc=row.regulations_count,
                    tg=row.target_genes_distinct,
                    avg=f"{row.avg_ba:.2f}",
                    mx=f"{row.max_ba:.2f}",
                )
            )
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export conserved lncRNA stats grouped by core_id.")
    parser.add_argument(
        "--species-id",
        type=int,
        default=1,
        help="Single species ID (default: 1). Only used when --species-ids is empty.",
    )
    parser.add_argument(
        "--species-ids",
        type=str,
        default="all",
        help="Comma separated species IDs, or 'all'. Default: all.",
    )
    parser.add_argument("--min-ba", type=float, default=100.0, help="Minimum binding affinity (default: 100).")
    parser.add_argument("--limit", type=int, default=50, help="Top rows to export (default: 50).")
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

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    generated_at_utc = (args.generated_at or "").strip() or _iso_ts()

    db = SessionLocal()
    try:
        raw_species_ids = (args.species_ids or "").strip()
        if raw_species_ids:
            if raw_species_ids.lower() in {"all", "*"}:
                species_ids = _query_all_species_ids(db)
                if not species_ids:
                    raise RuntimeError("No species found in DB (species table empty).")
                group = "all"
            else:
                species_ids = _parse_species_ids(raw_species_ids)
                group = "-".join(str(s) for s in species_ids)
        else:
            species_ids = [int(args.species_id)]
            group = str(args.species_id)

        species_labels = [_query_species_label(db, sid) for sid in species_ids]
        human_species_id = _query_species_id_by_code(db, "human")

        distribution = _query_distribution(db, species_ids=species_ids, min_ba=args.min_ba)
        top_rows = _query_top_lncrna(
            db,
            species_ids=species_ids,
            min_ba=args.min_ba,
            limit=args.limit,
            human_species_id=human_species_id,
        )

        csv_path = out_dir / f"conserved-lncrna-ba{int(args.min_ba)}-top{int(args.limit)}-species-{group}.csv"
        md_path = out_dir / f"conserved-lncrna-ba{int(args.min_ba)}-top{int(args.limit)}-species-{group}.md"

        _write_csv(csv_path, top_rows)
        _write_markdown(
            md_path,
            species_labels=species_labels,
            species_ids=species_ids,
            min_ba=args.min_ba,
            limit=args.limit,
            csv_path=csv_path,
            distribution=distribution,
            top_rows=top_rows,
            generated_at_utc=generated_at_utc,
        )
    finally:
        db.close()

    print(f"Wrote: {csv_path}")
    print(f"Wrote: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

