/**
 * Performance Metrics Utility Class
 *
 * Provides comprehensive performance measurement capabilities for Playwright E2E tests.
 * Supports API timing, rendering metrics, Web Vitals, and memory profiling.
 */

import { Page, Response } from '@playwright/test'

export interface WebVitals {
  LCP: number  // Largest Contentful Paint
  FID: number  // First Input Delay
  CLS: number  // Cumulative Layout Shift
  TTFB: number // Time to First Byte
}

export interface MemoryUsage {
  usedJSHeapSize: number
  totalJSHeapSize: number
  jsHeapSizeLimit: number
}

export class PerformanceMetrics {
  private page: Page
  private metrics: Map<string, number> = new Map()

  constructor(page: Page) {
    this.page = page
  }

  /**
   * Measure API response time
   *
   * @param urlPattern - URL pattern to match (string or RegExp)
   * @param action - Action that triggers the API call
   * @returns Response data with timing information
   */
  async measureAPIResponse(
    urlPattern: string | RegExp,
    action: () => Promise<void>
  ): Promise<{ response: Response; time: number; data: any; headers: Record<string, string> }> {
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
    const data = await response.json().catch(() => ({}))
    const headers = response.headers()

    const metricKey = typeof urlPattern === 'string' ? `api_${urlPattern}` : 'api_regex_match'
    this.metrics.set(metricKey, time)

    return { response, time, data, headers }
  }

  /**
   * Measure DOM element rendering time
   *
   * @param selector - CSS selector to wait for
   * @param action - Action that triggers the render
   * @returns Render time in milliseconds
   */
  async measureRenderTime(
    selector: string,
    action: () => Promise<void>
  ): Promise<number> {
    const startTime = Date.now()

    await action()
    await this.page.locator(selector).waitFor({ state: 'visible', timeout: 30000 })

    const time = Date.now() - startTime
    this.metrics.set(`render_${selector}`, time)

    return time
  }

