# Phase 2.3 实施检查清单

> **创建日期**: 2025-12-06
> **用途**: 逐步实施 ChIP-seq Epigenetic Marks 功能的操作指南
> **状态说明**: 本文档为 Phase 2.3 历史实施清单归档，不代表当前待办。
> **现状参考**: `docs/CURRENT_STATUS.md`，架构细节见 `docs/PHASE_2.3_CHIPSEQ_ARCHITECTURE.md`。

---

## 📋 总览

本检查清单将指导您完成 Phase 2.3 的实施，预计工期 **10 个工作日**。

**目标**: 建立通用 ChIP-seq 架构，并支持首个 mark (H3K27me3)

---

## ✅ 前置准备（Day 0）

### 环境检查

- [x] PostgreSQL 15+ 已安装并运行（历史记录）
- [x] Python 3.11+ 环境可用（历史记录）
- [x] Node.js 20+ 已安装（历史记录）
- [x] 磁盘空间充足（至少 50GB 可用）（历史记录）
- [x] 可以访问 ENCODE 数据库（历史记录）

### 数据准备

- [x] 确定目标 ENCODE 实验（建议选择 2-3 个高质量实验）（历史记录）
- [x] 下载 H3K27me3 narrowPeak/broadPeak 文件（历史记录）
- [x] 准备实验元数据 JSON 文件（参考模板）（历史记录）

**推荐的 ENCODE 实验**:
```
ENCSR000AEM - H1-hESC H3K27me3 (High quality)
ENCSR000AKP - GM12878 H3K27me3
ENCSR000AOF - HepG2 H3K27me3
```

### 代码库准备

- [x] 确保在 `human-lncrna-atlas-github` 目录（历史记录）
- [x] Git 工作区干净（无未提交更改）（历史记录）
- [x] 创建新分支：`git checkout -b feature/phase-2.3-chipseq`（历史记录）

---

## 📅 Day 1-2: 数据库设计与初始化

### 任务 1.1: 执行 SQL DDL

```bash
cd <repo-root>/frontend/backend

# 连接数据库
psql -U amax -d lncrna_production

# 执行建表脚本
\i sql/chipseq_schema.sql

# 验证表创建
\dt chipseq*
\dt epigenetic*

# 检查物化视图
\dv mv_*
```

**验证检查清单**:
- [x] `epigenetic_mark_types` 表已创建，包含 15 行预定义 marks（历史记录）
- [x] `chipseq_experiments` 表已创建（历史记录）
- [x] `chipseq_peaks` 表已创建（包含 4 个分区）（历史记录）
- [x] `gene_peak_associations` 表已创建（历史记录）
- [x] `mark_relationships` 表已创建（历史记录）
- [x] `mv_chipseq_mark_stats` 物化视图已创建（历史记录）
- [x] `mv_gene_mark_summary` 物化视图已创建（历史记录）

**验证命令**:
```sql
-- 检查 marks 预定义数据
SELECT mark_name, mark_category, display_color
FROM epigenetic_mark_types
ORDER BY display_order;

-- 应该看到 15 种 marks

-- 检查分区表
SELECT tablename FROM pg_tables
WHERE tablename LIKE 'chipseq_peaks_%';

-- 应该看到 4 个分区：_human, _chimp, _macaque, _marmoset
```

### 任务 1.2: 验证索引

```sql
-- 检查索引
SELECT indexname, tablename
FROM pg_indexes
WHERE tablename LIKE 'chipseq%'
ORDER BY tablename, indexname;
```

**验证检查清单**:
- [x] `chipseq_experiments` 有 4 个索引（历史记录）
- [x] `chipseq_peaks_human` 有 6 个索引（历史记录）
- [x] 其他 3 个物种分区也有相应索引（历史记录）

---

## 📅 Day 3-4: 后端 ORM 与 Pydantic

### 任务 2.1: 确认 ORM 模型已添加

