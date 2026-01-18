from pathlib import Path


def test_sample_inputs_manifest_is_valid() -> None:
    from etl.input_manifest import verify_manifest_file

    repo_root = Path(__file__).resolve().parents[2]
    manifest = repo_root / "etl/sample_inputs/etl-inputs.manifest.tsv"

    errors = verify_manifest_file(manifest)
    assert errors == []

