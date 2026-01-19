#!/usr/bin/env python3
"""
ETL E2E smoke verification for the committed sample input.

This script is intended to run in CI after:
1) Initializing schema (schema/v2.3/01_core.sql)
2) Seeding minimal genes required by the sample TSV
3) Running: python3 etl/import_regulations.py --file etl/sample_inputs/human_batch_human.tsv ...

It verifies:
- Record counts (regulations/import_batches/sequences)
- Value-level mapping from sample TSV -> regulations + sequences tables
"""

from __future__ import annotations

import csv
import os
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import psycopg2


SAMPLE_INPUT_PATH = Path(__file__).resolve().parent / "sample_inputs" / "human_batch_human.tsv"


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: str
    dbname: str
    user: str
    password: str


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _load_db_config() -> DbConfig:
    return DbConfig(
        host=_require_env("DB_HOST"),
        port=_require_env("DB_PORT"),
        dbname=_require_env("DB_NAME"),
        user=_require_env("DB_USER"),
        password=_require_env("DB_PASSWORD"),
    )


def _normalize_chr(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def _to_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    return int(text) if text else None


def _to_decimal(value: Optional[str]) -> Optional[Decimal]:
    if value is None:
        return None
    text = str(value).strip()
    return Decimal(text) if text else None


def _decimal_equal(actual: Any, expected: Any) -> bool:
    if actual is None or expected is None:
        return actual is expected
    return Decimal(str(actual)).quantize(Decimal("0.0001")) == Decimal(str(expected)).quantize(Decimal("0.0001"))


def _assert_eq(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise AssertionError(f"{label} mismatch: expected={expected!r}, actual={actual!r}")


def _assert_decimal_eq(label: str, actual: Any, expected: Any) -> None:
    if not _decimal_equal(actual, expected):
        raise AssertionError(f"{label} mismatch: expected={expected!r}, actual={actual!r}")


def _read_sample_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise RuntimeError(f"Sample input not found: {path}")

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if reader.fieldnames is None:
            raise RuntimeError(f"Failed to read TSV header: {path}")
        return [row for row in reader]


def main() -> int:
    config = _load_db_config()
    rows = _read_sample_rows(SAMPLE_INPUT_PATH)

    expected_regulations = len(rows)
    if expected_regulations <= 0:
        raise RuntimeError("Sample input has no rows; nothing to verify")

    conn = psycopg2.connect(
        host=config.host,
        port=config.port,
        dbname=config.dbname,
        user=config.user,
        password=config.password,
    )
    try:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM regulations")
        regulation_count = int(cur.fetchone()[0])
        _assert_eq("regulations count", regulation_count, expected_regulations)

        cur.execute(
            """
            SELECT batch_id, batch_name
            FROM import_batches
            WHERE batch_type = %s
            ORDER BY import_date DESC, batch_id DESC
            """,
            ("regulations",),
        )
        batch_rows = cur.fetchall()
        if not batch_rows:
            raise AssertionError("import_batches missing batch_type='regulations'")

        batch_id: Optional[int] = None
        for bid, bname in batch_rows:
            if bname == "ci-smoke":
                batch_id = int(bid)
                break

        if batch_id is None:
            available = ", ".join(sorted({str(b[1]) for b in batch_rows}))
            raise AssertionError(
                f"Expected import_batches batch_name='ci-smoke' not found. Available: {available}"
            )

        cur.execute("SELECT COUNT(*) FROM sequences")
        sequences_count = int(cur.fetchone()[0])
        _assert_eq("sequences count", sequences_count, expected_regulations)

        # Cache species_id lookup for sample rows
        species_cache: dict[str, int] = {}

        for idx, row in enumerate(rows, 1):
            species_code = row.get("Species", "").strip().lower()
            if not species_code:
                raise AssertionError(f"Row {idx}: missing Species")

            if species_code not in species_cache:
                cur.execute("SELECT species_id FROM species WHERE species_code = %s", (species_code,))
                sp = cur.fetchone()
                if not sp:
                    raise AssertionError(f"Row {idx}: unknown Species '{species_code}' in DB")
                species_cache[species_code] = int(sp[0])

            species_id = species_cache[species_code]

            lncrna_ident = row.get("LncRNA_ID", "").strip()
            target_ident = row.get("Target_Gene_ID", "").strip()
            if not lncrna_ident or not target_ident:
                raise AssertionError(f"Row {idx}: missing LncRNA_ID/Target_Gene_ID")

            cur.execute(
                """
                SELECT gene_id
                FROM genes
                WHERE species_id = %s AND (gene_ensembl_id = %s OR gene_name = %s)
                """,
                (species_id, lncrna_ident, lncrna_ident),
            )
            lncrna_gene = cur.fetchall()
            if len(lncrna_gene) != 1:
                raise AssertionError(
                    f"Row {idx}: expected exactly 1 lncRNA gene match for '{lncrna_ident}', got {len(lncrna_gene)}"
                )
            lncrna_gene_id = int(lncrna_gene[0][0])

            cur.execute(
                """
                SELECT gene_id
                FROM genes
                WHERE species_id = %s AND (gene_ensembl_id = %s OR gene_name = %s)
                """,
                (species_id, target_ident, target_ident),
            )
            target_gene = cur.fetchall()
            if len(target_gene) != 1:
                raise AssertionError(
                    f"Row {idx}: expected exactly 1 target gene match for '{target_ident}', got {len(target_gene)}"
                )
            target_gene_id = int(target_gene[0][0])

            expected_lncrna_start = _to_int(row.get("LncRNA_Start"))
            expected_lncrna_end = _to_int(row.get("LncRNA_End"))
            expected_dna_start = _to_int(row.get("DNA_Start"))
            expected_dna_end = _to_int(row.get("DNA_End"))

            cur.execute(
                """
                SELECT
                  regulation_id,
                  batch_id,
                  target_chromosome,
                  target_start,
                  target_end,
                  best_avg_ba,
                  best_peak_chr,
                  best_peak_start,
                  best_peak_end,
                  best_site_ba,
                  lncrna_start,
                  lncrna_end,
                  dna_start,
                  dna_end,
                  binding_affinity
                FROM regulations
                WHERE species_id = %s
                  AND lncrna_gene_id = %s
                  AND target_gene_id = %s
                  AND lncrna_start IS NOT DISTINCT FROM %s
                  AND lncrna_end IS NOT DISTINCT FROM %s
                  AND dna_start IS NOT DISTINCT FROM %s
                  AND dna_end IS NOT DISTINCT FROM %s
                """,
                (
                    species_id,
                    lncrna_gene_id,
                    target_gene_id,
                    expected_lncrna_start,
                    expected_lncrna_end,
                    expected_dna_start,
                    expected_dna_end,
                ),
            )
            regs = cur.fetchall()
            if len(regs) != 1:
                raise AssertionError(
                    f"Row {idx}: expected exactly 1 regulations row, got {len(regs)} "
                    f"(species={species_code}, lncrna={lncrna_ident}, target={target_ident})"
                )

            (
                regulation_id,
                reg_batch_id,
                target_chr,
                target_start,
                target_end,
                best_avg_ba,
                best_peak_chr,
                best_peak_start,
                best_peak_end,
                best_site_ba,
                lncrna_start,
                lncrna_end,
                dna_start,
                dna_end,
                binding_affinity,
            ) = regs[0]

            _assert_eq(f"row {idx}: batch_id", int(reg_batch_id), batch_id)

            expected_chr = _normalize_chr(row.get("Best_Peak_Chr"))
            _assert_eq(f"row {idx}: target_chromosome", target_chr, expected_chr)
            _assert_eq(f"row {idx}: best_peak_chr", best_peak_chr, expected_chr)

            _assert_eq(f"row {idx}: target_start", target_start, None)
            _assert_eq(f"row {idx}: target_end", target_end, None)

            _assert_eq(f"row {idx}: best_peak_start", int(best_peak_start), _to_int(row.get("Best_Peak_Start")))
            _assert_eq(f"row {idx}: best_peak_end", int(best_peak_end), _to_int(row.get("Best_Peak_End")))

            _assert_decimal_eq(f"row {idx}: best_avg_ba", best_avg_ba, _to_decimal(row.get("Best_Avg_BA")))
            _assert_decimal_eq(f"row {idx}: best_site_ba", best_site_ba, _to_decimal(row.get("Best_Site_BA")))
            _assert_decimal_eq(
                f"row {idx}: binding_affinity", binding_affinity, _to_decimal(row.get("Best_Site_BA"))
            )

            _assert_eq(f"row {idx}: lncrna_start", int(lncrna_start), expected_lncrna_start)
            _assert_eq(f"row {idx}: lncrna_end", int(lncrna_end), expected_lncrna_end)
            _assert_eq(f"row {idx}: dna_start", int(dna_start), expected_dna_start)
            _assert_eq(f"row {idx}: dna_end", int(dna_end), expected_dna_end)

            cur.execute(
                "SELECT lncrna_sequence, dna_sequence FROM sequences WHERE regulation_id = %s",
                (int(regulation_id),),
            )
            seq_rows = cur.fetchall()
            if len(seq_rows) != 1:
                raise AssertionError(f"Row {idx}: expected exactly 1 sequences row, got {len(seq_rows)}")
            lncrna_seq, dna_seq = seq_rows[0]

            expected_lncrna_seq = row.get("LncRNA_Sequence", "").strip() or None
            expected_dna_seq = row.get("DNA_Sequence", "").strip() or None

            _assert_eq(f"row {idx}: lncrna_sequence", lncrna_seq, expected_lncrna_seq)
            _assert_eq(f"row {idx}: dna_sequence", dna_seq, expected_dna_seq)

        print("ETL sample import verification passed")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ETL sample import verification failed: {exc}", file=sys.stderr)
        raise
