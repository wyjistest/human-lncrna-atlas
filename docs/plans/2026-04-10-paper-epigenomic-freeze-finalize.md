# Paper Epigenomic Freeze Finalization Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finalize the paper-facing epigenomic submission rule so the manuscript no longer uses provisional wording for mark inventory, extended tracks, or comparable cell-line subsets.

**Architecture:** Create one paper-local freeze document that records the fixed main-text inventory and subset rules, then update manuscript, figure checklist, and entry docs to cite the same decisions. Keep `docs/CURRENT_STATUS.md` as the full current inventory, but stop treating the paper baseline as negotiable.

**Tech Stack:** Markdown documentation under `docs/` and `docs/paper/`

### Task 1: Lock the final rules

**Files:**
- Create: `docs/paper/submission_snapshot.md`
- Reference: `docs/CURRENT_STATUS.md`
- Reference: `docs/ENCODE_DATA_GUIDE.md`

**Step 1: Freeze the main-text inventory**

Record that the main-text epigenomic baseline is fixed to eight core histone marks plus DNase-HS, excluding CTCF and H4K20me1 from baseline totals.

**Step 2: Freeze the exact counts**

Record the baseline totals:
- 8 core histone marks = 49 experiments, 3,343,903 peaks
- DNase-HS = 7 experiments, 1,223,622 peaks
- combined baseline = 56 experiments, 4,567,525 peaks

**Step 3: Freeze the comparable cell-line subset**

Record that cross-mark comparisons default to `A549`, `GM12878`, `H1-hESC`, `HepG2`, `HMEC`, and `K562`, while `MCF-7` is excluded from multi-mark comparisons because the frozen hg19 baseline only includes `H3K4me3` there.

### Task 2: Update paper documents to fixed wording

**Files:**
- Modify: `docs/paper/manuscript.md`
- Modify: `docs/paper/figures.md`
- Modify: `docs/paper/README.md`

**Step 1: Replace provisional wording**

Change “default / unless / if frozen” style phrases into fixed submission rules.

**Step 2: Inject the exact inventory totals**

Update the abstract, Figure 4 planning text, Methods inventory text, and Table 2 planning text to use the frozen counts and subset rule.

**Step 3: Link to the freeze document**

Point paper entry docs to `docs/paper/submission_snapshot.md` as the authoritative paper-facing freeze note.

### Task 3: Update repository-facing status docs

**Files:**
- Modify: `docs/CURRENT_STATUS.md`
- Optional: `README.md`

**Step 1: Clarify paper subset rule**

State that the main-text multi-mark comparison subset uses the six cell lines with broader frozen baseline coverage, excluding `MCF-7` from cross-mark comparisons.

**Step 2: Keep repo-level wording aligned**

If needed, add a reference to the paper freeze document without changing the underlying full-inventory status numbers.

### Task 4: Verify that the wording is final

**Files:**
- Verify: `docs/paper/submission_snapshot.md`
- Verify: `docs/paper/manuscript.md`
- Verify: `docs/paper/figures.md`
- Verify: `docs/CURRENT_STATUS.md`

**Step 1: Run targeted grep**

Check that the paper docs no longer say “unless the submission snapshot states otherwise” or other provisional inventory language.

**Step 2: Run diff formatting checks**

Ensure all changed markdown files pass `git diff --check`.

**Step 3: Summarize residual non-blockers**

List only what remains outside this freeze scope, such as orthology provenance and conserved-edge definitions.
