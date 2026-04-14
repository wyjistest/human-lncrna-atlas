# Main CI Hotfix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 `main` 分支 merge 后新增暴露的两类 CI 失败：前端视觉回归 smoke 和前端依赖安全审计。

**Architecture:** 这次修复拆成两条独立链路。视觉回归按 TDD 思路先复现失败，再判断是页面行为回归还是预期快照需要更新；安全审计则先锁定高危依赖来源，再做最小依赖升级并验证不引入新的构建或测试回归。

**Tech Stack:** GitHub Actions, Playwright, Vite, npm audit, React, TypeScript

### Task 1: 复现并收敛视觉回归失败

**Files:**
- Modify: `frontend/web/e2e/visual-regression-smoke.spec.ts`
- Verify: `scripts/run-tests.sh`
- Snapshot: `frontend/web/e2e/visual-regression-smoke.spec.ts-snapshots/*`

**Step 1: 写/调整能准确暴露失败的测试输入**

沿用现有 `visual-regression-smoke.spec.ts` 的失败用例，不新增无关页面。

**Step 2: 运行测试并确认 RED**

Run: `BASE_URL=http://127.0.0.1:5189 bash scripts/run-tests.sh e2e-visual-smoke`
Expected: `Regulations / Diseases / Analysis / Conservation` 视觉快照失败。

**Step 3: 做最小修复**

如果页面改动是预期叙事更新，更新对应 screenshot baseline；如果出现非预期布局漂移，则修页面代码而不是改快照。

**Step 4: 再次运行测试确认 GREEN**

Run: `BASE_URL=http://127.0.0.1:5189 bash scripts/run-tests.sh e2e-visual-smoke`
Expected: 视觉回归 smoke 通过。

### Task 2: 修复前端依赖安全审计失败

**Files:**
- Modify: `frontend/web/package.json`
- Modify: `frontend/web/package-lock.json`
- Verify: `.github/workflows/security-audit.yml`

**Step 1: 运行审计并确认 RED**

Run: `cd frontend/web && npm audit --registry=https://registry.npmjs.org --audit-level=high`
Expected: 至少出现 `axios` critical 以及 `vite` / `lodash` 等 high 漏洞。

**Step 2: 做最小依赖升级**

优先升级直接依赖和可控的顶层依赖，避免大范围工具链重构。

**Step 3: 重新运行审计确认 GREEN**

Run: `cd frontend/web && npm audit --registry=https://registry.npmjs.org --audit-level=high`
Expected: exit code 0。

### Task 3: 回归验证

**Files:**
- Verify: `scripts/run-tests.sh`

**Step 1: 运行相关验证**

Run:
- `bash scripts/run-tests.sh frontend-build`
- `bash scripts/run-tests.sh e2e-smoke`
- `BASE_URL=http://127.0.0.1:5189 bash scripts/run-tests.sh e2e-visual-smoke`
- `cd frontend/web && npm audit --registry=https://registry.npmjs.org --audit-level=high`

**Step 2: 评估是否需要补充更高层验证**

若以上通过，再决定是否跑 `ci-full` 或仅提交修复并等待 GitHub Actions。
