# Cell Genomics Competitiveness Boost Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the current Cell Genomics-ready draft from case-level independent support to atlas-wide computational validation suitable for presubmission inquiry and stronger initial submission.

**Architecture:** Extend the existing reviewer-facing package rather than creating a separate analysis stack. Reuse `scripts/paper/generate_cellgenomics_validation.py`, frozen `paper_figures/` TSVs, and processed external evidence inputs to add atlas-wide evidence summaries, stronger null calibration, and clearer target-program-only expression framing.

**Tech Stack:** Python 3, `unittest`, `matplotlib`, TSV/JSON manifests, existing `scripts/paper/` figure-generation conventions.

## Technical Assessment

The expert feedback is technically sound for the current manuscript state. The current package is strong enough for a Cell Genomics presubmission inquiry, but formal submission remains vulnerable to three reviewer objections:

1. Figure 6 is mostly obesity-case support rather than atlas-wide validation.
2. Expression support currently evaluates PCG target programs, not direct lncRNA-PCG co-expression.
3. Functional coherence and null calibration are currently too lightweight for a Cell Genomics-level computational genomics claim.

The next round should therefore prioritize computational strengthening before any wet-lab decision.

## Task 1: Add Atlas-Wide Independent Evidence Summary

**Files:**
- Modify: `scripts/paper/generate_cellgenomics_validation.py`
- Modify: `scripts/tests/test_generate_cellgenomics_validation.py`
- Output: `paper_figures/fig6/fig6A_atlas_evidence_summary.tsv`
- Output: `paper_figures/fig6/fig6A_atlas_evidence_summary.svg`
- Output: `paper_figures/tables/supp_data_atlas_evidence_summary.tsv`

**Steps:**
1. Write failing tests for an atlas-wide summary builder that compares observed modules against matched background.
2. Input top modules from `paper_figures/tables/table4_trait_prioritization.tsv` and `paper_figures/fig5/fig5B_ranking_matrix.tsv`.
3. Compute summary rows for all prioritized modules, conserved modules, rewired modules, and the obesity flagship module.
4. Report known trait-gene support overlap, expression-supported target fraction, and functional coherence distribution.
5. Render a compact Figure 6A replacement or extension that makes Figure 6 atlas-wide before the obesity case card.
6. Update `cell_genomics_manifest.tsv` with all new outputs.

**Verification:**

```bash
python3 -m unittest scripts.tests.test_generate_cellgenomics_validation
```

Expected: atlas-wide evidence tests pass and all manifest outputs exist.

## Task 2: Strengthen Figure 3E Null Calibration to 1,000 Permutations

**Files:**
- Modify: `scripts/paper/generate_batch1_figures.py`
- Modify: `scripts/tests/test_generate_batch1_figures.py`
- Regenerate: `paper_figures/supplementary/suppfig7B_null_counts.tsv`
- Regenerate: `paper_figures/supplementary/suppfig7C_null_pairwise.tsv`
- Regenerate: `paper_figures/fig3/fig3E_null_calibration.tsv`

**Steps:**
1. Write a failing test asserting the default null iteration count is at least `1000`.
2. Change the Supplementary Figure 7 null default from 100 to 1,000 permutations.
3. Keep deterministic `rng_seed=42`.
4. Regenerate batch-1 robustness assets or add a targeted null-regeneration path if full batch-1 is too slow.
5. Regenerate the Cell Genomics validation package so Figure 3E uses the 1,000-permutation output.
6. Update Methods wording from 100 permutations to 1,000 permutations.

**Verification:**

```bash
python3 -m unittest scripts.tests.test_generate_batch1_figures scripts.tests.test_generate_cellgenomics_validation
```

Expected: null TSVs report `null_iterations = 1000`.

## Task 3: Clarify and Improve lncRNA Expression Mapping

**Files:**
- Modify: `scripts/paper/generate_cellgenomics_validation.py`
- Modify: `scripts/tests/test_generate_cellgenomics_validation.py`
- Modify: `docs/paper/manuscript.md`
- Input/Output: `paper_figures/external/cellgenomics_expression_aliases.tsv`
- Input/Output: `paper_figures/tables/supp_data_expression_support.tsv`

