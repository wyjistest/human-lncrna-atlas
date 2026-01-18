#!/usr/bin/env python3
"""
Import UCSC RepeatMasker data (rmsk.txt) into lncrna_production database.

UCSC rmsk.txt format (17 columns, tab-separated):
  0: bin         - UCSC bin index (skip)
  1: swScore     - Smith-Waterman score
  2: milliDiv    - Divergence in parts per thousand
  3: milliDel    - Deletions in parts per thousand
  4: milliIns    - Insertions in parts per thousand
  5: genoName    - Chromosome (chr1, chr2, etc.)
  6: genoStart   - Start position (0-based)
  7: genoEnd     - End position
  8: genoLeft    - Bases remaining (skip)
  9: strand      - + or -
 10: repName     - Repeat name (AluSx, L1MC, etc.)
 11: repClass    - Repeat class (SINE, LINE, LTR, DNA, etc.)
 12: repFamily   - Repeat family (Alu, L1, etc.)
 13-16: repStart, repEnd, repLeft, id (skip)

Usage:
    python3 import_ucsc_rmsk.py rmsk.txt [--limit N] [--batch-size N]
"""

import argparse
from datetime import datetime
import logging
import os
import sys
from typing import Optional, Tuple

import psycopg2
from psycopg2.extras import execute_values, Json

try:
    from etl.backend_notify import notify_backend_best_effort
except ImportError:  # pragma: no cover
    try:
        from backend_notify import notify_backend_best_effort  # type: ignore
    except ImportError:  # pragma: no cover
        notify_backend_best_effort = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description='Import UCSC RepeatMasker data')
    parser.add_argument('input_file', help='Path to rmsk.txt file')
    parser.add_argument(
        '--input-manifest',
        help='Optional input manifest TSV (fail-fast verify bytes/lines/sha256 before import)',
    )
    parser.add_argument('--limit', type=int, default=0, help='Limit number of rows (0=all)')
    parser.add_argument('--batch-size', type=int, default=10000, help='Batch size for inserts')
    parser.add_argument('--skip-lines', type=int, default=0, help='Skip first N lines (resume support)')
    parser.add_argument('--species', default='human', help='Species code')
    parser.add_argument('--db', default=os.environ.get('DB_NAME', 'lncrna_production'), help='Database name')
    parser.add_argument('--user', default=os.environ.get('DB_USER', 'amax'), help='Database user')
    parser.add_argument('--host', default=os.environ.get('DB_HOST', 'localhost'), help='Database host')
    parser.add_argument('--port', default=os.environ.get('DB_PORT', '5432'), help='Database port')
    parser.add_argument('--password', default=os.environ.get('DB_PASSWORD', ''), help='Database password (optional)')
    return parser.parse_args()

def get_species_id(conn, species_code):
    """Get species_id from database"""
    with conn.cursor() as cur:
        cur.execute("SELECT species_id FROM species WHERE species_code = %s", (species_code,))
        result = cur.fetchone()
        if not result:
            raise ValueError(f"Species '{species_code}' not found in database")
        return result[0]

def get_track_id(conn):
    """Get RepeatMasker track_id"""
    with conn.cursor() as cur:
        cur.execute("SELECT track_id FROM feature_tracks WHERE track_name = 'repeatmasker_repeats'")
        result = cur.fetchone()
        if not result:
            raise ValueError("RepeatMasker track not found. Run schema_extension_phase2.sql first.")
        return result[0]

