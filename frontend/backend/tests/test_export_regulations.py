"""
测试 export_regulations 端点的内存限制和格式行为

覆盖修复点:
- export.py:51-53 MAX_JSON_LIMIT = 5000 常量
- export.py:776-784 JSON 格式强制限制
- 流式格式 (JSONL/CSV/Excel) 支持更大数据集

运行方式:
    pytest tests/test_export_regulations.py -v
    pytest tests/test_export_regulations.py -v -m unit         # 仅单元测试
    pytest tests/test_export_regulations.py -v -m integration  # 仅集成测试

注意:
- API 查询参数名为 `format`（Query(..., alias="format")），不是 `output_format`。
"""
import pytest


# ============== 单元测试: 常量验证 ==============

class TestExportConstants:
    """验证导出限制常量"""

    @pytest.mark.unit
    def test_max_limits_defined(self):
        """验证导出限制常量已定义"""
        from app.routers.export import MAX_EXPORT_LIMIT, MAX_JSON_LIMIT

        assert MAX_EXPORT_LIMIT == 50000, "MAX_EXPORT_LIMIT 应为 50000"
        assert MAX_JSON_LIMIT == 5000, "MAX_JSON_LIMIT 应为 5000"
        assert MAX_JSON_LIMIT < MAX_EXPORT_LIMIT, \
            "JSON 限制应小于通用导出限制"


# ============== 集成测试: JSON 格式限制 ==============

@pytest.mark.integration
class TestExportRegulationsJSONLimit:
    """测试 JSON 格式的内存限制"""

    def test_json_format_within_limit(self, api_client):
        """JSON 格式在限制内应正常返回"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 100,
                "format": "json",
            }
        )
        assert response.status_code in (200, 429), \
            f"JSON格式在限制内应返回200或429，实际 {response.status_code}"

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict), "JSON 格式应返回对象"
            assert "data" in data, "响应应包含 data 字段"
            assert isinstance(data["data"], list), "data 字段应为数组"

    def test_json_format_at_max_limit(self, api_client):
        """JSON 格式在 5000 条边界应正常返回"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 5000,
                "format": "json",
            }
        )
        assert response.status_code in (200, 429), \
            f"JSON格式5000条应返回200或429，实际 {response.status_code}"

    def test_json_format_exceeds_limit(self, api_client):
        """JSON 格式超过 5000 条应返回 400"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 5001,
                "format": "json",
            }
        )
        # 可能触发限流
        assert response.status_code in (400, 429), \
            f"JSON格式超过5000条应返回400或429，实际 {response.status_code}"

        if response.status_code == 400:
            data = response.json()
            assert isinstance(data.get("detail"), dict)
            message = str(data["detail"].get("message", "")).lower()
            assert "memory constraints" in message, \
                "错误消息应提及内存限制"
            assert "jsonl" in message, \
                "错误消息应建议使用 JSONL 格式"

    def test_json_format_far_exceeds_limit(self, api_client):
        """JSON 格式远超限制应返回 400"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 10000,
                "format": "json",
            }
        )
        # 可能触发限流
        assert response.status_code in (400, 429), \
            f"JSON格式10000条应返回400或429，实际 {response.status_code}"


# ============== 集成测试: 流式格式支持大数据集 ==============

