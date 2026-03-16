import pytest

from app.schemas.gene import GeneDetail, GeneListItem

pytestmark = pytest.mark.unit


def test_gene_list_item_allows_null_core_id() -> None:
    item = GeneListItem(
        gene_id=5,
        core_id=None,
        gene_name='GATA3',
        gene_ensembl_id='ENSG00000165424',
        gene_type='unknown',
        species_name='人类',
        chromosome='chr10',
        gene_start=8050500,
        gene_end=8125000,
        regulation_count=0,
    )

    assert item.core_id is None


def test_gene_detail_allows_null_core_id_without_orthologs() -> None:
    detail = GeneDetail(
        gene_id=5,
        core_id=None,
        species_id=1,
        species_name='人类',
        gene_name='GATA3',
        gene_ensembl_id='ENSG00000165424',
        gene_type='unknown',
        chromosome='chr10',
        gene_start=8050500,
        gene_end=8125000,
        strand='+',
        regulation_count=0,
        target_count=0,
        disease_count=0,
        orthologs=[],
        created_at=None,
    )

    assert detail.core_id is None
    assert detail.orthologs == []
