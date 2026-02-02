# Tests Self-hosted Checkout Fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** 让 `Tests` workflow 在 `workflow_dispatch + self-hosted` 场景下，即使 `actions/checkout` 被取消/超时，也能稳定触发 tarball 兜底并继续执行。

**Architecture:** 保持现有“checkout → (continue-on-error) → tarball recovery”结构不变，只把恢复条件从 `outcome == failure` 扩展为 `outcome != success`，覆盖 `cancelled` 等状态；对依赖 git 的步骤在 fallback 场景继续初始化 “git snapshot”。

**Tech Stack:** GitHub Actions YAML、bash（`scripts/ci/checkout_tarball.sh`）、`gh` CLI（用于触发与核验 run）。

---

### Task 1: 证据收集（已完成）

**Files:**
- Reference: `.github/workflows/test.yml`

**Step 1: 拉取失败样本日志**

Run: `gh run view 21565229937 --log --job 62135566473`

Expected: `actions/checkout` fetch 阶段出现 `Failed to connect to github.com port 443: Connection timed out`，且 step 可能以 `cancelled` 结束，导致后续 recovery 条件不命中。

---

### Task 2: 扩展 checkout recovery 条件（YAML 修改）

**Files:**
- Modify: `.github/workflows/test.yml`

**Step 1: 把所有 `steps.checkout.outcome == 'failure'` 改为 `steps.checkout.outcome != 'success'`**

覆盖 self-hosted checkout step 可能出现的 `cancelled`/`failure` 两种非成功状态。

**Step 2: 同步更新 `Prepare git snapshot` 等依赖相同条件的步骤**

保持 fallback 场景可运行 `git ls-files` 等命令。

**Step 3: 本地快速校验 YAML 语法**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/test.yml','r',encoding='utf-8')); print('ok')"`

Expected: 输出 `ok`

**Step 4: Commit**

Run:

```bash
git add .github/workflows/test.yml docs/plans/2026-02-02-tests-self-hosted-checkout-fallback.md
git commit -m "ci: recover tarball checkout when checkout is cancelled"
```

---

### Task 3: 触发 workflow_dispatch 验证（self-hosted）

**Files:**
- None

**Step 1: 触发 Tests workflow（self-hosted）**

Run (example):

```bash
gh workflow run Tests -f runs_on=self-hosted -f enable_postgres_jobs=false -f enable_e2e_tests=false -f enable_performance_audit=false
```

**Step 2: 观察 run 是否仍卡在 checkout，并确认 fallback 可继续**

Run: `gh run list -w Tests --limit 5`

Expected: 触发的新 run 最终 `success`（或至少不因 checkout cancelled 而直接失败）。

---

### Task 4: 收尾（可选）

**Files:**
- None

**Step 1: 合并到 main 并清理分支/工作区**

- Merge 方式：squash merge（保持 main 历史整洁）
- 删除远端与本地分支（若不再需要）

