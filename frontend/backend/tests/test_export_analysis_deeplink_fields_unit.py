from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.routers import export as export_module
from app.routers.export import router as export_router


pytestmark = pytest.mark.unit


class _MappingRow:
    def __init__(self, mapping: dict):
        self._mapping = mapping


class _DummySession:
    def __init__(self, responses: list[object]):
        self._responses = list(responses)
        self.calls: list[tuple[object, object]] = []

    def execute(self, statement, params=None):
        self.calls.append((statement, params))
        assert self._responses, "unexpected execute() call"
        return self._responses.pop(0)


def _build_client(db: _DummySession) -> TestClient:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(export_router, prefix="/api/v1")

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_chipseq_overlaps_json_exposes_gene_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(export_module, "_apply_json_memory_limit", lambda _request, limit, _fmt: limit)

    db = _DummySession([
        [
            _MappingRow(
                {
                    "regulation_id": 10,
                    "lncrna_gene_id": 201,
                    "lncrna_name": "MALAT1",
                    "target_gene_id": 101,
                    "target_name": "TP53",
                    "binding_affinity": 150.5,
                    "mark_name": "H3K27me3",
                    "peak_score": 9.1,
                    "peak_chr": "chr1",
                    "peak_start": 100,
                    "peak_end": 120,
                    "cell_type": "K562",
                }
            )
        ]
    ])
    client = _build_client(db)

    response = client.get(
        "/api/v1/export/chipseq-overlaps",
        params={"format": "json", "mark_names": "H3K27me3"},
    )

    assert response.status_code == 200
    payload = response.json()
    item = payload["data"][0]
    assert item["lncrna_gene_id"] == 201
    assert item["target_gene_id"] == 101

    statement_text = str(db.calls[0][0])
    assert "lncrna_gene_id" in statement_text
    assert "target_gene_id" in statement_text


def test_disease_network_json_exposes_deeplink_metadata() -> None:
    db = _DummySession([
        [
            SimpleNamespace(
                trait_name="Cancer",
                trait_id=7,
                ontology_id=11,
                evidence_species_id=1,
                gene_id=101,
                gene_name="TP53",
                pvalue=1e-8,
            )
        ],
        [
            SimpleNamespace(
                target_gene_id=101,
                lncrna_gene_id=201,
                lncrna_name="MALAT1",
                binding_affinity=150.5,
            )
        ],
    ])
    client = _build_client(db)

    response = client.get(
        "/api/v1/export/disease-network",
        params={"format": "json", "trait_name": "cancer", "limit": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    disease_node = next(node for node in payload["nodes"] if node["type"] == "disease")
    gene_node = next(node for node in payload["nodes"] if node["type"] == "gene")
    lncrna_node = next(node for node in payload["nodes"] if node["type"] == "lncrna")

    assert disease_node["trait_id"] == 7
    assert disease_node["ontology_id"] == 11
    assert disease_node["species_id"] == 1
    assert gene_node["gene_id"] == 101
    assert lncrna_node["gene_id"] == 201
