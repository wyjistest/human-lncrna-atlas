import gzip
import hashlib
from pathlib import Path

import pytest


def test_sha256_hex_file_matches_known_digest(tmp_path: Path) -> None:
    from etl.file_checks import sha256_hex_file

    path = tmp_path / "input.txt"
    path.write_text("hello\n", encoding="utf-8")

    expected = hashlib.sha256(b"hello\n").hexdigest()
    assert sha256_hex_file(path) == expected


def test_count_lines_supports_plain_and_gz(tmp_path: Path) -> None:
    from etl.file_checks import count_lines

    plain = tmp_path / "plain.txt"
    plain.write_text("a\nb\nc\n", encoding="utf-8")

    gz = tmp_path / "plain.txt.gz"
    with gzip.open(gz, "wt", encoding="utf-8") as f:
        f.write("a\nb\nc\n")

    assert count_lines(plain) == 3
    assert count_lines(gz) == 3


def test_validate_file_rejects_sha256_mismatch(tmp_path: Path) -> None:
    from etl.file_checks import validate_file

    path = tmp_path / "input.tsv"
    path.write_text("col1\tcol2\n1\t2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="SHA256"):
        validate_file(path, expected_sha256="0" * 64)


def test_validate_file_enforces_min_bytes_and_line_range(tmp_path: Path) -> None:
    from etl.file_checks import validate_file

    path = tmp_path / "small.txt"
    path.write_text("x\ny\n", encoding="utf-8")

    with pytest.raises(ValueError, match="min_bytes"):
        validate_file(path, min_bytes=10_000)

    with pytest.raises(ValueError, match="min_lines"):
        validate_file(path, min_lines=10)

    with pytest.raises(ValueError, match="max_lines"):
        validate_file(path, max_lines=1)

