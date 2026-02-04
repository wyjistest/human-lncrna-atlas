# 文档导航（开发 / 维护者）

本页作为 **docs 目录入口**，聚焦“现在该看什么、怎么跑、怎么测、怎么排障”。

## Start Here（推荐顺序）

1. 当前状态：`docs/CURRENT_STATUS.md`
2. 1–2 周路线图：`docs/ROADMAP_2026-02-03.md`
3. CI / Self-hosted Runner（含代理/网络止损）：`docs/CI_SELF_HOSTED_RUNNER.md`
4. 性能定位入口：`docs/PERFORMANCE_TRIAGE.md`
5. 仓库总览与快速开始：`README.md`

## 日常开发

### 测试与检查

- 统一入口脚本：`scripts/run-tests.sh`
- 文档检查：`bash scripts/run-tests.sh docs-check`

### 后端

- 状态与交付：`docs/backend/BACKEND_STATUS.md`
- 部署：`docs/backend/DEPLOYMENT.md`
- Overlap 物化视图：`docs/backend/OVERLAP_MATERIALIZED_VIEW.md`

### API 文档

- API 总指南：`docs/api/API_GUIDE.md`
- 端点速查：`docs/api/API_ENDPOINTS_QUICKREF.md`
- Overlap API：`docs/api/LNCRNA_CHIPSEQ_OVERLAP_API.md`

### 数据库 / Schema

- 数据库设计：`docs/DATABASE_DESIGN_FINAL.md`
- 迁移与变更：`docs/DB_MIGRATIONS.md`

## 性能门禁（Perf Regression）

- Overlap：`docs/testing/performance/OVERLAP_PERF_REGRESSION.md`
- Genes / Regulations：`docs/testing/performance/GENES_REGULATIONS_PERF_REGRESSION.md`

## 归档（历史材料）

`docs/archive/` 为历史归档材料，不保证与当前代码一致；请以 `docs/CURRENT_STATUS.md` 为准。
