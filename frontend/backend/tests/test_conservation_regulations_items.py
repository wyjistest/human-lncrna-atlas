import pytest
from types import SimpleNamespace

# Mark all tests in this module as unit tests (uses monkeypatch, no external deps)
pytestmark = pytest.mark.unit


def test_build_conserved_regulation_items_does_not_call_compute_conservation_map(monkeypatch):
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
            species_ba_pairs="人类:10,黑猩猩:20,猕猴:50",
        ),
    ]

    monkeypatch.setattr(
        conservation,
        "compute_conservation_map",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("compute_conservation_map should not be called")),
    )

    items = conservation._build_conserved_regulation_items(results, db=None)

    assert len(items) == 2
    assert items[0].core_id == 101
    assert items[0].conservation_label == "1100"
    assert items[1].conservation_label == "1110"


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
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("compute_conservation_map should not be called")),
    )

    items = conservation._build_conserved_regulation_items(results, db=None)
    item = items[0]

    assert item.species_ids == [1, 2]
    assert item.conservation_label == "1100"
    assert item.avg_binding_affinity == 140.0
    assert [(x.species_id, x.binding_affinity) for x in item.species_binding_affinities] == [
        (1, 110.0),
        (2, 200.0),
    ]
