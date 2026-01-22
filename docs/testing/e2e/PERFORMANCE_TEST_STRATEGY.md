# Network Disease Filter Performance Test Strategy

## 执行摘要

本文档定义了针对 **Network 页面疾病筛选功能 API 优化和缓存层**的性能测试策略。目标是验证优化后的性能提升，并建立可重复的性能基准测试框架。

---

## 1. 背景与目标

### 1.1 优化背景
- **现状**: 疾病下拉选项通过 `/api/v1/diseases` 端点获取，当前配置 `page_size=500`
- **问题**: 可能存在的性能瓶颈包括:
  - API 响应时间过长（特别是初次加载）
  - 前端渲染大量选项导致 UI 卡顿
  - 选择疾病后网络图加载缓慢
  - 缺乏有效的缓存机制

### 1.2 测试目标
1. **建立性能基准**: 记录优化前的性能指标
2. **验证优化效果**: 对比优化前后的性能提升
3. **发现性能瓶颈**: 识别前端、后端、数据库各层的性能问题
4. **预防性能回归**: 建立可持续的性能监控机制

---

## 2. 测试架构

### 2.1 测试层级
```
┌─────────────────────────────────────────────────────────┐
│                   Performance Test Suite                │
├─────────────────────────────────────────────────────────┤
│  1. API Layer Tests (Backend Performance)               │
│     - Disease options API response time                 │
│     - Network data API response time                    │
│     - Cache hit rate measurement                        │
├─────────────────────────────────────────────────────────┤
│  2. Frontend Rendering Tests (UI Performance)           │
│     - Disease dropdown render time                      │
│     - Large options list scroll performance             │
│     - UI interaction responsiveness                     │
├─────────────────────────────────────────────────────────┤
│  3. End-to-End User Journey Tests (Full Flow)           │
│     - Page load → disease selection → network render    │
│     - Multi-species comparison flow                     │
│     - Batch export with large datasets                  │
├─────────────────────────────────────────────────────────┤
│  4. Stress & Load Tests (Scalability)                   │
│     - Concurrent user simulation                        │
│     - Large dataset handling (500+ options)             │
│     - Memory leak detection                             │
└─────────────────────────────────────────────────────────┘
```

### 2.2 测试工具选择

| 工具 | 用途 | 优势 |
|------|------|------|
| **Playwright** | E2E 性能测试 | 真实浏览器环境、可测量实际用户体验 |
| **Playwright Performance API** | 精确时间测量 | `page.evaluate(() => performance.timing)` |
| **page.waitForResponse()** | API 响应时间 | 捕获网络请求时长 |
| **Chrome DevTools Protocol** | 性能分析 | CPU、内存、FPS 监控 |
| **Lighthouse CI** (可选) | 持续性能监控 | 自动生成性能报告 |

---

## 3. 关键性能指标 (KPI)

### 3.1 核心指标定义

#### A. API 层性能指标

| 指标 | 说明 | 基准目标 | 优化目标 | 测量方法 |
|------|------|----------|----------|----------|
| **Disease API TTFB** | 疾病列表首字节时间 | < 500ms | < 200ms | `page.waitForResponse()` |
| **Disease API Total Time** | 完整响应时间 (含数据传输) | < 1000ms | < 400ms | Response timing |
| **Network Data API TTFB** | 网络数据首字节时间 | < 1000ms | < 500ms | `page.waitForResponse()` |
| **Cache Hit Rate** | 缓存命中率 | N/A | > 80% | Response headers (`X-Cache-Status`) |
| **Payload Size** | 响应数据大小 | 记录 | 减少 30% | Response body size |

#### B. 前端渲染性能指标

| 指标 | 说明 | 基准目标 | 优化目标 | 测量方法 |
|------|------|----------|----------|----------|
| **Dropdown Render Time** | 下拉选项渲染时间 | < 500ms | < 200ms | `performance.mark()` |
| **Scroll Performance (FPS)** | 滚动流畅度 | > 30 FPS | > 55 FPS | Chrome DevTools `requestAnimationFrame` |
| **Select Interaction Time** | 选择疾病后响应时间 | < 300ms | < 100ms | `performance.measure()` |
| **Network Graph Render** | Cytoscape 图渲染时间 | < 3000ms | < 1500ms | Canvas ready time |
| **Memory Usage** | 页面内存占用 | < 200 MB | < 150 MB | `performance.memory` |

#### C. 用户体验指标 (Core Web Vitals)

| 指标 | 说明 | 基准目标 | 优化目标 | 测量方法 |
|------|------|----------|----------|----------|
| **LCP (Largest Contentful Paint)** | 最大内容绘制 | < 2.5s | < 1.8s | Web Vitals API |
| **FID (First Input Delay)** | 首次输入延迟 | < 100ms | < 50ms | Web Vitals API |
| **CLS (Cumulative Layout Shift)** | 累积布局偏移 | < 0.1 | < 0.05 | Web Vitals API |
| **TTI (Time to Interactive)** | 可交互时间 | < 3.5s | < 2.5s | Lighthouse |

#### D. E2E 断言预算（可通过环境变量覆盖）

