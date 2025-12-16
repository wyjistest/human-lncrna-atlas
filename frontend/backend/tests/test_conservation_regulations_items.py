import pytest
from types import SimpleNamespace

# Mark all tests in this module as unit tests (uses monkeypatch, no external deps)
pytestmark = pytest.mark.unit


def test_build_conserved_regulation_items_batches_conservation_map(monkeypatch):
    from app.routers import conservation

    results = [
        SimpleNamespace(
            lncrna_core_id=101,
            target_core_id=201,
            species_count=2,
            lncrna_symbol="LNC1",
            target_symbol="TGT1",
            species_ba_pairs="人类:100,黑猩猩:200,人类:120",
        ),
        SimpleNamespace(
            lncrna_core_id=102,
            target_core_id=202,
            species_count=3,
            lncrna_symbol="LNC2",
            target_symbol="TGT2",
            species_ba_pairs="猕猴:50",
        ),
    ]

    calls = []

    def fake_compute_conservation_map(core_ids, db):
        calls.append(set(core_ids))
        return {
            101: ("1100", 2),
            102: ("0011", 2),
            201: ("0001", 1),
            202: ("1111", 4),
        }

    monkeypatch.setattr(conservation, "compute_conservation_map", fake_compute_conservation_map)

    items = conservation._build_conserved_regulation_items(results, db=None)

    assert len(calls) == 1
    assert calls[0] == {101, 102, 201, 202}
    assert len(items) == 2
    assert items[0].core_id == 101
    assert items[0].conservation_label == "1100"


def test_build_conserved_regulation_items_parses_species_binding_affinities(monkeypatch):
    from app.routers import conservation

    results = [
        SimpleNamespace(
            lncrna_core_id=101,
            target_core_id=201,
            species_count=2,
            lncrna_symbol="LNC1",
            target_symbol="TGT1",
            species_ba_pairs="人类:100,黑猩猩:200,人类:120",
        ),
    ]

    monkeypatch.setattr(
        conservation,
        "compute_conservation_map",
        lambda core_ids, db: {101: ("1100", 2), 201: ("0001", 1)},
    )

    items = conservation._build_conserved_regulation_items(results, db=None)
    item = items[0]

    assert item.species_ids == [1, 2]
    assert item.avg_binding_affinity == 140.0
    assert [(x.species_id, x.binding_affinity) for x in item.species_binding_affinities] == [
        (1, 110.0),
        (2, 200.0),
    ]

