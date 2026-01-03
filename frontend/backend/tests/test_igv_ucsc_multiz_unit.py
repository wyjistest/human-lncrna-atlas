import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.mounts.genomes import mount_genomes_app
import app.routers.igv_ucsc_multiz as igv_ucsc_multiz


pytestmark = pytest.mark.unit


def test_ucsc_multiz_endpoint_returns_empty_when_no_genomes_dir(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "GENOMES_DIR", str(tmp_path), raising=False)

    app = FastAPI()
    app.include_router(igv_ucsc_multiz.router, prefix="/api/v1/igv")
    # GENOMES_DIR 存在但没有相关 .bw 文件时，端点应返回空 tracks
    mount_genomes_app(app)
    client = TestClient(app)

    resp = client.get("/api/v1/igv/config/ucsc-multiz/1")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert payload["data"]["genome_assembly"] == "hg19"
    assert payload["data"]["tracks"] == []


def test_ucsc_multiz_tracks_discovery_and_range_serving(tmp_path, monkeypatch: pytest.MonkeyPatch):
    phastcons_path = tmp_path / "hg19.100way.phastCons.bw"
    phylop_path = tmp_path / "hg19.100way.phyloP100way.bw"

    phastcons_path.write_bytes(b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    phylop_path.write_bytes(b"abcdefghijklmnopqrstuvwxyz0123456789")

    monkeypatch.setattr(settings, "GENOMES_DIR", str(tmp_path), raising=False)

    app = FastAPI()
    app.include_router(igv_ucsc_multiz.router, prefix="/api/v1/igv")
    assert mount_genomes_app(app) is True
    client = TestClient(app)

    resp = client.get("/api/v1/igv/config/ucsc-multiz/1")
    assert resp.status_code == 200
    payload = resp.json()
    tracks = payload["data"]["tracks"]

    assert {t["id"] for t in tracks} == {
        "ucsc_multiz_phastCons100way_hg19",
        "ucsc_multiz_phyloP100way_hg19",
    }

    by_id = {t["id"]: t for t in tracks}
    assert by_id["ucsc_multiz_phastCons100way_hg19"]["url"] == "/genomes/hg19.100way.phastCons.bw"
    assert by_id["ucsc_multiz_phyloP100way_hg19"]["url"] == "/genomes/hg19.100way.phyloP100way.bw"

    # StaticFiles 应支持 HTTP Range（IGV.js 读取 BigWig/2bit 的前提）
    range_resp = client.get(
        "/genomes/hg19.100way.phastCons.bw",
        headers={"Range": "bytes=0-9"},
    )
    assert range_resp.status_code == 206
    assert range_resp.content == b"0123456789"
    assert "content-range" in {k.lower() for k in range_resp.headers.keys()}

