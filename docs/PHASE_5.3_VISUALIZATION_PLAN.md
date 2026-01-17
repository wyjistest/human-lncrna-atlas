# Phase 5.3：高级可视化增强规划

**项目**: Human LncRNA Atlas
**阶段**: Phase 5.3 (Advanced Visualization)
**前置条件**: Phase 5.2 完成（全站性能优化）
**预计工作量**: 2-3 天
**优先级**: P1（高优先级，专业性提升）

---

## 项目背景

### 当前可视化能力

经过 Phase 1-5 的建设，项目已具备以下可视化功能：

| 可视化类型 | 工具 | 页面 | 成熟度 |
|----------|------|------|--------|
| **网络图** | Cytoscape.js | Network | ⭐⭐⭐⭐ |
| **基因组浏览** | IGV.js | GenomeBrowser | ⭐⭐⭐⭐⭐ |
| **统计图表** | ECharts | Stats, ChIPSeq | ⭐⭐⭐⭐ |
| **数据表格** | Ant Design Table | 所有列表页 | ⭐⭐⭐⭐⭐ |
| **保守性热力图** | ECharts | Conservation | ⭐⭐⭐⭐ |

### 提升空间

**缺失的高级可视化**:
1. ❌ 流向图（Sankey）- 调控关系流向
2. ❌ 关系图（Chord）- 物种间关系
3. ❌ 3D 可视化 - 空间网络拓扑
4. ❌ 监控仪表盘 - 系统性能实时监控
5. ❌ 交互式多维分析 - 数据钻取

---

## 可视化方案详细规划

### 🌊 方案 1：Sankey 流向图（调控路径可视化）

**展示内容**: lncRNA → 靶基因 → 疾病 的完整调控流向

#### 技术实现

**前端技术栈**:
- ECharts Sankey 图
- React 18 + TypeScript
- 动态数据加载

**后端数据 API**:
```python
# app/routers/visualization.py
@router.get("/sankey-data")
def get_sankey_flow_data(
    species_id: int = 1,
    min_ba: float = 50,
    top_lncrnas: int = 20,
    db: Session = Depends(get_db)
):
    """
    获取 Sankey 图数据：lncRNA → 靶基因 → 疾病

    返回格式：
    {
      "nodes": [
        {"name": "lncRNA_1", "category": "lncrna"},
        {"name": "Gene_1", "category": "gene"},
        {"name": "Disease_1", "category": "disease"}
      ],
      "links": [
        {"source": "lncRNA_1", "target": "Gene_1", "value": 120},
        {"source": "Gene_1", "target": "Disease_1", "value": 80}
      ]
    }
    """
```

**前端组件**:
```typescript
// src/components/SankeyFlow/index.tsx
import * as echarts from 'echarts'

const option = {
  series: {
    type: 'sankey',
    data: nodes,
    links: links,
    emphasis: {
      focus: 'adjacency'
    },
    lineStyle: {
      color: 'gradient',
      curveness: 0.5
    }
  }
}
```

**交互功能**:
- 点击节点：高亮关联路径
- 悬停：显示详细信息（调控数量、BA 值）
- 过滤：按 BA 阈值、物种、疾病类别
- 导出：PNG/SVG 高清图

**新建页面**: `/sankey-flow`

**工作量**: 6-8 小时

---

### 🎵 方案 2：Chord 关系图（物种间保守性）

**展示内容**: 物种间共享 lncRNA 的数量和关系强度

#### 技术实现

**前端技术栈**:
- ECharts Chord 图
- 自定义颜色方案（物种主题色）
- 动态数据过滤

**后端数据 API**:
```python
@router.get("/chord-conservation")
def get_chord_data(
    min_shared_lncrnas: int = 10,
    db: Session = Depends(get_db)
):
    """
    获取物种间保守性 Chord 图数据

    返回：物种对之间的共享 lncRNA 数量
    {
      "species": ["Human", "Chimp", "Macaque", "Marmoset"],
      "matrix": [
        [0, 1523, 876, 234],      # Human 与其他物种
        [1523, 0, 1102, 345],     # Chimp 与其他物种
        [876, 1102, 0, 289],      # Macaque 与其他物种
        [234, 345, 289, 0]        # Marmoset 与其他物种
      ]
    }
    """
```

