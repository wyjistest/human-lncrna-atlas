import pytest

from app.routers.chipseq_genes import _build_batch_heatmap_gene_result
from app.schemas.chipseq import CellMarkStats


@pytest.mark.unit
def test_build_batch_heatmap_gene_result_median_and_missing_combinations():
    mark_list = ["H3K27me3", "H3K4me3"]
    cell_type_list = ["K562", "HepG2"]

    stats_by_cell_mark = {
        "K562": {
            "H3K27me3": CellMarkStats(
                median_fold_enrichment=1.5,
                peak_count=2,
                total_coverage_bp=100,
                avg_signal=0.2,
                std_fold_enrichment=0.1,
            )
        }
    }

    result = _build_batch_heatmap_gene_result(
        gene_id=17276,
        gene_name="TEST1",
        gene_ensembl_id="ENSG00000000001",
        chromosome="chr1",
        region_start=100,
        region_end=200,
        mark_list=mark_list,
        cell_type_list=cell_type_list,
        metric="median_fold_enrichment",
        include_details=True,
        stats_by_cell_mark=stats_by_cell_mark,
    )

    assert result.matrix == [
        [1.5, None],
        [None, None],
    ]
    assert result.total_combinations == 4
    assert result.valid_combinations == 1
    assert result.missing_combinations is not None
    assert {"cell_type": "K562", "mark": "H3K4me3"} in result.missing_combinations

    assert result.details is not None
    assert result.details["K562"]["H3K27me3"].peak_count == 2
    assert "H3K4me3" not in result.details["K562"]
    assert result.details["HepG2"] == {}


def test_build_batch_heatmap_gene_result_peak_count_without_details():
    mark_list = ["H3K27me3"]
    cell_type_list = ["K562"]

    stats_by_cell_mark = {
        "K562": {
            "H3K27me3": CellMarkStats(
                median_fold_enrichment=1.5,
                peak_count=3,
                total_coverage_bp=100,
                avg_signal=0.2,
            )
        }
    }

    result = _build_batch_heatmap_gene_result(
        gene_id=1,
        gene_name="TEST2",
        gene_ensembl_id="ENSG00000000002",
        chromosome="chr2",
        region_start=0,
        region_end=10,
        mark_list=mark_list,
        cell_type_list=cell_type_list,
        metric="peak_count",
        include_details=False,
        stats_by_cell_mark=stats_by_cell_mark,
    )

    assert result.details is None
    assert result.matrix == [[3.0]]
    assert result.missing_combinations is None

