#!/usr/bin/env python3
"""
Download ENCODE histone modification ChIP-seq data from UCSC.

This script downloads broadPeak files from the Broad Histone track
for multiple cell lines and histone marks.

Usage:
    python3 download_encode_chipseq.py --all --output encode_data/
    python3 download_encode_chipseq.py --mark H3K27me3 --cell-line GM12878
"""

import argparse
import subprocess
from pathlib import Path
from typing import List, Optional
import json


# UCSC ENCODE Histone base URLs
BASE_URL_BROAD = 'http://hgdownload.soe.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeBroadHistone/'
BASE_URL_UW = 'http://hgdownload.soe.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeUwHistone/'
# Legacy URL (kept for backward compatibility)
BASE_URL = BASE_URL_BROAD

# File naming pattern: wgEncodeBroadHistone{CellLine}{Mark}{Replicate}.broadPeak.gz
# Example: wgEncodeBroadHistoneGm12878H3k27me3StdPk.broadPeak.gz

ENCODE_FILES = {
    'GM12878': {
        'H3K27me3': {
            'file': 'wgEncodeBroadHistoneGm12878H3k27me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k27me3StdPk.broadPeak.gz',
            'size_mb': 2.1,
        },
        'H3K4me1': {
            'file': 'wgEncodeBroadHistoneGm12878H3k4me1StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k4me1StdPk.broadPeak.gz',
            'size_mb': 5.1,
        },
        'H3K4me3': {
            'file': 'wgEncodeBroadHistoneGm12878H3k4me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k4me3StdPk.broadPeak.gz',
            'size_mb': 1.8,
        },
        'H3K27ac': {
            'file': 'wgEncodeBroadHistoneGm12878H3k27acStdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k27acStdPk.broadPeak.gz',
            'size_mb': 4.5,
        },
        'H3K36me3': {
            'file': 'wgEncodeBroadHistoneGm12878H3k36me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k36me3StdPk.broadPeak.gz',
        },
        'H3K9me3': {
            'file': 'wgEncodeBroadHistoneGm12878H3k9me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k9me3StdPk.broadPeak.gz',
        },
        # Phase 5 新增 marks
        'H3K9ac': {
            'file': 'wgEncodeBroadHistoneGm12878H3k9acStdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k9acStdPk.broadPeak.gz',
            'size_mb': 3.0,
        },
        'H3K4me2': {
            'file': 'wgEncodeBroadHistoneGm12878H3k4me2StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k4me2StdPk.broadPeak.gz',
            'size_mb': 4.0,
        },
    },
    'H1-hESC': {
        'H3K27me3': {
            'file': 'wgEncodeBroadHistoneH1hescH3k27me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k27me3StdPk.broadPeak.gz',
            'size_mb': 1.5,
        },
        'H3K4me1': {
            'file': 'wgEncodeBroadHistoneH1hescH3k4me1StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k4me1StdPk.broadPeak.gz',
            'size_mb': 4.2,
        },
        'H3K4me3': {
            'file': 'wgEncodeBroadHistoneH1hescH3k4me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k4me3StdPk.broadPeak.gz',
            'size_mb': 1.2,
        },
        'H3K27ac': {
            'file': 'wgEncodeBroadHistoneH1hescH3k27acStdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k27acStdPk.broadPeak.gz',
            'size_mb': 3.8,
        },
        'H3K36me3': {
            'file': 'wgEncodeBroadHistoneH1hescH3k36me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k36me3StdPk.broadPeak.gz',
        },
        'H3K9me3': {
            # 注意：UCSC 使用 H3k09me3（带 0），不是 H3k9me3
            'file': 'wgEncodeBroadHistoneH1hescH3k09me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k09me3StdPk.broadPeak.gz',
        },
        # Phase 5 新增 marks
        'H3K9ac': {
            'file': 'wgEncodeBroadHistoneH1hescH3k9acStdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k9acStdPk.broadPeak.gz',
            'size_mb': 2.5,
        },
        'H3K4me2': {
            'file': 'wgEncodeBroadHistoneH1hescH3k4me2StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k4me2StdPk.broadPeak.gz',
            'size_mb': 3.5,
        },
    },
    'K562': {
        'H3K27me3': {
            'file': 'wgEncodeBroadHistoneK562H3k27me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k27me3StdPk.broadPeak.gz',
            'size_mb': 2.3,
        },
        'H3K4me1': {
            'file': 'wgEncodeBroadHistoneK562H3k4me1StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k4me1StdPk.broadPeak.gz',
            'size_mb': 4.8,
        },
        'H3K4me3': {
            'file': 'wgEncodeBroadHistoneK562H3k4me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k4me3StdPk.broadPeak.gz',
            'size_mb': 1.6,
        },
        'H3K27ac': {
            'file': 'wgEncodeBroadHistoneK562H3k27acStdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k27acStdPk.broadPeak.gz',
            'size_mb': 4.2,
        },
        'H3K36me3': {
            'file': 'wgEncodeBroadHistoneK562H3k36me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k36me3StdPk.broadPeak.gz',
        },
        'H3K9me3': {
            'file': 'wgEncodeBroadHistoneK562H3k9me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k9me3StdPk.broadPeak.gz',
        },
        # Phase 5 新增 marks（UCSC hg19/Broad Histone 也可用）
        'H3K9ac': {
            'file': 'wgEncodeBroadHistoneK562H3k9acStdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k9acStdPk.broadPeak.gz',
        },
        'H3K4me2': {
            'file': 'wgEncodeBroadHistoneK562H3k4me2StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k4me2StdPk.broadPeak.gz',
        },
    },
    'HepG2': {
        'H3K27me3': {
            'file': 'wgEncodeBroadHistoneHepg2H3k27me3StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k27me3StdPk.broadPeak.gz',
        },
        'H3K4me1': {
            # 注意：UCSC 使用 H3k04me1（带 0），不是 H3k4me1
            'file': 'wgEncodeBroadHistoneHepg2H3k04me1StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k04me1StdPk.broadPeak.gz',
        },
        'H3K4me3': {
            'file': 'wgEncodeBroadHistoneHepg2H3k4me3StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k4me3StdPk.broadPeak.gz',
        },
        'H3K27ac': {
            'file': 'wgEncodeBroadHistoneHepg2H3k27acStdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k27acStdPk.broadPeak.gz',
        },
        'H3K36me3': {
            'file': 'wgEncodeBroadHistoneHepg2H3k36me3StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k36me3StdPk.broadPeak.gz',
        },
        'H3K9me3': {
            # 注意：UCSC HepG2 的 H3K9me3 文件是 Pk（无 Std），且为 H3k09me3（带 0）
            'file': 'wgEncodeBroadHistoneHepg2H3k09me3Pk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k09me3Pk.broadPeak.gz',
            'size_mb': 0.9,
        },
        'H3K9ac': {
            'file': 'wgEncodeBroadHistoneHepg2H3k9acStdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k9acStdPk.broadPeak.gz',
        },
        'H3K4me2': {
            'file': 'wgEncodeBroadHistoneHepg2H3k4me2StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k4me2StdPk.broadPeak.gz',
        },
    },
    # MCF-7: Breast adenocarcinoma cell line (UW Histone track - limited data)
    'MCF-7': {
        'H3K4me3': {
            'file': 'wgEncodeUwHistoneMcf7H3k4me3StdHotspotsRep1.broadPeak.gz',
            'url': BASE_URL_UW + 'wgEncodeUwHistoneMcf7H3k4me3StdHotspotsRep1.broadPeak.gz',
            'size_mb': 0.5,
        },
    },
    # HMEC: Human mammary epithelial cells (Broad Histone track - full data)
    'HMEC': {
        'H3K4me1': {
            'file': 'wgEncodeBroadHistoneHmecH3k4me1StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHmecH3k4me1StdPk.broadPeak.gz',
            'size_mb': 5.0,
        },
        'H3K4me3': {
            'file': 'wgEncodeBroadHistoneHmecH3k4me3StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHmecH3k4me3StdPk.broadPeak.gz',
            'size_mb': 1.5,
        },
        'H3K9me3': {
            'file': 'wgEncodeBroadHistoneHmecH3k09me3Pk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHmecH3k09me3Pk.broadPeak.gz',
            'size_mb': 2.0,
        },
        'H3K27me3': {
            'file': 'wgEncodeBroadHistoneHmecH3k27me3StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHmecH3k27me3StdPk.broadPeak.gz',
            'size_mb': 2.5,
        },
        'H3K27ac': {
            'file': 'wgEncodeBroadHistoneHmecH3k27acStdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHmecH3k27acStdPk.broadPeak.gz',
            'size_mb': 4.0,
        },
        'H3K36me3': {
            'file': 'wgEncodeBroadHistoneHmecH3k36me3StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHmecH3k36me3StdPk.broadPeak.gz',
            'size_mb': 3.0,
        },
    },
}

