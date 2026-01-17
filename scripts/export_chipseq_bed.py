#!/usr/bin/env python3
"""
Export ChIP-seq peaks to BED format for bigBed conversion

This script exports ChIP-seq peaks from PostgreSQL database to BED9 format,
grouped by cell_type. The output files can then be converted to BigBed format
using bedToBigBed for efficient IGV.js loading.

Usage:
    # Export all cell types
    python3 export_chipseq_bed.py --output-dir /path/to/output

    # Export specific cell type
    python3 export_chipseq_bed.py --cell-type K562 --output-dir /path/to/output

    # Export with mark type filter
    python3 export_chipseq_bed.py --mark-type H3K27me3 --output-dir /path/to/output
"""
import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Dict
import subprocess

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "frontend" / "backend"))

from sqlalchemy import text
from app.core.database import SessionLocal


# Mark type color mapping (RGB format for BED9 itemRgb)
MARK_COLORS: Dict[str, str] = {
    # Repressive marks - Red/Purple tones
    'H3K27me3': '178,102,255',    # Purple
    'H3K9me3': '139,0,0',         # Dark Red

    # Activating marks - Green/Blue tones
    'H3K4me3': '0,128,0',         # Green
    'H3K4me1': '60,179,113',      # Medium Sea Green
    'H3K27ac': '255,165,0',       # Orange (active enhancer)
    'H3K36me3': '70,130,180',     # Steel Blue
    'H3K4me2': '34,139,34',       # Forest Green
    'H3K9ac': '50,205,50',        # Lime Green

    # Open Chromatin
    'DNase-HS': '255,0,0',        # Red

    # Structural
    'CTCF': '0,0,139',            # Dark Blue
    'H4K20me1': '100,149,237',    # Cornflower Blue

    # Default
    'default': '128,128,128',     # Gray
}


def get_mark_color(mark_name: str) -> str:
    """Get RGB color string for a mark type"""
    return MARK_COLORS.get(mark_name, MARK_COLORS['default'])


