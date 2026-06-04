#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/paper/generate_cellgenomics_validation.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"missing module under test: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("generate_cellgenomics_validation", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_tsv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


class GenerateCellGenomicsValidationTests(unittest.TestCase):
    def test_expression_mapping_marks_missing_and_ambiguous_without_zeroing(self):
        module = load_module()

        module_nodes = [
            {"node_id": "lncrna_17738", "node_type": "lncrna", "display_label": "CATG045621"},
            {"node_id": "gene_29927", "node_type": "gene", "display_label": "ATP2B2"},
            {"node_id": "gene_31992", "node_type": "gene", "display_label": "ULK1"},
            {"node_id": "gene_999", "node_type": "gene", "display_label": "AMBIG"},
        ]
        alias_rows = [
            {"external_id": "CATG045621", "core_id": "17738", "gene_symbol": "CATG00000045621.1", "gene_type": "lncrna"},
            {"external_id": "CATG00000045621.1", "core_id": "17738", "gene_symbol": "CATG00000045621.1", "gene_type": "lncrna"},
            {"external_id": "ATP2B2", "core_id": "29927", "gene_symbol": "ATP2B2", "gene_type": "protein_coding"},
            {"external_id": "AMBIG", "core_id": "111", "gene_symbol": "AMBIG_A", "gene_type": "protein_coding"},
            {"external_id": "AMBIG", "core_id": "222", "gene_symbol": "AMBIG_B", "gene_type": "protein_coding"},
        ]
        expression_rows = [
            {"external_id": "CATG00000045621.1", "source": "ENCODE", "context": "K562", "tpm": "2.5"},
            {"external_id": "ATP2B2", "source": "GTEx", "context": "Adipose_Subcutaneous", "tpm": "12.0"},
            {"external_id": "AMBIG", "source": "ENCODE", "context": "K562", "tpm": "8.0"},
        ]

        rows = module.build_expression_support_rows(
            module_nodes,
            expression_rows=expression_rows,
            alias_rows=alias_rows,
            min_tpm=1.0,
        )

        by_key = {
            (row["core_id"], row["source"], row["context"]): row
            for row in rows
        }
        self.assertTrue(by_key[("17738", "ENCODE", "K562")]["expression_supported"])
        self.assertEqual(by_key[("17738", "ENCODE", "K562")]["mapping_status"], "mapped")
        self.assertEqual(by_key[("17738", "ENCODE", "K562")]["expression_tpm"], 2.5)

        self.assertTrue(by_key[("29927", "GTEx", "Adipose_Subcutaneous")]["expression_supported"])
        self.assertEqual(by_key[("31992", "ENCODE", "K562")]["mapping_status"], "missing")
        self.assertIsNone(by_key[("31992", "ENCODE", "K562")]["expression_tpm"])
        self.assertFalse(by_key[("31992", "ENCODE", "K562")]["expression_supported"])

        ambiguous = by_key[("999", "ENCODE", "K562")]
        self.assertEqual(ambiguous["mapping_status"], "ambiguous")
        self.assertIsNone(ambiguous["expression_tpm"])
        self.assertFalse(ambiguous["expression_supported"])

    def test_matched_random_background_preserves_requested_constraints(self):
        module = load_module()

        observed_rows = [
            {"target_gene_symbol": "A", "lncrna_degree_tier": "high", "ba_tier": "BA100", "target_availability": "mappable"},
            {"target_gene_symbol": "B", "lncrna_degree_tier": "high", "ba_tier": "BA100", "target_availability": "mappable"},
        ]
        background_rows = [
            {"target_gene_symbol": "C", "lncrna_degree_tier": "high", "ba_tier": "BA100", "target_availability": "mappable"},
            {"target_gene_symbol": "D", "lncrna_degree_tier": "high", "ba_tier": "BA100", "target_availability": "mappable"},
            {"target_gene_symbol": "E", "lncrna_degree_tier": "low", "ba_tier": "BA100", "target_availability": "mappable"},
        ]

        matched = module.build_matched_random_background(
            observed_rows,
            background_rows,
            matching_fields=["lncrna_degree_tier", "ba_tier", "target_availability"],
            seed=11,
        )

        self.assertEqual(len(matched), len(observed_rows))
        self.assertEqual({row["target_gene_symbol"] for row in matched}, {"C", "D"})
        for row in matched:
            self.assertEqual(row["lncrna_degree_tier"], "high")
            self.assertEqual(row["ba_tier"], "BA100")
            self.assertEqual(row["target_availability"], "mappable")

    def test_functional_coherence_reports_observed_null_percentile_fdr_and_gene_count(self):
        module = load_module()

        module_gene_sets = [
            {"module_id": "flagship_obesity", "genes": ["ULK1", "JMJD1C", "RSF1"]},
            {"module_id": "background_like", "genes": ["ATP2B2", "TDH", "TPPP"]},
        ]
        annotation_rows = [
            {"gene_symbol": "ULK1", "term_id": "GO:0006914", "term_name": "autophagy"},
            {"gene_symbol": "JMJD1C", "term_id": "GO:0006914", "term_name": "autophagy"},
            {"gene_symbol": "RSF1", "term_id": "GO:0006325", "term_name": "chromatin organization"},
            {"gene_symbol": "ATP2B2", "term_id": "GO:0006816", "term_name": "calcium ion transport"},
            {"gene_symbol": "TDH", "term_id": "GO:0006520", "term_name": "amino acid metabolism"},
            {"gene_symbol": "TPPP", "term_id": "GO:0007017", "term_name": "microtubule-based process"},
        ]
        null_gene_sets = [
            {"module_id": "flagship_obesity", "genes": ["ATP2B2", "TDH", "TPPP"]},
            {"module_id": "flagship_obesity", "genes": ["ATP2B2", "TDH", "RSF1"]},
            {"module_id": "background_like", "genes": ["ULK1", "JMJD1C", "RSF1"]},
            {"module_id": "background_like", "genes": ["ULK1", "TDH", "TPPP"]},
        ]

        rows = module.build_functional_coherence_rows(
            module_gene_sets,
            annotation_rows=annotation_rows,
            null_gene_sets=null_gene_sets,
        )

        by_module = {row["module_id"]: row for row in rows}
        flagship = by_module["flagship_obesity"]
        self.assertEqual(flagship["tested_gene_count"], 3)
        self.assertGreater(flagship["observed_score"], flagship["null_mean"])
        self.assertIn("null_p95", flagship)
        self.assertIn("empirical_percentile", flagship)
        self.assertIn("fdr", flagship)
        self.assertLessEqual(flagship["fdr"], 1.0)

    def test_expression_summary_defaults_to_pcg_target_program_scope(self):
        module = load_module()

        rows = [
            {
                "core_id": "lnc1",
                "node_type": "lncrna",
                "source": "GTEx",
                "context": "Liver",
                "mapping_status": "missing",
                "expression_supported": False,
            },
            {
                "core_id": "pcg1",
                "node_type": "protein_coding",
                "source": "GTEx",
                "context": "Liver",
                "mapping_status": "mapped",
                "expression_supported": True,
            },
            {
                "core_id": "pcg2",
                "node_type": "protein_coding",
                "source": "GTEx",
                "context": "Liver",
                "mapping_status": "mapped",
                "expression_supported": False,
            },
        ]

        summary = module.build_expression_summary_rows(rows)

        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["analysis_scope"], "pcg_target_program")
        self.assertEqual(summary[0]["tested_node_count"], 2)
        self.assertEqual(summary[0]["mappable_node_count"], 2)
        self.assertEqual(summary[0]["expression_supported_node_count"], 1)

    def test_atlas_wide_evidence_summary_covers_top_conserved_rewired_and_flagship_modules(self):
        module = load_module()

        ranking_rows = [
            {
                "lncrna_gene_id": "100",
                "lncrna_name": "TOP1",
                "target_count": "20",
                "high_affinity_edge_count": "8",
                "best_edge_conservation_count": "4",
                "rewiring_label": "conserved",
                "epigenomic_support_class": "active_like",
            },
            {
                "lncrna_gene_id": "101",
                "lncrna_name": "TOP2",
                "target_count": "10",
                "high_affinity_edge_count": "2",
                "best_edge_conservation_count": "2",
                "rewiring_label": "conserved",
                "epigenomic_support_class": "other",
            },
        ]
        trait_rows = [
            {
                "candidate_lncRNA": "CONS",
                "candidate_target_count": "12",
                "high_affinity_edges": "5",
                "best_edge_conservation_count": "4",
                "rewiring_label": "conserved",
                "epigenomic_support_class": "bivalent_like",
            },
            {
                "candidate_lncRNA": "REWIRE",
                "candidate_target_count": "7",
                "high_affinity_edges": "1",
                "best_edge_conservation_count": "1",
                "rewiring_label": "rewired",
                "epigenomic_support_class": "other",
            },
        ]
        flagship = {
            "trait_name": "obesity",
            "lncrna_name": "CATG00000045621.1",
            "candidate_targets": "8",
            "high_affinity_edges": "8",
            "best_edge_conservation_count": "2",
            "rewiring_label": "conserved",
            "epigenomic_support_class": "bivalent_like",
            "flagship_targets_with_trait_literature_support_fraction": "0.75",
        }
        null_rows = [
            {
                "conservation_count": "4",
                "observed_edge_count": "8799",
                "null_p95_edge_count": "3206.15",
                "null_iterations": "1000",
            }
        ]

        rows = module.build_atlas_wide_evidence_rows(
            ranking_rows=ranking_rows,
            trait_prioritization_rows=trait_rows,
            flagship_manifest=flagship,
            null_count_rows=null_rows,
            top_n=2,
        )

        scopes = {row["evidence_scope"] for row in rows}
        self.assertIn("top_prioritized_modules", scopes)
        self.assertIn("conserved_modules", scopes)
        self.assertIn("rewired_modules", scopes)
        self.assertIn("obesity_flagship", scopes)
        self.assertIn("edge_conservation_null", scopes)
        self.assertTrue(all("interpretation" in row for row in rows))
        self.assertEqual(
            next(row for row in rows if row["evidence_scope"] == "edge_conservation_null")["null_iterations"],
            1000,
        )

    def test_build_atlas_module_gene_sets_and_matched_nulls_enable_multi_module_coherence(self):
        module = load_module()

        ranking_rows = [
            {"lncrna_gene_id": "100", "lncrna_name": "TOP1"},
        ]
        trait_rows = [
            {"candidate_lncRNA": "REWIRE", "rewiring_label": "rewired", "high_affinity_edges": "2"},
        ]
        case_nodes = [
            {"node_id": "lncrna_17738", "node_type": "lncrna", "display_label": "CATG045621", "value": 8},
            {"node_id": "gene_1", "node_type": "gene", "display_label": "A", "value": 10},
            {"node_id": "gene_2", "node_type": "gene", "display_label": "B", "value": 9},
        ]
        edge_rows = [
            {"lncrna_core_id": "100", "lncrna_symbol": "TOP1", "target_symbol": "A", "max_ba": "120", "conservation_count": "4"},
            {"lncrna_core_id": "100", "lncrna_symbol": "TOP1", "target_symbol": "B", "max_ba": "110", "conservation_count": "3"},
            {"lncrna_core_id": "200", "lncrna_symbol": "REWIRE", "target_symbol": "C", "max_ba": "90", "conservation_count": "1"},
            {"lncrna_core_id": "200", "lncrna_symbol": "REWIRE", "target_symbol": "D", "max_ba": "80", "conservation_count": "1"},
            {"lncrna_core_id": "300", "lncrna_symbol": "BG", "target_symbol": "E", "max_ba": "70", "conservation_count": "2"},
            {"lncrna_core_id": "301", "lncrna_symbol": "BG2", "target_symbol": "F", "max_ba": "60", "conservation_count": "2"},
        ]
        annotation_rows = [
            {"gene_symbol": "A", "term_id": "GO:1", "term_name": "shared"},
            {"gene_symbol": "B", "term_id": "GO:1", "term_name": "shared"},
            {"gene_symbol": "C", "term_id": "GO:2", "term_name": "rewired"},
            {"gene_symbol": "D", "term_id": "GO:3", "term_name": "distinct"},
            {"gene_symbol": "E", "term_id": "GO:4", "term_name": "background"},
            {"gene_symbol": "F", "term_id": "GO:5", "term_name": "background"},
        ]

        module_sets = module.build_atlas_module_gene_sets(
            ranking_rows=ranking_rows,
            trait_prioritization_rows=trait_rows,
            case_nodes=case_nodes,
            edge_rows=edge_rows,
            top_n=1,
            max_genes_per_module=2,
        )
        null_sets = module.build_annotation_matched_null_gene_sets(
            module_sets,
            edge_rows=edge_rows,
            annotation_rows=annotation_rows,
            iterations=5,
            seed=42,
        )
        coherence_rows = module.build_functional_coherence_rows(
            module_sets,
            annotation_rows=annotation_rows,
            null_gene_sets=null_sets,
        )

        self.assertGreaterEqual(len(module_sets), 3)
        self.assertTrue(any(row["module_group"] == "top_prioritized" for row in module_sets))
        self.assertTrue(any(row["module_group"] == "rewired" for row in module_sets))
        self.assertTrue(any(row["module_id"] == "flagship_obesity" for row in module_sets))
        self.assertTrue(null_sets)
        self.assertTrue(all("matching_rule" in row for row in null_sets))
        self.assertEqual({row["module_id"] for row in module_sets}, {row["module_id"] for row in coherence_rows})

    def test_cli_writes_figure6_manifest_metadata_and_supplementary_data(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            fig5_dir = repo_root / "paper_figures/fig5"
            tables_dir = repo_root / "paper_figures/tables"
            supp_dir = repo_root / "paper_figures/supplementary"
            external_dir = repo_root / "paper_figures/external"

            write_tsv(
                fig5_dir / "fig5D_case_manifest.tsv",
                [
                    {
                        "trait_name": "obesity",
                        "lncrna_gene_id": 17738,
                        "lncrna_name": "CATG00000045621.1",
                        "candidate_targets": 3,
                        "high_affinity_edges": 3,
                        "ba_range": "145.99-213.99",
                        "best_edge_conservation_count": 2,
                        "rewiring_label": "conserved",
                        "epigenomic_support_class": "bivalent_like",
                        "flagship_targets_with_trait_literature_support": 2,
                        "flagship_targets_with_trait_literature_support_fraction": 0.666667,
                    }
                ],
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
            write_tsv(
                fig5_dir / "fig5D_case_nodes.tsv",
                [
                    {"node_id": "trait_obesity", "node_type": "trait", "display_label": "Obesity", "value": 3},
                    {"node_id": "lncrna_17738", "node_type": "lncrna", "display_label": "CATG045621", "value": 3},
                    {"node_id": "gene_29927", "node_type": "gene", "display_label": "ATP2B2", "value": 213.99},
                    {"node_id": "gene_31992", "node_type": "gene", "display_label": "ULK1", "value": 168.99},
                    {"node_id": "gene_24529", "node_type": "gene", "display_label": "RSF1", "value": 148.01},
                ],
                ["node_id", "node_type", "display_label", "value"],
            )
            write_tsv(
                fig5_dir / "fig5D_case_edges.tsv",
                [
                    {"source": "trait_obesity", "target": "lncrna_17738", "edge_type": "trait_anchor", "weight": 1.0},
                    {"source": "lncrna_17738", "target": "gene_29927", "edge_type": "regulation", "weight": 213.99},
                    {"source": "lncrna_17738", "target": "gene_31992", "edge_type": "regulation", "weight": 168.99},
                    {"source": "lncrna_17738", "target": "gene_24529", "edge_type": "regulation", "weight": 148.01},
                ],
                ["source", "target", "edge_type", "weight"],
            )
            write_tsv(
                tables_dir / "supp_table1_trait_literature_support.tsv",
                [
                    {
                        "trait_id": 102,
                        "trait_name": "obesity",
                        "unique_target_gene_count": 940,
                        "literature_supported_target_gene_count": 626,
                        "literature_supported_target_fraction": 0.665957,
                        "flagship_lncrna_name": "CATG00000045621.1",
                        "flagship_candidate_target_count": 3,
                        "flagship_targets_with_trait_literature_support": 2,
                        "flagship_targets_with_trait_literature_support_fraction": 0.666667,
                    }
                ],
                [
                    "trait_id",
                    "trait_name",
                    "unique_target_gene_count",
                    "literature_supported_target_gene_count",
                    "literature_supported_target_fraction",
                    "flagship_lncrna_name",
                    "flagship_candidate_target_count",
                    "flagship_targets_with_trait_literature_support",
                    "flagship_targets_with_trait_literature_support_fraction",
                ],
            )
            write_tsv(
                supp_dir / "suppfig7B_null_counts.tsv",
                [
                    {"conservation_count": 4, "observed_edge_count": 8799, "null_mean_edge_count": 91.387, "null_p95_edge_count": 107.0, "null_iterations": 1000}
                ],
                ["conservation_count", "observed_edge_count", "null_mean_edge_count", "null_p95_edge_count", "null_iterations"],
            )
            write_tsv(
                supp_dir / "suppfig7D_degree_null_counts.tsv",
                [
                    {
                        "null_model": "degree_bin_matched_target_permutation",
                        "conservation_count": 4,
                        "observed_edge_count": 8799,
                        "null_mean_edge_count": 130.0,
                        "null_p95_edge_count": 118.0,
                        "null_iterations": 1000,
                        "matching_rule": "species_id;lncrna_degree_tier;target_degree_tier",
                    }
                ],
                [
                    "null_model",
                    "conservation_count",
                    "observed_edge_count",
                    "null_mean_edge_count",
                    "null_p95_edge_count",
                    "null_iterations",
                    "matching_rule",
                ],
            )
            write_tsv(
                supp_dir / "suppfig7E_marmoset_downsampling.tsv",
                [
                    {
                        "null_model": "marmoset_edge_count_downsampling_target_permutation",
                        "reference_species": "marmoset",
                        "reference_edge_count": 31798,
                        "downsampled_edge_count_per_species": 31798,
                        "conservation_count": 4,
                        "observed_mean_edge_count": 227.81,
                        "observed_median_edge_count": 228.0,
                        "observed_p05_edge_count": 203.0,
                        "observed_p95_edge_count": 254.0,
                        "null_mean_edge_count": 3.517,
                        "null_median_edge_count": 3.0,
                        "null_p05_edge_count": 1.0,
                        "null_p95_edge_count": 7.0,
                        "null_iterations": 1000,
                        "sampling_rule": "human;chimp;macaque downsampled to marmoset edge count",
                    }
                ],
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
            write_tsv(
                external_dir / "cellgenomics_expression_support.tsv",
                [
                    {"external_id": "CATG00000045621.1", "source": "ENCODE", "context": "K562", "tpm": 2.5},
                    {"external_id": "ATP2B2", "source": "GTEx", "context": "Adipose_Subcutaneous", "tpm": 12.0},
                    {"external_id": "ULK1", "source": "GTEx", "context": "Liver", "tpm": 8.0},
                    {"external_id": "RSF1", "source": "ENCODE", "context": "HepG2", "tpm": 4.0},
                ],
                ["external_id", "source", "context", "tpm"],
            )
            write_tsv(
                external_dir / "cellgenomics_functional_terms.tsv",
                [
                    {"gene_symbol": "ULK1", "term_id": "GO:0006914", "term_name": "autophagy"},
                    {"gene_symbol": "RSF1", "term_id": "GO:0006325", "term_name": "chromatin organization"},
                    {"gene_symbol": "ATP2B2", "term_id": "GO:0006816", "term_name": "calcium ion transport"},
                ],
                ["gene_symbol", "term_id", "term_name"],
            )

            rc = module.main([
                "--repo-root",
                str(repo_root),
                "--out-dir",
                str(repo_root / "paper_figures"),
                "--generated-at",
                "2026-04-24T00:00:00Z",
                "--source-commit",
                "0" * 40,
            ])
            self.assertEqual(rc, 0)

            required = [
                repo_root / "paper_figures/fig6/fig6A_atlas_wide_evidence.tsv",
                repo_root / "paper_figures/fig6/fig6A_atlas_wide_evidence.svg",
                repo_root / "paper_figures/fig6/fig6A_atlas_wide_evidence.png",
                repo_root / "paper_figures/fig6/fig6A_metadata.json",
                repo_root / "paper_figures/fig6/fig6B_expression_support.tsv",
                repo_root / "paper_figures/fig6/fig6B_expression_support.svg",
                repo_root / "paper_figures/fig6/fig6B_expression_support.png",
                repo_root / "paper_figures/fig6/fig6B_metadata.json",
                repo_root / "paper_figures/fig6/fig6C_functional_coherence.tsv",
                repo_root / "paper_figures/fig6/fig6C_functional_coherence.svg",
                repo_root / "paper_figures/fig6/fig6C_functional_coherence.png",
                repo_root / "paper_figures/fig6/fig6C_metadata.json",
                repo_root / "paper_figures/fig6/fig6D_flagship_evidence_card.tsv",
                repo_root / "paper_figures/fig6/fig6D_flagship_evidence_card.svg",
                repo_root / "paper_figures/fig6/fig6D_flagship_evidence_card.png",
                repo_root / "paper_figures/fig6/fig6D_metadata.json",
                repo_root / "paper_figures/fig3/fig3E_null_calibration.tsv",
                repo_root / "paper_figures/fig3/fig3E_null_calibration.svg",
                repo_root / "paper_figures/fig3/fig3E_null_calibration.png",
                repo_root / "paper_figures/fig3/fig3E_metadata.json",
                repo_root / "paper_figures/tables/supp_data_expression_support.tsv",
                repo_root / "paper_figures/tables/supp_data_functional_coherence.tsv",
                repo_root / "paper_figures/tables/supp_data_flagship_module.tsv",
                repo_root / "paper_figures/tables/table7_known_evidence_benchmark.tsv",
                repo_root / "paper_figures/cell_genomics_manifest.tsv",
            ]
            for path in required:
                self.assertTrue(path.exists(), path)
                self.assertGreater(path.stat().st_size, 0, path)

            metadata = json.loads((repo_root / "paper_figures/fig6/fig6B_metadata.json").read_text(encoding="utf-8"))
            self.assertIn("external_data_versions", metadata)
            self.assertIn("generation_parameters", metadata)
            self.assertEqual(metadata["generation_parameters"]["analysis_mode"], "pcg_target_program_mappable_subset")
            self.assertEqual(metadata.get("title"), "PCG target-program expression context")
            self.assertIn("missing or ambiguous, not as zero expression", "\n".join(metadata.get("notes", [])))

            fig6a_metadata = json.loads((repo_root / "paper_figures/fig6/fig6A_metadata.json").read_text(encoding="utf-8"))
            fig6c_metadata = json.loads((repo_root / "paper_figures/fig6/fig6C_metadata.json").read_text(encoding="utf-8"))
            fig6d_metadata = json.loads((repo_root / "paper_figures/fig6/fig6D_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(fig6a_metadata.get("title"), "Atlas-wide benchmarking and robustness summary")
            self.assertEqual(fig6c_metadata.get("title"), "GO coherence benchmarking")
            self.assertEqual(fig6d_metadata.get("title"), "Obesity flagship candidate evidence card")

            fig6b_rows = read_tsv(repo_root / "paper_figures/fig6/fig6B_expression_support.tsv")
            self.assertTrue(fig6b_rows)
            self.assertTrue(all(row["analysis_scope"] == "pcg_target_program" for row in fig6b_rows))
            self.assertTrue(all(int(row["tested_node_count"]) == 3 for row in fig6b_rows))

            fig6a_svg = (repo_root / "paper_figures/fig6/fig6A_atlas_wide_evidence.svg").read_text(encoding="utf-8")
            fig6b_svg = (repo_root / "paper_figures/fig6/fig6B_expression_support.svg").read_text(encoding="utf-8")
            fig6c_svg = (repo_root / "paper_figures/fig6/fig6C_functional_coherence.svg").read_text(encoding="utf-8")
            fig6d_svg = (repo_root / "paper_figures/fig6/fig6D_flagship_evidence_card.svg").read_text(encoding="utf-8")
            self.assertIn("Atlas-wide benchmarking and robustness summary", fig6a_svg)
            self.assertNotIn("independent evidence", fig6a_svg)
            self.assertIn("PCG target-program expression context", fig6b_svg)
            self.assertIn("missing != zero", fig6b_svg)
            self.assertIn("GO coherence benchmarking", fig6c_svg)
            self.assertNotIn("Functional coherence versus", fig6c_svg)
            self.assertIn("Obesity flagship candidate evidence card", fig6d_svg)
            self.assertIn("Lead lncRNA", fig6d_svg)
            self.assertIn("High-affinity edges", fig6d_svg)
            self.assertIn("bivalent-like", fig6d_svg)
            self.assertIn("Best PCG expression context", fig6d_svg)
            self.assertNotIn("Best PCG target-program expression context", fig6d_svg)

            fig3e_svg = (repo_root / "paper_figures/fig3/fig3E_null_calibration.svg").read_text(encoding="utf-8")
            self.assertIn("Main four-species calibration", fig3e_svg)
            self.assertIn("Target-permutation p95", fig3e_svg)
            self.assertIn("Degree-bin p95", fig3e_svg)
            self.assertIn("Candidate core-pair edges (log scale)", fig3e_svg)
            self.assertIn("Marmoset downsampling", fig3e_svg)
            self.assertIn("8,799", fig3e_svg)
            self.assertIn("91.4", fig3e_svg)
            self.assertIn("107", fig3e_svg)
            self.assertIn("118", fig3e_svg)
            self.assertIn("228", fig3e_svg)
            self.assertIn("203-254", fig3e_svg)
            self.assertIn("null p95 = 7", fig3e_svg)
            self.assertNotIn("E. Observed-vs-null edge conservation calibration", fig3e_svg)

            fig3e_rows = read_tsv(repo_root / "paper_figures/fig3/fig3E_null_calibration.tsv")
            by_metric = {row["metric"]: row for row in fig3e_rows}
            self.assertEqual(by_metric["target_permutation_null_p95"]["value"], "107")
            self.assertEqual(by_metric["degree_bin_matched_p95"]["value"], "118")
            self.assertEqual(by_metric["marmoset_downsampling_observed_median"]["value"], "228")
            self.assertEqual(by_metric["marmoset_downsampling_observed_p05_p95"]["value"], "203-254")
            self.assertEqual(by_metric["marmoset_downsampling_null_p95"]["value"], "7")

            manifest_rows = read_tsv(repo_root / "paper_figures/cell_genomics_manifest.tsv")
            outputs = {row["output_file"] for row in manifest_rows}
            self.assertIn("paper_figures/fig6/fig6A_atlas_wide_evidence.tsv", outputs)
            self.assertIn("paper_figures/fig6/fig6B_expression_support.tsv", outputs)
            self.assertIn("paper_figures/tables/table7_known_evidence_benchmark.tsv", outputs)
            self.assertTrue(all((repo_root / row["output_file"]).exists() for row in manifest_rows))

            fig3e_manifest = [row for row in manifest_rows if row["figure_panel"] == "Figure3E"]
            self.assertTrue(fig3e_manifest)
            self.assertTrue(any("suppfig7D_degree_null_counts.tsv" in row["source_table"] for row in fig3e_manifest))
            self.assertTrue(any("suppfig7E_marmoset_downsampling.tsv" in row["source_table"] for row in fig3e_manifest))

            fig6a_rows = read_tsv(repo_root / "paper_figures/fig6/fig6A_atlas_wide_evidence.tsv")
            scopes = {row["evidence_scope"] for row in fig6a_rows}
            self.assertIn("degree_bin_matched_edge_null", scopes)

            benchmark_rows = read_tsv(repo_root / "paper_figures/tables/table7_known_evidence_benchmark.tsv")
            benchmark_scopes = {row["evidence_scope"] for row in benchmark_rows}
            self.assertIn("degree_bin_matched_edge_null", benchmark_scopes)


if __name__ == "__main__":
    unittest.main()
