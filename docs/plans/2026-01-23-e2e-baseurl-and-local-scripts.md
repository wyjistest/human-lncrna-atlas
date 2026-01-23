# E2E BaseURL + Local Scripts Configurability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 统一 E2E/性能测试与本地脚本的 BaseURL 来源，避免硬编码 `localhost:5173/8000` 导致的多环境不可复用与排障困难。

**Architecture:** Playwright 测试报告里的 `frontend_url` 改为读取 `testInfo.project.use.baseURL`（与实际运行一致）；本地脚本统一支持 `BASE_URL` / `API_BASE_URL` 覆盖，并保持默认值不变（仍为 localhost），保证向后兼容。

**Tech Stack:** Playwright (TS) / Bash scripts

---

### Task 1: 性能 E2E 报告读取真实 baseURL

**Files:**
- Modify: `frontend/web/e2e/performance/disease-dropdown-performance.spec.ts`

**Step 1: 写一个最小自测（执行级验证）**
- Run: `cd frontend/web && BASE_URL=http://example.invalid npx playwright test e2e/performance/disease-dropdown-performance.spec.ts --list`
- Expected: 命令可正常输出测试列表（不需要真正访问 URL）。

**Step 2: 实现：用 `testInfo.project.use.baseURL` 写入 report**
- 目标：`report.environment.frontend_url` 优先取 `testInfo.project.use.baseURL`，其次退化到 `process.env.BASE_URL`，最后为 `unknown`（不再硬编码 localhost）。
- 约束：不改变现有 `page.goto(PAGE_URL)` 的行为（仍使用相对路径 + Playwright baseURL）。

**Step 3: 验证**
- Run: `cd frontend/web && BASE_URL=http://localhost:5173 npx playwright test e2e/performance/disease-dropdown-performance.spec.ts -g \"P0\" --reporter=line`
- Expected: 至少能启动并执行（环境缺服务时允许失败，但 `test-results/performance-latest-metrics.json` 的 `environment.frontend_url` 不应写死 localhost）。

**Step 4: Commit**
- `git add frontend/web/e2e/performance/disease-dropdown-performance.spec.ts`
- `git commit -m "test(e2e): record Playwright baseURL in perf report"`

---

### Task 2: 本地测试脚本支持 BASE_URL / API_BASE_URL

**Files:**
- Modify: `scripts/run-tests.sh`
- Modify: `scripts/run_chipseq_tests.sh`
- (Optional) Modify: `docs/testing/e2e/README.md`

**Step 1: 实现：把脚本中的 localhost URL 参数化**
- 默认值保持不变：
  - `API_BASE_URL` 默认 `http://localhost:8000`
  - `BASE_URL` 默认 `http://localhost:5173`
- `check_services`/`check_*_server` 使用环境变量拼接路径，不再内联常量。
- `--help`/提示文案同步更新。

**Step 2: 验证（不依赖服务）**
- Run: `bash -n scripts/run-tests.sh scripts/run_chipseq_tests.sh`
- Expected: 语法检查通过（exit code 0）。

**Step 3: 验证（有服务时）**
- Run: `BASE_URL=http://localhost:5173 API_BASE_URL=http://localhost:8000 ./scripts/run-tests.sh status`
- Expected: 能正确检查并输出服务状态（与原行为一致）。

**Step 4: Commit**
- `git add scripts/run-tests.sh scripts/run_chipseq_tests.sh docs/testing/e2e/README.md`
- `git commit -m "chore: make local test scripts respect BASE_URL env"`

