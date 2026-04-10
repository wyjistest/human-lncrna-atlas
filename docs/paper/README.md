# Paper (Article) Draft

This directory contains the working draft of a research-first academic **article** on orthology-aware, triplex-informed primate lncRNA regulatory networks, with the web platform treated as a secondary delivery layer.

Paper-facing epigenomic baseline is fixed to `8 core histone marks + DNase-HS`. The current repository snapshot additionally contains `CTCF` and `H4K20me1` human-track coverage, but those remain extended inventory outside the main-text baseline. Orthology provenance, conserved-edge definitions, and BA strategy are also frozen. See `docs/paper/submission_snapshot.md` for the fixed counts, subset rules, and method definitions.

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
