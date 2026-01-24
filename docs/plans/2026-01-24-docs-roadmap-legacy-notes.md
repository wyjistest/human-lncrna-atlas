# Docs Roadmap Legacy Notes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 2026-01 路线图文档补充“历史快照”说明，避免被误解为当前待办。  
**Architecture:** 仅修改 Markdown 文档，在标题附近新增状态说明；不改动原有路线图内容。  
**Tech Stack:** Markdown、文档校验脚本 `python3 scripts/check_docs_commands.py`。

---

### Task 1: 标注 2026-01-17 路线图为历史快照

**Files:**
- Modify: `docs/ROADMAP_2026-01-17.md:1-6`

**Step 1: 添加状态说明**

在标题下增加说明：该路线图为当日快照，现状以 `docs/CURRENT_STATUS.md` 为准。

---

### Task 2: 标注 2026-01-19 路线图为历史快照

**Files:**
- Modify: `docs/ROADMAP_2026-01-19.md:1-6`

**Step 1: 添加状态说明**

在标题下增加说明：该路线图为当日快照，现状以 `docs/CURRENT_STATUS.md` 为准。

---

### Task 3: 标注 2026-01-21 路线图为历史快照

**Files:**
- Modify: `docs/ROADMAP_2026-01-21.md:1-6`

**Step 1: 添加状态说明**

在标题下增加说明：该路线图为当日快照，现状以 `docs/CURRENT_STATUS.md` 为准。

---

### Task 4: 验证与提交

**Files:**
- Modify: `docs/ROADMAP_2026-01-17.md`
- Modify: `docs/ROADMAP_2026-01-19.md`
- Modify: `docs/ROADMAP_2026-01-21.md`
- Add: `docs/plans/2026-01-24-docs-roadmap-legacy-notes.md`

**Step 1: 文档命令校验**

Run: `python3 scripts/check_docs_commands.py`  
Expected: `Docs command drift check passed (...)`

**Step 2: 本地 CI**

Run: `bash scripts/run-tests.sh ci`  
Expected: `所有测试通过`

**Step 3: 提交**

```bash
git add docs/ROADMAP_2026-01-17.md docs/ROADMAP_2026-01-19.md docs/ROADMAP_2026-01-21.md docs/plans/2026-01-24-docs-roadmap-legacy-notes.md
git commit -m "docs: add legacy notes to roadmap snapshots"
```
