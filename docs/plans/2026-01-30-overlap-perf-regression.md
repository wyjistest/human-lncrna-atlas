# Overlap Performance Regression Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
>
> 目标场景：`GET /api/v1/lncrna-chipseq-overlap` + `GET /api/v1/lncrna-chipseq-overlap/compare`
>
> 当前状态参考：`docs/CURRENT_STATUS.md`

**Goal:** 增加一个“Overlap 性能回归”门禁：可在 self-hosted runner 上手动触发（workflow_dispatch），基于 `GET /api/v1/admin/metrics` 的端点尾延迟/DB 百分位，对比仓库内 baseline，阻止明显回归（不阻塞 main push）。

**Architecture:** 新增 `scripts/perf_overlap_regression.py`（stdlib-only）。脚本先对 overlap list/compare 端点做固定参数 warmup（制造足够样本），再拉取 `/api/v1/admin/metrics`，提取并生成 compact snapshot JSON，最后与 repo baseline 对比并根据保守阈值判定 PASS/FAIL，同时输出 issue 友好的 Markdown 报告与 JSON 产物。

**Tech Stack:** Python 标准库 + `pytest`（离线单测，ThreadingHTTPServer mock API）。

## Task 1: 写 failing test（RED）

**Files:**
- Create: `etl/tests/test_perf_overlap_regression_unit.py`

**Step 1: Write the failing test**

- 起一个 `ThreadingHTTPServer`：
  - `GET /api/v1/lncrna-chipseq-overlap` 返回 200（内容随意）
  - `GET /api/v1/lncrna-chipseq-overlap/compare` 返回 200（内容随意）
  - `GET /api/v1/admin/metrics` 返回一个最小 JSON（包含 endpoints 列表，且包含 overlap/list 与 overlap/compare 的 `requests`、`percentiles(p95/p99)`、`db_percentiles(p95/p99)`）
- 用 `subprocess` 调脚本（还不存在）：
  - `python3 scripts/perf_overlap_regression.py check --base-url <server> --baseline-file <tmp>/baseline.json --out-dir <tmp>`
- 断言：当前应 FAIL（脚本不存在/参数未知）。

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest -q etl/tests/test_perf_overlap_regression_unit.py`
Expected: FAIL（缺少脚本或 exit code 非 0）。

## Task 2: 实现脚本最小能力（GREEN）

**Files:**
- Create: `scripts/perf_overlap_regression.py`

**Step 1: Implement CLI**

- 子命令：`check` 与 `generate-baseline`
- 参数：
  - `--base-url`（默认 `$API_BASE_URL` 或 `http://localhost:8000`）
  - `--admin-api-key`（默认 `$ADMIN_API_KEY`，用于拉取 `/api/v1/admin/metrics`）
  - `--out-dir`（默认 `docs/reports`）
  - `--baseline-file`（默认 `docs/baselines/performance/overlap-admin-metrics.baseline.json`）
  - `--warmup-rounds`（默认 20）
  - `--lncrna-gene-id`（默认 17276）
  - `--species-ids`（默认 `1,3`）
  - `--timeout-seconds`（默认 10）
- 默认设置 `NO_PROXY/no_proxy=127.0.0.1,localhost,::1`（如果用户未显式设置）。

**Step 2: Implement warmup + snapshot**

- warmup：循环 N 轮，每轮依次 GET：
  - `/api/v1/lncrna-chipseq-overlap?lncrna_gene_id=...&species_id=...`（用第一个 species）
  - `/api/v1/lncrna-chipseq-overlap/compare?lncrna_gene_id=...&species_ids=...`
- 拉取 `/api/v1/admin/metrics` 并从 `endpoints[]` 里找到对应 `path` 的统计信息。
- 生成 compact snapshot（JSON）并写入 out-dir（同时输出 Markdown 摘要）。

**Step 3: Run tests to verify it passes**

Run: `python3 -m pytest -q etl/tests/test_perf_overlap_regression_unit.py`
Expected: PASS

## Task 3: 加入 baseline 状态与门禁阈值（GREEN）

**Files:**
- Create: `docs/baselines/performance/overlap-admin-metrics.baseline.json`
- Modify: `scripts/perf_overlap_regression.py`

**Step 1: Add UNSET baseline**

- 新增 baseline 占位文件，`meta.status="UNSET"`（避免误用未初始化基线）。

**Step 2: Implement gating**

- `check` 模式遇到 `meta.status == "UNSET"`：直接 FAIL，并提示运行 `generate-baseline` 更新并提交基线。
- 对比字段（每个 endpoint）：
  - `response.p95_ms/p99_ms`
  - `db.p95_ms/p99_ms`
- 保守阈值（触发 FAIL）：
  - Response：同时满足 `>30%` 且 `>10ms`
  - DB：同时满足 `>30%` 且 `>2ms`
  - （更新：2026-02-01，现状以 `docs/testing/performance/OVERLAP_PERF_REGRESSION.md` 为准）
- 样本不足（requests < 10）或缺失字段：FAIL（避免“静默放过”）。

**Step 3: Run tests**

Run: `python3 -m pytest -q etl/tests/test_perf_overlap_regression_unit.py`
Expected: PASS（包含一个回归用例应触发 FAIL）。

## Task 4: 添加 GitHub Action（workflow_dispatch）

**Files:**
- Create: `.github/workflows/performance-overlap.yml`

**Step 1: Create workflow**

- 仅 `workflow_dispatch`
- inputs：
  - `runs_on`（默认空；取 `vars.CI_RUNS_ON` 或 `ubuntu-latest`）
  - `api_base_url`（默认 `http://127.0.0.1:8000`）
  - `mode`（`check`/`generate-baseline`）
  - `warmup_rounds`、`lncrna_gene_id`、`species_ids`
- self-hosted 时复用 `.github/workflows/test.yml` 的 tarball checkout 兜底逻辑（避免 git checkout 卡住）。
- 运行脚本并上传 artifacts（Markdown + compact snapshot + raw metrics）。

## Task 5: 更新文档（最短路径）

**Files:**
- Create: `docs/testing/performance/OVERLAP_PERF_REGRESSION.md`
- Modify: `docs/PERFORMANCE_TRIAGE.md`

**Step 1: Write docs**

- 文档说明：
  - 如何本地跑 `generate-baseline` 生成并提交 baseline
  - 如何跑 `check`、如何调阈值/参数
  - 常见失败：403（缺 Admin API Key）、样本不足、环境抖动
- `PERFORMANCE_TRIAGE.md` 增加一节链接到上面文档与 workflow 名称。
