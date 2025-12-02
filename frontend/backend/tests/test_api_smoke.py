"""
API冒烟测试 - 验证所有核心端点
运行: pytest tests/test_api_smoke.py -v
"""
import pytest
import requests
from typing import Dict, Any

BASE_URL = "http://localhost:8000"


class TestHealthCheck:
    """健康检查测试"""

    def test_health_endpoint(self):
        """测试健康检查端点"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "healthy"


class TestGenesAPI:
    """基因API测试"""

    def test_genes_list(self):
        """测试基因列表 - 验证分页修复"""
        response = requests.get(f"{BASE_URL}/api/v1/genes?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()

        # 验证分页
        assert data["total"] == 17248, "总数应为17248（不是1）"
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert len(data["items"]) == 10

        # 验证字段
        item = data["items"][0]
        assert "gene_id" in item
        assert "species_name" in item, "species_name字段应存在"
        assert "regulation_count" in item

    def test_genes_detail(self):
        """测试基因详情"""
        response = requests.get(f"{BASE_URL}/api/v1/genes/17276")
        assert response.status_code == 200
        data = response.json()

        assert data["gene_id"] == 17276
        assert "species_name" in data
        assert "orthologs" in data


class TestRegulationsAPI:
    """调控关系API测试"""

    def test_regulations_list(self):
        """测试调控关系列表 - 验证子查询和species_id"""
        response = requests.get(f"{BASE_URL}/api/v1/regulations?page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()

        # 验证分页
        assert data["total"] == 804630
        assert len(data["items"]) == 5

        # 验证字段
        item = data["items"][0]
        assert "species_id" in item, "species_id字段应存在"
        assert "species_name" in item
        assert "target_gene_name" in item, "target_gene_name应正常返回（子查询修复）"
        assert item["target_gene_name"] is not None

    def test_regulations_high_ba_filter(self):
        """测试高阈值过滤 - 验证BA上限修复"""
        response = requests.get(f"{BASE_URL}/api/v1/regulations?min_ba=700&page_size=10")
        assert response.status_code == 200, "min_ba=700应该正常工作（不再有le=100限制）"
        data = response.json()

        # 验证所有返回的BA都>=700
        for item in data["items"]:
            ba = float(item["binding_affinity"])
            assert ba >= 700, f"BA应>=700，实际为{ba}"

    def test_regulations_detail(self):
        """测试调控关系详情"""
        response = requests.get(f"{BASE_URL}/api/v1/regulations/804941")
        assert response.status_code == 200
        data = response.json()

        assert data["regulation_id"] == 804941
        assert "species_id" in data
        assert "species_name" in data
        assert "target_gene_name" in data


class TestDiseasesAPI:
    """疾病API测试"""

    def test_diseases_list(self):
        """测试疾病列表 - 返回Trait-Ontology组合"""
        response = requests.get(f"{BASE_URL}/api/v1/diseases?page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()

        # 当前返回Trait-Ontology组合，不是唯一疾病数
        assert data["total"] == 1857, "应返回1857个Trait-Ontology组合"

        # 验证字段
        item = data["items"][0]
        assert "trait_id" in item
        assert "trait_name" in item
        assert "trait_doid" in item
        assert "ontology_id" in item, "应包含ontology_id"
        assert "ontology_name" in item, "应包含ontology_name"
        assert "species_name" in item, "应包含species_name"
        assert "gene_count" in item
        assert "lncrna_count" in item

    def test_diseases_detail(self):
        """测试疾病详情"""
        response = requests.get(f"{BASE_URL}/api/v1/diseases/1")
        assert response.status_code == 200
        data = response.json()

        assert data["trait_id"] == 1
        assert "description" in data
        assert "trait_doid" in data


class TestStatsAPI:
    """统计API测试"""

    def test_stats_overview(self):
        """测试统计概览 - 验证species_name别名"""
        response = requests.get(f"{BASE_URL}/api/v1/stats/overview")
        assert response.status_code == 200
        data = response.json()

        # 验证统计数据
        assert data["total_genes"] == 17248
        assert data["total_regulations"] == 804630
        assert data["total_traits"] == 273

        # 验证物种统计
        assert len(data["species_stats"]) == 4
        species = data["species_stats"][0]
        assert "species_name" in species, "species_name字段应存在"
        assert species["species_name"] == "人类"

    def test_stats_top_genes(self):
        """测试Top基因"""
        response = requests.get(f"{BASE_URL}/api/v1/stats/top-genes?limit=5")
        assert response.status_code == 200
        data = response.json()

        assert len(data) == 5
        assert "species_name" in data[0]


class TestEdgeCases:
    """边界情况测试"""

    def test_genes_empty_page(self):
        """测试超出范围的页码"""
        response = requests.get(f"{BASE_URL}/api/v1/genes?page=99999&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0

    def test_regulations_zero_ba(self):
        """测试BA=0的边界"""
        response = requests.get(f"{BASE_URL}/api/v1/regulations?min_ba=0&page_size=1")
        assert response.status_code == 200

    def test_regulations_very_high_ba(self):
        """测试非常高的BA阈值"""
        response = requests.get(f"{BASE_URL}/api/v1/regulations?min_ba=1000&page_size=10")
        assert response.status_code == 200
        # 可能返回空结果，但不应报错


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
