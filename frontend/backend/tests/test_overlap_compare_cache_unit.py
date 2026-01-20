from __future__ import annotations

import pytest

from app.routers import lncrna_chipseq_overlap as overlap_router


def _unwrap(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__  # type: ignore[attr-defined]
    return func


class _DummyDB:
    def query(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("DB should not be queried on cache hit")


@pytest.mark.unit
def test_overlap_compare_cache_hit(monkeypatch):
    calls: dict[str, object] = {}
    cached_value = {
        "lncrna_core_id": 11,
        "target_core_id": None,
        "species_names": {"1": "Human"},
        "species_stats": {},
    }

    def make_key(namespace: str, **kwargs):
        calls["namespace"] = namespace
        calls["kwargs"] = kwargs
        return "dummy-key"

    def get(key: str):
        calls["get_key"] = key
        return cached_value

    monkeypatch.setattr(overlap_router.cache, "make_key", make_key)
    monkeypatch.setattr(overlap_router.cache, "get", get)

    func = _unwrap(overlap_router.compare_species_overlaps)
    result = func(
        request=None,
        lncrna_gene_id=17276,
        target_gene_id=None,
        mark_type=None,
        cell_type=None,
        chromosome=None,
        min_binding_affinity=None,
        max_qvalue=0.05,
        top_n=10,
        db=_DummyDB(),
    )

    assert result == cached_value
    assert calls["namespace"] == "overlap:compare"
    assert calls["get_key"] == "dummy-key"
    assert calls["kwargs"] == {
        "lncrna_gene_id": 17276,
        "target_gene_id": None,
        "mark_type": None,
        "cell_type": None,
        "chromosome": None,
        "min_binding_affinity": None,
        "max_qvalue": 0.05,
        "top_n": 10,
    }
