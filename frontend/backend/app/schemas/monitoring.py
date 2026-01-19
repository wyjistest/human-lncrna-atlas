"""
监控数据模型（Pydantic Schemas）

用于 Admin API 响应结构定义
Phase 2 新增：响应时间分布、错误趋势、端点统计
Phase 3 新增：系统指标、告警、百分位响应时间
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class RequestMetrics(BaseModel):
    """请求指标"""

    total: int = Field(description="总请求数")
    last_minute: int = Field(default=0, description="最近一分钟请求数")

    model_config = ConfigDict(from_attributes=True)


class ErrorMetrics(BaseModel):
    """错误指标"""

    total: int = Field(description="总错误数")
    rate: float = Field(ge=0, le=1, description="错误率 (0-1)")

    model_config = ConfigDict(from_attributes=True)


class ResponseTimeMetrics(BaseModel):
    """响应时间指标"""

    avg_ms: float = Field(ge=0, description="平均响应时间（毫秒）")

    model_config = ConfigDict(from_attributes=True)


class HealthMetrics(BaseModel):
    """健康状态指标"""

    status: Literal["healthy", "degraded", "down"] = Field(
        description="整体健康状态"
    )
    database: Literal["ok", "error"] = Field(description="数据库状态")
    cache: Literal["ok", "error", "not_configured"] = Field(description="缓存状态")
    uptime_seconds: int = Field(ge=0, description="运行时间（秒）")

    model_config = ConfigDict(from_attributes=True)


class CacheStats(BaseModel):
    """缓存统计摘要"""

    backend: str = Field(description="缓存后端类型（redis/memory）")
    enabled: bool = Field(description="是否启用缓存")
    hits: int = Field(ge=0, description="命中次数")
    misses: int = Field(ge=0, description="未命中次数")
    total_requests: int = Field(ge=0, description="缓存请求总数")
    hit_rate_pct: float = Field(ge=0, le=100, description="缓存命中率(%)")

    model_config = ConfigDict(from_attributes=True)


class CacheNamespaceBreakdownItem(BaseModel):
    """缓存命名空间统计（Top N）"""

    namespace: str = Field(description="缓存命名空间")
    requests: int = Field(ge=0, description="请求数")
    hits: int = Field(ge=0, description="命中数")
    misses: int = Field(ge=0, description="未命中数")
    hit_rate_pct: float = Field(ge=0, le=100, description="命中率(%)")
    compute_count: int = Field(ge=0, description="回源计算次数")
    compute_avg_ms: float = Field(ge=0, description="回源平均耗时(ms)")
    compute_max_ms: float = Field(ge=0, description="回源最大耗时(ms)")

    model_config = ConfigDict(from_attributes=True)


class CacheKeyBreakdownItem(BaseModel):
    """缓存热点 key 统计（Top N）"""

    key: str = Field(description="缓存键（可能包含 hash；用于定位热点）")
    namespace: Optional[str] = Field(default=None, description="best-effort 解析出的命名空间")
    requests: int = Field(ge=0, description="请求数")
    hits: int = Field(ge=0, description="命中数")
    misses: int = Field(ge=0, description="未命中数")
    hit_rate_pct: float = Field(ge=0, le=100, description="命中率(%)")

    model_config = ConfigDict(from_attributes=True)


class CacheNamespacesBreakdown(BaseModel):
    """缓存命名空间分布"""

    tracked: int = Field(ge=0, description="已跟踪命名空间数量")
    limit: int = Field(ge=0, description="Top N 限制")
    top: list[CacheNamespaceBreakdownItem] = Field(default_factory=list, description="Top 命名空间列表")

    model_config = ConfigDict(from_attributes=True)


class CacheKeysBreakdown(BaseModel):
    """缓存 key 分布"""

    tracked: int = Field(ge=0, description="已跟踪 key 数量")
    limit: int = Field(ge=0, description="Top N 限制")
    top: list[CacheKeyBreakdownItem] = Field(default_factory=list, description="Top key 列表")

    model_config = ConfigDict(from_attributes=True)


class CacheBreakdown(BaseModel):
    """缓存统计分解（命名空间/热点 key）"""

    namespaces: CacheNamespacesBreakdown = Field(description="命名空间维度统计")
    keys: CacheKeysBreakdown = Field(description="热点 key 维度统计")

    model_config = ConfigDict(from_attributes=True)


# Phase 2 新增模型
class ResponseTimeDistribution(BaseModel):
    """响应时间分布"""

    buckets: list[str] = Field(description="分布区间标签")
    counts: list[int] = Field(description="各区间请求数量")

    model_config = ConfigDict(from_attributes=True)


class ErrorTrend(BaseModel):
    """错误率趋势"""

    timestamps: list[str] = Field(
        description="时间点标签（最近10分钟，每分钟一个点，格式 HH:MM）"
    )
    error_rates: list[float] = Field(description="各时间点的错误率 (0-1)")

    model_config = ConfigDict(from_attributes=True)


class EndpointStats(BaseModel):
    """端点统计"""

    path: str = Field(description="API路径")
    requests: int = Field(ge=0, description="请求数")
    avg_ms: float = Field(ge=0, description="平均响应时间(ms)")
    percentiles: Optional["PercentileMetrics"] = Field(
        default=None,
        description="端点响应时间百分位(ms；数据不足时为null)",
    )
    db_avg_ms: Optional[float] = Field(
        default=None,
        ge=0,
        description="端点 DB 平均耗时(ms；按请求聚合；无 DB 查询时为 0)",
    )
    db_query_avg: Optional[float] = Field(
        default=None,
        ge=0,
        description="端点平均每请求 DB 查询数（best-effort）",
    )
    db_percentiles: Optional["PercentileMetrics"] = Field(
        default=None,
        description="端点请求级 DB 耗时百分位(ms；数据不足时为null)",
    )
    errors: int = Field(ge=0, description="错误数")
    error_rate: float = Field(ge=0, le=1, description="错误率")

    model_config = ConfigDict(from_attributes=True)


# Phase 3 新增模型
class SystemMemory(BaseModel):
    """系统内存指标"""

    used_mb: float = Field(ge=0, description="已使用内存(MB)")
    total_mb: float = Field(ge=0, description="总内存(MB)")
    percent: float = Field(ge=0, le=100, description="内存使用率(%)")

    model_config = ConfigDict(from_attributes=True)


class SystemDisk(BaseModel):
    """系统磁盘指标"""

    used_gb: float = Field(ge=0, description="已使用磁盘(GB)")
    total_gb: float = Field(ge=0, description="总磁盘(GB)")
    percent: float = Field(ge=0, le=100, description="磁盘使用率(%)")

    model_config = ConfigDict(from_attributes=True)


class ProcessInfo(BaseModel):
    """进程信息"""

    cpu_percent: float = Field(ge=0, description="进程CPU使用率(%)")
    memory_mb: float = Field(ge=0, description="进程内存使用(MB)")

    model_config = ConfigDict(from_attributes=True)


class SystemMetrics(BaseModel):
    """系统资源指标"""

    cpu_percent: float = Field(ge=0, le=100, description="系统CPU使用率(%)")
    memory: SystemMemory = Field(description="内存指标")
    disk: SystemDisk = Field(description="磁盘指标")
    process: ProcessInfo = Field(description="当前进程信息")

    model_config = ConfigDict(from_attributes=True)


class Alert(BaseModel):
    """告警信息"""

    type: Literal["warning", "critical"] = Field(description="告警级别")
    metric: str = Field(description="告警指标名称")
    value: float = Field(description="当前值")
    threshold: float = Field(description="阈值")
    message: str = Field(description="告警消息")

    model_config = ConfigDict(from_attributes=True)


class PercentileMetrics(BaseModel):
    """响应时间百分位指标"""

    p50_ms: float = Field(ge=0, description="50百分位响应时间(ms)")
    p95_ms: float = Field(ge=0, description="95百分位响应时间(ms)")
    p99_ms: float = Field(ge=0, description="99百分位响应时间(ms)")

    model_config = ConfigDict(from_attributes=True)


class CacheGetLatencyPercentiles(BaseModel):
    """缓存 get() 命中/未命中耗时百分位（毫秒）"""

    hits_samples: int = Field(ge=0, description="命中样本数")
    misses_samples: int = Field(ge=0, description="未命中样本数")
    max_samples: int = Field(ge=0, description="每类样本最大保留数量（ring buffer）")
    hits: Optional[PercentileMetrics] = Field(default=None, description="命中耗时百分位(ms)")
    misses: Optional[PercentileMetrics] = Field(default=None, description="未命中耗时百分位(ms)")

    model_config = ConfigDict(from_attributes=True)


class SlowQuerySummary(BaseModel):
    """慢查询榜单条目（按 SQL 指纹聚合）"""

    fingerprint: str = Field(description="SQL 语句指纹（用于聚合）")
    statement: str = Field(description="归一化后的 SQL（截断）")
    count: int = Field(ge=1, description="出现次数（在 ring buffer 窗口内）")
    total_time_ms: float = Field(ge=0, description="累计耗时(ms)")
    avg_ms: float = Field(ge=0, description="平均耗时(ms)")
    max_ms: float = Field(ge=0, description="最大耗时(ms)")
    last_seen: str = Field(description="最后一次出现时间（ISO8601）")
    route: Optional[str] = Field(default=None, description="触发该查询的端点（best-effort）")

    model_config = ConfigDict(from_attributes=True)


class DatabaseMetrics(BaseModel):
    """数据库查询性能指标（用于快速定位 DB 瓶颈）"""

    total_queries: int = Field(ge=0, description="累计 DB 查询数")
    total_time_ms: float = Field(ge=0, description="累计 DB 查询耗时(ms)")
    avg_ms: float = Field(ge=0, description="平均单次查询耗时(ms)")
    percentiles: Optional[PercentileMetrics] = Field(
        default=None,
        description="单次查询耗时百分位(ms；数据不足时为null)",
    )
    request_total_ms: float = Field(ge=0, description="累计请求级 DB 耗时(ms；每请求 sum(query))")
    request_avg_ms: float = Field(ge=0, description="平均每请求 DB 耗时(ms)")
    request_percentiles: Optional[PercentileMetrics] = Field(
        default=None,
        description="每请求 DB 耗时百分位(ms；数据不足时为null)",
    )
    slow_query_threshold_ms: float = Field(ge=0, description="慢查询阈值(ms；0 表示不记录)")
    slow_queries: list[SlowQuerySummary] = Field(default_factory=list, description="慢查询榜单（按指纹聚合）")

    model_config = ConfigDict(from_attributes=True)


class MetricsResponse(BaseModel):
    """
    监控指标响应

    API 响应结构（前后端约定）
    Phase 2 新增：response_time_distribution, error_trend, endpoints
    Phase 3 新增：system, alerts, percentiles
    """

    # Phase 1 - 基础指标（保留向后兼容）
    request: RequestMetrics = Field(description="请求指标")
    errors: ErrorMetrics = Field(description="错误指标")
    response_time: ResponseTimeMetrics = Field(description="响应时间指标")
    health: HealthMetrics = Field(description="健康状态指标")
    cache_stats: Optional[CacheStats] = Field(default=None, description="缓存统计摘要")
    cache_breakdown: Optional[CacheBreakdown] = Field(
        default=None,
        description="缓存命名空间/热点 key 分布（不包含 Redis host 等敏感信息）",
    )
    cache_get_latency: Optional[CacheGetLatencyPercentiles] = Field(
        default=None,
        description="缓存 get() 命中/未命中耗时百分位（ms；数据不足时为null）",
    )

    # Phase 2 - 新增指标
    response_time_distribution: ResponseTimeDistribution = Field(
        description="响应时间分布"
    )
    error_trend: ErrorTrend = Field(description="错误率趋势（最近10分钟）")
    endpoints: list[EndpointStats] = Field(description="端点统计（Top 20）")

    # Phase 3 - 系统监控指标
    system: SystemMetrics = Field(description="系统资源指标")
    alerts: list[Alert] = Field(default_factory=list, description="告警列表")
    percentiles: Optional[PercentileMetrics] = Field(
        default=None, description="响应时间百分位（数据不足时为null）"
    )
    database: Optional[DatabaseMetrics] = Field(
        default=None,
        description="数据库查询指标（用于定位慢查询与 DB 主导尾延迟）",
    )

    model_config = ConfigDict(from_attributes=True)
