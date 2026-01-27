# Frontend Bundle + Research Output Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** 按 roadmap 2.1/2.2 继续推进：减少首屏不必要的大 chunk（尤其避免 `pdf-vendor` 被首屏拉起），并产出一条可重复运行的 Phase 6.0 research 输出（BA>100 Top lncRNA CSV/Markdown）。

**Architecture:** 前端侧以“证据驱动”为先：用一个轻量 build 后检查脚本锁定首屏预加载列表，再通过 Vite 配置/拆分策略消除非必要预加载，并把检查纳入 `npm run build` 防回归。研究侧以“最小可复现产出”为先：提供一个脚本直连数据库聚合 `regulations.binding_affinity`，生成 Top lncRNA 统计文件与简要说明。

**Tech Stack:** React + Vite + TypeScript（前端）；Python（脚本）+ SQLAlchemy SessionLocal（复用后端 DB 配置）；GitHub Actions（CI）。

---

### Task 1: 记录首屏 modulepreload 列表（并加防回归检查）

**Files:**
- Create: `frontend/web/scripts/check-entry-preloads.mjs`
- (Optional) Modify: `frontend/web/package.json`

**Step 1: 写一个检查脚本（先让它在当前状态下失败）**

脚本逻辑：
- 读取 `frontend/web/dist/index.html`
- 提取所有 `<link rel="modulepreload" ... href="/assets/*.js">`
- 断言“首屏只允许 core vendor”：`react-vendor` / `query-vendor` / `i18n-vendor` / `antd-vendor`
- 如果发现 `pdf-vendor` / `igv-vendor` / `echarts-*` / `cytoscape-vendor` / `zip-vendor` 等，直接 `process.exit(1)` 并打印列表

**Step 2: 运行 build + 检查（预期 FAIL）**

Run:
`cd frontend/web && npm run build && node scripts/check-entry-preloads.mjs`

Expected:
- 退出码非 0
- 输出包含 `pdf-vendor`（当前已观察到被首屏 modulepreload）

**Step 3: Commit**

Run:
`git add frontend/web/scripts/check-entry-preloads.mjs && git commit -m "test(frontend): guard against eager modulepreload of heavy vendors"`

---

### Task 2: 修复首屏预加载（让 build 后检查通过）

**Files:**
- Modify: `frontend/web/vite.config.ts`

**Approach Options (choose one during execution):**
- **Option A (recommended):** `build.modulePreload = false`，禁用 Vite 的 modulepreload 机制，避免 `__vitePreload` helper 被放进大 chunk（导致首屏误拉起 `pdf-vendor`）。
- Option B: 调整 chunk 策略（如移除/改写 `pdf-vendor` manualChunks）把 preload helper 从大 chunk 挪走（风险：不确定性更高，需要多次试验）。

**Step 1: 应用 Option A（最小改动）**

在 `vite.config.ts` 的 `build` 配置下加入：
- `modulePreload: false`

**Step 2: 重新 build + 检查（预期 PASS）**

Run:
`cd frontend/web && npm run build && node scripts/check-entry-preloads.mjs`

Expected:
- 退出码 0
- `dist/index.html` 不再包含 `pdf-vendor` 的 modulepreload（或无 modulepreload）

**Step 3:（可选）把检查纳入 build**

若希望 CI 的 `npm run build` 自动防回归：
- 将 `frontend/web/package.json` 的 `build` 改为 `tsc -b && vite build && node scripts/check-entry-preloads.mjs`

**Step 4: Commit**

Run:
`git add frontend/web/vite.config.ts frontend/web/package.json && git commit -m "perf(frontend): avoid eager preload of pdf-vendor on first paint"`

---

### Task 3: Phase 6.0 最小 research 产出：BA>100 Top lncRNA

**Files:**
- Create: `scripts/research/top_lncrna_by_binding_affinity.py`
- Modify: `docs/PHASE_6.0_RESEARCH_ANALYSIS_PLAN.md`（或新增一份 docs/reports 说明文档）

**Step 1: 写脚本（支持可重复运行参数）**

脚本行为：
- 复用后端 DB 配置：`sys.path.insert(.../frontend/backend)` + `from app.core.database import SessionLocal`
- 参数：
  - `--species-id`（默认 1）
  - `--min-ba`（默认 100）
  - `--limit`（默认 50）
  - `--out-dir`（默认 `docs/reports`）
- 输出：
  - `top-lncrna-ba{min_ba}-species{species_id}.csv`
  - `top-lncrna-ba{min_ba}-species{species_id}.md`
- 指标（建议最小集）：
  - `lncrna_gene_id` / `lncrna_gene_name`
  - `regulations_count`（BA>=min_ba）
  - `target_genes_distinct`
  - `avg_ba` / `max_ba`

**Step 2: 本地运行（在有 DB 的环境下）**

Run:
`python3 scripts/research/top_lncrna_by_binding_affinity.py --species-id 1 --min-ba 100 --limit 50`

Expected:
- `docs/reports/` 下生成 CSV/MD 两个文件

**Step 3: 更新文档说明**

在 Phase 6.0 文档中加入：
- 产物路径
- 运行命令
- 输入依赖（需要可访问 DB；环境变量来源与后端一致）

**Step 4: Commit**

Run:
`git add scripts/research/top_lncrna_by_binding_affinity.py docs/PHASE_6.0_RESEARCH_ANALYSIS_PLAN.md && git commit -m "feat(research): export top lncRNA by binding affinity"`

---

### Task 4: 全链路验证 + 推送

**Step 1: 前端验证（最小必要）**

Run:
`cd frontend/web && npm run test:run && npm run lint && npm run build`

Expected:
- exit 0

**Step 2: 仓库级 CI gate（对齐既有流程）**

Run:
`bash scripts/run-tests.sh ci`

Expected:
- exit 0

**Step 3: Push**

Run:
`git push origin feat-frontend-bundle-research`

（如要直接落 main，再执行 merge/fast-forward 策略；默认走 PR 更安全）

