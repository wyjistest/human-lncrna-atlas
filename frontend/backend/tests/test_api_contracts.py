"""
API 合同测试 - 验证所有 API 响应符合定义的 Schema

这些测试确保 API 返回的数据结构与 Pydantic Schema 一致，
防止后端更改破坏前端期望的数据格式。

运行: pytest tests/test_api_contracts.py -v
"""
import pytest
import httpx

from conftest import (
    validate_paginated_response,
    validate_single_response,
)
from app.schemas.gene import GeneListItem, GeneDetail
from app.schemas.regulation import RegulationListItem, RegulationDetail
from app.schemas.stats import OverviewStats
from app.schemas.disease import TraitGeneAssociationDetail, TraitDetail

pytestmark = pytest.mark.integration


class TestGenesAPIContract:
    """基因 API 合同测试"""

    def test_genes_list_contract(self, api_client: httpx.Client, api_assert):
        """验证基因列表响应符合 GeneListItem Schema"""
        response = api_client.get("/api/v1/genes?page=1&page_size=5")
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        # 验证分页结构和每个 item 的 Schema
        items = validate_paginated_response(data, GeneListItem)

        # 额外业务断言
        assert data["total"] > 0, "基因总数应大于 0"
        assert len(items) == 5, "应返回 5 条记录"

        # 验证关键字段存在且有值
        for item in items:
            assert item.gene_id > 0
            assert item.species_name  # 非空字符串
            assert item.gene_type in ("lncRNA", "protein_coding")

    def test_genes_list_with_filters_contract(self, api_client: httpx.Client, api_assert):
        """验证带筛选条件的基因列表响应"""
        # 测试物种筛选
        response = api_client.get("/api/v1/genes?species_id=1&page_size=3")
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        items = validate_paginated_response(data, GeneListItem)

        # 所有结果应属于人类
        for item in items:
            assert item.species_name == "人类", f"筛选物种错误: {item.species_name}"

    def test_genes_detail_contract(
        self, api_client: httpx.Client, api_assert, known_gene_id: int
    ):
        """验证基因详情响应符合 GeneDetail Schema"""
        response = api_client.get(f"/api/v1/genes/{known_gene_id}")
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        # 验证 Schema
        gene = validate_single_response(data, GeneDetail)

        # 验证关键字段
        assert gene.gene_id == known_gene_id
        assert gene.species_name  # 非空
        assert isinstance(gene.orthologs, list)  # orthologs 应是列表

    def test_genes_detail_not_found(self, api_client: httpx.Client):
        """验证不存在的基因返回 404"""
        response = api_client.get("/api/v1/genes/999999999")
        assert response.status_code == 404


class TestRegulationsAPIContract:
    """调控关系 API 合同测试"""

    def test_regulations_list_contract(self, api_client: httpx.Client, api_assert):
        """验证调控关系列表响应符合 RegulationListItem Schema"""
        response = api_client.get("/api/v1/regulations?page=1&page_size=5")
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        items = validate_paginated_response(data, RegulationListItem)

        assert data["total"] > 0, "调控关系总数应大于 0"

        # 验证关键字段
        for item in items:
            assert item.regulation_id > 0
            assert item.species_id > 0
            assert item.species_name
            assert item.lncrna_gene_id > 0
            assert item.target_gene_id > 0
            # binding_affinity 可能为 None 或 Decimal
            if item.binding_affinity is not None:
                assert float(item.binding_affinity) >= 0

    def test_regulations_ba_filter_contract(self, api_client: httpx.Client, api_assert):
        """验证 BA 筛选功能和响应"""
        response = api_client.get("/api/v1/regulations?min_ba=100&max_ba=200&page_size=5")
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        items = validate_paginated_response(data, RegulationListItem)

        # 验证 BA 范围
        for item in items:
            if item.binding_affinity is not None:
                ba = float(item.binding_affinity)
                assert 100 <= ba <= 200, f"BA 应在 100-200 范围内，实际: {ba}"

    def test_regulations_detail_contract(
        self, api_client: httpx.Client, api_assert, known_regulation_id: int
    ):
        """验证调控关系详情响应符合 RegulationDetail Schema"""
        response = api_client.get(f"/api/v1/regulations/{known_regulation_id}")
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        regulation = validate_single_response(data, RegulationDetail)

        assert regulation.regulation_id == known_regulation_id
        assert regulation.species_name

        # 验证序列可用性标记存在
        assert isinstance(regulation.lncrna_sequence_available, bool)
        assert isinstance(regulation.dna_sequence_available, bool)


