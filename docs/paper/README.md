# Paper (Article) Draft

This directory contains the working draft of a Cell Genomics-facing **Resource / atlas** manuscript on orthology-aware, triplex-informed primate lncRNA–gene candidate networks, with the web platform treated as a secondary delivery layer.

Main-text epigenomic baseline is fixed to `8 core histone marks + DNase-HS`. The current repository snapshot additionally contains CTCF and H4K20me1 human-track coverage, but those remain extended inventory outside the main-text baseline. Orthology provenance, conserved-edge definitions, and BA strategy are also frozen. See `docs/paper/submission_snapshot.md` for the fixed counts, subset rules, and method definitions.

The Cell Genomics submission upgrade adds Figure 6 as an atlas-wide external benchmarking and contextualization figure and records reviewer-facing traceability in `paper_figures/cell_genomics_manifest.tsv` plus `paper_figures/cell_genomics_external_data_manifest.tsv`. Figure 6B is framed as PCG target-program expression context, and Supplementary Figure 7 / Figure 3E null calibration defaults to 1,000 permutations with `rng_seed=42`; Supplementary Figure 7D adds the stricter degree-bin matched target-permutation sensitivity layer.


## Internal Manuscript Notes

### Title decision log

Selected Resource-safe concept-forward title for the Cell Genomics-facing draft:

- `Triplex-informed lncRNA–gene candidate networks reveal edge-level conservation and rewiring across primates`

Earlier titles over-emphasized regulatory-network language; the current manuscript keeps candidate status in the title while preserving the comparative finding.

The repository-facing strategy, freeze notes, and figure-planning details live outside `docs/paper/manuscript.md` so that the manuscript draft can remain submission-facing.

## Companion Site Mapping

The current frontend is aligned to the paper-facing narrative as follows:

- `Overview`: frozen snapshot + live provenance
- `Traits`: trait-associated catalogs and associations
- `Trait-centered Networks`: candidate subnetworks across up to 4 species
- `Conservation & Rewiring`: conserved / rewired candidate edges
- `Epigenomic Context`: overlap and co-localization around candidate loci
- `Evidence Hub`: figure-aligned summaries corresponding to the manuscript figures

This mapping is intentionally narrative-first: public labels favor `trait`, `candidate edge`, `conservation & rewiring`, and `epigenomic context` over older toolbox-era labels.

## Files

- `docs/paper/manuscript.md`: main manuscript draft (Markdown; can be converted to PDF/LaTeX via Pandoc if needed).
- `docs/paper/submission_snapshot.md`: frozen paper-facing inventory and subset rules used by the manuscript and figure plan.
- `plan/2025-12-30_16-57-53-epigenetic-reg-network-article.md`: execution plan for writing + analysis.
- `notebooks/`: Phase 6 research notebooks + pre-generated results/figures used by the manuscript.

## Figures / Results Sources

Current manuscript figures reference assets under:

- `notebooks/figures/`
- `notebooks/results/`

If you regenerate figures, keep filenames stable or update references in `docs/paper/manuscript.md`.

## Regenerating Analysis (optional)

The notebooks expect the backend API to be available locally:

```bash
cd frontend/backend
python3 -m uvicorn main:app --reload --port 8000
```

Then follow `notebooks/README.md`.

You can also regenerate a lightweight Markdown summary from the precomputed CSV outputs:

```bash
python3 scripts/paper/generate_results_summary.py
```

To regenerate the batch-1 paper figures and shared source tables used by the
research-first narrative skeleton and revised main-text drafts (Figure 1D,
Figure 2A/B/C, Figure 3A/B/C):

```bash
python3 scripts/paper/generate_batch1_figures.py
```

To pin figure metadata to a specific frozen revision while keeping the generated
timestamp deterministic:

```bash
python3 scripts/paper/generate_batch1_figures.py \
  --generated-at 2026-04-15T06:20:58Z \
  --source-commit bcd67cc
```

This writes:

- `paper_figures/shared/`: frozen snapshot JSON + shared TSV working tables
- `paper_figures/fig1/`: Figure 1D KPI table + revised draft SVG/PNG + metadata
- `paper_figures/fig2/`: Figure 2A/B/C source tables, including `fig2A_summary.tsv`, plus revised draft SVG/PNG + metadata
- `paper_figures/fig3/`: Figure 3A/B/C source tables + revised draft SVG/PNG + metadata

Additional inputs used by the batch-1 generator:

- `docs/paper/fig2b_aliases.tsv`: paper-facing aliases for the Figure 2B top hubs; the current draft uses neutral `Hub-XX (short accession)` labels, and leaving `display_label` blank still falls back to the automatic shortened accession
- `Figure 2C` keeps the eigenvector-centrality view but now labels only the top five ranked lncRNA hubs in the current centrality ordering, reducing plot clutter without changing the underlying metric
- metadata output now records `source_commit`, meaning the git revision used to generate the assets; this is intentionally separate from the later commit that may add regenerated files to the branch

To regenerate the Cell Genomics benchmarking package (Figure 3E, Figure 6, Supplementary Data, and reviewer manifests) from compact processed inputs:

```bash
python3 scripts/paper/rebuild_cellgenomics_package.py --skip-manuscript
```

Primary outputs:

- `paper_figures/fig3/fig3E_null_calibration.*`
- `paper_figures/fig6/fig6A_*` through `fig6D_*`
- `paper_figures/tables/supp_data_expression_support.tsv`
- `paper_figures/tables/supp_data_functional_coherence.tsv`
- `paper_figures/tables/supp_data_flagship_module.tsv`
- `paper_figures/tables/table7_known_evidence_benchmark.tsv`
- `paper_figures/cell_genomics_manifest.tsv`
- `paper_figures/cell_genomics_external_data_manifest.tsv`

### Formal initial submission archive checklist

Before a full Cell Genomics initial submission, create a frozen GitHub release tag such as `v1.0-cellgenomics-submission`, archive that release through Zenodo/Figshare, and replace the manuscript's provisional archival-release sentence with the resulting Zenodo/Figshare DOI. Until that DOI exists, the manuscript should not claim that an archival copy is already available.

## Rendering a Submission-Prep Draft

The source manuscript now carries Pandoc YAML frontmatter (`bibliography`, `csl`, and `link-citations`) so that the submission-prep draft can move through a Pandoc-native pipeline. Because the current environment provides Pandoc without built-in citeproc support, the repository uses `scripts/paper/pandoc_citation_filter.py` as a local compatibility layer while still keeping `docs/paper/cell.csl` and `docs/paper/references.bib` in the manuscript source.

Use the repository-local Pandoc wrapper to generate a bibliography-expanded Markdown draft for review:

```bash
python3 scripts/paper/render_manuscript.py
```

Requirements:

- `pandoc` must be available on `PATH`

Default output:

- `docs/paper/build/manuscript_rendered.md`

The source of truth remains `docs/paper/manuscript.md`; the rendered file is a derived review artifact with inline citations expanded, the bibliography written out explicitly, and the YAML frontmatter removed from the review copy.

To export a Word manuscript whose body paragraphs default to full justification, use:

```bash
python3 scripts/paper/export_manuscript_docx.py
```

Default outputs:

- `docs/paper/build/manuscript_rendered.md`
- `docs/paper/build/reference_justified.docx`
- `docs/paper/build/manuscript_rendered.docx`

The DOCX exporter regenerates a Pandoc reference document on each run and forces the `Normal`, `BodyText`, and `FirstParagraph` paragraph styles to use `w:jc="both"`, so the main manuscript text opens in Word as two-sided justified paragraphs rather than left-aligned body text.
