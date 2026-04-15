#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import psycopg2
import psycopg2.extras
import seaborn as sns
from matplotlib.lines import Line2D
from mpl_toolkits.axes_grid1.inset_locator import inset_axes


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(__file__).resolve()

DEFAULT_SPECIES_ORDER = (
    {"species_id": 1, "species_code": "human", "display_name": "Human"},
    {"species_id": 2, "species_code": "chimp", "display_name": "Chimpanzee"},
    {"species_id": 3, "species_code": "macaque", "display_name": "Macaque"},
    {"species_id": 4, "species_code": "marmoset", "display_name": "Marmoset"},
)

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


def _clean_numeric_string(value: str) -> int:
    return int(value.replace(",", "").strip())


def _extract_number(text: str, patterns: Sequence[str]) -> int:
    number_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if not match:
            continue
        raw_value = match.group(1)
        lowered = raw_value.lower()
        if lowered in number_words:
            return number_words[lowered]
        return _clean_numeric_string(raw_value)
    raise ValueError(f"unable to extract numeric value using patterns: {patterns}")


def _extract_cell_line_subset(submission_md: str) -> list[str]:
    marker = "Cross-mark comparison panels in the main text default to the following six human cell lines:"
    if marker not in submission_md:
        return list(DEFAULT_CELL_LINE_SUBSET)

    tail = submission_md.split(marker, 1)[1]
    found: list[str] = []
    for line in tail.splitlines():
        stripped = line.strip()
        if not stripped:
            if found:
                break
            continue
        match = re.match(r"-\s+`([^`]+)`", stripped)
        if match:
            found.append(match.group(1))
            continue
        if found:
            break
    return found or list(DEFAULT_CELL_LINE_SUBSET)


def parse_frozen_submission_snapshot(
    figures_md: str,
    submission_md: str,
    manuscript_md: str,
) -> dict[str, Any]:
    species_count = _extract_number(
        figures_md + "\n" + manuscript_md,
        [
            r"`([\d,]+)`\s+primate species",
            r"across\s+([a-z]+)\s+primate species",
        ],
    )
    candidate_relationships = _extract_number(
        figures_md + "\n" + manuscript_md,
        [
            r"`([\d,]+)`\s+predicted lncRNA to protein-coding gene relationships",
            r"\*\*([\d,]+)\*\*\s+predicted lncRNA to protein-coding gene relationships",
        ],
    )
    baseline_experiments = _extract_number(
        submission_md + "\n" + figures_md,
        [
            r"Combined paper-facing baseline\*\*:\s+`([\d,]+)`\s+experiments,\s+`[\d,]+`\s+peaks",
            r"`([\d,]+)`\s+experiments,\s+`[\d,]+`\s+peaks",
            r"\*\*([\d,]+)\s+experiments\*\*",
        ],
    )
    baseline_peaks = _extract_number(
        submission_md + "\n" + figures_md,
        [
            r"Combined paper-facing baseline\*\*:\s+`[\d,]+`\s+experiments,\s+`([\d,]+)`\s+peaks",
            r"`[\d,]+`\s+experiments,\s+`([\d,]+)`\s+peaks",
            r"\*\*([\d,]+)\s+peaks\*\*",
        ],
    )
    return {
        "species_count": species_count,
        "candidate_relationships": candidate_relationships,
        "baseline_experiments": baseline_experiments,
        "baseline_peaks": baseline_peaks,
        "baseline_marks": list(PAPER_BASELINE_MARKS),
        "extended_tracks": list(EXTENDED_TRACKS),
        "cell_line_subset": _extract_cell_line_subset(submission_md),
    }


def _species_codes(species_order: Sequence[dict[str, Any]]) -> list[str]:
    return [str(spec["species_code"]) for spec in species_order]


def _species_id_to_code(species_order: Sequence[dict[str, Any]]) -> dict[int, str]:
    return {int(spec["species_id"]): str(spec["species_code"]) for spec in species_order}


def _conservation_bits(
    present_species_ids: set[int],
    species_order: Sequence[dict[str, Any]],
) -> tuple[dict[str, int], str, int]:
    bits: dict[str, int] = {}
    labels: list[str] = []
    count = 0
    for spec in species_order:
        code = str(spec["species_code"])
        present = 1 if int(spec["species_id"]) in present_species_ids else 0
        bits[code] = present
        labels.append(str(present))
        count += present
    return bits, "".join(labels), count


