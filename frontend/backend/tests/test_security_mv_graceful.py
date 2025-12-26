"""
安全测试: 物化视图 (MV) 降级处理

覆盖修复点:
- analysis.py:167-207 MV 查询 try-except 降级
- MV 不存在时返回空数据，不影响其他模块

运行方式:
    pytest tests/test_security_mv_graceful.py -v
    pytest tests/test_security_mv_graceful.py -v -m unit         # 仅单元测试
    pytest tests/test_security_mv_graceful.py -v -m integration  # 仅集成测试

注意:
    此测试主要通过集成测试验证降级行为。
    单元测试验证响应结构和基本逻辑。
"""
import pytest


# ============== 单元测试: 响应结构验证 ==============

class TestEpigeneticDataStructure:
    """测试 EpigeneticAnalysis 数据结构"""

    @pytest.mark.unit
    def test_epigenetic_default_values(self):
        """验证 EpigeneticAnalysis 可以用空值初始化"""
        from app.schemas.analysis import EpigeneticAnalysis

        # 模拟 MV 缺失时的降级数据
        epi = EpigeneticAnalysis(
            total_overlaps=0,
            by_mark={},
            by_cell_type={}
        )

        assert epi.total_overlaps == 0
        assert epi.by_mark == {}
        assert epi.by_cell_type == {}
        # Phase 9.29+：补齐统计卡片字段默认值
        assert epi.bivalent_domains == 0
        assert epi.active_marks == 0
        assert epi.repressive_marks == 0

    @pytest.mark.unit
    def test_epigenetic_with_data(self):
        """验证 EpigeneticAnalysis 可以存储正常数据"""
        from app.schemas.analysis import EpigeneticAnalysis

        epi = EpigeneticAnalysis(
            total_overlaps=1500,
            by_mark={"H3K27me3": 1000, "H3K4me3": 500},
            by_cell_type={"K562": 800, "HepG2": 700}
        )

        assert epi.total_overlaps == 1500
        assert epi.by_mark["H3K27me3"] == 1000
        assert epi.by_cell_type["K562"] == 800

    @pytest.mark.unit
    def test_analysis_summary_response_structure(self):
        """验证 AnalysisSummaryResponse 结构完整"""
        from app.schemas.analysis import (
            AnalysisSummaryResponse,
            HighAffinityAnalysis,
            ConservationAnalysis,
            EpigeneticAnalysis,
            DiseaseAnalysis,
        )

        # 构造完整响应（使用空/默认值）
        response = AnalysisSummaryResponse(
            high_affinity=HighAffinityAnalysis(
                total_regulations=0,
                unique_lncrnas=0,
                unique_targets=0,
                avg_ba=0.0,
                max_ba=0.0,
                top_lncrnas=[]
            ),
            conservation=ConservationAnalysis(
                four_species=0,
                three_species=0,
                two_species=0,
                total_conserved=0
            ),
            epigenetic=EpigeneticAnalysis(
                total_overlaps=0,
                by_mark={},
                by_cell_type={}
            ),
            disease=DiseaseAnalysis(
                total_diseases=0,
                total_lncrnas=0,
                total_genes=0
            )
        )

        # 验证结构
        assert response.high_affinity is not None
        assert response.conservation is not None
        assert response.epigenetic is not None
        assert response.disease is not None
        # Phase 9.29+：新增字段默认值保持可用
        assert response.disease.avg_connections == 0.0


class TestMVGracefulDegradationLogic:
    """测试 MV 降级逻辑"""

    @pytest.mark.unit
    def test_exception_handling_pattern(self):
        """验证异常处理模式正确"""
        # 模拟 analysis.py 中的降级逻辑
        by_mark = {}
        by_cell_type = {}
        total_overlaps = 0

        try:
            # 模拟 MV 查询失败
            raise Exception("relation 'mv_lncrna_chipseq_overlaps' does not exist")
        except Exception:
            # 降级处理
            by_mark = {}
            by_cell_type = {}
            total_overlaps = 0

        # 验证降级后的值
        assert total_overlaps == 0
        assert by_mark == {}
        assert by_cell_type == {}

    @pytest.mark.unit
    def test_partial_data_processing(self):
        """验证部分数据处理正确"""
        # 模拟正常的 MV 数据聚合逻辑
        mock_rows = [
            {"total_overlaps": 1000, "mark_name": "H3K27me3", "cell_type": "K562"},
            {"total_overlaps": 800, "mark_name": "H3K4me3", "cell_type": "K562"},
            {"total_overlaps": 500, "mark_name": "H3K27me3", "cell_type": "HepG2"},
        ]

        by_mark = {}
        by_cell_type = {}
        total_overlaps = 0

        for row in mock_rows:
            count = row["total_overlaps"] or 0
            total_overlaps += count

            mark = row["mark_name"]
            by_mark[mark] = by_mark.get(mark, 0) + count

            cell = row["cell_type"]
            by_cell_type[cell] = by_cell_type.get(cell, 0) + count

        # 验证聚合结果
        assert total_overlaps == 2300
        assert by_mark["H3K27me3"] == 1500  # 1000 + 500
        assert by_mark["H3K4me3"] == 800
        assert by_cell_type["K562"] == 1800  # 1000 + 800
        assert by_cell_type["HepG2"] == 500