**SQL 查询**:
```sql
-- 计算物种对间共享的 lncRNA
SELECT
    s1.species_id as species1,
    s2.species_id as species2,
    COUNT(DISTINCT cg1.core_id) as shared_lncrnas
FROM core_genes cg1
JOIN genes g1 ON cg1.core_id = g1.core_id
JOIN genes g2 ON cg1.core_id = g2.core_id
JOIN species s1 ON g1.species_id = s1.species_id
JOIN species s2 ON g2.species_id = s2.species_id
WHERE cg1.gene_type = 'lncRNA'
  AND g1.species_id < g2.species_id  -- 避免重复
GROUP BY s1.species_id, s2.species_id;
```

**前端组件**:
```typescript
const option = {
  series: {
    type: 'chord',
    data: species.map((name, idx) => ({
      name,
      itemStyle: { color: speciesColors[idx] }
    })),
    links: links,
    emphasis: {
      itemStyle: {
        borderColor: '#333',
        borderWidth: 2
      }
    }
  }
}
```

**交互功能**:
- 悬停：显示共享 lncRNA 数量
- 点击：展开共享 lncRNA 列表
- 过滤：按共享数量阈值
- 动画：自动旋转展示

**新建页面**: `/conservation-chord`

**工作量**: 4-6 小时

---

### 🌐 方案 3：3D 网络图（基因调控网络拓扑）

**展示内容**: 基因调控网络的 3D 空间布局，展示复杂的多层调控关系

#### 技术实现

**前端技术栈**:
- **选项 A**: react-force-graph-3d (推荐)
  - 基于 Three.js
  - 力导向布局
  - WebGL 加速

- **选项 B**: Plotly.js 3D scatter
  - 3D 散点图
  - 交互式旋转
  - 数据点连线

**后端数据 API**:
```python
@router.get("/network-3d")
def get_3d_network_data(
    lncrna_id: int,
    max_targets: int = 50,
    db: Session = Depends(get_db)
):
    """
    获取 3D 网络图数据

    返回：
    {
      "nodes": [
        {"id": "lnc_1", "type": "lncrna", "x": 0, "y": 0, "z": 0},
        {"id": "gene_1", "type": "target", "x": 10, "y": 5, "z": 3}
      ],
      "links": [
        {"source": "lnc_1", "target": "gene_1", "value": 120}
      ]
    }
    """
```

**3D 布局算法**:
```typescript
// 力导向布局（Force-Directed）
const forceGraph = ForceGraph3D()
  .nodeLabel('name')
  .nodeColor(node => nodeColors[node.type])
  .nodeVal(node => node.regulation_count)
  .linkWidth(link => link.value / 50)
  .linkColor(() => 'rgba(255,255,255,0.3)')
  .onNodeClick(node => showDetails(node))
```

**交互功能**:
- 🖱️ 拖拽旋转
- 🔍 缩放平移
- 🎯 点击节点：高亮连接
- 🎨 颜色编码：节点类型、BA 强度
- 📊 侧边栏：显示选中节点详情

**新建页面**: `/network-3d`

**依赖安装**:
```bash
npm install react-force-graph-3d three
npm install @types/three --save-dev
```

**工作量**: 8-10 小时

---

### 📈 方案 4：性能监控仪表盘（管理员工具）

**展示内容**: 系统性能实时监控和数据质量指标

#### 功能模块

**模块 1：API 性能监控**

**指标**:
```typescript
interface PerformanceMetrics {
  endpoint: string
  avg_response_time: number  // 平均响应时间
  p95_response_time: number  // 95 分位数
  requests_per_minute: number
  error_rate: number
  cache_hit_rate: number
}
```

**可视化**:
- 响应时间趋势图（折线图）
- API 调用分布（饼图）
- 缓存命中率（仪表盘）

