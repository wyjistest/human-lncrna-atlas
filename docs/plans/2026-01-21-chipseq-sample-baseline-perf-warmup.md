# ChIP-seq Sample Baseline + Performance Snapshot Warmup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 `schema/v2.3` 的最小样例库在安装 ChIP-seq schema 后可以产出 **非空** 的 overlap 结果，并强化性能定位的一键导出体验（样本不足时可选 warmup）。

**Architecture:** 在 baseline/CI 初始化时加载 `frontend/backend/sql/chipseq_schema.sql`，并在 `schema/v2.3/03_sample_data.sql` 中以“可选/可跳过”的方式插入最小 ChIP-seq experiment/peak；同时扩展 `scripts/api_snapshot.py` 的 `summaries` 输出（增加 overlap 统计摘要），以及为 `scripts/admin_metrics_snapshot.py` 增加可选 warmup 以补足 P95/P99 样本。

**Tech Stack:** Bash（baseline 脚本）、PostgreSQL（schema/sample data）、Python（`scripts/api_snapshot.py` / `scripts/admin_metrics_snapshot.py`）、pytest（`etl/tests`）、GitHub Actions（手动触发 workflow）。

---

## Task 1: API snapshot 增加 overlap summaries（TDD）

**Files:**
- Modify: `scripts/api_snapshot.py`
- Test: `etl/tests/test_api_snapshot_baseline_check.py`

**Step 1: Write failing test**
- 在 mock server 返回 overlap 响应的前提下，断言 `generated["summaries"]` 包含：
  - `overlap_total` / `overlap_items_len`
  - `overlap_stats_total_overlaps`（来自 `/statistics`）

**Step 2: Run test to verify it fails**
- Run: `python -m pytest -q etl/tests/test_api_snapshot_baseline_check.py::test_api_snapshot_check_baseline_matches`
- Expected: FAIL（缺少 summaries key）

**Step 3: Implement minimal code**
- 在 `scripts/api_snapshot.py:_snapshot()` 的 summaries 段落中，安全读取 overlap list/cursor/statistics 的关键字段并写入 summaries。

**Step 4: Run test to verify it passes**
- Run: `python -m pytest -q etl/tests/test_api_snapshot_baseline_check.py::test_api_snapshot_check_baseline_matches`
- Expected: PASS

---

## Task 2: sample DB 支持非空 overlap（最小 ChIP-seq peaks）

**Files:**
- Modify: `schema/v2.3/03_sample_data.sql`
- Modify: `scripts/baselines/generate_api_snapshot_baseline.sh`
- Modify: `scripts/baselines/generate_api_snapshot_baseline_local.sh`
- Modify: `.github/workflows/test.yml`

**Step 1: 更新 regulations 样例数据（让 join 可产生 overlap）**
- 在插入 `regulations` 时补齐：`best_peak_chr/best_peak_start/best_peak_end/best_site_ba`（至少 1 条落在 `chr22`）。

**Step 2: 条件化插入 chipseq_experiments + chipseq_peaks**
- 在 `03_sample_data.sql` 末尾增加 `DO $$ ... $$;`：
  - 若 `to_regclass('chipseq_experiments')` 或 `to_regclass('chipseq_peaks_human')` 为 NULL，则 `RAISE NOTICE` 并跳过（保持向后兼容）。
  - 否则：
    - 选取 `epigenetic_mark_types` 中 `H3K27ac` 的 `mark_type_id`
    - 插入 1 条 `chipseq_experiments`（species=1，is_active=true）
    - 插入 1 条 `chipseq_peaks`/`chipseq_peaks_human`（chr22，位置与 regulation.best_peak_* 重叠，qvalue<=1.0）

**Step 3: baseline/CI 初始化加载 chipseq schema**
- 在两份 baseline 生成脚本与 `.github/workflows/test.yml` 的 schema 加载列表中插入：
  - `frontend/backend/sql/chipseq_schema.sql`
  - 顺序：`01_core.sql` → `02_extension.sql` → `chipseq_schema.sql` → `03_sample_data.sql`

**Step 4: 验证 overlap 变为非空**
- Run: `bash scripts/baselines/generate_api_snapshot_baseline.sh`
- Check: `docs/baselines/api-snapshot.sample.json` 的 `summaries` 中 overlap 相关字段 > 0

---

## Task 3: 性能快照脚本增加可选 warmup（TDD）

**Files:**
- Modify: `scripts/admin_metrics_snapshot.py`
- Test: `etl/tests/test_admin_metrics_snapshot.py`（新建）
- Modify docs: `docs/PERFORMANCE_TRIAGE.md`

**Step 1: Write failing test**
- 起一个 mock server：
  - `/health`、`/api/v1/stats/overview` 等 warmup 目标路径会被请求计数
  - `/api/v1/admin/metrics` 返回的 `request.total` 反映上述计数
- 运行脚本：带 `--warmup-rounds 2`，断言输出 JSON/MD 写入 tmp 目录且 total requests 增加。

**Step 2: Run test to verify it fails**
- Run: `python -m pytest -q etl/tests/test_admin_metrics_snapshot.py`
- Expected: FAIL（脚本尚无 warmup 参数）

**Step 3: Implement minimal code**
- 为脚本增加参数：
  - `--warmup-rounds`（默认 0；>0 时执行 warmup）
  - `--warmup-timeout-seconds`（可选，默认复用 `--timeout-seconds`）
- warmup 行为：按固定路径列表循环请求（每轮一次），失败不致命但会打印 warning（不带敏感 header）。

**Step 4: Run test to verify it passes**
- Run: `python -m pytest -q etl/tests/test_admin_metrics_snapshot.py`
- Expected: PASS

**Step 5: 更新文档**
- 在 `docs/PERFORMANCE_TRIAGE.md` 补充：当 `n=<samples>/10` 样本不足时，可用 warmup 参数制造少量流量再导出。

---

## Task 4: 回归验证 + 交付

**Step 1: 重生成 baseline（确保 overlap 非空且 summaries 稳定）**
- Run: `bash scripts/baselines/generate_api_snapshot_baseline.sh`

**Step 2: 本地 CI**
- Run: `./scripts/run-tests.sh ci`

**Step 3: Commit & Push**
- Commit 1（B）：sample schema + baseline + workflow/script 更新
- Commit 2（C）：admin_metrics_snapshot warmup + docs + tests
- Push: `git push origin main`

