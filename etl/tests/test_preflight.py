from pathlib import Path


def test_list_manifest_paths_resolves_relative_entries(tmp_path: Path) -> None:
    from etl.input_manifest import build_manifest_entries, list_manifest_paths, write_manifest_tsv

    data = tmp_path / "data.tsv"
    data.write_text("a\tb\n1\t2\n", encoding="utf-8")

    manifest = tmp_path / "manifest.tsv"
    entries = build_manifest_entries([data], include_lines=True, include_sha256=True)
    # Force a relative path entry to exercise path resolution logic.
    entries[0]["path"] = "data.tsv"
    write_manifest_tsv(entries, manifest)

    resolved = list_manifest_paths(manifest)
    assert {p.resolve() for p in resolved} == {data.resolve()}


def test_verify_manifest_for_paths_reports_missing_required_file(tmp_path: Path) -> None:
    from etl.input_manifest import build_manifest_entries, write_manifest_tsv
    from etl.preflight import verify_manifest_for_paths

    data1 = tmp_path / "data1.tsv"
    data1.write_text("a\tb\n1\t2\n", encoding="utf-8")
    data2 = tmp_path / "data2.tsv"
    data2.write_text("x\ty\n3\t4\n", encoding="utf-8")

    manifest = tmp_path / "manifest.tsv"
    entries = build_manifest_entries([data1], include_lines=True, include_sha256=True)
    entries[0]["path"] = "data1.tsv"
    write_manifest_tsv(entries, manifest)

    errors = verify_manifest_for_paths(manifest, [data2])
    assert errors
    assert any("required file" in e.lower() for e in errors)


def test_verify_manifest_for_paths_surfaces_sha_mismatch(tmp_path: Path) -> None:
    from etl.input_manifest import build_manifest_entries, write_manifest_tsv
    from etl.preflight import verify_manifest_for_paths

    data = tmp_path / "data.tsv"
    data.write_text("a\tb\n1\t2\n", encoding="utf-8")

    manifest = tmp_path / "manifest.tsv"
    entries = build_manifest_entries([data], include_lines=True, include_sha256=True)
    entries[0]["path"] = "data.tsv"
    write_manifest_tsv(entries, manifest)

    # Modify file after manifest is created.
    data.write_text("a\tb\n1\t2\n3\t4\n", encoding="utf-8")

    errors = verify_manifest_for_paths(manifest, [data])
    assert errors
    assert any("sha256" in e.lower() for e in errors)


def test_verify_file_checks_for_paths_min_bytes(tmp_path: Path) -> None:
    from etl.preflight import verify_file_checks_for_paths

    data = tmp_path / "data.tsv"
    data.write_text("a\tb\n1\t2\n", encoding="utf-8")

    errors = verify_file_checks_for_paths([data], min_bytes=1000)
    assert errors
    assert any("min_bytes" in e.lower() for e in errors)


def test_verify_file_checks_for_paths_sha256_mismatch(tmp_path: Path) -> None:
    from etl.preflight import verify_file_checks_for_paths

    data = tmp_path / "data.tsv"
    data.write_text("a\tb\n1\t2\n", encoding="utf-8")

    errors = verify_file_checks_for_paths([data], expected_sha256=["deadbeef"])
    assert errors
    assert any("sha256 mismatch" in e.lower() for e in errors)
