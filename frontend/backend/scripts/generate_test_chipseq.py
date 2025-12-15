#!/usr/bin/env python3
"""
Generate synthetic ChIP-seq test data for Phase 2.4 validation.

This script generates realistic narrowPeak format data for testing the
ChIP-seq architecture without requiring ENCODE data downloads.

Usage:
    python3 generate_test_chipseq.py --mark H3K27me3 --peaks 500 --output test_data/
    python3 generate_test_chipseq.py --all --peaks-per-mark 300
"""

import argparse
import random
import json
from pathlib import Path
from typing import Tuple


# Chromosome sizes (hg19, selected chromosomes)
CHROM_SIZES = {
    'chr1': 249250621,
    'chr2': 243199373,
    'chr3': 198022430,
    'chr5': 180915260,
    'chr7': 159138663,
    'chr10': 135534747,
    'chr12': 133851895,
    'chr17': 81195210,
    'chrX': 155270560,
}

# Mark-specific parameters
MARK_PARAMS = {
    'H3K27me3': {
        'mark_category': 'repressive',
        'peak_type': 'broad',
        'avg_width': 2500,  # Broad peaks
        'avg_signal': 35.0,
        'avg_fold': 6.5,
        'qvalue_range': (8, 15),  # -log10(q-value)
    },
    'H3K4me1': {
        'mark_category': 'enhancer',
        'peak_type': 'narrow',
        'avg_width': 500,  # Narrow peaks
        'avg_signal': 45.0,
        'avg_fold': 8.0,
        'qvalue_range': (10, 20),
    },
    'H3K4me3': {
        'mark_category': 'activating',
        'peak_type': 'narrow',
        'avg_width': 400,
        'avg_signal': 65.0,
        'avg_fold': 12.0,
        'qvalue_range': (12, 25),
    },
    'H3K27ac': {
        'mark_category': 'enhancer',
        'peak_type': 'narrow',
        'avg_width': 600,
        'avg_signal': 55.0,
        'avg_fold': 10.0,
        'qvalue_range': (10, 22),
    },
}

# Cell lines for testing
CELL_LINES = {
    'GM12878': {'tissue_type': 'blood', 'cell_type': 'B-lymphocyte'},
    'K562': {'tissue_type': 'blood', 'cell_type': 'erythroleukemia'},
    'H1-hESC': {'tissue_type': 'embryonic_stem_cell', 'cell_type': 'embryonic_stem_cell'},
}


def generate_peak(chrom: str, chrom_size: int, mark_params: dict, peak_id: int) -> Tuple[str, dict]:
    """
    Generate a single peak in narrowPeak format.

    Returns:
        Tuple of (narrowPeak line, peak attributes dict)
    """
    # Random genomic position
    width = int(random.gauss(mark_params['avg_width'], mark_params['avg_width'] * 0.3))
    width = max(100, min(10000, width))  # Clamp to reasonable range

    start = random.randint(10000, chrom_size - width - 10000)
    end = start + width

    # Signal values
    signal = abs(random.gauss(mark_params['avg_signal'], mark_params['avg_signal'] * 0.3))
    fold = abs(random.gauss(mark_params['avg_fold'], mark_params['avg_fold'] * 0.25))

    # P-value and Q-value (-log10 transformed)
    qvalue_min, qvalue_max = mark_params['qvalue_range']
    qvalue = random.uniform(qvalue_min, qvalue_max)
    pvalue = qvalue + random.uniform(1, 3)  # p-value is usually higher

    # Score (0-1000)
    score = min(1000, int(signal * 10))

    # Strand
    strand = random.choice(['+', '-'])

    # Peak summit (relative to start)
    summit = random.randint(int(width * 0.3), int(width * 0.7))

    # narrowPeak format (10 columns, tab-separated)
    # chrom  chromStart  chromEnd  name  score  strand  signalValue  pValue  qValue  peak
    line = '\t'.join([
        chrom,
        str(start),
        str(end),
        f'peak_{peak_id}',
        str(score),
        strand,
        f'{signal:.2f}',
        f'{pvalue:.2f}',
        f'{qvalue:.2f}',
        str(summit)
    ])

    attrs = {
        'chrom': chrom,
        'start': start,
        'end': end,
        'width': width,
        'signal': signal,
        'fold': fold,
        'qvalue': qvalue,
    }

    return line, attrs


