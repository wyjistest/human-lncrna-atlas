# Paper (Article) Draft

This directory contains the working draft of a research-first academic **article** on orthology-aware, triplex-informed primate lncRNA regulatory networks, with the web platform treated as a secondary delivery layer.

Paper-facing epigenomic baseline is fixed to `8 core histone marks + DNase-HS`. The current repository snapshot additionally contains `CTCF` and `H4K20me1` human-track coverage, but those remain extended inventory outside the main-text baseline. Orthology provenance, conserved-edge definitions, and BA strategy are also frozen. See `docs/paper/submission_snapshot.md` for the fixed counts, subset rules, and method definitions.

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

This writes:

- `paper_figures/shared/`: frozen snapshot JSON + shared TSV working tables
- `paper_figures/fig1/`: Figure 1D KPI table + revised draft SVG/PNG + metadata
- `paper_figures/fig2/`: Figure 2A/B/C source tables, including `fig2A_summary.tsv`, plus revised draft SVG/PNG + metadata
- `paper_figures/fig3/`: Figure 3A/B/C source tables + revised draft SVG/PNG + metadata
