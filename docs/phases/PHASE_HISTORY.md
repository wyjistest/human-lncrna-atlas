# Phase 历史文档

> 此文档包含 Human LncRNA Atlas 项目的详细 Phase 历史记录，从 CLAUDE.md 中移出以保持主文档简洁。

## 目录

- [Phase 5.0-5.3: 性能优化](#phase-50-53-性能优化)
- [Phase 6.0: 科研数据分析](#phase-60-科研数据分析)
- [Phase 6.1: IGV 功能增强](#phase-61-igv-功能增强)
- [Phase 7.0-7.5: API 完善与代码质量](#phase-70-75-api-完善与代码质量)
- [Phase 8.0-8.3: 代码审查与修复](#phase-80-83-代码审查与修复)
- [Phase 9.0: 高级可视化](#phase-90-高级可视化)
- [Phase 9.1: 代码审查修复](#phase-91-代码审查修复)
- [Phase 9.2: Ruff Lint 修复](#phase-92-ruff-lint-全面修复)
- [Phase 9.3: 代码审查修复](#phase-93-代码审查修复)
- [Phase 9.45: Codex 三十五次审查修复](#phase-945-codex-三十五次审查修复)
- [Phase 9.46: Codex 三十六次审查修复](#phase-946-codex-三十六次审查修复)
- [Phase 9.47: Codex 三十七次审查修复](#phase-947-codex-三十七次审查修复)
- [Phase 9.48: Codex 三十八次审查修复](#phase-948-codex-三十八次审查修复)

---

## Phase 5.0-5.3: 性能优化

### Conservation API (Phase 5.0)

跨物种保守性分析功能，通过 `core_id` 机制实现跨物种基因映射。

| API 端点 | 说明 |
|----------|------|
| `/api/v1/conservation/overview` | 保守性统计概览 |
| `/api/v1/conservation/matrix` | 物种间保守性矩阵 |
| `/api/v1/conservation/regulations` | 保守调控关系列表 |

### Network 优化 (Phase 5.1)

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| API 响应 | 4951 ms | 7-50 ms | **550x** |
| 响应大小 | 240 KB | ~20 KB | **92% ↓** |

### Genes Options API (Phase 5.2)

| 指标 | 数值 |
|------|------|
| 首次响应 | 308 ms |
| 缓存响应 | 238 ms |
| 数据量 | 17,248 基因 |

### Sankey Flow (Phase 5.3)

三层 Sankey 流向图：lncRNA → Gene → Disease

---

## Phase 6.0: 科研数据分析

### 6.0-A: 数据导出 API

| 端点 | 用途 | 响应时间 |
|------|------|---------|
| `/api/v1/export/high-affinity` | 网络分析 | 14-60ms |
| `/api/v1/export/conservation` | 进化分析 | 20-50ms |
| `/api/v1/export/chipseq-overlaps` | 表观遗传 | 25-100ms |
| `/api/v1/export/disease-network` | 治疗靶点 | 30-150ms |

### 6.0-B: Jupyter Notebooks

| Notebook | 分析主题 |
|----------|---------|
| `01_high_affinity_analysis.ipynb` | 高亲和力调控网络 |
| `02_conservation_patterns.ipynb` | 跨物种保守性模式 |
| `03_epigenetic_marks.ipynb` | 表观遗传标记关联 |
| `04_disease_networks.ipynb` | 疾病关联网络 |

### 6.0-C: 前端分析结果展示

访问地址: `/analysis`

---

## Phase 6.1: IGV 功能增强

Overlap 页面 IGV 升级：
- GenomeBrowserToolbar
- ChIP-seq 轨道选择器
- RepeatMasker 轨道控制
- SVG/PNG 导出
- 4 物种支持

---

## Phase 7.0-7.5: API 完善与代码质量

### Phase 7.0: API 暴露

新增 20 个前端 API 方法，API 利用率从 30% 提升至 90%+。

### Phase 7.1: 代码质量修复

- React Hooks 顺序违规修复
- 后端空值检查
- ESLint 0 errors

### Phase 7.2: 单元测试

| 指标 | 结果 |
|------|------|
| 测试文件 | 12 个 |
| 测试用例 | 177 个 |
| 通过率 | 100% |

### Phase 7.3: 代码审查综合修复

- 安全修复 (5 项): X-Forwarded-For 验证, DB 异常清洗, CORS 严格模式
- API 契约 (6 项): 端点别名, 字段命名统一
- 性能优化 (4 项): Redis SCAN, MemoryCache 线程安全
- 代码清理 (3 项): 删除 115+ 过时 i18n 副本

### Phase 7.4: 本地审查修复

- ETL 序列映射 Bug 修复
- ESLint 警告: 904 → 110
- MIT License 添加

### Phase 7.5: 超大文件拆分

| 文件 | 拆分前 | 拆分后 | 减少率 |
|------|--------|--------|--------|
| Network/index.tsx | 1,779 行 | 287 行 | 84% |
| igv.py | 2,692 行 | 520 行 | 81% |
| chipseq.py | 2,634 行 | 236 行 | 91% |

---

## Phase 8.0-8.3: 代码审查与修复

### Phase 8.0: 代码审查修复

4 Agent 并行执行，修复 14 个问题：
- 高优先级: 基因组版本文档, 前端错误处理, 网络过滤 bug
- 性能: count() 缓存, 缓存 key 统一
- 工程化: 未使用依赖清理, CI 增强
- 可移植: 硬编码路径 → 环境变量

### Phase 8.1: CI/配置修复

- React Compiler memoization 错误
- GENOMES_DIR 配置
- 错误消息显示增强

### Phase 8.2: 数据一致性修复

- Migration JOIN 逻辑修复
- ETL 批次内重复处理
- genes.core_id NULL 支持

### Phase 8.3: Codex 5轮代码审查

使用 OpenAI Codex CLI (gpt-5.2) 进行 5 轮迭代审查，最终通过。

---

## Phase 9.0: 高级可视化

### 新增功能

| 功能 | 技术实现 |
|------|---------|
| Chord 图 | ECharts graph + circular layout |
| 交互式保守性矩阵 | ECharts click + Ant Design Drawer |
| 可视化导航中心 | 响应式卡片布局 |

### API 端点

`GET /api/v1/visualization/chord-data` - Chord 图数据

---

## Phase 9.1: 代码审查修复

### Codex (GPT-5.2) 审查修复

| 问题 | 修复内容 |
|------|---------|
| SlowAPI 限流集成 | 正确导入 ASGI middleware |
| OpenAPI 类型生成 | 添加 `npm run generate:types` |
| Ant Design v6 弃用 | 迁移 130+ 处 API 调用 |
| 文档配置契约 | `DATABASE_URL` → `DB_*` 变量 |
| Schema 脚本整理 | 标记弃用 + 添加 README |

### Ant Design v6 API 迁移

| 弃用 API | 新 API | 影响文件数 |
|----------|--------|-----------|
| `Space direction` | `Space orientation` | 82 |
| `Statistic valueStyle` | `styles.content` | 42 |
| `Drawer width` | `styles.wrapper.width` | 4 |
| `Card bodyStyle` | `styles.body` | 3 |

### 新增文件

| 文件 | 用途 |
|------|------|
| `src/types/echarts.ts` | ECharts 回调类型定义 |
| `schema/README.md` | Schema 执行顺序说明 |

### 验证结果

- ESLint: 0 errors, **0 warnings** ✅
- Unit Tests: 171 passed
- Build: ✅ 成功

### ESLint Warnings 清零

| Commit | 描述 | 警告数变化 |
|--------|------|-----------|
| `13f29c8` | 初始清理 | 135 → 124 |
| `a81136c` | Network 模块类型修复 | 124 → 89 |
| `c6f0baa` | ECharts 回调类型修复 | 89 → 51 |
| `2fdb483` | 最终清理完成 | 51 → 0 |

**修复的类型问题:**
- API 层: 添加后端响应接口 (`ChordBackendResponse`, `ClusteringBackendResponse`)
- ECharts 回调: 使用 `HeatmapParams`, `BarParams`, `TooltipFormatterParams`
- Table 组件: 使用 `Record<string, unknown>` 替代 `any`
- Selector 组件: 扩展 `DefaultOptionType` 添加自定义属性
- MSW 初始化: `console.log` → `console.warn`

---

## Phase 9.2: Ruff Lint 全面修复

### 修复统计

| 类别 | 数量 | 说明 |
|------|------|------|
| 自动修复 | 84 | 未使用导入、多余 f-string 前缀 |
| 手动修复 | 22 | 变量命名、未使用变量、notebook 格式 |
| **总计** | **106** | 全部通过 |

### 主要修复内容

| 规则 | 问题描述 | 修复方式 |
|------|---------|---------|
| F401 | 未使用的导入 | 自动删除 |
| F541 | f-string 无占位符 | 移除 `f` 前缀 |
| F841 | 变量赋值后未使用 | 删除或添加注释说明 |
| E741 | 模糊变量名 `l` | 重命名为 `lnc`/`line` |
| E402 | 导入不在文件顶部 | 添加 `# noqa: E402` (mimetypes 初始化必须先于导入) |
| E702 | 单行多语句 (notebook) | 拆分为多行 |

### 涉及文件 (31 个)

- **ETL 脚本**: `import_*.py`, `fix_chimp_empty_dna.py`
- **后端核心**: `main.py`, `visualization.py`
- **测试文件**: `test_*.py` (11 个文件)
- **验证脚本**: `scripts/*.py`
- **Notebook**: `01_high_affinity_analysis.ipynb`

### Codex (GPT-5.2) 审查确认

| 检查项 | 状态 |
|--------|------|
| 无功能性风险 | ✅ |
| 导入顺序处理正确 | ✅ |
| 变量移除安全 | ✅ |
| 测试全部通过 | ✅ (200 tests) |

### 验证结果

| 检查 | 状态 |
|------|------|
| `ruff check .` | ✅ All checks passed |
| `npm run lint` | ✅ 0 errors, 0 warnings |
| `npm run build` | ✅ 成功 (17.13s) |
| `pytest tests/` | ✅ 200 passed |

---

## Phase 9.3: 全面代码审查

### 审查概述

**审查日期**: 2025-12-16
**审查方法**: 安全审计 + 性能审计 Agent 并行执行
**详细报告**: `frontend/backend/CODE_REVIEW_REPORT_2025-12-16.md`

### 修复统计

| 优先级 | 发现 | 已修复 |
|--------|------|--------|
| P0 (Critical) | 4 | 4 ✅ |
| P1 (High) | 7 | 2 ✅ |
| P2 (Medium) | 7 | 待后续迭代 |

### P0 修复清单

| ID | 问题 | 文件 | 修复内容 |
|----|------|------|----------|
| CR-FIX-001 | SQL 注入风险 | `database.py:80,154,160` | f-string → 参数化查询 |
| CR-FIX-002 | Redis 超时过短 | `cache.py:102` | socket_timeout 5s → 10s |
| CR-FIX-003 | 无界查询 OOM | `export.py:502-511` | 无过滤时限制 500 条 |
| CR-FIX-004 | 限流实现不一致 | `lncrna_chipseq_overlap.py:40` | 统一使用 chipseq_rate_limit |

### P1 修复清单

| ID | 问题 | 文件 | 修复内容 |
|----|------|------|----------|
| CR-FIX-005 | 缺少 JOIN 索引 | `frontend/backend/scripts/add_regulation_indexes.sql` | 4 个新索引 |
| CR-FIX-006 | ILIKE 全表扫描 | `frontend/backend/scripts/add_pg_trgm_indexes.sql` | 4 个 GIN 索引 |

### 数据库迁移

**已创建的索引 (需手动执行):**

```bash
# Regulation 表索引 (优化 JOIN 和排序)
psql -d lncrna_production -f frontend/backend/scripts/add_regulation_indexes.sql

# pg_trgm GIN 索引 (优化 ILIKE '%pattern%')
psql -d lncrna_production -f frontend/backend/scripts/add_pg_trgm_indexes.sql
```

| 索引 | 表 | 用途 |
|------|------|------|
| `idx_regulations_lncrna_gene_id` | regulations | JOIN genes 优化 |
| `idx_regulations_target_gene_id` | regulations | JOIN genes 优化 |
| `idx_regulations_species_ba` | regulations | 物种 + 亲和力排序 |
| `idx_regulations_species_chr` | regulations | 物种 + 染色体过滤 |
| `idx_traits_trait_name_trgm` | traits | 模糊搜索优化 |
| `idx_chipseq_experiments_cell_type_trgm` | chipseq_experiments | 模糊搜索优化 |
| `idx_genes_gene_name_trgm` | genes | 模糊搜索优化 |
| `idx_genes_gene_ensembl_id_trgm` | genes | 模糊搜索优化 |

### 技术细节

**SQL 注入防护**

```python
# Before (P0 漏洞)
cursor.execute(f"SET statement_timeout = {QUERY_TIMEOUT_MS}")

# After (参数化)
cursor.execute("SET statement_timeout = %s", (QUERY_TIMEOUT_MS,))
```

**无界查询保护**

```python
# export.py - disease-network 端点
if trait_name is None:
    effective_limit = min(limit, 500)  # 无过滤时最多返回 500 条
    logger.warning(f"无过滤条件，限制返回 {effective_limit} 条")
else:
    effective_limit = limit
```

**限流统一化**

```python
# Before: 本地实现
def _is_private_request(request: Request) -> bool: ...  # 50 行重复代码

# After: 统一模块
from app.routers.chipseq_rate_limit import rate_limit
```

### 新增环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ADMIN_API_KEY` | Admin API 密钥 | - |
| `ADMIN_REQUIRE_API_KEY` | 严格模式 | false |
| `TRUSTED_PROXIES` | 可信代理 IP (JSON 数组) | - |
| `RATE_LIMIT_BYPASS_PRIVATE` | 私网绕过限流 | false |

### 待修复 P1 问题

| 问题 | 建议 |
|------|------|
| 核心路由缺少限流 | 添加 @rate_limit 装饰器 |
| Admin 私网自动信任 | 生产环境启用 ADMIN_REQUIRE_API_KEY=true |
| 缺少安全头 | 添加 CSP、X-Frame-Options 中间件 |
| 连接池过小 | pool_size=5 → 20 |
| 缓存无效化缺失 | 数据修改后调用 cache.invalidate() |

### Commit 记录

| Commit | 描述 |
|--------|------|
| `408dca9` | P0/P1 代码审查修复 (CR-001~CR-004) |
| `4e230a0` | P1 代码审查修复 (CR-005, CR-006) |
| `ddf4fb6` | 全面代码审查修复 - Phase 9.3 续 |
| `8cd9d32` | 添加全面代码审查报告 |
| `0e43ae6` | 更新 CLAUDE.md 文档 |

### 验证结果

| 检查 | 状态 |
|------|------|
| `ruff check .` | ✅ All checks passed |
| `npm run lint` | ✅ 0 errors, 0 warnings |
| `npm run build` | ✅ 成功 (21.77s) |
| GitHub Actions | ✅ 构建通过 |

---

## Phase 9.45: Codex 三十五次审查修复

**日期**: 2025-12-28

### 修复摘要

| 类别 | 修复内容 | 优先级 |
|------|----------|--------|
| 安全 | ETL 数据库连接泄漏防护 | P0 |
| 安全 | Admin CSRF Origin 增强校验 | P1 |
| 正确性 | SQLAlchemy `text` 导入缺失修复 | P0 |
| 代码质量 | 测试文件 import/pytestmark 统一 | P2 |

### 安全修复详情

**ETL 连接泄漏防护** (`etl/fix_chimp_empty_dna.py`)

```python
# Before: 异常时连接未关闭
conn = psycopg2.connect(**DB_CONFIG)
cursor = conn.cursor()
# ... 操作 ...
cursor.close()
conn.close()

# After: try/finally 确保关闭
conn = psycopg2.connect(**DB_CONFIG)
try:
    cursor = conn.cursor()
    # ... 操作 ...
finally:
    cursor.close()
    conn.close()
```

**Admin CSRF Origin 增强** (`frontend/backend/app/routers/admin.py`)

```python
# Before: 字符串操作解析 Origin
origin = request.headers.get("origin", "")
if origin.startswith("http://") or origin.startswith("https://"):
    # 可能被绕过

# After: urlsplit 安全解析
from urllib.parse import urlsplit
parsed = urlsplit(origin)
if parsed.scheme not in ("http", "https"):
    raise HTTPException(403, "Invalid Origin")
```

**SQLAlchemy 导入修复** (`frontend/backend/app/routers/chipseq_marks.py`)

```python
# Before: 缺失导入导致运行时 NameError
from sqlalchemy import func

# After: 补充 text 导入
from sqlalchemy import func, text
```

### 代码质量改进

| 文件 | 修复 |
|------|------|
| `main.py` | 导入顺序整理，mimetypes.add_type 移到导入后 |
| `test_*.py` (9个文件) | 统一 import/pytestmark 顺序 |
| `lncrna_chipseq_overlap.py` | 清理未使用变量 |
| `useChIPSeq.ts` | 消除分页字段剥离的未使用变量告警 |

### 验证结果

| 检查 | 结果 |
|------|------|
| `ruff check .` | ✅ All checks passed |
| `pytest -m unit` | ✅ 217 passed |
| `npm run lint` | ✅ 0 errors |
| `npm run test:run` | ✅ 184 passed |
| `npm run build` | ✅ 成功 |
| GitHub Actions - Tests | ✅ success |
| GitHub Actions - Security Audit | ✅ success |

### Commit

```
65b34a8 fix: Phase 9.45 Codex 三十五次审查修复 - 安全加固 + 代码质量
```

---

## Phase 9.46: Codex 三十六次审查修复

**日期**: 2025-12-28

### 修复摘要

| 类别 | 修复内容 | 优先级 |
|------|----------|--------|
| 性能/DoS | 导出接口流式查询 stream_results 优化 | P0 |
| 正确性 | 测试参数名修正 (format alias) | P1 |

### 流式查询优化

**问题**: 导出接口 CSV/Excel/JSONL 分支未启用 `stream_results`，大结果集时 PostgreSQL 驱动可能在客户端缓冲。

**修复**: 新增 `_execute_streaming()` 辅助函数

```python
def _execute_streaming(db: Session, stmt, params=None):
    executable = stmt.execution_options(stream_results=True)
    if params is not None:
        return db.execute(executable, params)
    return db.execute(executable)
```

### 测试参数名修正

| 文件 | 修复 |
|------|------|
| `test_export_regulations.py` | `output_format` → `format` |
| `test_security_like_filter.py` | `output_format` → `format` |

### 新增测试

- `test_export_stream_results_unit.py` (2 tests)

### Commit

```
860437f fix: Phase 9.46 Codex 三十六次审查修复 - 流式查询优化 + 测试参数修正
```

---

## Phase 9.47: Codex 三十七次审查修复

**日期**: 2025-12-28

### 修复摘要

| 类别 | 修复内容 | 优先级 |
|------|----------|--------|
| 资源管理 | 流式导出资源清理 (try/finally close) | P0 |
| 安全 | CSV 公式注入防护增强 (前导空白/BOM 绕过) | P1 |

### 资源清理修复

**问题**: `create_db_row_generator()` 未在生成器结束/取消时显式 `close()`，服务端游标场景下客户端断开可能延迟释放连接。

**修复**:

```python
def create_db_row_generator(db_execute_result, transform=None):
    close = getattr(db_execute_result, "close", None)
    try:
        for row in db_execute_result:
            row_dict = dict(row._mapping)
            if transform:
                row_dict = transform(row_dict)
            yield row_dict
    finally:
        if callable(close):
            close()
```

### CSV 公式注入增强

**问题**: `sanitize_csv_value()` 未处理前导空白或 UTF-8 BOM 绕过。

**修复**:

```python
# 检测前归一化
check_value = value.lstrip("\ufeff").lstrip()
if _CSV_FORMULA_PATTERN.match(check_value):
    return "'" + value
```

### 新增测试

- `test_streaming_export_resource_cleanup_unit.py` (2 tests)
- `test_security_csv_formula_injection_unit.py` (2 tests)

### Commit

```
a96517e fix: Phase 9.47 Codex 三十七次审查修复 - 资源清理 + CSV 注入防护
```

---

## Phase 9.48: Codex 三十八次审查修复

**日期**: 2025-12-28

### 修复摘要

| 类别 | 修复内容 | 优先级 |
|------|----------|--------|
| DoS 防护 | IGV 轨道区域大小限制 (10Mb) | P0 |
| DoS 防护 | IGV 轨道默认记录限制 (50k) | P0 |
| 功能增强 | 新增 limit 参数控制返回记录数 | P1 |

### DoS 防护参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `MAX_REGION_SIZE_BP` | 10,000,000 | 区域大小上限 (10Mb) |
| `DEFAULT_MAX_RECORDS_NO_REGION` | 50,000 | 无过滤时默认记录限制 |
| `MAX_LIMIT` | 100,000 | 用户可指定的最大记录数 |

### 防护逻辑

```python
# 区域过大拒绝
if start_int is not None and end_int is not None:
    if (end_int - start_int) > MAX_REGION_SIZE_BP:
        raise HTTPException(400, f"region too large (max {MAX_REGION_SIZE_BP} bp)")

# 智能限制
has_region_filter = chr is not None and start_int is not None and end_int is not None
if limit is not None:
    max_records = limit
elif not has_region_filter and lncrna is None:
    max_records = DEFAULT_MAX_RECORDS_NO_REGION
else:
    max_records = None  # 有过滤条件时不限制
```

### 修改文件

| 文件 | 变更 |
|------|------|
| `app/core/igv_stream_generators.py` | 添加 `max_records` 参数到 3 个生成器 |
| `app/routers/igv_regulations.py` | DoS 防护逻辑 |
| `app/routers/igv_repeatmasker.py` | DoS 防护逻辑 |

### 新增测试

- `test_security_igv_track_dos_limits_unit.py` (8 tests)

### 验证结果

| 检查 | 结果 |
|------|------|
| `pytest -m unit` | ✅ 233 passed |
| `npm run build` | ✅ 成功 |

### Commit

```
ea610ef fix: Phase 9.48 Codex 三十八次审查修复 - IGV 轨道 DoS 防护
```

---

## Phase 9.49: Codex 三十九次审查修复

**日期**: 2025-12-28

### 修复摘要

| 类别 | 修复内容 | 优先级 |
|------|----------|--------|
| 安全 | safeWindow.ts 日志脱敏 (防 token 泄露) | P1 |
| 代码质量 | ETL logging.basicConfig 副作用移除 | P2 |
| 代码质量 | config.py 未使用 import 清理 | P2 |
| 安全 | /genomes percent-encoding 路径遍历加固 | P0 |
| 性能/DoS | compute_conservation_map 分块查询 | P1 |
| 并发安全 | 缓存 Singleflight 防护 (cache stampede) | P0 |
| 资源管理 | Cytoscape tooltip 资源清理 | P1 |
| 资源管理 | IGV locuschange 事件解绑 | P1 |

### 日志脱敏 (safeWindow.ts)

**问题**: 阻止不安全 URL 时，日志中会记录完整 URL（含 query/fragment），可能泄露 token。

**修复**:

```typescript
function redactUrlForLog(rawUrl: string): string {
  // 1. 移除换行符防止日志注入
  const singleLine = trimmed.replace(/[\r\n\0]/g, '')
  // 2. 移除 query/fragment 防止 token 泄露
  const withoutQuery = singleLine.split(/[?#]/, 1)[0]
  // 3. 截断过长 URL (>512 字符)
  // 4. 规范化为 protocol://host/pathname 格式
}

// 使用
console.warn('[safeWindow] Blocked:', redactUrlForLog(url))
```

### ETL logging 副作用移除

**问题**: `etl/templates/` 模块在 import 时执行 `logging.basicConfig()`，会"抢占"应用的日志配置。

**修复**:

```python
# Before (模块顶层)
logging.basicConfig(level=logging.INFO)

# After (仅入口点)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="...")
```

### /genomes percent-encoding 路径遍历加固

**问题**: 现有 dotfile/traversal 检查未处理 `%2e%2e` 等 percent-encoding 绕过。

**修复**:

```python
from urllib.parse import unquote

# 解码后再检查
path = unquote(path)  # %2e%2e -> ..
if ".." in path or path.startswith("."):
    return False
```

**防护场景**:
- `/%2e%2e/secret.fa` → 解码后 `/../secret.fa` → 拦截
- `/%2eenv.gz` → 解码后 `/.env.gz` → 拦截

### 分块查询防 DoS (utils.py)

**问题**: `compute_conservation_map()` 对大 `core_ids` 列表可能触发 PostgreSQL 参数上限。

**修复**:

```python
def _unique_preserve_order(values: Iterable[int]) -> List[int]:
    """去重保序"""

def _iter_chunks(values: List[int], chunk_size: int) -> Iterator[List[int]]:
    """分块迭代"""

# 使用
unique_core_ids = _unique_preserve_order(core_ids)
for chunk in _iter_chunks(unique_core_ids, chunk_size=1000):
    rows = db.query(...).filter(Gene.core_id.in_(chunk))...
```

### 缓存 Singleflight 防护 (cache.py)

**问题**: 高并发下多个请求同时触发相同 key 的昂贵计算 (cache stampede)。

**修复**:

```python
# WeakValueDictionary 防止锁对象无限增长
self._singleflight_locks: weakref.WeakValueDictionary[str, threading.Lock]

def get_or_compute(self, namespace, key_params, compute_func, ttl):
    key = self._make_key(namespace, **key_params)
    cached = self.get(key)
    if cached is not None:
        return cached

    # Double-check under lock
    lock = self._get_singleflight_lock(key)
    with lock:
        cached = self.get(key)
        if cached is not None:
            return cached
        result = compute_func()  # 只执行一次
        self.set(key, result, ttl)
        return result
```

### Cytoscape tooltip 资源清理 (NetworkCard.tsx)

**问题**: tooltip DOM/handler 存到 `data()` 可能导致序列化问题和内存泄漏。

**修复**:
- 使用 `ele.scratch()` 存储不可序列化对象
- 销毁/重建/错误态时强制清理 edge mousemove 监听

### IGV 事件解绑 (GenomeBrowser/index.tsx)

**问题**: `browser.on('locuschange', handler)` 未在卸载时解绑，导致监听器残留。

**修复**:

```typescript
// 保存 handler 引用
const locusChangeHandlerRef = useRef<((...args: unknown[]) => void) | null>(null)

// 注册
locusChangeHandlerRef.current = handleLocusChange
browser.on('locuschange', handleLocusChange)

// 卸载时解绑
browser.un?.('locuschange', handler)
locusChangeHandlerRef.current = null
```

### 修改文件

| 文件 | 变更 |
|------|------|
| `frontend/web/src/utils/safeWindow.ts` | 新增 `redactUrlForLog()` |
| `etl/templates/batch_manager.py` | 移除顶层 `logging.basicConfig()` |
| `etl/templates/import_base.py` | 移除顶层 `logging.basicConfig()` |
| `frontend/backend/app/core/config.py` | 移除未使用 `quote` import |
| `frontend/backend/app/mounts/genomes.py` | 添加 `unquote()` 解码 |
| `frontend/backend/app/core/utils.py` | 添加分块查询辅助函数 |
| `frontend/backend/app/core/cache.py` | 添加 Singleflight 机制 |
| `frontend/web/src/pages/Network/components/NetworkCard.tsx` | tooltip 资源清理 |
| `frontend/web/src/types/cytoscape-ext.d.ts` | 补全 `scratch()` 类型 |
| `frontend/web/src/components/GenomeBrowser/index.tsx` | IGV 事件解绑 |

### 新增测试

| 测试文件 | 测试数 | 覆盖范围 |
|---------|--------|----------|
| `test_security_genomes_path_safety_unit.py` | +4 | percent-encoding 绕过 |
| `test_utils_chunking_unit.py` | 3 | 分块/去重函数 |
| `test_cache_singleflight_unit.py` | 1 | 10 线程并发仅执行 1 次 compute |
| `safeWindow.test.ts` | 3 | 日志脱敏 + tabnabbing |
| `GenomeBrowser.cleanup.test.tsx` | 1 | IGV locuschange 解绑 |

### 验证结果

| 检查 | 结果 |
|------|------|
| 后端 pytest | ✅ 253 passed, 241 skipped |
| 前端 vitest | ✅ 18 files, 188 passed |
| npm run build | ✅ 成功 |

---

*文档更新: 2025-12-28*

---

## Phase 9.50+: Codex 四十次审查修复

**日期**: 2025-12-29

### 修复摘要

| 类别 | 修复内容 | 优先级 |
|------|----------|--------|
| DoS 防护 | IGV ChIP-seq 轨道默认记录限制收敛（chromosome-only 也默认 50k） | P1 |
| DoS 防护 | IGV ChIP-seq 轨道区域大小限制 (10Mb) | P1 |
| 安全 | IGV overlap-track 日志字段脱敏（sanitize_for_log） | P2 |
| 测试 | 扩展 IGV 轨道 DoS 防护单测覆盖 chipseq | P2 |

### 行为变更说明

- `GET /api/v1/igv/tracks/chipseq/{species_id}.bed`：仅当同时提供 `chromosome+start+end` 且窗口 <=10Mb 时，默认不限制返回条目；否则默认限制 `50,000`（仍可用 `limit` 显式控制，最大 `100,000`）。

### 修改文件

| 文件 | 变更 |
|------|------|
| `frontend/backend/app/routers/igv_chipseq.py` | 新增 10Mb 窗口校验 + 默认 limit 策略收敛 + `mark_type` 长度限制 + 日志脱敏 |
| `frontend/backend/app/routers/igv_overlap_track.py` | 日志字段统一 `sanitize_for_log()` |
| `frontend/backend/tests/test_security_igv_track_dos_limits_unit.py` | 新增 chipseq 轨道 DoS guard 单测 |
| `CHANGELOG.md` | 记录本次安全/DoS 修复 |
| `docs/changelog/2025-12-06.md` | 更新 IGV ChIP-seq 默认限制说明 |

### 新增/更新测试

- `frontend/backend/tests/test_security_igv_track_dos_limits_unit.py`（新增 6 个 chipseq 相关用例）

### 验证结果

| 检查 | 结果 |
|------|------|
| 后端 `pytest -m unit` | ✅ 248 passed |
| 后端 `pytest` | ✅ 264 passed, 241 skipped |
| 前端 `npm run test:run` | ✅ 20 files, 195 passed |
| 前端 `npm run lint` | ✅ 成功 |
| 前端 `npm run build` | ✅ 成功 |

---

*文档更新: 2025-12-29*
