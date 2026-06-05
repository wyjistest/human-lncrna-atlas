#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import psycopg2
import psycopg2.extras
import seaborn as sns
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(__file__).resolve()

DEFAULT_CELL_LINE_SUBSET = ["A549", "GM12878", "H1-hESC", "HepG2", "HMEC", "K562"]
PAPER_BASELINE_MARKS = [
    "H3K27me3",
    "H3K4me3",
    "H3K4me2",
    "H3K4me1",
    "H3K27ac",
    "H3K36me3",
    "H3K9ac",
    "H3K9me3",
    "DNase-HS",
]
EXTENDED_TRACKS = ["CTCF", "H4K20me1"]
FIG4_SIGNATURE_TOP_N = 8
FIG5_TOP_TRAITS = 6
FIG5_RANKING_TOP_N = 20
FIG5_TRIPARTITE_TOP_LNCRNAS = 3
FIG5_TRIPARTITE_TOP_TARGETS = 10
FIG5_CASE_TARGET_LIMIT = 8
FIG5C_TOP_LNCRNAS = 12

FIG5_TRAIT_LABEL_MAP = {
    "obesity": "Obesity",
    "Abnormality of the nervous system": "nervous system",
    "Arteriosclerosis": "atherosclerosis",
    "Sclerosis of metaphyses of the upper limbs": "metaphyseal sclerosis",
}


sns.set_theme(style="whitegrid")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return str(path)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip().strip("\r")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def write_tsv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def save_figure(fig: plt.Figure, svg_path: Path, png_path: Path) -> None:
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(svg_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def with_generation_provenance(
    payload: dict[str, Any],
    *,
    generated_at: str,
    source_commit: str,
) -> dict[str, Any]:
    output = dict(payload)
    output["generated_at"] = generated_at
    output["source_commit"] = source_commit
    output.pop("release_commit", None)
    return output


def panel_metadata(
    *,
    panel_id: str,
    title: str,
    repo_root: Path,
    generated_at: str,
    source_commit: str,
    input_paths: Sequence[Path],
    output_paths: Sequence[Path],
    filters: dict[str, Any],
    notes: Sequence[str] | None = None,
) -> dict[str, Any]:
    return with_generation_provenance(
        {
            "panel_id": panel_id,
            "title": title,
            "script": display_path(SCRIPT_PATH, repo_root),
            "inputs": [display_path(path, repo_root) for path in input_paths],
            "outputs": [display_path(path, repo_root) for path in output_paths],
            "filters": filters,
            "notes": list(notes or []),
        },
        generated_at=generated_at,
        source_commit=source_commit,
    )


def git_commit_sha(repo_root: Path, ref: str = "HEAD") -> str:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", ref],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            .stdout.strip()
        )
    except Exception:
        return "unknown"


def query_dict_rows(
    conn: psycopg2.extensions.connection,
    sql: str,
    params: Sequence[Any] | dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def connect_db(env_path: Path) -> psycopg2.extensions.connection:
    env = parse_env_file(env_path)
    return psycopg2.connect(
        host=env["DB_HOST"],
        port=int(env["DB_PORT"]),
        user=env["DB_USER"],
        dbname=env["DB_NAME"],
    )


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader)


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def shorten_gene_label(symbol: str | None) -> str:
    value = (symbol or "").strip()
    if not value:
        return "NA"
    matched = re.match(r"^(CATG|ENSG)0*(\d+)(?:\.\d+)?$", value)
    if matched:
        prefix = matched.group(1)
        digits = matched.group(2)[-6:].zfill(6)
        return f"{prefix}{digits}"
    if len(value) > 18:
        return value[:15] + "..."
    return value


def fetch_epigenomic_inventory_rows(conn: psycopg2.extensions.connection) -> list[dict[str, Any]]:
    sql = """
        SELECT
            m.mark_name,
            COALESCE(NULLIF(e.cell_type, ''), NULLIF(e.cell_line, ''), 'unknown') AS cell_line,
            COUNT(DISTINCT e.experiment_id) AS experiment_count,
            COUNT(p.peak_id) AS peak_count
        FROM epigenetic_mark_types m
        JOIN chipseq_experiments e ON e.mark_type_id = m.mark_type_id
        JOIN species s ON s.species_id = e.species_id
        LEFT JOIN chipseq_peaks p
          ON p.experiment_id = e.experiment_id
         AND p.species_id = e.species_id
        WHERE s.species_code = 'human'
          AND m.mark_name = ANY(%s)
          AND COALESCE(e.is_active, TRUE) = TRUE
        GROUP BY m.mark_name, COALESCE(NULLIF(e.cell_type, ''), NULLIF(e.cell_line, ''), 'unknown')
        ORDER BY m.mark_name, cell_line
    """
    return query_dict_rows(conn, sql, [PAPER_BASELINE_MARKS + EXTENDED_TRACKS])


def fetch_total_candidate_regulations(conn: psycopg2.extensions.connection, *, min_ba: float) -> int:
    sql = """
        SELECT COUNT(DISTINCT r.regulation_id) AS total_count
        FROM regulations r
        WHERE r.species_id = 1
          AND r.binding_affinity >= %s
    """
    rows = query_dict_rows(conn, sql, [min_ba])
    if not rows:
        return 0
    return safe_int(rows[0].get("total_count"))


def fetch_overlap_detail_rows(
    conn: psycopg2.extensions.connection,
    *,
    min_ba: float | None = None,
    marks: Sequence[str] | None = None,
    cell_lines: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    filters: list[str] = []
    params: list[Any] = []
    if min_ba is not None:
        filters.append("o.binding_affinity >= %s")
        params.append(min_ba)
    if marks:
        filters.append("o.mark_name = ANY(%s)")
        params.append(list(marks))
    if cell_lines:
        filters.append("o.cell_type = ANY(%s)")
        params.append(list(cell_lines))
    where_sql = ""
    if filters:
        where_sql = "WHERE " + " AND ".join(filters)
    sql = f"""
        SELECT
            o.regulation_id,
            o.lncrna_gene_id,
            lnc.core_id AS lncrna_core_id,
            o.lncrna_name,
            o.target_gene_id,
            tgt.core_id AS target_core_id,
            o.target_gene_name,
            o.binding_affinity,
            o.mark_name,
            o.cell_type AS cell_line,
            o.chromosome AS peak_chr,
            o.peak_start,
            o.peak_end,
            r.target_chromosome,
            r.target_start,
            r.target_end
        FROM mv_lncrna_chipseq_overlaps o
        JOIN regulations r ON r.regulation_id = o.regulation_id
        JOIN genes lnc ON lnc.gene_id = o.lncrna_gene_id
        JOIN genes tgt ON tgt.gene_id = o.target_gene_id
        {where_sql}
        ORDER BY o.binding_affinity DESC, o.regulation_id ASC, o.mark_name ASC, o.cell_type ASC
    """
    return query_dict_rows(conn, sql, params)


def fetch_trait_summary_rows_db(conn: psycopg2.extensions.connection) -> list[dict[str, Any]]:
    sql = """
        WITH trait_targets AS (
            SELECT
                tga.trait_id,
                t.trait_name,
                g.gene_id AS target_gene_id,
                MIN(tga.trait_snp_pvalue) AS trait_pvalue
            FROM trait_gene_associations tga
            JOIN traits t ON t.trait_id = tga.trait_id
            JOIN genes g ON g.core_id = tga.core_id
            WHERE g.species_id = 1
              AND g.core_id IS NOT NULL
            GROUP BY tga.trait_id, t.trait_name, g.gene_id
        ),
        trait_network AS (
            SELECT
                tt.trait_id,
                tt.trait_name,
                r.regulation_id,
                r.lncrna_gene_id,
                r.target_gene_id,
                r.binding_affinity
            FROM trait_targets tt
            JOIN regulations r
              ON r.target_gene_id = tt.target_gene_id
             AND r.species_id = 1
            JOIN genes lnc ON lnc.gene_id = r.lncrna_gene_id
            WHERE lnc.core_id IS NOT NULL
        )
        SELECT
            trait_id,
            trait_name,
            COUNT(DISTINCT lncrna_gene_id) AS unique_lncrna_count,
            COUNT(DISTINCT target_gene_id) AS unique_target_gene_count,
            COUNT(DISTINCT regulation_id) AS regulation_count,
            MAX(binding_affinity) AS max_ba
        FROM trait_network
        GROUP BY trait_id, trait_name
        ORDER BY
            COUNT(DISTINCT lncrna_gene_id) DESC,
            COUNT(DISTINCT target_gene_id) DESC,
            MAX(binding_affinity) DESC,
            trait_id ASC
    """
    return query_dict_rows(conn, sql)


def fetch_trait_network_rows(conn: psycopg2.extensions.connection, trait_ids: Sequence[int]) -> list[dict[str, Any]]:
    if not trait_ids:
        return []
    sql = """
        WITH trait_targets AS (
            SELECT
                tga.trait_id,
                t.trait_name,
                g.gene_id AS target_gene_id,
                g.gene_name AS target_gene_name,
                g.core_id AS target_core_id,
                MIN(tga.trait_snp_pvalue) AS trait_pvalue,
                BOOL_OR(COALESCE(tga.literature_support, FALSE)) AS trait_literature_support
            FROM trait_gene_associations tga
            JOIN traits t ON t.trait_id = tga.trait_id
            JOIN genes g ON g.core_id = tga.core_id
            WHERE g.species_id = 1
              AND g.core_id IS NOT NULL
              AND tga.trait_id = ANY(%s)
            GROUP BY tga.trait_id, t.trait_name, g.gene_id, g.gene_name, g.core_id
        )
        SELECT
            tt.trait_id,
            tt.trait_name,
            tt.trait_pvalue,
            tt.trait_literature_support,
            r.regulation_id,
            r.binding_affinity,
            r.lncrna_gene_id,
            lnc.gene_name AS lncrna_name,
            lnc.core_id AS lncrna_core_id,
            tt.target_gene_id,
            tt.target_gene_name,
            tt.target_core_id
        FROM trait_targets tt
        JOIN regulations r
          ON r.target_gene_id = tt.target_gene_id
         AND r.species_id = 1
        JOIN genes lnc ON lnc.gene_id = r.lncrna_gene_id
        WHERE lnc.core_id IS NOT NULL
        ORDER BY tt.trait_id ASC, r.binding_affinity DESC, r.regulation_id ASC
    """
    return query_dict_rows(conn, sql, [list(trait_ids)])


def build_fig4a_rows(
    *,
    inventory_rows: Sequence[dict[str, Any]],
    overlap_rows: Sequence[dict[str, Any]],
    total_candidate_regulations: int,
    marks: Sequence[str],
    cell_lines: Sequence[str],
) -> list[dict[str, Any]]:
    inventory_map = {
        (str(row["mark_name"]), str(row["cell_line"])): row
        for row in inventory_rows
    }
    overlap_map = {
        (str(row["mark_name"]), str(row["cell_line"])): safe_int(row.get("overlapped_regulation_count"))
        for row in overlap_rows
    }
    output: list[dict[str, Any]] = []
    denominator = max(total_candidate_regulations, 0)
    for mark_name in marks:
        for cell_line in cell_lines:
            inventory = inventory_map.get((mark_name, cell_line))
            if inventory is None:
                output.append(
                    {
                        "mark_name": mark_name,
                        "cell_line": cell_line,
                        "experiment_count": 0,
                        "peak_count": 0,
                        "overlapped_regulation_count": 0,
                        "overlap_fraction": "",
                        "availability_status": "NA",
                    }
                )
                continue
            overlap_count = overlap_map.get((mark_name, cell_line), 0)
            overlap_fraction = 0.0 if denominator <= 0 else round(overlap_count / float(denominator), 6)
            output.append(
                {
                    "mark_name": mark_name,
                    "cell_line": cell_line,
                    "experiment_count": safe_int(inventory.get("experiment_count")),
                    "peak_count": safe_int(inventory.get("peak_count")),
                    "overlapped_regulation_count": overlap_count,
                    "overlap_fraction": overlap_fraction,
                    "availability_status": "observed",
                }
            )
    return output


def classify_fig4_context(mark_names: set[str]) -> str:
    if {"H3K4me3", "H3K27me3"}.issubset(mark_names):
        return "bivalent_like"
    active_marks = {"H3K4me3", "H3K27ac", "H3K4me1"}
    if mark_names.intersection(active_marks) and "H3K27me3" not in mark_names:
        return "active_like_non_bivalent"
    return "other"


def collapse_overlap_rows(overlap_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, str], dict[str, Any]] = {}
    for row in overlap_rows:
        regulation_id = safe_int(row.get("regulation_id"))
        cell_line = str(row.get("cell_line") or "")
        if regulation_id <= 0 or not cell_line:
            continue
        key = (regulation_id, cell_line)
        entry = grouped.setdefault(
            key,
            {
                "regulation_id": regulation_id,
                "cell_line": cell_line,
                "lncrna_gene_id": safe_int(row.get("lncrna_gene_id")),
                "lncrna_core_id": safe_int(row.get("lncrna_core_id")),
                "lncrna_name": str(row.get("lncrna_name") or ""),
                "target_gene_id": safe_int(row.get("target_gene_id")),
                "target_core_id": safe_int(row.get("target_core_id")),
                "target_gene_name": str(row.get("target_gene_name") or ""),
                "binding_affinity": safe_float(row.get("binding_affinity")),
                "target_chromosome": str(row.get("target_chromosome") or row.get("peak_chr") or ""),
                "target_start": safe_int(row.get("target_start")),
                "target_end": safe_int(row.get("target_end")),
                "peak_chr": str(row.get("peak_chr") or row.get("target_chromosome") or ""),
                "peak_start": safe_int(row.get("peak_start")),
                "peak_end": safe_int(row.get("peak_end")),
                "mark_names": set(),
                "track_rows": [],
            },
        )
        entry["binding_affinity"] = max(entry["binding_affinity"], safe_float(row.get("binding_affinity")))
        entry["mark_names"].add(str(row.get("mark_name") or ""))
        entry["track_rows"].append(dict(row))
        peak_start = safe_int(row.get("peak_start"))
        peak_end = safe_int(row.get("peak_end"))
        if peak_start and (not entry["peak_start"] or peak_start < entry["peak_start"]):
            entry["peak_start"] = peak_start
        if peak_end and peak_end > entry["peak_end"]:
            entry["peak_end"] = peak_end
    output: list[dict[str, Any]] = []
    for key in sorted(grouped):
        entry = grouped[key]
        mark_names = {mark for mark in entry["mark_names"] if mark}
        output.append(
            {
                **{k: v for k, v in entry.items() if k not in {"mark_names", "track_rows"}},
                "mark_signature": " | ".join(sorted(mark_names)),
                "mark_count": len(mark_names),
                "mark_names": sorted(mark_names),
                "context_class": classify_fig4_context(mark_names),
                "track_rows": entry["track_rows"],
            }
        )
    return output


