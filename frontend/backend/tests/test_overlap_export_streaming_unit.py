import types

import pytest


class _DummyResult:
    def __init__(self, *, fetchall_rows: list[object] | None = None, fetchmany_batches: list[list[object]] | None = None):
        self._fetchall_rows = list(fetchall_rows or [])
        self._fetchmany_batches = list(fetchmany_batches or [])
        self.closed = False

    def fetchall(self) -> list[object]:
        return list(self._fetchall_rows)

    def fetchmany(self, size: int) -> list[object]:
        if not self._fetchmany_batches:
            return []
        return self._fetchmany_batches.pop(0)

    def close(self) -> None:
        self.closed = True


class _DummyDB:
    """
    Fake SQLAlchemy Session for unit-testing streaming exporters.

    Supports both:
    - legacy offset-based loop (execute called multiple times with offset param)
    - new streaming loop (execute called once, then fetchmany on result)
    """

    def __init__(self, rows: list[object]):
        self._rows = list(rows)
        self.execute_calls = 0
        self.last_result: _DummyResult | None = None

    def execute(self, stmt, params=None):  # noqa: ANN001
        self.execute_calls += 1

        params = params or {}
        if isinstance(params, dict) and "offset" in params:
            offset = int(params.get("offset", 0) or 0)
            limit = int(params.get("limit", 0) or 0)
            if offset <= 0:
                batch = self._rows[: max(0, limit)]
            else:
                batch = []
            result = _DummyResult(fetchall_rows=batch)
        else:
            result = _DummyResult(fetchmany_batches=[self._rows[:2], self._rows[2:], []])

        self.last_result = result
        return result


def _make_row(*, overlap_id: str, overlap_start: int) -> object:
    return types.SimpleNamespace(
        overlap_id=overlap_id,
        regulation_id=1,
        lncrna_gene_id=2,
        lncrna_name="LNC",
        target_gene_id=3,
        target_gene_name="TGT",
        mark_type="H3K27me3",
        mark_category="histone",
        cell_type="K562",
        chromosome="chr22",
        lncrna_binding_start=100,
        lncrna_binding_end=200,
        peak_start=110,
        peak_end=190,
        overlap_start=overlap_start,
        overlap_end=overlap_start + 10,
        overlap_length=10,
        binding_affinity=80.0,
        peak_fold_enrichment=5.0,
        peak_qvalue=0.01,
    )


@pytest.mark.unit
def test_generate_overlap_export_uses_single_execute_and_closes_result():
    from app.routers.lncrna_chipseq_overlap import generate_overlap_export

    # Ensure legacy offset-based implementation would need >1 execute call:
    # max_rows=2001 -> first batch_limit=1000 -> triggers a second execute(offset=1000).
    rows = [_make_row(overlap_id=f"reg_{i}_peak_{i}", overlap_start=i * 10) for i in range(1, 1002)]
    db = _DummyDB(rows)

    kwargs = {
        "db": db,  # type: ignore[arg-type]
        "format": "csv",
        "chromosome": "chr22",
        "max_rows": 2001,
    }
    try:
        gen = generate_overlap_export(**kwargs, use_materialized_view=False)  # type: ignore[call-arg]
    except TypeError:
        gen = generate_overlap_export(**kwargs)  # type: ignore[call-arg]

    first = next(gen)
    assert "overlap_id" in first
    for _ in gen:
        pass

    assert db.execute_calls == 1
    assert db.last_result is not None and db.last_result.closed is True


@pytest.mark.unit
def test_generate_overlap_export_closes_result_when_max_rows_stops_early():
    from app.routers.lncrna_chipseq_overlap import generate_overlap_export

    rows = [
        _make_row(overlap_id="reg_1_peak_1", overlap_start=1000),
        _make_row(overlap_id="reg_2_peak_2", overlap_start=2000),
        _make_row(overlap_id="reg_3_peak_3", overlap_start=3000),
    ]
    db = _DummyDB(rows)

    kwargs = {
        "db": db,  # type: ignore[arg-type]
        "format": "csv",
        "chromosome": "chr22",
        "max_rows": 1,
    }
    try:
        gen = generate_overlap_export(**kwargs, use_materialized_view=False)  # type: ignore[call-arg]
    except TypeError:
        gen = generate_overlap_export(**kwargs)  # type: ignore[call-arg]

    content = "".join(gen)

    assert "reg_1_peak_1" in content
    assert "reg_2_peak_2" not in content

    assert db.execute_calls == 1
    assert db.last_result is not None and db.last_result.closed is True
