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
import psycopg2
from psycopg2.extras import execute_values

def parse_args():
    parser = argparse.ArgumentParser(description='Import UCSC RepeatMasker data')
    parser.add_argument('input_file', help='Path to rmsk.txt file')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of rows (0=all)')
    parser.add_argument('--batch-size', type=int, default=10000, help='Batch size for inserts')
    parser.add_argument('--species', default='human', help='Species code')
    parser.add_argument('--db', default='lncrna_production', help='Database name')
    parser.add_argument('--user', default='amax', help='Database user')
    parser.add_argument('--host', default='localhost', help='Database host')
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

def update_batch(conn, batch_id, status, record_count=None):
    """Update batch status"""
    with conn.cursor() as cur:
        if status == 'completed':
            cur.execute("""
                UPDATE import_batches
                SET status = %s, record_count = %s, completed_at = %s
                WHERE batch_id = %s
            """, (status, record_count, datetime.now(), batch_id))
        else:
            cur.execute("""
                UPDATE import_batches SET status = %s WHERE batch_id = %s
            """, (status, batch_id))
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

def import_data(conn, input_file, species_id, track_id, batch_id, batch_size=10000, limit=0):
    """Import RepeatMasker data"""

    insert_sql = """
        INSERT INTO genomic_features
        (track_id, species_id, chromosome, feature_start, feature_end,
         feature_name, strand, score, attributes, batch_id)
        VALUES %s
    """

    total_imported = 0
    batch_data = []

    print(f"Reading {input_file}...")

    with open(input_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            if limit > 0 and line_num > limit:
                break

            record = parse_rmsk_line(line)
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
                # JSONB attributes
                f'{{"repeat_class": "{record["repeat_class"]}", "repeat_family": "{record["repeat_family"]}", "divergence": {record["divergence"]}}}',
                batch_id
            )
            batch_data.append(row)

            # Batch insert
            if len(batch_data) >= batch_size:
                with conn.cursor() as cur:
                    execute_values(cur, insert_sql, batch_data, page_size=batch_size)
                conn.commit()
                total_imported += len(batch_data)
                print(f"  Imported {total_imported:,} records...", end='\r')
                batch_data = []

    # Insert remaining
    if batch_data:
        with conn.cursor() as cur:
            execute_values(cur, insert_sql, batch_data, page_size=batch_size)
        conn.commit()
        total_imported += len(batch_data)

    print(f"\n  Total imported: {total_imported:,} records")
    return total_imported

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

    # Connect to database
    conn = psycopg2.connect(
        dbname=args.db,
        user=args.user,
        host=args.host
    )

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
        total = import_data(conn, args.input_file, species_id, track_id, batch_id,
                           args.batch_size, args.limit)
        elapsed = (datetime.now() - start_time).total_seconds()

        # Update batch status
        update_batch(conn, batch_id, 'completed', total)

        print()
        print("=" * 60)
        print("Import completed successfully!")
        print(f"  Records: {total:,}")
        print(f"  Time: {elapsed:.1f} seconds")
        print(f"  Speed: {total/elapsed:,.0f} records/second")
        print("=" * 60)

    except Exception as e:
        print(f"\n ERROR: {e}")
        if 'batch_id' in locals():
            update_batch(conn, batch_id, 'failed')
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    main()
