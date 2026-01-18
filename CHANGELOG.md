# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- **Phase 9.8: Codex 安全审查** (2025-12-18)
  - **P0 Critical**: `/metrics` 端点从 OpenAPI schema 隐藏 (`include_in_schema=False`)
  - **P1 High**: Admin API Key 时序攻击防护 - 使用 `secrets.compare_digest()` 常量时间比较
  - **P1 High**: 缓存命名空间注入防护 - 添加 `ALLOWED_CACHE_NAMESPACES` 白名单 + 正则验证
  - **P1 High**: Redis 密码 SecretStr 修复 - `cache.py` 使用 `get_secret_value()`
  - **P2 Medium**: 敏感字段保护 - `DATABASE_PASSWORD`, `REDIS_PASSWORD`, `ADMIN_API_KEY` 改用 `SecretStr` 类型
  - **P2 Medium**: 输入验证加固 - `lncrna_chipseq_overlap.py` 添加长度限制和逗号分隔项数验证
  - 新增 `safe_database_url` 属性用于日志脱敏
  - 涉及文件: `main.py`, `admin.py`, `config.py`, `cache.py`, `lncrna_chipseq_overlap.py`
- **Phase 9.50+: IGV ChIP-seq 轨道 DoS 防护补齐** (2025-12-29)
  - **P1 High**: `/api/v1/igv/tracks/chipseq/{species_id}.bed` 默认限制策略收敛：仅在 `chromosome+start+end`（<=10Mb）时允许不设默认上限
  - **P1 High**: IGV ChIP-seq 轨道新增 10Mb 区域大小上限（与其他 IGV 轨道一致）
  - **P2 Medium**: IGV 相关日志字段统一 `sanitize_for_log()`（降低日志注入/日志膨胀风险）
  - 涉及文件: `frontend/backend/app/routers/igv_chipseq.py`, `frontend/backend/app/routers/igv_overlap_track.py`, `frontend/backend/tests/test_security_igv_track_dos_limits_unit.py`

### Added
- **Admin Monitoring 可观测性补齐** (2026-01-18)
  - `GET /api/v1/admin/metrics`：轻量 in-memory 请求级指标（包含 `cache_stats` 摘要）
  - `POST /api/v1/admin/metrics/reset-stats`：重置 in-memory 监控统计（不影响 Prometheus `/metrics`）
  - `POST /api/v1/admin/cache/reset-stats`：重置缓存统计计数器（不清缓存）
  - 后端回归脚本改为 Prometheus 文本校验（避免把 `/metrics` 当 JSON）

### Fixed
- **Phase 9.3: 代码审查修复** (2025-12-15)
  - 全局异常返回结构：统一为 `{detail: {...}}` 格式与前端约定一致
  - Limiter 实例统一：`lncrna_chipseq_overlap.py` 复用共享的 limiter
  - 脚本硬编码路径：改为环境变量 + argparse 参数化
  - Vite 兼容性：`process.env.NODE_ENV` → `import.meta.env.DEV`
  - 分页交互：搜索/筛选时重置页码到第一页

- **Phase 9.51: 前端可访问性与 AntD6 兼容** (2025-12-30)
  - Sankey Flow：加载态也渲染页面标题（`h1`），修复 Playwright 可访问性用例失败
  - Ant Design 6：`Alert` 组件迁移 `message` → `title`，清理控制台弃用警告（降低 E2E flaky 风险）
  - 涉及文件: `frontend/web/src/pages/Visualization/SankeyFlow/index.tsx`, `frontend/web/src/pages/**`, `frontend/web/src/components/**`

- **Phase 9.52: ChIP-seq 基因 peaks 导出端点补齐** (2025-12-30)
  - 新增 `/api/v1/features/chipseq/genes/{gene_id}/export`（BED 导出），修复 Playwright 导出用例因 404 被跳过
  - 补充后端集成测试覆盖导出端点基本契约
  - 涉及文件: `frontend/backend/app/routers/chipseq_export.py`, `frontend/backend/tests/test_chipseq_api.py`

### Changed
- **移除未使用依赖**: zustand (前端状态管理库，项目中未实际使用)

### Fixed
- **Ruff Lint 全面修复** (2025-12-15)
  - 自动修复 84 个问题：未使用导入、多余 f-string 前缀
  - 手动修复 22 个问题：变量命名、未使用变量、notebook 格式
  - 模糊变量名修复：`l` → `lnc` (PEP8 E741 规范)
  - main.py 导入顺序：添加 `# noqa: E402` 注释（mimetypes 配置必须先于导入）
  - Jupyter notebook 代码风格：拆分单行多语句、import 置于 cell 顶部

### Changed
- **涉及文件**: etl/import_ortholog_data.py, frontend/backend/main.py, frontend/backend/app/routers/visualization.py, frontend/backend/tests/*.py, scripts/*.py, notebooks/01_high_affinity_analysis.ipynb

### Added
- **Phase 8.3: Codex 5轮代码审查** (2025-12-13)
  - 使用 OpenAI Codex CLI (gpt-5.2) 进行 5 轮迭代代码审查
  - 新增 8 个测试文件，6 个新模块文件
  - 新增 `DecimalAsFloat` 类型别名（Pydantic v2 兼容）
  - 新增 `OverlapSortField` 和 `OverlapSortOrder` 枚举（SQL 注入防护）

### Fixed
- **N+1 查询优化** - `conservation.py` 批量计算 conservation_map
- **SQL 注入防护** - 字符串参数改为 Enum 白名单验证
- **命令注入修复** - 移除所有 `shell=True` subprocess 调用
- **Pydantic v2 兼容** - `json_encoders` → `PlainSerializer`
- **React Hooks 依赖** - 修复 3 处 missing dependency 警告
- **未使用导入清理** - 移除 `chipseq.py`, `import_base.py` 中的死代码
- **CI: Backend tests silent failure** - Fixed pytest exit code handling in `.github/workflows/test.yml`

### Changed
- **性能优化**: O(n²) → O(n log n) 滑动窗口算法 (`chipseq_export.py`)
- **代码质量**: 26 个文件修改，+1,059/-828 行代码变更
- **安全加固**: Ruff S608 安全规则全部通过
