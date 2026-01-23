# Docs TODO Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 继续清理历史文档中的 TODO/Mock 误导描述，并补充清晰的“历史记录”标注。

**Architecture:** 仅更新 Markdown 文档；保留历史内容但加注释与指向现行状态文档，不改动任何运行时代码。

**Tech Stack:** Markdown、仓库现有状态/计划文档。

---

### Task 1: 标注 Phase 1 Mock 配置为历史示例

**Files:**
- Modify: `docs/phases/PHASE1_IMPLEMENTATION_PLAN.md`
- Reference: `frontend/web/src/mocks/handlers.ts`

**Step 1: 更新 Mock 配置章节说明**

- 在“Mock 配置方案”章节顶部增加 2026-01-23 更新说明
- 明确当前 MSW 默认不启用，仅保留空 handlers

**Step 2: 调整示例代码为“历史示例”**

- 标记示例为历史示例，避免误解为当前实现

**Step 3: 验证**

Run: `python3 scripts/check_docs_commands.py`  
Expected: `Docs command drift check passed (...)`

**Step 4: Commit**

```bash
git add docs/phases/PHASE1_IMPLEMENTATION_PLAN.md
git commit -m "docs(phases): mark MSW mock plan as legacy"
```

---

### Task 2: 对齐 Phase 0 导出待办与历史标注

**Files:**
- Modify: `docs/phases/PHASE0_FOUNDATION.md`
- Reference: `frontend/web/src/utils/export.ts`

**Step 1: 标注导出任务清单为历史记录**

- 将 Task 4 清单标注为历史
- 如确认实现存在，仅做“历史完成/已实现”注记，不写具体功能细节

**Step 2: 验证**

Run: `python3 scripts/check_docs_commands.py`  
Expected: `Docs command drift check passed (...)`

**Step 3: Commit**

```bash
git add docs/phases/PHASE0_FOUNDATION.md
git commit -m "docs(phases): mark export checklist as legacy"
```

---

### Task 3: Session Summary 添加历史说明

**Files:**
- Modify: `docs/sessions/SESSION_SUMMARY_2025-11-28_TODO_PHASE1-2.md`
- Reference: `docs/frontend/TODO_IMPLEMENTATION_PLAN.md`

**Step 1: 添加历史说明与指引**

- 在文档顶部添加“历史记录”说明
- 指向 `docs/frontend/TODO_IMPLEMENTATION_PLAN.md` 的最终状态

**Step 2: 验证**

Run: `python3 scripts/check_docs_commands.py`  
Expected: `Docs command drift check passed (...)`

**Step 3: Commit**

```bash
git add docs/sessions/SESSION_SUMMARY_2025-11-28_TODO_PHASE1-2.md
git commit -m "docs(sessions): add legacy note for phase1-2 todo summary"
```

