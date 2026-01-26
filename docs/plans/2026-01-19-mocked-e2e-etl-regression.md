# Mocked E2E + ETL Regression Anchors Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.
> 提示（2026-01-26）：本文件为计划/设计记录；现状以 `docs/CURRENT_STATUS.md` 为准。

**Goal:** 扩展完全 mocked 的 Playwright e2e-smoke 覆盖（优先 Genes/Regulations 核心数据页），并把 ETL sample import 的回归锚点升级为“值级别校验”，让 CI 与本地复刻更稳、更可定位。

**Architecture:** 前端侧为关键页面补齐 `data-testid` 稳定选择器；Playwright smoke 通过 `page.route()` 拦截并返回最小 JSON 合约响应，确保离线可跑。ETL 侧新增一个可复用的 sample import 校验脚本：连接 CI Postgres，读取并断言导入结果（count + 关键字段 + sequences），避免“行数通过但内容漂移”。

**Tech Stack:** React + TypeScript + Ant Design / Playwright / FastAPI + PostgreSQL / GitHub Actions / Python

---

### Task 1: Genes 页面稳定选择器 + 单测

**Files:**
- Modify: `frontend/web/src/pages/Genes/index.tsx`
- Create: `frontend/web/src/pages/Genes/index.test.tsx`

**Step 1: 写 failing test（先验收目标）**

```ts
// 断言 Genes 页面具备稳定锚点
expect(screen.getByTestId('genes-page')).toBeInTheDocument()
expect(screen.getByTestId('genes-table')).toBeInTheDocument()
```

**Step 2: 实现最小改动**
- 给页面容器添加 `data-testid="genes-page"`。
- 给表格区域添加 `data-testid="genes-table"`（用 wrapper div，避免依赖 AntD DOM）。

**Step 3: 运行并确认通过**
- Run: `./scripts/run-tests.sh unit`
- Expected: PASS

**Step 4: Commit**
- `git add frontend/web/src/pages/Genes/index.tsx frontend/web/src/pages/Genes/index.test.tsx`
- `git commit -m "test(e2e): add stable selectors for genes page"`

---

### Task 2: Regulations 页面稳定选择器 + 单测

**Files:**
- Modify: `frontend/web/src/pages/Regulations/index.tsx`
- Create: `frontend/web/src/pages/Regulations/index.test.tsx`

**Step 1: 写 failing test**
- mock `useRegulations()` 返回最小分页数据
- mock `useBARange()`（`@/hooks/useDetailedStats`）返回最小 BA range
- 断言页面锚点与表格锚点存在

**Step 2: 实现最小改动**
- 给页面容器添加 `data-testid="regulations-page"`。
- 给表格区域添加 `data-testid="regulations-table"`（wrapper div）。

**Step 3: 运行并确认通过**
- Run: `./scripts/run-tests.sh unit`
- Expected: PASS

**Step 4: Commit**
- `git add frontend/web/src/pages/Regulations/index.tsx frontend/web/src/pages/Regulations/index.test.tsx`
- `git commit -m "test(e2e): add stable selectors for regulations page"`

---

### Task 3: 新增 mocked Playwright smoke（Genes/Regulations）并接入 CI

**Files:**
- Create: `frontend/web/e2e/genes-smoke.spec.ts`
- Create: `frontend/web/e2e/regulations-smoke.spec.ts`
- Modify: `.github/workflows/test.yml`
- Modify: `scripts/run-tests.sh`
- (Optional) Docs: `docs/testing/e2e/README.md`

**Step 1: Genes smoke**
- intercept `**/api/v1/genes*` 返回 1 条记录（total=1 避免 prefetch）
- 断言 `admin` 外其它页面不依赖 i18n 文案：使用 `getByTestId('genes-page')` + gene_id 文本

**Step 2: Regulations smoke**
- intercept `**/api/v1/regulations*` 返回 1 条记录（total=1）
- intercept `**/api/v1/stats/ba-range` 返回 `BARange`
- 断言 `getByTestId('regulations-page')` + regulation_id 文本

**Step 3: 接入 CI / 本地 e2e-smoke**
- 将新 spec 加入 `.github/workflows/test.yml` 的 `npx playwright test ...` 列表
- 将新 spec 加入 `./scripts/run-tests.sh e2e-smoke` 列表

**Step 4: 本地验证**
- Run: `./scripts/run-tests.sh e2e-smoke`
- Expected: PASS

**Step 5: Commit**
- `git add frontend/web/e2e/*.spec.ts .github/workflows/test.yml scripts/run-tests.sh docs/testing/e2e/README.md`
- `git commit -m "test(e2e): add mocked smoke for genes/regulations"`

---

### Task 4: 强化 ETL sample import 回归校验（值级别）

**Files:**
- Create: `etl/smoke_verify_sample_import.py`
- Modify: `.github/workflows/test.yml`
- (Optional) Docs: `etl/sample_inputs/README.md`

**Step 1: 写校验脚本（可复用）**
- 读取 `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`
- 断言：
  - `regulations` 行数为 2
  - `import_batches` 至少 1 条（batch_type='regulations'）
  - JOIN `genes` + `regulations` + `sequences`，逐行比对样例中的关键字段（lncrna/target ensembl id、chr/start/end、best_avg_ba、best_site_ba、sequences）

**Step 2: CI 调整**
- 在 sample import 命令启用 `--store-sequences`（让 sequences 可被值级校验）
- 在 ETL E2E smoke job 用该脚本替换/补充原本 inline Python verify step

**Step 3: 本地验证（最小）**
- Run: `./scripts/run-tests.sh ci`
- Expected: PASS

**Step 4: Commit**
- `git add etl/smoke_verify_sample_import.py .github/workflows/test.yml etl/sample_inputs/README.md`
- `git commit -m "test(etl): strengthen sample import verification"`

---

### Task 5: Final verification + Push

**Steps:**
1. `./scripts/run-tests.sh ci`
2. `./scripts/run-tests.sh e2e-smoke`
3. `./scripts/run-tests.sh security-audit`
4. `git push origin main`
5. `gh run watch <run_id> --exit-status`（`Tests` + `Security Audit`）
