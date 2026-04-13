# Epigenomic Inventory Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify the paper-facing and repository-facing epigenomic inventory language so README, CURRENT_STATUS, and paper documents no longer contradict each other.

**Architecture:** Keep `docs/CURRENT_STATUS.md` as the authoritative inventory of the current database snapshot, while defining a stable paper-facing default inventory for manuscript language. Use one explicit distinction everywhere: the paper baseline is `8 core histone marks + DNase-HS`, and the current human snapshot additionally contains `CTCF` and `H4K20me1` coverage.

**Tech Stack:** Markdown documentation under repository root and `docs/paper/`

### Task 1: Freeze the wording model

**Files:**
- Modify: `docs/CURRENT_STATUS.md`
- Reference: `README.md`
- Reference: `docs/paper/manuscript.md`
- Reference: `docs/paper/figures.md`

**Step 1: Define the canonical distinction**

Write the documentation so it explicitly distinguishes between:
- paper-facing baseline: 8 core histone marks + DNase-HS;
- current DB snapshot: the same baseline plus additional human tracks for CTCF and H4K20me1.

**Step 2: Preserve current totals**

Keep `docs/CURRENT_STATUS.md` totals intact and explain what is included in the 4,924,916 total rather than deleting categories to match the paper wording.

### Task 2: Update repository entry documents

**Files:**
- Modify: `README.md`
- Modify: `docs/CURRENT_STATUS.md`

**Step 1: Update README feature bullets**

Make the feature bullets say the paper-facing baseline is 8 core histone marks + DNase-HS, and point to `docs/CURRENT_STATUS.md` for the complete extended inventory.

**Step 2: Annotate CURRENT_STATUS**

Add a short note near the epigenomic statistics table clarifying which tracks belong to the paper-facing baseline and which tracks are additional snapshot coverage.

### Task 3: Update paper-facing documents

**Files:**
- Modify: `docs/paper/manuscript.md`
- Modify: `docs/paper/figures.md`
- Optional: `docs/paper/README.md`

**Step 1: Update manuscript wording**

Replace generic “inventory still diverges” language with a concrete draft rule: the manuscript baseline uses 8 core histone marks + DNase-HS, while CTCF and H4K20me1 remain optional extended human tracks unless explicitly analyzed.

**Step 2: Update figure/table planning**

Make Table 2 and Figure 4 wording inherit the same baseline-versus-extended distinction.

**Step 3: Update paper README if needed**

If the paper directory README still implies a platform-first framing or ambiguous epigenomic wording, tighten it to match the new paper narrative.

### Task 4: Verify consistency

**Files:**
- Verify: `README.md`
- Verify: `docs/CURRENT_STATUS.md`
- Verify: `docs/paper/manuscript.md`
- Verify: `docs/paper/figures.md`

**Step 1: Run targeted grep**

Check for remaining contradictory phrases such as “six core marks” or mismatched inventory descriptions.

**Step 2: Run diff formatting checks**

Ensure the changed markdown files pass `git diff --check`.

**Step 3: Summarize residual follow-ups**

Record what still requires a frozen submission snapshot: exact peak totals for the paper package, comparable cell-line subset, and whether CTCF / H4K20me1 stay supplementary or enter the main text.
