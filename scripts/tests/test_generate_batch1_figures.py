#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import csv
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

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

    def test_select_fig2c_label_rows_uses_only_first_five_centrality_rows(self):
        module = load_module()

        centrality_rows = [
            {"core_id": 101, "out_degree": 320, "eigenvector_centrality": 0.24, "mean_outgoing_ba": 160.0},
            {"core_id": 102, "out_degree": 300, "eigenvector_centrality": 0.21, "mean_outgoing_ba": 155.0},
            {"core_id": 103, "out_degree": 280, "eigenvector_centrality": 0.20, "mean_outgoing_ba": 150.0},
            {"core_id": 104, "out_degree": 260, "eigenvector_centrality": 0.18, "mean_outgoing_ba": 148.0},
            {"core_id": 105, "out_degree": 240, "eigenvector_centrality": 0.16, "mean_outgoing_ba": 145.0},
            {"core_id": 106, "out_degree": 999, "eigenvector_centrality": 0.10, "mean_outgoing_ba": 120.0},
        ]

        label_rows = module.select_fig2c_label_rows(centrality_rows)

        self.assertEqual([row["core_id"] for row in label_rows], [101, 102, 103, 104, 105])

    def test_select_fig2c_label_rows_returns_all_rows_when_fewer_than_limit(self):
        module = load_module()

        centrality_rows = [
            {"core_id": 201, "out_degree": 120, "eigenvector_centrality": 0.14, "mean_outgoing_ba": 140.0},
            {"core_id": 202, "out_degree": 110, "eigenvector_centrality": 0.11, "mean_outgoing_ba": 130.0},
        ]

        label_rows = module.select_fig2c_label_rows(centrality_rows)

        self.assertEqual([row["core_id"] for row in label_rows], [201, 202])

    def test_generated_suppfig7_metadata_uses_script_provenance_and_permutation_wording(self):
        metadata_path = REPO_ROOT / "paper_figures/supplementary/suppfig7_robustness.metadata.json"
        self.assertTrue(metadata_path.exists(), f"missing generated metadata: {metadata_path}")

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(metadata.get("script"), "scripts/paper/generate_batch1_figures.py")
        self.assertEqual(
            metadata.get("filters", {}).get("ba_thresholds"),
            [0, 100, 150],
        )
        self.assertIn(
            "permute target assignments within species",
            "\n".join(metadata.get("notes", [])),
        )

    def test_generated_suppfig7e_marmoset_downsampling_tsv_reports_coverage_sensitivity(self):
        tsv_path = REPO_ROOT / "paper_figures/supplementary/suppfig7E_marmoset_downsampling.tsv"
        self.assertTrue(tsv_path.exists(), f"missing generated TSV: {tsv_path}")

        with tsv_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        by_count = {int(row["conservation_count"]): row for row in rows}

        self.assertEqual(by_count[4]["null_model"], "marmoset_edge_count_downsampling_target_permutation")
        self.assertEqual(by_count[4]["reference_species"], "marmoset")
        self.assertEqual(int(by_count[4]["reference_edge_count"]), 31798)
        self.assertEqual(int(by_count[4]["downsampled_edge_count_per_species"]), 31798)
        self.assertEqual(float(by_count[4]["observed_median_edge_count"]), 228.0)
        self.assertEqual(float(by_count[4]["observed_p05_edge_count"]), 203.0)
        self.assertEqual(float(by_count[4]["observed_p95_edge_count"]), 254.0)
        self.assertEqual(float(by_count[4]["null_p95_edge_count"]), 7.0)
        self.assertEqual(int(by_count[4]["null_iterations"]), 1000)
        self.assertIn(
            "human;chimp;macaque downsampled to marmoset edge count",
            by_count[4]["sampling_rule"],
        )
        self.assertIn("observed and null samples use seeded random subsampling", by_count[4]["sampling_rule"])

    def test_draw_species_specific_exemplar_uses_larger_target_labels(self):
        module = load_module()

        fig, ax = plt.subplots(figsize=(4, 3))
        try:
            module._draw_species_specific_exemplar(
                ax,
                species_code="human",
                species_name="Human",
                node_rows=[
                    {"node_role": "lncrna", "core_id": 1, "display_label": "LNC1"},
                    {"node_role": "target", "core_id": 2, "display_label": "TARGET1"},
                    {"node_role": "target", "core_id": 3, "display_label": "TARGET2"},
                ],
                edge_rows=[
                    {"target_core_id": 2, "human": 1, "max_ba": 180.0},
                    {"target_core_id": 3, "human": 1, "max_ba": 150.0},
                ],
            )

            target_font_sizes = [
                text.get_fontsize()
                for text in ax.texts
                if text.get_text() in {"TARGET1", "TARGET2"}
            ]
        finally:
            plt.close(fig)

        self.assertEqual(len(target_font_sizes), 2)
        self.assertTrue(all(size >= 10.0 for size in target_font_sizes))

    def test_fig1d_metadata_uses_short_submission_snapshot_title(self):
        metadata_path = REPO_ROOT / "paper_figures/fig1/fig1D_metadata.json"
        self.assertTrue(metadata_path.exists(), f"missing generated metadata: {metadata_path}")

        import json
        metadata = json.loads(metadata_path.read_text())

        self.assertEqual(metadata.get("title"), "Frozen submission snapshot")

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

    def test_build_robustness_threshold_rows_tracks_counts_across_ba_tiers(self):
        module = load_module()

        species_edge_rows = [
            {"lncrna_core_id": 1, "target_core_id": 11, "species_id": 1, "lncrna_symbol": "L1", "target_symbol": "T11", "max_ba": 180.0},
            {"lncrna_core_id": 1, "target_core_id": 11, "species_id": 2, "lncrna_symbol": "L1", "target_symbol": "T11", "max_ba": 170.0},
            {"lncrna_core_id": 2, "target_core_id": 22, "species_id": 1, "lncrna_symbol": "L2", "target_symbol": "T22", "max_ba": 120.0},
            {"lncrna_core_id": 2, "target_core_id": 22, "species_id": 3, "lncrna_symbol": "L2", "target_symbol": "T22", "max_ba": 80.0},
            {"lncrna_core_id": 3, "target_core_id": 33, "species_id": 1, "lncrna_symbol": "L3", "target_symbol": "T33", "max_ba": 155.0},
            {"lncrna_core_id": 3, "target_core_id": 33, "species_id": 2, "lncrna_symbol": "L3", "target_symbol": "T33", "max_ba": 150.0},
            {"lncrna_core_id": 3, "target_core_id": 33, "species_id": 3, "lncrna_symbol": "L3", "target_symbol": "T33", "max_ba": 149.0},
        ]

        rows = module.build_robustness_threshold_rows(
            species_edge_rows,
            module.DEFAULT_SPECIES_ORDER,
            thresholds=(0.0, 100.0, 150.0),
        )

        by_key = {(row["threshold_label"], row["conservation_count"]): row for row in rows}
        self.assertEqual(by_key[("All edges", 2)]["edge_count"], 2)
        self.assertEqual(by_key[("All edges", 3)]["edge_count"], 1)
        self.assertEqual(by_key[("BA ≥ 100", 2)]["edge_count"], 3)
        self.assertEqual(by_key[("BA ≥ 150", 2)]["edge_count"], 2)
        self.assertEqual(by_key[("BA ≥ 150", 3)]["edge_count"], 0)

    def test_permute_species_edge_rows_preserves_species_level_marginals(self):
        module = load_module()

        species_edge_rows = [
            {"lncrna_core_id": 1, "target_core_id": 11, "species_id": 1, "lncrna_symbol": "L1", "target_symbol": "T11", "max_ba": 90.0},
            {"lncrna_core_id": 1, "target_core_id": 12, "species_id": 1, "lncrna_symbol": "L1", "target_symbol": "T12", "max_ba": 95.0},
            {"lncrna_core_id": 2, "target_core_id": 13, "species_id": 1, "lncrna_symbol": "L2", "target_symbol": "T13", "max_ba": 100.0},
            {"lncrna_core_id": 3, "target_core_id": 21, "species_id": 2, "lncrna_symbol": "L3", "target_symbol": "T21", "max_ba": 80.0},
            {"lncrna_core_id": 4, "target_core_id": 22, "species_id": 2, "lncrna_symbol": "L4", "target_symbol": "T22", "max_ba": 85.0},
            {"lncrna_core_id": 4, "target_core_id": 23, "species_id": 2, "lncrna_symbol": "L4", "target_symbol": "T23", "max_ba": 88.0},
        ]

        permuted_rows = module.permute_species_edge_rows(
            species_edge_rows,
            rng=np.random.default_rng(7),
        )

        def species_counts(rows, key):
            summary = {}
            for row in rows:
                species_id = int(row["species_id"])
                summary.setdefault(species_id, {})
                value = int(row[key])
                summary[species_id][value] = summary[species_id].get(value, 0) + 1
            return summary

        self.assertEqual(species_counts(permuted_rows, "lncrna_core_id"), species_counts(species_edge_rows, "lncrna_core_id"))
        self.assertEqual(species_counts(permuted_rows, "target_core_id"), species_counts(species_edge_rows, "target_core_id"))
        self.assertEqual(len(permuted_rows), len({(row["species_id"], row["lncrna_core_id"], row["target_core_id"]) for row in permuted_rows}))

    def test_build_node_vs_edge_summary_keeps_two_to_four_species_for_main_text(self):
        module = load_module()

        node_rows = [
            {"conservation_count": 1},
            {"conservation_count": 2},
            {"conservation_count": 2},
            {"conservation_count": 4},
        ]
        edge_rows = [
            {"conservation_count": 1},
            {"conservation_count": 2},
            {"conservation_count": 3},
            {"conservation_count": 3},
            {"conservation_count": 4},
        ]

        summary_rows = module.build_node_vs_edge_summary(node_rows, edge_rows)

        self.assertEqual(sorted({row["conservation_count"] for row in summary_rows}), [2, 3, 4])
        node_summary = {(row["item_type"], row["conservation_count"]): row for row in summary_rows}
        self.assertEqual(node_summary[("node", 2)]["raw_count"], 2)
        self.assertEqual(node_summary[("node", 4)]["raw_count"], 1)
        self.assertEqual(node_summary[("edge", 3)]["raw_count"], 2)
        self.assertEqual(node_summary[("edge", 4)]["raw_count"], 1)


    def test_build_fig1c_workflow_rows_uses_four_readable_cards(self):
        module = load_module()

        rows = module.build_fig1c_workflow_rows()

        self.assertEqual([row["step_key"] for row in rows], [
            "catalogs",
            "core_ids",
            "triplex_inference",
            "candidate_network",
        ])
        self.assertEqual(rows[0]["display_label"], "Catalogs")
        self.assertEqual(rows[1]["display_label"], "Core IDs")
        self.assertEqual(rows[2]["display_label"], "Triplex inference")
        self.assertEqual(rows[3]["display_label"], "Candidate lncRNA–PCG edge network")

    def test_generated_main_figure_wording_uses_candidate_edge_framing(self):
        checks = {
            REPO_ROOT / "paper_figures/fig1/fig1A_catalog_gap.svg": [
                ("Nodes, not candidate edges", True),
                ("Nodes, not edges", False),
            ],
            REPO_ROOT / "paper_figures/fig1/fig1C_workflow.svg": [
                ("Candidate lncRNA–PCG edge network", True),
                ("Candidate regulatory network", False),
            ],
            REPO_ROOT / "paper_figures/fig1/fig1D_kpi.svg": [
                ("Candidate lncRNA–PCG edges", True),
                ("Candidate regulatory edges", False),
            ],
            REPO_ROOT / "paper_figures/fig2/fig2A_ba_distribution.svg": [
                ("BA ≥100 prioritization zone", True),
                ("BA = 100 priority line", False),
            ],
            REPO_ROOT / "paper_figures/fig2/fig2C_centrality.svg": [
                ("Unique target-core breadth", True),
                ("Out-degree (unique target cores)", False),
            ],
        }
        for path, expectations in checks.items():
            self.assertTrue(path.exists(), f"missing generated svg: {path}")
            text = path.read_text(encoding="utf-8")
            for needle, should_exist in expectations:
                if should_exist:
                    self.assertIn(needle, text, f"{needle!r} missing from {path}")
                else:
                    self.assertNotIn(needle, text, f"{needle!r} should not remain in {path}")

    def test_parse_args_exposes_source_commit_override(self):
        module = load_module()
        original_argv = sys.argv[:]
        try:
            sys.argv = ["generate_batch1_figures.py"]
            args = module.parse_args()
        finally:
            sys.argv = original_argv

        self.assertTrue(hasattr(args, "source_commit"))
        self.assertIsNone(args.source_commit)

    def test_generated_supplementary_figure7_robustness_assets_exist(self):
        svg_path = REPO_ROOT / "paper_figures/supplementary/suppfig7_robustness.svg"
        metadata_path = REPO_ROOT / "paper_figures/supplementary/suppfig7_robustness.metadata.json"
        self.assertTrue(svg_path.exists(), f"missing generated svg: {svg_path}")
        self.assertTrue(metadata_path.exists(), f"missing generated metadata: {metadata_path}")

        import json
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(metadata.get("panel_id"), "SupplementaryFigure7")
        self.assertEqual(metadata.get("title"), "Robustness of edge-level conservation and rewiring summaries")
        self.assertEqual(metadata.get("filters", {}).get("ba_thresholds"), [0, 100, 150])
        self.assertGreaterEqual(int(metadata.get("filters", {}).get("null_iterations", 0)), 1000)

    def test_default_supplementary_figure7_null_iterations_are_publication_strength(self):
        module = load_module()

        self.assertGreaterEqual(module.SUPP_FIG7_NULL_ITERATIONS, 1000)
        self.assertEqual(module.SUPP_FIG7_RNG_SEED, 42)

    def test_degree_bin_matched_null_preserves_degree_tiers(self):
        module = load_module()

        species_edge_rows = [
            {"species_id": 1, "lncrna_core_id": 10, "target_core_id": 100, "target_symbol": "A"},
            {"species_id": 1, "lncrna_core_id": 10, "target_core_id": 101, "target_symbol": "B"},
            {"species_id": 1, "lncrna_core_id": 11, "target_core_id": 102, "target_symbol": "C"},
            {"species_id": 1, "lncrna_core_id": 12, "target_core_id": 100, "target_symbol": "A"},
            {"species_id": 1, "lncrna_core_id": 12, "target_core_id": 103, "target_symbol": "D"},
        ]

        permuted = module.permute_species_edge_rows_degree_bin_matched(
            species_edge_rows,
            rng=module.np.random.default_rng(7),
        )

        observed_lnc_degrees = {}
        observed_target_degrees = {}
        for row in species_edge_rows:
            observed_lnc_degrees[row["lncrna_core_id"]] = observed_lnc_degrees.get(row["lncrna_core_id"], 0) + 1
            observed_target_degrees[row["target_core_id"]] = observed_target_degrees.get(row["target_core_id"], 0) + 1

        permuted_lnc_degrees = {}
        for row in permuted:
            permuted_lnc_degrees[row["lncrna_core_id"]] = permuted_lnc_degrees.get(row["lncrna_core_id"], 0) + 1
            original_tier = module.degree_tier(observed_lnc_degrees[row["lncrna_core_id"]])
            assigned_target_tier = module.degree_tier(observed_target_degrees[row["target_core_id"]])
            self.assertIn(original_tier, {"2-4", "1"})
            self.assertIn(assigned_target_tier, {"2-4", "1"})

        self.assertEqual(permuted_lnc_degrees, observed_lnc_degrees)

    def test_degree_bin_matched_null_summary_reports_model(self):
        module = load_module()

        species_order = [
            {"species_id": 1, "species_code": "sp1", "display_name": "Species 1"},
            {"species_id": 2, "species_code": "sp2", "display_name": "Species 2"},
        ]
        species_edge_rows = [
            {"species_id": 1, "lncrna_core_id": 10, "target_core_id": 100, "target_symbol": "A"},
            {"species_id": 1, "lncrna_core_id": 10, "target_core_id": 101, "target_symbol": "B"},
            {"species_id": 2, "lncrna_core_id": 10, "target_core_id": 100, "target_symbol": "A"},
            {"species_id": 2, "lncrna_core_id": 11, "target_core_id": 102, "target_symbol": "C"},
        ]

        rows = module.build_degree_bin_matched_null_conservation_summary_rows(
            species_edge_rows,
            species_order,
            iterations=3,
            rng_seed=42,
        )

        self.assertTrue(rows)
        self.assertTrue(all(row["null_model"] == "degree_bin_matched_target_permutation" for row in rows))
        self.assertTrue(all(row["null_iterations"] == 3 for row in rows))
        self.assertIn("lncrna_degree_tier", rows[0]["matching_rule"])

    def test_marmoset_edge_count_downsampling_sensitivity_matches_reference_species_size(self):
        module = load_module()

        species_order = [
            {"species_id": 1, "species_code": "human", "display_name": "Human"},
            {"species_id": 2, "species_code": "chimp", "display_name": "Chimpanzee"},
            {"species_id": 3, "species_code": "macaque", "display_name": "Macaque"},
            {"species_id": 4, "species_code": "marmoset", "display_name": "Marmoset"},
        ]
        species_edge_rows = []
        for species_id in [1, 2, 3]:
            for offset in range(5):
                species_edge_rows.append(
                    {
                        "species_id": species_id,
                        "lncrna_core_id": 100 + offset,
                        "target_core_id": 200 + offset,
                        "target_symbol": f"T{offset}",
                    }
                )
        for offset in range(3):
            species_edge_rows.append(
                {
                    "species_id": 4,
                    "lncrna_core_id": 100 + offset,
                    "target_core_id": 200 + offset,
                    "target_symbol": f"T{offset}",
                }
            )

        rows = module.build_marmoset_edge_count_downsampling_sensitivity_rows(
            species_edge_rows,
            species_order,
            iterations=5,
            rng_seed=42,
        )

        by_count = {row["conservation_count"]: row for row in rows}
        self.assertEqual(by_count[4]["reference_species"], "marmoset")
        self.assertEqual(by_count[4]["reference_edge_count"], 3)
        self.assertEqual(by_count[4]["downsampled_edge_count_per_species"], 3)
        self.assertIn("observed_median_edge_count", by_count[4])
        self.assertNotIn("observed_edge_count", by_count[4])
        self.assertLessEqual(by_count[4]["null_p95_edge_count"], by_count[4]["observed_p95_edge_count"])
        self.assertEqual(by_count[4]["null_iterations"], 5)
        self.assertIn("human;chimp;macaque downsampled to marmoset edge count", by_count[4]["sampling_rule"])
        self.assertIn("observed and null samples use seeded random subsampling", by_count[4]["sampling_rule"])

    def test_generated_fig2_metadata_marks_unadjusted_hub_prioritization(self):
        fig2b_metadata_path = REPO_ROOT / "paper_figures/fig2/fig2B_metadata.json"
        fig2c_metadata_path = REPO_ROOT / "paper_figures/fig2/fig2C_metadata.json"
        self.assertTrue(fig2b_metadata_path.exists(), f"missing generated metadata: {fig2b_metadata_path}")
        self.assertTrue(fig2c_metadata_path.exists(), f"missing generated metadata: {fig2c_metadata_path}")

        fig2b_metadata = json.loads(fig2b_metadata_path.read_text(encoding="utf-8"))
        fig2c_metadata = json.loads(fig2c_metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(fig2b_metadata.get("title"), "Unadjusted target-core breadth prioritization")
        self.assertIn(
            "not normalized for transcript length, GC content, repeat content, or triplex-compatible motif opportunity",
            "\n".join(fig2b_metadata.get("notes", [])),
        )
        self.assertEqual(fig2c_metadata.get("title"), "Network-central candidate organizers")

    def test_with_generation_provenance_uses_source_commit_key(self):
        module = load_module()

        payload = module.with_generation_provenance(
            {"panel_id": "Figure2A"},
            generated_at="2026-04-15T06:20:58Z",
            source_commit="bcd67cc7986d39112cf5c361b12934289b61a518",
        )

        self.assertEqual(payload["generated_at"], "2026-04-15T06:20:58Z")
        self.assertEqual(payload["source_commit"], "bcd67cc7986d39112cf5c361b12934289b61a518")
        self.assertNotIn("release_commit", payload)

    def test_load_fig2b_alias_manifest_reads_rows_by_core_id(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "fig2b_aliases.tsv"
            manifest_path.write_text(
                "\n".join(
                    [
                        "lncrna_core_id\treference_accession\tdisplay_label\tnotes",
                        "83332\tCATG00000083332.1\tHub-A\tshared conserved hub",
                        "944\tCATG00000000944.1\t\tleave blank to fallback",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            alias_rows = module.load_fig2b_alias_manifest(manifest_path)

        self.assertEqual(alias_rows[83332]["display_label"], "Hub-A")
        self.assertEqual(alias_rows[944]["reference_accession"], "CATG00000000944.1")

    def test_apply_fig2b_alias_manifest_prefers_alias_and_falls_back_to_shortened_id(self):
        module = load_module()

        hub_rows = [
            {
                "lncrna_core_id": 83332,
                "lncrna_symbol": "CATG00000083332.1",
                "lncrna_human_ensembl_id": "CATG00000083332.1",
            },
            {
                "lncrna_core_id": 944,
                "lncrna_symbol": "CATG00000000944.1",
                "lncrna_human_ensembl_id": "CATG00000000944.1",
            },
        ]
        alias_rows = {
            83332: {
                "lncrna_core_id": 83332,
                "reference_accession": "CATG00000083332.1",
                "display_label": "Hub-A",
                "notes": "shared conserved hub",
            },
            944: {
                "lncrna_core_id": 944,
                "reference_accession": "CATG00000000944.1",
                "display_label": "",
                "notes": "fallback",
            },
        }

        applied_rows = module.apply_fig2b_alias_manifest(hub_rows, alias_rows)

        self.assertEqual(applied_rows[0]["display_label"], "Hub-A")
        self.assertEqual(applied_rows[1]["display_label"], "CATG000944")

    def test_apply_fig2b_alias_manifest_rejects_reference_mismatch_when_alias_is_nonempty(self):
        module = load_module()

        hub_rows = [
            {
                "lncrna_core_id": 83332,
                "lncrna_symbol": "CATG00000083332.1",
                "lncrna_human_ensembl_id": "CATG00000083332.1",
            }
        ]
        alias_rows = {
            83332: {
                "lncrna_core_id": 83332,
                "reference_accession": "ENSG00000255197.1",
                "display_label": "Hub-A",
                "notes": "mismatch should fail",
            }
        }

        with self.assertRaisesRegex(ValueError, "reference_accession"):
            module.apply_fig2b_alias_manifest(hub_rows, alias_rows)

    def test_build_fig1a_catalog_gap_rows_use_nodes_not_edges_language(self):
        module = load_module()

        rows = module.build_fig1a_catalog_gap_rows()

        self.assertEqual([row["catalog_type"] for row in rows], ["lncrna_catalog", "protein_coding_catalog"])
        self.assertTrue(all("nodes, not edges" in row["gap_message"] for row in rows))
        self.assertEqual(rows[0]["display_label"], "Trait-associated lncRNAs")
        self.assertEqual(rows[1]["display_label"], "Trait-associated protein-coding genes")

    def test_build_fig1b_species_summary_rows_count_core_coverage_by_species(self):
        module = load_module()

        node_rows = [
            {"core_id": 1, "gene_type": "lncRNA", "species_id": 1},
            {"core_id": 1, "gene_type": "lncRNA", "species_id": 2},
            {"core_id": 2, "gene_type": "lncRNA", "species_id": 1},
            {"core_id": 3, "gene_type": "protein_coding", "species_id": 1},
            {"core_id": 3, "gene_type": "protein_coding", "species_id": 3},
            {"core_id": 3, "gene_type": "protein_coding", "species_id": 4},
            {"core_id": 4, "gene_type": "protein_coding", "species_id": 2},
            {"core_id": 4, "gene_type": "protein_coding", "species_id": 3},
        ]

        rows = module.build_fig1b_species_summary_rows(node_rows, module.DEFAULT_SPECIES_ORDER)

        self.assertEqual([row["species_code"] for row in rows], ["human", "chimp", "macaque", "marmoset"])
        self.assertEqual(rows[0]["lncrna_core_count"], 2)
        self.assertEqual(rows[0]["protein_coding_core_count"], 1)
        self.assertEqual(rows[0]["comparable_core_group_count"], 2)
        self.assertEqual(rows[1]["lncrna_core_count"], 1)
        self.assertEqual(rows[1]["protein_coding_core_count"], 1)
        self.assertEqual(rows[2]["lncrna_core_count"], 0)
        self.assertEqual(rows[2]["protein_coding_core_count"], 2)
        self.assertEqual(rows[3]["comparable_core_group_count"], 1)

    def test_build_fig1c_workflow_rows_follow_research_first_narrative(self):
        module = load_module()

        rows = module.build_fig1c_workflow_rows()

        self.assertEqual(
            [row["step_key"] for row in rows],
            ["catalogs", "core_ids", "triplex_inference", "candidate_network"],
        )
        self.assertEqual(rows[0]["subtitle"], "Trait-associated lncRNAs / PCGs")
        self.assertIn("ortholog tables", rows[1]["subtitle"])
        self.assertEqual(rows[-1]["display_label"], "Candidate regulatory network")

    def test_select_fig2d_hub_module_chooses_top_hub_and_limits_targets(self):
        module = load_module()

        edge_rows = []
        for target_core_id, max_ba in zip(range(100, 109), range(210, 201, -1), strict=True):
            edge_rows.append(
                {
                    "lncrna_core_id": 1,
                    "target_core_id": target_core_id,
                    "lncrna_symbol": "L1",
                    "lncrna_human_ensembl_id": "ENSG-L1",
                    "target_symbol": f"T{target_core_id}",
                    "human": 1,
                    "chimp": 1,
                    "macaque": 0,
                    "marmoset": 0,
                    "conservation_label": "1100",
                    "conservation_count": 2,
                    "species_count": 2,
                    "supporting_regulation_count": 2,
                    "mean_ba": float(max_ba - 2),
                    "max_ba": float(max_ba),
                }
            )
        edge_rows.extend(
            [
                {
                    "lncrna_core_id": 2,
                    "target_core_id": 200,
                    "lncrna_symbol": "L2",
                    "lncrna_human_ensembl_id": "ENSG-L2",
                    "target_symbol": "T200",
                    "human": 1,
                    "chimp": 0,
                    "macaque": 0,
                    "marmoset": 0,
                    "conservation_label": "1000",
                    "conservation_count": 1,
                    "species_count": 1,
                    "supporting_regulation_count": 1,
                    "mean_ba": 180.0,
                    "max_ba": 180.0,
                }
            ]
        )

        manifest_row, node_rows, module_edges = module.select_fig2d_hub_module(edge_rows, max_targets=8)

        self.assertEqual(manifest_row["module_kind"], "hub")
        self.assertEqual(manifest_row["lncrna_core_id"], 1)
        self.assertEqual(manifest_row["node_count"], 9)
        self.assertEqual(len(module_edges), 8)
        self.assertEqual([row["target_core_id"] for row in module_edges], list(range(100, 108)))
        self.assertEqual(sum(1 for row in node_rows if row["node_role"] == "lncrna"), 1)

    def test_select_fig2d_community_module_prefers_best_sized_high_affinity_component(self):
        module = load_module()

        edge_rows = []
        for lncrna_core_id in (10, 11):
            for target_core_id, mean_ba in zip(range(300, 308), range(170, 162, -1), strict=True):
                edge_rows.append(
                    {
                        "lncrna_core_id": lncrna_core_id,
                        "target_core_id": target_core_id,
                        "lncrna_symbol": f"L{lncrna_core_id}",
                        "lncrna_human_ensembl_id": f"ENSG-L{lncrna_core_id}",
                        "target_symbol": f"T{target_core_id}",
                        "human": 1,
                        "chimp": 1,
                        "macaque": 1,
                        "marmoset": 0,
                        "conservation_label": "1110",
                        "conservation_count": 3,
                        "species_count": 3,
                        "supporting_regulation_count": 1,
                        "mean_ba": float(mean_ba),
                        "max_ba": float(mean_ba + 5),
                    }
                )
        for lncrna_core_id in (20, 21):
            for target_core_id, mean_ba in zip(range(400, 408), range(140, 132, -1), strict=True):
                edge_rows.append(
                    {
                        "lncrna_core_id": lncrna_core_id,
                        "target_core_id": target_core_id,
                        "lncrna_symbol": f"L{lncrna_core_id}",
                        "lncrna_human_ensembl_id": f"ENSG-L{lncrna_core_id}",
                        "target_symbol": f"T{target_core_id}",
                        "human": 1,
                        "chimp": 0,
                        "macaque": 1,
                        "marmoset": 1,
                        "conservation_label": "1011",
                        "conservation_count": 3,
                        "species_count": 3,
                        "supporting_regulation_count": 1,
                        "mean_ba": float(mean_ba),
                        "max_ba": float(mean_ba + 4),
                    }
                )

        manifest_row, node_rows, module_edges = module.select_fig2d_community_module(edge_rows)

        self.assertEqual(manifest_row["module_kind"], "community")
        self.assertEqual(manifest_row["lncrna_core_id"], 10)
        self.assertEqual(manifest_row["node_count"], 10)
        self.assertEqual(len(module_edges), 14)
        self.assertEqual(sum(1 for row in node_rows if row["node_role"] == "lncrna"), 2)
        self.assertEqual({row["lncrna_core_id"] for row in module_edges}, {10, 11})

    def test_select_fig3d_conserved_exemplar_prioritizes_multispecies_targets(self):
        module = load_module()

        node_rows = [
            {"core_id": 1, "gene_type": "lncRNA", "human": 1, "chimp": 1, "macaque": 1, "marmoset": 1, "conservation_count": 4},
            {"core_id": 2, "gene_type": "lncRNA", "human": 1, "chimp": 1, "macaque": 1, "marmoset": 0, "conservation_count": 3},
        ]
        edge_rows = [
            {"lncrna_core_id": 1, "target_core_id": 101, "target_symbol": "A", "human": 1, "chimp": 1, "macaque": 1, "marmoset": 1, "conservation_count": 4, "supporting_regulation_count": 4, "mean_ba": 180.0, "max_ba": 200.0},
            {"lncrna_core_id": 1, "target_core_id": 102, "target_symbol": "B", "human": 1, "chimp": 1, "macaque": 1, "marmoset": 0, "conservation_count": 3, "supporting_regulation_count": 3, "mean_ba": 170.0, "max_ba": 190.0},
            {"lncrna_core_id": 1, "target_core_id": 103, "target_symbol": "C", "human": 1, "chimp": 1, "macaque": 0, "marmoset": 1, "conservation_count": 3, "supporting_regulation_count": 3, "mean_ba": 160.0, "max_ba": 180.0},
            {"lncrna_core_id": 2, "target_core_id": 201, "target_symbol": "D", "human": 1, "chimp": 1, "macaque": 1, "marmoset": 0, "conservation_count": 3, "supporting_regulation_count": 3, "mean_ba": 150.0, "max_ba": 170.0},
            {"lncrna_core_id": 2, "target_core_id": 202, "target_symbol": "E", "human": 1, "chimp": 1, "macaque": 0, "marmoset": 0, "conservation_count": 2, "supporting_regulation_count": 2, "mean_ba": 140.0, "max_ba": 165.0},
        ]

        manifest_row, node_manifest_rows, edge_manifest_rows = module.select_fig3d_conserved_exemplar(node_rows, edge_rows)

        self.assertEqual(manifest_row["exemplar_kind"], "conserved")
        self.assertEqual(manifest_row["lncrna_core_id"], 1)
        self.assertEqual([row["target_core_id"] for row in edge_manifest_rows], [101, 102, 103])
        self.assertTrue(all(row["lncrna_core_id"] == 1 for row in edge_manifest_rows))
        self.assertTrue(any(row["node_role"] == "lncrna" for row in node_manifest_rows))

    def test_select_fig3d_rewired_exemplar_prefers_low_jaccard_target_sets(self):
        module = load_module()

        node_rows = [
            {"core_id": 30, "gene_type": "lncRNA", "human": 1, "chimp": 1, "macaque": 1, "marmoset": 1, "conservation_count": 4},
            {"core_id": 40, "gene_type": "lncRNA", "human": 1, "chimp": 1, "macaque": 1, "marmoset": 1, "conservation_count": 4},
        ]
        edge_rows = [
            {"lncrna_core_id": 30, "target_core_id": 501, "target_symbol": "T501", "human": 1, "chimp": 0, "macaque": 0, "marmoset": 0, "conservation_count": 1, "supporting_regulation_count": 1, "mean_ba": 200.0, "max_ba": 210.0},
            {"lncrna_core_id": 30, "target_core_id": 502, "target_symbol": "T502", "human": 1, "chimp": 1, "macaque": 0, "marmoset": 0, "conservation_count": 2, "supporting_regulation_count": 2, "mean_ba": 180.0, "max_ba": 195.0},
            {"lncrna_core_id": 30, "target_core_id": 503, "target_symbol": "T503", "human": 0, "chimp": 1, "macaque": 0, "marmoset": 0, "conservation_count": 1, "supporting_regulation_count": 1, "mean_ba": 190.0, "max_ba": 205.0},
            {"lncrna_core_id": 30, "target_core_id": 504, "target_symbol": "T504", "human": 0, "chimp": 0, "macaque": 1, "marmoset": 1, "conservation_count": 2, "supporting_regulation_count": 2, "mean_ba": 175.0, "max_ba": 188.0},
            {"lncrna_core_id": 30, "target_core_id": 505, "target_symbol": "T505", "human": 0, "chimp": 0, "macaque": 1, "marmoset": 0, "conservation_count": 1, "supporting_regulation_count": 1, "mean_ba": 165.0, "max_ba": 180.0},
            {"lncrna_core_id": 30, "target_core_id": 506, "target_symbol": "T506", "human": 0, "chimp": 0, "macaque": 0, "marmoset": 1, "conservation_count": 1, "supporting_regulation_count": 1, "mean_ba": 160.0, "max_ba": 176.0},
            {"lncrna_core_id": 40, "target_core_id": 601, "target_symbol": "T601", "human": 1, "chimp": 1, "macaque": 1, "marmoset": 1, "conservation_count": 4, "supporting_regulation_count": 4, "mean_ba": 170.0, "max_ba": 182.0},
            {"lncrna_core_id": 40, "target_core_id": 602, "target_symbol": "T602", "human": 1, "chimp": 1, "macaque": 1, "marmoset": 1, "conservation_count": 4, "supporting_regulation_count": 4, "mean_ba": 168.0, "max_ba": 180.0},
        ]

        manifest_row, node_manifest_rows, edge_manifest_rows = module.select_fig3d_rewired_exemplar(node_rows, edge_rows)

        self.assertEqual(manifest_row["exemplar_kind"], "rewired")
        self.assertEqual(manifest_row["lncrna_core_id"], 30)
        self.assertLessEqual(manifest_row["mean_pairwise_jaccard"], 0.35)
        self.assertEqual(len(edge_manifest_rows), 6)
        self.assertTrue(any(row["node_role"] == "lncrna" for row in node_manifest_rows))


if __name__ == "__main__":
    unittest.main()