# Metadata for each cell line
CELL_LINE_METADATA = {
    'GM12878': {
        'tissue_type': 'blood',
        'cell_type': 'B-lymphocyte',
        'description': 'B-lymphoblastoid cell line',
        'category': 'normal',
    },
    'H1-hESC': {
        'tissue_type': 'embryonic_stem_cell',
        'cell_type': 'embryonic_stem_cell',
        'description': 'Human embryonic stem cells',
        'category': 'stem_cell',
    },
    'K562': {
        'tissue_type': 'blood',
        'cell_type': 'erythroleukemia',
        'description': 'Chronic myelogenous leukemia',
        'category': 'cancer',
    },
    'HepG2': {
        'tissue_type': 'liver',
        'cell_type': 'hepatocellular_carcinoma',
        'description': 'Hepatocellular carcinoma cell line',
        'category': 'cancer',
    },
    'MCF-7': {
        'tissue_type': 'breast',
        'cell_type': 'breast_adenocarcinoma',
        'description': 'Breast adenocarcinoma cell line',
        'category': 'cancer',
    },
    'HMEC': {
        'tissue_type': 'breast',
        'cell_type': 'mammary_epithelial',
        'description': 'Human mammary epithelial cells',
        'category': 'normal',
    },
}


def download_file(url: str, output_path: Path, *, dry_run: bool = False, min_bytes: Optional[int] = None) -> bool:
    """Download a file using wget"""
    if dry_run:
        print(f'  [DRY RUN] Would download: {url}')
        return True

    print(f'  Downloading: {output_path.name} ...')
    try:
        result = subprocess.run(
            ['wget', '-q', '--show-progress', '-O', str(output_path), url],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes timeout
        )
        if result.returncode == 0:
            if min_bytes is not None:
                try:
                    size = output_path.stat().st_size
                except OSError as e:
                    print(f'  ✗ Cannot stat downloaded file: {e}')
                    return False

                if size < min_bytes:
                    print(
                        f'  ✗ Downloaded file too small: {size} bytes '
                        f'(expected >= {min_bytes} bytes). '
                        'Possible truncated download or error page.'
                    )
                    try:
                        output_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                    return False

            print(f'  ✓ Downloaded: {output_path.name}')
            return True
        else:
            print(f'  ✗ Failed: {result.stderr}')
            return False
    except Exception as e:
        print(f'  ✗ Error: {e}')
        return False


