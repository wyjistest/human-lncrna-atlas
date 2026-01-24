# Docs Legacy Cleanup 6 Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** 继续为 checklist/计划类文档补充“模板/快照/非当前待办”说明，统一指向 `docs/CURRENT_STATUS.md`，降低读者误解成本。

**Architecture:** 仅增加少量 blockquote 说明行；不改动原始清单内容与结构。

**Tech Stack:** Markdown 文档维护（无行为变更）。

## Tasks

### Task 1: Sessions/Research/Testing/Deploy 文档补充说明

**Files:**
- Modify: `docs/sessions/SESSION_PHASE4_NETWORK_I18N.md`
- Modify: `docs/archive/technical_research.md`
- Modify: `docs/testing/e2e/DATA_TESTID_REQUIREMENTS.md`
- Modify: `docs/PERFORMANCE_ISSUE_ANALYSIS.md`
- Modify: `docs/testing/e2e/PERFORMANCE_TEST_STRATEGY.md`
- Modify: `docs/backend/DEPLOYMENT.md`
- Modify: `docs/api/REGULATIONS_API_INTEGRATION_PLAN.md`
- Modify: `docs/frontend/PLAN_P2_OPTIMIZATION.md`

**Steps:**
1. 在标题或摘要段落附近加入“模板/快照/不代表当前开发待办”的说明
2. 明确现状以 `docs/CURRENT_STATUS.md` 为准

### Task 2: 验证与集成

**Steps:**
1. 运行 `python3 scripts/check_docs_commands.py`
2. 提交、合并回 `main` 并推送（pre-push 本地 CI 会自动跑）

