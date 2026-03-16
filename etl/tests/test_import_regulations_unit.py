from __future__ import annotations

import csv
from pathlib import Path


class _DummyConn:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _write_minimal_regulations_tsv(file_path: Path) -> None:
    with file_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Species", "LncRNA_ID", "Target_Gene_ID"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerow(
            {
                "Species": "chimp",
                "LncRNA_ID": "ENSG000001",
                "Target_Gene_ID": "ENSG000002",
            }
        )


def test_import_regulations_preserves_species_id_when_all_rows_are_skipped(
    tmp_path: Path,
) -> None:
    from etl.import_regulations import RegulationsImporter

    data_file = tmp_path / "chimp.tsv"
    _write_minimal_regulations_tsv(data_file)

    importer = RegulationsImporter({})
    importer.conn = _DummyConn()

    created_batches: list[tuple[str, int, str]] = []
    updated_batches: list[tuple[int, str, int]] = []

    importer._validate_columns = lambda _file_path: None
    importer._check_required_index = lambda: None
    importer._load_species_map = lambda: setattr(importer, "species_map", {"chimp": 2})
    importer._load_gene_cache = lambda species_id: importer._loaded_species.add(species_id)
    importer._get_gene_id = lambda species_id, gene_id: None
    importer._set_batch_error = lambda batch_id, error_msg: None

    def _create_batch(batch_name: str, species_id: int, file_path: str) -> int:
        created_batches.append((batch_name, species_id, file_path))
        return 101

    def _update_batch(batch_id: int, status: str, record_count: int) -> None:
        updated_batches.append((batch_id, status, record_count))

    importer._create_batch = _create_batch
    importer._update_batch = _update_batch

    importer.import_file(
        file_path=str(data_file),
        species_code="chimp",
        dry_run=False,
    )

    assert created_batches == [
        ("Regulations Import chimp", 2, str(data_file)),
    ]
    assert updated_batches == [
        (101, "completed", 0),
    ]