def generate_experiment_metadata(mark_type: str, cell_line: str, replicate: int = 1) -> dict:
    """Generate experiment metadata JSON"""
    cell_info = CELL_LINES[cell_line]
    mark_params = MARK_PARAMS[mark_type]

    # Generate synthetic ENCODE accession
    encode_id = f'ENCSR{random.randint(100000, 999999)}'
    biosample_id = f'ENCBS{random.randint(100000, 999999)}'

    metadata = {
        'mark_type': mark_type,
        'mark_category': mark_params['mark_category'],
        'encode_accession': encode_id,
        'biosample_accession': biosample_id,
        'tissue_type': cell_info['tissue_type'],
        'cell_type': cell_info['cell_type'],
        'cell_line': cell_line,
        'treatment': None,
        'developmental_stage': 'adult' if cell_line != 'H1-hESC' else 'embryonic',
        'antibody_target': mark_type,
        'antibody_source': f'Abcam ab{random.randint(1000, 9999)}',
        'replicate_type': 'biological',
        'replicate_number': replicate,
        'total_reads': random.randint(30000000, 60000000),
        'mapped_reads': None,  # Will be calculated
        'mapping_rate': round(random.uniform(88.0, 96.0), 2),
        'frac_of_reads_in_peaks': round(random.uniform(10.0, 25.0), 2),
        'nsc': round(random.uniform(1.02, 1.15), 2),
        'rsc': round(random.uniform(0.85, 1.05), 2),
        'quality_score': round(random.uniform(75.0, 95.0), 1),
        'peak_type': mark_params['peak_type'],
        'source_database': 'TEST_DATA',
        'genome_assembly': 'hg19',
    }

    # Calculate mapped_reads
    metadata['mapped_reads'] = int(metadata['total_reads'] * metadata['mapping_rate'] / 100)

    return metadata


