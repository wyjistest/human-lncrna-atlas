#!/usr/bin/env python3
"""
Export RepeatMasker annotations from PostgreSQL to BED9 format.

BED9 format: chr, start, end, name, score, strand, thickStart, thickEnd, itemRGB
- itemRGB is assigned based on repeat_class (UCSC standard colors)

This script exports data from the genomic_features table where track_name = 'repeatmasker_repeats'.
"""

import argparse
import logging
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import DictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# UCSC standard RepeatMasker color scheme
# Colors are in RGB format: R,G,B
REPEAT_CLASS_COLORS = {
    'SINE': '255,0,0',           # Red
    'LINE': '0,0,204',           # Blue
    'LTR': '0,204,0',            # Green
    'DNA': '204,0,204',          # Purple/Magenta
    'Simple_repeat': '0,0,0',    # Black
    'Low_complexity': '102,102,102',  # Gray
    'Satellite': '204,102,0',    # Orange
    'RNA': '139,69,19',          # Brown (for rRNA, tRNA, etc.)
    'snRNA': '70,130,180',       # Steel blue
    'scRNA': '70,130,180',       # Steel blue
    'srpRNA': '70,130,180',      # Steel blue
    'tRNA': '139,69,19',         # Brown
    'rRNA': '139,69,19',         # Brown
    'RC': '128,0,128',           # Purple (Rolling Circle)
    'Retroposon': '255,165,0',   # Orange
    'Unknown': '136,136,136',    # Dark gray
}

# Default color for unknown repeat classes
DEFAULT_COLOR = '136,136,136'  # Dark gray


def get_repeat_class_color(repeat_class: str) -> str:
    """
    Get the RGB color for a given repeat class.

    Args:
        repeat_class: The repeat class name (e.g., 'SINE', 'LINE', 'LTR')

    Returns:
        RGB color string in format 'R,G,B'
    """
    if not repeat_class:
        return DEFAULT_COLOR

    # Direct match
    if repeat_class in REPEAT_CLASS_COLORS:
        return REPEAT_CLASS_COLORS[repeat_class]

    # Try partial match (e.g., 'SINE?' -> 'SINE')
    for class_prefix in REPEAT_CLASS_COLORS:
        if repeat_class.startswith(class_prefix):
            return REPEAT_CLASS_COLORS[class_prefix]

    return DEFAULT_COLOR


