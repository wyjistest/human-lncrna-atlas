"""
lncRNA-ChIP-seq overlap 排序参数枚举测试

目的：确保 sort_by / sort_order 白名单类型支持大小写输入（避免"静默降级"与潜在注入面）。
"""
import pytest

from app.schemas.lncrna_chipseq_overlap import OverlapSortField, OverlapSortOrder


@pytest.mark.unit
def test_sort_order_is_case_insensitive():
    assert OverlapSortOrder("DESC") is OverlapSortOrder.desc
    assert OverlapSortOrder("Asc") is OverlapSortOrder.asc


@pytest.mark.unit
def test_sort_field_is_case_insensitive():
    assert OverlapSortField("BINDING_AFFINITY") is OverlapSortField.binding_affinity
    assert OverlapSortField("PEAK_QVALUE") is OverlapSortField.peak_qvalue

