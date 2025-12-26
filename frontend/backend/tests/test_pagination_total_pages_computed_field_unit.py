import pytest


@pytest.mark.unit
def test_repeatmasker_response_model_dump_includes_total_pages():
    from app.schemas.features import RepeatMaskerResponse

    resp = RepeatMaskerResponse(total=101, items=[], page=1, page_size=50)
    dumped = resp.model_dump()

    assert dumped["total_pages"] == 3


@pytest.mark.unit
def test_chipseq_paginated_response_model_dump_includes_total_pages():
    from app.schemas.chipseq import ChIPSeqPaginatedResponse

    resp = ChIPSeqPaginatedResponse(total=101, items=[], page=2, page_size=50)
    dumped = resp.model_dump()

    assert dumped["total_pages"] == 3

