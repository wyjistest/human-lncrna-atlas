"""
安全测试: 输入参数验证

覆盖修复点:
- app.core.validators.parse_int_list: 解析逗号分隔的整数列表（严格模式）
- 任何无效 ID 都会返回 400 错误（Phase 9.15 增强）

运行方式:
    pytest tests/test_security_input_validation.py -v
    pytest tests/test_security_input_validation.py -v -m unit         # 仅单元测试
    pytest tests/test_security_input_validation.py -v -m integration  # 仅集成测试

历史:
    Phase 9.13: 使用 _parse_ids() 函数（软模式，忽略无效项）
    Phase 9.15: 迁移到 parse_int_list()（严格模式，拒绝任何无效项）
"""
import pytest

from fastapi import HTTPException
from app.core.validators import parse_int_list, parse_comma_list, MAX_COMMA_SEPARATED_ITEMS


# ============== 单元测试: parse_int_list ==============

class TestParseIntList:
    """测试 parse_int_list 函数 - 解析逗号分隔的整数字符串（严格模式）"""

    @pytest.mark.unit
    def test_valid_single_id(self):
        """单个有效 ID"""
        result = parse_int_list("1", param_name="test_param")
        assert result == [1]

    @pytest.mark.unit
    def test_valid_multiple_ids(self):
        """多个有效 ID"""
        result = parse_int_list("1,2,3", param_name="test_param")
        assert result == [1, 2, 3]

    @pytest.mark.unit
    def test_valid_ids_with_spaces(self):
        """带空格的有效 ID"""
        result = parse_int_list(" 1 , 2 , 3 ", param_name="test_param")
        assert result == [1, 2, 3]

    @pytest.mark.unit
    def test_empty_string_returns_none(self):
        """空字符串返回 None"""
        result = parse_int_list("", param_name="test_param")
        assert result is None

    @pytest.mark.unit
    def test_none_returns_none(self):
        """None 输入返回 None"""
        result = parse_int_list(None, param_name="test_param")
        assert result is None

    @pytest.mark.unit
    def test_single_invalid_raises_400(self):
        """单个无效 ID 时抛出 400 HTTPException"""
        with pytest.raises(HTTPException) as exc_info:
            parse_int_list("abc", param_name="species_ids")

        assert exc_info.value.status_code == 400
        assert "abc" in exc_info.value.detail
        assert "not a valid integer" in exc_info.value.detail

    @pytest.mark.unit
    def test_all_invalid_raises_400(self):
        """全部无效 ID 时抛出 400 HTTPException"""
        with pytest.raises(HTTPException) as exc_info:
            parse_int_list("abc,xyz", param_name="species_ids")

        assert exc_info.value.status_code == 400
        # 严格模式：遇到第一个无效项即失败
        assert "abc" in exc_info.value.detail

    @pytest.mark.unit
    def test_mixed_valid_invalid_raises_400(self):
        """混合有效/无效 ID 时抛出 400（严格模式）"""
        with pytest.raises(HTTPException) as exc_info:
            parse_int_list("1,abc,2", param_name="test_param")

        assert exc_info.value.status_code == 400
        assert "abc" in exc_info.value.detail

    @pytest.mark.unit
    @pytest.mark.parametrize("invalid_input,expected_invalid", [
        ("abc", "abc"),
        ("null", "null"),
        ("undefined", "undefined"),
        ("NaN", "NaN"),
        ("1.5", "1.5"),
        ("true", "true"),
        ("false", "false"),
        ("-", "-"),
        ("1-2", "1-2"),
        ("1..2", "1..2"),
    ])
    def test_various_invalid_formats(self, invalid_input, expected_invalid):
        """各种无效格式应抛出 400"""
        with pytest.raises(HTTPException) as exc_info:
            parse_int_list(invalid_input, param_name="test_param")

        assert exc_info.value.status_code == 400
        assert expected_invalid in exc_info.value.detail

    @pytest.mark.unit
    def test_negative_ids_are_parsed(self):
        """负数 ID 应被解析（可能在业务层被拒绝）"""
        result = parse_int_list("-1,-2", param_name="test_param")
        assert result == [-1, -2]

    @pytest.mark.unit
    def test_zero_is_valid(self):
        """0 是有效整数"""
        result = parse_int_list("0,1,2", param_name="test_param")
        assert result == [0, 1, 2]

    @pytest.mark.unit
    def test_large_numbers(self):
        """大数字应正常解析"""
        result = parse_int_list("999999999,1000000000", param_name="test_param")
        assert result == [999999999, 1000000000]

    @pytest.mark.unit
    def test_duplicate_ids_preserved(self):
        """重复 ID 应保留（去重由业务层处理）"""
        result = parse_int_list("1,1,2,2,3", param_name="test_param")
        assert result == [1, 1, 2, 2, 3]

    @pytest.mark.unit
    def test_trailing_comma_ignored(self):
        """尾随逗号应被忽略"""
        result = parse_int_list("1,2,3,", param_name="test_param")
        assert result == [1, 2, 3]

    @pytest.mark.unit
    def test_leading_comma_ignored(self):
        """前导逗号应被忽略"""
        result = parse_int_list(",1,2,3", param_name="test_param")
        assert result == [1, 2, 3]

    @pytest.mark.unit
    def test_max_items_exceeded_raises_400(self):
        """超过最大项数限制时抛出 400"""
        # 生成超过限制的项
        many_ids = ",".join(str(i) for i in range(MAX_COMMA_SEPARATED_ITEMS + 5))
        with pytest.raises(HTTPException) as exc_info:
            parse_int_list(many_ids, param_name="test_param")

        assert exc_info.value.status_code == 400
        assert "Maximum" in exc_info.value.detail

    @pytest.mark.unit
    def test_custom_max_items_limit(self):
        """自定义最大项数限制"""
        result = parse_int_list("1,2,3", param_name="test_param", max_items=5)
        assert result == [1, 2, 3]

        with pytest.raises(HTTPException) as exc_info:
            parse_int_list("1,2,3,4,5,6", param_name="test_param", max_items=5)

        assert exc_info.value.status_code == 400


