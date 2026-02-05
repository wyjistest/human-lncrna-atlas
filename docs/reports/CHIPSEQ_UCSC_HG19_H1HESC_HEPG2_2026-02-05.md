# ChIP-seq：补齐 UCSC hg19 broadHistone peaks（H1-hESC / HepG2）

日期：2026-02-05

## 背景

在排查 IGV 轨道错位问题时，发现部分 ChIP-seq peaks 混入了 **GRCh38** 坐标（hg19 项目中出现 `end > chrom_len` 越界）。为保证 hg19（GRCh37）一致性，本次从 UCSC 重新下载并导入 **hg19** 版本的 broadPeak，并重建离线 BigBed 轨道。

## 数据来源（UCSC / hg19）

目录：`hg19/encodeDCC/wgEncodeBroadHistone/`

细胞系 × 标记（共 8 个 broadPeak.gz）：

- H1-hESC：H3K27ac / H3K27me3 / H3K4me1 / H3K4me3
- HepG2：H3K27ac / H3K27me3 / H3K4me1 / H3K4me3

注意：HepG2 的 H3K4me1 文件名为 `H3k04me1`（不是 `H3k4me1`）。

## DB 变更（lncrna_production）

新增实验（reference_genome=hg19）：

- `UCSC_hg19_H1hESC_H3K27ac` (experiment_id=67)
- `UCSC_hg19_H1hESC_H3K27me3` (experiment_id=68)
- `UCSC_hg19_H1hESC_H3K4me1` (experiment_id=69)
- `UCSC_hg19_H1hESC_H3K4me3` (experiment_id=70)
- `UCSC_hg19_HepG2_H3K27ac` (experiment_id=71)
- `UCSC_hg19_HepG2_H3K27me3` (experiment_id=72)
- `UCSC_hg19_HepG2_H3K4me1` (experiment_id=73)
- `UCSC_hg19_HepG2_H3K4me3` (experiment_id=74)

历史问题实验（GRCh38，已停用）：

- `ENCODE_H1hESC_*` / `ENCODE_HepG2_*`（experiment_id=15..22，is_active=false）

## 离线轨道产物（hg19）

已重建并覆盖：

- `chipseq_bed/chipseq_H1_hESC.bed`（records=635,065）
- `chipseq_bed/chipseq_HepG2.bed`（records=549,419）
- `genomes/chipseq_H1_hESC.bb`
- `genomes/chipseq_HepG2.bb`

## 审计/回滚（本机路径）

本次导入的审计目录：

- `/data/wenyujianData/humanLncAtlas/audits/2026-02-05_10-48-28_ucsc_hg19_broadHistone_import/`

包含：

- `configs/*.json`：8 个 `import_chipseq.py --config` 配置
- `logs/*.log`：每次导入与导出日志
- `db_ucsc_hg19_chipseq_experiments.tsv`：DB 实验清单（含 peak_count）
- `rollback_deactivate_ucsc_hg19_experiments.sql` / `rollback_reactivate_ucsc_hg19_experiments.sql`
- `sha256_ucsc_hg19_broadHistone_files.txt`

离线轨道备份（覆盖前）：

- `/data/wenyujianData/humanLncAtlas/backup_chipseq_assets_2026-02-05_10-54-46_before_rebuild_hg19_histone/`

## 备注：并发刷新物化视图

`refresh_chipseq_stats()` 使用 `REFRESH MATERIALIZED VIEW CONCURRENTLY`，需要 `mv_gene_mark_summary` 上存在无 WHERE 子句的唯一索引。

已补齐索引：`idx_mv_gene_mark_summary_unique (gene_id, species_id, mark_name)`。
