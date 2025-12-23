#!/usr/bin/env python3
"""
ChIP-seq Peak Data Import Script
Unified importer for multiple histone modification marks

Usage:
    python3 import_chipseq.py --input peaks.narrowPeak \
        --mark-type H3K27me3 \
        --species human \
        --experiment-name "ENCODE_H1_H3K27me3" \
        --cell-type "H1-hESC"

    python3 import_chipseq.py --config experiment_config.json

Supported input formats:
    - narrowPeak (ENCODE standard)
    - broadPeak (for broad marks like H3K36me3)
    - BED6+4 (custom)
    - MACS2 output
"""
import argparse
import gzip
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Iterator, Tuple

import psycopg2
from psycopg2.extras import execute_values

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration and Data Classes
# =============================================================================

@dataclass
class ExperimentConfig:
    """Configuration for a ChIP-seq experiment import"""
    # Required fields
    input_file: str
    mark_type: str
    species_code: str
    experiment_name: str

    # Optional metadata
    cell_type: Optional[str] = None
    tissue_type: Optional[str] = None
    cell_line: Optional[str] = None
    treatment: Optional[str] = None

    # Data source
    source_database: Optional[str] = None
    source_accession: Optional[str] = None
    data_url: Optional[str] = None

    # Processing info
    peak_caller: str = "MACS2"
    peak_caller_version: Optional[str] = None
    pipeline_version: Optional[str] = None
    reference_genome: Optional[str] = None

    # Quality metrics (from peak calling)
    total_reads: Optional[int] = None
    mapped_reads: Optional[int] = None
    duplicate_rate: Optional[float] = None
    frip_score: Optional[float] = None

    # Import settings
    file_format: str = "narrowPeak"  # narrowPeak, broadPeak, bed
    qvalue_column: int = 8  # 0-indexed, default for narrowPeak
    fold_enrichment_column: int = 6
    summit_column: int = 9  # Summit offset from peak start
    min_qvalue: Optional[float] = None  # Filter threshold
    min_fold_enrichment: Optional[float] = None
    batch_size: int = 10000

    # Mark-specific config (flexible)
    mark_specific_config: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, json_file: str) -> 'ExperimentConfig':
        """Load configuration from JSON file"""
        with open(json_file, 'r') as f:
            data = json.load(f)
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            k: v for k, v in self.__dict__.items()
            if v is not None
        }


@dataclass
class ChIPSeqPeak:
    """Represents a single ChIP-seq peak"""
    chromosome: str
    peak_start: int
    peak_end: int
    peak_name: Optional[str] = None
    score: Optional[int] = None
    strand: str = "."
    signal_value: Optional[float] = None
    pvalue: Optional[float] = None
    qvalue: Optional[float] = None
    summit_offset: Optional[int] = None
    fold_enrichment: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    @property
    def summit_position(self) -> Optional[int]:
        """Calculate absolute summit position"""
        if self.summit_offset is not None:
            return self.peak_start + self.summit_offset
        return None

    @property
    def peak_width(self) -> int:
        return self.peak_end - self.peak_start

    def validate(self) -> Tuple[bool, Optional[str]]:
        """Validate peak data"""
        if self.peak_start < 0:
            return False, "peak_start cannot be negative"
        if self.peak_end <= self.peak_start:
            return False, "peak_end must be greater than peak_start"
        if self.summit_offset is not None and self.summit_offset < 0:
            return False, "summit_offset cannot be negative"
        if self.summit_offset is not None and self.summit_offset > self.peak_width:
            return False, "summit_offset cannot exceed peak width"
        return True, None


# =============================================================================
# File Parsers
# =============================================================================

class PeakParser:
    """Base class for peak file parsers"""

    def __init__(self, config: ExperimentConfig):
        self.config = config

    def parse(self, filepath: str) -> Iterator[ChIPSeqPeak]:
        """Parse file and yield peaks"""
        raise NotImplementedError

    def _open_file(self, filepath: str):
        """Open file with gzip support"""
        if filepath.endswith('.gz'):
            return gzip.open(filepath, 'rt')
        return open(filepath, 'r')


