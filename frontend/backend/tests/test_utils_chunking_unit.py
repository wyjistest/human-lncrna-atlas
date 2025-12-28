import pytest


pytestmark = pytest.mark.unit


def test_unique_preserve_order_deduplicates_ints():
    from app.core.utils import _unique_preserve_order

    assert _unique_preserve_order([1, 2, 1, 3, 2, 4, 4]) == [1, 2, 3, 4]


def test_iter_chunks_splits_list_and_keeps_order():
    from app.core.utils import _iter_chunks

    assert list(_iter_chunks([1, 2, 3, 4, 5], chunk_size=2)) == [[1, 2], [3, 4], [5]]


def test_iter_chunks_rejects_non_positive_chunk_size():
    from app.core.utils import _iter_chunks

    with pytest.raises(ValueError):
        list(_iter_chunks([1, 2, 3], chunk_size=0))