**技术**: ECharts + WebSocket 实时更新

---

**模块 2：Redis 缓存监控**

**指标**:
```typescript
interface CacheMetrics {
  total_keys: number
  memory_used: string  // "125 MB"
  hit_rate: number  // 85.3%
  evicted_keys: number
  expired_keys: number
  connections: number
}
```

**后端 API**:
```python
@router.get("/admin/redis-stats")
def get_redis_stats():
    """
    获取 Redis 统计信息
    """
    info = redis_client.info()
    return {
        "total_keys": redis_client.dbsize(),
        "memory_used": info['used_memory_human'],
        "hit_rate": calculate_hit_rate(info),
        "evicted_keys": info['evicted_keys'],
        ...
    }
```

**可视化**:
- 内存使用趋势图
- 缓存键分布（树状图）
- 命中率实时显示（大数字卡片）

---

**模块 3：数据质量仪表盘**

**指标**:
```typescript
interface DataQualityMetrics {
  total_regulations: number
  sequences_coverage: number  // 99.975%
  empty_sequences: number  // 203
  species_distribution: SpeciesStats[]
  ba_distribution: BADistribution
  data_freshness: Date  // 最后更新时间
}
```

**可视化**:
- 数据完整性卡片（KPI 卡片）
- 物种分布饼图
- BA 分布箱线图
- 数据时效性日历热力图

---

**模块 4：用户行为分析**（可选）

**指标**:
- 页面访问量（PV/UV）
- 最热门查询（Top 10）
- 用户停留时间
- 跳出率

**可视化**:
- 漏斗图（用户旅程）
- 热力图（页面点击）
- 时间轴（用户活动）

---

#### 技术实现

**前端组件库**:
```bash
# 仪表盘组件
npm install @ant-design/pro-components
npm install @ant-design/charts

# 实时数据
npm install socket.io-client
```

**页面路由**: `/admin/dashboard`

**权限控制**: 仅管理员可访问

**工作量**: 6-8 小时

---

## 可视化组件库扩展

### 通用组件开发

#### 组件 1：DataFlowSankey

**路径**: `src/components/DataFlowSankey/`

**功能**:
- 通用 Sankey 图组件
- 支持自定义节点/边样式
- 数据格式适配器

**API**:
```typescript
<DataFlowSankey
  data={{nodes, links}}
  onNodeClick={(node) => {}}
  colorScheme="default"
  height={600}
/>
```

---

#### 组件 2：ConservationChord

**路径**: `src/components/ConservationChord/`

**功能**:
- 物种间关系 Chord 图
- 自定义物种颜色
- 交互式数据钻取

**API**:
```typescript
<ConservationChord
  species={['Human', 'Chimp', 'Macaque', 'Marmoset']}
  matrix={[[0, 1523, ...], ...]}
  onSpeciesPairClick={(pair) => {}}
/>
```

---

#### 组件 3：Network3DViewer

**路径**: `src/components/Network3DViewer/`

**功能**:
- 3D 力导向网络图
- 节点分类着色
- 连线强度可视化

**API**:
```typescript
<Network3DViewer
  graphData={{nodes, links}}
  nodeColor={node => nodeColorMap[node.type]}
  linkWidth={link => link.ba / 50}
  onNodeClick={(node) => showDetails(node)}
/>
```

---

#### 组件 4：PerformanceDashboard

**路径**: `src/components/PerformanceDashboard/`

**功能**:
- 性能指标卡片
- 实时数据更新
- 告警提示

**API**:
```typescript
<PerformanceDashboard
  metrics={liveMetrics}
  refreshInterval={5000}  // 5秒刷新
  alertThresholds={{
    response_time: 1000,
    error_rate: 0.01
  }}
/>
```

---

## 新建页面规划

### 页面 1: Sankey Flow（Sankey 流向图）

**路由**: `/visualization/sankey-flow`

