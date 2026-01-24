# Docs TODO Cleanup 2 Implementation Plan

> 更新（2026-01-24）：本文档为文档清理实施计划的过程记录快照，不代表当前开发待办；现状以 `docs/CURRENT_STATUS.md` 为准。

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 继续清理历史计划文档中的未勾选清单/Mock 步骤，统一标注为历史记录，减少误读为“当前待办”的风险。

**Architecture:** 仅编辑 Markdown 文档；保留原内容结构但加“历史说明”和清单语义调整；不改动代码实现。

**Tech Stack:** Markdown、文档校验脚本 `python3 scripts/check_docs_commands.py`。

---

### Task 1: Phase 0 验证清单标注为历史

**Files:**
- Modify: `docs/phases/PHASE0_FOUNDATION.md`

**Step 1: 在 Task 1 验证清单前添加历史说明，并移除待办语义**

在“Task 1: 统一类型出口”下的“验证清单”位置，添加：

```
> 更新（2026-01-23）：以下为历史验收清单，保留用于回溯，不作为当前待办。
```

并将该清单条目统一改为 `[x]` + “（历史记录）”后缀，例如：

```
- [x] `src/types/api-extensions.ts` 创建，包含所有扩展类型（历史记录）
```

**Step 2: 验证**

Run: `python3 scripts/check_docs_commands.py`  
Expected: `Docs command drift check passed (...)`

**Step 3: Commit**

```bash
git add docs/phases/PHASE0_FOUNDATION.md
git commit -m "docs(phases): archive phase0 task1 checklist"
```

---

### Task 2: Phase 1 Revised Plan 前置准备改为历史说明

**Files:**
- Modify: `docs/phases/PHASE1_REVISED_PLAN.md`

**Step 1: 在 Phase 1A 前置准备加入历史说明**

在 “Phase 1A: 前置准备（30min）” 小节前加入：

```
> 更新（2026-01-23）：以下前置准备为历史计划，当前实现已完成且 MSW 默认不启用。
```

并将与 MSW 相关的安装/初始化步骤改为“历史记录”措辞（保留命令，但在标题或注释中标注历史）。

**Step 2: 验证**

Run: `python3 scripts/check_docs_commands.py`  
Expected: `Docs command drift check passed (...)`

**Step 3: Commit**

```bash
git add docs/phases/PHASE1_REVISED_PLAN.md
git commit -m "docs(phases): mark phase1a prep as legacy"
```

---

### Task 3: Phase 1 Implementation Plan 清单统一历史化

**Files:**
- Modify: `docs/phases/PHASE1_IMPLEMENTATION_PLAN.md`

**Step 1: 标注 8.x 执行清单为历史**

在 “#### 检查清单” 与 “### 8.2/8.5/8.9/8.10” 等清单段落前增加历史说明，并将 `[ ]` 条目改为 `[x]` + “（历史记录）”后缀，避免待办语义。

**Step 2: 验证**

Run: `python3 scripts/check_docs_commands.py`  
Expected: `Docs command drift check passed (...)`

**Step 3: Commit**

```bash
git add docs/phases/PHASE1_IMPLEMENTATION_PLAN.md
git commit -m "docs(phases): archive phase1 implementation checklists"
```
