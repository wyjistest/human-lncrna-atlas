# hg19 IGV 离线资源（可选）

目的：为 IGV.js 提供本地参考资源，避免运行时访问 UCSC / GitHub 等外网依赖。后端会将 `GENOMES_DIR` 目录以 `/genomes` 静态文件形式暴露给前端。

## 一键下载

```bash
# 仅下载核心文件（2bit / cytoband / chrom.sizes / alias）
GENOMES_DIR="/path/to/genomes" ./scripts/genomes/download_hg19_igv_assets.sh

# 可选：下载保守性 BigWig（文件很大）
./scripts/genomes/download_hg19_igv_assets.sh --with-conservation "/path/to/genomes"

# 其他物种/组装（示例）
./scripts/genomes/download_hg19_igv_assets.sh --assembly panTro5 "/path/to/genomes"
./scripts/genomes/download_hg19_igv_assets.sh --assembly rheMac10 "/path/to/genomes"
./scripts/genomes/download_hg19_igv_assets.sh --assembly calJac3 "/path/to/genomes"
```

## 可选校验（防止静默损坏）

脚本默认会做轻量 sanity checks（最小文件尺寸、`.gz` 可解压、行数范围等）。如需要“强校验”（checksum），可通过环境变量提供期望 SHA256：

```bash
# 变量名前缀规则：<ASSEMBLY> 大写 + 去掉非字母数字字符
# 例如：hg19 -> HG19, panTro5 -> PANTRO5

export HG19_2BIT_SHA256="<64-hex>"
export HG19_CYTOBAND_SHA256="<64-hex>"
export HG19_CHROMSIZES_SHA256="<64-hex>"
export HG19_ALIAS_SHA256="<64-hex>"
export HG19_PHASTCONS_SHA256="<64-hex>"
export HG19_PHYLOP_SHA256="<64-hex>"
```

当对应文件存在且期望值已设置时，脚本会在校验失败时直接退出（fail-fast）。

## 下载清单（基线）

为了便于后续回归（文件大小/哈希对比），可生成下载清单：

```bash
./scripts/genomes/download_hg19_igv_assets.sh --write-manifest "/path/to/genomes"

# 如需对大文件也计算 SHA256（可能较慢）
./scripts/genomes/download_hg19_igv_assets.sh --write-manifest --hash-large-files "/path/to/genomes"
```

清单默认写入：`$GENOMES_DIR/hg19_igv_assets.manifest.tsv`，包含：

- `file`：文件名
- `bytes`：文件大小（字节）
- `sha256`：SHA256（小文件默认计算；大文件需要 `--hash-large-files`）

## 组装一致性校验（可选）

当你在 `GENOMES_DIR` 中混入了来自不同来源的 `.bw/.bb` 轨道文件时，最容易踩的坑就是 **hg19/hg38 等组装不一致**（文件能加载，但坐标会整体错位）。

仓库提供了一个“只读、可审计”的快速校验脚本：读取 BigWig/BigBed header 里的染色体表，并与 `<assembly>.chrom.sizes` 比对。

```bash
python3 scripts/genomes/validate_track_assemblies.py --genomes-dir "/path/to/genomes"

# 对于 chipseq_*.bb / repeatmasker_*.bb 等不带组装前缀的文件，可显式指定默认组装
python3 scripts/genomes/validate_track_assemblies.py --genomes-dir "/path/to/genomes" --default-assembly hg19
```

说明：
- 该脚本依赖 `pyBigWig`；若环境缺失，按提示安装：`python3 -m pip install pyBigWig`

## Peak 坐标边界校验（BED/broadPeak/narrowPeak）

BigBed/BigWig 会在生成时强依赖 `chrom.sizes`，但纯文本的 peaks（例如 `.bed/.broadPeak/.narrowPeak`）很容易在导入/拼接时混入不同组装的数据而“静默通过”。常见症状是：

- IGV 能加载，但部分 peak 在染色体末端附近整体错位
- 或出现 `end > chrom_len` 这类明显越界坐标（例如 hg19 项目里混入 GRCh38 peaks）