**布局**:
```
┌─────────────────────────────────────────────┐
│  [物种选择] [BA阈值] [Top N] [导出]         │
├─────────────────────────────────────────────┤
│                                             │
│           Sankey 流向图                      │
│     (lncRNA → 靶基因 → 疾病)                 │
│                                             │
├─────────────────────────────────────────────┤
│  选中节点详情：                               │
│  - 节点名称                                  │
│  - 连接数量                                  │
│  - 相关数据表格                              │
└─────────────────────────────────────────────┘
```

**数据流**:
1. 用户选择物种 + BA 阈值
2. 调用 `/visualization/sankey-data` API
3. ECharts 渲染 Sankey 图
4. 交互式探索（点击、悬停）

---

### 页面 2: Conservation Chord（保守性关系图）

**路由**: `/visualization/conservation-chord`

**布局**:
```
┌─────────────────────────────────────────────┐
│  [最小共享数] [基因类型] [导出]              │
├─────────────────────────────────────────────┤
│                                             │
│            Chord 关系图                      │
│      (物种间 lncRNA 共享关系)                │
│                                             │
├─────────────────────────────────────────────┤
│  物种对详情：                                │
│  - Human ↔ Chimp: 1,523 shared lncRNAs     │
│  - 共享 lncRNA 列表                         │
└─────────────────────────────────────────────┘
```

**技术挑战**:
- 对称矩阵数据处理
- 和弦粗细映射（共享数量）
- 颜色渐变（物种特征色）

---

### 页面 3: 3D Network（3D 网络拓扑）

**路由**: `/visualization/network-3d`

**布局**:
```
┌─────────────────────────────────────────────┐
│  [中心 lncRNA] [最大层级] [布局算法] [重置]  │
├───────────────────┬─────────────────────────┤
│                   │  选中节点详情：           │
│                   │  - 基因名                │
│   3D 网络图        │  - 调控数量              │
│   (可旋转缩放)     │  - BA 统计               │
│                   │  - 疾病关联              │
│                   │  [查看详情] [添加到收藏]  │
└───────────────────┴─────────────────────────┘
```

**布局算法**:
- Force-Directed（力导向）
- Hierarchical（层级布局）
- Circular（环形布局）

**性能优化**:
- WebGL 渲染（Three.js）
- LOD（Level of Detail）- 远处节点简化
- 节点数量限制（<500 个）

---

### 页面 4: Admin Dashboard（管理员仪表盘）

**路由**: `/admin/performance-dashboard`

**布局**:
```
┌───────────────────────────────────────────────────┐
│  性能概览                                          │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐             │
│  │ API  │ │缓存  │ │数据库│ │用户  │             │
│  │响应  │ │命中率│ │连接数│ │在线  │             │
│  │ 18ms │ │ 87% │ │  5   │ │ 12  │             │
│  └──────┘ └──────┘ └──────┘ └──────┘             │
├───────────────────────────────────────────────────┤
│  API 响应时间趋势 (折线图，最近 1 小时)            │
├─────────────────────┬─────────────────────────────┤
│  缓存命中率         │  数据库查询分布              │
│  (仪表盘)          │  (饼图)                      │
├─────────────────────┴─────────────────────────────┤
│  慢查询日志 (最近 10 条)                           │
│  - GET /regulations - 2.5s                        │
│  - GET /genes - 1.8s                              │
└───────────────────────────────────────────────────┘
```

**实时数据**:
```typescript
// 使用 WebSocket 或轮询
const { data: metrics } = useQuery({
  queryKey: ['performance-metrics'],
  queryFn: () => adminApi.getMetrics(),
  refetchInterval: 5000,  // 5秒刷新
})
```

**工作量**: 8-10 小时

---

## 技术实现细节

### ECharts 配置优化

#### Sankey 图配置

```javascript
const sankeyOption = {
  title: {
    text: 'lncRNA 调控流向图'
  },
  tooltip: {
    trigger: 'item',
    formatter: (params) => {
      if (params.dataType === 'node') {
        return `${params.name}<br/>连接数: ${params.value}`
      } else {
        return `${params.source} → ${params.target}<br/>调控数: ${params.value}`
      }
    }
  },
  series: {
    type: 'sankey',
    layout: 'none',
    emphasis: {
      focus: 'adjacency'
    },
    data: nodes,
    links: links,
    lineStyle: {
      color: 'gradient',
      curveness: 0.5,
      opacity: 0.5
    },
    label: {
      position: 'right'
    }
  }
}
```