def create_batch(conn, species_id, source_file):
    """Create import batch record"""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO import_batches (batch_name, batch_type, species_id, source_file, status, import_date)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING batch_id
        """, (
            f"UCSC RepeatMasker {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            'repeatmasker',
            species_id,
            source_file,
            'in_progress',
            datetime.now()
        ))
        batch_id = cur.fetchone()[0]
        conn.commit()
        return batch_id

def update_batch(conn, batch_id, status, record_count: Optional[int] = None, error_message: Optional[str] = None):
    """Update batch status (best-effort)"""
    with conn.cursor() as cur:
        if status in ('completed', 'failed'):
            cur.execute("""
                UPDATE import_batches
                SET status = %s,
                    record_count = COALESCE(%s, record_count),
                    error_message = COALESCE(%s, error_message),
                    completed_at = %s
                WHERE batch_id = %s
            """, (status, record_count, error_message, datetime.now(), batch_id))
        else:
            cur.execute("""
                UPDATE import_batches
                SET status = %s,
                    record_count = COALESCE(%s, record_count),
                    error_message = COALESCE(%s, error_message)
                WHERE batch_id = %s
            """, (status, record_count, error_message, batch_id))
        conn.commit()

def parse_rmsk_line(line):
    """Parse a single line from rmsk.txt"""
    fields = line.strip().split('\t')
    if len(fields) < 13:
        return None

    return {
        'sw_score': float(fields[1]),
        'divergence': float(fields[2]) / 10.0,  # Convert from milli to percent
        'chromosome': fields[5],
        'start': int(fields[6]),
        'end': int(fields[7]),
        'strand': fields[9],
        'repeat_name': fields[10],
        'repeat_class': fields[11],
        'repeat_family': fields[12]
    }

def import_data(
    conn,
    input_file: str,
    species_id: int,
    track_id: int,
    batch_id: int,
    *,
    batch_size: int = 10000,
    limit: int = 0,
    skip_lines: int = 0,
    progress: Optional[dict] = None,
) -> Tuple[int, int, int]:
    """
    Import RepeatMasker data.

    Returns:
        (total_imported, last_line_num, parse_errors)
    """

    insert_sql = """
        INSERT INTO genomic_features
        (track_id, species_id, chromosome, feature_start, feature_end,
         feature_name, strand, score, attributes, batch_id)
        VALUES %s
    """

    total_imported = 0
    batch_data = []
    parse_errors = 0
    last_line_num = 0

    logger.info(f"Reading {input_file}...")
    if skip_lines > 0:
        logger.info(f"Resume mode: skipping first {skip_lines:,} lines")

    with open(input_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            last_line_num = line_num
            if progress is not None:
                progress["last_line_num"] = last_line_num
            if skip_lines > 0 and line_num <= skip_lines:
                continue
            if limit > 0 and line_num > limit:
                break

            try:
                record = parse_rmsk_line(line)
            except (ValueError, TypeError):
                parse_errors += 1
                if progress is not None:
                    progress["parse_errors"] = parse_errors
                # Avoid spamming logs for huge files
                if parse_errors <= 10:
                    logger.warning(f"Parse failed at line {line_num}: {line[:120].rstrip()!r}")
                continue
            if not record:
                continue

            # Prepare tuple for batch insert
            row = (
                track_id,
                species_id,
                record['chromosome'],
                record['start'],
                record['end'],
                record['repeat_name'],
                record['strand'],
                record['sw_score'],
                # JSONB attributes - use Json adapter for correct escaping and typing
                Json({
                    "repeat_class": record["repeat_class"],
                    "repeat_family": record["repeat_family"],
                    "divergence": record["divergence"]
                }),
                batch_id
            )
            batch_data.append(row)

            # Batch insert
            if len(batch_data) >= batch_size:
                with conn.cursor() as cur:
                    execute_values(cur, insert_sql, batch_data, page_size=batch_size)
                conn.commit()
                total_imported += len(batch_data)
                if progress is not None:
                    progress["total_imported"] = total_imported
                logger.info(f"Imported {total_imported:,} records (line {line_num:,})")
                batch_data = []

    # Insert remaining
    if batch_data:
        with conn.cursor() as cur:
            execute_values(cur, insert_sql, batch_data, page_size=batch_size)
        conn.commit()
        total_imported += len(batch_data)
        if progress is not None:
            progress["total_imported"] = total_imported

    logger.info(f"Total imported: {total_imported:,} records (parse_errors={parse_errors:,})")
    return total_imported, last_line_num, parse_errors

def main():
    args = parse_args()

    print("=" * 60)
    print("UCSC RepeatMasker Import")
    print("=" * 60)
    print(f"Input file: {args.input_file}")
    print(f"Species: {args.species}")
    print(f"Batch size: {args.batch_size:,}")
    if args.limit > 0:
        print(f"Limit: {args.limit:,} rows")
    print()

    if args.input_manifest:
        try:
            from etl.preflight import verify_manifest_for_paths
        except ImportError:  # pragma: no cover
            from preflight import verify_manifest_for_paths  # type: ignore

        errors = verify_manifest_for_paths(args.input_manifest, [args.input_file])
        if errors:
            for e in errors:
                print(e, file=sys.stderr)
            sys.exit(1)

    # Verify input file exists
    if not os.path.exists(args.input_file):
        print(f"\n ERROR: File not found: {args.input_file}")
        sys.exit(1)

    # Connect to database
    db_config = {
        "dbname": args.db,
        "user": args.user,
        "host": args.host,
        "port": int(args.port),
    }
    # If password is empty, omit it to allow .pgpass / trust auth
    if args.password:
        db_config["password"] = args.password
    conn = psycopg2.connect(**db_config)

    try:
        # Get IDs
        species_id = get_species_id(conn, args.species)
        track_id = get_track_id(conn)
        print(f"Species ID: {species_id}, Track ID: {track_id}")

        # Create batch
        batch_id = create_batch(conn, species_id, args.input_file)
        print(f"Created batch: {batch_id}")

        # Import data
        start_time = datetime.now()
        progress = {"total_imported": 0, "last_line_num": 0, "parse_errors": 0}
        total, last_line_num, parse_errors = import_data(
            conn,
            args.input_file,
            species_id,
            track_id,
            batch_id,
            batch_size=args.batch_size,
            limit=args.limit,
            skip_lines=args.skip_lines,
            progress=progress,
        )
        elapsed = (datetime.now() - start_time).total_seconds()

        # Update batch status
        update_batch(conn, batch_id, 'completed', total)

        # 可选：通知后端失效缓存 / 重置 MV 可用性缓存（best-effort）
        if notify_backend_best_effort is not None:
            notify_backend_best_effort(reason="etl/import_ucsc_rmsk")

        print()
        print("=" * 60)
        print("Import completed successfully!")
        print(f"  Records: {total:,}")
        print(f"  Parse errors: {parse_errors:,}")
        print(f"  Time: {elapsed:.1f} seconds")
        print(f"  Speed: {total/elapsed:,.0f} records/second")
        print("=" * 60)

    except Exception as e:
        print(f"\n ERROR: {e}")
        # Ensure the connection is not in aborted state before updating batch metadata
        try:
            conn.rollback()
        except Exception:
            pass

        if 'batch_id' in locals():
            # Best-effort: record partial progress and a resume hint
            imported = progress.get("total_imported", 0) if "progress" in locals() else 0
            last_line_num = progress.get("last_line_num", 0) if "progress" in locals() else 0
            resume_hint = (
                f"PARTIAL_IMPORT: {imported} records committed before error. "
                f"Resume: python3 import_ucsc_rmsk.py {args.input_file} "
                f"--species {args.species} --skip-lines={max(last_line_num - 1, 0)}"
            )
            try:
                update_batch(conn, batch_id, 'failed', record_count=imported, error_message=resume_hint)
            except Exception as update_err:
                logger.warning(f"Failed to update batch status after error: {update_err}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    main()