def generate_test_data(mark_type: str, num_peaks: int, cell_line: str, output_dir: Path):
    """
    Generate test data for a single mark type.

    Args:
        mark_type: H3K27me3, H3K4me1, H3K4me3, or H3K27ac
        num_peaks: Number of peaks to generate
        cell_line: GM12878, K562, or H1-hESC
        output_dir: Output directory for files
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    mark_params = MARK_PARAMS[mark_type]

    # Generate metadata
    metadata = generate_experiment_metadata(mark_type, cell_line)

    # Generate peaks
    peaks_file = output_dir / f'{mark_type}_{cell_line}_peaks.narrowPeak'
    metadata_file = output_dir / f'{mark_type}_{cell_line}_metadata.json'

    print(f'\n{"="*60}')
    print(f'Generating {mark_type} test data for {cell_line}')
    print(f'{"="*60}')
    print(f'Peaks: {num_peaks}')
    print(f'Peak type: {mark_params["peak_type"]}')
    print(f'Avg width: {mark_params["avg_width"]} bp')
    print(f'Output: {peaks_file}')

    with open(peaks_file, 'w') as f:
        # Write header (optional)
        f.write(f'# {mark_type} ChIP-seq peaks for {cell_line} (TEST DATA)\n')
        f.write(f'# {num_peaks} peaks generated\n')

        peak_id = 1
        chroms = list(CHROM_SIZES.keys())

        for _ in range(num_peaks):
            # Distribute peaks across chromosomes
            chrom = random.choice(chroms)
            chrom_size = CHROM_SIZES[chrom]

            line, attrs = generate_peak(chrom, chrom_size, mark_params, peak_id)
            f.write(line + '\n')
            peak_id += 1

    # Write metadata
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f'✓ Generated {peaks_file.name}')
    print(f'✓ Generated {metadata_file.name}')

    return peaks_file, metadata_file


def generate_all_phase24_data(output_dir: Path, peaks_per_mark: int = 300):
    """
    Generate test data for all Phase 2.4 marks.

    Phase 2.4 marks:
    - H3K27me3 (baseline from Phase 2.3)
    - H3K4me1 (new)
    - H3K4me3 (new)
    - H3K27ac (new)
    """
    output_dir = Path(output_dir)

    marks_to_generate = [
        ('H3K27me3', 'GM12878', peaks_per_mark),
        ('H3K4me1', 'GM12878', peaks_per_mark),
        ('H3K4me3', 'GM12878', peaks_per_mark),
        ('H3K27ac', 'GM12878', peaks_per_mark),
        # Optional: Add more cell lines for diversity
        ('H3K27me3', 'K562', int(peaks_per_mark * 0.8)),
        ('H3K4me1', 'K562', int(peaks_per_mark * 0.8)),
    ]

    generated_files = []

    for mark, cell_line, num_peaks in marks_to_generate:
        peaks_file, metadata_file = generate_test_data(mark, num_peaks, cell_line, output_dir)
        generated_files.append({
            'mark_type': mark,
            'cell_line': cell_line,
            'peaks_file': str(peaks_file),
            'metadata_file': str(metadata_file),
            'num_peaks': num_peaks
        })

    # Generate import config file
    config_file = output_dir / 'batch_import_config.json'
    config = {
        'species': 'human',
        'experiments': generated_files,
        'options': {
            'batch_size': 5000,
            'compute_associations': True,
            'parallel': 3
        }
    }

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    print(f'\n{"="*60}')
    print('✓ All test data generated')
    print(f'{"="*60}')
    print(f'Total experiments: {len(generated_files)}')
    print(f'Total peaks: {sum(e["num_peaks"] for e in generated_files)}')
    print(f'Config file: {config_file}')
    print('\nNext steps:')
    print(f'  1. Review generated files in {output_dir}/')
    print('  2. Import data:')
    print(f'     python3 scripts/batch_import_chipseq.py {config_file}')

    return config_file


def parse_args():
    parser = argparse.ArgumentParser(
        description='Generate synthetic ChIP-seq test data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 500 H3K27me3 peaks for GM12878
  python3 generate_test_chipseq.py --mark H3K27me3 --peaks 500 --cell-line GM12878

  # Generate all Phase 2.4 marks (H3K27me3, H3K4me1, H3K4me3, H3K27ac)
  python3 generate_test_chipseq.py --all --peaks-per-mark 300
        """
    )

    parser.add_argument('--mark', choices=list(MARK_PARAMS.keys()),
                        help='Mark type to generate')
    parser.add_argument('--peaks', type=int, default=500,
                        help='Number of peaks to generate (default: 500)')
    parser.add_argument('--cell-line', choices=list(CELL_LINES.keys()), default='GM12878',
                        help='Cell line (default: GM12878)')
    parser.add_argument('--output', default='test_chipseq_data',
                        help='Output directory (default: test_chipseq_data)')
    parser.add_argument('--all', action='store_true',
                        help='Generate all Phase 2.4 marks')
    parser.add_argument('--peaks-per-mark', type=int, default=300,
                        help='Peaks per mark when using --all (default: 300)')
    parser.add_argument('--seed', type=int,
                        help='Random seed for reproducibility')

    return parser.parse_args()


def main():
    args = parse_args()

    if args.seed:
        random.seed(args.seed)
        print(f'Using random seed: {args.seed}')

    output_dir = Path(args.output)

    if args.all:
        # Generate all Phase 2.4 marks
        config_file = generate_all_phase24_data(output_dir, args.peaks_per_mark)
        print('\n✨ Ready for Phase 2.4 validation!')
        print(f'   Config: {config_file}')
    else:
        # Generate single mark
        if not args.mark:
            print('Error: --mark is required when not using --all')
            return 1

        peaks_file, metadata_file = generate_test_data(
            args.mark,
            args.peaks,
            args.cell_line,
            output_dir
        )

        print('\n✨ Test data generated!')
        print('   Import with:')
        print('   python3 scripts/import_chipseq.py \\')
        print(f'       --input {peaks_file} \\')
        print(f'       --mark-type {args.mark} \\')
        print('       --species human \\')
        print(f'       --experiment-name "Test_{args.mark}_{args.cell_line}" \\')
        print(f'       --metadata {metadata_file} \\')
        print('       --compute-associations')


if __name__ == '__main__':
    main()
