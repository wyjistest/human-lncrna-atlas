# AntD Deprecations + Performance Explainability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> 提示（2026-01-26）：本文件为计划/设计记录；现状以 `docs/CURRENT_STATUS.md` 为准。

**Goal:** 按 `docs/ROADMAP_2026-01-21.md` 同步推进两件事：持续清理 Ant Design v6 deprecations（以控制台 warning 为准），以及增强性能可解释的“1 次导出 + 1 次截图”工作流可用性与稳定性。

**Architecture:** deprecations 采用“扫描 → 最小修复 → 小步防回归测试”策略（优先修正文档/示例里会触发 warning 的代码片段）；性能可解释侧优先提升 `scripts/admin_metrics_snapshot.py` 的可用性（环境变量默认值 + 代理环境下的 localhost 可靠访问），并用离线 mock server 的 pytest 覆盖关键行为。

**Tech Stack:** React + Ant Design v6 (Vitest) / Python stdlib scripts + pytest

---

### Task 1: 修正文档示例中的 `Alert.message` 弃用用法（TDD）

**Files:**
- Modify: `frontend/web/src/components/BatchGeneHeatmap/README.md`
- Create: `frontend/web/src/components/BatchGeneHeatmap/__tests__/BatchGeneHeatmap.antd-deprecations.test.ts`

**Step 1: Write the failing test**

新增一个 Vitest 测试，读取 `README.md` 并断言不出现 `<Alert ... message=...>`：

```ts
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('AntD deprecations (BatchGeneHeatmap docs)', () => {
  it('does not use deprecated Alert.message in README snippets', () => {
    const sourcePath = join(process.cwd(), 'src/components/BatchGeneHeatmap/README.md')
    const source = readFileSync(sourcePath, 'utf-8')
    expect(source).not.toMatch(/<Alert[^>]*\\bmessage\\s*=/)
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend/web && npm run test:run -- src/components/BatchGeneHeatmap/__tests__/BatchGeneHeatmap.antd-deprecations.test.ts`

Expected: FAIL（当前 README 示例仍包含 `message=`）。

**Step 3: Write minimal implementation**

将示例从：

`<Alert type="error" message={error.message} />`

改为：

`<Alert type="error" title={error.message} />`

**Step 4: Run test to verify it passes**

Run: `cd frontend/web && npm run test:run -- src/components/BatchGeneHeatmap/__tests__/BatchGeneHeatmap.antd-deprecations.test.ts`

Expected: PASS

**Step 5: Commit**

```bash
git add frontend/web/src/components/BatchGeneHeatmap/README.md \
  frontend/web/src/components/BatchGeneHeatmap/__tests__/BatchGeneHeatmap.antd-deprecations.test.ts
git commit -m "docs(frontend): avoid deprecated Alert.message in examples"
```

---

### Task 2: `admin_metrics_snapshot.py` 支持 env 默认值 + 代理环境下的 localhost 可靠访问（TDD）

**Files:**
- Modify: `scripts/admin_metrics_snapshot.py`
- Create: `etl/tests/test_admin_metrics_snapshot_env_defaults_unit.py`
- (Optional) Modify: `docs/PERFORMANCE_TRIAGE.md`
- (Optional) Modify: `.github/ISSUE_TEMPLATE/performance-triage.md`

**Step 1: Write the failing test**

起一个本地 mock server：
- `GET /api/v1/admin/metrics` 要求 header `X-Admin-API-Key`，否则返回 403
- 成功时返回最小 metrics JSON（空样本即可）

测试用例设置环境变量：
- `API_BASE_URL` 指向 mock server
- `ADMIN_API_KEY` 为预期 key
- `http_proxy/https_proxy` 指向不可用端口（模拟“全局代理但未设置 no_proxy”）
- 不传 `--base-url/--admin-api-key`，只传 `--out-dir tmp_path --timeout-seconds 1`

期望：脚本能成功导出并 exit 0（证明：读取 env 默认值 + 对 localhost 自动绕过代理）。

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q etl/tests/test_admin_metrics_snapshot_env_defaults_unit.py`

Expected: FAIL（当前脚本默认 base url 固定为 localhost:8000，且不读取 env；代理环境下可能无法连到 mock server）。

**Step 3: Write minimal implementation**

在 `scripts/admin_metrics_snapshot.py`：
- `--base-url` 默认值：优先 `API_BASE_URL` env（否则 fallback `http://localhost:8000`）
- `--admin-api-key` 默认值：优先 `ADMIN_API_KEY` env
- 若 `NO_PROXY/no_proxy` 未设置：默认补齐 `127.0.0.1,localhost,::1`（避免本地代理导致请求卡住/走代理）

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q etl/tests/test_admin_metrics_snapshot_env_defaults_unit.py`

Expected: PASS

**Step 5: Docs update（可选但推荐）**

在 `docs/PERFORMANCE_TRIAGE.md` 与 `.github/ISSUE_TEMPLATE/performance-triage.md` 补充说明：
- 若已设置 `API_BASE_URL`/`ADMIN_API_KEY`，可直接运行 `python3 scripts/admin_metrics_snapshot.py`（无需重复传参）

**Step 6: Commit**

```bash
git add scripts/admin_metrics_snapshot.py etl/tests/test_admin_metrics_snapshot_env_defaults_unit.py \
  docs/PERFORMANCE_TRIAGE.md .github/ISSUE_TEMPLATE/performance-triage.md
git commit -m "perf: make admin_metrics_snapshot respect env and proxy-safe"
```

---

### Task 3: 最小回归验证（本地）

**Step 1: Frontend unit tests**

Run: `cd frontend/web && npm run test:run`

Expected: PASS

**Step 2: ETL unit tests**

Run: `python -m pytest -q etl/tests`

Expected: PASS