#### Chord 图配置

```javascript
const chordOption = {
  series: {
    type: 'chord',
    radius: '75%',
    center: ['50%', '50%'],
    ribbonType: 'line',
    blendMode: 'lighter',
    data: species.map((name, i) => ({
      name,
      itemStyle: {
        color: speciesColors[i],
        borderColor: '#fff',
        borderWidth: 2
      }
    })),
    links: matrix.flatMap((row, i) =>
      row.map((value, j) =>
        i < j ? { source: i, target: j, value } : null
      ).filter(Boolean)
    )
  }
}
```

---

### React Force Graph 3D 配置

```typescript
import ForceGraph3D from 'react-force-graph-3d'

<ForceGraph3D
  graphData={data}

  // 节点配置
  nodeLabel="name"
  nodeColor={node => {
    switch(node.type) {
      case 'lncrna': return '#ff6b6b'
      case 'target': return '#4ecdc4'
      case 'disease': return '#ffe66d'
    }
  }}
  nodeVal={node => node.regulation_count || 1}

  // 连线配置
  linkColor={() => 'rgba(255,255,255,0.2)'}
  linkWidth={link => Math.sqrt(link.ba) / 5}
  linkOpacity={0.5}

  // 交互
  onNodeClick={handleNodeClick}
  onNodeHover={handleNodeHover}

  // 性能
  enableNodeDrag={true}
  warmupTicks={100}
  cooldownTicks={0}
/>
```

---

## 前端路由配置

### 新增路由

```typescript
// src/router/index.tsx
const routes = [
  // ... 现有路由 ...

  // Phase 5.3: 高级可视化
  {
    path: '/visualization',
    children: [
      {
        path: 'sankey-flow',
        element: <SankeyFlowPage />,
        meta: { title: 'Sankey 流向图' }
      },
      {
        path: 'conservation-chord',
        element: <ConservationChordPage />,
        meta: { title: '保守性关系图' }
      },
      {
        path: 'network-3d',
        element: <Network3DPage />,
        meta: { title: '3D 网络拓扑' }
      }
    ]
  },

  // 管理员页面
  {
    path: '/admin/performance-dashboard',
    element: <PerformanceDashboard />,
    meta: { title: '性能监控', requiresAuth: true }
  }
]
```

### 导航菜单

**顶部菜单添加**:
```typescript
{
  label: '高级可视化',
  key: 'visualization',
  icon: <LineChartOutlined />,
  children: [
    { label: 'Sankey 流向图', key: 'sankey' },
    { label: '保守性关系图', key: 'chord' },
    { label: '3D 网络拓扑', key: '3d-network' }
  ]
}
```

---

## API 端点规划

### 新建 Visualization Router

**文件**: `frontend/backend/app/routers/visualization.py`

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

router = APIRouter(prefix="/visualization", tags=["visualization"])

@router.get("/sankey-data")
def get_sankey_data(...):
    """Sankey 图数据"""
    pass

@router.get("/chord-conservation")
def get_chord_data(...):
    """Chord 图保守性数据"""
    pass

@router.get("/network-3d")
def get_3d_network(...):
    """3D 网络图数据"""
    pass
```

**注册路由**:
```python
# main.py
from app.routers import visualization

