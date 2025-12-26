import pytest


class _DummyCursor:
    def __init__(self):
        self.executed: list[tuple[str, object]] = []
        self.rowcount = 0

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split())
        self.executed.append((normalized, params))

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyConn:
    def __init__(self, cursor: _DummyCursor):
        self._cursor = cursor
        self.rollbacks = 0
        self.commits = 0

    def cursor(self):
        return self._cursor

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1


@pytest.mark.unit
def test_batch_manager_rollback_writes_error_message():
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    try:
        from etl.templates.batch_manager import BatchManager  # type: ignore

        cur = _DummyCursor()
        conn = _DummyConn(cur)

        # Use a non-regulations batch type with a cleanup callback so rollback path is deterministic.
        bm = BatchManager(
            conn,
            batch_name="Test Batch",
            batch_type="repeatmasker",
            cleanup_callback=lambda _batch_id, _cursor: None,
        )
        bm.batch_id = 123

        bm._rollback_batch(error_message="boom")  # noqa: SLF001 - unit test for rollback behavior

        assert conn.rollbacks == 1
        assert conn.commits == 1
        assert cur.executed, "Expected UPDATE statement"
        sql_text, params = cur.executed[-1]
        assert "UPDATE import_batches" in sql_text
        assert "error_message = %s" in sql_text
        assert params == ("boom", 123)
    finally:
        try:
            sys.path.remove(str(repo_root))
        except ValueError:
            pass

