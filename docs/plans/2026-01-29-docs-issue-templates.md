# Docs & Issue Templates Maintenance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 更新现状文档并优化性能定位 issue 模板，降低“信息不一致/硬编码地址/敏感信息误贴”的风险。

**Architecture:** 仅做 Markdown / GitHub issue template 的最小改动，不改任何运行时代码逻辑；每个主题独立 commit，确保可 `git revert` 回滚。

**Tech Stack:** Markdown、GitHub Issue Templates（`.github/ISSUE_TEMPLATE`）

---

### Task 1: 更新 CURRENT_STATUS（记录 2026-01-29 变更）

**Files:**
- Modify: `docs/CURRENT_STATUS.md`

**Step 1: 修改文档**
- 更新文档头部“最后更新”日期为 `2026-01-29`
- 在“✅ 最近完成的功能”中新增 `2026-01-29` 小节，记录：
  - Stats/Conservation/Analysis（含各 tab）URL 参数同步扩展
  - `scripts/run-tests.sh` 可执行位修复（文档中的 `./scripts/run-tests.sh …` 不再需要 `bash`）

**Step 2: 运行验证**

Run: `./scripts/run-tests.sh docs-check`  
Expected: `Docs command drift check passed` + `Docs status marker check passed` + exit 0

**Step 3: Commit**

```bash
git add docs/CURRENT_STATUS.md
git commit -m "docs: update CURRENT_STATUS (2026-01-29)"
```

---

### Task 2: 优化性能定位 issue 模板（避免硬编码与敏感信息误贴）

**Files:**
- Modify: `.github/ISSUE_TEMPLATE/performance-triage.md`

**Step 1: 修改模板内容**
- 将命令示例从硬编码 `http://localhost:8000` 调整为“环境变量优先”（`API_BASE_URL` / `ADMIN_API_KEY`），并保留显式参数示例作为 fallback
- 明确提示：不要把 `ADMIN_API_KEY` 粘贴到 issue（仅作为环境变量传入脚本）

**Step 2: 运行验证**

Run: `./scripts/run-tests.sh docs-check`  
Expected: PASS + exit 0

**Step 3: Commit**

```bash
git add .github/ISSUE_TEMPLATE/performance-triage.md
git commit -m "docs: clarify performance triage issue template"
```

---

### Task 3: 集成（合并到 main + CI 核验）

**Step 1: Merge**

```bash
git checkout main
git pull --ff-only
git merge --ff-only chore/issue-templates
```

**Step 2: Push**

```bash
git push origin main
```

**Step 3: 核验 GitHub Actions**

```bash
gh run list --limit 1
gh run watch <RUN_ID> --exit-status
```

