# 文档导航（开发 / 维护者）

本页作为 **docs 目录入口**，聚焦“现在该看什么、怎么跑、怎么测、怎么排障”。

## Start Here（推荐顺序）

1. 当前状态：`docs/CURRENT_STATUS.md`
2. 当前路线图（稳定入口）：`docs/roadmaps/ROADMAP_CURRENT.md`
3. backlog 自动化与治理规则：`docs/governance/BACKLOG_AUTOMATION.md`
4. CI / Self-hosted Runner（含代理/网络止损）：`docs/CI_SELF_HOSTED_RUNNER.md`
5. 性能定位入口：`docs/PERFORMANCE_TRIAGE.md`
6. 仓库总览与快速开始：`README.md`

## 日常开发

### 工作区约定

- 根工作区默认用于跟进 `origin/main`、查阅代码与执行低风险只读命令；开始新开发前先确认 `git status` 干净。
- 依赖升级、PR 验证、较高风险的修复请放到 `.worktrees/<topic>`，避免把评估残留带回根工作区。
- 推荐起手式：

```bash
git fetch origin
git worktree add ".worktrees/<topic>" -b "<branch>" origin/main
```

### 测试与检查

- 统一入口脚本：`scripts/run-tests.sh`
- 若脚本在自动依赖同步阶段遇到 `npm ci` / `pip install` 失败，会立即返回非 0；不要再把后续 lint/test/build 输出视为有效结果。
- `Tests` / `Security Audit` 默认只对 `main` 分支 `push` 自动触发；若你在 `.worktrees/<topic>` 或普通 feature branch 上验证改动，请在 push 后用 `workflow_dispatch` 手动触发对应 workflow。
- 文档检查：`bash scripts/run-tests.sh docs-check`
- backlog 同步 dry-run：`python3 scripts/governance/sync_backlog_issues.py --repo "wyjistest/human-lncrna-atlas" --dry-run`
- 前端首屏 bundle / modulepreload 回归锚点：`docs/testing/frontend/FRONTEND_BUNDLE_REGRESSION.md`

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
