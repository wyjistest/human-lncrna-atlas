# Docs Command Drift Check Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** 防止文档中的后端启动命令/入口漂移（例如 `python -m uvicorn`、`app.main:app`、`poetry run uvicorn`），并让本地与 GitHub Actions 在回归时快速失败。

**Architecture:** 新增一个轻量的 Python 脚本扫描仓库内已跟踪的 Markdown 文件，发现不允许的启动命令模式就输出 `file:line` 并以非 0 退出；把该检查接入 `scripts/run-tests.sh`（本地一键）与 `.github/workflows/test.yml`（CI 门禁）。

**Tech Stack:** Python 3（标准库）、bash（run-tests 集成）、GitHub Actions。

---

### Task 1: 新增文档漂移检查脚本（fast fail）

**Files:**
- Create: `scripts/check_docs_commands.py`

**Step 1: 实现最小检查**
- 扫描 `git ls-files '*.md'` 输出的文件列表（仅检查已跟踪文档）
- 发现以下模式即失败：
  - `poetry run uvicorn`
  - `app.main:app`
  - `python -m uvicorn`
- 输出格式：`<path>:<line>: <message>`（便于 GitHub Actions 直接定位）

**Step 2: 本地验证**
- Run: `python3 scripts/check_docs_commands.py`
- Expected: exit 0（当前仓库应无上述漂移模式）

---

### Task 2: 接入本地一键入口（run-tests.sh）

**Files:**
- Modify: `scripts/run-tests.sh`

**Step 1: 新增子命令**
- 新增 `docs-check` target，调用 `python3 scripts/check_docs_commands.py`
- 将 `docs-check` 纳入 `ci` target（CI 对齐集合）

**Step 2: 本地验证**
- Run: `bash scripts/run-tests.sh docs-check`
- Expected: PASS（exit 0）

---

### Task 3: 接入 GitHub Actions（Tests 工作流）

**Files:**
- Modify: `.github/workflows/test.yml`

**Step 1: 新增一步**
- 在 `Backend Checks` job 中添加一步 `python3 scripts/check_docs_commands.py`

**Step 2: 推送后验证**
- Run: `gh run list --branch main --limit 5`
- Run: `gh run watch <run-id> --exit-status`
- Expected: `Tests` 工作流成功

---

### Task 4: 小步提交（便于回滚）

**Step 1: Commit**
- `git add scripts/check_docs_commands.py scripts/run-tests.sh .github/workflows/test.yml docs/plans/2026-01-18-docs-command-drift-check.md`
- `git commit -m "chore(docs): add docs command drift check"`

**Step 2: Push**
- `git push origin main`

