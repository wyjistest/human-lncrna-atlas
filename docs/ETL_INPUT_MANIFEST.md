# ETL 输入文件指纹（manifest）

目标：在运行 ETL 导入前，对外部输入文件做“可选校验（checksum / size / line-count）”，避免下载损坏/截断导致的静默脏数据。

该工具不会下载数据，也不会写入数据库；只负责生成与校验一个小型 TSV manifest。

## 生成 manifest

```bash
python3 -m etl.input_manifest build \
  --output etl-inputs.manifest.tsv \
  --lines \
  --sha256 \
  /path/to/input1.tsv \
  /path/to/input2.tsv
```

说明：
- `bytes` 总是记录
- `--lines` 会统计行数（对超大文件可能较慢）
- `--sha256` 会计算 SHA256（对超大文件可能较慢）

## 校验 manifest（fail-fast）

```bash
python3 -m etl.input_manifest verify etl-inputs.manifest.tsv
```

校验规则：
- `bytes` / `lines` / `sha256` 字段为空时会跳过对应检查
- manifest 中的相对路径会按 manifest 所在目录解析

## 推荐用法（团队协作）

- 不要把大文件提交到仓库；可以提交 manifest（小文件、可审查）
- 每次外部下载/更新输入数据后，重新生成 manifest 并留档
- 在 ETL 运行前先 `verify`，确认输入未被意外替换/损坏

## 仓库内样例（可选）

仓库内提供了一个可提交的极小样例，用于演示 manifest 校验流程：

```bash
python3 -m etl.input_manifest verify etl/sample_inputs/etl-inputs.manifest.tsv
```

## 与导入脚本集成（可选）

多数 `etl/import_*.py` 导入脚本支持 `--input-manifest` 参数，会在连接数据库/开始导入前先校验 manifest，并确保“本次导入用到的输入文件”确实在 manifest 中列出（避免误以为已校验）。

示例：

```bash
# 先生成/校验（可选：也可以直接让脚本校验）
python3 -m etl.input_manifest verify etl-inputs.manifest.tsv

# 导入时自动 fail-fast
python3 etl/import_regulations.py --file /path/to/human_batch_human.txt \
  --input-manifest etl-inputs.manifest.tsv \
  --user "$DB_USER"
```
