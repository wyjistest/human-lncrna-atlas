# CI Runner Fallback (Self-hosted) Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 GitHub Actions 因账单/额度（spending limit）导致 `ubuntu-latest` 作业无法启动时，仍可通过 `self-hosted` runner 跑通核心 CI（lint/unit/build/e2e-smoke），并提供清晰的文档止损路径。

**Architecture:** 为 `.github/workflows/test.yml` 与 `.github/workflows/security-audit.yml` 增加可配置的 `runs-on`（仓库变量 `CI_RUNS_ON`，默认 `ubuntu-latest`），并对依赖 Docker service 的 Postgres jobs 做“self-hosted 默认跳过、可显式开启”的门控；同时补齐 self-hosted runner 配置文档与 README 指引。

**Tech Stack:** GitHub Actions、GitHub repo variables（`vars` context）、bash、Node.js、Python

---

### Task 1: 记录现状与验收标准

**Files:**
- Create: `docs/CI_SELF_HOSTED_RUNNER.md`
- Modify: `README.md:CI section (billing note)`

**Step 1: 明确验收标准**
- `CI_RUNS_ON` 未配置时：workflow 行为保持不变（仍用 `ubuntu-latest`）。
- `CI_RUNS_ON=self-hosted` 时：`Tests`/`Security Audit` 至少能启动并跑完核心 jobs（不因 Postgres service/dpkg 依赖失败）。
- 文档能指导用户在 GitHub UI 完成 runner 配置与变量设置。

---

### Task 2: 让 `Tests` workflow 支持 runner 可配置

**Files:**
- Modify: `.github/workflows/test.yml`

**Step 1: 为非 `e2e-tests` jobs 引入可配置 `runs-on`**
- 用 `runs-on: ${{ vars.CI_RUNS_ON || 'ubuntu-latest' }}` 替换固定的 `ubuntu-latest`（保持默认不变）。
- `e2e-tests`（手动触发的全量 E2E）保持 `runs-on: self-hosted`（按设计）。

**Step 2: Postgres service jobs 增加门控**
- `etl-e2e-smoke`、`api-snapshot-baseline`：在 `CI_RUNS_ON=self-hosted` 时默认跳过，除非 `CI_ENABLE_POSTGRES_JOBS=true`。

**Step 3: Playwright 安装在 self-hosted 环境避免 `--with-deps`**
- `e2e-smoke`：当 `CI_RUNS_ON=self-hosted` 时改用 `npx playwright install chromium`（不调用系统包管理器），并在文档中说明需提前安装系统依赖。

---

### Task 3: 让 `Security Audit` workflow 支持 runner 可配置

**Files:**
- Modify: `.github/workflows/security-audit.yml`

**Step 1: 替换 `runs-on: ubuntu-latest`**
- 改为 `runs-on: ${{ vars.CI_RUNS_ON || 'ubuntu-latest' }}`，保持默认不变。

---

### Task 4: 补齐 self-hosted runner 文档与排障指引

**Files:**
- Create: `docs/CI_SELF_HOSTED_RUNNER.md`
- Modify: `README.md`
- Modify: `SECURITY.md`（可选，补充 audit 运行方式）

**Step 1: 文档内容**
- GitHub UI 如何添加 self-hosted runner（repo settings → Actions → Runners）。
- 需要的系统依赖（Node/Python/可选 Docker、Playwright 依赖）。
- 如何设置 repo variable：`CI_RUNS_ON=self-hosted`（可选 `CI_ENABLE_POSTGRES_JOBS=true`）。
- 如何验证：push 一次或手动触发 `workflow_dispatch`，并用 `gh run list` 检查。

---

### Task 5: 本地验证 + 提交推送

**Step 1: 本地验证（不依赖 GitHub hosted runner）**

Run: `timeout 60 bash scripts/run-tests.sh ci`
Expected: `所有测试通过!`

**Step 2: 提交**

```bash
git add .github/workflows/test.yml .github/workflows/security-audit.yml docs/CI_SELF_HOSTED_RUNNER.md README.md
git commit -m "ci: support self-hosted runner fallback via CI_RUNS_ON"
```

**Step 3: 推送并检查**

```bash
git push origin main
gh run list --branch main --limit 5
```

Expected:
- 若仍用 `ubuntu-latest` 且账单/额度未修复：可能继续出现 “not started due to billing”；
- 若已配置 self-hosted runner + `CI_RUNS_ON=self-hosted`：workflow 可以正常启动并跑完。

