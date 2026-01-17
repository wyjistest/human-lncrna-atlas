# 国际化方案：简体中文 + English 双语支持

**日期**: 2025-11-28
**版本**: v1.0
**复杂度**: ⭐⭐⭐⭐ (较高)

---

## 一、现状分析

### 1.1 项目规模

| 指标 | 数值 |
|------|------|
| 含中文文件数 | 31 |
| 中文文本总数 | 1,101 处 |
| 去重后文本数 | 786 个 |
| 主要文件 | Network, Regulations, Stats, Home |

### 1.2 文本分布

```
369 处  pages/Network/index.tsx      ← 最复杂
148 处  types/api.ts                 ← 类型注释（不需翻译）
 61 处  utils/pdf-export.ts
 58 处  Regulations/AdvancedFilters.tsx
 57 处  Regulations/index.tsx
 55 处  BatchVisualizationModal.tsx
 45 处  utils/export.ts
 ...
```

### 1.3 文本类型

| 类型 | 示例 | 处理方式 |
|------|------|----------|
| 静态标签 | "首页", "调控关系" | t('nav.home') |
| 按钮文本 | "导出", "搜索" | t('action.export') |
| 表格列头 | "基因名称", "物种" | t('table.geneName') |
| 消息提示 | "导出成功", "加载失败" | t('message.exportSuccess') |
| 动态插值 | "共 {count} 条" | t('result.total', { count }) |
| 图表标签 | "物种分布", "BA分布" | t('chart.speciesDistribution') |
| 表单标签 | "请输入关键词" | t('form.enterKeyword') |

---

## 二、技术选型

### 2.1 框架对比

| 方案 | Bundle | 特点 | 推荐度 |
|------|--------|------|--------|
| **react-i18next** | ~15KB | 生态成熟，懒加载，TS 支持 | ⭐⭐⭐⭐⭐ |
| react-intl | ~25KB | Facebook 方案，ICU 格式 | ⭐⭐⭐ |
| 自定义 Context | ~2KB | 轻量但功能有限 | ⭐⭐ |

**选择**: `react-i18next` + `i18next`

### 2.2 依赖安装

```bash
npm install i18next react-i18next i18next-browser-languagedetector
```

| 包 | 作用 | 大小 |
|-----|------|------|
| i18next | 核心国际化引擎 | ~10KB |
| react-i18next | React 绑定 | ~5KB |
| i18next-browser-languagedetector | 浏览器语言检测 | ~2KB |

---

## 三、架构设计

### 3.1 目录结构

```
src/
├── i18n/
│   ├── index.ts              # i18n 初始化配置
│   ├── types.ts              # 类型定义（自动生成）
│   └── locales/
│       ├── zh-CN/
│       │   ├── common.json       # 通用文本
│       │   ├── nav.json          # 导航菜单
│       │   ├── home.json         # 首页
│       │   ├── stats.json        # 统计页
│       │   ├── genes.json        # 基因页
│       │   ├── regulations.json  # 调控关系页
│       │   ├── diseases.json     # 疾病页
│       │   ├── network.json      # 网络页
│       │   ├── table.json        # 表格相关
│       │   ├── form.json         # 表单相关
│       │   ├── message.json      # 消息提示
│       │   └── chart.json        # 图表相关
│       └── en/
│           ├── common.json
│           ├── nav.json
│           └── ... (同上)
```

### 3.2 命名空间设计

```typescript
// 命名空间划分
const namespaces = [
  'common',      // 通用：按钮、状态、单位
  'nav',         // 导航菜单
  'home',        // 首页
  'stats',       // 统计概览
  'genes',       // 基因列表
  'regulations', // 调控关系
  'diseases',    // 疾病关联
  'network',     // 网络可视化
  'table',       // 表格列头、分页
  'form',        // 表单标签、验证
  'message',     // 成功/错误消息
  'chart'        // 图表标题、标签
]
```

### 3.3 翻译文件示例

