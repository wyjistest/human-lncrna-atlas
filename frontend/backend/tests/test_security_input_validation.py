"""
安全测试: 输入参数验证

覆盖修复点:
- regulations.py:220-256 _parse_ids() 函数
- 全部无效 ID 时返回 400 错误（而非静默忽略）

运行方式:
    pytest tests/test_security_input_validation.py -v
    pytest tests/test_security_input_validation.py -v -m unit         # 仅单元测试
    pytest tests/test_security_input_validation.py -v -m integration  # 仅集成测试
"""
import pytest

from fastapi import HTTPException
from app.routers.regulations import _parse_ids


# ============== 单元测试: _parse_ids ==============

class TestParseIds:
    """测试 _parse_ids 函数 - 解析逗号分隔的 ID 字符串"""

    @pytest.mark.unit
    def test_valid_single_id(self):
        """单个有效 ID"""
        result = _parse_ids("1", "test_param")
        assert result == [1]

    @pytest.mark.unit
    def test_valid_multiple_ids(self):
        """多个有效 ID"""
        result = _parse_ids("1,2,3", "test_param")
        assert result == [1, 2, 3]

    @pytest.mark.unit
    def test_valid_ids_with_spaces(self):
        """带空格的有效 ID"""
        result = _parse_ids(" 1 , 2 , 3 ", "test_param")
        assert result == [1, 2, 3]

    @pytest.mark.unit
    def test_empty_string_returns_empty(self):
        """空字符串返回空列表（不抛异常）"""
        result = _parse_ids("", "test_param")
        assert result == []

    @pytest.mark.unit
    def test_all_invalid_raises_400(self):
        """全部无效 ID 时抛出 400 HTTPException"""
        with pytest.raises(HTTPException) as exc_info:
            _parse_ids("abc,xyz,!!!", "species_ids")

        assert exc_info.value.status_code == 400
        assert "Invalid species_ids format" in exc_info.value.detail
        assert "abc" in exc_info.value.detail
        assert "xyz" in exc_info.value.detail

    @pytest.mark.unit
    def test_mixed_valid_invalid_returns_valid_only(self):
        """混合有效/无效 ID 时只返回有效部分"""
        result = _parse_ids("1,abc,2,xyz,3", "test_param")
        assert result == [1, 2, 3]

    @pytest.mark.unit
    def test_raise_on_empty_false_allows_empty(self):
        """raise_on_empty=False 时不抛异常"""
        result = _parse_ids("abc,xyz", "test_param", raise_on_empty=False)
        assert result == []

    @pytest.mark.unit
    @pytest.mark.parametrize("invalid_input", [
        "abc",
        "null",
        "undefined",
        "NaN",
        "1.5",
        "true",
        "false",
        "-",
        "1-2",
        "1..2",
    ])
    def test_various_invalid_formats(self, invalid_input):
        """各种无效格式单独时应抛出 400"""
        with pytest.raises(HTTPException) as exc_info:
            _parse_ids(invalid_input, "test_param")

        assert exc_info.value.status_code == 400

    @pytest.mark.unit
    def test_negative_ids_are_parsed(self):
        """负数 ID 应被解析（可能在业务层被拒绝）"""
        # 负数在 Python 中是有效整数，_parse_ids 只做格式解析
        result = _parse_ids("-1,-2", "test_param")
        assert result == [-1, -2]

    @pytest.mark.unit
    def test_zero_is_valid(self):
        """0 是有效整数"""
        result = _parse_ids("0,1,2", "test_param")
        assert result == [0, 1, 2]

    @pytest.mark.unit
    def test_large_numbers(self):
        """大数字应正常解析"""
        result = _parse_ids("999999999,1000000000", "test_param")
        assert result == [999999999, 1000000000]

    @pytest.mark.unit
    def test_duplicate_ids_preserved(self):
        """重复 ID 应保留（去重由业务层处理）"""
        result = _parse_ids("1,1,2,2,3", "test_param")
        assert result == [1, 1, 2, 2, 3]

    @pytest.mark.unit
    def test_trailing_comma_ignored(self):
        """尾随逗号应被忽略"""
        result = _parse_ids("1,2,3,", "test_param")
        assert result == [1, 2, 3]

    @pytest.mark.unit
    def test_leading_comma_ignored(self):
        """前导逗号应被忽略"""
        result = _parse_ids(",1,2,3", "test_param")
        assert result == [1, 2, 3]


# ============== 集成测试: API 行为验证 ==============

