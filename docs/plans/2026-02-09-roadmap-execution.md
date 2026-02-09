# 1–2 周路线图落地（hg19 审计 + 轨道补齐 + 门禁/文档）实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** 在保持“可审计、可回滚、可定位”的前提下，完成 hg19 外部数据/轨道一致性补齐，并同步推进性能门禁与文档清理。

**Architecture:** 以“先恢复可构建（CI/依赖）→ 再补齐轨道（DB 元数据 + 导出/转换）→ 最后收口文档与门禁”为主线；每个主题独立 commit/PR，确保 `git revert <sha>` 可回滚。

**Tech Stack:** GitHub Actions（self-hosted）、Python（后端脚本 + 审计）、Postgres（`lncrna_production`）、UCSC bigBed 工具（`bedToBigBed_v369/v385`）。

---

## Task 1：Dependabot 止损（避免再次合入已知破坏性 major）

**Files:**
- Modify: `.github/dependabot.yml`
- (Optional) Modify: `docs/CI_SELF_HOSTED_RUNNER.md`

**Step 1: 增加 ignore 规则（eslint / @eslint/js 的 semver-major）**
- 目标：阻止 Dependabot 继续创建/推荐 eslint v10 这类当前与 `@typescript-eslint/*` 不兼容的升级 PR。

**Step 2: 文档补充“合并依赖 PR 的最小核验流程”**
- 目标：明确“先本地跑 `./scripts/run-tests.sh ci` 再 merge”，避免再次在 main 上引入不可构建状态。

**Step 3: 本地只读核验**
- Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/dependabot.yml')); print('OK')"`
- Expected: `OK`

**Step 4: Commit**
- `git add .github/dependabot.yml docs/CI_SELF_HOSTED_RUNNER.md`
- `git commit -m "chore(dependabot): ignore eslint major updates for stability"`

---

## Task 2：修复 DB 元数据与轨道“缺口”（补齐 cell_line 归并）

**Context (Why):**
- 当前 `scripts/export_chipseq_bed.py` 按 `chipseq_experiments.cell_type` 导出，导致同一 cell line（例如 GM12878）被拆到多个 bed（如 `chipseq_GM12878.bed` + `chipseq_B_lymphocyte.bed`），从而 `genomes/chipseq_GM12878.bb` 不包含全部 marks。
- 目标：补齐/修正导出维度为 `cell_line`，让 `chipseq_<CellLine>.bb` 真正包含该 cell line 的全部 marks。

**Files:**
- Modify: `scripts/export_chipseq_bed.py`
- (Optional) Modify: `docs/HG19_OFFLINE_ASSETS.md`

**Step 1: 为导出脚本增加 `--group-by`（`cell_type|cell_line`）**
- 默认仍保持 `cell_type`（向后兼容）
- 新增：`--cell-line` 过滤（与现有 `--cell-type` 并存）
- 文件名规范：兼容 `MCF-7 -> MCF7`、`H1-hESC -> H1_hESC`

**Step 2: 运行脚本级快速校验（语法/导入）**
- Run: `python3 -m py_compile scripts/export_chipseq_bed.py`
- Expected: exit 0

**Step 3: Commit**
- `git add scripts/export_chipseq_bed.py docs/HG19_OFFLINE_ASSETS.md`
- `git commit -m "chore(tracks): support exporting ChIP-seq by cell_line"`

---

## Task 3：hg19 轨道再生成（可审计 + 可回滚）

**Files / Directories (external, not in git):**
- Write: `/data/wenyujianData/humanLncAtlas/audits/<ts>_chipseq_cellline_tracks_regen/*`
- Overwrite (with backup): `/data/wenyujianData/humanLncAtlas/chipseq_bed/chipseq_*.bed`
- Overwrite (with backup): `/data/wenyujianData/humanLncAtlas/genomes/chipseq_*.bb`

