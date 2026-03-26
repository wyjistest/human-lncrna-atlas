from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.routers import regulations as regulations_router


def _unwrap(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__  # type: ignore[attr-defined]
    return func


class _FakeDataQuery:
    def __init__(self, items):
        self._items = items
        self.offset_calls: list[int] = []
        self.limit_calls: list[int] = []

    def offset(self, value: int):
        self.offset_calls.append(value)
        return self

    def limit(self, value: int):
        self.limit_calls.append(value)
        return self

    def all(self):
        return list(self._items)


@pytest.mark.unit
def test_list_regulations_uses_shared_filtered_query_builder(monkeypatch):
    calls: dict[str, object] = {}
    db_token = object()
    item = SimpleNamespace(
        regulation_id=99,
        species_id=1,
        species_name="Human",
        lncrna_gene_id=10,
        lncrna_gene_name="LNC1",
        target_gene_id=20,
        target_gene_name="GENE1",
        target_chromosome="chr1",
        target_start=100,
        target_end=200,
        binding_affinity=88.0,
        best_avg_ba=77.0,
        num_peaks=3,
    )
    data_query = _FakeDataQuery([item])
    count_query = object()

    monkeypatch.setattr(regulations_router.cache, "make_list_key", lambda *args, **kwargs: "cache-key")
    monkeypatch.setattr(regulations_router.cache, "get", lambda key: None)
    monkeypatch.setattr(regulations_router.cache, "set", lambda *args, **kwargs: True)

    def fake_get_cached_count(query, cache_key):  # noqa: ANN001 - test double
        calls["count_query"] = query
        calls["count_cache_key"] = cache_key
        return 1

    monkeypatch.setattr(regulations_router.cache, "get_cached_count", fake_get_cached_count)

    def fail_old_builder(db):  # noqa: ANN001 - test double
        raise AssertionError("list route should use shared filtered query builder")

    monkeypatch.setattr(regulations_router, "_build_regulation_list_query", fail_old_builder, raising=False)

    def fake_filtered_queries(db, **kwargs):  # noqa: ANN001 - test double
        calls["builder_db"] = db
        calls["builder_kwargs"] = kwargs
        return data_query, count_query

    monkeypatch.setattr(
        regulations_router,
        "_build_filtered_regulation_list_queries",
        fake_filtered_queries,
        raising=False,
    )

    func = _unwrap(regulations_router.list_regulations)
    response = func(
        request=None,
        page=2,
        page_size=25,
        species_id=1,
        species_ids=" 2,1 ",
        lncrna_gene_id=10,
        target_gene_id=20,
        lncrna_gene_name=" LNC1 ",
        target_gene_name=" GENE1 ",
        min_ba=1.5,
        max_ba=9.5,
        chromosome=" Chr1 ",
        chromosomes=" chr2 , chr1 ",
        db=db_token,
    )

    assert calls["builder_db"] is db_token
    assert calls["builder_kwargs"] == {
        "species_id": 1,
        "normalized_species_ids": "1,2",
        "lncrna_gene_id": 10,
        "target_gene_id": 20,
        "normalized_lncrna_gene_name": "LNC1",
        "normalized_target_gene_name": "GENE1",
        "min_ba": 1.5,
        "max_ba": 9.5,
        "normalized_chromosome": "chr1",
        "normalized_chromosomes": "chr1,chr2",
    }
    assert calls["count_query"] is count_query
    assert calls["count_cache_key"] == "cache-key"
    assert data_query.offset_calls == [25]
    assert data_query.limit_calls == [25]

    assert response.total == 1
    assert response.page == 2
    assert response.page_size == 25
    assert response.total_pages == 1
    assert len(response.items) == 1
    assert response.items[0].regulation_id == 99
    assert response.items[0].target_gene_name == "GENE1"
