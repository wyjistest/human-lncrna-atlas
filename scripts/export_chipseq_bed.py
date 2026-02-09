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
import re
import sys
from pathlib import Path
from typing import Optional, Dict
import subprocess

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "frontend" / "backend"))

from sqlalchemy import bindparam, text
from app.core.database import SessionLocal
from app.core.igv_utils import get_genome_reference
from app.core.genome_assembly import reference_genome_aliases


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
    cell_line: Optional[str] = None,
    mark_type: Optional[str] = None,
    species_id: int = 1,  # Human
    batch_size: int = 50000,
    group_by: str = "cell_type",
) -> Dict[str, str]:
    """
    Export ChIP-seq peaks as BED9 format files grouped by cell_type

    BED9 format: chrom, chromStart, chromEnd, name, score, strand, thickStart, thickEnd, itemRgb
    - name: mark_type|peak_name
    - score: scaled from fold_enrichment (0-1000)
    - strand: . (ChIP-seq peaks don't have strand)
    - thickStart/thickEnd: same as chromStart/chromEnd
    - itemRgb: color based on mark_type

    Returns dict of {group_value: output_file_path}
    """
    group_by = (group_by or "cell_type").strip().lower()
    if group_by not in {"cell_type", "cell_line"}:
        raise ValueError(f"Invalid group_by={group_by!r}; expected 'cell_type' or 'cell_line'")

    db = SessionLocal()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    exported_files: Dict[str, str] = {}

    try:
        # Determine expected assembly for this species (e.g. hg19 for human).
        # NOTE: 为保持向后兼容，reference_genome 为空时视为“未知”，默认允许通过；
        # 仅排除明确不匹配的实验（例如 GRCh38 在 hg19 项目里）。
        try:
            expected_assembly = get_genome_reference(species_id).id
        except Exception:
            expected_assembly = None

        allowed_ref_aliases = (
            sorted(reference_genome_aliases(expected_assembly)) if expected_assembly else []
        )

        group_expr = "e.cell_type" if group_by == "cell_type" else "e.cell_line"

        def safe_group_name(value: str) -> str:
            # 目标：兼容既有轨道命名（例如 MCF-7 -> MCF7，H1-hESC -> H1_hESC）
            safe = str(value).strip().replace(" ", "_").replace("-", "_")
            safe = re.sub(r"^([A-Za-z]+)_([0-9]+)$", r"\1\2", safe)  # MCF_7 -> MCF7
            return safe

        # Build query to get all peaks with experiment info
        sql = f"""
            SELECT
                p.chromosome,
                p.peak_start,
                p.peak_end,
                p.peak_name,
                p.fold_enrichment,
                m.mark_name,
                {group_expr} AS group_key
            FROM chipseq_peaks p
            JOIN chipseq_experiments e ON p.experiment_id = e.experiment_id
            JOIN epigenetic_mark_types m ON e.mark_type_id = m.mark_type_id
            WHERE p.species_id = :species_id
              AND e.is_active = TRUE
              AND (:cell_type IS NULL OR e.cell_type = :cell_type)
              AND (:cell_line IS NULL OR e.cell_line = :cell_line)
              AND (:mark_type IS NULL OR m.mark_name = :mark_type)
        """

        if allowed_ref_aliases:
            sql += """
              AND (
                e.reference_genome IS NULL
                OR lower(e.reference_genome) IN :allowed_ref_aliases
              )
            """

        sql += """
            ORDER BY group_key, p.chromosome, p.peak_start
        """

        query = (
            text(sql).bindparams(bindparam("allowed_ref_aliases", expanding=True))
            if allowed_ref_aliases
            else text(sql)
        )

        params = {
            'species_id': species_id,
            'cell_type': cell_type,
            'cell_line': cell_line,
            'mark_type': mark_type,
        }
        if allowed_ref_aliases:
            params["allowed_ref_aliases"] = allowed_ref_aliases

        result = db.execute(query, params)

        # Group by group_key and write to separate files
        current_group_value = None
        current_file = None
        processed = 0
        group_counts: Dict[str, int] = {}
        skipped_missing_group = 0

        for row in result:
            chrom, start, end, peak_name, fold_enrichment, mark_name, row_group_value = row

            # Skip invalid coordinates
            if not chrom or start is None or end is None:
                continue

            if row_group_value is None or not str(row_group_value).strip():
                skipped_missing_group += 1
                continue

            # Handle group change
            if row_group_value != current_group_value:
                if current_file:
                    current_file.close()
                    print(f"  ✅ {current_group_value}: {group_counts.get(str(current_group_value), 0):,} peaks")

                current_group_value = row_group_value
                safe_group = safe_group_name(str(row_group_value))
                output_file = output_path / f"chipseq_{safe_group}.bed"
                current_file = open(output_file, 'w')
                exported_files[str(row_group_value)] = str(output_file)
                group_counts[str(row_group_value)] = 0
                print(f"📝 Exporting {row_group_value} ({group_by})...")

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

            group_counts[str(row_group_value)] = group_counts.get(str(row_group_value), 0) + 1
            processed += 1

            if processed % 500000 == 0:
                print(f"  Processed {processed:,} peaks...")

        # Close last file
        if current_file:
            current_file.close()
            print(f"  ✅ {current_group_value}: {group_counts.get(str(current_group_value), 0):,} peaks")

        print(f"\n✅ Total exported: {processed:,} peaks to {len(exported_files)} files")
        if skipped_missing_group:
            print(f"⚠️ Skipped records with missing {group_by}: {skipped_missing_group:,}")

        # Print summary
        print(f"\n📊 Summary by {group_by}:")
        for key, count in sorted(group_counts.items()):
            print(f"  {key}: {count:,} peaks")

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

  # Export by cell line (recommended for chipseq_<CellLine>.bb)
  python3 export_chipseq_bed.py --group-by cell_line --output-dir ./chipseq_bed --convert-bigbed
        """
    )

    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default='./chipseq_bed',
        help='Output directory for BED files (default: ./chipseq_bed)'
    )
    parser.add_argument(
        '--group-by',
        type=str,
        choices=['cell_type', 'cell_line'],
        default=os.environ.get('CHIPSEQ_GROUP_BY', 'cell_type'),
        help="Group exported tracks by 'cell_type' (default) or 'cell_line' (recommended for IGV bigBed tracks)"
    )
    parser.add_argument(
        '--cell-type', '-c',
        type=str,
        help='Filter by cell type (e.g., K562, GM12878)'
    )
    parser.add_argument(
        '--cell-line',
        type=str,
        help='Filter by cell line (e.g., K562, GM12878, A549, HMEC, MCF-7)'
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
    print(f"Group by: {args.group_by}")
    print(f"Cell type filter: {args.cell_type or 'All'}")
    print(f"Cell line filter: {args.cell_line or 'All'}")
    print(f"Mark type filter: {args.mark_type or 'All'}")
    print(f"Species ID: {args.species_id}")
    print(f"Convert to BigBed: {args.convert_bigbed}")
    print("=" * 60)

    # Step 1: Export BED files
    print("\n📤 Step 1: Exporting BED files...")
    exported_files = export_chipseq_bed(
        output_dir=args.output_dir,
        cell_type=args.cell_type,
        cell_line=args.cell_line,
        mark_type=args.mark_type,
        species_id=args.species_id,
        group_by=args.group_by,
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
