"""
性能测试 - 测试大数据量查询响应时间
运行: pytest tests/test_performance.py -v -s
"""
import pytest
import requests
import time

# Mark all tests in this module as integration + performance + slow tests
# Phase 9.20: Added 'slow' marker for test layer optimization
pytestmark = [pytest.mark.integration, pytest.mark.performance, pytest.mark.slow]

BASE_URL = "http://localhost:8000"


class TestPerformance:
    """性能测试"""

    def test_genes_large_page(self):
        """测试大分页查询性能"""
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/v1/genes?page=1&page_size=1000")
        elapsed = time.time() - start

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1000

        print(f"\n✅ 基因列表(1000条): {elapsed:.2f}秒")
        assert elapsed < 5.0, f"查询时间过长: {elapsed:.2f}秒"

    def test_regulations_large_page(self):
        """测试调控关系大分页性能"""
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/v1/regulations?page=1&page_size=1000")
        elapsed = time.time() - start

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1000

        print(f"\n✅ 调控关系列表(1000条): {elapsed:.2f}秒")
        assert elapsed < 10.0, f"查询时间过长: {elapsed:.2f}秒"

    def test_regulations_with_filter(self):
        """测试带过滤的查询性能"""
        start = time.time()
        response = requests.get(
            f"{BASE_URL}/api/v1/regulations?species_id=1&min_ba=50&page_size=100"
        )
        elapsed = time.time() - start

        assert response.status_code == 200
        print(f"\n✅ 调控关系过滤查询(100条): {elapsed:.2f}秒")
        assert elapsed < 5.0, f"查询时间过长: {elapsed:.2f}秒"

    def test_stats_overview(self):
        """测试统计概览性能"""
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/v1/stats/overview")
        elapsed = time.time() - start

        assert response.status_code == 200
        print(f"\n✅ 统计概览: {elapsed:.2f}秒")
        assert elapsed < 3.0, f"查询时间过长: {elapsed:.2f}秒"

    def test_gene_detail_with_orthologs(self):
        """测试基因详情（含同源基因）性能"""
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/v1/genes/17276")
        elapsed = time.time() - start

        assert response.status_code == 200
        print(f"\n✅ 基因详情: {elapsed:.2f}秒")
        assert elapsed < 2.0, f"查询时间过长: {elapsed:.2f}秒"

    def test_concurrent_requests(self):
        """测试并发请求"""
        import concurrent.futures

        def make_request():
            response = requests.get(f"{BASE_URL}/api/v1/genes?page=1&page_size=10")
            return response.status_code == 200

        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        elapsed = time.time() - start

        assert all(results), "所有请求应成功"
        print(f"\n✅ 并发50个请求: {elapsed:.2f}秒 (平均{elapsed/50*1000:.0f}ms/请求)")
        assert elapsed < 10.0, f"并发请求时间过长: {elapsed:.2f}秒"


class TestDatabaseIndexes:
    """数据库索引建议"""

    def test_check_slow_queries(self):
        """检查可能的慢查询"""
        # 测试没有索引可能导致的慢查询
        queries = [
            ("species_id过滤", f"{BASE_URL}/api/v1/regulations?species_id=1&page_size=100"),
            ("gene_id过滤", f"{BASE_URL}/api/v1/regulations?lncrna_gene_id=17276&page_size=100"),
            ("BA过滤", f"{BASE_URL}/api/v1/regulations?min_ba=50&page_size=100"),
        ]

        print("\n\n=== 慢查询检测 ===")
        for name, url in queries:
            start = time.time()
            requests.get(url)  # Execute query for timing
            elapsed = time.time() - start

            status = "⚠️ 慢" if elapsed > 2.0 else "✅ 快"
            print(f"{status} {name}: {elapsed:.3f}秒")

            if elapsed > 2.0:
                print("   建议: 为相关字段添加索引")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
