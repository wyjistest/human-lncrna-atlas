# Phase 4: Network 页面国际化方案

**日期**: 2025-11-28
**状态**: 待实施
**复杂度**: ⭐⭐⭐⭐⭐ (最高)

> 更新（2026-01-24）：本文档为会话/方案快照，可能与当前进展不一致；现状以 `docs/CURRENT_STATUS.md` 为准。

---

## 一、现状分析

### 1.1 页面规模

| 指标 | 数值 |
|------|------|
| 文件行数 | 1,478 行 |
| 中文文本处 | ~369 处 |
| 组件数 | 2 (NetworkCard + Network) |
| 依赖 | cytoscape, jszip, file-saver |

### 1.2 文本分类

| 类型 | 数量 | 示例 |
|------|------|------|
| **静态标签** | ~50 | "网络可视化", "物种", "疾病" |
| **表单/输入** | ~20 | "搜索基因", "选择物种" |
| **消息提示** | ~40 | "网络图未加载", "导出成功" |
| **过滤器** | ~30 | "高级过滤器", "BA阈值", "节点类型" |
| **Drawer 详情** | ~25 | "基因名称", "染色体", "保守性标签" |
| **导出相关** | ~50 | "导出为PNG", "批量导出所有物种" |
| **布局选项** | ~15 | "同心圆布局", "力导向布局" |
| **动态拼接** | ~20 | `正在生成${speciesName}的PNG...` |

---

## 二、翻译文件结构

### 2.1 新增 `network.json`

```
src/i18n/locales/
├── zh-CN/
│   └── network.json    # 新增
└── en/
    └── network.json    # 新增
```

### 2.2 翻译 Key 结构设计

```json
{
  "title": "网络可视化",
  "description": "根据疾病-Ontology组合构建lncRNA调控网络（支持多物种对比，最多4个）",

  "species": {
    "label": "物种",
    "placeholder": "选择物种（最多4个）",
    "max4Warning": "最多选择4个物种",
    "selectAtLeast1": "请至少选择一个物种",
    "human": "人类",
    "chimpanzee": "黑猩猩",
    "macaque": "猕猴",
    "marmoset": "狨猴"
  },

  "disease": {
    "label": "疾病",
    "placeholder": "选择疾病"
  },

  "ontology": {
    "label": "Ontology",
    "placeholder": "选择Ontology"
  },

  "query": {
    "button": "查询网络",
    "selectDiseaseOntology": "请选择疾病和Ontology"
  },

  "card": {
    "noData": "该物种无网络数据",
    "nodes": "节点",
    "edges": "边",
    "lncrna": "lncRNA",
    "targetGenes": "靶基因",
    "searchResults": "搜索结果",
    "searchPlaceholder": "搜索基因",
    "clickToLocate": "点击定位"
  },

  "filters": {
    "title": "高级过滤器",
    "enabled": "已启用",
    "baThreshold": "Binding Affinity 阈值",
    "nodeType": "节点类型",
    "all": "全部",
    "targetGene": "靶基因",
    "minDegree": "最小度数（连接数）",
    "layout": "布局算法",
    "resetAll": "重置所有设置"
  },

  "layouts": {
    "concentric": "同心圆布局 (Concentric)",
    "cose": "力导向布局 (COSE)",
    "circle": "圆形布局 (Circle)",
    "grid": "网格布局 (Grid)",
    "breadthfirst": "层次布局 (Breadthfirst)",
    "random": "随机布局 (Random)"
  },

  "export": {
    "button": "导出",
    "png": "导出为PNG",
    "svg": "导出为SVG",
    "csv": "导出为CSV",
    "json": "导出为JSON",
    "svgNotSupported": "SVG导出功能需要额外插件，当前使用PNG格式",
    "noData": "无数据可导出",
    "networkNotLoaded": "网络图未加载",
    "generating": "正在生成{{species}}的{{format}}...",
    "success": "{{species}} {{format}}导出成功",
    "failed": "{{species}} {{format}}导出失败"
  },

  "batchExport": {
    "button": "批量导出所有物种",
    "title": "批量导出所有物种网络图",
    "speciesCount": "将导出 {{count}} 个物种的网络图",
    "diseaseLabel": "疾病",
    "ontologyLabel": "Ontology",
    "selectFormats": "选择导出格式",
    "pngFormat": "PNG 图片 (高分辨率 2x)",
    "csvFormat": "CSV 数据 (节点和边)",
    "jsonFormat": "JSON 原始数据",
    "zipNote": "文件将打包为 ZIP 格式下载",
    "startExport": "开始导出",
    "cancel": "取消",
    "selectAtLeastOne": "请至少选择一个导出格式",
    "preparing": "正在准备导出...",
    "generatingImages": "正在生成网络图...",
    "packing": "正在打包文件...",
    "success": "成功导出 {{count}} 个物种的网络图！",
    "failed": "导出失败，请重试",
    "noExportable": "没有可导出的网络图，请确保网络已加载完成",
    "notReady": "还有 {{count}} 个物种未加载完成（{{names}}），请稍后再导出",
    "mergeImageFailed": "合并图像生成失败，仅导出单独图片"
  },

  "drawer": {
    "title": "基因详情",
    "geneName": "基因名称",
    "ensemblId": "Ensembl ID",
    "ensemblLink": "Ensembl Link",
    "ensemblLinkNA": "N/A (仅支持 ENSG)",
    "fantomLink": "FANTOM5 CAT Link",
    "geneType": "基因类型",
    "species": "物种",
    "conservationLabel": "保守性标签",
    "conservationCount": "{{count}}/4 物种",
    "chromosome": "染色体",
    "startPosition": "起始位置",
    "endPosition": "终止位置",
    "strand": "链",
    "coreId": "Core ID",
    "asSource": "作为源的调控",
    "asTarget": "作为目标的调控",
    "totalRegulations": "总调控关系",
    "totalBA": "总Binding Affinity",
    "noData": "无数据"
  },

  "tooltip": {
    "baTooltip": "BA ≥ {{value}}",
    "degreeTooltip": "度数 ≥ {{value}}"
  }
}
```

