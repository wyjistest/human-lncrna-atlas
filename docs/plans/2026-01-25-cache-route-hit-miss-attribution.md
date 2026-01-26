# Cache Route Hit/Miss Attribution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> 提示（2026-01-26）：本文件为计划/设计记录；现状以 `docs/CURRENT_STATUS.md` 为准。

**Goal:** 在 `/api/v1/admin/metrics` 与 Admin/Monitoring UI 中，补齐 “按 route 归因的 cache hit/miss/requests/hit_rate_pct”，并与现有的 route compute attribution 合并展示，便于快速定位“哪个端点在频繁 miss / 命中率低 / 回源计算多且慢”。

**Architecture:** 在 `CacheService` 的 route stats 中新增 request/hit/miss 计数；`get_stats()` 的 `routes.top` 继续按 compute 总耗时排序（Compute Top），但每个 route item 同时携带 hit/miss/requests/hit_rate_pct 与 compute 指标；最后同步 schema、admin router、快照脚本与前端 UI/types/tests。

**Tech Stack:** FastAPI + Pydantic v2（backend），React + Ant Design（frontend），pytest/vitest/playwright（tests），GitHub Actions（self-hosted workflow_dispatch）。

---

### Task 1: Backend cache route stats（requests/hits/misses）

**Files:**
- Modify: `frontend/backend/app/core/cache.py`
- Test: `frontend/backend/tests/test_cache_route_stats_unit.py`

**Step 1: Write the failing test**

新增单测：在 request_context 绑定 route template 后，执行一次 miss + 一次 hit，断言 `cache.get_stats()["routes"]["top"][0]` 包含 `requests/hits/misses/hit_rate_pct`。

Run: `cd frontend/backend && .venv/bin/python -m pytest -m unit tests/test_cache_route_stats_unit.py -q`
Expected: FAIL（routes 为空或缺少字段）

**Step 2: Write minimal implementation**

- 在 `CacheService.get()` 中获取 `route_template = get_route_template()`，并在 `_stats_lock` 下记录 route request（hit/miss）。
- 新增 `_record_route_request_locked(route, hit=...)`，并让 `_record_route_compute_locked` 初始化同一份 stats dict（包含 request/hit/miss + compute 字段，避免分裂）。
- `get_stats()` 在 `stats["routes"]["top"]` 里输出 `requests/hits/misses/hit_rate_pct`（与 compute 并存）。

**Step 3: Verify GREEN**

Run: `cd frontend/backend && .venv/bin/python -m pytest -m unit tests/test_cache_route_stats_unit.py -q`
Expected: PASS

**Step 4: Commit**

Run:
`git add frontend/backend/app/core/cache.py frontend/backend/tests/test_cache_route_stats_unit.py && git commit -m "feat(cache): track route hit/miss stats"`

---

### Task 2: Admin metrics schema + router mapping

**Files:**
- Modify: `frontend/backend/app/schemas/monitoring.py`
- Modify: `frontend/backend/app/routers/admin.py`
- Test: `frontend/backend/tests/test_admin_metrics_middleware_unit.py`
- Test: `frontend/backend/tests/test_admin_metrics_snapshot_markdown_unit.py`（如需要扩展输出）

**Steps:**
1. 先更新单测：断言 `cache_breakdown.routes.top[0]` 的新字段存在且数值正确（monkeypatch `cache.get_stats`）。
2. 更新 schema：`CacheRouteBreakdownItem` 增加 `requests/hits/misses/hit_rate_pct`（保持 compute 字段不变）。
3. 更新 router：从 `stats["routes"]["top"]` 读取新字段并填充到 `CacheRouteBreakdownItem`。
4. 跑相关单测，确认通过。
5. Commit：`git commit -m "feat(metrics): include route cache hit/miss breakdown"`

---

### Task 3: Snapshot script（可选但推荐）

**Files:**
- Modify: `scripts/admin_metrics_snapshot.py`
- Test: `frontend/backend/tests/test_admin_metrics_snapshot_markdown_unit.py`

**Steps:**
1. 新增断言：routes block 里包含 `hit_rate`/`hits`/`misses`（或保持 compute-only，视输出简洁度）。
2. 更新脚本输出（Top 10）：`requests/hit_rate/hits/misses/compute_*`。
3. 跑单测，Commit：`git commit -m "docs(snapshot): enrich cache routes block with hit/miss"`

---

### Task 4: Frontend types + UI

**Files:**
- Modify: `frontend/web/src/types/monitoring.ts`
- Modify: `frontend/web/src/pages/Admin/Monitoring/components/CacheRoutesTable.tsx`
- Modify: `frontend/web/src/pages/Admin/Monitoring/index.test.tsx`
- Modify: `frontend/web/e2e/admin-monitoring-smoke.spec.ts`（如 mock 需补字段）

**Steps:**
1. 先更新 vitest：mock `cache_breakdown.routes.top[0]` 增加新字段，并断言新列标题/关键值出现。
2. 更新 TS types：`CacheRouteBreakdownItem` 增加 `requests/hits/misses/hit_rate_pct`。
3. 更新 UI：`CacheRoutesTable` 增加 Requests / Hit Rate / Hits / Misses 列（compute 列保留）。
4. 跑 `npm --prefix frontend/web run test:run`，Commit：`git commit -m "feat(monitoring): show route hit/miss in cache routes table"`

---

### Task 5: Verification + merge

**Steps:**
1. 本地：`bash scripts/run-tests.sh ci`
2. Push：`git push -u origin roadmap/cache-route`
3. 触发 self-hosted Actions：`gh workflow run Tests --ref roadmap/cache-route -f runs_on=self-hosted` + `gh workflow run Security Audit --ref roadmap/cache-route -f runs_on=self-hosted`
4. 绿了后合并到 `main`（fast-forward 或 PR merge），再触发 `main` 复核。
