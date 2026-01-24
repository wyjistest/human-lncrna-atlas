# Baseline Browser Mapping + Status Update Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 消除前端 `eslint` 输出的 `[baseline-browser-mapping]` 数据过期警告，并同步更新项目状态文档，保持“可审计、可回滚、可复现”。

**Architecture:** 通过在 `frontend/web` 显式添加 `baseline-browser-mapping` devDependency 来提升 npm hoist 版本（仍满足 `browserslist` 的依赖范围），避免警告；同时更新 `docs/CURRENT_STATUS.md` 与路线图快照的进度说明。

**Tech Stack:** Node.js / npm / Vite / ESLint / Markdown docs

---

### Task 1: 更新当前状态文档（2026-01-24）

**Files:**
- Modify: `docs/CURRENT_STATUS.md`

**Step 1: 修改文档头部日期**
- 把 `> 最后更新:` 更新为 `2026-01-24`。

**Step 2: 补充“最近完成的功能”条目**
- 增加一条 2026-01-24 的完成项，覆盖：
  - 后端回归脚本 `frontend/backend/scripts/run_tests.sh` / `frontend/backend/scripts/run_chipseq_tests.sh` 支持 `API_BASE_URL`（兼容 `HLA_BACKEND_URL/BACKEND_URL`）与默认 `NO_PROXY`
  - `scripts/run-tests.sh e2e-smoke` 的端口提示与 BASE_URL 解析行为
  - `frontend/backend/app/routers/export.py` 示例不写死后端地址

**Step 3: 验证**
- Run: `python3 scripts/check_docs_commands.py`
- Expected: `Docs command drift check passed`

**Step 4: Commit**
- `git add docs/CURRENT_STATUS.md`
- `git commit -m "docs: update current status (2026-01-24)"`

---

### Task 2: 更新路线图快照进度（可选但推荐）

**Files:**
- Modify: `docs/ROADMAP_2026-01-21.md`

**Step 1: 追加进度条目**
- 在 “进度” 区补充本次完成项（脚本 base url 可配置性补齐）。

**Step 2: Commit**
- `git add docs/ROADMAP_2026-01-21.md`
- `git commit -m "docs: update roadmap snapshot progress"`

---

### Task 3: 升级 baseline-browser-mapping（消除 eslint warning）

**Files:**
- Modify: `frontend/web/package.json`
- Modify: `frontend/web/package-lock.json`

**Step 1: 写入/升级 devDependency**
- Run: `cd frontend/web && npm i baseline-browser-mapping@latest -D`

**Step 2: 验证警告消失**
- Run: `cd frontend/web && npm run lint`
- Expected: 不再出现 `[baseline-browser-mapping]` 的数据过期提示（其它 warning 可接受）。

**Step 3: 回归验证（对齐 CI）**
- Run: `bash scripts/run-tests.sh ci`
- Expected: exit code 0

**Step 4: Commit**
- `git add frontend/web/package.json frontend/web/package-lock.json`
- `git commit -m "chore(frontend): bump baseline-browser-mapping to latest"`

---

### Task 4: 合并与清理

**Step 1: push 分支并触发 self-hosted Actions（可选）**
- `git push -u origin <branch>`
- `gh workflow run Tests --ref <branch> -f runs_on=self-hosted`

**Step 2: ff-only 合并到 main**
- `git checkout main && git pull --ff-only`
- `git merge --ff-only <branch> && git push`

**Step 3: 清理 worktree 与远端分支**
- `git worktree remove <path>`
- `git branch -d <branch>`
- `git push origin --delete <branch>`