---

## 三、实施步骤

### 3.1 Phase 4.1: 创建翻译文件

| 操作 | 文件 |
|------|------|
| 创建 | `src/i18n/locales/zh-CN/network.json` |
| 创建 | `src/i18n/locales/en/network.json` |
| 修改 | `src/i18n/index.ts` (添加 import) |

### 3.2 Phase 4.2: 改造 Network 主组件

**改造点**:
- [ ] 页面标题和描述
- [ ] 物种选择器 (Select)
- [ ] 疾病/Ontology 选择器
- [ ] 查询按钮
- [ ] 批量导出按钮和 Modal

**代码示例**:
```tsx
// 改造前
<h1>网络可视化</h1>

// 改造后
const { t } = useTranslation('network')
<h1>{t('title')}</h1>
```

### 3.3 Phase 4.3: 改造 NetworkCard 组件

**改造点**:
- [ ] 搜索框 placeholder
- [ ] 统计信息 (节点/边/lncRNA/靶基因)
- [ ] 高级过滤器 Collapse
- [ ] 过滤器标签和选项
- [ ] 布局选择器
- [ ] 导出菜单
- [ ] 消息提示 (message.xxx)

**关键难点**:
```tsx
// 动态拼接需要使用插值
// 改造前
message.loading({ content: `正在生成${speciesName}的PNG...` })

// 改造后
message.loading({ content: t('export.generating', { species: speciesName, format: 'PNG' }) })
```

### 3.4 Phase 4.4: 改造 Drawer 详情

**改造点**:
- [ ] Drawer 标题
- [ ] Descriptions.Item 的 label
- [ ] 保守性标签说明文本
- [ ] 链接文本

### 3.5 Phase 4.5: 物种名称本地化

**特殊处理**:
```tsx
// SPECIES_OPTIONS 需要动态翻译
const { t, i18n } = useTranslation('network')

const localizedSpeciesOptions = useMemo(() => [
  { label: t('species.human'), value: 1 },
  { label: t('species.chimpanzee'), value: 2 },
  { label: t('species.macaque'), value: 3 },
  { label: t('species.marmoset'), value: 4 },
], [t, i18n.language])
```

---

## 四、技术要点

### 4.1 消息提示的处理

由于 `message.xxx()` 在组件外部调用，需要确保 `t()` 在调用时可用：

```tsx
// 方案 A: 在函数内部获取 t
const exportAsPNG = async () => {
  // t 已在组件顶层定义
  message.loading({ content: t('export.generating', { species, format: 'PNG' }) })
}

// 方案 B: 传入翻译后的字符串
const exportAsPNG = async (labels: { generating: string; success: string; failed: string }) => {
  message.loading({ content: labels.generating })
}
```

**推荐方案 A**，因为 `t()` 在 React 组件内部始终可用。

### 4.2 动态拼接的插值

```json
// 翻译文件
{
  "export": {
    "generating": "正在生成{{species}}的{{format}}..."
  }
}

// 使用
t('export.generating', { species: '人类', format: 'PNG' })
// 输出: "正在生成人类的PNG..."
```

### 4.3 Slider tooltip 格式化

```tsx
// 改造前
tooltip={{ formatter: (value) => `BA ≥ ${value}` }}

// 改造后
tooltip={{ formatter: (value) => t('tooltip.baTooltip', { value }) }}
```

### 4.4 保守性标签的特殊处理

```tsx
// 改造前
<div style={{ marginTop: 4, fontSize: 11, color: '#999' }}>
  {geneDetail.conservation_label[0] === '1' && '人类 '}
  {geneDetail.conservation_label[1] === '1' && '黑猩猩 '}
  ...
</div>

// 改造后
const speciesNames = [
  t('species.human'),
  t('species.chimpanzee'),
  t('species.macaque'),
  t('species.marmoset')
]

<div>
  {geneDetail.conservation_label.split('').map((flag, i) =>
    flag === '1' ? speciesNames[i] + ' ' : ''
  ).join('')}
</div>
```

---

## 五、工作量评估

| 阶段 | 内容 | 文本量 | 复杂度 |
|------|------|--------|--------|
| 4.1 | 创建翻译文件 | ~150 keys | ⭐⭐ |
| 4.2 | Network 主组件 | ~80 处 | ⭐⭐⭐ |
| 4.3 | NetworkCard 组件 | ~200 处 | ⭐⭐⭐⭐ |
| 4.4 | Drawer 详情 | ~40 处 | ⭐⭐ |
| 4.5 | 物种名称本地化 | ~20 处 | ⭐⭐ |

**总预计改动行数**: ~300-400 行

---

## 六、验收标准

- [ ] 页面标题和描述正确切换
- [ ] 所有 Select 的 placeholder 正确翻译
- [ ] 高级过滤器全部文本正确翻译
- [ ] 导出菜单和消息提示正确翻译
- [ ] Drawer 详情页全部标签正确翻译
- [ ] 物种名称随语言切换正确变化
- [ ] 批量导出 Modal 全部文本正确翻译
- [ ] TypeScript 无错误
- [ ] 功能测试通过（导出、过滤、搜索等）

---

## 七、恢复命令

```bash
# 读取本文档继续实施
cat <repo-root>/frontend/SESSION_PHASE4_NETWORK_I18N.md
```

---

**文档版本**: v1.0
**作者**: Claude Code
