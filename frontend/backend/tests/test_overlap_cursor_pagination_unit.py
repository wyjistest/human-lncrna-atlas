import pytest
from fastapi import HTTPException
from starlette.requests import Request
import inspect
from decimal import Decimal

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


def _unwrap(func):
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__  # type: ignore[attr-defined]
    return func


pytestmark = pytest.mark.unit


def test_cursor_endpoint_symbol_exists():
    import app.routers.lncrna_chipseq_overlap as mod

    assert hasattr(mod, "get_lncrna_chipseq_overlaps_cursor"), "需要新增 cursor 分页端点"


def test_cursor_endpoint_has_cursor_and_page_size_params():
    import app.routers.lncrna_chipseq_overlap as mod

    handler = _unwrap(mod.get_lncrna_chipseq_overlaps_cursor)
    sig = inspect.signature(handler)
    assert "cursor" in sig.parameters
    assert "page_size" in sig.parameters
    assert "sort_by" in sig.parameters
    assert "sort_order" in sig.parameters


def test_invalid_chromosome_returns_http_422(monkeypatch):
    import app.routers.lncrna_chipseq_overlap as mod

    monkeypatch.setattr(mod, "check_materialized_view_exists", lambda db: False)

    handler = _unwrap(mod.get_lncrna_chipseq_overlaps)

    with pytest.raises(Exception) as exc:
        handler(
            _make_request(),
            lncrna_gene_id=None,
            target_gene_id=None,
            mark_type=None,
            cell_type=None,
            chromosome="chr999",
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

    assert isinstance(exc.value, HTTPException)
    assert exc.value.status_code == 422


def test_cursor_response_schema_exists():
    import app.schemas.lncrna_chipseq_overlap as schemas

    assert hasattr(schemas, "OverlapCursorResponse"), "需要新增 cursor 分页响应模型"


def test_cursor_endpoint_returns_cursor_response(monkeypatch):
    import app.schemas.lncrna_chipseq_overlap as schemas
    import app.routers.lncrna_chipseq_overlap as mod

    assert hasattr(schemas, "OverlapCursorResponse"), "需要新增 cursor 分页响应模型"

    monkeypatch.setattr(mod, "check_materialized_view_exists", lambda db: True)
    monkeypatch.setattr(
        mod,
        "get_lncrna_chipseq_overlaps_cursor_from_mv",
        lambda db, filters, *, cursor, page_size, sort_by, sort_order: ([], 0),
        raising=False,
    )

    handler = _unwrap(mod.get_lncrna_chipseq_overlaps_cursor)

    try:
        resp = handler(
            _make_request(path="/api/v1/lncrna-chipseq-overlap/cursor"),
            lncrna_gene_id=None,
            target_gene_id=None,
            mark_type=None,
            cell_type=None,
            chromosome=None,
            min_overlap_length=None,
            min_binding_affinity=None,
            min_peak_strength=None,
            max_qvalue=0.05,
            cursor=None,
            page_size=2,
            sort_by=OverlapSortField.binding_affinity,
            sort_order=OverlapSortOrder.desc,
            db=object(),
        )
    except Exception as e:
        assert False, f"cursor 端点不应抛异常: {e}"

    assert isinstance(resp, schemas.OverlapCursorResponse)


def test_cursor_endpoint_sets_items_total_and_next_cursor(monkeypatch):
    import app.routers.lncrna_chipseq_overlap as mod

    monkeypatch.setattr(mod, "check_materialized_view_exists", lambda db: True)

    def _item(overlap_id: str, *, regulation_id: int, binding_affinity: str):
        return {
            "overlap_id": overlap_id,
            "regulation_id": regulation_id,
            "lncrna_gene_id": 1,
            "lncrna_name": "lnc",
            "target_gene_id": 2,
            "target_gene_name": "tgt",
            "mark_type": "H3K27me3",
            "mark_category": "repressive",
            "cell_type": "K562",
            "chromosome": "chr22",
            "lncrna_binding_start": 10,
            "lncrna_binding_end": 20,
            "peak_start": 15,
            "peak_end": 25,
            "overlap_start": 15,
            "overlap_end": 20,
            "overlap_length": 5,
            "binding_affinity": Decimal(binding_affinity),
            "peak_fold_enrichment": Decimal("1.0"),
            "peak_qvalue": None,
        }

    def _fake_mv_cursor_query(db, filters, *, cursor, page_size, sort_by, sort_order):
        assert cursor is None
        assert page_size == 2
        assert sort_by == OverlapSortField.binding_affinity
        assert sort_order == OverlapSortOrder.desc

        # 返回 page_size + 1 条用于判断 has_more
        items = [
            _item("reg_1_peak_1", regulation_id=1, binding_affinity="100"),
            _item("reg_2_peak_2", regulation_id=2, binding_affinity="90"),
            _item("reg_3_peak_3", regulation_id=3, binding_affinity="80"),
        ]
        return items, 123

    monkeypatch.setattr(mod, "get_lncrna_chipseq_overlaps_cursor_from_mv", _fake_mv_cursor_query, raising=False)

    handler = _unwrap(mod.get_lncrna_chipseq_overlaps_cursor)
    resp = handler(
        _make_request(path="/api/v1/lncrna-chipseq-overlap/cursor"),
        lncrna_gene_id=None,
        target_gene_id=None,
        mark_type=None,
        cell_type=None,
        chromosome=None,
        min_overlap_length=None,
        min_binding_affinity=None,
        min_peak_strength=None,
        max_qvalue=0.05,
        cursor=None,
        page_size=2,
        sort_by=OverlapSortField.binding_affinity,
        sort_order=OverlapSortOrder.desc,
        db=object(),
    )

    assert resp.total == 123
    assert resp.page_size == 2
    assert len(resp.items) == 2
    assert resp.has_more is True
    assert isinstance(resp.next_cursor, str) and resp.next_cursor


def test_cursor_endpoint_decodes_cursor_payload(monkeypatch):
    import app.routers.lncrna_chipseq_overlap as mod

    monkeypatch.setattr(mod, "check_materialized_view_exists", lambda db: True)

    captured: dict = {}

    def _fake_mv_cursor_query(db, filters, *, cursor, page_size, sort_by, sort_order):
        captured["cursor"] = cursor
        return [], 0

    monkeypatch.setattr(mod, "get_lncrna_chipseq_overlaps_cursor_from_mv", _fake_mv_cursor_query, raising=False)

    token = mod._encode_overlap_cursor(
        {
            "v": 1,
            "sort_by": "binding_affinity",
            "sort_order": "desc",
            "sort_value": "90",
            "overlap_id": "reg_2_peak_2",
        }
    )

    handler = _unwrap(mod.get_lncrna_chipseq_overlaps_cursor)
    handler(
        _make_request(path="/api/v1/lncrna-chipseq-overlap/cursor"),
        lncrna_gene_id=None,
        target_gene_id=None,
        mark_type=None,
        cell_type=None,
        chromosome=None,
        min_overlap_length=None,
        min_binding_affinity=None,
        min_peak_strength=None,
        max_qvalue=0.05,
        cursor=token,
        page_size=2,
        sort_by=OverlapSortField.binding_affinity,
        sort_order=OverlapSortOrder.desc,
        db=object(),
    )

    assert isinstance(captured.get("cursor"), dict)
    assert captured["cursor"].get("overlap_id") == "reg_2_peak_2"
    assert str(captured["cursor"].get("sort_value")) == "90"


def test_cursor_endpoint_supports_peak_qvalue_sort(monkeypatch):
    import app.schemas.lncrna_chipseq_overlap as schemas
    import app.routers.lncrna_chipseq_overlap as mod

    monkeypatch.setattr(mod, "check_materialized_view_exists", lambda db: True)
    monkeypatch.setattr(
        mod,
        "get_lncrna_chipseq_overlaps_cursor_from_mv",
        lambda db, filters, *, cursor, page_size, sort_by, sort_order: ([], 0),
        raising=False,
    )

    handler = _unwrap(mod.get_lncrna_chipseq_overlaps_cursor)
    resp = handler(
        _make_request(path="/api/v1/lncrna-chipseq-overlap/cursor"),
        lncrna_gene_id=None,
        target_gene_id=None,
        mark_type=None,
        cell_type=None,
        chromosome=None,
        min_overlap_length=None,
        min_binding_affinity=None,
        min_peak_strength=None,
        max_qvalue=0.05,
        cursor=None,
        page_size=2,
        sort_by=OverlapSortField.peak_qvalue,
        sort_order=OverlapSortOrder.asc,
        db=object(),
    )

    assert isinstance(resp, schemas.OverlapCursorResponse)


def test_cursor_endpoint_encodes_null_qvalue(monkeypatch):
    import app.routers.lncrna_chipseq_overlap as mod

    monkeypatch.setattr(mod, "check_materialized_view_exists", lambda db: True)

    def _item(overlap_id: str, *, peak_qvalue):
        return {
            "overlap_id": overlap_id,
            "regulation_id": 1,
            "lncrna_gene_id": 1,
            "lncrna_name": "lnc",
            "target_gene_id": 2,
            "target_gene_name": "tgt",
            "mark_type": "H3K27me3",
            "mark_category": "repressive",
            "cell_type": "K562",
            "chromosome": "chr22",
            "lncrna_binding_start": 10,
            "lncrna_binding_end": 20,
            "peak_start": 15,
            "peak_end": 25,
            "overlap_start": 15,
            "overlap_end": 20,
            "overlap_length": 5,
            "binding_affinity": Decimal("1.0"),
            "peak_fold_enrichment": Decimal("1.0"),
            "peak_qvalue": peak_qvalue,
        }

    def _fake_mv_cursor_query(db, filters, *, cursor, page_size, sort_by, sort_order):
        items = [
            _item("reg_1_peak_1", peak_qvalue=Decimal("0.01")),
            _item("reg_2_peak_2", peak_qvalue=None),
            _item("reg_3_peak_3", peak_qvalue=None),
        ]
        return items, 3

    monkeypatch.setattr(mod, "get_lncrna_chipseq_overlaps_cursor_from_mv", _fake_mv_cursor_query, raising=False)

    handler = _unwrap(mod.get_lncrna_chipseq_overlaps_cursor)
    resp = handler(
        _make_request(path="/api/v1/lncrna-chipseq-overlap/cursor"),
        lncrna_gene_id=None,
        target_gene_id=None,
        mark_type=None,
        cell_type=None,
        chromosome=None,
        min_overlap_length=None,
        min_binding_affinity=None,
        min_peak_strength=None,
        max_qvalue=0.05,
        cursor=None,
        page_size=2,
        sort_by=OverlapSortField.peak_qvalue,
        sort_order=OverlapSortOrder.desc,
        db=object(),
    )

    assert resp.has_more is True
    assert isinstance(resp.next_cursor, str) and resp.next_cursor

    decoded = mod._decode_overlap_cursor(resp.next_cursor, sort_by=OverlapSortField.peak_qvalue, sort_order=OverlapSortOrder.desc)
    assert decoded.get("is_null") is True
    assert decoded.get("sort_value") is None


def test_cursor_endpoint_decodes_null_qvalue_cursor(monkeypatch):
    import app.routers.lncrna_chipseq_overlap as mod

    monkeypatch.setattr(mod, "check_materialized_view_exists", lambda db: True)

    captured: dict = {}

    def _fake_mv_cursor_query(db, filters, *, cursor, page_size, sort_by, sort_order):
        captured["cursor"] = cursor
        return [], 0

    monkeypatch.setattr(mod, "get_lncrna_chipseq_overlaps_cursor_from_mv", _fake_mv_cursor_query, raising=False)

    token = mod._encode_overlap_cursor(
        {
            "v": 1,
            "sort_by": "peak_qvalue",
            "sort_order": "asc",
            "is_null": True,
            "sort_value": None,
            "overlap_id": "reg_2_peak_2",
        }
    )

    handler = _unwrap(mod.get_lncrna_chipseq_overlaps_cursor)
    handler(
        _make_request(path="/api/v1/lncrna-chipseq-overlap/cursor"),
        lncrna_gene_id=None,
        target_gene_id=None,
        mark_type=None,
        cell_type=None,
        chromosome=None,
        min_overlap_length=None,
        min_binding_affinity=None,
        min_peak_strength=None,
        max_qvalue=0.05,
        cursor=token,
        page_size=2,
        sort_by=OverlapSortField.peak_qvalue,
        sort_order=OverlapSortOrder.asc,
        db=object(),
    )

    assert captured.get("cursor", {}).get("is_null") is True
    assert captured.get("cursor", {}).get("sort_value") is None


def test_join_cursor_peak_qvalue_null_segment_uses_is_null_keyset(monkeypatch):
    import app.routers.lncrna_chipseq_overlap as mod

    monkeypatch.setattr(mod.cache, "get_or_compute", lambda _key, fn, **_kwargs: fn())

    class _FakeResult:
        def __init__(self, *, one=None, all_rows=None):
            self._one = one
            self._all_rows = all_rows

        def fetchone(self):
            return self._one

        def fetchall(self):
            return self._all_rows

    class _FakeSession:
        def __init__(self):
            self.calls: list[tuple[object, dict]] = []

        def execute(self, stmt, params=None):
            self.calls.append((stmt, dict(params or {})))
            if len(self.calls) == 1:
                return _FakeResult(one=(0,))
            return _FakeResult(all_rows=[])

    fake_db = _FakeSession()
    filters = mod.OverlapFilters(
        chromosome="chr22",
        page_size=2,
        sort_by=OverlapSortField.peak_qvalue,
        sort_order=OverlapSortOrder.desc,
    )

    mod.get_lncrna_chipseq_overlaps_cursor_query(
        fake_db,
        filters,
        cursor={"overlap_id": "reg_2_peak_2", "sort_value": None, "is_null": True},
        page_size=2,
        sort_by=OverlapSortField.peak_qvalue,
        sort_order=OverlapSortOrder.desc,
    )

    # Second execute() is the data query.
    data_stmt = fake_db.calls[1][0]

    from sqlalchemy.dialects import postgresql

    sql = str(
        data_stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    )
    assert "qvalue IS NULL" in sql
    assert "cursor_sort_value" not in sql
