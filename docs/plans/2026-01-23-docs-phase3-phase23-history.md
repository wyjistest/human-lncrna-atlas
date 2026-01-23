# Docs Phase3/Phase2.3 历史语义对齐 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 Phase 3 计划文档补充现状说明，并将 Phase 2.3 实施清单归档为历史记录，避免被误读为当前待办。  
**Architecture:** 仅修改 Markdown 文档，保留原有内容与结构，新增历史说明与清单语义调整，并指向 `docs/CURRENT_STATUS.md` 作为现状参考。  
**Tech Stack:** Markdown、文档校验脚本 `python3 scripts/check_docs_commands.py`。

---

### Task 1: Phase 3 计划文档现状说明

**Files:**
- Modify: `docs/phases/PHASE3_PLAN.md:1-20`

**Step 1: 添加现状说明**

在“日期/版本/状态”附近增加说明，强调该文档仍为未来规划、不代表当前实现，并指向现状文档（`docs/CURRENT_STATUS.md`）。

**Step 2: 自检**

Run: `rg -n "现状|当前状态" docs/phases/PHASE3_PLAN.md`  
Expected: 能看到新增说明位置

---

### Task 2: Phase 2.3 实施清单归档

**Files:**
- Modify: `docs/PHASE_2.3_IMPLEMENTATION_CHECKLIST.md:1-700`

**Step 1: 增加历史归档说明**

在文档顶部新增“历史归档”提示，并说明现状以 `docs/CURRENT_STATUS.md` 为准，架构细节参考 `docs/PHASE_2.3_CHIPSEQ_ARCHITECTURE.md`。

**Step 2: 统一清单语义**

将全文件所有 `- [ ]` / `  - [ ]` 改为 `- [x]` / `  - [x]`，并在条目末尾追加 `（历史记录）`，确保不再被理解为当前待办。

**Step 3: 自检**

Run: `rg -n "\\[ \\]" docs/PHASE_2.3_IMPLEMENTATION_CHECKLIST.md`  
Expected: 无输出

---

### Task 3: 验证与提交

**Files:**
- Modify: `docs/phases/PHASE3_PLAN.md`
- Modify: `docs/PHASE_2.3_IMPLEMENTATION_CHECKLIST.md`
- Add: `docs/plans/2026-01-23-docs-phase3-phase23-history.md`

**Step 1: 文档命令校验**

Run: `python3 scripts/check_docs_commands.py`  
Expected: `Docs command drift check passed (...)`

**Step 2: 本地 CI**

Run: `bash scripts/run-tests.sh ci`  
Expected: `所有测试通过`

**Step 3: 提交**

```bash
git add docs/phases/PHASE3_PLAN.md docs/PHASE_2.3_IMPLEMENTATION_CHECKLIST.md docs/plans/2026-01-23-docs-phase3-phase23-history.md
git commit -m "docs: archive Phase 2.3 checklist and clarify Phase 3 plan status"
```
