#!/usr/bin/env python3
"""
导出高亲和力（binding_affinity）Top lncRNA 的靶基因列表（TSV + TXT + Markdown）。

目标：
- Phase 6.0「靶基因功能富集分析」最小可复现入口：从数据库提取 Top lncRNA 的靶基因集合
- 输出可直接作为 GO/KEGG 等富集工具的输入（TXT），并保留可追溯参数（TSV/MD）

依赖：
- 复用后端 SQLAlchemy DB 配置（同 `frontend/backend`）
- 需要可访问 PostgreSQL（环境变量与后端一致：DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD）

示例：
  python3 scripts/research/top_lncrna_target_genes_for_enrichment.py --species-id 1 --min-ba 100 --top-n 50
  python3 scripts/research/top_lncrna_target_genes_for_enrichment.py --species-id 1 --min-ba 100 --top-n 50 --target-protein-coding-only
  python3 scripts/research/top_lncrna_target_genes_for_enrichment.py --species-ids 1,3 --min-ba 100 --top-n 50
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


@dataclass(frozen=True)
class LncrnaRow:
    lncrna_gene_id: int
    lncrna_gene_name: str
    lncrna_ensembl_id: str
    regulations_count: int
    target_genes_distinct: int
    avg_ba: float
    max_ba: float


@dataclass(frozen=True)
class TargetRow:
    target_gene_id: int
    target_gene_name: str
    target_ensembl_id: str
    target_core_id: Optional[int]
    target_gene_type: str
    target_canonical_symbol: str
    target_human_ensembl_id: str
    regulations_count: int
    lncrna_distinct: int
    avg_ba: float
    max_ba: float


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


def _query_top_lncrna(db, species_id: int, min_ba: float, top_n: int) -> list[LncrnaRow]:
    from sqlalchemy import text

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
            {"species_id": species_id, "min_ba": min_ba, "limit": top_n},
        )
        .mappings()
        .all()
    )

    out: list[LncrnaRow] = []
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

        out.append(
            LncrnaRow(
                lncrna_gene_id=gene_id,
                lncrna_gene_name=name,
                lncrna_ensembl_id=ensembl_id,
                regulations_count=regulations_count or 0,
                target_genes_distinct=target_distinct or 0,
                avg_ba=avg_ba or 0.0,
                max_ba=max_ba or 0.0,
            )
        )
    return out


def _query_target_genes(
    db,
    *,
    species_id: int,
    min_ba: float,
    lncrna_gene_ids: list[int],
    target_protein_coding_only: bool,
) -> list[TargetRow]:
    if not lncrna_gene_ids:
        return []

    from sqlalchemy import bindparam, text

    filters: list[str] = []
    if target_protein_coding_only:
        filters.append("cg.gene_type = 'protein_coding'")

    where_extra = ""
    if filters:
        where_extra = " AND " + " AND ".join(filters)

    stmt = (
        text(
            f"""
            SELECT
              tgt.gene_id AS target_gene_id,
              COALESCE(NULLIF(TRIM(tgt.gene_name), ''), tgt.gene_ensembl_id) AS target_gene_name,
              tgt.gene_ensembl_id AS target_ensembl_id,
              tgt.core_id AS target_core_id,
              COALESCE(cg.gene_type, '') AS target_gene_type,
              COALESCE(cg.canonical_symbol, '') AS target_canonical_symbol,
              COALESCE(cg.human_ensembl_id, '') AS target_human_ensembl_id,
              COUNT(*) AS regulations_count,
              COUNT(DISTINCT r.lncrna_gene_id) AS lncrna_distinct,
              AVG(r.binding_affinity) AS avg_ba,
              MAX(r.binding_affinity) AS max_ba
            FROM regulations r
            JOIN genes tgt ON tgt.gene_id = r.target_gene_id
            LEFT JOIN core_genes cg ON cg.core_id = tgt.core_id
            WHERE r.species_id = :species_id
              AND r.binding_affinity >= :min_ba
              AND r.lncrna_gene_id IN :lncrna_gene_ids
              {where_extra}
            GROUP BY
              tgt.gene_id, tgt.gene_name, tgt.gene_ensembl_id, tgt.core_id,
              cg.gene_type, cg.canonical_symbol, cg.human_ensembl_id
            ORDER BY
              regulations_count DESC,
              lncrna_distinct DESC,
              max_ba DESC,
              avg_ba DESC,
              tgt.gene_id ASC
            """
        )
        .bindparams(bindparam("lncrna_gene_ids", expanding=True))
    )

    rows = (
        db.execute(
            stmt,
            {"species_id": species_id, "min_ba": min_ba, "lncrna_gene_ids": lncrna_gene_ids},
        )
        .mappings()
        .all()
    )

    out: list[TargetRow] = []
    for r in rows:
        gene_id = _to_int(r.get("target_gene_id"))
        if gene_id is None:
            continue

        name = str(r.get("target_gene_name") or "").strip()
        ensembl_id = str(r.get("target_ensembl_id") or "").strip()
        core_id = _to_int(r.get("target_core_id"))

        gene_type = str(r.get("target_gene_type") or "").strip()
        canonical = str(r.get("target_canonical_symbol") or "").strip()
        human_ens = str(r.get("target_human_ensembl_id") or "").strip()

        regulations_count = _to_int(r.get("regulations_count")) or 0
        lncrna_distinct = _to_int(r.get("lncrna_distinct")) or 0
        avg_ba = _to_float(r.get("avg_ba")) or 0.0
        max_ba = _to_float(r.get("max_ba")) or 0.0

        if not name:
            name = canonical or ensembl_id or str(gene_id)

        out.append(
            TargetRow(
                target_gene_id=gene_id,
                target_gene_name=name,
                target_ensembl_id=ensembl_id,
                target_core_id=core_id,
                target_gene_type=gene_type,
                target_canonical_symbol=canonical,
                target_human_ensembl_id=human_ens,
                regulations_count=regulations_count,
                lncrna_distinct=lncrna_distinct,
                avg_ba=avg_ba,
                max_ba=max_ba,
            )
        )
    return out


def _write_tsv(path: Path, rows: list[TargetRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(
            [
                "rank",
                "target_gene_id",
                "target_gene_name",
                "target_ensembl_id",
                "target_core_id",
                "target_gene_type",
                "target_canonical_symbol",
                "target_human_ensembl_id",
                "regulations_count",
                "lncrna_distinct",
                "avg_ba",
                "max_ba",
            ]
        )
        for idx, row in enumerate(rows, start=1):
            writer.writerow(
                [
                    idx,
                    row.target_gene_id,
                    row.target_gene_name,
                    row.target_ensembl_id,
                    row.target_core_id if row.target_core_id is not None else "",
                    row.target_gene_type,
                    row.target_canonical_symbol,
                    row.target_human_ensembl_id,
                    row.regulations_count,
                    row.lncrna_distinct,
                    f"{row.avg_ba:.4f}",
                    f"{row.max_ba:.4f}",
                ]
            )


def _write_txt(path: Path, rows: list[TargetRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for row in rows:
        token = (row.target_canonical_symbol or "").strip() or (row.target_gene_name or "").strip()
        if not token:
            token = (row.target_ensembl_id or "").strip() or str(row.target_gene_id)
        lines.append(token)

    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_markdown(
    path: Path,
    *,
    species_label: str,
    min_ba: float,
    top_n: int,
    target_protein_coding_only: bool,
    lncrnas: list[LncrnaRow],
    tsv_path: Path,
    txt_path: Path,
    targets: list[TargetRow],
    generated_at_utc: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Top lncRNA Target Genes (for Enrichment)")
    lines.append("")
    lines.append(f"- Species: **{_md_escape(species_label)}**")
    lines.append(f"- Filter: **binding_affinity >= {min_ba}**")
    lines.append(f"- Top lncRNAs: **{top_n}**")
    lines.append(f"- Target filter: **{'protein_coding only' if target_protein_coding_only else 'none'}**")
    lines.append(f"- Generated (UTC): **{_md_escape(generated_at_utc)}**")
    lines.append("")
    lines.append(f"- Targets TSV: `{tsv_path}`")
    lines.append(f"- Targets TXT (for enrichment): `{txt_path}`")
    lines.append("")
    lines.append(f"Targets count: **{len(targets)}**")
    lines.append("")

    lines.append("## Included Top lncRNAs")
    lines.append("")
    if not lncrnas:
        lines.append("_No lncRNAs returned (check DB connection / filters)._")
        lines.append("")
    else:
        lines.append("| rank | lncRNA | ensembl_id | regulations | target_genes | avg_ba | max_ba |")
        lines.append("|---:|---|---|---:|---:|---:|---:|")
        for idx, row in enumerate(lncrnas, start=1):
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


def _write_multi_index_markdown(
    path: Path,
    *,
    species_ids: list[int],
    min_ba: float,
    top_n: int,
    target_protein_coding_only: bool,
    outputs: list[tuple[int, str, Path, Path, Path]],
    generated_at_utc: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Top lncRNA Target Genes Index")
    lines.append("")
    lines.append(f"- Species IDs: **{', '.join(str(s) for s in species_ids)}**")
    lines.append(f"- Filter: **binding_affinity >= {min_ba}**")
    lines.append(f"- Top lncRNAs: **{top_n}**")
    lines.append(f"- Target filter: **{'protein_coding only' if target_protein_coding_only else 'none'}**")
    lines.append(f"- Generated (UTC): **{_md_escape(generated_at_utc)}**")
    lines.append("")
    lines.append("| species_id | species | targets_tsv | targets_txt | report |")
    lines.append("|---:|---|---|---|---|")
    for sid, label, tsv_path, txt_path, md_path in outputs:
        lines.append(
            "| {sid} | {label} | `{tsv}` | `{txt}` | `{md}` |".format(
                sid=sid,
                label=_md_escape(label),
                tsv=tsv_path,
                txt=txt_path,
                md=md_path,
            )
        )
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export target genes for enrichment from Top lncRNAs.")
    parser.add_argument("--species-id", type=int, default=1, help="Species ID (default: 1).")
    parser.add_argument(
        "--species-ids",
        type=str,
        default="",
        help="Comma separated species IDs, or 'all'. If set, overrides --species-id.",
    )
    parser.add_argument("--min-ba", type=float, default=100.0, help="Minimum binding affinity (default: 100).")
    parser.add_argument(
        "--top-n",
        "--limit",
        dest="top_n",
        type=int,
        default=50,
        help="Top lncRNAs to include (default: 50). (--limit is an alias)",
    )
    parser.add_argument(
        "--target-protein-coding-only",
        action="store_true",
        help="If set, only keep targets whose core_genes.gene_type='protein_coding'.",
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

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    species_ids: list[int] = []
    outputs: list[tuple[int, str, Path, Path, Path]] = []
    index_md: Optional[Path] = None
    generated_at_utc = (args.generated_at or "").strip() or _iso_ts()

    db = SessionLocal()
    try:
        raw_species_ids = (args.species_ids or "").strip()
        if raw_species_ids:
            if raw_species_ids.lower() in {"all", "*"}:
                species_ids = _query_all_species_ids(db)
                if not species_ids:
                    raise RuntimeError("No species found in DB (species table empty).")
            else:
                species_ids = _parse_species_ids(raw_species_ids)
        else:
            species_ids = [int(args.species_id)]

        for sid in species_ids:
            tsv_path = out_dir / f"top-lncrna-target-genes-ba{int(args.min_ba)}-top{int(args.top_n)}-species{sid}.tsv"
            txt_path = out_dir / f"top-lncrna-target-genes-ba{int(args.min_ba)}-top{int(args.top_n)}-species{sid}.txt"
            md_path = out_dir / f"top-lncrna-target-genes-ba{int(args.min_ba)}-top{int(args.top_n)}-species{sid}.md"

            species_label = _query_species_label(db, sid)
            lncrnas = _query_top_lncrna(db, species_id=sid, min_ba=args.min_ba, top_n=args.top_n)
            lncrna_gene_ids = [r.lncrna_gene_id for r in lncrnas]

            targets = _query_target_genes(
                db,
                species_id=sid,
                min_ba=args.min_ba,
                lncrna_gene_ids=lncrna_gene_ids,
                target_protein_coding_only=bool(args.target_protein_coding_only),
            )

            _write_tsv(tsv_path, targets)
            _write_txt(txt_path, targets)
            _write_markdown(
                md_path,
                species_label=species_label,
                min_ba=args.min_ba,
                top_n=args.top_n,
                target_protein_coding_only=bool(args.target_protein_coding_only),
                lncrnas=lncrnas,
                tsv_path=tsv_path,
                txt_path=txt_path,
                targets=targets,
                generated_at_utc=generated_at_utc,
            )

            outputs.append((sid, species_label, tsv_path, txt_path, md_path))

        if len(species_ids) > 1:
            group = "all" if raw_species_ids.lower() in {"all", "*"} else "-".join(str(s) for s in species_ids)
            index_md = out_dir / f"top-lncrna-target-genes-ba{int(args.min_ba)}-top{int(args.top_n)}-species-{group}.md"
            _write_multi_index_markdown(
                index_md,
                species_ids=species_ids,
                min_ba=args.min_ba,
                top_n=args.top_n,
                target_protein_coding_only=bool(args.target_protein_coding_only),
                outputs=outputs,
                generated_at_utc=generated_at_utc,
            )
    finally:
        db.close()

    for _sid, _label, tsv_path, txt_path, md_path in outputs:
        print(f"Wrote: {tsv_path}")
        print(f"Wrote: {txt_path}")
        print(f"Wrote: {md_path}")
    if index_md is not None:
        print(f"Wrote: {index_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