上表是“优化目标”。实际跑 Playwright E2E 时，性能断言会受环境影响（dev server、CPU、缓存冷热）。
当前实现 `frontend/web/e2e/performance/disease-dropdown-performance.spec.ts` 支持通过环境变量覆盖预算（单位：毫秒，除非特别说明）：

| Env var | Default | 说明 |
|--------|---------|------|
| `BASE_URL` | `http://localhost:5173` | 前端地址 |
| `API_BASE_URL` | `http://localhost:8000` | 后端地址 |
| `E2E_DISEASE_OPTIONS_API_BUDGET_MS` | `3000` | `/api/v1/diseases/options` 响应预算 |
| `E2E_DISEASE_DROPDOWN_RENDER_BUDGET_MS` | `1500` | 下拉渲染预算 |
| `E2E_DISEASE_FLOW_BUDGET_MS` | `15000` | “打开页面→选择疾病→渲染网络图”的总预算 |
| `E2E_DISEASE_DROPDOWN_SCROLL_FPS_MIN` | `20` | 下拉滚动最低 FPS |
| `E2E_NETWORK_API_BUDGET_MS` | `12000` | 网络图相关 API 响应预算 |
| `E2E_NETWORK_RENDER_BUDGET_MS` | `12000` | 网络图渲染预算 |
| `E2E_MEMORY_LIMIT_MB` | `250` | 内存上限（MB） |
| `E2E_LCP_BUDGET_MS` | `4000` | LCP 预算 |
| `E2E_FID_BUDGET_MS` | `200` | FID 预算 |
| `E2E_CLS_BUDGET` | `0.25` | CLS 预算（分数） |

### 3.2 性能等级划分

| 等级 | 描述 | 响应时间范围 | 用户感知 |
|------|------|--------------|----------|
| **优秀 (Excellent)** | 即时响应 | < 200ms | 无感知延迟 |
| **良好 (Good)** | 流畅体验 | 200ms - 500ms | 轻微延迟但可接受 |
| **中等 (Fair)** | 可接受 | 500ms - 1000ms | 明显延迟 |
| **差 (Poor)** | 需要优化 | > 1000ms | 用户不满 |

---

## 4. 关键测试场景

### 4.1 场景 1: 疾病下拉选项加载性能

**测试目标**: 验证疾病列表 API 和前端渲染性能

**前置条件**:
- 清空浏览器缓存
- 数据库包含 > 500 条疾病记录
- 后端缓存层已部署 (优化后测试)

**测试步骤**:
```typescript
test('Scenario 1: Disease dropdown loading performance', async ({ page }) => {
  // 1. 清空缓存
  await page.context().clearCookies()
  await page.goto('about:blank')

  // 2. 记录 API 响应时间
  const apiStartTime = Date.now()
  const responsePromise = page.waitForResponse(
    resp => resp.url().includes('/api/v1/diseases') && resp.status() === 200
  )

  await page.goto('/network')

  const response = await responsePromise
  const apiResponseTime = Date.now() - apiStartTime

  // 3. 记录前端渲染时间
  const renderStartTime = Date.now()
  const diseaseSelect = page.locator('.ant-select').filter({ hasText: /Disease|疾病/ }).first()
  await diseaseSelect.waitFor({ state: 'visible' })
  await diseaseSelect.click()

  // 等待下拉选项渲染完成
  const dropdown = page.locator('.ant-select-dropdown:visible')
  await dropdown.waitFor({ state: 'visible' })
  const firstOption = dropdown.locator('.ant-select-item').first()
  await firstOption.waitFor({ state: 'visible' })

  const renderTime = Date.now() - renderStartTime

  // 4. 验证数据
  const data = await response.json()
  const totalItems = data.total
  const returnedItems = data.items?.length || 0

  // 5. 性能断言
  expect(apiResponseTime).toBeLessThan(1000) // 基准: 1s
  expect(renderTime).toBeLessThan(500) // 基准: 0.5s

  // 6. 记录指标
  console.log(`📊 Disease Dropdown Performance Metrics:`)
  console.log(`  - API Response Time: ${apiResponseTime}ms`)
  console.log(`  - Render Time: ${renderTime}ms`)
  console.log(`  - Total Items: ${totalItems}`)
  console.log(`  - Returned Items: ${returnedItems}`)
  console.log(`  - Payload Size: ${response.headers()['content-length']} bytes`)
})
```

**KPI 记录**:
- API Response Time (优化前 vs 优化后)
- Render Time (优化前 vs 优化后)
- Payload Size (优化前 vs 优化后)

---

### 4.2 场景 2: 大量选项滚动性能

**测试目标**: 验证 500+ 选项的虚拟滚动实现

**前置条件**:
- 疾病列表已加载
- Ant Design Select 组件已渲染