**Step 1: 审计 DB：确认 active experiments 均为 hg19，且补齐缺失 cell_line**
- Run (read-only summary):  
  `psql -d lncrna_production -U amax -c "SELECT COALESCE(reference_genome,'<NULL>') ref, COUNT(*) FROM chipseq_experiments WHERE is_active=TRUE AND species_id=1 GROUP BY 1 ORDER BY 2 DESC;"`
- Expected: `hg19 | 62`

- Run (定位缺失 cell_line):  
  `psql -d lncrna_production -U amax -c "SELECT experiment_id, experiment_name, cell_type FROM chipseq_experiments WHERE is_active=TRUE AND species_id=1 AND (cell_line IS NULL OR btrim(cell_line)='') ORDER BY experiment_id;"`
- Expected: 仅少量（当前为 K562 的若干实验）

**Step 2: 生成“可回滚 SQL”并应用（只改缺失 cell_line 的行）**
- 输出：`update_cell_line.sql` / `rollback_cell_line.sql`（写入 audit 目录）
- Apply：`psql -d lncrna_production -U amax -f update_cell_line.sql`

**Step 3: 备份现有 cell-line 轨道资产**
- Copy：`chipseq_{A549,GM12878,H1_hESC,HMEC,HepG2,K562,MCF7}.{bed,bb}`（存在则备份）

**Step 4: 重新导出 bed（按 cell_line）并转换 bigBed**
- Run（示例）：  
  `BIGBED_TOOL=/data/wenyujianData/humanLncAtlas/scripts/bedToBigBed_v385 CHROM_SIZES=/data/wenyujianData/humanLncAtlas/genomes/hg19.chrom.sizes BIGBED_OUTPUT_DIR=/data/wenyujianData/humanLncAtlas/genomes python3 scripts/export_chipseq_bed.py --output-dir /data/wenyujianData/humanLncAtlas/chipseq_bed --convert-bigbed --group-by cell_line`
- Expected：生成/更新 `chipseq_<CellLine>.bed` 与 `chipseq_<CellLine>.bb`

**Step 5: 组装一致性审计（防止 hg38 混入）**
- Run: `HUMAN_LNC_ATLAS_DATA_DIR=/data/wenyujianData/humanLncAtlas bash scripts/genomes/audit_external_data_assemblies.sh`
- Expected: `OK`

**Step 6: （可选）更新 `docs/CURRENT_STATUS.md` 与审计报告**
- 新增报告：`docs/reports/CHIPSEQ_HG19_CELL_LINE_TRACKS_REGEN_2026-02-09.md`
- 更新 `docs/CURRENT_STATUS.md` 的“最近完成”与日期

---

## Task 4：文档清理（历史快照显式“过期提示”）

**Files:**
- Modify: `docs/PROJECT_STATUS_REPORT.md`
- Modify: `docs/ROADMAP_*.md`（仅补充统一的“快照提示”，不改正文）

**Step 1: 为历史文档统一加“以 CURRENT_STATUS 为准”提示**

**Step 2: docs-check**
- Run: `./scripts/run-tests.sh docs-check`
- Expected: exit 0

**Step 3: Commit**
- `git add docs/*`
- `git commit -m "docs: add snapshot disclaimers to historical reports"`

---

## Task 5：性能门禁（可定位性增强，尽量不再大幅收紧阈值）

**Files:**
- Modify: `scripts/perf_overlap_regression.py` / `scripts/perf_genes_regulations_regression.py`（如需要）
- Modify: `docs/PERFORMANCE_TRIAGE.md`（如需要）

**Step 1: 复核门禁失败报告的 triage hints 覆盖（样本不足/429/reset 失败）**

**Step 2: 本地快速核验（不跑全量 build）**
- Run: `./scripts/run-tests.sh ci`（或最小子集：backend unit + scripts/tests）

**Step 3: Commit**
- `git add scripts docs`
- `git commit -m \"perf(ci): improve regression triage hints\"`

