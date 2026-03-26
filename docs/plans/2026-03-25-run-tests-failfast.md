# run-tests Fail-Fast Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 `scripts/run-tests.sh`，确保前端 `npm ci` 或后端 `pip install` 失败时立即返回非 0，并阻断后续 stage，避免假阳性通过。

**Architecture:** 保持现有 `ensure_frontend_deps()` / `ensure_backend_deps()` 结构不变，只把“依赖安装”从“忽略退出码后返回 0”改成“显式检查失败并返回 1”。测试继续沿用 `scripts/tests/` 里的 shell 回归模式，在临时目录中复制最小仓库结构，通过 fake npm / fake python 复现失败场景。

**Tech Stack:** Bash, shell regression tests, fake command injection via `PATH`

### Task 1: 前端失败用例

**Files:**
- Create: `scripts/tests/test_run_tests_frontend_deps_install_failure.sh`
- Modify: none
- Test: `scripts/tests/test_run_tests_frontend_deps_install_failure.sh`

**Step 1: Write the failing test**

构造 `package-lock.json` 漂移场景，并让 fake `npm ci` 返回 42；断言 `bash scripts/run-tests.sh frontend-lint` 必须非 0 退出，且不能继续把结果当作通过。

**Step 2: Run test to verify it fails**

Run: `bash scripts/tests/test_run_tests_frontend_deps_install_failure.sh`
Expected: FAIL，因为当前脚本会在 `npm ci` 失败后继续执行并返回 0。

### Task 2: 后端失败用例

**Files:**
- Create: `scripts/tests/test_run_tests_backend_deps_install_failure.sh`
- Modify: none
- Test: `scripts/tests/test_run_tests_backend_deps_install_failure.sh`

**Step 1: Write the failing test**

构造 backend venv 依赖漂移场景，并让 fake `python -m pip install` 返回 17；断言 `bash scripts/run-tests.sh backend-unit` 必须非 0 退出。

**Step 2: Run test to verify it fails**

Run: `bash scripts/tests/test_run_tests_backend_deps_install_failure.sh`
Expected: FAIL，因为当前脚本会吞掉 `pip install` 的失败并继续执行。

### Task 3: 最小修复脚本逻辑

**Files:**
- Modify: `scripts/run-tests.sh`
- Test: `scripts/tests/test_run_tests_frontend_deps_install_failure.sh`
- Test: `scripts/tests/test_run_tests_backend_deps_install_failure.sh`

**Step 1: Write minimal implementation**

在 `ensure_frontend_deps()` 和 `ensure_backend_deps()` 里显式判断依赖安装命令退出码；失败时打印错误并 `return 1`，成功时才继续写 stamp 或返回 0。

**Step 2: Run targeted tests**

Run:
- `bash scripts/tests/test_run_tests_frontend_deps_install_failure.sh`
- `bash scripts/tests/test_run_tests_backend_deps_install_failure.sh`

Expected: PASS

### Task 4: 回归验证

**Files:**
- Test: `scripts/tests/test_run_tests_frontend_deps.sh`
- Test: `scripts/tests/test_run_tests_backend_deps.sh`
- Test: `scripts/tests/test_run_tests_backend_checks_propagates_failures.sh`

**Step 1: Run regression checks**

Run:
- `bash scripts/tests/test_run_tests_frontend_deps.sh`
- `bash scripts/tests/test_run_tests_backend_deps.sh`
- `bash scripts/tests/test_run_tests_backend_checks_propagates_failures.sh`

Expected: PASS，确认旧行为不回退，失败传播逻辑仍然正确。
