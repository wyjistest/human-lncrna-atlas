#!/usr/bin/env python3
"""
Convert FANTOM CAT GTF to BED12 format with exon structure.
Groups exons by transcript_id to create proper block structure.

BED12 Format:
1. chrom       - Chromosome name
2. chromStart  - Start position (0-based)
3. chromEnd    - End position
4. name        - Gene|Transcript ID
5. score       - TIE Score (0-1000)
6. strand      - + or -
7. thickStart  - CDS start (same as chromStart for lncRNA)
8. thickEnd    - CDS end (same as chromStart for lncRNA - no CDS)
9. itemRgb     - RGB color value
10. blockCount - Number of exons
11. blockSizes - Comma-separated exon sizes
12. blockStarts- Comma-separated exon starts (relative to chromStart)
"""

import re
import sys
from collections import defaultdict
from typing import Dict, List, Tuple


def parse_gtf_attributes(attr_string: str) -> Dict[str, str]:
    """Parse GTF attribute string into dictionary."""
    attrs = {}
    for match in re.finditer(r'(\w+)\s+"([^"]+)"', attr_string):
        attrs[match.group(1)] = match.group(2)
    return attrs


def gtf_to_bed12(gtf_file: str, output_file: str):
    """
    Convert GTF to BED12 format.

    Groups exons by transcript_id and creates block structure.
    """
    # Store transcript info and exons
    transcripts = {}  # transcript_id -> {chrom, strand, gene_id, score}
    exons = defaultdict(list)  # transcript_id -> [(start, end), ...]

    print(f"Reading GTF file: {gtf_file}")
    line_count = 0
    transcript_count = 0
    exon_count = 0

    with open(gtf_file, 'r') as f:
        for line in f:
            line_count += 1
            if line_count % 500000 == 0:
                print(f"  Processed {line_count:,} lines...")

            if line.startswith('#'):
                continue

            fields = line.strip().split('\t')
            if len(fields) < 9:
                continue

            chrom, source, feature, start, end, score, strand, frame, attributes = fields
            start, end = int(start), int(end)

            attrs = parse_gtf_attributes(attributes)
            transcript_id = attrs.get('transcript_id')

            if not transcript_id:
                continue

            if feature == 'transcript':
                transcript_count += 1
                # Store transcript metadata
                gene_id = attrs.get('gene_id', '')
                tie_score = attrs.get('TIEScore', '0')
                coding_status = attrs.get('coding_status', 'nonCoding')
                gene_class = attrs.get('geneClass', '')

                try:
                    score_val = float(tie_score)
                except ValueError:
                    score_val = 0

                transcripts[transcript_id] = {
                    'chrom': chrom,
                    'strand': strand,
                    'gene_id': gene_id,
                    'score': int(min(1000, score_val * 10)),  # Scale to 0-1000
                    'start': start,
                    'end': end,
                    'coding_status': coding_status,
                    'gene_class': gene_class
                }

            elif feature == 'exon':
                exon_count += 1
                # Store exon coordinates (GTF is 1-based, BED is 0-based)
                exons[transcript_id].append((start - 1, end))

    print(f"Parsed {line_count:,} lines")
    print(f"Found {transcript_count:,} transcripts")
    print(f"Found {exon_count:,} exons")
    print(f"Transcripts with exon info: {len(transcripts):,}")

    # Write BED12 output
    bed_records = []

    for transcript_id, info in transcripts.items():
        exon_list = exons.get(transcript_id, [])

        if not exon_list:
            # Single-exon transcript (use transcript coordinates)
            exon_list = [(info['start'] - 1, info['end'])]

        # Sort exons by start position
        exon_list.sort(key=lambda x: x[0])

        chrom = info['chrom']
        strand = info['strand']
        gene_id = info['gene_id']
        score = info['score']
        coding_status = info['coding_status']

        # Calculate transcript boundaries from exons
        chrom_start = min(e[0] for e in exon_list)
        chrom_end = max(e[1] for e in exon_list)

        # For lncRNA: thickStart = thickEnd = chromStart (no CDS)
        # This creates a thin line with no thick blocks in IGV
        thick_start = chrom_start
        thick_end = chrom_start  # No thick region for non-coding

        # RGB color based on coding status
        # Blue for lncRNA, green for coding
        if coding_status == 'coding':
            item_rgb = "0,128,0"  # Green for coding
        else:
            item_rgb = "74,144,217"  # Blue for lncRNA

        # Block information
        block_count = len(exon_list)
        block_sizes = ','.join(str(e[1] - e[0]) for e in exon_list)
        block_starts = ','.join(str(e[0] - chrom_start) for e in exon_list)

        # Name: 只显示 gene_id (更简洁)
        # IGV.js 会在 track 上直接显示这个名字
        name = gene_id

        bed_records.append((
            chrom, chrom_start, chrom_end, name, score, strand,
            thick_start, thick_end, item_rgb,
            block_count, block_sizes, block_starts
        ))

    # Sort by chromosome and position
    def sort_key(record):
        chrom = record[0]
        # Extract chromosome number for natural sort
        if chrom.startswith('chr'):
            chrom_part = chrom[3:]
            if chrom_part.isdigit():
                return (0, int(chrom_part), record[1])
            elif chrom_part == 'X':
                return (1, 0, record[1])
            elif chrom_part == 'Y':
                return (1, 1, record[1])
            elif chrom_part == 'M':
                return (1, 2, record[1])
        return (2, 0, record[1])

    print("Sorting records...")
    bed_records.sort(key=sort_key)

    # Write output
    print(f"Writing BED12 to: {output_file}")
    with open(output_file, 'w') as f:
        for record in bed_records:
            f.write('\t'.join(str(x) for x in record) + '\n')

    print(f"\nDone! Wrote {len(bed_records):,} transcripts")

    # Print statistics
    multi_exon = sum(1 for tid in transcripts if len(exons.get(tid, [])) > 1)
    single_exon = len(bed_records) - multi_exon

    # Count by exon number
    exon_distribution = defaultdict(int)
    for tid in transcripts:
        exon_count = len(exons.get(tid, []))
        if exon_count == 0:
            exon_count = 1  # Treated as single exon
        exon_distribution[exon_count] += 1

    print(f"\n=== Statistics ===")
    print(f"Total transcripts: {len(bed_records):,}")
    print(f"Multi-exon transcripts: {multi_exon:,} ({100*multi_exon/len(bed_records):.1f}%)")
    print(f"Single-exon transcripts: {single_exon:,} ({100*single_exon/len(bed_records):.1f}%)")

    print(f"\nExon count distribution (top 10):")
    for count in sorted(exon_distribution.keys())[:10]:
        num = exon_distribution[count]
        print(f"  {count} exon(s): {num:,} transcripts ({100*num/len(bed_records):.1f}%)")

    # Max exons
    max_exons = max(exon_distribution.keys())
    print(f"  Max exons: {max_exons} ({exon_distribution[max_exons]} transcripts)")

    return len(bed_records), multi_exon, single_exon


if __name__ == '__main__':
    gtf_file = '/data/wenyujianData/humanLncAtlas/FANTOM_CAT.lv3_robust.gtf'
    output_file = '/data/wenyujianData/humanLncAtlas/genomes/fantom_cat_transcripts_bed12.bed'

    gtf_to_bed12(gtf_file, output_file)
