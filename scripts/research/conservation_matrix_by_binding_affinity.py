#!/usr/bin/env python3
"""
导出跨物种 lncRNA 保守性矩阵（基于 binding_affinity 阈值、按 core_id 聚合）。

目标：
- Phase 6.0「方向 2.2：保守性矩阵与热力图」最小可复现入口
- 输出物种两两共享 lncRNA 数量矩阵 + 行归一化共享率矩阵（CSV + Markdown）
- 可选：若本机安装了 matplotlib，则额外输出热力图 PNG（缺失依赖时跳过，不报错）

口径（以物种集合为单位）：
- 对每个物种 s，定义 L_s = {lncRNA core_id | 存在 regulations 记录满足：
    - regulations.species_id = s
    - regulations.binding_affinity >= min_ba
    - genes.core_id 非空且 core_genes.gene_type = 'lncRNA'
  }
- 共享数量矩阵：M_count[i][j] = |L_i ∩ L_j|
- 行归一化共享率矩阵：M_row_share[i][j] = |L_i ∩ L_j| / |L_i|

依赖：
- 复用后端 SQLAlchemy DB 配置（同 `frontend/backend`）
- 需要可访问 PostgreSQL（环境变量与后端一致：DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD）

示例：
  python3 scripts/research/conservation_matrix_by_binding_affinity.py --species-ids all --min-ba 100 --out-dir docs/reports
  python3 scripts/research/conservation_matrix_by_binding_affinity.py --species-ids 1,3 --min-ba 100 --out-dir docs/reports
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from _report_paths import display_path, resolve_out_dir


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


def _query_lncrna_core_ids_by_species(
    db,
    *,
    species_ids: list[int],
    min_ba: float,
) -> dict[int, set[int]]:
    if not species_ids:
        return {}

    from sqlalchemy import bindparam, text

    stmt = (
        text(
            """
            SELECT DISTINCT
              r.species_id,
              g.core_id AS lncrna_core_id
            FROM regulations r
            JOIN genes g ON g.gene_id = r.lncrna_gene_id
            JOIN core_genes cg ON cg.core_id = g.core_id
            WHERE g.core_id IS NOT NULL
              AND cg.gene_type = 'lncRNA'
              AND r.binding_affinity >= :min_ba
              AND r.species_id IN :species_ids
            """
        )
        .bindparams(bindparam("species_ids", expanding=True))
    )

    rows = db.execute(stmt, {"min_ba": min_ba, "species_ids": species_ids}).mappings().all()

    out: dict[int, set[int]] = {sid: set() for sid in species_ids}
    for r in rows:
        sid = _to_int(r.get("species_id"))
        core_id = _to_int(r.get("lncrna_core_id"))
        if sid is None or core_id is None:
            continue
        if sid not in out:
            out[sid] = set()
        out[sid].add(core_id)

    for sid in species_ids:
        out.setdefault(sid, set())
    return out


def _compute_count_matrix(species_ids: list[int], sets_by_species: dict[int, set[int]]) -> list[list[int]]:
    matrix: list[list[int]] = []
    for sid_i in species_ids:
        row: list[int] = []
        set_i = sets_by_species.get(sid_i, set())
        for sid_j in species_ids:
            set_j = sets_by_species.get(sid_j, set())
            row.append(len(set_i & set_j))
        matrix.append(row)
    return matrix


def _compute_row_share_matrix(
    species_ids: list[int], sets_by_species: dict[int, set[int]], count_matrix: list[list[int]]
) -> list[list[float]]:
    matrix: list[list[float]] = []
    for idx_i, sid_i in enumerate(species_ids):
        denom = len(sets_by_species.get(sid_i, set()))
        row: list[float] = []
        for idx_j, _sid_j in enumerate(species_ids):
            if denom <= 0:
                row.append(0.0)
            else:
                row.append(count_matrix[idx_i][idx_j] / denom)
        matrix.append(row)
    return matrix


def _write_counts_csv(path: Path, *, species_ids: list[int], count_matrix: list[list[int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["species_id", *species_ids])
        for sid, row in zip(species_ids, count_matrix, strict=True):
            writer.writerow([sid, *row])


def _write_row_share_csv(path: Path, *, species_ids: list[int], share_matrix: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["species_id", *species_ids])
        for sid, row in zip(species_ids, share_matrix, strict=True):
            writer.writerow([sid, *[f"{v:.6f}" for v in row]])


def _write_markdown(
    path: Path,
    *,
    species_ids: list[int],
    species_labels: list[str],
    min_ba: float,
    generated_at_utc: str,
    lncrna_counts: dict[int, int],
    counts_csv: Path,
    row_share_csv: Path,
    counts_png: Optional[Path],
    row_share_png: Optional[Path],
    count_matrix: list[list[int]],
    row_share_matrix: list[list[float]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Conservation Matrix (by Binding Affinity)")
    lines.append("")
    lines.append(f"- Species IDs: **{', '.join(str(s) for s in species_ids)}**")
    if species_labels:
        lines.append(f"- Species labels: **{_md_escape(', '.join(species_labels))}**")
    lines.append(f"- Filter: **binding_affinity >= {min_ba}**")
    lines.append(f"- Generated (UTC): **{_md_escape(generated_at_utc)}**")
    lines.append("")
    lines.append("Metric definitions:")
    lines.append("- `L_s`: lncRNA core_id set per species `s` under the filter")
    lines.append("- `count(i,j) = |L_i ∩ L_j|`")
    lines.append("- `row_share(i,j) = |L_i ∩ L_j| / |L_i|`")
    lines.append("")

    lines.append("Outputs:")
    lines.append(f"- Counts CSV: `{display_path(REPO_ROOT, counts_csv)}`")
    lines.append(f"- Row-share CSV: `{display_path(REPO_ROOT, row_share_csv)}`")
    if counts_png is not None:
        lines.append(f"- Counts heatmap (PNG): `{display_path(REPO_ROOT, counts_png)}`")
    else:
        lines.append("- Counts heatmap (PNG): _skipped (matplotlib not available)_")
    if row_share_png is not None:
        lines.append(f"- Row-share heatmap (PNG): `{display_path(REPO_ROOT, row_share_png)}`")
    else:
        lines.append("- Row-share heatmap (PNG): _skipped (matplotlib not available)_")
    lines.append("")

    lines.append("## Per-species lncRNA set size")
    lines.append("")
    lines.append("| species_id | species | lncrna_count |")
    lines.append("|---:|---|---:|")
    label_by_id = {sid: lab for sid, lab in zip(species_ids, species_labels, strict=False)}
    for sid in species_ids:
        label = label_by_id.get(sid, f"species_id={sid}")
        lines.append(f"| {sid} | {_md_escape(label)} | {lncrna_counts.get(sid, 0)} |")
    lines.append("")

    lines.append("## Shared lncRNA count matrix")
    lines.append("")
    lines.append("| species_id | " + " | ".join(str(s) for s in species_ids) + " |")
    lines.append("|---:|" + "|".join(["---:"] * len(species_ids)) + "|")
    for sid, row in zip(species_ids, count_matrix, strict=True):
        lines.append("| {sid} | {vals} |".format(sid=sid, vals=" | ".join(str(v) for v in row)))
    lines.append("")

    lines.append("## Shared lncRNA row-share matrix")
    lines.append("")
    lines.append("| species_id | " + " | ".join(str(s) for s in species_ids) + " |")
    lines.append("|---:|" + "|".join(["---:"] * len(species_ids)) + "|")
    for sid, row in zip(species_ids, row_share_matrix, strict=True):
        lines.append(
            "| {sid} | {vals} |".format(
                sid=sid,
                vals=" | ".join(f"{v:.2%}" for v in row),
            )
        )
    lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _maybe_write_heatmap_png(
    path: Path,
    *,
    title: str,
    species_ids: list[int],
    matrix: list[list[float]],
    fmt: str,
    cmap: str,
) -> Optional[Path]:
    try:
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except Exception:
        return None

    path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(matrix, cmap=cmap)

    ax.set_title(title)
    ax.set_xticks(range(len(species_ids)))
    ax.set_yticks(range(len(species_ids)))
    ax.set_xticklabels([str(s) for s in species_ids])
    ax.set_yticklabels([str(s) for s in species_ids])
    ax.set_xlabel("species_id")
    ax.set_ylabel("species_id")

    for i in range(len(species_ids)):
        for j in range(len(species_ids)):
            ax.text(j, i, format(matrix[i][j], fmt), ha="center", va="center", fontsize=9, color="black")

    fig.colorbar(im, ax=ax, shrink=0.85)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export cross-species conservation matrix grouped by lncRNA core_id.")
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
        "--generated-at",
        type=str,
        default="",
        help="Override 'Generated (UTC)' in Markdown outputs. Empty = use current UTC time.",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="docs/reports",
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

    out_dir = resolve_out_dir(REPO_ROOT, args.out_dir)
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

        sets_by_species = _query_lncrna_core_ids_by_species(db, species_ids=species_ids, min_ba=args.min_ba)
        lncrna_counts = {sid: len(sets_by_species.get(sid, set())) for sid in species_ids}

        count_matrix = _compute_count_matrix(species_ids, sets_by_species)
        row_share_matrix = _compute_row_share_matrix(species_ids, sets_by_species, count_matrix)

        counts_csv = out_dir / f"conservation-matrix-ba{int(args.min_ba)}-species-{group}-counts.csv"
        row_share_csv = out_dir / f"conservation-matrix-ba{int(args.min_ba)}-species-{group}-row-share.csv"
        report_md = out_dir / f"conservation-matrix-ba{int(args.min_ba)}-species-{group}.md"

        _write_counts_csv(counts_csv, species_ids=species_ids, count_matrix=count_matrix)
        _write_row_share_csv(row_share_csv, species_ids=species_ids, share_matrix=row_share_matrix)

        counts_png = _maybe_write_heatmap_png(
            out_dir / f"conservation-matrix-ba{int(args.min_ba)}-species-{group}-counts.png",
            title="Shared lncRNA count",
            species_ids=species_ids,
            matrix=[[float(v) for v in row] for row in count_matrix],
            fmt=",.0f",
            cmap="YlOrRd",
        )
        row_share_png = _maybe_write_heatmap_png(
            out_dir / f"conservation-matrix-ba{int(args.min_ba)}-species-{group}-row-share.png",
            title="Shared lncRNA row-share",
            species_ids=species_ids,
            matrix=row_share_matrix,
            fmt=".2f",
            cmap="Blues",
        )

        _write_markdown(
            report_md,
            species_ids=species_ids,
            species_labels=species_labels,
            min_ba=args.min_ba,
            generated_at_utc=generated_at_utc,
            lncrna_counts=lncrna_counts,
            counts_csv=counts_csv,
            row_share_csv=row_share_csv,
            counts_png=counts_png,
            row_share_png=row_share_png,
            count_matrix=count_matrix,
            row_share_matrix=row_share_matrix,
        )
    finally:
        db.close()

    print(f"Wrote: {display_path(REPO_ROOT, counts_csv)}")
    print(f"Wrote: {display_path(REPO_ROOT, row_share_csv)}")
    if counts_png is not None:
        print(f"Wrote: {display_path(REPO_ROOT, counts_png)}")
    if row_share_png is not None:
        print(f"Wrote: {display_path(REPO_ROOT, row_share_png)}")
    print(f"Wrote: {display_path(REPO_ROOT, report_md)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