```json
// src/i18n/locales/zh-CN/common.json
{
  "action": {
    "export": "导出",
    "search": "搜索",
    "reset": "重置",
    "confirm": "确定",
    "cancel": "取消",
    "close": "关闭",
    "view": "查看",
    "download": "下载"
  },
  "status": {
    "loading": "加载中...",
    "noData": "暂无数据",
    "error": "加载失败"
  },
  "unit": {
    "count": "条",
    "total": "共 {{count}} 条"
  }
}

// src/i18n/locales/en/common.json
{
  "action": {
    "export": "Export",
    "search": "Search",
    "reset": "Reset",
    "confirm": "OK",
    "cancel": "Cancel",
    "close": "Close",
    "view": "View",
    "download": "Download"
  },
  "status": {
    "loading": "Loading...",
    "noData": "No data",
    "error": "Failed to load"
  },
  "unit": {
    "count": "records",
    "total": "{{count}} records in total"
  }
}
```

```json
// src/i18n/locales/zh-CN/nav.json
{
  "home": "首页",
  "stats": "统计概览",
  "genes": "基因列表",
  "regulations": "调控关系",
  "diseases": "疾病关联",
  "network": "网络可视化"
}

// src/i18n/locales/en/nav.json
{
  "home": "Home",
  "stats": "Statistics",
  "genes": "Gene List",
  "regulations": "Regulations",
  "diseases": "Disease Associations",
  "network": "Network Visualization"
}
```

---

## 四、核心实现

### 4.1 i18n 初始化

```typescript
// src/i18n/index.ts
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

// 导入所有翻译文件
import zhCommon from './locales/zh-CN/common.json'
import zhNav from './locales/zh-CN/nav.json'
import zhHome from './locales/zh-CN/home.json'
// ... 其他命名空间

import enCommon from './locales/en/common.json'
import enNav from './locales/en/nav.json'
import enHome from './locales/en/home.json'
// ... 其他命名空间

const resources = {
  'zh-CN': {
    common: zhCommon,
    nav: zhNav,
    home: zhHome,
    // ...
  },
  en: {
    common: enCommon,
    nav: enNav,
    home: enHome,
    // ...
  }
}

i18n
  .use(LanguageDetector)  // 自动检测浏览器语言
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'zh-CN',  // 默认中文
    defaultNS: 'common',   // 默认命名空间

    interpolation: {
      escapeValue: false   // React 已处理 XSS
    },

    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'i18n_lang'
    }
  })

export default i18n
```

### 4.2 App 入口集成

```typescript
// src/main.tsx
import './i18n'  // 在 App 之前导入
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
```

### 4.3 语言切换组件

```typescript
// src/components/LanguageSwitch.tsx
import { Select } from 'antd'
import { GlobalOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'

const LANGUAGES = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en', label: 'English' }
]

export function LanguageSwitch() {
  const { i18n } = useTranslation()

  const handleChange = (lang: string) => {
    i18n.changeLanguage(lang)
  }

  return (
    <Select
      value={i18n.language}
      onChange={handleChange}
      options={LANGUAGES}
      style={{ width: 120 }}
      suffixIcon={<GlobalOutlined />}
      variant="borderless"
    />
  )
}
```

### 4.4 组件使用示例

```typescript
// 改造前
export default function MainLayout() {
  const menuItems = [
    { key: '/', icon: <HomeOutlined />, label: '首页' },
    { key: '/stats', icon: <BarChartOutlined />, label: '统计概览' },
    // ...
  ]
}

// 改造后
import { useTranslation } from 'react-i18next'

export default function MainLayout() {
  const { t } = useTranslation('nav')  // 使用 nav 命名空间

  const menuItems = [
    { key: '/', icon: <HomeOutlined />, label: t('home') },
    { key: '/stats', icon: <BarChartOutlined />, label: t('stats') },
    // ...
  ]
}
```

### 4.5 动态插值

```typescript
// 翻译文件
// zh-CN: "共 {{count}} 条，已选择 {{selected}} 条"
// en:    "{{count}} records, {{selected}} selected"

// 组件中使用
const { t } = useTranslation('table')
t('pagination.info', { count: 1000, selected: 5 })
```

