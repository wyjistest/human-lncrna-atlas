"""
Redis 缓存服务

提供统一的缓存接口，支持：
- Redis 持久化缓存（主要）
- 内存缓存回退（Redis 不可用时）
- 自动序列化/反序列化
- TTL 管理
- 缓存键生成
"""
import json
import hashlib
import logging
import time
import threading
from typing import Any, Optional, Callable, TypeVar, Tuple
from functools import wraps

try:
    import redis
    from redis.exceptions import RedisError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    RedisError = Exception

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============== 内存缓存（回退方案） ==============

class MemoryCache:
    """简单的内存缓存（支持 TTL，线程安全）"""

    def __init__(self, max_size: int = 1000):
        self._cache: dict[str, Tuple[Any, float]] = {}
        self._max_size = max_size
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if time.time() < expiry:
                    return value
                del self._cache[key]
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        with self._lock:
            if len(self._cache) >= self._max_size:
                self._evict_expired()
            if len(self._cache) >= self._max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            self._cache[key] = (value, time.time() + ttl)
            return True

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._cache.pop(key, None) is not None

    def clear(self) -> int:
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def _evict_expired(self):
        """Evict expired entries. Must be called while holding self._lock."""
        current = time.time()
        expired = [k for k, (_, exp) in self._cache.items() if exp <= current]
        for k in expired:
            del self._cache[k]


# ============== Redis 缓存 ==============

