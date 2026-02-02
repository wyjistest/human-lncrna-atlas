# CI Self-hosted：每周“全量回归”触发指南补齐 Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不改变默认 CI 行为（push/main 仍走 fast-ci）的前提下，补齐 `docs/CI_SELF_HOSTED_RUNNER.md` 中关于 `workflow_dispatch` 触发“每周全量回归”的可复制操作指南（GitHub UI + GH CLI）。

**Architecture:** 仅改文档，不改 workflow：对齐 `.github/workflows/test.yml` 的 `workflow_dispatch.inputs`，给出推荐组合、前置条件（backend / Docker）与可复制命令。

**Tech Stack:** GitHub Actions、GitHub UI、GitHub CLI (`gh`)

---

### Task 1: 对齐 workflow_dispatch inputs 并补齐文档段落

**Files:**
- Modify: `docs/CI_SELF_HOSTED_RUNNER.md:4.2`
- Reference: `.github/workflows/test.yml:on.workflow_dispatch.inputs`

**Step 1: 核对 inputs 名称与语义**
- `runs_on`
- `api_base_url`
- `enable_postgres_jobs`
- `enable_e2e_tests`
- `enable_performance_audit`
- `enable_firefox_smoke`

**Step 2: 在文档中补齐**
- GitHub UI 触发路径（Actions → Tests → Run workflow）
- 推荐组合与前置条件说明（backend 可用、Docker 可用）
- GH CLI 可复制命令（`gh workflow run` + `-f key=value`）
- 触发后 watch 命令（`gh run watch`）

---

### Task 2: 本地验证（docs-check）

**Step 1: 运行 docs 门禁**

Run: `timeout 60 bash scripts/run-tests.sh docs-check`

Expected: exit code `0`

---

### Task 3: 提交、推送、合并

**Step 1: 提交**

```bash
git add docs/CI_SELF_HOSTED_RUNNER.md
git commit -m "docs: add self-hosted full regression trigger guide"
```

**Step 2: 推送并创建 PR**

```bash
git push -u origin <branch>
gh pr create --fill
```

**Step 3: 合并**

```bash
gh pr merge --squash --delete-branch
```