```bash
# 检查 models.py 文件
grep -n "class EpigeneticMarkType" frontend/backend/app/models/models.py
grep -n "class ChIPSeqExperiment" frontend/backend/app/models/models.py
grep -n "class ChIPSeqPeak" frontend/backend/app/models/models.py
```

**验证检查清单**:
- [x] `EpigeneticMarkType` 模型已添加（历史记录）
- [x] `MarkRelationship` 模型已添加（历史记录）
- [x] `ChIPSeqExperiment` 模型已添加（历史记录）
- [x] `ChIPSeqPeak` 模型已添加（历史记录）
- [x] `GenePeakAssociation` 模型已添加（历史记录）
- [x] `models/__init__.py` 已导出新模型（历史记录）

### 任务 2.2: 测试 ORM 模型

```python
# 在 Python shell 中测试
python3
>>> from app.models import EpigeneticMarkType, ChIPSeqExperiment
>>> from app.core.database import SessionLocal
>>> db = SessionLocal()
>>> marks = db.query(EpigeneticMarkType).all()
>>> print(f"Found {len(marks)} marks")
>>> for m in marks[:3]:
...     print(f"{m.mark_name}: {m.mark_category}")
>>> db.close()
```

**验证检查清单**:
- [x] 能成功导入所有模型（历史记录）
- [x] 能查询到 15 个 marks（历史记录）
- [x] 能看到正确的 mark_category (repressive, activating, enhancer)（历史记录）

### 任务 2.3: 确认 Pydantic Schemas

```bash
# 检查 schemas 文件
ls -lh frontend/backend/app/schemas/chipseq.py

# 查看 schemas 内容
head -50 frontend/backend/app/schemas/chipseq.py
```

**验证检查清单**:
- [x] `MarkTypeResponse` schema 已定义（历史记录）
- [x] `ChIPSeqPeak` schema 已定义（历史记录）
- [x] `ChIPSeqResponse` schema 已定义（历史记录）
- [x] `ChIPSeqSummary` schema 已定义（历史记录）
- [x] `ChIPSeqCompareResponse` schema 已定义（历史记录）

---

## 📅 Day 5-7: 后端 API 实现

### 任务 3.1: 确认 Router 已创建

```bash
# 检查 router 文件
ls -lh frontend/backend/app/routers/chipseq.py

# 查看端点定义
grep -n "@router" frontend/backend/app/routers/chipseq.py
```

**验证检查清单**:
- [x] `chipseq.py` router 文件存在（历史记录）
- [x] 至少包含 8 个端点定义（历史记录）

### 任务 3.2: 注册 Router 到 main.py

```python
# 编辑 frontend/backend/main.py
# 添加以下代码

from app.routers import chipseq  # 新增

# 在 app 初始化后添加
app.include_router(chipseq.router, prefix="/api/v1")
```

**验证检查清单**:
- [x] `chipseq` router 已导入（历史记录）
- [x] Router 已通过 `app.include_router` 注册（历史记录）

### 任务 3.3: 启动后端测试

```bash
cd <repo-root>/frontend/backend

# 启动开发服务器
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 在另一个终端测试
curl http://localhost:8000/api/v1/features/chipseq/marks?species_id=1

# 应该返回可用 marks 列表（目前为空，因为还没导入数据）
```

**验证检查清单**:
- [x] 服务器成功启动，无报错（历史记录）
- [x] `/features/chipseq/marks` 端点可访问（历史记录）
- [x] 返回 JSON 格式数据（即使是空数组）（历史记录）
- [x] Swagger UI 可访问：http://localhost:8000/docs（历史记录）
- [x] 在 Swagger UI 中看到 `chipseq` 标签和 8 个端点（历史记录）

### 任务 3.4: 测试所有端点

```bash
# 测试端点 1: 获取可用 marks
curl "http://localhost:8000/api/v1/features/chipseq/marks?species_id=1"

# 测试端点 2: 获取基因 peaks（会返回空，因为还没数据）
curl "http://localhost:8000/api/v1/features/chipseq/genes/12345?mark_type=H3K27me3"

# 测试端点 3: 获取统计
curl "http://localhost:8000/api/v1/features/chipseq/stats"
```

