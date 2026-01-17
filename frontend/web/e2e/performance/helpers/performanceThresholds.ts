/**
 * Performance Test Thresholds Configuration
 *
 * Central configuration for all performance test thresholds.
 * Update these values based on baseline measurements and optimization goals.
 */

export interface PerformanceThresholds {
  API: {
    DISEASE_LIST_MAX: number          // Disease API response time (ms)
    NETWORK_DATA_MAX: number          // Network data API response time (ms)
    CACHE_HIT_MIN: number             // Minimum cache hit rate (%)
    TTFB_MAX: number                  // Time to First Byte (ms)
  }
  FRONTEND: {
    DROPDOWN_RENDER_MAX: number       // Dropdown render time (ms)
    GRAPH_RENDER_MAX: number          // Cytoscape graph render time (ms)
    TOTAL_USER_TIME_MAX: number       // Total user experience time (ms)
    MEMORY_MAX: number                // Maximum JS heap usage (bytes)
    SCROLL_FPS_MIN: number            // Minimum scroll FPS
  }
  WEB_VITALS: {
    LCP_MAX: number                   // Largest Contentful Paint (ms)
    FID_MAX: number                   // First Input Delay (ms)
    CLS_MAX: number                   // Cumulative Layout Shift (score)
    TTFB_MAX: number                  // Time to First Byte (ms)
  }
  STRESS_TEST: {
    CONCURRENT_USERS: number          // Number of concurrent users to simulate
    SUCCESS_RATE_MIN: number          // Minimum success rate (%)
    AVG_RESPONSE_TIME_MAX: number     // Maximum average response time (ms)
  }
}

/**
 * Baseline Thresholds (Before Optimization)
 *
 * These represent acceptable performance before implementing optimizations.
 * Use as reference for measuring improvement.
 */
export const BASELINE_THRESHOLDS: PerformanceThresholds = {
  API: {
    DISEASE_LIST_MAX: 1000,           // 1 second
    NETWORK_DATA_MAX: 5000,           // 5 seconds
    CACHE_HIT_MIN: 0,                 // No cache initially
    TTFB_MAX: 500,                    // 500ms
  },
  FRONTEND: {
    DROPDOWN_RENDER_MAX: 500,         // 0.5 seconds
    GRAPH_RENDER_MAX: 3000,           // 3 seconds
    TOTAL_USER_TIME_MAX: 8000,        // 8 seconds total experience
    MEMORY_MAX: 200 * 1024 * 1024,    // 200 MB
    SCROLL_FPS_MIN: 30,               // 30 FPS minimum
  },
  WEB_VITALS: {
    LCP_MAX: 2500,                    // 2.5 seconds (Google recommended)
    FID_MAX: 100,                     // 100ms (Google recommended)
    CLS_MAX: 0.1,                     // 0.1 score (Google recommended)
    TTFB_MAX: 800,                    // 800ms
  },
  STRESS_TEST: {
    CONCURRENT_USERS: 10,
    SUCCESS_RATE_MIN: 90,             // 90% success rate
    AVG_RESPONSE_TIME_MAX: 10000,     // 10 seconds average
  }
}

/**
 * Optimized Thresholds (After Optimization Goals)
 *
 * These represent performance goals after implementing optimizations.
 * Target 50-80% improvement in critical metrics.
 */
export const OPTIMIZED_THRESHOLDS: PerformanceThresholds = {
  API: {
    DISEASE_LIST_MAX: 200,            // 80% improvement
    NETWORK_DATA_MAX: 2000,           // 60% improvement
    CACHE_HIT_MIN: 80,                // 80% cache hit rate
    TTFB_MAX: 150,                    // 70% improvement
  },
  FRONTEND: {
    DROPDOWN_RENDER_MAX: 200,         // 60% improvement
    GRAPH_RENDER_MAX: 1500,           // 50% improvement
    TOTAL_USER_TIME_MAX: 3000,        // 63% improvement
    MEMORY_MAX: 150 * 1024 * 1024,    // 25% reduction (150 MB)
    SCROLL_FPS_MIN: 55,               // 83% improvement
  },
  WEB_VITALS: {
    LCP_MAX: 1800,                    // 28% improvement
    FID_MAX: 50,                      // 50% improvement
    CLS_MAX: 0.05,                    // 50% improvement
    TTFB_MAX: 300,                    // 63% improvement
  },
  STRESS_TEST: {
    CONCURRENT_USERS: 20,             // Test with more users
    SUCCESS_RATE_MIN: 95,             // 95% success rate
    AVG_RESPONSE_TIME_MAX: 5000,      // 50% improvement
  }
}