**测试步骤**:
```typescript
test('Scenario 2: Large options list scroll performance', async ({ page }) => {
  await page.goto('/network')

  // 打开疾病下拉框
  const diseaseSelect = page.locator('.ant-select').filter({ hasText: /Disease/ }).first()
  await diseaseSelect.click()

  const dropdown = page.locator('.ant-select-dropdown:visible')
  await dropdown.waitFor({ state: 'visible' })

  // 测量滚动性能 - 使用 Chrome DevTools Protocol
  const client = await page.context().newCDPSession(page)
  await client.send('Performance.enable')

  // 执行快速滚动
  const scrollStartTime = Date.now()

  for (let i = 0; i < 10; i++) {
    await dropdown.evaluate(el => {
      el.scrollTop += 500
    })
    await page.waitForTimeout(100)
  }

  const scrollDuration = Date.now() - scrollStartTime

  // 获取性能指标
  const metrics = await client.send('Performance.getMetrics')
  const jsHeapUsedSize = metrics.metrics.find(m => m.name === 'JSHeapUsedSize')?.value || 0

  console.log(`📊 Scroll Performance Metrics:`)
  console.log(`  - Total Scroll Duration: ${scrollDuration}ms`)
  console.log(`  - JS Heap Used: ${(jsHeapUsedSize / 1024 / 1024).toFixed(2)} MB`)

  // 性能断言: 滚动应该流畅，平均每次滚动 < 100ms
  expect(scrollDuration / 10).toBeLessThan(100)
})
```

**KPI 记录**:
- Average Scroll Time (ms)
- Frame Rate (FPS)
- Memory Usage (MB)

---

### 4.3 场景 3: 选择疾病后网络图渲染时间

**测试目标**: 验证端到端的性能体验

**前置条件**:
- 选择至少一个物种
- 有可用的疾病和 Ontology 数据

**测试步骤**:
```typescript
test('Scenario 3: Disease selection → Network graph rendering', async ({ page }) => {
  await page.goto('/network')
  await page.waitForLoadState('networkidle')

  // 1. 选择物种
  const speciesSelect = page.locator('.ant-select').first()
  await speciesSelect.click()
  await page.locator('.ant-select-dropdown:visible .ant-select-item').first().click()

  // 2. 选择疾病
  const diseaseSelect = page.locator('.ant-select').filter({ hasText: /Disease/ }).first()
  await diseaseSelect.click()

  const diseaseSelectStartTime = Date.now()
  await page.locator('.ant-select-dropdown:visible .ant-select-item').first().click()
  const diseaseSelectTime = Date.now() - diseaseSelectStartTime

  // 3. 选择 Ontology
  await page.waitForTimeout(500)
  const ontologySelect = page.locator('.ant-select').filter({ hasText: /Ontology/ }).first()
  await ontologySelect.click()
  await page.locator('.ant-select-dropdown:visible .ant-select-item').first().click()

  // 4. 点击查询按钮
  const queryButton = page.getByRole('button', { name: /Query|查询/ })

  const networkAPIStartTime = Date.now()
  const networkResponsePromise = page.waitForResponse(
    resp => resp.url().includes('/api/v1/network/disease') && resp.status() === 200,
    { timeout: 30000 }
  )

  await queryButton.click()

  // 等待 API 响应
  const networkResponse = await networkResponsePromise
  const networkAPITime = Date.now() - networkAPIStartTime

  // 5. 等待 Cytoscape 图表渲染完成
  const renderStartTime = Date.now()
  const canvas = page.locator('canvas').first()
  await canvas.waitFor({ state: 'visible', timeout: 15000 })

  // 等待图表渲染完成（检查 canvas 是否有内容）
  await page.waitForTimeout(1000)
  const renderTime = Date.now() - renderStartTime

  // 6. 验证图表数据
  const networkData = await networkResponse.json()
  const nodeCount = networkData.nodes?.length || 0
  const edgeCount = networkData.edges?.length || 0

  // 7. 总用户体验时间 (从选择疾病到图表渲染完成)
  const totalUserTime = diseaseSelectTime + networkAPITime + renderTime

  console.log(`📊 Network Graph Rendering Performance:`)
  console.log(`  - Disease Select Time: ${diseaseSelectTime}ms`)
  console.log(`  - Network API Time: ${networkAPITime}ms`)
  console.log(`  - Graph Render Time: ${renderTime}ms`)
  console.log(`  - Total User Experience Time: ${totalUserTime}ms`)
  console.log(`  - Nodes: ${nodeCount}, Edges: ${edgeCount}`)

  // 性能断言
  expect(networkAPITime).toBeLessThan(5000) // API 响应 < 5s
  expect(renderTime).toBeLessThan(3000) // 渲染 < 3s
  expect(totalUserTime).toBeLessThan(8000) // 总体验 < 8s
})
```

**KPI 记录**:
- Network API Response Time
- Graph Render Time
- Total User Experience Time
- Node/Edge Count

---

### 4.4 场景 4: 缓存层性能验证

**测试目标**: 验证后端缓存命中率和性能提升

**前置条件**:
- 后端已部署 Redis 或内存缓存
- 缓存 TTL 已配置 (建议 5 分钟)

