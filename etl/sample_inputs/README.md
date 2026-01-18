# ETL 样例输入（可提交的小基线）

本目录提供**极小的、可提交到仓库**的 ETL 输入样例，用于：

- 演示 `etl.input_manifest` / `--input-manifest` 的使用方式
- 提供一个可审查的 baseline（bytes/lines/sha256），便于后续重构时快速回归

注意：
- 这里的数据是**合成样例**，不包含真实数据
- 文件名刻意与默认 ETL 输入保持一致（例如 `human_batch_human.*`；此处使用 `.tsv` 以避免仓库忽略规则）