### 4.6 Ant Design 国际化

```typescript
// src/App.tsx
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import enUS from 'antd/locale/en_US'
import { useTranslation } from 'react-i18next'

function App() {
  const { i18n } = useTranslation()

  // Ant Design 语言包映射
  const antdLocale = i18n.language === 'en' ? enUS : zhCN

  return (
    <ConfigProvider locale={antdLocale}>
      <RouterProvider router={router} />
    </ConfigProvider>
  )
}
```

---

## 五、类型安全

### 5.1 TypeScript 类型定义

```typescript
// src/i18n/types.ts
import 'i18next'
import type common from './locales/zh-CN/common.json'
import type nav from './locales/zh-CN/nav.json'
// ... 其他

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'common'
    resources: {
      common: typeof common
      nav: typeof nav
      // ...
    }
  }
}
```

### 5.2 自动类型生成（可选）

```bash
# 使用 i18next-parser 提取文本并生成类型
npm install -D i18next-parser
```

---

## 六、实施步骤

### Phase 1: 基础设施（预计改动 5 个文件）

| 步骤 | 文件 | 说明 |
|------|------|------|
| 1.1 | 安装依赖 | npm install |
| 1.2 | `src/i18n/index.ts` | 新建初始化配置 |
| 1.3 | `src/i18n/locales/**` | 创建翻译文件结构 |
| 1.4 | `src/main.tsx` | 导入 i18n |
| 1.5 | `src/App.tsx` | ConfigProvider 语言切换 |
| 1.6 | `LanguageSwitch.tsx` | 新建语言切换组件 |
| 1.7 | `MainLayout.tsx` | 集成语言切换器 |

### Phase 2: 核心页面（预计改动 6 个文件）

| 步骤 | 文件 | 文本量 |
|------|------|--------|
| 2.1 | `MainLayout.tsx` | 6 处 |
| 2.2 | `Home/index.tsx` | 15 处 |
| 2.3 | `Stats/index.tsx` | 28 处 |
| 2.4 | `Stats/components/*.tsx` | 28 处 |
| 2.5 | `Genes/index.tsx` | 9 处 |
| 2.6 | `Diseases/index.tsx` | 6 处 |

### Phase 3: 复杂页面（预计改动 5 个文件）

| 步骤 | 文件 | 文本量 |
|------|------|--------|
| 3.1 | `Regulations/index.tsx` | 57 处 |
| 3.2 | `Regulations/AdvancedFilters.tsx` | 58 处 |
| 3.3 | `Regulations/SelectionToolbar.tsx` | 15 处 |
| 3.4 | `Regulations/BatchVisualizationModal.tsx` | 55 处 |
| 3.5 | `Network/index.tsx` | 369 处 ⚠️ |

### Phase 4: 工具函数（预计改动 4 个文件）

| 步骤 | 文件 | 文本量 |
|------|------|--------|
| 4.1 | `utils/export.ts` | 45 处 |
| 4.2 | `utils/pdf-export.ts` | 61 处 |
| 4.3 | `utils/chart-export.ts` | 9 处 |
| 4.4 | `components/*.tsx` | 5 处 |

### Phase 5: 收尾

| 步骤 | 说明 |
|------|------|
| 5.1 | 英文翻译校对 |
| 5.2 | 测试语言切换 |
| 5.3 | 检查遗漏文本 |
| 5.4 | 文档更新 |

---

## 七、特殊场景处理

### 7.1 工具函数中的消息

```typescript
// utils/export.ts 改造

// 方案 A: 传入 t 函数
export function exportToExcel(data: any[], t: TFunction) {
  message.success(t('message.exportSuccess'))
}

// 方案 B: 返回状态，由调用方显示消息
export function exportToExcel(data: any[]): { success: boolean } {
  // ...
  return { success: true }
}
// 调用方
const result = exportToExcel(data)
if (result.success) message.success(t('message.exportSuccess'))
```

**推荐方案 B**: 保持函数纯净，消息由 UI 层处理。

