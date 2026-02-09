# hg19：按 cell line 重新生成 ChIP-seq bed/bigBed 轨道（补齐缺失 marks）

> 日期：2026-02-09  
> 目标：让 `genomes/chipseq_<CellLine>.bb` 真正包含该 cell line 的全部 marks（避免被 `cell_type` 拆分）。

## 背景

后端 IGV 配置（`frontend/backend/app/config/igv_genomes.py`）默认引用：

- `/genomes/chipseq_K562.bb`
- `/genomes/chipseq_GM12878.bb`
- `/genomes/chipseq_H1_hESC.bb`
- `/genomes/chipseq_HepG2.bb`
- `/genomes/chipseq_A549.bb`
- `/genomes/chipseq_HMEC.bb`
- `/genomes/chipseq_MCF7.bb`

历史导出脚本按 `chipseq_experiments.cell_type` 分组导出，若同一 cell line 的 `cell_type` 命名不一致（例如 GM12878 同时出现 `GM12878` 与 `B-lymphocyte`），会导致：

- `chipseq_GM12878.bed/.bb` 只包含 `cell_type=GM12878` 的子集
- 其余 peaks 落在 `chipseq_B_lymphocyte.bed`，从而前端“看起来缺失一部分 marks/peaks”

本次通过 `--group-by cell_line` 重新导出，完成“补齐”。

## 审计/回滚目录（落盘）

主审计目录（含 DB SQL、轨道备份、导出日志）：

- `/data/wenyujianData/humanLncAtlas/audits/2026-02-09_12-10-01_chipseq_cellline_tracks_regen/`

外部数据组装审计（复核无 hg38 混入）：

- `/data/wenyujianData/humanLncAtlas/audits/2026-02-09_12-11-23_external_assembly_audit/`

## 执行步骤摘要

1. **DB 元数据修复（可回滚）**
   - 回填缺失 `cell_line`：`experiment_id IN (5..10)`（K562 历史实验）
     - update：`update_cell_line.sql`
     - rollback：`rollback_cell_line.sql`
   - 对齐 `species.genome_assembly`（与项目离线资源/IGV 配置一致）
     - update：`update_species_genome_assembly.sql`
     - rollback：`rollback_species_genome_assembly.sql`

2. **备份现有轨道资产**
   - 备份目录：`backup/chipseq_bed/` 与 `backup/genomes/`

3. **按 cell line 导出 bed + 转 bigBed**
   - 使用脚本：`python3 scripts/export_chipseq_bed.py --group-by cell_line --convert-bigbed`
   - `bedToBigBed`：`/data/wenyujianData/humanLncAtlas/scripts/bedToBigBed_v385`
   - 输出目录：
     - BED：`/data/wenyujianData/humanLncAtlas/chipseq_bed/`
     - BigBed：`/data/wenyujianData/humanLncAtlas/genomes/`

4. **组装一致性审计**
   - `bash scripts/genomes/audit_external_data_assemblies.sh`（输出为 `OK`）

## 产物与峰数量（BED 行数）

| Cell line | BED | Peaks |
|---|---|---:|
| A549 | `chipseq_A549.bed` | 782,674 |
| GM12878 | `chipseq_GM12878.bed` | 734,789 |
| H1-hESC | `chipseq_H1_hESC.bed` | 874,023 |
| HepG2 | `chipseq_HepG2.bed` | 781,991 |
| HMEC | `chipseq_HMEC.bed` | 518,447 |
| K562 | `chipseq_K562.bed` | 843,309 |
| MCF-7 | `chipseq_MCF7.bed` | 238,634 |

合计：4,773,867 peaks（与 `docs/CURRENT_STATUS.md` 的 Human epigenomic 总 peaks 一致）。

## 回滚方式

按需二选一或组合：

1. **回滚 DB**
   - `psql -d lncrna_production -U amax -f rollback_cell_line.sql`
   - `psql -d lncrna_production -U amax -f rollback_species_genome_assembly.sql`

2. **回滚轨道文件**
   - 从 `backup/chipseq_bed/` 与 `backup/genomes/` 恢复覆盖到对应目录即可。

