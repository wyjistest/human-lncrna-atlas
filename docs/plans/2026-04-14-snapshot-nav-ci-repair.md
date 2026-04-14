# Snapshot Nav And CI Repair Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expose the submission snapshot in public companion navigation, surface frozen provenance metadata, update reviewer docs, and restore green GitHub Actions for the branch.

**Architecture:** Keep the change minimal and reviewer-facing. Reuse the existing `PAPER_SNAPSHOT` constant for frozen metadata, wire `/snapshot` into the public sidebar and locale files, then update the visual regression baseline only if the failing screenshots reflect intentional UI changes already present on the branch.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Playwright, GitHub Actions

### Task 1: Verify current branch state and failing CI scope

**Files:**
- Inspect: `frontend/web/src/layouts/MainLayout.tsx`
- Inspect: `frontend/web/src/pages/Snapshot/index.tsx`
- Inspect: `frontend/web/src/config/paperSnapshot.ts`
- Inspect: `.github/workflows/`

**Step 1: Confirm the local diff**

Run: `git status -sb && git diff --stat`
Expected: only companion nav/provenance files are modified.

**Step 2: Inspect failed workflow details**

Run: `gh run view 24380221612 --json conclusion,status,jobs`
Expected: previous branch failure is isolated to Playwright visual regression smoke.

### Task 2: Reproduce the failing visual regression locally

**Files:**
- Inspect: `frontend/web/e2e/visual-regression-smoke.spec.ts`
- Update if needed: `frontend/web/e2e/visual-regression-smoke.spec.ts-snapshots/*.png`

**Step 1: Build the frontend**

Run: `cd frontend/web && npm run build`
Expected: production build succeeds.

**Step 2: Run the failing visual regression targets without updating baselines**

Run: `cd frontend/web && BASE_URL=http://127.0.0.1:5173 npx playwright test e2e/visual-regression-smoke.spec.ts --project=chromium --grep "Stats|Analysis"`
Expected: the same screenshot mismatches reproduce or fail for a clearly related reason.

**Step 3: Update baselines only if the mismatch matches intentional UI changes**

Run: `cd frontend/web && BASE_URL=http://127.0.0.1:5173 npx playwright test e2e/visual-regression-smoke.spec.ts --project=chromium --grep "Stats|Analysis" --update-snapshots`
Expected: tracked snapshots refresh to the intended companion UI.

### Task 3: Update reviewer-facing docs

**Files:**
- Modify: `frontend/web/README.md`
- Modify: `docs/preview/FRP_SINGLE_PORT_REVIEWER_PREVIEW.md`

**Step 1: Document public snapshot navigation**

Add that `Submission Snapshot` is part of the public sidebar for reviewer navigation.

**Step 2: Document frozen provenance metadata**

Add that the snapshot page shows frozen metadata such as freeze date and release commit.

### Task 4: Verify focused tests and working tree integrity

**Files:**
- Verify: `frontend/web/src/layouts/MainLayout.test.tsx`
- Verify: `frontend/web/src/pages/Snapshot/index.test.tsx`
- Verify: `frontend/web/src/i18n/locales/paperNarrative.test.ts`

**Step 1: Run focused unit tests**

Run: `cd frontend/web && npm run test -- src/pages/Home/index.test.tsx src/layouts/MainLayout.test.tsx src/pages/Snapshot/index.test.tsx src/i18n/locales/paperNarrative.test.ts src/i18n/index.test.ts`
Expected: all targeted tests pass.

**Step 2: Run the relevant visual regression smoke again**

Run: `cd frontend/web && BASE_URL=http://127.0.0.1:5173 npx playwright test e2e/visual-regression-smoke.spec.ts --project=chromium --grep "Stats|Analysis"`
Expected: both screenshot tests pass.

**Step 3: Run lightweight integrity check**

Run: `git diff --check`
Expected: no whitespace or merge marker issues.

### Task 5: Commit, push, and confirm fresh GitHub Actions success

**Files:**
- Commit scope: companion nav/provenance/docs plus any refreshed visual baselines

**Step 1: Commit the branch**

Run: `git add ... && git commit -m "chore: expose snapshot metadata in companion nav"`
Expected: one commit capturing the reviewer-facing polish and CI repair.

**Step 2: Push to origin**

Run: `git push origin pr-eval-frontend`
Expected: remote branch updates successfully.

**Step 3: Confirm workflows**

Run: `gh run watch <new-run-id>` and `gh run view <new-run-id> --json conclusion,jobs,url`
Expected: latest `Workflow Lint` and `Tests` conclude successfully, with `Build` green inside `Tests`.
