# Docs Legacy Cleanup 5 Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** 继续压缩 docs 中“看起来像当前 backlog”的残留 `[ ]/TODO/待实现`，为模板/规划/交付总结补充统一说明（不删除历史），并指向 `docs/CURRENT_STATUS.md`。

**Architecture:** 不改动功能代码，仅在文档顶部或相关清单段落前补充「模板/计划快照/历史记录」注释；对真正用于执行的测试清单明确其“可勾选模板”属性。

**Tech Stack:** Markdown 文档维护（无行为变更）。

## Tasks

### Task 1: 高密度 checklist 文档加“模板说明”

**Files:**
- Modify: `docs/testing/phase-3-1-manual-checklist.md`
- Modify: `docs/testing/phase-3-1-testing-strategy.md`
- Modify: `docs/reports/HOW_TO_TEST_OVERLAP_PAGE.md`
- Modify: `docs/testing/e2e/ACCEPTANCE_CHECKLIST.md`

**Steps:**
1. 在标题下方添加“本文件为测试执行清单模板，可复制勾选；不代表当前开发待办”的说明
2. 指向 `docs/CURRENT_STATUS.md` 作为当前状态来源

### Task 2: 规划/交付类文档加“快照说明”

**Files:**
- Modify: `docs/IGV_INTEGRATION_PLAN.md`
- Modify: `docs/api/GENES_API_DELIVERABLES.md`
- (Optional) Modify: `docs/api/GENES_API_INTEGRATION_PLAN.md`

**Steps:**
1. 在标题或状态附近增加“计划快照/不代表当前待办”的说明
2. 指向 `docs/CURRENT_STATUS.md`

### Task 3: 验证与集成

**Steps:**
1. 运行 `python3 scripts/check_docs_commands.py`
2. 运行 `bash scripts/run-tests.sh ci`（或至少跑文档校验 + 关键单测）
3. 提交、合并回 `main` 并推送

### Task 4: 远端分支清理（已合并）

**Steps:**
1. 列出 `origin/*` 中已合并到 `origin/main` 的分支
2. 仅删除“已合并且非保护/非系统分支”（例如跳过 `main`、`dependabot/*`）

