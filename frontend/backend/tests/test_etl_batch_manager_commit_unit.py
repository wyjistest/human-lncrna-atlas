import pytest


class _DummyCursor:
    def __init__(self):
        self.executed: list[tuple[str, object]] = []
        self._fetchone_calls = 0
        self.rowcount = 0

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split())
        self.executed.append((normalized, params))

    def fetchone(self):
        # First fetchone() is for INSERT ... RETURNING batch_id.
        self._fetchone_calls += 1
        return (123,)

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
def test_batch_manager_commit_inside_with_does_not_double_complete():
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    try:
        from etl.templates.batch_manager import BatchManager  # type: ignore

        cur = _DummyCursor()
        conn = _DummyConn(cur)

        with BatchManager(conn, "Test Batch", "regulations", species_id=1) as batch:
            batch.add_records(1)
            batch.commit()

        # Expected commits:
        # - _create_batch() commits once
        # - _complete_batch() commits once (explicit commit())
        # - __exit__ should NOT commit again
        assert conn.commits == 2

        completed_updates = [
            q for q, _params in cur.executed
            if "UPDATE import_batches" in q and "status = 'completed'" in q
        ]
        assert len(completed_updates) == 1
    finally:
        try:
            sys.path.remove(str(repo_root))
        except ValueError:
            pass