**验证检查清单**:
- [x] 所有端点返回 200 状态码（历史记录）
- [x] 返回 JSON 格式正确（历史记录）
- [x] 错误处理正常（如 404, 422）（历史记录）

---

## 📅 Day 8: 数据导入

### 任务 4.1: 准备导入脚本

```bash
cd <repo-root>/frontend/backend

# 确认导入脚本存在
ls -lh scripts/import_chipseq.py

# 查看帮助
python3 scripts/import_chipseq.py --help
```

**验证检查清单**:
- [x] `import_chipseq.py` 脚本存在（历史记录）
- [x] 脚本有可执行权限（历史记录）
- [x] `--help` 显示正确的参数说明（历史记录）

### 任务 4.2: 准备实验元数据

```bash
# 创建元数据文件
cat > /tmp/h3k27me3_brain_metadata.json << 'EOF'
{
  "mark_type": "H3K27me3",
  "encode_accession": "ENCSR000AEM",
  "biosample_accession": "ENCBS000AAA",
  "tissue_type": "brain",
  "cell_type": "neuron",
  "cell_line": null,
  "treatment": null,
  "developmental_stage": "adult",
  "antibody_target": "H3K27me3",
  "antibody_source": "Abcam ab6002",
  "replicate_type": "biological",
  "total_reads": 45000000,
  "mapped_reads": 42000000,
  "mapping_rate": 93.33,
  "frac_of_reads_in_peaks": 15.2,
  "nsc": 1.05,
  "rsc": 0.95,
  "quality_score": 85.5,
  "peak_type": "broad"
}
EOF
```

**验证检查清单**:
- [x] 元数据 JSON 文件已创建（历史记录）
- [x] JSON 格式正确（可用 `jq` 验证）（历史记录）
- [x] 所有必需字段都已填写（历史记录）

### 任务 4.3: 下载 ENCODE 数据

```bash
# 下载 H3K27me3 peaks 文件（示例）
cd <repo-root>/chipseq_data
mkdir -p h3k27me3

# 下载示例数据（替换为实际 ENCODE URL）
wget -O h3k27me3/brain_peaks.narrowPeak.gz \
  https://www.encodeproject.org/files/ENCFF000XXX/@@download/ENCFF000XXX.bed.gz

# 解压
gunzip h3k27me3/brain_peaks.narrowPeak.gz
```

**验证检查清单**:
- [x] Peaks 文件已下载（历史记录）
- [x] 文件格式正确（BED/narrowPeak/broadPeak）（历史记录）
- [x] 文件大小合理（通常 5-50 MB）（历史记录）

### 任务 4.4: 执行数据导入

```bash
cd <repo-root>/frontend/backend

# 执行导入
python3 scripts/import_chipseq.py \
    --input <repo-root>/chipseq_data/h3k27me3/brain_peaks.narrowPeak \
    --mark-type H3K27me3 \
    --species human \
    --experiment-name "ENCODE_Brain_H3K27me3" \
    --metadata /tmp/h3k27me3_brain_metadata.json \
    --batch-size 10000 \
    --compute-associations

# 导入过程应该显示进度条
```

**验证检查清单**:
- [x] 导入脚本成功执行，无报错（历史记录）
- [x] 显示导入进度和统计信息（历史记录）
- [x] 导入完成后显示总导入记录数（历史记录）

### 任务 4.5: 验证导入数据

```sql
-- 检查实验记录
SELECT * FROM chipseq_experiments WHERE mark_type_id = 1;

-- 检查 peaks 数量
SELECT COUNT(*) FROM chipseq_peaks_human WHERE experiment_id = 1;

-- 检查信号分布
SELECT
    AVG(signal_value) as avg_signal,
    AVG(fold_enrichment) as avg_fold,
    MAX(fold_enrichment) as max_fold
FROM chipseq_peaks_human
WHERE experiment_id = 1;

-- 检查 gene-peak 关联
SELECT COUNT(*) FROM gene_peak_associations WHERE experiment_id = 1;
```

