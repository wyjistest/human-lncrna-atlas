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

    model_config = ConfigDict(from_attributes=True)
