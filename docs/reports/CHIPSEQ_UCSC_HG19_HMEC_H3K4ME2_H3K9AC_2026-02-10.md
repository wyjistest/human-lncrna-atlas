# CHIPSEQ UCSC hg19: HMEC H3K4me2/H3K9ac 补齐（2026-02-10）

## 目标

- 补齐 Human(hg19) 的 HMEC 细胞系缺失 marks：`H3K4me2`、`H3K9ac`。
- 确保外部 peaks/轨道无 hg38 混入（可审计、可回滚）。

## 数据来源（UCSC hg19 ENCODE Broad Histone）

- H3K4me2: `wgEncodeBroadHistoneHmecH3k4me2StdPk.broadPeak.gz`
  - URL: `https://hgdownload.soe.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeBroadHistone/wgEncodeBroadHistoneHmecH3k4me2StdPk.broadPeak.gz`
- H3K9ac: `wgEncodeBroadHistoneHmecH3k9acStdPk.broadPeak.gz`
  - URL: `https://hgdownload.soe.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeBroadHistone/wgEncodeBroadHistoneHmecH3k9acStdPk.broadPeak.gz`

下载/导入审计目录（含配置、日志、回滚 SQL）：

- `/data/wenyujianData/humanLncAtlas/audits/2026-02-10_12-24-51_hmec_hg19_marks_backfill/`

## 组装/边界校验（hg19）

执行：

- `python3 scripts/genomes/validate_peak_bed_bounds.py --chrom-sizes /data/wenyujianData/humanLncAtlas/genomes/hg19.chrom.sizes /data/wenyujianData/humanLncAtlas/audits/2026-02-10_12-24-51_hmec_hg19_marks_backfill`

结果（records）：

- H3K4me2: `98,744`
- H3K9ac: `52,305`

## DB 导入（lncrna_production）

导入配置（JSON）：

- `/data/wenyujianData/humanLncAtlas/audits/2026-02-10_12-24-51_hmec_hg19_marks_backfill/hmec_h3k4me2_ucsc_hg19_import.json`
- `/data/wenyujianData/humanLncAtlas/audits/2026-02-10_12-24-51_hmec_hg19_marks_backfill/hmec_h3k9ac_ucsc_hg19_import.json`

导入命令（计算 `gene_peak_associations`）：

- `python3 frontend/backend/scripts/import_chipseq.py --config <json> --db-name lncrna_production --db-user amax --compute-associations`

导入日志：

- `/data/wenyujianData/humanLncAtlas/audits/2026-02-10_12-24-51_hmec_hg19_marks_backfill/import_h3k4me2.log`
- `/data/wenyujianData/humanLncAtlas/audits/2026-02-10_12-24-51_hmec_hg19_marks_backfill/import_h3k9ac.log`

导入结果（关键字段）：

- `H3K4me2_HMEC_BROAD_HMEC_H3K4me2`
  - `experiment_id=76`
  - `import_batch_id=89`
  - `peaks_imported=98744`
  - `associations_inserted=29718`
  - `reference_genome=hg19`
- `H3K9ac_HMEC_BROAD_HMEC_H3K9ac`
  - `experiment_id=77`
  - `import_batch_id=90`
  - `peaks_imported=52305`
  - `associations_inserted=16992`
  - `reference_genome=hg19`

## HMEC 轨道重生成（cell_line）

轨道文件：

- BED：`/data/wenyujianData/humanLncAtlas/chipseq_bed/chipseq_HMEC.bed`
- BigBed：`/data/wenyujianData/humanLncAtlas/genomes/chipseq_HMEC.bb`

覆盖前备份（可回滚，见审计目录）：

- `chipseq_HMEC.bed.bak_2026-02-10_13-24-34`
- `chipseq_HMEC.bb.bak_2026-02-10_13-24-34`

导出命令：

- `BIGBED_TOOL=/data/wenyujianData/humanLncAtlas/scripts/bedToBigBed_v385 CHROM_SIZES=/data/wenyujianData/humanLncAtlas/genomes/hg19.chrom.sizes BIGBED_OUTPUT_DIR=/data/wenyujianData/humanLncAtlas/genomes python3 scripts/export_chipseq_bed.py --group-by cell_line --cell-line HMEC --output-dir /data/wenyujianData/humanLncAtlas/chipseq_bed --convert-bigbed`

导出日志：

- `/data/wenyujianData/humanLncAtlas/audits/2026-02-10_12-24-51_hmec_hg19_marks_backfill/export_chipseq_tracks_HMEC.log`

导出结果：

- `chipseq_HMEC.bed` 记录数：`669,496`

## 全量外部数据 assembly 审计（hg19）

- 执行：`HUMAN_LNC_ATLAS_DATA_DIR=/data/wenyujianData/humanLncAtlas ASSEMBLY=hg19 bash scripts/genomes/audit_external_data_assemblies.sh`
- 输出目录：`/data/wenyujianData/humanLncAtlas/audits/2026-02-10_13-25-36_external_assembly_audit`

## 回滚（危险操作止损）

回滚 SQL（已落盘）：

- `/data/wenyujianData/humanLncAtlas/audits/2026-02-10_12-24-51_hmec_hg19_marks_backfill/rollback.sql`

说明：

- 回滚会删除 `experiment_id IN (76,77)` 对应的：
  - `gene_peak_associations`
  - `chipseq_peaks`
  - `chipseq_experiments`
  - `import_batches(batch_id IN (89,90))`

