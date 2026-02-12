# ChIP-seq hg19 外部数据版本审计 + `gene_peak_associations` 复核（2026-02-12）

## 目标

1. 核验当前外部轨道/peaks 资产是否 **全部为 hg19**（防止 hg38 混入）。
2. 核验 DB（`lncrna_production`）中 human active ChIP-seq experiments 的 `reference_genome` 与覆盖情况。
3. 核验 `gene_peak_associations` 是否已生成且覆盖全部 active experiments（用于后续性能/物化视图/查询优化）。

---

## 1) 外部数据组装一致性审计（hg19）

**命令（只读）**：

```bash
ASSEMBLY=hg19 HUMAN_LNC_ATLAS_DATA_DIR=/data/wenyujianData/humanLncAtlas \
  bash scripts/genomes/audit_external_data_assemblies.sh
```

**审计输出目录**：

- `/data/wenyujianData/humanLncAtlas/audits/2026-02-12_14-49-36_external_assembly_audit/`

**关键信号**：

- `meta.env` 中包含：
  - `git_head=b4214f5ba02e096d96f2c44ce3410fd9d5d34068`
  - `git_branch=main`
- `validate_track_assemblies.py`：BigWig/BigBed header 与 `hg19.chrom.sizes` 一致
- `validate_peak_bed_bounds.py`：`chipseq_bed/`、`encode_data/`、`chipseq_data/encode_peaks/`、`genomes/` 下文本 peaks 均无越界/未知染色体

---

## 2) DB `reference_genome` 缺口审计（hg19）

**命令（只读；默认仅生成可回滚 SQL，不写 DB）**：

```bash
DB_USER=amax DB_NAME=lncrna_production HUMAN_LNC_ATLAS_DATA_DIR=/data/wenyujianData/humanLncAtlas \
  bash scripts/genomes/audit_chipseq_reference_genome_db.sh --assembly hg19
```

**审计输出目录**：

- `/data/wenyujianData/humanLncAtlas/audits/2026-02-12_14-49-21_chipseq_reference_genome_db_audit/`

**结论**：

- `pass_experiments=0` / `fail_experiments=0`  
  说明：当前 **human active experiments 已全部写入 `reference_genome=hg19`**（无 NULL 待回填）。

---

## 3) DB 覆盖核验（human / active）

**只读统计（`lncrna_production`）**：

- Genes：`17,248`
- Human active epigenomic experiments：`64`
- `reference_genome`：active experiments **全部为 `hg19`**
- cell_line：`A549, GM12878, H1-hESC, HepG2, HMEC, K562, MCF-7`

> 备注：`MCF-7` 当前仅覆盖 `H3K4me3` + `DNase-HS`（详见 `docs/CURRENT_STATUS.md` 的“细胞系覆盖”表）。

---

## 4) `gene_peak_associations` 覆盖核验

**只读统计（`lncrna_production`）**：

- `gene_peak_associations` 总行数：`1,560,825`
- 覆盖 experiments 数：`64 / 64`

**脚本复核（dry-run）**：

```bash
cd frontend/backend
EXPECTED_REFERENCE_GENOME=hg19 DB_USER=amax DB_NAME=lncrna_production \
  python3 scripts/compute_gene_peak_associations.py --dry-run
```

预期：全部输出 `skipped_existing`（表示 associations 已存在，无需重复计算）。

---

## 结论与下一步

- ✅ 外部数据与轨道资产通过 hg19 组装一致性审计；未发现 hg38 混入。
- ✅ DB（human active experiments）`reference_genome` 全为 hg19。
- ✅ `gene_peak_associations` 已覆盖全部 active experiments，可直接用于后续性能/统计/查询优化。
- 🔜 若需要把 `MCF-7` 补齐到 “8 marks” 覆盖：需要补充该细胞系在 hg19 下的其它 histone peaks 数据源（当前 UCSC 映射为 UW Histone track，数据较少）。

