# Paper Method Freeze Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finalize the remaining paper-level method freeze items: orthology provenance, conserved-edge definition, and binding-affinity threshold strategy.

**Architecture:** Extend the existing paper freeze note (`docs/paper/submission_snapshot.md`) into the authoritative methods-freeze document. Then update manuscript and figure-planning docs so they inherit the same fixed definitions instead of referring to unresolved placeholders.

**Tech Stack:** Markdown documentation under `docs/paper/`, ETL import script references, backend conservation/export router references

### Task 1: Freeze orthology provenance

**Files:**
- Modify: `docs/paper/submission_snapshot.md`
- Reference: `etl/import_ortholog_data.py`
- Reference: `docs/paper/data_dictionary.md`

**Step 1: Define the orthology source actually supported by the repo**

Record that the paper uses repository-frozen import tables `ortholog_lnc_table.csv` and `ortholog_gene_table.csv`, imported through `etl/import_ortholog_data.py` v1.0 (dated 2025-11-20), rather than claiming an external orthology release version not preserved in the repo.

**Step 2: Define the normalization rule**

Record how `core_id` is assigned from CATG / ENSG identifiers, including ENSG offsetting and the preference for human entries when setting canonical symbols.

### Task 2: Freeze conserved-node and conserved-edge definitions

**Files:**
- Modify: `docs/paper/submission_snapshot.md`
- Reference: `frontend/backend/app/core/utils.py`
- Reference: `frontend/backend/app/routers/conservation.py`

**Step 1: Freeze node conservation**

Record that node conservation is computed from `genes.core_id` presence across species, yielding a 4-bit label in the fixed species order.

**Step 2: Freeze edge conservation**

Record that conserved edges are defined at the `(lncrna_core_id, target_core_id)` level, with species presence determined by at least one regulation linking that core pair in a species.

**Step 3: Freeze exclusion rules**

Record that genes lacking `core_id` are excluded from cross-species node/edge conservation analyses.

### Task 3: Freeze BA threshold strategy

**Files:**
- Modify: `docs/paper/submission_snapshot.md`
- Reference: `notebooks/01_high_affinity_analysis.ipynb`
- Reference: `notebooks/02_conservation_patterns.ipynb`
- Reference: `notebooks/03_epigenetic_marks.ipynb`
- Reference: `frontend/backend/app/routers/export.py`
- Reference: `frontend/backend/app/routers/analysis.py`

**Step 1: Freeze the high-affinity threshold**

Record that high-affinity and epigenomic-overlap analyses use `BA >= 100`.

**Step 2: Freeze the conservation overview rule**

Record that the current conservation overview notebook/export uses no BA filter and instead requires `min_species_count >= 2`.

**Step 3: Freeze the interpretation rule**

Record a fixed two-tier strategy: all-edge conservation overview for Figure 3, `BA >= 100` for high-affinity / overlap prioritization analyses, and BA-as-ranking for current disease-network exports unless a future figure explicitly applies a stricter filtered export.

### Task 4: Propagate the frozen rules

**Files:**
- Modify: `docs/paper/manuscript.md`
- Modify: `docs/paper/figures.md`
- Modify: `docs/paper/README.md`

**Step 1: Replace unresolved method placeholders**

Update manuscript methods, results planning text, and freeze checklist so they point to fixed definitions rather than “TBC” wording.

**Step 2: Align figure planning**

Update Figure 3 / Table 3 language to match the fixed core-pair conservation definition and BA strategy.

### Task 5: Verify the freeze

**Files:**
- Verify: `docs/paper/submission_snapshot.md`
- Verify: `docs/paper/manuscript.md`
- Verify: `docs/paper/figures.md`

**Step 1: Run targeted grep**

Check that orthology provenance, conserved-edge definition, and BA strategy are no longer described as unresolved in the paper docs.

**Step 2: Run diff formatting checks**

Ensure changed files pass `git diff --check`.

**Step 3: Summarize what still remains unfrozen**

List only any leftover items that cannot be defended from current repo evidence.
