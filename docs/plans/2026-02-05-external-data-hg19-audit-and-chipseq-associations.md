# External Data hg19 Audit + gene_peak_associations Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把“外部轨道/peaks 的 hg19 组装一致性校验”固化成一键可审计流程，并补齐 ENCODE hg19 peaks 下载映射（8 个 marks），实现可选的 `gene_peak_associations` 预计算入口（用于后续性能优化与物化视图刷新）。

**Architecture:** 以 `scripts/genomes/validate_track_assemblies.py`（BigWig/BigBed header 比对）+ `scripts/genomes/validate_peak_bed_bounds.py`（文本 peaks 越界/未知染色体检查）为核心；新增一个 `audit_external_data_assemblies.sh` 负责串联与落盘审计日志；导入侧在 `frontend/backend/scripts/import_chipseq.py` 增加 `--compute-associations`，用 SQL `INSERT ... SELECT ... ON CONFLICT DO NOTHING` 生成 `gene_peak_associations`；下载侧扩展 `download_encode_chipseq.py` 的 UCSC hg19 文件映射以覆盖 8 个 marks。

**Tech Stack:** Bash / Python / PostgreSQL (psycopg2) / GitHub Actions (self-hosted)

---

### Task 1: 新增一键外部数据组装审计脚本（只读、可回滚）

**Files:**
- Create: `scripts/genomes/audit_external_data_assemblies.sh`

**Step 1: 实现脚本骨架（fail-fast + 可审计落盘）**
- 默认审计目录：`$HUMAN_LNC_ATLAS_DATA_DIR/audits/<timestamp>_external_assembly_audit/`
- 默认数据根：`/data/wenyujianData/humanLncAtlas`（支持 env 覆盖）
- 依次执行：
  - `validate_track_assemblies.py`（`genomes/` 下 `.bw/.bb`）
  - `validate_peak_bed_bounds.py`（`chipseq_bed/`、`encode_data/`、`chipseq_data/encode_peaks/`、`genomes/` 下文本 peaks）

**Step 2: 本机验证（不修改数据）**
- Run: `bash scripts/genomes/audit_external_data_assemblies.sh`
- Expected: exit code 0；审计目录生成且包含每步日志与 summary。

**Step 3: Commit**
- `git add scripts/genomes/audit_external_data_assemblies.sh`
- `git commit -m "chore(genomes): add external data hg19 assembly audit script"`

---

### Task 2: 为审计脚本增加 GitHub Action（self-hosted 手动触发）

**Files:**
- Create: `.github/workflows/external-data-assembly-audit.yml`

**Step 1: Workflow 仅 workflow_dispatch**
- `runs-on: self-hosted`
- `env: HUMAN_LNC_ATLAS_DATA_DIR=/data/wenyujianData/humanLncAtlas`
- Run: `bash scripts/genomes/audit_external_data_assemblies.sh`

**Step 2: 验证**
- Run: `python3 -m compileall .github/workflows >/dev/null 2>&1 || true`（只做最小 sanity；workflow 语法由 CI linter 覆盖）

**Step 3: Commit**
- `git add .github/workflows/external-data-assembly-audit.yml`
- `git commit -m "ci: add external data assembly audit workflow"`

---

### Task 3: 补齐 ENCODE hg19 peaks 下载映射（8 个 marks）

**Files:**
- Modify: `frontend/backend/scripts/download_encode_chipseq.py`
- Modify: `docs/ENCODE_DATA_GUIDE.md`

**Step 1: 扩展 ENCODE_FILES 覆盖 8 marks**
- 目标 marks：`H3K27me3,H3K4me3,H3K4me1,H3K27ac,H3K36me3,H3K9me3,H3K9ac,H3K4me2`
- 优先覆盖核心 cell lines：`GM12878,H1-hESC,K562,HepG2`
- 处理已知 UCSC 命名坑：如 `HepG2 H3K4me1` 的 `H3k04me1`、`H3K9me3` 的 `H3k09me3`。

**Step 2: 最小验证（不下载）**
- Run: `cd frontend/backend && python3 scripts/download_encode_chipseq.py --all --cell-line GM12878 --dry-run`
- Expected: 输出包含 8 个 marks 的下载条目（或明确提示缺失/不可用）。

**Step 3: Commit**
- `git add frontend/backend/scripts/download_encode_chipseq.py docs/ENCODE_DATA_GUIDE.md`
- `git commit -m "feat(encode): complete hg19 UCSC peaks mapping for 8 marks"`

---

### Task 4: 实现 `--compute-associations`：生成 `gene_peak_associations`

**Files:**
- Modify: `frontend/backend/scripts/import_chipseq.py`
- Modify: `frontend/backend/scripts/batch_import_chipseq.py`

**Step 1: CLI 增加 `--compute-associations`**
- `import_chipseq.py`：解析参数并传入 import 流程
- `batch_import_chipseq.py`：读取 config `options.compute_associations`，为子进程追加 `--compute-associations`

**Step 2: 在导入完成后计算关联**
- SQL 策略：对当前 `experiment_id` 的 peaks join `genes`（同 species/chr，按 flanking 区间相交），生成 overlap_type / distance_to_tss / overlap_bp / overlap_percentage，并写入 `gene_peak_associations`（冲突忽略）。
- 仅在显式启用 `--compute-associations` 时执行（默认保持行为不变）。

**Step 3: 验证（无 DB 时只做语法/导入流程不跑）**
- Run: `python3 -m compileall frontend/backend/scripts/import_chipseq.py frontend/backend/scripts/batch_import_chipseq.py`
- Expected: exit code 0。

**Step 4: Commit**
- `git add frontend/backend/scripts/import_chipseq.py frontend/backend/scripts/batch_import_chipseq.py`
- `git commit -m "feat(chipseq): add optional gene-peak association precompute"`

---

### Task 5: 更新文档（把“人工流程”改成“一键可执行”）

**Files:**
- Modify: `docs/HG19_OFFLINE_ASSETS.md`
- Modify: `docs/ENCODE_DATA_GUIDE.md`

**Step 1: 增加“一键审计”章节**
- 给出命令、默认路径、审计落盘位置、失败含义（hg38 混入/下载损坏/未知染色体等）。

**Step 2: Commit**
- `git add docs/HG19_OFFLINE_ASSETS.md docs/ENCODE_DATA_GUIDE.md`
- `git commit -m "docs: add external data hg19 audit + association steps"`

---

### Task 6: 统一验证 + 推送

**Step 1: 仅对改动文件做轻量验证**
- Run: `bash -n scripts/genomes/audit_external_data_assemblies.sh`
- Run: `python3 -m compileall scripts/genomes/validate_track_assemblies.py scripts/genomes/validate_peak_bed_bounds.py frontend/backend/scripts/*.py`

**Step 2: Push**
- Run: `git push`（如遇网络问题可用 `http_proxy=http://localhost:7890 git push`）