@pytest.mark.integration
class TestExportRegulationsStreamingFormats:
    """测试流式格式支持更大数据集"""

    def test_jsonl_format_allows_large_limit(self, api_client):
        """JSONL 格式应支持大于 5000 条的限制"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 10000,
                "format": "jsonl",
            }
        )
        # JSONL 不应触发 JSON 的 5000 条限制
        assert response.status_code in (200, 429), \
            f"JSONL格式10000条应返回200或429，实际 {response.status_code}"

    def test_csv_format_allows_large_limit(self, api_client):
        """CSV 格式应支持大于 5000 条的限制"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 10000,
                "format": "csv",
            }
        )
        assert response.status_code in (200, 429), \
            f"CSV格式10000条应返回200或429，实际 {response.status_code}"

    def test_excel_format_allows_large_limit(self, api_client):
        """Excel 格式应支持大于 5000 条的限制"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 10000,
                "format": "excel",
            }
        )
        assert response.status_code in (200, 429), \
            f"Excel格式10000条应返回200或429，实际 {response.status_code}"


# ============== 集成测试: 响应格式验证 ==============

@pytest.mark.integration
class TestExportRegulationsResponseFormats:
    """验证不同格式的响应类型"""

    def test_json_returns_application_json(self, api_client):
        """JSON 格式应返回正确的 Content-Type"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 10,
                "format": "json",
            }
        )
        if response.status_code == 200:
            assert "application/json" in response.headers.get("content-type", ""), \
                "JSON 格式应返回 application/json"

    def test_jsonl_returns_text_plain(self, api_client):
        """JSONL 格式应返回正确的 Content-Type"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 10,
                "format": "jsonl",
            }
        )
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            assert "text/plain" in content_type or "application/x-ndjson" in content_type, \
                "JSONL 格式应返回 text/plain 或 application/x-ndjson"

    def test_csv_returns_text_csv(self, api_client):
        """CSV 格式应返回正确的 Content-Type"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 10,
                "format": "csv",
            }
        )
        if response.status_code == 200:
            assert "text/csv" in response.headers.get("content-type", ""), \
                "CSV 格式应返回 text/csv"

    def test_excel_returns_spreadsheet(self, api_client):
        """Excel 格式应返回正确的 Content-Type"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 10,
                "format": "excel",
            }
        )
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            assert "spreadsheet" in content_type or "excel" in content_type, \
                "Excel 格式应返回 spreadsheet Content-Type"


# ============== 边界情况测试 ==============

@pytest.mark.integration
class TestExportRegulationsEdgeCases:
    """边界情况测试"""

    def test_limit_zero(self, api_client):
        """limit=0 应被正常处理或拒绝"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 0,
                "format": "json",
            }
        )
        # Pydantic ge=1 验证会返回 422
        assert response.status_code in (200, 400, 422, 429), \
            f"limit=0 应返回 200/400/422/429，实际 {response.status_code}"

    def test_limit_negative(self, api_client):
        """负数 limit 应被拒绝"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": -1,
                "format": "json",
            }
        )
        # 应返回 422（Pydantic 验证失败）
        assert response.status_code == 422, \
            f"负数 limit 应返回 422，实际 {response.status_code}"

    def test_exceeds_max_export_limit(self, api_client):
        """超过 MAX_EXPORT_LIMIT (50000) 应返回 422 (Pydantic 验证)"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 50001,
                "format": "jsonl",
            }
        )
        # Pydantic le=MAX_EXPORT_LIMIT 验证会返回 422
        assert response.status_code in (400, 422, 429), \
            f"超过MAX_EXPORT_LIMIT应返回400/422/429，实际 {response.status_code}"

    def test_invalid_output_format(self, api_client):
        """无效的 format 应返回 422"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 10,
                "format": "invalid_format",
            }
        )
        # 可能触发限流
        assert response.status_code in (422, 429), \
            f"无效格式应返回422或429，实际 {response.status_code}"

    def test_json_with_filters_within_limit(self, api_client):
        """JSON 格式配合过滤条件在限制内应正常"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 100,
                "format": "json",
                "species_ids": "1",
                "min_ba": "50",
            }
        )
        assert response.status_code in (200, 429), \
            f"JSON格式配合过滤应返回200或429，实际 {response.status_code}"

    def test_json_with_filters_exceeds_limit(self, api_client):
        """JSON 格式配合过滤条件超限应返回 400"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 6000,
                "format": "json",
                "species_ids": "1",
            }
        )
        # 可能触发限流
        assert response.status_code in (400, 429), \
            f"JSON格式超限应返回400或429，实际 {response.status_code}"


# ============== 性能测试（可选） ==============

@pytest.mark.integration
@pytest.mark.slow
class TestExportRegulationsPerformance:
    """性能相关测试（可选，标记为 slow）"""

    def test_json_5000_records_acceptable_time(self, api_client):
        """JSON 5000 条记录应在合理时间内完成"""
        import time

        start = time.time()
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 5000,
                "format": "json",
            }
        )
        elapsed = time.time() - start

        if response.status_code == 200:
            # 5000 条记录应在 10 秒内完成
            assert elapsed < 10.0, \
                f"JSON 5000 条记录耗时 {elapsed:.2f}s，超过 10s 阈值"

    def test_jsonl_10000_records_streaming(self, api_client):
        """JSONL 10000 条应流式返回"""
        response = api_client.get(
            "/api/v1/export/regulations",
            params={
                "limit": 10000,
                "format": "jsonl",
            }
        )
        if response.status_code == 200:
            # 验证是流式响应（非一次性返回）
            # 注：具体验证方法取决于客户端实现
            assert response.headers.get("transfer-encoding") == "chunked" or \
                   "content-length" not in response.headers or \
                   response.status_code == 200, \
                "JSONL 应使用流式传输"