**测试步骤**:
```typescript
test('Scenario 4: Cache layer performance verification', async ({ page }) => {
  const diseaseAPIUrl = 'http://localhost:8000/api/v1/diseases?page=1&page_size=500'

  // 1. 首次请求 (Cold Cache)
  await page.context().clearCookies()
  const coldStart = Date.now()
  const coldResponse = await page.request.get(diseaseAPIUrl)
  const coldTime = Date.now() - coldStart
  const coldCacheStatus = coldResponse.headers()['x-cache-status'] || 'UNKNOWN'

  // 2. 第二次请求 (Warm Cache)
  const warmStart = Date.now()
  const warmResponse = await page.request.get(diseaseAPIUrl)
  const warmTime = Date.now() - warmStart
  const warmCacheStatus = warmResponse.headers()['x-cache-status'] || 'UNKNOWN'

  // 3. 连续 10 次请求，统计缓存命中率
  const hits = []
  for (let i = 0; i < 10; i++) {
    const start = Date.now()
    const response = await page.request.get(diseaseAPIUrl)
    const time = Date.now() - start
    const status = response.headers()['x-cache-status'] || 'MISS'

    hits.push({ time, status })
  }

  const hitCount = hits.filter(h => h.status === 'HIT').length
  const hitRate = (hitCount / hits.length) * 100
  const avgHitTime = hits.filter(h => h.status === 'HIT')
    .reduce((sum, h) => sum + h.time, 0) / hitCount || 0

  console.log(`📊 Cache Performance Metrics:`)
  console.log(`  - Cold Cache Time: ${coldTime}ms (Status: ${coldCacheStatus})`)
  console.log(`  - Warm Cache Time: ${warmTime}ms (Status: ${warmCacheStatus})`)
  console.log(`  - Cache Hit Rate: ${hitRate.toFixed(2)}%`)
  console.log(`  - Average Hit Time: ${avgHitTime.toFixed(2)}ms`)
  console.log(`  - Performance Improvement: ${((coldTime - avgHitTime) / coldTime * 100).toFixed(2)}%`)

  // 性能断言
  expect(hitRate).toBeGreaterThan(80) // 缓存命中率 > 80%
  expect(avgHitTime).toBeLessThan(coldTime * 0.5) // 缓存响应时间至少快 50%
})
```

**KPI 记录**:
- Cold Cache Response Time
- Warm Cache Response Time
- Cache Hit Rate (%)
- Performance Improvement (%)

---

### 4.5 场景 5: 并发用户压力测试

**测试目标**: 模拟多用户并发访问，验证系统稳定性

**前置条件**:
- 后端缓存层已启用
- 数据库连接池已配置

**测试步骤**:
```typescript
test('Scenario 5: Concurrent users stress test', async ({ browser }) => {
  const concurrentUsers = 10 // 模拟 10 个并发用户

  const userSessions = await Promise.all(
    Array.from({ length: concurrentUsers }, async (_, i) => {
      const context = await browser.newContext()
      const page = await context.newPage()

      const startTime = Date.now()

      try {
        // 模拟用户行为: 加载页面 → 选择疾病 → 查询网络
        await page.goto('/network')
        await page.waitForLoadState('networkidle')

        // 选择物种
        const speciesSelect = page.locator('.ant-select').first()
        await speciesSelect.click()
        await page.locator('.ant-select-dropdown:visible .ant-select-item').first().click()

        // 选择疾病
        const diseaseSelect = page.locator('.ant-select').filter({ hasText: /Disease/ }).first()
        await diseaseSelect.click()
        await page.locator('.ant-select-dropdown:visible .ant-select-item').nth(i).click()

        // 选择 Ontology
        await page.waitForTimeout(300)
        const ontologySelect = page.locator('.ant-select').filter({ hasText: /Ontology/ }).first()
        await ontologySelect.click()
        await page.locator('.ant-select-dropdown:visible .ant-select-item').first().click()

        // 查询网络
        const queryButton = page.getByRole('button', { name: /Query/ })
        const networkResponsePromise = page.waitForResponse(
          resp => resp.url().includes('/api/v1/network/disease'),
          { timeout: 30000 }
        )

        await queryButton.click()
        await networkResponsePromise

        const totalTime = Date.now() - startTime

        return {
          userId: i + 1,
          success: true,
          totalTime,
          error: null
        }
      } catch (error) {
        return {
          userId: i + 1,
          success: false,
          totalTime: Date.now() - startTime,
          error: String(error)
        }
      } finally {
        await context.close()
      }
    })
  )

  // 统计结果
  const successCount = userSessions.filter(s => s.success).length
  const failureCount = userSessions.filter(s => !s.success).length
  const avgTime = userSessions.reduce((sum, s) => sum + s.totalTime, 0) / userSessions.length
  const maxTime = Math.max(...userSessions.map(s => s.totalTime))
  const minTime = Math.min(...userSessions.map(s => s.totalTime))

  console.log(`📊 Concurrent Users Stress Test Results:`)
  console.log(`  - Total Users: ${concurrentUsers}`)
  console.log(`  - Successful: ${successCount}`)
  console.log(`  - Failed: ${failureCount}`)
  console.log(`  - Average Time: ${avgTime.toFixed(2)}ms`)
  console.log(`  - Max Time: ${maxTime}ms`)
  console.log(`  - Min Time: ${minTime}ms`)

  // 性能断言
  expect(successCount).toBe(concurrentUsers) // 所有用户请求应该成功
  expect(avgTime).toBeLessThan(10000) // 平均响应时间 < 10s
})
```

**KPI 记录**:
- Success Rate (%)
- Average Response Time
- Max Response Time
- System Stability

---

## 5. 性能测试脚本框架