**验证检查清单**:
- [x] `chipseq_experiments` 表有 1 条记录（历史记录）
- [x] `chipseq_peaks_human` 表有正确数量的 peaks（历史记录）
- [x] 信号值在合理范围内（signal_value > 0, fold_enrichment > 1）（历史记录）
- [x] `gene_peak_associations` 表有关联记录（如果使用了 `--compute-associations`）（历史记录）

### 任务 4.6: 刷新物化视图

```sql
-- 刷新统计物化视图
REFRESH MATERIALIZED VIEW mv_chipseq_mark_stats;
REFRESH MATERIALIZED VIEW mv_gene_mark_summary;

-- 检查统计结果
SELECT * FROM mv_chipseq_mark_stats WHERE mark_name = 'H3K27me3';
```

**验证检查清单**:
- [x] 物化视图刷新成功（历史记录）
- [x] 统计数据正确显示（peak_count, avg_signal 等）（历史记录）

---

## 📅 Day 9-10: 前端组件开发

### 任务 5.1: 确认前端文件已生成

```bash
cd <repo-root>/frontend/web

# 检查类型定义
ls -lh src/types/chipseq.ts

# 检查配置文件
ls -lh src/config/markConfigs.ts

# 检查 API 客户端
ls -lh src/api/chipseq.ts

# 检查 Hooks
ls -lh src/hooks/useChIPSeq.ts

# 检查组件
ls -lh src/components/ChIPSeqPeaksTable/
```

**验证检查清单**:
- [x] `types/chipseq.ts` 存在（历史记录）
- [x] `config/markConfigs.ts` 存在，包含 16 种 marks（历史记录）
- [x] `api/chipseq.ts` 存在（历史记录）
- [x] `hooks/useChIPSeq.ts` 存在（历史记录）
- [x] `components/ChIPSeqPeaksTable/` 目录存在，包含 6 个组件（历史记录）

### 任务 5.2: 安装依赖（如果需要）

```bash
cd <repo-root>/frontend/web

# 检查 package.json，确认所需依赖
# 如果缺少依赖，运行：
npm install
```

**验证检查清单**:
- [x] `@tanstack/react-query` 已安装（历史记录）
- [x] `echarts` 和 `echarts-for-react` 已安装（历史记录）
- [x] `antd` 已安装（历史记录）
- [x] TypeScript 编译无错误（历史记录）

### 任务 5.3: 集成到 GeneDetail 页面

编辑 `src/pages/GeneDetail/index.tsx`：

```typescript
// 1. 导入组件
import { ChIPSeqPeaksTable } from '@/components/ChIPSeqPeaksTable'

// 2. 在 Tabs 中添加新 Tab
<Tabs defaultActiveKey="core">
  <TabPane tab={t('detail.tabs.core')} key="core">
    {/* 现有内容 */}
  </TabPane>

  <TabPane tab={t('detail.tabs.genomicFeatures')} key="genomic">
    <Tabs type="card">
      <TabPane tab={t('detail.tabs.repeatElements')} key="repeats">
        <RepeatMaskerTable geneId={geneId} />
      </TabPane>

      {/* 新增 ChIP-seq Tab */}
      <TabPane tab={t('detail.tabs.chipseqPeaks')} key="chipseq">
        <ChIPSeqPeaksTable
          geneId={geneId}
          initialMarkType="H3K27me3"
          enableComparison={true}
        />
      </TabPane>
    </Tabs>
  </TabPane>
</Tabs>
```

**验证检查清单**:
- [x] `ChIPSeqPeaksTable` 组件已导入（历史记录）
- [x] 新 Tab 已添加到 Genomic Features 下（历史记录）
- [x] TypeScript 编译无错误（历史记录）

### 任务 5.4: 添加国际化翻译

编辑 `src/i18n/locales/en/genes.json` 和 `zh-CN/genes.json`：

