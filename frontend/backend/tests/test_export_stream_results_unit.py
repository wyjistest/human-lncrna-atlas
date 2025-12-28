import pytest
from starlette.requests import Request
from fastapi.responses import StreamingResponse


class _DummySession:
    def __init__(self):
        self.calls = []

    def execute(self, stmt, params=None):  # noqa: ANN001 - test double
        self.calls.append((stmt, params))
        # Return an empty iterable; StreamingResponse will still emit headers.
        return []


def _make_request(path: str, *, query_string: bytes = b"") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "query_string": query_string,
        "headers": [],
        "client": ("testclient", 123),
        "server": ("testserver", 80),
        "scheme": "http",
        "root_path": "",
    }
    return Request(scope)


@pytest.mark.unit
def test_execute_streaming_sets_stream_results_for_select_and_text():
    from sqlalchemy import select, text
    from app.routers.export import _execute_streaming

    db = _DummySession()

    _execute_streaming(db, select(1))
    _execute_streaming(db, text("select 1"))

    assert len(db.calls) == 2
    for stmt, _params in db.calls:
        assert getattr(stmt, "_execution_options", {}).get("stream_results") is True


@pytest.mark.unit
def test_export_high_affinity_csv_uses_stream_results():
    from app.routers.export import export_high_affinity

    db = _DummySession()
    request = _make_request("/api/v1/export/high-affinity")

    resp = export_high_affinity(
        request=request,
        min_ba=100.0,
        species_id=None,
        limit=10,
        output_format="csv",
        db=db,
    )

    assert isinstance(resp, StreamingResponse)
    assert db.calls, "Expected DB execute() to be called"
    stmt, _params = db.calls[0]
    assert getattr(stmt, "_execution_options", {}).get("stream_results") is True

