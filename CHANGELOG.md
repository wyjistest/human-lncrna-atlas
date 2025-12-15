# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
