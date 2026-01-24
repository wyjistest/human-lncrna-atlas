# Docs Legacy Cleanup 3 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 继续清理历史交付文档中的未勾选清单，并为已完成的 Phase 2.8 文档补充“未来方向”说明，避免被误读为当前待办。  
**Architecture:** 仅修改 Markdown 文档；保留历史内容结构，新增状态说明与清单语义调整；不改动任何代码逻辑。  
**Tech Stack:** Markdown、文档校验脚本 `python3 scripts/check_docs_commands.py`。

---

### Task 1: 归档 Phase 2.3 Delivery Summary 清单

**Files:**
- Modify: `docs/PHASE_2.3_DELIVERY_SUMMARY.md:1-720`

**Step 1: 添加历史说明**

在文档顶部元信息附近新增说明，明确该文档为历史交付总结，现状以 `docs/CURRENT_STATUS.md` 为准。

**Step 2: 清单语义历史化**

将以下段落内所有 `- [ ]` 条目改为 `- [x]`，并在条目末尾追加 `（历史记录）`：  
- “✅ 验收标准”下的功能验收/性能验收/代码质量  
- “准备工作”清单

**Step 3: 自检**

Run: `rg -n "\\[ \\]" docs/PHASE_2.3_DELIVERY_SUMMARY.md`  
Expected: 无输出

---

### Task 2: 标注 Phase 2.8 未来改进方向

**Files:**
- Modify: `docs/PHASE_2.8_CELL_LINE_COMPARISON.md:270-310`

**Step 1: 添加未来方向说明**

在 “## 🎯 未来改进方向” 标题下新增一行说明，强调该列表为未来方向，不代表当前待办或承诺时间。

**Step 2: 自检**

Run: `rg -n "未来改进方向" docs/PHASE_2.8_CELL_LINE_COMPARISON.md`  
Expected: 能看到新增说明

---

### Task 3: 验证与提交

**Files:**
- Modify: `docs/PHASE_2.3_DELIVERY_SUMMARY.md`
- Modify: `docs/PHASE_2.8_CELL_LINE_COMPARISON.md`
- Add: `docs/plans/2026-01-24-docs-legacy-cleanup-3.md`

**Step 1: 文档命令校验**

Run: `python3 scripts/check_docs_commands.py`  
Expected: `Docs command drift check passed (...)`

**Step 2: 本地 CI**

Run: `bash scripts/run-tests.sh ci`  
Expected: `所有测试通过`

**Step 3: 提交**

```bash
git add docs/PHASE_2.3_DELIVERY_SUMMARY.md docs/PHASE_2.8_CELL_LINE_COMPARISON.md docs/plans/2026-01-24-docs-legacy-cleanup-3.md
git commit -m "docs: archive Phase 2.3 delivery checklist and clarify Phase 2.8 future work"
```