```json
{
  "detail": {
    "tabs": {
      "chipseqPeaks": "ChIP-seq Peaks"
    },
    "chipseq": {
      // 已在生成的文件中包含完整翻译
    }
  }
}
```

**验证检查清单**:
- [x] 英文翻译已添加（历史记录）
- [x] 中文翻译已添加（历史记录）
- [x] 所有 16 种 marks 的翻译都已包含（历史记录）

### 任务 5.5: 启动前端测试

```bash
cd <repo-root>/frontend/web

# 启动开发服务器
npm run dev -- --host 0.0.0.0

# 访问 http://localhost:5173
```

**验证检查清单**:
- [x] 前端成功启动，无编译错误（历史记录）
- [x] 能够访问 GeneDetail 页面（历史记录）
- [x] 能够看到 "ChIP-seq Peaks" Tab（历史记录）
- [x] 点击 Tab 后组件正常渲染（历史记录）

### 任务 5.6: 功能测试

在浏览器中测试：

1. **Mark 选择器测试**:
   - [x] 下拉框能打开（历史记录）
   - [x] 能看到 H3K27me3 (Repressive) 选项（历史记录）
   - [x] 选项按类别分组（Repressive / Activating / Enhancer）（历史记录）
   - [x] 能够搜索 marks（历史记录）

2. **数据加载测试**:
   - [x] 选择 H3K27me3 后能加载数据（历史记录）
   - [x] 显示 Loading 状态（历史记录）
   - [x] 数据加载完成后显示统计卡片（历史记录）
   - [x] 显示数据表格（历史记录）

3. **统计卡片测试**:
   - [x] Total Peaks 显示正确数量（历史记录）
   - [x] Avg Signal 显示合理值（历史记录）
   - [x] Avg Fold Enrichment 显示合理值（历史记录）
   - [x] Position Distribution 显示正确（历史记录）

4. **过滤器测试**:
   - [x] Q-Value 下拉框可用（历史记录）
   - [x] Fold Enrichment 滑块可用（历史记录）
   - [x] 应用过滤器后数据更新（历史记录）

5. **表格测试**:
   - [x] 表格显示 peaks 数据（历史记录）
   - [x] 列头可点击排序（历史记录）
   - [x] 分页控件可用（历史记录）
   - [x] 信号值有颜色编码（历史记录）

6. **导出测试**:
   - [x] 点击 "Export BED" 按钮（历史记录）
   - [x] 能够下载 BED 文件（历史记录）

---

## 📅 Day 11: 集成测试与优化

### 任务 6.1: E2E 测试

```bash
cd <repo-root>/frontend/web

# 运行 E2E 测试
npm run test:e2e
```

**验证检查清单**:
- [x] 所有现有测试通过（历史记录）
- [x] （可选）添加 ChIP-seq 相关的 E2E 测试（历史记录）

### 任务 6.2: 性能测试

```bash
# 测试基因查询性能
time curl "http://localhost:8000/api/v1/features/chipseq/genes/12345?mark_type=H3K27me3"

# 应该在 100ms 内返回
```

**验证检查清单**:
- [x] API 响应时间 < 100ms（历史记录）
- [x] 前端首次加载 < 3s（历史记录）
- [x] 表格分页流畅，无卡顿（历史记录）

### 任务 6.3: 文档更新

编辑 `docs/project.md`，添加 Phase 2.3 完成记录：

```markdown
### Phase 2.3: ChIP-seq Epigenetic Marks（已完成）
- ✅ 通用 ChIP-seq 架构设计
- ✅ 支持 15+ 种组蛋白修饰
- ✅ H3K27me3 数据导入和展示
- ✅ 前端通用组件 ChIPSeqPeaksTable
- ✅ 配置驱动的 mark 管理
```

**验证检查清单**:
- [x] 项目文档已更新（历史记录）
- [x] Changelog 已添加 Phase 2.3 条目（历史记录）

---

## 📅 Day 12: 提交与部署

### 任务 7.1: 代码审查

```bash
# 查看所有修改
git status

# 查看 diff
git diff
```

