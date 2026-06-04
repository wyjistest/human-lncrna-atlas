#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MANUSCRIPT_PATH = REPO_ROOT / "docs/paper/manuscript.md"
FIGURES_PATH = REPO_ROOT / "docs/paper/figures.md"
README_PATH = REPO_ROOT / "docs/paper/README.md"
SNAPSHOT_PATH = REPO_ROOT / "docs/paper/submission_snapshot.md"
BIB_PATH = REPO_ROOT / "docs/paper/references.bib"
CSL_PATH = REPO_ROOT / "docs/paper/cell.csl"
SUBMISSION_PACKAGE_PATH = REPO_ROOT / "docs/paper/cell_genomics_submission_package.md"
PRESUBMISSION_EMAIL_PATH = REPO_ROOT / "docs/paper/presubmission_email.md"
RESOURCE_SAFE_TITLE = (
    "Triplex-informed lncRNA–gene candidate networks reveal edge-level "
    "conservation and rewiring across primates"
)


class PaperManuscriptDocsTests(unittest.TestCase):
    def test_manuscript_has_submission_frontmatter_and_csl(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        self.assertTrue(text.startswith("---\n"))
        self.assertIn("bibliography: docs/paper/references.bib", text)
        self.assertIn("csl: docs/paper/cell.csl", text)
        self.assertNotIn("csl: docs/paper/nature.csl", text)
        self.assertIn("link-citations: true", text)

        self.assertTrue(CSL_PATH.exists())
        self.assertIn("<style", CSL_PATH.read_text(encoding="utf-8"))

    def test_abstract_frontloads_comparative_claim_without_inventory_details(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")
        abstract = text.split("## Abstract", 1)[1].split("**Keywords:**", 1)[0].strip()

        self.assertNotIn("across seven human cell lines", abstract)
        self.assertNotIn("For the paper package", abstract)
        for phrase in [
            "49 histone-mark experiments",
            "3,343,903",
            "histone peaks",
            "7 DNase-HS experiments",
            "1,223,622",
            "DNase peaks",
            "56 experiments",
            "4,567,525",
            "peaks",
        ]:
            self.assertNotIn(phrase, abstract)
        self.assertIn("804,630", abstract)
        self.assertIn("Jaccard **0.79**", abstract)
        self.assertIn("Jaccard **0.37**", abstract)
        self.assertIn("8,799", abstract)
        self.assertIn("empirical p < 0.001", abstract)
        self.assertIn("This atlas prioritizes", abstract)
        self.assertIn("without establishing causal regulation", abstract)
        self.assertIn("Gene Ontology (GO)-based module-coherence benchmarking", abstract)
        self.assertNotIn("GO coherence", abstract)
        self.assertIn("main-text human-only epigenomic baseline", text)
        self.assertIn("fixed human-only epigenomic baseline", text)
        self.assertIn("CTCF", text)
        self.assertIn("H4K20me1", text)

        self.assertEqual(1, len([paragraph for paragraph in abstract.split("\n\n") if paragraph.strip()]))

    def test_manuscript_uses_pcg_terminology_and_submission_facing_wording(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("protein-coding genes (PCGs)", text)
        self.assertIn("lncRNA–PCG", text)
        self.assertNotIn("lncRNA-PCG", text)
        self.assertNotIn("lncRNA-to-protein-coding-gene", text)
        self.assertIn("candidate lncRNA–PCG edge", text)
        self.assertNotIn("**Keywords:** lncRNA, triplex, orthology, regulatory network", text)
        self.assertIn("BA ≥ 100", text)
        self.assertNotIn("BA >= 100", text)
        self.assertNotIn("current snapshot", text)
        self.assertNotIn("current frozen flagship example", text)
        self.assertNotIn("candidate disease-relevant lncRNAs", text)
        self.assertNotIn("paper-facing epigenomic baseline", text)
        self.assertNotIn("`CTCF`", text)
        self.assertNotIn("`H4K20me1`", text)
        self.assertNotIn("`DNase-HS`", text)
        self.assertNotIn("`H3K36me3`", text)
        self.assertNotIn("`804,630`", text)
        self.assertNotIn("`56`", text)
        self.assertNotIn("`4,567,525`", text)
        self.assertNotIn("`A549`", text)
        self.assertNotIn("`GM12878`", text)
        self.assertNotIn("`H1-hESC`", text)
        self.assertNotIn("`HepG2`", text)
        self.assertNotIn("`HMEC`", text)
        self.assertNotIn("`K562`", text)

    def test_results_chain_includes_cell_genomics_benchmarking_section(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn(
            f"# {RESOURCE_SAFE_TITLE}",
            text,
        )

        for heading in [
            "### 1. Constructing orthology-aware, triplex-informed candidate lncRNA–PCG edge networks from prior trait-associated gene catalogs",
            "### 2. Global network architecture prioritizes hub lncRNAs and modular target gene programs",
            "### 3. Conserved and rewired candidate lncRNA–PCG edges across primates",
            "### 4. Human epigenomic context stratifies candidate loci",
            "### 5. Trait-centered subnetworks prioritize candidate trait-relevant lncRNAs",
            "### 6. External evidence layers benchmark and contextualize prioritized modules",
        ]:
            self.assertIn(heading, text)
        self.assertNotIn("### 6. Web resource and programmatic access", text)

    def test_cell_genomics_benchmarking_wording_is_present_and_conservative(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        for phrase in [
            "node conservation is not edge conservation",
            "External evidence layers benchmark and contextualize prioritized modules",
            "mappable subset",
            "matched-null",
            "ENCODE and GTEx",
            "GO coherence benchmarking",
            "Figure 6",
            "empirical p < 0.001",
        ]:
            self.assertIn(phrase, text)

        self.assertNotIn("validated regulation", text)
        self.assertNotIn("causal proof", text)
        self.assertNotIn("### 6. Independent evidence supports prioritized candidate lncRNA–PCG modules", text)
        self.assertNotIn("Figure 6 therefore provides independent support", text)

    def test_data_and_code_availability_reframes_companion_as_secondary_layer(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("Human LncRNA Atlas Companion", text)
        self.assertIn("reproducibility and evidence-inspection layer", text)
        self.assertRegex(text, r"commit `[0-9a-f]{40}`")
        self.assertIn("Supplementary Figure 6", text)
        self.assertIn("Query interface", text)
        self.assertIn("Network view", text)
        self.assertIn("Genome-browser view", text)
        self.assertIn("Export / API workflow", text)
        self.assertIn("repository-local backend exposes an OpenAPI schema", text)
        self.assertIn("when run locally", text)
        self.assertIn("No public deployment URL is used in this manuscript", text)
        self.assertIn("A frozen archival package has been prepared at the GitHub commit recorded above", text)
        self.assertIn("will be deposited at Zenodo prior to peer review", text)
        self.assertIn("Data and Code Availability statement at submission", text)
        self.assertNotIn("will be deposited at Zenodo or Figshare before publication", text)
        self.assertNotIn("Deployed instances of the backend expose", text)
        self.assertNotIn("Submission exports should pin", text)
        self.assertNotIn("Before journal submission", text)

    def test_formal_submission_archive_todo_does_not_claim_missing_doi(self):
        readme = README_PATH.read_text(encoding="utf-8")
        snapshot = SNAPSHOT_PATH.read_text(encoding="utf-8")

        self.assertIn("Formal initial submission archive checklist", readme)
        self.assertIn("v1.0-cellgenomics-submission", readme)
        self.assertIn("Zenodo/Figshare DOI", readme)
        self.assertIn("final GitHub release and Zenodo/Figshare DOI", snapshot)
        self.assertNotIn("A frozen archival copy is available at [DOI]", readme)
        self.assertNotIn("A frozen archival copy is available at [DOI]", snapshot)

    def test_internal_strategy_notes_move_out_of_manuscript(self):
        manuscript = MANUSCRIPT_PATH.read_text(encoding="utf-8")
        readme = README_PATH.read_text(encoding="utf-8")
        snapshot = SNAPSHOT_PATH.read_text(encoding="utf-8")

        for phrase in [
            "Author note:",
            "Conservative title alternatives",
            "Recommended content:",
            "Final panel set:",
            "This section should",
            "The strongest version of this section should",
            "The final manuscript must",
            "Submission Freeze Checklist",
            "Before submission, the manuscript package must unify",
            "Recommended workflow:",
        ]:
            self.assertNotIn(phrase, manuscript)

        self.assertIn("Title decision log", readme)
        self.assertIn(RESOURCE_SAFE_TITLE, readme)
        self.assertNotIn("Conservative title alternatives", readme)
        self.assertIn("Submission package checklist", snapshot)

    def test_manuscript_uses_pandoc_citations_and_bibliography_file(self):
        manuscript = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        self.assertRegex(manuscript, r"@[A-Za-z0-9_:-]+")
        self.assertIn("## References", manuscript)
        self.assertIn("::: {#refs}", manuscript)
        self.assertNotIn("References (placeholder)", manuscript)
        self.assertNotIn("TBC.", manuscript)

        self.assertTrue(BIB_PATH.exists())
        bib = BIB_PATH.read_text(encoding="utf-8")
        for key in [
            "@article{statello2021",
            "@article{mattick2023",
            "@article{hon2017",
            "@article{frankish2021",
            "@article{mondal2015",
            "@article{buske2012",
            "@article{necsulea2014",
            "@article{moore2020",
            "@article{roadmap2015",
        ]:
            self.assertIn(key, bib)
        self.assertNotIn("Harrison, Paul W. and others", bib)
        self.assertIn("Harrison, Peter W. and Amode, M Ridwan", bib)
        self.assertIn("Yates, Andrew D", bib)

    def test_result4_and_methods_lock_context_cohorts_and_observation_wording(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn(
            "The all-edge cohort was used to summarize baseline mark-overlap signatures without an additional BA cutoff.",
            text,
        )
        self.assertIn(
            "The high-affinity prioritization cohort was generated with `min_ba=100`.",
            text,
        )
        self.assertIn(
            "distinct overlapped `regulation_id` counts per mark-by-cell-line combination",
            text,
        )
        self.assertIn("human-only epigenomic context layer", text)
        self.assertNotIn("fold_enrichment DESC", text)
        self.assertIn(
            "active-like non-bivalent candidate observations",
            text,
        )
        self.assertNotIn("active-like non-bivalent loci", text)
        self.assertNotIn("bivalent-like loci", text)

    def test_methods_record_orthology_and_triplex_provenance(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("Infernal-derived homology assignments", text)
        self.assertIn("Ensembl-derived ortholog export assignments", text)
        self.assertIn("LongTarget-derived prediction tables", text)
        self.assertIn("archived upstream triplex workflow", text)
        self.assertIn("does not re-run triplex prediction during manuscript generation", text)
        self.assertIn("Best_Site_BA", text)
        self.assertNotIn("etl/import_regulations.py", text)
        self.assertNotIn("etl/sample_inputs/human_batch_human.tsv", text)
        self.assertNotIn("resultAllLongTarget", text)
        self.assertNotIn("resultMinusLongTarget", text)
        self.assertNotIn("analyze_peaks_binding_affinity.py", text)

    def test_manuscript_uses_conservative_candidate_wording_for_comparative_claims(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("conserved candidate core-pair patterns", text)
        self.assertIn("lineage-specific candidate rewiring patterns", text)
        self.assertIn("edge-level conservation is more selective than node-level conservation", text)
        self.assertIn("orthologous nodes can be broadly retained while their candidate lncRNA–PCG edges are lost, gained, or rewired", text)
        self.assertIn("Conserved candidate lncRNA–PCG edges were defined", text)
        self.assertNotIn("Conserved regulatory edges were defined", text)
        self.assertIn("### 3. Conserved and rewired candidate lncRNA–PCG edges across primates", text)
        self.assertNotIn("### 3. Conserved and rewired candidate lncRNA–PCG edges across primate evolution", text)
        self.assertNotIn("conserved regulatory cores", text)
        self.assertNotIn("lineage-specific rewiring patterns", text)
        self.assertNotIn("persistent regulatory cores", text)
        self.assertNotIn("regulatory conservation is more stringent", text)
        self.assertNotIn("candidate edge conservation is more stringent", text)

    def test_manuscript_includes_figure_legends_section(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("## Figure Legends", text)
        for heading in [
            "### Figure 1.",
            "### Figure 2.",
            "### Figure 3.",
            "### Figure 4.",
            "### Figure 5.",
            "### Figure 6.",
        ]:
            self.assertIn(heading, text)

    def test_methods_include_triplex_and_epigenomic_reproducibility_anchors(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        for phrase in [
            "Best_Site_BA",
            "target_chromosome",
            "target_start",
            "target_end",
            "flanking=10000",
            "promoter_window=2000",
            "min_ba=100",
            "overlap_type",
            "distance_to_tss",
            "overlap_bp",
            "overlap_percentage",
            "active-like non-bivalent",
            "computational predictions",
            "all-edge cohort",
            "high-affinity prioritization cohort",
            "gene-centered layer was used to summarize promoter-proximal and gene-body chromatin context",
            "direct spatial intersection",
            "predicted triplex target region",
            "`networkx` 3.2.1",
            "eigenvector centrality was evaluated on the full undirected weighted projection",
            "mean_ba",
            "activating histone mark",
            "The upstream frozen marmoset LongTarget prediction input contains approximately 50,000 candidate rows",
            "31,798 orthology-mappable marmoset species-edge rows",
            "upstream LongTarget input pipeline coverage",
            "rather than a plotting or manuscript-generation cap",
            "triplex-informed candidate lncRNA–PCG edge networks across four primate species",
            "marmoset-edge-count downsampling sensitivity",
            "independently downsampled without replacement",
            "with non-null binding affinity and orthology-mappable core-pair assignments",
            "observed statistic was computed directly from the randomly downsampled edge sets",
            "corresponding null statistic was computed by applying within-species target permutation",
            "1,000 random draws with random seed 42",
            "hub breadth may be influenced by transcript length, repeat content, GC composition, and triplex-compatible motif opportunity",
        ]:
            self.assertIn(phrase, text)

        self.assertNotIn("mv_lncrna_chipseq_overlaps", text)
        self.assertNotIn("GET /api/v1/export/chipseq-overlaps", text)
        self.assertNotIn("GET /api/v1/export/disease-network", text)
        self.assertNotIn("stable core-pair-ordering sample", text)
        self.assertNotIn("deterministic core-pair-sorted downsampled network", text)
        self.assertNotIn("The frozen marmoset prediction set contains 50,000 candidate edges with non-null binding affinity", text)
        self.assertNotIn("triplex-informed candidate lncRNA–PCG regulatory networks across four primate species", text)

    def test_manuscript_uses_en_dash_for_result2_target_range(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("300–540", text)
        self.assertNotIn("300-540", text)

    def test_figure4_is_explicitly_human_only_in_results_and_legends(self):
        manuscript = MANUSCRIPT_PATH.read_text(encoding="utf-8")
        figures = FIGURES_PATH.read_text(encoding="utf-8")

        phrase = "human-only epigenomic context layer"
        self.assertIn(phrase, manuscript)
        self.assertIn(phrase, figures)

    def test_figure5_explains_fixed_flagship_trait_selection_rule(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("unique lncRNA count, unique target gene count, and maximum BA", text)
        self.assertIn("obesity ranked first", text)
        self.assertIn("conserved-edge and non-other epigenomic-context filters", text)

    def test_results_and_docs_frontload_calibration_and_trait_literature_context(self):
        manuscript = MANUSCRIPT_PATH.read_text(encoding="utf-8")
        figures = FIGURES_PATH.read_text(encoding="utf-8")

        self.assertIn("Figure 3E moves the compact observed-vs-null calibration into the main figure", manuscript)
        self.assertIn("within-species target-permutation null models", manuscript)
        self.assertIn("Downsampling summaries used 1,000 random draws with random seed 42", manuscript)
        self.assertIn("percentile-interpolated edge-count bounds can be non-integer", manuscript)
        self.assertIn("Supplementary Table 1", manuscript)
        self.assertIn("literature-backed trait-gene context", manuscript)
        self.assertIn("frozen trait-gene association layer", manuscript)
        self.assertIn("literature_support = TRUE", manuscript)
        self.assertIn("Supplementary Table 1 — Trait-level literature-backed target context for flagship prioritization", figures)
        self.assertIn("Figure 6 — External evidence layers benchmark and contextualize prioritized modules", figures)
        self.assertIn("Compact observed-vs-null calibration summary moved into the main-text figure", figures)
        self.assertNotIn("when reviewer-facing robustness support is needed", figures)

    def test_trait_centered_methods_use_trait_gene_layer_wording(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("The trait-gene layer joins `trait_gene_associations`", text)
        self.assertNotIn("The disease-gene layer joins", text)

    def test_supplementary_figure7_is_listed_for_robustness_analyses(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("Supplementary Figure 7", text)
        self.assertIn("BA sensitivity", text)
        self.assertIn("null comparisons", text)
        self.assertIn("interpolated null p95 of approximately **107**", text)
        self.assertIn("pairwise target-permutation null details", text)

    def test_figure1_legend_disambiguates_panel_b_node_counts(self):
        manuscript = MANUSCRIPT_PATH.read_text(encoding="utf-8")
        figures = FIGURES_PATH.read_text(encoding="utf-8")

        phrase = "this panel reports orthology-mapped catalog node counts for lncRNAs and PCGs"
        self.assertIn(phrase, manuscript)
        self.assertIn(phrase, figures)

    def test_figure4_legend_uses_inspection_wording(self):
        manuscript = MANUSCRIPT_PATH.read_text(encoding="utf-8")
        figures = FIGURES_PATH.read_text(encoding="utf-8")

        phrase = "Representative local epigenomic tracks allow prioritized candidate loci to be inspected"
        self.assertIn(phrase, manuscript)
        self.assertIn(phrase, figures)
        self.assertNotIn("Representative local epigenomic tracks place prioritized loci", manuscript)
        self.assertNotIn("Representative local epigenomic tracks place prioritized loci", figures)

    def test_figure_legends_avoid_internal_submission_snapshot_paths(self):
        manuscript = MANUSCRIPT_PATH.read_text(encoding="utf-8")
        figures = FIGURES_PATH.read_text(encoding="utf-8")

        self.assertNotIn("submission-facing metrics fixed in `docs/paper/submission_snapshot.md`", manuscript)
        self.assertNotIn("submission-facing metrics fixed in `docs/paper/submission_snapshot.md`", figures)
        self.assertIn("The frozen analysis snapshot shown here includes four primate species", manuscript)
        self.assertIn("The frozen analysis snapshot shown here includes four primate species", figures)
        self.assertIn("main-text human-only epigenomic baseline", manuscript)
        self.assertIn("main-text human-only epigenomic baseline", figures)
        self.assertNotIn("main-text epigenomic baseline of **56** experiments", manuscript)

    def test_figure4_legend_drops_duplicate_prioritization_sentence(self):
        manuscript = MANUSCRIPT_PATH.read_text(encoding="utf-8")
        figures = FIGURES_PATH.read_text(encoding="utf-8")

        duplicate_phrase = "Figure 4 prioritized overlap views keep BA ≥ 100 as a prioritization zone rather than a universal inclusion threshold."
        polished_phrase = "In Figure 4, BA ≥ 100 is used only as a prioritization zone within the human-only epigenomic context layer, not as a universal inclusion threshold."
        self.assertIn(polished_phrase, manuscript)
        self.assertIn("26 of 54 possible cell-line x mark combinations", manuscript)
        self.assertNotIn(duplicate_phrase, manuscript)
        self.assertNotIn(duplicate_phrase, figures)

    def test_figures_doc_frames_figure6_as_external_benchmarking(self):
        text = FIGURES_PATH.read_text(encoding="utf-8")

        self.assertIn("Figure 6 — External evidence layers benchmark and contextualize prioritized modules", text)
        self.assertIn("Cell Genomics external benchmarking figure", text)
        self.assertIn("Human LncRNA Atlas Companion remains Supplementary Figure 6", text)
        self.assertNotIn("Figure 6 is now the Cell Genomics independent support figure", text)

    def test_cell_genomics_docs_frame_figure6_as_atlas_wide_target_program_context(self):
        manuscript = MANUSCRIPT_PATH.read_text(encoding="utf-8")
        figures = FIGURES_PATH.read_text(encoding="utf-8")

        self.assertIn("atlas-wide external evidence", manuscript)
        self.assertIn("top prioritized, conserved, rewired, and obesity flagship modules", manuscript)
        self.assertIn("PCG target-program expression context", manuscript)
        self.assertIn("target program rather than direct lncRNA–PCG co-expression", manuscript)
        self.assertIn("target-program-level only", manuscript)
        self.assertIn("limited module-level coherence", manuscript)
        self.assertIn("degree-bin matched null", manuscript)
        self.assertIn("A degree-bin matched target-permutation null is reported in Supplementary Figure 7D", manuscript)
        self.assertIn("Across the evaluated module classes, evidence layers were summarized separately", manuscript)
        self.assertIn("repository-frozen ENCODE RNA-seq input slot", manuscript)
        self.assertNotIn("reviewer-supplied ENCODE RNA-seq slot", manuscript)
        self.assertIn("atlas-wide benchmarking summary", figures)
        self.assertIn("obesity flagship as a representative case card", figures)
        self.assertIn("(E) Observed-vs-null calibration", manuscript)
        self.assertIn("degree-bin matched target-permutation p95 of 118 indicated as a stricter calibration", manuscript)
        self.assertIn("p95 of 118 indicated as a stricter calibration", manuscript)
        self.assertIn("compares 8,799 observed shared core-pair edges", manuscript)
        self.assertIn("uses log-scale y-axes and compares 8,799 observed shared core-pair edges", manuscript)
        self.assertIn("marmoset-edge-count random downsampling sensitivity in Supplementary Figure 7E", manuscript)
        self.assertIn("observed median remained **228** shared core-pair edges", manuscript)
        self.assertIn("p05-p95 **203-254**", manuscript)
        self.assertIn("matched target-permutation null p95 of **7**", manuscript)
        self.assertIn("Supplementary Figure 7E reports a marmoset-edge-count random downsampling sensitivity", manuscript)
        self.assertIn("observed four-species median remained 228 shared core-pair edges (p05-p95 203-254)", manuscript)
        self.assertIn("above the matched target-permutation null p95 of 7", manuscript)
        self.assertNotIn("2,007", manuscript)
        self.assertIn("626 of 940", manuscript)
        self.assertIn("6 of 8 targets", manuscript)
        self.assertIn("obesity trait layer reports 626 of 940 obesity-linked target genes", manuscript)
        self.assertIn("displayed flagship subset reports 6 of 8 targets", manuscript)
        self.assertIn(
            "Panel (A) summarizes the full candidate-edge binding-affinity distribution and highlights the high-affinity prioritization zone at BA ≥ 100",
            manuscript,
        )
        self.assertIn(
            "(B) Unadjusted target-core breadth prioritizes candidate broad hubs",
            manuscript,
        )
        self.assertIn("not normalized for transcript length, GC content, repeat content, or triplex-compatible motif opportunity", manuscript)
        self.assertIn("observed lower bound (p05 = 203) remained well above the matched null p95 of 7", manuscript)
        self.assertIn("hub breadth and network-centrality analyses prioritize a subset of lncRNAs", manuscript)
        self.assertIn("### Figure 2. Global architecture of primate candidate lncRNA–gene networks", manuscript)
        self.assertIn("Ranking lncRNAs by unique target-core breadth prioritized a small set of candidate broad hubs", manuscript)
        self.assertIn("Hub breadth is compared with eigenvector centrality", manuscript)
        self.assertIn("Representative filtered subnetworks are shown instead of dense whole-network visualizations", manuscript)
        self.assertIn("Gene Ontology (GO)-based module-coherence benchmarking", manuscript)
        self.assertIn("GTEx (Genotype-Tissue Expression) v8", manuscript)
        self.assertIn("ENCODE (Encyclopedia of DNA Elements)", manuscript)
        self.assertIn("transcripts per million (TPM)", manuscript)
        self.assertIn("false discovery rate (FDR)", manuscript)
        self.assertIn("DNase I hypersensitive sites (DNase-HS)", manuscript)
        self.assertIn("Figure 6 summarizes atlas-wide external evidence", manuscript)
        self.assertIn("processed GTEx v8 median-expression summaries for the Figure 6B PCG targets", manuscript)
        self.assertIn("PCG target-program expression context", manuscript)
        self.assertIn("lncRNA alias missing is treated as missing, not zero", manuscript)
        self.assertIn("1 of 11 module entries exceeded the matched-null p95", manuscript)
        self.assertIn("no module survived FDR < 0.1", manuscript)
        self.assertIn("Human LncRNA Atlas Companion local interface and programmatic access", manuscript)
        self.assertIn("Human LncRNA Atlas Companion local interface and programmatic access", figures)
        self.assertIn("column-normalized visualization only and not a regulatory effect size", manuscript)
        self.assertIn("14 displayed nodes", manuscript)
        self.assertIn("188 candidate edges", manuscript)
        self.assertIn("8 displayed targets", manuscript)
        self.assertIn("8 high-affinity edges", manuscript)
        self.assertIn("(A)", manuscript)
        self.assertIn("(D)", manuscript)
        self.assertNotIn("identifies lncRNAs with unusually broad target coverage", manuscript)
        self.assertNotIn("Ranking lncRNAs by unique target-core breadth identified a small set of broad hubs", manuscript)
        self.assertNotIn("the inferred primate regulatory networks are summarized", manuscript)
        self.assertNotIn("high-affinity zone at BA ≥ 100, highlights lncRNAs", manuscript)
        self.assertNotIn("hub breadth and network-centrality analyses identify a subset of lncRNAs", manuscript)
        self.assertNotIn("### Figure 2. Global architecture of primate lncRNA regulatory networks", manuscript)
        self.assertNotIn("Figure 6 now summarizes", manuscript)
        self.assertNotIn("Figure 5D PCG targets", manuscript)

    def test_cell_genomics_submission_package_draft_exists(self):
        self.assertTrue(SUBMISSION_PACKAGE_PATH.exists(), f"missing submission package draft: {SUBMISSION_PACKAGE_PATH}")

        text = SUBMISSION_PACKAGE_PATH.read_text(encoding="utf-8")
        self.assertIn("## Highlights", text)
        self.assertIn("## In Brief", text)
        self.assertIn("## eTOC Blurb", text)
        self.assertIn("## Graphical Abstract Concept", text)
        self.assertIn("## Key Resources Table Draft", text)
        self.assertIn("Lead Contact", text)
        self.assertIn("Author Contributions", text)
        self.assertIn("Competing Interests", text)
        self.assertIn("Zenodo/Figshare DOI", text)
        self.assertIn("## Full Submission Robustness Checklist", text)
        self.assertIn("Confirmed current Supplementary Figure 7E values", text)
        self.assertIn("228 (203-254) observed four-species shared core-pair edges", text)
        self.assertIn("matched null p95 7", text)
        self.assertIn("Re-verify if the marmoset edge set or random seed is regenerated", text)
        self.assertIn(
            "Robustness analyses for edge-level conservation, rewiring, degree structure, and species-coverage sensitivity",
            text,
        )
        self.assertIn("Hub target-breadth normalization: current status is addressed", text)
        self.assertIn("Figure 2B legend caveat and Discussion Limitation 3", text)
        self.assertIn("Consider quantitative transcript-length, repeat, GC, or triplex-motif-opportunity controls only if reviewers push back", text)
        self.assertIn("coordinate-based expression rescue", text)
        self.assertIn("Keep the Human LncRNA Atlas Companion positioned as local-only", text)
        self.assertIn("unless the authors provide and verify a public deployment URL", text)
        self.assertIn("must remain open before formal full submission", text)
        self.assertIn("Cell CSL", text)
        self.assertIn("docs/paper/cell.csl", text)
        self.assertNotIn("Replace current Nature CSL", text)
        self.assertIn("## Cover Letter Draft", text)
        self.assertIn("## Suggested Reviewers / Excluded Reviewers", text)
        self.assertIn("## Open Science / Inclusion and Diversity Statement", text)
        self.assertIn("| REAGENT or RESOURCE | SOURCE | IDENTIFIER | NOTES |", text)
        self.assertIn("**Software and algorithms**", text)
        self.assertIn("**Deposited data**", text)
        self.assertIn("**Other**", text)
        self.assertNotIn("Highlight:", text)
        self.assertIn(f"Title: `{RESOURCE_SAFE_TITLE}`", text)
        self.assertNotIn("Title: `Edge-level conservation and rewiring of primate lncRNA regulatory networks`", text)
        highlights_block = text.split("## Highlights", 1)[1].split("## In Brief", 1)[0]
        highlights = [
            line.removeprefix("- ").strip()
            for line in highlights_block.splitlines()
            if line.startswith("- ")
        ]
        self.assertEqual(4, len(highlights))
        self.assertIn("Four-species shared edges (8,799) exceed target-permutation null p95 (~107)", highlights)
        self.assertIn("Trait-centered subnetworks nominate obesity-linked lncRNAs for follow-up", highlights)
        self.assertTrue(all(len(line) <= 85 for line in highlights))
        self.assertIn("Use the In Brief text above as the eTOC blurb", text)
        self.assertIn("Option A: add orthogonal RNA-chromatin or perturbation evidence", text)
        self.assertIn("Option B: maintain the current evidence package", text)
        self.assertIn("GO coherence as a supplementary benchmarking layer", text)
        self.assertNotIn("Before formal initial submission, choose one path", text)
        self.assertNotIn("Keep GO coherence as a supplementary benchmarking layer if no stronger orthogonal evidence is added", text)

    def test_manuscript_uses_cell_press_resource_availability_structure(self):
        text = MANUSCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn("## Resource Availability", text)
        self.assertIn("### Lead Contact", text)
        self.assertIn("### Materials Availability", text)
        self.assertIn("### Data and Code Availability", text)
        self.assertLess(text.index("### Lead Contact"), text.index("### Materials Availability"))
        self.assertLess(text.index("### Materials Availability"), text.index("### Data and Code Availability"))
        self.assertIn("Further information and requests for resources should be directed to the Lead Contact", text)
        self.assertIn("Lead Contact details remain TBD until verified by the submitting authors", text)
        self.assertIn("This study did not generate new unique reagents", text)
        self.assertIn("will be deposited at Zenodo prior to peer review", text)
        self.assertNotIn("The frozen archival package is available at Zenodo, DOI: XXXX", text)

    def test_presubmission_inquiry_exists_and_emphasizes_cell_genomics_advance(self):
        path = REPO_ROOT / "docs/paper/presubmission_inquiry.md"
        self.assertTrue(path.exists(), f"missing presubmission inquiry draft: {path}")

        text = path.read_text(encoding="utf-8")
        self.assertIn("# Cell Genomics Presubmission Inquiry Draft", text)
        self.assertIn(RESOURCE_SAFE_TITLE, text)
        self.assertNotIn("Orthology-aware, triplex-informed reconstruction of candidate lncRNA-regulatory networks across primates", text)
        self.assertIn("node conservation is not edge conservation", text)
        self.assertIn("edge-level lncRNA–PCG conservation and rewiring", text)
        self.assertLess(text.index("Figure 3"), text.index("Figure 6"))
        self.assertIn("804,630 predicted lncRNA–PCG relationships", text)
        self.assertIn("human-chimpanzee node Jaccard 0.79 versus edge Jaccard 0.37", text)
        self.assertIn("8,799 observed four-species core-pair edges", text)
        self.assertIn("null mean 91.4", text)
        self.assertIn("empirical p < 0.001", text)
        self.assertIn("Figure 3 observed-vs-null calibration", text)
        self.assertIn("external evidence layers benchmark and contextualize prioritized modules", text)
        self.assertIn("Cell Genomics", text)
        self.assertIn("presubmission inquiry", text)

    def test_presubmission_email_draft_is_ready_without_invented_metadata(self):
        self.assertTrue(PRESUBMISSION_EMAIL_PATH.exists(), f"missing presubmission email draft: {PRESUBMISSION_EMAIL_PATH}")

        text = PRESUBMISSION_EMAIL_PATH.read_text(encoding="utf-8")
        self.assertIn("To: cellgenomics@cell.com", text)
        self.assertIn(f"Subject: Presubmission inquiry: {RESOURCE_SAFE_TITLE}", text)
        self.assertIn("Dear Cell Genomics editorial team,", text)
        self.assertIn("We would like to ask whether Cell Genomics would consider a full submission", text)
        self.assertIn("node conservation is not edge conservation", text)
        self.assertIn("804,630 predicted lncRNA–PCG relationships", text)
        self.assertIn("human-chimpanzee node Jaccard 0.79 versus edge Jaccard 0.37", text)
        self.assertIn("8,799 observed four-species core-pair edges", text)
        self.assertIn("null mean 91.4", text)
        self.assertIn("empirical p < 0.001", text)
        self.assertIn("Figure 3", text)
        self.assertIn("Figure 6", text)
        self.assertIn("external benchmarking and contextualization rather than causal evidence", text)
        self.assertIn("reproducibility and evidence-inspection layer", text)
        self.assertIn("[Lead Contact Name]", text)
        self.assertIn("[Affiliation]", text)
        self.assertIn("[Email]", text)
        self.assertNotIn("Zenodo DOI:", text)
        self.assertNotIn("A frozen archival copy is available", text)
        body = text.split("Subject:", 1)[1]
        word_count = len(body.split())
        self.assertLessEqual(word_count, 750)


if __name__ == "__main__":
    unittest.main()
