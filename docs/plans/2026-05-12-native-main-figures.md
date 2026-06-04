# Native Main Figures Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Render main-text Figures 2-5 as native single matplotlib figures instead of panel PNG composites.

**Architecture:** Keep existing panel TSV outputs as the frozen data source. Add a native main-figure renderer that reads those TSVs and draws all panels into one matplotlib Figure per main figure. Keep the old composite assets available for reference, but switch DOCX export for Figures 2-5 to the native outputs.

**Tech Stack:** Python, matplotlib, seaborn, NetworkX, PIL-free native figure rendering, unittest.

### Task 1: Add Failing Tests For Native Figure Assets

**Files:**
- Modify: `scripts/tests/test_export_manuscript_docx.py`
- Modify: `scripts/tests/test_generate_composite_figures.py` or create a new focused test module if cleaner.

**Steps:**
1. Assert Figure 2-5 DOCX image references point to `paper_figures/native/figureN_native.png`.
2. Assert Figure 1 and Figure 6 may still use existing composite PNGs.
3. Assert native metadata contains `rendering_mode: native_matplotlib_single_figure`.
4. Run the tests and verify they fail because the native renderer/export path does not exist yet.

### Task 2: Implement Native Main-Figure Renderer

**Files:**
- Create: `scripts/paper/generate_native_main_figures.py`

**Steps:**
1. Read existing TSV inputs for Figures 2-5 from `paper_figures/fig2`, `fig3`, `fig4`, and `fig5`.
2. Draw Figure 2 panels A-D into one matplotlib figure.
3. Draw Figure 3 panels A-E into one matplotlib figure.
4. Draw Figure 4 baseline strip plus panels A-D into one matplotlib figure.
5. Draw Figure 5 panels A-D into one matplotlib figure.
6. Save each figure as `paper_figures/native/figureN_native.svg`, `.png`, and `.metadata.json`.
7. Metadata must list TSV inputs and state that no panel PNG/SVG image assets were pasted.

### Task 3: Switch DOCX Export To Native Assets

**Files:**
- Modify: `scripts/paper/export_manuscript_docx.py`

**Steps:**
1. Call the native renderer before markdown-to-DOCX export.
2. Set Figure 2-5 assets to `paper_figures/native/figureN_native.png`.
3. Leave Figure 1 and Figure 6 on existing composite PNGs for now.
4. Verify generated markdown contains native image paths for Figures 2-5.

### Task 4: Regenerate And Verify

**Commands:**
- `python3 scripts/paper/generate_native_main_figures.py`
- `python3 scripts/paper/export_manuscript_docx.py`
- `python3 -m unittest scripts.tests.test_generate_composite_figures scripts.tests.test_export_manuscript_docx scripts.tests.test_paper_manuscript_docs`

**Checks:**
1. Native PNGs exist and are nonblank.
2. DOCX still contains 6 embedded PNGs.
3. Figure 2-5 embedded assets come from native PNGs, not composite PNGs.
4. Old panel-border code may remain only in legacy composite script and must not affect Figure 2-5 DOCX output.
