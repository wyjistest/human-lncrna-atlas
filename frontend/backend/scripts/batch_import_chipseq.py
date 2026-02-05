#!/usr/bin/env python3
"""
Batch import multiple ChIP-seq experiments from a configuration file.

Usage:
    python3 batch_import_chipseq.py batch_import_config.json
    python3 batch_import_chipseq.py --config test_data/config.json --parallel 3
"""

import argparse
import json
import os
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


_SCRIPT_DIR = Path(__file__).resolve().parent
_IMPORT_SCRIPT = _SCRIPT_DIR / "import_chipseq.py"


def import_single_experiment(exp_config: dict, options: dict, db_options: dict) -> dict:
    """
    Import a single ChIP-seq experiment.

    Args:
        exp_config: {
            'mark_type': 'H3K27me3',
            'cell_line': 'GM12878',
            'peaks_file': 'path/to/peaks.narrowPeak',
            'metadata_file': 'path/to/metadata.json'
        }
        options: {
            'batch_size': 10000,
            'compute_associations': True
        }

    Returns:
        Result dict with success status and statistics
    """
    mark_type = exp_config['mark_type']
    cell_line = exp_config.get('cell_line', 'Unknown')
    peaks_file = Path(exp_config['peaks_file'])
    metadata_file = Path(exp_config['metadata_file'])

    if not peaks_file.exists():
        return {
            'mark_type': mark_type,
            'cell_line': cell_line,
            'success': False,
            'error': f'Peaks file not found: {peaks_file}'
        }

    if not metadata_file.exists():
        return {
            'mark_type': mark_type,
            'cell_line': cell_line,
            'success': False,
            'error': f'Metadata file not found: {metadata_file}'
        }

    # Read metadata to build command arguments
    with open(metadata_file, encoding="utf-8") as f:
        metadata = json.load(f)

    experiment_name = f"{mark_type}_{cell_line}_{metadata.get('encode_accession', 'TEST')}"

    # Build command using individual arguments (shell=False, avoids command injection).
    cmd = [
        'python3', str(_IMPORT_SCRIPT),
        '--input', str(peaks_file),
        '--mark-type', mark_type,
        '--species', 'human',
        '--experiment-name', experiment_name,
        '--batch-size', str(options.get('batch_size', 10000)),
        '--db-host', str(db_options['host']),
        '--db-port', str(db_options['port']),
        '--db-name', str(db_options['name']),
        '--db-user', str(db_options['user']),
    ]

    if options.get('compute_associations'):
        cmd.append('--compute-associations')
        if options.get('associations_flanking') is not None:
            cmd.extend(['--associations-flanking', str(options['associations_flanking'])])
        if options.get('associations_promoter_window') is not None:
            cmd.extend(['--associations-promoter-window', str(options['associations_promoter_window'])])

    # Add metadata fields as command arguments
    if metadata.get('cell_type'):
        cmd.extend(['--cell-type', metadata['cell_type']])
    if metadata.get('tissue_type'):
        cmd.extend(['--tissue-type', metadata['tissue_type']])
    if metadata.get('cell_line'):
        cmd.extend(['--cell-line', metadata['cell_line']])
    if metadata.get('encode_accession'):
        cmd.extend(['--accession', metadata['encode_accession']])
    if metadata.get('source_database'):
        cmd.extend(['--source', metadata['source_database']])
    if metadata.get('peak_type'):
        cmd.extend(['--format', 'broadPeak' if metadata['peak_type'] == 'broad' else 'narrowPeak'])

    # Execute import
    print(f'\n[{mark_type} / {cell_line}] Starting import...')
    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes timeout
        )

        elapsed = time.time() - start_time

        if result.returncode == 0:
            # Parse output to get peak count
            output_lines = result.stdout.split('\n')
            peak_count = 0
            for line in output_lines:
                if 'Imported' in line and 'peaks' in line:
                    try:
                        peak_count = int(''.join(filter(str.isdigit, line.split('Imported')[1].split('peaks')[0])))
                    except (ValueError, IndexError):
                        pass

            print(f'[{mark_type} / {cell_line}] ✓ Completed in {elapsed:.1f}s ({peak_count} peaks)')

            return {
                'mark_type': mark_type,
                'cell_line': cell_line,
                'success': True,
                'peak_count': peak_count,
                'elapsed_time': elapsed,
            }
        else:
            print(f'[{mark_type} / {cell_line}] ✗ Failed: {result.stderr[:200]}')
            return {
                'mark_type': mark_type,
                'cell_line': cell_line,
                'success': False,
                'error': result.stderr[:500]
            }

    except subprocess.TimeoutExpired:
        print(f'[{mark_type} / {cell_line}] ✗ Timeout (>10 minutes)')
        return {
            'mark_type': mark_type,
            'cell_line': cell_line,
            'success': False,
            'error': 'Timeout'
        }
    except Exception as e:
        print(f'[{mark_type} / {cell_line}] ✗ Error: {e}')
        return {
            'mark_type': mark_type,
            'cell_line': cell_line,
            'success': False,
            'error': str(e)
        }


