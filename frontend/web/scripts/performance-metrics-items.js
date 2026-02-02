export const PERFORMANCE_METRICS_ITEMS = [
  { path: 'critical_metrics.api_response_time.value_ms', label: 'API 响应时间 (ms)', higherIsBetter: false },
  { path: 'critical_metrics.cache_performance.cold_cache_time_ms', label: '冷缓存耗时 (ms)', higherIsBetter: false },
  { path: 'critical_metrics.cache_performance.warm_cache_time_ms', label: '热缓存耗时 (ms)', higherIsBetter: false },
  { path: 'critical_metrics.cache_performance.cache_hit_rate_percent', label: '缓存命中率 (%)', higherIsBetter: true },
  { path: 'critical_metrics.cache_performance.average_hit_time_ms', label: '平均命中耗时 (ms)', higherIsBetter: false },
  { path: 'critical_metrics.cache_performance.average_miss_time_ms', label: '平均未命中耗时 (ms)', higherIsBetter: false },
  { path: 'test_results.pass_rate_percent', label: '测试通过率 (%)', higherIsBetter: true },
]

