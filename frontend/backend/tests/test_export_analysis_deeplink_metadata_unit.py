"""
单元测试: analysis deep-link 所需的 export metadata
"""

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.routers import export as export_router


pytestmark = pytest.mark.unit


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


class _FakeDB:
    def __init__(self, *responses):
        self._responses = list(responses)

    def execute(self, *_args, **_kwargs):
        assert self._responses, "unexpected db.execute call"
        return _FakeResult(self._responses.pop(0))


def _make_request(path: str, query_string: str = "") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": query_string.encode("utf-8"),
            "headers": [],
        }
    )


def test_export_chipseq_overlaps_includes_gene_ids_in_json():
    request = _make_request("/api/v1/export/chipseq-overlaps", "format=json")
    db = _FakeDB(
        [
            SimpleNamespace(
                _mapping={
                    "regulation_id": 1,
                    "lncrna_gene_id": 11,
                    "lncrna_name": "MALAT1",
                    "target_gene_id": 22,
                    "target_name": "TP53",
                    "binding_affinity": 120.0,
                    "mark_name": "H3K27me3",
                    "peak_score": 7.5,
                    "peak_chr": "chr1",
                    "peak_start": 100,
                    "peak_end": 200,
                    "cell_type": "K562",
                }
            )
        ]
    )

    response = export_router.export_chipseq_overlaps(
        request=request,
        mark_names=["H3K27me3"],
        min_ba=100.0,
        limit=10,
        output_format="json",
        db=db,
    )

    assert response.data[0].lncrna_gene_id == 11
    assert response.data[0].target_gene_id == 22


def test_export_disease_network_includes_node_navigation_metadata():
    request = _make_request("/api/v1/export/disease-network", "trait_name=diabetes&format=json")
    db = _FakeDB(
        [
            SimpleNamespace(
                trait_name="Type 2 Diabetes",
                trait_id=5,
                ontology_id=9,
                evidence_species_id=1,
                gene_id=101,
                gene_name="TP53",
                pvalue=1e-8,
            )
        ],
        [
            SimpleNamespace(
                target_gene_id=101,
                target_name="TP53",
                target_species_id=1,
                lncrna_gene_id=202,
                lncrna_name="MALAT1",
                lncrna_species_id=1,
                binding_affinity=150.0,
            )
        ],
    )

    response = export_router.export_disease_network(
        request=request,
        trait_name="diabetes",
        limit=10,
        output_format="json",
        db=db,
    )

    disease_node = next(node for node in response.nodes if node.type == "disease")
    gene_node = next(node for node in response.nodes if node.type == "gene")
    lncrna_node = next(node for node in response.nodes if node.type == "lncrna")

    assert disease_node.trait_id == 5
    assert disease_node.ontology_id == 9
    assert disease_node.species_id == 1
    assert gene_node.gene_id == 101
    assert gene_node.species_id == 1
    assert lncrna_node.gene_id == 202
    assert lncrna_node.species_id == 1