def batch_import(
    config_file: Path,
    parallel: int = 1,
    *,
    db_host: str,
    db_port: int,
    db_name: str,
    db_user: str,
):
    """
    Import multiple experiments in parallel.

    Args:
        config_file: Path to JSON configuration file
        parallel: Number of parallel imports (default: 1 for sequential)
    """
    with open(config_file, encoding="utf-8") as f:
        config = json.load(f)

    experiments = config.get('experiments', [])
    options = config.get('options', {})
    db_options = {
        "host": db_host,
        "port": db_port,
        "name": db_name,
        "user": db_user,
    }

    if not experiments:
        print('Error: No experiments in configuration file')
        return 1

    print('='*60)
    print('Batch ChIP-seq Import')
    print('='*60)
    print(f'Config file: {config_file}')
    print(f'Total experiments: {len(experiments)}')
    print(f'Parallel workers: {parallel}')
    print(f'Options: {options}')

    # Import experiments
    results = []

    if parallel == 1:
        # Sequential import
        for i, exp in enumerate(experiments, 1):
            print(f'\n--- Experiment {i}/{len(experiments)} ---')
            result = import_single_experiment(exp, options, db_options)
            results.append(result)
    else:
        # Parallel import
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {
                executor.submit(import_single_experiment, exp, options, db_options): exp
                for exp in experiments
            }

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

    # Summary
    print(f'\n{"="*60}')
    print('Import Summary')
    print('='*60)

    success_count = sum(1 for r in results if r['success'])
    failed_count = len(results) - success_count
    total_peaks = sum(r.get('peak_count', 0) for r in results if r['success'])

    print(f'Successful: {success_count}/{len(results)}')
    print(f'Failed: {failed_count}')
    print(f'Total peaks imported: {total_peaks:,}')

    if success_count > 0:
        avg_time = sum(r.get('elapsed_time', 0) for r in results if r['success']) / success_count
        print(f'Avg time per experiment: {avg_time:.1f}s')

    # List successful imports
    print('\n✓ Successful imports:')
    for r in results:
        if r['success']:
            print(f"  - {r['mark_type']:10s} / {r['cell_line']:10s} ({r.get('peak_count', 0):,} peaks)")

    # List failures
    if failed_count > 0:
        print('\n✗ Failed imports:')
        for r in results:
            if not r['success']:
                print(f"  - {r['mark_type']:10s} / {r['cell_line']:10s} - {r.get('error', 'Unknown')[:80]}")

    # Refresh materialized views
    if success_count > 0:
        print(f'\n{"="*60}')
        print('Refreshing materialized views...')
        print('='*60)

        refresh_sql = (
            "REFRESH MATERIALIZED VIEW mv_chipseq_mark_stats; "
            "REFRESH MATERIALIZED VIEW mv_gene_mark_summary; "
            "SELECT 'Materialized views refreshed' AS status;"
        )

        try:
            subprocess.run(
                [
                    "psql",
                    "-h",
                    db_options["host"],
                    "-p",
                    str(db_options["port"]),
                    "-U",
                    db_options["user"],
                    "-d",
                    db_options["name"],
                    "-c",
                    refresh_sql,
                ],
                check=True,
                text=True,
            )
            print('✓ Materialized views refreshed')
        except Exception as e:
            print(f'⚠️  Warning: Failed to refresh materialized views: {e}')

    print('\n✨ Batch import complete!')
    print(f'   Success rate: {success_count}/{len(results)} ({100*success_count/len(results):.1f}%)')

    return 0 if failed_count == 0 else 1


def parse_args():
    parser = argparse.ArgumentParser(description='Batch import ChIP-seq experiments')
    parser.add_argument('config_file', help='Path to batch import JSON config file')
    parser.add_argument('--parallel', type=int, default=1,
                        help='Number of parallel imports (default: 1 for sequential)')
    parser.add_argument(
        '--db-host',
        default=os.getenv("DB_HOST", "localhost"),
        help='Database host (default: env DB_HOST or localhost)',
    )
    parser.add_argument(
        '--db-port',
        type=int,
        default=int(os.getenv("DB_PORT", "5432")),
        help='Database port (default: env DB_PORT or 5432)',
    )
    parser.add_argument(
        '--db-name',
        default=os.getenv("DB_NAME", "lncrna_production"),
        help='Database name (default: env DB_NAME or lncrna_production)',
    )
    parser.add_argument(
        '--db-user',
        default=os.getenv("DB_USER", "amax"),
        help='Database user (default: env DB_USER or amax)',
    )
    return parser.parse_args()


def main():
    args = parse_args()

    config_file = Path(args.config_file)

    if not config_file.exists():
        print(f'Error: Config file not found: {config_file}')
        return 1

    return batch_import(
        config_file,
        args.parallel,
        db_host=args.db_host,
        db_port=args.db_port,
        db_name=args.db_name,
        db_user=args.db_user,
    )


if __name__ == '__main__':
    exit(main())