**Steps:**
1. Write failing tests for target-program-only framing when the lead lncRNA remains unmapped.
2. Add optional coordinate/alias mapping fields for CATG IDs if a processed FANTOM/GENCODE mapping TSV is supplied.
3. If the lead lncRNA maps, report lncRNA expression and target PCG co-expression compatibility.
4. If it remains unmapped, explicitly label Figure 6B and Methods as `PCG target-program expression support`.
5. Ensure missing or ambiguous lncRNA aliases remain `missing` or `ambiguous`, never zero.

**Verification:**

```bash
python3 -m unittest scripts.tests.test_generate_cellgenomics_validation scripts.tests.test_paper_manuscript_docs
```

Expected: rendered manuscript does not imply direct lncRNA-PCG co-expression unless lncRNA expression is actually mapped.

## Task 4: Expand Functional Coherence Beyond the Obesity Case

**Files:**
- Modify: `scripts/paper/generate_cellgenomics_validation.py`
- Modify: `scripts/tests/test_generate_cellgenomics_validation.py`
- Output: `paper_figures/fig6/fig6C_module_coherence_distribution.tsv`
- Output: `paper_figures/tables/supp_data_module_coherence_distribution.tsv`

**Steps:**
1. Write failing tests for multi-module coherence output with observed score, null mean, null p95, empirical percentile, FDR, and tested gene count.
2. Build module gene sets from top prioritized modules in `table4_trait_prioritization.tsv`.
3. Generate matched nulls preserving target gene-set size and annotation availability.
4. Report distribution-level enrichment for top modules, conserved modules, and rewired modules.
5. Keep the obesity module as a representative case, not the only evidence layer.

**Verification:**

```bash
python3 -m unittest scripts.tests.test_generate_cellgenomics_validation
```

Expected: Figure 6C supports a module distribution claim, not a single-case claim.

## Task 5: Add Known-Evidence Benchmark Layer

**Files:**
- Modify: `scripts/paper/generate_cellgenomics_validation.py`
- Modify: `scripts/tests/test_generate_cellgenomics_validation.py`
- Output: `paper_figures/tables/supp_data_known_evidence_benchmark.tsv`

**Steps:**
1. Start with existing `trait_gene_associations` / Supplementary Table 1 provenance.
2. Add optional processed curated lncRNA-target / lncRNA-disease TSV inputs if available.
3. Implement mappable-only overlap accounting with matched random background.
4. Report mapping rate separately from evidence support rate.
5. Do not infer absence of evidence from unmapped lncRNAs.

**Verification:**

```bash
python3 -m unittest scripts.tests.test_generate_cellgenomics_validation
```

Expected: known-evidence benchmark outputs include observed overlap, matched background, mapping rate, and support rate.

## Task 6: Update Manuscript and Presubmission Package

**Files:**
- Modify: `docs/paper/manuscript.md`
- Modify: `docs/paper/figures.md`
- Modify: `docs/paper/README.md`
- Create: `docs/paper/presubmission_inquiry.md`
- Regenerate: `docs/paper/build/manuscript_rendered.md`
- Regenerate: `docs/paper/build/manuscript_rendered.docx`

**Steps:**
1. Rewrite Figure 6 text from case-level evidence to atlas-wide independent support, with obesity as the representative case.
2. Make expression wording explicit: direct lncRNA-PCG co-expression only if lncRNA expression mapping succeeds; otherwise target-program-level support.
3. Keep GO coherence as supportive unless FDR is clearly strong across modules.
4. Add a presubmission inquiry draft centered on conceptual advance, comparative discovery, and evidence integration.
5. Re-render Markdown and DOCX.

**Verification:**

```bash
python3 -m unittest scripts.tests.test_paper_manuscript_docs
python3 scripts/paper/render_manuscript.py
python3 scripts/paper/export_manuscript_docx.py
```

Expected: rendered manuscript includes Figure 6 atlas-wide language and avoids overclaiming.

## Wet-Lab Decision Gate

Wet-lab validation is not required for the next computational strengthening pass. After Tasks 1-6, decide whether to pursue one focused validation:

- CRISPRi/ASO knockdown plus qPCR of the 8 predicted targets.
- ChIRP-qPCR / CHART-qPCR at 1-2 predicted triplex target regions.
- Public RNA-DNA interaction dataset lookup if direct experiments are not feasible.

This should remain outside the current code package unless real data are available.
