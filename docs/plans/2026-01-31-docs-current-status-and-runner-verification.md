# Docs Current Status + Runner Verification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把“前端 bundle 体积可定位”与“self-hosted runner 核验方式（可复现）”写入权威文档，并以 PR 方式合入 main（可审计可回滚）。

**Architecture:** 仅改动文档（`docs/`）且不改变现有脚本行为；优先更新 `docs/CURRENT_STATUS.md`（权威入口）与 `docs/CI_SELF_HOSTED_RUNNER.md`（止损/核验指南）。

**Tech Stack:** Markdown、`bash scripts/run-tests.sh docs-check`、`gh` CLI（PR/merge）。

---

### Task 1: 更新权威入口 `docs/CURRENT_STATUS.md`

**Files:**
- Modify: `docs/CURRENT_STATUS.md`

**Step 1: 更新“最后更新”日期**
- 将 `最后更新` 改为今天的日期（按仓库格式）。

**Step 2: 补充“前端 bundle 体积定位”入口**
- 在“回归与性能门禁（面向开发者）”或 TL;DR 处新增一条：
  - `cd frontend/web && npm run build && npm run report:bundle -- --top 15`
- 说明用途：用于定位 `dist/assets` 下最大的 JS chunks（raw + gzip），便于排查首屏/预加载回归。

---

### Task 2: 更新 self-hosted runner 核验命令 `docs/CI_SELF_HOSTED_RUNNER.md`

**Files:**
- Modify: `docs/CI_SELF_HOSTED_RUNNER.md`

**Step 1: 让“核验 runner”命令更可复制**
- 将示例从纯 `gh run list ...` 改为更稳的方式（例如 `gh run list --json ...` 或 `gh api .../jobs`），避免在某些终端环境下表格输出为空导致误判。
- 输出建议包含：`runner_name` 与 `labels`（是否包含 `self-hosted`）。

---

### Task 3: 验证文档门禁

**Step 1: 跑 docs-check**
- Run: `bash scripts/run-tests.sh docs-check`
- Expected: PASS

---

### Task 4: 小步提交 + PR

**Step 1: 建分支**
- Branch: `docs/current-status-bundle-report`

**Step 2: Commit**
- Commit message: `docs: update current status and runner verification`

**Step 3: Push + PR**
- Create PR（squash merge），合并后删除远端分支。

