#!/usr/bin/env python3
"""
导出高亲和力（binding_affinity）Top lncRNA 榜单（CSV + Markdown）。

目标：
- Phase 6.0 最小可复现产出：BA>=阈值 的 Top lncRNA（按高 BA 调控条数排序）
- 输出可直接用于论文/汇报的“初筛榜单”，并保留可追溯参数

依赖：
- 复用后端 SQLAlchemy DB 配置（同 `frontend/backend`）
- 需要可访问 PostgreSQL（环境变量与后端一致：DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD）

示例：
  python3 scripts/research/top_lncrna_by_binding_affinity.py --species-id 1 --min-ba 100 --limit 50
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

from sqlalchemy import text  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402


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
    # Escape pipe to keep markdown table stable.
    return text_value.replace("|", "\\|")


@dataclass(frozen=True)
class RowOut:
    lncrna_gene_id: int
    lncrna_gene_name: str
    lncrna_ensembl_id: str
    regulations_count: int
    target_genes_distinct: int
    avg_ba: float
    max_ba: float


def _query_species_label(db, species_id: int) -> str:
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


def _query_top_lncrna(db, *, species_id: int, min_ba: float, limit: int) -> list[RowOut]:
    rows = (
        db.execute(
            text(
                """
                SELECT
                  g.gene_id AS lncrna_gene_id,
                  COALESCE(NULLIF(TRIM(g.gene_name), ''), g.gene_ensembl_id) AS lncrna_gene_name,
                  g.gene_ensembl_id AS lncrna_ensembl_id,
                  COUNT(*) AS regulations_count,
                  COUNT(DISTINCT r.target_gene_id) AS target_genes_distinct,
                  AVG(r.binding_affinity) AS avg_ba,
                  MAX(r.binding_affinity) AS max_ba
                FROM regulations r
                JOIN genes g ON g.gene_id = r.lncrna_gene_id
                LEFT JOIN core_genes cg ON cg.core_id = g.core_id
                WHERE r.species_id = :species_id
                  AND r.binding_affinity >= :min_ba
                  AND (cg.gene_type = 'lncRNA' OR cg.gene_type IS NULL)
                GROUP BY g.gene_id, g.gene_name, g.gene_ensembl_id
                ORDER BY regulations_count DESC, max_ba DESC, avg_ba DESC, g.gene_id ASC
                LIMIT :limit
                """
            ),
            {"species_id": species_id, "min_ba": min_ba, "limit": limit},
        )
        .mappings()
        .all()
    )

    out: list[RowOut] = []
    for r in rows:
        gene_id = _to_int(r.get("lncrna_gene_id"))
        name = str(r.get("lncrna_gene_name") or "").strip()
        ensembl_id = str(r.get("lncrna_ensembl_id") or "").strip()
        regulations_count = _to_int(r.get("regulations_count"))
        target_distinct = _to_int(r.get("target_genes_distinct"))
        avg_ba = _to_float(r.get("avg_ba"))
        max_ba = _to_float(r.get("max_ba"))

        if gene_id is None:
            continue
        if not name:
            name = ensembl_id or str(gene_id)
        if regulations_count is None:
            regulations_count = 0
        if target_distinct is None:
            target_distinct = 0
        if avg_ba is None:
            avg_ba = 0.0
        if max_ba is None:
            max_ba = 0.0

        out.append(
            RowOut(
                lncrna_gene_id=gene_id,
                lncrna_gene_name=name,
                lncrna_ensembl_id=ensembl_id,
                regulations_count=regulations_count,
                target_genes_distinct=target_distinct,
                avg_ba=avg_ba,
                max_ba=max_ba,
            )
        )
    return out


def _write_csv(path: Path, rows: list[RowOut]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "rank",
                "lncrna_gene_id",
                "lncrna_gene_name",
                "lncrna_ensembl_id",
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
                    row.lncrna_gene_id,
                    row.lncrna_gene_name,
                    row.lncrna_ensembl_id,
                    row.regulations_count,
                    row.target_genes_distinct,
                    f"{row.avg_ba:.4f}",
                    f"{row.max_ba:.4f}",
                ]
            )


def _write_markdown(
    path: Path,
    *,
    species_label: str,
    min_ba: float,
    limit: int,
    csv_path: Path,
    rows: list[RowOut],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Top lncRNA by Binding Affinity")
    lines.append("")
    lines.append(f"- Species: {species_label}")
    lines.append(f"- BA threshold: >= {min_ba}")
    lines.append(f"- Limit: {limit}")
    lines.append(f"- Generated (UTC): {_iso_ts()}")
    lines.append("")
    lines.append(f"CSV: `{csv_path}`")
    lines.append("")

    if not rows:
        lines.append("_No rows returned (check DB connection / filters)._")
        lines.append("")
    else:
        lines.append("| rank | lncRNA | ensembl_id | regulations | target_genes | avg_ba | max_ba |")
        lines.append("|---:|---|---|---:|---:|---:|---:|")
        for idx, row in enumerate(rows, start=1):
            lines.append(
                "| {rank} | `{name}` | `{ens}` | {cnt} | {tg} | {avg} | {mx} |".format(
                    rank=idx,
                    name=_md_escape(row.lncrna_gene_name),
                    ens=_md_escape(row.lncrna_ensembl_id or "-"),
                    cnt=row.regulations_count,
                    tg=row.target_genes_distinct,
                    avg=f"{row.avg_ba:.2f}",
                    mx=f"{row.max_ba:.2f}",
                )
            )
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Top lncRNA by binding_affinity (CSV + Markdown).")
    parser.add_argument("--species-id", type=int, default=1, help="Species ID (default: 1).")
    parser.add_argument("--min-ba", type=float, default=100.0, help="Minimum binding affinity (default: 100).")
    parser.add_argument("--limit", type=int, default=50, help="Max rows to export (default: 50).")
    parser.add_argument(
        "--out-dir",
        type=str,
        default=str(REPO_ROOT / "docs" / "reports"),
        help="Output directory (default: docs/reports).",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / f"top-lncrna-ba{int(args.min_ba)}-species{args.species_id}.csv"
    md_path = out_dir / f"top-lncrna-ba{int(args.min_ba)}-species{args.species_id}.md"

    db = SessionLocal()
    try:
        species_label = _query_species_label(db, args.species_id)
        rows = _query_top_lncrna(db, species_id=args.species_id, min_ba=args.min_ba, limit=args.limit)
    finally:
        db.close()

    _write_csv(csv_path, rows)
    _write_markdown(
        md_path,
        species_label=species_label,
        min_ba=args.min_ba,
        limit=args.limit,
        csv_path=csv_path,
        rows=rows,
    )

    print(f"Wrote: {csv_path}")
    print(f"Wrote: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