/**
 * Current Active Thresholds
 *
 * Set this to BASELINE_THRESHOLDS initially, then gradually tighten to OPTIMIZED_THRESHOLDS
 * as optimizations are implemented and verified.
 */
export const CURRENT_THRESHOLDS: PerformanceThresholds = BASELINE_THRESHOLDS

/**
 * Performance Level Classification
 */
export enum PerformanceLevel {
  EXCELLENT = 'excellent',
  GOOD = 'good',
  FAIR = 'fair',
  POOR = 'poor'
}

/**
 * Classify performance based on metric value
 *
 * @param metricValue - Measured value
 * @param thresholdValue - Threshold value
 * @param isLowerBetter - If true, lower values are better (e.g., response time)
 * @returns Performance level
 */
export function classifyPerformance(
  metricValue: number,
  thresholdValue: number,
  isLowerBetter: boolean = true
): PerformanceLevel {
  if (isLowerBetter) {
    const ratio = metricValue / thresholdValue
    if (ratio <= 0.5) return PerformanceLevel.EXCELLENT
    if (ratio <= 0.8) return PerformanceLevel.GOOD
    if (ratio <= 1.0) return PerformanceLevel.FAIR
    return PerformanceLevel.POOR
  } else {
    // Higher is better (e.g., FPS, cache hit rate)
    const ratio = metricValue / thresholdValue
    if (ratio >= 1.5) return PerformanceLevel.EXCELLENT
    if (ratio >= 1.2) return PerformanceLevel.GOOD
    if (ratio >= 1.0) return PerformanceLevel.FAIR
    return PerformanceLevel.POOR
  }
}

/**
 * Check if metrics pass all thresholds
 *
 * @param metrics - Measured metrics
 * @param thresholds - Threshold configuration
 * @returns Pass/fail result with violations
 */
export function checkThresholds(
  metrics: {
    apiResponseTime?: number
    renderTime?: number
    totalUserTime?: number
    memoryUsage?: number
    scrollFPS?: number
    cacheHitRate?: number
    webVitals?: {
      LCP?: number
      FID?: number
      CLS?: number
      TTFB?: number
    }
  },
  thresholds: PerformanceThresholds = CURRENT_THRESHOLDS
): { passed: boolean; violations: string[]; warnings: string[] } {
  const violations: string[] = []
  const warnings: string[] = []

  // API metrics
  if (metrics.apiResponseTime !== undefined) {
    if (metrics.apiResponseTime > thresholds.API.DISEASE_LIST_MAX) {
      violations.push(
        `API response time ${metrics.apiResponseTime.toFixed(2)}ms exceeds threshold ${thresholds.API.DISEASE_LIST_MAX}ms`
      )
    } else if (metrics.apiResponseTime > thresholds.API.DISEASE_LIST_MAX * 0.8) {
      warnings.push(
        `API response time ${metrics.apiResponseTime.toFixed(2)}ms is approaching threshold ${thresholds.API.DISEASE_LIST_MAX}ms`
      )
    }
  }

  // Frontend metrics
  if (metrics.renderTime !== undefined) {
    if (metrics.renderTime > thresholds.FRONTEND.DROPDOWN_RENDER_MAX) {
      violations.push(
        `Render time ${metrics.renderTime.toFixed(2)}ms exceeds threshold ${thresholds.FRONTEND.DROPDOWN_RENDER_MAX}ms`
      )
    } else if (metrics.renderTime > thresholds.FRONTEND.DROPDOWN_RENDER_MAX * 0.8) {
      warnings.push(
        `Render time ${metrics.renderTime.toFixed(2)}ms is approaching threshold ${thresholds.FRONTEND.DROPDOWN_RENDER_MAX}ms`
      )
    }
  }

  if (metrics.totalUserTime !== undefined) {
    if (metrics.totalUserTime > thresholds.FRONTEND.TOTAL_USER_TIME_MAX) {
      violations.push(
        `Total user time ${metrics.totalUserTime.toFixed(2)}ms exceeds threshold ${thresholds.FRONTEND.TOTAL_USER_TIME_MAX}ms`
      )
    }
  }

  if (metrics.memoryUsage !== undefined) {
    if (metrics.memoryUsage > thresholds.FRONTEND.MEMORY_MAX) {
      violations.push(
        `Memory usage ${(metrics.memoryUsage / 1024 / 1024).toFixed(2)}MB exceeds threshold ${(thresholds.FRONTEND.MEMORY_MAX / 1024 / 1024).toFixed(2)}MB`
      )
    }
  }

  if (metrics.scrollFPS !== undefined) {
    if (metrics.scrollFPS < thresholds.FRONTEND.SCROLL_FPS_MIN) {
      violations.push(
        `Scroll FPS ${metrics.scrollFPS.toFixed(2)} is below threshold ${thresholds.FRONTEND.SCROLL_FPS_MIN}`
      )
    }
  }

  // Cache metrics
  if (metrics.cacheHitRate !== undefined && thresholds.API.CACHE_HIT_MIN > 0) {
    if (metrics.cacheHitRate < thresholds.API.CACHE_HIT_MIN) {
      violations.push(
        `Cache hit rate ${metrics.cacheHitRate.toFixed(2)}% is below threshold ${thresholds.API.CACHE_HIT_MIN}%`
      )
    }
  }

  // Web Vitals
  if (metrics.webVitals) {
    if (metrics.webVitals.LCP !== undefined && metrics.webVitals.LCP > thresholds.WEB_VITALS.LCP_MAX) {
      violations.push(
        `LCP ${metrics.webVitals.LCP.toFixed(2)}ms exceeds threshold ${thresholds.WEB_VITALS.LCP_MAX}ms`
      )
    }

    if (metrics.webVitals.FID !== undefined && metrics.webVitals.FID > thresholds.WEB_VITALS.FID_MAX) {
      violations.push(
        `FID ${metrics.webVitals.FID.toFixed(2)}ms exceeds threshold ${thresholds.WEB_VITALS.FID_MAX}ms`
      )
    }

    if (metrics.webVitals.CLS !== undefined && metrics.webVitals.CLS > thresholds.WEB_VITALS.CLS_MAX) {
      violations.push(
        `CLS ${metrics.webVitals.CLS.toFixed(4)} exceeds threshold ${thresholds.WEB_VITALS.CLS_MAX}`
      )
    }
  }

  return {
    passed: violations.length === 0,
    violations,
    warnings
  }
}

