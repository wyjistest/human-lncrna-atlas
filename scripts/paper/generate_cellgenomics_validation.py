#!/usr/bin/env python3
"""Generate Cell Genomics-style validation assets for the paper package.

The script intentionally consumes frozen, reviewer-facing TSV assets instead of
querying the live database. Large ENCODE/GTEx matrices should be preprocessed
into the compact expression-support TSV accepted by this entrypoint.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
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
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = Path(__file__).resolve()

DEFAULT_EXTERNAL_DATA_VERSIONS = {
    "ENCODE_RNA_seq": {
        "version": "processed compact matrix supplied by paper_figures/external/cellgenomics_expression_support.tsv",
        "url": "https://www.encodeproject.org/",
        "license_or_terms": "ENCODE data use terms; cite ENCODE Project Consortium",
    },
    "GTEx_v8": {
        "version": "GTEx Analysis V8 processed expression context",
        "url": "https://gtexportal.org/home/datasets",
        "license_or_terms": "GTEx Portal data use terms",
    },
    "GO_functional_terms": {
        "version": "GO biological-process annotations supplied by paper_figures/external/cellgenomics_functional_terms.tsv",
        "url": "https://geneontology.org/; https://mygene.info/",
        "license_or_terms": "GO and MyGene.info source terms",
    },
}

DEFAULT_CONTEXTS = [
    ("ENCODE", "A549"),
    ("ENCODE", "GM12878"),
    ("ENCODE", "H1-hESC"),
    ("ENCODE", "HepG2"),
    ("ENCODE", "HMEC"),
    ("ENCODE", "K562"),
    ("GTEx", "Adipose_Subcutaneous"),
    ("GTEx", "Adipose_Visceral_Omentum"),
    ("GTEx", "Liver"),
    ("GTEx", "Muscle_Skeletal"),
    ("GTEx", "Whole_Blood"),
]

FIG6_OUTPUTS = {
    "Figure6A": "fig6A_atlas_wide_evidence",
    "Figure6B": "fig6B_expression_support",
    "Figure6C": "fig6C_functional_coherence",
    "Figure6D": "fig6D_flagship_evidence_card",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _tsv_value(row.get(field)) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _tsv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return value


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
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
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def git_commit_sha(repo_root: Path, ref: str = "HEAD") -> str:
    if re.fullmatch(r"[0-9a-fA-F]{40}", ref):
        return ref.lower()
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
    source_commit: str,
    input_paths: Sequence[Path],
    output_paths: Sequence[Path],
    generation_parameters: dict[str, Any],
    notes: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "panel_id": panel_id,
        "title": title,
        "script": display_path(SCRIPT_PATH, repo_root),
        "inputs": [display_path(path, repo_root) for path in input_paths],
        "outputs": [display_path(path, repo_root) for path in output_paths],
        "external_data_versions": DEFAULT_EXTERNAL_DATA_VERSIONS,
        "generation_parameters": generation_parameters,
        "notes": list(notes or []),
        "generated_at": generated_at,
        "source_commit": source_commit,
    }


def _normalize_alias(value: Any) -> str:
    return str(value or "").strip()


def _alias_keys(value: Any) -> set[str]:
    raw = _normalize_alias(value)
    if not raw:
        return set()
    return {raw, raw.upper()}


def _core_id_from_node(node: dict[str, Any]) -> str:
    node_id = str(node.get("node_id") or "")
    if "_" in node_id:
        suffix = node_id.rsplit("_", 1)[-1]
        if suffix.isdigit():
            return suffix
    return str(node.get("core_id") or node.get("gene_id") or "").strip()


def build_default_alias_rows(
    module_nodes: Sequence[dict[str, Any]],
    flagship_manifest: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for node in module_nodes:
        core_id = _core_id_from_node(node)
        if not core_id:
            continue
        node_type = str(node.get("node_type") or "")
        display_label = str(node.get("display_label") or "")
        rows.append(
            {
                "external_id": display_label,
                "core_id": core_id,
                "gene_symbol": display_label,
                "gene_type": "lncrna" if node_type == "lncrna" else "protein_coding",
            }
        )
    if flagship_manifest:
        lnc_id = str(flagship_manifest.get("lncrna_gene_id") or "").strip()
        lnc_name = str(flagship_manifest.get("lncrna_name") or "").strip()
        if lnc_id and lnc_name:
            rows.append(
                {
                    "external_id": lnc_name,
                    "core_id": lnc_id,
                    "gene_symbol": lnc_name,
                    "gene_type": "lncrna",
                }
            )
    return rows


def _build_alias_lookup(alias_rows: Sequence[dict[str, Any]]) -> tuple[dict[str, set[str]], dict[str, dict[str, Any]]]:
    alias_to_core_ids: dict[str, set[str]] = defaultdict(set)
    alias_payload: dict[str, dict[str, Any]] = {}
    for row in alias_rows:
        core_id = str(row.get("core_id") or "").strip()
        if not core_id:
            continue
        for key in _alias_keys(row.get("external_id")) | _alias_keys(row.get("gene_symbol")):
            alias_to_core_ids[key].add(core_id)
            alias_payload.setdefault(key, dict(row))
    return alias_to_core_ids, alias_payload


def _node_aliases(node: dict[str, Any], flagship_manifest: dict[str, Any] | None = None) -> set[str]:
    aliases = set()
    aliases |= _alias_keys(node.get("display_label"))
    aliases |= _alias_keys(node.get("external_id"))
    aliases |= _alias_keys(node.get("gene_symbol"))
    core_id = _core_id_from_node(node)
    if core_id:
        aliases.add(core_id)
    if flagship_manifest and str(node.get("node_type") or "") == "lncrna":
        aliases |= _alias_keys(flagship_manifest.get("lncrna_name"))
    return {alias for alias in aliases if alias}


def build_expression_support_rows(
    module_nodes: Sequence[dict[str, Any]],
    *,
    expression_rows: Sequence[dict[str, Any]],
    alias_rows: Sequence[dict[str, Any]],
    min_tpm: float = 1.0,
    contexts: Sequence[tuple[str, str]] | None = None,
    flagship_manifest: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    alias_to_core_ids, _ = _build_alias_lookup(alias_rows)
    expression_contexts = list(contexts) if contexts is not None else list(DEFAULT_CONTEXTS)
    for row in expression_rows:
        key = (str(row.get("source") or "unknown"), str(row.get("context") or "unknown"))
        if key not in expression_contexts:
            expression_contexts.append(key)
    if not expression_contexts:
        expression_contexts = list(DEFAULT_CONTEXTS)

    mapped_values: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    ambiguous_aliases_by_context: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in expression_rows:
        source = str(row.get("source") or "unknown")
        context = str(row.get("context") or "unknown")
        external_id = str(row.get("external_id") or row.get("gene_id") or row.get("gene_symbol") or "").strip()
        keys = _alias_keys(external_id)
        resolved: set[str] = set()
        for key in keys:
            resolved |= alias_to_core_ids.get(key, set())
        if len(resolved) == 1:
            core_id = next(iter(resolved))
            mapped_values[(core_id, source, context)].append(safe_float(row.get("tpm")))
        elif len(resolved) > 1:
            ambiguous_aliases_by_context[(source, context)].update(keys)

    output: list[dict[str, Any]] = []
    for node in module_nodes:
        node_type = str(node.get("node_type") or "")
        if node_type not in {"lncrna", "gene"}:
            continue
        core_id = _core_id_from_node(node)
        aliases = _node_aliases(node, flagship_manifest=flagship_manifest)
        display_label = str(node.get("display_label") or core_id)
        for source, context in expression_contexts:
            values = mapped_values.get((core_id, source, context), [])
            ambiguous = bool(aliases & ambiguous_aliases_by_context.get((source, context), set()))
            if values:
                expression_tpm: float | None = round(float(statistics.fmean(values)), 6)
                mapping_status = "mapped"
            elif ambiguous:
                expression_tpm = None
                mapping_status = "ambiguous"
            else:
                expression_tpm = None
                mapping_status = "missing"
            output.append(
                {
                    "core_id": core_id,
                    "node_type": "lncrna" if node_type == "lncrna" else "protein_coding",
                    "display_label": display_label,
                    "source": source,
                    "context": context,
                    "expression_tpm": expression_tpm,
                    "expression_supported": expression_tpm is not None and expression_tpm >= min_tpm,
                    "mapping_status": mapping_status,
                }
            )
    return output


def build_expression_summary_rows(expression_support_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in expression_support_rows:
        if str(row.get("node_type") or "") != "protein_coding":
            continue
        grouped[(str(row["source"]), str(row["context"]))].append(row)

    output: list[dict[str, Any]] = []
    for (source, context), rows in sorted(grouped.items()):
        mappable_rows = [row for row in rows if str(row.get("mapping_status")) == "mapped"]
        supported_rows = [row for row in mappable_rows if safe_bool(row.get("expression_supported"))]
        output.append(
            {
                "source": source,
                "context": context,
                "tested_node_count": len(rows),
                "mappable_node_count": len(mappable_rows),
                "mapping_rate": round(len(mappable_rows) / len(rows), 6) if rows else 0.0,
                "expression_supported_node_count": len(supported_rows),
                "expression_supported_fraction": round(len(supported_rows) / len(mappable_rows), 6)
                if mappable_rows
                else 0.0,
                "analysis_mode": "mappable_subset",
                "analysis_scope": "pcg_target_program",
            }
        )
    return output


def _median(values: Sequence[float | int]) -> float:
    cleaned = [float(value) for value in values if value is not None]
    if not cleaned:
        return 0.0
    return round(float(statistics.median(cleaned)), 6)


def _slug(value: Any) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip()).strip("_")
    return slug or "module"


def _parse_gene_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [gene for gene in value.split(";") if gene]
    return [str(gene) for gene in list(value or []) if str(gene)]


def _summarize_module_group(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    module_count = len(rows)
    conserved = [
        row
        for row in rows
        if str(row.get("rewiring_label") or "") == "conserved"
        or safe_int(row.get("best_edge_conservation_count")) >= 4
    ]
    rewired = [
        row
        for row in rows
        if str(row.get("rewiring_label") or "") in {"rewired", "species_specific"}
    ]
    return {
        "module_count": module_count,
        "median_target_count": _median(
            [
                safe_float(row.get("target_count", row.get("candidate_target_count", row.get("candidate_targets"))))
                for row in rows
            ]
        ),
        "median_high_affinity_edges": _median(
            [
                safe_float(row.get("high_affinity_edge_count", row.get("high_affinity_edges")))
                for row in rows
            ]
        ),
        "conserved_module_fraction": round(len(conserved) / module_count, 6) if module_count else 0.0,
        "rewired_module_fraction": round(len(rewired) / module_count, 6) if module_count else 0.0,
    }


def build_atlas_wide_evidence_rows(
    *,
    ranking_rows: Sequence[dict[str, Any]],
    trait_prioritization_rows: Sequence[dict[str, Any]],
    flagship_manifest: dict[str, Any],
    null_count_rows: Sequence[dict[str, Any]],
    strict_null_count_rows: Sequence[dict[str, Any]] | None = None,
    top_n: int = 20,
) -> list[dict[str, Any]]:
    top_rows = list(ranking_rows[:top_n])
    if not top_rows and flagship_manifest:
        top_rows = [flagship_manifest]

    conserved_rows = [
        row
        for row in trait_prioritization_rows
        if str(row.get("rewiring_label") or "") == "conserved"
        and safe_int(row.get("best_edge_conservation_count")) >= 4
    ]
    rewired_rows = [
        row
        for row in trait_prioritization_rows
        if str(row.get("rewiring_label") or "") in {"rewired", "species_specific"}
    ]
    null_four_species = next(
        (row for row in null_count_rows if safe_int(row.get("conservation_count")) == 4),
        {},
    )
    strict_null_four_species = next(
        (row for row in (strict_null_count_rows or []) if safe_int(row.get("conservation_count")) == 4),
        {},
    )

    output: list[dict[str, Any]] = []
    for scope, label, rows, interpretation in [
        (
            "top_prioritized_modules",
            f"Top {len(top_rows)} prioritized lncRNA target-program modules",
            top_rows,
            "Atlas-wide prioritized modules are summarized across ranking, edge-conservation, and epigenomic-context features.",
        ),
        (
            "conserved_modules",
            "Conserved candidate modules across the atlas",
            conserved_rows,
            "Conserved modules capture target programs with four-species edge-level support rather than node conservation alone.",
        ),
        (
            "rewired_modules",
            "Rewired or species-specific candidate modules across the atlas",
            rewired_rows,
            "Rewired modules capture lineage-specific candidate target programs for comparative follow-up.",
        ),
    ]:
        summary = _summarize_module_group(rows)
        output.append(
            {
                "evidence_scope": scope,
                "module_count": summary["module_count"],
                "median_target_count": summary["median_target_count"],
                "median_high_affinity_edges": summary["median_high_affinity_edges"],
                "conserved_module_fraction": summary["conserved_module_fraction"],
                "rewired_module_fraction": summary["rewired_module_fraction"],
                "observed_value": summary["module_count"],
                "null_or_background_value": "",
                "null_iterations": "",
                "evidence_label": label,
                "interpretation": interpretation,
            }
        )

    flagship_summary = _summarize_module_group([flagship_manifest] if flagship_manifest else [])
    output.append(
        {
            "evidence_scope": "obesity_flagship",
            "module_count": 1 if flagship_manifest else 0,
            "median_target_count": flagship_summary["median_target_count"],
            "median_high_affinity_edges": flagship_summary["median_high_affinity_edges"],
            "conserved_module_fraction": flagship_summary["conserved_module_fraction"],
            "rewired_module_fraction": flagship_summary["rewired_module_fraction"],
            "observed_value": safe_float(flagship_manifest.get("flagship_targets_with_trait_literature_support_fraction")),
            "null_or_background_value": "",
            "null_iterations": "",
            "evidence_label": "Obesity flagship representative case",
            "interpretation": "The obesity module is retained as a representative evidence card, not the sole benchmarking layer.",
        }
    )

    if null_four_species:
        output.append(
            {
                "evidence_scope": "edge_conservation_null",
                "module_count": "",
                "median_target_count": "",
                "median_high_affinity_edges": "",
                "conserved_module_fraction": "",
                "rewired_module_fraction": "",
                "observed_value": safe_float(null_four_species.get("observed_edge_count")),
                "null_or_background_value": safe_float(null_four_species.get("null_p95_edge_count")),
                "null_iterations": safe_int(null_four_species.get("null_iterations")),
                "evidence_label": "Four-species edge conservation null calibration",
                "interpretation": "Observed shared candidate edges are compared against the target-permutation null p95.",
            }
        )
    if strict_null_four_species:
        output.append(
            {
                "evidence_scope": "degree_bin_matched_edge_null",
                "module_count": "",
                "median_target_count": "",
                "median_high_affinity_edges": "",
                "conserved_module_fraction": "",
                "rewired_module_fraction": "",
                "observed_value": safe_float(strict_null_four_species.get("observed_edge_count")),
                "null_or_background_value": safe_float(strict_null_four_species.get("null_p95_edge_count")),
                "null_iterations": safe_int(strict_null_four_species.get("null_iterations")),
                "evidence_label": "Four-species edge conservation degree-bin matched null",
                "interpretation": "Observed shared candidate edges are compared against a stricter degree-bin matched target-permutation null.",
            }
        )
    return output


def _module_targets_from_edges(
    edge_rows: Sequence[dict[str, Any]],
    *,
    lncrna_core_id: Any = None,
    lncrna_symbol: Any = None,
    max_genes: int,
) -> list[str]:
    core_id = str(lncrna_core_id or "").strip()
    symbol = str(lncrna_symbol or "").strip()
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in edge_rows:
        if core_id and str(row.get("lncrna_core_id") or "").strip() != core_id:
            if not symbol or str(row.get("lncrna_symbol") or "").strip() != symbol:
                continue
        elif symbol and str(row.get("lncrna_symbol") or "").strip() != symbol:
            continue
        elif not core_id and not symbol:
            continue
        gene = str(row.get("target_symbol") or "").strip()
        if not gene or gene in seen:
            continue
        seen.add(gene)
        candidates.append(row)
    candidates.sort(
        key=lambda row: (
            -safe_float(row.get("max_ba", row.get("mean_ba"))),
            -safe_int(row.get("conservation_count")),
            str(row.get("target_symbol") or ""),
        )
    )
    return [str(row.get("target_symbol")) for row in candidates[:max_genes]]


def build_atlas_module_gene_sets(
    *,
    ranking_rows: Sequence[dict[str, Any]],
    trait_prioritization_rows: Sequence[dict[str, Any]],
    case_nodes: Sequence[dict[str, Any]],
    edge_rows: Sequence[dict[str, Any]],
    top_n: int = 8,
    max_genes_per_module: int = 20,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    used_module_ids: set[str] = set()

    def add_module(module_id: str, module_group: str, label: str, genes: Sequence[str]) -> None:
        cleaned = [gene for gene in genes if gene]
        if not cleaned or module_id in used_module_ids:
            return
        used_module_ids.add(module_id)
        output.append(
            {
                "module_id": module_id,
                "module_group": module_group,
                "module_label": label,
                "genes": list(cleaned),
                "target_gene_count": len(cleaned),
            }
        )

    for row in list(ranking_rows[:top_n]):
        core_id = row.get("lncrna_gene_id")
        label = str(row.get("lncrna_name") or core_id or "top")
        genes = _module_targets_from_edges(
            edge_rows,
            lncrna_core_id=core_id,
            lncrna_symbol=label,
            max_genes=max_genes_per_module,
        )
        add_module(f"top_prioritized_{_slug(core_id or label)}", "top_prioritized", label, genes)

    conserved_rows = sorted(
        [
            row
            for row in trait_prioritization_rows
            if str(row.get("rewiring_label") or "") == "conserved"
            and safe_int(row.get("best_edge_conservation_count")) >= 4
        ],
        key=lambda row: (
            -safe_int(row.get("high_affinity_edges")),
            -safe_int(row.get("candidate_target_count")),
            str(row.get("candidate_lncRNA") or ""),
        ),
    )
    rewired_rows = sorted(
        [
            row
            for row in trait_prioritization_rows
            if str(row.get("rewiring_label") or "") in {"rewired", "species_specific"}
        ],
        key=lambda row: (
            -safe_int(row.get("high_affinity_edges")),
            -safe_int(row.get("candidate_target_count")),
            str(row.get("candidate_lncRNA") or ""),
        ),
    )
    for module_group, rows in [("conserved", conserved_rows), ("rewired", rewired_rows)]:
        for row in rows[: max(1, min(3, top_n))]:
            label = str(row.get("candidate_lncRNA") or "")
            genes = _module_targets_from_edges(edge_rows, lncrna_symbol=label, max_genes=max_genes_per_module)
            add_module(f"{module_group}_{_slug(label)}", module_group, label, genes)

    add_module(
        "flagship_obesity",
        "obesity_flagship",
        "CATG00000045621.1 obesity target program",
        _case_target_symbols(case_nodes),
    )
    return output


def build_annotation_matched_null_gene_sets(
    module_gene_sets: Sequence[dict[str, Any]],
    *,
    edge_rows: Sequence[dict[str, Any]],
    annotation_rows: Sequence[dict[str, Any]],
    iterations: int = 100,
    seed: int = 42,
) -> list[dict[str, Any]]:
    lookup = _term_lookup(annotation_rows)
    background_genes = sorted(
        {
            str(row.get("target_symbol") or "").strip()
            for row in edge_rows
            if str(row.get("target_symbol") or "").strip() and lookup.get(str(row.get("target_symbol") or "").strip())
        }
    )
    if not background_genes:
        return []

    rng = random.Random(seed)
    output: list[dict[str, Any]] = []
    for module in module_gene_sets:
        module_id = str(module.get("module_id") or "")
        observed_genes = _parse_gene_list(module.get("genes"))
        annotated_observed = [gene for gene in observed_genes if lookup.get(gene)]
        sample_size = len(annotated_observed) or len(observed_genes)
        if not module_id or sample_size <= 0:
            continue
        candidates = [gene for gene in background_genes if gene not in set(observed_genes)]
        if not candidates:
            candidates = list(background_genes)
        for iteration in range(1, int(iterations) + 1):
            if len(candidates) >= sample_size:
                genes = rng.sample(candidates, sample_size)
            else:
                genes = [rng.choice(candidates) for _ in range(sample_size)]
            output.append(
                {
                    "module_id": module_id,
                    "null_set_id": f"annotation_matched_{iteration:03d}",
                    "genes": genes,
                    "matching_rule": (
                        f"target_gene_set_size={len(observed_genes)};"
                        f"annotation_available={sample_size};"
                        "source=atlas_high_affinity_core_edges"
                    ),
                }
            )
    return output


def build_known_evidence_benchmark_rows(
    *,
    atlas_rows: Sequence[dict[str, Any]],
    expression_summary_rows: Sequence[dict[str, Any]],
    functional_rows: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in atlas_rows:
        output.append(
            {
                "benchmark_layer": "atlas_wide_module_summary",
                "evidence_scope": row.get("evidence_scope"),
                "observed_value": row.get("observed_value"),
                "background_value": row.get("null_or_background_value"),
                "module_count": row.get("module_count"),
                "interpretation": row.get("interpretation"),
            }
        )
    best_expression = max(
        expression_summary_rows,
        key=lambda row: safe_float(row.get("expression_supported_fraction")),
        default={},
    )
    output.append(
        {
            "benchmark_layer": "pcg_target_program_expression",
            "evidence_scope": "best_context",
            "observed_value": safe_float(best_expression.get("expression_supported_fraction")),
            "background_value": "",
            "module_count": safe_int(best_expression.get("tested_node_count")),
            "interpretation": "Expression context is summarized over the mappable PCG target program, not direct lncRNA–PCG co-expression.",
        }
    )
    if functional_rows:
        above_null = [row for row in functional_rows if safe_float(row.get("observed_score")) > safe_float(row.get("null_mean"))]
        output.append(
            {
                "benchmark_layer": "module_functional_coherence",
                "evidence_scope": "multi_module_distribution",
                "observed_value": round(len(above_null) / len(functional_rows), 6),
                "background_value": "observed_score > null_mean",
                "module_count": len(functional_rows),
                "interpretation": "GO coherence is treated as module-level benchmarking context.",
            }
        )
    return output


def build_matched_random_background(
    observed_rows: Sequence[dict[str, Any]],
    background_rows: Sequence[dict[str, Any]],
    *,
    matching_fields: Sequence[str],
    seed: int = 42,
) -> list[dict[str, Any]]:
    grouped_background: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    observed_symbols = {str(row.get("target_gene_symbol") or "") for row in observed_rows}
    for row in background_rows:
        if str(row.get("target_gene_symbol") or "") in observed_symbols:
            continue
        key = tuple(row.get(field) for field in matching_fields)
        grouped_background[key].append(dict(row))

    rng = random.Random(seed)
    output: list[dict[str, Any]] = []
    for observed in observed_rows:
        key = tuple(observed.get(field) for field in matching_fields)
        candidates = grouped_background.get(key, [])
        if not candidates:
            raise ValueError(f"No matched background row for constraints {key!r}")
        selected_index = rng.randrange(len(candidates))
        selected = dict(candidates[selected_index])
        output.append(selected)
        grouped_background[key] = [
            row for index, row in enumerate(candidates) if index != selected_index
        ]
        if not grouped_background[key]:
            grouped_background[key] = candidates
    return output


def _term_lookup(annotation_rows: Sequence[dict[str, Any]]) -> dict[str, set[tuple[str, str]]]:
    lookup: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in annotation_rows:
        gene = str(row.get("gene_symbol") or row.get("gene") or "").strip()
        term_id = str(row.get("term_id") or row.get("pathway_id") or row.get("term_name") or "").strip()
        term_name = str(row.get("term_name") or term_id).strip()
        if gene and term_id:
            lookup[gene].add((term_id, term_name))
    return lookup


def _coherence_score(genes: Sequence[str], lookup: dict[str, set[tuple[str, str]]]) -> dict[str, Any]:
    tested_genes = [gene for gene in genes if lookup.get(gene)]
    if not tested_genes:
        return {
            "tested_gene_count": 0,
            "observed_score": 0.0,
            "best_term_id": "",
            "best_term_name": "",
            "best_term_gene_count": 0,
        }
    term_counts: dict[tuple[str, str], int] = defaultdict(int)
    for gene in tested_genes:
        for term in lookup.get(gene, set()):
            term_counts[term] += 1
    best_term, best_count = sorted(
        term_counts.items(),
        key=lambda item: (-item[1], item[0][1], item[0][0]),
    )[0]
    return {
        "tested_gene_count": len(tested_genes),
        "observed_score": round(best_count / len(tested_genes), 6),
        "best_term_id": best_term[0],
        "best_term_name": best_term[1],
        "best_term_gene_count": best_count,
    }


def _bh_fdr(p_values: Sequence[float]) -> list[float]:
    if not p_values:
        return []
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    n = len(indexed)
    adjusted = [0.0 for _ in p_values]
    running = 1.0
    for rank_from_end, (index, p_value) in enumerate(reversed(indexed), start=1):
        rank = n - rank_from_end + 1
        running = min(running, p_value * n / rank)
        adjusted[index] = min(1.0, round(running, 6))
    return adjusted


def build_functional_coherence_rows(
    module_gene_sets: Sequence[dict[str, Any]],
    *,
    annotation_rows: Sequence[dict[str, Any]],
    null_gene_sets: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    lookup = _term_lookup(annotation_rows)
    null_by_module: dict[str, list[Sequence[str]]] = defaultdict(list)
    for row in null_gene_sets:
        module_id = str(row.get("module_id") or "")
        genes = list(row.get("genes") or [])
        if isinstance(row.get("genes"), str):
            genes = [gene for gene in str(row.get("genes") or "").split(";") if gene]
        if module_id:
            null_by_module[module_id].append(genes)

    rows: list[dict[str, Any]] = []
    p_values: list[float] = []
    for module in module_gene_sets:
        module_id = str(module.get("module_id") or "module")
        genes = list(module.get("genes") or [])
        if isinstance(module.get("genes"), str):
            genes = [gene for gene in str(module.get("genes") or "").split(";") if gene]
        observed = _coherence_score(genes, lookup)
        null_scores = [
            _coherence_score(null_genes, lookup)["observed_score"]
            for null_genes in null_by_module.get(module_id, [])
        ]
        if null_scores:
            null_mean = float(statistics.fmean(null_scores))
            null_p95 = float(np.quantile(null_scores, 0.95))
            empirical_percentile = sum(1 for score in null_scores if score <= observed["observed_score"]) / len(null_scores)
            empirical_p_value = (1 + sum(1 for score in null_scores if score >= observed["observed_score"])) / (len(null_scores) + 1)
        else:
            null_mean = 0.0
            null_p95 = 0.0
            empirical_percentile = 1.0 if observed["observed_score"] > 0 else 0.0
            empirical_p_value = 1.0
        rows.append(
            {
                "module_id": module_id,
                "tested_gene_count": observed["tested_gene_count"],
                "observed_score": observed["observed_score"],
                "null_mean": round(null_mean, 6),
                "null_p95": round(null_p95, 6),
                "empirical_percentile": round(empirical_percentile, 6),
                "empirical_p_value": round(empirical_p_value, 6),
                "fdr": 1.0,
                "best_term_id": observed["best_term_id"],
                "best_term_name": observed["best_term_name"],
                "best_term_gene_count": observed["best_term_gene_count"],
            }
        )
        p_values.append(float(rows[-1]["empirical_p_value"]))
    for row, fdr in zip(rows, _bh_fdr(p_values), strict=True):
        row["fdr"] = fdr
    return rows


def build_known_evidence_rows(
    flagship_manifest: dict[str, Any],
    trait_support_rows: Sequence[dict[str, Any]],
    null_count_rows: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    trait_name = str(flagship_manifest.get("trait_name") or "")
    trait_row = next((row for row in trait_support_rows if str(row.get("trait_name") or "") == trait_name), {})
    null_four_species = next(
        (row for row in null_count_rows if safe_int(row.get("conservation_count")) == 4),
        {},
    )
    output = [
        {
            "evidence_layer": "trait_gene_provenance",
            "observed_value": safe_float(trait_row.get("literature_supported_target_fraction")),
            "null_or_background_value": "",
            "supporting_count": safe_int(trait_row.get("literature_supported_target_gene_count")),
            "tested_count": safe_int(trait_row.get("unique_target_gene_count")),
            "evidence_label": "Trait-gene provenance overlap",
            "interpretation": "Prior trait-gene support for the target program; not lncRNA regulation validation",
        },
        {
            "evidence_layer": "flagship_module_provenance",
            "observed_value": safe_float(flagship_manifest.get("flagship_targets_with_trait_literature_support_fraction")),
            "null_or_background_value": "",
            "supporting_count": safe_int(flagship_manifest.get("flagship_targets_with_trait_literature_support")),
            "tested_count": safe_int(flagship_manifest.get("candidate_targets")),
            "evidence_label": "Flagship displayed targets with trait support",
            "interpretation": "Displayed obesity targets trace to trait-gene provenance",
        },
    ]
    if null_four_species:
        output.append(
            {
                "evidence_layer": "edge_conservation_null",
                "observed_value": safe_float(null_four_species.get("observed_edge_count")),
                "null_or_background_value": safe_float(null_four_species.get("null_p95_edge_count")),
                "supporting_count": safe_int(null_four_species.get("observed_edge_count")),
                "tested_count": safe_int(null_four_species.get("null_iterations")),
                "evidence_label": "Four-species edge conservation calibration",
                "interpretation": "Observed shared candidate edges exceed matched target-permutation null p95",
            }
        )
    return output


def build_flagship_evidence_card_rows(
    flagship_manifest: dict[str, Any],
    expression_summary_rows: Sequence[dict[str, Any]],
    functional_rows: Sequence[dict[str, Any]],
    known_rows: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    best_expression = max(
        expression_summary_rows,
        key=lambda row: (
            safe_float(row.get("expression_supported_fraction")),
            safe_float(row.get("mapping_rate")),
            str(row.get("source")),
            str(row.get("context")),
        ),
        default={},
    )
    flagship_function = next((row for row in functional_rows if row.get("module_id") == "flagship_obesity"), {})
    provenance = next((row for row in known_rows if row.get("evidence_layer") == "flagship_module_provenance"), {})
    return [
        {
            "metric": "lead_lncRNA",
            "value": flagship_manifest.get("lncrna_name"),
            "source": "fig5D_case_manifest.tsv",
        },
        {
            "metric": "displayed_targets",
            "value": safe_int(flagship_manifest.get("candidate_targets")),
            "source": "fig5D_case_manifest.tsv",
        },
        {
            "metric": "high_affinity_edges",
            "value": safe_int(flagship_manifest.get("high_affinity_edges")),
            "source": "fig5D_case_manifest.tsv",
        },
        {
            "metric": "binding_affinity_range",
            "value": flagship_manifest.get("ba_range"),
            "source": "fig5D_case_manifest.tsv",
        },
        {
            "metric": "conservation_rewiring_class",
            "value": f"{flagship_manifest.get('best_edge_conservation_count')}-species / {flagship_manifest.get('rewiring_label')}",
            "source": "fig5D_case_manifest.tsv",
        },
        {
            "metric": "epigenomic_class",
            "value": flagship_manifest.get("epigenomic_support_class"),
            "source": "fig5D_case_manifest.tsv",
        },
        {
            "metric": "literature_backed_targets",
            "value": f"{safe_int(provenance.get('supporting_count'))}/{safe_int(provenance.get('tested_count'))}",
            "source": "supp_table1_trait_literature_support.tsv",
        },
        {
            "metric": "best_expression_context",
            "value": f"{best_expression.get('source', 'NA')}:{best_expression.get('context', 'NA')} ({safe_float(best_expression.get('expression_supported_fraction')):.2f})",
            "source": "fig6B_expression_support.tsv",
        },
        {
            "metric": "functional_coherence",
            "value": f"{safe_float(flagship_function.get('observed_score')):.2f} vs null mean {safe_float(flagship_function.get('null_mean')):.2f}",
            "source": "fig6C_functional_coherence.tsv",
        },
    ]


def _case_target_symbols(module_nodes: Sequence[dict[str, Any]]) -> list[str]:
    return [
        str(row.get("display_label") or "")
        for row in module_nodes
        if str(row.get("node_type") or "") == "gene" and str(row.get("display_label") or "")
    ]


def _default_null_gene_sets(target_symbols: Sequence[str]) -> list[dict[str, Any]]:
    if not target_symbols:
        return []
    rotated = list(target_symbols[1:]) + list(target_symbols[:1])
    reversed_genes = list(reversed(target_symbols))
    return [
        {"module_id": "flagship_obesity", "genes": rotated},
        {"module_id": "flagship_obesity", "genes": reversed_genes},
    ]


def _default_background_rows(target_symbols: Sequence[str]) -> list[dict[str, Any]]:
    return [
        {
            "target_gene_symbol": gene,
            "lncrna_degree_tier": "flagship",
            "ba_tier": "BA100",
            "target_availability": "mappable",
        }
        for gene in target_symbols
    ]


def render_fig6a(rows: Sequence[dict[str, Any]], svg_path: Path, png_path: Path) -> None:
    labels = [str(row["evidence_label"]) for row in rows]
    observed = [safe_float(row.get("observed_value")) for row in rows]
    background = [
        safe_float(row.get("null_or_background_value")) if row.get("null_or_background_value") not in ("", None) else 0.0
        for row in rows
    ]
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    y = np.arange(len(rows))
    colors = ["#4C78A8" if str(row.get("evidence_scope")) != "obesity_flagship" else "#F58518" for row in rows]
    ax.barh(y, observed, color=colors, label="Observed")
    if any(value > 0 for value in background):
        ax.scatter(background, y, color="#E45756", s=60, label="Null/background")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Count or calibration statistic")
    ax.set_title("A. Atlas-wide benchmarking and robustness summary")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(axis="x", alpha=0.2)
    save_figure(fig, svg_path, png_path)


def render_fig6b(rows: Sequence[dict[str, Any]], svg_path: Path, png_path: Path) -> None:
    plot_rows = [row for row in rows if str(row.get("source") or "") == "GTEx"] or list(rows)
    skipped_contexts = [f"{row['source']}:{row['context']}" for row in rows if row not in plot_rows]
    labels = [f"{row['source']}:{row['context']}".replace("_", " ") for row in plot_rows]
    supported = [safe_float(row.get("expression_supported_fraction")) for row in plot_rows]
    mapping = [safe_float(row.get("mapping_rate")) for row in plot_rows]
    x = np.arange(len(plot_rows))
    fig, ax = plt.subplots(figsize=(max(8.2, len(plot_rows) * 1.05), 5.7))
    ax.bar(x - 0.18, mapping, width=0.36, color="#72B7B2", label="Mappable")
    ax.bar(x + 0.18, supported, width=0.36, color="#F58518", label="PCG targets TPM ≥ 1")
    ax.set_ylim(0, 1.05)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("Fraction")
    ax.set_title("B. PCG target-program expression context")
    if skipped_contexts:
        ax.text(
            0.02,
            0.96,
            "ENCODE contexts retained in manifest; not evaluated in main PCG context bars",
            transform=ax.transAxes,
            fontsize=8.6,
            color="#5F6C7B",
            ha="left",
            va="top",
            bbox={"boxstyle": "round,pad=0.24", "facecolor": "#F2F4F7", "edgecolor": "#CBD5E1", "alpha": 0.92},
        )
    ax.text(
        0.0,
        -0.31,
        "PCG target-program only; lncRNA alias missing != zero",
        transform=ax.transAxes,
        fontsize=9,
        color="#555555",
        ha="left",
        va="top",
    )
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.2)
    save_figure(fig, svg_path, png_path)


def render_fig6c(rows: Sequence[dict[str, Any]], svg_path: Path, png_path: Path) -> None:
    labels = [format_module_display_label(str(row["module_id"]), index=index) for index, row in enumerate(rows, start=1)]
    observed = [safe_float(row.get("observed_score")) for row in rows]
    null_mean = [safe_float(row.get("null_mean")) for row in rows]
    null_p95 = [safe_float(row.get("null_p95")) for row in rows]
    x = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.bar(x - 0.18, null_mean, width=0.36, color="#D9D9D9", label="Null mean")
    ax.scatter(x + 0.18, observed, color="#4C78A8", s=80, label="Observed")
    for xpos, p95 in zip(x, null_p95, strict=True):
        ax.plot([xpos - 0.38, xpos - 0.02], [p95, p95], color="#666666", linewidth=2)
    ax.set_ylim(0, 1.05)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("Coherence score")
    ax.set_title("C. GO coherence benchmarking")
    above_p95 = sum(1 for row in rows if safe_float(row.get("observed_score")) > safe_float(row.get("null_p95")))
    fdr_hits = sum(1 for row in rows if safe_float(row.get("fdr")) < 0.1)
    ax.text(
        0.02,
        0.96,
        f"{above_p95}/{len(rows)} above null p95; none FDR < 0.1" if fdr_hits == 0 else f"{above_p95}/{len(rows)} above null p95; {fdr_hits} FDR < 0.1",
        transform=ax.transAxes,
        fontsize=9,
        color="#4B5563",
        ha="left",
        va="top",
        bbox={"boxstyle": "round,pad=0.24", "facecolor": "#FFFFFF", "edgecolor": "#CBD5E1", "alpha": 0.9},
    )
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.2)
    save_figure(fig, svg_path, png_path)


def format_module_display_label(module_id: str, *, index: int) -> str:
    if module_id == "flagship_obesity":
        return "Obesity"
    if module_id.startswith("top_prioritized_"):
        return f"Top {index}"
    if module_id.startswith("conserved_"):
        return f"Conserved {index}"
    if module_id.startswith("rewired_"):
        return f"Rewired {index}"
    return module_id[:18]


def format_evidence_card_metric(metric: str) -> str:
    labels = {
        "lead_lncRNA": "Lead lncRNA",
        "displayed_targets": "Displayed targets",
        "high_affinity_edges": "High-affinity edges",
        "binding_affinity_range": "Binding-affinity range",
        "conservation_rewiring_class": "Conservation / rewiring class",
        "epigenomic_class": "Epigenomic context",
        "literature_backed_targets": "Literature-backed targets",
        "best_expression_context": "Best PCG expression context",
        "functional_coherence": "GO coherence benchmarking",
    }
    return labels.get(metric, metric.replace("_", " "))


def format_evidence_card_value(metric: str, value: str) -> str:
    if metric == "epigenomic_class":
        return value.replace("_", "-")
    if metric == "best_expression_context":
        return value.replace(":", ": ", 1).replace("_", " ")
    return value


def render_fig6d(rows: Sequence[dict[str, Any]], svg_path: Path, png_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9.4, 5.4))
    ax.axis("off")
    ax.set_title("D. Obesity flagship candidate evidence card", loc="left", fontsize=14, fontweight="bold")
    y = 0.91
    for index, row in enumerate(rows):
        metric = str(row.get("metric") or "")
        value = format_evidence_card_value(metric, str(row.get("value") or "NA"))
        if index % 2 == 0:
            ax.add_patch(
                plt.Rectangle((0.01, y - 0.052), 0.98, 0.072, color="#F7FAFC", ec="none", zorder=0)
            )
        ax.text(0.03, y, format_evidence_card_metric(metric), fontsize=9.5, fontweight="bold", va="top")
        ax.text(0.50, y, value, fontsize=9.5, va="top")
        y -= 0.085
    ax.text(
        0.02,
        0.03,
        "Benchmarking context only: candidate prioritization, not experimentally confirmed regulation or causal evidence.",
        fontsize=9,
        color="#555555",
    )
    save_figure(fig, svg_path, png_path)


def _select_conservation_row(rows: Sequence[dict[str, Any]], conservation_count: int = 4) -> dict[str, Any]:
    selected = next((row for row in rows if safe_int(row.get("conservation_count")) == conservation_count), None)
    if selected is not None:
        return selected
    return max(rows, key=lambda row: safe_int(row.get("conservation_count")), default={})


def _format_int_value(value: Any) -> str:
    return str(int(round(safe_float(value))))


def _format_decimal_value(value: Any, digits: int = 1) -> str:
    return f"{safe_float(value):.{digits}f}"


def _metric_value(rows: Sequence[dict[str, Any]], metric: str) -> str:
    row = next((candidate for candidate in rows if candidate.get("metric") == metric), {})
    return str(row.get("value") or "0")


def build_fig3_null_calibration_rows(
    null_count_rows: Sequence[dict[str, Any]],
    strict_null_count_rows: Sequence[dict[str, Any]] | None = None,
    marmoset_downsampling_rows: Sequence[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    four_species = _select_conservation_row(null_count_rows, conservation_count=4)
    strict_four_species = _select_conservation_row(strict_null_count_rows or [], conservation_count=4)
    marmoset_four_species = _select_conservation_row(marmoset_downsampling_rows or [], conservation_count=4)
    observed = safe_float(four_species.get("observed_edge_count"))
    null_mean = safe_float(four_species.get("null_mean_edge_count"))
    null_p95 = safe_float(four_species.get("null_p95_edge_count"))
    strict_p95 = safe_float(strict_four_species.get("null_p95_edge_count"))
    downsampled_median = safe_float(marmoset_four_species.get("observed_median_edge_count"))
    downsampled_p05 = safe_float(marmoset_four_species.get("observed_p05_edge_count"))
    downsampled_p95 = safe_float(marmoset_four_species.get("observed_p95_edge_count"))
    downsampled_null_p95 = safe_float(marmoset_four_species.get("null_p95_edge_count"))
    null_iterations = safe_int(four_species.get("null_iterations"))
    downsampled_iterations = safe_int(marmoset_four_species.get("null_iterations"))

    return [
        {
            "section": "main_four_species_calibration",
            "metric": "observed_four_species_shared_edges",
            "label": "Observed four-species shared core-pair edges",
            "value": _format_int_value(observed),
            "detail": "all orthology-mappable edges; no BA cutoff",
        },
        {
            "section": "main_four_species_calibration",
            "metric": "target_permutation_null_mean",
            "label": "Target-permutation null mean",
            "value": _format_decimal_value(null_mean),
            "detail": f"{null_iterations:,} iterations" if null_iterations else "target-permutation null",
        },
        {
            "section": "main_four_species_calibration",
            "metric": "target_permutation_null_p95",
            "label": "Target-permutation p95",
            "value": _format_int_value(null_p95),
            "detail": "target-permutation null p95",
        },
        {
            "section": "main_four_species_calibration",
            "metric": "degree_bin_matched_p95",
            "label": "Degree-bin p95",
            "value": _format_int_value(strict_p95),
            "detail": "degree-bin matched target-permutation p95",
        },
        {
            "section": "marmoset_downsampling",
            "metric": "marmoset_downsampling_observed_median",
            "label": "Observed median",
            "value": _format_int_value(downsampled_median),
            "detail": f"{downsampled_iterations:,} random draws" if downsampled_iterations else "marmoset-edge-count downsampling",
        },
        {
            "section": "marmoset_downsampling",
            "metric": "marmoset_downsampling_observed_p05_p95",
            "label": "Observed p05-p95",
            "value": f"{_format_int_value(downsampled_p05)}-{_format_int_value(downsampled_p95)}",
            "detail": "human, chimpanzee, and macaque downsampled to marmoset edge count",
        },
        {
            "section": "marmoset_downsampling",
            "metric": "marmoset_downsampling_null_p95",
            "label": "Matched target-permutation null p95",
            "value": _format_int_value(downsampled_null_p95),
            "detail": "matched target-permutation null after downsampling",
        },
    ]


def render_fig3e(rows: Sequence[dict[str, Any]], svg_path: Path, png_path: Path) -> None:
    observed = safe_float(_metric_value(rows, "observed_four_species_shared_edges"))
    null_mean = safe_float(_metric_value(rows, "target_permutation_null_mean"))
    target_p95 = safe_float(_metric_value(rows, "target_permutation_null_p95"))
    degree_p95 = safe_float(_metric_value(rows, "degree_bin_matched_p95"))
    downsampled_median = safe_float(_metric_value(rows, "marmoset_downsampling_observed_median"))
    downsampled_range = _metric_value(rows, "marmoset_downsampling_observed_p05_p95")
    downsampled_p05, downsampled_p95 = [
        safe_float(value) for value in downsampled_range.split("-", 1)
    ] if "-" in downsampled_range else (downsampled_median, downsampled_median)
    downsampled_null_p95 = safe_float(_metric_value(rows, "marmoset_downsampling_null_p95"))

    fig, (ax_main, ax_downsampled) = plt.subplots(
        1,
        2,
        figsize=(11.4, 3.2),
        gridspec_kw={"width_ratios": [1.45, 1.0]},
    )
    main_labels = ["Null mean", "Target p95", "Degree-bin p95", "Observed"]
    main_values = [null_mean, target_p95, degree_p95, observed]
    main_colors = ["#D9D9D9", "#A6BDD7", "#74A9CF", "#D62728"]
    x_main = np.arange(len(main_values))
    ax_main.bar(x_main, main_values, color=main_colors, edgecolor="#4A5568", linewidth=0.8)
    ax_main.set_yscale("log")
    ax_main.set_ylabel("Candidate core-pair edges (log scale)")
    ax_main.set_xticks(x_main)
    ax_main.set_xticklabels(main_labels, rotation=18, ha="right")
    ax_main.set_title("Main four-species calibration", loc="left", fontsize=12, fontweight="bold")
    ax_main.text(
        0.02,
        0.93,
        f"Observed = {int(observed):,}; null mean = {null_mean:.1f}\n"
        f"Target-permutation p95 = {int(target_p95)}; Degree-bin p95 = {int(degree_p95)}",
        transform=ax_main.transAxes,
        fontsize=9,
        va="top",
        bbox={"facecolor": "white", "edgecolor": "#CBD5E1", "boxstyle": "round,pad=0.35"},
    )
    for xpos, value in zip(x_main, main_values, strict=True):
        label = f"{int(value):,}" if value >= 1000 else f"{value:.1f}" if value != int(value) else f"{int(value)}"
        ax_main.text(xpos, value * 1.12, label, ha="center", va="bottom", fontsize=8)
    ax_main.grid(axis="y", alpha=0.2)

    downsampled_labels = ["Null p95", "Observed median"]
    downsampled_values = [downsampled_null_p95, downsampled_median]
    x_downsampled = np.arange(len(downsampled_values))
    ax_downsampled.bar(
        x_downsampled,
        downsampled_values,
        color=["#A6BDD7", "#D62728"],
        edgecolor="#4A5568",
        linewidth=0.8,
    )
    ax_downsampled.errorbar(
        [1],
        [downsampled_median],
        yerr=[[downsampled_median - downsampled_p05], [downsampled_p95 - downsampled_median]],
        fmt="none",
        ecolor="#2D3748",
        elinewidth=1.4,
        capsize=4,
        zorder=3,
    )
    ax_downsampled.set_yscale("log")
    ax_downsampled.set_ylabel("Candidate core-pair edges (log scale)")
    ax_downsampled.set_xticks(x_downsampled)
    ax_downsampled.set_xticklabels(downsampled_labels, rotation=12, ha="right")
    ax_downsampled.set_title("Marmoset downsampling", loc="left", fontsize=12, fontweight="bold")
    ax_downsampled.text(
        0.04,
        0.93,
        f"Observed median = {int(downsampled_median)}\n"
        f"p05-p95 {int(downsampled_p05)}-{int(downsampled_p95)}; null p95 = {int(downsampled_null_p95)}",
        transform=ax_downsampled.transAxes,
        fontsize=9,
        va="top",
        bbox={"facecolor": "white", "edgecolor": "#CBD5E1", "boxstyle": "round,pad=0.35"},
    )
    for xpos, value in zip(x_downsampled, downsampled_values, strict=True):
        ax_downsampled.text(xpos, value * 1.15, f"{int(value)}", ha="center", va="bottom", fontsize=8)
    ax_downsampled.grid(axis="y", alpha=0.2)
    fig.tight_layout(w_pad=2.0)
    save_figure(fig, svg_path, png_path)


def build_cell_genomics_manifest_rows(
    *,
    repo_root: Path,
    generated_at: str,
    source_commit: str,
    panel_outputs: dict[str, Sequence[Path]],
    panel_inputs: dict[str, Sequence[Path]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for panel_id, outputs in panel_outputs.items():
        for output in outputs:
            rows.append(
                {
                    "figure_panel": panel_id,
                    "source_table": ";".join(display_path(path, repo_root) for path in panel_inputs.get(panel_id, [])),
                    "script": display_path(SCRIPT_PATH, repo_root),
                    "input_files": ";".join(display_path(path, repo_root) for path in panel_inputs.get(panel_id, [])),
                    "external_data_version": json.dumps(DEFAULT_EXTERNAL_DATA_VERSIONS, ensure_ascii=False, sort_keys=True),
                    "output_file": display_path(output, repo_root),
                    "commit_sha": source_commit,
                    "generated_at": generated_at,
                }
            )
    return rows


def build_external_data_manifest_rows(
    *,
    repo_root: Path,
    out_dir: Path,
    generated_at: str,
) -> list[dict[str, Any]]:
    external_dir = out_dir / "external"
    processed_inputs = {
        "ENCODE_RNA_seq": external_dir / "cellgenomics_expression_support.tsv",
        "GTEx_v8": external_dir / "cellgenomics_expression_support.tsv",
        "GO_functional_terms": external_dir / "cellgenomics_functional_terms.tsv",
    }
    rows: list[dict[str, Any]] = []
    for source_name, payload in DEFAULT_EXTERNAL_DATA_VERSIONS.items():
        processed_input = processed_inputs[source_name]
        rows.append(
            {
                "source_name": source_name,
                "version": payload["version"],
                "url": payload["url"],
                "license_or_terms": payload["license_or_terms"],
                "processed_input": display_path(processed_input, repo_root),
                "processed_input_present": processed_input.exists(),
                "download_or_access_date": generated_at[:10],
                "notes": "Large public matrices are represented by compact processed TSV inputs for this package.",
            }
        )
    return rows


def write_package(
    *,
    repo_root: Path,
    out_dir: Path,
    generated_at: str,
    source_commit: str,
    min_tpm: float,
) -> list[Path]:
    fig5_dir = out_dir / "fig5"
    fig3_dir = out_dir / "fig3"
    fig6_dir = out_dir / "fig6"
    tables_dir = out_dir / "tables"
    supp_dir = out_dir / "supplementary"
    external_dir = out_dir / "external"

    manifest_rows = read_tsv_rows(fig5_dir / "fig5D_case_manifest.tsv")
    if not manifest_rows:
        raise FileNotFoundError("Missing paper_figures/fig5/fig5D_case_manifest.tsv")
    flagship_manifest = manifest_rows[0]
    case_nodes = read_tsv_rows(fig5_dir / "fig5D_case_nodes.tsv")
    case_edges = read_tsv_rows(fig5_dir / "fig5D_case_edges.tsv")
    ranking_rows = read_tsv_rows(fig5_dir / "fig5B_ranking_matrix.tsv")
    trait_prioritization_rows = read_tsv_rows(tables_dir / "table4_trait_prioritization.tsv")
    trait_support_rows = read_tsv_rows(tables_dir / "supp_table1_trait_literature_support.tsv")
    null_count_rows = read_tsv_rows(supp_dir / "suppfig7B_null_counts.tsv")
    strict_null_count_rows = read_tsv_rows(supp_dir / "suppfig7D_degree_null_counts.tsv")
    marmoset_downsampling_rows = read_tsv_rows(supp_dir / "suppfig7E_marmoset_downsampling.tsv")
    expression_rows = read_tsv_rows(external_dir / "cellgenomics_expression_support.tsv")
    functional_terms = read_tsv_rows(external_dir / "cellgenomics_functional_terms.tsv")
    null_functional_sets = read_tsv_rows(external_dir / "cellgenomics_functional_null_sets.tsv")
    alias_rows = read_tsv_rows(external_dir / "cellgenomics_expression_aliases.tsv")
    edge_rows = read_tsv_rows(out_dir / "shared/edge_corepair_presence.tsv")
    if not alias_rows:
        alias_rows = build_default_alias_rows(case_nodes, flagship_manifest)

    target_symbols = _case_target_symbols(case_nodes)
    expression_support_rows = build_expression_support_rows(
        case_nodes,
        expression_rows=expression_rows,
        alias_rows=alias_rows,
        min_tpm=min_tpm,
        contexts=None,
        flagship_manifest=flagship_manifest,
    )
    expression_summary_rows = build_expression_summary_rows(expression_support_rows)

    module_gene_sets = build_atlas_module_gene_sets(
        ranking_rows=ranking_rows,
        trait_prioritization_rows=trait_prioritization_rows,
        case_nodes=case_nodes,
        edge_rows=edge_rows,
    )
    if not module_gene_sets:
        module_gene_sets = [{"module_id": "flagship_obesity", "module_group": "obesity_flagship", "genes": target_symbols}]
    parsed_null_sets: list[dict[str, Any]] = []
    for row in null_functional_sets:
        parsed_null_sets.append(
            {
                "module_id": row.get("module_id") or "flagship_obesity",
                "genes": [gene for gene in str(row.get("genes") or "").split(";") if gene],
                "matching_rule": row.get("matching_rule") or "processed_input",
            }
        )
    generated_null_sets = build_annotation_matched_null_gene_sets(
        module_gene_sets,
        edge_rows=edge_rows,
        annotation_rows=functional_terms,
        iterations=100,
        seed=42,
    )
    existing_null_modules = {str(row.get("module_id") or "") for row in parsed_null_sets}
    parsed_null_sets.extend(
        row for row in generated_null_sets if str(row.get("module_id") or "") not in existing_null_modules
    )
    modules_with_nulls = {str(row.get("module_id") or "") for row in parsed_null_sets}
    for module_set in module_gene_sets:
        module_id = str(module_set.get("module_id") or "")
        if module_id and module_id not in modules_with_nulls:
            genes = _parse_gene_list(module_set.get("genes"))
            parsed_null_sets.extend(
                {
                    "module_id": module_id,
                    "genes": row["genes"],
                    "matching_rule": "fallback_rotated_or_reversed_target_program",
                }
                for row in _default_null_gene_sets(genes)
            )
    functional_rows = build_functional_coherence_rows(
        module_gene_sets,
        annotation_rows=functional_terms,
        null_gene_sets=parsed_null_sets,
    )
    known_rows = build_known_evidence_rows(flagship_manifest, trait_support_rows, null_count_rows)
    atlas_rows = build_atlas_wide_evidence_rows(
        ranking_rows=ranking_rows,
        trait_prioritization_rows=trait_prioritization_rows,
        flagship_manifest=flagship_manifest,
        null_count_rows=null_count_rows,
        strict_null_count_rows=strict_null_count_rows,
    )
    fig3_null_rows = build_fig3_null_calibration_rows(
        null_count_rows,
        strict_null_count_rows=strict_null_count_rows,
        marmoset_downsampling_rows=marmoset_downsampling_rows,
    )
    evidence_card_rows = build_flagship_evidence_card_rows(
        flagship_manifest,
        expression_summary_rows,
        functional_rows,
        known_rows,
    )
    benchmark_rows = build_known_evidence_benchmark_rows(
        atlas_rows=atlas_rows,
        expression_summary_rows=expression_summary_rows,
        functional_rows=functional_rows,
    )

    fig6a_base = fig6_dir / FIG6_OUTPUTS["Figure6A"]
    fig6b_base = fig6_dir / FIG6_OUTPUTS["Figure6B"]
    fig6c_base = fig6_dir / FIG6_OUTPUTS["Figure6C"]
    fig6d_base = fig6_dir / FIG6_OUTPUTS["Figure6D"]

    fig6a_tsv = fig6a_base.with_suffix(".tsv")
    fig6b_tsv = fig6b_base.with_suffix(".tsv")
    fig6c_tsv = fig6c_base.with_suffix(".tsv")
    fig6d_tsv = fig6d_base.with_suffix(".tsv")

    write_tsv(
        fig6a_tsv,
        atlas_rows,
        [
            "evidence_scope",
            "module_count",
            "median_target_count",
            "median_high_affinity_edges",
            "conserved_module_fraction",
            "rewired_module_fraction",
            "observed_value",
            "null_or_background_value",
            "null_iterations",
            "evidence_label",
            "interpretation",
        ],
    )
    write_tsv(
        fig6b_tsv,
        expression_summary_rows,
        [
            "source",
            "context",
            "tested_node_count",
            "mappable_node_count",
            "mapping_rate",
            "expression_supported_node_count",
            "expression_supported_fraction",
            "analysis_mode",
            "analysis_scope",
        ],
    )
    write_tsv(
        fig6c_tsv,
        functional_rows,
        [
            "module_id",
            "tested_gene_count",
            "observed_score",
            "null_mean",
            "null_p95",
            "empirical_percentile",
            "empirical_p_value",
            "fdr",
            "best_term_id",
            "best_term_name",
            "best_term_gene_count",
        ],
    )
    write_tsv(fig6d_tsv, evidence_card_rows, ["metric", "value", "source"])

    supp_expression_tsv = tables_dir / "supp_data_expression_support.tsv"
    supp_functional_tsv = tables_dir / "supp_data_functional_coherence.tsv"
    supp_flagship_tsv = tables_dir / "supp_data_flagship_module.tsv"
    benchmark_tsv = tables_dir / "table7_known_evidence_benchmark.tsv"
    write_tsv(
        supp_expression_tsv,
        expression_support_rows,
        [
            "core_id",
            "node_type",
            "display_label",
            "source",
            "context",
            "expression_tpm",
            "expression_supported",
            "mapping_status",
        ],
    )
    write_tsv(
        supp_functional_tsv,
        functional_rows,
        [
            "module_id",
            "tested_gene_count",
            "observed_score",
            "null_mean",
            "null_p95",
            "empirical_percentile",
            "empirical_p_value",
            "fdr",
            "best_term_id",
            "best_term_name",
            "best_term_gene_count",
        ],
    )
    write_tsv(
        benchmark_tsv,
        benchmark_rows,
        [
            "benchmark_layer",
            "evidence_scope",
            "observed_value",
            "background_value",
            "module_count",
            "interpretation",
        ],
    )
    write_tsv(
        supp_flagship_tsv,
        [flagship_manifest],
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

    render_fig6a(atlas_rows, fig6a_base.with_suffix(".svg"), fig6a_base.with_suffix(".png"))
    render_fig6b(expression_summary_rows, fig6b_base.with_suffix(".svg"), fig6b_base.with_suffix(".png"))
    render_fig6c(functional_rows, fig6c_base.with_suffix(".svg"), fig6c_base.with_suffix(".png"))
    render_fig6d(evidence_card_rows, fig6d_base.with_suffix(".svg"), fig6d_base.with_suffix(".png"))

    fig3e_base = fig3_dir / "fig3E_null_calibration"
    fig3e_tsv = fig3e_base.with_suffix(".tsv")
    write_tsv(
        fig3e_tsv,
        fig3_null_rows,
        [
            "section",
            "metric",
            "label",
            "value",
            "detail",
        ],
    )
    render_fig3e(fig3_null_rows, fig3e_base.with_suffix(".svg"), fig3e_base.with_suffix(".png"))

    panel_inputs = {
        "Figure6A": [
            fig5_dir / "fig5B_ranking_matrix.tsv",
            tables_dir / "table4_trait_prioritization.tsv",
            fig5_dir / "fig5D_case_manifest.tsv",
            tables_dir / "supp_table1_trait_literature_support.tsv",
            supp_dir / "suppfig7B_null_counts.tsv",
        ],
        "Figure6B": [
            external_dir / "cellgenomics_expression_support.tsv",
            external_dir / "cellgenomics_expression_aliases.tsv",
        ],
        "Figure6C": [
            fig5_dir / "fig5B_ranking_matrix.tsv",
            tables_dir / "table4_trait_prioritization.tsv",
            fig5_dir / "fig5D_case_nodes.tsv",
            out_dir / "shared/edge_corepair_presence.tsv",
            external_dir / "cellgenomics_functional_terms.tsv",
            external_dir / "cellgenomics_functional_null_sets.tsv",
        ],
        "Figure6D": [
            fig5_dir / "fig5D_case_manifest.tsv",
            fig6a_tsv,
            fig6b_tsv,
            fig6c_tsv,
        ],
        "Figure3E": [
            supp_dir / "suppfig7B_null_counts.tsv",
            supp_dir / "suppfig7D_degree_null_counts.tsv",
            supp_dir / "suppfig7E_marmoset_downsampling.tsv",
        ],
        "Table7": [
            fig6a_tsv,
            fig6b_tsv,
            fig6c_tsv,
        ],
        "SupplementaryData": [
            fig6b_tsv,
            fig6c_tsv,
            fig5_dir / "fig5D_case_manifest.tsv",
        ],
    }
    panel_outputs = {
        "Figure6A": [fig6a_tsv, fig6a_base.with_suffix(".svg"), fig6a_base.with_suffix(".png")],
        "Figure6B": [fig6b_tsv, fig6b_base.with_suffix(".svg"), fig6b_base.with_suffix(".png")],
        "Figure6C": [fig6c_tsv, fig6c_base.with_suffix(".svg"), fig6c_base.with_suffix(".png")],
        "Figure6D": [fig6d_tsv, fig6d_base.with_suffix(".svg"), fig6d_base.with_suffix(".png")],
        "Figure3E": [fig3e_tsv, fig3e_base.with_suffix(".svg"), fig3e_base.with_suffix(".png")],
        "Table7": [benchmark_tsv],
        "SupplementaryData": [supp_expression_tsv, supp_functional_tsv, supp_flagship_tsv],
    }

    metadata_paths: list[Path] = []
    metadata_payloads = {
        "Figure6A": panel_metadata(
            panel_id="Figure6A",
            title="Atlas-wide benchmarking and robustness summary",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=panel_inputs["Figure6A"],
            output_paths=panel_outputs["Figure6A"],
            generation_parameters={"analysis_mode": "atlas_wide_module_evidence_summary"},
        ),
        "Figure6B": panel_metadata(
            panel_id="Figure6B",
            title="PCG target-program expression context",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=panel_inputs["Figure6B"],
            output_paths=panel_outputs["Figure6B"],
            generation_parameters={"analysis_mode": "pcg_target_program_mappable_subset", "min_tpm": min_tpm},
            notes=[
                "Unmapped or ambiguous lncRNA IDs are reported as missing or ambiguous, not as zero expression.",
                "Figure 6B summarizes PCG target-program expression context rather than direct lncRNA–PCG co-expression.",
                "Expression matrices are expected as compact processed TSV inputs for reviewer reproducibility.",
            ],
        ),
        "Figure6C": panel_metadata(
            panel_id="Figure6C",
            title="GO coherence benchmarking",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=panel_inputs["Figure6C"],
            output_paths=panel_outputs["Figure6C"],
            generation_parameters={"analysis_mode": "multi_module_matched_null_gene_set_coherence"},
        ),
        "Figure6D": panel_metadata(
            panel_id="Figure6D",
            title="Obesity flagship candidate evidence card",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=panel_inputs["Figure6D"],
            output_paths=panel_outputs["Figure6D"],
            generation_parameters={"analysis_mode": "evidence_convergence_card"},
            notes=["This evidence card supports prioritization only and does not claim experimentally confirmed regulation."],
        ),
        "Figure3E": panel_metadata(
            panel_id="Figure3E",
            title="Observed-vs-null edge conservation calibration and marmoset downsampling sensitivity",
            repo_root=repo_root,
            generated_at=generated_at,
            source_commit=source_commit,
            input_paths=panel_inputs["Figure3E"],
            output_paths=panel_outputs["Figure3E"],
            generation_parameters={"analysis_mode": "main_text_null_calibration_summary"},
            notes=[
                "Figure 3E summarizes the main four-species target-permutation calibration, degree-bin matched p95, and marmoset-edge-count downsampling sensitivity.",
                "Full BA sensitivity and pairwise null details remain in Supplementary Figure 7.",
            ],
        ),
    }
    for panel_id, payload in metadata_payloads.items():
        output_stem = FIG6_OUTPUTS.get(panel_id, "fig3E_null_calibration")
        metadata_dir = fig3_dir if panel_id == "Figure3E" else fig6_dir
        metadata_path = metadata_dir / f"{output_stem.split('_', 1)[0]}_metadata.json"
        write_json(metadata_path, payload)
        metadata_paths.append(metadata_path)
        panel_outputs[panel_id] = [*panel_outputs[panel_id], metadata_path]

    manifest_tsv = out_dir / "cell_genomics_manifest.tsv"
    manifest_output_rows = build_cell_genomics_manifest_rows(
        repo_root=repo_root,
        generated_at=generated_at,
        source_commit=source_commit,
        panel_outputs=panel_outputs,
        panel_inputs=panel_inputs,
    )
    write_tsv(
        manifest_tsv,
        manifest_output_rows,
        [
            "figure_panel",
            "source_table",
            "script",
            "input_files",
            "external_data_version",
            "output_file",
            "commit_sha",
            "generated_at",
        ],
    )

    external_manifest_tsv = out_dir / "cell_genomics_external_data_manifest.tsv"
    write_tsv(
        external_manifest_tsv,
        build_external_data_manifest_rows(
            repo_root=repo_root,
            out_dir=out_dir,
            generated_at=generated_at,
        ),
        [
            "source_name",
            "version",
            "url",
            "license_or_terms",
            "processed_input",
            "processed_input_present",
            "download_or_access_date",
            "notes",
        ],
    )

    written = [
        fig6a_tsv,
        fig6b_tsv,
        fig6c_tsv,
        fig6d_tsv,
        *metadata_paths,
        *[path for outputs in panel_outputs.values() for path in outputs if path.suffix in {".svg", ".png"}],
        supp_expression_tsv,
        supp_functional_tsv,
        supp_flagship_tsv,
        benchmark_tsv,
        fig3e_tsv,
        manifest_tsv,
        external_manifest_tsv,
    ]
    return sorted(set(written))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Repository root")
    parser.add_argument("--out-dir", default="paper_figures", help="Paper figure output directory")
    parser.add_argument("--generated-at", default=None, help="Fixed UTC timestamp for metadata")
    parser.add_argument("--source-commit", default="HEAD", help="Git ref or 40-char SHA for provenance")
    parser.add_argument("--min-tpm", type=float, default=1.0, help="Expression support threshold")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = repo_root / out_dir
    out_dir = out_dir.resolve()
    generated_at = args.generated_at or utc_now_iso()
    source_commit = git_commit_sha(repo_root, str(args.source_commit or "HEAD"))
    written = write_package(
        repo_root=repo_root,
        out_dir=out_dir,
        generated_at=generated_at,
        source_commit=source_commit,
        min_tpm=float(args.min_tpm),
    )
    for path in written:
        print(f"Wrote: {display_path(path, repo_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
