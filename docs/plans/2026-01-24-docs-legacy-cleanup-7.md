# Docs Legacy Cleanup 7 Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** 为剩余仍未引用 `docs/CURRENT_STATUS.md` 的 checklist/历史文档补充统一说明，完成“含 checklist 文档全覆盖”。

**Architecture:** 仅添加少量 blockquote 说明行；不删除历史内容、不重写结构。

**Tech Stack:** Markdown 文档维护（无行为变更）。

## Targets (15 files)

- `docs/archive/REVISION_SUMMARY_V2.md`
- `docs/archive/CRITICAL_FIX_v2.3.1.md`
- `docs/PHASE_2.8_CELL_LINE_COMPARISON.md`
- `docs/sessions/SESSION_SUMMARY_2025-11-27_PHASE2.md`
- `docs/sessions/SESSION_SUMMARY_2025-11-28_I18N_COMPLETE.md`
- `docs/changelog/2025-12-03.md`
- `docs/sessions/SESSION_SUMMARY_2025-11-28_PHASE3.md`
- `docs/plans/2026-01-23-docs-todo-cleanup-2-design.md`
- `docs/plans/2026-01-23-docs-todo-cleanup-2.md`
- `docs/api/REGULATIONS_API_SUMMARY.md`
- `docs/api/LNCRNA_CHIPSEQ_OVERLAP_API.md`
- `docs/api/GENES_API_QUICK_START.md`
- `docs/testing/TEST_FIX_GUIDE.md`
- `docs/frontend/PLAN_I18N_BILINGUAL.md`
- `docs/testing/e2e/RUN_A549_VALIDATION.md`

## Tasks

### Task 1: 为每个目标文件添加“快照/模板/历史”说明

**Steps:**
1. 在标题附近增加说明：不代表当前开发待办/现状以 `docs/CURRENT_STATUS.md` 为准
2. 对 changelog 类文件，说明其为历史变更记录快照（如有更改以最新 changelog/CURRENT_STATUS 为准）

### Task 2: 验证与集成

**Steps:**
1. 运行 `python3 scripts/check_docs_commands.py`
2. 提交、合并回 `main` 并推送（pre-push 本地 CI 自动跑）