/**
 * Calculate performance improvement percentage
 *
 * @param baselineValue - Baseline measurement
 * @param currentValue - Current measurement
 * @param isLowerBetter - If true, improvement means reduction
 * @returns Improvement percentage (positive = better)
 */
export function calculateImprovement(
  baselineValue: number,
  currentValue: number,
  isLowerBetter: boolean = true
): number {
  if (baselineValue === 0) return 0

  if (isLowerBetter) {
    // For metrics where lower is better (e.g., response time)
    return ((baselineValue - currentValue) / baselineValue) * 100
  } else {
    // For metrics where higher is better (e.g., FPS)
    return ((currentValue - baselineValue) / baselineValue) * 100
  }
}

/**
 * Generate performance comparison report
 *
 * @param baseline - Baseline metrics
 * @param current - Current metrics
 * @returns Formatted comparison report
 */
export function generateComparisonReport(
  baseline: Record<string, number>,
  current: Record<string, number>
): string {
  let report = '\n📊 Performance Comparison Report\n'
  report += '='.repeat(80) + '\n'
  report += `${'Metric'.padEnd(40)} | ${'Baseline'.padEnd(12)} | ${'Current'.padEnd(12)} | ${'Change'.padEnd(10)}\n`
  report += '-'.repeat(80) + '\n'

  for (const [key, baselineValue] of Object.entries(baseline)) {
    const currentValue = current[key]
    if (currentValue !== undefined) {
      const improvement = calculateImprovement(baselineValue, currentValue, true)
      const changeStr = improvement >= 0
        ? `↓ ${improvement.toFixed(1)}%`
        : `↑ ${Math.abs(improvement).toFixed(1)}%`
      const emoji = improvement >= 10 ? '✅' : improvement >= 0 ? '⚠️' : '❌'

      report += `${key.padEnd(40)} | ${baselineValue.toFixed(2).padStart(10)}ms | ${currentValue.toFixed(2).padStart(10)}ms | ${changeStr.padStart(10)} ${emoji}\n`
    }
  }

  report += '='.repeat(80) + '\n'
  return report
}
