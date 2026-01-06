"""
共享输入验证器模块

提供跨路由的统一输入验证，确保安全性和一致性。

Phase 9.11: 统一逗号分隔列表验证，防止 DoS 攻击

Usage:
    from app.core.validators import parse_comma_list, validate_comma_list

    # 在路由中使用
    mark_types = parse_comma_list(mark_type_param)

    # Pydantic 验证器中使用
    @field_validator('mark_type')
    def validate_marks(cls, v):
        return validate_comma_list(v)
"""
import logging
from typing import List, Optional

from fastapi import HTTPException

from app.core.utils import sanitize_for_log

logger = logging.getLogger(__name__)

# ============================================================================
# 安全限制常量
# ============================================================================

# 逗号分隔列表的最大项数
MAX_COMMA_SEPARATED_ITEMS = 20

# 单个项目的最大字符长度
MAX_ITEM_LENGTH = 50

# 整个字段的最大字符长度
MAX_FIELD_LENGTH = 500

# 导出相关的更严格限制
MAX_EXPORT_MARKS = 10  # 导出端点最多允许的 marks 数量

# JSON 导出在内存中的硬上限（非流式 JSON 响应）
# NOTE: JSON 需要一次性序列化为完整对象/数组，内存占用与记录数线性增长。
# 对于更大数据集，请使用 JSONL/CSV 等流式格式。
MAX_JSON_EXPORT_LIMIT = 5000

# 分页相关的更严格限制
# SECURITY/PERF: 防止恶意构造超大 OFFSET 导致慢查询/DoS（深分页通常应改用更窄的过滤或导出接口）
MAX_PAGINATION_OFFSET = 1_000_000


# ============================================================================
# 验证函数
# ============================================================================

def compute_pagination_offset(
    page: int,
    page_size: int,
    *,
    max_offset: int = MAX_PAGINATION_OFFSET,
    param_name: str = "page",
) -> int:
    """
    计算并验证分页 offset。

    目的：
    - 防止恶意构造超大 page/page_size 组合导致数据库执行极大 OFFSET（慢查询/资源消耗）
    - 保持路由实现一致，逐步替换散落的 `(page - 1) * page_size` 计算

    Raises:
        HTTPException(400): 当 offset 超过 max_offset
    """
    offset = (page - 1) * page_size
    if offset > max_offset:
        logger.warning(
            "Pagination offset too large: %s=%s, page_size=%s -> offset=%s (max=%s)",
            param_name,
            page,
            page_size,
            offset,
            max_offset,
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f"Pagination offset too large (max offset {max_offset}). "
                "Please narrow your filters or use export endpoints for large result sets."
            ),
        )
    return offset


def normalize_optional_str(value: Optional[str]) -> Optional[str]:
    """
    Normalize optional string inputs.

    - Strips leading/trailing whitespace
    - Converts blank strings to None

    Motivation:
    - Improves cache hit rate by avoiding distinct cache keys for semantically empty inputs
    - Avoids accidental broad LIKE queries caused by whitespace-only parameters
    """
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def parse_comma_list(
    value: Optional[str],
    *,
    max_items: int = MAX_COMMA_SEPARATED_ITEMS,
    max_item_length: int = MAX_ITEM_LENGTH,
    param_name: str = "parameter",
) -> Optional[List[str]]:
    """
    解析并验证逗号分隔的字符串

    Args:
        value: 逗号分隔的字符串，如 "H3K27me3,H3K4me3"
        max_items: 最大项数限制
        max_item_length: 单项最大长度
        param_name: 参数名（用于错误消息）

    Returns:
        解析后的字符串列表，或 None（如果输入为空）

    Raises:
        HTTPException: 400 如果验证失败

    Example:
        >>> parse_comma_list("H3K27me3, H3K4me3")
        ['H3K27me3', 'H3K4me3']
        >>> parse_comma_list(None)
        None
    """
    if not value:
        return None

    # 检查总长度
    if len(value) > MAX_FIELD_LENGTH:
        logger.warning(f"Input too long for {param_name}: {len(value)} chars")
        raise HTTPException(
            status_code=400,
            detail=f"{param_name}: Input too long, maximum {MAX_FIELD_LENGTH} characters allowed"
        )

    # 解析并过滤空项
    items = [item.strip() for item in value.split(',') if item.strip()]

    if not items:
        return None

    # 检查项数
    if len(items) > max_items:
        logger.warning(f"Too many items in {param_name}: {len(items)} (max: {max_items})")
        raise HTTPException(
            status_code=400,
            detail=f"{param_name}: Maximum {max_items} items allowed, got {len(items)}"
        )

    # 检查每项长度
    for item in items:
        if len(item) > max_item_length:
            logger.warning(f"Item too long in {param_name}: {len(item)} chars")
            raise HTTPException(
                status_code=400,
                detail=f"{param_name}: Item '{item[:20]}...' too long, maximum {max_item_length} characters"
            )

    return items


