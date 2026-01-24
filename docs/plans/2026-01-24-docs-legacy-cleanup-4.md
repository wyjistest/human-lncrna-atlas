# Docs Legacy Cleanup 4 Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** 继续清理历史文档中的「待办/未实现」语义，避免读者误解为当前 roadmap/backlog。

**Architecture:** 不删除历史内容；在文档关键位置补充“历史快照/模板说明/现状参考”的注释，统一以 `docs/CURRENT_STATUS.md` 作为当前权威状态来源。

**Tech Stack:** Markdown 文档维护（无代码行为变更）。

## Tasks

### Task 1: 扫描与分组

**Files:**
- Inspect: `docs/**`（重点：含 `[ ]`/TODO/待实现/未实现 的文档）

**Steps:**
1. 使用 `rg -n "\\[ \\]" docs` 与 `rg -n "TODO|待实现|未实现" docs` 定位候选点
2. 仅对“历史报告/阶段总结/规划快照/模板清单”补充说明，避免破坏可执行清单的用途

### Task 2: 更新文档说明（历史/模板/快照）

**Files:**
- Modify: `docs/PHASE_1_FINAL_ACCEPTANCE.md`
- Modify: `docs/PHASE_2.9_HEATMAP_MATRIX.md`
- Modify: `docs/PHASE_3.0_LNCRNA_CHIPSEQ_OVERLAP.md`
- Modify: `docs/phases/PHASE1_FINAL_INTEGRATION_COMPLETE.md`
- Modify: `docs/SECURITY_DEPLOYMENT.md`

**Steps:**
1. 在“后续行动/未来改进/任务清单/检查清单”等段落前添加注释：该段为历史快照或执行模板，不代表当前待办
2. 统一指向 `docs/CURRENT_STATUS.md`

### Task 3: 验证与集成

**Steps:**
1. 运行文档/CI 脚本（本仓库约定）确保无回归
2. 提交变更并合并回 `main`