def export_chipseq_bed(
    output_dir: str,
    cell_type: Optional[str] = None,
    mark_type: Optional[str] = None,
    species_id: int = 1,  # Human
    batch_size: int = 50000
) -> Dict[str, str]:
    """
    Export ChIP-seq peaks as BED9 format files grouped by cell_type

    BED9 format: chrom, chromStart, chromEnd, name, score, strand, thickStart, thickEnd, itemRgb
    - name: mark_type|peak_name
    - score: scaled from fold_enrichment (0-1000)
    - strand: . (ChIP-seq peaks don't have strand)
    - thickStart/thickEnd: same as chromStart/chromEnd
    - itemRgb: color based on mark_type

    Returns dict of {cell_type: output_file_path}
    """
    db = SessionLocal()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    exported_files: Dict[str, str] = {}

    try:
        # Build query to get all peaks with experiment info
        query = text("""
            SELECT
                p.chromosome,
                p.peak_start,
                p.peak_end,
                p.peak_name,
                p.fold_enrichment,
                m.mark_name,
                e.cell_type
            FROM chipseq_peaks p
            JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
            JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
            WHERE p.species_id = :species_id
              AND e.is_active = TRUE
              AND (:cell_type IS NULL OR e.cell_type = :cell_type)
              AND (:mark_type IS NULL OR m.mark_name = :mark_type)
            ORDER BY e.cell_type, p.chromosome, p.peak_start
        """)

        result = db.execute(query, {
            'species_id': species_id,
            'cell_type': cell_type,
            'mark_type': mark_type
        })

        # Group by cell_type and write to separate files
        current_cell_type = None
        current_file = None
        processed = 0
        cell_type_counts: Dict[str, int] = {}

        for row in result:
            chrom, start, end, peak_name, fold_enrichment, mark_name, row_cell_type = row

            # Skip invalid coordinates
            if not chrom or start is None or end is None:
                continue

            # Handle cell_type change
            if row_cell_type != current_cell_type:
                if current_file:
                    current_file.close()
                    print(f"  ✅ {current_cell_type}: {cell_type_counts.get(current_cell_type, 0):,} peaks")

                current_cell_type = row_cell_type
                # Sanitize cell type for filename
                safe_cell_type = row_cell_type.replace('-', '_').replace(' ', '_')
                output_file = output_path / f"chipseq_{safe_cell_type}.bed"
                current_file = open(output_file, 'w')
                exported_files[row_cell_type] = str(output_file)
                cell_type_counts[row_cell_type] = 0
                print(f"📝 Exporting {row_cell_type}...")

            # Calculate score (0-1000) from fold_enrichment
            # Typical fold_enrichment: 1-100, map to 0-1000
            fe = float(fold_enrichment) if fold_enrichment else 1.0
            score = min(1000, max(0, int(fe * 10)))

            # Get color for mark type
            item_rgb = get_mark_color(mark_name)

            # Build name: mark_type|peak_name or mark_type|peak_N
            name = f"{mark_name}|{peak_name}" if peak_name else f"{mark_name}|peak_{processed}"

            # Write BED9 line
            # chrom, start, end, name, score, strand, thickStart, thickEnd, itemRgb
            current_file.write(
                f"{chrom}\t{start}\t{end}\t{name}\t{score}\t.\t{start}\t{end}\t{item_rgb}\n"
            )

            cell_type_counts[row_cell_type] = cell_type_counts.get(row_cell_type, 0) + 1
            processed += 1

            if processed % 500000 == 0:
                print(f"  Processed {processed:,} peaks...")

        # Close last file
        if current_file:
            current_file.close()
            print(f"  ✅ {current_cell_type}: {cell_type_counts.get(current_cell_type, 0):,} peaks")

        print(f"\n✅ Total exported: {processed:,} peaks to {len(exported_files)} files")

        # Print summary
        print("\n📊 Summary by cell type:")
        for ct, count in sorted(cell_type_counts.items()):
            print(f"  {ct}: {count:,} peaks")

        return exported_files

    finally:
        db.close()


def sort_bed_file(bed_file: str) -> str:
    """Sort BED file by chromosome and position (required for bedToBigBed)"""
    sorted_file = bed_file.replace('.bed', '_sorted.bed')
    print(f"🔄 Sorting {Path(bed_file).name}...")

    # Use sort command for efficient sorting
    with open(sorted_file, "w", encoding="utf-8") as out:
        subprocess.run(
            ["sort", "-k1,1", "-k2,2n", bed_file],
            stdout=out,
            check=True,
        )

    return sorted_file