def build_node_presence_rows(
    rows: Iterable[dict[str, Any]],
    species_order: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        core_id = int(row["core_id"])
        entry = grouped.setdefault(
            core_id,
            {
                "core_id": core_id,
                "gene_type": row.get("gene_type") or "",
                "canonical_symbol": row.get("canonical_symbol") or "",
                "human_ensembl_id": row.get("human_ensembl_id") or "",
                "_species_ids": set(),
            },
        )
        entry["_species_ids"].add(int(row["species_id"]))

    output: list[dict[str, Any]] = []
    for core_id in sorted(grouped):
        entry = grouped[core_id]
        bits, label, count = _conservation_bits(entry["_species_ids"], species_order)
        row = {
            "core_id": core_id,
            "gene_type": entry["gene_type"],
            "canonical_symbol": entry["canonical_symbol"],
            "human_ensembl_id": entry["human_ensembl_id"],
            **bits,
            "conservation_label": label,
            "conservation_count": count,
        }
        output.append(row)
    return output


def _weighted_mean(total_weight: int, weighted_sum: float) -> float:
    if total_weight <= 0:
        return 0.0
    return weighted_sum / float(total_weight)


def _quantile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(float(value) for value in values)
    index = (len(ordered) - 1) * max(0.0, min(1.0, q))
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return float(ordered[lower])
    lower_value = ordered[lower]
    upper_value = ordered[upper]
    return float(lower_value * (upper - index) + upper_value * (index - lower))


def _round_up_to_step(value: float, step: float) -> float:
    if value <= 0:
        return float(step)
    return float(math.ceil(value / step) * step)


def _short_accession_label(value: str) -> str:
    stripped = value.split(".", 1)[0].strip()
    match = re.match(r"^(CATG|ENSG)0*([0-9]+)$", stripped)
    if not match:
        return stripped
    prefix, digits = match.groups()
    return f"{prefix}{digits[-6:].zfill(6)}"


def format_lncRNA_display_label(symbol: str, fallback_id: str) -> str:
    primary = (symbol or "").strip()
    secondary = (fallback_id or "").strip()
    if primary and not re.match(r"^(CATG|ENSG)[0-9]+\.[0-9]+$", primary):
        return primary
    if primary:
        return _short_accession_label(primary)
    if secondary:
        return _short_accession_label(secondary)
    return ""


def build_ba_summary_rows(
    species_values: dict[str, Sequence[float]],
    species_order: Sequence[dict[str, Any]],
    *,
    priority_line: float,
    clip_quantile: float = 0.995,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for spec in species_order:
        code = str(spec["species_code"])
        display_name = str(spec["display_name"])
        values = [float(value) for value in species_values.get(code, [])]
        full_plot_ymax = max(values) if values else 0.0
        p99 = _quantile(values, 0.99)
        p995 = _quantile(values, clip_quantile)
        n_ge_priority = sum(1 for value in values if value >= priority_line)
        total_edges = len(values)
        frac_ge_priority = 0.0 if total_edges == 0 else n_ge_priority / float(total_edges)
        clipped_upper = min(full_plot_ymax, p995) if values else 0.0
        main_plot_ymax = max(priority_line * 2.0, _round_up_to_step(clipped_upper, 10.0))
        output.append(
            {
                "species_code": code,
                "species_name": display_name,
                "total_edges": total_edges,
                "n_ge_100": n_ge_priority,
                "frac_ge_100": round(frac_ge_priority, 6),
                "p99": round(float(p99), 6),
                "p995": round(float(p995), 6),
                "main_plot_ymax": round(float(main_plot_ymax), 6),
                "full_plot_ymax": round(float(full_plot_ymax), 6),
            }
        )
    return output


def build_edge_presence_rows(
    rows: Iterable[dict[str, Any]],
    species_order: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int], dict[str, Any]] = {}
    for row in rows:
        lncrna_core_id = int(row["lncrna_core_id"])
        target_core_id = int(row["target_core_id"])
        key = (lncrna_core_id, target_core_id)
        support_count = int(row.get("supporting_regulation_count") or 1)
        mean_ba = float(
            row.get("mean_ba")
            if row.get("mean_ba") is not None
            else row.get("binding_affinity") or 0.0
        )
        max_ba = float(
            row.get("max_ba")
            if row.get("max_ba") is not None
            else row.get("binding_affinity") or 0.0
        )
        entry = grouped.setdefault(
            key,
            {
                "lncrna_core_id": lncrna_core_id,
                "target_core_id": target_core_id,
                "lncrna_symbol": row.get("lncrna_symbol") or "",
                "target_symbol": row.get("target_symbol") or "",
                "_species_ids": set(),
                "_support_total": 0,
                "_weighted_ba_sum": 0.0,
                "_max_ba": 0.0,
            },
        )
        entry["_species_ids"].add(int(row["species_id"]))
        entry["_support_total"] += support_count
        entry["_weighted_ba_sum"] += mean_ba * support_count
        entry["_max_ba"] = max(entry["_max_ba"], max_ba)

    output: list[dict[str, Any]] = []
    for key in sorted(grouped):
        entry = grouped[key]
        bits, label, count = _conservation_bits(entry["_species_ids"], species_order)
        support_total = int(entry["_support_total"])
        row = {
            "lncrna_core_id": entry["lncrna_core_id"],
            "target_core_id": entry["target_core_id"],
            "lncrna_symbol": entry["lncrna_symbol"],
            "target_symbol": entry["target_symbol"],
            **bits,
            "conservation_label": label,
            "conservation_count": count,
            "supporting_regulation_count": support_total,
            "mean_ba": round(_weighted_mean(support_total, entry["_weighted_ba_sum"]), 6),
            "max_ba": round(float(entry["_max_ba"]), 6),
        }
        output.append(row)
    return output


def build_high_affinity_core_edge_rows(
    rows: Iterable[dict[str, Any]],
    species_order: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int], dict[str, Any]] = {}
    for row in rows:
        key = (int(row["lncrna_core_id"]), int(row["target_core_id"]))
        support_count = int(row.get("supporting_regulation_count") or 1)
        mean_ba = float(
            row.get("mean_ba")
            if row.get("mean_ba") is not None
            else row.get("binding_affinity") or 0.0
        )
        max_ba = float(
            row.get("max_ba")
            if row.get("max_ba") is not None
            else row.get("binding_affinity") or 0.0
        )
        entry = grouped.setdefault(
            key,
            {
                "lncrna_core_id": int(row["lncrna_core_id"]),
                "target_core_id": int(row["target_core_id"]),
                "lncrna_symbol": row.get("lncrna_symbol") or "",
                "lncrna_human_ensembl_id": row.get("lncrna_human_ensembl_id") or "",
                "target_symbol": row.get("target_symbol") or "",
                "_species_ids": set(),
                "_support_total": 0,
                "_weighted_ba_sum": 0.0,
                "_max_ba": 0.0,
            },
        )
        entry["_species_ids"].add(int(row["species_id"]))
        entry["_support_total"] += support_count
        entry["_weighted_ba_sum"] += mean_ba * support_count
        entry["_max_ba"] = max(entry["_max_ba"], max_ba)

    output: list[dict[str, Any]] = []
    for key in sorted(grouped):
        entry = grouped[key]
        bits, label, count = _conservation_bits(entry["_species_ids"], species_order)
        support_total = int(entry["_support_total"])
        output.append(
            {
                "lncrna_core_id": entry["lncrna_core_id"],
                "target_core_id": entry["target_core_id"],
                "lncrna_symbol": entry["lncrna_symbol"],
                "lncrna_human_ensembl_id": entry["lncrna_human_ensembl_id"],
                "target_symbol": entry["target_symbol"],
                **bits,
                "conservation_label": label,
                "conservation_count": count,
                "species_count": count,
                "supporting_regulation_count": support_total,
                "mean_ba": round(_weighted_mean(support_total, entry["_weighted_ba_sum"]), 6),
                "max_ba": round(float(entry["_max_ba"]), 6),
            }
        )
    return output


