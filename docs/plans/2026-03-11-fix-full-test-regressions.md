# Full Test Regression Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复当前 `bash scripts/run-tests.sh all` 暴露的高优先级回归，使后端核心接口与关键 E2E 套件重新稳定。

**Architecture:** 先处理真实后端故障，再修正过期测试数据和脆弱 E2E 断言。优先保证 `/api/v1/genes`、固定测试 ID、批量查询与语言切换等基础契约稳定，再回归受影响测试。

**Tech Stack:** FastAPI, pytest, React, React Query, Ant Design, Playwright, Vite

### Task 1: `/api/v1/genes` 第 5 条记录触发 500

**Files:**
- Modify: `frontend/backend/...`（待定位具体 service/router/schema 文件）
- Test: `frontend/backend/tests/...` 或新增最小回归测试

**Step 1: 写出能稳定复现 page_size=5 / gene_id=5 失败的测试**

**Step 2: 运行测试，确认先红**

**Step 3: 修复列表序列化或数据映射链路中的根因**

**Step 4: 重跑对应测试，确认转绿**

### Task 2: 过期固定测试 ID 改为动态可用数据

**Files:**
- Modify: `frontend/backend/tests/conftest.py`
- Modify: `frontend/web/e2e/api/chipseq-compare.spec.ts`
- Possibly modify: 其他直接硬编码 `17276` / `804941` 的测试文件

**Step 1: 写测试或查询辅助逻辑，先找当前环境真实存在的 gene/regulation/chipseq 数据**

**Step 2: 让旧固定 ID 的测试先以当前环境失败，确认红灯**

**Step 3: 改成动态发现或环境变量回退策略**

**Step 4: 重跑相关 API 合同测试和 `chipseq-compare` 套件**

### Task 3: 修复批量查询与 gene_id selector 的 E2E 契约漂移

**Files:**
- Modify: `frontend/web/e2e/genes-flow.spec.ts`
- Modify: `frontend/web/e2e/regulations-smoke.spec.ts`
- Reference: `frontend/web/src/pages/Genes/index.tsx`
- Reference: `frontend/web/src/pages/Regulations/components/AdvancedFilters.tsx`

**Step 1: 为当前真实交互写出最小失败断言**

**Step 2: 确认旧测试因过期输入或错误交互路径失败**

**Step 3: 改成匹配当前 UI 的请求/URL 更新契约**

**Step 4: 重跑对应 Playwright 定向用例**

### Task 4: 修复错误态与语言切换的脆弱 E2E

**Files:**
- Modify: `frontend/web/e2e/error-states-global.spec.ts`
- Modify: `frontend/web/e2e/navigation/menu.spec.ts`
- Modify: `frontend/web/e2e/lncrna-chipseq-overlap.spec.ts`
- Reference: `frontend/web/src/components/LanguageSwitch.tsx`

**Step 1: 用失败快照验证当前 UI 实际文案/交互**

**Step 2: 先让针对 404/503 与语言切换的测试稳定失败**

**Step 3: 改成基于 `ErrorState` 与 Ant Design `Select` 的稳定断言/操作**

**Step 4: 重跑定向 Playwright**

### Task 5: 最终回归

**Files:**
- No code changes expected

**Step 1: 跑受影响的后端 pytest**

**Step 2: 跑受影响的前端 Vitest / Playwright**

**Step 3: 必要时重跑 `bash scripts/run-tests.sh all` 或其最小等价子集**

**Step 4: 汇总剩余风险与未覆盖项**