app.include_router(visualization.router, prefix="/api/v1")
```

---

## 工作量估算

### 按可视化类型

| 可视化方案 | 前端 | 后端 | 测试 | 总计 |
|----------|------|------|------|------|
| **Sankey Flow** | 4h | 2h | 1h | **7h** |
| **Chord 关系图** | 3h | 2h | 1h | **6h** |
| **3D Network** | 6h | 2h | 2h | **10h** |
| **性能仪表盘** | 6h | 2h | 1h | **9h** |

**总计**: 约 32 小时 = **4 天**（单人）或 **2 天**（双人并行）

---

### 按实施阶段

**MVP 阶段**（1 天，8 小时）:
- ✅ Sankey 流向图（核心功能）
- ✅ 基础后端 API
- ✅ 简单交互

**完整阶段**（2-3 天，20 小时）:
- ✅ Chord 关系图
- ✅ 3D 网络图（简化版）
- ✅ 完整交互功能

**增强阶段**（3-4 天，32 小时）:
- ✅ 性能仪表盘
- ✅ 所有高级交互
- ✅ 完整测试覆盖

---

## 成功验收标准

### 可视化质量

- ✅ 图表清晰美观（符合科研发表标准）
- ✅ 颜色方案协调一致
- ✅ 交互流畅（60 FPS）
- ✅ 响应式布局（支持不同屏幕）

### 功能完整性

- ✅ 所有交互功能正常
- ✅ 数据导出功能
- ✅ 错误处理完善
- ✅ 加载状态友好

### 性能要求

- ✅ 图表渲染时间 <2s
- ✅ 交互响应 <100ms
- ✅ 内存占用 <500MB
- ✅ 支持 1000+ 节点（3D 图）

### 文档要求

- ✅ 使用文档（用户手册）
- ✅ 开发文档（技术文档）
- ✅ API 文档（接口说明）

---

## 依赖安装清单

### NPM 包

```json
{
  "dependencies": {
    "react-force-graph-3d": "^1.24.4",
    "three": "^0.160.0",
    "@ant-design/pro-components": "^2.6.48",
    "@ant-design/charts": "^2.0.3",
    "socket.io-client": "^4.6.1"
  },
  "devDependencies": {
    "@types/three": "^0.160.0"
  }
}
```

### Python 包（如需后端生成图表）

```bash
pip install plotly
pip install kaleido  # 图表导出
```

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **3D 性能问题** | 中 | 中 | 节点数限制、LOD、WebGL 优化 |
| **浏览器兼容性** | 低 | 中 | Polyfill、降级方案 |
| **数据量过大** | 中 | 高 | 分页加载、懒加载、虚拟化 |
| **学习曲线陡峭** | 中 | 低 | 详细文档、示例代码 |
| **实时数据延迟** | 低 | 低 | WebSocket + 缓存 |

---

## 参考资源

### ECharts 官方示例

- Sankey: https://echarts.apache.org/examples/zh/editor.html?c=sankey-simple
- Chord: https://echarts.apache.org/examples/zh/editor.html?c=graph-circular-layout

### React Force Graph

- 官网: https://github.com/vasturiano/react-force-graph
- 3D 示例: https://vasturiano.github.io/react-force-graph/example/3d/

### Three.js

- 官网: https://threejs.org/
- 示例: https://threejs.org/examples/

---

## 后续扩展

### Phase 5.4（未来）

**更多可视化类型**:
1. **基因组圆环图**（Circos Plot）- 染色体级别的调控关系
2. **小提琴图**（Violin Plot）- BA 分布的详细展示
3. **旭日图**（Sunburst）- 分层数据（物种 → 基因类型 → 基因）
4. **河流图**（Stream Graph）- 调控关系随进化的变化趋势
5. **地理图**（Geo Map）- 实验室/数据源地理分布（如有元数据）

---

## 总结

**Phase 5.3 高级可视化**将：

1. **提升专业性** - 科研级可视化工具
2. **增强交互性** - 3D/动态图表
3. **改善用户体验** - 直观的数据探索
4. **支持决策** - 性能监控仪表盘

**预期产出**:
- 4 个新可视化页面
- 4 个通用组件
- 3 个新 API 端点
- 完整的使用文档

**投入产出比**: ⭐⭐⭐⭐（高价值，中等工作量）

**下一步**: 安装依赖，创建 Visualization Router，实现第一个 Sankey 图

---

**规划创建**: 2025-12-10
**规划版本**: Phase 5.3
**状态**: 📋 规划就绪，等待执行

**AI 协助**: Claude Sonnet 4.5 (1M context)