def build_hub_rows(edge_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    for row in edge_rows:
        lncrna_core_id = int(row["lncrna_core_id"])
        support_count = int(row.get("supporting_regulation_count") or 0)
        mean_ba = float(row.get("mean_ba") or 0.0)
        entry = grouped.setdefault(
            lncrna_core_id,
            {
                "lncrna_core_id": lncrna_core_id,
                "lncrna_symbol": row.get("lncrna_symbol") or "",
                "lncrna_human_ensembl_id": row.get("lncrna_human_ensembl_id") or "",
                "_targets": set(),
                "_supporting_edge_count": 0,
                "_weighted_ba_sum": 0.0,
                "_species_ids": set(),
                "_max_ba": 0.0,
            },
        )
        entry["_targets"].add(int(row["target_core_id"]))
        entry["_supporting_edge_count"] += support_count
        entry["_weighted_ba_sum"] += mean_ba * support_count
        entry["_max_ba"] = max(entry["_max_ba"], float(row.get("max_ba") or 0.0))
        for code in _species_codes(DEFAULT_SPECIES_ORDER):
            if int(row.get(code) or 0):
                species_id = _species_code_to_id(DEFAULT_SPECIES_ORDER)[code]
                entry["_species_ids"].add(species_id)

    output: list[dict[str, Any]] = []
    for lncrna_core_id, entry in grouped.items():
        bits, label, count = _conservation_bits(entry["_species_ids"], DEFAULT_SPECIES_ORDER)
        support_total = int(entry["_supporting_edge_count"])
        output.append(
            {
                "lncrna_core_id": lncrna_core_id,
                "lncrna_symbol": entry["lncrna_symbol"],
                "lncrna_human_ensembl_id": entry["lncrna_human_ensembl_id"],
                **bits,
                "conservation_label": label,
                "species_count": count,
                "unique_target_core_count": len(entry["_targets"]),
                "supporting_edge_count": support_total,
                "mean_outgoing_ba": round(_weighted_mean(support_total, entry["_weighted_ba_sum"]), 6),
                "max_outgoing_ba": round(float(entry["_max_ba"]), 6),
            }
        )

    output.sort(
        key=lambda row: (
            -int(row["unique_target_core_count"]),
            -float(row["mean_outgoing_ba"]),
            -float(row["max_outgoing_ba"]),
            int(row["lncrna_core_id"]),
        )
    )
    return output


def _species_code_to_id(species_order: Sequence[dict[str, Any]]) -> dict[str, int]:
    return {str(spec["species_code"]): int(spec["species_id"]) for spec in species_order}


def build_upset_rows(edge_presence_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = defaultdict(int)
    for row in edge_presence_rows:
        conservation_count = int(row["conservation_count"])
        if conservation_count < 2:
            continue
        counts[str(row["conservation_label"])] += 1

    output: list[dict[str, Any]] = []
    for label, count in counts.items():
        output.append(
            {
                "conservation_label": label,
                "count": count,
                "human": int(label[0]),
                "chimp": int(label[1]),
                "macaque": int(label[2]),
                "marmoset": int(label[3]),
                "conservation_count": int(sum(int(bit) for bit in label)),
            }
        )
    output.sort(
        key=lambda row: (
            -int(row["conservation_count"]),
            -int(row["count"]),
            str(row["conservation_label"]),
        )
    )
    return output


def build_pairwise_sharing_rows(
    presence_rows: Iterable[dict[str, Any]],
    species_order: Sequence[dict[str, Any]],
    *,
    item_type: str,
) -> list[dict[str, Any]]:
    sets_by_species: dict[str, set[Any]] = {str(spec["species_code"]): set() for spec in species_order}
    species_codes = _species_codes(species_order)

    for row in presence_rows:
        if item_type == "edge":
            item_key = (int(row["lncrna_core_id"]), int(row["target_core_id"]))
        else:
            item_key = int(row["core_id"])
        conservation_label = str(row.get("conservation_label") or "")
        for code in species_codes:
            present_value = row.get(code)
            if present_value is None and conservation_label and len(conservation_label) == len(species_codes):
                present_value = conservation_label[species_codes.index(code)]
            if int(present_value or 0):
                sets_by_species[code].add(item_key)

    output: list[dict[str, Any]] = []
    for species_a in species_codes:
        for species_b in species_codes:
            set_a = sets_by_species[species_a]
            set_b = sets_by_species[species_b]
            intersection_count = len(set_a & set_b)
            union_count = len(set_a | set_b)
            jaccard = 0.0 if union_count == 0 else intersection_count / float(union_count)
            output.append(
                {
                    "item_type": item_type,
                    "species_a": species_a,
                    "species_b": species_b,
                    "intersection_count": intersection_count,
                    "union_count": union_count,
                    "jaccard": round(jaccard, 6),
                }
            )
    return output


def build_node_vs_edge_summary(
    node_rows: Iterable[dict[str, Any]],
    edge_rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item_type, rows in (("node", list(node_rows)), ("edge", list(edge_rows))):
        total = len(rows)
        for conservation_count in range(1, 5):
            raw_count = sum(1 for row in rows if int(row["conservation_count"]) == conservation_count)
            proportion = 0.0 if total == 0 else raw_count / float(total)
            output.append(
                {
                    "item_type": item_type,
                    "conservation_count": conservation_count,
                    "raw_count": raw_count,
                    "proportion": round(proportion, 6),
                }
            )
    return output


def build_centrality_rows(edge_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    graph = nx.DiGraph()
    symbol_by_core: dict[int, str] = {}
    ensembl_by_core: dict[int, str] = {}
    outgoing_ba: dict[int, list[float]] = defaultdict(list)
    outgoing_supports: dict[int, int] = defaultdict(int)
    outgoing_targets: dict[int, set[int]] = defaultdict(set)

    for row in edge_rows:
        lncrna_core_id = int(row["lncrna_core_id"])
        target_core_id = int(row["target_core_id"])
        mean_ba = float(row["mean_ba"])
        graph.add_node(lncrna_core_id, node_type="lncRNA")
        graph.add_node(target_core_id, node_type="protein_coding")
        graph.add_edge(
            lncrna_core_id,
            target_core_id,
            weight=mean_ba,
            distance=1.0 / max(mean_ba, 1e-9),
        )
        symbol_by_core[lncrna_core_id] = str(row.get("lncrna_symbol") or "")
        ensembl_by_core[lncrna_core_id] = str(row.get("lncrna_human_ensembl_id") or "")
        outgoing_ba[lncrna_core_id].append(mean_ba)
        outgoing_supports[lncrna_core_id] += int(row.get("supporting_regulation_count") or 0)
        outgoing_targets[lncrna_core_id].add(target_core_id)

    undirected = graph.to_undirected()
    try:
        eigenvector = nx.eigenvector_centrality_numpy(undirected, weight="weight") if undirected.number_of_nodes() else {}
    except Exception:
        eigenvector = {node: 0.0 for node in undirected.nodes}
    clamped_eigenvector = {node: max(float(value), 0.0) for node, value in eigenvector.items()}

    output: list[dict[str, Any]] = []
    for lncrna_core_id in sorted(outgoing_targets):
        mean_outgoing_ba = statistics.fmean(outgoing_ba[lncrna_core_id]) if outgoing_ba[lncrna_core_id] else 0.0
        output.append(
            {
                "core_id": lncrna_core_id,
                "node_type": "lncRNA",
                "canonical_symbol": symbol_by_core.get(lncrna_core_id, ""),
                "human_ensembl_id": ensembl_by_core.get(lncrna_core_id, ""),
                "out_degree": len(outgoing_targets[lncrna_core_id]),
                "eigenvector_centrality": round(float(clamped_eigenvector.get(lncrna_core_id, 0.0)), 8),
                "mean_outgoing_ba": round(float(mean_outgoing_ba), 6),
                "supporting_edge_count": int(outgoing_supports[lncrna_core_id]),
            }
        )

    output.sort(
        key=lambda row: (
            -float(row["eigenvector_centrality"]),
            -int(row["out_degree"]),
            -float(row["mean_outgoing_ba"]),
            int(row["core_id"]),
        )
    )
    return output


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


def panel_metadata(
    *,
    panel_id: str,
    title: str,
    repo_root: Path,
    generated_at: str,
    commit_sha: str,
    input_paths: Sequence[Path],
    output_paths: Sequence[Path],
    filters: dict[str, Any],
    notes: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "panel_id": panel_id,
        "title": title,
        "script": display_path(SCRIPT_PATH, repo_root),
        "generated_at": generated_at,
        "release_commit": commit_sha,
        "inputs": [display_path(path, repo_root) for path in input_paths],
        "outputs": [display_path(path, repo_root) for path in output_paths],
        "filters": filters,
        "notes": list(notes or []),
    }


def query_dict_rows(
    conn: psycopg2.extensions.connection,
    sql: str,
    params: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def git_commit_sha(repo_root: Path) -> str:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            .stdout.strip()
        )
    except Exception:
        return "unknown"


def build_frozen_snapshot_payload(repo_root: Path) -> dict[str, Any]:
    figures_md = (repo_root / "docs/paper/figures.md").read_text(encoding="utf-8")
    submission_md = (repo_root / "docs/paper/submission_snapshot.md").read_text(encoding="utf-8")
    manuscript_md = (repo_root / "docs/paper/manuscript.md").read_text(encoding="utf-8")
    payload = parse_frozen_submission_snapshot(figures_md, submission_md, manuscript_md)
    payload["source_documents"] = [
        "docs/paper/figures.md",
        "docs/paper/submission_snapshot.md",
        "docs/paper/manuscript.md",
    ]
    return payload


def connect_db(env_path: Path) -> psycopg2.extensions.connection:
    env = parse_env_file(env_path)
    return psycopg2.connect(
        host=env["DB_HOST"],
        port=int(env["DB_PORT"]),
        user=env["DB_USER"],
        dbname=env["DB_NAME"],
    )


def fetch_species_rows(conn: psycopg2.extensions.connection) -> list[dict[str, Any]]:
    return query_dict_rows(
        conn,
        """
        SELECT species_id, species_code, display_name, genome_assembly
        FROM species
        WHERE species_id IN (1, 2, 3, 4)
        ORDER BY species_id
        """,
    )


def normalize_species_rows(
    rows: Iterable[dict[str, Any]],
    species_order: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    name_map = {int(spec["species_id"]): str(spec["display_name"]) for spec in species_order}
    code_map = {int(spec["species_id"]): str(spec["species_code"]) for spec in species_order}
    output: list[dict[str, Any]] = []
    for row in rows:
        species_id = int(row["species_id"])
        output.append(
            {
                "species_id": species_id,
                "species_code": code_map.get(species_id, str(row.get("species_code") or "")),
                "display_name": name_map.get(species_id, str(row.get("display_name") or "")),
                "genome_assembly": row.get("genome_assembly") or "",
            }
        )
    output.sort(key=lambda item: int(item["species_id"]))
    return output


def fetch_node_presence_input(conn: psycopg2.extensions.connection) -> list[dict[str, Any]]:
    return query_dict_rows(
        conn,
        """
        SELECT
          cg.core_id,
          cg.gene_type,
          COALESCE(cg.canonical_symbol, '') AS canonical_symbol,
          COALESCE(cg.human_ensembl_id, '') AS human_ensembl_id,
          g.species_id
        FROM genes g
        JOIN core_genes cg ON cg.core_id = g.core_id
        WHERE g.core_id IS NOT NULL
          AND cg.gene_type IN ('lncRNA', 'protein_coding')
        GROUP BY cg.core_id, cg.gene_type, cg.canonical_symbol, cg.human_ensembl_id, g.species_id
        ORDER BY cg.core_id, g.species_id
        """,
    )


def fetch_edge_presence_input(conn: psycopg2.extensions.connection) -> list[dict[str, Any]]:
    return query_dict_rows(
        conn,
        """
        SELECT
          lg.core_id AS lncrna_core_id,
          tg.core_id AS target_core_id,
          r.species_id,
          COALESCE(cl.canonical_symbol, '') AS lncrna_symbol,
          COALESCE(ct.canonical_symbol, '') AS target_symbol,
          COUNT(*) AS supporting_regulation_count,
          AVG(r.binding_affinity) AS mean_ba,
          MAX(r.binding_affinity) AS max_ba
        FROM regulations r
        JOIN genes lg ON lg.gene_id = r.lncrna_gene_id
        JOIN genes tg ON tg.gene_id = r.target_gene_id
        JOIN core_genes cl ON cl.core_id = lg.core_id
        JOIN core_genes ct ON ct.core_id = tg.core_id
        WHERE lg.core_id IS NOT NULL
          AND tg.core_id IS NOT NULL
          AND cl.gene_type = 'lncRNA'
          AND ct.gene_type = 'protein_coding'
        GROUP BY lg.core_id, tg.core_id, r.species_id, cl.canonical_symbol, ct.canonical_symbol
        ORDER BY lg.core_id, tg.core_id, r.species_id
        """,
    )


def fetch_high_affinity_input(conn: psycopg2.extensions.connection) -> list[dict[str, Any]]:
    return query_dict_rows(
        conn,
        """
        SELECT
          lg.core_id AS lncrna_core_id,
          tg.core_id AS target_core_id,
          r.species_id,
          COALESCE(cl.canonical_symbol, '') AS lncrna_symbol,
          COALESCE(cl.human_ensembl_id, '') AS lncrna_human_ensembl_id,
          COALESCE(ct.canonical_symbol, '') AS target_symbol,
          COUNT(*) AS supporting_regulation_count,
          AVG(r.binding_affinity) AS mean_ba,
          MAX(r.binding_affinity) AS max_ba
        FROM regulations r
        JOIN genes lg ON lg.gene_id = r.lncrna_gene_id
        JOIN genes tg ON tg.gene_id = r.target_gene_id
        JOIN core_genes cl ON cl.core_id = lg.core_id
        JOIN core_genes ct ON ct.core_id = tg.core_id
        WHERE lg.core_id IS NOT NULL
          AND tg.core_id IS NOT NULL
          AND cl.gene_type = 'lncRNA'
          AND ct.gene_type = 'protein_coding'
          AND r.binding_affinity >= 100
        GROUP BY lg.core_id, tg.core_id, r.species_id, cl.canonical_symbol, cl.human_ensembl_id, ct.canonical_symbol
        ORDER BY lg.core_id, tg.core_id, r.species_id
        """,
    )


def generate_fig1d(
    *,
    snapshot_payload: dict[str, Any],
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    commit_sha: str,
) -> None:
    tsv_path = fig_dir / "fig1D_kpi.tsv"
    svg_path = fig_dir / "fig1D_kpi.svg"
    png_path = fig_dir / "fig1D_kpi.png"
    meta_path = fig_dir / "fig1D_metadata.json"

    rows = [
        {
            "metric_key": "species_count",
            "display_label": "Primate species",
            "value": snapshot_payload["species_count"],
            "note": "Paper-facing freeze",
        },
        {
            "metric_key": "candidate_relationships",
            "display_label": "Candidate regulatory edges",
            "value": snapshot_payload["candidate_relationships"],
            "note": "Paper-facing freeze",
        },
        {
            "metric_key": "baseline_experiments",
            "display_label": "Epigenomic experiments",
            "value": snapshot_payload["baseline_experiments"],
            "note": "Main-text baseline",
        },
        {
            "metric_key": "baseline_peaks",
            "display_label": "Main-text baseline peaks",
            "value": snapshot_payload["baseline_peaks"],
            "note": "Main-text baseline",
        },
    ]
    write_tsv(tsv_path, rows, ["metric_key", "display_label", "value", "note"])

    fig, axes = plt.subplots(2, 2, figsize=(10, 6))
    fig.patch.set_facecolor("white")
    colors = ["#0B3954", "#087E8B", "#FF5A5F", "#C81D25"]
    for ax, row, color in zip(axes.flat, rows, colors, strict=True):
        ax.set_facecolor("#F7F5F2")
        for spine in ax.spines.values():
            spine.set_color("#D7D2CB")
            spine.set_linewidth(1.2)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.text(0.05, 0.78, row["display_label"], fontsize=11, color="#404040", transform=ax.transAxes)
        ax.text(0.05, 0.38, f"{int(row['value']):,}", fontsize=24, fontweight="bold", color=color, transform=ax.transAxes)
    fig.suptitle("Figure 1D · Frozen paper-facing study scope", fontsize=14, fontweight="bold")
    fig.text(
        0.5,
        0.03,
        "Paper-facing freeze; main-text baseline = 8 core histone marks + DNase-HS",
        ha="center",
        va="center",
        fontsize=9,
        color="#6A6A6A",
    )
    fig.tight_layout(rect=[0, 0.06, 1, 0.94])
    save_figure(fig, svg_path, png_path)

    write_json(
        meta_path,
        panel_metadata(
            panel_id="Figure1D",
            title="Frozen submission snapshot KPI tiles",
            repo_root=repo_root,
            generated_at=generated_at,
            commit_sha=commit_sha,
            input_paths=[
                repo_root / "docs/paper/figures.md",
                repo_root / "docs/paper/submission_snapshot.md",
                repo_root / "docs/paper/manuscript.md",
            ],
            output_paths=[tsv_path, svg_path, png_path],
            filters={"frozen_snapshot_only": True},
        ),
    )


def generate_fig2a(
    *,
    conn: psycopg2.extensions.connection,
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    commit_sha: str,
) -> None:
    tsv_path = fig_dir / "fig2A_ba_distribution.tsv"
    summary_tsv_path = fig_dir / "fig2A_summary.tsv"
    svg_path = fig_dir / "fig2A_ba_distribution.svg"
    png_path = fig_dir / "fig2A_ba_distribution.png"
    meta_path = fig_dir / "fig2A_metadata.json"

    species_values: dict[str, list[float]] = {spec["species_code"]: [] for spec in DEFAULT_SPECIES_ORDER}
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    with conn.cursor() as cursor, tsv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["species_id", "species_code", "species_name", "binding_affinity"])
        cursor.execute(
            """
            SELECT
              r.species_id,
              s.species_code,
              s.display_name AS species_name,
              r.binding_affinity
            FROM regulations r
            JOIN species s ON s.species_id = r.species_id
            WHERE r.species_id IN (1, 2, 3, 4)
              AND r.binding_affinity IS NOT NULL
            ORDER BY r.species_id, r.regulation_id
            """
        )
        for species_id, species_code, species_name, binding_affinity in cursor:
            writer.writerow([species_id, species_code, species_name, binding_affinity])
            species_values[str(species_code)].append(float(binding_affinity))

    ordered_codes = [spec["species_code"] for spec in DEFAULT_SPECIES_ORDER]
    ordered_names = [spec["display_name"] for spec in DEFAULT_SPECIES_ORDER]
    ordered_data = [species_values[code] for code in ordered_codes]
    summary_rows = build_ba_summary_rows(species_values, DEFAULT_SPECIES_ORDER, priority_line=100.0)
    write_tsv(
        summary_tsv_path,
        summary_rows,
        [
            "species_code",
            "species_name",
            "total_edges",
            "n_ge_100",
            "frac_ge_100",
            "p99",
            "p995",
            "main_plot_ymax",
            "full_plot_ymax",
        ],
    )
    summary_by_code = {row["species_code"]: row for row in summary_rows}
    main_plot_ymax = max(float(row["main_plot_ymax"]) for row in summary_rows) if summary_rows else 200.0
    full_plot_ymax = max(float(row["full_plot_ymax"]) for row in summary_rows) if summary_rows else 0.0

    fig, ax = plt.subplots(figsize=(10, 6))
    violin = ax.violinplot(ordered_data, showmeans=False, showmedians=False, showextrema=False)
    palette = ["#0B3954", "#087E8B", "#BFD7EA", "#FF5A5F"]
    for body, color in zip(violin["bodies"], palette, strict=True):
        body.set_facecolor(color)
        body.set_edgecolor("#2B2B2B")
        body.set_alpha(0.75)
    box = ax.boxplot(ordered_data, widths=0.15, patch_artist=True, showfliers=False)
    for patch in box["boxes"]:
        patch.set_facecolor("#F7F5F2")
        patch.set_edgecolor("#2B2B2B")
    for median in box["medians"]:
        median.set_color("#C81D25")
        median.set_linewidth(1.5)
    ax.axhline(100.0, color="#C81D25", linestyle="--", linewidth=1.4, label="BA = 100 priority line")
    ax.set_xticks(range(1, len(ordered_names) + 1))
    ax.set_xticklabels(ordered_names)
    ax.set_ylabel("Binding affinity")
    ax.set_ylim(40, main_plot_ymax)
    for index, code in enumerate(ordered_codes, start=1):
        summary = summary_by_code[code]
        ax.text(
            index,
            44.0,
            f">=100: {float(summary['frac_ge_100']) * 100:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#404040",
        )
    ax.set_title("Figure 2A · Binding-affinity landscape with priority-zone focus")
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.2)

    inset = inset_axes(ax, width="34%", height="38%", loc="upper left", borderpad=1.2)
    inset_violin = inset.violinplot(ordered_data, showmeans=False, showmedians=False, showextrema=False)
    for body, color in zip(inset_violin["bodies"], palette, strict=True):
        body.set_facecolor(color)
        body.set_edgecolor("#2B2B2B")
        body.set_alpha(0.65)
    inset_box = inset.boxplot(ordered_data, widths=0.18, patch_artist=True, showfliers=False)
    for patch in inset_box["boxes"]:
        patch.set_facecolor("#F7F5F2")
        patch.set_edgecolor("#2B2B2B")
    for median in inset_box["medians"]:
        median.set_color("#C81D25")
        median.set_linewidth(1.2)
    inset.axhline(100.0, color="#C81D25", linestyle="--", linewidth=1.0)
    inset.set_ylim(0, max(full_plot_ymax, main_plot_ymax))
    inset.set_xticks(range(1, len(ordered_names) + 1))
    inset.set_xticklabels(["H", "C", "M", "Mm"], fontsize=8)
    inset.set_title("Full range", fontsize=9)
    inset.tick_params(axis="y", labelsize=8)
    inset.grid(axis="y", alpha=0.15)

    fig.subplots_adjust(top=0.88, bottom=0.14, hspace=0.08)
    save_figure(fig, svg_path, png_path)

    write_json(
        meta_path,
        panel_metadata(
            panel_id="Figure2A",
            title="Binding-affinity landscape",
            repo_root=repo_root,
            generated_at=generated_at,
            commit_sha=commit_sha,
            input_paths=[],
            output_paths=[tsv_path, summary_tsv_path, svg_path, png_path],
            filters={
                "priority_line_ba": 100,
                "species_order": ordered_codes,
                "main_plot_ylim": [40, main_plot_ymax],
                "inset_full_range": True,
                "clip_quantile": 0.995,
                "priority_fraction_metric": "fraction_ge_100",
            },
        ),
    )


def generate_fig2b(
    *,
    hub_rows: Sequence[dict[str, Any]],
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    commit_sha: str,
    input_paths: Sequence[Path],
) -> None:
    tsv_path = fig_dir / "fig2B_hubs.tsv"
    svg_path = fig_dir / "fig2B_hubs.svg"
    png_path = fig_dir / "fig2B_hubs.png"
    meta_path = fig_dir / "fig2B_metadata.json"

    top_rows = list(hub_rows[:12])
    for row in top_rows:
        row["display_label"] = format_lncRNA_display_label(
            str(row.get("lncrna_symbol") or ""),
            str(row.get("lncrna_human_ensembl_id") or ""),
        ) or str(row["lncrna_core_id"])
    write_tsv(
        tsv_path,
        top_rows,
        [
            "lncrna_core_id",
            "lncrna_symbol",
            "lncrna_human_ensembl_id",
            "display_label",
            "unique_target_core_count",
            "supporting_edge_count",
            "mean_outgoing_ba",
            "max_outgoing_ba",
            "species_count",
            "conservation_label",
        ],
    )

    plot_rows = list(reversed(top_rows))
    y_positions = list(range(len(plot_rows)))

    fig, ax = plt.subplots(figsize=(10, 6))
    species_color_map = {
        1: "#C81D25",
        2: "#FF8C42",
        3: "#087E8B",
        4: "#0B3954",
    }
    for y_pos, row in zip(y_positions, plot_rows, strict=True):
        value = int(row["unique_target_core_count"])
        species_count = int(row["species_count"])
        ax.hlines(y=y_pos, xmin=0, xmax=value, color="#D7DCE2", linewidth=2.5)
        ax.plot(value, y_pos, "o", color=species_color_map.get(species_count, "#0B3954"), markersize=8)
    ax.set_yticks(y_positions)
    ax.set_yticklabels([row["display_label"] or row["lncrna_core_id"] for row in plot_rows])
    ax.set_xlabel("Unique target core count (BA ≥ 100)")
    ax.set_title("Figure 2B · Top hub lncRNAs in the high-affinity core network")
    ax.grid(axis="x", alpha=0.2)
    ax.legend(
        handles=[
            Line2D([0], [0], marker="o", color="w", label=f"{count} species", markerfacecolor=color, markersize=8)
            for count, color in sorted(species_color_map.items())
        ],
        title="Species count",
        loc="lower right",
        frameon=True,
    )
    fig.subplots_adjust(top=0.88, bottom=0.16, hspace=0.06)
    save_figure(fig, svg_path, png_path)

    write_json(
        meta_path,
        panel_metadata(
            panel_id="Figure2B",
            title="Top hub lncRNAs",
            repo_root=repo_root,
            generated_at=generated_at,
            commit_sha=commit_sha,
            input_paths=input_paths,
            output_paths=[tsv_path, svg_path, png_path],
            filters={
                "min_ba": 100,
                "ranking_metric": "unique_target_core_count",
                "top_n": 12,
                "label_strategy": "shortened_id_fallback",
                "color_metric": "species_count",
            },
        ),
    )


def generate_fig2c(
    *,
    centrality_rows: Sequence[dict[str, Any]],
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    commit_sha: str,
    input_paths: Sequence[Path],
) -> None:
    tsv_path = fig_dir / "fig2C_centrality.tsv"
    svg_path = fig_dir / "fig2C_centrality.svg"
    png_path = fig_dir / "fig2C_centrality.png"
    meta_path = fig_dir / "fig2C_metadata.json"

    write_tsv(
        tsv_path,
        list(centrality_rows),
        [
            "core_id",
            "canonical_symbol",
            "human_ensembl_id",
            "out_degree",
            "eigenvector_centrality",
            "mean_outgoing_ba",
            "supporting_edge_count",
        ],
    )

    top_labels: list[dict[str, Any]] = []
    labeled_ids: set[int] = set()
    for row in list(centrality_rows[:5]) + sorted(
        centrality_rows,
        key=lambda row: (
            -int(row["out_degree"]),
            -float(row["eigenvector_centrality"]),
            int(row["core_id"]),
        ),
    )[:3]:
        core_id = int(row["core_id"])
        if core_id in labeled_ids:
            continue
        labeled_ids.add(core_id)
        top_labels.append(row)
    max_ba = max(float(row["mean_outgoing_ba"]) for row in centrality_rows) if centrality_rows else 1.0
    max_support = max(int(row["supporting_edge_count"]) for row in centrality_rows) if centrality_rows else 1

    fig, ax = plt.subplots(figsize=(10, 6))
    x = [int(row["out_degree"]) for row in centrality_rows]
    y = [float(row["eigenvector_centrality"]) for row in centrality_rows]
    sizes = [60 + 260 * (int(row["supporting_edge_count"]) / max(max_support, 1)) for row in centrality_rows]
    colors = [float(row["mean_outgoing_ba"]) for row in centrality_rows]
    scatter = ax.scatter(x, y, s=sizes, c=colors, cmap="viridis", alpha=0.8, edgecolor="black", linewidth=0.3)
    for row in top_labels:
        label = format_lncRNA_display_label(
            str(row.get("canonical_symbol") or ""),
            str(row.get("human_ensembl_id") or ""),
        ) or str(row["core_id"])
        x_value = int(row["out_degree"])
        y_value = float(row["eigenvector_centrality"])
        x_offset = -6 if x and x_value >= max(x) * 0.9 else 4
        horizontal_alignment = "right" if x_offset < 0 else "left"
        ax.annotate(
            label,
            (x_value, y_value),
            textcoords="offset points",
            xytext=(x_offset, 4),
            fontsize=8,
            ha=horizontal_alignment,
        )
    ax.set_xlabel("Out-degree (unique target cores)")
    ax.set_ylabel("Eigenvector centrality")
    ax.set_xlim(-10, max(x) * 1.1 if x else 1.0)
    ax.set_title("Figure 2C · Centrality landscape of high-affinity lncRNA hubs")
    ax.grid(alpha=0.2)
    colorbar = fig.colorbar(scatter, ax=ax, pad=0.02)
    colorbar.set_label("Mean outgoing BA")
    fig.subplots_adjust(top=0.88, bottom=0.16, hspace=0.06)
    save_figure(fig, svg_path, png_path)

    notes = []
    if len(centrality_rows) > 2500:
        notes.append("Betweenness uses NetworkX approximation when node count exceeds 2,500.")

    write_json(
        meta_path,
        panel_metadata(
            panel_id="Figure2C",
            title="Centrality landscape",
            repo_root=repo_root,
            generated_at=generated_at,
            commit_sha=commit_sha,
            input_paths=input_paths,
            output_paths=[tsv_path, svg_path, png_path],
            filters={
                "min_ba": 100,
                "x_metric": "out_degree",
                "y_metric": "eigenvector_centrality_undirected",
            },
            notes=notes,
        ),
    )


def generate_fig3a(
    *,
    upset_rows: Sequence[dict[str, Any]],
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    commit_sha: str,
    input_paths: Sequence[Path],
) -> None:
    tsv_path = fig_dir / "fig3A_edge_upset.tsv"
    svg_path = fig_dir / "fig3A_edge_upset.svg"
    png_path = fig_dir / "fig3A_edge_upset.png"
    meta_path = fig_dir / "fig3A_metadata.json"

    write_tsv(
        tsv_path,
        list(upset_rows),
        ["conservation_label", "conservation_count", "count", "human", "chimp", "macaque", "marmoset"],
    )

    fig = plt.figure(figsize=(10, 6))
    grid = fig.add_gridspec(2, 1, height_ratios=[3.0, 1.3], hspace=0.05)
    ax_bar = fig.add_subplot(grid[0])
    ax_matrix = fig.add_subplot(grid[1], sharex=ax_bar)

    x_positions = list(range(len(upset_rows)))
    counts = [int(row["count"]) for row in upset_rows]
    color_by_species_count = {
        4: "#0B3954",
        3: "#087E8B",
        2: "#BFD7EA",
    }
    bar_colors = [color_by_species_count.get(int(row["conservation_count"]), "#0B3954") for row in upset_rows]
    ax_bar.bar(x_positions, counts, color=bar_colors)
    ax_bar.set_ylabel("Core-pair count")
    ax_bar.set_title("Figure 3A · Conserved-edge strata across two to four species")
    ax_bar.grid(axis="y", alpha=0.2)

    species_codes = ["human", "chimp", "macaque", "marmoset"]
    y_positions = list(reversed(range(len(species_codes))))
    ax_matrix.set_yticks(y_positions)
    ax_matrix.set_yticklabels(["Human", "Chimpanzee", "Macaque", "Marmoset"])
    ax_matrix.set_ylim(-0.5, len(species_codes) - 0.5)
    ax_matrix.set_xlabel("Conservation label")
    ax_matrix.set_xticks(x_positions)
    ax_matrix.set_xticklabels([row["conservation_label"] for row in upset_rows], rotation=0)
    ax_matrix.grid(False)
    for x_pos, row in zip(x_positions, upset_rows, strict=True):
        row_color = color_by_species_count.get(int(row["conservation_count"]), "#0B3954")
        present_points: list[int] = []
        for y_pos, code in zip(y_positions, species_codes, strict=True):
            present = int(row[code])
            ax_matrix.scatter(x_pos, y_pos, s=80, color=row_color if present else "#D0D0D0", zorder=3)
            if present:
                present_points.append(y_pos)
        if len(present_points) >= 2:
            ax_matrix.plot([x_pos, x_pos], [min(present_points), max(present_points)], color=row_color, linewidth=2)
    for index in range(1, len(upset_rows)):
        if int(upset_rows[index]["conservation_count"]) != int(upset_rows[index - 1]["conservation_count"]):
            separator = index - 0.5
            ax_bar.axvline(separator, color="#D0D0D0", linewidth=1.0)
            ax_matrix.axvline(separator, color="#D0D0D0", linewidth=1.0)

    fig.subplots_adjust(top=0.88, bottom=0.16, hspace=0.06)
    save_figure(fig, svg_path, png_path)

    write_json(
        meta_path,
        panel_metadata(
            panel_id="Figure3A",
            title="UpSet of conserved-edge strata",
            repo_root=repo_root,
            generated_at=generated_at,
            commit_sha=commit_sha,
            input_paths=input_paths,
            output_paths=[tsv_path, svg_path, png_path],
            filters={"min_species_count": 2, "singleton_edges_excluded": True},
        ),
    )


def generate_fig3b(
    *,
    summary_rows: Sequence[dict[str, Any]],
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    commit_sha: str,
    input_paths: Sequence[Path],
) -> None:
    tsv_path = fig_dir / "fig3B_node_vs_edge.tsv"
    svg_path = fig_dir / "fig3B_node_vs_edge.svg"
    png_path = fig_dir / "fig3B_node_vs_edge.png"
    meta_path = fig_dir / "fig3B_metadata.json"

    write_tsv(tsv_path, list(summary_rows), ["item_type", "conservation_count", "raw_count", "proportion"])

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8), sharey=True)
    y_limit = max(float(row["proportion"]) for row in summary_rows) * 1.15 if summary_rows else 1.0
    for ax, item_type, color in zip(axes, ["node", "edge"], ["#087E8B", "#C81D25"], strict=True):
        rows = [row for row in summary_rows if row["item_type"] == item_type]
        xs = [int(row["conservation_count"]) for row in rows]
        ys = [float(row["proportion"]) for row in rows]
        ax.bar(xs, ys, color=color)
        total = sum(int(row["raw_count"]) for row in rows)
        for x_value, y_value, row in zip(xs, ys, rows, strict=True):
            ax.text(x_value, y_value + y_limit * 0.015, f"{int(row['raw_count']):,}", ha="center", va="bottom", fontsize=8)
        ax.set_xticks([1, 2, 3, 4])
        ax.set_xlabel("Species count")
        ax.set_ylim(0, y_limit)
        ax.set_title(f"{item_type.capitalize()} conservation (n={total})")
        ax.grid(axis="y", alpha=0.2)
    axes[0].set_ylabel("Proportion")
    fig.suptitle("Figure 3B · Node conservation versus edge conservation", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    save_figure(fig, svg_path, png_path)

    write_json(
        meta_path,
        panel_metadata(
            panel_id="Figure3B",
            title="Node conservation versus edge conservation",
            repo_root=repo_root,
            generated_at=generated_at,
            commit_sha=commit_sha,
            input_paths=input_paths,
            output_paths=[tsv_path, svg_path, png_path],
            filters={"species_order": [spec["species_code"] for spec in DEFAULT_SPECIES_ORDER]},
        ),
    )


def generate_fig3c(
    *,
    pairwise_rows: Sequence[dict[str, Any]],
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    commit_sha: str,
    input_paths: Sequence[Path],
) -> None:
    tsv_path = fig_dir / "fig3C_pairwise_sharing.tsv"
    svg_path = fig_dir / "fig3C_pairwise_sharing.svg"
    png_path = fig_dir / "fig3C_pairwise_sharing.png"
    meta_path = fig_dir / "fig3C_metadata.json"

    write_tsv(
        tsv_path,
        list(pairwise_rows),
        ["item_type", "species_a", "species_b", "intersection_count", "union_count", "jaccard"],
    )

    species_codes = [spec["species_code"] for spec in DEFAULT_SPECIES_ORDER]
    species_labels = [spec["display_name"] for spec in DEFAULT_SPECIES_ORDER]

    def matrix_for(item_type: str) -> list[list[float]]:
        matrix: list[list[float]] = []
        for species_a in species_codes:
            row: list[float] = []
            for species_b in species_codes:
                match = next(
                    row_data
                    for row_data in pairwise_rows
                    if row_data["item_type"] == item_type
                    and row_data["species_a"] == species_a
                    and row_data["species_b"] == species_b
                )
                row.append(float(match["jaccard"]))
            matrix.append(row)
        return matrix

    node_matrix = matrix_for("node")
    edge_matrix = matrix_for("edge")

    mask = np.eye(len(species_codes), dtype=bool)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
    cbar_ax = fig.add_axes([0.92, 0.2, 0.015, 0.6])
    for index, (ax, matrix, title) in enumerate(
        zip(
            axes,
            [node_matrix, edge_matrix],
            ["Node sharing (Jaccard)", "Edge sharing (Jaccard)"],
            strict=True,
        )
    ):
        sns.heatmap(
            np.array(matrix),
            ax=ax,
            mask=mask,
            cmap="Blues",
            vmin=0.0,
            vmax=1.0,
            annot=True,
            fmt=".2f",
            xticklabels=species_labels,
            yticklabels=species_labels,
            cbar=index == 1,
            cbar_ax=cbar_ax if index == 1 else None,
            square=True,
        )
        ax.set_title(title)
    cbar_ax.set_ylabel("Jaccard index")
    fig.suptitle("Figure 3C · Species-pair sharing heatmaps", fontsize=13, fontweight="bold")
    fig.subplots_adjust(left=0.06, right=0.9, bottom=0.13, top=0.83, wspace=0.08)
    save_figure(fig, svg_path, png_path)

    write_json(
        meta_path,
        panel_metadata(
            panel_id="Figure3C",
            title="Species-pair sharing heatmaps",
            repo_root=repo_root,
            generated_at=generated_at,
            commit_sha=commit_sha,
            input_paths=input_paths,
            output_paths=[tsv_path, svg_path, png_path],
            filters={"metric": "jaccard", "species_order": species_codes},
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate batch-1 research-first paper figure assets.")
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    env_path = (repo_root / args.backend_env).resolve()
    out_dir = (repo_root / args.out_dir).resolve()
    shared_dir = out_dir / "shared"
    fig1_dir = out_dir / "fig1"
    fig2_dir = out_dir / "fig2"
    fig3_dir = out_dir / "fig3"

    generated_at = args.generated_at or utc_now_iso()
    commit_sha = git_commit_sha(repo_root)

    snapshot_payload = build_frozen_snapshot_payload(repo_root)
    snapshot_payload["generated_at"] = generated_at
    snapshot_payload["release_commit"] = commit_sha
    snapshot_json_path = shared_dir / "frozen_submission_snapshot.json"
    write_json(snapshot_json_path, snapshot_payload)

    with connect_db(env_path) as conn:
        species_rows = normalize_species_rows(fetch_species_rows(conn), DEFAULT_SPECIES_ORDER)
        node_presence_rows = build_node_presence_rows(fetch_node_presence_input(conn), DEFAULT_SPECIES_ORDER)
        edge_presence_rows = build_edge_presence_rows(fetch_edge_presence_input(conn), DEFAULT_SPECIES_ORDER)
        high_affinity_edge_rows = build_high_affinity_core_edge_rows(fetch_high_affinity_input(conn), DEFAULT_SPECIES_ORDER)

        species_tsv_path = shared_dir / "species.tsv"
        node_tsv_path = shared_dir / "node_core_presence.tsv"
        edge_tsv_path = shared_dir / "edge_corepair_presence.tsv"
        high_affinity_tsv_path = shared_dir / "high_affinity_core_edges.tsv"

        write_tsv(species_tsv_path, species_rows, ["species_id", "species_code", "display_name", "genome_assembly"])
        write_tsv(
            node_tsv_path,
            node_presence_rows,
            [
                "core_id",
                "gene_type",
                "canonical_symbol",
                "human_ensembl_id",
                "human",
                "chimp",
                "macaque",
                "marmoset",
                "conservation_label",
                "conservation_count",
            ],
        )
        write_tsv(
            edge_tsv_path,
            edge_presence_rows,
            [
                "lncrna_core_id",
                "target_core_id",
                "lncrna_symbol",
                "target_symbol",
                "human",
                "chimp",
                "macaque",
                "marmoset",
                "conservation_label",
                "conservation_count",
                "supporting_regulation_count",
                "mean_ba",
                "max_ba",
            ],
        )
        write_tsv(
            high_affinity_tsv_path,
            high_affinity_edge_rows,
            [
                "lncrna_core_id",
                "target_core_id",
                "lncrna_symbol",
                "lncrna_human_ensembl_id",
                "target_symbol",
                "human",
                "chimp",
                "macaque",
                "marmoset",
                "conservation_label",
                "conservation_count",
                "species_count",
                "supporting_regulation_count",
                "mean_ba",
                "max_ba",
            ],
        )

        generate_fig1d(
            snapshot_payload=snapshot_payload,
            fig_dir=fig1_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            commit_sha=commit_sha,
        )

        generate_fig2a(
            conn=conn,
            fig_dir=fig2_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            commit_sha=commit_sha,
        )

        hub_rows = build_hub_rows(high_affinity_edge_rows)
        centrality_rows = build_centrality_rows(high_affinity_edge_rows)
        generate_fig2b(
            hub_rows=hub_rows,
            fig_dir=fig2_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            commit_sha=commit_sha,
            input_paths=[high_affinity_tsv_path],
        )
        generate_fig2c(
            centrality_rows=centrality_rows,
            fig_dir=fig2_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            commit_sha=commit_sha,
            input_paths=[high_affinity_tsv_path],
        )

        upset_rows = build_upset_rows(edge_presence_rows)
        summary_rows = build_node_vs_edge_summary(node_presence_rows, edge_presence_rows)
        pairwise_rows = build_pairwise_sharing_rows(
            node_presence_rows,
            DEFAULT_SPECIES_ORDER,
            item_type="node",
        ) + build_pairwise_sharing_rows(
            edge_presence_rows,
            DEFAULT_SPECIES_ORDER,
            item_type="edge",
        )
        generate_fig3a(
            upset_rows=upset_rows,
            fig_dir=fig3_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            commit_sha=commit_sha,
            input_paths=[edge_tsv_path],
        )
        generate_fig3b(
            summary_rows=summary_rows,
            fig_dir=fig3_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            commit_sha=commit_sha,
            input_paths=[node_tsv_path, edge_tsv_path],
        )
        generate_fig3c(
            pairwise_rows=pairwise_rows,
            fig_dir=fig3_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            commit_sha=commit_sha,
            input_paths=[node_tsv_path, edge_tsv_path],
        )

    for path in [
        snapshot_json_path,
        species_tsv_path,
        node_tsv_path,
        edge_tsv_path,
        high_affinity_tsv_path,
        fig1_dir / "fig1D_kpi.tsv",
        fig2_dir / "fig2A_ba_distribution.tsv",
        fig2_dir / "fig2A_summary.tsv",
        fig2_dir / "fig2B_hubs.tsv",
        fig2_dir / "fig2C_centrality.tsv",
        fig3_dir / "fig3A_edge_upset.tsv",
        fig3_dir / "fig3B_node_vs_edge.tsv",
        fig3_dir / "fig3C_pairwise_sharing.tsv",
    ]:
        print(f"Wrote: {display_path(path, repo_root)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