### 7.2 表格列定义

```typescript
// 改造前
const columns = [
  { title: '基因名称', dataIndex: 'gene_name' },
  { title: '物种', dataIndex: 'species' }
]

// 改造后：使用 useMemo
const { t } = useTranslation('table')

const columns = useMemo(() => [
  { title: t('geneName'), dataIndex: 'gene_name' },
  { title: t('species'), dataIndex: 'species' }
], [t])
```

### 7.3 ECharts 图表

```typescript
// 图表配置需要在语言变化时更新
const { t, i18n } = useTranslation('chart')

const option = useMemo(() => ({
  title: { text: t('speciesDistribution') },
  // ...
}), [t, i18n.language])  // 依赖语言变化
```

### 7.4 动态 API 数据

API 返回的数据（如物种名称）有两种处理方式：

| 方案 | 实现 | 优点 | 缺点 |
|------|------|------|------|
| 前端映射 | `SPECIES_MAP[data.species_id]` | 简单 | 维护成本 |
| 后端多语言 | API 参数 `?lang=en` | 数据一致 | 后端改动 |

**推荐**: 静态数据（物种、染色体）用前端映射；动态数据保持英文（如基因名）。

```typescript
// config/constants.ts
export const SPECIES_NAMES: Record<number, { zh: string; en: string }> = {
  1: { zh: '人类', en: 'Human' },
  2: { zh: '黑猩猩', en: 'Chimpanzee' },
  3: { zh: '猕猴', en: 'Macaque' },
  4: { zh: '狨猴', en: 'Marmoset' }
}

// 使用
const speciesName = SPECIES_NAMES[id][i18n.language === 'en' ? 'en' : 'zh']
```

---

## 八、性能优化

### 8.1 翻译文件懒加载（可选）

```typescript
// 仅在切换语言时加载对应文件
i18n.use(Backend).init({
  backend: {
    loadPath: '/locales/{{lng}}/{{ns}}.json'
  }
})
```

**当前项目规模不大，建议静态导入**，避免增加复杂度。

### 8.2 避免不必要的重渲染

```typescript
// 使用 useMemo 缓存静态配置
const menuItems = useMemo(() => [
  { key: '/', label: t('nav.home') }
], [t])
```

---

## 九、测试清单

| 场景 | 验证点 |
|------|--------|
| 默认语言 | 首次访问显示中文 |
| 语言切换 | 点击后立即切换，无刷新 |
| 持久化 | 刷新页面保持语言选择 |
| Ant Design | Table/Pagination 等组件语言正确 |
| 图表 | ECharts 标签更新 |
| 消息提示 | message/notification 语言正确 |
| 动态内容 | 插值参数正确显示 |
| 边界情况 | 缺失翻译显示 key 而非空白 |

---

## 十、工作量评估

| Phase | 文件数 | 文本量 | 复杂度 |
|-------|--------|--------|--------|
| Phase 1 | 5 | - | ⭐ |
| Phase 2 | 6 | ~90 | ⭐⭐ |
| Phase 3 | 5 | ~550 | ⭐⭐⭐⭐ |
| Phase 4 | 4 | ~120 | ⭐⭐ |
| Phase 5 | - | 校对 | ⭐⭐ |
| **总计** | **20** | **~760** | |

### 主要风险点

| 风险 | 影响 | 缓解 |
|------|------|------|
| Network 页 369 处文本 | 工作量大 | 批量替换 + 仔细校对 |
| 工具函数消息 | 需要重构调用方式 | 方案 B 返回状态 |
| 遗漏文本 | 用户体验不一致 | grep 检查中文 |
| 翻译质量 | 专业术语不准确 | 领域专家审核 |

---

## 十一、后续扩展

- [ ] 繁体中文支持
- [ ] 更多语言（日语、韩语）
- [ ] 翻译管理平台集成（如 Crowdin）
- [ ] 自动化翻译检查 CI

---

**文档版本**: v1.0
**作者**: Claude Code
**预计完成周期**: Phase 1-5 分步实施
