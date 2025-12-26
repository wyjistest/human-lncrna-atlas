import pytest


class _DummyCursor:
    def __init__(self, *, fetchone_results=None):
        self._fetchone_results = list(fetchone_results or [])
        self.executed: list[tuple[str, object]] = []

    def execute(self, query, params=None):
        # Normalize whitespace for easier assertions
        normalized = " ".join(str(query).split())
        self.executed.append((normalized, params))

    def fetchone(self):
        if not self._fetchone_results:
            return None
        return self._fetchone_results.pop(0)

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyConn:
    def __init__(self, cursors: list[_DummyCursor]):
        self._cursors = list(cursors)
        self.commits = 0

    def cursor(self):
        assert self._cursors, "No more cursors configured for this test"
        return self._cursors.pop(0)

    def commit(self):
        self.commits += 1


@pytest.mark.unit
def test_repeatmasker_update_batch_completed_clears_error_message():
    # Import here to avoid polluting global sys.path for other tests
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    try:
        from etl.import_repeatmasker import RepeatMaskerImporter  # type: ignore

        cur = _DummyCursor()
        conn = _DummyConn([cur])
        importer = RepeatMaskerImporter(db_config={})
        importer.conn = conn

        importer._update_batch(batch_id=1, status="completed", record_count=10)

        assert conn.commits == 1
        assert cur.executed, "Expected an UPDATE statement"
        sql_text, _params = cur.executed[0]
        assert "error_message = NULL" in sql_text
    finally:
        # Best-effort cleanup: remove the inserted path entry
        try:
            sys.path.remove(str(repo_root))
        except ValueError:
            pass


@pytest.mark.unit
def test_repeatmasker_resume_batch_returns_existing_record_count_and_resets_status():
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    try:
        from etl.import_repeatmasker import RepeatMaskerImporter  # type: ignore

        file_path = "/tmp/repeats.out"
        # _resume_batch() calls:
        # 1) _get_batch_info() -> cursor.fetchone()
        # 2) UPDATE import_batches ... -> commit
        cur_info = _DummyCursor(
            fetchone_results=[("repeatmasker", 1, file_path, "failed", 123)],
        )
        cur_update = _DummyCursor()
        conn = _DummyConn([cur_info, cur_update])

        importer = RepeatMaskerImporter(db_config={})
        importer.conn = conn

        baseline = importer._resume_batch(batch_id=99, expected_species_id=1, file_path=file_path)

        assert baseline == 123
        assert conn.commits == 1
        assert cur_update.executed, "Expected resume UPDATE statement"
        sql_text, _params = cur_update.executed[0]
        assert "SET status = 'in_progress'" in sql_text
        assert "error_message = NULL" in sql_text
        assert "completed_at = NULL" in sql_text
    finally:
        try:
            sys.path.remove(str(repo_root))
        except ValueError:
            pass

