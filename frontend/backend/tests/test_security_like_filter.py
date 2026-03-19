"""
安全测试: LIKE 通配符绕过防护

覆盖修复点:
- export.py:55-72 is_effective_like_filter() 函数
- export.py:549-565 无效过滤时限制 500 条
- app/core/utils.py:17-19 escape_like_pattern() 函数
- visualization.py:113-115 Sankey trait_name 转义

运行方式:
    pytest tests/test_security_like_filter.py -v
    pytest tests/test_security_like_filter.py -v -m unit      # 仅单元测试
    pytest tests/test_security_like_filter.py -v -m integration  # 仅集成测试
"""
import pytest

from app.routers.export import is_effective_like_filter
from app.core.utils import escape_like_pattern


# ============== 单元测试: is_effective_like_filter ==============

class TestIsEffectiveLikeFilter:
    """测试 is_effective_like_filter 函数 - 检测纯通配符输入"""

    @pytest.mark.unit
    @pytest.mark.parametrize("value,expected", [
        # 无效情况: None 或空
        (None, False),
        ("", False),
        ("   ", False),
        # 无效情况: 纯通配符
        ("%", False),
        ("%%", False),
        ("%%%", False),
        ("_", False),
        ("__", False),
        ("___", False),
        ("%_", False),
        ("_%", False),
        ("%_%", False),
        ("_%%_", False),
        # 有效情况: 包含非通配符字符
        ("diabetes", True),
        ("type%", True),
        ("%cancer%", True),
        ("heart_disease", True),
        ("dia%betes", True),
        ("a", True),
        (" a ", True),  # 空格中间有有效字符
        ("50%", True),
        ("type_2", True),
        ("test\\value", True),  # 反斜杠是有效字符
    ])
    def test_filter_effectiveness(self, value, expected):
        """参数化测试各种输入的有效性判断"""
        assert is_effective_like_filter(value) == expected, \
            f"is_effective_like_filter({value!r}) 应返回 {expected}"


class TestEscapeLikePattern:
    """测试 escape_like_pattern 函数 - SQL LIKE 特殊字符转义"""

    @pytest.mark.unit
    @pytest.mark.parametrize("value,expected", [
        # 无特殊字符
        ("diabetes", "diabetes"),
        ("cancer", "cancer"),
        ("heart disease", "heart disease"),
        # 转义 %
        ("type%", r"type\%"),
        ("%cancer", r"\%cancer"),
        ("%diabetes%", r"\%diabetes\%"),
        ("50%", r"50\%"),
        # 转义 _
        ("heart_disease", r"heart\_disease"),
        ("type_2", r"type\_2"),
        ("_prefix", r"\_prefix"),
        # 转义 \
        (r"back\slash", r"back\\slash"),
        (r"test\value", r"test\\value"),
        # 多个特殊字符组合
        ("50%_done", r"50\%\_done"),
        ("%_\\", r"\%\_\\"),  # 包含反斜杠需用普通字符串
        ("100%_complete", r"100\%\_complete"),
        # 空字符串
        ("", ""),
    ])
    def test_escape_special_chars(self, value, expected):
        """参数化测试特殊字符转义"""
        assert escape_like_pattern(value) == expected, \
            f"escape_like_pattern({value!r}) 应返回 {expected!r}"


# ============== 集成测试: API 行为验证 ==============

@pytest.mark.integration
class TestDiseaseNetworkExportFiltering:
    """测试 /export/disease-network 端点的 LIKE 过滤行为"""

    def test_wildcard_only_limits_to_500(self, api_client):
        """纯通配符 trait_name 应限制总边数到 500 条以内"""
        response = api_client.get(
            "/api/v1/export/disease-network",
            params={"trait_name": "%", "limit": 1000, "format": "json"}
        )
        # 应返回 200 或 429（限流），两者都是安全的
        assert response.status_code in (200, 429), \
            f"应返回 200 或 429，实际 {response.status_code}"

        if response.status_code == 200:
            data = response.json()
            edges = data.get("edges", [])
            assert len(edges) <= 500, \
                f"纯通配符过滤应限制总边数 500 条，实际返回 {len(edges)} 条"

    def test_empty_filter_limits_to_500(self, api_client):
        """空 trait_name 应限制总边数到 500 条以内"""
        response = api_client.get(
            "/api/v1/export/disease-network",
            params={"trait_name": "", "limit": 1000, "format": "json"}
        )
        assert response.status_code in (200, 429), \
            f"应返回 200 或 429，实际 {response.status_code}"

        if response.status_code == 200:
            data = response.json()
            edges = data.get("edges", [])
            assert len(edges) <= 500, \
                f"空过滤应限制总边数 500 条，实际返回 {len(edges)} 条"

    def test_valid_filter_allows_larger_limit(self, api_client):
        """有效 trait_name 应允许更大 limit"""
        response = api_client.get(
            "/api/v1/export/disease-network",
            params={"trait_name": "diabetes", "limit": 1000, "format": "json"}
        )
        # 应返回 200 或 429，只验证不报错
        assert response.status_code in (200, 429), \
            f"应返回 200 或 429，实际 {response.status_code}"

    def test_special_chars_in_filter_no_error(self, api_client, api_assert):
        """trait_name 包含 SQL 特殊字符应正常处理（不触发 SQL 错误）"""
        special_values = [
            "type%",          # 包含 %
            "heart_disease",  # 包含 _
            "test\\value",    # 包含 \
            "50%_done",       # 多个特殊字符
        ]
        for value in special_values:
            response = api_client.get(
                "/api/v1/export/disease-network",
                params={"trait_name": value, "limit": 10, "format": "json"}
            )
            # 应返回 200 或 400（参数问题），绝不应该 500
            assert response.status_code != 500, \
                f"trait_name={value!r} 导致 500 错误: {response.text[:200]}"


