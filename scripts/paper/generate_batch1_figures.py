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
from itertools import combinations
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
DEFAULT_FIG2B_ALIAS_MANIFEST = "docs/paper/fig2b_aliases.tsv"

SUPP_FIG7_BA_THRESHOLDS = (0.0, 100.0, 150.0)
SUPP_FIG7_NULL_ITERATIONS = 1000
SUPP_FIG7_RNG_SEED = 42


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
            r"\*\*([\d,]+)\*\*\s+predicted lncRNA–PCG relationships",
            r"([\d,]+)\s+predicted lncRNA–PCG relationships",
            r"`([\d,]+)`\s+candidate relationships",
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


def fig2b_reference_accession(row: dict[str, Any]) -> str:
    return str(row.get("lncrna_human_ensembl_id") or row.get("lncrna_symbol") or "").strip()


def load_fig2b_alias_manifest(path: Path) -> dict[int, dict[str, str]]:
    alias_rows: dict[int, dict[str, str]] = {}
    if not path.exists():
        return alias_rows
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for raw_row in reader:
            core_id_raw = str(raw_row.get("lncrna_core_id") or "").strip()
            if not core_id_raw:
                continue
            core_id = int(core_id_raw)
            alias_rows[core_id] = {
                "lncrna_core_id": core_id_raw,
                "reference_accession": str(raw_row.get("reference_accession") or "").strip(),
                "display_label": str(raw_row.get("display_label") or "").strip(),
                "notes": str(raw_row.get("notes") or "").strip(),
            }
    return alias_rows


