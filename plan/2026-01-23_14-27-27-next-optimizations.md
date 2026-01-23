---
mode: plan
cwd: /data/wenyujianData/human-lncrna-atlas-github
task: 接下来两周的优化方向与执行计划
complexity: medium
tool: mcp__sequential-thinking__sequentialthinking
total_thoughts: 7
created_at: 2026-01-23T14:29:41+08:00
---

# 接下来两周的优化方向与执行计划

已使用 superpowers:brainstorming 与 superpowers:writing-plans 生成此计划（因更高优先级约束，计划文件存放在 `plan/`）。

## 🎯 任务概述
目标是将“可审计、可回滚、可定位”的优化方向系统化落地，覆盖 CI 连续性、测试/基线回归锚点、性能可观测与慢点处置、数据与 ETL 可靠性、前端技术债清理。计划以 1 周与 2 周为节奏，按小步 PR 推进，保证每步都有可验证的验收标准与回滚路径。

## ✅ 已有上下文与约束
- 已有路线图：`docs/ROADMAP_2026-01-21.md`、`docs/ROADMAP_2026-01-17.md`
- 性能定位指南：`docs/PERFORMANCE_TRIAGE.md`
- 回归锚点：`docs/baselines/`、`scripts/api_snapshot.py`
- CI 脚本：`.github/workflows/test.yml`、`.github/workflows/security-audit.yml`
- 测试入口：`scripts/run-tests.sh`
- 约束：用户明确要求“都做、可审计可回滚、小步提交、self-hosted 优先”，且“先不管系统级服务（systemd）”

## 🧠 用户确认要点（来自对话）
- 方向：都推进、都做
- 时间节奏：1 周优先，2 周也可
- 目标偏好：性能可定位、可审计、可回滚
- 执行风格：多用 superpower，按推荐方案走

## 🧭 优化方向（含推荐与备选）
### 方向 A：CI 连续性与成本控制（P0-P1）
- 方案 1（推荐）：继续保持 `workflow_dispatch` 为主，恢复 push/PR 触发需明确额度后再开。
- 方案 2：push/PR 触发限频或仅在关键分支触发，降低成本。
- 方案 3：保持全量触发但迁移 self-hosted 扩容（成本与维护更高）。

### 方向 B：回归锚点与测试基线扩展（P1）
- 方案 1（推荐）：扩大 API snapshot 覆盖、补充最小样例数据基线。
- 方案 2：优先 E2E 关键路径基线（成本高，需环境）。
- 方案 3：仅保留关键模块基线（风险低但覆盖不足）。

### 方向 C：性能可解释与慢点处置（P1）
- 方案 1（推荐）：沿 `docs/PERFORMANCE_TRIAGE.md` 形成统一 issue 模板与导出流程。
- 方案 2：为 Top endpoints 增加诊断字段（代码改动较多）。
- 方案 3：重点端点分层缓存与限流（复杂度高）。

### 方向 D：数据与 ETL 可靠性（P2）
- 方案 1（推荐）：下载/导入链路增加可选校验（checksum/行数/尺寸阈值）。
- 方案 2：构建小型样例数据集与 hash 基线。

### 方向 E：前端技术债与告警清理（P2）
- 方案 1（推荐）：持续清理 AntD deprecations，保证构建无 warning。
- 方案 2：集中一次性清理（风险高、回滚成本高）。

## 📋 两周执行计划（可审计、可回滚）
### Week 1（优先级 P0-P1）
1. **CI 连续性盘点与恢复策略**  
   - 文件：`.github/workflows/test.yml`、`.github/workflows/security-audit.yml`  
   - 产出：触发策略决策记录 + 可回滚修改方案  
   - 验收：`workflow_dispatch` 可在 self-hosted 可靠运行  

2. **回归锚点扩展（API snapshot + 基线文档）**  
   - 文件：`scripts/api_snapshot.py`、`docs/baselines/*`  
   - 产出：新增 2-4 个高风险端点快照  
   - 验收：`python3 scripts/api_snapshot.py --check-baseline ...` 一致  

3. **性能可定位流程固化**  
   - 文件：`docs/PERFORMANCE_TRIAGE.md`、`scripts/admin_metrics_snapshot.py`  
   - 产出：Issue 模板与导出流程说明  
   - 验收：一次导出可生成可贴 issue 的 Markdown  

### Week 2（优先级 P1-P2）
4. **数据与 ETL 可靠性增强**  
   - 文件：`scripts/` 下 ETL/下载脚本、`docs/` 相关说明  
   - 产出：可选校验逻辑与样例数据基线  
   - 验收：坏数据可被检测并输出明确错误  

5. **前端技术债清理（deprecations）**  
   - 文件：`frontend/web` 相关组件与构建日志  
   - 验收：`npm run build` 无 AntD deprecations  

## 🧪 测试与验证策略
- 快速验证：`./scripts/run-tests.sh ci`  
- 基线一致性：`python3 scripts/api_snapshot.py --check-baseline docs/baselines/api-snapshot.sample.json`  
- 文档一致性：`./scripts/run-tests.sh docs-check`  
- 前端构建：`cd frontend/web && npm run build`  

## 🔁 审计与回滚策略
- 所有改动小步提交（每个主题 1-2 commits）。
- 任何失败通过 `git revert <commit>` 可回滚（不强制重写历史）。
- 文档与基线必须同步更新，否则不合入。

## ⚠️ 风险与依赖
- 依赖升级链可能引发大范围变更：建议分批、可回滚。
- E2E/ETL 校验需要数据库与数据集，耗时不确定。
- CI 额度/组织策略为外部依赖，需明确后再恢复自动触发。

## 📎 参考（关键入口）
- `docs/ROADMAP_2026-01-21.md:18`
- `docs/ROADMAP_2026-01-17.md:32`
- `docs/PERFORMANCE_TRIAGE.md:1`
- `docs/baselines/README.md:1`
- `scripts/api_snapshot.py:1`
- `.github/workflows/test.yml:31`
- `scripts/run-tests.sh:1`

## ✅ TODO（可执行清单）
- [ ] 确认 CI 触发策略（保留手动 / 恢复 push / 混合）
- [ ] 选定 2-4 个高风险端点扩展基线
- [ ] 固化性能导出 + issue 模板（含证据链接）
- [ ] 选择 ETL 校验范围与样例基线方案
- [ ] 评估前端 deprecations 清理范围
