# Docs CI Commit Push Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finalize the current documentation work, verify the changed docs, and prepare a commit/push workflow that includes checking GitHub Actions after the push.

**Architecture:** Keep the scope limited to the already-modified documentation files and plan notes. Use read-only verification locally before any git write operation, then commit and push only after explicit user confirmation required by repository policy.

**Tech Stack:** Markdown documentation, git, GitHub CLI, existing repository CI workflows

### Task 1: Review the pending doc changes

**Files:**
- Verify: `README.md`
- Verify: `docs/CURRENT_STATUS.md`
- Verify: `docs/paper/README.md`
- Verify: `docs/paper/manuscript.md`
- Verify: `docs/paper/figures.md`
- Verify: `docs/paper/submission_snapshot.md`
- Verify: `docs/plans/2026-04-10-*.md`

**Step 1: Inspect status and branch**

Confirm the exact pending files and active branch before preparing a commit.

**Step 2: Review diff summary**

Read the current diff to ensure only intended documentation work is included.

### Task 2: Run local verification

**Files:**
- Verify: current changed docs only

**Step 1: Run diff-format checks**

Run `git diff --check` for the changed files.

**Step 2: Run any additional read-only checks justified by scope**

Keep verification scoped to the changed documentation unless the user explicitly asks for a broader local run.

### Task 3: Commit and push after explicit confirmation

**Files:**
- Modify: git history only after confirmation

**Step 1: Prepare commit message**

Choose a commit message that reflects the paper documentation freeze and manuscript reframing work.

**Step 2: Ask for explicit dangerous-operation confirmation**

Use the repository-mandated confirmation template before `git commit` and `git push`.

**Step 3: Push and monitor Actions**

After confirmation, push the branch and use GitHub CLI to inspect or watch the triggered workflow runs until success or failure is known.
