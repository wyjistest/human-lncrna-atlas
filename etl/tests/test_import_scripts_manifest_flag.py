from __future__ import annotations

from pathlib import Path

import pytest


def _write_manifest(tmp_path: Path, file_path: Path, *, rel_name: str) -> Path:
    from etl.input_manifest import build_manifest_entries, write_manifest_tsv

    entries = build_manifest_entries([file_path], include_lines=True, include_sha256=True)
    entries[0]["path"] = rel_name
    manifest = tmp_path / "manifest.tsv"
    write_manifest_tsv(entries, manifest)
    return manifest


def test_import_regulations_supports_input_manifest_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import etl.import_regulations as mod

    monkeypatch.delenv("DB_USER", raising=False)

    data = tmp_path / "data.tsv"
    data.write_text("a\tb\n1\t2\n", encoding="utf-8")
    manifest = _write_manifest(tmp_path, data, rel_name="data.tsv")

    # Introduce mismatch after manifest is created.
    data.write_text("a\tb\n1\t2\n3\t4\n", encoding="utf-8")

    monkeypatch.setattr(
        mod.sys,
        "argv",
        ["import_regulations.py", "--file", str(data), "--input-manifest", str(manifest)],
    )

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "sha256" in (captured.err + captured.out).lower()


def test_import_sequences_supports_input_manifest_without_data_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import etl.import_sequences as mod

    monkeypatch.delenv("LNCRNA_DATA_PATH", raising=False)
    monkeypatch.delenv("DB_USER", raising=False)

    data = tmp_path / "human_batch_human.txt"
    data.write_text("a\tb\n1\t2\n", encoding="utf-8")
    manifest = _write_manifest(tmp_path, data, rel_name="human_batch_human.txt")
    data.write_text("a\tb\n1\t2\n3\t4\n", encoding="utf-8")

    monkeypatch.setattr(
        mod.sys,
        "argv",
        [
            "import_sequences.py",
            "--species",
            "1",
            "--file",
            str(data),
            "--input-manifest",
            str(manifest),
            "--dry-run",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "sha256" in (captured.err + captured.out).lower()


def test_import_ortholog_data_supports_input_manifest_multi_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import etl.import_ortholog_data as mod

    monkeypatch.delenv("DB_USER", raising=False)

    lncrna = tmp_path / "lnc.csv"
    lncrna.write_text("a,b\n1,2\n", encoding="utf-8")
    gene = tmp_path / "gene.csv"
    gene.write_text("a,b\n3,4\n", encoding="utf-8")

    # Manifest includes only one file; required file check should fail.
    manifest = _write_manifest(tmp_path, lncrna, rel_name="lnc.csv")

    monkeypatch.setattr(
        mod.sys,
        "argv",
        [
            "import_ortholog_data.py",
            "--lncrna-file",
            str(lncrna),
            "--gene-file",
            str(gene),
            "--input-manifest",
            str(manifest),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "required file" in (captured.err + captured.out).lower()

