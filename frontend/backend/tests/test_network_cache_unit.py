from __future__ import annotations

from app.routers import network as network_router


def _unwrap(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__  # type: ignore[attr-defined]
    return func


class _DummyDB:
    def query(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("DB should not be queried on cache hit")


def test_network_disease_cache_hit(monkeypatch):
    calls: dict[str, object] = {}
    cached_value = {"nodes": [], "edges": [], "stats": {"total_nodes": 0}}

    def make_key(namespace: str, **kwargs):
        calls["namespace"] = namespace
        calls["kwargs"] = kwargs
        return "dummy-key"

    def get(key: str):
        calls["get_key"] = key
        return cached_value

    monkeypatch.setattr(network_router.cache, "make_key", make_key)
    monkeypatch.setattr(network_router.cache, "get", get)

    func = _unwrap(network_router.get_disease_network)
    result = func(
        request=None,
        trait_id=1,
        ontology_id=2,
        species_id=None,
        min_ba=50,
        max_nodes=500,
        max_edges=2000,
        db=_DummyDB(),
    )

    assert result == cached_value
    assert calls["namespace"] == "network:disease"
    assert calls["get_key"] == "dummy-key"
    assert calls["kwargs"] == {
        "trait_id": 1,
        "ontology_id": 2,
        "species_id": None,
        "min_ba": 50,
        "max_nodes": 500,
        "max_edges": 2000,
    }


def test_network_gene_cache_hit(monkeypatch):
    calls: dict[str, object] = {}
    cached_value = {"nodes": [], "edges": [], "stats": {"total_nodes": 0}}

    def make_key(namespace: str, **kwargs):
        calls["namespace"] = namespace
        calls["kwargs"] = kwargs
        return "dummy-key"

    def get(key: str):
        calls["get_key"] = key
        return cached_value

    monkeypatch.setattr(network_router.cache, "make_key", make_key)
    monkeypatch.setattr(network_router.cache, "get", get)

    func = _unwrap(network_router.get_gene_network)
    result = func(
        request=None,
        gene_id=123,
        species_id=1,
        min_ba=0,
        max_distance=None,
        depth=1,
        max_edges=500,
        db=_DummyDB(),
    )

    assert result == cached_value
    assert calls["namespace"] == "network:gene"
    assert calls["get_key"] == "dummy-key"
    assert calls["kwargs"] == {
        "gene_id": 123,
        "species_id": 1,
        "min_ba": 0,
        "max_distance": None,
        "depth": 1,
        "max_edges": 500,
    }


def test_network_compare_cache_hit(monkeypatch):
    calls: dict[str, object] = {}
    cached_value = {
        "lncrna_core_id": 11,
        "species_names": {"1": "Human"},
        "species_networks": {},
        "conserved_target_count": 0,
        "conserved_targets": [],
    }

    def make_key(namespace: str, **kwargs):
        calls["namespace"] = namespace
        calls["kwargs"] = kwargs
        return "dummy-key"

    def get(key: str):
        calls["get_key"] = key
        return cached_value

    monkeypatch.setattr(network_router.cache, "make_key", make_key)
    monkeypatch.setattr(network_router.cache, "get", get)

    func = _unwrap(network_router.compare_species_networks)
    result = func(
        request=None,
        lncrna_gene_id=17276,
        min_ba=50,
        max_targets_per_species=100,
        db=_DummyDB(),
    )

    assert result == cached_value
    assert calls["namespace"] == "network:compare"
    assert calls["get_key"] == "dummy-key"
    assert calls["kwargs"] == {
        "lncrna_gene_id": 17276,
        "min_ba": 50,
        "max_targets_per_species": 100,
    }