class NarrowPeakParser(PeakParser):
    """
    Parser for ENCODE narrowPeak format

    Format (10 columns):
    1. chrom
    2. chromStart
    3. chromEnd
    4. name
    5. score
    6. strand
    7. signalValue (fold enrichment)
    8. pValue (-log10)
    9. qValue (-log10)
    10. peak (summit offset from chromStart)
    """

    def parse(self, filepath: str) -> Iterator[ChIPSeqPeak]:
        with self._open_file(filepath) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('track'):
                    continue

                try:
                    fields = line.split('\t')
                    if len(fields) < 10:
                        logger.warning(f"Line {line_num}: Insufficient columns ({len(fields)})")
                        continue

                    # Parse fields
                    chrom = fields[0]
                    start = int(fields[1])
                    end = int(fields[2])
                    name = fields[3] if fields[3] != '.' else None
                    score = int(fields[4]) if fields[4] != '.' else None
                    strand = fields[5] if fields[5] in ['+', '-', '.'] else '.'

                    # Signal and statistics
                    signal_value = float(fields[6]) if fields[6] != '.' and fields[6] != '-1' else None
                    neg_log10_pvalue = float(fields[7]) if fields[7] != '.' and fields[7] != '-1' else None
                    neg_log10_qvalue = float(fields[8]) if fields[8] != '.' and fields[8] != '-1' else None
                    summit_offset = int(fields[9]) if fields[9] != '.' and fields[9] != '-1' else None

                    # Convert -log10 values to actual p/q-values
                    pvalue = 10 ** (-neg_log10_pvalue) if neg_log10_pvalue is not None else None
                    qvalue = 10 ** (-neg_log10_qvalue) if neg_log10_qvalue is not None else None

                    # Apply filters
                    if self.config.min_qvalue is not None and qvalue is not None:
                        if qvalue > self.config.min_qvalue:
                            continue

                    if self.config.min_fold_enrichment is not None and signal_value is not None:
                        if signal_value < self.config.min_fold_enrichment:
                            continue

                    yield ChIPSeqPeak(
                        chromosome=chrom,
                        peak_start=start,
                        peak_end=end,
                        peak_name=name,
                        score=score,
                        strand=strand,
                        signal_value=signal_value,
                        fold_enrichment=signal_value,  # In narrowPeak, signalValue is fold enrichment
                        pvalue=pvalue,
                        qvalue=qvalue,
                        summit_offset=summit_offset,
                    )

                except (ValueError, IndexError) as e:
                    logger.warning(f"Line {line_num}: Parse error - {e}")
                    continue


class BroadPeakParser(PeakParser):
    """
    Parser for ENCODE broadPeak format

    Format (9 columns) - similar to narrowPeak but without summit:
    1. chrom
    2. chromStart
    3. chromEnd
    4. name
    5. score
    6. strand
    7. signalValue
    8. pValue (-log10)
    9. qValue (-log10)
    """

    def parse(self, filepath: str) -> Iterator[ChIPSeqPeak]:
        with self._open_file(filepath) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('track'):
                    continue

                try:
                    fields = line.split('\t')
                    if len(fields) < 9:
                        logger.warning(f"Line {line_num}: Insufficient columns ({len(fields)})")
                        continue

                    chrom = fields[0]
                    start = int(fields[1])
                    end = int(fields[2])
                    name = fields[3] if fields[3] != '.' else None
                    score = int(fields[4]) if fields[4] != '.' else None
                    strand = fields[5] if fields[5] in ['+', '-', '.'] else '.'
                    signal_value = float(fields[6]) if fields[6] != '.' and fields[6] != '-1' else None
                    neg_log10_pvalue = float(fields[7]) if fields[7] != '.' and fields[7] != '-1' else None
                    neg_log10_qvalue = float(fields[8]) if fields[8] != '.' and fields[8] != '-1' else None

                    pvalue = 10 ** (-neg_log10_pvalue) if neg_log10_pvalue is not None else None
                    qvalue = 10 ** (-neg_log10_qvalue) if neg_log10_qvalue is not None else None

                    # Apply filters
                    if self.config.min_qvalue is not None and qvalue is not None:
                        if qvalue > self.config.min_qvalue:
                            continue

                    if self.config.min_fold_enrichment is not None and signal_value is not None:
                        if signal_value < self.config.min_fold_enrichment:
                            continue

                    yield ChIPSeqPeak(
                        chromosome=chrom,
                        peak_start=start,
                        peak_end=end,
                        peak_name=name,
                        score=score,
                        strand=strand,
                        signal_value=signal_value,
                        fold_enrichment=signal_value,
                        pvalue=pvalue,
                        qvalue=qvalue,
                        summit_offset=None,  # No summit for broad peaks
                    )

                except (ValueError, IndexError) as e:
                    logger.warning(f"Line {line_num}: Parse error - {e}")
                    continue