仓库提供了一个“只读、可审计”的快速校验脚本：逐行解析坐标，并与 `chrom.sizes` 做边界比对。

```bash
python3 scripts/genomes/validate_peak_bed_bounds.py \
  --chrom-sizes "/path/to/genomes/hg19.chrom.sizes" \
  "/path/to/chipseq_bed"

# 也可用于校验从 UCSC 下载的 .broadPeak.gz / .narrowPeak.gz
python3 scripts/genomes/validate_peak_bed_bounds.py \
  --chrom-sizes "/path/to/genomes/hg19.chrom.sizes" \
  "/tmp/ucsc_hg19_recheck_peaks"
```

当检测到 `FAIL ... reason=end_gt_chrom_len(...)` 时，优先怀疑：
- 该 peaks 文件对应的参考组装与项目不一致（hg19/hg38 混用）
- 或数据库中混入了明确标注为其他 reference genome 的实验（例如 `reference_genome=GRCh38`）

补充：后端在导出 IGV ChIP-seq peaks（`/api/v1/igv/tracks/chipseq/{species_id}.bed`）以及 `scripts/export_chipseq_bed.py` 中，会根据 `get_genome_reference(species_id).id` 对 `chipseq_experiments.reference_genome` 做兼容性过滤（NULL 视为“未知但兼容”，仅排除明确不匹配的值），以避免 hg19/hg38 混用造成的坐标错位。

## DB reference_genome 回填（可选，推荐）

当你历史导入过一些 ChIP-seq 实验但 `chipseq_experiments.reference_genome` 仍为空（NULL）时，虽然系统会把 NULL 当作“未知但兼容”，但长期会让审计与排障变得不确定。

仓库提供了一个“可审计、可回滚”的回填脚本：它会对 **DB 中 active 且 reference_genome IS NULL** 的实验做坐标边界校验（`peak_end <= hg19.chrom.sizes`），并生成回填/回滚 SQL（默认不写 DB；`--apply` 才会执行）。

```bash
# 只读审计（推荐先跑）
HUMAN_LNC_ATLAS_DATA_DIR="/data/wenyujianData/humanLncAtlas" \
  bash scripts/genomes/audit_chipseq_reference_genome_db.sh --assembly hg19

# 审计 OK 且确认无误后，可执行回填（会写 DB；会同时生成 rollback SQL）
HUMAN_LNC_ATLAS_DATA_DIR="/data/wenyujianData/humanLncAtlas" \
  bash scripts/genomes/audit_chipseq_reference_genome_db.sh --assembly hg19 --apply
```

输出目录：`$HUMAN_LNC_ATLAS_DATA_DIR/audits/<timestamp>_chipseq_reference_genome_db_audit/`，包含：
- `chipseq_reference_genome_audit.tsv`：每个实验的峰数量/越界统计
- `update_reference_genome_hg19.sql` / `rollback_reference_genome_hg19.sql`：可回滚 SQL

## 一键外部数据组装审计（推荐）

如果你有一套“线上生效”的外部数据目录（例如 `/data/wenyujianData/humanLncAtlas`），推荐直接跑一键审计脚本，它会串联本文档提到的两个校验器，并把审计日志落盘，方便回溯与对比：

```bash
HUMAN_LNC_ATLAS_DATA_DIR="/data/wenyujianData/humanLncAtlas" \
  bash scripts/genomes/audit_external_data_assemblies.sh
```

输出目录：`$HUMAN_LNC_ATLAS_DATA_DIR/audits/<timestamp>_external_assembly_audit/`，包含：
- `meta.env`：审计环境信息（host、repo SHA、路径等）
- `01_*.log ...`：每一步的详细日志
- `summary.txt`：总结与审计输出路径

可选环境变量（按需覆盖默认目录）：
- `ASSEMBLY`（默认 `hg19`）
- `GENOMES_DIR` / `CHROM_SIZES`
- `CHIPSEQ_BED_DIR` / `ENCODE_DATA_DIR` / `ENCODE_PEAKS_DIR`
