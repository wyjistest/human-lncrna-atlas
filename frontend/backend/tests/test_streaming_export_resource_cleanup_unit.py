import pytest


class _DummyRow:
    def __init__(self, mapping: dict):
        self._mapping = mapping


class _DummyResult:
    def __init__(self, rows: list[_DummyRow]):
        self._rows = rows
        self.closed = False

    def __iter__(self):
        return iter(self._rows)

    def close(self):
        self.closed = True


@pytest.mark.unit
def test_create_db_row_generator_closes_result_after_full_iteration():
    from app.utils.streaming_export import create_db_row_generator

    result = _DummyResult([_DummyRow({"x": 1}), _DummyRow({"x": 2})])
    rows = list(create_db_row_generator(result))
    assert rows == [{"x": 1}, {"x": 2}]
    assert result.closed is True


@pytest.mark.unit
def test_create_db_row_generator_closes_result_on_early_close():
    from app.utils.streaming_export import create_db_row_generator

    result = _DummyResult([_DummyRow({"x": 1}), _DummyRow({"x": 2})])
    gen = create_db_row_generator(result)
    assert next(gen) == {"x": 1}
    gen.close()
    assert result.closed is True