def build_fig4b_rows(overlap_rows: Sequence[dict[str, Any]], *, top_n: int = FIG4_SIGNATURE_TOP_N) -> list[dict[str, Any]]:
    grouped_rows = collapse_overlap_rows(overlap_rows)
    cohorts = {
        "all_human_edges": grouped_rows,
        "high_affinity": [row for row in grouped_rows if safe_float(row.get("binding_affinity")) >= 100.0],
    }
    output: list[dict[str, Any]] = []
    for cohort, rows in cohorts.items():
        counts = Counter(row["mark_signature"] or "No overlap" for row in rows)
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        kept = ordered[:top_n]
        other_count = sum(count for _, count in ordered[top_n:])
        total = sum(counts.values())
        rank = 1
        for signature, count in kept:
            output.append(
                {
                    "cohort": cohort,
                    "signature_label": signature,
                    "display_label": signature,
                    "regulation_cell_count": count,
                    "fraction": 0.0 if total <= 0 else round(count / float(total), 6),
                    "rank": rank,
                }
            )
            rank += 1
        if other_count > 0:
            output.append(
                {
                    "cohort": cohort,
                    "signature_label": "Other",
                    "display_label": "Other",
                    "regulation_cell_count": other_count,
                    "fraction": 0.0 if total <= 0 else round(other_count / float(total), 6),
                    "rank": rank,
                }
            )
    return output


