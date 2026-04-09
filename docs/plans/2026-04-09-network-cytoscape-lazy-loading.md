# Network Cytoscape Lazy Loading Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 `/network` 路由被 `cytoscape` 顶层依赖拖垮的问题，保证页面先可加载，再按需初始化网络图。

**Architecture:** 保持现有路由和页面结构不变，只把 `cytoscape` 与 `cytoscape-svg` 的 runtime 加载从模块顶层移到按需异步加载 helper 中。页面级回归测试验证“依赖不可用时路由仍可渲染”，图组件内部负责显示局部加载或错误状态。

**Tech Stack:** React 19、TypeScript、Vite、Vitest、Cytoscape.js、Ant Design

### Task 1: 写出路由隔离失败测试

**Files:**
- Create: `frontend/web/src/pages/Network/index.lazy-loading.test.tsx`
- Test: `frontend/web/src/pages/Network/index.lazy-loading.test.tsx`

**Step 1: Write the failing test**

新增测试，模拟 `cytoscape` 模块不可用，断言 `Network` 页面仍能渲染筛选器而不是在模块导入阶段直接崩溃。

**Step 2: Run test to verify it fails**

Run: `npm run test:run -- src/pages/Network/index.lazy-loading.test.tsx`

Expected: FAIL，原因是 `Network` 路由模块仍在顶层导入 `cytoscape`

### Task 2: 把 Cytoscape 改成按需加载

**Files:**
- Create: `frontend/web/src/pages/Network/utils/loadCytoscape.ts`
- Modify: `frontend/web/src/pages/Network/index.tsx`
- Modify: `frontend/web/src/pages/Network/components/NetworkCard.tsx`
- Modify: `frontend/web/src/pages/Network/utils/cytoscapeExport.ts`

**Step 1: Write minimal implementation**

新增带缓存的 `loadCytoscape()` helper，负责：
- 动态导入 `cytoscape`
- 动态导入 `cytoscape-svg`
- 只注册一次 SVG 插件

然后把 `Network` 页面相关 runtime 依赖切到这个 helper，避免页面模块顶层触发重依赖。

**Step 2: Run targeted tests**

Run: `npm run test:run -- src/pages/Network/index.lazy-loading.test.tsx src/pages/Network/index.test.tsx`

Expected: PASS

### Task 3: 更新文档与范围验证

**Files:**
- Modify: `frontend/web/README.md`

**Step 1: Update docs**

补充 `/network` 页面与 `cytoscape` 重依赖按需加载的说明。

**Step 2: Run checks**

Run: `npx eslint src/pages/Network/index.tsx src/pages/Network/components/NetworkCard.tsx src/pages/Network/utils/cytoscapeExport.ts src/pages/Network/utils/loadCytoscape.ts src/pages/Network/index.test.tsx src/pages/Network/index.lazy-loading.test.tsx`

Expected: PASS

**Step 3: Optional follow-up**

如有需要，再运行 `npm run build` 做一次路由级构建回归。
