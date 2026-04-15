#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/paper/generate_batch1_figures.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"missing module under test: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("generate_batch1_figures", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GenerateBatch1FiguresTests(unittest.TestCase):
    def test_parse_frozen_submission_snapshot_extracts_frozen_metrics(self):
        module = load_module()

        figures_md = """
        frozen-snapshot KPI tiles using only already frozen metrics (`4` primate species, `804,630` predicted lncRNA to protein-coding gene relationships, `56` experiments, `4,567,525` peaks).
        """
        submission_md = """
        - **8 core histone marks**: `49` experiments, `3,343,903` peaks
        - **DNase-HS**: `7` experiments, `1,223,622` peaks
        - **Combined paper-facing baseline**: `56` experiments, `4,567,525` peaks
        Cross-mark comparison panels in the main text default to the following six human cell lines:
        - `A549`
        - `GM12878`
        - `H1-hESC`
        - `HepG2`
        - `HMEC`
        - `K562`
        """
        manuscript_md = """
        The frozen working snapshot contains **804,630** predicted lncRNA to protein-coding gene relationships across four primate species.
        """

        snapshot = module.parse_frozen_submission_snapshot(figures_md, submission_md, manuscript_md)

        self.assertEqual(snapshot["species_count"], 4)
        self.assertEqual(snapshot["candidate_relationships"], 804630)
        self.assertEqual(snapshot["baseline_experiments"], 56)
        self.assertEqual(snapshot["baseline_peaks"], 4567525)
        self.assertEqual(
            snapshot["cell_line_subset"],
            ["A549", "GM12878", "H1-hESC", "HepG2", "HMEC", "K562"],
        )

    def test_build_node_presence_rows_uses_fixed_species_order(self):
        module = load_module()

        rows = [
            {"core_id": 10, "species_id": 1, "gene_type": "lncRNA", "canonical_symbol": "L1", "human_ensembl_id": "ENSG1"},
            {"core_id": 10, "species_id": 3, "gene_type": "lncRNA", "canonical_symbol": "L1", "human_ensembl_id": "ENSG1"},
            {"core_id": 11, "species_id": 2, "gene_type": "protein_coding", "canonical_symbol": "PC1", "human_ensembl_id": "ENSG2"},
            {"core_id": 11, "species_id": 4, "gene_type": "protein_coding", "canonical_symbol": "PC1", "human_ensembl_id": "ENSG2"},
        ]

        presence_rows = module.build_node_presence_rows(rows, module.DEFAULT_SPECIES_ORDER)

        self.assertEqual(len(presence_rows), 2)
        by_core = {row["core_id"]: row for row in presence_rows}
        self.assertEqual(by_core[10]["conservation_label"], "1010")
        self.assertEqual(by_core[10]["conservation_count"], 2)
        self.assertEqual(by_core[11]["conservation_label"], "0101")
        self.assertEqual(by_core[11]["conservation_count"], 2)

    def test_build_edge_presence_rows_aggregates_core_pair_presence_and_ba(self):
        module = load_module()

        rows = [
            {"lncrna_core_id": 100, "target_core_id": 200, "species_id": 1, "binding_affinity": 120.0, "lncrna_symbol": "L100", "target_symbol": "T200"},
            {"lncrna_core_id": 100, "target_core_id": 200, "species_id": 1, "binding_affinity": 180.0, "lncrna_symbol": "L100", "target_symbol": "T200"},
            {"lncrna_core_id": 100, "target_core_id": 200, "species_id": 3, "binding_affinity": 160.0, "lncrna_symbol": "L100", "target_symbol": "T200"},
            {"lncrna_core_id": 100, "target_core_id": 200, "species_id": 4, "binding_affinity": 90.0, "lncrna_symbol": "L100", "target_symbol": "T200"},
        ]

        presence_rows = module.build_edge_presence_rows(rows, module.DEFAULT_SPECIES_ORDER)

        self.assertEqual(len(presence_rows), 1)
        row = presence_rows[0]
        self.assertEqual(row["conservation_label"], "1011")
        self.assertEqual(row["conservation_count"], 3)
        self.assertEqual(row["supporting_regulation_count"], 4)
        self.assertTrue(math.isclose(row["mean_ba"], 137.5))
        self.assertEqual(row["max_ba"], 180.0)

    def test_build_high_affinity_core_edges_and_hubs_collapse_duplicate_edges(self):
        module = load_module()

        rows = [
            {"lncrna_core_id": 10, "target_core_id": 20, "species_id": 1, "binding_affinity": 150.0, "lncrna_symbol": "L10", "lncrna_human_ensembl_id": "ENSG-L10", "target_symbol": "T20"},
            {"lncrna_core_id": 10, "target_core_id": 20, "species_id": 2, "binding_affinity": 170.0, "lncrna_symbol": "L10", "lncrna_human_ensembl_id": "ENSG-L10", "target_symbol": "T20"},
            {"lncrna_core_id": 10, "target_core_id": 21, "species_id": 1, "binding_affinity": 140.0, "lncrna_symbol": "L10", "lncrna_human_ensembl_id": "ENSG-L10", "target_symbol": "T21"},
            {"lncrna_core_id": 11, "target_core_id": 22, "species_id": 1, "binding_affinity": 130.0, "lncrna_symbol": "L11", "lncrna_human_ensembl_id": "ENSG-L11", "target_symbol": "T22"},
        ]

        edge_rows = module.build_high_affinity_core_edge_rows(rows, module.DEFAULT_SPECIES_ORDER)
        hub_rows = module.build_hub_rows(edge_rows)

        self.assertEqual(len(edge_rows), 3)
        by_pair = {(row["lncrna_core_id"], row["target_core_id"]): row for row in edge_rows}
        self.assertEqual(by_pair[(10, 20)]["species_count"], 2)
        self.assertEqual(by_pair[(10, 20)]["conservation_label"], "1100")
        self.assertTrue(math.isclose(by_pair[(10, 20)]["mean_ba"], 160.0))

        self.assertEqual(hub_rows[0]["lncrna_core_id"], 10)
        self.assertEqual(hub_rows[0]["unique_target_core_count"], 2)
        self.assertEqual(hub_rows[0]["supporting_edge_count"], 3)

    def test_format_lncRNA_display_label_shortens_accession_like_symbols(self):
        module = load_module()

        self.assertEqual(module.format_lncRNA_display_label("LINC00152", "ENSG00000222041.8"), "LINC00152")
        self.assertEqual(
            module.format_lncRNA_display_label("CATG00000083332.1", "CATG00000083332.1"),
            "CATG083332",
        )
        self.assertEqual(
            module.format_lncRNA_display_label("ENSG00000255197.1", "ENSG00000255197.1"),
            "ENSG255197",
        )
        self.assertEqual(
            module.format_lncRNA_display_label("", "ENSG00000224078.8"),
            "ENSG224078",
        )

    def test_build_ba_summary_rows_reports_priority_fraction_and_plot_limits(self):
        module = load_module()

        rows = module.build_ba_summary_rows(
            {
                "human": [50.0, 60.0, 100.0, 120.0],
                "chimp": [55.0, 65.0, 75.0, 85.0],
            },
            [
                {"species_code": "human", "display_name": "Human"},
                {"species_code": "chimp", "display_name": "Chimpanzee"},
            ],
            priority_line=100.0,
        )

        self.assertEqual([row["species_code"] for row in rows], ["human", "chimp"])
        self.assertEqual(rows[0]["total_edges"], 4)
        self.assertEqual(rows[0]["n_ge_100"], 2)
        self.assertTrue(math.isclose(rows[0]["frac_ge_100"], 0.5))
        self.assertEqual(rows[0]["full_plot_ymax"], 120.0)
        self.assertEqual(rows[0]["main_plot_ymax"], 200.0)
        self.assertEqual(rows[1]["n_ge_100"], 0)
        self.assertTrue(math.isclose(rows[1]["frac_ge_100"], 0.0))

    def test_build_centrality_rows_uses_eigenvector_metric_for_lncRNAs(self):
        module = load_module()

        edge_rows = [
            {
                "lncrna_core_id": 1,
                "target_core_id": 10,
                "lncrna_symbol": "L1",
                "lncrna_human_ensembl_id": "ENSG-L1",
                "mean_ba": 180.0,
                "supporting_regulation_count": 2,
            },
            {
                "lncrna_core_id": 1,
                "target_core_id": 11,
                "lncrna_symbol": "L1",
                "lncrna_human_ensembl_id": "ENSG-L1",
                "mean_ba": 150.0,
                "supporting_regulation_count": 1,
            },
            {
                "lncrna_core_id": 2,
                "target_core_id": 10,
                "lncrna_symbol": "L2",
                "lncrna_human_ensembl_id": "ENSG-L2",
                "mean_ba": 130.0,
                "supporting_regulation_count": 1,
            },
        ]

        centrality_rows = module.build_centrality_rows(edge_rows)

        self.assertEqual(centrality_rows[0]["core_id"], 1)
        self.assertIn("eigenvector_centrality", centrality_rows[0])
        self.assertNotIn("betweenness", centrality_rows[0])
        self.assertGreater(float(centrality_rows[0]["eigenvector_centrality"]), 0.0)
        self.assertGreater(
            float(centrality_rows[0]["eigenvector_centrality"]),
            float(centrality_rows[1]["eigenvector_centrality"]),
        )

    def test_normalize_species_rows_prefers_fixed_english_display_names(self):
        module = load_module()

        rows = [
            {"species_id": 1, "species_code": "human", "display_name": "人类", "genome_assembly": "hg19"},
            {"species_id": 2, "species_code": "chimp", "display_name": "黑猩猩", "genome_assembly": "panTro5"},
        ]

        normalized = module.normalize_species_rows(rows, module.DEFAULT_SPECIES_ORDER)

        self.assertEqual(normalized[0]["display_name"], "Human")
        self.assertEqual(normalized[1]["display_name"], "Chimpanzee")

    def test_build_upset_and_pairwise_sharing_rows_filter_and_score_consistently(self):
        module = load_module()

        edge_presence_rows = [
            {"lncrna_core_id": 1, "target_core_id": 11, "conservation_label": "1100", "conservation_count": 2},
            {"lncrna_core_id": 2, "target_core_id": 12, "conservation_label": "1010", "conservation_count": 2},
            {"lncrna_core_id": 3, "target_core_id": 13, "conservation_label": "1110", "conservation_count": 3},
            {"lncrna_core_id": 4, "target_core_id": 14, "conservation_label": "1000", "conservation_count": 1},
        ]

        upset_rows = module.build_upset_rows(edge_presence_rows)
        pairwise_rows = module.build_pairwise_sharing_rows(edge_presence_rows, module.DEFAULT_SPECIES_ORDER, item_type="edge")

        self.assertEqual([row["conservation_label"] for row in upset_rows], ["1110", "1010", "1100"])
        self.assertEqual([row["count"] for row in upset_rows], [1, 1, 1])

        human_chimp = next(
            row for row in pairwise_rows if row["species_a"] == "human" and row["species_b"] == "chimp"
        )
        self.assertEqual(human_chimp["intersection_count"], 2)
        self.assertEqual(human_chimp["union_count"], 4)
        self.assertTrue(math.isclose(human_chimp["jaccard"], 0.5))


if __name__ == "__main__":
    unittest.main()
