# IGV.js 基因组浏览器集成实施计划

> 创建日期: 2025-12-02
> 状态: 规划中

> 更新（2026-01-24）：本文档为 IGV 集成计划快照（规划中），不代表当前待办清单；现状以 `docs/CURRENT_STATUS.md` 为准。

---

## 1. 项目概述

### 1.1 目标

在 Human LncRNA Atlas 平台中集成 IGV.js 基因组浏览器，实现：
- 可视化展示 LncRNA-Target 调控关系在基因组上的位置
- 支持 4 个灵长类物种的基因组浏览
- 与现有调控关系数据联动

### 1.2 预期成果

| 功能 | 描述 |
|------|------|
| 基因组浏览 | 浏览参考基因组，支持缩放、导航 |
| 结合位点轨道 | 展示 LncRNA-Target 结合位点 (BED 格式) |
| 调控弧线轨道 | 展示 LncRNA 到 Target 的调控关系弧线 (BEDPE 格式) |
| 基因搜索 | 按基因名/ID 定位到基因组位置 |
| 物种切换 | 支持 Human/Chimp/Macaque/Marmoset 切换 |
| 数据联动 | 从 Regulations/GeneDetail 页面跳转 |

### 1.3 参考基因组版本

| 物种 | 基因组版本 | UCSC ID | 数据来源 |
|------|-----------|---------|----------|
| Human | GRCh37 | **hg19** | IGV.org 公共服务 |
| Chimpanzee | Pan_tro_2.1.4 | **panTro5** | UCSC 自托管 |
| Macaque | Mmul_10 | **rheMac10** | UCSC 自托管 |
| Marmoset | Callithrix_jacchus-3.2 | **calJac3** | UCSC 自托管 |

---

## 2. 技术选型

### 2.1 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| IGV.js | ^3.x | 基因组浏览器核心 |
| React | 19.x | UI 框架 (现有) |
| TypeScript | 5.x | 类型系统 (现有) |
| Zustand | 5.x | 浏览器状态管理 |
| TanStack Query | 5.x | 数据获取 (现有) |

### 2.2 后端

| 技术 | 用途 |
|------|------|
| FastAPI | API 框架 (现有) |
| 流式响应 | 大文件传输 |
| Gzip 压缩 | BED 文件压缩 |
| Tabix | BED 文件索引 (可选) |

### 2.3 数据格式

| 格式 | 用途 | 说明 |
|------|------|------|
| BED6 | 结合位点轨道 | chr, start, end, name, score, strand |
| BEDPE | 调控弧线轨道 | 展示 lncRNA-target 连接 |
| JSON | 区域查询 API | 动态数据加载 |

---

## 3. 实施阶段

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: MVP (Human Only)                         预计: 5天   │
│  ├── 前端 IGV.js 组件封装                                      │
│  ├── 后端 BED 导出 API                                         │
│  └── Human (hg19) 基础浏览功能                                 │
├─────────────────────────────────────────────────────────────────┤
│  Phase 2: 多物种支持                               预计: 5天   │
│  ├── 下载/托管其他物种参考基因组                               │
│  ├── 物种切换功能                                              │
│  └── 同源基因导航                                              │
├─────────────────────────────────────────────────────────────────┤
│  Phase 3: 高级功能                                 预计: 4天   │
│  ├── BEDPE 弧线轨道                                            │
│  ├── 页面联动 (GeneDetail/Regulations)                         │
│  └── 导出功能 (SVG/PNG)                                        │
├─────────────────────────────────────────────────────────────────┤
│  Phase 4: 优化与测试                               预计: 3天   │
│  ├── 性能优化 (索引/缓存)                                      │
│  ├── E2E 测试                                                  │
│  └── 文档完善                                                  │
└─────────────────────────────────────────────────────────────────┘
                                                     总计: ~17天