  /**
   * Measure performance using browser Performance API
   *
   * @param name - Metric name
   * @param action - Action to measure
   * @returns Duration in milliseconds
   */
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
      performance.clearMarks()
      performance.clearMeasures()
      return measure?.duration || 0
    }, name)

    this.metrics.set(`perf_${name}`, duration)
    return duration
  }

  /**
   * Get Web Vitals metrics
   *
   * @returns Web Vitals data (LCP, FID, CLS, TTFB)
   */
  async getWebVitals(): Promise<WebVitals> {
    return await this.page.evaluate(() => {
      return new Promise<WebVitals>((resolve) => {
        const vitals: WebVitals = { LCP: 0, FID: 0, CLS: 0, TTFB: 0 }

        // LCP - Largest Contentful Paint
        try {
          new PerformanceObserver((list) => {
            const entries = list.getEntries()
            if (entries.length > 0) {
              const lastEntry = entries[entries.length - 1] as any
              vitals.LCP = lastEntry.renderTime || lastEntry.loadTime || 0
            }
          }).observe({ entryTypes: ['largest-contentful-paint'], buffered: true })
        } catch (e) {
          console.warn('LCP measurement not supported')
        }

        // FID - First Input Delay
        try {
          new PerformanceObserver((list) => {
            const entries = list.getEntries()
            if (entries.length > 0) {
              const firstEntry = entries[0] as any
              vitals.FID = (firstEntry.processingStart || 0) - (firstEntry.startTime || 0)
            }
          }).observe({ entryTypes: ['first-input'], buffered: true })
        } catch (e) {
          console.warn('FID measurement not supported')
        }

        // CLS - Cumulative Layout Shift
        try {
          new PerformanceObserver((list) => {
            const entries = list.getEntries()
            entries.forEach((entry: any) => {
              if (!entry.hadRecentInput) {
                vitals.CLS += entry.value || 0
              }
            })
          }).observe({ entryTypes: ['layout-shift'], buffered: true })
        } catch (e) {
          console.warn('CLS measurement not supported')
        }

        // TTFB - Time to First Byte
        try {
          const navigationEntries = performance.getEntriesByType('navigation')
          if (navigationEntries.length > 0) {
            const navigation = navigationEntries[0] as any
            vitals.TTFB = (navigation.responseStart || 0) - (navigation.requestStart || 0)
          }
        } catch (e) {
          console.warn('TTFB measurement not supported')
        }

        // Wait 2 seconds to collect metrics
        setTimeout(() => {
          resolve(vitals)
        }, 2000)
      })
    })
  }

  /**
   * Get current memory usage
   *
   * @returns Memory usage data (requires Chrome with --enable-precise-memory-info)
   */
  async getMemoryUsage(): Promise<MemoryUsage> {
    return await this.page.evaluate(() => {
      if ('memory' in performance) {
        const mem = (performance as any).memory
        return {
          usedJSHeapSize: mem.usedJSHeapSize || 0,
          totalJSHeapSize: mem.totalJSHeapSize || 0,
          jsHeapSizeLimit: mem.jsHeapSizeLimit || 0
        }
      }
      return {
        usedJSHeapSize: 0,
        totalJSHeapSize: 0,
        jsHeapSizeLimit: 0
      }
    })
  }

  /**
   * Measure scroll performance (FPS)
   *
   * @param selector - Element to scroll
   * @param scrollDistance - Distance to scroll (px)
   * @param duration - Duration of scroll (ms)
   * @returns Average FPS during scroll
   */
  async measureScrollPerformance(
    selector: string,
    scrollDistance: number = 1000,
    duration: number = 1000
  ): Promise<{ averageFPS: number; frameCount: number }> {
    const element = this.page.locator(selector).first()

    const result = await this.page.evaluate(
      async ({ sel, distance, dur }) => {
        const el = document.querySelector(sel)
        if (!el) return { averageFPS: 0, frameCount: 0 }

        let frameCount = 0
        let lastTime = performance.now()
        const frames: number[] = []

        const measureFrame = () => {
          const currentTime = performance.now()
          const delta = currentTime - lastTime
          if (delta > 0) {
            frames.push(1000 / delta) // Calculate FPS
          }
          lastTime = currentTime
          frameCount++
        }

        return new Promise<{ averageFPS: number; frameCount: number }>((resolve) => {
          const startTime = performance.now()
          const startScroll = el.scrollTop

          const animate = () => {
            const elapsed = performance.now() - startTime
            const progress = Math.min(elapsed / dur, 1)

            el.scrollTop = startScroll + distance * progress
            measureFrame()

            if (progress < 1) {
              requestAnimationFrame(animate)
            } else {
              const avgFPS = frames.length > 0
                ? frames.reduce((sum, fps) => sum + fps, 0) / frames.length
                : 0
              resolve({ averageFPS: avgFPS, frameCount })
            }
          }

          requestAnimationFrame(animate)
        })
      },
      { sel: selector, distance: scrollDistance, dur: duration }
    )

    this.metrics.set('scroll_fps', result.averageFPS)
    return result
  }

  /**
   * Get Navigation Timing metrics
   *
   * @returns Navigation timing breakdown
   */
  async getNavigationTiming(): Promise<Record<string, number>> {
    return await this.page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0] as any
      if (!navigation) return {}

      return {
        dns: navigation.domainLookupEnd - navigation.domainLookupStart,
        tcp: navigation.connectEnd - navigation.connectStart,
        request: navigation.responseStart - navigation.requestStart,
        response: navigation.responseEnd - navigation.responseStart,
        domProcessing: navigation.domComplete - navigation.domLoading,
        domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
        load: navigation.loadEventEnd - navigation.loadEventStart,
        total: navigation.loadEventEnd - navigation.fetchStart
      }
    })
  }

  /**
   * Clear all collected metrics
   */
  clear() {
    this.metrics.clear()
  }

  /**
   * Generate human-readable performance report
   *
   * @returns Formatted report string
   */
  generateReport(): string {
    let report = `\n📊 Performance Metrics Report\n`
    report += `${'='.repeat(70)}\n`

    if (this.metrics.size === 0) {
      report += `  No metrics recorded.\n`
    } else {
      this.metrics.forEach((value, key) => {
        const formattedKey = key.padEnd(50)
        const formattedValue = value.toFixed(2).padStart(10)
        report += `  ${formattedKey}: ${formattedValue}ms\n`
      })
    }

    report += `${'='.repeat(70)}\n`
    return report
  }

  /**
   * Export metrics as JSON
   *
   * @returns Metrics object
   */
  exportJSON(): Record<string, number> {
    return Object.fromEntries(this.metrics)
  }

  /**
   * Get specific metric value
   *
   * @param key - Metric key
   * @returns Metric value or undefined
   */
  getMetric(key: string): number | undefined {
    return this.metrics.get(key)
  }

  /**
   * Get all metric keys
   *
   * @returns Array of metric keys
   */
  getMetricKeys(): string[] {
    return Array.from(this.metrics.keys())
  }
}