def validate_comma_list(
    value: Optional[str],
    *,
    max_items: int = MAX_COMMA_SEPARATED_ITEMS,
    max_item_length: int = MAX_ITEM_LENGTH,
) -> Optional[str]:
    """
    验证逗号分隔的字符串（用于 Pydantic 验证器）

    与 parse_comma_list 不同，此函数返回原始字符串（通过验证后），
    适用于 Pydantic field_validator。

    Args:
        value: 逗号分隔的字符串
        max_items: 最大项数限制
        max_item_length: 单项最大长度

    Returns:
        原始字符串（如果验证通过），或 None

    Raises:
        ValueError: 如果验证失败（Pydantic 会捕获并转换为验证错误）

    Example:
        @field_validator('mark_type')
        def validate_marks(cls, v):
            return validate_comma_list(v)
    """
    if not value:
        return value

    # 检查总长度
    if len(value) > MAX_FIELD_LENGTH:
        raise ValueError(f"Input too long: maximum {MAX_FIELD_LENGTH} characters allowed")

    # 解析并过滤空项
    items = [item.strip() for item in value.split(',') if item.strip()]

    if not items:
        return value

    # 检查项数
    if len(items) > max_items:
        raise ValueError(f"Too many items: maximum {max_items} allowed, got {len(items)}")

    # 检查每项长度
    for item in items:
        if len(item) > max_item_length:
            raise ValueError(f"Item too long: maximum {max_item_length} characters, got {len(item)}")

    return value


def parse_int_list(
    value: Optional[str],
    *,
    max_items: int = MAX_COMMA_SEPARATED_ITEMS,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
    param_name: str = "parameter",
) -> Optional[List[int]]:
    """
    解析并验证逗号分隔的整数列表

    Args:
        value: 逗号分隔的整数字符串，如 "1,2,3,4"
        max_items: 最大项数限制
        param_name: 参数名（用于错误消息）

    Returns:
        解析后的整数列表，或 None（如果输入为空）

    Raises:
        HTTPException: 400 如果验证失败或包含非整数

    Example:
        >>> parse_int_list("1, 2, 3")
        [1, 2, 3]
    """
    if not value:
        return None

    # 先做字符串级别的验证
    items_str = parse_comma_list(value, max_items=max_items, param_name=param_name)
    if not items_str:
        return None

    # 转换为整数
    result = []
    for item in items_str:
        try:
            parsed_int = int(item)
        except ValueError:
            logger.warning(
                "Invalid integer in %s: %s",
                param_name,
                sanitize_for_log(item, max_length=200),
            )
            raise HTTPException(
                status_code=400,
                detail=f"{param_name}: '{item}' is not a valid integer"
            )

        if min_value is not None and parsed_int < min_value:
            logger.warning("%s out of range (<%s): %s", param_name, min_value, parsed_int)
            raise HTTPException(
                status_code=400,
                detail=f"{param_name}: '{parsed_int}' is less than minimum allowed value ({min_value})",
            )
        if max_value is not None and parsed_int > max_value:
            logger.warning("%s out of range (>%s): %s", param_name, max_value, parsed_int)
            raise HTTPException(
                status_code=400,
                detail=f"{param_name}: '{parsed_int}' is greater than maximum allowed value ({max_value})",
            )

        result.append(parsed_int)

    return result


__all__ = [
    "MAX_COMMA_SEPARATED_ITEMS",
    "MAX_ITEM_LENGTH",
    "MAX_FIELD_LENGTH",
    "MAX_EXPORT_MARKS",
    "MAX_PAGINATION_OFFSET",
    "compute_pagination_offset",
    "parse_comma_list",
    "validate_comma_list",
    "parse_int_list",
]