```

---

## 4. Phase 1: MVP (Human Only)

### 4.1 目标

实现最小可用版本：能够在 Human (hg19) 基因组上浏览调控位点。

### 4.2 任务清单

#### 4.2.1 前端任务

- [ ] **创建 TypeScript 类型声明**
  - 文件: `frontend/web/src/types/igv.d.ts`
  - 内容: IGV.js 核心 API 类型定义

- [ ] **封装 GenomeBrowser 组件**
  - 文件: `frontend/web/src/components/GenomeBrowser/index.tsx`
  - 功能: IGV.js 初始化、生命周期管理、Ref 暴露

- [ ] **创建基因组浏览器页面**
  - 文件: `frontend/web/src/pages/GenomeBrowser/index.tsx`
  - 路由: `/genome-browser`
  - 功能: 工具栏、搜索框、浏览器区域

- [ ] **添加国际化文案**
  - 文件: `frontend/web/src/i18n/locales/*/genomeBrowser.json`
  - 内容: 中英文界面文案

- [ ] **更新路由配置**
  - 文件: `frontend/web/src/App.tsx`
  - 内容: 添加 `/genome-browser` 路由 (懒加载)

- [ ] **更新导航菜单**
  - 文件: `frontend/web/src/components/Layout/index.tsx`
  - 内容: 添加 "Genome Browser" 菜单项

#### 4.2.2 后端任务

- [ ] **创建 IGV 路由模块**
  - 文件: `frontend/backend/app/routers/igv.py`
  - 端点:
    - `GET /api/v1/igv/config/{species_id}` - 获取浏览器配置
    - `GET /api/v1/igv/tracks/regulations/{species_id}.bed` - BED 格式轨道

- [ ] **创建数据导出服务**
  - 文件: `frontend/backend/app/services/igv_export.py`
  - 功能: regulations 表 → BED 格式转换

- [ ] **注册路由**
  - 文件: `frontend/backend/main.py`
  - 内容: 引入 igv router

- [ ] **添加数据库索引**
  ```sql
  CREATE INDEX idx_regulations_igv ON regulations (
      species_id, best_peak_chr, dna_start, dna_end
  ) WHERE best_peak_chr IS NOT NULL;
  ```

### 4.3 API 设计

#### GET /api/v1/igv/config/{species_id}

**响应示例:**
```json
{
  "reference": {
    "id": "hg19",
    "name": "Human (GRCh37/hg19)",
    "fastaURL": "https://igv.org/genomes/data/hg19/hg19.fa",
    "indexURL": "https://igv.org/genomes/data/hg19/hg19.fa.fai",
    "cytobandURL": "https://igv.org/genomes/data/hg19/cytoBandIdeo.txt"
  },
  "locus": "chr1:1-1000000",
  "tracks": [
    {
      "name": "LncRNA-Target Binding Sites",
      "type": "annotation",
      "format": "bed",
      "url": "/api/v1/igv/tracks/regulations/1.bed",
      "color": "rgb(0, 128, 255)",
      "height": 100
    }
  ]
}
```

#### GET /api/v1/igv/tracks/regulations/{species_id}.bed

**响应格式 (BED6):**
```
chr1    155186114    155186153    HOTAIR->TP53    85    +
chr1    155200000    155200100    MALAT1->BRCA1   92    -
```

### 4.4 组件结构

```
frontend/web/src/
├── components/
│   └── GenomeBrowser/
│       ├── index.tsx           # 核心组件
│       ├── GenomeBrowserToolbar.tsx  # 工具栏
│       └── styles.module.css   # 样式
├── pages/
│   └── GenomeBrowser/
│       ├── index.tsx           # 页面
│       └── hooks/
│           └── useGenomeBrowser.ts  # 状态管理
├── api/
│   └── genome.ts               # API 客户端
└── types/
    └── igv.d.ts                # 类型声明
```

### 4.5 验收标准

- [ ] 访问 `/genome-browser` 显示 IGV.js 浏览器
- [ ] 能够加载 Human (hg19) 参考基因组
- [ ] 显示调控位点 BED 轨道
- [ ] 支持基因名搜索定位
- [ ] 支持缩放、拖拽导航

---

## 5. Phase 2: 多物种支持

### 5.1 目标

扩展支持 Chimpanzee、Macaque、Marmoset 三个物种。

### 5.2 任务清单

#### 5.2.1 基因组数据准备

- [ ] **下载参考基因组**
  ```bash
  # Chimpanzee (panTro5)
  wget https://hgdownload.soe.ucsc.edu/goldenPath/panTro5/bigZips/panTro5.fa.gz

  # Macaque (rheMac10)
  wget https://hgdownload.soe.ucsc.edu/goldenPath/rheMac10/bigZips/rheMac10.fa.gz

  # Marmoset (calJac3)
  wget https://hgdownload.soe.ucsc.edu/goldenPath/calJac3/bigZips/calJac3.fa.gz
  ```

- [ ] **生成索引文件**
  ```bash
  samtools faidx panTro5.fa
  samtools faidx rheMac10.fa
  samtools faidx calJac3.fa
  ```

- [ ] **配置静态文件服务**
  - 目录: `/data/genomes/`
  - Nginx/FastAPI 静态文件路由

#### 5.2.2 前端任务

- [ ] **物种选择器组件**
  - 文件: `GenomeBrowser/SpeciesSelector.tsx`
  - 功能: 下拉菜单切换物种

- [ ] **物种切换逻辑**
  - 切换时重新加载 IGV 配置
  - 保留当前基因名，尝试定位同源基因

#### 5.2.3 后端任务

- [ ] **同源基因导航 API**
  ```
  GET /api/v1/igv/ortholog-locus
  参数: from_species, to_species, gene_id
  响应: { locus: "chr5:12345-67890", gene_name: "TP53" }
  ```

- [ ] **静态文件路由配置**
  ```python
  from fastapi.staticfiles import StaticFiles
  app.mount("/genomes", StaticFiles(directory="/data/genomes"), name="genomes")
  ```

### 5.3 存储需求

| 物种 | FASTA (压缩) | FASTA (解压) | Index | 合计 |
|------|-------------|-------------|-------|------|
| panTro5 | ~1.0 GB | ~3.0 GB | ~50 MB | ~4 GB |
| rheMac10 | ~0.9 GB | ~2.9 GB | ~50 MB | ~4 GB |
| calJac3 | ~0.9 GB | ~2.8 GB | ~50 MB | ~4 GB |
| **总计** | | | | **~12 GB** |

### 5.4 验收标准

- [ ] 物种选择器正常工作
- [ ] 4 个物种都能正确加载基因组
- [ ] 切换物种时自动定位到同源基因
- [ ] 各物种的调控位点轨道正确显示

---

## 6. Phase 3: 高级功能

### 6.1 目标

实现调控弧线轨道、页面联动、导出功能。

### 6.2 任务清单

#### 6.2.1 BEDPE 弧线轨道

- [ ] **后端: BEDPE 导出 API**
  ```
  GET /api/v1/igv/tracks/interactions/{species_id}.bedpe
  ```

  **格式:**
  ```
  chr1  1000  2000  chr5  50000  51000  HOTAIR->TP53  85  +  -
  ```

- [ ] **前端: 添加弧线轨道配置**
  ```javascript
  {
    name: "Regulatory Interactions",
    type: "interaction",
    format: "bedpe",
    arcType: "proportional",
    color: "rgb(255, 100, 100)",
    alpha: 0.15
  }
  ```

#### 6.2.2 页面联动

- [ ] **GeneDetail 页面添加入口**
  ```tsx
  <Button onClick={() => navigate(`/genome-browser?gene=${gene.gene_ensembl_id}`)}>
    View in Genome Browser
  </Button>
  ```

- [ ] **Regulations 页面添加入口**
  - 单行: "查看位点"
  - 多选: "对比选中项"

- [ ] **URL 参数支持**
  ```
  /genome-browser?gene=ENSG00000xxx
  /genome-browser?chr=chr1&start=12345&end=67890
  /genome-browser?regulation_id=12345
  /genome-browser?ids=1,2,3 (多个高亮)
  ```

#### 6.2.3 导出功能

- [ ] **SVG 导出**
  ```typescript
  const svg = browserRef.current?.toSVG();
  downloadFile(svg, 'genome-view.svg', 'image/svg+xml');
  ```

- [ ] **PNG 导出**
  - 使用 html2canvas 或 canvg 转换

- [ ] **当前区域数据导出 (CSV)**

### 6.3 验收标准

- [ ] 调控弧线正确显示 lncRNA-Target 连接
- [ ] 从 GeneDetail 点击能正确跳转并定位
- [ ] 从 Regulations 能跳转并高亮
- [ ] SVG/PNG 导出功能正常

---

## 7. Phase 4: 优化与测试

### 7.1 目标

性能优化、测试覆盖、文档完善。

### 7.2 任务清单

#### 7.2.1 性能优化

- [ ] **预生成 BED 文件**
  - 定时任务生成静态文件
  - 使用 Tabix 建立索引

- [ ] **API 缓存**
  ```python
  @cache.cached(ttl=3600)
  def get_regulations_bed(species_id: int):
      ...
  ```

- [ ] **前端懒加载**
  - 代码分割 IGV.js chunk
  - 路由级懒加载

- [ ] **大区域数据限制**
  - visibilityWindow 配置
  - 超大区域显示简化视图

#### 7.2.2 测试

- [ ] **后端 API 测试**
  - 文件: `frontend/backend/tests/test_igv_api.py`
  - 覆盖: 配置获取、BED 导出、区域查询

- [ ] **前端 E2E 测试**
  - 文件: `frontend/web/e2e/genome-browser.spec.ts`
  - 覆盖: 页面加载、搜索、物种切换

#### 7.2.3 文档

- [ ] **API 文档**
  - 在 API_GUIDE.md 中添加 IGV 相关端点

- [ ] **用户指南**
  - 基因组浏览器使用说明

### 7.3 验收标准

- [ ] 首次加载时间 < 3 秒
- [ ] 大区域 (>10MB) 浏览流畅
- [ ] 测试覆盖率 > 80%
- [ ] 文档完整

---

## 8. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 非人类基因组下载失败 | 中 | 高 | 提前验证 UCSC 链接，准备备用源 |
| IGV.js 与 React 19 不兼容 | 低 | 高 | Phase 1 开始前进行原型验证 |
| 存储空间不足 | 中 | 中 | 确认服务器有 20GB+ 可用空间 |
| BED 文件过大影响加载 | 高 | 中 | 使用 Tabix 索引，按区域加载 |
| 移动端体验差 | 高 | 低 | 明确标注桌面端专用 |

---

## 9. 里程碑

| 里程碑 | 预计完成 | 交付物 |
|--------|----------|--------|
| M1: Phase 1 完成 | +5 天 | Human 基因组浏览器 MVP |
| M2: Phase 2 完成 | +10 天 | 4 物种完整支持 |
| M3: Phase 3 完成 | +14 天 | 弧线轨道 + 页面联动 |
| M4: Phase 4 完成 | +17 天 | 生产就绪版本 |

---

## 10. 附录

### 10.1 IGV.js 配置参考

```javascript
const igvConfig = {
  genome: "hg19",
  locus: "chr1:1-1000000",
  tracks: [
    {
      name: "Binding Sites",
      type: "annotation",
      format: "bed",
      url: "/api/v1/igv/tracks/regulations/1.bed",
      indexed: false,
      displayMode: "EXPANDED",
      color: "rgb(0, 128, 255)",
      height: 100,
      visibilityWindow: 5000000
    },
    {
      name: "Interactions",
      type: "interaction",
      format: "bedpe",
      url: "/api/v1/igv/tracks/interactions/1.bedpe",
      arcType: "proportional",
      color: "rgb(255, 100, 100)",
      alpha: 0.15,
      height: 150
    }
  ]
};
```

### 10.2 BED6 格式规范

```
# 字段: chrom, chromStart, chromEnd, name, score, strand
# 坐标系: 0-based, half-open [start, end)
chr1    155186114    155186153    HOTAIR->TP53    85    +
```

### 10.3 BEDPE 格式规范

```
# 字段: chrom1, start1, end1, chrom2, start2, end2, name, score, strand1, strand2
# 用于展示两个基因组区域之间的关联
chr1    1000    2000    chr5    50000    51000    HOTAIR->TP53    85    +    -
```

---

## 更新日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2025-12-02 | v1.0 | 初始版本，创建实施计划 |
