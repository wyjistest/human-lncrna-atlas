from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.routers import lncrna_chipseq_overlap as overlap_router


def _unwrap(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__  # type: ignore[attr-defined]
    return func


def _stats(total: int) -> dict:
    return {
        "total_overlaps": total,
        "unique_lncrnas": 1 if total else 0,
        "unique_target_genes": 0,
        "unique_marks": 0,
        "unique_cell_types": 0,
        "avg_overlap_length": 0.0,
        "avg_binding_affinity": 0.0,
        "avg_peak_strength": 0.0,
        "by_mark_type": [],
        "by_cell_type": [],
        "default_filter_applied": False,
        "effective_chromosome": None,
    }


@pytest.mark.unit
def test_overlap_compare_species_builds_per_species_stats_on_cache_miss(monkeypatch):
    calls: dict[str, object] = {}

    # Cache miss.
    monkeypatch.setattr(overlap_router.cache, "make_key", lambda *args, **kwargs: "dummy-key")
    monkeypatch.setattr(overlap_router.cache, "get", lambda key: None)

    def set_(key: str, value, ttl: int):  # noqa: ANN001 - test double
        calls["set"] = {"key": key, "ttl": ttl, "value": value}
        return True

    monkeypatch.setattr(overlap_router.cache, "set", set_)

    # Stub DB-dependent helpers.
    monkeypatch.setattr(
        overlap_router,
        "_get_gene_or_404",
        lambda db, gene_id, label: SimpleNamespace(gene_id=gene_id, core_id=11),
        raising=False,
    )
    monkeypatch.setattr(
        overlap_router,
        "_get_ortholog_gene_map",
        lambda db, core_id: {1: 101, 2: 201},
        raising=False,
    )

    def fake_batch_stats(**kwargs):  # noqa: ANN001 - test double
        pairs = kwargs["species_gene_pairs"]
        result = {}
        for species_id in pairs:
            if species_id == 1:
                result[species_id] = _stats(10)
            elif species_id == 2:
                result[species_id] = _stats(3)
            else:
                result[species_id] = _stats(0)
        return result

    monkeypatch.setattr(overlap_router, "_compute_overlap_statistics_batch_impl", fake_batch_stats, raising=False)

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
        species_ids=None,
        db=object(),
    )

    assert result["lncrna_core_id"] == 11
    assert result["target_core_id"] is None

    # Always return entries for all 4 species (missing orthologs become empty stats).
    stats = result["species_stats"]
    assert set(stats.keys()) == {1, 2, 3, 4}
    assert stats[1]["lncrna_gene_id"] == 101
    assert stats[2]["lncrna_gene_id"] == 201
    assert stats[3]["lncrna_gene_id"] is None
    assert stats[4]["lncrna_gene_id"] is None

    assert stats[1]["statistics"]["total_overlaps"] == 10
    assert stats[2]["statistics"]["total_overlaps"] == 3
    assert stats[3]["statistics"]["total_overlaps"] == 0

    # Writes to cache on miss.
    assert calls["set"]["key"] == "dummy-key"
    assert calls["set"]["ttl"] == overlap_router.cache.TTL_LIST


@pytest.mark.unit
def test_overlap_compare_species_ids_filters_output(monkeypatch):
    calls: dict[str, object] = {}

    def make_key(namespace: str, **kwargs):
        calls["make_key"] = {"namespace": namespace, "kwargs": kwargs}
        return "dummy-key"

    monkeypatch.setattr(overlap_router.cache, "make_key", make_key)
    monkeypatch.setattr(overlap_router.cache, "get", lambda key: None)
    monkeypatch.setattr(overlap_router.cache, "set", lambda *args, **kwargs: True)

    monkeypatch.setattr(
        overlap_router,
        "_get_gene_or_404",
        lambda db, gene_id, label: SimpleNamespace(gene_id=gene_id, core_id=11),
        raising=False,
    )
    monkeypatch.setattr(
        overlap_router,
        "_get_ortholog_gene_map",
        lambda db, core_id: {1: 101, 3: 301},
        raising=False,
    )
    monkeypatch.setattr(
        overlap_router,
        "_compute_overlap_statistics_batch_impl",
        lambda **kwargs: {species_id: _stats(1) for species_id in kwargs["species_gene_pairs"]},
        raising=False,
    )

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
        species_ids="1,3",
        db=object(),
    )

    assert result["lncrna_core_id"] == 11
    assert set(result["species_stats"].keys()) == {1, 3}
    assert calls["make_key"]["namespace"] == "overlap:compare"
    assert calls["make_key"]["kwargs"]["species_ids"] == "1,3"


