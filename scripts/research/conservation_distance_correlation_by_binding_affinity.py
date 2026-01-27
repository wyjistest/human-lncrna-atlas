#!/usr/bin/env python3
"""
导出「进化距离 vs 保守性」相关性报告（基于 binding_affinity 阈值、按 core_id 聚合）。

目标：
- Phase 6.0「方向 2.3：进化距离与保守性相关性」最小可复现入口
- 输出物种两两的共享指标（CSV + Markdown）
- 计算 Pearson / Spearman 相关系数（不依赖 scipy）
- 可选：若本机安装了 matplotlib，则额外输出散点图 PNG（缺失依赖时跳过，不报错）

口径（以物种集合为单位）：
- 对每个物种 s，定义 L_s = {lncRNA core_id | 存在 regulations 记录满足：
    - regulations.species_id = s
    - regulations.binding_affinity >= min_ba
    - genes.core_id 非空且 core_genes.gene_type = 'lncRNA'
  }
- 对每个物种对 (i, j)，计算：
    - intersection = |L_i ∩ L_j|
    - union = |L_i ∪ L_j|
    - jaccard = intersection / union
    - overlap_min = intersection / min(|L_i|, |L_j|)
    - avg_row_share = 0.5 * (intersection/|L_i| + intersection/|L_j|)

进化距离：
- 默认内置 4 种灵长类（human/chimp/macaque/marmoset）的近似分歧时间（Mya）。
- 若你的 species_code 不在默认映射中，请用 --distances-json 覆盖。

依赖：
- 复用后端 SQLAlchemy DB 配置（同 `frontend/backend`）
- 需要可访问 PostgreSQL（环境变量与后端一致：DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD）

示例：
  python3 scripts/research/conservation_distance_correlation_by_binding_affinity.py \
    --species-ids all --min-ba 100 --out-dir docs/reports
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "frontend" / "backend"
sys.path.insert(0, str(BACKEND_DIR))


DEFAULT_DISTANCES_MYA: dict[tuple[str, str], float] = {
    ("chimp", "human"): 6.0,
    ("human", "macaque"): 25.0,
    ("human", "marmoset"): 40.0,
    ("chimp", "macaque"): 25.0,
    ("chimp", "marmoset"): 40.0,
    ("macaque", "marmoset"): 40.0,
}


@dataclass(frozen=True)
class SpeciesInfo:
    species_id: int
    species_code: str
    display_name: str

    @property
    def label(self) -> str:
        display = self.display_name.strip()
        code = self.species_code.strip()
        if display and code:
            return f"{display} ({code}, species_id={self.species_id})"
        if display:
            return f"{display} (species_id={self.species_id})"
        if code:
            return f"{code} (species_id={self.species_id})"
        return f"species_id={self.species_id}"


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


def _query_species_info(db, species_ids: list[int]) -> dict[int, SpeciesInfo]:
    if not species_ids:
        return {}

    from sqlalchemy import bindparam, text

    stmt = (
        text(
            """
            SELECT species_id, species_code, display_name
            FROM species
            WHERE species_id IN :species_ids
            ORDER BY species_id
            """
        )
        .bindparams(bindparam("species_ids", expanding=True))
    )
    rows = db.execute(stmt, {"species_ids": species_ids}).mappings().all()

    out: dict[int, SpeciesInfo] = {}
    for r in rows:
        sid = _to_int(r.get("species_id"))
        if sid is None:
            continue
        code = str(r.get("species_code") or "").strip()
        display = str(r.get("display_name") or "").strip()
        out[sid] = SpeciesInfo(species_id=sid, species_code=code, display_name=display)

    # 兜底：确保每个 sid 都有 entry
    for sid in species_ids:
        out.setdefault(sid, SpeciesInfo(species_id=sid, species_code="", display_name=""))
    return out


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
        out.setdefault(sid, set()).add(core_id)

    for sid in species_ids:
        out.setdefault(sid, set())
    return out


def _pair_key(a: str, b: str) -> tuple[str, str]:
    a = (a or "").strip()
    b = (b or "").strip()
    if a <= b:
        return (a, b)
    return (b, a)


def _load_distance_overrides(path: Path) -> dict[tuple[str, str], float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("distances-json must be a JSON object mapping 'codeA-codeB' to distance(Mya)")

    out: dict[tuple[str, str], float] = {}
    for k, v in data.items():
        if not isinstance(k, str):
            continue
        distance = _to_float(v)
        if distance is None or distance < 0:
            continue
        key = k.replace(":", "-").strip()
        parts = [p.strip() for p in key.split("-") if p.strip()]
        if len(parts) != 2:
            continue
        a, b = parts
        out[_pair_key(a, b)] = float(distance)
    return out


def _get_distance_mya(
    *,
    code_a: str,
    code_b: str,
    overrides: Optional[dict[tuple[str, str], float]],
) -> Optional[float]:
    key = _pair_key(code_a, code_b)
    if overrides and key in overrides:
        return overrides[key]
    if key in DEFAULT_DISTANCES_MYA:
        return DEFAULT_DISTANCES_MYA[key]
    return None


def _pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    n = float(len(xs))
    mx = sum(xs) / n
    my = sum(ys) / n
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0.0 or vy <= 0.0:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    return cov / math.sqrt(vx * vy)


def _rankdata(values: list[float]) -> list[float]:
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    next_rank = 1.0  # 1-based
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        span = (j - i) + 1
        avg_rank = (next_rank + (next_rank + span - 1.0)) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        next_rank += span
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> Optional[float]:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    rx = _rankdata(xs)
    ry = _rankdata(ys)
    return _pearson(rx, ry)


def _fmt_opt_float(v: Optional[float], *, digits: int = 4) -> str:
    if v is None or math.isnan(v):
        return "N/A"
    return f"{v:.{digits}f}"


def _maybe_write_scatter_png(
    path: Path,
    *,
    title: str,
    x_values: list[float],
    y_values: list[float],
    labels: list[str],
    xlabel: str,
    ylabel: str,
) -> Optional[Path]:
    try:
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except Exception:
        return None

    if len(x_values) != len(y_values) or len(x_values) != len(labels) or not x_values:
        return None

    path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.0, 5.5))
    ax.scatter(x_values, y_values, s=55)
    for x, y, lab in zip(x_values, y_values, labels, strict=True):
        ax.annotate(lab, (x, y), textcoords="offset points", xytext=(6, 6), fontsize=9)

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.6)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export conservation vs evolutionary distance correlation report.")
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
        "--distances-json",
        type=str,
        default="",
        help="Optional JSON file mapping 'codeA-codeB' to distance in Mya (overrides defaults).",
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

    distance_overrides: Optional[dict[tuple[str, str], float]] = None
    if (args.distances_json or "").strip():
        distance_overrides = _load_distance_overrides(Path(args.distances_json))

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

        species_info_by_id = _query_species_info(db, species_ids)
        sets_by_species = _query_lncrna_core_ids_by_species(db, species_ids=species_ids, min_ba=args.min_ba)

        per_species_count = {sid: len(sets_by_species.get(sid, set())) for sid in species_ids}

        # Build pairwise rows
        pair_rows: list[dict[str, Any]] = []
        for i, sid_a in enumerate(species_ids):
            for sid_b in species_ids[i + 1 :]:
                info_a = species_info_by_id.get(sid_a) or SpeciesInfo(sid_a, "", "")
                info_b = species_info_by_id.get(sid_b) or SpeciesInfo(sid_b, "", "")

                set_a = sets_by_species.get(sid_a, set())
                set_b = sets_by_species.get(sid_b, set())
                intersection = len(set_a & set_b)
                union = len(set_a | set_b)
                count_a = len(set_a)
                count_b = len(set_b)

                jaccard = (intersection / union) if union > 0 else 0.0
                denom_min = min(count_a, count_b)
                overlap_min = (intersection / denom_min) if denom_min > 0 else 0.0
                row_share_a = (intersection / count_a) if count_a > 0 else 0.0
                row_share_b = (intersection / count_b) if count_b > 0 else 0.0
                avg_row_share = 0.5 * (row_share_a + row_share_b)

                distance_mya = _get_distance_mya(
                    code_a=info_a.species_code,
                    code_b=info_b.species_code,
                    overrides=distance_overrides,
                )

                pair_code = f"{info_a.species_code or sid_a}-{info_b.species_code or sid_b}"
                pair_rows.append(
                    {
                        "pair": pair_code,
                        "species_id_a": sid_a,
                        "species_id_b": sid_b,
                        "species_code_a": info_a.species_code,
                        "species_code_b": info_b.species_code,
                        "lncrna_count_a": count_a,
                        "lncrna_count_b": count_b,
                        "intersection_count": intersection,
                        "union_count": union,
                        "jaccard": jaccard,
                        "overlap_min": overlap_min,
                        "row_share_a": row_share_a,
                        "row_share_b": row_share_b,
                        "avg_row_share": avg_row_share,
                        "distance_mya": distance_mya,
                    }
                )

        # Correlations (distance vs metrics)
        xs: list[float] = []
        ys_jaccard: list[float] = []
        ys_avg_row_share: list[float] = []
        labels: list[str] = []
        for r in pair_rows:
            d = r.get("distance_mya")
            if d is None:
                continue
            xs.append(float(d))
            ys_jaccard.append(float(r["jaccard"]))
            ys_avg_row_share.append(float(r["avg_row_share"]))
            labels.append(str(r["pair"]))

        pearson_j = _pearson(xs, ys_jaccard)
        spearman_j = _spearman(xs, ys_jaccard)
        pearson_s = _pearson(xs, ys_avg_row_share)
        spearman_s = _spearman(xs, ys_avg_row_share)

        # Outputs
        csv_path = out_dir / f"conservation-distance-ba{int(args.min_ba)}-species-{group}.csv"
        md_path = out_dir / f"conservation-distance-ba{int(args.min_ba)}-species-{group}.md"
        plot_jaccard = _maybe_write_scatter_png(
            out_dir / f"conservation-distance-ba{int(args.min_ba)}-species-{group}-jaccard.png",
            title="Evolutionary distance vs Jaccard similarity",
            x_values=xs,
            y_values=ys_jaccard,
            labels=labels,
            xlabel="Evolutionary distance (Mya)",
            ylabel="Jaccard similarity",
        )
        plot_avg_row_share = _maybe_write_scatter_png(
            out_dir / f"conservation-distance-ba{int(args.min_ba)}-species-{group}-avg-row-share.png",
            title="Evolutionary distance vs avg row-share",
            x_values=xs,
            y_values=ys_avg_row_share,
            labels=labels,
            xlabel="Evolutionary distance (Mya)",
            ylabel="avg row-share",
        )

        # CSV
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "pair",
                    "species_id_a",
                    "species_id_b",
                    "species_code_a",
                    "species_code_b",
                    "lncrna_count_a",
                    "lncrna_count_b",
                    "intersection_count",
                    "union_count",
                    "jaccard",
                    "overlap_min",
                    "row_share_a",
                    "row_share_b",
                    "avg_row_share",
                    "distance_mya",
                ]
            )
            for r in pair_rows:
                writer.writerow(
                    [
                        r["pair"],
                        r["species_id_a"],
                        r["species_id_b"],
                        r["species_code_a"],
                        r["species_code_b"],
                        r["lncrna_count_a"],
                        r["lncrna_count_b"],
                        r["intersection_count"],
                        r["union_count"],
                        f"{float(r['jaccard']):.6f}",
                        f"{float(r['overlap_min']):.6f}",
                        f"{float(r['row_share_a']):.6f}",
                        f"{float(r['row_share_b']):.6f}",
                        f"{float(r['avg_row_share']):.6f}",
                        "" if r["distance_mya"] is None else f"{float(r['distance_mya']):.3f}",
                    ]
                )

        # Markdown
        md_lines: list[str] = []
        md_lines.append("# Conservation vs Evolutionary Distance (by Binding Affinity)")
        md_lines.append("")
        md_lines.append(f"- Species IDs: **{', '.join(str(s) for s in species_ids)}**")
        md_lines.append(f"- Filter: **binding_affinity >= {args.min_ba}**")
        md_lines.append(f"- Generated (UTC): **{_md_escape(generated_at_utc)}**")
        md_lines.append("")
        md_lines.append("Outputs:")
        md_lines.append(f"- Pairs CSV: `{csv_path}`")
        md_lines.append(f"- Report Markdown: `{md_path}`")
        if plot_jaccard is not None:
            md_lines.append(f"- Scatter (Jaccard): `{plot_jaccard}`")
        else:
            md_lines.append("- Scatter (Jaccard): _skipped (matplotlib not available)_")
        if plot_avg_row_share is not None:
            md_lines.append(f"- Scatter (avg row-share): `{plot_avg_row_share}`")
        else:
            md_lines.append("- Scatter (avg row-share): _skipped (matplotlib not available)_")
        md_lines.append("")

        md_lines.append("## Per-species lncRNA set size")
        md_lines.append("")
        md_lines.append("| species_id | species | lncrna_count |")
        md_lines.append("|---:|---|---:|")
        for sid in species_ids:
            info = species_info_by_id.get(sid) or SpeciesInfo(sid, "", "")
            md_lines.append(f"| {sid} | {_md_escape(info.label)} | {per_species_count.get(sid, 0)} |")
        md_lines.append("")

        md_lines.append("## Pairwise metrics")
        md_lines.append("")
        md_lines.append(
            "| pair | distance_mya | intersection | union | jaccard | overlap_min | avg_row_share |"
        )
        md_lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for r in pair_rows:
            md_lines.append(
                "| {pair} | {dist} | {inter} | {union} | {jaccard:.4f} | {overlap:.4f} | {avg:.4f} |".format(
                    pair=_md_escape(str(r["pair"])),
                    dist=("N/A" if r["distance_mya"] is None else f"{float(r['distance_mya']):.2f}"),
                    inter=int(r["intersection_count"]),
                    union=int(r["union_count"]),
                    jaccard=float(r["jaccard"]),
                    overlap=float(r["overlap_min"]),
                    avg=float(r["avg_row_share"]),
                )
            )
        md_lines.append("")

        md_lines.append("## Correlation (distance vs metric)")
        md_lines.append("")
        md_lines.append(
            "| metric | pearson_r | spearman_r | n_pairs |"
        )
        md_lines.append("|---|---:|---:|---:|")
        md_lines.append(
            "| jaccard | {p} | {s} | {n} |".format(
                p=_fmt_opt_float(pearson_j),
                s=_fmt_opt_float(spearman_j),
                n=len(xs),
            )
        )
        md_lines.append(
            "| avg_row_share | {p} | {s} | {n} |".format(
                p=_fmt_opt_float(pearson_s),
                s=_fmt_opt_float(spearman_s),
                n=len(xs),
            )
        )
        md_lines.append("")

        missing_pairs: list[str] = []
        for r in pair_rows:
            if r.get("distance_mya") is None:
                missing_pairs.append(str(r["pair"]))
        if missing_pairs:
            md_lines.append("Notes:")
            md_lines.append(
                "- Missing distances for pairs: **{pairs}**. Provide `--distances-json` to cover them.".format(
                    pairs=_md_escape(", ".join(sorted(missing_pairs)))
                )
            )
            md_lines.append("")
        md_lines.append(
            "Distance mapping is an approximation (Mya). For strict phylogenetic modeling, please replace distances via `--distances-json`."
        )
        md_lines.append("")

        md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    finally:
        db.close()

    print(f"Wrote: {csv_path}")
    if plot_jaccard is not None:
        print(f"Wrote: {plot_jaccard}")
    if plot_avg_row_share is not None:
        print(f"Wrote: {plot_avg_row_share}")
    print(f"Wrote: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

