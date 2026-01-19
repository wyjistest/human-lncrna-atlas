# Roadmap A/B/C Implementation Plan
> **For Codex:** 执行时逐条完成；每个 task 保持小步提交（commit 粒度清晰、可回滚）。

**Goal:** 在不破坏现有 API/数据格式的前提下，补齐“可回归数据基线 + 更强可观测性 + 更多完全 mocked 的 E2E smoke”，让迭代更稳、更可重复。

**Architecture:** 以现有 in-memory monitoring 与 CI smoke 为基础：后端在采集侧做低开销聚合（固定窗口、限制 cardinality），在读取侧计算分位数；前端只展示新增字段；E2E 通过 Playwright network interception 保持完全离线可跑。

**Tech Stack:** FastAPI / Pydantic v2 / SQLAlchemy / React + TypeScript / Playwright / GitHub Actions

---

## Task 1: Mocked E2E Smoke - Admin Monitoring

**Files:**
- Create: `frontend/web/e2e/admin-monitoring-smoke.spec.ts`
- Modify: `.github/workflows/test.yml`
- (Optional) Docs: `docs/testing/e2e/README.md`

**Step 1: 添加 Playwright spec（完全 mock /api/v1/admin/metrics）**
- 验收：`/admin/monitoring` 可加载；页面包含 “System Monitoring” 与 “Cache Get Latency”；展示 P50/P95/P99 文本。

**Step 2: 在 CI 的 `e2e-smoke` job 中运行该 spec**
- 验收：`e2e-smoke` 仍保持无需后端/DB，可在 ubuntu-latest 通过。

---

## Task 2: Admin Metrics - Endpoint 级别响应时间百分位

**Files:**
- Modify: `frontend/backend/app/middleware/admin_metrics.py`
- Modify: `frontend/backend/app/routers/admin.py`
- Modify: `frontend/backend/app/schemas/monitoring.py`
- Modify: `frontend/backend/tests/test_admin_metrics_middleware_unit.py`
- Modify: `frontend/web/src/types/monitoring.ts`
- Modify: `frontend/web/src/pages/Admin/Monitoring/components/EndpointTable.tsx`
- Modify: `frontend/web/src/pages/Admin/Monitoring/index.test.tsx`

**Step 1: 写后端单测（先失败）**
- 目标：`GET /api/v1/admin/metrics` 的 `endpoints[*]` 返回 `percentiles`（p50/p95/p99，数据不足则为 null）。

**Step 2: 采集侧（middleware）加 per-endpoint ring buffer**
- 约束：限制 endpoints 数量（沿用 `_max_endpoints`），每个 endpoint 的样本队列 maxlen 固定（例如 200）。
- 目标：不增加高基数，不在热路径排序。

**Step 3: 读取侧（admin router）计算百分位并写入响应**
- 复用已有 `calculate_percentiles()`；对每个 endpoint 的样本列表计算。

**Step 4: 前端表格展示 p95/p99（数据不足显示 “-”）**
- 目标：EndpointTable 增加列；不改变现有列语义。

---

## Task 3: CI - 校验 ETL sample inputs manifest（防止样例被意外改坏）

**Files:**
- Modify: `.github/workflows/test.yml`
- (Optional) Docs: `etl/sample_inputs/README.md`

**Step 1: 在 `backend-checks` job 增加一步 manifest verify**
- 命令：`python -m etl.input_manifest verify etl/sample_inputs/etl-inputs.manifest.tsv`
- 验收：文件被意外改动会 fail-fast 提示 bytes/lines/sha256 mismatch。

---

## Task 4: 文档与回归

**Files:**
- Modify: `docs/ROADMAP_2026-01-17.md`
- (Optional) Modify: `README.md`

**Step 1: 更新 Roadmap 进度条目**
- 记录新增 smoke 覆盖与 endpoint percentiles 的完成情况。

---

## Verification

**Local (fast):**
- `./scripts/run-tests.sh ci`

**CI:**
- `gh run list --branch main --workflow Tests --limit 3`
- `gh run watch <run_id> --exit-status`

