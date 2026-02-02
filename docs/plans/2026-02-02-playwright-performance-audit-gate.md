# Playwright Performance Audit Gate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** 让 `Tests` workflow 的 `Performance Audit (Playwright)` 在启用时真正成为“门禁”：当关键性能指标相对 baseline 发生显著回归时，job 直接 fail（可审计、可回滚）。

**Architecture:** 不改采样与指标生成逻辑，仅在比较阶段启用 `--fail-on-regression` 并收紧 `--regression-threshold`；同时补齐一个脚本级单测，确保门禁退出码行为可回归验证；同步更新 E2E/性能文档说明，避免误解“compare 只是报告不拦截”。

**Tech Stack:** GitHub Actions YAML、Node.js（`compare-performance-metrics.js`）、Bash（`scripts/tests`）、Markdown

---

## Task 1: 让 Performance Audit 真的会拦截回归（CI）

**Files:**
- Modify: `.github/workflows/test.yml`

**Steps:**
1. 在 `Performance Audit (Playwright)` job 的 compare 步骤中，将：
   - `node scripts/compare-performance-metrics.js ...`
   调整为带门禁参数：
   - `--fail-on-regression`
   - `--regression-threshold 5`
2. 本地快速校验 YAML 语法：
   - Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml','r',encoding='utf-8')); print('ok')"`
   - Expected: 输出 `ok`

---

## Task 2: 增加脚本级单测覆盖“门禁退出码”

**Files:**
- Create: `scripts/tests/test_compare_performance_metrics_gate.sh`
- Modify: `scripts/run-tests.sh`

**Steps:**
1. 新增 `scripts/tests/test_compare_performance_metrics_gate.sh`：
   - 构造 baseline/current 两份最小 JSON（只包含 compare 脚本读取的数值路径）。
   - 场景 A：回归超过 5% 时，带 `--fail-on-regression --regression-threshold 5` 应 exit 1。
   - 场景 B：回归不超过 5% 时，应 exit 0。
2. 将该脚本加入 `scripts/run-tests.sh` 的 `run_scripts_unit_tests()` 列表。
3. 运行脚本级单测：
   - Run: `bash scripts/run-tests.sh scripts-tests`
   - Expected: `scripts/tests/test_compare_performance_metrics_gate.sh` PASS

---

## Task 3: 同步更新文档（避免误导）

**Files:**
- Modify: `docs/testing/e2e/README.md`

**Steps:**
1. 在 “Performance Audit / performance-audit” 相关段落补充说明：
   - compare 会在回归超过阈值时 fail（默认阈值 5%）。
   - 若只是想生成报告但不拦截，可去掉 `--fail-on-regression`（或在本地运行 compare 命令不带该参数）。
2. 验证 docs-check：
   - Run: `bash scripts/run-tests.sh docs-check`
   - Expected: PASS

---

## Task 4: 提交与验证（可回滚）

**Steps:**
1. 最小验证：
   - `bash scripts/run-tests.sh scripts-tests`
   - `bash scripts/run-tests.sh docs-check`
2. Commit（建议单 commit，便于 revert）：
   - `git commit -m "ci(perf): enforce Playwright performance audit regression gate"`

