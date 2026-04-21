#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
