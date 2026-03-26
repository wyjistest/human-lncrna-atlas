from types import SimpleNamespace

import pytest

from app.routers import export as export_router


def _unwrap(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__  # type: ignore[attr-defined]
    return func


class _DummyDB:
    def __init__(self):
        self.calls: list[tuple[str, dict | None]] = []

    def execute(self, stmt, params=None):  # noqa: ANN001
        sql_text = str(stmt)
        self.calls.append((sql_text, params))

        if "trait_gene_associations" in sql_text.lower():
            return [
                SimpleNamespace(trait_id=1, trait_name="Trait A", gene_id=101, gene_name="GENE1", pvalue=1e-8),
                SimpleNamespace(trait_id=1, trait_name="Trait A", gene_id=102, gene_name="GENE2", pvalue=2e-8),
            ]

        if "from regulations r" in sql_text.lower():
            assert params is not None
            assert params["limit"] == 1
            return [
                SimpleNamespace(
                    target_gene_id=101,
                    target_name="GENE1",
                    lncrna_gene_id=201,
                    lncrna_name="LNC1",
                    binding_affinity=150.0,
                )
            ]

        raise AssertionError(f"Unexpected SQL executed in unit test:\n{sql_text}")


@pytest.mark.unit
def test_export_disease_network_limit_caps_total_edges():
    response = _unwrap(export_router.export_disease_network)(
        request=SimpleNamespace(query_params={}),
        trait_name="trait",
        limit=3,
        output_format="json",
        db=_DummyDB(),
    )

    assert len(response.edges) == 3
    assert [edge.type for edge in response.edges] == ["disease-gene", "disease-gene", "regulation"]
    disease_node = next(node for node in response.nodes if node.type == "disease")
    assert disease_node.ontology_id is None
    assert disease_node.species_id is None