class TestStatsAPIContract:
    """统计 API 合同测试"""

    def test_stats_overview_contract(self, api_client: httpx.Client, api_assert):
        """验证统计概览响应符合 OverviewStats Schema"""
        response = api_client.get("/api/v1/stats/overview")
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        stats = validate_single_response(data, OverviewStats)

        # 验证关键统计数据
        assert stats.total_genes > 0
        assert stats.total_regulations > 0
        assert stats.total_core_genes > 0

        # 验证物种统计
        assert len(stats.species_stats) == 4, "应有 4 个物种的统计"

        # 验证每个物种统计符合 SpeciesStats
        for sp_stat in stats.species_stats:
            assert sp_stat.species_id > 0
            assert sp_stat.species_name
            assert sp_stat.gene_count >= 0
            assert sp_stat.regulation_count >= 0

    def test_stats_top_genes_contract(self, api_client: httpx.Client, api_assert):
        """验证 Top 基因响应结构"""
        response = api_client.get("/api/v1/stats/top-genes?limit=10")
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        assert isinstance(data, list), "Top 基因应返回列表"
        assert len(data) <= 10, "不应超过 limit"

        # 验证每个 item 的关键字段
        for item in data:
            assert "gene_id" in item
            assert "gene_name" in item
            assert "regulation_count" in item
            assert "species_name" in item


class TestDiseasesAPIContract:
    """疾病 API 合同测试"""

    def test_diseases_list_contract(self, api_client: httpx.Client, api_assert):
        """验证疾病列表响应符合 TraitGeneAssociationDetail Schema"""
        response = api_client.get("/api/v1/diseases?page=1&page_size=5")
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        items = validate_paginated_response(data, TraitGeneAssociationDetail)

        assert data["total"] > 0

        # 验证关键字段
        for item in items:
            assert item.trait_id > 0
            assert item.trait_name
            assert item.ontology_id > 0
            assert item.ontology_name

    def test_diseases_detail_contract(
        self, api_client: httpx.Client, api_assert, known_disease_id: int
    ):
        """验证疾病详情响应符合 TraitDetail Schema"""
        response = api_client.get(f"/api/v1/diseases/{known_disease_id}")
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        trait = validate_single_response(data, TraitDetail)

        assert trait.trait_id == known_disease_id
        assert trait.trait_name


class TestAPIErrorHandling:
    """API 错误处理合同测试"""

    def test_invalid_page_returns_empty(self, api_client: httpx.Client, api_assert):
        """超出范围的页码应返回空列表，不报错"""
        response = api_client.get("/api/v1/genes?page=999999&page_size=10")
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        assert data["items"] == []
        assert data["total"] > 0  # 总数仍应正确

    def test_invalid_id_returns_404(self, api_client: httpx.Client):
        """不存在的 ID 应返回 404"""
        endpoints = [
            "/api/v1/genes/999999999",
            "/api/v1/regulations/999999999",
            "/api/v1/diseases/999999999",
        ]

        for endpoint in endpoints:
            response = api_client.get(endpoint)
            assert response.status_code == 404, f"{endpoint} 应返回 404"

    def test_invalid_params_handled(self, api_client: httpx.Client):
        """无效参数应被妥善处理（返回 422 或忽略）"""
        # 负数页码
        response = api_client.get("/api/v1/genes?page=-1")
        assert response.status_code in (200, 422), "负数页码应返回 422 或被忽略"

        # 非数字参数
        response = api_client.get("/api/v1/genes?page=abc")
        assert response.status_code == 422, "非数字页码应返回 422"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