# ============== 单元测试: parse_comma_list ==============

class TestParseCommaList:
    """测试 parse_comma_list 函数 - 解析逗号分隔的字符串列表"""

    @pytest.mark.unit
    def test_valid_items(self):
        """有效项目列表"""
        result = parse_comma_list("H3K27me3,H3K4me3", param_name="marks")
        assert result == ["H3K27me3", "H3K4me3"]

    @pytest.mark.unit
    def test_items_with_spaces(self):
        """带空格的项目"""
        result = parse_comma_list(" H3K27me3 , H3K4me3 ", param_name="marks")
        assert result == ["H3K27me3", "H3K4me3"]

    @pytest.mark.unit
    def test_empty_returns_none(self):
        """空字符串返回 None"""
        result = parse_comma_list("", param_name="marks")
        assert result is None

    @pytest.mark.unit
    def test_too_many_items_raises_400(self):
        """超过项数限制"""
        many_items = ",".join([f"item{i}" for i in range(30)])
        with pytest.raises(HTTPException) as exc_info:
            parse_comma_list(many_items, param_name="marks")

        assert exc_info.value.status_code == 400
        assert "Maximum" in exc_info.value.detail

    @pytest.mark.unit
    def test_item_too_long_raises_400(self):
        """单项过长"""
        long_item = "a" * 100
        with pytest.raises(HTTPException) as exc_info:
            parse_comma_list(long_item, param_name="marks")

        assert exc_info.value.status_code == 400
        assert "too long" in exc_info.value.detail


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

    def test_mixed_valid_invalid_ids_returns_400(self, api_client):
        """混合有效/无效 ID 应返回 400（严格模式）"""
        response = api_client.get(
            "/api/v1/regulations",
            params={"species_ids": "1,abc,2,xyz", "page_size": 5}
        )
        # Phase 9.15: 严格模式，任何无效 ID 都会导致 400
        assert response.status_code == 400, \
            f"混合有效/无效 ID 应返回 400，实际 {response.status_code}"

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
    def test_various_invalid_formats_return_400(self, api_client, invalid_ids):
        """各种无效格式应返回 400"""
        response = api_client.get(
            "/api/v1/regulations",
            params={"species_ids": invalid_ids, "page_size": 5}
        )
        # 应返回 400，不应该 500
        assert response.status_code == 400, \
            f"species_ids={invalid_ids!r} 应返回 400，实际 {response.status_code}"

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

    def test_very_long_species_ids_list_returns_400(self, api_client):
        """超过最大项数的 species_ids 列表应返回 400"""
        # 生成超过 MAX_COMMA_SEPARATED_ITEMS 的 ID
        long_ids = ",".join(str(i) for i in range(1, MAX_COMMA_SEPARATED_ITEMS + 10))
        response = api_client.get(
            "/api/v1/regulations",
            params={"species_ids": long_ids, "page_size": 5}
        )
        # Phase 9.15: 超过限制应返回 400
        assert response.status_code == 400, \
            f"超长 species_ids 列表应返回 400，实际 {response.status_code}"

    def test_within_limit_species_ids(self, api_client, api_assert):
        """在限制范围内的 species_ids 列表应正常处理"""
        # 使用 4 个有效物种 ID（符合项目的物种数量）
        valid_ids = "1,2,3,4"
        response = api_client.get(
            "/api/v1/regulations",
            params={"species_ids": valid_ids, "page_size": 5}
        )
        api_assert.assert_successful_response(response)

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
            # 应返回 400（解析失败），不应 500
            assert response.status_code == 400, \
                f"SQL 注入尝试 {attempt!r} 应返回 400，实际 {response.status_code}"