def generate_metadata(mark_type: str, cell_line: str, file_info: dict) -> dict:
    """Generate metadata JSON for an experiment"""
    cell_info = CELL_LINE_METADATA[cell_line]

    # Determine data source based on URL
    url = file_info['url']
    if 'UwHistone' in url or 'wgEncodeUw' in url:
        source_database = 'ENCODE_UW'
        antibody_source = 'University of Washington'
        encode_accession = f'UW_{cell_line}_{mark_type}'
        biosample_accession = f'UW_BS_{cell_line}'
    else:
        source_database = 'ENCODE_Broad'
        antibody_source = 'Broad Institute'
        encode_accession = f'BROAD_{cell_line}_{mark_type}'
        biosample_accession = f'BROAD_BS_{cell_line}'

    metadata = {
        'mark_type': mark_type,
        'encode_accession': encode_accession,
        'biosample_accession': biosample_accession,
        'tissue_type': cell_info['tissue_type'],
        'cell_type': cell_info['cell_type'],
        'cell_line': cell_line,
        'category': cell_info.get('category', 'unknown'),
        'treatment': None,
        'developmental_stage': 'embryonic' if cell_line == 'H1-hESC' else 'adult',
        'antibody_target': mark_type,
        'antibody_source': antibody_source,
        'replicate_type': 'pooled',
        'source_database': source_database,
        'peak_type': 'broad',
        'genome_assembly': 'hg19',
        'data_source': 'UCSC_ENCODE',
        'download_url': url,
    }

    return metadata


def download_mark_data(mark_type: str, cell_lines: List[str], output_dir: Path, dry_run: bool = False):
    """Download data for a specific mark type across multiple cell lines"""
    print(f'\n{"="*60}')
    print(f'Mark: {mark_type}')
    print(f'{"="*60}')

    downloaded = []

    for cell_line in cell_lines:
        if cell_line not in ENCODE_FILES:
            print(f'  ⚠️  {cell_line} not available')
            continue

        if mark_type not in ENCODE_FILES[cell_line]:
            print(f'  ⚠️  {mark_type} not available for {cell_line}')
            continue

        file_info = ENCODE_FILES[cell_line][mark_type]

        print(f'\n  Cell line: {cell_line}')
        size_mb = file_info.get("size_mb")
        if size_mb is not None:
            print(f'  File size: ~{size_mb} MB')
        else:
            print('  File size: unknown')

        # Download peaks file
        peaks_filename = file_info['file']
        peaks_path = output_dir / peaks_filename

        expected_mb_raw = file_info.get("size_mb")
        expected_mb = float(expected_mb_raw) if expected_mb_raw is not None else 0.0
        # Allow some variance; this is a sanity guard against empty/error-page downloads.
        if expected_mb > 0:
            min_bytes = int(expected_mb * 1024 * 1024 * 0.5)
        else:
            # 没有 size_mb 时，给一个保守的下限（避免拿到 404/HTML 错误页也“下载成功”）
            min_bytes = 200 * 1024

        if download_file(file_info['url'], peaks_path, dry_run=dry_run, min_bytes=min_bytes):
            # Generate metadata
            metadata = generate_metadata(mark_type, cell_line, file_info)
            metadata_path = output_dir / f'{mark_type}_{cell_line}_metadata.json'

            if dry_run:
                print(f'  [DRY RUN] Would write metadata: {metadata_path.name}')
            else:
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)

                print(f'  ✓ Metadata: {metadata_path.name}')

            downloaded.append({
                'mark_type': mark_type,
                'cell_line': cell_line,
                'peaks_file': str(peaks_path),
                'metadata_file': str(metadata_path),
            })

    return downloaded


