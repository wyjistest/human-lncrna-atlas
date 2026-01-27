#!/usr/bin/env python3
"""
导出“保守等级分层（species_count）”对应的靶基因列表（TSV + TXT + Markdown）。

目标：
- Phase 6.0「方向 2.4：功能富集分析」最小可复现入口
- 基于 binding_affinity 阈值，按 lncRNA core_id 聚合，选出指定保守等级（species_count）的 lncRNA 集合
- 汇总这些 lncRNA 的靶基因集合，输出可直接作为 GO/KEGG 等富集工具输入（TXT）
- 同时输出可追溯统计（TSV/MD）

口径（在选择的物种集合 S 内）：
- 对每个 lncRNA core_id，计算 species_count = COUNT(DISTINCT regulations.species_id)（在过滤条件下）
- 选择 species_count == N 的 lncRNA 集合
- 在同样过滤条件下，汇总这些 lncRNA 的 target genes（按 target_gene_id 去重）

依赖：
- 复用后端 SQLAlchemy DB 配置（同 `frontend/backend`）
- 需要可访问 PostgreSQL（环境变量与后端一致：DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD）

示例：
  # 真实数据库
  python3 scripts/research/conserved_lncrna_target_genes_for_enrichment.py --species-ids all --min-ba 100 --species-count 0
  python3 scripts/research/conserved_lncrna_target_genes_for_enrichment.py --species-ids 1,2,3,4 --min-ba 100 --species-count 4 --include-specific
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
        if sid is None or sid <= 0:
            raise ValueError(f"Invalid species id: {part!r}")
        if sid not in out:
            out.append(sid)
    if not out:
        raise ValueError("species-ids is empty after parsing")
    return out


def _query_all_species_ids(db) -> list[int]:
    from sqlalchemy import text

    rows = db.execute(text("SELECT species_id FROM species ORDER BY species_id")).mappings().all()
    out: list[int] = []
    for r in rows:
        sid = _to_int(r.get("species_id"))
        if sid is not None:
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

    display = str(row.get("display_name") or "").strip()
    code = str(row.get("species_code") or "").strip()

    if display:
        return f"{display} (species_id={species_id})"
    if code:
        return f"{code} (species_id={species_id})"
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


def _query_lncrna_core_ids_by_species_count(
    db,
    *,
    species_ids: list[int],
    min_ba: float,
    species_count: int,
) -> list[int]:
    if not species_ids:
        return []

    from sqlalchemy import bindparam, text

    stmt = (
        text(
            """
            SELECT
              g.core_id AS lncrna_core_id
            FROM regulations r
            JOIN genes g ON g.gene_id = r.lncrna_gene_id
            JOIN core_genes cg ON cg.core_id = g.core_id
            WHERE g.core_id IS NOT NULL
              AND cg.gene_type = 'lncRNA'
              AND r.binding_affinity >= :min_ba
              AND r.species_id IN :species_ids
            GROUP BY g.core_id
            HAVING COUNT(DISTINCT r.species_id) = :species_count
            ORDER BY g.core_id ASC
            """
        )
        .bindparams(bindparam("species_ids", expanding=True))
    )

    rows = (
        db.execute(stmt, {"min_ba": min_ba, "species_ids": species_ids, "species_count": species_count})
        .mappings()
        .all()
    )

    out: list[int] = []
    for r in rows:
        core_id = _to_int(r.get("lncrna_core_id"))
        if core_id is not None:
            out.append(core_id)
    return out


@dataclass(frozen=True)
class LncrnaPreviewRow:
    lncrna_core_id: int
    lncrna_name: str
    human_ensembl_id: str
    regulations_count: int
    target_genes_distinct: int
    avg_ba: float
    max_ba: float


def _query_lncrna_preview(
    db,
    *,
    species_ids: list[int],
    min_ba: float,
    species_count: int,
    limit: int,
    human_species_id: Optional[int],
) -> list[LncrnaPreviewRow]:
    if not species_ids or limit <= 0:
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
            HAVING COUNT(DISTINCT r.species_id) = :species_count
            ORDER BY
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
            {
                "min_ba": min_ba,
                "species_ids": species_ids,
                "species_count": species_count,
                "limit": limit,
                "human_species_id": human_sid,
            },
        )
        .mappings()
        .all()
    )

    out: list[LncrnaPreviewRow] = []
    for r in rows:
        core_id = _to_int(r.get("lncrna_core_id"))
        if core_id is None:
            continue

        canonical = str(r.get("canonical_symbol") or "").strip()
        human_name = str(r.get("human_gene_name") or "").strip()
        human_ens = str(r.get("human_ensembl_id") or "").strip()
        name = canonical or human_name or human_ens or str(core_id)

        regulations_count = _to_int(r.get("regulations_count")) or 0
        target_genes_distinct = _to_int(r.get("target_genes_distinct")) or 0
        avg_ba = _to_float(r.get("avg_ba")) or 0.0
        max_ba = _to_float(r.get("max_ba")) or 0.0

        out.append(
            LncrnaPreviewRow(
                lncrna_core_id=core_id,
                lncrna_name=name,
                human_ensembl_id=human_ens,
                regulations_count=regulations_count,
                target_genes_distinct=target_genes_distinct,
                avg_ba=avg_ba,
                max_ba=max_ba,
            )
        )
    return out


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
    lncrna_core_distinct: int
    avg_ba: float
    max_ba: float


def _query_target_genes(
    db,
    *,
    species_ids: list[int],
    min_ba: float,
    lncrna_core_ids: list[int],
    target_protein_coding_only: bool,
) -> list[TargetRow]:
    if not species_ids or not lncrna_core_ids:
        return []

    from sqlalchemy import bindparam, text

    where_extra = ""
    if target_protein_coding_only:
        where_extra = " AND cg.gene_type = 'protein_coding'"

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
              COUNT(DISTINCT lncrna.core_id) AS lncrna_core_distinct,
              AVG(r.binding_affinity) AS avg_ba,
              MAX(r.binding_affinity) AS max_ba
            FROM regulations r
            JOIN genes lncrna ON lncrna.gene_id = r.lncrna_gene_id
            JOIN core_genes lcg ON lcg.core_id = lncrna.core_id
            JOIN genes tgt ON tgt.gene_id = r.target_gene_id
            LEFT JOIN core_genes cg ON cg.core_id = tgt.core_id
            WHERE lncrna.core_id IS NOT NULL
              AND lcg.gene_type = 'lncRNA'
              AND r.binding_affinity >= :min_ba
              AND r.species_id IN :species_ids
              AND lncrna.core_id IN :lncrna_core_ids
              {where_extra}
            GROUP BY
              tgt.gene_id, tgt.gene_name, tgt.gene_ensembl_id, tgt.core_id,
              cg.gene_type, cg.canonical_symbol, cg.human_ensembl_id
            ORDER BY
              regulations_count DESC,
              lncrna_core_distinct DESC,
              max_ba DESC,
              avg_ba DESC,
              tgt.gene_id ASC
            """
        )
        .bindparams(
            bindparam("species_ids", expanding=True),
            bindparam("lncrna_core_ids", expanding=True),
        )
    )

    rows = (
        db.execute(stmt, {"min_ba": min_ba, "species_ids": species_ids, "lncrna_core_ids": lncrna_core_ids})
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
        lncrna_core_distinct = _to_int(r.get("lncrna_core_distinct")) or 0
        avg_ba = _to_float(r.get("avg_ba")) or 0.0
        max_ba = _to_float(r.get("max_ba")) or 0.0

        if not name:
            name = canonical or human_ens or ensembl_id or str(gene_id)

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
                lncrna_core_distinct=lncrna_core_distinct,
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
                "lncrna_core_distinct",
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
                    row.lncrna_core_distinct,
                    f"{row.avg_ba:.4f}",
                    f"{row.max_ba:.4f}",
                ]
            )


