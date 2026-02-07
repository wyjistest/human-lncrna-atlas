# ChIP-seq：补齐 UCSC hg19 broadHistone peaks（HepG2 H3K9me3）

日期：2026-02-07

## 背景

在外部数据组装一致性审计（hg19）过程中，发现 **HepG2 缺失 H3K9me3** 的 peaks/轨道，导致该细胞系的抑制性标记覆盖不完整。为保持 hg19（GRCh37）坐标一致性，本次从 UCSC 重新下载并导入 **hg19** 版本的 broadPeak，并生成对应的 `gene_peak_associations` 与离线 BigBed 轨道。

## 数据来源（UCSC / hg19）

目录：`hg19/encodeDCC/wgEncodeBroadHistone/`

- `wgEncodeBroadHistoneHepg2H3k09me3Pk.broadPeak.gz`

备注：UCSC 文件名里为 `H3k09me3`（不是 `H3k9me3`）。

## DB 变更（lncrna_production）

新增实验（reference_genome=hg19）：

- `UCSC_hg19_HepG2_H3K9me3` (experiment_id=75, peaks=53,227)

新增关联：

- `gene_peak_associations`：experiment_id=75 新增 12,146 行

## 离线轨道产物（hg19）

已重建并覆盖：

- `/data/wenyujianData/humanLncAtlas/chipseq_bed/chipseq_HepG2.bed`（records=602,646）
- `/data/wenyujianData/humanLncAtlas/genomes/chipseq_HepG2.bb`

## 审计/回滚（本机路径）

本次导入审计目录：

- `/data/wenyujianData/humanLncAtlas/audits/2026-02-07_18-15-31_ucsc_hg19_hepg2_h3k09me3_import/`

离线轨道备份（覆盖前）：

- `/data/wenyujianData/humanLncAtlas/backup_chipseq_assets_2026-02-07_18-18-58_before_hepg2_h3k9me3/`

审计目录包含（用于追溯与回滚）：

- `configs/*.json`：导入/导出配置
- `logs/*.log`：导入与导出日志
- `sha256_*.txt`：文件校验
- `rollback_*.sql`：回滚 SQL

## 备注：bedToBigBed 运行环境

当前宿主机 glibc 版本较低时，UCSC `bedToBigBed` 预编译二进制可能无法直接运行；可在具备更高 glibc 的容器镜像中执行 `bedToBigBed`，并用 `--user` 写回宿主机输出目录，保持可回滚、可审计。