class RedisCache:
    """Redis 缓存实现"""

    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._connect()

    def _connect(self):
        """连接 Redis"""
        if not REDIS_AVAILABLE or not settings.ENABLE_CACHE:
            return

        try:
            self._client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            self._client.ping()
            logger.info(f"Redis 连接成功: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Redis 连接失败: {e}")
            self._client = None

    @property
    def connected(self) -> bool:
        return self._client is not None

    def get(self, key: str) -> Optional[Any]:
        if not self._client:
            return None
        try:
            value = self._client.get(key)
            if value:
                return json.loads(value)
        except (RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Redis GET 失败 [{key}]: {e}")
        return None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        if not self._client:
            return False
        try:
            serialized = json.dumps(value, default=str, ensure_ascii=False)
            self._client.setex(key, ttl, serialized)
            return True
        except (RedisError, TypeError) as e:
            logger.warning(f"Redis SET 失败 [{key}]: {e}")
            return False

    def delete(self, key: str) -> bool:
        if not self._client:
            return False
        try:
            return self._client.delete(key) > 0
        except RedisError as e:
            logger.warning(f"Redis DELETE 失败 [{key}]: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern using non-blocking SCAN"""
        if not self._client:
            return 0
        try:
            deleted = 0
            cursor = 0
            while True:
                cursor, keys = self._client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    deleted += self._client.delete(*keys)
                if cursor == 0:
                    break
            return deleted
        except RedisError as e:
            logger.warning(f"Redis batch delete failed [{pattern}]: {e}")
        return 0

    def clear(self, prefix: str = "lncrna:") -> int:
        return self.delete_pattern(f"{prefix}*")


# ============== 统一缓存服务 ==============

class CacheService:
    """
    统一缓存服务

    优先使用 Redis，不可用时回退到内存缓存
    """

    PREFIX = "lncrna:"

    # TTL 配置（秒）
    TTL_STATS = 3600      # 统计数据 1 小时
    TTL_LIST = 300        # 列表数据 5 分钟
    TTL_DETAIL = 600      # 详情数据 10 分钟
    TTL_SHORT = 60        # 短期缓存 1 分钟
    TTL_COUNT = 300       # count() 查询缓存 5 分钟

    def __init__(self):
        self._redis = RedisCache()
        self._memory = MemoryCache()
        self._hits = 0
        self._misses = 0

    @property
    def backend(self) -> str:
        """当前使用的缓存后端"""
        return "redis" if self._redis.connected else "memory"

    @property
    def enabled(self) -> bool:
        """缓存是否启用"""
        return settings.ENABLE_CACHE

    def _make_key(self, namespace: str, **kwargs) -> str:
        """生成缓存键"""
        if kwargs:
            # 过滤掉 None 值和 db 参数
            filtered = {k: v for k, v in sorted(kwargs.items())
                       if v is not None and k != 'db'}
            params_str = json.dumps(filtered, sort_keys=True, default=str)
            params_hash = hashlib.md5(params_str.encode()).hexdigest()[:10]
            return f"{self.PREFIX}{namespace}:{params_hash}"
        return f"{self.PREFIX}{namespace}"

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if not self.enabled:
            return None

        # 优先 Redis
        if self._redis.connected:
            value = self._redis.get(key)
        else:
            value = self._memory.get(key)

        if value is not None:
            self._hits += 1
        else:
            self._misses += 1

        return value

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """设置缓存"""
        if not self.enabled:
            return False

        if ttl is None:
            ttl = settings.CACHE_TTL

        if self._redis.connected:
            return self._redis.set(key, value, ttl)
        return self._memory.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """删除缓存"""
        if self._redis.connected:
            return self._redis.delete(key)
        return self._memory.delete(key)

    def invalidate(self, namespace: str) -> int:
        """使指定命名空间的缓存失效"""
        pattern = f"{self.PREFIX}{namespace}:*"
        if self._redis.connected:
            return self._redis.delete_pattern(pattern)
        return 0

    def clear_all(self) -> int:
        """清除所有缓存"""
        if self._redis.connected:
            return self._redis.clear(self.PREFIX)
        return self._memory.clear()

    def get_or_compute(
        self,
        namespace: str,
        compute_func: Callable[[], T],
        ttl: int = None,
        **key_params
    ) -> T:
        """
        获取缓存或计算并缓存

        Args:
            namespace: 命名空间
            compute_func: 计算函数
            ttl: 缓存时间
            **key_params: 用于生成缓存键的参数

        Returns:
            缓存或计算的结果
        """
        key = self._make_key(namespace, **key_params)

        # 尝试获取缓存
        cached = self.get(key)
        if cached is not None:
            logger.debug(f"[CACHE HIT] {namespace}")
            return cached

        # 计算结果
        logger.debug(f"[CACHE MISS] {namespace}")
        result = compute_func()

        # 转换为可序列化的格式
        cache_data = self._serialize(result)

        # 存入缓存
        self.set(key, cache_data, ttl)

        return result

    def _serialize(self, data: Any) -> Any:
        """将数据转换为可序列化的格式"""
        if hasattr(data, 'model_dump'):
            return data.model_dump()
        elif hasattr(data, 'dict'):
            return data.dict()
        elif isinstance(data, list):
            return [self._serialize(item) for item in data]
        elif isinstance(data, dict):
            return {k: self._serialize(v) for k, v in data.items()}
        return data

    def get_stats(self) -> dict:
        """获取缓存统计"""
        total = self._hits + self._misses
        return {
            "backend": self.backend,
            "enabled": self.enabled,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{(self._hits / max(total, 1)) * 100:.1f}%",
        }

    # ============== 新增：缓存键生成辅助方法 ==============

    def make_list_key(self, endpoint: str, **params) -> str:
        """
        生成列表查询的缓存键

        Args:
            endpoint: API 端点名称（如 "regulations", "genes"）
            **params: 查询参数（page, page_size, species_id 等）

        Returns:
            规范化的缓存键
        """
        return self._make_key(f"{endpoint}:list", **params)

    def make_options_key(self, endpoint: str, **params) -> str:
        """
        生成选项查询的缓存键

        Args:
            endpoint: API 端点名称（如 "regulations", "genes"）
            **params: 查询参数（species_id, gene_type 等）

        Returns:
            规范化的缓存键
        """
        return self._make_key(f"{endpoint}:options", **params)

    def get_cached_count(self, query, cache_key: str) -> int:
        """
        获取带缓存的 query.count() 结果

        优化：使用 order_by(None) 移除排序以生成更高效的 COUNT SQL

        Args:
            query: SQLAlchemy Query 对象
            cache_key: 缓存键（使用 _make_key 或 make_list_key 生成）

        Returns:
            查询结果总数（从缓存或数据库）

        Example:
            >>> cache_key = cache.make_list_key("regulations", species_id=1, page=1)
            >>> total = cache.get_cached_count(query, cache_key)
        """
        if not self.enabled:
            # Remove ORDER BY for more efficient COUNT SQL
            return query.order_by(None).count()

        # 尝试从缓存获取
        cached = self.get(cache_key)
        if cached is not None:
            logger.debug(f"[CACHE HIT] count: {cache_key}")
            return cached

        # 计算并缓存
        # Remove ORDER BY for more efficient COUNT SQL
        logger.debug(f"[CACHE MISS] count: {cache_key}")
        count = query.order_by(None).count()
        self.set(cache_key, count, self.TTL_COUNT)

        return count


# 全局缓存实例
cache = CacheService()


# ============== 装饰器 ==============

def cached(namespace: str, ttl: int = None):
    """
    缓存装饰器（同步函数）

    Usage:
        @cached("stats:overview", ttl=3600)
        def get_overview_stats(db):
            return {...}
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not cache.enabled:
                return func(*args, **kwargs)

            # 生成缓存键（过滤掉非业务参数，如 db / request）
            excluded_keys = {"db", "request"}
            key_params = {k: v for k, v in kwargs.items() if k not in excluded_keys}
            key = cache._make_key(namespace, **key_params)

            # 尝试获取缓存
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug(f"[CACHE HIT] {namespace}")
                return cached_value

            # 执行函数
            logger.debug(f"[CACHE MISS] {namespace}")
            result = func(*args, **kwargs)

            # 序列化并缓存
            cache_data = cache._serialize(result)
            cache.set(key, cache_data, ttl or cache.TTL_LIST)

            return result

        return wrapper
    return decorator


def cache_response(expire: int = 300):
    """
    异步缓存装饰器（兼容旧接口）

    Usage:
        @cache_response(expire=300)
        async def get_data():
            return {...}
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not cache.enabled:
                return await func(*args, **kwargs)

            excluded_keys = {"db", "request"}
            key_params = {k: v for k, v in kwargs.items() if k not in excluded_keys}
            key = cache._make_key(func.__name__, **key_params)

            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value

            result = await func(*args, **kwargs)
            cache_data = cache._serialize(result)
            cache.set(key, cache_data, expire)

            return result

        return wrapper
    return decorator