### 5.1 文件结构
```
frontend/web/e2e/
├── performance/
│   ├── disease-dropdown-performance.spec.ts
│   ├── network-graph-rendering.spec.ts
│   ├── cache-layer-performance.spec.ts
│   ├── stress-test.spec.ts
│   └── helpers/
│       ├── performanceMetrics.ts
│       ├── cacheValidation.ts
│       └── dataGenerators.ts
├── playwright.config.ts (更新配置)
└── PERFORMANCE_TEST_REPORT.md (自动生成)
```

### 5.2 通用性能测量工具类

```typescript
// frontend/web/e2e/performance/helpers/performanceMetrics.ts

import { Page, Response } from '@playwright/test'

export class PerformanceMetrics {
  private page: Page
  private metrics: Map<string, number> = new Map()

  constructor(page: Page) {
    this.page = page
  }

  // 测量 API 响应时间
  async measureAPIResponse(
    urlPattern: string | RegExp,
    action: () => Promise<void>
  ): Promise<{ response: Response; time: number; data: any }> {
    const startTime = Date.now()

    const responsePromise = this.page.waitForResponse(
      resp => {
        if (typeof urlPattern === 'string') {
          return resp.url().includes(urlPattern) && resp.status() === 200
        }
        return urlPattern.test(resp.url()) && resp.status() === 200
      },
      { timeout: 30000 }
    )

    await action()

    const response = await responsePromise
    const time = Date.now() - startTime
    const data = await response.json()

    this.metrics.set(`api_${urlPattern}`, time)

    return { response, time, data }
  }

  // 测量 DOM 渲染时间
  async measureRenderTime(
    selector: string,
    action: () => Promise<void>
  ): Promise<number> {
    const startTime = Date.now()

    await action()
    await this.page.locator(selector).waitFor({ state: 'visible' })

    const time = Date.now() - startTime
    this.metrics.set(`render_${selector}`, time)

    return time
  }

  // 使用 Performance API 测量
  async measureWithPerformanceAPI(
    name: string,
    action: () => Promise<void>
  ): Promise<number> {
    await this.page.evaluate((markName) => {
      performance.mark(`${markName}-start`)
    }, name)

    await action()

    const duration = await this.page.evaluate((markName) => {
      performance.mark(`${markName}-end`)
      performance.measure(
        markName,
        `${markName}-start`,
        `${markName}-end`
      )
      const measure = performance.getEntriesByName(markName)[0]
      return measure.duration
    }, name)

    this.metrics.set(`perf_${name}`, duration)
    return duration
  }

  // 获取 Web Vitals
  async getWebVitals(): Promise<{
    LCP: number
    FID: number
    CLS: number
    TTFB: number
  }> {
    return await this.page.evaluate(() => {
      return new Promise((resolve) => {
        let LCP = 0, FID = 0, CLS = 0, TTFB = 0

        // LCP
        new PerformanceObserver((list) => {
          const entries = list.getEntries()
          const lastEntry = entries[entries.length - 1]
          LCP = lastEntry.renderTime || lastEntry.loadTime
        }).observe({ entryTypes: ['largest-contentful-paint'] })

        // FID
        new PerformanceObserver((list) => {
          const entries = list.getEntries()
          FID = entries[0].processingStart - entries[0].startTime
        }).observe({ entryTypes: ['first-input'] })

        // CLS
        new PerformanceObserver((list) => {
          const entries = list.getEntries()
          entries.forEach((entry: any) => {
            if (!entry.hadRecentInput) {
              CLS += entry.value
            }
          })
        }).observe({ entryTypes: ['layout-shift'] })

        // TTFB
        const navigation = performance.getEntriesByType('navigation')[0] as any
        TTFB = navigation.responseStart - navigation.requestStart

        // 等待 3 秒收集指标
        setTimeout(() => {
          resolve({ LCP, FID, CLS, TTFB })
        }, 3000)
      })
    })
  }

  // 获取内存使用情况
  async getMemoryUsage(): Promise<{ usedJSHeapSize: number; totalJSHeapSize: number }> {
    return await this.page.evaluate(() => {
      if ('memory' in performance) {
        const mem = (performance as any).memory
        return {
          usedJSHeapSize: mem.usedJSHeapSize,
          totalJSHeapSize: mem.totalJSHeapSize
        }
      }
      return { usedJSHeapSize: 0, totalJSHeapSize: 0 }
    })
  }

  // 生成性能报告
  generateReport(): string {
    let report = `\n📊 Performance Metrics Report\n`
    report += `${'='.repeat(60)}\n`

    this.metrics.forEach((value, key) => {
      report += `  ${key.padEnd(40)}: ${value.toFixed(2)}ms\n`
    })

    report += `${'='.repeat(60)}\n`
    return report
  }

  // 导出 JSON 格式
  exportJSON(): Record<string, number> {
    return Object.fromEntries(this.metrics)
  }
}
```

### 5.3 使用示例

