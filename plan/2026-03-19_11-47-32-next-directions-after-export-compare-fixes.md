---
mode: plan
cwd: /data/wenyujianData/human-lncrna-atlas-github
task: 导出/compare/MV 修复后的下一阶段方向规划
complexity: medium
tool: mcp__sequential-thinking__sequentialthinking
total_thoughts: 7
created_at: 2026-03-19T11:47:32+08:00
---

# Plan: 导出/compare/MV 修复后的下一阶段方向

🎯 任务概述

当前基线已经完成一轮“纠偏型”修复：导出链路更真实、`/chipseq-compare` 不再展示 mock 数据、MV 缺失时的后端行为更诚实、CI 也已恢复到可通过状态。下一阶段不应继续零散补洞，而应该围绕“真实能力缺口、可运维性、验证闭环”来推进。

本计划基于三条证据线整理：
- 对外承诺：`README.md` 已明确 `VITE_API_BASE_URL` 只能填 origin，`/chipseq-compare` 当前只是状态页。
- 代码现状：`frontend/web/src/api/globalCompare.ts` 明确声明 public global compare contract 目前不存在；Overlap/MV 相关后端已具备降级，但仍强依赖运维前置条件。
- 验证机制：`.github/workflows/test.yml` 的 self-hosted fast path 仍把大量检查串在单个核心步骤里，定位成本偏高。

## 当前判断

1. **最重要的缺口不是“再修一个 bug”**  
   当前最显眼的产品能力缺口，是 `/chipseq-compare` 仍没有真实后端契约，只是被诚实地暴露为 unavailable。这个状态比 mock 好，但仍然是导航层面的未兑现承诺。

2. **Overlap/MV 已经从“功能错误”变成“运维依赖”问题**  
   代码层已经能在 MV 缺失时优雅退化，但大染色体、重查询、导出性能仍然受 `mv_lncrna_chipseq_overlaps` 是否存在/刷新是否健康影响。接下来重点应转向“如何让这个前置条件可见、可维护、可恢复”。

3. **CI 通过了，但可解释性不够强**  
   `Tests` workflow 的 self-hosted fast path 把核心检查集中在一个长步骤里，虽然能跑通，但对未来排障和演进并不友好。下一阶段应该优先提升失败归因能力，而不是盲目扩矩阵。

4. **项目现在缺少一个新的“真实交付主题”**  
   这轮提交主要是修正错误承诺。下一轮应该选一个主题型方向推进，例如“real compare contract”“MV operability”“research baselines 扩展”，而不是同时铺太多线。

## 建议方向

### 方向 A：为 `/chipseq-compare` 定义真实后端契约，或明确降级为非主导航能力

**为什么现在做**
- 当前导航仍然暴露 `/chipseq-compare`，但前端 API 客户端已明确拒绝调用假接口。
- 这意味着产品入口存在，但能力并不存在，后续最容易再次滑回“前端先做 mock、后端再补”的失真模式。

**建议做法**
1. 先做 contract 设计，而不是先写页面。
2. 明确 compare 的问题边界：
   - 是“跨 gene 的全局 mark 对比”？
   - 还是“基于一组 gene 的聚合 compare”？
   - 还是把现有 gene-scoped compare 能力重新组织成入口流程？
3. 若 1 个迭代内没有后端数据/查询方案 owner，则把 `/chipseq-compare` 从主导航降为文档入口或实验入口。

**最小交付**
- 一份 API contract 草案
- 一份查询成本评估（直接 JOIN / 预聚合表 / 新 MV）
- 一份前端能力切换方案（feature flag 或 availability registry）

**验收**
- 要么新增真实 backend contract 并接上 smoke test
- 要么移除“像已上线功能”的视觉暗示，不再让用户误以为它可用

### 方向 B：把 MV 从“代码里能降级”升级为“运维上可管理”

**为什么现在做**
- Overlap 与 epigenetic 相关能力已经具备更安全的 fallback，但 fallback 本身不是长期解法。
- `docs/backend/OVERLAP_MATERIALIZED_VIEW.md` 已说明 MV 是性能关键路径，这说明问题已从代码 correctness 转到 operability。

**建议做法**
1. 给 admin/health 增加 MV 可用性与最后刷新时间的可见状态。
2. 统一 MV 相关文档入口，不要让运维知识散落在 README、schema 和脚本说明之间。
3. 增加一个最小 smoke：
   - MV 存在时，验证 fast path
   - MV 缺失时，验证 fallback 与 `QUERY_TOO_BROAD` 提示

**最小交付**
- MV status endpoint 或 admin 卡片
- 刷新/回退操作手册
- 一个面向 CI 或本地的 MV 状态验证脚本

**验收**
- 运维人员无需读源码即可判断“为什么 overlap 变慢”
- 开发人员能快速判断问题是 schema 缺失、MV 未刷新，还是查询条件过宽

### 方向 C：重构 self-hosted fast CI 的可观测性，而不是先扩大测试矩阵

