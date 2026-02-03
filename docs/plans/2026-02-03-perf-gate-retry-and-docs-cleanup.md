# Perf Gate Retry + Docs Cleanup Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.
>
> 现状与进度以 `docs/CURRENT_STATUS.md` 为准。

**Goal:** 提升 perf regression 在 self-hosted 环境的稳定性与可定位性：对 warmup 期间的 429/5xx 做有限重试（减少偶发误报），并同步相关文档入口与说明。

**Architecture:** 在两个 perf 回归脚本中为 warmup 请求增加“可配置、有限次数”的 retry/backoff；单元测试使用 mock server 模拟 429/5xx 一次后恢复，验证不会误失败；文档补充新参数与排障提示。

**Tech Stack:** Python 3（标准库）、pytest、GitHub Actions（self-hosted runner）。

---

### Task 1: 为 perf warmup 增加 retry/backoff（Overlap）

**Files:**
- Modify: `scripts/perf_overlap_regression.py`
- Test: `etl/tests/test_perf_overlap_regression_unit.py`

**Step 1: 扩展脚本参数（只影响 warmup）**
- 新增参数：
  - `--warmup-max-retries`（int，默认 2）
  - `--warmup-retry-base-sleep-ms`（int，默认 200）
- 行为：仅对 warmup 请求生效；遇到可重试状态（至少包含 429/502/503/504）才会 sleep 并重试。

**Step 2: 实现 warmup 重试**
- 新增 helper（示意，按项目风格落地）：
  - `_warmup_get_with_retry(url, timeout_seconds, max_retries, base_sleep_ms) -> None`
  - 对 `HTTPError` 提取 status code；可重试则指数退避（例如 200ms, 400ms, 800ms…）并继续；超限后抛 `WarmupRequestError`。

**Step 3: 补单元测试**
- 在 mock server 中增加“按序返回状态码”的能力（例如：`compare_status_sequence_by_gene_id={17276:[429,200]}`）。
- 新增测试：`test_perf_overlap_warmup_retries_on_429_then_succeeds`
  - 触发 compare warmup 第一次 429，第二次 200；期望 `generate-baseline` returncode=0。

---

### Task 2: 为 perf warmup 增加 retry/backoff（Genes/Regulations）

**Files:**
- Modify: `scripts/perf_genes_regulations_regression.py`
- Test: `etl/tests/test_perf_genes_regulations_regression_unit.py`

**Step 1: 扩展脚本参数（与 overlap 一致）**
- `--warmup-max-retries`（默认 2）
- `--warmup-retry-base-sleep-ms`（默认 200）

**Step 2: 实现 warmup 重试**
- 新增 helper：`_warmup_get_with_retry(...)`
- warmup 循环改用重试版 helper。

**Step 3: 补单元测试**
- mock server 增加对 `/api/v1/genes` 或 `/api/v1/regulations` 的状态序列控制（例如：`status_sequence_by_path={"/api/v1/genes":[503,200]}`）。
- 新增测试：`test_perf_genes_regulations_warmup_retries_on_503_then_succeeds`
  - 期望 `generate-baseline` returncode=0。

---

### Task 3: 文档同步（perf 回归测试说明）

**Files:**
- Modify: `docs/testing/performance/OVERLAP_PERF_REGRESSION.md`
- Modify: `docs/testing/performance/GENES_REGULATIONS_PERF_REGRESSION.md`
- Modify: `docs/ROADMAP_2026-02-03.md`（进度区追加 1 条）

**Step 1: 更新参数说明**
- 记录新增 warmup retry 参数与默认值，并解释什么时候需要调大/调小。

**Step 2: 更新排障提示**
- 增补：429 的典型根因与最小止损动作（例如 docker-sample 的 `RATE_LIMIT_BYPASS_PRIVATE=true`）。

---

### Task 4: 验证与提交

**Step 1: 快速验证**
- Run: `python3 -m py_compile scripts/perf_overlap_regression.py scripts/perf_genes_regulations_regression.py`
- Run: `pytest etl/tests/test_perf_overlap_regression_unit.py -q`
- Run: `pytest etl/tests/test_perf_genes_regulations_regression_unit.py -q`
- Run: `bash scripts/run-tests.sh docs-check`

**Step 2: 小步提交（可回滚）**
- Commit 1（代码+测试）：`perf: retry warmup requests in perf regression scripts`
- Commit 2（文档）：`docs(perf): document warmup retry knobs`
