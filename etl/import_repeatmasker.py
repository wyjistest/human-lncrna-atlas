#!/usr/bin/env python3
"""
RepeatMasker Data Import Script
================================

Imports RepeatMasker annotations into the genomic_features table.

Supported Input Formats:
1. RepeatMasker .out format (standard output)
2. BED format with extra columns for repeat info
3. TSV format with headers

Usage:
    python3 import_repeatmasker.py --species human --file /path/to/hg19.fa.out
    python3 import_repeatmasker.py --species human --file /path/to/repeats.bed --format bed
    python3 import_repeatmasker.py --species chimp --file /path/to/repeats.tsv --format tsv

Version: 1.0
Date: 2025-12-04
"""

import sys
import os
import argparse
import logging
from typing import Dict, List, Optional, Generator, Tuple
from datetime import datetime

import psycopg2
from psycopg2.extras import execute_values

try:
    from etl.backend_notify import notify_backend_best_effort
except ImportError:  # pragma: no cover
    try:
        from backend_notify import notify_backend_best_effort  # type: ignore
    except ImportError:  # pragma: no cover
        notify_backend_best_effort = None

try:
    from etl.db_config import get_db_config_from_env, finalize_db_config
except ImportError:  # pragma: no cover
    from db_config import get_db_config_from_env, finalize_db_config  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RepeatMaskerImporter:
    """Import RepeatMasker data into genomic_features table"""

    # Species code to ID mapping
    SPECIES_MAP = {
        'human': 1,
        'chimp': 2,
        'macaque': 3,
        'marmoset': 4,
    }

    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.conn = None
        self.track_id = None
        self.stats = {
            'total_lines': 0,
            'imported': 0,
            'skipped': 0,
            'errors': [],
        }

    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            logger.info(f"Connected to database: {self.db_config['dbname']}")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def _get_track_id(self) -> int:
        """Get the track_id for RepeatMasker"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT track_id FROM feature_tracks
            WHERE track_name = 'repeatmasker_repeats'
        """)
        result = cursor.fetchone()
        cursor.close()

        if not result:
            raise ValueError(
                "RepeatMasker track not found. Please run schema_extension_phase2.sql first."
            )
        return result[0]

    def _get_species_id(self, species_code: str) -> int:
        """Get species_id from species code"""
        if species_code.lower() not in self.SPECIES_MAP:
            raise ValueError(f"Unknown species code: {species_code}")
        return self.SPECIES_MAP[species_code.lower()]

    def _create_batch(self, batch_name: str, species_id: int, file_path: str) -> int:
        """Create an import batch record"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO import_batches (batch_name, batch_type, species_id, source_file, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING batch_id
        """, (batch_name, 'repeatmasker', species_id, file_path, 'in_progress'))

        batch_id = cursor.fetchone()[0]
        self.conn.commit()
        cursor.close()

        logger.info(f"Created batch: {batch_name} (batch_id={batch_id})")
        return batch_id

    def _get_batch_info(self, batch_id: int) -> Optional[Tuple[str, int, Optional[str], str, Optional[int]]]:
        """
        获取批次信息，用于断点续传/安全校验

        Returns:
            (batch_type, species_id, source_file, status, record_count) 或 None
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT batch_type, species_id, source_file, status, record_count
            FROM import_batches
            WHERE batch_id = %s
            """,
            (batch_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return None
        return row[0], row[1], row[2], row[3], row[4]

    def _resume_batch(self, batch_id: int, *, expected_species_id: int, file_path: str) -> int:
        """
        断点续传：复用已有 batch_id，重置状态为 in_progress

        注意：
        - 仅支持 repeatmasker 批次类型
        - species_id 必须匹配，避免误写入
        """
        info = self._get_batch_info(batch_id)
        if info is None:
            raise ValueError(f"Resume batch_id not found: {batch_id}")

        batch_type, species_id, source_file, status, record_count = info
        if batch_type != "repeatmasker":
            raise ValueError(
                f"Resume batch_id={batch_id} type mismatch: {batch_type!r} (expected 'repeatmasker')"
            )
        if int(species_id) != int(expected_species_id):
            raise ValueError(
                f"Resume batch_id={batch_id} species mismatch: {species_id} (expected {expected_species_id})"
            )
        if source_file and os.path.abspath(source_file) != os.path.abspath(file_path):
            logger.warning(
                f"Resume batch_id={batch_id} source_file differs:\n"
                f"  batch.source_file={source_file}\n"
                f"  --file={file_path}\n"
                f"Continuing anyway (ensure you are resuming the same dataset)."
            )

        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE import_batches
            SET status = 'in_progress',
                error_message = NULL,
                completed_at = NULL
            WHERE batch_id = %s
            """,
            (batch_id,),
        )
        self.conn.commit()
        cursor.close()

        logger.info(
            f"Resuming existing batch_id={batch_id} "
            f"(previous status={status!r}, record_count={record_count})"
        )
        return int(record_count or 0)

    def _update_batch(self, batch_id: int, status: str, record_count: int):
        """Update batch status"""
        cursor = self.conn.cursor()
        if status == "completed":
            cursor.execute(
                """
                UPDATE import_batches
                SET status = %s,
                    record_count = %s,
                    error_message = NULL,
                    completed_at = CURRENT_TIMESTAMP
                WHERE batch_id = %s
                """,
                (status, record_count, batch_id),
            )
        else:
            cursor.execute(
                """
                UPDATE import_batches
                SET status = %s, record_count = %s, completed_at = CURRENT_TIMESTAMP
                WHERE batch_id = %s
                """,
                (status, record_count, batch_id),
            )
        self.conn.commit()
        cursor.close()

    def _set_error_message(self, batch_id: int, message: Optional[str]):
        """Set error message for a batch"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE import_batches
            SET error_message = %s
            WHERE batch_id = %s
        """, (message, batch_id))
        self.conn.commit()
        cursor.close()

    def _parse_repeatmasker_out(self, file_path: str) -> Generator[Dict, None, None]:
        """
        Parse RepeatMasker .out format

        Format (space-delimited, variable whitespace):
        SW score | perc div | perc del | perc ins | query seq | begin | end | (left) | + | repeat | class/family | begin | end | (left) | ID
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            # Skip header lines
            for i, line in enumerate(f):
                line = line.strip()

                # Skip empty lines and header lines
                if not line or line.startswith('SW') or line.startswith('score'):
                    continue

                # Skip lines that look like headers
                if 'perc' in line.lower() or 'query' in line.lower():
                    continue

                try:
                    # Split by whitespace
                    parts = line.split()

                    # RepeatMasker .out format has at least 15 columns
                    if len(parts) < 11:
                        continue

                    # Parse fields
                    # Column indices (0-based):
                    # 0: SW score
                    # 1: perc div
                    # 2: perc del
                    # 3: perc ins
                    # 4: query sequence (chromosome)
                    # 5: begin in query
                    # 6: end in query
                    # 7: (left) in query
                    # 8: strand (+ or C)
                    # 9: repeat name/class
                    # 10: class/family

                    score = float(parts[0]) if parts[0].replace('.', '').isdigit() else 0
                    divergence = float(parts[1]) if parts[1].replace('.', '').isdigit() else 0

                    chromosome = parts[4]
                    # Add 'chr' prefix if not present
                    if not chromosome.startswith('chr'):
                        chromosome = 'chr' + chromosome

                    start = int(parts[5]) - 1  # Convert to 0-based
                    end = int(parts[6])

                    strand = '+' if parts[8] == '+' else '-'

                    repeat_name = parts[9]

                    # Parse class/family (format: "class/family" or just "class")
                    class_family = parts[10] if len(parts) > 10 else "Unknown/Unknown"
                    if '/' in class_family:
                        repeat_class, repeat_family = class_family.split('/', 1)
                    else:
                        repeat_class = class_family
                        repeat_family = class_family

                    yield {
                        'chromosome': chromosome,
                        'feature_start': start,
                        'feature_end': end,
                        'feature_name': repeat_name,
                        'strand': strand,
                        'score': score,
                        'repeat_class': repeat_class,
                        'repeat_family': repeat_family,
                        'divergence': divergence,
                    }

                except (ValueError, IndexError) as e:
                    if len(self.stats['errors']) < 100:
                        self.stats['errors'].append(f"Line {i+1}: {e}")
                    self.stats['skipped'] += 1

    def _parse_bed_format(self, file_path: str) -> Generator[Dict, None, None]:
        """
        Parse BED format with optional extra columns

        Expected format:
        chr  start  end  name  score  strand  [repeat_class  repeat_family  divergence]

        Or minimal:
        chr  start  end  name  score  strand  repeat_class/family  divergence
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                try:
                    parts = line.split('\t')

                    if len(parts) < 6:
                        self.stats['skipped'] += 1
                        continue

                    chromosome = parts[0]
                    start = int(parts[1])
                    end = int(parts[2])
                    repeat_name = parts[3]
                    score = float(parts[4]) if parts[4] and parts[4] != '.' else 0
                    strand = parts[5] if parts[5] in ('+', '-', '.') else '.'

                    # Parse repeat class/family from additional columns
                    repeat_class = "Unknown"
                    repeat_family = "Unknown"
                    divergence = 0.0

                    if len(parts) >= 9:
                        # Full format: chr start end name score strand class family divergence
                        repeat_class = parts[6]
                        repeat_family = parts[7]
                        divergence = float(parts[8]) if parts[8] and parts[8] != '.' else 0.0
                    elif len(parts) >= 8:
                        # Compact format: chr start end name score strand class/family divergence
                        class_family = parts[6]
                        if '/' in class_family:
                            repeat_class, repeat_family = class_family.split('/', 1)
                        else:
                            repeat_class = class_family
                            repeat_family = class_family
                        divergence = float(parts[7]) if parts[7] and parts[7] != '.' else 0.0
                    elif len(parts) >= 7:
                        # Minimal extra: chr start end name score strand class/family
                        class_family = parts[6]
                        if '/' in class_family:
                            repeat_class, repeat_family = class_family.split('/', 1)
                        else:
                            repeat_class = class_family
                            repeat_family = class_family

                    yield {
                        'chromosome': chromosome,
                        'feature_start': start,
                        'feature_end': end,
                        'feature_name': repeat_name,
                        'strand': strand,
                        'score': score,
                        'repeat_class': repeat_class,
                        'repeat_family': repeat_family,
                        'divergence': divergence,
                    }

                except (ValueError, IndexError) as e:
                    if len(self.stats['errors']) < 100:
                        self.stats['errors'].append(f"Line {i+1}: {e}")
                    self.stats['skipped'] += 1

    def _parse_tsv_format(self, file_path: str) -> Generator[Dict, None, None]:
        """
        Parse TSV format with headers

        Expected headers:
        chromosome, start/feature_start, end/feature_end, name/repeat_name,
        score, strand, repeat_class/class, repeat_family/family, divergence
        """
        import csv

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')

            for i, row in enumerate(reader):
                try:
                    # Flexible column name matching
                    chromosome = row.get('chromosome') or row.get('chr') or row.get('chrom')
                    start = row.get('start') or row.get('feature_start') or row.get('chromStart')
                    end = row.get('end') or row.get('feature_end') or row.get('chromEnd')
                    name = row.get('name') or row.get('repeat_name') or row.get('feature_name')
                    score = row.get('score', '0')
                    strand = row.get('strand', '.')
                    repeat_class = row.get('repeat_class') or row.get('class') or row.get('repClass', 'Unknown')
                    repeat_family = row.get('repeat_family') or row.get('family') or row.get('repFamily', 'Unknown')
                    divergence = row.get('divergence') or row.get('div') or row.get('milliDiv', '0')

                    if not all([chromosome, start, end]):
                        self.stats['skipped'] += 1
                        continue

                    # Convert milliDiv (per mille) to percent if needed
                    div_value = float(divergence) if divergence else 0
                    if div_value > 100:  # Likely milliDiv
                        div_value = div_value / 10

                    yield {
                        'chromosome': chromosome,
                        'feature_start': int(start),
                        'feature_end': int(end),
                        'feature_name': name or 'repeat',
                        'strand': strand if strand in ('+', '-', '.') else '.',
                        'score': float(score) if score and score != '.' else 0,
                        'repeat_class': repeat_class,
                        'repeat_family': repeat_family,
                        'divergence': div_value,
                    }

                except (ValueError, KeyError) as e:
                    if len(self.stats['errors']) < 100:
                        self.stats['errors'].append(f"Row {i+1}: {e}")
                    self.stats['skipped'] += 1

    def _batch_insert(self, features: List[Dict], species_id: int, batch_id: int):
        """Batch insert features"""
        if not features:
            return 0

        cursor = self.conn.cursor()

        # Prepare values
        values = []
        for f in features:
            values.append((
                self.track_id,
                species_id,
                f['chromosome'],
                f['feature_start'],
                f['feature_end'],
                f['feature_name'],
                f['strand'],
                f['score'],
                psycopg2.extras.Json({
                    'repeat_class': f['repeat_class'],
                    'repeat_family': f['repeat_family'],
                    'divergence': f['divergence'],
                }),
                batch_id,
            ))

        # Bulk insert
        execute_values(cursor, """
            INSERT INTO genomic_features (
                track_id, species_id, chromosome, feature_start, feature_end,
                feature_name, strand, score, attributes, batch_id
            ) VALUES %s
        """, values)

        self.stats['imported'] += len(features)
        cursor.close()
        return len(features)

    def import_file(
        self,
        file_path: str,
        species_code: str,
        file_format: str = 'out',
        batch_name: Optional[str] = None,
        batch_size: int = 5000,
        commit_every: int = 10,
        dry_run: bool = False,
        chromosome_filter: Optional[str] = None,
        skip_records: int = 0,
        resume_batch_id: Optional[int] = None,
    ):
        """
        Import RepeatMasker data from file

        Args:
            file_path: Path to input file
            species_code: Species code (human, chimp, macaque, marmoset)
            file_format: Input format (out, bed, tsv)
            batch_name: Optional batch name
            batch_size: Number of records per batch insert
            commit_every: Commit transaction after every N batch inserts (default: 10)
                          Set to 0 to commit only at the end (old behavior, not recommended)
            dry_run: If True, don't actually insert data
            chromosome_filter: Optional chromosome filter (e.g., 'chr1')
        """
        logger.info("Starting RepeatMasker import")
        logger.info(f"  File: {file_path}")
        logger.info(f"  Species: {species_code}")
        logger.info(f"  Format: {file_format}")
        logger.info(f"  Dry run: {dry_run}")
        if skip_records:
            logger.info(f"  Skip records: {skip_records:,}")
        if resume_batch_id:
            logger.info(f"  Resume batch_id: {resume_batch_id}")

        # Get track_id
        self.track_id = self._get_track_id()
        logger.info(f"  Track ID: {self.track_id}")

        # Get species_id
        species_id = self._get_species_id(species_code)
        logger.info(f"  Species ID: {species_id}")

        # Create batch
        batch_id = None
        baseline_imported = 0
        if resume_batch_id and dry_run:
            logger.warning("--resume-batch-id is ignored in --dry-run mode")
            resume_batch_id = None
        if resume_batch_id and batch_name:
            logger.warning("--batch-name is ignored when --resume-batch-id is set")
        if not dry_run:
            if resume_batch_id:
                batch_id = int(resume_batch_id)
                baseline_imported = self._resume_batch(batch_id, expected_species_id=species_id, file_path=file_path)
            else:
                if not batch_name:
                    batch_name = f"RepeatMasker {species_code} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                batch_id = self._create_batch(batch_name, species_id, file_path)

        # Select parser based on format
        if file_format.lower() == 'out':
            parser = self._parse_repeatmasker_out(file_path)
        elif file_format.lower() == 'bed':
            parser = self._parse_bed_format(file_path)
        elif file_format.lower() == 'tsv':
            parser = self._parse_tsv_format(file_path)
        else:
            raise ValueError(f"Unknown file format: {file_format}")

        # Process records
        features = []
        batch_insert_count = 0  # Track batch inserts for periodic commits
        processed_records = 0
        last_committed_processed_records = max(skip_records, 0) if resume_batch_id else 0
        pending_imported = 0
        committed_imported = baseline_imported
        if baseline_imported:
            # Resume into the same batch_id: keep counters consistent with already-committed rows
            self.stats['imported'] = baseline_imported
        try:
            for record in parser:
                processed_records += 1
                self.stats['total_lines'] = processed_records

                # Resume support: skip first N parsed records (counts parsed records, not raw file lines)
                if skip_records > 0 and processed_records <= skip_records:
                    continue

                # Apply chromosome filter
                if chromosome_filter and record['chromosome'] != chromosome_filter:
                    continue

                features.append(record)

                # Batch insert
                if len(features) >= batch_size:
                    if not dry_run:
                        inserted = self._batch_insert(features, species_id, batch_id)
                        pending_imported += inserted
                        batch_insert_count += 1

                        # Periodic commit to avoid large transaction / WAL pressure
                        if commit_every > 0 and batch_insert_count % commit_every == 0:
                            self.conn.commit()
                            committed_imported += pending_imported
                            pending_imported = 0
                            last_committed_processed_records = processed_records
                            logger.info(f"Committed {self.stats['imported']:,} records "
                                      f"({batch_insert_count} batches)")
                    else:
                        self.stats['imported'] += len(features)
                    features = []

                    # Progress update
                    if self.stats['total_lines'] % 100000 == 0:
                        logger.info(f"Processed {self.stats['total_lines']:,} lines, "
                                  f"imported {self.stats['imported']:,}")

            # Insert remaining records
            if features:
                if not dry_run:
                    inserted = self._batch_insert(features, species_id, batch_id)
                    pending_imported += inserted
                else:
                    self.stats['imported'] += len(features)

            # Final commit for any uncommitted data
            if not dry_run:
                self.conn.commit()
                committed_imported += pending_imported
                pending_imported = 0
                last_committed_processed_records = processed_records
                self.stats['imported'] = committed_imported
                self._update_batch(batch_id, 'completed', self.stats['imported'])

            logger.info("Import completed successfully!")

        except Exception as e:
            logger.error(f"Import failed: {e}")
            if not dry_run:
                self.conn.rollback()  # Only rolls back uncommitted batches
                # Ensure stats reflect committed state (uncommitted inserts were rolled back)
                self.stats['imported'] = committed_imported
                if batch_id:
                    if committed_imported > 0:
                        logger.warning(
                            f"Partial data committed before failure: {committed_imported:,} records. "
                            f"To cleanup: DELETE FROM genomic_features WHERE batch_id = {batch_id}"
                        )
                    self._update_batch(batch_id, 'failed', committed_imported)
                    resume_hint = (
                        f"PARTIAL_FAILURE: committed_records={committed_imported}, "
                        f"last_committed_processed_records={last_committed_processed_records}. "
                        f"Resume: re-run with the same CLI args plus "
                        f"--resume-batch-id={batch_id} --skip-records={last_committed_processed_records}.\n"
                        f"Cleanup (discard batch): DELETE FROM genomic_features WHERE batch_id = {batch_id}"
                    )
                    self._set_error_message(batch_id, resume_hint)
            raise

    def print_stats(self):
        """Print import statistics"""
        print("\n" + "=" * 60)
        print("RepeatMasker Import Statistics")
        print("=" * 60)
        print(f"Total lines processed:  {self.stats['total_lines']:,}")
        print(f"Features imported:      {self.stats['imported']:,}")
        print(f"Lines skipped:          {self.stats['skipped']:,}")
        print(f"Errors:                 {len(self.stats['errors'])}")

        if self.stats['errors']:
            print("\nFirst 20 errors:")
            for error in self.stats['errors'][:20]:
                print(f"  - {error}")

        print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Import RepeatMasker data into genomic_features table',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import from RepeatMasker .out file
  python3 import_repeatmasker.py --species human --file hg19.fa.out --user amax

  # Import from BED format
  python3 import_repeatmasker.py --species human --file repeats.bed --format bed --user amax

  # Import from TSV format with headers
  python3 import_repeatmasker.py --species chimp --file repeats.tsv --format tsv --user amax

  # Dry run to test parsing
  python3 import_repeatmasker.py --species human --file repeats.bed --format bed --dry-run --user amax

  # Import only chr1
  python3 import_repeatmasker.py --species human --file hg19.fa.out --chr chr1 --user amax
        """
    )

    parser.add_argument('--file', required=True, help='Input file path')
    parser.add_argument(
        '--input-manifest',
        help='Optional input manifest TSV (fail-fast verify bytes/lines/sha256 before import)',
    )
    parser.add_argument('--species', required=True,
                       choices=['human', 'chimp', 'macaque', 'marmoset'],
                       help='Species code')
    parser.add_argument('--format', default='out',
                       choices=['out', 'bed', 'tsv'],
                       help='Input file format (default: out)')
    parser.add_argument('--batch-name', help='Custom batch name')
    parser.add_argument('--batch-size', type=int, default=5000,
                       help='Batch insert size (default: 5000)')
    parser.add_argument('--commit-every', type=int, default=10,
                       help='Commit after every N batch inserts (default: 10, 0=end only)')
    parser.add_argument('--chr', dest='chromosome',
                       help='Only import specific chromosome (e.g., chr1)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Parse file without inserting data')
    parser.add_argument('--skip-records', type=int, default=0,
                       help='Skip first N parsed records (resume support; counts parsed records, not raw file lines)')
    parser.add_argument('--resume-batch-id', type=int,
                       help='Resume into an existing import_batches.batch_id (use with --skip-records)')

    # Database connection
    parser.add_argument('--host', help='Database host (or set DB_HOST env var)')
    parser.add_argument('--port', help='Database port (or set DB_PORT env var)')
    parser.add_argument('--dbname', help='Database name (or set DB_NAME env var)')
    parser.add_argument('--user', help='Database user (or set DB_USER env var)')
    parser.add_argument('--password', help='Database password (optional; or DB_PASSWORD / .pgpass)')

    args = parser.parse_args()

    if args.input_manifest:
        try:
            from etl.preflight import verify_manifest_for_paths
        except ImportError:  # pragma: no cover
            from preflight import verify_manifest_for_paths  # type: ignore

        errors = verify_manifest_for_paths(args.input_manifest, [args.file])
        if errors:
            for e in errors:
                print(e, file=sys.stderr)
            sys.exit(1)

    # Verify file exists
    if not os.path.exists(args.file):
        logger.error(f"File not found: {args.file}")
        sys.exit(1)

    db_config = get_db_config_from_env()
    if args.host:
        db_config["host"] = args.host
    if args.port:
        db_config["port"] = args.port
    if args.dbname:
        db_config["dbname"] = args.dbname
    if args.user:
        db_config["user"] = args.user
    if args.password:
        db_config["password"] = args.password

    if not db_config.get("user"):
        logger.error("DB user is required (--user or DB_USER)")
        sys.exit(1)

    db_config = finalize_db_config(db_config)

    # Run import
    importer = RepeatMaskerImporter(db_config)

    try:
        importer.connect()
        importer.import_file(
            file_path=args.file,
            species_code=args.species,
            file_format=args.format,
            batch_name=args.batch_name,
            batch_size=args.batch_size,
            commit_every=args.commit_every,
            dry_run=args.dry_run,
            chromosome_filter=args.chromosome,
            skip_records=args.skip_records,
            resume_batch_id=args.resume_batch_id,
        )
        importer.print_stats()

        # Verify results
        if not args.dry_run:
            cursor = importer.conn.cursor()

            # Count by species
            cursor.execute("""
                SELECT s.species_code, s.species_id, COUNT(gf.feature_id)
                FROM genomic_features gf
                JOIN feature_tracks ft ON gf.track_id = ft.track_id
                JOIN species s ON gf.species_id = s.species_id
                WHERE ft.track_name = 'repeatmasker_repeats'
                GROUP BY s.species_code, s.species_id
                ORDER BY s.species_id
            """)
            results = cursor.fetchall()

            print("\nDatabase Verification - RepeatMasker features by species:")
            print("-" * 60)
            for species, species_id, count in results:
                print(f"  {species}: {count:,}")

            # Count by repeat class for imported species
            cursor.execute("""
                SELECT
                    gf.attributes->>'repeat_class' AS repeat_class,
                    COUNT(*) AS count
                FROM genomic_features gf
                JOIN feature_tracks ft ON gf.track_id = ft.track_id
                WHERE ft.track_name = 'repeatmasker_repeats'
                  AND gf.species_id = %s
                GROUP BY gf.attributes->>'repeat_class'
                ORDER BY count DESC
                LIMIT 10
            """, (importer._get_species_id(args.species),))
            class_results = cursor.fetchall()

            if class_results:
                print(f"\nTop 10 repeat classes for {args.species}:")
                print("-" * 60)
                for repeat_class, count in class_results:
                    print(f"  {repeat_class}: {count:,}")

            cursor.close()

        logger.info("Import completed!")
        # 可选：通知后端失效缓存 / 重置 MV 可用性缓存（best-effort）
        if notify_backend_best_effort is not None and not args.dry_run:
            notify_backend_best_effort(reason="etl/import_repeatmasker")

    except Exception as e:
        logger.error(f"Import failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        importer.disconnect()


if __name__ == '__main__':
    main()