**为什么现在做**
- 当前 `.github/workflows/test.yml` 的核心检查由单个 `Run core checks (self-hosted fast path)` 步骤承载。
- 这种设计在“全绿”时没问题，但在“局部失败”时会放大排障成本，也容易把未来新增检查继续堆进去。

**建议做法**
1. 保持现有 fast path，不要立刻改大矩阵。
2. 先把 fast path 的关键阶段输出成 job summary / artifact：
   - backend lint/import
   - ETL tests
   - scripts/tests
   - backend unit
   - frontend unit/lint/build
3. 如果后续仍频繁排障，再考虑把其中 2-3 段拆成独立 jobs。

**最小交付**
- CI summary 报告
- 失败阶段标识
- 与 `scripts/run-tests.sh ci` 对齐的分段输出协议

**验收**
- 单次失败能在 GitHub UI 上直接看出卡在哪一段
- 不需要翻完整日志才能判断是 backend / frontend / docs / script 哪一层出问题

### 方向 D：补 research/export 的基线与回归锚点，避免“修好了但没人盯”

**为什么现在做**
- 本轮刚修过 export 行为和前端导出接线，但回归锚点主要集中在单测与部分 smoke。
- 导出类能力最怕后续悄悄改掉参数语义、header、limit 含义或 response shape。

**建议做法**
1. 为高价值导出端点扩 API snapshot / sample baseline：
   - `export/disease-network`
   - analysis 四个导出入口
   - overlap statistics 的 schema-missing empty response
2. 让前端导出文件名解析、query param 序列化与后端响应头形成一组 contract test。
3. 对“unavailable feature”也建立回归锚点，防止以后又偷偷回到 mock 页面。

**最小交付**
- 2-4 个新增 baseline
- 1 组前后端导出契约测试
- 1 个 compare unavailable 的稳定 smoke 断言

**验收**
- 改动导出语义时，CI 能尽早提示
- 页面从“诚实 unavailable”退回“伪可用”时，测试会红

### 方向 E：建立数据导入质量护栏，减少 ETL 成功但数据质量漂移的风险

**为什么现在做**
- 项目已经有不少 ETL/导入脚本与 batch/retry 机制，但当前更偏“可跑完”，对输入质量和样本一致性的约束还不够集中。
- 随着研究导出、快照和性能基线越来越依赖真实数据，ETL 质量会逐渐成为上游风险源。

**建议做法**
1. 为关键导入增加 checksum / 文件大小 / 行数阈值校验。
2. 选 1-2 条研究路径建立小样本 hash baseline。
3. 把导入失败与“数据明显缩水”区分成不同告警等级。

**最小交付**
- 一个可复用的 ETL input validation helper
- 一组 sample dataset baseline
- 一份“数据质量异常 triage”文档

**验收**
- 数据源变化不会只在前端页面或性能报告里被动暴露
- 导入链路能更早提示“格式合法但数据异常”

## 推荐顺序

### 短期（1 周）
1. 方向 C：先提高 CI 可解释性
2. 方向 B：补 MV 运维可见性
3. 方向 D：给刚修好的 export / unavailable compare 建立回归锚点

### 中期（1-2 个迭代）
1. 方向 A：决定 `/chipseq-compare` 的真实去向
2. 方向 E：把 ETL 质量护栏纳入工程主线

### 依赖前置条件
- 若没有明确的数据 owner / 后端 owner，方向 A 不应直接开做页面实现
- 若部署环境无法可靠维护 MV，方向 B 应先做“可见状态 + 限制文档”，不要强推更复杂的 SQL 结构

## 现在不建议做的事

- 不建议把 `/chipseq-compare` 重新做成 mock-rich 页面  
  这会再次制造“看起来可用、实际上无契约”的技术债。

- 不建议立刻把 `Tests` workflow 拆成大量并行 jobs  
  当前更缺的是可解释性，不是并行度本身。

- 不建议先做大规模前端视觉改造  
  现阶段更关键的是能力边界、后端契约和验证闭环。

## 风险与注意事项

- **范围膨胀风险**：方向 A 很容易从“定义 contract”膨胀到“重做整个 compare 产品”，必须先锁边界。
- **运维耦合风险**：方向 B 如果直接推强依赖 MV 的能力，而不补状态可见性，会把部署问题继续埋在运行时。
- **CI 噪音风险**：方向 C 如果只加更多检查、不改善报告结构，会让 workflow 更慢却不更清晰。
- **数据漂移风险**：方向 D/E 若不建立样本锚点，后续回归只能靠肉眼发现。

## 参考

- `README.md:192`
- `README.md:197`
- `.github/workflows/test.yml:303`
- `docs/backend/OVERLAP_MATERIALIZED_VIEW.md:1`
- `frontend/web/src/api/globalCompare.ts:1`
- `frontend/web/src/components/GlobalCompare/index.tsx:1`
- `frontend/backend/app/routers/export.py:654`
- `frontend/backend/app/routers/analysis.py:259`
- `frontend/backend/app/routers/lncrna_chipseq_overlap.py:2110`
