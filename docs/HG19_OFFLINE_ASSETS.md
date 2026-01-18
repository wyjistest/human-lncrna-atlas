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
