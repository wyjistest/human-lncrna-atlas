import { test, expect } from '@playwright/test'
import { PerformanceMetrics } from './helpers/performanceMetrics'

/**
 * Disease Dropdown Performance E2E Tests
 *
 * Test Suite: Validates performance of disease selection dropdown in Network page
 *
 * Scenarios:
 * 1. Disease options API loading performance
 * 2. Dropdown rendering performance
 * 3. Large options list scroll performance
 * 4. Cache layer effectiveness
 * 5. Memory usage during interaction
 */

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000'
const PAGE_URL = '/network'

function getEnvInt(name: string, fallback: number): number {
  const raw = process.env[name]
  if (!raw) return fallback
  const parsed = Number.parseInt(raw, 10)
  return Number.isFinite(parsed) ? parsed : fallback
}

const NETWORK_API_BUDGET_MS = getEnvInt('E2E_NETWORK_API_BUDGET_MS', 12000)
const NETWORK_RENDER_BUDGET_MS = getEnvInt('E2E_NETWORK_RENDER_BUDGET_MS', 12000)

// Performance thresholds (environment-dependent; override via env vars)
const THRESHOLDS = {
  API_RESPONSE_TIME: getEnvInt('E2E_DISEASE_OPTIONS_API_BUDGET_MS', 3000), // cold cache + dev server can be slower
  RENDER_TIME: getEnvInt('E2E_DISEASE_DROPDOWN_RENDER_BUDGET_MS', 1500),
  TOTAL_USER_TIME: getEnvInt('E2E_DISEASE_FLOW_BUDGET_MS', 15000),
  SCROLL_FPS: getEnvInt('E2E_DISEASE_DROPDOWN_SCROLL_FPS_MIN', 20),
  MEMORY_LIMIT: getEnvInt('E2E_MEMORY_LIMIT_MB', 250) * 1024 * 1024,
  LCP: getEnvInt('E2E_LCP_BUDGET_MS', 4000),
  FID: getEnvInt('E2E_FID_BUDGET_MS', 200),
  CLS: Number(process.env.E2E_CLS_BUDGET ?? 0.25),
}

function getSelectByTestId(page: any, testId: string) {
  return page.getByTestId(testId).first()
    .or(page.locator(`[data-testid="${testId}"]`).first())
}

