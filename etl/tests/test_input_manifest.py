from pathlib import Path


def test_build_and_verify_manifest_roundtrip(tmp_path: Path) -> None:
    from etl.input_manifest import build_manifest_entries, verify_manifest_file, write_manifest_tsv

    data = tmp_path / "data.tsv"
    data.write_text("a\tb\n1\t2\n", encoding="utf-8")

    manifest = tmp_path / "manifest.tsv"
    entries = build_manifest_entries([data], include_lines=True, include_sha256=True)
    write_manifest_tsv(entries, manifest)

    errors = verify_manifest_file(manifest)
    assert errors == []


def test_verify_manifest_detects_sha_mismatch(tmp_path: Path) -> None:
    from etl.input_manifest import build_manifest_entries, verify_manifest_file, write_manifest_tsv

    data = tmp_path / "data.tsv"
    data.write_text("a\tb\n1\t2\n", encoding="utf-8")

    manifest = tmp_path / "manifest.tsv"
    entries = build_manifest_entries([data], include_lines=True, include_sha256=True)
    write_manifest_tsv(entries, manifest)

    # Modify file after manifest is created
    data.write_text("a\tb\n1\t2\n3\t4\n", encoding="utf-8")

    errors = verify_manifest_file(manifest)
    assert errors
    assert any("sha256" in e.lower() for e in errors)
