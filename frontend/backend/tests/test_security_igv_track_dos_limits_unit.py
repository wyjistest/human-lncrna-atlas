"""
Unit tests: IGV streaming track endpoints should have basic DoS guards.

Focus:
- Default max_records for unbounded requests (no region filter) to prevent full-table streaming.
- Region size upper bound to avoid large window scans.
"""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.database import get_db
from app.models import ChIPSeqExperiment, EpigeneticMarkType, FeatureTrack, Species
import app.routers.igv_repeatmasker as igv_repeatmasker
import app.routers.igv_regulations as igv_regulations
import app.routers.igv_chipseq as igv_chipseq


pytestmark = pytest.mark.unit


class _FakeQuery:
    def __init__(self, *, first_row=None):
        self._first_row = first_row

    def filter(self, *args, **kwargs):  # noqa: ARG002
        return self

    def first(self):
        return self._first_row

    def scalar(self):
        return 0


class _DummySession:
    def query(self, model, *args, **kwargs):  # noqa: ARG002
        if model is Species:
            return _FakeQuery(first_row=SimpleNamespace(species_id=1, display_name="Human"))
        if model is EpigeneticMarkType:
            return _FakeQuery(first_row=SimpleNamespace(mark_type_id=1, mark_name="H3K27me3"))
        if model is ChIPSeqExperiment.experiment_id:
            return _FakeQuery(first_row=SimpleNamespace(experiment_id=1))
        if model is FeatureTrack:
            return _FakeQuery(first_row=SimpleNamespace(track_id=1))
        return _FakeQuery(first_row=None)


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(igv_repeatmasker.router, prefix="/api/v1/igv")
    app.include_router(igv_regulations.router, prefix="/api/v1/igv")
    app.include_router(igv_chipseq.router, prefix="/api/v1/igv")

    def _override_get_db():
        yield _DummySession()

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_repeatmasker_bed_default_limit_when_no_region_filter(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    seen = {}

    def _fake_stream(*, max_records=None, **kwargs):  # noqa: ARG001
        seen["max_records"] = max_records
        yield "chr1\t0\t1\trepeat\t0\t.\n"

    monkeypatch.setattr(igv_repeatmasker, "generate_repeatmasker_bed_stream", _fake_stream)

    resp = client.get("/api/v1/igv/tracks/repeatmasker/1.bed")
    assert resp.status_code == 200
    assert seen["max_records"] == igv_repeatmasker.DEFAULT_MAX_RECORDS_NO_REGION


def test_repeatmasker_bed_limit_overrides_default(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    seen = {}

    def _fake_stream(*, max_records=None, **kwargs):  # noqa: ARG001
        seen["max_records"] = max_records
        yield "chr1\t0\t1\trepeat\t0\t.\n"

    monkeypatch.setattr(igv_repeatmasker, "generate_repeatmasker_bed_stream", _fake_stream)

    resp = client.get("/api/v1/igv/tracks/repeatmasker/1.bed", params={"limit": 123})
    assert resp.status_code == 200
    assert seen["max_records"] == 123


def test_repeatmasker_bed_region_filter_disables_default_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    seen = {}

    def _fake_stream(*, max_records=None, **kwargs):  # noqa: ARG001
        seen["max_records"] = max_records
        yield "chr1\t0\t1\trepeat\t0\t.\n"

    monkeypatch.setattr(igv_repeatmasker, "generate_repeatmasker_bed_stream", _fake_stream)

    resp = client.get(
        "/api/v1/igv/tracks/repeatmasker/1.bed",
        params={"chr": "chr1", "start": 0, "end": 100},
    )
    assert resp.status_code == 200
    assert seen["max_records"] is None


def test_repeatmasker_bed_region_too_large_returns_400(client: TestClient):
    resp = client.get(
        "/api/v1/igv/tracks/repeatmasker/1.bed",
        params={"chr": "chr1", "start": 0, "end": igv_repeatmasker.MAX_REGION_SIZE_BP + 1},
    )
    assert resp.status_code == 400


def test_regulations_bed_default_limit_when_no_region_and_no_lncrna(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    seen = {}

    def _fake_stream(*, max_records=None, **kwargs):  # noqa: ARG001
        seen["max_records"] = max_records
        yield "chr1\t0\t1\tLNC->TGT\t1\t.\n"

    monkeypatch.setattr(igv_regulations, "generate_bed_stream", _fake_stream)

    resp = client.get("/api/v1/igv/tracks/regulations/1.bed")
    assert resp.status_code == 200
    assert seen["max_records"] == igv_regulations.DEFAULT_MAX_RECORDS_NO_REGION


def test_regulations_bed_no_default_limit_when_lncrna_provided(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    seen = {}

    def _fake_stream(*, max_records=None, **kwargs):  # noqa: ARG001
        seen["max_records"] = max_records
        yield "chr1\t0\t1\tLNC->TGT\t1\t.\n"

    monkeypatch.setattr(igv_regulations, "generate_bed_stream", _fake_stream)

    resp = client.get("/api/v1/igv/tracks/regulations/1.bed", params={"lncrna": "LNC_TEST"})
    assert resp.status_code == 200
    assert seen["max_records"] is None


def test_interactions_bedpe_default_limit_when_no_region_and_no_lncrna(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    seen = {}

    def _fake_stream(*, max_records=None, **kwargs):  # noqa: ARG001
        seen["max_records"] = max_records
        yield "chr1\t0\t1\tchr1\t2\t3\tLNC|TGT\t1\n"

    monkeypatch.setattr(igv_regulations, "generate_bedpe_stream", _fake_stream)

    resp = client.get("/api/v1/igv/tracks/interactions/1.bedpe")
    assert resp.status_code == 200
    assert seen["max_records"] == igv_regulations.DEFAULT_MAX_RECORDS_NO_REGION


def test_regulations_bed_region_too_large_returns_400(client: TestClient):
    resp = client.get(
        "/api/v1/igv/tracks/regulations/1.bed",
        params={"chr": "chr1", "start": 0, "end": igv_regulations.MAX_REGION_SIZE_BP + 1},
    )
    assert resp.status_code == 400


def test_chipseq_bed_default_limit_when_no_region_filter(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    seen = {}

    def _fake_stream(*, max_records=None, **kwargs):  # noqa: ARG001
        seen["max_records"] = max_records
        yield "chr1\t0\t1\tpeak\t0\t.\t0\t0\t0\n"

    monkeypatch.setattr(igv_chipseq, "generate_chipseq_bed_stream", _fake_stream)

    resp = client.get("/api/v1/igv/tracks/chipseq/1.bed", params={"mark_type": "H3K27me3"})
    assert resp.status_code == 200
    assert seen["max_records"] == igv_chipseq.DEFAULT_MAX_RECORDS_NO_REGION


def test_chipseq_bed_limit_overrides_default(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    seen = {}

    def _fake_stream(*, max_records=None, **kwargs):  # noqa: ARG001
        seen["max_records"] = max_records
        yield "chr1\t0\t1\tpeak\t0\t.\t0\t0\t0\n"

    monkeypatch.setattr(igv_chipseq, "generate_chipseq_bed_stream", _fake_stream)

    resp = client.get(
        "/api/v1/igv/tracks/chipseq/1.bed",
        params={"mark_type": "H3K27me3", "limit": 123},
    )
    assert resp.status_code == 200
    assert seen["max_records"] == 123


def test_chipseq_bed_chromosome_only_uses_default_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    seen = {}

    def _fake_stream(*, max_records=None, **kwargs):  # noqa: ARG001
        seen["max_records"] = max_records
        yield "chr1\t0\t1\tpeak\t0\t.\t0\t0\t0\n"

    monkeypatch.setattr(igv_chipseq, "generate_chipseq_bed_stream", _fake_stream)

    resp = client.get(
        "/api/v1/igv/tracks/chipseq/1.bed",
        params={"mark_type": "H3K27me3", "chromosome": "chr1"},
    )
    assert resp.status_code == 200
    assert seen["max_records"] == igv_chipseq.DEFAULT_MAX_RECORDS_NO_REGION


def test_chipseq_bed_region_filter_disables_default_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    seen = {}

    def _fake_stream(*, max_records=None, **kwargs):  # noqa: ARG001
        seen["max_records"] = max_records
        yield "chr1\t0\t1\tpeak\t0\t.\t0\t0\t0\n"

    monkeypatch.setattr(igv_chipseq, "generate_chipseq_bed_stream", _fake_stream)

    resp = client.get(
        "/api/v1/igv/tracks/chipseq/1.bed",
        params={"mark_type": "H3K27me3", "chromosome": "chr1", "start": 0, "end": 100},
    )
    assert resp.status_code == 200
    assert seen["max_records"] is None


def test_chipseq_bed_region_too_large_returns_400(client: TestClient):
    resp = client.get(
        "/api/v1/igv/tracks/chipseq/1.bed",
        params={"mark_type": "H3K27me3", "chromosome": "chr1", "start": 0, "end": igv_chipseq.MAX_REGION_SIZE_BP + 1},
    )
    assert resp.status_code == 400


def test_chipseq_bed_mark_type_too_long_returns_422(client: TestClient):
    resp = client.get(
        "/api/v1/igv/tracks/chipseq/1.bed",
        params={"mark_type": "a" * 65},
    )
    assert resp.status_code == 422
