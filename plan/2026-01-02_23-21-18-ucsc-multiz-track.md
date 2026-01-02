---
mode: plan
cwd: /data/wenyujianData/human-lncrna-atlas-github
task: 评估并规划接入 UCSC multiz（多序列比对/保守性）轨道到现有 IGV.js GenomeBrowser
complexity: complex
tool: mcp__sequential-thinking__sequentialthinking
total_thoughts: 10
created_at: 2026-01-02T23:21:18+08:00
---

# Plan: UCSC multiz track 接入可行性评估与落地方案

🎯 任务概述
现有项目已集成 IGV.js，并通过后端 `/api/v1/igv/*` 下发基因组与轨道配置，同时也支持直接加载 UCSC 远端 2bit（并具备 CORS + Range）。本任务目标是评估并规划“UCSC multiz track”的接入路径：优先以最小成本在现有 GenomeBrowser 中增加可选轨道；若 IGV.js 不支持 multiz 对齐（MAF/BigMaf），则退而求其次集成其衍生的保守性分数/保守元件轨道（phastCons/phyloP 等）。

📋 执行计划
1. 明确需求与验收标准
   - 需要确认“multiz track”指的是多序列比对对齐本身（Alignments/MAF）还是保守性分数/保守元件（Conservation/Elements）。
   - 默认假设：先支持 Human(hg19) 的保守性分数（bigWig）+ 可选保守元件（bigBed），并在 UI 中可开关；加载失败要有明确提示且不影响其他轨道。

2. 代码现状盘点（接入点确认）
   - 前端 IGV 初始化与轨道 URL 处理：可相对路径（后端静态 /genomes）也可绝对 URL（UCSC）。
   - 后端 IGV Track schema 支持 `type/format/url/indexURL/sourceType`，可扩展新 track。
   - 后端静态文件白名单已允许 `.bw/.bigwig` 与 `.bb/.bigbed`，具备本地托管轨道的通道。

3. 数据源可达性与格式匹配验证（关键可行性门槛）
   - 列出候选 UCSC 资源（按 assembly=hg19/hg38）：
     - 保守性分数：phastCons/phyloP（通常为 bigWig）
     - 保守元件：phastConsElements（通常为 bigBed）
     - 多序列对齐：multiz MAF/BigMaf（体量巨大，且需确认 IGV.js 是否支持）
   - 用 `curl -I`/小范围试拉验证：CORS 头、Accept-Ranges、文件大小、URL 稳定性。

4. 最小原型（优先走“无需后端改动”的路线）
   - 在后端 IGV config（Gene Mode 或 Species Mode）追加 1-2 条 UCSC 远端轨道配置（建议先 Gene Mode，降低一次性加载压力）。
   - 前端无需改动即可加载（GenomeBrowser 会将绝对 URL 原样透传给 IGV.js）。
   - 快速验证：在 `frontend/web` 的 GenomeBrowser 页面选定 locus 后能看到轨道渲染；失败时记录具体错误类型（CORS、格式不支持、超时）。

5. UI 交互与可配置化（让功能可用且可维护）
   - 在 GenomeBrowser 页面增加“Conservation/Multiz”轨道开关（默认关闭，避免初次加载变慢）。
   - 配置来源建议：后端通过环境变量/配置文件维护 track 列表（不同 assembly/不同 track URL）。

6. 若“对齐轨道”需求强制：评估替代实现（成本/收益对比）
   - 若 IGV.js 不支持 MAF/BigMaf：
     - 方案 A：仅支持保守性分数 + 元件（推荐，性价比最高）。
     - 方案 B：在前端提供“跳转/嵌入 UCSC Genome Browser”查看 multiz alignments（iframe/外链），保留现有 IGV 做其他轨道。
     - 方案 C：后端引入对齐切片服务（对 MAF 做索引与区间查询）+ 前端自定义渲染（成本最高，需明确业务价值才做）。

7. 性能与运维方案（可选但建议预留）
   - 若直连 UCSC 在生产环境不稳定：
     - 提供后端代理/缓存（best-effort，避免把浏览器直连外网作为单点），或在 `/genomes` 下本地镜像核心 bigWig/bigBed。
   - 监控：记录 track 加载失败率/耗时（前端埋点或后端代理日志）。

8. 测试与文档交付
   - 后端：为 IGV config 生成新增轨道增加单测（只验证配置结构/URL）。
   - 前端：增加轻量测试（轨道开关行为，不强依赖外网）；若要 E2E，需提供可跳过/可 mock 的策略。
   - 文档：说明支持的 assembly、轨道来源、可配置项与常见失败原因（CORS、网络、超大区域）。

⚠️ 风险与注意事项
- IGV.js 对多序列对齐（MAF/BigMaf）支持不确定：可能只能展示分数轨道（bigWig）与注释轨道（bigBed）。
- 数据体量与性能：multiz 对齐数据极大，必须按需加载；默认不建议本地全量导入数据库。
- Assembly 一致性：当前人类内置为 hg19；UCSC multiz track 必须匹配同一 assembly（否则坐标错位）。
- 外网依赖：直连 UCSC 需要稳定网络；生产环境可能需要代理/镜像方案。
- 许可与再分发：若要镜像/打包数据，需要确认 UCSC 数据使用条款与团队策略。

📎 参考
- `frontend/web/src/components/GenomeBrowser/index.tsx:35`（IGV 内置基因组与 UCSC twoBit 直连）
- `frontend/web/src/components/GenomeBrowser/index.tsx:279`（track URL 允许绝对 URL，支持直连 UCSC）
- `frontend/backend/app/routers/igv.py:55`（IGV config 下发入口）
- `frontend/backend/app/schemas/igv.py:28`（IGVTrack schema：type/format/url/sourceType）
- `frontend/backend/app/config/igv_genomes.py:63`（物种/assembly 配置现状：hg19/panTro5/rheMac10/calJac3）
- `frontend/backend/app/mounts/genomes.py:25`（/genomes 静态白名单允许 .bw/.bb，可用于本地托管）
- `frontend/backend/app/models/models.py:269`（FeatureTrack/GenomicFeature：存在“轨道注册/特征表”实现基础）
- `frontend/backend/app/routers/features.py:52`（/api/v1/features/tracks：轨道注册 API）
- `docs/DATABASE_DESIGN_FINAL.md:302`（设计中已预留 multiz_conserved track 概念）
- `schema/v2.3/02_extension.sql:68`（multiz_conserved 预定义 track）
