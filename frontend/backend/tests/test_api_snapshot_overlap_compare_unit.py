import importlib.util
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest


def _load_api_snapshot_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "api_snapshot.py"
    spec = importlib.util.spec_from_file_location("api_snapshot", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_api_snapshot_includes_overlap_compare_endpoints(monkeypatch):
    api_snapshot = _load_api_snapshot_module()

    def ok(payload):
        digest = api_snapshot._sha256_hex(api_snapshot._stable_json_bytes(payload))
        return api_snapshot.EndpointResult(status_code=200, json=payload, sha256=digest, error=None)

    def http_get_json(url: str, *, timeout_seconds: float):
        parsed = urlparse(url)
        path = parsed.path
        qs = parse_qs(parsed.query or "")

        if path == "/health":
            return ok({"status": "ok"})
        if path == "/api/v1/stats/overview":
            return ok({"status": "ok"})
        if path == "/api/v1/genes":
            return ok({"total": 1, "items": [{"gene_id": 1}]})
        if path == "/api/v1/genes/options":
            return ok(
                {
                    "genes": [
                        {
                            "gene_id": 101,
                            "gene_ensembl_id": "ENSG00000101",
                            "gene_name": "LNC_A",
                            "species_id": 1,
                            "species_name": "Human",
                        },
                        {
                            "gene_id": 102,
                            "gene_ensembl_id": "ENSG00000102",
                            "gene_name": "LNC_B",
                            "species_id": 1,
                            "species_name": "Human",
                        },
                    ]
                }
            )
        if path.startswith("/api/v1/genes/"):
            gene_id = int(path.rsplit("/", 1)[-1])
            # 101 intentionally lacks core_id to simulate an invalid ortholog mapping candidate.
            if gene_id == 101:
                return ok({"gene_id": 101, "core_id": None})
            return ok({"gene_id": gene_id, "core_id": 222})
        if path == "/api/v1/regulations":
            return ok({"total": 1, "items": [{"regulation_id": 1}]})
        if path.startswith("/api/v1/regulations/"):
            return ok({"regulation_id": 1})
        if path == "/api/v1/diseases/options":
            return ok({"traits": []})
        if path.startswith("/api/v1/stats/top-genes"):
            return ok({"items": []})
        if path.startswith("/api/v1/stats/top-diseases"):
            return ok({"items": []})
        if path == "/api/v1/analysis/summary":
            return ok({"status": "ok"})

        if path == "/api/v1/features/chipseq/marks":
            return ok({"items": []})
        if path == "/api/v1/features/chipseq/marks/relationships":
            return ok({"items": []})
        if path == "/api/v1/features/chipseq/marks/1":
            return ok({"items": []})
        if path == "/api/v1/features/chipseq/stats":
            return ok({"status": "ok"})
        if path == "/api/v1/features/chipseq/experiments":
            return ok({"items": [{"experiment_id": 1}]})
        if path.startswith("/api/v1/features/chipseq/experiments/"):
            return ok({"experiment_id": 1})
        if path.startswith("/api/v1/features/chipseq/regions/"):
            return ok({"items": [], "total": 0})
        if path.startswith("/api/v1/igv/chipseq/marks/"):
            return ok({"items": []})

        if path == "/api/v1/lncrna-chipseq-overlap":
            return ok({"items": [], "total": 0})
        if path == "/api/v1/lncrna-chipseq-overlap/cursor":
            return ok({"items": [], "total": 0})
        if path == "/api/v1/lncrna-chipseq-overlap/statistics":
            return ok({"total_overlaps": 0})

        if path == "/api/v1/lncrna-chipseq-overlap/compare":
            lncrna_gene_id = int((qs.get("lncrna_gene_id") or ["0"])[0])
            # 101 should not be selected because it lacks core_id above.
            if lncrna_gene_id == 101:
                return api_snapshot.EndpointResult(
                    status_code=400,
                    json={"detail": "LncRNA has no core_id (ortholog mapping unavailable)"},
                    sha256="",
                    error=None,
                )
            return ok(
                {
                    "lncrna_core_id": 222,
                    "target_core_id": None,
                    "species_names": {"1": "Human"},
                    "species_stats": {
                        "1": {
                            "species_id": 1,
                            "species_name": "Human",
                            "lncrna_gene_id": lncrna_gene_id,
                            "target_gene_id": None,
                            "statistics": {"total_overlaps": 0},
                        }
                    },
                }
            )

        raise AssertionError(f"Unexpected URL in api_snapshot: {url}")

    monkeypatch.setattr(api_snapshot, "_http_get_json", http_get_json)

    snap = api_snapshot._snapshot("http://example.test", timeout_seconds=0.1)
    endpoints = snap["endpoints"]

    assert "lncrna_chipseq_overlap_compare_from_lncrna_options_top_n_3" in endpoints
    assert endpoints["lncrna_chipseq_overlap_compare_from_lncrna_options_top_n_3"]["status_code"] == 200

    assert "lncrna_chipseq_overlap_compare_from_lncrna_options_species_ids_1_3_top_n_3" in endpoints
    assert (
        endpoints["lncrna_chipseq_overlap_compare_from_lncrna_options_species_ids_1_3_top_n_3"]["status_code"]
        == 200
    )