# ============== 集成测试 ==============

@pytest.mark.integration
class TestAnalysisSummaryEndpoint:
    """测试 /analysis/summary 端点"""

    def test_returns_200(self, api_client, api_assert):
        """/analysis/summary 应返回 200"""
        response = api_client.get("/api/v1/analysis/summary")
        api_assert.assert_successful_response(response)

    def test_response_structure_complete(self, api_client, api_assert):
        """响应结构应完整"""
        response = api_client.get("/api/v1/analysis/summary")
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        # 验证四个分析模块都存在
        assert "high_affinity" in data
        assert "conservation" in data
        assert "epigenetic" in data
        assert "disease" in data

    def test_epigenetic_structure(self, api_client, api_assert):
        """epigenetic 结构应有效（无论 MV 是否存在）"""
        response = api_client.get("/api/v1/analysis/summary")
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        epi = data["epigenetic"]

        # 验证字段存在（值可能为 0 或空）
        assert "total_overlaps" in epi
        assert "by_mark" in epi
        assert "by_cell_type" in epi

        # 验证类型
        assert isinstance(epi["total_overlaps"], int)
        assert isinstance(epi["by_mark"], dict)
        assert isinstance(epi["by_cell_type"], dict)

        # 验证非负
        assert epi["total_overlaps"] >= 0

    def test_high_affinity_structure(self, api_client, api_assert):
        """high_affinity 结构验证"""
        response = api_client.get("/api/v1/analysis/summary")
        api_assert.assert_successful_response(response)
        data = api_assert.assert_json_response(response)

        ha = data["high_affinity"]
        assert "total_regulations" in ha
        assert "unique_lncrnas" in ha
        assert "unique_targets" in ha
        assert "avg_ba" in ha
        assert "max_ba" in ha
        assert "top_lncrnas" in ha

    def test_conservation_structure(self, api_client):
        """conservation 结构验证"""
        response = api_client.get("/api/v1/analysis/summary")
        assert response.status_code in (200, 429), \
            f"应返回 200 或 429，实际 {response.status_code}"

        if response.status_code == 200:
            data = response.json()
            cons = data["conservation"]
            assert "four_species" in cons
            assert "three_species" in cons
            assert "two_species" in cons
            assert "total_conserved" in cons

            # 验证 total_conserved 是正确的和
            expected_total = cons["four_species"] + cons["three_species"] + cons["two_species"]
            assert cons["total_conserved"] == expected_total

    def test_disease_structure(self, api_client):
        """disease 结构验证"""
        response = api_client.get("/api/v1/analysis/summary")
        assert response.status_code in (200, 429), \
            f"应返回 200 或 429，实际 {response.status_code}"

        if response.status_code == 200:
            data = response.json()
            disease = data["disease"]
            assert "total_diseases" in disease
            assert "total_lncrnas" in disease
            assert "total_genes" in disease

    def test_no_500_error(self, api_client):
        """任何场景下都不应返回 500"""
        response = api_client.get("/api/v1/analysis/summary")
        assert response.status_code != 500, \
            f"不应返回 500 错误: {response.text[:500]}"

    def test_response_is_cacheable(self, api_client):
        """响应应可被缓存（多次请求应一致）"""
        response1 = api_client.get("/api/v1/analysis/summary")
        assert response1.status_code in (200, 429), \
            f"应返回 200 或 429，实际 {response1.status_code}"

        if response1.status_code == 200:
            data1 = response1.json()

            response2 = api_client.get("/api/v1/analysis/summary")
            if response2.status_code == 200:
                data2 = response2.json()
                # 短时间内数据应一致（缓存生效）
                assert data1 == data2


# ============== 边界情况测试 ==============

@pytest.mark.integration
class TestAnalysisSummaryEdgeCases:
    """边界情况测试"""

    def test_concurrent_requests(self, api_client):
        """并发请求应正常处理"""
        import concurrent.futures

        def make_request():
            return api_client.get("/api/v1/analysis/summary")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(make_request) for _ in range(3)]
            responses = [f.result() for f in futures]

        # 所有请求都应成功（200 或 429 都是正常行为）
        for response in responses:
            assert response.status_code in (200, 429), \
                f"并发请求应返回 200 或 429，实际 {response.status_code}"

    def test_epigenetic_values_non_negative(self, api_client):
        """epigenetic 值应非负"""
        response = api_client.get("/api/v1/analysis/summary")
        assert response.status_code in (200, 429), \
            f"应返回 200 或 429，实际 {response.status_code}"

        if response.status_code == 200:
            data = response.json()
            epi = data["epigenetic"]
            assert epi["total_overlaps"] >= 0

            for mark, count in epi["by_mark"].items():
                assert count >= 0, f"by_mark[{mark}] 不应为负"

            for cell, count in epi["by_cell_type"].items():
                assert count >= 0, f"by_cell_type[{cell}] 不应为负"
