#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/paper/generate_batch2_figures.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"missing module under test: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("generate_batch2_figures", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GenerateBatch2FiguresTests(unittest.TestCase):
    def test_build_fig4a_rows_distinguishes_na_from_measured_zero(self):
        module = load_module()

        inventory_rows = [
            {"mark_name": "H3K4me3", "cell_line": "A549", "experiment_count": 1, "peak_count": 1200},
            {"mark_name": "H3K27me3", "cell_line": "A549", "experiment_count": 1, "peak_count": 800},
        ]
        overlap_rows = [
            {"mark_name": "H3K4me3", "cell_line": "A549", "overlapped_regulation_count": 25},
        ]

        rows = module.build_fig4a_rows(
            inventory_rows=inventory_rows,
            overlap_rows=overlap_rows,
            total_candidate_regulations=100,
            marks=["H3K4me3", "H3K27me3", "DNase-HS"],
            cell_lines=["A549"],
        )

        by_key = {(row["mark_name"], row["cell_line"]): row for row in rows}
        self.assertEqual(by_key[("H3K4me3", "A549")]["availability_status"], "observed")
        self.assertEqual(by_key[("H3K4me3", "A549")]["overlapped_regulation_count"], 25)
        self.assertEqual(by_key[("H3K4me3", "A549")]["overlap_fraction"], 0.25)

        self.assertEqual(by_key[("H3K27me3", "A549")]["availability_status"], "observed")
        self.assertEqual(by_key[("H3K27me3", "A549")]["overlapped_regulation_count"], 0)
        self.assertEqual(by_key[("H3K27me3", "A549")]["overlap_fraction"], 0.0)

        self.assertEqual(by_key[("DNase-HS", "A549")]["availability_status"], "NA")
        self.assertEqual(by_key[("DNase-HS", "A549")]["experiment_count"], 0)
        self.assertEqual(by_key[("DNase-HS", "A549")]["peak_count"], 0)

    def test_classify_fig4_context_requires_same_cell_line_for_bivalent(self):
        module = load_module()

        self.assertEqual(
            module.classify_fig4_context({"H3K4me3", "H3K27me3"}),
            "bivalent_like",
        )
        self.assertEqual(
            module.classify_fig4_context({"H3K4me3", "H3K27ac"}),
            "active_like_non_bivalent",
        )
        self.assertEqual(
            module.classify_fig4_context({"DNase-HS"}),
            "other",
        )

    def test_build_fig4c_rows_groups_regulation_by_cell_line(self):
        module = load_module()

        overlap_rows = [
            {"regulation_id": 1, "cell_line": "A549", "mark_name": "H3K4me3", "binding_affinity": 180.0},
            {"regulation_id": 1, "cell_line": "A549", "mark_name": "H3K27me3", "binding_affinity": 180.0},
            {"regulation_id": 1, "cell_line": "GM12878", "mark_name": "H3K4me3", "binding_affinity": 180.0},
            {"regulation_id": 2, "cell_line": "A549", "mark_name": "H3K4me1", "binding_affinity": 130.0},
            {"regulation_id": 2, "cell_line": "A549", "mark_name": "H3K27ac", "binding_affinity": 130.0},
        ]

        rows = module.build_fig4c_rows(overlap_rows)
        by_key = {(row["regulation_id"], row["cell_line"]): row for row in rows}

        self.assertEqual(by_key[(1, "A549")]["context_class"], "bivalent_like")
        self.assertEqual(by_key[(1, "GM12878")]["context_class"], "active_like_non_bivalent")
        self.assertEqual(by_key[(2, "A549")]["context_class"], "active_like_non_bivalent")

    def test_build_trait_summary_rows_applies_filter_and_sort_order(self):
        module = load_module()

        network_rows = [
            {"trait_id": 1, "trait_name": "Trait A", "lncrna_gene_id": 10, "target_gene_id": 101, "binding_affinity": 120.0},
            {"trait_id": 1, "trait_name": "Trait A", "lncrna_gene_id": 10, "target_gene_id": 102, "binding_affinity": 140.0},
            {"trait_id": 1, "trait_name": "Trait A", "lncrna_gene_id": 11, "target_gene_id": 103, "binding_affinity": 160.0},
            {"trait_id": 1, "trait_name": "Trait A", "lncrna_gene_id": 12, "target_gene_id": 104, "binding_affinity": 180.0},
            {"trait_id": 1, "trait_name": "Trait A", "lncrna_gene_id": 12, "target_gene_id": 105, "binding_affinity": 110.0},
            {"trait_id": 2, "trait_name": "Trait B", "lncrna_gene_id": 20, "target_gene_id": 201, "binding_affinity": 200.0},
            {"trait_id": 2, "trait_name": "Trait B", "lncrna_gene_id": 21, "target_gene_id": 202, "binding_affinity": 190.0},
            {"trait_id": 2, "trait_name": "Trait B", "lncrna_gene_id": 22, "target_gene_id": 203, "binding_affinity": 180.0},
            {"trait_id": 2, "trait_name": "Trait B", "lncrna_gene_id": 23, "target_gene_id": 204, "binding_affinity": 170.0},
            {"trait_id": 2, "trait_name": "Trait B", "lncrna_gene_id": 23, "target_gene_id": 205, "binding_affinity": 160.0},
            {"trait_id": 2, "trait_name": "Trait B", "lncrna_gene_id": 24, "target_gene_id": 206, "binding_affinity": 150.0},
            {"trait_id": 3, "trait_name": "Trait C", "lncrna_gene_id": 30, "target_gene_id": 301, "binding_affinity": 220.0},
            {"trait_id": 3, "trait_name": "Trait C", "lncrna_gene_id": 31, "target_gene_id": 302, "binding_affinity": 210.0},
        ]

        rows = module.build_trait_summary_rows(network_rows)

        self.assertEqual([row["trait_name"] for row in rows], ["Trait B", "Trait A"])
        self.assertGreater(rows[0]["unique_lncrna_count"], rows[1]["unique_lncrna_count"])
        self.assertEqual(rows[1]["unique_target_gene_count"], 5)

    def test_build_trait_summary_rows_accepts_preaggregated_summary_rows(self):
        module = load_module()

        summary_rows = [
            {
                "trait_id": 2,
                "trait_name": "Trait B",
                "unique_lncrna_count": 6,
                "unique_target_gene_count": 8,
                "regulation_count": 20,
                "max_ba": 180.0,
            },
            {
                "trait_id": 1,
                "trait_name": "Trait A",
                "unique_lncrna_count": 4,
                "unique_target_gene_count": 5,
                "regulation_count": 12,
                "max_ba": 210.0,
            },
            {
                "trait_id": 3,
                "trait_name": "Trait C",
                "unique_lncrna_count": 2,
                "unique_target_gene_count": 9,
                "regulation_count": 10,
                "max_ba": 300.0,
            },
        ]

        rows = module.build_trait_summary_rows(summary_rows)

        self.assertEqual([row["trait_name"] for row in rows], ["Trait B", "Trait A"])
        self.assertEqual(rows[0]["unique_lncrna_count"], 6)
        self.assertEqual(rows[1]["max_ba"], 210.0)

    def test_build_flagship_trait_selection_rows_marks_rank_and_flagship(self):
        module = load_module()

        trait_summary_rows = [
            {"trait_id": 102, "trait_name": "obesity", "unique_lncrna_count": 10, "unique_target_gene_count": 24, "regulation_count": 188, "max_ba": 213.99},
            {"trait_id": 205, "trait_name": "Trait B", "unique_lncrna_count": 8, "unique_target_gene_count": 20, "regulation_count": 140, "max_ba": 201.0},
        ]

        rows = module.build_flagship_trait_selection_rows(trait_summary_rows, flagship_trait_name="obesity")

        self.assertEqual(rows[0]["flagship_rank"], 1)
        self.assertTrue(rows[0]["is_flagship"])
        self.assertEqual(rows[1]["flagship_rank"], 2)
        self.assertFalse(rows[1]["is_flagship"])

    def test_build_table6_rows_summarizes_trait_level_and_flagship_literature_support(self):
        module = load_module()

        trait_summary_rows = [
            {"trait_id": 1, "trait_name": "Trait A", "unique_target_gene_count": 3},
        ]
        network_rows = [
            {"trait_id": 1, "trait_name": "Trait A", "lncrna_gene_id": 11, "lncrna_name": "L1", "target_gene_id": 101, "binding_affinity": 120.0, "trait_literature_support": True},
            {"trait_id": 1, "trait_name": "Trait A", "lncrna_gene_id": 11, "lncrna_name": "L1", "target_gene_id": 102, "binding_affinity": 118.0, "trait_literature_support": False},
            {"trait_id": 1, "trait_name": "Trait A", "lncrna_gene_id": 11, "lncrna_name": "L1", "target_gene_id": 103, "binding_affinity": 111.0, "trait_literature_support": True},
            {"trait_id": 1, "trait_name": "Trait A", "lncrna_gene_id": 12, "lncrna_name": "L2", "target_gene_id": 101, "binding_affinity": 95.0, "trait_literature_support": True},
        ]
        pair_rows = [
            {"trait_id": 1, "trait_name": "Trait A", "lncrna_gene_id": 11, "lncrna_name": "L1", "target_count": 3, "high_affinity_edge_count": 3, "best_edge_conservation_count": 2, "epigenomic_support_class": "active_like", "max_ba": 120.0},
            {"trait_id": 1, "trait_name": "Trait A", "lncrna_gene_id": 12, "lncrna_name": "L2", "target_count": 1, "high_affinity_edge_count": 0, "best_edge_conservation_count": 0, "epigenomic_support_class": "other", "max_ba": 95.0},
        ]

        rows = module.build_table6_rows(
            trait_summary_rows,
            network_rows=network_rows,
            pair_rows=pair_rows,
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["trait_name"], "Trait A")
        self.assertEqual(row["literature_supported_target_gene_count"], 2)
        self.assertAlmostEqual(row["literature_supported_target_fraction"], 2 / 3, places=6)
        self.assertEqual(row["flagship_lncrna_name"], "L1")
        self.assertEqual(row["flagship_candidate_target_count"], 3)
        self.assertEqual(row["flagship_targets_with_trait_literature_support"], 2)
        self.assertAlmostEqual(row["flagship_targets_with_trait_literature_support_fraction"], 2 / 3, places=6)

    def test_rank_trait_lnc_candidates_uses_fixed_sort_and_rewiring_priority(self):
        module = load_module()

        candidate_rows = [
            {
                "lncrna_gene_id": 1,
                "lncrna_name": "L1",
                "trait_count": 2,
                "target_count": 8,
                "high_affinity_edge_count": 3,
                "best_edge_conservation_count": 4,
                "max_ba": 180.0,
                "rewiring_label": "conserved",
            },
            {
                "lncrna_gene_id": 2,
                "lncrna_name": "L2",
                "trait_count": 2,
                "target_count": 8,
                "high_affinity_edge_count": 3,
                "best_edge_conservation_count": 2,
                "max_ba": 210.0,
                "rewiring_label": "rewired",
            },
            {
                "lncrna_gene_id": 3,
                "lncrna_name": "L3",
                "trait_count": 1,
                "target_count": 9,
                "high_affinity_edge_count": 4,
                "best_edge_conservation_count": 1,
                "max_ba": 250.0,
                "rewiring_label": "species_specific",
            },
        ]

        ranked = module.rank_trait_lnc_candidates(candidate_rows)

        self.assertEqual([row["lncrna_gene_id"] for row in ranked], [1, 2, 3])

    def test_select_flagship_case_prefers_supported_top_ranked_candidate(self):
        module = load_module()

        candidate_rows = [
            {
                "trait_name": "Trait A",
                "lncrna_gene_id": 1,
                "lncrna_name": "L1",
                "target_count": 6,
                "high_affinity_edge_count": 4,
                "best_edge_conservation_count": 0,
                "epigenomic_support_class": "other",
            },
            {
                "trait_name": "Trait A",
                "lncrna_gene_id": 2,
                "lncrna_name": "L2",
                "target_count": 5,
                "high_affinity_edge_count": 3,
                "best_edge_conservation_count": 2,
                "epigenomic_support_class": "active_like",
            },
        ]

        selected = module.select_flagship_case(candidate_rows, flagship_trait_name="Trait A")

        self.assertEqual(selected["lncrna_gene_id"], 2)
        self.assertEqual(selected["trait_name"], "Trait A")

    def test_build_table2_rows_separates_main_text_and_extended_tracks(self):
        module = load_module()

        inventory_rows = [
            {"mark_name": "H3K4me3", "cell_line": "A549", "experiment_count": 1, "peak_count": 1000},
            {"mark_name": "DNase-HS", "cell_line": "A549", "experiment_count": 1, "peak_count": 900},
            {"mark_name": "CTCF", "cell_line": "A549", "experiment_count": 1, "peak_count": 800},
        ]

        rows = module.build_table2_rows(
            inventory_rows,
            baseline_marks=["H3K4me3", "DNase-HS"],
            extended_marks=["CTCF", "H4K20me1"],
        )

        by_mark = {row["mark_name"]: row for row in rows}
        self.assertEqual(by_mark["H3K4me3"]["inventory_group"], "main_text_baseline")
        self.assertEqual(by_mark["DNase-HS"]["inventory_group"], "main_text_baseline")
        self.assertEqual(by_mark["CTCF"]["inventory_group"], "extended_tracks")


    def test_build_fig5c_rows_limits_plot_to_top_ranked_lncRNAs(self):
        module = load_module()

        pair_rows = [
            {"trait_name": "Trait A", "lncrna_gene_id": 1, "lncrna_name": "L1", "target_count": 8, "mean_ba": 180.0},
            {"trait_name": "Trait B", "lncrna_gene_id": 1, "lncrna_name": "L1", "target_count": 7, "mean_ba": 170.0},
            {"trait_name": "Trait A", "lncrna_gene_id": 2, "lncrna_name": "L2", "target_count": 6, "mean_ba": 160.0},
            {"trait_name": "Trait C", "lncrna_gene_id": 3, "lncrna_name": "L3", "target_count": 5, "mean_ba": 150.0},
        ]
        ranked_candidate_rows = [
            {"lncrna_gene_id": 1},
            {"lncrna_gene_id": 2},
            {"lncrna_gene_id": 3},
        ]

        rows = module.build_fig5c_rows(
            pair_rows,
            ranked_candidate_rows=ranked_candidate_rows,
            trait_names=["Trait A", "Trait B", "Trait C"],
            max_lnc_labels=2,
        )

        self.assertEqual(sorted({row["lncrna_gene_id"] for row in rows}), [1, 2])
        self.assertEqual(sorted({row["trait_name"] for row in rows}), ["Trait A", "Trait B"])

    def test_format_fig5d_evidence_lines_uses_submission_terms(self):
        module = load_module()

        lines = module.format_fig5d_evidence_lines(
            {
                "trait_name": "obesity",
                "lncrna_name": "CATG00000045621.1",
                "candidate_targets": 8,
                "high_affinity_edges": 8,
                "ba_range": "145.99-213.99",
                "best_edge_conservation_count": 2,
                "rewiring_label": "conserved",
                "epigenomic_support_class": "bivalent_like",
                "flagship_targets_with_trait_literature_support": 3,
            }
        )

        self.assertIn("Edge class: conserved, 2-species", lines)
        self.assertIn("Epigenomic context: bivalent-like", lines)
        self.assertIn("Lit.-backed targets: 3/8", lines)
        self.assertNotIn("Best edge conservation", "\n".join(lines))
        self.assertNotIn("Rewiring label", "\n".join(lines))

    def test_format_genomic_window_label_uses_megabase_coordinates(self):
        module = load_module()

        label = module.format_genomic_window_label("chr19", 51012345, 51104567)

        self.assertEqual(label, "chr19:51.0-51.1 Mb")

    def test_generated_fig4a_svg_marks_na_combinations_in_gray(self):
        svg_path = REPO_ROOT / "paper_figures/fig4/fig4A_overlap_summary.svg"
        self.assertTrue(svg_path.exists(), f"missing generated svg: {svg_path}")

        svg_text = svg_path.read_text()

        self.assertIn("Gray = unavailable experiment", svg_text)

    def test_generated_fig4b_svg_uses_edge_cell_line_observation_titles(self):
        svg_path = REPO_ROOT / "paper_figures/fig4/fig4B_mark_signatures.svg"
        metadata_path = REPO_ROOT / "paper_figures/fig4/fig4B_metadata.json"
        self.assertTrue(svg_path.exists(), f"missing generated svg: {svg_path}")
        self.assertTrue(metadata_path.exists(), f"missing generated metadata: {metadata_path}")

        svg_text = svg_path.read_text()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertIn("All human edge-cell-line observations", svg_text)
        self.assertIn("BA ≥ 100 edge-cell-line observations", svg_text)
        self.assertEqual(metadata.get("title"), "Mark-overlap context classes")
        self.assertNotIn("Direct mark-overlap signature classes", metadata.get("title", ""))

    def test_generated_fig5_metadata_records_flagship_selection_rules(self):
        fig5a_meta_path = REPO_ROOT / "paper_figures/fig5/fig5A_metadata.json"
        fig5d_meta_path = REPO_ROOT / "paper_figures/fig5/fig5D_metadata.json"
        table5_path = REPO_ROOT / "paper_figures/tables/table5_flagship_trait_selection.tsv"
        table6_path = REPO_ROOT / "paper_figures/tables/table6_trait_literature_support.tsv"
        self.assertTrue(fig5a_meta_path.exists(), f"missing generated metadata: {fig5a_meta_path}")
        self.assertTrue(fig5d_meta_path.exists(), f"missing generated metadata: {fig5d_meta_path}")
        self.assertTrue(table5_path.exists(), f"missing generated table: {table5_path}")
        self.assertTrue(table6_path.exists(), f"missing generated table: {table6_path}")

        fig5a_meta = json.loads(fig5a_meta_path.read_text(encoding="utf-8"))
        fig5d_meta = json.loads(fig5d_meta_path.read_text(encoding="utf-8"))

        self.assertEqual(
            fig5a_meta.get("filters", {}).get("trait_selection_sort"),
            ["unique_lncrna_count desc", "unique_target_gene_count desc", "max_ba desc", "trait_id asc"],
        )
        self.assertEqual(
            fig5d_meta.get("filters", {}).get("case_selection_filters"),
            ["best_edge_conservation_count >= 1", "epigenomic_support_class != other"],
        )

    def test_generated_table6_reports_obesity_trait_literature_support(self):
        table6_path = REPO_ROOT / "paper_figures/tables/table6_trait_literature_support.tsv"
        self.assertTrue(table6_path.exists(), f"missing generated table: {table6_path}")

        with table6_path.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))

        self.assertTrue(rows)
        obesity_rows = [row for row in rows if row.get("trait_name") == "obesity"]
        self.assertEqual(len(obesity_rows), 1)
        obesity_row = obesity_rows[0]
        self.assertIn("literature_supported_target_gene_count", obesity_row)
        self.assertIn("flagship_targets_with_trait_literature_support", obesity_row)
        self.assertGreaterEqual(int(obesity_row["literature_supported_target_gene_count"]), 0)
        self.assertGreaterEqual(int(obesity_row["flagship_targets_with_trait_literature_support"]), 0)

    def test_generated_supplementary_table1_alias_matches_trait_literature_table(self):
        table6_path = REPO_ROOT / "paper_figures/tables/table6_trait_literature_support.tsv"
        supp_table1_path = REPO_ROOT / "paper_figures/tables/supp_table1_trait_literature_support.tsv"
        self.assertTrue(table6_path.exists(), f"missing generated table: {table6_path}")
        self.assertTrue(supp_table1_path.exists(), f"missing Supplementary Table 1 alias: {supp_table1_path}")

        self.assertEqual(
            table6_path.read_text(encoding="utf-8"),
            supp_table1_path.read_text(encoding="utf-8"),
        )

    def test_generated_suppfig6_companion_assets_exist_and_record_local_only_access(self):
        svg_path = REPO_ROOT / "paper_figures/supplementary/suppfig6_companion_access.svg"
        png_path = REPO_ROOT / "paper_figures/supplementary/suppfig6_companion_access.png"
        metadata_path = REPO_ROOT / "paper_figures/supplementary/suppfig6_companion_access.metadata.json"
        self.assertTrue(svg_path.exists(), f"missing Supplementary Figure 6 svg: {svg_path}")
        self.assertTrue(png_path.exists(), f"missing Supplementary Figure 6 png: {png_path}")
        self.assertTrue(metadata_path.exists(), f"missing Supplementary Figure 6 metadata: {metadata_path}")

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata.get("panel_id"), "SupplementaryFigure6")
        self.assertEqual(metadata.get("title"), "Human LncRNA Atlas Companion local access layer")
        self.assertEqual(
            metadata.get("filters", {}).get("panels"),
            ["Query interface", "Network view", "Genome-browser view", "Export / API workflow"],
        )
        self.assertIn("No public deployment URL", "\n".join(metadata.get("notes", [])))
        self.assertIn("FastAPI /docs", "\n".join(metadata.get("notes", [])))
        self.assertIn("repository-local", "\n".join(metadata.get("notes", [])))

    def test_generated_fig5_metadata_and_svg_lock_displayed_subset_wording(self):
        fig5a_meta_path = REPO_ROOT / "paper_figures/fig5/fig5A_metadata.json"
        fig5b_meta_path = REPO_ROOT / "paper_figures/fig5/fig5B_metadata.json"
        fig5d_meta_path = REPO_ROOT / "paper_figures/fig5/fig5D_metadata.json"
        fig5b_svg_path = REPO_ROOT / "paper_figures/fig5/fig5B_ranking_matrix.svg"
        fig5d_svg_path = REPO_ROOT / "paper_figures/fig5/fig5D_case_study.svg"
        for path in [fig5a_meta_path, fig5b_meta_path, fig5d_meta_path, fig5b_svg_path, fig5d_svg_path]:
            self.assertTrue(path.exists(), f"missing generated Figure 5 file: {path}")

        fig5a_meta = json.loads(fig5a_meta_path.read_text(encoding="utf-8"))
        fig5b_meta = json.loads(fig5b_meta_path.read_text(encoding="utf-8"))
        fig5d_meta = json.loads(fig5d_meta_path.read_text(encoding="utf-8"))
        self.assertEqual(fig5a_meta.get("filters", {}).get("displayed_node_count"), 14)
        self.assertEqual(fig5a_meta.get("filters", {}).get("full_exported_candidate_edge_count"), 188)
        self.assertIn(
            "column-normalized visualization only, not regulatory effect size",
            "\n".join(fig5b_meta.get("notes", [])),
        )
        self.assertIn(
            "Displayed subset is separate from the full exported flagship subnetwork",
            "\n".join(fig5d_meta.get("notes", [])),
        )
        self.assertIn("not effect size", fig5b_svg_path.read_text(encoding="utf-8"))
        self.assertIn("Displayed targets", fig5d_svg_path.read_text(encoding="utf-8"))
        self.assertIn("High-affinity edges", fig5d_svg_path.read_text(encoding="utf-8"))

    def test_generated_fig5_tripartite_svgs_use_explicit_obesity_label(self):
        fig5a_svg_path = REPO_ROOT / "paper_figures/fig5/fig5A_tripartite_network.svg"
        fig5d_svg_path = REPO_ROOT / "paper_figures/fig5/fig5D_case_study.svg"
        self.assertTrue(fig5a_svg_path.exists(), f"missing generated svg: {fig5a_svg_path}")
        self.assertTrue(fig5d_svg_path.exists(), f"missing generated svg: {fig5d_svg_path}")

        fig5a_svg_text = fig5a_svg_path.read_text()
        fig5d_svg_text = fig5d_svg_path.read_text()

        self.assertIn("Obesity", fig5a_svg_text)
        self.assertIn("Obesity", fig5d_svg_text)
        self.assertNotIn("<!-- obesity -->", fig5a_svg_text)
        self.assertNotIn("<!-- obesity -->", fig5d_svg_text)

    def test_figure5_caption_draft_explains_column_normalized_matrix(self):
        figures_md = (REPO_ROOT / "docs/paper/figures.md").read_text()
        manuscript_md = (REPO_ROOT / "docs/paper/manuscript.md").read_text()

        self.assertIn("column-normalized score", figures_md)
        self.assertIn("class membership", figures_md)
        self.assertIn("column-normalized score", manuscript_md)
        self.assertIn("class membership", manuscript_md)

    def test_figure3_and_figure4_caption_drafts_lock_submission_rules(self):
        figures_md = (REPO_ROOT / "docs/paper/figures.md").read_text()
        manuscript_md = (REPO_ROOT / "docs/paper/manuscript.md").read_text()

        for text in (figures_md, manuscript_md):
            self.assertIn("min_species_count >= 2", text)
            self.assertIn("no additional BA cutoff", text)
            self.assertIn("BA ≥ 100", text)
        self.assertIn("edge-level sharing is the primary comparative readout", figures_md)
        self.assertIn("edge-level sharing is the primary comparative readout", manuscript_md)
        for text in (figures_md, manuscript_md):
            self.assertIn("all-edge baseline observations with the BA ≥ 100 prioritization cohort", text)
            self.assertIn("rather than a universal inclusion threshold", text)
            self.assertIn("overlap fraction is calculated as distinct regulation IDs", text)

    def test_generated_fig5c_svg_explains_bubble_size(self):
        svg_path = REPO_ROOT / "paper_figures/fig5/fig5C_trait_specificity.svg"
        self.assertTrue(svg_path.exists(), f"missing generated svg: {svg_path}")

        svg_text = svg_path.read_text()

        self.assertIn("Bubble size = number of PCG targets", svg_text)

    def test_generated_fig4d_metadata_uses_local_epigenomic_tracks_title(self):
        metadata_path = REPO_ROOT / "paper_figures/fig4/fig4D_metadata.json"
        self.assertTrue(metadata_path.exists(), f"missing generated metadata: {metadata_path}")

        metadata = json.loads(metadata_path.read_text())

        self.assertEqual(metadata.get("title"), "Representative local epigenomic tracks")


if __name__ == "__main__":
    unittest.main()
