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
from typing import Any, Optional, Callable, TypeVar, Tuple, TYPE_CHECKING
from functools import wraps

try:
    import redis
    from redis.exceptions import RedisError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    RedisError = Exception

if TYPE_CHECKING:  # pragma: no cover
    import redis as redis_types  # noqa: F401

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============== 内存缓存（回退方案） ==============

class MemoryCache:
    """
    LRU 内存缓存（支持 TTL，线程安全）

    使用 OrderedDict 实现真正的 LRU（Least Recently Used）淘汰策略：
    - 每次 get() 访问会将键移动到末尾（最近使用）
    - 空间不足时从头部（最久未使用）开始淘汰
    """

    def __init__(self, max_size: int = 1000):
        from collections import OrderedDict
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()
        # LRU 统计
        self._evictions = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if time.time() < expiry:
                    # LRU: 移动到末尾（最近访问）
                    self._cache.move_to_end(key)
                    return value
                # 过期删除
                del self._cache[key]
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        with self._lock:
            # 如果键已存在，更新并移动到末尾
            if key in self._cache:
                self._cache[key] = (value, time.time() + ttl)
                self._cache.move_to_end(key)
                return True

            # 空间检查：先淘汰过期项，再按 LRU 淘汰
            if len(self._cache) >= self._max_size:
                self._evict_expired()
            while len(self._cache) >= self._max_size:
                # LRU 淘汰：从头部删除最久未使用的项
                self._cache.popitem(last=False)
                self._evictions += 1

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

    def get_stats(self) -> dict:
        """获取内存缓存统计"""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "evictions": self._evictions,
            }


# ============== Redis 缓存 ==============

class RedisCache:
    """Redis 缓存实现"""

    def __init__(self):
        # NOTE: redis 是可选依赖；使用字符串注解避免在 ImportError 场景下触发 NameError
        self._client: Optional["redis.Redis"] = None
        self._connect()

    def _connect(self):
        """连接 Redis"""
        if not REDIS_AVAILABLE or not settings.ENABLE_CACHE:
            return

        try:
            # SECURITY: 使用 get_secret_value() 获取真实密码（SecretStr 类型）
            redis_password = settings.REDIS_PASSWORD.get_secret_value() if settings.REDIS_PASSWORD else None
            self._client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=redis_password,
                decode_responses=True,
                socket_timeout=10,  # 读写超时（增加容错性，减少网络抖动时的缓存失效）
                socket_connect_timeout=5,  # 连接建立超时
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
        # 统计字段在多线程环境下可能被并发更新，仅用于监控但仍需保证一致性
        self._stats_lock = threading.Lock()

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
            params_hash = hashlib.sha256(params_str.encode()).hexdigest()[:10]
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
            with self._stats_lock:
                self._hits += 1
        else:
            with self._stats_lock:
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

        return cache_data

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
        with self._stats_lock:
            hits = self._hits
            misses = self._misses
        total = hits + misses
        hit_rate = (hits / max(total, 1)) * 100
        stats = {
            "backend": self.backend,
            "enabled": self.enabled,
            "hits": hits,
            "misses": misses,
            "total_requests": total,
            "hit_rate": f"{hit_rate:.1f}%",
            "hit_rate_pct": round(hit_rate, 2),
        }

        # 添加后端特定统计
        if self._redis.connected:
            stats["redis"] = {
                "host": f"{settings.REDIS_HOST}:{settings.REDIS_PORT}",
                "connected": True,
            }
        else:
            stats["memory"] = self._memory.get_stats()

        return stats

    def reset_stats(self) -> None:
        """重置统计计数器（用于监控周期性重置）"""
        with self._stats_lock:
            self._hits = 0
            self._misses = 0

    # ============== 新增：缓存键生成辅助方法 ==============

    def make_key(self, namespace: str, **kwargs) -> str:
        """
        生成缓存键（公共 API）

        Args:
            namespace: 命名空间（如 "stats:overview", "conservation:matrix"）
            **kwargs: 用于生成唯一键的参数

        Returns:
            带前缀的规范化缓存键

        Example:
            >>> cache.make_key("stats:overview")
            'lncrna:stats:overview'
            >>> cache.make_key("genes:list", species_id=1, page=1)
            'lncrna:genes:list:abc123def4'
        """
        return self._make_key(namespace, **kwargs)

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

def _is_hashable(obj: Any) -> bool:
    """检查对象是否可哈希"""
    try:
        hash(obj)
        return True
    except TypeError:
        return False


def _should_exclude_arg(obj: Any) -> bool:
    """
    判断参数是否应从缓存键中排除

    排除条件：
    - 数据库连接/Session 对象
    - Request 对象
    - 不可哈希的对象
    """
    # 按类型名排除常见不可缓存对象
    type_name = type(obj).__name__
    excluded_types = {"Session", "Request", "Connection", "Engine", "scoped_session"}
    if type_name in excluded_types:
        return True

    # 排除不可哈希的对象
    if not _is_hashable(obj):
        return True

    return False


def cached(namespace: str, ttl: int = None):
    """
    缓存装饰器（同步函数）

    注意：会将可哈希的位置参数和关键字参数都纳入缓存键生成。
    数据库连接、Request 等不可哈希对象会自动排除。

    Usage:
        @cached("stats:overview", ttl=3600)
        def get_overview_stats(db, species_id: int):
            return {...}

        # 以下两种调用会生成相同的缓存键：
        get_overview_stats(db, 1)
        get_overview_stats(db, species_id=1)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not cache.enabled:
                return func(*args, **kwargs)

            # 生成缓存键：同时考虑 args 和 kwargs
            # 过滤掉非业务参数（db/request）和不可哈希对象
            excluded_keys = {"db", "request"}

            # 处理位置参数：过滤不可缓存的对象，保留可哈希参数
            hashable_args = tuple(
                arg for arg in args
                if not _should_exclude_arg(arg)
            )

            # 处理关键字参数：过滤排除的键和不可哈希值
            key_params = {
                k: v for k, v in kwargs.items()
                if k not in excluded_keys and not _should_exclude_arg(v)
            }

            # 将位置参数也纳入 key 生成（使用特殊前缀避免与 kwargs 冲突）
            if hashable_args:
                key_params["__args__"] = hashable_args

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

            return cache_data

        return wrapper
    return decorator


def cache_response(expire: int = 300):
    """
    异步缓存装饰器（兼容旧接口）

    注意：会将可哈希的位置参数和关键字参数都纳入缓存键生成。

    Usage:
        @cache_response(expire=300)
        async def get_data(species_id: int):
            return {...}
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not cache.enabled:
                return await func(*args, **kwargs)

            excluded_keys = {"db", "request"}

            # 处理位置参数
            hashable_args = tuple(
                arg for arg in args
                if not _should_exclude_arg(arg)
            )

            # 处理关键字参数
            key_params = {
                k: v for k, v in kwargs.items()
                if k not in excluded_keys and not _should_exclude_arg(v)
            }

            if hashable_args:
                key_params["__args__"] = hashable_args

            key = cache._make_key(func.__name__, **key_params)

            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value

            result = await func(*args, **kwargs)
            cache_data = cache._serialize(result)
            cache.set(key, cache_data, expire)

            return cache_data

        return wrapper
    return decorator
