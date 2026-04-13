# Paper Research-First Reframe Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reframe the paper draft from a database/resource-first narrative to a research-first narrative centered on orthology-aware, triplex-informed primate lncRNA regulatory networks.

**Architecture:** Update only the paper-facing markdown documents so the manuscript and figure checklist tell the same story. Keep data claims conservative by explicitly flagging frozen-snapshot dependencies instead of inventing new numbers or silently normalizing inconsistent epigenomic inventories.

**Tech Stack:** Markdown documentation, existing paper draft under `docs/paper/`, repository documentation conventions

### Task 1: Reframe the manuscript structure

**Files:**
- Modify: `docs/paper/manuscript.md`
- Reference: `docs/paper/figures.md`
- Reference: `README.md`
- Reference: `docs/CURRENT_STATUS.md`

**Step 1: Rewrite the title and article positioning**

Replace the current atlas/database title with a research-first title and remove the `(database/resource)` qualifier from the article type line.

**Step 2: Rewrite the abstract scaffold**

Replace the current platform-first abstract with a six-part structure covering problem, gap, approach, scale, main findings, and resource value. Keep quantitative claims tied to a frozen submission snapshot.

**Step 3: Reorder the manuscript sections**

Restructure Introduction, Results, Discussion, and Methods around network construction, conservation/rewiring, epigenomic context, and trait-centered subnetworks. Keep a separate web resource section as optional or secondary.

**Step 4: Make uncertainty explicit**

Add explicit wording that orthology mapping source/version, conserved-edge definitions, BA cutoff sensitivity, and epigenomic mark inventory must be frozen before submission.

### Task 2: Reframe the figure checklist

**Files:**
- Modify: `docs/paper/figures.md`
- Reference: `notebooks/README.md`

**Step 1: Reorder main figures**

Move the story start from BA distribution to “from prior trait-associated catalogs to orthology-aware regulatory edges”, then follow with network architecture, conservation/rewiring, epigenomic context, and trait-centered subnetworks.

**Step 2: Downgrade platform visuals**

Keep the web resource figure as optional for resource-oriented submissions and note that it should move to Supplementary / Extended Data for research-first submissions.

**Step 3: Preserve asset traceability**

Where current source images still exist, note that they are provisional source material for redesigned figures rather than final figure order.

### Task 3: Validate wording and structure

**Files:**
- Verify: `docs/paper/manuscript.md`
- Verify: `docs/paper/figures.md`

**Step 1: Read back the updated sections**

Run targeted read-only checks to confirm heading order, terminology consistency, and frozen-snapshot cautions.

**Step 2: Check for contradictions introduced by the rewrite**

Ensure the manuscript no longer claims a database/resource-first positioning and that figure numbering matches the rewritten results narrative.

**Step 3: Summarize remaining follow-ups**

Document the still-unresolved items: exact submission snapshot, epigenomic inventory, orthology provenance, conserved-edge definition, and sensitivity analyses.