```typescript
// frontend/web/e2e/performance/disease-dropdown-performance.spec.ts

import { test, expect } from '@playwright/test'
import { PerformanceMetrics } from './helpers/performanceMetrics'

test.describe('Disease Dropdown Performance Tests', () => {
  test('should load disease options within performance budget', async ({ page }) => {
    const metrics = new PerformanceMetrics(page)

    // 测量 API 响应时间
    const { response, time: apiTime, data } = await metrics.measureAPIResponse(
      '/api/v1/diseases',
      async () => {
        await page.goto('/network')
        await page.waitForLoadState('networkidle')
      }
    )

    // 测量渲染时间
    const renderTime = await metrics.measureRenderTime(
      '.ant-select',
      async () => {
        const diseaseSelect = page.locator('.ant-select').filter({ hasText: /Disease/ }).first()
        await diseaseSelect.click()
      }
    )

    // 获取 Web Vitals
    const webVitals = await metrics.getWebVitals()

    // 性能断言
    expect(apiTime).toBeLessThan(1000)
    expect(renderTime).toBeLessThan(500)
    expect(webVitals.LCP).toBeLessThan(2500)

    // 打印报告
    console.log(metrics.generateReport())
    console.log(`\n🌐 Web Vitals:`)
    console.log(`  - LCP: ${webVitals.LCP.toFixed(2)}ms`)
    console.log(`  - FID: ${webVitals.FID.toFixed(2)}ms`)
    console.log(`  - CLS: ${webVitals.CLS.toFixed(4)}`)
    console.log(`  - TTFB: ${webVitals.TTFB.toFixed(2)}ms`)
  })
})
```

---

## 6. Playwright 配置优化

### 6.1 Performance-Specific Configuration

```typescript
// playwright.config.ts - 添加性能测试专用配置

export default defineConfig({
  // ... 现有配置 ...

  projects: [
    // 现有项目配置 ...

    // 新增: 性能测试专用项目
    {
      name: 'performance',
      testDir: './e2e/performance',
      timeout: 120000, // 性能测试需要更长超时
      use: {
        ...devices['Desktop Chrome'],
        // 禁用 throttling，测量真实性能
        launchOptions: {
          args: [
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox'
          ]
        },
        // 启用性能追踪
        trace: 'on',
        video: 'off', // 性能测试不需要视频
        screenshot: 'only-on-failure'
      }
    },

    // 新增: 网络限速测试 (模拟慢速网络)
    {
      name: 'performance-slow-3g',
      testDir: './e2e/performance',
      timeout: 180000,
      use: {
        ...devices['Desktop Chrome'],
        // 模拟 Slow 3G
        offline: false,
        // 使用 CDP 设置网络限速
        launchOptions: {
          args: ['--disable-blink-features=AutomationControlled']
        }
      }
    }
  ]
})
```

### 6.2 网络限速配置

```typescript
// frontend/web/e2e/performance/helpers/networkThrottling.ts

import { Page } from '@playwright/test'

export async function setNetworkThrottling(page: Page, profile: 'slow-3g' | 'fast-3g' | '4g' | 'none') {
  const client = await page.context().newCDPSession(page)

  const profiles = {
    'slow-3g': {
      offline: false,
      downloadThroughput: (500 * 1024) / 8, // 500 kbps
      uploadThroughput: (500 * 1024) / 8,
      latency: 400 // ms
    },
    'fast-3g': {
      offline: false,
      downloadThroughput: (1.6 * 1024 * 1024) / 8, // 1.6 Mbps
      uploadThroughput: (750 * 1024) / 8,
      latency: 150
    },
    '4g': {
      offline: false,
      downloadThroughput: (4 * 1024 * 1024) / 8, // 4 Mbps
      uploadThroughput: (3 * 1024 * 1024) / 8,
      latency: 50
    },
    'none': {
      offline: false,
      downloadThroughput: -1,
      uploadThroughput: -1,
      latency: 0
    }
  }

  await client.send('Network.emulateNetworkConditions', profiles[profile])
}
```

---

## 7. 性能数据收集与可视化

### 7.1 自动生成性能报告

```typescript
// frontend/web/e2e/performance/helpers/reportGenerator.ts

import fs from 'fs'
import path from 'path'

export interface PerformanceTestResult {
  testName: string
  timestamp: string
  apiResponseTime: number
  renderTime: number
  totalUserTime: number
  webVitals: {
    LCP: number
    FID: number
    CLS: number
    TTFB: number
  }
  memoryUsage: {
    usedJSHeapSize: number
    totalJSHeapSize: number
  }
  metadata: {
    nodeCount?: number
    edgeCount?: number
    payloadSize?: number
    cacheStatus?: string
  }
}

export class PerformanceReportGenerator {
  private results: PerformanceTestResult[] = []

  addResult(result: PerformanceTestResult) {
    this.results.push(result)
  }

  generateMarkdownReport(): string {
    const report = `
# Performance Test Report

**Generated**: ${new Date().toISOString()}

## Summary

| Test Name | API Time | Render Time | Total Time | LCP | CLS |
|-----------|----------|-------------|------------|-----|-----|
${this.results.map(r => `| ${r.testName} | ${r.apiResponseTime.toFixed(2)}ms | ${r.renderTime.toFixed(2)}ms | ${r.totalUserTime.toFixed(2)}ms | ${r.webVitals.LCP.toFixed(2)}ms | ${r.webVitals.CLS.toFixed(4)} |`).join('\n')}

