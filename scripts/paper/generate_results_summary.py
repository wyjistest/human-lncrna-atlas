#!/usr/bin/env python3
"""Generate a paper-facing results summary from frozen figure assets."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AssetPaths:
    repo_root: Path
    snapshot_json: Path
    fig1b_counts_tsv: Path
    fig2a_summary_tsv: Path
    fig2b_hubs_tsv: Path
    fig2c_centrality_tsv: Path
    fig2d_manifest_tsv: Path
    fig3a_upset_tsv: Path
    fig3c_pairwise_tsv: Path
    fig3d_manifest_tsv: Path
    fig4a_tsv: Path
    fig4b_tsv: Path
    fig4c_tsv: Path
    fig4d_manifest_tsv: Path
    fig5a_nodes_tsv: Path
    fig5a_edges_tsv: Path
    fig5b_tsv: Path
    fig5c_tsv: Path
    fig5d_manifest_tsv: Path
    table2_tsv: Path
    table4_tsv: Path


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def format_int(value: Any) -> str:
    return f"{safe_int(value):,}"


def format_pct(value: Any) -> str:
    return f"{safe_float(value) * 100:.1f}%"


def short_commit(value: str) -> str:
    return value[:7] if value else "unknown"


def display_path(paths: AssetPaths, path: Path) -> str:
    try:
        return path.relative_to(paths.repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def require_rows(title: str, rows: list[dict[str, str]], path: Path) -> list[str]:
    if rows:
        return []
    return [f"### Missing: `{path}`", ""]


def summarize_fig1(paths: AssetPaths) -> str:
    snapshot = read_json(paths.snapshot_json)
    fig1b_rows = read_tsv_rows(paths.fig1b_counts_tsv)

    lines = ["## Figure 1 Draft Assets", ""]
    if fig1b_rows:
        lines.extend([
            "### Figure 1B ortholog mapping summary",
            "",
            f"Source: `{display_path(paths, paths.fig1b_counts_tsv)}`",
            "",
        ])
        for row in fig1b_rows:
            lines.append(
                "- "
                f"{row.get('species_name')}: `{format_int(row.get('lncrna_core_count'))}` lncRNA core groups, "
                f"`{format_int(row.get('protein_coding_core_count'))}` protein-coding core groups, "
                f"`{format_int(row.get('comparable_core_group_count'))}` comparable shared core groups"
            )
        lines.append("")
    else:
        lines.extend(require_rows("Figure 1B", fig1b_rows, paths.fig1b_counts_tsv))

    lines.extend([
        "### Figure 1A / 1C / 1D narrative anchors",
        "",
        "Source assets:",
        "",
        "- `paper_figures/fig1/fig1A_catalog_gap.*`",
        "- `paper_figures/fig1/fig1C_workflow.*`",
        "- `paper_figures/fig1/fig1D_kpi.*`",
        "",
        "Current draft language:",
        "",
        "- Figure 1A keeps the paper-facing framing that prior trait-associated catalogs nominate `nodes, not edges`",
        "- Figure 1C fixes the workflow to `trait-associated catalogs -> ortholog mapping -> repository-frozen ortholog import snapshot -> triplex-informed inference -> candidate regulatory edges`",
    ])
    if snapshot:
        lines.append(
            "- Figure 1D uses the frozen submission snapshot: "
            f"`{format_int(snapshot.get('species_count'))}` primate species, "
            f"`{format_int(snapshot.get('candidate_relationships'))}` candidate relationships, "
            f"`{format_int(snapshot.get('baseline_experiments'))}` baseline experiments, "
            f"`{format_int(snapshot.get('baseline_peaks'))}` baseline peaks "
            f"(source commit `{short_commit(str(snapshot.get('source_commit') or ''))}`)"
        )
    lines.append("")
    return "\n".join(lines)


def summarize_fig2(paths: AssetPaths) -> str:
    fig2a_rows = read_tsv_rows(paths.fig2a_summary_tsv)
    fig2b_rows = read_tsv_rows(paths.fig2b_hubs_tsv)
    fig2c_rows = read_tsv_rows(paths.fig2c_centrality_tsv)
    fig2d_rows = read_tsv_rows(paths.fig2d_manifest_tsv)

    lines = ["## Figure 2 Draft Assets", ""]
    if fig2a_rows:
        lines.extend(["### Figure 2A-C", "", "Source assets:", "", "- `paper_figures/fig2/fig2A_*`", "- `paper_figures/fig2/fig2B_*`", "- `paper_figures/fig2/fig2C_*`", ""])
        lines.append("Binding-affinity prioritization zone (`BA >= 100`) by species:")
        lines.append("")
        for row in fig2a_rows:
            lines.append(
                "- "
                f"{row.get('species_name')}: `{format_pct(row.get('frac_ge_100'))}` of edges are in the priority zone "
                f"(`{format_int(row.get('n_ge_100'))}` / `{format_int(row.get('total_edges'))}`), main clipped view capped at `{safe_float(row.get('main_plot_ymax')):.0f}`"
            )
        lines.append("")

        if fig2b_rows:
            lines.append("Current hub-alias draft (top 5):")
            lines.append("")
            for row in fig2b_rows[:5]:
                lines.append(
                    "- "
                    f"{row.get('display_label')}: `{format_int(row.get('unique_target_core_count'))}` target core groups, "
                    f"`{format_int(row.get('species_count'))}` species, mean BA `{safe_float(row.get('mean_outgoing_ba')):.2f}`"
                )
            lines.append("")

        if fig2c_rows:
            lines.append("Figure 2C now uses eigenvector centrality (top 5 by centrality):")
            lines.append("")
            for row in fig2c_rows[:5]:
                lines.append(
                    "- "
                    f"{row.get('canonical_symbol')}: out-degree `{format_int(row.get('out_degree'))}`, "
                    f"eigenvector centrality `{safe_float(row.get('eigenvector_centrality')):.3f}`, mean BA `{safe_float(row.get('mean_outgoing_ba')):.2f}`"
                )
            lines.append("")
    else:
        lines.extend(require_rows("Figure 2", fig2a_rows, paths.fig2a_summary_tsv))

    if fig2d_rows:
        lines.extend(["### Figure 2D readable subnetworks", "", f"Source: `{display_path(paths, paths.fig2d_manifest_tsv)}`", "", "Current selected modules:", ""])
        for row in fig2d_rows:
            lines.append(
                "- "
                f"{row.get('module_kind').capitalize()} module: `lncrna_core_id = {row.get('lncrna_core_id')}`, "
                f"`{format_int(row.get('target_count'))}` targets, `{format_int(row.get('node_count'))}` nodes total, "
                f"mean edge BA `{safe_float(row.get('mean_edge_ba')):.6f}`"
            )
        lines.append("")
    return "\n".join(lines)


def summarize_fig3(paths: AssetPaths) -> str:
    fig3a_rows = read_tsv_rows(paths.fig3a_upset_tsv)
    fig3c_rows = read_tsv_rows(paths.fig3c_pairwise_tsv)
    fig3d_rows = read_tsv_rows(paths.fig3d_manifest_tsv)

    lines = ["## Figure 3 Draft Assets", ""]
    if fig3a_rows or fig3c_rows:
        lines.extend(["### Figure 3A-C", "", "Source assets:", "", "- `paper_figures/fig3/fig3A_*`", "- `paper_figures/fig3/fig3B_*`", "- `paper_figures/fig3/fig3C_*`", ""])

        by_label = {row.get("conservation_label"): row for row in fig3a_rows}
        if by_label:
            lines.append(
                "- Conserved-edge strata: `1111` has "
                f"`{format_int(by_label.get('1111', {}).get('count'))}` fully shared edges; `1110` has "
                f"`{format_int(by_label.get('1110', {}).get('count'))}` three-species edges; `1100` has "
                f"`{format_int(by_label.get('1100', {}).get('count'))}` two-species edges"
            )
        pairwise = {(row.get('item_type'), row.get('species_a'), row.get('species_b')): row for row in fig3c_rows}
        human_chimp_node = pairwise.get(("node", "human", "chimp"), {})
        human_chimp_edge = pairwise.get(("edge", "human", "chimp"), {})
        chimp_macaque_node = pairwise.get(("node", "chimp", "macaque"), {})
        chimp_macaque_edge = pairwise.get(("edge", "chimp", "macaque"), {})
        if human_chimp_node and human_chimp_edge:
            lines.append(
                "- Human-chimp pairwise sharing: node Jaccard "
                f"`{safe_float(human_chimp_node.get('jaccard')):.2f}`, edge Jaccard `{safe_float(human_chimp_edge.get('jaccard')):.2f}`"
            )
        if chimp_macaque_node and chimp_macaque_edge:
            lines.append(
                "- Chimp-macaque pairwise sharing: node Jaccard "
                f"`{safe_float(chimp_macaque_node.get('jaccard')):.2f}`, edge Jaccard `{safe_float(chimp_macaque_edge.get('jaccard')):.2f}`"
            )
        lines.append("")

    if fig3d_rows:
        lines.extend(["### Figure 3D conserved vs rewired exemplars", "", f"Source: `{display_path(paths, paths.fig3d_manifest_tsv)}`", "", "Current selected exemplars:", ""])
        for row in fig3d_rows:
            extra = ""
            if row.get("exemplar_kind") == "rewired":
                extra = f", mean pairwise target-set Jaccard `{safe_float(row.get('mean_pairwise_jaccard')):.1f}`"
            lines.append(
                "- "
                f"{row.get('exemplar_kind').capitalize()} module: `lncrna_core_id = {row.get('lncrna_core_id')}`, "
                f"`{format_int(row.get('target_count'))}` displayed targets, `{format_int(row.get('node_count'))}` nodes total, "
                f"mean edge BA `{safe_float(row.get('mean_edge_ba')):.6f}`{extra}"
            )
        lines.append("")
    return "\n".join(lines)


def summarize_fig4(paths: AssetPaths) -> str:
    table2_rows = read_tsv_rows(paths.table2_tsv)
    fig4a_rows = read_tsv_rows(paths.fig4a_tsv)
    fig4b_rows = read_tsv_rows(paths.fig4b_tsv)
    fig4c_rows = read_tsv_rows(paths.fig4c_tsv)
    fig4d_rows = read_tsv_rows(paths.fig4d_manifest_tsv)

    lines = ["## Figure 4 Draft Assets", ""]
    if table2_rows:
        main_text_rows = [row for row in table2_rows if row.get("inventory_group") == "main_text_baseline"]
        extended_rows = [row for row in table2_rows if row.get("inventory_group") == "extended_tracks"]
        main_experiments = sum(safe_int(row.get("experiment_count")) for row in main_text_rows)
        main_peaks = sum(safe_int(row.get("peak_count")) for row in main_text_rows)
        lines.extend([
            "### Table 2 epigenomic inventory",
            "",
            f"Source: `{display_path(paths, paths.table2_tsv)}`",
            "",
            f"- Main-text baseline rows: `{len(main_text_rows)}` marks, `{format_int(main_experiments)}` experiments, `{format_int(main_peaks)}` peaks",
            f"- Extended tracks: `{', '.join(row.get('mark_name', '') for row in extended_rows)}`",
            "",
        ])

    if fig4a_rows:
        observed_rows = [row for row in fig4a_rows if row.get("availability_status") == "observed"]
        observed_rows.sort(key=lambda row: safe_float(row.get("overlap_fraction")), reverse=True)
        lines.extend([
            "### Figure 4A-D",
            "",
            "Source assets:",
            "",
            "- `paper_figures/fig4/fig4A_*`",
            "- `paper_figures/fig4/fig4B_*`",
            "- `paper_figures/fig4/fig4C_*`",
            "- `paper_figures/fig4/fig4D_*`",
            "",
            f"- Figure 4A distinguishes `{len(observed_rows)}` observed mark-by-cell-line combinations from `{sum(row.get('availability_status') == 'NA' for row in fig4a_rows)}` frozen-baseline `NA` combinations",
        ])
        if observed_rows:
            top_row = observed_rows[0]
            lines.append(
                "- Highest overlap fraction in the current draft: "
                f"`{top_row.get('mark_name')}` in `{top_row.get('cell_line')}` with fraction `{safe_float(top_row.get('overlap_fraction')):.3f}` "
                f"(`{format_int(top_row.get('overlapped_regulation_count'))}` overlapped regulations)"
            )

        if fig4b_rows:
            all_human_top = [row for row in fig4b_rows if row.get("cohort") == "all_human_edges"][:3]
            high_affinity_top = [row for row in fig4b_rows if row.get("cohort") == "high_affinity"][:3]
            if all_human_top:
                lines.append(
                    "- Figure 4B top all-edge signatures: "
                    + ", ".join(
                        f"`{row.get('signature_label')}` ({format_pct(row.get('fraction'))})"
                        for row in all_human_top
                    )
                )
            if high_affinity_top:
                lines.append(
                    "- Figure 4B top high-affinity signatures: "
                    + ", ".join(
                        f"`{row.get('signature_label')}` ({format_pct(row.get('fraction'))})"
                        for row in high_affinity_top
                    )
                )

        if fig4c_rows:
            context_counts: dict[str, int] = {}
            for row in fig4c_rows:
                key = str(row.get("context_class") or "other")
                context_counts[key] = context_counts.get(key, 0) + 1
            lines.append(
                "- Figure 4C context counts: "
                + ", ".join(
                    f"`{key}` = `{format_int(value)}`"
                    for key, value in sorted(context_counts.items())
                )
            )

        if fig4d_rows:
            lines.append("- Figure 4D current IGV exemplars:")
            for row in fig4d_rows:
                lines.append(
                    "  - "
                    f"{row.get('exemplar_kind')}: `{row.get('lncrna_name')}` -> `{row.get('target_gene_name')}` in `{row.get('cell_line')}`, "
                    f"BA `{safe_float(row.get('binding_affinity')):.2f}`, signature `{row.get('mark_signature')}`"
                )
        lines.append("")
    return "\n".join(lines)


def summarize_fig5(paths: AssetPaths) -> str:
    fig5a_nodes = read_tsv_rows(paths.fig5a_nodes_tsv)
    fig5a_edges = read_tsv_rows(paths.fig5a_edges_tsv)
    fig5b_rows = read_tsv_rows(paths.fig5b_tsv)
    fig5c_rows = read_tsv_rows(paths.fig5c_tsv)
    fig5d_rows = read_tsv_rows(paths.fig5d_manifest_tsv)
    table4_rows = read_tsv_rows(paths.table4_tsv)

    lines = ["## Figure 5 Draft Assets", ""]
    if fig5a_nodes or fig5b_rows:
        lines.extend([
            "### Figure 5A-D",
            "",
            "Source assets:",
            "",
            "- `paper_figures/fig5/fig5A_*`",
            "- `paper_figures/fig5/fig5B_*`",
            "- `paper_figures/fig5/fig5C_*`",
            "- `paper_figures/fig5/fig5D_*`",
            "- `paper_figures/tables/table4_trait_prioritization.tsv`",
            "",
        ])
        trait_nodes = [row for row in fig5a_nodes if row.get("node_type") == "trait"]
        lnc_nodes = [row for row in fig5a_nodes if row.get("node_type") == "lncrna"]
        if trait_nodes:
            lines.append(
                "- Figure 5A flagship trait: "
                f"`{trait_nodes[0].get('display_label')}` with `{len(fig5a_nodes)}` displayed nodes and `{len(fig5a_edges)}` edges"
            )
        if lnc_nodes:
            lines.append(
                "- Figure 5A top displayed lncRNAs: "
                + ", ".join(
                    f"`{row.get('display_label')}` ({format_int(row.get('value'))} targets)"
                    for row in lnc_nodes[:3]
                )
            )

        if fig5b_rows:
            lines.append(
                "- Figure 5B top ranking candidates: "
                + ", ".join(f"`{row.get('lncrna_name')}`" for row in fig5b_rows[:5])
            )
            lines.append(
                f"- Figure 5B keeps `{sum(row.get('flagship_membership') == 'True' for row in fig5b_rows)}` flagship-member lncRNA inside the top-20 ranking matrix"
            )

        if fig5c_rows:
            unique_traits = []
            seen_traits: set[str] = set()
            for row in fig5c_rows:
                trait_name = str(row.get("trait_name") or "")
                if trait_name and trait_name not in seen_traits:
                    seen_traits.add(trait_name)
                    unique_traits.append(trait_name)
            lines.append(
                "- Figure 5C covers the current cross-trait set: "
                + ", ".join(f"`{trait}`" for trait in unique_traits)
            )

        if fig5d_rows:
            row = fig5d_rows[0]
            lines.append(
                "- Figure 5D flagship case: "
                f"`{row.get('trait_name')}` centered on `{row.get('lncrna_name')}` with "
                f"`{format_int(row.get('candidate_targets'))}` candidate targets, `{format_int(row.get('high_affinity_edges'))}` high-affinity edges, "
                f"BA range `{row.get('ba_range')}`, rewiring label `{row.get('rewiring_label')}`, context `{row.get('epigenomic_support_class')}`"
            )

        if table4_rows:
            lines.append(f"- Table 4 currently reports `{len(table4_rows)}` prioritized trait-centered rows")
        lines.append("")
    return "\n".join(lines)


def build_markdown(paths: AssetPaths) -> str:
    sections: list[str] = [
        "# Results Summary (Paper Assets)",
        "",
        "This summary tracks the current paper-facing draft assets generated by ",
        "`scripts/paper/generate_batch1_figures.py`, `scripts/paper/generate_batch2_figures.py`,",
        "and `scripts/paper/generate_results_summary.py`.",
        "",
        summarize_fig1(paths).rstrip(),
        summarize_fig2(paths).rstrip(),
        summarize_fig3(paths).rstrip(),
        summarize_fig4(paths).rstrip(),
        summarize_fig5(paths).rstrip(),
        "## Notes",
        "",
        "- Regenerate Figure 1-3 paper assets with `python3 scripts/paper/generate_batch1_figures.py`",
        "- Regenerate Figure 4-5 / Table 2 / Table 4 paper assets with `python3 scripts/paper/generate_batch2_figures.py`",
        "- Refresh this summary with `python3 scripts/paper/generate_results_summary.py`",
        "- Freeze semantics for counts, provenance, BA rules, and conservation definitions remain fixed in `docs/paper/submission_snapshot.md`",
        "",
    ]
    return "\n".join(section for section in sections if section is not None).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Repository root (default: current directory)")
    parser.add_argument(
        "--out",
        default="docs/paper/results_summary.md",
        help="Output markdown path (default: docs/paper/results_summary.md)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    out_path = (repo_root / args.out).resolve()

    paths = AssetPaths(
        repo_root=repo_root,
        snapshot_json=repo_root / "paper_figures/shared/frozen_submission_snapshot.json",
        fig1b_counts_tsv=repo_root / "paper_figures/fig1/fig1B_ortholog_counts.tsv",
        fig2a_summary_tsv=repo_root / "paper_figures/fig2/fig2A_summary.tsv",
        fig2b_hubs_tsv=repo_root / "paper_figures/fig2/fig2B_hubs.tsv",
        fig2c_centrality_tsv=repo_root / "paper_figures/fig2/fig2C_centrality.tsv",
        fig2d_manifest_tsv=repo_root / "paper_figures/fig2/fig2D_module_manifest.tsv",
        fig3a_upset_tsv=repo_root / "paper_figures/fig3/fig3A_edge_upset.tsv",
        fig3c_pairwise_tsv=repo_root / "paper_figures/fig3/fig3C_pairwise_sharing.tsv",
        fig3d_manifest_tsv=repo_root / "paper_figures/fig3/fig3D_exemplar_manifest.tsv",
        fig4a_tsv=repo_root / "paper_figures/fig4/fig4A_overlap_summary.tsv",
        fig4b_tsv=repo_root / "paper_figures/fig4/fig4B_mark_signatures.tsv",
        fig4c_tsv=repo_root / "paper_figures/fig4/fig4C_bivalent_contrast.tsv",
        fig4d_manifest_tsv=repo_root / "paper_figures/fig4/fig4D_igv_manifest.tsv",
        fig5a_nodes_tsv=repo_root / "paper_figures/fig5/fig5A_tripartite_nodes.tsv",
        fig5a_edges_tsv=repo_root / "paper_figures/fig5/fig5A_tripartite_edges.tsv",
        fig5b_tsv=repo_root / "paper_figures/fig5/fig5B_ranking_matrix.tsv",
        fig5c_tsv=repo_root / "paper_figures/fig5/fig5C_trait_specificity.tsv",
        fig5d_manifest_tsv=repo_root / "paper_figures/fig5/fig5D_case_manifest.tsv",
        table2_tsv=repo_root / "paper_figures/tables/table2_epigenomic_inventory.tsv",
        table4_tsv=repo_root / "paper_figures/tables/table4_trait_prioritization.tsv",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_markdown(paths), encoding="utf-8")
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
