# Paper (Article) Draft

This directory contains the working draft of an academic **article** describing the *Human LncRNA Atlas* dataset and platform (cross-species lncRNA regulatory relationships across four primates, with integrated epigenomic context).

## Files

- `docs/paper/manuscript.md`: main manuscript draft (Markdown; can be converted to PDF/LaTeX via Pandoc if needed).
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