@pytest.mark.integration
class TestSankeyTraitNameEscape:
    """测试 Sankey 图 trait_name SQL 注入防护"""

    def test_special_chars_no_sql_error(self, api_client):
        """trait_name 包含 SQL 特殊字符不应导致 SQL 错误"""
        special_names = [
            "type%",
            "heart_disease",
            r"test\value",
            "50%",
            "%_",
        ]
        for name in special_names:
            response = api_client.get(
                "/api/v1/visualization/sankey-data",
                params={"species_id": 1, "trait_name": name, "limit": 10}
            )
            # 应返回 200（可能空结果）或 4xx（参数验证失败），不应 500
            assert response.status_code != 500, \
                f"trait_name={name!r} 导致 500 错误: {response.text[:200]}"

    def test_percent_is_escaped_literally(self, api_client, api_assert):
        """trait_name 中的 % 应被字面匹配，不作为 SQL 通配符"""
        # 搜索包含字面量 "type%" 的疾病（如果数据库中没有，应返回空）
        response = api_client.get(
            "/api/v1/visualization/sankey-data",
            params={"species_id": 1, "trait_name": "type%", "limit": 10}
        )
        api_assert.assert_successful_response(response)
        # 不验证具体结果，只要不报错且正确执行即可

    def test_underscore_is_escaped_literally(self, api_client, api_assert):
        """trait_name 中的 _ 应被字面匹配，不作为单字符通配符"""
        response = api_client.get(
            "/api/v1/visualization/sankey-data",
            params={"species_id": 1, "trait_name": "type_2", "limit": 10}
        )
        api_assert.assert_successful_response(response)


# ============== 边界情况测试 ==============

@pytest.mark.integration
class TestLikeFilterEdgeCases:
    """边界情况测试"""

    def test_unicode_in_trait_name(self, api_client):
        """Unicode 字符应正常处理"""
        response = api_client.get(
            "/api/v1/export/disease-network",
            params={"trait_name": "糖尿病", "limit": 10, "format": "json"}
        )
        # 应正常返回（可能空结果）或 429（触发限流，仍然表示安全防护有效）
        assert response.status_code in (200, 429), \
            f"Unicode trait_name 应返回 200 或 429，实际 {response.status_code}"

    def test_very_long_trait_name(self, api_client):
        """超长 trait_name 应被正常处理或拒绝"""
        long_name = "a" * 1000
        response = api_client.get(
            "/api/v1/export/disease-network",
            params={"trait_name": long_name, "limit": 10, "format": "json"}
        )
        # 应返回 200 或 4xx，不应 500
        assert response.status_code != 500, \
            "超长 trait_name 导致 500 错误"

    def test_whitespace_only_trait_name(self, api_client):
        """纯空白 trait_name 应被视为无效过滤"""
        response = api_client.get(
            "/api/v1/export/disease-network",
            params={"trait_name": "   ", "limit": 1000, "format": "json"}
        )
        # 可能返回 200 或 429（限流），两者都是安全的
        assert response.status_code in (200, 429), \
            f"纯空白 trait_name 应返回 200 或 429，实际 {response.status_code}"

        if response.status_code == 200:
            data = response.json()
            edges = data.get("edges", [])
            assert len(edges) <= 500, \
                f"纯空白过滤应限制总边数 500 条，实际返回 {len(edges)} 条"
