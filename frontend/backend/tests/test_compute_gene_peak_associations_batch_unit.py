import importlib.util
from pathlib import Path
import sys

import pytest


def _load_compute_gene_peak_associations_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "frontend" / "backend" / "scripts" / "compute_gene_peak_associations.py"

    spec = importlib.util.spec_from_file_location("compute_gene_peak_associations", script_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeConn:
    def __init__(self):
        self.commits = 0
        self.closed = False

    def commit(self):
        self.commits += 1

    def rollback(self):
        # 供异常路径使用（本测试不覆盖）
        pass

    def close(self):
        self.closed = True


@pytest.mark.unit
def test_compute_gene_peak_associations_dry_run_skips_compute(monkeypatch):
    mod = _load_compute_gene_peak_associations_module()
    conn = _FakeConn()

    experiments = [
        mod.ActiveExperiment(
            experiment_id=1,
            species_id=1,
            experiment_name="ENCODE_TEST_1",
            reference_genome="hg19",
        ),
        mod.ActiveExperiment(
            experiment_id=2,
            species_id=1,
            experiment_name="ENCODE_TEST_2",
            reference_genome="hg19",
        ),
    ]

    monkeypatch.setattr(mod.psycopg2, "connect", lambda **_: conn)
    monkeypatch.setattr(mod, "has_gene_peak_associations_table", lambda _conn: True)
    monkeypatch.setattr(mod, "fetch_active_experiments", lambda _conn: experiments)
    monkeypatch.setattr(mod, "experiment_has_any_associations", lambda _conn, experiment_id: False)

    compute_calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        mod,
        "compute_gene_peak_associations_for_experiment",
        lambda _conn, experiment_id, species_id, **__: compute_calls.append((experiment_id, species_id))
        or 0,
    )

    refresh_calls = {"n": 0}
    monkeypatch.setattr(
        mod,
        "refresh_chipseq_materialized_views",
        lambda _conn: refresh_calls.__setitem__("n", refresh_calls["n"] + 1),
    )

    rc = mod.main(["--dry-run"])
    assert rc == 0
    assert compute_calls == []
    assert refresh_calls["n"] == 0
    assert conn.commits == 0


@pytest.mark.unit
def test_compute_gene_peak_associations_runs_for_active_experiments(monkeypatch):
    mod = _load_compute_gene_peak_associations_module()
    conn = _FakeConn()

    experiments = [
        mod.ActiveExperiment(
            experiment_id=10,
            species_id=1,
            experiment_name="HAS_ASSOC",
            reference_genome="hg19",
        ),
        mod.ActiveExperiment(
            experiment_id=11,
            species_id=1,
            experiment_name="NEEDS_ASSOC",
            reference_genome="hg19",
        ),
        mod.ActiveExperiment(
            experiment_id=12,
            species_id=1,
            experiment_name="HG38_SHOULD_SKIP",
            reference_genome="hg38",
        ),
    ]
    existing = {10: True, 11: False, 12: False}

    monkeypatch.setattr(mod.psycopg2, "connect", lambda **_: conn)
    monkeypatch.setattr(mod, "has_gene_peak_associations_table", lambda _conn: True)
    monkeypatch.setattr(mod, "fetch_active_experiments", lambda _conn: experiments)
    monkeypatch.setattr(
        mod,
        "experiment_has_any_associations",
        lambda _conn, experiment_id: existing.get(experiment_id, False),
    )

    compute_calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        mod,
        "compute_gene_peak_associations_for_experiment",
        lambda _conn, experiment_id, species_id, **__: compute_calls.append((experiment_id, species_id))
        or 123,
    )

    refresh_calls = {"n": 0}
    monkeypatch.setattr(
        mod,
        "refresh_chipseq_materialized_views",
        lambda _conn: refresh_calls.__setitem__("n", refresh_calls["n"] + 1),
    )

    rc = mod.main([])
    assert rc == 0
    assert compute_calls == [(11, 1)]
    assert refresh_calls["n"] == 1
    assert conn.commits == 2  # 每个 experiment compute 一次 + refresh MV 一次
