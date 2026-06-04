# Paper Research-First Manuscript Lock Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Lock the paper draft into a research-first manuscript by removing the web resource from the main Results chain and tightening the abstract and availability text.

**Architecture:** Keep Figure 1–5 as the only main-text results, move the web platform to a reproducibility layer in Data and Code Availability plus Supplementary Figure 6, and preserve conservative freeze language already fixed in the paper docs. Add markdown-based regression tests before changing the draft text.

**Tech Stack:** Markdown documentation, Python unittest text assertions

### Task 1: Add failing manuscript-lock tests

**Files:**
- Create: `scripts/tests/test_paper_manuscript_docs.py`
- Modify: none
- Test: `scripts/tests/test_paper_manuscript_docs.py`

**Step 1: Write the failing test**
- Assert the abstract no longer contains `across seven human cell lines`.
- Assert Results no longer contains `### 6. Web resource and programmatic access`.
- Assert Data and Code Availability mentions `Human LncRNA Atlas Companion` and `Supplementary Figure 6`.

**Step 2: Run test to verify it fails**
Run: `python3 -m unittest scripts.tests.test_paper_manuscript_docs`
Expected: FAIL because the current manuscript still contains the old abstract wording and Result 6.

### Task 2: Patch manuscript draft

**Files:**
- Modify: `docs/paper/manuscript.md`
- Test: `scripts/tests/test_paper_manuscript_docs.py`

**Step 1: Update abstract**
- Remove the phrase `across seven human cell lines`.
- Keep only frozen epigenomic totals and extended-track wording.

**Step 2: Lock Results to Figure 1–5**
- Remove the `### 6. Web resource and programmatic access` main-text Results section.
- Keep the Results chain focused on reconstruction, architecture, conservation/rewiring, epigenomic context, and trait prioritization.

**Step 3: Add research-first companion wording**
- Add a concise paragraph to `Data and Code Availability` describing the Human LncRNA Atlas Companion as a reproducibility/evidence-inspection layer.
- Add a short `Supplementary / Extended Data` note that defines `Supplementary Figure 6` and its four panels.
- Add an internal note with two conservative title alternatives.

### Task 3: Sync figure-plan wording if needed

**Files:**
- Modify: `docs/paper/figures.md` only if wording conflicts remain
- Test: `scripts/tests/test_paper_manuscript_docs.py`

**Step 1: Verify Figure 6 placement language**
- Ensure Figure 6 is described as Supplementary / Extended Data by default for research-first submission.

### Task 4: Verify and stop

**Files:**
- Test: `scripts/tests/test_paper_manuscript_docs.py`
- Test: `python3 -m py_compile scripts/tests/test_paper_manuscript_docs.py`

**Step 1: Run targeted tests**
Run: `python3 -m unittest scripts.tests.test_paper_manuscript_docs`
Expected: PASS

**Step 2: Run full relevant regression**
Run: `python3 -m unittest scripts.tests.test_generate_batch1_figures scripts.tests.test_generate_batch2_figures scripts.tests.test_generate_composite_figures scripts.tests.test_paper_manuscript_docs`
Expected: PASS
