# Docs Legacy Cleanup 8 Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** 为仍包含 TODO/待实现/未实现/stub 的历史文档补充统一说明，明确现状以 `docs/CURRENT_STATUS.md` 为准，减少误读。

**Architecture:** 仅添加少量 blockquote 说明行；不删除历史内容。

**Tech Stack:** Markdown 文档维护（无行为变更）。

## Targets (5 files)

- `docs/sessions/SESSION_SUMMARY_2025-11-27_PHASE1.md`
- `docs/sessions/SESSION_SUMMARY_2025-11-28_TODO_PHASE1-2.md`
- `docs/DATABASE_DESIGN_FINAL.md`
- `docs/plans/2026-01-23-docs-todo-cleanup.md`
- `docs/archive/SYNC_VERIFICATION_v2.3.md`

## Tasks

### Task 1: 补充 CURRENT_STATUS 说明

**Steps:**
1. 在标题附近添加“历史快照/过程记录/不代表当前待办”的说明
2. 指向 `docs/CURRENT_STATUS.md`

### Task 2: 验证与集成

**Steps:**
1. 运行 `python3 scripts/check_docs_commands.py`
2. 提交、合并回 `main` 并推送（pre-push 本地 CI 自动跑）