## Detailed Results

${this.results.map(r => this.generateDetailedSection(r)).join('\n\n')}
`
    return report
  }

  private generateDetailedSection(result: PerformanceTestResult): string {
    return `
### ${result.testName}

**Timestamp**: ${result.timestamp}

**API Performance**:
- Response Time: ${result.apiResponseTime.toFixed(2)}ms
- Payload Size: ${result.metadata.payloadSize ? (result.metadata.payloadSize / 1024).toFixed(2) + ' KB' : 'N/A'}
- Cache Status: ${result.metadata.cacheStatus || 'N/A'}

**Frontend Performance**:
- Render Time: ${result.renderTime.toFixed(2)}ms
- Total User Time: ${result.totalUserTime.toFixed(2)}ms

**Web Vitals**:
- LCP (Largest Contentful Paint): ${result.webVitals.LCP.toFixed(2)}ms
- FID (First Input Delay): ${result.webVitals.FID.toFixed(2)}ms
- CLS (Cumulative Layout Shift): ${result.webVitals.CLS.toFixed(4)}
- TTFB (Time to First Byte): ${result.webVitals.TTFB.toFixed(2)}ms

**Memory Usage**:
- JS Heap Used: ${(result.memoryUsage.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB
- JS Heap Total: ${(result.memoryUsage.totalJSHeapSize / 1024 / 1024).toFixed(2)} MB

**Network Data**:
- Nodes: ${result.metadata.nodeCount || 'N/A'}
- Edges: ${result.metadata.edgeCount || 'N/A'}
`
  }

  saveReport(filename: string) {
    const reportPath = path.join(__dirname, '../../', filename)
    fs.writeFileSync(reportPath, this.generateMarkdownReport())
    console.log(`📄 Report saved to: ${reportPath}`)
  }

  saveJSON(filename: string) {
    const jsonPath = path.join(__dirname, '../../', filename)
    fs.writeFileSync(jsonPath, JSON.stringify(this.results, null, 2))
    console.log(`📊 JSON data saved to: ${jsonPath}`)
  }
}
```

### 7.2 性能趋势分析 (CI/CD 集成)

```json
// package.json - 添加性能测试命令

{
  "scripts": {
    "test:e2e": "playwright test",
    "test:performance": "playwright test --project=performance",
    "test:performance:report": "playwright test --project=performance --reporter=html,json",
    "test:performance:baseline": "playwright test --project=performance && node scripts/saveBaseline.js",
    "test:performance:compare": "playwright test --project=performance && node scripts/compareBaseline.js"
  }
}
```

---

## 8. 性能优化建议 (基于测试结果)

### 8.1 后端优化建议

| 问题 | 优化方案 | 预期提升 | 优先级 |
|------|----------|----------|--------|
| 疾病列表 API 慢 | 添加 Redis 缓存 (TTL 5min) | 80% ↓ | P0 |
| 数据库查询慢 | 添加索引 (trait_id, ontology_id) | 50% ↓ | P0 |
| Payload 过大 | 分页加载 + 懒加载 | 减少 70% | P1 |
| 无缓存头 | 添加 `Cache-Control` 响应头 | 客户端缓存 | P1 |
| 网络数据慢 | 物化视图预计算 (已实现) | 90% ↓ | P0 |

### 8.2 前端优化建议

| 问题 | 优化方案 | 预期提升 | 优先级 |
|------|----------|----------|--------|
| 大量选项渲染卡顿 | 使用虚拟滚动 (Ant Design 内置) | 70% ↓ | P0 |
| 重复渲染 | React.memo + useMemo 优化 | 40% ↓ | P1 |
| 网络图渲染慢 | Web Worker 渲染 Cytoscape | 50% ↓ | P2 |
| 内存泄漏 | 清理 Cytoscape 实例 (已实现) | 防止崩溃 | P0 |
| Bundle 过大 | 代码分割 + 动态导入 | 减少 30% | P2 |

### 8.3 数据库优化建议

```sql
-- 添加性能关键索引
CREATE INDEX idx_trait_gene_associations_trait_id ON trait_gene_associations(trait_id);
CREATE INDEX idx_trait_gene_associations_ontology_id ON trait_gene_associations(ontology_id);
CREATE INDEX idx_genes_core_id ON genes(core_id);

-- 刷新物化视图统计信息
ANALYZE mv_lncrna_chipseq_overlaps;
```

---

## 9. 持续性能监控

### 9.1 CI/CD 集成

```yaml
# .github/workflows/performance-tests.yml

name: Performance Tests

on:
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *' # 每天凌晨 2 点运行

jobs:
  performance-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: cd frontend/web && npm ci

      - name: Install Playwright browsers
        run: cd frontend/web && npx playwright install --with-deps chromium

      - name: Start backend
        run: |
          cd frontend/backend
          python3 -m venv venv
          source venv/bin/activate
          python3 -m pip install -r requirements.txt -c constraints.txt
          python3 -m uvicorn main:app --port 8000 &
          sleep 10

      - name: Start frontend
        run: |
          cd frontend/web
          npm run dev &
          sleep 10

      - name: Run performance tests
        run: cd frontend/web && npm run test:performance

      - name: Upload performance report
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: performance-report
          path: frontend/web/e2e/PERFORMANCE_TEST_REPORT.md

      - name: Comment PR with results
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs')
            const report = fs.readFileSync('frontend/web/e2e/PERFORMANCE_TEST_REPORT.md', 'utf8')
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## 📊 Performance Test Results\n\n${report}`
            })
