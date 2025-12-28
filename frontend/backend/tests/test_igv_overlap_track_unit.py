"""
IGV overlap-track 路由单元测试（不依赖外部服务/数据库）

目标：
- 覆盖 chr/chromosome 参数别名与标准化
- 覆盖 start/end 与区域大小校验
- 保证输出为 text/plain 且为 BED6（至少一行）
"""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.database import get_db
from app.routers.igv_overlap_track import router as overlap_track_router

pytestmark = pytest.mark.unit


class _DummyResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class _DummySession:
    """最小 Session stub：仅覆盖 overlap-track 所需方法。"""

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def execute(self, sql, params=None):
        sql_text = getattr(sql, "text", str(sql))
        params = params or {}

        # 物化视图可用性检查：返回 relispopulated=True
        if "pg_class" in sql_text:
            return _DummyResult([SimpleNamespace(relname="mv_lncrna_chipseq_overlaps", relispopulated=True)])

        # overlap 主查询：返回一条数据，便于校验 BED6 结构与 chr 标准化
        chromosome = params.get("chromosome", "chr1")
        mark_type = params.get("mark_type") or "H3K27me3"
        return _DummyResult(
            [
                SimpleNamespace(
                    chromosome=chromosome,
                    overlap_start=params.get("start", 0),
                    overlap_end=params.get("end", 1),
                    lncrna_name="LNC_TEST",
                    target_gene_name="GENE_TEST",
                    mark_type=mark_type,
                    cell_type="K562",
                    binding_affinity=100.0,
                )
            ]
        )


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(overlap_track_router, prefix="/api/v1/igv")

    def _override_get_db():
        yield _DummySession()

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_missing_chr_and_chromosome_returns_400(client: TestClient):
    resp = client.get("/api/v1/igv/overlap-track", params={"start": 0, "end": 1})
    assert resp.status_code == 400


def test_start_greater_or_equal_end_returns_400(client: TestClient):
    resp = client.get("/api/v1/igv/overlap-track", params={"chr": "chr1", "start": 10, "end": 10})
    assert resp.status_code == 400


def test_region_too_large_returns_400(client: TestClient):
    resp = client.get(
        "/api/v1/igv/overlap-track",
        params={"chr": "chr1", "start": 0, "end": 10_000_001},
    )
    assert resp.status_code == 400


def test_chr_is_normalized_and_output_is_bed6(client: TestClient):
    resp = client.get(
        "/api/v1/igv/overlap-track",
        params={"chr": "1", "start": 0, "end": 100},
    )
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("text/plain")

    line = resp.text.strip().splitlines()[0]
    fields = line.split("\t")
    assert fields[0] == "chr1"
    assert len(fields) == 6


def test_chromosome_alias_is_supported(client: TestClient):
    resp = client.get(
        "/api/v1/igv/overlap-track",
        params={"chromosome": "22", "start": 0, "end": 100},
    )
    assert resp.status_code == 200
    line = resp.text.strip().splitlines()[0]
    assert line.split("\t")[0] == "chr22"


def test_mark_type_is_included_in_name_field(client: TestClient):
    resp = client.get(
        "/api/v1/igv/overlap-track",
        params={"chr": "chr1", "start": 0, "end": 100, "mark_type": "H3K27me3"},
    )
    assert resp.status_code == 200
    line = resp.text.strip().splitlines()[0]
    fields = line.split("\t")
    assert "H3K27me3" in fields[3]