def apply_fig2b_alias_manifest(
    hub_rows: Sequence[dict[str, Any]],
    alias_rows: dict[int, dict[str, str]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in hub_rows:
        updated = dict(row)
        default_label = format_lncRNA_display_label(
            str(updated.get("lncrna_symbol") or ""),
            str(updated.get("lncrna_human_ensembl_id") or ""),
        ) or str(updated["lncrna_core_id"])
        updated["display_label"] = default_label
        alias_row = alias_rows.get(int(updated["lncrna_core_id"]))
        if alias_row:
            alias_label = str(alias_row.get("display_label") or "").strip()
            if alias_label:
                expected_accession = str(alias_row.get("reference_accession") or "").strip()
                actual_accession = fig2b_reference_accession(updated)
                if expected_accession != actual_accession:
                    raise ValueError(
                        "Figure 2B alias reference_accession mismatch for "
                        f"core {updated['lncrna_core_id']}: expected {actual_accession}, got {expected_accession}"
                    )
                updated["display_label"] = alias_label
        output.append(updated)
    return output


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
    *,
    min_conservation_count: int = 2,
    max_conservation_count: int = 4,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    start = max(1, int(min_conservation_count))
    stop = max(start, int(max_conservation_count))
    for item_type, rows in (("node", list(node_rows)), ("edge", list(edge_rows))):
        total = len(rows)
        filtered_total = sum(1 for row in rows if start <= int(row["conservation_count"]) <= stop)
        for conservation_count in range(start, stop + 1):
            raw_count = sum(1 for row in rows if int(row["conservation_count"]) == conservation_count)
            proportion = 0.0 if filtered_total == 0 else raw_count / float(filtered_total)
            output.append(
                {
                    "item_type": item_type,
                    "conservation_count": conservation_count,
                    "raw_count": raw_count,
                    "proportion": round(proportion, 6),
                }
            )
    return output


def format_ba_threshold_label(threshold: float) -> str:
    if threshold <= 0:
        return "All edges"
    if float(threshold).is_integer():
        return f"BA ≥ {int(threshold)}"
    return f"BA ≥ {threshold:g}"


def build_robustness_threshold_rows(
    species_edge_rows: Sequence[dict[str, Any]],
    species_order: Sequence[dict[str, Any]],
    *,
    thresholds: Sequence[float] = SUPP_FIG7_BA_THRESHOLDS,
) -> list[dict[str, Any]]:
    base_edge_rows = build_edge_presence_rows(species_edge_rows, species_order)
    max_species_count = len(species_order)
    output: list[dict[str, Any]] = []

    for threshold in thresholds:
        threshold_value = float(threshold)
        threshold_label = format_ba_threshold_label(threshold_value)
        if threshold_value <= 0:
            filtered_edge_rows = base_edge_rows
            overview_two_plus_count = sum(1 for row in base_edge_rows if int(row.get("conservation_count") or 0) >= 2)
        else:
            filtered_species_rows = [
                dict(row)
                for row in species_edge_rows
                if float(row.get("max_ba") or row.get("binding_affinity") or 0.0) >= threshold_value
            ]
            filtered_edge_rows = build_edge_presence_rows(filtered_species_rows, species_order)
            overview_two_plus_count = sum(
                1
                for row in base_edge_rows
                if int(row.get("conservation_count") or 0) >= 2
                and float(row.get("max_ba") or 0.0) >= threshold_value
            )

        exact_counts = {count: 0 for count in range(2, max_species_count + 1)}
        for row in filtered_edge_rows:
            conservation_count = int(row.get("conservation_count") or 0)
            if conservation_count in exact_counts:
                exact_counts[conservation_count] += 1

        for conservation_count in range(2, max_species_count + 1):
            is_overview_row = threshold_value > 0 and conservation_count == 2
            output.append(
                {
                    "threshold": threshold_value,
                    "threshold_label": threshold_label,
                    "conservation_count": conservation_count,
                    "edge_count": overview_two_plus_count if is_overview_row else exact_counts[conservation_count],
                    "count_mode": "overview_two_plus" if is_overview_row else "exact_after_species_threshold",
                }
            )
    return output


def permute_species_edge_rows(
    species_edge_rows: Sequence[dict[str, Any]],
    *,
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in species_edge_rows:
        grouped[int(row["species_id"])].append(dict(row))

    output: list[dict[str, Any]] = []
    for species_id in sorted(grouped):
        rows = [dict(row) for row in grouped[species_id]]
        if len(rows) <= 1:
            output.extend(rows)
            continue

        target_assignments = [
            (int(row["target_core_id"]), str(row.get("target_symbol") or ""))
            for row in rows
        ]
        permutation = rng.permutation(len(rows))
        assigned_targets = [target_assignments[index] for index in permutation]

        for row, (target_core_id, target_symbol) in zip(rows, assigned_targets):
            updated = dict(row)
            updated["target_core_id"] = target_core_id
            updated["target_symbol"] = target_symbol
            output.append(updated)

    return output


def degree_tier(count: int) -> str:
    if count <= 1:
        return "1"
    if count <= 4:
        return "2-4"
    if count <= 9:
        return "5-9"
    return "10+"


def permute_species_edge_rows_degree_bin_matched(
    species_edge_rows: Sequence[dict[str, Any]],
    *,
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in species_edge_rows:
        grouped[int(row["species_id"])].append(dict(row))

    output: list[dict[str, Any]] = []
    for species_id in sorted(grouped):
        rows = [dict(row) for row in grouped[species_id]]
        if len(rows) <= 1:
            output.extend(rows)
            continue

        lncrna_degrees: dict[int, int] = defaultdict(int)
        target_degrees: dict[int, int] = defaultdict(int)
        for row in rows:
            lncrna_degrees[int(row["lncrna_core_id"])] += 1
            target_degrees[int(row["target_core_id"])] += 1

        bin_to_indices: dict[tuple[str, str], list[int]] = defaultdict(list)
        for index, row in enumerate(rows):
            key = (
                degree_tier(lncrna_degrees[int(row["lncrna_core_id"])]),
                degree_tier(target_degrees[int(row["target_core_id"])]),
            )
            bin_to_indices[key].append(index)

        assigned_targets_by_index: dict[int, tuple[int, str]] = {}
        for indices in bin_to_indices.values():
            target_assignments = [
                (int(rows[index]["target_core_id"]), str(rows[index].get("target_symbol") or ""))
                for index in indices
            ]
            if len(indices) > 1:
                permutation = rng.permutation(len(indices))
                target_assignments = [target_assignments[index] for index in permutation]
            for row_index, assignment in zip(indices, target_assignments):
                assigned_targets_by_index[row_index] = assignment

        for index, row in enumerate(rows):
            target_core_id, target_symbol = assigned_targets_by_index[index]
            updated = dict(row)
            updated["target_core_id"] = target_core_id
            updated["target_symbol"] = target_symbol
            output.append(updated)

    return output


def _build_edge_count_lookup(edge_rows: Sequence[dict[str, Any]], species_order: Sequence[dict[str, Any]]) -> dict[int, int]:
    lookup = {count: 0 for count in range(2, len(species_order) + 1)}
    for row in edge_rows:
        conservation_count = int(row.get("conservation_count") or 0)
        if conservation_count in lookup:
            lookup[conservation_count] += 1
    return lookup


def _upper_triangle_pairwise_rows(
    edge_rows: Sequence[dict[str, Any]],
    species_order: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    order_lookup = {str(spec["species_code"]): index for index, spec in enumerate(species_order)}
    return [
        row
        for row in build_pairwise_sharing_rows(edge_rows, species_order, item_type="edge")
        if order_lookup[str(row["species_a"])] < order_lookup[str(row["species_b"])]
    ]


def build_null_conservation_summary_rows(
    species_edge_rows: Sequence[dict[str, Any]],
    species_order: Sequence[dict[str, Any]],
    *,
    iterations: int = SUPP_FIG7_NULL_ITERATIONS,
    rng_seed: int = SUPP_FIG7_RNG_SEED,
    permutation_fn=permute_species_edge_rows,
) -> list[dict[str, Any]]:
    observed_edge_rows = build_edge_presence_rows(species_edge_rows, species_order)
    observed_lookup = _build_edge_count_lookup(observed_edge_rows, species_order)
    null_counts: dict[int, list[int]] = {count: [] for count in observed_lookup}

    rng = np.random.default_rng(rng_seed)
    for _ in range(int(iterations)):
        permuted_rows = permutation_fn(species_edge_rows, rng=rng)
        permuted_edge_rows = build_edge_presence_rows(permuted_rows, species_order)
        permuted_lookup = _build_edge_count_lookup(permuted_edge_rows, species_order)
        for conservation_count in null_counts:
            null_counts[conservation_count].append(permuted_lookup[conservation_count])

    output: list[dict[str, Any]] = []
    for conservation_count in sorted(observed_lookup):
        values = sorted(null_counts[conservation_count])
        output.append(
            {
                "conservation_count": conservation_count,
                "observed_edge_count": observed_lookup[conservation_count],
                "null_mean_edge_count": round(float(statistics.fmean(values)) if values else 0.0, 6),
                "null_median_edge_count": float(statistics.median(values)) if values else 0.0,
                "null_p05_edge_count": float(np.quantile(values, 0.05)) if values else 0.0,
                "null_p95_edge_count": float(np.quantile(values, 0.95)) if values else 0.0,
                "null_iterations": int(iterations),
            }
        )
    return output


def build_degree_bin_matched_null_conservation_summary_rows(
    species_edge_rows: Sequence[dict[str, Any]],
    species_order: Sequence[dict[str, Any]],
    *,
    iterations: int = SUPP_FIG7_NULL_ITERATIONS,
    rng_seed: int = SUPP_FIG7_RNG_SEED,
) -> list[dict[str, Any]]:
    observed_edge_rows = build_edge_presence_rows(species_edge_rows, species_order)
    observed_lookup = _build_edge_count_lookup(observed_edge_rows, species_order)
    null_counts: dict[int, list[int]] = {count: [] for count in observed_lookup}
    if not species_edge_rows:
        return [
            {
                "null_model": "degree_bin_matched_target_permutation",
                "conservation_count": conservation_count,
                "observed_edge_count": observed_count,
                "null_mean_edge_count": 0.0,
                "null_median_edge_count": 0.0,
                "null_p05_edge_count": 0.0,
                "null_p95_edge_count": 0.0,
                "null_iterations": int(iterations),
                "matching_rule": "species_id;lncrna_degree_tier;target_degree_tier",
            }
            for conservation_count, observed_count in sorted(observed_lookup.items())
        ]

    max_target_core_id = max(int(row["target_core_id"]) for row in species_edge_rows)
    key_multiplier = max_target_core_id + 1
    grouped_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in species_edge_rows:
        grouped_rows[int(row["species_id"])].append(dict(row))

    prepared_species: list[dict[str, Any]] = []
    for species_id in sorted(grouped_rows):
        rows = grouped_rows[species_id]
        lncrna_array = np.asarray([int(row["lncrna_core_id"]) for row in rows], dtype=np.int64)
        target_array = np.asarray([int(row["target_core_id"]) for row in rows], dtype=np.int64)
        unique_lnc, lnc_counts = np.unique(lncrna_array, return_counts=True)
        unique_target, target_counts = np.unique(target_array, return_counts=True)
        lnc_degree_lookup = dict(zip(unique_lnc.tolist(), lnc_counts.tolist(), strict=True))
        target_degree_lookup = dict(zip(unique_target.tolist(), target_counts.tolist(), strict=True))
        bin_to_indices: dict[tuple[str, str], list[int]] = defaultdict(list)
        for index, (lncrna_core_id, target_core_id) in enumerate(zip(lncrna_array.tolist(), target_array.tolist(), strict=True)):
            bin_to_indices[
                (
                    degree_tier(int(lnc_degree_lookup[lncrna_core_id])),
                    degree_tier(int(target_degree_lookup[target_core_id])),
                )
            ].append(index)
        prepared_species.append(
            {
                "lncrna_array": lncrna_array,
                "target_array": target_array,
                "bin_indices": [np.asarray(indices, dtype=np.int64) for indices in bin_to_indices.values()],
            }
        )

    rng = np.random.default_rng(rng_seed)
    for _ in range(int(iterations)):
        species_pair_keys: list[np.ndarray] = []
        for prepared in prepared_species:
            lncrna_array = prepared["lncrna_array"]
            target_array = prepared["target_array"]
            assigned_targets = target_array.copy()
            for indices in prepared["bin_indices"]:
                if len(indices) > 1:
                    assigned_targets[indices] = assigned_targets[indices][rng.permutation(len(indices))]
            species_pair_keys.append(np.unique(lncrna_array * key_multiplier + assigned_targets))

        if species_pair_keys:
            _, species_counts = np.unique(np.concatenate(species_pair_keys), return_counts=True)
        else:
            species_counts = np.asarray([], dtype=np.int64)
        for conservation_count in null_counts:
            null_counts[conservation_count].append(int(np.count_nonzero(species_counts == conservation_count)))

    output: list[dict[str, Any]] = []
    for conservation_count in sorted(observed_lookup):
        values = sorted(null_counts[conservation_count])
        output.append(
            {
                "null_model": "degree_bin_matched_target_permutation",
                "conservation_count": conservation_count,
                "observed_edge_count": observed_lookup[conservation_count],
                "null_mean_edge_count": round(float(statistics.fmean(values)) if values else 0.0, 6),
                "null_median_edge_count": float(statistics.median(values)) if values else 0.0,
                "null_p05_edge_count": float(np.quantile(values, 0.05)) if values else 0.0,
                "null_p95_edge_count": float(np.quantile(values, 0.95)) if values else 0.0,
                "null_iterations": int(iterations),
                "matching_rule": "species_id;lncrna_degree_tier;target_degree_tier",
            }
        )
    return output


def _prepare_species_edge_groups_for_downsampling(
    species_edge_rows: Sequence[dict[str, Any]],
    species_order: Sequence[dict[str, Any]],
    *,
    reference_species_code: str,
) -> tuple[dict[int, list[dict[str, Any]]], dict[int, dict[str, Any]], int, int]:
    species_by_id = {int(spec["species_id"]): spec for spec in species_order}
    reference_species = next(
        (spec for spec in species_order if str(spec["species_code"]) == reference_species_code),
        None,
    )
    if reference_species is None:
        raise ValueError(f"Unknown reference species code: {reference_species_code}")

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in species_edge_rows:
        grouped[int(row["species_id"])].append(dict(row))

    for species_id, rows in grouped.items():
        grouped[species_id] = sorted(
            rows,
            key=lambda row: (
                int(row["lncrna_core_id"]),
                int(row["target_core_id"]),
                str(row.get("lncrna_symbol") or ""),
                str(row.get("target_symbol") or ""),
            ),
        )

    reference_species_id = int(reference_species["species_id"])
    reference_edge_count = len(grouped.get(reference_species_id, []))
    return dict(grouped), species_by_id, reference_species_id, reference_edge_count


def _downsample_prepared_species_edge_groups(
    grouped: dict[int, list[dict[str, Any]]],
    species_by_id: dict[int, dict[str, Any]],
    *,
    reference_species_id: int,
    reference_edge_count: int,
    rng: np.random.Generator | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    output: list[dict[str, Any]] = []
    downsampled_species_codes: list[str] = []

    for species_id in sorted(grouped):
        rows = grouped[species_id]
        if species_id != reference_species_id and len(rows) > reference_edge_count:
            downsampled_species_codes.append(str(species_by_id[species_id]["species_code"]))
            if reference_edge_count == 0:
                rows = []
            elif rng is None:
                rows = rows[:reference_edge_count]
            else:
                selected_indices = sorted(
                    int(index)
                    for index in rng.choice(len(rows), size=reference_edge_count, replace=False)
                )
                rows = [rows[index] for index in selected_indices]
        output.extend(dict(row) for row in rows)

    return output, downsampled_species_codes


def build_marmoset_edge_count_downsampling_sensitivity_rows(
    species_edge_rows: Sequence[dict[str, Any]],
    species_order: Sequence[dict[str, Any]],
    *,
    iterations: int = SUPP_FIG7_NULL_ITERATIONS,
    rng_seed: int = SUPP_FIG7_RNG_SEED,
    reference_species_code: str = "marmoset",
) -> list[dict[str, Any]]:
    grouped, species_by_id, reference_species_id, reference_edge_count = (
        _prepare_species_edge_groups_for_downsampling(
            species_edge_rows,
            species_order,
            reference_species_code=reference_species_code,
        )
    )
    max_species_count = len(species_order)
    conservation_counts = range(2, max_species_count + 1)
    max_target_core_id = max((int(row["target_core_id"]) for row in species_edge_rows), default=0)
    key_multiplier = max_target_core_id + 1

    prepared_species: list[dict[str, Any]] = []
    downsampled_species_codes: list[str] = []
    for species_id in sorted(grouped):
        rows = grouped[species_id]
        lnc_array = np.asarray([int(row["lncrna_core_id"]) for row in rows], dtype=np.int64)
        target_array = np.asarray([int(row["target_core_id"]) for row in rows], dtype=np.int64)
        needs_downsampling = species_id != reference_species_id and len(rows) > reference_edge_count
        if needs_downsampling:
            downsampled_species_codes.append(str(species_by_id[species_id]["species_code"]))
        prepared_species.append(
            {
                "lnc_array": lnc_array,
                "target_array": target_array,
                "all_indices": np.arange(len(rows), dtype=np.int64),
                "needs_downsampling": needs_downsampling,
            }
        )
    observed_counts: dict[int, list[int]] = {count: [] for count in conservation_counts}
    null_counts: dict[int, list[int]] = {count: [] for count in conservation_counts}

    rng = np.random.default_rng(rng_seed)
    for _ in range(int(iterations)):
        observed_pair_keys: list[np.ndarray] = []
        null_pair_keys: list[np.ndarray] = []
        for prepared in prepared_species:
            lnc_array = prepared["lnc_array"]
            target_array = prepared["target_array"]
            all_indices = prepared["all_indices"]
            if prepared["needs_downsampling"]:
                if reference_edge_count == 0:
                    indices = np.asarray([], dtype=np.int64)
                else:
                    indices = rng.choice(len(all_indices), size=reference_edge_count, replace=False)
            else:
                indices = all_indices
            if len(indices) == 0:
                continue
            selected_lnc = lnc_array[indices]
            selected_targets = target_array[indices]
            observed_pair_keys.append(np.unique(selected_lnc * key_multiplier + selected_targets))
            assigned_targets = selected_targets.copy()
            if len(indices) > 1:
                assigned_targets = assigned_targets[rng.permutation(len(indices))]
            null_pair_keys.append(np.unique(selected_lnc * key_multiplier + assigned_targets))

        if observed_pair_keys:
            _, observed_species_counts = np.unique(np.concatenate(observed_pair_keys), return_counts=True)
        else:
            observed_species_counts = np.asarray([], dtype=np.int64)
        if null_pair_keys:
            _, null_species_counts = np.unique(np.concatenate(null_pair_keys), return_counts=True)
        else:
            null_species_counts = np.asarray([], dtype=np.int64)
        for conservation_count in null_counts:
            observed_counts[conservation_count].append(
                int(np.count_nonzero(observed_species_counts == conservation_count))
            )
            null_counts[conservation_count].append(int(np.count_nonzero(null_species_counts == conservation_count)))

    sampling_prefix = ";".join(downsampled_species_codes) or "no non-reference species"
    sampling_rule = (
        f"{sampling_prefix} downsampled to {reference_species_code} edge count; "
        f"{reference_species_code} retained at observed edge count; "
        "observed and null samples use seeded random subsampling without replacement"
    )
    output: list[dict[str, Any]] = []
    for conservation_count in sorted(observed_counts):
        observed_values = sorted(observed_counts[conservation_count])
        values = sorted(null_counts[conservation_count])
        output.append(
            {
                "null_model": "marmoset_edge_count_downsampling_target_permutation",
                "reference_species": reference_species_code,
                "reference_edge_count": reference_edge_count,
                "downsampled_edge_count_per_species": reference_edge_count,
                "conservation_count": conservation_count,
                "observed_mean_edge_count": round(float(statistics.fmean(observed_values)) if observed_values else 0.0, 6),
                "observed_median_edge_count": float(statistics.median(observed_values)) if observed_values else 0.0,
                "observed_p05_edge_count": float(np.quantile(observed_values, 0.05)) if observed_values else 0.0,
                "observed_p95_edge_count": float(np.quantile(observed_values, 0.95)) if observed_values else 0.0,
                "null_mean_edge_count": round(float(statistics.fmean(values)) if values else 0.0, 6),
                "null_median_edge_count": float(statistics.median(values)) if values else 0.0,
                "null_p05_edge_count": float(np.quantile(values, 0.05)) if values else 0.0,
                "null_p95_edge_count": float(np.quantile(values, 0.95)) if values else 0.0,
                "null_iterations": int(iterations),
                "sampling_rule": sampling_rule,
            }
        )
    return output


def build_null_pairwise_summary_rows(
    species_edge_rows: Sequence[dict[str, Any]],
    species_order: Sequence[dict[str, Any]],
    *,
    iterations: int = SUPP_FIG7_NULL_ITERATIONS,
    rng_seed: int = SUPP_FIG7_RNG_SEED,
) -> list[dict[str, Any]]:
    display_lookup = {str(spec["species_code"]): str(spec["display_name"]) for spec in species_order}
    observed_rows = _upper_triangle_pairwise_rows(
        build_edge_presence_rows(species_edge_rows, species_order),
        species_order,
    )
    observed_lookup = {
        (str(row["species_a"]), str(row["species_b"])): float(row.get("jaccard") or 0.0)
        for row in observed_rows
    }
    null_values: dict[tuple[str, str], list[float]] = {key: [] for key in observed_lookup}

    rng = np.random.default_rng(rng_seed)
    for _ in range(int(iterations)):
        permuted_rows = permute_species_edge_rows(species_edge_rows, rng=rng)
        pairwise_rows = _upper_triangle_pairwise_rows(
            build_edge_presence_rows(permuted_rows, species_order),
            species_order,
        )
        pairwise_lookup = {
            (str(row["species_a"]), str(row["species_b"])): float(row.get("jaccard") or 0.0)
            for row in pairwise_rows
        }
        for key in null_values:
            null_values[key].append(pairwise_lookup.get(key, 0.0))

    output: list[dict[str, Any]] = []
    for species_a, species_b in sorted(null_values):
        values = sorted(null_values[(species_a, species_b)])
        output.append(
            {
                "species_a": species_a,
                "species_b": species_b,
                "pair_label": f"{display_lookup[species_a]} vs {display_lookup[species_b]}",
                "observed_jaccard": round(observed_lookup[(species_a, species_b)], 6),
                "null_mean_jaccard": round(float(statistics.fmean(values)) if values else 0.0, 6),
                "null_median_jaccard": float(statistics.median(values)) if values else 0.0,
                "null_p05_jaccard": float(np.quantile(values, 0.05)) if values else 0.0,
                "null_p95_jaccard": float(np.quantile(values, 0.95)) if values else 0.0,
                "null_iterations": int(iterations),
            }
        )
    return output


def render_suppfig7_robustness(
    threshold_rows: Sequence[dict[str, Any]],
    null_count_rows: Sequence[dict[str, Any]],
    null_pairwise_rows: Sequence[dict[str, Any]],
    svg_path: Path,
    png_path: Path,
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(16.5, 4.5))

    threshold_order = []
    for row in threshold_rows:
        label = str(row["threshold_label"])
        if label not in threshold_order:
            threshold_order.append(label)
    count_colors = {2: "#1f77b4", 3: "#ff7f0e", 4: "#2ca02c"}
    for conservation_count in sorted({int(row["conservation_count"]) for row in threshold_rows}):
        y_values = []
        for threshold_label in threshold_order:
            matched = next(
                row
                for row in threshold_rows
                if str(row["threshold_label"]) == threshold_label
                and int(row["conservation_count"]) == conservation_count
            )
            y_values.append(float(matched["edge_count"]))
        axes[0].plot(
            threshold_order,
            y_values,
            marker="o",
            linewidth=2,
            color=count_colors.get(conservation_count, "#555555"),
            label=f"{conservation_count}-species",
        )
    axes[0].set_title("A. BA sensitivity")
    axes[0].set_ylabel("Edge count")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].legend(frameon=False, fontsize=8)

    conservation_labels = [str(row["conservation_count"]) for row in null_count_rows]
    null_means = [float(row["null_mean_edge_count"]) for row in null_count_rows]
    observed_counts = [float(row["observed_edge_count"]) for row in null_count_rows]
    lower_errors = [float(row["null_mean_edge_count"]) - float(row["null_p05_edge_count"]) for row in null_count_rows]
    upper_errors = [float(row["null_p95_edge_count"]) - float(row["null_mean_edge_count"]) for row in null_count_rows]
    x_positions = np.arange(len(null_count_rows))
    axes[1].bar(x_positions, null_means, color="#d9d9d9", edgecolor="#666666", label="Null mean")
    axes[1].errorbar(
        x_positions,
        null_means,
        yerr=[lower_errors, upper_errors],
        fmt="none",
        ecolor="#666666",
        elinewidth=1.5,
        capsize=4,
    )
    axes[1].scatter(x_positions, observed_counts, color="#d62728", s=45, zorder=3, label="Observed")
    axes[1].set_xticks(x_positions)
    axes[1].set_xticklabels(conservation_labels)
    axes[1].set_title("B. Null comparison: shared-edge counts")
    axes[1].set_xlabel("Shared-species count")
    axes[1].set_ylabel("Edge count")
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].legend(frameon=False, fontsize=8)

    pair_labels = [str(row["pair_label"]) for row in null_pairwise_rows]
    pair_null_means = [float(row["null_mean_jaccard"]) for row in null_pairwise_rows]
    pair_observed = [float(row["observed_jaccard"]) for row in null_pairwise_rows]
    pair_lower = [float(row["null_mean_jaccard"]) - float(row["null_p05_jaccard"]) for row in null_pairwise_rows]
    pair_upper = [float(row["null_p95_jaccard"]) - float(row["null_mean_jaccard"]) for row in null_pairwise_rows]
    pair_positions = np.arange(len(null_pairwise_rows))
    axes[2].bar(pair_positions, pair_null_means, color="#cfe8f3", edgecolor="#4c78a8", label="Null mean")
    axes[2].errorbar(
        pair_positions,
        pair_null_means,
        yerr=[pair_lower, pair_upper],
        fmt="none",
        ecolor="#4c78a8",
        elinewidth=1.5,
        capsize=4,
    )
    axes[2].scatter(pair_positions, pair_observed, color="#1f77b4", s=45, zorder=3, label="Observed")
    axes[2].set_xticks(pair_positions)
    axes[2].set_xticklabels(pair_labels, rotation=35, ha="right")
    axes[2].set_title("C. Null comparison: pairwise edge Jaccard")
    axes[2].set_ylabel("Jaccard")
    axes[2].grid(axis="y", alpha=0.25)
    axes[2].legend(frameon=False, fontsize=8)

    fig.suptitle("Supplementary Figure 7. Robustness of edge-level conservation and rewiring summaries", fontsize=13)
    fig.tight_layout()
    save_figure(fig, svg_path, png_path)


def build_fig1a_catalog_gap_rows() -> list[dict[str, str]]:
    gap_message = "Trait-associated catalogs nominate relevant nodes, not edges."
    return [
        {
            "catalog_type": "lncrna_catalog",
            "display_label": "Trait-associated lncRNAs",
            "support_label": "Candidate lncRNA nodes from prior catalogs",
            "gap_message": gap_message,
        },
        {
            "catalog_type": "protein_coding_catalog",
            "display_label": "Trait-associated protein-coding genes",
            "support_label": "Candidate target-gene nodes from prior catalogs",
            "gap_message": gap_message,
        },
    ]


def build_fig1b_species_summary_rows(
    node_rows: Iterable[dict[str, Any]],
    species_order: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped_by_core: dict[int, dict[str, Any]] = {}
    for row in node_rows:
        core_id = int(row["core_id"])
        entry = grouped_by_core.setdefault(
            core_id,
            {
                "gene_type": str(row.get("gene_type") or ""),
                "species_ids": set(),
            },
        )
        entry["species_ids"].add(int(row["species_id"]))

    output: list[dict[str, Any]] = []
    for spec in species_order:
        species_id = int(spec["species_id"])
        lnc_count = 0
        protein_count = 0
        comparable_count = 0
        for entry in grouped_by_core.values():
            species_ids = entry["species_ids"]
            if species_id not in species_ids:
                continue
            if entry["gene_type"] == "lncRNA":
                lnc_count += 1
            elif entry["gene_type"] == "protein_coding":
                protein_count += 1
            if len(species_ids) >= 2:
                comparable_count += 1
        output.append(
            {
                "species_id": species_id,
                "species_code": str(spec["species_code"]),
                "species_name": str(spec["display_name"]),
                "lncrna_core_count": lnc_count,
                "protein_coding_core_count": protein_count,
                "comparable_core_group_count": comparable_count,
            }
        )
    return output


def build_fig1c_workflow_rows() -> list[dict[str, str]]:
    return [
        {
            "step_key": "catalogs",
            "display_label": "Catalogs",
            "subtitle": "Trait-associated lncRNAs / PCGs",
        },
        {
            "step_key": "core_ids",
            "display_label": "Core IDs",
            "subtitle": "lncRNA: Infernal\nPCG: ortholog tables",
        },
        {
            "step_key": "triplex_inference",
            "display_label": "Triplex inference",
            "subtitle": "lncRNA-DNA triplex sites",
        },
        {
            "step_key": "candidate_network",
            "display_label": "Candidate lncRNA–PCG edge network",
            "subtitle": "candidate lncRNA-PCG edges",
        },
    ]


def _count_present_species(row: dict[str, Any], species_order: Sequence[dict[str, Any]] = DEFAULT_SPECIES_ORDER) -> int:
    total = 0
    for spec in species_order:
        total += int(row.get(str(spec["species_code"])) or 0)
    if total:
        return total
    return int(row.get("conservation_count") or row.get("species_count") or 0)


def _format_target_display_label(symbol: str, fallback_core_id: int) -> str:
    primary = (symbol or "").strip()
    if primary:
        if re.match(r"^(CATG|ENSG)[0-9]+\.[0-9]+$", primary):
            return _short_accession_label(primary)
        return primary
    return f"Target {fallback_core_id}"


def _format_lncrna_display_label(symbol: str, fallback_id: str, core_id: int) -> str:
    label = format_lncRNA_display_label(symbol, fallback_id)
    return label or f"lncRNA {core_id}"


def _edge_sort_key(row: dict[str, Any]) -> tuple[float, int, int, int]:
    return (
        -float(row.get("max_ba") or row.get("mean_ba") or 0.0),
        -int(row.get("supporting_regulation_count") or 0),
        int(row["lncrna_core_id"]),
        int(row["target_core_id"]),
    )


def _deduplicate_edges(edge_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[int, int]] = set()
    output: list[dict[str, Any]] = []
    for row in sorted(edge_rows, key=_edge_sort_key):
        key = (int(row["lncrna_core_id"]), int(row["target_core_id"]))
        if key in seen:
            continue
        seen.add(key)
        output.append(dict(row))
    return output


def _limit_edges_preserving_targets(edge_rows: Sequence[dict[str, Any]], max_edges: int) -> list[dict[str, Any]]:
    ranked_rows = _deduplicate_edges(edge_rows)
    if len(ranked_rows) <= max_edges:
        return ranked_rows

    selected_keys: set[tuple[int, int]] = set()
    selected_rows: list[dict[str, Any]] = []
    seen_targets: set[int] = set()
    seen_lncrnas: set[int] = set()

    def add_row(row: dict[str, Any]) -> None:
        key = (int(row["lncrna_core_id"]), int(row["target_core_id"]))
        if key in selected_keys or len(selected_rows) >= max_edges:
            return
        selected_keys.add(key)
        selected_rows.append(dict(row))
        seen_targets.add(int(row["target_core_id"]))
        seen_lncrnas.add(int(row["lncrna_core_id"]))

    for row in ranked_rows:
        if int(row["target_core_id"]) not in seen_targets:
            add_row(row)
    for row in ranked_rows:
        if int(row["lncrna_core_id"]) not in seen_lncrnas:
            add_row(row)
    for row in ranked_rows:
        add_row(row)

    return sorted(selected_rows, key=_edge_sort_key)


def _build_module_node_rows(edge_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    for row in edge_rows:
        lnc_core_id = int(row["lncrna_core_id"])
        target_core_id = int(row["target_core_id"])
        species_count = _count_present_species(row)
        lnc_key = ("lncrna", lnc_core_id)
        target_key = ("target", target_core_id)
        nodes.setdefault(
            lnc_key,
            {
                "node_role": "lncrna",
                "core_id": lnc_core_id,
                "display_label": _format_lncrna_display_label(
                    str(row.get("lncrna_symbol") or ""),
                    str(row.get("lncrna_human_ensembl_id") or ""),
                    lnc_core_id,
                ),
                "species_count": species_count,
                "conservation_count": int(row.get("species_count") or row.get("conservation_count") or species_count),
            },
        )
        nodes.setdefault(
            target_key,
            {
                "node_role": "target",
                "core_id": target_core_id,
                "display_label": _format_target_display_label(str(row.get("target_symbol") or ""), target_core_id),
                "species_count": species_count,
                "conservation_count": int(row.get("conservation_count") or species_count),
            },
        )
    return sorted(
        nodes.values(),
        key=lambda row: (0 if row["node_role"] == "lncrna" else 1, int(row["core_id"])),
    )


def _manifest_mean_ba(edge_rows: Sequence[dict[str, Any]]) -> float:
    return round(statistics.fmean(float(row.get("mean_ba") or 0.0) for row in edge_rows), 6) if edge_rows else 0.0


def select_fig2d_hub_module(
    edge_rows: Sequence[dict[str, Any]],
    *,
    max_targets: int = 8,
    min_unique_targets: int = 6,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    hub_rows = build_hub_rows(edge_rows)
    if not hub_rows:
        raise ValueError("No high-affinity edges available for Figure 2D hub module.")

    hub_row = next(
        (row for row in hub_rows if int(row["unique_target_core_count"]) >= min_unique_targets),
        hub_rows[0],
    )
    selected_edges = sorted(
        (
            dict(row)
            for row in edge_rows
            if int(row["lncrna_core_id"]) == int(hub_row["lncrna_core_id"])
        ),
        key=_edge_sort_key,
    )[:max_targets]
    node_rows = _build_module_node_rows(selected_edges)
    manifest_row = {
        "module_kind": "hub",
        "lncrna_core_id": int(hub_row["lncrna_core_id"]),
        "node_count": len(node_rows),
        "edge_count": len(selected_edges),
        "target_count": sum(1 for row in node_rows if row["node_role"] == "target"),
        "mean_edge_ba": _manifest_mean_ba(selected_edges),
    }
    return manifest_row, node_rows, selected_edges


def _community_lncRNA_ids(edge_rows: Sequence[dict[str, Any]]) -> list[int]:
    return sorted({int(row["lncrna_core_id"]) for row in edge_rows})


def _community_target_ids(edge_rows: Sequence[dict[str, Any]]) -> list[int]:
    return sorted({int(row["target_core_id"]) for row in edge_rows})


def select_fig2d_community_module(
    edge_rows: Sequence[dict[str, Any]],
    *,
    min_nodes: int = 10,
    max_nodes: int = 18,
    min_lncrnas: int = 2,
    max_lncrnas: int = 4,
    min_targets: int = 6,
    max_targets: int = 12,
    max_edges: int = 14,
    max_candidate_lncrnas: int = 24,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_lncrna_ids = [
        int(row["lncrna_core_id"])
        for row in build_hub_rows(edge_rows)[:max_candidate_lncrnas]
    ]
    edge_lookup = {
        (int(row["lncrna_core_id"]), int(row["target_core_id"])): dict(row)
        for row in _deduplicate_edges(edge_rows)
        if int(row["lncrna_core_id"]) in candidate_lncrna_ids
    }
    target_sets: dict[int, set[int]] = defaultdict(set)
    for lnc_core_id, target_core_id in edge_lookup:
        target_sets[int(lnc_core_id)].add(int(target_core_id))

    best_candidate: tuple[tuple[float, int, int], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]] | None = None
    for lnc_a, lnc_b in combinations(candidate_lncrna_ids, 2):
        shared_targets = target_sets.get(int(lnc_a), set()) & target_sets.get(int(lnc_b), set())
        if len(shared_targets) < min_targets:
            continue

        ranked_targets = sorted(
            shared_targets,
            key=lambda target_core_id: (
                -statistics.fmean(
                    [
                        float(edge_lookup[(lnc_id, target_core_id)].get("mean_ba") or 0.0)
                        for lnc_id in (lnc_a, lnc_b)
                    ]
                ),
                -sum(
                    int(edge_lookup[(lnc_id, target_core_id)].get("supporting_regulation_count") or 0)
                    for lnc_id in (lnc_a, lnc_b)
                ),
                int(target_core_id),
            ),
        )[:max_targets]
        candidate_edges = [
            edge_lookup[(lnc_id, target_core_id)]
            for target_core_id in ranked_targets
            for lnc_id in (lnc_a, lnc_b)
            if (lnc_id, target_core_id) in edge_lookup
        ]
        limited_edges = _limit_edges_preserving_targets(candidate_edges, max_edges=max_edges)
        node_rows = _build_module_node_rows(limited_edges)
        target_count = sum(1 for row in node_rows if row["node_role"] == "target")
        lnc_count = sum(1 for row in node_rows if row["node_role"] == "lncrna")
        if not (min_nodes <= len(node_rows) <= max_nodes):
            continue
        if not (min_lncrnas <= lnc_count <= max_lncrnas):
            continue
        if not (min_targets <= target_count <= max_targets):
            continue

        lead_lncrna = sorted(
            (int(lnc_a), int(lnc_b)),
            key=lambda core_id: (
                -sum(1 for row in limited_edges if int(row["lncrna_core_id"]) == core_id),
                -statistics.fmean(
                    float(row.get("mean_ba") or 0.0)
                    for row in limited_edges
                    if int(row["lncrna_core_id"]) == core_id
                ),
                core_id,
            ),
        )[0]
        manifest_row = {
            "module_kind": "community",
            "lncrna_core_id": int(lead_lncrna),
            "node_count": len(node_rows),
            "edge_count": len(limited_edges),
            "target_count": target_count,
            "mean_edge_ba": _manifest_mean_ba(limited_edges),
        }
        score = (
            float(manifest_row["mean_edge_ba"]),
            len(ranked_targets),
            -int(manifest_row["lncrna_core_id"]),
        )
        if best_candidate is None or score > best_candidate[0]:
            best_candidate = (score, manifest_row, node_rows, limited_edges)

    if best_candidate is None:
        raise ValueError("No qualifying community module found for Figure 2D.")

    return best_candidate[1], best_candidate[2], best_candidate[3]


def _node_lookup(node_rows: Sequence[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(row["core_id"]): dict(row) for row in node_rows}


def _group_edge_rows_by_lncrna(edge_rows: Sequence[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in edge_rows:
        grouped[int(row["lncrna_core_id"])].append(dict(row))
    return grouped


def _build_exemplar_node_rows(
    lnc_row: dict[str, Any] | None,
    edge_rows: Sequence[dict[str, Any]],
    node_rows: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    lookup = _node_lookup(node_rows)
    output: list[dict[str, Any]] = []
    if lnc_row:
        lnc_core_id = int(lnc_row["core_id"])
        output.append(
            {
                "node_role": "lncrna",
                "core_id": lnc_core_id,
                "display_label": _format_lncrna_display_label(
                    str(lnc_row.get("canonical_symbol") or ""),
                    str(lnc_row.get("human_ensembl_id") or ""),
                    lnc_core_id,
                ),
                "species_count": int(lnc_row.get("conservation_count") or 0),
                "conservation_count": int(lnc_row.get("conservation_count") or 0),
            }
        )
    seen_targets: set[int] = set()
    for row in edge_rows:
        target_core_id = int(row["target_core_id"])
        if target_core_id in seen_targets:
            continue
        seen_targets.add(target_core_id)
        target_lookup = lookup.get(target_core_id, {})
        output.append(
            {
                "node_role": "target",
                "core_id": target_core_id,
                "display_label": _format_target_display_label(
                    str(target_lookup.get("canonical_symbol") or row.get("target_symbol") or ""),
                    target_core_id,
                ),
                "species_count": _count_present_species(row),
                "conservation_count": int(row.get("conservation_count") or _count_present_species(row)),
            }
        )
    return output


def select_fig3d_conserved_exemplar(
    node_rows: Sequence[dict[str, Any]],
    edge_rows: Sequence[dict[str, Any]],
    *,
    max_targets: int = 6,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    grouped_edge_rows = _group_edge_rows_by_lncrna(edge_rows)
    lnc_candidates = [
        row for row in node_rows
        if str(row.get("gene_type") or "") == "lncRNA" and int(row.get("conservation_count") or 0) == 4
    ]
    scored_candidates: list[tuple[tuple[int, float, int], dict[str, Any], list[dict[str, Any]]]] = []
    for lnc_row in lnc_candidates:
        candidate_edges = [
            row for row in grouped_edge_rows.get(int(lnc_row["core_id"]), [])
            if int(row.get("conservation_count") or 0) >= 3
        ]
        if len(candidate_edges) < 3:
            continue
        score = (
            len(candidate_edges),
            statistics.fmean(float(row.get("mean_ba") or 0.0) for row in candidate_edges),
            -int(lnc_row["core_id"]),
        )
        scored_candidates.append((score, dict(lnc_row), candidate_edges))

    if not scored_candidates:
        raise ValueError("No conserved exemplar satisfies Figure 3D selection rules.")

    _, selected_lnc_row, selected_edges = max(scored_candidates, key=lambda item: item[0])
    ranked_edges = sorted(
        selected_edges,
        key=lambda row: (
            -int(row.get("conservation_count") or 0),
            -float(row.get("mean_ba") or 0.0),
            int(row["target_core_id"]),
        ),
    )[:max_targets]
    node_manifest_rows = _build_exemplar_node_rows(selected_lnc_row, ranked_edges, node_rows)
    manifest_row = {
        "exemplar_kind": "conserved",
        "lncrna_core_id": int(selected_lnc_row["core_id"]),
        "node_count": len(node_manifest_rows),
        "edge_count": len(ranked_edges),
        "target_count": sum(1 for row in node_manifest_rows if row["node_role"] == "target"),
        "mean_edge_ba": _manifest_mean_ba(ranked_edges),
    }
    return manifest_row, node_manifest_rows, ranked_edges


def _species_target_sets(
    edge_rows: Sequence[dict[str, Any]],
    species_order: Sequence[dict[str, Any]],
) -> dict[str, set[int]]:
    output: dict[str, set[int]] = {str(spec["species_code"]): set() for spec in species_order}
    for row in edge_rows:
        target_core_id = int(row["target_core_id"])
        for spec in species_order:
            code = str(spec["species_code"])
            if int(row.get(code) or 0):
                output[code].add(target_core_id)
    return output


def select_fig3d_rewired_exemplar(
    node_rows: Sequence[dict[str, Any]],
    edge_rows: Sequence[dict[str, Any]],
    *,
    max_targets: int = 6,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    grouped_edge_rows = _group_edge_rows_by_lncrna(edge_rows)
    lnc_candidates = [
        row for row in node_rows
        if str(row.get("gene_type") or "") == "lncRNA" and int(row.get("conservation_count") or 0) >= 3
    ]
    scored_candidates: list[tuple[tuple[float, int, int], dict[str, Any], list[dict[str, Any]], float]] = []
    for lnc_row in lnc_candidates:
        candidate_edges = grouped_edge_rows.get(int(lnc_row["core_id"]), [])
        if not candidate_edges:
            continue
        species_targets = _species_target_sets(candidate_edges, DEFAULT_SPECIES_ORDER)
        active_species = {code: targets for code, targets in species_targets.items() if targets}
        if len(active_species) < 3:
            continue
        if any(len(targets) < 2 for targets in active_species.values()):
            continue
        jaccards: list[float] = []
        for (_, targets_a), (_, targets_b) in combinations(active_species.items(), 2):
            union = targets_a | targets_b
            if not union:
                continue
            jaccards.append(len(targets_a & targets_b) / float(len(union)))
        if not jaccards:
            continue
        mean_pairwise_jaccard = statistics.fmean(jaccards)
        score = (
            -mean_pairwise_jaccard,
            sum(int(row.get("supporting_regulation_count") or 0) for row in candidate_edges),
            -int(lnc_row["core_id"]),
        )
        scored_candidates.append((score, dict(lnc_row), candidate_edges, mean_pairwise_jaccard))

    if not scored_candidates:
        raise ValueError("No rewired exemplar satisfies Figure 3D selection rules.")

    _, selected_lnc_row, selected_edges, mean_pairwise_jaccard = max(scored_candidates, key=lambda item: item[0])
    ranked_edges = sorted(
        selected_edges,
        key=lambda row: (
            _count_present_species(row),
            -float(row.get("max_ba") or row.get("mean_ba") or 0.0),
            int(row["target_core_id"]),
        ),
    )[:max_targets]
    node_manifest_rows = _build_exemplar_node_rows(selected_lnc_row, ranked_edges, node_rows)
    manifest_row = {
        "exemplar_kind": "rewired",
        "lncrna_core_id": int(selected_lnc_row["core_id"]),
        "node_count": len(node_manifest_rows),
        "edge_count": len(ranked_edges),
        "target_count": sum(1 for row in node_manifest_rows if row["node_role"] == "target"),
        "mean_edge_ba": _manifest_mean_ba(ranked_edges),
        "mean_pairwise_jaccard": round(float(mean_pairwise_jaccard), 6),
    }
    return manifest_row, node_manifest_rows, ranked_edges


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


def select_fig2c_label_rows(centrality_rows: Sequence[dict[str, Any]], *, max_labels: int = 5) -> list[dict[str, Any]]:
    return [dict(row) for row in list(centrality_rows)[:max_labels]]


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


def query_dict_rows(
    conn: psycopg2.extensions.connection,
    sql: str,
    params: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


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
    source_commit: str,
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
            "display_label": "Candidate lncRNA–PCG edges",
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

    fig, ax = plt.subplots(figsize=(13, 2.0))
    fig.patch.set_facecolor("white")
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    colors = ["#0B3954", "#C81D25", "#087E8B", "#FF8C42"]
    xs = np.linspace(0.12, 0.88, len(rows))
    ax.add_patch(plt.Rectangle((0.02, 0.18), 0.96, 0.62, facecolor="#F7F5F2", edgecolor="#D7D2CB", linewidth=1.2))
    for index, (x_pos, row, color) in enumerate(zip(xs, rows, colors, strict=True)):
        if index:
            divider_x = (xs[index - 1] + x_pos) / 2.0
            ax.plot([divider_x, divider_x], [0.24, 0.74], color="#D7D2CB", linewidth=1.1)
        ax.text(x_pos, 0.62, row["display_label"], ha="center", va="center", fontsize=10, color="#404040")
        ax.text(x_pos, 0.38, f"{int(row['value']):,}", ha="center", va="center", fontsize=18, fontweight="bold", color=color)
    fig.text(
        0.5,
        0.05,
        "Paper-facing freeze; main-text baseline = 8 core histone marks + DNase-HS",
        ha="center",
        va="center",
        fontsize=8.5,
        color="#6A6A6A",
    )
    fig.tight_layout(rect=[0, 0.1, 1, 0.98])
    save_figure(fig, svg_path, png_path)

    write_json(
        meta_path,
        panel_metadata(
            panel_id="Figure1D",
            title="Frozen submission snapshot",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[
                repo_root / "docs/paper/figures.md",
                repo_root / "docs/paper/submission_snapshot.md",
                repo_root / "docs/paper/manuscript.md",
            ],
            output_paths=[tsv_path, svg_path, png_path],
            filters={"frozen_snapshot_only": True},
        ),
    )


def generate_fig1a(
    *,
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    source_commit: str,
) -> None:
    tsv_path = fig_dir / "fig1A_catalog_gap.tsv"
    svg_path = fig_dir / "fig1A_catalog_gap.svg"
    png_path = fig_dir / "fig1A_catalog_gap.png"
    meta_path = fig_dir / "fig1A_metadata.json"

    rows = build_fig1a_catalog_gap_rows()
    write_tsv(tsv_path, rows, ["catalog_type", "display_label", "support_label", "gap_message"])

    fig, ax = plt.subplots(figsize=(10.5, 4.5))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    positions = [(0.18, 0.58), (0.82, 0.58)]
    colors = ["#C81D25", "#087E8B"]
    for (x_pos, y_pos), color, row in zip(positions, colors, rows, strict=True):
        ax.text(
            x_pos,
            y_pos,
            row["display_label"],
            ha="center",
            va="center",
            fontsize=13,
            color="white",
            bbox={"boxstyle": "round,pad=0.6", "facecolor": color, "edgecolor": color},
        )
        ax.text(
            x_pos,
            y_pos - 0.18,
            row["support_label"],
            ha="center",
            va="center",
            fontsize=9.5,
            color="#404040",
        )
        ax.annotate(
            "",
            xy=(0.43 if x_pos < 0.5 else 0.57, 0.58),
            xytext=(x_pos + (0.12 if x_pos < 0.5 else -0.12), 0.58),
            arrowprops={"arrowstyle": "->", "color": "#8A8A8A", "linewidth": 1.5},
        )

    ax.text(
        0.5,
        0.58,
        "Nodes, not candidate edges",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
        color="#C81D25",
        bbox={"boxstyle": "round,pad=0.55", "facecolor": "#F7F5F2", "edgecolor": "#C81D25", "linestyle": "--"},
    )
    ax.text(
        0.5,
        0.28,
        "Trait-associated catalogs prioritize relevant genes,\n"
        "but they do not specify candidate lncRNA-PCG edges.",
        ha="center",
        va="center",
        fontsize=10,
        color="#5A5A5A",
    )
    fig.tight_layout()
    save_figure(fig, svg_path, png_path)

    write_json(
        meta_path,
        panel_metadata(
            panel_id="Figure1A",
            title="Catalog-gap schematic",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[repo_root / "docs/paper/figures.md", repo_root / "docs/paper/manuscript.md"],
            output_paths=[tsv_path, svg_path, png_path],
            filters={"static_concept_panel": True, "gap_language": "nodes_not_edges"},
        ),
    )


def generate_fig1b(
    *,
    node_input_rows: Sequence[dict[str, Any]],
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    source_commit: str,
) -> None:
    tsv_path = fig_dir / "fig1B_ortholog_counts.tsv"
    svg_path = fig_dir / "fig1B_ortholog_mapping.svg"
    png_path = fig_dir / "fig1B_ortholog_mapping.png"
    meta_path = fig_dir / "fig1B_metadata.json"

    summary_rows = build_fig1b_species_summary_rows(node_input_rows, DEFAULT_SPECIES_ORDER)
    write_tsv(
        tsv_path,
        summary_rows,
        [
            "species_id",
            "species_code",
            "species_name",
            "lncrna_core_count",
            "protein_coding_core_count",
            "comparable_core_group_count",
        ],
    )

    x_positions = np.arange(len(summary_rows))
    lnc_counts = [int(row["lncrna_core_count"]) for row in summary_rows]
    protein_counts = [int(row["protein_coding_core_count"]) for row in summary_rows]
    comparable_counts = [int(row["comparable_core_group_count"]) for row in summary_rows]
    labels = [str(row["species_name"]) for row in summary_rows]

    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    width = 0.32
    ax.bar(x_positions - width / 2, lnc_counts, width=width, color="#087E8B", label="lncRNA core groups")
    ax.bar(x_positions + width / 2, protein_counts, width=width, color="#BFD7EA", label="Protein-coding core groups")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Core groups with non-null core_id")
    ax.grid(axis="y", alpha=0.18)

    ax2 = ax.twinx()
    ax2.plot(x_positions, comparable_counts, color="#C81D25", marker="o", linewidth=2, label="Comparable shared core groups")
    ax2.set_ylabel("Shared core groups present in at least 2 species")

    handles1, labels1 = ax.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(handles1 + handles2, labels1 + labels2, loc="upper right", frameon=True)
    fig.tight_layout()
    save_figure(fig, svg_path, png_path)

    write_json(
        meta_path,
        panel_metadata(
            panel_id="Figure1B",
            title="Ortholog mapping across four primates",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[repo_root / "docs/paper/submission_snapshot.md"],
            output_paths=[tsv_path, svg_path, png_path],
            filters={"species_order": [spec["species_code"] for spec in DEFAULT_SPECIES_ORDER]},
        ),
    )


def generate_fig1c(
    *,
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    source_commit: str,
) -> None:
    tsv_path = fig_dir / "fig1C_workflow.tsv"
    svg_path = fig_dir / "fig1C_workflow.svg"
    png_path = fig_dir / "fig1C_workflow.png"
    meta_path = fig_dir / "fig1C_metadata.json"

    rows = build_fig1c_workflow_rows()
    write_tsv(tsv_path, rows, ["step_key", "display_label", "subtitle"])

    fig, ax = plt.subplots(figsize=(12.5, 4.2))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    xs = np.linspace(0.12, 0.88, len(rows))
    palette = ["#C81D25", "#0B3954", "#FF8C42", "#087E8B"]
    subtitle_colors = ["white", "white", "#1F2933", "white"]
    for index, (x_pos, row, color, subtitle_color) in enumerate(zip(xs, rows, palette, subtitle_colors, strict=True)):
        ax.text(
            x_pos,
            0.64,
            row["display_label"],
            ha="center",
            va="center",
            fontsize=12,
            fontweight="bold",
            color="white" if color != "#FF8C42" else "#102A43",
            bbox={"boxstyle": "round,pad=0.58", "facecolor": color, "edgecolor": color},
        )
        ax.text(
            x_pos,
            0.36,
            row["subtitle"],
            ha="center",
            va="center",
            fontsize=9.5,
            color=subtitle_color,
            linespacing=1.25,
            bbox={"boxstyle": "round,pad=0.34", "facecolor": color, "edgecolor": color, "alpha": 0.92},
        )
        if index < len(rows) - 1:
            ax.annotate(
                "",
                xy=(xs[index + 1] - 0.09, 0.51),
                xytext=(x_pos + 0.09, 0.51),
                arrowprops={"arrowstyle": "->", "color": "#7A7A7A", "linewidth": 1.6},
            )
    fig.tight_layout()
    save_figure(fig, svg_path, png_path)

    write_json(
        meta_path,
        panel_metadata(
            panel_id="Figure1C",
            title="Triplex-informed edge reconstruction workflow",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[
                repo_root / "docs/paper/figures.md",
                repo_root / "docs/paper/submission_snapshot.md",
                repo_root / "docs/paper/manuscript.md",
            ],
            output_paths=[tsv_path, svg_path, png_path],
            filters={"workflow_step_count": len(rows), "candidate_edge_language": True},
        ),
    )


def generate_fig2a(
    *,
    conn: psycopg2.extensions.connection,
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    source_commit: str,
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
    ax.axhline(100.0, color="#C81D25", linestyle="--", linewidth=1.4, label="BA ≥100 prioritization zone")
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
    inset.set_xticklabels([])
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
            source_commit=source_commit,
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
    alias_rows: dict[int, dict[str, str]],
    alias_manifest_path: Path,
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    source_commit: str,
    input_paths: Sequence[Path],
) -> None:
    tsv_path = fig_dir / "fig2B_hubs.tsv"
    svg_path = fig_dir / "fig2B_hubs.svg"
    png_path = fig_dir / "fig2B_hubs.png"
    meta_path = fig_dir / "fig2B_metadata.json"

    top_rows = apply_fig2b_alias_manifest(list(hub_rows[:12]), alias_rows)
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
    ax.text(
        0.01,
        0.02,
        "Unadjusted breadth; not length/GC/repeat/motif normalized",
        transform=ax.transAxes,
        fontsize=8.5,
        color="#555555",
        va="bottom",
        ha="left",
    )
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
            title="Unadjusted target-core breadth prioritization",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[*input_paths, alias_manifest_path],
            output_paths=[tsv_path, svg_path, png_path],
            filters={
                "min_ba": 100,
                "ranking_metric": "unique_target_core_count",
                "top_n": 12,
                "label_strategy": "alias_manifest_then_shortened_id_fallback",
                "color_metric": "species_count",
            },
            notes=[
                "Unadjusted target-core breadth is not normalized for transcript length, GC content, repeat content, or triplex-compatible motif opportunity."
            ],
        ),
    )


def generate_fig2c(
    *,
    centrality_rows: Sequence[dict[str, Any]],
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    source_commit: str,
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

    top_labels = select_fig2c_label_rows(centrality_rows)
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
    ax.set_xlabel("Unique target-core breadth")
    ax.set_ylabel("Eigenvector centrality")
    ax.set_title("Network-central candidate organizers")
    ax.set_xlim(-10, max(x) * 1.1 if x else 1.0)
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
            title="Network-central candidate organizers",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=input_paths,
            output_paths=[tsv_path, svg_path, png_path],
            filters={
                "min_ba": 100,
                "x_metric": "out_degree",
                "y_metric": "eigenvector_centrality_undirected",
                "label_strategy": "top_5_centrality_rows",
            },
            notes=notes,
        ),
    )


def _node_id(node_row: dict[str, Any]) -> str:
    return f"{node_row['node_role']}:{int(node_row['core_id'])}"


def _hub_layout(node_rows: Sequence[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    lnc_nodes = [row for row in node_rows if row["node_role"] == "lncrna"]
    target_nodes = [row for row in node_rows if row["node_role"] == "target"]
    positions: dict[str, tuple[float, float]] = {}
    if lnc_nodes:
        positions[_node_id(lnc_nodes[0])] = (0.18, 0.5)
    if not target_nodes:
        return positions
    ys = np.linspace(0.15, 0.85, len(target_nodes))
    for y_pos, row in zip(ys, target_nodes, strict=True):
        positions[_node_id(row)] = (0.78, float(y_pos))
    return positions


def _community_layout(node_rows: Sequence[dict[str, Any]], edge_rows: Sequence[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    graph = nx.Graph()
    for row in node_rows:
        graph.add_node(_node_id(row))
    for row in edge_rows:
        graph.add_edge(f"lncrna:{int(row['lncrna_core_id'])}", f"target:{int(row['target_core_id'])}", weight=float(row.get("mean_ba") or 0.0))
    positions = nx.spring_layout(graph, seed=42, weight="weight")
    xs = [float(value[0]) for value in positions.values()]
    ys = [float(value[1]) for value in positions.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    normalized: dict[str, tuple[float, float]] = {}
    for key, (x_pos, y_pos) in positions.items():
        x_norm = 0.1 + 0.8 * ((float(x_pos) - min_x) / (max_x - min_x or 1.0))
        y_norm = 0.12 + 0.76 * ((float(y_pos) - min_y) / (max_y - min_y or 1.0))
        normalized[str(key)] = (x_norm, y_norm)
    return normalized


def _draw_module_network(
    ax: plt.Axes,
    *,
    node_rows: Sequence[dict[str, Any]],
    edge_rows: Sequence[dict[str, Any]],
    layout: dict[str, tuple[float, float]],
    title: str,
) -> None:
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    max_ba = max(float(row.get("max_ba") or row.get("mean_ba") or 1.0) for row in edge_rows) if edge_rows else 1.0

    for row in edge_rows:
        source = f"lncrna:{int(row['lncrna_core_id'])}"
        target = f"target:{int(row['target_core_id'])}"
        if source not in layout or target not in layout:
            continue
        x0, y0 = layout[source]
        x1, y1 = layout[target]
        ax.plot(
            [x0, x1],
            [y0, y1],
            color="#999999",
            linewidth=1.0 + 3.0 * (float(row.get("max_ba") or row.get("mean_ba") or 0.0) / max_ba),
            alpha=0.7,
            zorder=1,
        )

    lnc_nodes = [row for row in node_rows if row["node_role"] == "lncrna"]
    target_nodes = [row for row in node_rows if row["node_role"] == "target"]
    if lnc_nodes:
        ax.scatter(
            [layout[_node_id(row)][0] for row in lnc_nodes],
            [layout[_node_id(row)][1] for row in lnc_nodes],
            s=220,
            color="#C81D25",
            edgecolor="black",
            zorder=3,
        )
    if target_nodes:
        ax.scatter(
            [layout[_node_id(row)][0] for row in target_nodes],
            [layout[_node_id(row)][1] for row in target_nodes],
            s=170,
            color="#BFD7EA",
            marker="s",
            edgecolor="black",
            zorder=3,
        )

    for row in node_rows:
        x_pos, y_pos = layout[_node_id(row)]
        ax.text(
            x_pos + (0.02 if row["node_role"] == "lncrna" else 0.015),
            y_pos,
            str(row["display_label"]),
            fontsize=8,
            va="center",
            ha="left",
        )


def generate_fig2d(
    *,
    high_affinity_edge_rows: Sequence[dict[str, Any]],
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    source_commit: str,
    input_paths: Sequence[Path],
) -> None:
    manifest_tsv_path = fig_dir / "fig2D_module_manifest.tsv"
    hub_nodes_tsv_path = fig_dir / "fig2D_hub_module_nodes.tsv"
    hub_edges_tsv_path = fig_dir / "fig2D_hub_module_edges.tsv"
    community_nodes_tsv_path = fig_dir / "fig2D_community_nodes.tsv"
    community_edges_tsv_path = fig_dir / "fig2D_community_edges.tsv"
    svg_path = fig_dir / "fig2D_readable_subnetworks.svg"
    png_path = fig_dir / "fig2D_readable_subnetworks.png"
    meta_path = fig_dir / "fig2D_metadata.json"

    hub_manifest_row, hub_node_rows, hub_edge_rows = select_fig2d_hub_module(high_affinity_edge_rows)
    community_manifest_row, community_node_rows, community_edge_rows = select_fig2d_community_module(high_affinity_edge_rows)

    write_tsv(
        manifest_tsv_path,
        [hub_manifest_row, community_manifest_row],
        ["module_kind", "lncrna_core_id", "node_count", "edge_count", "target_count", "mean_edge_ba"],
    )
    write_tsv(hub_nodes_tsv_path, hub_node_rows, ["node_role", "core_id", "display_label", "species_count", "conservation_count"])
    write_tsv(
        hub_edges_tsv_path,
        hub_edge_rows,
        ["lncrna_core_id", "target_core_id", "lncrna_symbol", "target_symbol", "conservation_count", "species_count", "supporting_regulation_count", "mean_ba", "max_ba"],
    )
    write_tsv(community_nodes_tsv_path, community_node_rows, ["node_role", "core_id", "display_label", "species_count", "conservation_count"])
    write_tsv(
        community_edges_tsv_path,
        community_edge_rows,
        ["lncrna_core_id", "target_core_id", "lncrna_symbol", "target_symbol", "conservation_count", "species_count", "supporting_regulation_count", "mean_ba", "max_ba"],
    )

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8))
    _draw_module_network(
        axes[0],
        node_rows=hub_node_rows,
        edge_rows=hub_edge_rows,
        layout=_hub_layout(hub_node_rows),
        title="Hub-centered module",
    )
    _draw_module_network(
        axes[1],
        node_rows=community_node_rows,
        edge_rows=community_edge_rows,
        layout=_community_layout(community_node_rows, community_edge_rows),
        title="Modular community",
    )
    fig.tight_layout()
    save_figure(fig, svg_path, png_path)

    write_json(
        meta_path,
        panel_metadata(
            panel_id="Figure2D",
            title="Readable subnetworks",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=input_paths,
            output_paths=[
                manifest_tsv_path,
                hub_nodes_tsv_path,
                hub_edges_tsv_path,
                community_nodes_tsv_path,
                community_edges_tsv_path,
                svg_path,
                png_path,
            ],
            filters={
                "min_ba": 100,
                "hub_target_limit": 8,
                "community_node_bounds": [10, 18],
                "community_edge_limit": 14,
            },
        ),
    )


def generate_fig3a(
    *,
    upset_rows: Sequence[dict[str, Any]],
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    source_commit: str,
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
    ax_bar.grid(axis="y", alpha=0.2)

    species_codes = ["human", "chimp", "macaque", "marmoset"]
    y_positions = list(reversed(range(len(species_codes))))
    ax_matrix.set_yticks(y_positions)
    ax_matrix.set_yticklabels(["Human", "Chimpanzee", "Macaque", "Marmoset"])
    ax_matrix.set_ylim(-0.5, len(species_codes) - 0.5)
    ax_matrix.set_xlabel("Binary pattern (H, C, Ma, Mm)")
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
            source_commit=source_commit,
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
    source_commit: str,
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
        ax.set_xticks(xs)
        ax.set_xlabel("Species count")
        ax.set_ylim(0, y_limit)
        ax.set_title(f"{item_type.capitalize()} conservation (n={total})")
        ax.grid(axis="y", alpha=0.2)
    axes[0].set_ylabel("Proportion within item class")
    fig.tight_layout()
    save_figure(fig, svg_path, png_path)

    write_json(
        meta_path,
        panel_metadata(
            panel_id="Figure3B",
            title="Node conservation versus edge conservation",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
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
    source_commit: str,
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
    fig.subplots_adjust(left=0.06, right=0.9, bottom=0.13, top=0.83, wspace=0.08)
    save_figure(fig, svg_path, png_path)

    write_json(
        meta_path,
        panel_metadata(
            panel_id="Figure3C",
            title="Species-pair node and edge sharing",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=input_paths,
            output_paths=[tsv_path, svg_path, png_path],
            filters={"metric": "jaccard", "species_order": species_codes},
        ),
    )


def _draw_species_specific_exemplar(
    ax: plt.Axes,
    *,
    species_code: str,
    species_name: str,
    node_rows: Sequence[dict[str, Any]],
    edge_rows: Sequence[dict[str, Any]],
) -> None:
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title(species_name, fontsize=10, fontweight="bold")

    lnc_node = next((row for row in node_rows if row["node_role"] == "lncrna"), None)
    target_nodes = [row for row in node_rows if row["node_role"] == "target"]
    lnc_pos = (0.18, 0.5)
    ys = np.linspace(0.14, 0.86, max(len(target_nodes), 1))
    target_positions = {int(row["core_id"]): (0.78, float(y_pos)) for row, y_pos in zip(target_nodes, ys, strict=True)}

    if lnc_node is not None:
        ax.scatter([lnc_pos[0]], [lnc_pos[1]], s=210, color="#C81D25", edgecolor="black", zorder=3)
        ax.text(lnc_pos[0] + 0.03, lnc_pos[1], str(lnc_node["display_label"]), fontsize=9.0, va="center")
    for row in target_nodes:
        x_pos, y_pos = target_positions[int(row["core_id"])]
        ax.scatter([x_pos], [y_pos], s=160, marker="s", color="#BFD7EA", edgecolor="black", zorder=2)
        ax.text(x_pos + 0.02, y_pos, str(row["display_label"]), fontsize=10.2, va="center")

    edge_lookup = {
        int(row["target_core_id"]): dict(row)
        for row in edge_rows
        if int(row.get(species_code) or 0)
    }
    max_ba = max(float(row.get("max_ba") or row.get("mean_ba") or 1.0) for row in edge_lookup.values()) if edge_lookup else 1.0
    for target_core_id, row in edge_lookup.items():
        if target_core_id not in target_positions:
            continue
        x_pos, y_pos = target_positions[target_core_id]
        ax.plot(
            [lnc_pos[0], x_pos],
            [lnc_pos[1], y_pos],
            color="#C81D25",
            linewidth=1.2 + 2.6 * (float(row.get("max_ba") or row.get("mean_ba") or 0.0) / max_ba),
            alpha=0.85,
            zorder=1,
        )


def generate_fig3d(
    *,
    node_rows: Sequence[dict[str, Any]],
    edge_rows: Sequence[dict[str, Any]],
    fig_dir: Path,
    repo_root: Path,
    generated_at: str,
    source_commit: str,
    input_paths: Sequence[Path],
) -> None:
    manifest_tsv_path = fig_dir / "fig3D_exemplar_manifest.tsv"
    conserved_nodes_tsv_path = fig_dir / "fig3D_conserved_nodes.tsv"
    conserved_edges_tsv_path = fig_dir / "fig3D_conserved_edges.tsv"
    rewired_nodes_tsv_path = fig_dir / "fig3D_rewired_nodes.tsv"
    rewired_edges_tsv_path = fig_dir / "fig3D_rewired_edges.tsv"
    svg_path = fig_dir / "fig3D_examples.svg"
    png_path = fig_dir / "fig3D_examples.png"
    meta_path = fig_dir / "fig3D_metadata.json"

    conserved_manifest_row, conserved_node_rows, conserved_edge_rows = select_fig3d_conserved_exemplar(node_rows, edge_rows)
    rewired_manifest_row, rewired_node_rows, rewired_edge_rows = select_fig3d_rewired_exemplar(node_rows, edge_rows)

    write_tsv(
        manifest_tsv_path,
        [conserved_manifest_row, rewired_manifest_row],
        ["exemplar_kind", "lncrna_core_id", "node_count", "edge_count", "target_count", "mean_edge_ba", "mean_pairwise_jaccard"],
    )
    write_tsv(conserved_nodes_tsv_path, conserved_node_rows, ["node_role", "core_id", "display_label", "species_count", "conservation_count"])
    write_tsv(
        conserved_edges_tsv_path,
        conserved_edge_rows,
        ["lncrna_core_id", "target_core_id", "target_symbol", "human", "chimp", "macaque", "marmoset", "conservation_count", "supporting_regulation_count", "mean_ba", "max_ba"],
    )
    write_tsv(rewired_nodes_tsv_path, rewired_node_rows, ["node_role", "core_id", "display_label", "species_count", "conservation_count"])
    write_tsv(
        rewired_edges_tsv_path,
        rewired_edge_rows,
        ["lncrna_core_id", "target_core_id", "target_symbol", "human", "chimp", "macaque", "marmoset", "conservation_count", "supporting_regulation_count", "mean_ba", "max_ba"],
    )

    fig, axes = plt.subplots(2, 4, figsize=(15, 8))
    species_sequence = [(str(spec["species_code"]), str(spec["display_name"])) for spec in DEFAULT_SPECIES_ORDER]
    for column, (species_code, species_name) in enumerate(species_sequence):
        _draw_species_specific_exemplar(
            axes[0, column],
            species_code=species_code,
            species_name=species_name,
            node_rows=conserved_node_rows,
            edge_rows=conserved_edge_rows,
        )
        _draw_species_specific_exemplar(
            axes[1, column],
            species_code=species_code,
            species_name=species_name,
            node_rows=rewired_node_rows,
            edge_rows=rewired_edge_rows,
        )
    axes[0, 0].text(-0.02, 1.06, "D1 Conserved module", transform=axes[0, 0].transAxes, va="bottom", ha="left", fontsize=10.5, fontweight="bold", clip_on=False)
    axes[1, 0].text(-0.02, 1.06, "D2 Rewired module", transform=axes[1, 0].transAxes, va="bottom", ha="left", fontsize=10.5, fontweight="bold", clip_on=False)
    fig.tight_layout(rect=[0.02, 0, 1, 0.95])
    save_figure(fig, svg_path, png_path)

    write_json(
        meta_path,
        panel_metadata(
            panel_id="Figure3D",
            title="Paired conserved and rewired exemplars",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=input_paths,
            output_paths=[
                manifest_tsv_path,
                conserved_nodes_tsv_path,
                conserved_edges_tsv_path,
                rewired_nodes_tsv_path,
                rewired_edges_tsv_path,
                svg_path,
                png_path,
            ],
            filters={"species_order": [spec["species_code"] for spec in DEFAULT_SPECIES_ORDER], "max_targets_per_exemplar": 6},
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
    shared_dir = out_dir / "shared"
    fig1_dir = out_dir / "fig1"
    fig2_dir = out_dir / "fig2"
    fig3_dir = out_dir / "fig3"
    supp_dir = out_dir / "supplementary"
    fig2b_alias_manifest_path = (repo_root / DEFAULT_FIG2B_ALIAS_MANIFEST).resolve()

    generated_at = args.generated_at or utc_now_iso()
    source_commit_ref = str(args.source_commit or "HEAD").strip() or "HEAD"
    source_commit = git_commit_sha(repo_root, source_commit_ref)
    if args.source_commit and source_commit == "unknown":
        raise RuntimeError(f"Unable to resolve --source-commit {args.source_commit!r} via git rev-parse")

    snapshot_payload = with_generation_provenance(
        build_frozen_snapshot_payload(repo_root),
        generated_at=generated_at,
        source_commit=source_commit,
    )
    snapshot_json_path = shared_dir / "frozen_submission_snapshot.json"
    write_json(snapshot_json_path, snapshot_payload)

    with connect_db(env_path) as conn:
        fig2b_alias_rows = load_fig2b_alias_manifest(fig2b_alias_manifest_path)
        species_rows = normalize_species_rows(fetch_species_rows(conn), DEFAULT_SPECIES_ORDER)
        node_input_rows = fetch_node_presence_input(conn)
        node_presence_rows = build_node_presence_rows(node_input_rows, DEFAULT_SPECIES_ORDER)
        species_edge_rows = fetch_edge_presence_input(conn)
        edge_presence_rows = build_edge_presence_rows(species_edge_rows, DEFAULT_SPECIES_ORDER)
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

        generate_fig1a(
            fig_dir=fig1_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
        )
        generate_fig1b(
            node_input_rows=node_input_rows,
            fig_dir=fig1_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
        )
        generate_fig1c(
            fig_dir=fig1_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
        )
        generate_fig1d(
            snapshot_payload=snapshot_payload,
            fig_dir=fig1_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
        )

        generate_fig2a(
            conn=conn,
            fig_dir=fig2_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
        )

        hub_rows = build_hub_rows(high_affinity_edge_rows)
        centrality_rows = build_centrality_rows(high_affinity_edge_rows)
        generate_fig2b(
            hub_rows=hub_rows,
            alias_rows=fig2b_alias_rows,
            alias_manifest_path=fig2b_alias_manifest_path,
            fig_dir=fig2_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[high_affinity_tsv_path],
        )
        generate_fig2c(
            centrality_rows=centrality_rows,
            fig_dir=fig2_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[high_affinity_tsv_path],
        )
        generate_fig2d(
            high_affinity_edge_rows=high_affinity_edge_rows,
            fig_dir=fig2_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
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
            source_commit=source_commit,
            input_paths=[edge_tsv_path],
        )
        generate_fig3b(
            summary_rows=summary_rows,
            fig_dir=fig3_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[node_tsv_path, edge_tsv_path],
        )
        generate_fig3c(
            pairwise_rows=pairwise_rows,
            fig_dir=fig3_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[node_tsv_path, edge_tsv_path],
        )
        generate_fig3d(
            node_rows=node_presence_rows,
            edge_rows=edge_presence_rows,
            fig_dir=fig3_dir,
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=[node_tsv_path, edge_tsv_path],
        )


        robustness_threshold_rows = build_robustness_threshold_rows(
            species_edge_rows,
            DEFAULT_SPECIES_ORDER,
            thresholds=SUPP_FIG7_BA_THRESHOLDS,
        )
        null_count_rows = build_null_conservation_summary_rows(
            species_edge_rows,
            DEFAULT_SPECIES_ORDER,
            iterations=SUPP_FIG7_NULL_ITERATIONS,
            rng_seed=SUPP_FIG7_RNG_SEED,
        )
        null_pairwise_rows = build_null_pairwise_summary_rows(
            species_edge_rows,
            DEFAULT_SPECIES_ORDER,
            iterations=SUPP_FIG7_NULL_ITERATIONS,
            rng_seed=SUPP_FIG7_RNG_SEED,
        )
        degree_null_count_rows = build_degree_bin_matched_null_conservation_summary_rows(
            species_edge_rows,
            DEFAULT_SPECIES_ORDER,
            iterations=SUPP_FIG7_NULL_ITERATIONS,
            rng_seed=SUPP_FIG7_RNG_SEED,
        )
        marmoset_downsampling_rows = build_marmoset_edge_count_downsampling_sensitivity_rows(
            species_edge_rows,
            DEFAULT_SPECIES_ORDER,
            iterations=SUPP_FIG7_NULL_ITERATIONS,
            rng_seed=SUPP_FIG7_RNG_SEED,
        )

        suppfig7a_tsv = supp_dir / "suppfig7A_threshold_sensitivity.tsv"
        suppfig7b_tsv = supp_dir / "suppfig7B_null_counts.tsv"
        suppfig7c_tsv = supp_dir / "suppfig7C_null_pairwise.tsv"
        suppfig7d_tsv = supp_dir / "suppfig7D_degree_null_counts.tsv"
        suppfig7e_tsv = supp_dir / "suppfig7E_marmoset_downsampling.tsv"
        suppfig7_svg = supp_dir / "suppfig7_robustness.svg"
        suppfig7_png = supp_dir / "suppfig7_robustness.png"
        suppfig7_meta = supp_dir / "suppfig7_robustness.metadata.json"

        write_tsv(
            suppfig7a_tsv,
            robustness_threshold_rows,
            ["threshold", "threshold_label", "conservation_count", "edge_count", "count_mode"],
        )
        write_tsv(
            suppfig7b_tsv,
            null_count_rows,
            [
                "conservation_count",
                "observed_edge_count",
                "null_mean_edge_count",
                "null_median_edge_count",
                "null_p05_edge_count",
                "null_p95_edge_count",
                "null_iterations",
            ],
        )
        write_tsv(
            suppfig7c_tsv,
            null_pairwise_rows,
            [
                "species_a",
                "species_b",
                "pair_label",
                "observed_jaccard",
                "null_mean_jaccard",
                "null_median_jaccard",
                "null_p05_jaccard",
                "null_p95_jaccard",
                "null_iterations",
            ],
        )
        write_tsv(
            suppfig7d_tsv,
            degree_null_count_rows,
            [
                "null_model",
                "conservation_count",
                "observed_edge_count",
                "null_mean_edge_count",
                "null_median_edge_count",
                "null_p05_edge_count",
                "null_p95_edge_count",
                "null_iterations",
                "matching_rule",
            ],
        )
        write_tsv(
            suppfig7e_tsv,
            marmoset_downsampling_rows,
            [
                "null_model",
                "reference_species",
                "reference_edge_count",
                "downsampled_edge_count_per_species",
                "conservation_count",
                "observed_mean_edge_count",
                "observed_median_edge_count",
                "observed_p05_edge_count",
                "observed_p95_edge_count",
                "null_mean_edge_count",
                "null_median_edge_count",
                "null_p05_edge_count",
                "null_p95_edge_count",
                "null_iterations",
                "sampling_rule",
            ],
        )
        render_suppfig7_robustness(
            robustness_threshold_rows,
            null_count_rows,
            null_pairwise_rows,
            suppfig7_svg,
            suppfig7_png,
        )
        write_json(
            suppfig7_meta,
            panel_metadata(
                panel_id="SupplementaryFigure7",
                title="Robustness of edge-level conservation and rewiring summaries",
                repo_root=repo_root,
                generated_at=generated_at,
                source_commit=source_commit,
                input_paths=[edge_tsv_path],
                output_paths=[suppfig7a_tsv, suppfig7b_tsv, suppfig7c_tsv, suppfig7d_tsv, suppfig7e_tsv, suppfig7_svg, suppfig7_png],
                filters={
                    "ba_thresholds": [0, 100, 150],
                    "null_iterations": SUPP_FIG7_NULL_ITERATIONS,
                    "rng_seed": SUPP_FIG7_RNG_SEED,
                    "strict_null_model": "degree_bin_matched_target_permutation",
                    "coverage_sensitivity": "marmoset_edge_count_downsampling_target_permutation",
                },
                notes=[
                    "BA sensitivity summarizes retained overview edges across fixed thresholds.",
                    "Null comparisons permute target assignments within species while preserving species-level lncRNA and target marginals.",
                    "Degree-bin matched null comparisons additionally preserve lncRNA row-degree tiers and target row-degree tiers within species.",
                    "Marmoset-edge-count downsampling repeats shared-edge calibration with seeded random downsampling for both observed and target-permutation null summaries.",
                ],
            ),
        )

    for path in [
        snapshot_json_path,
        species_tsv_path,
        node_tsv_path,
        edge_tsv_path,
        high_affinity_tsv_path,
        fig1_dir / "fig1A_catalog_gap.tsv",
        fig1_dir / "fig1B_ortholog_counts.tsv",
        fig1_dir / "fig1C_workflow.tsv",
        fig1_dir / "fig1D_kpi.tsv",
        fig2_dir / "fig2A_ba_distribution.tsv",
        fig2_dir / "fig2A_summary.tsv",
        fig2_dir / "fig2B_hubs.tsv",
        fig2_dir / "fig2C_centrality.tsv",
        fig2_dir / "fig2D_module_manifest.tsv",
        fig3_dir / "fig3A_edge_upset.tsv",
        fig3_dir / "fig3B_node_vs_edge.tsv",
        fig3_dir / "fig3C_pairwise_sharing.tsv",
        fig3_dir / "fig3D_exemplar_manifest.tsv",
        supp_dir / "suppfig7A_threshold_sensitivity.tsv",
        supp_dir / "suppfig7B_null_counts.tsv",
        supp_dir / "suppfig7C_null_pairwise.tsv",
        supp_dir / "suppfig7D_degree_null_counts.tsv",
        supp_dir / "suppfig7E_marmoset_downsampling.tsv",
        supp_dir / "suppfig7_robustness.svg",
    ]:
        print(f"Wrote: {display_path(path, repo_root)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