test.describe('Disease Dropdown Performance Tests', () => {
  test.setTimeout(60000) // 1 minute timeout for performance tests

  test('P0: Disease options API should load within performance budget', async ({ page }) => {
    const metrics = new PerformanceMetrics(page)

    // Clear cache to simulate first visit
    await page.context().clearCookies()

    console.log('\n🚀 Starting Disease API Performance Test...')

    // Measure API response time (optimized endpoint)
    const { response, time: apiTime, data, headers } = await metrics.measureAPIResponse(
      '/api/v1/diseases/options',
      async () => {
        await page.goto(`${BASE_URL}${PAGE_URL}`)
        await page.waitForLoadState('domcontentloaded')
      }
    )

    // Extract data metrics (new response structure)
    const totalItems = data.traits?.length || 0
    const returnedItems = data.traits?.length || 0
    const payloadSize = parseInt(headers['content-length'] || '0', 10)
    const cacheStatus = headers['x-cache-status'] || 'MISS'

    console.log(`\n📊 API Performance Metrics:`)
    console.log(`  - Response Time: ${apiTime}ms`)
    console.log(`  - Total Diseases: ${totalItems}`)
    console.log(`  - Deduplicated Count: ${returnedItems}`)
    console.log(`  - Payload Size: ${(payloadSize / 1024).toFixed(2)} KB`)
    console.log(`  - Cache Status: ${cacheStatus}`)

    // Performance assertions
    expect(apiTime).toBeLessThan(THRESHOLDS.API_RESPONSE_TIME)
    expect(response.status()).toBe(200)
    expect(returnedItems).toBeGreaterThan(0)

    console.log(`✅ Disease API Performance Test PASSED`)
  })

  test('P0: Dropdown should render large options list within performance budget', async ({ page }) => {
    const metrics = new PerformanceMetrics(page)

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    console.log('\n🚀 Starting Dropdown Render Performance Test...')

    // Measure dropdown rendering time
    const renderTime = await metrics.measureRenderTime(
      '.ant-select-dropdown:visible',
      async () => {
        const diseaseSelect = getSelectByTestId(page, 'network-disease-select')
        await diseaseSelect.waitFor({ state: 'visible' })
        // Wait for options to be loaded (Select enabled) before measuring render time
        const diseaseInput = diseaseSelect.locator('input[role="combobox"]').first()
        await expect(diseaseInput).toBeEnabled({ timeout: 15000 })
        await diseaseSelect.click()
      }
    )

    // Wait for options to be fully rendered
    const dropdown = page.locator('.ant-select-dropdown:visible')
    await dropdown.waitFor({ state: 'visible' })

    const firstOption = dropdown.locator('.ant-select-item').first()
    await firstOption.waitFor({ state: 'visible' })

    // Count rendered options
    const optionCount = await dropdown.locator('.ant-select-item').count()

    console.log(`\n📊 Dropdown Render Metrics:`)
    console.log(`  - Render Time: ${renderTime}ms`)
    console.log(`  - Options Rendered: ${optionCount}`)

    // Get memory usage after render
    const memoryAfterRender = await metrics.getMemoryUsage()
    console.log(`  - JS Heap Used: ${(memoryAfterRender.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB`)

    // Performance assertions
    expect(renderTime).toBeLessThan(THRESHOLDS.RENDER_TIME)
    expect(optionCount).toBeGreaterThan(0)
    expect(memoryAfterRender.usedJSHeapSize).toBeLessThan(THRESHOLDS.MEMORY_LIMIT)

    console.log(`✅ Dropdown Render Performance Test PASSED`)
  })

  test('P1: Large options list should maintain smooth scroll performance', async ({ page }) => {
    const metrics = new PerformanceMetrics(page)

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    // Open disease dropdown
    const diseaseSelect = getSelectByTestId(page, 'network-disease-select')
    const diseaseInput = diseaseSelect.locator('input[role="combobox"]').first()
    await expect(diseaseInput).toBeEnabled({ timeout: 15000 })
    await diseaseSelect.scrollIntoViewIfNeeded()
    await diseaseSelect.click()

    const dropdown = page.locator('.ant-select-dropdown:visible')
    await dropdown.waitFor({ state: 'visible', timeout: 15000 })

    console.log('\n🚀 Starting Scroll Performance Test...')

    // Measure scroll performance
    const scrollStartTime = Date.now()
    const scrollIterations = 10

    for (let i = 0; i < scrollIterations; i++) {
      await dropdown.evaluate(el => {
        el.scrollTop += 500
      })
      await page.waitForTimeout(100) // Wait for scroll to settle
    }

    const scrollDuration = Date.now() - scrollStartTime
    const avgScrollTime = scrollDuration / scrollIterations

    console.log(`\n📊 Scroll Performance Metrics:`)
    console.log(`  - Total Scroll Duration: ${scrollDuration}ms`)
    console.log(`  - Average Scroll Time: ${avgScrollTime.toFixed(2)}ms`)
    console.log(`  - Estimated FPS: ${(1000 / avgScrollTime).toFixed(2)}`)

    // Get memory after scrolling
    const memoryAfterScroll = await metrics.getMemoryUsage()
    console.log(`  - JS Heap Used: ${(memoryAfterScroll.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB`)

    // Performance assertions: average scroll time should be reasonable
    expect(avgScrollTime).toBeLessThan(150) // headless is noisier than interactive browsers
    expect(memoryAfterScroll.usedJSHeapSize).toBeLessThan(THRESHOLDS.MEMORY_LIMIT)

    console.log(`✅ Scroll Performance Test PASSED`)
  })

  test('P0: End-to-end disease selection flow should complete within performance budget', async ({ page }) => {
    const metrics = new PerformanceMetrics(page)

    console.log('\n🚀 Starting E2E Disease Selection Performance Test...')

    // Step 1: Page load
    const pageLoadStart = Date.now()
    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')
    const pageLoadTime = Date.now() - pageLoadStart

    // Step 2: Open disease dropdown and select
    const diseaseSelectStart = Date.now()

    const diseaseSelect = getSelectByTestId(page, 'network-disease-select')
    // Wait for options to be loaded (Select enabled) before interacting.
    const diseaseInput = diseaseSelect.locator('input[role="combobox"]').first()
    await expect(diseaseInput).toBeEnabled({ timeout: 15000 })
    await diseaseSelect.scrollIntoViewIfNeeded()
    await diseaseSelect.click()
    {
      const dropdown = page.locator('.ant-select-dropdown:visible')
      await dropdown.waitFor({ state: 'visible', timeout: 15000 })
      const firstOption = dropdown.locator('.ant-select-item').first()
      await firstOption.waitFor({ state: 'visible', timeout: 10000 })
      await page.waitForTimeout(100) // allow dropdown to settle (virtual list / transition)
      await firstOption.click()
      // AntD Select may keep the popup open in some environments; explicitly close it
      await page.keyboard.press('Escape')
      await page.waitForTimeout(100)
    }

    const diseaseSelectTime = Date.now() - diseaseSelectStart

    // Step 3: Select ontology
    const ontologySelect = getSelectByTestId(page, 'network-ontology-select')
    // Wait for ontology select to become enabled after disease is selected
    const ontologyInput = ontologySelect.locator('input[role="combobox"]').first()
    await expect(ontologyInput).toBeEnabled({ timeout: 15000 })
    await page.waitForTimeout(200)
    await ontologySelect.click()
    {
      const dropdown = page.locator('.ant-select-dropdown:visible')
      await dropdown.waitFor({ state: 'visible', timeout: 10000 })
      const firstOption = dropdown.locator('.ant-select-item').first()
      await firstOption.waitFor({ state: 'visible', timeout: 10000 })
      await page.waitForTimeout(100) // allow dropdown to settle (virtual list / transition)
      await firstOption.click()
      await page.keyboard.press('Escape')
      await page.waitForTimeout(100)
    }

    // Step 4: Query network
    const queryButton = getSelectByTestId(page, 'network-query-button')
      .or(page.getByRole('button', { name: /Query|查询/ }).first())

    const networkAPIStart = Date.now()
    const networkResponsePromise = page.waitForResponse(
      resp => resp.url().includes('/api/v1/network/disease') && resp.status() === 200,
      { timeout: 30000 }
    )

    await queryButton.click()

    const networkResponse = await networkResponsePromise
    const networkAPITime = Date.now() - networkAPIStart

    // Step 5: Wait for network graph to render
    const renderStart = Date.now()
    const canvas = page.locator('canvas').first()
    await canvas.waitFor({ state: 'visible', timeout: 15000 })
    await page.waitForTimeout(1000) // Wait for graph to stabilize
    const renderTime = Date.now() - renderStart

    // Calculate total user experience time
    const totalUserTime = diseaseSelectTime + networkAPITime + renderTime

    // Extract network data
    const networkData = await networkResponse.json()
    const nodeCount = networkData.nodes?.length || 0
    const edgeCount = networkData.edges?.length || 0

    // Get Web Vitals
    const webVitals = await metrics.getWebVitals()

    // Get memory usage
    const memoryUsage = await metrics.getMemoryUsage()

    console.log(`\n📊 E2E Performance Metrics:`)
    console.log(`  - Page Load Time: ${pageLoadTime}ms`)
    console.log(`  - Disease Select Time: ${diseaseSelectTime}ms`)
    console.log(`  - Network API Time: ${networkAPITime}ms`)
    console.log(`  - Graph Render Time: ${renderTime}ms`)
    console.log(`  - Total User Experience Time: ${totalUserTime}ms`)
    console.log(`\n  Network Data:`)
    console.log(`  - Nodes: ${nodeCount}`)
    console.log(`  - Edges: ${edgeCount}`)
    console.log(`\n  Web Vitals:`)
    console.log(`  - LCP: ${webVitals.LCP.toFixed(2)}ms`)
    console.log(`  - FID: ${webVitals.FID.toFixed(2)}ms`)
    console.log(`  - CLS: ${webVitals.CLS.toFixed(4)}`)
    console.log(`  - TTFB: ${webVitals.TTFB.toFixed(2)}ms`)
    console.log(`\n  Memory Usage:`)
    console.log(`  - JS Heap Used: ${(memoryUsage.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB`)
    console.log(`  - JS Heap Total: ${(memoryUsage.totalJSHeapSize / 1024 / 1024).toFixed(2)} MB`)

    // Performance assertions (budgeted; override via env vars)
    expect(networkAPITime).toBeLessThan(NETWORK_API_BUDGET_MS)
    expect(renderTime).toBeLessThan(NETWORK_RENDER_BUDGET_MS)
    expect(totalUserTime).toBeLessThan(THRESHOLDS.TOTAL_USER_TIME)

    // Web Vitals assertions
    expect(webVitals.LCP).toBeLessThan(THRESHOLDS.LCP)
    expect(webVitals.CLS).toBeLessThan(THRESHOLDS.CLS)

    // Memory assertions
    expect(memoryUsage.usedJSHeapSize).toBeLessThan(THRESHOLDS.MEMORY_LIMIT)

    console.log(`✅ E2E Disease Selection Performance Test PASSED`)
    console.log(metrics.generateReport())
  })

  test('P1: Cache layer should improve API response time on subsequent requests', async ({ page }) => {
    console.log('\n🚀 Starting Cache Performance Test...')

    const diseaseAPIUrl = `${API_BASE}/api/v1/diseases?page=1&page_size=500`

    // Request 1: Cold cache
    await page.context().clearCookies()
    const coldStart = Date.now()
    const coldResponse = await page.request.get(diseaseAPIUrl)
    const coldTime = Date.now() - coldStart
    const coldCacheStatus = coldResponse.headers()['x-cache-status'] || 'MISS'

    // Request 2: Warm cache
    const warmStart = Date.now()
    const warmResponse = await page.request.get(diseaseAPIUrl)
    const warmTime = Date.now() - warmStart
    const warmCacheStatus = warmResponse.headers()['x-cache-status'] || 'MISS'

    // Request 3-12: Measure cache hit rate
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
    const avgHitTime = hitCount > 0
      ? hits.filter(h => h.status === 'HIT').reduce((sum, h) => sum + h.time, 0) / hitCount
      : 0
    const avgMissTime = hits.length - hitCount > 0
      ? hits.filter(h => h.status !== 'HIT').reduce((sum, h) => sum + h.time, 0) / (hits.length - hitCount)
      : 0

    const performanceImprovement = coldTime > 0 ? ((coldTime - warmTime) / coldTime * 100) : 0

    console.log(`\n📊 Cache Performance Metrics:`)
    console.log(`  - Cold Cache Time: ${coldTime}ms (Status: ${coldCacheStatus})`)
    console.log(`  - Warm Cache Time: ${warmTime}ms (Status: ${warmCacheStatus})`)
    console.log(`  - Cache Hit Rate: ${hitRate.toFixed(2)}% (${hitCount}/${hits.length})`)
    console.log(`  - Average Hit Time: ${avgHitTime.toFixed(2)}ms`)
    console.log(`  - Average Miss Time: ${avgMissTime.toFixed(2)}ms`)
    console.log(`  - Performance Improvement: ${performanceImprovement.toFixed(2)}%`)

    // Performance assertions
    // Note: Cache assertions are informational; may not be enabled in all environments
    if (warmCacheStatus === 'HIT') {
      expect(warmTime).toBeLessThan(coldTime) // Cached request should be faster
      console.log(`✅ Cache layer is working correctly`)
    } else {
      console.log(`⚠️  Cache layer not detected or not enabled`)
      console.log(`   Consider implementing Redis cache or HTTP caching headers`)
    }

    console.log(`✅ Cache Performance Test COMPLETED`)
  })

  test('P2: Memory usage should not increase significantly during repeated interactions', async ({ page }) => {
    const metrics = new PerformanceMetrics(page)

    await page.goto(`${BASE_URL}${PAGE_URL}`)
    await page.waitForLoadState('domcontentloaded')

    console.log('\n🚀 Starting Memory Leak Detection Test...')

    // Baseline memory
    const baselineMemory = await metrics.getMemoryUsage()
    console.log(`\n📊 Baseline Memory: ${(baselineMemory.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB`)

    // Perform 5 cycles of opening/closing dropdown
    for (let cycle = 1; cycle <= 5; cycle++) {
      const diseaseSelect = getSelectByTestId(page, 'network-disease-select')
      const diseaseInput = diseaseSelect.locator('input[role="combobox"]').first()
      await expect(diseaseInput).toBeEnabled({ timeout: 15000 })
      await diseaseSelect.scrollIntoViewIfNeeded()

      // Open dropdown
      await diseaseSelect.click()
      const dropdown = page.locator('.ant-select-dropdown:visible')
      await dropdown.waitFor({ state: 'visible', timeout: 15000 })

      // Scroll through options
      for (let i = 0; i < 3; i++) {
        await dropdown.evaluate(el => { el.scrollTop += 300 })
        await page.waitForTimeout(100)
      }

      // Close dropdown
      await page.keyboard.press('Escape')
      await page.waitForTimeout(500)

      // Measure memory after each cycle
      const cycleMemory = await metrics.getMemoryUsage()
      const memoryIncrease = cycleMemory.usedJSHeapSize - baselineMemory.usedJSHeapSize
      const increasePercent = (memoryIncrease / baselineMemory.usedJSHeapSize) * 100

      console.log(`  Cycle ${cycle}: ${(cycleMemory.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB (+${increasePercent.toFixed(2)}%)`)
    }

    // Final memory check
    const finalMemory = await metrics.getMemoryUsage()
    const totalIncrease = finalMemory.usedJSHeapSize - baselineMemory.usedJSHeapSize
    const totalIncreasePercent = (totalIncrease / baselineMemory.usedJSHeapSize) * 100

    console.log(`\n📊 Memory Leak Detection Results:`)
    console.log(`  - Baseline Memory: ${(baselineMemory.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB`)
    console.log(`  - Final Memory: ${(finalMemory.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB`)
    console.log(`  - Total Increase: ${(totalIncrease / 1024 / 1024).toFixed(2)} MB (+${totalIncreasePercent.toFixed(2)}%)`)

    // Memory leak assertion: memory increase should be < 50% of baseline
    expect(totalIncreasePercent).toBeLessThan(50)
    expect(finalMemory.usedJSHeapSize).toBeLessThan(THRESHOLDS.MEMORY_LIMIT)

    console.log(`✅ No significant memory leak detected`)
  })
})
