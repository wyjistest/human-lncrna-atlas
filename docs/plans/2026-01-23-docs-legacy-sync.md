# Docs Legacy Status Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 对历史阶段文档做“现实对齐”，移除误导性的 TODO/Mock 描述，并明确当前真实实现状态。

**Architecture:** 仅修改 Markdown 文档，不改动任何运行时代码；保留历史内容但标注过期/已完成并指向现行文档。

**Tech Stack:** Markdown 文档、仓库既有状态文件与注释。

---

### Task 1: 归档后端状态文档

**Files:**
- Modify: `docs/backend/BACKEND_STATUS.md`
- Reference: `docs/CURRENT_STATUS.md`

**Step 1: 更新文档头部与状态说明**

- 将“状态/日期”更新为“历史归档”语义
- 增加“该文档为历史记录，现状以 CURRENT_STATUS 为准”的醒目标注

**Step 2: 历史问题章节降级为“历史记录”**

- 将“发现的问题/需要修复”改为“历史问题（已修复或不再适用）”
- 保留技术细节但明确它是历史背景

**Step 3: 验证**

Run: `python3 scripts/check_docs_commands.py`  
Expected: `Docs command drift check passed (...)`

**Step 4: Commit**

```bash
git add docs/backend/BACKEND_STATUS.md
git commit -m "docs(backend): archive legacy status notes"
```

---

### Task 2: 对齐 Phase 0/1 的 MSW/BA 描述

**Files:**
- Modify: `docs/phases/PHASE0_FOUNDATION.md`
- Modify: `docs/phases/PHASE1_REVISED_PLAN.md`
- Reference: `frontend/web/src/mocks/handlers.ts`
- Reference: `frontend/web/src/mocks/data/stats.mock.ts`

**Step 1: 标注 MSW/Mock 相关内容为历史示例**

- 将 Task 2/Task 3 的 TODO/清单改为“已完成/已废弃”
- 明确 Mock 仅为历史方案，当前已使用真实 API

**Step 2: 修正 BA 范围描述**

- 将“硬编码/待查询”类描述改为“后端已返回真实范围”
- 指向实际配置或接口来源（文档内说明即可）

**Step 3: 验证**

Run: `python3 scripts/check_docs_commands.py`  
Expected: `Docs command drift check passed (...)`

**Step 4: Commit**

```bash
git add docs/phases/PHASE0_FOUNDATION.md docs/phases/PHASE1_REVISED_PLAN.md
git commit -m "docs(phases): align MSW/BA notes with current impl"
```

