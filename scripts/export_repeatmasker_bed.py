#!/usr/bin/env python3
"""
Export RepeatMasker data to BED6 format for bigBed conversion

Usage:
    python3 export_repeatmasker_bed.py --species 1 --output repeatmasker_human.bed
"""
import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "frontend" / "backend"))

from app.core.database import SessionLocal
from app.models.models import GenomicFeature, FeatureTrack, Species
from sqlalchemy import and_


def export_repeatmasker_bed(species_id: int, output_file: str):
    """
    Export RepeatMasker annotations as BED6 format

    BED6 format: chrom, chromStart, chromEnd, name, score, strand
    - name: repeat_name (e.g., AluSx, L1M2)
    - score: scaled from divergence (0 = high divergence, 1000 = perfect match)
    - strand: +/-/.
    """
    db = SessionLocal()

    try:
        # Get species info
        species = db.query(Species).filter(Species.species_id == species_id).first()
        if not species:
            raise ValueError(f"Species {species_id} not found")

        print(f"Exporting RepeatMasker for {species.display_name}...")

        # Get RepeatMasker track
        track = db.query(FeatureTrack).filter(
            FeatureTrack.track_name == 'repeatmasker_repeats'
        ).first()

        if not track:
            raise ValueError("RepeatMasker track not found in database")

        track_id = track.track_id

        # Query all RepeatMasker features for this species
        # Order by chromosome and position for better compression
        query = (
            db.query(GenomicFeature)
            .filter(GenomicFeature.track_id == track_id)
            .filter(GenomicFeature.species_id == species_id)
            .order_by(GenomicFeature.chromosome, GenomicFeature.feature_start)
        )

        total_count = query.count()
        print(f"Total features to export: {total_count:,}")

        # Write BED file
        with open(output_file, 'w') as f:
            batch_size = 50000
            processed = 0

            for feature in query.yield_per(batch_size):
                # Extract attributes
                attrs = feature.attributes or {}
                repeat_name = feature.feature_name or 'Unknown'
                divergence = attrs.get('divergence', 0)
                strand = attrs.get('strand', '.')

                # Convert divergence to score (0-1000)
                # Lower divergence = higher conservation = higher score
                # divergence range: 0-50%, map to score 1000-0
                score = max(0, min(1000, int(1000 * (1 - divergence / 50))))

                # Write BED6 line
                # Format: chrom, chromStart, chromEnd, name, score, strand
                f.write(f"{feature.chromosome}\t{feature.feature_start}\t{feature.feature_end}\t{repeat_name}\t{score}\t{strand}\n")

                processed += 1
                if processed % 500000 == 0:
                    print(f"  Processed {processed:,} / {total_count:,} ({100*processed/total_count:.1f}%)")

        print(f"✅ Exported {processed:,} features to {output_file}")

        # Get file size
        file_size = Path(output_file).stat().st_size
        print(f"   File size: {file_size / 1024 / 1024:.1f} MB")

    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Export RepeatMasker to BED format')
    parser.add_argument('--species', type=int, required=True, help='Species ID (1=human, 2=chimp, 3=macaque, 4=marmoset)')
    parser.add_argument('--output', type=str, required=True, help='Output BED file path')

    args = parser.parse_args()

    export_repeatmasker_bed(args.species, args.output)
