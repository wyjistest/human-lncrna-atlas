import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.schemas.lncrna_chipseq_overlap import OverlapSortField, OverlapSortOrder


def _make_request(
    *,
    path: str = "/api/v1/lncrna-chipseq-overlap",
    method: str = "GET",
    client_ip: str = "127.0.0.1",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers or [(b"host", b"testserver")],
        "client": (client_ip, 12345),
        "server": ("testserver", 80),
        "root_path": "",
    }
    return Request(scope)


pytestmark = pytest.mark.unit


def _unwrap(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__  # type: ignore[attr-defined]
    return func


@pytest.mark.parametrize("chromosome", ["chr1", "chr2", "chr3"])
def test_large_chr_query_without_mv_requires_narrowing_filter(monkeypatch, chromosome):
    import app.routers.lncrna_chipseq_overlap as mod

    monkeypatch.setattr(mod, "check_materialized_view_exists", lambda db: False)

    handler = _unwrap(mod.get_lncrna_chipseq_overlaps)

    with pytest.raises(HTTPException) as exc:
        handler(
            _make_request(),
            lncrna_gene_id=None,
            target_gene_id=None,
            mark_type=None,
            cell_type=None,
            chromosome=chromosome,
            min_overlap_length=None,
            min_binding_affinity=None,
            min_peak_strength=None,
            max_qvalue=0.05,
            page=1,
            page_size=10,
            sort_by=OverlapSortField.binding_affinity,
            sort_order=OverlapSortOrder.desc,
            db=object(),
        )

    assert exc.value.status_code == 400
    assert isinstance(exc.value.detail, dict)
    assert exc.value.detail.get("error") == "QUERY_TOO_BROAD"
    assert exc.value.detail.get("chromosome") == chromosome


@pytest.mark.parametrize("chromosome", ["chr1", "chr2", "chr3"])
def test_large_chr_query_with_mark_type_allowed_without_mv(monkeypatch, chromosome):
    import app.routers.lncrna_chipseq_overlap as mod

    monkeypatch.setattr(mod, "check_materialized_view_exists", lambda db: False)
    monkeypatch.setattr(mod, "get_lncrna_chipseq_overlaps_query", lambda db, filters: ([], 0))

    handler = _unwrap(mod.get_lncrna_chipseq_overlaps)
    resp = handler(
        _make_request(),
        lncrna_gene_id=None,
        target_gene_id=None,
        mark_type="H3K27me3",
        cell_type=None,
        chromosome=chromosome,
        min_overlap_length=None,
        min_binding_affinity=None,
        min_peak_strength=None,
        max_qvalue=0.05,
        page=1,
        page_size=10,
        sort_by=OverlapSortField.binding_affinity,
        sort_order=OverlapSortOrder.desc,
        db=object(),
    )

    assert resp.total == 0
    assert resp.page == 1
    assert resp.page_size == 10
    assert resp.using_materialized_view is False
    assert resp.default_filter_applied is False
    assert resp.effective_chromosome == chromosome