def _target_token(row: TargetRow) -> str:
    token = (row.target_canonical_symbol or "").strip()
    if token:
        return token
    token = (row.target_human_ensembl_id or "").strip()
    if token:
        return token
    token = (row.target_gene_name or "").strip()
    if token:
        return token
    token = (row.target_ensembl_id or "").strip()
    if token:
        return token
    return str(row.target_gene_id)


def _write_txt(path: Path, rows: list[TargetRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [_target_token(r) for r in rows if _target_token(r)]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_markdown(
    path: Path,
    *,
    species_ids: list[int],
    species_labels: list[str],
    min_ba: float,
    species_count: int,
    target_protein_coding_only: bool,
    lncrna_count: int,
    lncrna_preview: list[LncrnaPreviewRow],
    tsv_path: Path,
    txt_path: Path,
    targets: list[TargetRow],
    generated_at_utc: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Conserved lncRNA Target Genes (for Enrichment)")
    lines.append("")
    lines.append(f"- Species IDs: **{', '.join(str(s) for s in species_ids)}**")
    if species_labels:
        lines.append(f"- Species labels: **{_md_escape(', '.join(species_labels))}**")
    lines.append(f"- Filter: **binding_affinity >= {min_ba}**")
    lines.append(f"- Conservation level: **species_count == {species_count}**")
    lines.append(
        f"- Target filter: **{'protein_coding only' if target_protein_coding_only else 'none'}**"
    )
    lines.append(f"- Generated (UTC): **{_md_escape(generated_at_utc)}**")
    lines.append("")
    lines.append(f"- Targets TSV: `{tsv_path}`")
    lines.append(f"- Targets TXT (for enrichment): `{txt_path}`")
    lines.append("")
    lines.append(f"Selected lncRNAs (core_id) count: **{lncrna_count}**")
    lines.append(f"Targets count: **{len(targets)}**")
    lines.append("")

    lines.append("## Included lncRNA preview (top by regulations_count)")
    lines.append("")
    if not lncrna_preview:
        lines.append("_No lncRNAs returned (check DB connection / filters)._")
        lines.append("")
    else:
        lines.append("| rank | lncRNA | core_id | regulations | target_genes | avg_ba | max_ba |")
        lines.append("|---:|---|---:|---:|---:|---:|---:|")
        for idx, row in enumerate(lncrna_preview, start=1):
            lines.append(
                "| {rank} | `{name}` | {cid} | {rc} | {tg} | {avg} | {mx} |".format(
                    rank=idx,
                    name=_md_escape(row.lncrna_name),
                    cid=row.lncrna_core_id,
                    rc=row.regulations_count,
                    tg=row.target_genes_distinct,
                    avg=f"{row.avg_ba:.2f}",
                    mx=f"{row.max_ba:.2f}",
                )
            )
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_index_markdown(
    path: Path,
    *,
    species_ids: list[int],
    min_ba: float,
    target_protein_coding_only: bool,
    outputs: list[tuple[int, Path, Path, Path, int, int]],
    generated_at_utc: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Conserved lncRNA Target Genes Index")
    lines.append("")
    lines.append(f"- Species IDs: **{', '.join(str(s) for s in species_ids)}**")
    lines.append(f"- Filter: **binding_affinity >= {min_ba}**")
    lines.append(
        f"- Target filter: **{'protein_coding only' if target_protein_coding_only else 'none'}**"
    )
    lines.append(f"- Generated (UTC): **{_md_escape(generated_at_utc)}**")
    lines.append("")
    lines.append("| species_count | lncrna_count | targets_count | targets_tsv | targets_txt | report |")
    lines.append("|---:|---:|---:|---|---|---|")
    for sc, tsv_path, txt_path, md_path, lncrna_count, targets_count in outputs:
        lines.append(
            "| {sc} | {lc} | {tc} | `{tsv}` | `{txt}` | `{md}` |".format(
                sc=sc,
                lc=lncrna_count,
                tc=targets_count,
                tsv=tsv_path,
                txt=txt_path,
                md=md_path,
            )
        )
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _export_one(
    db,
    *,
    species_ids: list[int],
    species_labels: list[str],
    group: str,
    min_ba: float,
    species_count: int,
    target_protein_coding_only: bool,
    preview_limit: int,
    human_species_id: Optional[int],
    out_dir: Path,
    generated_at_utc: str,
) -> tuple[int, Path, Path, Path, int, int]:
    lncrna_core_ids = _query_lncrna_core_ids_by_species_count(
        db,
        species_ids=species_ids,
        min_ba=min_ba,
        species_count=species_count,
    )
    lncrna_count = len(lncrna_core_ids)

    targets = _query_target_genes(
        db,
        species_ids=species_ids,
        min_ba=min_ba,
        lncrna_core_ids=lncrna_core_ids,
        target_protein_coding_only=target_protein_coding_only,
    )

    suffix = f"ba{int(min_ba)}-sc{species_count}-species-{group}"
    tsv_path = out_dir / f"conserved-lncrna-target-genes-{suffix}.tsv"
    txt_path = out_dir / f"conserved-lncrna-target-genes-{suffix}.txt"
    md_path = out_dir / f"conserved-lncrna-target-genes-{suffix}.md"

    lncrna_preview = _query_lncrna_preview(
        db,
        species_ids=species_ids,
        min_ba=min_ba,
        species_count=species_count,
        limit=preview_limit,
        human_species_id=human_species_id,
    )

    _write_tsv(tsv_path, targets)
    _write_txt(txt_path, targets)
    _write_markdown(
        md_path,
        species_ids=species_ids,
        species_labels=species_labels,
        min_ba=min_ba,
        species_count=species_count,
        target_protein_coding_only=target_protein_coding_only,
        lncrna_count=lncrna_count,
        lncrna_preview=lncrna_preview,
        tsv_path=tsv_path,
        txt_path=txt_path,
        targets=targets,
        generated_at_utc=generated_at_utc,
    )

    return (species_count, tsv_path, txt_path, md_path, lncrna_count, len(targets))


def main() -> int:
    parser = argparse.ArgumentParser(description="Export target genes for enrichment by lncRNA conservation level.")
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
    parser.add_argument(
        "--species-count",
        type=int,
        default=0,
        help="Conservation level (COUNT(DISTINCT species_id)). 0 = use max level (len(species_ids)).",
    )
    parser.add_argument(
        "--include-specific",
        action="store_true",
        help="If set, also export species_count==1 (species-specific) for comparison.",
    )
    parser.add_argument(
        "--target-protein-coding-only",
        action="store_true",
        help="If set, only keep targets whose core_genes.gene_type='protein_coding'.",
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=50,
        help="Top lncRNAs preview rows in Markdown (default: 50).",
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
        max_level = len(species_ids)
        primary_level = int(args.species_count) if int(args.species_count) > 0 else max_level

        levels: list[int] = []
        if primary_level > 0:
            levels.append(primary_level)
        if bool(args.include_specific) and 1 not in levels:
            levels.append(1)

        outputs: list[tuple[int, Path, Path, Path, int, int]] = []
        human_species_id = _query_species_id_by_code(db, "human")

        for level in levels:
            outputs.append(
                _export_one(
                    db,
                    species_ids=species_ids,
                    species_labels=species_labels,
                    group=group,
                    min_ba=args.min_ba,
                    species_count=level,
                    target_protein_coding_only=bool(args.target_protein_coding_only),
                    preview_limit=int(args.preview_limit),
                    human_species_id=human_species_id,
                    out_dir=out_dir,
                    generated_at_utc=generated_at_utc,
                )
            )

        if len(outputs) > 1:
            index_md = out_dir / f"conserved-lncrna-target-genes-ba{int(args.min_ba)}-species-{group}.md"
            _write_index_markdown(
                index_md,
                species_ids=species_ids,
                min_ba=args.min_ba,
                target_protein_coding_only=bool(args.target_protein_coding_only),
                outputs=outputs,
                generated_at_utc=generated_at_utc,
            )
            print(f"Wrote: {index_md}")

    finally:
        db.close()

    for _sc, tsv_path, txt_path, md_path, _lc, _tc in outputs:
        print(f"Wrote: {tsv_path}")
        print(f"Wrote: {txt_path}")
        print(f"Wrote: {md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

