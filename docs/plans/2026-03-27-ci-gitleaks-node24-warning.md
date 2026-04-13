# CI Gitleaks Node24 Warning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 消除 `test.yml` 中 secret-scan job 因 `gitleaks/gitleaks-action@v2` 带来的 Node.js 20 deprecation warning，同时保留现有 secret scan 行为。

**Architecture:** 复用仓库里已经存在的 gitleaks CLI 下载与 filesystem fallback 模式，把 git history 扫描路径也统一为显式 `gitleaks git` 调用。这样可以移除对 `gitleaks-action@v2` 的 node20 运行时依赖，并继续在有 `.git` 时扫描历史、无 `.git` 时扫描工作区。

**Tech Stack:** GitHub Actions YAML、Bash、gitleaks CLI、actionlint

### Task 1: 固定回归约束

**Files:**
- Create: `scripts/tests/test_gitleaks_workflow_uses_cli.sh`
- Test: `scripts/tests/test_gitleaks_workflow_uses_cli.sh`

**Step 1: Write the failing test**

新增 shell 测试，断言：
- `.github/workflows/test.yml` 不再引用 `gitleaks/gitleaks-action@v2`
- workflow 同时保留 `gitleaks git` 与 `gitleaks dir` 两条扫描命令

**Step 2: Run test to verify it fails**

Run: `bash scripts/tests/test_gitleaks_workflow_uses_cli.sh`
Expected: FAIL，因为当前 workflow 仍包含 `gitleaks/gitleaks-action@v2`

### Task 2: 统一 secret-scan 的 gitleaks 执行路径

**Files:**
- Modify: `.github/workflows/test.yml`
- Modify: `SECURITY.md`
- Test: `scripts/tests/test_gitleaks_workflow_uses_cli.sh`

**Step 3: Write minimal implementation**

在 `secret-scan` job 中：
- 把 gitleaks 安装步骤改成统一前置步骤
- 删除 `uses: gitleaks/gitleaks-action@v2`
- 当 `has_git == true` 时显式执行 `gitleaks git`
- 当 `has_git != true` 时显式执行 `gitleaks dir`
- 保持 `results.sarif` 产物路径一致

**Step 4: Run test to verify it passes**

Run: `bash scripts/tests/test_gitleaks_workflow_uses_cli.sh`
Expected: PASS

### Task 3: 验证 workflow 语法与 CI 兼容性

**Files:**
- Modify: `.github/workflows/test.yml`
- Test: `.github/workflows/*.yml`

**Step 5: Run focused verification**

Run:
- `./tmp/actionlint .github/workflows/*.yml` 或等价 `actionlint` 命令
- `git diff --check`

Expected:
- workflow lint 通过
- 无 diff 格式错误

### Task 4: 远端验证 warning 是否消失

**Files:**
- Modify: `.github/workflows/test.yml`

**Step 6: Trigger and inspect GitHub Actions**

Run:
- `gh workflow run test.yml --ref <branch>`
- `gh run watch <run-id> --exit-status`
- `gh run view <run-id> --json jobs`

Expected:
- `test.yml` 全部关键 job 成功
- 不再出现 `gitleaks/gitleaks-action@v2` 的 Node.js 20 deprecation warning

### Task 5: 提交与交接

**Files:**
- Modify: `docs/plans/2026-03-27-ci-gitleaks-node24-warning.md`
- Modify: `.github/workflows/test.yml`
- Modify: `SECURITY.md`
- Create: `scripts/tests/test_gitleaks_workflow_uses_cli.sh`

**Step 7: Commit**

Run:
- `git add docs/plans/2026-03-27-ci-gitleaks-node24-warning.md .github/workflows/test.yml SECURITY.md scripts/tests/test_gitleaks_workflow_uses_cli.sh`
- `git commit -m "ci: replace gitleaks action with cli scan"`

**Step 8: Push**

Run: `git push`

**Step 9: Summarize**

记录新的 run id、验证结果、残余风险（如果有）。