def get_parser(config: ExperimentConfig) -> PeakParser:
    """Get appropriate parser for file format"""
    format_map = {
        'narrowPeak': NarrowPeakParser,
        'narrowpeak': NarrowPeakParser,
        'broadPeak': BroadPeakParser,
        'broadpeak': BroadPeakParser,
    }
    parser_class = format_map.get(config.file_format, NarrowPeakParser)
    return parser_class(config)


# =============================================================================
# Database Operations
# =============================================================================

class ChIPSeqImporter:
    """Handles database operations for ChIP-seq data import"""

    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        self.conn = None

    def connect(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(**self.db_config)
        self.conn.autocommit = False

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.conn.rollback()
        self.close()

    def get_species_id(self, species_code: str) -> int:
        """Get species_id from species_code"""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT species_id FROM species WHERE species_code = %s",
                (species_code,)
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Species not found: {species_code}")
            return row[0]

    def get_mark_type_id(self, mark_name: str) -> int:
        """Get mark_type_id from mark_name"""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT mark_type_id FROM epigenetic_mark_types WHERE mark_name = %s",
                (mark_name,)
            )
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Mark type not found: {mark_name}")
            return row[0]

    def create_import_batch(self, config: ExperimentConfig, species_id: int) -> int:
        """Create import batch record"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO import_batches (
                    batch_name, batch_type, species_id, source_file, status
                ) VALUES (%s, %s, %s, %s, 'in_progress')
                RETURNING batch_id
            """, (
                f"ChIP-seq_{config.mark_type}_{config.experiment_name}",
                'chipseq',
                species_id,
                config.input_file,
            ))
            return cur.fetchone()[0]

    def create_or_get_experiment(self, config: ExperimentConfig, species_id: int,
                                  mark_type_id: int, batch_id: int) -> int:
        """Create experiment record or get existing one"""
        with self.conn.cursor() as cur:
            # Check if experiment exists
            cur.execute("""
                SELECT experiment_id FROM chipseq_experiments
                WHERE experiment_name = %s AND species_id = %s
            """, (config.experiment_name, species_id))
            row = cur.fetchone()

            if row:
                logger.info(f"Using existing experiment: {config.experiment_name} (ID: {row[0]})")
                return row[0]

            # Create new experiment
            cur.execute("""
                INSERT INTO chipseq_experiments (
                    experiment_name, species_id, mark_type_id,
                    cell_type, tissue_type, cell_line, treatment,
                    source_database, source_accession, data_url,
                    pipeline_version, peak_caller, peak_caller_version, reference_genome,
                    total_reads, mapped_reads, duplicate_rate, frip_score,
                    signal_threshold, mark_specific_config,
                    import_batch_id, is_active
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, TRUE
                )
                RETURNING experiment_id
            """, (
                config.experiment_name, species_id, mark_type_id,
                config.cell_type, config.tissue_type, config.cell_line, config.treatment,
                config.source_database, config.source_accession, config.data_url,
                config.pipeline_version, config.peak_caller, config.peak_caller_version, config.reference_genome,
                config.total_reads, config.mapped_reads, config.duplicate_rate, config.frip_score,
                json.dumps({
                    'qvalue_cutoff': config.min_qvalue,
                    'fold_enrichment_min': config.min_fold_enrichment,
                }) if config.min_qvalue or config.min_fold_enrichment else None,
                json.dumps(config.mark_specific_config) if config.mark_specific_config else None,
                batch_id,
            ))

            experiment_id = cur.fetchone()[0]
            logger.info(f"Created experiment: {config.experiment_name} (ID: {experiment_id})")
            return experiment_id

    def import_peaks(self, peaks: Iterator[ChIPSeqPeak], experiment_id: int,
                     species_id: int, batch_size: int = 10000) -> Tuple[int, int]:
        """
        Import peaks in batches

        Returns: (imported_count, skipped_count)
        """
        imported = 0
        skipped = 0
        batch = []

        with self.conn.cursor() as cur:
            for peak in peaks:
                # Validate peak
                valid, error = peak.validate()
                if not valid:
                    logger.debug(f"Skipping invalid peak: {error}")
                    skipped += 1
                    continue

                # Calculate derived values
                log2_fe = None
                if peak.fold_enrichment and peak.fold_enrichment > 0:
                    import math
                    log2_fe = math.log2(peak.fold_enrichment)

                neg_log10_pvalue = None
                neg_log10_qvalue = None
                if peak.pvalue and peak.pvalue > 0:
                    import math
                    neg_log10_pvalue = -math.log10(peak.pvalue)
                if peak.qvalue and peak.qvalue > 0:
                    import math
                    neg_log10_qvalue = -math.log10(peak.qvalue)

                batch.append((
                    experiment_id,
                    species_id,
                    peak.chromosome,
                    peak.peak_start,
                    peak.peak_end,
                    peak.summit_position,
                    peak.peak_name,
                    peak.strand,
                    peak.fold_enrichment,
                    log2_fe,
                    peak.pvalue,
                    neg_log10_pvalue,
                    peak.qvalue,
                    neg_log10_qvalue,
                    peak.signal_value,
                    peak.score,
                    json.dumps(peak.attributes) if peak.attributes else '{}',
                ))

                if len(batch) >= batch_size:
                    self._insert_batch(cur, batch)
                    imported += len(batch)
                    logger.info(f"Imported {imported} peaks...")
                    batch = []

            # Insert remaining
            if batch:
                self._insert_batch(cur, batch)
                imported += len(batch)

        return imported, skipped

    def _insert_batch(self, cur, batch: List[tuple]):
        """Insert a batch of peaks"""
        execute_values(cur, """
            INSERT INTO chipseq_peaks (
                experiment_id, species_id, chromosome, peak_start, peak_end,
                summit_position, peak_name, strand,
                fold_enrichment, log2_fold_enrichment,
                pvalue, neg_log10_pvalue, qvalue, neg_log10_qvalue,
                signal_value, score, attributes
            ) VALUES %s
        """, batch, template="""(
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s::jsonb
        )""")

    def update_batch_status(self, batch_id: int, status: str,
                            record_count: int = None, error_message: str = None):
        """Update import batch status"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE import_batches
                SET status = %s,
                    record_count = %s,
                    error_message = %s,
                    completed_at = CASE WHEN %s IN ('completed', 'failed') THEN NOW() ELSE NULL END
                WHERE batch_id = %s
            """, (status, record_count, error_message, status, batch_id))

    def commit(self):
        """Commit transaction"""
        self.conn.commit()

    def refresh_materialized_views(self):
        """Refresh materialized views after import"""
        logger.info("Refreshing materialized views...")
        with self.conn.cursor() as cur:
            try:
                cur.execute("SELECT refresh_chipseq_stats()")
            except Exception as e:
                logger.warning(f"Failed to refresh materialized views: {e}")