def convert_to_bigbed(
    bed_file: str,
    chrom_sizes: str,
    output_dir: str,
    bed_to_bigbed_path: str = "bedToBigBed"
) -> Optional[str]:
    """
    Convert sorted BED9 file to BigBed format

    Args:
        bed_file: Path to sorted BED file
        chrom_sizes: Path to chromosome sizes file
        output_dir: Directory for output BigBed file
        bed_to_bigbed_path: Path to bedToBigBed executable

    Returns:
        Path to BigBed file or None if failed
    """
    bed_path = Path(bed_file)
    bb_file = Path(output_dir) / bed_path.name.replace('.bed', '.bb').replace('_sorted', '')

    print(f"🔄 Converting {bed_path.name} to BigBed...")

    try:
        # bedToBigBed -type=bed9 input.bed chrom.sizes output.bb
        result = subprocess.run(
            [bed_to_bigbed_path, "-type=bed9", bed_file, chrom_sizes, str(bb_file)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"  ❌ Failed: {result.stderr}")
            return None

        # Get file sizes
        bed_size = bed_path.stat().st_size / (1024 * 1024)  # MB
        bb_size = bb_file.stat().st_size / (1024 * 1024)  # MB
        compression = (1 - bb_size / bed_size) * 100 if bed_size > 0 else 0

        print(f"  ✅ {bb_file.name}: {bb_size:.1f}MB (compressed {compression:.1f}%)")
        return str(bb_file)

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Export ChIP-seq peaks to BED/BigBed format for IGV.js',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all cell types to BED files
  python3 export_chipseq_bed.py --output-dir ./chipseq_bed

  # Export and convert to BigBed
  python3 export_chipseq_bed.py --output-dir ./chipseq_bed --convert-bigbed

  # Export specific cell type
  python3 export_chipseq_bed.py --cell-type K562 --output-dir ./chipseq_bed
        """
    )

    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default='./chipseq_bed',
        help='Output directory for BED files (default: ./chipseq_bed)'
    )
    parser.add_argument(
        '--cell-type', '-c',
        type=str,
        help='Filter by cell type (e.g., K562, GM12878)'
    )
    parser.add_argument(
        '--mark-type', '-m',
        type=str,
        help='Filter by mark type (e.g., H3K27me3)'
    )
    parser.add_argument(
        '--species-id', '-s',
        type=int,
        default=1,
        help='Species ID (1=human, default: 1)'
    )
    parser.add_argument(
        '--convert-bigbed',
        action='store_true',
        help='Convert BED files to BigBed format after export'
    )
    parser.add_argument(
        '--chrom-sizes',
        type=str,
        default=os.environ.get('CHROM_SIZES', './data/genomes/hg19.chrom.sizes'),
        help='Path to chromosome sizes file (env: CHROM_SIZES)'
    )
    parser.add_argument(
        '--bigbed-tool',
        type=str,
        default=os.environ.get('BIGBED_TOOL', 'bedToBigBed'),
        help='Path to bedToBigBed executable (env: BIGBED_TOOL)'
    )
    parser.add_argument(
        '--bigbed-output-dir',
        type=str,
        default=os.environ.get('BIGBED_OUTPUT_DIR', './data/genomes'),
        help='Output directory for BigBed files (env: BIGBED_OUTPUT_DIR)'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("ChIP-seq BED/BigBed Export Tool")
    print("=" * 60)
    print(f"Output directory: {args.output_dir}")
    print(f"Cell type filter: {args.cell_type or 'All'}")
    print(f"Mark type filter: {args.mark_type or 'All'}")
    print(f"Species ID: {args.species_id}")
    print(f"Convert to BigBed: {args.convert_bigbed}")
    print("=" * 60)

    # Step 1: Export BED files
    print("\n📤 Step 1: Exporting BED files...")
    exported_files = export_chipseq_bed(
        output_dir=args.output_dir,
        cell_type=args.cell_type,
        mark_type=args.mark_type,
        species_id=args.species_id
    )

    if not exported_files:
        print("❌ No files exported!")
        return 1

    # Step 2: Convert to BigBed (optional)
    if args.convert_bigbed:
        print("\n📦 Step 2: Converting to BigBed format...")

        # Check chrom.sizes file exists
        if not Path(args.chrom_sizes).exists():
            print(f"❌ Chromosome sizes file not found: {args.chrom_sizes}")
            return 1

        # Check bedToBigBed exists
        if not Path(args.bigbed_tool).exists():
            print(f"❌ bedToBigBed tool not found: {args.bigbed_tool}")
            return 1

        bigbed_files = []
        for cell_type, bed_file in exported_files.items():
            # Sort BED file
            sorted_bed = sort_bed_file(bed_file)

            # Convert to BigBed
            bb_file = convert_to_bigbed(
                sorted_bed,
                args.chrom_sizes,
                args.bigbed_output_dir,
                args.bigbed_tool
            )

            if bb_file:
                bigbed_files.append(bb_file)

            # Clean up sorted file
            Path(sorted_bed).unlink(missing_ok=True)

        print(f"\n✅ Created {len(bigbed_files)} BigBed files in {args.bigbed_output_dir}")
        for bb in bigbed_files:
            print(f"  - {Path(bb).name}")

    print("\n✨ Export complete!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
