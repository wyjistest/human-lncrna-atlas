"""
测试配置和共享 Fixtures
"""
import os
import sys
from typing import Any, Generator

import httpx
import pytest

# 添加项目根目录到 path，以便导入 app 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.schemas.gene import GeneDetail, GeneListItem
from app.schemas.regulation import RegulationDetail, RegulationListItem
from app.schemas.stats import OverviewStats


@pytest.fixture(scope="session", autouse=True)
def _install_uvloop_policy() -> None:
    """
    为测试安装 uvloop 事件循环策略（如果可用）。

    说明：
    - 部分环境下（例如受限沙箱/特定 asyncio 实现）默认事件循环在跨线程唤醒上可能不稳定，
      会导致 FastAPI/Starlette 的同步路由（threadpool）或 TestClient 请求卡死。
    - uvicorn[standard] 通常会带上 uvloop；此处在测试侧显式启用，以提升稳定性与性能。
    """
    try:
        import uvloop  # type: ignore
    except Exception:
        return

    uvloop.install()

# ============== 配置 ==============

BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"


def _truthy_env(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def pytest_configure(config: pytest.Config) -> None:  # pragma: no cover
    """
    Register custom markers even when pytest.ini is not discovered (e.g. running pytest from repo root).
    This prevents PytestUnknownMarkWarning noise and keeps marker semantics consistent.
    """
    config.addinivalue_line(
        "markers",
        "unit: Pure unit tests - no external dependencies (database, network)",
    )
    config.addinivalue_line(
        "markers",
        "integration: Integration tests - require running database/server",
    )
    config.addinivalue_line(
        "markers",
        "performance: Performance benchmarks - may take longer to run",
    )
    config.addinivalue_line(
        "markers",
        "slow: Tests that take > 5 seconds (use -m 'not slow' to skip)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """
    Make `pytest` runnable out-of-the-box by skipping integration/performance tests unless explicitly enabled.

    Rationale:
    - integration tests depend on an externally running API server + database,
      and will fail in constrained/CI environments by default.
    - performance tests are intentionally heavier and should be opt-in.
    """
    run_integration = _truthy_env("RUN_INTEGRATION_TESTS")
    run_performance = _truthy_env("RUN_PERFORMANCE_TESTS")

    # If a custom API URL is provided, assume integration tests are intended.
    if os.getenv("TEST_API_URL"):
        run_integration = True

    for item in items:
        if "integration" in item.keywords and not run_integration:
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        "Integration tests are opt-in. "
                        "Set RUN_INTEGRATION_TESTS=1 (and ensure TEST_API_URL points to a running API)."
                    )
                )
            )
        if "performance" in item.keywords and not run_performance:
            item.add_marker(
                pytest.mark.skip(
                    reason="Performance tests are opt-in. Set RUN_PERFORMANCE_TESTS=1 to enable."
                )
            )


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
# 可通过环境变量配置，支持不同环境/数据集

@pytest.fixture(scope="session")
def known_gene_id(client: httpx.Client) -> int:
    """已知存在的基因 ID（用于详情测试）"""
    return resolve_existing_resource_id(
        api_client=client,
        env_name="TEST_KNOWN_GENE_ID",
        fallback_id=17276,
        list_path="/api/v1/genes?page=1&page_size=1",
        detail_path_template="/api/v1/genes/{resource_id}",
        id_field="gene_id",
    )


@pytest.fixture(scope="session")
def known_regulation_id(client: httpx.Client) -> int:
    """已知存在的调控关系 ID"""
    return resolve_existing_resource_id(
        api_client=client,
        env_name="TEST_KNOWN_REGULATION_ID",
        fallback_id=804941,
        list_path="/api/v1/regulations?page=1&page_size=1",
        detail_path_template="/api/v1/regulations/{resource_id}",
        id_field="regulation_id",
    )


@pytest.fixture
def known_disease_id() -> int:
    """已知存在的疾病 ID"""
    return int(os.getenv("TEST_KNOWN_DISEASE_ID", "1"))


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
        assert response.status_code == expected_status, (
            f"期望状态码 {expected_status}，实际 {response.status_code}，响应: {response.text[:500]}"
        )

    @staticmethod
    def assert_json_response(response: httpx.Response) -> dict:
        """断言响应是有效 JSON 并返回"""
        assert "application/json" in response.headers.get("content-type", ""), (
            f"响应不是 JSON，Content-Type: {response.headers.get('content-type')}"
        )
        return response.json()

    @staticmethod
    def assert_pagination_bounds(data: dict, page: int, page_size: int):
        """断言分页参数正确"""
        assert data["page"] == page, f"页码应为 {page}，实际 {data['page']}"
        assert data["page_size"] == page_size, f"页大小应为 {page_size}，实际 {data['page_size']}"
        assert len(data["items"]) <= page_size, f"返回项数 {len(data['items'])} 超过页大小 {page_size}"


@pytest.fixture
def api_assert() -> APIAssertions:
    """API 断言辅助"""
    return APIAssertions()


def resolve_existing_resource_id(
    api_client: httpx.Client,
    env_name: str,
    fallback_id: int,
    list_path: str,
    detail_path_template: str,
    id_field: str,
) -> int:
    """
    解析当前测试环境中真实存在的资源 ID。

    优先使用环境变量或历史默认值；若详情接口不可用，则回退到列表接口首条记录，
    避免合同测试被特定样本数据集的固定 ID 绑死。
    """
    candidate = _parse_positive_int(os.getenv(env_name)) or fallback_id
    detail_response = api_client.get(detail_path_template.format(resource_id=candidate))
    if detail_response.status_code == 200:
        return candidate

    list_response = api_client.get(list_path)
    assert list_response.status_code == 200, (
        f"无法通过 {list_path} 解析可用 ID，状态码: {list_response.status_code}，"
        f"响应: {list_response.text[:500]}"
    )

    payload = list_response.json()
    items = payload.get("items")
    assert isinstance(items, list) and items, f"{list_path} 未返回可用 items"

    resolved_id = _parse_positive_int(items[0].get(id_field))
    assert resolved_id is not None, f"{list_path} 返回的首条记录缺少有效的 {id_field}"
    return resolved_id


def _parse_positive_int(value: Any) -> int | None:
    """将环境变量或 JSON 字段安全解析为正整数。"""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


# ============== 安全测试 Fixtures ==============

@pytest.fixture
def security_test_patterns() -> dict:
    """
    返回常见的安全测试输入模式

    用于参数化测试各种安全边界情况
    """
    return {
        "like_wildcards": [
            "%", "%%", "%%%",
            "_", "__", "___",
            "%_", "_%", "%_%",
        ],
        "sql_injection": [
            "'; DROP TABLE users; --",
            "1 OR 1=1",
            "1; SELECT * FROM passwords",
            "' OR '1'='1",
            "1; DELETE FROM regulations; --",
        ],
        "invalid_ids": [
            "abc", "null", "undefined", "NaN",
            "1.5", "true", "false",
            "[1,2]", '{"id":1}',
        ],
        "special_chars": [
            "\\", "'", '"',
            "<script>", "{{", "}}",
            "\x00", "\n", "\r\n",
        ],
        "unicode": [
            "糖尿病", "émoji", "🧬",
            "\u0000", "\uffff",
        ],
    }


@pytest.fixture
def expect_no_500_error():
    """
    断言响应不是 500 错误的辅助函数

    用法:
        response = api_client.get("/some/endpoint")
        expect_no_500_error(response)
    """

    def _assert(response: httpx.Response, context: str = ""):
        msg = "不应返回 500 错误"
        if context:
            msg = f"{context}: {msg}"
        assert response.status_code != 500, (
            f"{msg}，实际: {response.status_code}，响应: {response.text[:300]}"
        )
        return response

    return _assert


@pytest.fixture
def expect_client_error():
    """
    断言响应是客户端错误 (4xx) 的辅助函数

    用法:
        response = api_client.get("/some/endpoint", params={"invalid": "param"})
        expect_client_error(response)
    """

    def _assert(response: httpx.Response, context: str = ""):
        msg = "应返回 4xx 客户端错误"
        if context:
            msg = f"{context}: {msg}"
        assert 400 <= response.status_code < 500, f"{msg}，实际: {response.status_code}"
        return response

    return _assert