**验证检查清单**:
- [x] 所有新文件已添加到 Git（历史记录）
- [x] 无调试代码残留（历史记录）
- [x] 无敏感信息（如密码、token）（历史记录）

### 任务 7.2: 提交代码

```bash
# 添加文件
git add frontend/backend/sql/chipseq_schema.sql
git add frontend/backend/app/models/models.py
git add frontend/backend/app/schemas/chipseq.py
git add frontend/backend/app/routers/chipseq.py
git add frontend/backend/scripts/import_chipseq.py
git add frontend/web/src/types/chipseq.ts
git add frontend/web/src/config/markConfigs.ts
git add frontend/web/src/api/chipseq.ts
git add frontend/web/src/hooks/useChIPSeq.ts
git add frontend/web/src/components/ChIPSeqPeaksTable/
git add frontend/web/src/i18n/locales/*/genes.json
git add docs/PHASE_2.3_CHIPSEQ_ARCHITECTURE.md
git add docs/PHASE_2.3_IMPLEMENTATION_CHECKLIST.md

# 提交
git commit -m "feat: Phase 2.3 - ChIP-seq Epigenetic Marks 通用架构

- 添加通用 ChIP-seq 数据库 Schema（支持 15+ marks）
- 实现后端 API（8 个端点）
- 实现前端通用组件 ChIPSeqPeaksTable
- 支持 H3K27me3 数据导入和可视化
- 配置驱动的 mark 管理，扩展性强

🤖 Generated with Claude Code (https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# 推送到远程
git push origin feature/phase-2.3-chipseq
```

**验证检查清单**:
- [x] Commit message 清晰描述了改动（历史记录）
- [x] 代码已推送到远程仓库（历史记录）

### 任务 7.3: 创建 Pull Request

在 GitHub 上创建 Pull Request：

- Title: `feat: Phase 2.3 - ChIP-seq Epigenetic Marks 通用架构`
- Description: 引用 `docs/PHASE_2.3_CHIPSEQ_ARCHITECTURE.md`
- Reviewers: （如果有）

**验证检查清单**:
- [x] PR 已创建（历史记录）
- [x] CI/CD 测试通过（历史记录）
- [x] 文档链接正确（历史记录）

---

## 🎉 完成标准

所有以下条件满足时，Phase 2.3 视为完成：

- [x] 数据库 Schema 已创建并验证
- [x] 后端 8 个 API 端点可用且测试通过
- [x] 至少导入 1 个 H3K27me3 实验的数据
- [x] 前端 ChIPSeqPeaksTable 组件可用
- [x] 能够在 GeneDetail 页面查看 ChIP-seq peaks
- [x] Mark 选择器工作正常
- [x] 统计卡片、过滤器、表格功能正常
- [x] BED 文件导出功能可用
- [x] 国际化（中英文）完整
- [x] 代码已提交并推送

---

## 🚀 下一步：Phase 2.4

完成 Phase 2.3 后，可以开始 Phase 2.4：

- 导入 3 个额外的 marks（H3K4me1, H3K4me3, H3K27ac）
- 验证通用架构的扩展性
- 添加多 marks 对比功能的基础

详见：`docs/PHASE_2.3_CHIPSEQ_ARCHITECTURE.md` 的 Phase 2.4 部分。

---

## 📞 遇到问题？

### 常见问题

**Q: 数据库建表失败**
- 检查 PostgreSQL 版本是否 >= 15
- 确认用户有创建表权限
- 查看错误日志

**Q: 导入脚本报错**
- 确认 peaks 文件格式正确（BED/narrowPeak/broadPeak）
- 检查元数据 JSON 格式
- 确认数据库连接正常

**Q: 前端组件不显示**
- 检查浏览器控制台错误
- 确认后端 API 可访问
- 验证 CORS 设置

**Q: API 返回空数据**
- 确认已导入数据
- 刷新物化视图
- 检查 SQL 查询日志

---

**文档版本**: v1.0
**最后更新**: 2025-12-06
