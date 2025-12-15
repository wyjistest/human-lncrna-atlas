"""
测试配置和共享 Fixtures
"""
import pytest
import httpx
from typing import Generator, Any
import sys
import os

# 添加项目根目录到 path，以便导入 app 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.schemas.gene import GeneListItem, GeneDetail
from app.schemas.regulation import RegulationListItem, RegulationDetail
from app.schemas.stats import OverviewStats


# ============== 配置 ==============

BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"


# ============== HTTP Client Fixtures ==============

@pytest.fixture(scope="session")
def base_url() -> str:
    """返回 API 基础 URL"""
    return BASE_URL


@pytest.fixture(scope="session")
def api_url() -> str:
    """返回完整 API URL（含前缀）"""
    return f"{BASE_URL}{API_PREFIX}"


@pytest.fixture(scope="session")
def client() -> Generator[httpx.Client, None, None]:
    """创建 httpx 同步客户端（会话级别复用）"""
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="function")
def api_client(client: httpx.Client) -> httpx.Client:
    """每个测试函数使用的 API 客户端"""
    return client


# ============== Schema 验证辅助函数 ==============

def validate_paginated_response(data: dict, item_schema: type) -> list:
    """
    验证分页响应结构并返回验证后的 items

    Args:
        data: API 响应 JSON
        item_schema: Pydantic 模型类

    Returns:
        验证后的 items 列表

    Raises:
        AssertionError: 如果结构不符合预期
        ValidationError: 如果数据不符合 Schema
    """
    # 验证分页字段
    assert "total" in data, "响应缺少 'total' 字段"
    assert "page" in data, "响应缺少 'page' 字段"
    assert "page_size" in data, "响应缺少 'page_size' 字段"
    assert "items" in data, "响应缺少 'items' 字段"

    assert isinstance(data["total"], int), "'total' 必须是整数"
    assert isinstance(data["page"], int), "'page' 必须是整数"
    assert isinstance(data["page_size"], int), "'page_size' 必须是整数"
    assert isinstance(data["items"], list), "'items' 必须是列表"

    # 验证每个 item 符合 Schema
    validated_items = []
    for i, item in enumerate(data["items"]):
        try:
            validated = item_schema.model_validate(item)
            validated_items.append(validated)
        except Exception as e:
            raise AssertionError(f"Item[{i}] 不符合 {item_schema.__name__} Schema: {e}")

    return validated_items


def validate_single_response(data: dict, schema: type) -> Any:
    """
    验证单个响应并返回验证后的对象

    Args:
        data: API 响应 JSON
        schema: Pydantic 模型类

    Returns:
        验证后的对象
    """
    try:
        return schema.model_validate(data)
    except Exception as e:
        raise AssertionError(f"响应不符合 {schema.__name__} Schema: {e}")


# ============== 常用测试数据 ==============

@pytest.fixture
def known_gene_id() -> int:
    """已知存在的基因 ID（用于详情测试）"""
    return 17276  # 从现有测试中获取


@pytest.fixture
def known_regulation_id() -> int:
    """已知存在的调控关系 ID"""
    return 804941


@pytest.fixture
def known_disease_id() -> int:
    """已知存在的疾病 ID"""
    return 1


# ============== Schema Fixtures（方便测试使用） ==============

@pytest.fixture
def gene_list_schema():
    """基因列表 Schema"""
    return GeneListItem


@pytest.fixture
def gene_detail_schema():
    """基因详情 Schema"""
    return GeneDetail


@pytest.fixture
def regulation_list_schema():
    """调控关系列表 Schema"""
    return RegulationListItem


@pytest.fixture
def regulation_detail_schema():
    """调控关系详情 Schema"""
    return RegulationDetail


@pytest.fixture
def overview_stats_schema():
    """统计概览 Schema"""
    return OverviewStats


# ============== 断言辅助 ==============

class APIAssertions:
    """API 测试断言辅助类"""

    @staticmethod
    def assert_successful_response(response: httpx.Response, expected_status: int = 200):
        """断言响应成功"""
        assert response.status_code == expected_status, \
            f"期望状态码 {expected_status}，实际 {response.status_code}，响应: {response.text[:500]}"

    @staticmethod
    def assert_json_response(response: httpx.Response) -> dict:
        """断言响应是有效 JSON 并返回"""
        assert "application/json" in response.headers.get("content-type", ""), \
            f"响应不是 JSON，Content-Type: {response.headers.get('content-type')}"
        return response.json()

    @staticmethod
    def assert_pagination_bounds(data: dict, page: int, page_size: int):
        """断言分页参数正确"""
        assert data["page"] == page, f"页码应为 {page}，实际 {data['page']}"
        assert data["page_size"] == page_size, f"页大小应为 {page_size}，实际 {data['page_size']}"
        assert len(data["items"]) <= page_size, \
            f"返回项数 {len(data['items'])} 超过页大小 {page_size}"


@pytest.fixture
def api_assert() -> APIAssertions:
    """API 断言辅助"""
    return APIAssertions()