@pytest.mark.unit
def test_overlap_compare_species_uses_batch_stats_builder(monkeypatch):
    calls: dict[str, object] = {}
    db_token = object()

    monkeypatch.setattr(overlap_router.cache, "make_key", lambda *args, **kwargs: "dummy-key")
    monkeypatch.setattr(overlap_router.cache, "get", lambda key: None)
    monkeypatch.setattr(overlap_router.cache, "set", lambda *args, **kwargs: True)

    def fake_get_gene(db, gene_id, label):  # noqa: ANN001 - test double
        core_id = 11 if label == "LncRNA" else 22
        return SimpleNamespace(gene_id=gene_id, core_id=core_id)

    monkeypatch.setattr(overlap_router, "_get_gene_or_404", fake_get_gene, raising=False)

    def fake_ortholog_map(db, core_id):  # noqa: ANN001 - test double
        if core_id == 11:
            return {1: 101, 3: 301}
        if core_id == 22:
            return {1: 501, 3: 701}
        raise AssertionError(f"unexpected core_id: {core_id}")

    monkeypatch.setattr(overlap_router, "_get_ortholog_gene_map", fake_ortholog_map, raising=False)

    def fail_if_called(**kwargs):  # noqa: ANN001 - test double
        raise AssertionError("compare route should use batch statistics helper")

    monkeypatch.setattr(
        overlap_router,
        "_compute_overlap_statistics_impl",
        fail_if_called,
        raising=False,
    )

    def fake_batch_stats(**kwargs):  # noqa: ANN001 - test double
        calls.update(kwargs)
        return {
            1: _stats(10),
            3: _stats(4),
        }

    monkeypatch.setattr(
        overlap_router,
        "_compute_overlap_statistics_batch_impl",
        fake_batch_stats,
        raising=False,
    )

    func = _unwrap(overlap_router.compare_species_overlaps)
    result = func(
        request=None,
        lncrna_gene_id=17276,
        target_gene_id=24680,
        mark_type="H3K27me3",
        cell_type="K562",
        chromosome="chr1",
        min_binding_affinity=50.0,
        max_qvalue=0.01,
        top_n=5,
        species_ids="1,3",
        db=db_token,
    )

    assert calls["db"] is db_token
    assert calls["species_gene_pairs"] == {
        1: {"lncrna_gene_id": 101, "target_gene_id": 501},
        3: {"lncrna_gene_id": 301, "target_gene_id": 701},
    }
    assert calls["mark_type"] == "H3K27me3"
    assert calls["cell_type"] == "K562"
    assert calls["chromosome"] == "chr1"
    assert calls["min_binding_affinity"] == 50.0
    assert calls["max_qvalue"] == 0.01
    assert calls["top_n"] == 5
    assert result["species_stats"][1]["statistics"]["total_overlaps"] == 10
    assert result["species_stats"][3]["statistics"]["total_overlaps"] == 4

class _MissingSchemaSession:
    def execute(self, stmt, params=None):  # noqa: ANN001
        raise Exception("no such table: chipseq_peaks_human")


@pytest.mark.unit
def test_compute_overlap_statistics_impl_returns_empty_stats_when_schema_missing(monkeypatch):
    monkeypatch.setattr(overlap_router, "check_materialized_view_exists", lambda db: False, raising=False)

    result = overlap_router._compute_overlap_statistics_impl(
        db=_MissingSchemaSession(),
        species_id=1,
        lncrna_gene_id=17276,
        target_gene_id=None,
        mark_type=None,
        cell_type=None,
        chromosome=None,
        min_binding_affinity=None,
        max_qvalue=0.05,
        top_n=10,
    )

    assert isinstance(result, dict)
    assert result["total_overlaps"] == 0
    assert result["by_mark_type"] == []
    assert result["by_cell_type"] == []