def generate_batch_import_config(experiments: List[dict], output_dir: Path):
    """Generate batch import configuration file"""
    config = {
        'species': 'human',
        'experiments': experiments,
        'options': {
            'batch_size': 10000,
            'compute_associations': True,
            'parallel': 3,
        }
    }

    config_file = output_dir / 'encode_batch_import_config.json'
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    print(f'\n{"="*60}')
    print('✓ Batch import config generated')
    print(f'{"="*60}')
    print(f'Config file: {config_file}')
    print(f'Total experiments: {len(experiments)}')

    return config_file


def parse_args():
    parser = argparse.ArgumentParser(
        description='Download ENCODE histone modification data from UCSC',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all Phase 2.4 marks for GM12878
  python3 download_encode_chipseq.py --all --cell-line GM12878

  # Download H3K27me3 for multiple cell lines
  python3 download_encode_chipseq.py --mark H3K27me3 --cell-line GM12878 K562 H1-hESC

  # Dry run to see what would be downloaded
  python3 download_encode_chipseq.py --all --cell-line GM12878 --dry-run
        """
    )

    parser.add_argument('--mark', choices=['H3K27me3', 'H3K4me1', 'H3K4me3', 'H3K27ac', 'H3K9me3', 'H3K36me3', 'H3K9ac', 'H3K4me2'],
                        help='Mark type to download')
    parser.add_argument('--cell-line', nargs='+', default=['GM12878'],
                        choices=list(ENCODE_FILES.keys()),
                        help='Cell lines to download (default: GM12878)')
    parser.add_argument('--all', action='store_true',
                        help='Download all available marks for selected cell lines')
    parser.add_argument('--output', default='encode_chipseq_data',
                        help='Output directory (default: encode_chipseq_data)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be downloaded without actually downloading')

    return parser.parse_args()


def main():
    args = parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print('='*60)
    print('ENCODE Histone Modification Data Downloader')
    print('='*60)
    print('Source: UCSC Broad Histone (hg19)')
    print(f'Output: {output_dir}')
    print(f'Cell lines: {", ".join(args.cell_line)}')
    if args.dry_run:
        print('Mode: DRY RUN (no actual downloads)')

    all_experiments = []

    if args.all:
        # Collect all available marks across selected cell lines
        available_marks = set()
        for cell_line in args.cell_line:
            if cell_line in ENCODE_FILES:
                available_marks.update(ENCODE_FILES[cell_line].keys())

        # Download all available marks
        for mark in sorted(available_marks):
            experiments = download_mark_data(mark, args.cell_line, output_dir, args.dry_run)
            all_experiments.extend(experiments)
    else:
        if not args.mark:
            print('Error: --mark is required when not using --all')
            return 1

        experiments = download_mark_data(args.mark, args.cell_line, output_dir, args.dry_run)
        all_experiments.extend(experiments)

    # Generate batch import config
    if all_experiments and not args.dry_run:
        config_file = generate_batch_import_config(all_experiments, output_dir)
        print('\n✨ Ready to import!')
        print(f'   Next: python3 scripts/batch_import_chipseq.py {config_file}')
    elif args.dry_run:
        print('\n📋 Dry run complete. Run without --dry-run to download.')
        print(f'   Total files to download: {len(all_experiments)}')
        total_size = 0.0
        unknown_sizes = 0
        for exp in all_experiments:
            size_mb = ENCODE_FILES[exp['cell_line']][exp['mark_type']].get('size_mb')
            if size_mb is None:
                unknown_sizes += 1
                continue
            try:
                total_size += float(size_mb)
            except (TypeError, ValueError):
                unknown_sizes += 1

        if unknown_sizes > 0:
            print(f'   Estimated total size: >= {total_size:.1f} MB (+{unknown_sizes} unknown)')
        else:
            print(f'   Estimated total size: ~{total_size:.1f} MB')


if __name__ == '__main__':
    main()