@pytest.mark.integration
class TestRegulationsSpeciesIdsValidation:
    """测试 /regulations 端点的 species_ids 参数验证"""

    def test_valid_species_ids(self, api_client, api_assert):
        """有效的 species_ids 应正常返回"""
        response = api_client.get(
            "/api/v1/regulations",
            params={"species_ids": "1,2", "page_size": 5}
        )
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        # 验证返回的数据只包含指定物种
        for item in data.get("items", []):
            assert item.get("species_id") in (1, 2), \
                f"返回了非预期物种: {item.get('species_id')}"

    def test_all_invalid_species_ids_returns_400(self, api_client):
        """全部无效的 species_ids 应返回 400"""
        response = api_client.get(
            "/api/v1/regulations",
            params={"species_ids": "abc,xyz,!!!", "page_size": 5}
        )
        assert response.status_code == 400, \
            f"全部无效 species_ids 应返回 400，实际 {response.status_code}"

        data = response.json()
        assert "detail" in data
        assert "invalid" in data["detail"].lower()

    def test_mixed_valid_invalid_ids_uses_valid(self, api_client, api_assert):
        """混合有效/无效 ID 应只使用有效部分"""
        response = api_client.get(
            "/api/v1/regulations",
            params={"species_ids": "1,abc,2,xyz", "page_size": 5}
        )
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        # 验证返回的数据只包含有效物种 ID
        for item in data.get("items", []):
            assert item.get("species_id") in (1, 2), \
                f"返回了非预期物种: {item.get('species_id')}"

    def test_empty_species_ids_returns_all(self, api_client, api_assert):
        """空 species_ids 应返回所有物种"""
        response = api_client.get(
            "/api/v1/regulations",
            params={"species_ids": "", "page_size": 5}
        )
        api_assert.assert_successful_response(response)

    def test_single_valid_id(self, api_client, api_assert):
        """单个有效 ID"""
        response = api_client.get(
            "/api/v1/regulations",
            params={"species_ids": "1", "page_size": 5}
        )
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        for item in data.get("items", []):
            assert item.get("species_id") == 1

    @pytest.mark.parametrize("invalid_ids", [
        "not_a_number",
        "1.5,2.5",
        "null",
        "undefined",
        "NaN",
        "[1,2]",      # JSON 数组格式
        '{"id":1}',   # JSON 对象格式
    ])
    def test_various_invalid_formats_handled(self, api_client, invalid_ids):
        """各种无效格式应被妥善处理（400 或 422）"""
        response = api_client.get(
            "/api/v1/regulations",
            params={"species_ids": invalid_ids, "page_size": 5}
        )
        # 应返回 400/422，不应该 500
        assert response.status_code in (400, 422), \
            f"species_ids={invalid_ids!r} 应返回 400/422，实际 {response.status_code}"

    def test_species_ids_with_spaces(self, api_client, api_assert):
        """带空格的 species_ids 应正常处理"""
        response = api_client.get(
            "/api/v1/regulations",
            params={"species_ids": " 1 , 2 ", "page_size": 5}
        )
        api_assert.assert_successful_response(response)

    def test_nonexistent_species_id_returns_empty(self, api_client, api_assert):
        """不存在的物种 ID 应返回空结果"""
        response = api_client.get(
            "/api/v1/regulations",
            params={"species_ids": "9999", "page_size": 5}
        )
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        # 不存在的物种应返回空结果
        assert len(data.get("items", [])) == 0


# ============== 边界情况测试 ==============

@pytest.mark.integration
class TestInputValidationEdgeCases:
    """输入验证边界情况测试"""

    def test_very_long_species_ids_list(self, api_client):
        """超长 species_ids 列表应被正常处理"""
        # 生成 100 个 ID
        long_ids = ",".join(str(i) for i in range(1, 101))
        response = api_client.get(
            "/api/v1/regulations",
            params={"species_ids": long_ids, "page_size": 5}
        )
        # 应返回 200 或 4xx，不应 500
        assert response.status_code != 500, \
            "超长 species_ids 列表导致 500 错误"

    def test_sql_injection_attempt(self, api_client):
        """SQL 注入尝试应被安全处理"""
        injection_attempts = [
            "1; DROP TABLE regulations; --",
            "1 OR 1=1",
            "1' OR '1'='1",
            "1; SELECT * FROM users; --",
        ]
        for attempt in injection_attempts:
            response = api_client.get(
                "/api/v1/regulations",
                params={"species_ids": attempt, "page_size": 5}
            )
            # 应返回 400（解析失败）或正常结果，不应 500
            assert response.status_code != 500, \
                f"SQL 注入尝试 {attempt!r} 导致 500 错误"