def export_repeatmasker_bed9(
    db_host: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_password: str,
    species_id: int,
    output_file: Path,
    batch_size: int = 100000,
    repeat_class: str = None,
) -> int:
    """
    Export RepeatMasker annotations to BED9 format.

    Args:
        db_host: Database host
        db_port: Database port
        db_name: Database name
        db_user: Database user
        db_password: Database password (empty string for no password)
        species_id: Species ID to export (1 = Human)
        output_file: Output BED9 file path
        batch_size: Number of records to fetch per batch
        repeat_class: Optional repeat class filter (e.g., 'SINE', 'LINE', 'LTR')

    Returns:
        Total number of records exported
    """
    # Connect to database
    conn_params = {
        'host': db_host,
        'port': db_port,
        'dbname': db_name,
        'user': db_user,
    }
    if db_password:
        conn_params['password'] = db_password

    logger.info(f"Connecting to database {db_name}@{db_host}:{db_port}")
    conn = psycopg2.connect(**conn_params)

    try:
        # Get track_id for RepeatMasker
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                "SELECT track_id FROM feature_tracks WHERE track_name = 'repeatmasker_repeats'"
            )
            result = cur.fetchone()
            if not result:
                raise ValueError("RepeatMasker track not found in feature_tracks table")
            track_id = result['track_id']
            logger.info(f"Found RepeatMasker track_id: {track_id}")

        # Count total records
        with conn.cursor() as cur:
            if repeat_class:
                cur.execute("""
                    SELECT COUNT(*) FROM genomic_features
                    WHERE track_id = %s AND species_id = %s
                    AND attributes->>'repeat_class' = %s
                """, (track_id, species_id, repeat_class))
            else:
                cur.execute(
                    "SELECT COUNT(*) FROM genomic_features WHERE track_id = %s AND species_id = %s",
                    (track_id, species_id)
                )
            total_count = cur.fetchone()[0]
            if repeat_class:
                logger.info(f"Total RepeatMasker features to export (class={repeat_class}): {total_count:,}")
            else:
                logger.info(f"Total RepeatMasker features to export: {total_count:,}")

        # Export in batches using server-side cursor for memory efficiency
        exported_count = 0

        with conn.cursor(name='repeatmasker_export', cursor_factory=DictCursor) as cur:
            # Query with ordering for consistent output
            if repeat_class:
                cur.execute("""
                    SELECT
                        chromosome,
                        feature_start,
                        feature_end,
                        feature_name,
                        score,
                        strand,
                        attributes
                    FROM genomic_features
                    WHERE track_id = %s AND species_id = %s
                    AND attributes->>'repeat_class' = %s
                    ORDER BY chromosome, feature_start
                """, (track_id, species_id, repeat_class))
            else:
                cur.execute("""
                    SELECT
                        chromosome,
                        feature_start,
                        feature_end,
                        feature_name,
                        score,
                        strand,
                        attributes
                    FROM genomic_features
                    WHERE track_id = %s AND species_id = %s
                    ORDER BY chromosome, feature_start
                """, (track_id, species_id))

            with open(output_file, 'w') as f:
                while True:
                    batch = cur.fetchmany(batch_size)
                    if not batch:
                        break

                    for row in batch:
                        # Extract fields
                        chrom = row['chromosome']
                        start = row['feature_start']
                        end = row['feature_end']
                        name = row['feature_name'] or 'repeat'

                        # Score: use existing score or calculate from divergence
                        attrs = row['attributes'] or {}
                        if row['score'] is not None:
                            score = min(1000, max(0, int(float(row['score']))))
                        else:
                            # Calculate score from divergence (lower = better)
                            divergence = attrs.get('divergence', 50)
                            score = max(0, min(1000, int(1000 - float(divergence) * 20)))

                        strand = row['strand'] or '.'

                        # BED9: thickStart = start, thickEnd = end (no thick distinction)
                        thick_start = start
                        thick_end = end

                        # Get color based on repeat_class
                        repeat_class = attrs.get('repeat_class', '')
                        item_rgb = get_repeat_class_color(repeat_class)

                        # Write BED9 line
                        f.write(f"{chrom}\t{start}\t{end}\t{name}\t{score}\t{strand}\t{thick_start}\t{thick_end}\t{item_rgb}\n")
                        exported_count += 1

                    # Progress update
                    if exported_count % 500000 == 0:
                        logger.info(f"Exported {exported_count:,} / {total_count:,} records ({100*exported_count/total_count:.1f}%)")

        logger.info(f"Export complete: {exported_count:,} records written to {output_file}")
        return exported_count

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Export RepeatMasker annotations from PostgreSQL to BED9 format'
    )
    parser.add_argument(
        '--host',
        default='localhost',
        help='Database host (default: localhost)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5432,
        help='Database port (default: 5432)'
    )
    parser.add_argument(
        '--database',
        default='lncrna_production',
        help='Database name (default: lncrna_production)'
    )
    parser.add_argument(
        '--user',
        default='amax',
        help='Database user (default: amax)'
    )
    parser.add_argument(
        '--password',
        default='',
        help='Database password (default: empty)'
    )
    parser.add_argument(
        '--species-id',
        type=int,
        default=1,
        help='Species ID to export (default: 1 for Human)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('/data/wenyujianData/humanLncAtlas/genomes/repeatmasker_human_bed9.bed'),
        help='Output BED9 file path'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100000,
        help='Batch size for database queries (default: 100000)'
    )
    parser.add_argument(
        '--repeat-class',
        type=str,
        default=None,
        help='Filter by repeat class (e.g., SINE, LINE, LTR, DNA, Simple_repeat, Low_complexity)'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=None,
        help='Output directory for batch export (exports all classes separately)'
    )

    args = parser.parse_args()

    try:
        # Batch export mode: export all classes separately
        if args.output_dir:
            output_dir = args.output_dir
            output_dir.mkdir(parents=True, exist_ok=True)

            # Define repeat classes to export
            repeat_classes = ['SINE', 'LINE', 'LTR', 'DNA', 'Simple_repeat', 'Low_complexity']

            total_exported = 0
            for repeat_class in repeat_classes:
                output_file = output_dir / f"repeatmasker_{repeat_class}.bed"
                logger.info(f"Exporting {repeat_class} to {output_file}")

                count = export_repeatmasker_bed9(
                    db_host=args.host,
                    db_port=args.port,
                    db_name=args.database,
                    db_user=args.user,
                    db_password=args.password,
                    species_id=args.species_id,
                    output_file=output_file,
                    batch_size=args.batch_size,
                    repeat_class=repeat_class,
                )
                total_exported += count
                logger.info(f"Exported {count:,} {repeat_class} features")

            # Export "Other" class (all remaining classes)
            output_file = output_dir / "repeatmasker_Other.bed"
            logger.info(f"Exporting Other classes to {output_file}")

            # For "Other", we need to export all classes NOT in the main list
            # This requires a different approach - export all and filter
            conn_params = {
                'host': args.host,
                'port': args.port,
                'dbname': args.database,
                'user': args.user,
            }
            if args.password:
                conn_params['password'] = args.password

            conn = psycopg2.connect(**conn_params)
            try:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(
                        "SELECT track_id FROM feature_tracks WHERE track_name = 'repeatmasker_repeats'"
                    )
                    result = cur.fetchone()
                    track_id = result['track_id']

                with conn.cursor(name='other_export', cursor_factory=DictCursor) as cur:
                    cur.execute("""
                        SELECT
                            chromosome,
                            feature_start,
                            feature_end,
                            feature_name,
                            score,
                            strand,
                            attributes
                        FROM genomic_features
                        WHERE track_id = %s AND species_id = %s
                        AND attributes->>'repeat_class' NOT IN ('SINE', 'LINE', 'LTR', 'DNA', 'Simple_repeat', 'Low_complexity')
                        ORDER BY chromosome, feature_start
                    """, (track_id, args.species_id))

                    other_count = 0
                    with open(output_file, 'w') as f:
                        while True:
                            batch = cur.fetchmany(args.batch_size)
                            if not batch:
                                break

                            for row in batch:
                                chrom = row['chromosome']
                                start = row['feature_start']
                                end = row['feature_end']
                                name = row['feature_name'] or 'repeat'
                                attrs = row['attributes'] or {}

                                if row['score'] is not None:
                                    score = min(1000, max(0, int(float(row['score']))))
                                else:
                                    divergence = attrs.get('divergence', 50)
                                    score = max(0, min(1000, int(1000 - float(divergence) * 20)))

                                strand = row['strand'] or '.'
                                thick_start = start
                                thick_end = end
                                repeat_class = attrs.get('repeat_class', '')
                                item_rgb = get_repeat_class_color(repeat_class)

                                f.write(f"{chrom}\t{start}\t{end}\t{name}\t{score}\t{strand}\t{thick_start}\t{thick_end}\t{item_rgb}\n")
                                other_count += 1

                    total_exported += other_count
                    logger.info(f"Exported {other_count:,} Other features")
            finally:
                conn.close()

            logger.info(f"Successfully exported {total_exported:,} RepeatMasker features across all classes")
            sys.exit(0)

        # Single file export mode
        count = export_repeatmasker_bed9(
            db_host=args.host,
            db_port=args.port,
            db_name=args.database,
            db_user=args.user,
            db_password=args.password,
            species_id=args.species_id,
            output_file=args.output,
            batch_size=args.batch_size,
            repeat_class=args.repeat_class,
        )

        logger.info(f"Successfully exported {count:,} RepeatMasker features")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Export failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