# =============================================================================
# Main Import Function
# =============================================================================

def import_chipseq(config: ExperimentConfig, db_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main import function

    Args:
        config: Experiment configuration
        db_config: Database connection parameters

    Returns:
        Import results dictionary
    """
    logger.info(f"Starting ChIP-seq import: {config.experiment_name}")
    logger.info(f"  Mark type: {config.mark_type}")
    logger.info(f"  Species: {config.species_code}")
    logger.info(f"  Input file: {config.input_file}")

    # Validate input file
    if not os.path.exists(config.input_file):
        raise FileNotFoundError(f"Input file not found: {config.input_file}")

    results = {
        'success': False,
        'experiment_name': config.experiment_name,
        'mark_type': config.mark_type,
        'peaks_imported': 0,
        'peaks_skipped': 0,
        'errors': [],
    }

    with ChIPSeqImporter(db_config) as importer:
        try:
            # Get IDs
            species_id = importer.get_species_id(config.species_code)
            mark_type_id = importer.get_mark_type_id(config.mark_type)

            # Create import batch
            batch_id = importer.create_import_batch(config, species_id)
            results['batch_id'] = batch_id

            # Create or get experiment
            experiment_id = importer.create_or_get_experiment(
                config, species_id, mark_type_id, batch_id
            )
            results['experiment_id'] = experiment_id

            # Parse and import peaks
            parser = get_parser(config)
            peaks = parser.parse(config.input_file)
            imported, skipped = importer.import_peaks(
                peaks, experiment_id, species_id, config.batch_size
            )

            results['peaks_imported'] = imported
            results['peaks_skipped'] = skipped

            # Update batch status
            importer.update_batch_status(batch_id, 'completed', imported)

            # Commit
            importer.commit()

            # Refresh materialized views
            importer.refresh_materialized_views()
            importer.commit()

            results['success'] = True
            logger.info(f"Import completed: {imported} peaks imported, {skipped} skipped")

        except Exception as e:
            logger.error(f"Import failed: {e}")
            results['errors'].append(str(e))
            if 'batch_id' in results:
                try:
                    importer.update_batch_status(
                        results['batch_id'], 'failed', error_message=str(e)
                    )
                    importer.commit()
                except Exception as update_error:
                    logger.warning(f"Failed to update batch status for batch_id={results['batch_id']}: {update_error}")
            raise

    return results


# =============================================================================
# CLI Interface
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description='Import ChIP-seq peak data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import narrowPeak file
  python3 import_chipseq.py \\
    --input H3K27me3_peaks.narrowPeak.gz \\
    --mark-type H3K27me3 \\
    --species human \\
    --experiment-name "ENCODE_H1_H3K27me3" \\
    --cell-type "H1-hESC"

  # Import with configuration file
  python3 import_chipseq.py --config experiment.json

  # Import broadPeak (for H3K36me3)
  python3 import_chipseq.py \\
    --input H3K36me3_peaks.broadPeak \\
    --mark-type H3K36me3 \\
    --format broadPeak \\
    --species human \\
    --experiment-name "ENCODE_K562_H3K36me3"
        """
    )

    # Config file option
    parser.add_argument(
        '--config', '-c',
        help='JSON configuration file (overrides other options)'
    )

    # Required options (if no config)
    parser.add_argument(
        '--input', '-i',
        help='Input peak file (narrowPeak, broadPeak, BED)'
    )
    parser.add_argument(
        '--mark-type', '-m',
        help='Mark type (e.g., H3K27me3, H3K4me1)'
    )
    parser.add_argument(
        '--species', '-s',
        help='Species code (e.g., human, mouse)'
    )
    parser.add_argument(
        '--experiment-name', '-n',
        help='Unique experiment name'
    )

    # Optional metadata
    parser.add_argument('--cell-type', help='Cell type')
    parser.add_argument('--tissue-type', help='Tissue type')
    parser.add_argument('--cell-line', help='Cell line')
    parser.add_argument('--treatment', help='Treatment')
    parser.add_argument('--source', help='Source database (ENCODE, GEO)')
    parser.add_argument('--accession', help='Source accession')

    # Format options
    parser.add_argument(
        '--format', '-f',
        default='narrowPeak',
        choices=['narrowPeak', 'broadPeak', 'bed'],
        help='Input file format (default: narrowPeak)'
    )

    # Filter options
    parser.add_argument(
        '--min-qvalue',
        type=float,
        help='Minimum q-value threshold'
    )
    parser.add_argument(
        '--min-fold-enrichment',
        type=float,
        help='Minimum fold enrichment threshold'
    )

    # Database options
    parser.add_argument('--db-host', default='localhost')
    parser.add_argument('--db-port', type=int, default=5432)
    parser.add_argument('--db-name', default='lncrna_production')
    parser.add_argument('--db-user', default='postgres')
    parser.add_argument('--db-password', default='')

    # Other options
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10000,
        help='Batch size for database inserts'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Parse file without importing'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Build configuration
    if args.config:
        config = ExperimentConfig.from_json(args.config)
    else:
        if not all([args.input, args.mark_type, args.species, args.experiment_name]):
            print("Error: --input, --mark-type, --species, and --experiment-name are required")
            print("       Or use --config with a JSON configuration file")
            sys.exit(1)

        config = ExperimentConfig(
            input_file=args.input,
            mark_type=args.mark_type,
            species_code=args.species,
            experiment_name=args.experiment_name,
            cell_type=args.cell_type,
            tissue_type=args.tissue_type,
            cell_line=args.cell_line,
            treatment=args.treatment,
            source_database=args.source,
            source_accession=args.accession,
            file_format=args.format,
            min_qvalue=args.min_qvalue,
            min_fold_enrichment=args.min_fold_enrichment,
            batch_size=args.batch_size,
        )

    # Dry run mode
    if args.dry_run:
        logger.info("Dry run mode - parsing file without importing")
        parser = get_parser(config)
        count = 0
        for peak in parser.parse(config.input_file):
            count += 1
            if count <= 5:
                print(f"  Peak {count}: {peak.chromosome}:{peak.peak_start}-{peak.peak_end} "
                      f"FE={peak.fold_enrichment} q={peak.qvalue}")
        print(f"\nTotal peaks parsed: {count}")
        return

    # Database config
    db_config = {
        'host': args.db_host,
        'port': args.db_port,
        'dbname': args.db_name,
        'user': args.db_user,
        'password': args.db_password,
    }

    # Run import
    try:
        results = import_chipseq(config, db_config)
        print("\n" + "=" * 50)
        print("Import Results:")
        print(f"  Success: {results['success']}")
        print(f"  Experiment ID: {results.get('experiment_id', 'N/A')}")
        print(f"  Peaks imported: {results['peaks_imported']}")
        print(f"  Peaks skipped: {results['peaks_skipped']}")
        if results['errors']:
            print(f"  Errors: {results['errors']}")
        print("=" * 50)

    except Exception as e:
        logger.error(f"Import failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
