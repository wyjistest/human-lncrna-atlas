"""
日志和监控中间件
"""
import time
import re
import logging
from collections import deque
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable, Optional

logger = logging.getLogger("api")


# Phase 2 - 辅助函数
def normalize_path(path: str) -> Optional[str]:
    """
    归一化路径，将路径参数替换为占位符

    Args:
        path: 原始请求路径

    Returns:
        归一化后的路径，如果是应跳过的路径则返回 None
    """
    skip_prefixes = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/static",
        "/health",
        "/internal",
        "/genomes",  # 静态文件服务，绕过中间件
    ]
    if any(path.startswith(p) for p in skip_prefixes):
        return None
    # 将数字 ID 替换为 {id}
    normalized = re.sub(r"/\d+", "/{id}", path)
    return normalized


def get_bucket(response_time_ms: float) -> str:
    """
    将响应时间分配到对应的 bucket

    Args:
        response_time_ms: 响应时间（毫秒）

    Returns:
        bucket 标签字符串
    """
    if response_time_ms < 50:
        return "0-50"
    elif response_time_ms < 100:
        return "50-100"
    elif response_time_ms < 200:
        return "100-200"
    elif response_time_ms < 500:
        return "200-500"
    else:
        return "500+"


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 跳过静态文件路径（避免 BaseHTTPMiddleware 与流式响应的兼容性问题）
        if request.url.path.startswith("/genomes"):
            return await call_next(request)

        # 记录请求开始
        start_time = time.time()

        # 获取请求信息
        method = request.method
        url = str(request.url)
        client_ip = request.client.host if request.client else "unknown"

        # 处理请求
        try:
            response = await call_next(request)

            # 计算耗时
            process_time = time.time() - start_time

            # 记录日志
            logger.info(
                f"{method} {url} - {response.status_code} - "
                f"{process_time:.3f}s - {client_ip}"
            )

            # 添加响应头
            response.headers["X-Process-Time"] = f"{process_time:.3f}"

            return response

        except Exception as e:
            # 记录错误
            process_time = time.time() - start_time
            logger.error(
                f"{method} {url} - ERROR - {process_time:.3f}s - "
                f"{client_ip} - {str(e)}"
            )
            raise


class MetricsMiddleware(BaseHTTPMiddleware):
    """性能指标中间件 - Phase 2 增强版"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 跳过静态文件路径（避免 BaseHTTPMiddleware 与流式响应的兼容性问题）
        if request.url.path.startswith("/genomes"):
            return await call_next(request)

        start_time = time.time()

        # 获取app.state中的指标数据
        if not hasattr(request.app.state, "metrics_data"):
            request.app.state.metrics_data = {
                "total_requests": 0,
                "total_errors": 0,
                "total_time": 0.0,
                "last_minute_requests": 0,
                "response_time_buckets": {
                    "0-50": 0,
                    "50-100": 0,
                    "100-200": 0,
                    "200-500": 0,
                    "500+": 0,
                },
                "time_series": deque(maxlen=600),
                "endpoints": {},
                "current_second": {"timestamp": 0, "requests": 0, "errors": 0},
            }

        metrics = request.app.state.metrics_data
        is_error = False

        try:
            response = await call_next(request)

            # 检查是否为错误响应
            if response.status_code >= 500:
                is_error = True
                metrics["total_errors"] += 1

            return response

        except Exception as e:
            is_error = True
            metrics["total_errors"] += 1
            raise

        finally:
            # 计算处理时间
            process_time = time.time() - start_time
            process_time_ms = process_time * 1000

            # Phase 1 - 基础指标更新
            metrics["total_requests"] += 1
            metrics["total_time"] += process_time

            # 记录慢请求
            if process_time > 2.0:
                logger.warning(
                    f"🐢 SLOW REQUEST DETECTED\n"
                    f"  Method: {request.method}\n"
                    f"  URL: {request.url}\n"
                    f"  Duration: {process_time:.3f}s\n"
                    f"  Client IP: {request.client.host if request.client else 'unknown'}\n"
                    f"  Query Params: {dict(request.query_params)}"
                )

            # Phase 2 - 响应时间分布更新
            bucket = get_bucket(process_time_ms)
            if "response_time_buckets" in metrics:
                metrics["response_time_buckets"][bucket] += 1

            # Phase 3 - 记录响应时间到 deque（用于百分位计算）
            if "response_times" in metrics:
                metrics["response_times"].append(process_time_ms)

            # Phase 2 - 端点统计更新
            path = request.url.path
            normalized_path = normalize_path(path)
            if normalized_path and "endpoints" in metrics:
                if normalized_path not in metrics["endpoints"]:
                    metrics["endpoints"][normalized_path] = {
                        "requests": 0,
                        "errors": 0,
                        "total_time": 0.0,
                    }
                metrics["endpoints"][normalized_path]["requests"] += 1
                metrics["endpoints"][normalized_path]["total_time"] += process_time_ms
                if is_error:
                    metrics["endpoints"][normalized_path]["errors"] += 1

            # Phase 2 - 时间序列更新（滑动窗口）
            current_ts = int(time.time())
            if "current_second" in metrics and "time_series" in metrics:
                current_second = metrics["current_second"]

                if current_second["timestamp"] != current_ts:
                    # 新的一秒开始，保存上一秒数据到 time_series
                    if current_second["timestamp"] > 0:
                        metrics["time_series"].append({
                            "timestamp": current_second["timestamp"],
                            "requests": current_second["requests"],
                            "errors": current_second["errors"],
                        })
                    # 重置当前秒计数器
                    current_second["timestamp"] = current_ts
                    current_second["requests"] = 1
                    current_second["errors"] = 1 if is_error else 0
                else:
                    # 同一秒内累加
                    current_second["requests"] += 1
                    if is_error:
                        current_second["errors"] += 1