```

### 9.2 性能监控告警

```typescript
// frontend/web/e2e/performance/helpers/performanceThresholds.ts

export const PERFORMANCE_THRESHOLDS = {
  API: {
    DISEASE_LIST_MAX: 1000, // ms
    NETWORK_DATA_MAX: 5000, // ms
    CACHE_HIT_MIN: 80 // %
  },
  FRONTEND: {
    DROPDOWN_RENDER_MAX: 500, // ms
    GRAPH_RENDER_MAX: 3000, // ms
    MEMORY_MAX: 200 * 1024 * 1024 // 200 MB
  },
  WEB_VITALS: {
    LCP_MAX: 2500, // ms
    FID_MAX: 100, // ms
    CLS_MAX: 0.1 // score
  }
}

export function checkThresholds(metrics: any): { passed: boolean; violations: string[] } {
  const violations: string[] = []

  if (metrics.apiResponseTime > PERFORMANCE_THRESHOLDS.API.DISEASE_LIST_MAX) {
    violations.push(`API response time ${metrics.apiResponseTime}ms exceeds threshold ${PERFORMANCE_THRESHOLDS.API.DISEASE_LIST_MAX}ms`)
  }

  if (metrics.renderTime > PERFORMANCE_THRESHOLDS.FRONTEND.DROPDOWN_RENDER_MAX) {
    violations.push(`Render time ${metrics.renderTime}ms exceeds threshold ${PERFORMANCE_THRESHOLDS.FRONTEND.DROPDOWN_RENDER_MAX}ms`)
  }

  if (metrics.webVitals.LCP > PERFORMANCE_THRESHOLDS.WEB_VITALS.LCP_MAX) {
    violations.push(`LCP ${metrics.webVitals.LCP}ms exceeds threshold ${PERFORMANCE_THRESHOLDS.WEB_VITALS.LCP_MAX}ms`)
  }

  return {
    passed: violations.length === 0,
    violations
  }
}
```

---

## 10. 执行计划

### 10.1 Phase 1: 建立基准 (Week 1)
- [ ] 实现 5 个核心性能测试场景
- [ ] 在优化前运行所有测试，记录基准数据
- [ ] 生成初始性能报告 (`PERFORMANCE_BASELINE_REPORT.md`)

### 10.2 Phase 2: 后端优化 (Week 2)
- [ ] 部署 Redis 缓存层
- [ ] 添加数据库索引
- [ ] 优化 API 响应头 (Cache-Control, ETag)
- [ ] 运行性能测试验证优化效果

### 10.3 Phase 3: 前端优化 (Week 3)
- [ ] 实现虚拟滚动 (如果 Ant Design Select 未内置)
- [ ] 优化 React 组件渲染 (memo, useMemo, useCallback)
- [ ] 优化 Cytoscape 图表渲染
- [ ] 运行性能测试验证优化效果

### 10.4 Phase 4: 持续监控 (Week 4)
- [ ] 集成 CI/CD 性能测试
- [ ] 设置性能告警阈值
- [ ] 建立性能趋势仪表板
- [ ] 编写性能优化最佳实践文档

---

## 11. 成功标准

### 11.1 性能提升目标

| 指标 | 优化前基准 | 优化后目标 | 提升幅度 |
|------|------------|------------|----------|
| 疾病 API 响应时间 | 1000ms | < 200ms | 80% ↓ |
| 下拉框渲染时间 | 500ms | < 200ms | 60% ↓ |
| 网络图渲染时间 | 3000ms | < 1500ms | 50% ↓ |
| 缓存命中率 | 0% | > 80% | N/A |
| 总用户体验时间 | 8000ms | < 3000ms | 63% ↓ |

### 11.2 验收标准
- ✅ 所有性能测试通过 (无 threshold 违规)
- ✅ 性能报告显示明显提升 (> 50%)
- ✅ 无性能回归 (CI/CD 持续监控)
- ✅ 用户体验指标达标 (LCP < 2.5s, FID < 100ms, CLS < 0.1)

---

## 12. 附录

### 12.1 参考资料
- [Playwright Performance Testing Guide](https://playwright.dev/docs/api/class-page#page-evaluate)
- [Web Vitals Documentation](https://web.dev/vitals/)
- [Chrome DevTools Protocol - Performance](https://chromedevtools.github.io/devtools-protocol/tot/Performance/)
- [Ant Design Performance Optimization](https://ant.design/docs/react/practical-projects#Performance-Optimization)

### 12.2 工具清单
- Playwright (E2E 测试)
- Chrome DevTools Protocol (性能分析)
- Web Vitals API (用户体验指标)
- Redis (后端缓存)
- PostgreSQL EXPLAIN ANALYZE (数据库查询优化)

---

**文档版本**: v1.0
**作者**: Claude Code (Elite Frontend Testing Specialist)
**日期**: 2025-12-10
**状态**: 待审核