def build_fig4c_rows(overlap_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped_rows = collapse_overlap_rows(overlap_rows)
    output: list[dict[str, Any]] = []
    for row in grouped_rows:
        output.append(
            {
                "regulation_id": row["regulation_id"],
                "cell_line": row["cell_line"],
                "lncrna_gene_id": row["lncrna_gene_id"],
                "lncrna_core_id": row["lncrna_core_id"],
                "lncrna_name": row["lncrna_name"],
                "target_gene_id": row["target_gene_id"],
                "target_core_id": row["target_core_id"],
                "target_gene_name": row["target_gene_name"],
                "binding_affinity": round(safe_float(row.get("binding_affinity")), 6),
                "mark_signature": row["mark_signature"],
                "mark_count": row["mark_count"],
                "context_class": row["context_class"],
                "target_chromosome": row["target_chromosome"],
                "target_start": row["target_start"],
                "target_end": row["target_end"],
            }
        )
    output.sort(
        key=lambda row: (
            row["context_class"],
            -safe_float(row.get("binding_affinity")),
            row["cell_line"],
            safe_int(row.get("regulation_id")),
        )
    )
    return output


def build_table2_rows(
    inventory_rows: Sequence[dict[str, Any]],
    *,
    baseline_marks: Sequence[str],
    extended_marks: Sequence[str],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in inventory_rows:
        mark_name = str(row.get("mark_name") or "")
        if not mark_name:
            continue
        entry = grouped.setdefault(
            mark_name,
            {
                "mark_name": mark_name,
                "cell_line_count": 0,
                "experiment_count": 0,
                "peak_count": 0,
                "inventory_group": "other",
            },
        )
        entry["cell_line_count"] += 1
        entry["experiment_count"] += safe_int(row.get("experiment_count"))
        entry["peak_count"] += safe_int(row.get("peak_count"))
        if mark_name in baseline_marks:
            entry["inventory_group"] = "main_text_baseline"
        elif mark_name in extended_marks:
            entry["inventory_group"] = "extended_tracks"
    order_index = {mark: index for index, mark in enumerate(list(baseline_marks) + list(extended_marks))}
    output = list(grouped.values())
    output.sort(key=lambda row: (order_index.get(row["mark_name"], 10_000), row["mark_name"]))
    return output


def pick_best_context_class(classes: Iterable[str]) -> str:
    class_set = set(classes)
    if "bivalent_like" in class_set:
        return "bivalent_like"
    if "active_like_non_bivalent" in class_set:
        return "active_like_non_bivalent"
    return "other"


def normalize_fig5_epigenomic_support(context_class: str) -> str:
    if context_class == "active_like_non_bivalent":
        return "active_like"
    return context_class or "other"


def build_trait_summary_rows(
    network_rows: Sequence[dict[str, Any]],
    *,
    min_lncrnas: int = 3,
    min_targets: int = 5,
) -> list[dict[str, Any]]:
    if network_rows and "unique_lncrna_count" in network_rows[0] and "lncrna_gene_id" not in network_rows[0]:
        output = [
            {
                "trait_id": safe_int(row.get("trait_id")),
                "trait_name": str(row.get("trait_name") or ""),
                "unique_lncrna_count": safe_int(row.get("unique_lncrna_count")),
                "unique_target_gene_count": safe_int(row.get("unique_target_gene_count")),
                "regulation_count": safe_int(row.get("regulation_count")),
                "max_ba": round(safe_float(row.get("max_ba")), 6),
            }
            for row in network_rows
            if safe_int(row.get("unique_lncrna_count")) >= min_lncrnas
            and safe_int(row.get("unique_target_gene_count")) >= min_targets
        ]
        output.sort(
            key=lambda row: (
                -safe_int(row.get("unique_lncrna_count")),
                -safe_int(row.get("unique_target_gene_count")),
                -safe_float(row.get("max_ba")),
                safe_int(row.get("trait_id")),
            )
        )
        return output

    grouped: dict[int, dict[str, Any]] = {}
    for row in network_rows:
        trait_id = safe_int(row.get("trait_id"))
        if trait_id <= 0:
            continue
        entry = grouped.setdefault(
            trait_id,
            {
                "trait_id": trait_id,
                "trait_name": str(row.get("trait_name") or ""),
                "lncrna_gene_ids": set(),
                "target_gene_ids": set(),
                "max_ba": 0.0,
                "regulation_ids": set(),
            },
        )
        entry["lncrna_gene_ids"].add(safe_int(row.get("lncrna_gene_id")))
        entry["target_gene_ids"].add(safe_int(row.get("target_gene_id")))
        entry["regulation_ids"].add(safe_int(row.get("regulation_id"), safe_int(row.get("target_gene_id"))))
        entry["max_ba"] = max(entry["max_ba"], safe_float(row.get("binding_affinity")))
    output: list[dict[str, Any]] = []
    for trait_id, entry in grouped.items():
        unique_lncrna_count = len({value for value in entry["lncrna_gene_ids"] if value > 0})
        unique_target_gene_count = len({value for value in entry["target_gene_ids"] if value > 0})
        if unique_lncrna_count < min_lncrnas or unique_target_gene_count < min_targets:
            continue
        output.append(
            {
                "trait_id": trait_id,
                "trait_name": entry["trait_name"],
                "unique_lncrna_count": unique_lncrna_count,
                "unique_target_gene_count": unique_target_gene_count,
                "regulation_count": len(entry["regulation_ids"]),
                "max_ba": round(entry["max_ba"], 6),
            }
        )
    output.sort(
        key=lambda row: (
            -safe_int(row.get("unique_lncrna_count")),
            -safe_int(row.get("unique_target_gene_count")),
            -safe_float(row.get("max_ba")),
            safe_int(row.get("trait_id")),
        )
    )
    return output


def build_flagship_trait_selection_rows(
    trait_summary_rows: Sequence[dict[str, Any]],
    *,
    flagship_trait_name: str,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, row in enumerate(trait_summary_rows, start=1):
        output.append(
            {
                "flagship_rank": index,
                "trait_id": safe_int(row.get("trait_id")),
                "trait_name": str(row.get("trait_name") or ""),
                "unique_lncrna_count": safe_int(row.get("unique_lncrna_count")),
                "unique_target_gene_count": safe_int(row.get("unique_target_gene_count")),
                "regulation_count": safe_int(row.get("regulation_count")),
                "max_ba": round(safe_float(row.get("max_ba")), 6),
                "is_flagship": str(row.get("trait_name") or "") == flagship_trait_name,
            }
        )
    return output


def load_edge_presence_map(path: Path) -> dict[tuple[int, int], dict[str, Any]]:
    rows = read_tsv_rows(path)
    return {
        (safe_int(row.get("lncrna_core_id")), safe_int(row.get("target_core_id"))): row
        for row in rows
    }


def load_node_presence_map(path: Path) -> dict[int, dict[str, Any]]:
    rows = read_tsv_rows(path)
    return {safe_int(row.get("core_id")): row for row in rows}


def derive_edge_rewiring_label(
    *,
    lncrna_core_id: int,
    target_core_id: int,
    edge_presence_map: dict[tuple[int, int], dict[str, Any]],
    node_presence_map: dict[int, dict[str, Any]],
) -> tuple[str, int]:
    edge_row = edge_presence_map.get((lncrna_core_id, target_core_id))
    edge_conservation = safe_int((edge_row or {}).get("conservation_count"))
    if edge_conservation >= 2:
        return ("conserved", edge_conservation)
    lnc_node = node_presence_map.get(lncrna_core_id, {})
    target_node = node_presence_map.get(target_core_id, {})
    if safe_int(lnc_node.get("conservation_count")) >= 2 and safe_int(target_node.get("conservation_count")) >= 2:
        return ("rewired", edge_conservation)
    return ("species_specific", edge_conservation)


def combine_rewiring_labels(labels: Iterable[str]) -> str:
    label_set = set(labels)
    if "conserved" in label_set:
        return "conserved"
    if "rewired" in label_set:
        return "rewired"
    return "species_specific"


def build_trait_pair_rows(
    network_rows: Sequence[dict[str, Any]],
    *,
    edge_presence_map: dict[tuple[int, int], dict[str, Any]],
    node_presence_map: dict[int, dict[str, Any]],
    context_by_regulation: dict[int, str],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int], dict[str, Any]] = {}
    for row in network_rows:
        trait_id = safe_int(row.get("trait_id"))
        lncrna_gene_id = safe_int(row.get("lncrna_gene_id"))
        if trait_id <= 0 or lncrna_gene_id <= 0:
            continue
        key = (trait_id, lncrna_gene_id)
        entry = grouped.setdefault(
            key,
            {
                "trait_id": trait_id,
                "trait_name": str(row.get("trait_name") or ""),
                "lncrna_gene_id": lncrna_gene_id,
                "lncrna_name": str(row.get("lncrna_name") or ""),
                "lncrna_core_id": safe_int(row.get("lncrna_core_id")),
                "target_gene_ids": set(),
                "regulation_ids": set(),
                "trait_pvalues": [],
                "max_ba": 0.0,
                "ba_values": [],
                "edge_labels": [],
                "edge_conservation_counts": [],
                "context_classes": [],
                "edge_rows": [],
            },
        )
        target_gene_id = safe_int(row.get("target_gene_id"))
        target_core_id = safe_int(row.get("target_core_id"))
        binding_affinity = safe_float(row.get("binding_affinity"))
        regulation_id = safe_int(row.get("regulation_id"))
        rewiring_label, edge_conservation = derive_edge_rewiring_label(
            lncrna_core_id=safe_int(row.get("lncrna_core_id")),
            target_core_id=target_core_id,
            edge_presence_map=edge_presence_map,
            node_presence_map=node_presence_map,
        )
        entry["target_gene_ids"].add(target_gene_id)
        entry["regulation_ids"].add(regulation_id)
        if row.get("trait_pvalue") not in (None, ""):
            entry["trait_pvalues"].append(safe_float(row.get("trait_pvalue")))
        entry["max_ba"] = max(entry["max_ba"], binding_affinity)
        entry["ba_values"].append(binding_affinity)
        entry["edge_labels"].append(rewiring_label)
        entry["edge_conservation_counts"].append(edge_conservation)
        entry["context_classes"].append(context_by_regulation.get(regulation_id, "other"))
        entry["edge_rows"].append(dict(row))
    output: list[dict[str, Any]] = []
    for key in sorted(grouped):
        entry = grouped[key]
        output.append(
            {
                "trait_id": entry["trait_id"],
                "trait_name": entry["trait_name"],
                "lncrna_gene_id": entry["lncrna_gene_id"],
                "lncrna_name": entry["lncrna_name"],
                "lncrna_core_id": entry["lncrna_core_id"],
                "target_count": len(entry["target_gene_ids"]),
                "high_affinity_edge_count": sum(1 for value in entry["ba_values"] if value >= 100.0),
                "mean_ba": round(statistics.fmean(entry["ba_values"]) if entry["ba_values"] else 0.0, 6),
                "max_ba": round(entry["max_ba"], 6),
                "best_edge_conservation_count": max(entry["edge_conservation_counts"] or [0]),
                "rewiring_label": combine_rewiring_labels(entry["edge_labels"]),
                "epigenomic_support_class": normalize_fig5_epigenomic_support(pick_best_context_class(entry["context_classes"])),
                "min_trait_pvalue": min(entry["trait_pvalues"]) if entry["trait_pvalues"] else None,
                "edge_rows": entry["edge_rows"],
            }
        )
    return output


def build_lnc_candidate_rows(pair_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    for row in pair_rows:
        lnc_id = safe_int(row.get("lncrna_gene_id"))
        entry = grouped.setdefault(
            lnc_id,
            {
                "lncrna_gene_id": lnc_id,
                "lncrna_name": str(row.get("lncrna_name") or ""),
                "trait_names": set(),
                "target_count": 0,
                "high_affinity_edge_count": 0,
                "max_ba": 0.0,
                "mean_ba_values": [],
                "best_edge_conservation_count": 0,
                "rewiring_labels": [],
                "epigenomic_support_classes": [],
            },
        )
        entry["trait_names"].add(str(row.get("trait_name") or ""))
        entry["target_count"] += safe_int(row.get("target_count"))
        entry["high_affinity_edge_count"] += safe_int(row.get("high_affinity_edge_count"))
        entry["max_ba"] = max(entry["max_ba"], safe_float(row.get("max_ba")))
        entry["mean_ba_values"].append(safe_float(row.get("mean_ba")))
        entry["best_edge_conservation_count"] = max(
            entry["best_edge_conservation_count"],
            safe_int(row.get("best_edge_conservation_count")),
        )
        entry["rewiring_labels"].append(str(row.get("rewiring_label") or "species_specific"))
        entry["epigenomic_support_classes"].append(str(row.get("epigenomic_support_class") or "other"))
    output: list[dict[str, Any]] = []
    for lnc_id in sorted(grouped):
        entry = grouped[lnc_id]
        output.append(
            {
                "lncrna_gene_id": lnc_id,
                "lncrna_name": entry["lncrna_name"],
                "trait_count": len({name for name in entry["trait_names"] if name}),
                "target_count": entry["target_count"],
                "high_affinity_edge_count": entry["high_affinity_edge_count"],
                "mean_ba": round(statistics.fmean(entry["mean_ba_values"]) if entry["mean_ba_values"] else 0.0, 6),
                "max_ba": round(entry["max_ba"], 6),
                "best_edge_conservation_count": entry["best_edge_conservation_count"],
                "rewiring_label": combine_rewiring_labels(entry["rewiring_labels"]),
                "epigenomic_support_class": normalize_fig5_epigenomic_support(
                    pick_best_context_class(
                        "active_like_non_bivalent" if item == "active_like" else item
                        for item in entry["epigenomic_support_classes"]
                    )
                ),
                "flagship_membership": False,
            }
        )
    return output


def rank_trait_lnc_candidates(candidate_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = [dict(row) for row in candidate_rows]
    ranked.sort(
        key=lambda row: (
            -safe_int(row.get("trait_count")),
            -safe_int(row.get("target_count")),
            -safe_int(row.get("high_affinity_edge_count")),
            -safe_int(row.get("best_edge_conservation_count")),
            -safe_float(row.get("max_ba")),
            safe_int(row.get("lncrna_gene_id")),
        )
    )
    return ranked


def select_flagship_case(candidate_rows: Sequence[dict[str, Any]], *, flagship_trait_name: str) -> dict[str, Any]:
    filtered = [
        dict(row)
        for row in candidate_rows
        if str(row.get("trait_name") or "") == flagship_trait_name
        and safe_int(row.get("best_edge_conservation_count")) >= 1
        and str(row.get("epigenomic_support_class") or "other") not in {"other", ""}
    ]
    if not filtered:
        filtered = [dict(row) for row in candidate_rows if str(row.get("trait_name") or "") == flagship_trait_name]
    if not filtered:
        raise ValueError(f"No candidate rows available for flagship trait {flagship_trait_name!r}")
    filtered.sort(
        key=lambda row: (
            -safe_int(row.get("target_count")),
            -safe_int(row.get("high_affinity_edge_count")),
            -safe_int(row.get("best_edge_conservation_count")),
            -safe_float(row.get("max_ba")),
            safe_int(row.get("lncrna_gene_id")),
        )
    )
    return filtered[0]


def build_fig5a_asset_rows(network_rows: Sequence[dict[str, Any]], *, flagship_trait_name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[int], set[int]]:
    trait_rows = [row for row in network_rows if str(row.get("trait_name") or "") == flagship_trait_name]
    if not trait_rows:
        raise ValueError(f"No network rows for flagship trait {flagship_trait_name!r}")
    lnc_groups: dict[int, dict[str, Any]] = {}
    for row in trait_rows:
        lnc_id = safe_int(row.get("lncrna_gene_id"))
        entry = lnc_groups.setdefault(
            lnc_id,
            {
                "lncrna_gene_id": lnc_id,
                "lncrna_name": str(row.get("lncrna_name") or ""),
                "target_ids": set(),
                "max_ba": 0.0,
                "high_affinity_edge_count": 0,
            },
        )
        entry["target_ids"].add(safe_int(row.get("target_gene_id")))
        entry["max_ba"] = max(entry["max_ba"], safe_float(row.get("binding_affinity")))
        if safe_float(row.get("binding_affinity")) >= 100.0:
            entry["high_affinity_edge_count"] += 1
    top_lnc_rows = sorted(
        lnc_groups.values(),
        key=lambda row: (
            -len(row["target_ids"]),
            -row["high_affinity_edge_count"],
            -row["max_ba"],
            row["lncrna_gene_id"],
        ),
    )[:FIG5_TRIPARTITE_TOP_LNCRNAS]
    selected_lnc_ids = {row["lncrna_gene_id"] for row in top_lnc_rows}
    filtered_edges = [row for row in trait_rows if safe_int(row.get("lncrna_gene_id")) in selected_lnc_ids]

    target_groups: dict[int, dict[str, Any]] = {}
    for row in filtered_edges:
        target_id = safe_int(row.get("target_gene_id"))
        entry = target_groups.setdefault(
            target_id,
            {
                "target_gene_id": target_id,
                "target_gene_name": str(row.get("target_gene_name") or ""),
                "lncrna_ids": set(),
                "max_ba": 0.0,
            },
        )
        entry["lncrna_ids"].add(safe_int(row.get("lncrna_gene_id")))
        entry["max_ba"] = max(entry["max_ba"], safe_float(row.get("binding_affinity")))
    top_target_rows = sorted(
        target_groups.values(),
        key=lambda row: (
            -len(row["lncrna_ids"]),
            -row["max_ba"],
            str(row["target_gene_name"]),
        ),
    )[:FIG5_TRIPARTITE_TOP_TARGETS]
    selected_target_ids = {row["target_gene_id"] for row in top_target_rows}
    final_edges = [
        row for row in filtered_edges if safe_int(row.get("target_gene_id")) in selected_target_ids
    ]

    trait_node_id = f"trait_{safe_int(trait_rows[0].get('trait_id'))}"
    nodes: list[dict[str, Any]] = [
        {
            "node_id": trait_node_id,
            "node_type": "trait",
            "display_label": format_trait_display_label(flagship_trait_name),
            "value": len(selected_target_ids),
        }
    ]
    edges: list[dict[str, Any]] = []
    for row in top_lnc_rows:
        nodes.append(
            {
                "node_id": f"lncrna_{row['lncrna_gene_id']}",
                "node_type": "lncrna",
                "display_label": shorten_gene_label(str(row["lncrna_name"])),
                "value": len(row["target_ids"]),
            }
        )
        edges.append(
            {
                "source": trait_node_id,
                "target": f"lncrna_{row['lncrna_gene_id']}",
                "edge_type": "trait_anchor",
                "weight": 1.0,
            }
        )
    for row in top_target_rows:
        nodes.append(
            {
                "node_id": f"gene_{row['target_gene_id']}",
                "node_type": "gene",
                "display_label": shorten_gene_label(str(row["target_gene_name"])),
                "value": len(row["lncrna_ids"]),
            }
        )
    for row in final_edges:
        edges.append(
            {
                "source": f"lncrna_{safe_int(row.get('lncrna_gene_id'))}",
                "target": f"gene_{safe_int(row.get('target_gene_id'))}",
                "edge_type": "regulation",
                "weight": round(safe_float(row.get("binding_affinity")), 6),
            }
        )
    return nodes, edges, selected_lnc_ids, selected_target_ids


def build_fig5c_rows(
    pair_rows: Sequence[dict[str, Any]],
    *,
    ranked_candidate_rows: Sequence[dict[str, Any]],
    trait_names: Sequence[str],
    max_lnc_labels: int = FIG5C_TOP_LNCRNAS,
) -> list[dict[str, Any]]:
    selected_ranked_rows = [dict(row) for row in ranked_candidate_rows[:max_lnc_labels]]
    selected_lnc_ids = [safe_int(row.get("lncrna_gene_id")) for row in selected_ranked_rows]
    selected_lookup = {lnc_id: index for index, lnc_id in enumerate(selected_lnc_ids)}
    output: list[dict[str, Any]] = []
    for row in pair_rows:
        lnc_id = safe_int(row.get("lncrna_gene_id"))
        trait_name = str(row.get("trait_name") or "")
        if lnc_id not in selected_lookup:
            continue
        if trait_name not in trait_names:
            continue
        output.append(
            {
                "trait_name": trait_name,
                "lncrna_gene_id": lnc_id,
                "lncrna_name": str(row.get("lncrna_name") or ""),
                "display_label": shorten_gene_label(str(row.get("lncrna_name") or "")),
                "target_count": safe_int(row.get("target_count")),
                "mean_ba": round(safe_float(row.get("mean_ba")), 6),
            }
        )
    output.sort(
        key=lambda row: (
            trait_names.index(row["trait_name"]),
            selected_lookup.get(row["lncrna_gene_id"], 999),
            row["display_label"],
        )
    )
    return output


def build_case_assets(
    network_rows: Sequence[dict[str, Any]],
    *,
    flagship_case: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    trait_name = str(flagship_case.get("trait_name") or "")
    lnc_id = safe_int(flagship_case.get("lncrna_gene_id"))
    filtered = [
        row
        for row in network_rows
        if str(row.get("trait_name") or "") == trait_name
        and safe_int(row.get("lncrna_gene_id")) == lnc_id
    ]
    filtered = sorted(
        filtered,
        key=lambda row: (
            -safe_float(row.get("binding_affinity")),
            shorten_gene_label(str(row.get("target_gene_name") or "")),
        ),
    )[:FIG5_CASE_TARGET_LIMIT]
    if not filtered:
        raise ValueError("No network rows available for selected flagship case")
    target_literature_support: dict[int, bool] = {}
    for row in filtered:
        target_gene_id = safe_int(row.get("target_gene_id"))
        if target_gene_id <= 0:
            continue
        target_literature_support[target_gene_id] = target_literature_support.get(target_gene_id, False) or safe_bool(
            row.get("trait_literature_support")
        )
    candidate_targets = len(target_literature_support)
    flagship_targets_with_trait_literature_support = sum(
        1 for supported in target_literature_support.values() if supported
    )
    manifest = {
        "trait_name": trait_name,
        "lncrna_gene_id": lnc_id,
        "lncrna_name": str(flagship_case.get("lncrna_name") or ""),
        "candidate_targets": candidate_targets,
        "high_affinity_edges": sum(1 for row in filtered if safe_float(row.get("binding_affinity")) >= 100.0),
        "ba_range": f"{min(safe_float(row.get('binding_affinity')) for row in filtered):.2f}-{max(safe_float(row.get('binding_affinity')) for row in filtered):.2f}",
        "best_edge_conservation_count": safe_int(flagship_case.get("best_edge_conservation_count")),
        "rewiring_label": str(flagship_case.get("rewiring_label") or "species_specific"),
        "epigenomic_support_class": str(flagship_case.get("epigenomic_support_class") or "other"),
        "flagship_targets_with_trait_literature_support": flagship_targets_with_trait_literature_support,
        "flagship_targets_with_trait_literature_support_fraction": round(
            flagship_targets_with_trait_literature_support / candidate_targets, 6
        ) if candidate_targets else 0.0,
    }
    nodes = [
        {
            "node_id": f"trait_{trait_name}",
            "node_type": "trait",
            "display_label": format_trait_display_label(trait_name),
            "value": len(filtered),
        },
        {
            "node_id": f"lncrna_{lnc_id}",
            "node_type": "lncrna",
            "display_label": shorten_gene_label(str(flagship_case.get("lncrna_name") or "")),
            "value": len(filtered),
        },
    ]
    edges = [
        {
            "source": f"trait_{trait_name}",
            "target": f"lncrna_{lnc_id}",
            "edge_type": "trait_anchor",
            "weight": 1.0,
        }
    ]
    for row in filtered:
        target_id = safe_int(row.get("target_gene_id"))
        target_name = str(row.get("target_gene_name") or "")
        nodes.append(
            {
                "node_id": f"gene_{target_id}",
                "node_type": "gene",
                "display_label": shorten_gene_label(target_name),
                "value": safe_float(row.get("binding_affinity")),
            }
        )
        edges.append(
            {
                "source": f"lncrna_{lnc_id}",
                "target": f"gene_{target_id}",
                "edge_type": "regulation",
                "weight": round(safe_float(row.get("binding_affinity")), 6),
            }
        )
    return manifest, nodes, edges


def build_table4_rows(pair_rows: Sequence[dict[str, Any]], *, trait_order: Sequence[str]) -> list[dict[str, Any]]:
    order_index = {name: index for index, name in enumerate(trait_order)}
    rows = [dict(row) for row in pair_rows if str(row.get("trait_name") or "") in order_index]
    rows.sort(
        key=lambda row: (
            order_index[str(row.get("trait_name") or "")],
            -safe_int(row.get("target_count")),
            -safe_int(row.get("high_affinity_edge_count")),
            -safe_int(row.get("best_edge_conservation_count")),
            safe_int(row.get("lncrna_gene_id")),
        )
    )
    output: list[dict[str, Any]] = []
    for row in rows:
        note = (
            f"{safe_int(row.get('target_count'))} targets; "
            f"{safe_int(row.get('high_affinity_edge_count'))} high-affinity edges; "
            f"{str(row.get('epigenomic_support_class') or 'other')} context"
        )
        output.append(
            {
                "trait_name": row["trait_name"],
                "candidate_lncRNA": row["lncrna_name"],
                "species": "human",
                "candidate_target_count": row["target_count"],
                "high_affinity_edges": row["high_affinity_edge_count"],
                "mean_ba": row["mean_ba"],
                "max_ba": row["max_ba"],
                "best_edge_conservation_count": row["best_edge_conservation_count"],
                "rewiring_label": row["rewiring_label"],
                "epigenomic_support_class": row["epigenomic_support_class"],
                "prioritization_note": note,
            }
        )
    return output


def build_table6_rows(
    trait_summary_rows: Sequence[dict[str, Any]],
    *,
    network_rows: Sequence[dict[str, Any]],
    pair_rows: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    network_by_trait: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in network_rows:
        trait_name = str(row.get("trait_name") or "")
        if trait_name:
            network_by_trait[trait_name].append(dict(row))

    pair_by_trait: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pair_rows:
        trait_name = str(row.get("trait_name") or "")
        if trait_name:
            pair_by_trait[trait_name].append(dict(row))

    output: list[dict[str, Any]] = []
    for summary_row in trait_summary_rows:
        trait_id = safe_int(summary_row.get("trait_id"))
        trait_name = str(summary_row.get("trait_name") or "")
        trait_network_rows = network_by_trait.get(trait_name, [])
        target_support: dict[int, bool] = {}
        for row in trait_network_rows:
            target_gene_id = safe_int(row.get("target_gene_id"))
            if target_gene_id <= 0:
                continue
            target_support[target_gene_id] = target_support.get(target_gene_id, False) or safe_bool(
                row.get("trait_literature_support")
            )
        unique_target_gene_count = safe_int(summary_row.get("unique_target_gene_count")) or len(target_support)
        literature_supported_target_gene_count = sum(1 for supported in target_support.values() if supported)
        literature_supported_target_fraction = round(
            literature_supported_target_gene_count / unique_target_gene_count, 6
        ) if unique_target_gene_count else 0.0

        trait_pair_rows = rank_trait_lnc_candidates(pair_by_trait.get(trait_name, []))
        if trait_pair_rows:
            flagship_case = select_flagship_case(trait_pair_rows, flagship_trait_name=trait_name)
            flagship_lnc_id = safe_int(flagship_case.get("lncrna_gene_id"))
            flagship_lncrna_name = str(flagship_case.get("lncrna_name") or "")
        else:
            flagship_case = {}
            flagship_lnc_id = 0
            flagship_lncrna_name = ""

        flagship_target_support: dict[int, bool] = {}
        for row in trait_network_rows:
            if safe_int(row.get("lncrna_gene_id")) != flagship_lnc_id:
                continue
            target_gene_id = safe_int(row.get("target_gene_id"))
            if target_gene_id <= 0:
                continue
            flagship_target_support[target_gene_id] = flagship_target_support.get(target_gene_id, False) or safe_bool(
                row.get("trait_literature_support")
            )
        flagship_candidate_target_count = len(flagship_target_support)
        flagship_targets_with_trait_literature_support = sum(
            1 for supported in flagship_target_support.values() if supported
        )
        flagship_targets_with_trait_literature_support_fraction = round(
            flagship_targets_with_trait_literature_support / flagship_candidate_target_count, 6
        ) if flagship_candidate_target_count else 0.0

        output.append(
            {
                "trait_id": trait_id,
                "trait_name": trait_name,
                "unique_target_gene_count": unique_target_gene_count,
                "literature_supported_target_gene_count": literature_supported_target_gene_count,
                "literature_supported_target_fraction": literature_supported_target_fraction,
                "flagship_lncrna_name": flagship_lncrna_name,
                "flagship_candidate_target_count": flagship_candidate_target_count,
                "flagship_targets_with_trait_literature_support": flagship_targets_with_trait_literature_support,
                "flagship_targets_with_trait_literature_support_fraction": flagship_targets_with_trait_literature_support_fraction,
            }
        )
    return output


def format_trait_display_label(trait_name: str) -> str:
    normalized = (trait_name or "").strip()
    return FIG5_TRAIT_LABEL_MAP.get(normalized, normalized)


def format_genomic_window_label(chromosome: str, start: int, end: int) -> str:
    return f"{chromosome}:{start / 1_000_000:.1f}-{end / 1_000_000:.1f} Mb"


def format_conservation_class(count: Any) -> str:
    numeric = safe_int(count)
    return f"{numeric}-species" if numeric > 0 else "species-specific"


def format_edge_class_label(label: str) -> str:
    normalized = (label or "species_specific").strip().replace("_", "-")
    return normalized or "species-specific"


def format_epigenomic_context_label(label: str) -> str:
    normalized = (label or "other").strip()
    mapping = {
        "bivalent_like": "bivalent-like",
        "active_like": "active-like",
        "active_like_non_bivalent": "active-like",
    }
    return mapping.get(normalized, normalized.replace("_", "-"))


def format_fig5d_evidence_lines(manifest: dict[str, Any]) -> list[str]:
    edge_class = format_edge_class_label(str(manifest.get("rewiring_label") or "species_specific"))
    conservation_class = format_conservation_class(manifest.get("best_edge_conservation_count"))
    lines = [
        f"Trait: {format_trait_display_label(str(manifest['trait_name']))}",
        f"Candidate lncRNA: {manifest['lncrna_name']}",
        f"Displayed targets: {manifest['candidate_targets']}",
        f"High-affinity edges: {manifest['high_affinity_edges']}",
        f"BA range: {manifest['ba_range']}",
        f"Edge class: {edge_class}, {conservation_class}",
        f"Epigenomic context: {format_epigenomic_context_label(str(manifest.get('epigenomic_support_class') or 'other'))}",
    ]
    if "flagship_targets_with_trait_literature_support" in manifest:
        lines.append(
            f"Lit.-backed targets: {safe_int(manifest.get('flagship_targets_with_trait_literature_support'))}/{safe_int(manifest.get('candidate_targets'))}"
        )
    return lines


def render_fig4a(rows: Sequence[dict[str, Any]], svg_path: Path, png_path: Path) -> None:
    mark_order = [row["mark_name"] for row in rows if row["cell_line"] == DEFAULT_CELL_LINE_SUBSET[0]]
    cell_lines = DEFAULT_CELL_LINE_SUBSET
    values = np.full((len(mark_order), len(cell_lines)), np.nan)
    annot = np.empty((len(mark_order), len(cell_lines)), dtype=object)
    row_lookup = {(row["mark_name"], row["cell_line"]): row for row in rows}
    for i, mark_name in enumerate(mark_order):
        for j, cell_line in enumerate(cell_lines):
            row = row_lookup[(mark_name, cell_line)]
            if row["availability_status"] == "NA":
                annot[i, j] = "NA"
            else:
                values[i, j] = safe_float(row.get("overlap_fraction"))
                annot[i, j] = f"{100.0 * safe_float(row.get('overlap_fraction')):.1f}%"
    cmap = plt.get_cmap("YlOrRd").copy()
    cmap.set_bad("#D9D9D9")
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    sns.heatmap(
        values,
        cmap=cmap,
        vmin=0.0,
        vmax=np.nanmax(values) if np.isfinite(values).any() else 1.0,
        annot=annot,
        fmt="",
        xticklabels=cell_lines,
        yticklabels=mark_order,
        linewidths=0.5,
        linecolor="#F0F0F0",
        cbar_kws={"label": "Overlap fraction"},
        ax=ax,
    )
    ax.set_xlabel("Cell line")
    ax.set_ylabel("Mark")
    ax.tick_params(axis="x", labelsize=9)
    ax.tick_params(axis="y", labelsize=9)
    fig.text(0.73, 0.02, "Gray = unavailable experiment", fontsize=9, color="#4B5563")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    save_figure(fig, svg_path, png_path)


def render_fig4b(rows: Sequence[dict[str, Any]], svg_path: Path, png_path: Path) -> None:
    cohorts = ["all_human_edges", "high_affinity"]
    cohort_titles = {
        "all_human_edges": "All human edge-cell-line observations",
        "high_affinity": "BA ≥ 100 edge-cell-line observations",
    }
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), sharex=False)
    for ax, cohort in zip(axes, cohorts, strict=True):
        cohort_rows = [row for row in rows if row["cohort"] == cohort]
        labels = [row["display_label"] for row in reversed(cohort_rows)]
        fractions = [safe_float(row.get("fraction")) for row in reversed(cohort_rows)]
        total = sum(safe_int(row.get("regulation_cell_count")) for row in cohort_rows)
        ax.barh(labels, fractions, color="#0B3954" if cohort == "all_human_edges" else "#C81D25")
        ax.set_title(f"{cohort_titles[cohort]} (n={total:,})")
        ax.set_xlabel("Fraction of regulation × cell-line observations")
        ax.set_xlim(0.0, max(fractions) * 1.12 if fractions else 1.0)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value * 100:.0f}%"))
    fig.tight_layout()
    save_figure(fig, svg_path, png_path)


def render_fig4c(rows: Sequence[dict[str, Any]], svg_path: Path, png_path: Path) -> None:
    plot_rows = [row for row in rows if row["context_class"] in {"bivalent_like", "active_like_non_bivalent", "other"}]
    class_order = ["bivalent_like", "active_like_non_bivalent", "other"]
    labels = ["Bivalent-like", "Active-like", "Other"]
    grouped = [[safe_float(row.get("binding_affinity")) for row in plot_rows if row["context_class"] == key] for key in class_order]
    fig, ax = plt.subplots(figsize=(8, 5.4))
    ax.boxplot(grouped, tick_labels=labels, patch_artist=True, boxprops={"facecolor": "#BFD7EA"})
    for index, values in enumerate(grouped, start=1):
        ax.text(index, max(values) * 1.02 if values else 0.5, f"n={len(values)}", ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("Binding affinity")
    fig.tight_layout()
    save_figure(fig, svg_path, png_path)


def render_fig4d(manifest_rows: Sequence[dict[str, Any]], track_rows: Sequence[dict[str, Any]], svg_path: Path, png_path: Path) -> None:
    fig, axes = plt.subplots(len(manifest_rows), 1, figsize=(12, 3.2 * max(1, len(manifest_rows))))
    if len(manifest_rows) == 1:
        axes = [axes]
    grouped_tracks: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in track_rows:
        grouped_tracks[(safe_int(row.get("regulation_id")), str(row.get("cell_line") or ""))].append(row)
    for ax, manifest in zip(axes, manifest_rows, strict=True):
        key = (safe_int(manifest.get("regulation_id")), str(manifest.get("cell_line") or ""))
        rows = grouped_tracks.get(key, [])
        if not rows:
            ax.text(0.5, 0.5, "No overlap tracks available", ha="center", va="center")
            ax.axis("off")
            continue
        mark_names = sorted({str(row.get("mark_name") or "") for row in rows})
        start = min(safe_int(row.get("peak_start")) for row in rows)
        end = max(safe_int(row.get("peak_end")) for row in rows)
        target_start = safe_int(manifest.get("target_start"), start)
        target_end = safe_int(manifest.get("target_end"), end)
        region_start = min(start, target_start)
        region_end = max(end, target_end)
        ax.add_patch(
            Rectangle(
                (target_start, -0.3),
                max(1, target_end - target_start),
                len(mark_names) + 0.6,
                facecolor="#FDE68A",
                alpha=0.25,
                edgecolor="none",
            )
        )
        for y_index, mark_name in enumerate(mark_names):
            mark_rows = [row for row in rows if str(row.get("mark_name") or "") == mark_name]
            for row in mark_rows:
                ax.hlines(
                    y=y_index,
                    xmin=safe_int(row.get("peak_start")),
                    xmax=safe_int(row.get("peak_end")),
                    linewidth=5,
                    color="#0B3954" if mark_name != "DNase-HS" else "#C81D25",
                )
        midpoint = target_start + max(1, target_end - target_start) / 2.0
        ax.text(
            midpoint,
            len(mark_names) - 0.28,
            "predicted triplex target region",
            ha="center",
            va="bottom",
            fontsize=7.5,
            color="#7C2D12",
            clip_on=False,
        )
        ax.set_xlim(region_start, region_end)
        ax.set_ylim(-0.45, len(mark_names) - 0.05)
        ax.set_yticks(range(len(mark_names)))
        ax.set_yticklabels(mark_names)
        ax.set_title(
            f"{manifest['exemplar_kind'].replace('_', ' ').title()}: {shorten_gene_label(manifest['lncrna_name'])} → {shorten_gene_label(manifest['target_gene_name'])} ({manifest['cell_line']})",
            fontsize=11,
        )
        ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: f"{value / 1_000_000:.2f}"))
        ax.tick_params(axis="x", labelsize=8)
        ax.set_xlabel(format_genomic_window_label(str(manifest['target_chromosome']), region_start, region_end))
    fig.tight_layout()
    save_figure(fig, svg_path, png_path)


def draw_tripartite(ax: plt.Axes, nodes: Sequence[dict[str, Any]], edges: Sequence[dict[str, Any]], *, title: str | None = None) -> None:
    node_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        node_groups[str(node.get("node_type") or "other")].append(node)
    x_positions = {"trait": 0.0, "lncrna": 1.0, "gene": 2.18}
    positions: dict[str, tuple[float, float]] = {}
    for node_type, items in node_groups.items():
        count = len(items)
        y_values = np.linspace(0.84, 0.16, count) if count > 1 else np.array([0.5])
        for y, item in zip(y_values, items, strict=True):
            positions[str(item["node_id"])] = (x_positions.get(node_type, 1.5), float(y))
    max_reg_weight = max((safe_float(edge.get("weight")) for edge in edges if edge.get("edge_type") == "regulation"), default=1.0)
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source not in positions or target not in positions:
            continue
        linewidth = 1.2
        color = "#B0B0B0"
        alpha = 0.7
        if edge.get("edge_type") == "regulation":
            linewidth = 0.9 + 2.2 * safe_float(edge.get("weight")) / max(max_reg_weight, 1e-9)
            color = "#C81D25"
            alpha = 0.38
        elif edge.get("edge_type") in {"trait_anchor", "trait_lncrna"}:
            linewidth = 1.5
            color = "#7B8794"
            alpha = 0.85
        else:
            linewidth = 1.1
            color = "#BCCCDC"
            alpha = 0.6
        ax.plot(
            [positions[source][0], positions[target][0]],
            [positions[source][1], positions[target][1]],
            color=color,
            linewidth=linewidth,
            alpha=alpha,
            zorder=1,
        )
    palette = {"trait": "#D97706", "lncrna": "#C81D25", "gene": "#087E8B"}
    base_sizes = {"trait": 320.0, "lncrna": 180.0, "gene": 90.0}
    size_scales = {"trait": 28.0, "lncrna": 18.0, "gene": 10.0}
    for node in nodes:
        node_id = str(node.get("node_id") or "")
        node_type = str(node.get("node_type") or "other")
        x, y = positions[node_id]
        value = max(1.0, safe_float(node.get("value")))
        size = base_sizes.get(node_type, 120.0) + size_scales.get(node_type, 12.0) * math.sqrt(value)
        ax.scatter([x], [y], s=size, color=palette.get(node_type, "#999999"), edgecolors="white", linewidth=1.2, zorder=2)
        label = str(node.get("display_label") or "")
        if node_type == "gene":
            ax.text(x + 0.08, y, label, ha="left", va="center", fontsize=8.5, color="#102A43")
        elif node_type == "trait":
            ax.text(x, y - 0.085, label, ha="center", va="top", fontsize=9.5, color="#7C2D12", fontweight="bold")
        else:
            ax.text(
                x - 0.08,
                y,
                label,
                ha="right",
                va="center",
                fontsize=8.5,
                color="#7C2D12",
                fontweight="bold",
                bbox={"boxstyle": "round,pad=0.16", "facecolor": "white", "edgecolor": "none", "alpha": 0.82},
            )
    ax.set_xlim(-0.25, 2.55)
    ax.set_ylim(0.0, 1.0)
    ax.axis("off")
    if title:
        ax.set_title(title)


def render_fig5a(nodes: Sequence[dict[str, Any]], edges: Sequence[dict[str, Any]], svg_path: Path, png_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    draw_tripartite(ax, nodes, edges, title=None)
    fig.tight_layout()
    save_figure(fig, svg_path, png_path)


def render_fig5b(rows: Sequence[dict[str, Any]], svg_path: Path, png_path: Path) -> None:
    if not rows:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "No ranking rows available", ha="center", va="center")
        ax.axis("off")
        save_figure(fig, svg_path, png_path)
        return
    heatmap = []
    row_labels = []
    for row in rows:
        rewiring_score = {"species_specific": 0, "rewired": 1, "conserved": 2}.get(str(row.get("rewiring_label")), 0)
        epigenomic_score = {"other": 0, "active_like": 1, "bivalent_like": 2}.get(str(row.get("epigenomic_support_class")), 0)
        flagship_score = 1 if row.get("flagship_membership") else 0
        raw_values = [
            safe_float(row.get("trait_count")),
            safe_float(row.get("target_count")),
            safe_float(row.get("high_affinity_edge_count")),
            safe_float(row.get("mean_ba")),
            safe_float(row.get("max_ba")),
            safe_float(row.get("best_edge_conservation_count")),
            float(rewiring_score),
            float(epigenomic_score),
            float(flagship_score),
        ]
        heatmap.append(raw_values)
        row_labels.append(shorten_gene_label(str(row.get("lncrna_name") or "")))
    matrix = np.array(heatmap, dtype=float)
    normalized = np.zeros_like(matrix)
    for col_index in range(matrix.shape[1]):
        column = matrix[:, col_index]
        max_value = float(np.max(column)) if len(column) else 0.0
        min_value = float(np.min(column)) if len(column) else 0.0
        if math.isclose(max_value, min_value):
            normalized[:, col_index] = 0.0
        else:
            normalized[:, col_index] = (column - min_value) / (max_value - min_value)
    fig, ax = plt.subplots(figsize=(11, max(5.4, len(rows) * 0.38)))
    sns.heatmap(
        normalized,
        cmap="YlGnBu",
        xticklabels=[
            "Traits",
            "Targets",
            "BA>=100",
            "Mean BA",
            "Max BA",
            "Conservation",
            "Rewiring",
            "Epigenomics",
            "Flagship",
        ],
        yticklabels=row_labels,
        cbar_kws={"label": "Column-normalized score"},
        ax=ax,
    )
    ax.text(
        0.0,
        -0.19,
        "Column-normalized visualization only; not effect size",
        transform=ax.transAxes,
        fontsize=9,
        color="#555555",
        ha="left",
        va="top",
        bbox={"boxstyle": "round,pad=0.24", "facecolor": "#FFFFFF", "edgecolor": "#CBD5E1", "alpha": 0.92},
    )
    fig.subplots_adjust(left=0.28, right=0.97, top=0.97, bottom=0.27)
    save_figure(fig, svg_path, png_path)


def render_fig5c(rows: Sequence[dict[str, Any]], *, trait_names: Sequence[str], svg_path: Path, png_path: Path) -> None:
    ordered_trait_names = [name for name in trait_names if any(row["trait_name"] == name for row in rows)]
    lnc_labels = list(dict.fromkeys(row["display_label"] for row in rows))
    y_index = {label: idx for idx, label in enumerate(lnc_labels)}
    x_index = {name: idx for idx, name in enumerate(ordered_trait_names)}
    fig, ax = plt.subplots(figsize=(10.6, max(4.8, len(lnc_labels) * 0.42)))
    xs, ys, sizes, colors = [], [], [], []
    for row in rows:
        xs.append(x_index[row["trait_name"]])
        ys.append(y_index[row["display_label"]])
        sizes.append(35 + 18 * math.sqrt(max(1, safe_int(row.get("target_count")))))
        colors.append(safe_float(row.get("mean_ba")))
    scatter = ax.scatter(xs, ys, s=sizes, c=colors, cmap="OrRd", alpha=0.68, edgecolors="#334E68", linewidth=0.35)
    ax.set_xticks(range(len(ordered_trait_names)))
    ax.set_xticklabels([format_trait_display_label(name) for name in ordered_trait_names], rotation=18, ha="right")
    ax.set_yticks(range(len(lnc_labels)))
    ax.set_yticklabels(lnc_labels)
    ax.set_xlabel("Trait")
    ax.set_ylabel("Candidate lncRNA")
    ax.grid(axis="x", alpha=0.15)
    ax.grid(axis="y", alpha=0.08)
    fig.colorbar(scatter, ax=ax, label="Mean BA")
    legend_counts = sorted({max(1, safe_int(row.get("target_count"))) for row in rows})
    if legend_counts:
        representative_counts = sorted({legend_counts[0], legend_counts[len(legend_counts) // 2], legend_counts[-1]})
        handles = [
            ax.scatter([], [], s=35 + 18 * math.sqrt(count), color="#F8CFA9", alpha=0.9, edgecolors="#334E68", linewidth=0.35)
            for count in representative_counts
        ]
        legend = ax.legend(
            handles,
            [str(count) for count in representative_counts],
            title="Bubble size = number of PCG targets",
            loc="upper center",
            bbox_to_anchor=(0.50, -0.30),
            ncol=len(representative_counts),
            frameon=True,
        )
        legend.get_title().set_fontsize(9)
    fig.subplots_adjust(left=0.18, right=0.86, top=0.95, bottom=0.34)
    save_figure(fig, svg_path, png_path)


def render_fig5d(
    *,
    manifest: dict[str, Any],
    nodes: Sequence[dict[str, Any]],
    edges: Sequence[dict[str, Any]],
    svg_path: Path,
    png_path: Path,
) -> None:
    fig = plt.figure(figsize=(13, 5.8))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.5, 1.0])
    ax_network = fig.add_subplot(grid[0])
    ax_text = fig.add_subplot(grid[1])
    draw_tripartite(ax_network, nodes, edges, title=None)
    ax_text.axis("off")
    evidence_rows = [line.split(": ", 1) if ": " in line else [line, ""] for line in format_fig5d_evidence_lines(manifest)]
    ax_text.text(0.0, 0.98, "Evidence card", fontsize=13, fontweight="bold", va="top")
    table = ax_text.table(
        cellText=evidence_rows,
        colLabels=["Evidence", "Value"],
        cellLoc="left",
        colLoc="left",
        colWidths=[0.42, 0.56],
        bbox=[0.0, 0.05, 0.98, 0.84],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.25)
    for (row_index, col_index), cell in table.get_celld().items():
        cell.set_edgecolor("#D9E2EC")
        if row_index == 0:
            cell.set_facecolor("#EEF2F7")
            cell.set_text_props(weight="bold", color="#102A43")
        else:
            cell.set_facecolor("#FFFFFF" if row_index % 2 else "#F8FAFC")
            if col_index == 0:
                cell.set_text_props(weight="bold", color="#334E68")
    fig.tight_layout()
    save_figure(fig, svg_path, png_path)


def render_suppfig6_companion_access(svg_path: Path, png_path: Path) -> None:
    panels = [
        {
            "label": "A",
            "title": "Query interface",
            "body": ["Filter candidate", "lncRNA-PCG edges", "by gene, trait, species"],
            "accent": "#0B3954",
        },
        {
            "label": "B",
            "title": "Network view",
            "body": ["Inspect lncRNA", "target modules", "and evidence layers"],
            "accent": "#C81D25",
        },
        {
            "label": "C",
            "title": "Genome-browser view",
            "body": ["Review target loci", "with local chromatin", "context tracks"],
            "accent": "#087E8B",
        },
        {
            "label": "D",
            "title": "Export / API workflow",
            "body": ["Download tables", "or inspect local", "FastAPI /docs schema"],
            "accent": "#D97706",
        },
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.2))
    fig.patch.set_facecolor("white")
    for ax, panel in zip(axes.flat, panels, strict=True):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.add_patch(Rectangle((0.03, 0.08), 0.94, 0.84, facecolor="#F8FAFC", edgecolor="#CBD5E1", linewidth=1.4))
        ax.add_patch(Rectangle((0.03, 0.78), 0.94, 0.14, facecolor=panel["accent"], edgecolor=panel["accent"]))
        ax.text(0.07, 0.85, str(panel["label"]), color="white", fontsize=16, fontweight="bold", va="center")
        ax.text(0.16, 0.85, str(panel["title"]), color="white", fontsize=13, fontweight="bold", va="center")
        for index, line in enumerate(panel["body"]):
            ax.text(0.09, 0.62 - index * 0.15, line, color="#102A43", fontsize=13, va="center")
        ax.add_patch(Rectangle((0.68, 0.18), 0.20, 0.34, facecolor="#E2E8F0", edgecolor="#94A3B8", linewidth=1.0))
        ax.add_patch(Rectangle((0.71, 0.46), 0.14, 0.035, facecolor=panel["accent"], edgecolor=panel["accent"]))
        ax.add_patch(Rectangle((0.71, 0.38), 0.14, 0.035, facecolor="#FFFFFF", edgecolor="#94A3B8"))
        ax.add_patch(Rectangle((0.71, 0.30), 0.14, 0.035, facecolor="#FFFFFF", edgecolor="#94A3B8"))
        ax.text(0.78, 0.13, "local", color="#64748B", fontsize=9, ha="center")
    fig.suptitle("Human LncRNA Atlas Companion: local reproducibility and evidence-inspection layer", fontsize=15, fontweight="bold")
    fig.text(0.5, 0.025, "No public deployment URL is assumed; API documentation is available through FastAPI /docs when the backend is run locally.", ha="center", fontsize=10, color="#475569")
    fig.tight_layout(rect=[0, 0.05, 1, 0.94])
    save_figure(fig, svg_path, png_path)


def build_fig4d_manifest_rows(fig4c_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped_by_regulation: dict[int, set[str]] = defaultdict(set)
    for row in fig4c_rows:
        grouped_by_regulation[safe_int(row.get("regulation_id"))].add(str(row.get("cell_line") or ""))
    candidates_by_kind: dict[str, list[dict[str, Any]]] = {"active_like": [], "bivalent_like": []}
    for row in fig4c_rows:
        context_class = str(row.get("context_class") or "other")
        if context_class == "active_like_non_bivalent":
            candidate_kind = "active_like"
        elif context_class == "bivalent_like":
            candidate_kind = "bivalent_like"
        else:
            continue
        candidates_by_kind[candidate_kind].append(dict(row))
    output: list[dict[str, Any]] = []
    for exemplar_kind in ["active_like", "bivalent_like"]:
        candidates = candidates_by_kind[exemplar_kind]
        if not candidates:
            continue
        candidates.sort(
            key=lambda row: (
                -safe_float(row.get("binding_affinity")),
                -safe_int(row.get("mark_count")),
                -len(grouped_by_regulation[safe_int(row.get("regulation_id"))]),
                safe_int(row.get("regulation_id")),
            )
        )
        row = candidates[0]
        output.append(
            {
                "exemplar_kind": exemplar_kind,
                "regulation_id": row["regulation_id"],
                "cell_line": row["cell_line"],
                "lncrna_name": row["lncrna_name"],
                "target_gene_name": row["target_gene_name"],
                "binding_affinity": row["binding_affinity"],
                "mark_signature": row["mark_signature"],
                "mark_count": row["mark_count"],
                "supporting_cell_line_count": len(grouped_by_regulation[safe_int(row.get("regulation_id"))]),
                "target_chromosome": row["target_chromosome"],
                "target_start": row["target_start"],
                "target_end": row["target_end"],
            }
        )
    return output


def build_fig4d_track_rows(
    manifest_rows: Sequence[dict[str, Any]],
    overlap_rows: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in overlap_rows:
        for manifest in manifest_rows:
            if safe_int(row.get("regulation_id")) == safe_int(manifest.get("regulation_id")) and str(row.get("cell_line") or "") == str(manifest.get("cell_line") or ""):
                output.append(
                    {
                        "exemplar_kind": manifest["exemplar_kind"],
                        "regulation_id": safe_int(row.get("regulation_id")),
                        "cell_line": str(row.get("cell_line") or ""),
                        "mark_name": str(row.get("mark_name") or ""),
                        "peak_chr": str(row.get("peak_chr") or ""),
                        "peak_start": safe_int(row.get("peak_start")),
                        "peak_end": safe_int(row.get("peak_end")),
                        "target_chromosome": str(row.get("target_chromosome") or ""),
                        "target_start": safe_int(row.get("target_start")),
                        "target_end": safe_int(row.get("target_end")),
                    }
                )
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate batch-2 research-first paper figure assets.")
    parser.add_argument("--repo-root", default=".", help="Repository root (default: current directory)")
    parser.add_argument(
        "--backend-env",
        default="frontend/backend/.env",
        help="Backend .env file used for database connectivity",
    )
    parser.add_argument(
        "--out-dir",
        default="paper_figures",
        help="Output directory for generated figure assets (default: paper_figures)",
    )
    parser.add_argument(
        "--generated-at",
        default=None,
        help="Optional fixed UTC timestamp for metadata (default: now)",
    )
    parser.add_argument(
        "--source-commit",
        default=None,
        help="Optional git ref to record as source_commit provenance (default: HEAD)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    env_path = (repo_root / args.backend_env).resolve()
    out_dir = (repo_root / args.out_dir).resolve()
    fig4_dir = out_dir / "fig4"
    fig5_dir = out_dir / "fig5"
    tables_dir = out_dir / "tables"
    shared_dir = out_dir / "shared"
    supp_dir = out_dir / "supplementary"

    generated_at = args.generated_at or utc_now_iso()
    source_commit_ref = str(args.source_commit or "HEAD").strip() or "HEAD"
    source_commit = git_commit_sha(repo_root, source_commit_ref)
    if args.source_commit and source_commit == "unknown":
        raise RuntimeError(f"Unable to resolve --source-commit {args.source_commit!r} via git rev-parse")

    edge_presence_path = shared_dir / "edge_corepair_presence.tsv"
    node_presence_path = shared_dir / "node_core_presence.tsv"
    if not edge_presence_path.exists() or not node_presence_path.exists():
        raise FileNotFoundError("Missing batch-1 shared TSVs; generate batch-1 assets before batch-2")

    with connect_db(env_path) as conn:
        inventory_rows = fetch_epigenomic_inventory_rows(conn)
        total_candidate_regulations = fetch_total_candidate_regulations(conn, min_ba=100.0)
        overlap_rows_for_fig4 = fetch_overlap_detail_rows(
            conn,
            min_ba=None,
            marks=PAPER_BASELINE_MARKS,
            cell_lines=DEFAULT_CELL_LINE_SUBSET,
        )
        overlap_summary_rows = query_dict_rows(
            conn,
            """
                SELECT
                    o.mark_name,
                    o.cell_type AS cell_line,
                    COUNT(DISTINCT o.regulation_id) AS overlapped_regulation_count
                FROM mv_lncrna_chipseq_overlaps o
                WHERE o.binding_affinity >= %s
                  AND o.mark_name = ANY(%s)
                  AND o.cell_type = ANY(%s)
                GROUP BY o.mark_name, o.cell_type
                ORDER BY o.mark_name, o.cell_type
            """,
            [100.0, PAPER_BASELINE_MARKS, DEFAULT_CELL_LINE_SUBSET],
        )

        fig4a_rows = build_fig4a_rows(
            inventory_rows=inventory_rows,
            overlap_rows=overlap_summary_rows,
            total_candidate_regulations=total_candidate_regulations,
            marks=PAPER_BASELINE_MARKS,
            cell_lines=DEFAULT_CELL_LINE_SUBSET,
        )
        fig4b_rows = build_fig4b_rows(overlap_rows_for_fig4)
        fig4c_rows = build_fig4c_rows(
            [row for row in overlap_rows_for_fig4 if safe_float(row.get("binding_affinity")) >= 100.0]
        )
        fig4d_manifest_rows = build_fig4d_manifest_rows(fig4c_rows)
        fig4d_track_rows = build_fig4d_track_rows(fig4d_manifest_rows, overlap_rows_for_fig4)
        table2_rows = build_table2_rows(
            inventory_rows,
            baseline_marks=PAPER_BASELINE_MARKS,
            extended_marks=EXTENDED_TRACKS,
        )

        trait_summary_db_rows = fetch_trait_summary_rows_db(conn)
        trait_summary_rows = build_trait_summary_rows(trait_summary_db_rows)[:FIG5_TOP_TRAITS]
        top_trait_ids = [safe_int(row.get("trait_id")) for row in trait_summary_rows]
        network_rows = fetch_trait_network_rows(conn, top_trait_ids)
        edge_presence_map = load_edge_presence_map(edge_presence_path)
        node_presence_map = load_node_presence_map(node_presence_path)
        context_by_regulation: dict[int, str] = {}
        for row in fig4c_rows:
            regulation_id = safe_int(row.get("regulation_id"))
            existing = context_by_regulation.get(regulation_id)
            context_by_regulation[regulation_id] = pick_best_context_class(
                [item for item in [existing, str(row.get("context_class") or "other")] if item]
            )
        pair_rows = build_trait_pair_rows(
            network_rows,
            edge_presence_map=edge_presence_map,
            node_presence_map=node_presence_map,
            context_by_regulation=context_by_regulation,
        )
        candidate_rows = rank_trait_lnc_candidates(build_lnc_candidate_rows(pair_rows))[:FIG5_RANKING_TOP_N]

        flagship_trait_name = trait_summary_rows[0]["trait_name"] if trait_summary_rows else ""
        flagship_selection_rows = build_flagship_trait_selection_rows(
            trait_summary_rows,
            flagship_trait_name=flagship_trait_name,
        )
        fig5a_nodes, fig5a_edges, selected_lnc_ids, _ = build_fig5a_asset_rows(
            network_rows,
            flagship_trait_name=flagship_trait_name,
        )
        for row in candidate_rows:
            if safe_int(row.get("lncrna_gene_id")) in selected_lnc_ids:
                row["flagship_membership"] = True
        ranked_pair_rows = [
            row for row in pair_rows if str(row.get("trait_name") or "") == flagship_trait_name
        ]
        ranked_pair_rows = rank_trait_lnc_candidates(ranked_pair_rows)
        flagship_case = select_flagship_case(ranked_pair_rows, flagship_trait_name=flagship_trait_name)
        fig5d_manifest, fig5d_nodes, fig5d_edges = build_case_assets(network_rows, flagship_case=flagship_case)
        trait_names = [str(row.get("trait_name") or "") for row in trait_summary_rows]
        fig5c_rows = build_fig5c_rows(pair_rows, ranked_candidate_rows=candidate_rows, trait_names=trait_names)
        table4_rows = build_table4_rows(pair_rows, trait_order=trait_names)
        table6_rows = build_table6_rows(
            trait_summary_rows,
            network_rows=network_rows,
            pair_rows=pair_rows,
        )

    fig4a_tsv = fig4_dir / "fig4A_overlap_summary.tsv"
    fig4a_svg = fig4_dir / "fig4A_overlap_summary.svg"
    fig4a_png = fig4_dir / "fig4A_overlap_summary.png"
    fig4a_meta = fig4_dir / "fig4A_metadata.json"
    write_tsv(
        fig4a_tsv,
        fig4a_rows,
        [
            "mark_name",
            "cell_line",
            "experiment_count",
            "peak_count",
            "overlapped_regulation_count",
            "overlap_fraction",
            "availability_status",
        ],
    )
    render_fig4a(fig4a_rows, fig4a_svg, fig4a_png)
    write_json(
        fig4a_meta,
        panel_metadata(
            panel_id="Figure4A",
            title="Histone-mark / DNase overlap summary",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[repo_root / "docs/paper/submission_snapshot.md"],
            output_paths=[fig4a_tsv, fig4a_svg, fig4a_png],
            filters={
                "marks": PAPER_BASELINE_MARKS,
                "cell_lines": DEFAULT_CELL_LINE_SUBSET,
                "min_ba": 100,
                "na_rule": "inventory_defined_absence",
            },
        ),
    )

    fig4b_tsv = fig4_dir / "fig4B_mark_signatures.tsv"
    fig4b_svg = fig4_dir / "fig4B_mark_signatures.svg"
    fig4b_png = fig4_dir / "fig4B_mark_signatures.png"
    fig4b_meta = fig4_dir / "fig4B_metadata.json"
    write_tsv(
        fig4b_tsv,
        fig4b_rows,
        ["cohort", "signature_label", "display_label", "regulation_cell_count", "fraction", "rank"],
    )
    render_fig4b(fig4b_rows, fig4b_svg, fig4b_png)
    write_json(
        fig4b_meta,
        panel_metadata(
            panel_id="Figure4B",
            title="Mark-overlap context classes",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[repo_root / "docs/paper/figures.md"],
            output_paths=[fig4b_tsv, fig4b_svg, fig4b_png],
            filters={
                "cell_lines": DEFAULT_CELL_LINE_SUBSET,
                "top_signatures": FIG4_SIGNATURE_TOP_N,
                "high_affinity_rule": "BA >= 100",
            },
        ),
    )

    fig4c_tsv = fig4_dir / "fig4C_bivalent_contrast.tsv"
    fig4c_svg = fig4_dir / "fig4C_bivalent_contrast.svg"
    fig4c_png = fig4_dir / "fig4C_bivalent_contrast.png"
    fig4c_meta = fig4_dir / "fig4C_metadata.json"
    write_tsv(
        fig4c_tsv,
        fig4c_rows,
        [
            "regulation_id",
            "cell_line",
            "lncrna_gene_id",
            "lncrna_core_id",
            "lncrna_name",
            "target_gene_id",
            "target_core_id",
            "target_gene_name",
            "binding_affinity",
            "mark_signature",
            "mark_count",
            "context_class",
            "target_chromosome",
            "target_start",
            "target_end",
        ],
    )
    render_fig4c(fig4c_rows, fig4c_svg, fig4c_png)
    write_json(
        fig4c_meta,
        panel_metadata(
            panel_id="Figure4C",
            title="Bivalent versus non-bivalent contrast",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[repo_root / "docs/paper/manuscript.md"],
            output_paths=[fig4c_tsv, fig4c_svg, fig4c_png],
            filters={
                "min_ba": 100,
                "bivalent_rule": "same regulation_id and same cell_line contain H3K4me3 + H3K27me3",
            },
        ),
    )

    fig4d_manifest_tsv = fig4_dir / "fig4D_igv_manifest.tsv"
    fig4d_tracks_tsv = fig4_dir / "fig4D_overlap_tracks.tsv"
    fig4d_svg = fig4_dir / "fig4D_igv_snapshots.svg"
    fig4d_png = fig4_dir / "fig4D_igv_snapshots.png"
    fig4d_meta = fig4_dir / "fig4D_metadata.json"
    write_tsv(
        fig4d_manifest_tsv,
        fig4d_manifest_rows,
        [
            "exemplar_kind",
            "regulation_id",
            "cell_line",
            "lncrna_name",
            "target_gene_name",
            "binding_affinity",
            "mark_signature",
            "mark_count",
            "supporting_cell_line_count",
            "target_chromosome",
            "target_start",
            "target_end",
        ],
    )
    write_tsv(
        fig4d_tracks_tsv,
        fig4d_track_rows,
        [
            "exemplar_kind",
            "regulation_id",
            "cell_line",
            "mark_name",
            "peak_chr",
            "peak_start",
            "peak_end",
            "target_chromosome",
            "target_start",
            "target_end",
        ],
    )
    render_fig4d(fig4d_manifest_rows, fig4d_track_rows, fig4d_svg, fig4d_png)
    write_json(
        fig4d_meta,
        panel_metadata(
            panel_id="Figure4D",
            title="Representative local epigenomic tracks",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[fig4c_tsv],
            output_paths=[fig4d_manifest_tsv, fig4d_tracks_tsv, fig4d_svg, fig4d_png],
            filters={
                "selection_rule": "BA desc -> mark_count desc -> supporting_cell_line_count desc -> regulation_id asc",
                "exemplar_classes": ["active_like", "bivalent_like"],
            },
        ),
    )

    table2_tsv = tables_dir / "table2_epigenomic_inventory.tsv"
    write_tsv(
        table2_tsv,
        table2_rows,
        ["mark_name", "inventory_group", "cell_line_count", "experiment_count", "peak_count"],
    )

    fig5a_nodes_tsv = fig5_dir / "fig5A_tripartite_nodes.tsv"
    fig5a_edges_tsv = fig5_dir / "fig5A_tripartite_edges.tsv"
    fig5a_svg = fig5_dir / "fig5A_tripartite_network.svg"
    fig5a_png = fig5_dir / "fig5A_tripartite_network.png"
    fig5a_meta = fig5_dir / "fig5A_metadata.json"
    write_tsv(fig5a_nodes_tsv, fig5a_nodes, ["node_id", "node_type", "display_label", "value"])
    write_tsv(fig5a_edges_tsv, fig5a_edges, ["source", "target", "edge_type", "weight"])
    render_fig5a(fig5a_nodes, fig5a_edges, fig5a_svg, fig5a_png)
    write_json(
        fig5a_meta,
        panel_metadata(
            panel_id="Figure5A",
            title="Simplified trait–lncRNA–PCG tripartite network",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[edge_presence_path, node_presence_path],
            output_paths=[fig5a_nodes_tsv, fig5a_edges_tsv, fig5a_svg, fig5a_png],
            filters={
                "flagship_trait": flagship_trait_name,
                "top_lncrnas": FIG5_TRIPARTITE_TOP_LNCRNAS,
                "top_targets": FIG5_TRIPARTITE_TOP_TARGETS,
                "trait_selection_sort": [
                    "unique_lncrna_count desc",
                    "unique_target_gene_count desc",
                    "max_ba desc",
                    "trait_id asc",
                ],
                "displayed_node_count": len(fig5a_nodes),
                "full_exported_candidate_edge_count": len(fig5a_edges),
            },
        ),
    )

    fig5b_tsv = fig5_dir / "fig5B_ranking_matrix.tsv"
    fig5b_svg = fig5_dir / "fig5B_ranking_matrix.svg"
    fig5b_png = fig5_dir / "fig5B_ranking_matrix.png"
    fig5b_meta = fig5_dir / "fig5B_metadata.json"
    write_tsv(
        fig5b_tsv,
        candidate_rows,
        [
            "lncrna_gene_id",
            "lncrna_name",
            "trait_count",
            "target_count",
            "high_affinity_edge_count",
            "mean_ba",
            "max_ba",
            "best_edge_conservation_count",
            "rewiring_label",
            "epigenomic_support_class",
            "flagship_membership",
        ],
    )
    render_fig5b(candidate_rows, fig5b_svg, fig5b_png)
    write_json(
        fig5b_meta,
        panel_metadata(
            panel_id="Figure5B",
            title="Integrated candidate lncRNA ranking matrix",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[edge_presence_path, node_presence_path, fig4c_tsv],
            output_paths=[fig5b_tsv, fig5b_svg, fig5b_png],
            filters={
                "top_n": FIG5_RANKING_TOP_N,
                "ranking_sort": [
                    "trait_count desc",
                    "target_count desc",
                    "high_affinity_edge_count desc",
                    "best_edge_conservation_count desc",
                    "max_ba desc",
                    "lncrna_gene_id asc",
                ],
            },
            notes=["The heatmap is a column-normalized visualization only, not regulatory effect size."],
        ),
    )

    fig5c_tsv = fig5_dir / "fig5C_trait_specificity.tsv"
    fig5c_svg = fig5_dir / "fig5C_trait_specificity.svg"
    fig5c_png = fig5_dir / "fig5C_trait_specificity.png"
    fig5c_meta = fig5_dir / "fig5C_metadata.json"
    write_tsv(
        fig5c_tsv,
        fig5c_rows,
        ["trait_name", "lncrna_gene_id", "lncrna_name", "display_label", "target_count", "mean_ba"],
    )
    render_fig5c(fig5c_rows, trait_names=trait_names, svg_path=fig5c_svg, png_path=fig5c_png)
    write_json(
        fig5c_meta,
        panel_metadata(
            panel_id="Figure5C",
            title="Shared versus trait-specific regulators",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[fig5b_tsv],
            output_paths=[fig5c_tsv, fig5c_svg, fig5c_png],
            filters={"trait_names": trait_names},
        ),
    )

    fig5d_manifest_tsv = fig5_dir / "fig5D_case_manifest.tsv"
    fig5d_nodes_tsv = fig5_dir / "fig5D_case_nodes.tsv"
    fig5d_edges_tsv = fig5_dir / "fig5D_case_edges.tsv"
    fig5d_svg = fig5_dir / "fig5D_case_study.svg"
    fig5d_png = fig5_dir / "fig5D_case_study.png"
    fig5d_meta = fig5_dir / "fig5D_metadata.json"
    write_tsv(
        fig5d_manifest_tsv,
        [fig5d_manifest],
        [
            "trait_name",
            "lncrna_gene_id",
            "lncrna_name",
            "candidate_targets",
            "high_affinity_edges",
            "ba_range",
            "best_edge_conservation_count",
            "rewiring_label",
            "epigenomic_support_class",
            "flagship_targets_with_trait_literature_support",
            "flagship_targets_with_trait_literature_support_fraction",
        ],
    )
    write_tsv(fig5d_nodes_tsv, fig5d_nodes, ["node_id", "node_type", "display_label", "value"])
    write_tsv(fig5d_edges_tsv, fig5d_edges, ["source", "target", "edge_type", "weight"])
    render_fig5d(manifest=fig5d_manifest, nodes=fig5d_nodes, edges=fig5d_edges, svg_path=fig5d_svg, png_path=fig5d_png)
    write_json(
        fig5d_meta,
        panel_metadata(
            panel_id="Figure5D",
            title="Focused flagship case study",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[fig5b_tsv, fig4c_tsv],
            output_paths=[fig5d_manifest_tsv, fig5d_nodes_tsv, fig5d_edges_tsv, fig5d_svg, fig5d_png],
            filters={
                "flagship_trait": flagship_trait_name,
                "case_target_limit": FIG5_CASE_TARGET_LIMIT,
                "case_selection_filters": [
                    "best_edge_conservation_count >= 1",
                    "epigenomic_support_class != other",
                ],
            },
            notes=[
                "Displayed subset is separate from the full exported flagship subnetwork.",
                f"Displayed targets: {safe_int(fig5d_manifest.get('candidate_targets'))}; high-affinity edges: {safe_int(fig5d_manifest.get('high_affinity_edges'))}.",
            ],
        ),
    )


    table5_tsv = tables_dir / "table5_flagship_trait_selection.tsv"
    write_tsv(
        table5_tsv,
        flagship_selection_rows,
        [
            "flagship_rank",
            "trait_id",
            "trait_name",
            "unique_lncrna_count",
            "unique_target_gene_count",
            "regulation_count",
            "max_ba",
            "is_flagship",
        ],
    )

    table6_tsv = tables_dir / "table6_trait_literature_support.tsv"
    supp_table1_tsv = tables_dir / "supp_table1_trait_literature_support.tsv"
    table6_fieldnames = [
        "trait_id",
        "trait_name",
        "unique_target_gene_count",
        "literature_supported_target_gene_count",
        "literature_supported_target_fraction",
        "flagship_lncrna_name",
        "flagship_candidate_target_count",
        "flagship_targets_with_trait_literature_support",
        "flagship_targets_with_trait_literature_support_fraction",
    ]
    write_tsv(
        table6_tsv,
        table6_rows,
        table6_fieldnames,
    )
    write_tsv(
        supp_table1_tsv,
        table6_rows,
        table6_fieldnames,
    )

    suppfig6_svg = supp_dir / "suppfig6_companion_access.svg"
    suppfig6_png = supp_dir / "suppfig6_companion_access.png"
    suppfig6_meta = supp_dir / "suppfig6_companion_access.metadata.json"
    render_suppfig6_companion_access(suppfig6_svg, suppfig6_png)
    write_json(
        suppfig6_meta,
        panel_metadata(
            panel_id="SupplementaryFigure6",
            title="Human LncRNA Atlas Companion local access layer",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[],
            output_paths=[suppfig6_svg, suppfig6_png],
            filters={
                "panels": ["Query interface", "Network view", "Genome-browser view", "Export / API workflow"],
                "public_deployment_url": None,
            },
            notes=[
                "No public deployment URL is used in this manuscript.",
                "FastAPI /docs is available when the repository-local backend is run locally.",
                "Supplementary Figure 6 depicts Human LncRNA Atlas Companion local access and programmatic export workflows.",
                "This companion layer supports reproducibility and evidence inspection rather than serving as a primary result.",
            ],
        ),
    )

    table4_tsv = tables_dir / "table4_trait_prioritization.tsv"
    write_tsv(
        table4_tsv,
        table4_rows,
        [
            "trait_name",
            "candidate_lncRNA",
            "species",
            "candidate_target_count",
            "high_affinity_edges",
            "mean_ba",
            "max_ba",
            "best_edge_conservation_count",
            "rewiring_label",
            "epigenomic_support_class",
            "prioritization_note",
        ],
    )

    for path in [
        fig4a_tsv,
        fig4b_tsv,
        fig4c_tsv,
        fig4d_manifest_tsv,
        table2_tsv,
        fig5a_nodes_tsv,
        fig5a_edges_tsv,
        fig5b_tsv,
        fig5c_tsv,
        fig5d_manifest_tsv,
        table4_tsv,
        table5_tsv,
        table6_tsv,
        supp_table1_tsv,
        suppfig6_svg,
    ]:
        print(f"Wrote: {display_path(path, repo_root)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
