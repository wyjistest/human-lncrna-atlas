"""通用数据模型"""
from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")


class PaginationParams(BaseModel):
    """分页参数"""

    page: int = Field(default=1, ge=1, description="页码（从1开始）")
    page_size: int = Field(default=100, ge=1, le=1000, description="每页数量")
    sort_by: Optional[str] = Field(default=None, description="排序字段")
    sort_order: Optional[str] = Field(default="asc", description="排序方向（asc/desc）")


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""

    items: List[T] = Field(description="数据列表")
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    total_pages: int = Field(description="总页数")

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """通用消息响应"""

    message: str
    code: int = 200


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str
    database: str
    redis: Optional[str] = None
    version: str
